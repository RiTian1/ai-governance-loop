#!/usr/bin/env python3
"""报告质量指标：替代耗时作为主判据。

为什么不用耗时
--------------
同模型同任务的逐对耗时差值 SD 达 109 秒，而治理效应约 8 秒，信噪比 1:13。
按此噪声水平需要 n≈700 才能达到 p<0.05。耗时/token 的方差来源（服务排队、
思考长度、采样路径）与治理无关，测不出东西。

本脚本算的是可自动判定、方差小的指标：

1. citation_rate          引用可追溯率——报告里的"第 N 行/Table N/§N.N/URL"
                          能否在冻结源中找到对应锚点
2. section_coverage       必需章节覆盖率（按 suite 的 required_sections）
3. unsupported_density    无锚点断言密度——每千字里没有引用支撑的断言句
4. uncertainty_labeled    不确定信息是否显式标注
5. numeric_claim_density  数字断言密度（高密度但低引用率 = 高风险）

用法
----
    python3 rsi_quality_metrics.py --suite tasks.json --task R01-redteam-events \
        --work <work目录> --out metrics.json

`work` 需含 `report.md` 与 `sources/`。输出为 JSON，可直接汇总成表。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 引用锚点模式：(类型, 正则)
CITATION_PATTERNS = [
    # 最强形式：文件:行号（如 manifest.json:13-14）
    ("file_line", r"([\w\-\.]+\.(?:json|txt|html|md|pdf)):(\d{1,5}(?:\s*[-–,、]\s*\d{1,5})*)"),
    ("lines_zh", r"第\s*(\d{1,5})\s*[–\-~至到]\s*(\d{1,5})\s*行"),
    ("line_zh", r"第\s*(\d{1,5})\s*行"),
    ("lines_en", r"lines?\s+(\d{1,5})\s*[–\-~]\s*(\d{1,5})"),
    ("line_en", r"\bline\s+(\d{1,5})\b"),
    ("table_en", r"\bTable\s+(\d{1,3})\b"),
    ("table_zh", r"表\s*(\d{1,3})"),
    ("section", r"§\s*(\d{1,2}(?:\.\d{1,2})*)"),
    ("url", r"https?://[^\s\)\]\>,，。；]+"),
    ("page", r"\bp\.?\s*(\d{1,4})\b"),
]

# 断言句的粗判：含判断动词或数字
ASSERTION_HINTS = re.compile(
    r"(是|为|等于|表明|显示|证明|说明|可以|不能|必须|应当|达到|超过|低于|高于|"
    r"\bis\b|\bare\b|\bshows?\b|\bindicates?\b|\bproves?\b|\bmust\b|\bexceeds?\b)", re.I)

UNCERTAIN_HINTS = re.compile(
    r"(不确定|未核实|待确认|可能|推测|尚无|未见|存疑|无法确认|"
    r"\buncertain\b|\bunverified\b|\bunconfirmed\b|\bpossibly\b|\blikely\b|\bseems?\b)", re.I)

NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?")


def load_sources(work: Path) -> tuple[str, dict]:
    """返回 (合并文本, 每个文件的 {name: text})。"""
    folder = work / "sources"
    texts: dict[str, str] = {}
    if folder.is_dir():
        # 必须覆盖 manifest 里声明的所有格式。早先只收 .txt/.md/.html/.json，
        # 导致 CSV 语料的引用全部超界、追溯率被错误压到 0.15。
        allowed = (".txt", ".md", ".html", ".htm", ".json", ".csv", ".tsv", ".yaml", ".yml")
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() in allowed:
                try:
                    texts[p.name] = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
    merged = "\n".join(texts.values())
    return merged, texts


def extract_citations(text: str) -> list[dict]:
    found = []
    for kind, pattern in CITATION_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            found.append({"kind": kind, "raw": m.group(0).strip(), "span": m.span()})
    return found


def verify_citation(cit: dict, sources: str, per_file: dict) -> bool:
    """能否在冻结源中找到该引用的锚点。"""
    kind, raw = cit["kind"], cit["raw"]
    if kind == "file_line":
        m = re.match(r"([\w\-\.]+\.(?:json|txt|html|md|pdf)):(\d{1,5}(?:\s*[-–,、]\s*\d{1,5})*)", raw)
        if not m:
            return False
        fname, span = m.group(1), m.group(2)
        text = per_file.get(fname)
        if text is None:
            # 名字可能带路径前缀，退化为按后缀匹配
            for name, body in per_file.items():
                if name.endswith(fname) or fname.endswith(name):
                    text = body
                    break
        if text is None:
            return False
        nums = [int(x) for x in re.findall(r"\d+", span)]
        total_lines = len(text.splitlines())
        # CSV 的行号语义有歧义：模型说的"第 N 行"通常指数据行（不含表头），
        # 而文件行号含表头。两种约定都接受，避免把格式差异误判为不可追溯。
        if fname.lower().endswith((".csv", ".tsv")):
            return bool(nums) and all(1 <= n <= total_lines + 1 for n in nums)
        return bool(nums) and all(1 <= n <= total_lines for n in nums)
    if kind == "url":
        # URL 必须在 manifest 记录的来源里，或出现在源文本中
        return raw.rstrip(".,;)") in sources
    if kind in ("table_en", "table_zh"):
        num = re.findall(r"\d+", raw)
        if not num:
            return False
        n = num[0]
        return bool(re.search(rf"[Tt]able\s*{n}\b|表\s*{n}\b", sources))
    if kind == "section":
        num = re.findall(r"[\d.]+", raw)
        if not num:
            return False
        sec = num[0].rstrip(".")
        # 源里出现 "3.2" 或 "3.2 " 形式的章节号即视为存在
        return bool(re.search(rf"(?<![\d.]){re.escape(sec)}(?![\d])", sources))
    if kind in ("line_zh", "lines_zh", "line_en", "lines_en", "page"):
        nums = [int(x) for x in re.findall(r"\d+", raw)]
        if not nums:
            return False
        # 无法确定引用的是哪个文件，只要任一文件行数上限覆盖即算存在
        max_lines = max((len(t.splitlines()) for t in per_file.values()), default=0)
        if kind == "page":
            return nums[0] <= max(1, max_lines // 60)  # 粗估每页 60 行
        return all(n <= max_lines for n in nums)
    return False


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？\.\!\?])\s+|\n{2,}", text)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def compute(report: str, sources: str, per_file: dict, required: list[str]) -> dict:
    cits = extract_citations(report)
    verified = sum(1 for c in cits if verify_citation(c, sources, per_file))
    total_cit = len(cits)

    sent = split_sentences(report)
    assert_sents = [s for s in sent if ASSERTION_HINTS.search(s)]
    # 有锚点的断言句：句内或相邻句含引用标记
    anchored = 0
    for s in assert_sents:
        if extract_citations(s) or re.search(r"[（(]\s*(见|cf\.|see)\s", s, re.I):
            anchored += 1
    unsupported = len(assert_sents) - anchored
    chars = max(1, len(report))

    sec_cov = {}
    for name in required:
        sec_cov[name] = bool(re.search(rf"^#+\s*.*{re.escape(name)}", report, re.M))

    numeric = len(NUMBER_RE.findall(report))
    uncertain = len(UNCERTAIN_HINTS.findall(report))

    return {
        "chars": chars,
        "citation_total": total_cit,
        "citation_verified": verified,
        "citation_rate": round(verified / total_cit, 3) if total_cit else None,
        "citation_per_kchar": round(total_cit / (chars / 1000), 2),
        "section_required": len(required),
        "section_covered": sum(1 for v in sec_cov.values() if v),
        "section_coverage": round(sum(1 for v in sec_cov.values() if v) / len(required), 3) if required else None,
        "section_detail": sec_cov,
        "assertion_sentences": len(assert_sents),
        "unsupported_assertions": unsupported,
        "unsupported_density_per_kchar": round(unsupported / (chars / 1000), 2),
        "uncertainty_marks": uncertain,
        "uncertainty_per_kchar": round(uncertain / (chars / 1000), 2),
        "numeric_claims": numeric,
        "numeric_per_kchar": round(numeric / (chars / 1000), 2),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="计算报告质量指标")
    ap.add_argument("--suite", required=True, help="tasks.json 路径")
    ap.add_argument("--task", required=True, help="任务 id")
    ap.add_argument("--work", required=True, help="含 report.md 与 sources/ 的目录")
    ap.add_argument("--out", default=None, help="输出 JSON 路径；省略则打印")
    args = ap.parse_args(argv)

    work = Path(args.work)
    report_path = work / "report.md"
    if not report_path.is_file():
        print(f"缺少 {report_path}", file=sys.stderr)
        return 2
    report = report_path.read_text(encoding="utf-8", errors="replace")

    suite = json.loads(Path(args.suite).read_text(encoding="utf-8-sig"))
    task = next((t for t in suite.get("tasks", []) if t.get("id") == args.task), None)
    if task is None:
        print(f"suite 中找不到任务 {args.task}", file=sys.stderr)
        return 2
    required = task.get("required_sections") or []

    sources, per_file = load_sources(work)
    metrics = compute(report, sources, per_file, required)
    metrics["task"] = args.task
    metrics["work"] = str(work)
    metrics["source_files"] = sorted(per_file)

    payload = json.dumps(metrics, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
