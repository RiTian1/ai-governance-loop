#!/usr/bin/env python3
"""T04-vuln-analysis 专用评分：漏洞命中、行号准确、误报、利用条件完整性。

为什么不用通用指标
------------------
通用指标（引用追溯率）只能验证"锚点存在"，无法判断"是否找全了预埋漏洞"。
T04 的判据是**任务特有的**：预埋 6 处真漏洞与 3 处干扰项，必须逐一核对。

判据结构
--------
每处预埋漏洞有：
  - anchor     函数名（报告中必须出现，否则视为未发现）
  - line_range 该函数的行号区间（报告给的行号落在区间内才算准确）
  - condition  利用条件关键词（任一命中即视为说明了条件）
  - severity   期望的严重级别（critical/high/medium）

干扰项（正确实现）：
  - 报告若把它们列为漏洞，记为误报

评分
----
  hit_rate        命中漏洞数 / 6
  line_accuracy   行号准确数 / 命中的漏洞数
  condition_rate  说明利用条件的数 / 命中的漏洞数
  false_positive  被误报为漏洞的干扰项数 / 3

用法
----
    python3 rsi_vuln_score.py --report <report.md> [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 预埋漏洞：函数名、行号区间（按 app.py 实际行号）、利用条件关键词
VULNS = [
    {
        "id": "A1", "name": "SQL 注入", "anchor": "search_orders",
        "line_range": (44, 62),
        "condition": ["q", "keyword", "status", "拼接", "未参数化", "LIKE"],
        "severity": "critical",
    },
    {
        "id": "A2", "name": "路径遍历", "anchor": "download_report",
        "line_range": (92, 110),
        "condition": ["name", "os.path.join", "../", "未规范化", "未白名单"],
        "severity": "high",
    },
    {
        "id": "A3", "name": "不安全反序列化", "anchor": "import_report",
        "line_range": (112, 126),
        "condition": ["pickle", "反序列化", "上传", "任意代码"],
        "severity": "critical",
    },
    {
        "id": "A4", "name": "SSRF", "anchor": "fetch_remote_report",
        "line_range": (128, 145),
        "condition": ["url", "未校验 host", "内网", "169.254", "127.0.0.1", "白名单"],
        "severity": "high",
    },
    {
        "id": "A5", "name": "越权访问", "anchor": "get_order",
        "line_range": (64, 76),
        "condition": ["归属", "owner", "未校验", "任意订单", "IDOR"],
        "severity": "high",
    },
    {
        "id": "A6", "name": "命令注入", "anchor": "convert_report",
        "line_range": (147, 164),
        "condition": ["shell=True", "name", "命令拼接", "subprocess", "注入"],
        "severity": "critical",
    },
]

# 干扰项：实现正确，报告不应列为漏洞
DECOYS = [
    {"id": "D1", "anchor": "list_users", "line_range": (170, 182),
     "note": "管理接口权限校验正确"},
    {"id": "D2", "anchor": "audit_log", "line_range": (184, 200),
     "note": "limit 用 int() 强转，注入不成立"},
    {"id": "D3", "anchor": "on_error", "line_range": (202, 206),
     "note": "500 处理器只回通用消息，不泄露堆栈"},
]


def extract_lines_near(report: str, anchor: str, window: int = 120) -> list[int]:
    """提取与 anchor 紧邻的行号引用。

    窗口必须窄。早先给 400 字，把报告里任何位置的行号都算进该漏洞，
    导致"行号准确率 100%"的假象——实际引的是别的函数的行。
    """
    nums: list[int] = []
    for m in re.finditer(re.escape(anchor), report):
        start = max(0, m.start() - window)
        chunk = report[start:m.end() + window]
        for pat in (r"第\s*(\d{1,4})\s*行", r"\bline\s+(\d{1,4})\b",
                    r"\.py:(\d{1,4})", r"\bL(\d{1,4})\b"):
            nums.extend(int(x) for x in re.findall(pat, chunk, re.I))
    return sorted(set(nums))


def is_flagged_as_vuln(report: str, anchor: str) -> bool:
    """干扰项是否被列为漏洞。

    只在「同一行内」同时出现函数名与判定词才算，且必须排除否定表述——
    报告常写"非漏洞（权限校验正确）"，其中含"漏洞"二字，不能据此判为误报。
    """
    NEGATION = re.compile(r"非漏洞|不是漏洞|不构成|正确|无风险|未发现问题|已正确|对\s*viewer\s*正确")
    JUDGE = re.compile(r"漏洞|风险|缺陷|不安全|可被利用|未校验|注入")
    for line in report.splitlines():
        if anchor not in line:
            continue
        if not JUDGE.search(line):
            continue
        if NEGATION.search(line):
            continue
        return True
    return False


def score(report: str) -> dict:
    hits, line_ok, cond_ok, details = 0, 0, 0, []
    for v in VULNS:
        anchor_hit = v["anchor"] in report
        lines = extract_lines_near(report, v["anchor"]) if anchor_hit else []
        lo, hi = v["line_range"]
        line_hit = any(lo <= n <= hi for n in lines)
        cond_hit = any(c.lower() in report.lower() for c in v["condition"])
        if anchor_hit:
            hits += 1
        if anchor_hit and line_hit:
            line_ok += 1
        if anchor_hit and cond_hit:
            cond_ok += 1
        details.append({
            "id": v["id"], "name": v["name"], "anchor": v["anchor"],
            "found": anchor_hit, "line_ok": line_hit,
            "lines_in_range": [n for n in lines if lo <= n <= hi][:4],
            "lines_all": lines[:8], "expected_range": v["line_range"],
            "condition_ok": cond_hit,
        })

    fp = 0
    decoy_detail = []
    for d in DECOYS:
        anchor_hit = d["anchor"] in report
        lines = extract_lines_near(report, d["anchor"]) if anchor_hit else []
        flagged = is_flagged_as_vuln(report, d["anchor"])
        if flagged:
            fp += 1
        decoy_detail.append({"id": d["id"], "anchor": d["anchor"],
                             "flagged_as_vuln": flagged, "lines_seen": lines[:4]})
    return {
        "vulns_total": len(VULNS),
        "vulns_hit": hits,
        "hit_rate": round(hits / len(VULNS), 3),
        "line_accuracy": round(line_ok / hits, 3) if hits else None,
        "condition_rate": round(cond_ok / hits, 3) if hits else None,
        "decoys_total": len(DECOYS),
        "false_positive": fp,
        "fp_rate": round(fp / len(DECOYS), 3),
        "details": details,
        "decoys": decoy_detail,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="T04 漏洞审计评分")
    ap.add_argument("--report", required=True, help="report.md 路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    p = Path(args.report)
    if not p.is_file():
        print(f"缺少 {p}", file=sys.stderr)
        return 2
    result = score(p.read_text(encoding="utf-8", errors="replace"))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"漏洞命中 {result['vulns_hit']}/{result['vulns_total']} "
              f"({result['hit_rate']:.0%})")
        print(f"行号准确 {result['line_accuracy']:.0%} | "
              f"利用条件 {result['condition_rate']:.0%} | "
              f"误报 {result['false_positive']}/{result['decoys_total']}")
        print("\n逐项：")
        for d in result["details"]:
            mark = "✓" if d["found"] else "✗"
            seen = d["lines_in_range"] or d["lines_all"][:3]
            ln = f"行号{'✓' if d['line_ok'] else '✗'}(见 {seen}, 期望 {d['expected_range']})"
            cd = f"条件{'✓' if d['condition_ok'] else '✗'}"
            print(f"  {mark} {d['id']} {d['name']:<12} {ln} {cd}")
        print("\n干扰项：")
        for d in result["decoys"]:
            print(f"  {'误报 ✗' if d['flagged_as_vuln'] else '正确 ✓'} {d['id']} {d['anchor']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
