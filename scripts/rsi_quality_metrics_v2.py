#!/usr/bin/env python3
"""报告质量指标 v2：修正引用漏计缺陷。

v1 的问题
---------
`rsi_quality_metrics.py` 的 `file_line` 模式要求引用必须带扩展名：

    r"([\\w\\-\\.]+\\.(?:json|txt|html|md|pdf)):(\\d{1,5}...)"

实测报告里大量引用写成裸 basename：

    extracted:463-464      html:265      manifest:13

这些既不进 `citation_total`，也不进 `citation_verified`。R01 十轮里
r6 gov 有 93 处裸引用，v1 只识别到 5 处（验证 0 处），追溯率被判 0.000。
r3 gov 有 109 处裸引用，v1 只识别到 1 处。

漏计在两组之间、不同轮次之间完全不成比例（r1 gov 漏 27、r6 gov 漏 93、
r10 base 漏 206），所以 v1 的 citation_rate 测的不是"有没有引用"，
而是"引用写法是否符合某个特定格式"。

**连带影响**：`unsupported_density` 用 v1 的 `extract_citations` 判断
"句子是否有锚点"。裸 basename 引用被判为无锚点，于是用了这种写法的报告
会被多算"无支撑断言"。这个指标也被污染了，只是方向相反。

v2 的做法
---------
两套并行计算，v1 字段原样保留（可比性）：

- `citation_rate` / `unsupported_density_per_kchar`   ← v1 严格口径
- `citation_rate_loose` / `unsupported_density_loose_per_kchar`  ← 宽松口径

宽松口径新增一条模式：首字符为字母/下划线的裸 basename + 行号，
且验证时按"文件名主体（stem）"匹配源文件（`extracted` → `extracted.txt`）。

用法与 v1 一致：
    python3 rsi_quality_metrics_v2.py --suite tasks.json --task R01-redteam-events \
        --work <work目录> --out metrics-v2.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---- v1 原样保留 ----
CITATION_PATTERNS = [
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

# ---- v2 新增：裸 basename + 行号 ----
# 首字符必须是字母或下划线，避免把 "15:05" 这类时刻当成引用；
# 前面不能是 / 或单词字符，避免把 URL 里的片段算进来。
LOOSE_FILE_LINE = re.compile(
    r"(?<![\w/])([A-Za-z_][\w\-\.]{0,60}):(\d{1,5}(?:\s*[-–,、]\s*\d{1,5})*)"
)

ASSERTION_HINTS = re.compile(
    r"(是|为|等于|表明|显示|证明|说明|可以|不能|必须|应当|达到|超过|低于|高于|"
    r"\bis\b|\bare\b|\bshows?\b|\bindicates?\b|\bproves?\b|\bmust\b|\bexceeds?\b)", re.I)

UNCERTAIN_HINTS = re.compile(
    r"(不确定|未核实|待确认|可能|推测|尚无|未见|存疑|无法确认|"
    r"\buncertain\b|\bunverified\b|\bunconfirmed\b|\bpossibly\b|\blikely\b|\bseems?\b)", re.I)

NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?")


def load_sources(work: Path) -> tuple[str, dict]:
    folder = work / "sources"
    texts: dict[str, str] = {}
    if folder.is_dir():
        allowed = (".txt", ".md", ".html", ".htm", ".json", ".csv", ".tsv", ".yaml", ".yml")
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() in allowed:
                try:
                    texts[p.name] = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
    return "\n".join(texts.values()), texts


def _stem(name: str) -> str:
    return name.rsplit(".", 1)[0] if "." in name else name


def resolve_source(fname: str, per_file: dict) -> str | None:
    """把引用里的文件名映射到源文本。先精确、再按 stem、最后按后缀。"""
    if fname in per_file:
        return per_file[fname]
    stem = _stem(fname)
    for name, body in per_file.items():
        if _stem(name) == stem:
            return body
    for name, body in per_file.items():
        if name.endswith(fname) or fname.endswith(name):
            return body
    return None


def _line_ok(body: str, span: str, is_csv: bool) -> bool:
    nums = [int(x) for x in re.findall(r"\d+", span)]
    if not nums:
        return False
    total = len(body.splitlines())
    hi = total + 1 if is_csv else total
    return all(1 <= n <= hi for n in nums)


def extract_citations_strict(text: str) -> list[dict]:
    found = []
    for kind, pattern in CITATION_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            found.append({"kind": kind, "raw": m.group(0).strip(), "span": m.span()})
    return found


def extract_citations_loose(text: str) -> list[dict]:
    """strict 的全部，加上"裸 basename:行号"里 strict 没覆盖到的部分。"""
    found = extract_citations_strict(text)
    taken = [(c["span"][0], c["span"][1]) for c in found]
    for m in LOOSE_FILE_LINE.finditer(text):
        s, e = m.span()
        # 与已是 file_line 的片段重叠则跳过（避免重复计数）
        if any(not (e <= a or s >= b) for a, b in taken):
            continue
        # 已经带扩展名的交给 strict 处理
        if re.match(r"[\w\-\.]+\.(?:json|txt|html|md|pdf|csv|tsv|yaml|yml):",
                    m.group(0), re.I):
            continue
        found.append({"kind": "file_line_loose", "raw": m.group(0).strip(), "span": (s, e)})
    return found


def verify_citation(cit: dict, sources: str, per_file: dict) -> bool:
    kind, raw = cit["kind"], cit["raw"]
    if kind in ("file_line", "file_line_loose"):
        if kind == "file_line":
            m = re.match(r"([\w\-\.]+\.(?:json|txt|html|md|pdf)):(\d{1,5}(?:\s*[-–,、]\s*\d{1,5})*)", raw)
        else:
            m = re.match(r"([A-Za-z_][\w\-\.]{0,60}):(\d{1,5}(?:\s*[-–,、]\s*\d{1,5})*)", raw)
        if not m:
            return False
        fname, span = m.group(1), m.group(2)
        body = resolve_source(fname, per_file)
        if body is None:
            return False
        return _line_ok(body, span, fname.lower().endswith((".csv", ".tsv")))
    if kind == "url":
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
        return bool(re.search(rf"(?<![\d.]){re.escape(sec)}(?![\d])", sources))
    if kind in ("line_zh", "lines_zh", "line_en", "lines_en", "page"):
        nums = [int(x) for x in re.findall(r"\d+", raw)]
        if not nums:
            return False
        max_lines = max((len(t.splitlines()) for t in per_file.values()), default=0)
        if kind == "page":
            return nums[0] <= max(1, max_lines // 60)
        return all(n <= max_lines for n in nums)
    return False


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？\.\!\?])\s+|\n{2,}", text)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def _density(unsupported: int, chars: int) -> float:
    return round(unsupported / (chars / 1000), 2)


def compute(report: str, sources: str, per_file: dict, required: list[str]) -> dict:
    cits_s = extract_citations_strict(report)
    cits_l = extract_citations_loose(report)
    ver_s = sum(1 for c in cits_s if verify_citation(c, sources, per_file))
    ver_l = sum(1 for c in cits_l if verify_citation(c, sources, per_file))

    sent = split_sentences(report)
    assert_sents = [s for s in sent if ASSERTION_HINTS.search(s)]

    def count_unsupported(extractor) -> int:
        anchored = 0
        for s in assert_sents:
            if extractor(s) or re.search(r"[（(]\s*(见|cf\.|see)\s", s, re.I):
                anchored += 1
        return len(assert_sents) - anchored

    unsup_s = count_unsupported(extract_citations_strict)
    unsup_l = count_unsupported(extract_citations_loose)

    chars = max(1, len(report))
    sec_cov = {n: bool(re.search(rf"^#+\s*.*{re.escape(n)}", report, re.M)) for n in required}
    covered = sum(1 for v in sec_cov.values() if v)

    return {
        "chars": chars,
        # v1 口径（原样）
        "citation_total": len(cits_s),
        "citation_verified": ver_s,
        "citation_rate": round(ver_s / len(cits_s), 3) if cits_s else None,
        "citation_per_kchar": round(len(cits_s) / (chars / 1000), 2),
        # v2 宽松口径
        "citation_total_loose": len(cits_l),
        "citation_verified_loose": ver_l,
        "citation_rate_loose": round(ver_l / len(cits_l), 3) if cits_l else None,
        "citation_per_kchar_loose": round(len(cits_l) / (chars / 1000), 2),
        "citation_missed_by_strict": len(cits_l) - len(cits_s),
        # 章节 / 断言
        "section_required": len(required),
        "section_covered": covered,
        "section_coverage": round(covered / len(required), 3) if required else None,
        "section_detail": sec_cov,
        "assertion_sentences": len(assert_sents),
        "unsupported_assertions": unsup_s,
        "unsupported_density_per_kchar": _density(unsup_s, chars),
        "unsupported_assertions_loose": unsup_l,
        "unsupported_density_loose_per_kchar": _density(unsup_l, chars),
        # 其余
        "uncertainty_marks": len(UNCERTAIN_HINTS.findall(report)),
        "uncertainty_per_kchar": round(len(UNCERTAIN_HINTS.findall(report)) / (chars / 1000), 2),
        "numeric_claims": len(NUMBER_RE.findall(report)),
        "numeric_per_kchar": round(len(NUMBER_RE.findall(report)) / (chars / 1000), 2),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="计算报告质量指标 v2")
    ap.add_argument("--suite", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", default=None)
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
