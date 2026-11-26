#!/usr/bin/env python3
"""夜间队列结果汇总：把 status.tsv 与各组的 quality.json 汇成一份 Markdown。

设计意图
--------
用户睡前启动队列，早上看结论。所以汇总必须：

1. 全覆盖——每个任务、每个轮次、两个组都在表里，缺的显式标注为缺失
2. 按指标分类——效率类（count，方差小）与质量类（比例，可判定）分开
3. 给出配对统计——均值、中位数、逐对方向、粗算 t，并说明样本量是否足够
4. 诚实标注——样本不足、状态异常、指标缺失都要写出来，不做有利解读

用法
----
    python3 rsi_night_report.py --root /root/rsi-night \
        --suite tasks.json --out /root/rsi-night/report.md
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 指标分组：key -> (显示名, 单位, 是否越小越好)
EFFICIENCY = {
    "elapsed": ("耗时", "s", True),
    "steps": ("步数", "", True),
    "input": ("input token", "", True),
    "output": ("output token", "", False),
    "grep": ("grep 次数", "", True),
    "report_bytes": ("报告字节", "B", False),
}
QUALITY = {
    "citation_total": ("引用数", "", False),
    "citation_verified": ("可追溯引用", "", False),
    "citation_rate": ("追溯率", "", False),
    "section_coverage": ("章节覆盖", "", False),
    "unsupported_assertions": ("无支撑断言", "", True),
    "unsupported_density_per_kchar": ("无支撑/千字", "", True),
    "uncertainty_marks": ("不确定标注", "", False),
    "numeric_per_kchar": ("数字/千字", "", False),
}


def load_runs(root: Path) -> dict:
    """扫 root/<task>/r<N>/{out-<arm>/{init,resume}.json, <arm>/report.md, out-<arm>/quality.json}"""
    runs: dict = defaultdict(lambda: defaultdict(dict))
    for task_dir in sorted(root.iterdir()):
        if not task_dir.is_dir() or task_dir.name.startswith("_"):
            continue
        for round_dir in sorted(task_dir.glob("r*"), key=lambda p: int(p.name[1:]) if p.name[1:].isdigit() else 0):
            rnd = int(round_dir.name[1:]) if round_dir.name[1:].isdigit() else 0
            for arm in ("baseline", "governance"):
                out = round_dir / f"out-{arm}"
                work = round_dir / arm
                rec: dict = {"round": rnd, "arm": arm}
                init_p, resume_p = out / "init.json", out / "resume.json"
                if not resume_p.is_file():
                    rec["status"] = "missing"
                    runs[task_dir.name][rnd][arm] = rec
                    continue
                try:
                    resume = json.loads(resume_p.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    rec["status"] = "bad_json"
                    runs[task_dir.name][rnd][arm] = rec
                    continue
                init = {}
                if init_p.is_file():
                    try:
                        init = json.loads(init_p.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        init = {}
                tokens_r = resume.get("observed_tokens_lower_bound") or {}
                tokens_i = init.get("observed_tokens_lower_bound") or {}
                rec["status"] = resume.get("status") or "?"
                rec["elapsed"] = round((resume.get("elapsed_seconds") or 0) + (init.get("elapsed_seconds") or 0), 1)
                rec["steps"] = len(resume.get("step_timeline") or [])
                rec["input"] = (tokens_r.get("input") or 0) + (tokens_i.get("input") or 0)
                rec["output"] = (tokens_r.get("output") or 0) + (tokens_i.get("output") or 0)
                tc = resume.get("tool_counts") or {}
                rec["grep"] = tc.get("grep", 0)
                rp = work / "report.md"
                rec["report_bytes"] = rp.stat().st_size if rp.is_file() else 0
                qp = out / "quality.json"
                if qp.is_file():
                    try:
                        rec["quality"] = json.loads(qp.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        rec["quality"] = None
                else:
                    rec["quality"] = None
                runs[task_dir.name][rnd][arm] = rec
    return runs


def summarize(values: list) -> dict:
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return {"n": 0}
    mean = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    med = statistics.median(vals)
    return {"n": len(vals), "mean": mean, "sd": sd, "median": med,
            "min": min(vals), "max": max(vals)}


def paired(rows: list, key: str, get=lambda r, k: r.get(k)) -> dict:
    """配对差值统计。rows 为 [(base_rec, gov_rec), ...]"""
    diffs, pairs = [], 0
    for b, g in rows:
        vb, vg = get(b, key), get(g, key)
        if isinstance(vb, (int, float)) and isinstance(vg, (int, float)):
            diffs.append(vg - vb)
            pairs += 1
    if not diffs:
        return {"pairs": 0}
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    t = mean / (sd / len(diffs) ** 0.5) if sd else 0.0
    return {"pairs": pairs, "mean_diff": mean, "sd": sd, "t": t,
            "gov_higher": sum(1 for d in diffs if d > 0),
            "gov_lower": sum(1 for d in diffs if d < 0)}


def fmt(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}{unit}" if abs(v) < 100 else f"{v:,.0f}{unit}"
    return f"{v:,}{unit}" if isinstance(v, int) else str(v)


def build(root: Path, suite_path: Path) -> str:
    runs = load_runs(root)
    suite = {}
    if suite_path.is_file():
        try:
            data = json.loads(suite_path.read_text(encoding="utf-8-sig"))
            suite = {t["id"]: t for t in data.get("tasks", [])}
        except json.JSONDecodeError:
            suite = {}

    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# RSI 夜间队列汇总（{now}）\n")
    lines.append("> 由 `scripts/rsi_night_report.py` 自动生成。")
    lines.append("> 配对差值定义为 governance − baseline；正数表示治理组更高。\n")

    total_runs = sum(len(a) for t in runs.values() for a in t.values())
    lines.append(f"共扫到 **{total_runs}** 个组完成的记录，覆盖 **{len(runs)}** 个任务。\n")

    grand = []
    for task, rounds in runs.items():
        meta = suite.get(task, {})
        lines.append(f"\n## {task}")
        if meta.get("category"):
            lines.append(f"- 类别：`{meta['category']}`")
        if meta.get("required_sections"):
            lines.append(f"- 必需章节：{len(meta['required_sections'])} 个")

        rows = []
        lines.append("\n| 轮 | 组 | 状态 | 耗时 s | 步 | input | output | grep | 报告 B | 引用 | 追溯率 | 章节 |")
        lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for rnd in sorted(rounds):
            for arm in ("baseline", "governance"):
                rec = rounds[rnd].get(arm)
                if not rec:
                    continue
                q = rec.get("quality") or {}
                rate = q.get("citation_rate")
                rate_s = f"{rate:.3f}" if isinstance(rate, (int, float)) else "—"
                lines.append(
                    f"| {rnd} | {arm} | {rec.get('status','?')} | {fmt(rec.get('elapsed'))} | "
                    f"{fmt(rec.get('steps'))} | {fmt(rec.get('input'))} | {fmt(rec.get('output'))} | "
                    f"{fmt(rec.get('grep'))} | {fmt(rec.get('report_bytes'))} | "
                    f"{fmt(q.get('citation_total'))} | {rate_s} | {fmt(q.get('section_coverage'))} |")
            b, g = rounds[rnd].get("baseline"), rounds[rnd].get("governance")
            if b and g and b.get("status") != "missing" and g.get("status") != "missing":
                rows.append((b, g))

        if not rows:
            lines.append("\n_无成对数据_")
            continue

        lines.append(f"\n### 效率类（{task}，配对 n={len(rows)}）\n")
        lines.append("| 指标 | baseline 均值 | governance 均值 | 差 | 差% | 配对 t | gov 更高/更低 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for key, (name, unit, _) in EFFICIENCY.items():
            bvals = [r[0].get(key) for r in rows]
            gvals = [r[1].get(key) for r in rows]
            sb, sg = summarize(bvals), summarize(gvals)
            p = paired(rows, key)
            if not sb.get("n") or not sg.get("n"):
                continue
            diff = sg["mean"] - sb["mean"]
            pct = (diff / sb["mean"] * 100) if sb["mean"] else 0.0
            lines.append(f"| {name} | {fmt(sb['mean'], unit)} | {fmt(sg['mean'], unit)} | "
                         f"{diff:+,.1f}{unit} | {pct:+.1f}% | {p.get('t', 0):.2f} | "
                         f"{p.get('gov_higher',0)}/{p.get('gov_lower',0)} |")

        lines.append(f"\n### 质量类（{task}）\n")
        lines.append("| 指标 | baseline 均值 | governance 均值 | 差 | 配对 t | gov 更高/更低 |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for key, (name, unit, _) in QUALITY.items():
            bvals = [(r[0].get("quality") or {}).get(key) for r in rows]
            gvals = [(r[1].get("quality") or {}).get(key) for r in rows]
            sb, sg = summarize(bvals), summarize(gvals)
            if not sb.get("n") or not sg.get("n"):
                continue
            p = paired(rows, key, get=lambda r, k: (r.get("quality") or {}).get(k))
            diff = sg["mean"] - sb["mean"]
            lines.append(f"| {name} | {fmt(sb['mean'], unit)} | {fmt(sg['mean'], unit)} | "
                         f"{diff:+,.2f}{unit} | {p.get('t', 0):.2f} | "
                         f"{p.get('gov_higher',0)}/{p.get('gov_lower',0)} |")

        grand.extend(rows)

    if grand:
        lines.append("\n## 跨任务总览\n")
        lines.append("| 指标 | baseline 均值 | governance 均值 | 差% | 配对 n | 配对 t |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for key, (name, unit, _) in EFFICIENCY.items():
            bvals = [r[0].get(key) for r in grand]
            gvals = [r[1].get(key) for r in grand]
            if not any(isinstance(v, (int, float)) for v in bvals):
                continue
            sb, sg = summarize(bvals), summarize(gvals)
            p = paired(grand, key)
            if not sb.get("n") or not sg.get("n"):
                continue
            pct = (sg["mean"] - sb["mean"]) / sb["mean"] * 100 if sb["mean"] else 0
            lines.append(f"| {name} | {fmt(sb['mean'], unit)} | {fmt(sg['mean'], unit)} | "
                         f"{pct:+.1f}% | {p.get('pairs',0)} | {p.get('t',0):.2f} |")
        for key, (name, unit, _) in QUALITY.items():
            bvals = [(r[0].get("quality") or {}).get(key) for r in grand]
            gvals = [(r[1].get("quality") or {}).get(key) for r in grand]
            if not any(isinstance(v, (int, float)) for v in bvals):
                continue
            sb, sg = summarize(bvals), summarize(gvals)
            p = paired(grand, key, get=lambda r, k: (r.get("quality") or {}).get(k))
            if not sb.get("n") or not sg.get("n"):
                continue
            pct = (sg["mean"] - sb["mean"]) / sb["mean"] * 100 if sb["mean"] else 0
            lines.append(f"| {name} | {fmt(sb['mean'], unit)} | {fmt(sg['mean'], unit)} | "
                         f"{pct:+.1f}% | {p.get('pairs',0)} | {p.get('t',0):.2f} |")

    lines.append("\n## 读数须知\n")
    lines.append("1. **配对 t 仅作参考**。n<6 时 t 值不稳定，|t|<2 不应解读为「无差异」，")
    lines.append("   |t|>2 也不应解读为「已证实」。真正要看的是一致性（gov 更高/更低 的次数）。")
    lines.append("2. **状态列**若出现 `timeout` / `protocol_violation` / `artifact_review_required`，")
    lines.append("   该组数据不全，其指标不应参与比较。")
    lines.append("3. **引用类指标依赖源包**。`file:line` 引用只有在源文件确实含该行时才算可追溯；")
    lines.append("   合成语料（T02/T03）行数少，追溯率天然偏高，跨任务比较时应只看同任务内的组间差。")
    lines.append("4. **章节覆盖率有天花板**。若各任务普遍 1.0，该指标无区分度，改看引用与无支撑断言。")

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="汇总夜间队列结果")
    ap.add_argument("--root", default="/root/rsi-night")
    ap.add_argument("--suite", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"目录不存在: {root}", file=sys.stderr)
        return 2
    suite = Path(args.suite) if args.suite else root / "tasks.json"
    md = build(root, suite)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
