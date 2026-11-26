#!/usr/bin/env python3
"""RSI 配对实验统计：输入逐轮指标 JSON，输出配对比较表。

为什么单独一个脚本
------------------
这一轮实验里反复出现同一个问题：每次统计都手写一遍 t 检验，口径稍有不同
（用哪个字段、缺值怎么处理、比的是均值还是配对差），结果对不上。
把口径固定下来，避免"换个脚本就换个结论"。

口径
----
- 配对单位是"轮次"（同一轮的 baseline vs governance）
- 差值定义：governance − baseline，正数表示治理组更高
- 配对 t：mean(diff) / (sd(diff) / sqrt(n))，只统计两组都有值的轮次
- 同时给出方向一致数（diff > 0 的轮次数 / 有效配对数），不看均值说服力

用法
----
    python3 rsi_pair_stats.py runs.json --task R01-redteam-events --fields citation_rate,elapsed
    python3 rsi_pair_stats.py runs.json --all
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

# 字段 → (中文名, 小数位)
FIELD_LABELS = {
    "citation_rate": ("追溯率(严格)", 3),
    "citation_rate_loose": ("追溯率(宽松)", 3),
    "citation_total": ("引用数", 0),
    "citation_missed_by_strict": ("严格口径漏计", 0),
    "unsupported_density_per_kchar": ("无支撑密度(严格)", 2),
    "unsupported_density_loose_per_kchar": ("无支撑密度(宽松)", 2),
    "section_coverage": ("章节覆盖", 3),
    "uncertainty_per_kchar": ("不确定标注/千字", 2),
    "numeric_per_kchar": ("数字密度/千字", 2),
    "chars": ("报告字数", 0),
    "elapsed_seconds": ("耗时 s", 0),
    "input_tokens": ("input token", 0),
    "output_tokens": ("output token", 0),
    "steps": ("步数", 1),
}


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("runs", [])
    return data


def pair(rows: list[dict], task: str) -> list[tuple[dict, dict, int]]:
    """按 (task, round) 配对，返回 [(baseline, governance, round)]。"""
    buckets: dict[int, dict[str, dict]] = {}
    for r in rows:
        if task != "*" and r.get("task") != task:
            continue
        buckets.setdefault(int(r["round"]), {})[r["arm"]] = r
    out = []
    for rnd in sorted(buckets):
        b, g = buckets[rnd].get("baseline"), buckets[rnd].get("governance")
        if b and g:
            out.append((b, g, rnd))
    return out


def paired_stats(pairs, key):
    """返回 (base均值, gov均值, 均值差, 差%, t, gov更高轮数, 有效n)。"""
    vals = []
    for b, g, _ in pairs:
        bv, gv = b.get(key), g.get(key)
        if bv is None or gv is None:
            continue
        vals.append((float(bv), float(gv)))
    if not vals:
        return None
    base = statistics.mean(v[0] for v in vals)
    gov = statistics.mean(v[1] for v in vals)
    diffs = [v[1] - v[0] for v in vals]
    sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    t = statistics.mean(diffs) / (sd / math.sqrt(len(diffs))) if sd else 0.0
    higher = sum(1 for d in diffs if d > 0)
    pct = (gov - base) / abs(base) * 100 if base else float("nan")
    return base, gov, statistics.mean(diffs), pct, t, higher, len(vals)


def render(rows: list[dict], tasks: list[str], fields: list[str]) -> str:
    out = []
    for task in tasks:
        pairs = pair(rows, task)
        if not pairs:
            continue
        out.append(f"\n### {task}（配对 n={len(pairs)}）\n")
        header = ["指标", "baseline", "governance", "差%", "配对 t", "gov更高"]
        out.append("| " + " | ".join(header) + " |")
        out.append("|" + "|".join(["---", "---:", "---:", "---:", "---:", "---:"]) + "|")
        for key in fields:
            st = paired_stats(pairs, key)
            if not st:
                continue
            base, gov, _, pct, t, higher, n = st
            label, dec = FIELD_LABELS.get(key, (key, 2))
            fmt = f"{{:,.{dec}f}}"
            mark = "**" if abs(t) >= 2 else ""
            out.append(
                f"| {label} | {fmt.format(base)} | {fmt.format(gov)} | "
                f"{mark}{pct:+.1f}%{mark} | {mark}{t:+.2f}{mark} | {higher}/{n} |"
            )
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RSI 配对实验统计")
    ap.add_argument("runs", help="逐轮指标 JSON")
    ap.add_argument("--task", default=None, help="任务 id；--all 时忽略")
    ap.add_argument("--all", action="store_true", help="所有任务分别出表")
    ap.add_argument("--fields", default=None, help="逗号分隔的字段名")
    args = ap.parse_args(argv)

    rows = load(Path(args.runs))
    default_fields = [
        "citation_rate", "citation_rate_loose",
        "unsupported_density_per_kchar", "unsupported_density_loose_per_kchar",
        "section_coverage", "chars", "elapsed_seconds", "input_tokens",
    ]
    if args.fields:
        fields = [f for f in args.fields.split(",") if f in FIELD_LABELS]
    else:
        fields = [f for f in default_fields if f in FIELD_LABELS]
    if not fields:
        fields = list(FIELD_LABELS)

    if args.all:
        tasks = sorted({r.get("task") for r in rows if r.get("task")})
    elif args.task:
        tasks = [args.task]
    else:
        print("需要 --task 或 --all", file=sys.stderr)
        return 2

    print(render(rows, tasks, fields))
    return 0


if __name__ == "__main__":
    sys.exit(main())
