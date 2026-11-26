#!/usr/bin/env python3
"""Validate promptfoo (or compatible) eval report against pass-rate gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_results(report_path: Path) -> list[dict]:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "results" in data:
            return data["results"]
        if "results" in data.get("table", {}):
            return data["table"]["results"]
    raise ValueError(f"Unrecognized report shape: {report_path}")


def pass_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    passed = 0
    for row in results:
        success = row.get("success")
        if success is None:
            success = row.get("pass")
        if success is None and "gradingResult" in row:
            success = row["gradingResult"].get("pass")
        if success:
            passed += 1
    return passed / len(results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--min-pass-rate", type=float, default=0.85)
    args = parser.parse_args()

    if not args.report.exists():
        print(f"ERROR: report not found: {args.report}", file=sys.stderr)
        return 2

    results = load_results(args.report)
    rate = pass_rate(results)
    print(f"pass_rate={rate:.4f} ({int(rate * len(results))}/{len(results)})")

    if rate < args.min_pass_rate:
        print(
            f"FAIL: below min_pass_rate {args.min_pass_rate}",
            file=sys.stderr,
        )
        return 1
    print("OK: eval gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
