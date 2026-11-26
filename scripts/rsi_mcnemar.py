#!/usr/bin/env python3
r"""McNemar 配对检验：治理让"任务达成"变多了还是变少了。

为什么不能用配对 t
------------------
交付型 benchmark 的主指标是二元「达成 / 未达成」，不是连续分数。
对二元配对数据用 t 检验会低估方差、给出虚高的显著性。

McNemar 只看**不一致对**（discordant pairs）：

|                | governance 成功 | governance 失败 |
|----------------|-----------------|-----------------|
| baseline 成功  | a               | **c**           |
| baseline 失败  | **b**           | d               |

只有 b 和 c 携带信息 —— a 和 d 是"两组一致"，对"谁更好"没有贡献。
原假设 H0：b 与 c 的期望相等（治理没有偏向）。

统计量
------
- 连续性校正：χ² = (|b − c| − 1)² / (b + c)，df=1
- p = erfc(sqrt(χ²/2))（χ² 分布 df=1 的生存函数）
- b + c < 25 时改用精确二项检验（双侧）

用法
----
    python scripts/rsi_mcnemar.py runs.json --task J3-code-audit
    python scripts/rsi_mcnemar.py runs.json --all

runs.json 格式：

    {"runs": [
      {"task": "J3-code-audit", "round": 1, "arm": "baseline",   "achieved": false},
      {"task": "J3-code-audit", "round": 1, "arm": "governance", "achieved": true},
      ...
    ]}
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def read_runs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    runs = data.get("runs") if isinstance(data, dict) else data
    if not isinstance(runs, list):
        raise ValueError("runs 必须是数组，或 {'runs': [...]}")
    return runs


def to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes", "pass", "achieved", "ok"}
    return False


def pair(runs: list[dict], task: str) -> list[tuple[bool | None, bool | None]]:
    buckets: dict[int, dict[str, bool]] = {}
    for r in runs:
        if task != "*" and r.get("task") != task:
            continue
        if r.get("achieved") is None:
            continue
        arm = (r.get("arm") or "").lower()
        if arm not in ("baseline", "governance"):
            continue
        buckets.setdefault(int(r["round"]), {})[arm] = to_bool(r["achieved"])
    out = []
    for rnd in sorted(buckets):
        b = buckets[rnd].get("baseline")
        g = buckets[rnd].get("governance")
        if b is None or g is None:
            continue
        out.append((b, g))
    return out


def binom_two_sided_p(b: int, c: int) -> float:
    """精确二项检验（双侧），H0: p=0.5。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # 双侧 = 2 * P(X <= k)，上限 1
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def mcnemar(pairs: list[tuple[bool, bool]]) -> dict:
    a = sum(1 for b, g in pairs if b and g)
    d = sum(1 for b, g in pairs if not b and not g)
    bb = sum(1 for b, g in pairs if not b and g)   # baseline 失败 → governance 成功（改善）
    cc = sum(1 for b, g in pairs if b and not g)   # baseline 成功 → governance 失败（退化）
    n = len(pairs)

    disc = bb + cc
    if disc == 0:
        return {
            "n_pairs": n, "a_both_pass": a, "d_both_fail": d,
            "b_gov_better": bb, "c_gov_worse": cc,
            "discordant": 0,
            "chi2": 0.0, "p_value": 1.0, "test": "none",
            "note": "两组完全一致（无 discordant 对），无法判断优劣",
            "direction": "tie",
            "pass_rate_baseline": round((a + cc) / n, 3) if n else None,
            "pass_rate_governance": round((a + bb) / n, 3) if n else None,
        }

    chi2 = (abs(bb - cc) - 1) ** 2 / disc if disc > 0 else 0.0
    chi2 = max(0.0, chi2)
    p_chi = math.erfc(math.sqrt(chi2 / 2)) if chi2 > 0 else 1.0

    use_exact = disc < 25
    p = binom_two_sided_p(bb, cc) if use_exact else p_chi
    test = "exact_binomial" if use_exact else "chi2_continuity_corrected"

    if p < 0.05:
        direction = "governance_better" if bb > cc else "governance_worse"
    else:
        direction = "no_significant_difference"

    return {
        "n_pairs": n,
        "a_both_pass": a,
        "d_both_fail": d,
        "b_gov_better": bb,
        "c_gov_worse": cc,
        "discordant": disc,
        "chi2": round(chi2, 3),
        "p_value": round(p, 4),
        "test": test,
        "direction": direction,
        "pass_rate_baseline": round((a + cc) / n, 3) if n else None,
        "pass_rate_governance": round((a + bb) / n, 3) if n else None,
    }


def render(task: str, res: dict) -> str:
    lines = [f"\n### {task}（配对 n={res['n_pairs']}）\n"]
    lines.append("| | governance 达成 | governance 未达成 |")
    lines.append("|---|---:|---:|")
    lines.append(f"| **baseline 达成** | {res['a_both_pass']} | {res['c_gov_worse']} |")
    lines.append(f"| **baseline 未达成** | {res['b_gov_better']} | {res['d_both_fail']} |")
    lines.append("")
    lines.append(
        f"- 达成率：baseline {res['pass_rate_baseline']:.1%} → "
        f"governance {res['pass_rate_governance']:.1%}"
    )
    lines.append(f"- Discordant：治理改善 {res['b_gov_better']} 轮 / 退化 {res['c_gov_worse']} 轮")
    if res["test"] == "none":
        lines.append(f"- {res['note']}")
    else:
        lines.append(
            f"- χ²={res['chi2']}，p={res['p_value']}（{res['test']}）→ **{res['direction']}**"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="McNemar 配对检验（二元达成）")
    ap.add_argument("runs", help="逐轮结果 JSON")
    ap.add_argument("--task", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非表格")
    args = ap.parse_args(argv)

    runs = read_runs(Path(args.runs))
    if args.all:
        tasks = sorted({r.get("task") for r in runs if r.get("task")})
    elif args.task:
        tasks = [args.task]
    else:
        print("需要 --task 或 --all", file=sys.stderr)
        return 2

    results = {}
    for t in tasks:
        ps = pair(runs, t)
        if not ps:
            continue
        results[t] = mcnemar(ps)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for t, res in results.items():
            print(render(t, res))
        if not results:
            print("(无可用配对数据)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
