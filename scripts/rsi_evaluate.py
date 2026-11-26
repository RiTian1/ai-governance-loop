#!/usr/bin/env python3
"""Compare paired baseline/candidate long-task runs before promoting an agent change."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIELDS = ("task_id", "passed", "rework_steps", "recovery_minutes", "input_tokens", "critical_misses")
NUMERIC = FIELDS[2:]


def read(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of run records")
    result = {}
    for row in data:
        if not isinstance(row, dict) or any(key not in row for key in FIELDS):
            raise ValueError(f"{path}: each run needs {', '.join(FIELDS)}")
        task = row["task_id"]
        if not isinstance(task, str) or not task or task in result:
            raise ValueError(f"{path}: duplicate or invalid task_id")
        if type(row["passed"]) is not bool:
            raise ValueError(f"{path}: passed must be boolean")
        if any(type(row[key]) not in (int, float) or row[key] < 0 for key in NUMERIC):
            raise ValueError(f"{path}: numeric metrics must be nonnegative")
        result[task] = row
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--min-tasks", type=int, default=5)
    parser.add_argument("--max-token-growth", type=float, default=0.20)
    args = parser.parse_args()
    try:
        if args.min_tasks < 1 or args.max_token_growth < 0:
            raise ValueError("invalid gate threshold")
        before, after = read(Path(args.baseline)), read(Path(args.candidate))
        if set(before) != set(after):
            raise ValueError("baseline and candidate must contain the same task IDs")
        if len(before) < args.min_tasks:
            raise ValueError(f"need at least {args.min_tasks} paired tasks")
        ids = sorted(before)
        old_pass = sum(before[i]["passed"] for i in ids)
        new_pass = sum(after[i]["passed"] for i in ids)
        regressions = [i for i in ids if before[i]["passed"] and not after[i]["passed"]]
        totals = {k: (sum(before[i][k] for i in ids), sum(after[i][k] for i in ids)) for k in NUMERIC}
        old_tokens, new_tokens = totals["input_tokens"]
        growth = (new_tokens - old_tokens) / old_tokens if old_tokens else (0 if not new_tokens else float("inf"))
        gates = {
            "task_regressions": not regressions,
            "pass_count": new_pass >= old_pass,
            "critical_misses": totals["critical_misses"][1] <= totals["critical_misses"][0],
            "rework_steps": totals["rework_steps"][1] <= totals["rework_steps"][0],
            "recovery_minutes": totals["recovery_minutes"][1] <= totals["recovery_minutes"][0],
            "token_growth": growth <= args.max_token_growth,
        }
        print(json.dumps({"paired_tasks": len(ids), "pass_count": [old_pass, new_pass],
                          "totals_baseline_candidate": totals, "token_growth": growth,
                          "regressed_tasks": regressions, "gates": gates,
                          "eligible_for_review": all(gates.values())}, ensure_ascii=False, indent=2))
        return 0 if all(gates.values()) else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
