#!/usr/bin/env python3
"""成熟度判据自测（cap.evidence.maturity）。

判据本身要能被证伪。`check_capability_map.py` 决定每个能力的成熟度是否诚实，
它自己算错的时候没人会发现——所以给它一组对抗输入。

覆盖 CHECKLIST D1 要求的四类，另加三组边界：

  A 全对        attempts=10 rejected=10        → 通过
  B 漏 N        attempts=10 rejected=8         → 报错（有绕过成功）
  C 样本不足    attempts=5  rejected=5         → 报错（< MIN_BYPASS_ATTEMPTS）
  D 空输入      只有 destructive_test           → 报错
  E 原路径      只有 effect_size                → 通过
  F 缺字段      有 attempts 无 rejected         → 报错
  G M4 顶替     两处 bypass 冒充跨任务复现       → 报错

用法：python scripts/check_capability_map_selftest.py
退出码：0 全通过 / 1 有失败
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
cm = importlib.import_module("check_capability_map")


def _maturity_findings(evidence, current="M3", target="M3") -> list:
    cap = {"id": "cap.selftest.probe", "current": current,
           "target": target, "evidence": evidence}
    return [f for f in cm.check_maturity(cap, 0)
            if f.code.startswith("M3") or f.code.startswith("M4")]


CASES = [
    ("A 全对：attempts=10 rejected=10",
     [{"kind": "bypass_attempt", "ref": "x", "attempts": 10, "rejected": 10}],
     "M3", "M3", False),
    ("B 漏N：attempts=10 rejected=8",
     [{"kind": "bypass_attempt", "ref": "x", "attempts": 10, "rejected": 8}],
     "M3", "M3", True),
    ("C 样本不足：attempts=5 rejected=5",
     [{"kind": "bypass_attempt", "ref": "x", "attempts": 5, "rejected": 5}],
     "M3", "M3", True),
    ("D 空输入：只有 destructive_test",
     [{"kind": "destructive_test", "ref": "x"}],
     "M3", "M3", True),
    ("E 原路径：只有 effect_size",
     [{"kind": "effect_size", "ref": "x"}],
     "M3", "M3", False),
    ("F 缺字段：有 attempts 无 rejected",
     [{"kind": "bypass_attempt", "ref": "x", "attempts": 10}],
     "M3", "M3", True),
    ("G M4 用两处 bypass 顶替",
     [{"kind": "bypass_attempt", "ref": "x", "attempts": 10, "rejected": 10},
      {"kind": "bypass_attempt", "ref": "y", "attempts": 12, "rejected": 12}],
     "M4", "M4", True),
]


def main() -> int:
    print("成熟度判据自测（bypass_attempt / effect_size 双路径）")
    print("MIN_BYPASS_ATTEMPTS = %d\n" % cm.MIN_BYPASS_ATTEMPTS)
    failed = 0
    for label, evidence, cur, tgt, expect_error in CASES:
        hits = _maturity_findings(evidence, cur, tgt)
        got_error = bool(hits)
        ok = got_error == expect_error
        print("  %-34s %s %s" % (label, "报错" if got_error else "通过",
                                 "ok" if ok else "FAIL"))
        if not ok:
            failed += 1
            print("     期望 %s，实际 %s" % ("报错" if expect_error else "通过",
                                          "报错" if got_error else "通过"))
        elif hits:
            print("     └ %s" % hits[0].msg[:88])

    print()
    if failed:
        print("失败 %d / %d" % (failed, len(CASES)))
        return 1
    print("全部 %d 组符合预期" % len(CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
