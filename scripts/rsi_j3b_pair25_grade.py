#!/usr/bin/env python3
"""J3b §8.6 配对实验判分（PAIRED-25-PREREG.md 的执行体）。

只做一件事：把 25 对 findings.json 变成配对表 + McNemar 精确检验 + 天花板判定。

判定口径（跑之前定死，不在看到结果后调）
----------------------------------------
预注册原文：「GT-B01（**会不会把 `ExportError` 这个公共根因单独成条**）」。

所以主口径是**行号锚定**：存在一条 finding 的 `file` 含 `function.asp`
且 `line` 落在 GT 证据区间 744–749 的容差范围（738–752）内。
"单独成条"意味着它自己占一条 finding，不是别的条目里顺带提一句。

同时输出**第二口径**（文本提及：evidence/precondition 里出现
`ExportError` 且带"不终止/未终止/根因/Response.End"任一关键词）作为敏感性分析。
两个口径结论不同时必须并列报告——口径决定结论本身就是结论的一部分。

用法：
  python scripts/rsi_j3b_<配对实验>_grade.py --root <解压后的 <配对实验> 目录>
  python scripts/rsi_j3b_<配对实验>_grade.py --root ... --json

退出码：0 判分完成 / 2 输入不足（有效配对 < 2）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from math import comb
from pathlib import Path

HIT_LINE_LO, HIT_LINE_HI = 738, 752      # GT 证据 744-749，外扩 6 行容忍近似定位
KEY_ANCHOR = "function.asp"
MIN_PAIRS = 2
CEILING = 0.9                            # 预注册：基线命中率 >= 0.9 则测不出东西


def _norm(s) -> str:
    return re.sub(r"[\s_\-]+", "", str(s)).lower()


def hit_by_line(findings) -> bool:
    for f in findings:
        if KEY_ANCHOR not in str(f.get("file", "")):
            continue
        try:
            ln = int(f.get("line") or 0)
        except (TypeError, ValueError):
            continue
        if HIT_LINE_LO <= ln <= HIT_LINE_HI:
            return True
    return False


def hit_by_text(findings) -> bool:
    markers = ("不终止", "未终止", "根因", "responseend", "不中断")
    for f in findings:
        blob = _norm(f.get("evidence", "")) + _norm(f.get("precondition", "")) \
            + _norm(f.get("fix", ""))
        if "exporterror" in blob and any(m in blob for m in markers):
            return True
    return False


def mcnemar_exact(b: int, c: int) -> float:
    """双侧精确 McNemar。b/c 为两组不一致的配对数。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def collect(root: Path) -> dict:
    rows: dict = {}
    for p in sorted(root.rglob("findings.json")):
        arm = p.parent.name
        if arm not in ("base", "gov"):
            continue
        pair = p.parent.parent.name
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print("[warn] 跳过 %s：%s" % (p, exc), file=sys.stderr)
            continue
        fs = data.get("findings") or []
        rows.setdefault(pair, {})[arm] = {
            "n_findings": len(fs),
            "line": hit_by_line(fs),
            "text": hit_by_text(fs),
        }
    return rows


def pair_table(rows: dict, key: str) -> tuple:
    a = b = c = d = 0
    complete = []
    for pair, v in sorted(rows.items()):
        if "base" not in v or "gov" not in v:
            continue
        hb, hg = v["base"][key], v["gov"][key]
        if hb and hg:
            a += 1
        elif hg and not hb:
            b += 1
        elif hb and not hg:
            c += 1
        else:
            d += 1
        complete.append(pair)
    return a, b, c, d, complete


def selftest() -> int:
    """判据自测（CHECKLIST D1）。判据算错会直接翻转结论，必须先自证。"""
    cases = [
        # (b, c, 期望 p, 说明)
        (8, 0, 0.0078, "b=8 c=0 单侧极端，双侧≈2^-7"),
        (0, 8, 0.0078, "对称：方向反了 p 应相同"),
        (5, 5, 1.0, "完全对称，无差异"),
        (0, 0, 1.0, "无不一致对"),
        (4, 0, 0.125, "b=4 c=0，双侧≈2^-3"),
        (1, 0, 1.0, "单对不一致不足以显著"),
    ]
    bad = 0
    for b, c, expect, why in cases:
        got = mcnemar_exact(b, c)
        ok = abs(got - expect) < 1e-3
        print("  mcnemar(b=%d,c=%d)=%.4f  期望≈%.4f  %s  %s"
              % (b, c, got, expect, "ok" if ok else "FAIL", why))
        if not ok:
            bad += 1

    # 配对表语义：base 命中 = a+c，gov 命中 = a+b。这一条曾在实现里写反，
    # 导致得出"天花板"的错误结论——必须锁死。
    rows = {
        "x1": {"base": {"line": True}, "gov": {"line": True}},
        "x2": {"base": {"line": False}, "gov": {"line": True}},
        "x3": {"base": {"line": True}, "gov": {"line": False}},
        "x4": {"base": {"line": False}, "gov": {"line": False}},
    }
    a, b, c, d, _ = pair_table(rows, "line")
    checks = [
        (a == 1, "a(both)=1 实际 %d" % a),
        (b == 1, "b(gov_only)=1 实际 %d" % b),
        (c == 1, "c(base_only)=1 实际 %d" % c),
        (d == 1, "d(neither)=1 实际 %d" % d),
        (a + c == 2, "base 命中数 = a+c = 2"),
        (a + b == 2, "gov 命中数 = a+b = 2"),
    ]
    for ok, msg in checks:
        print("  %s  %s" % ("ok  " if ok else "FAIL", msg))
        if not ok:
            bad += 1

    print()
    print("判据自测：%d 项，失败 %d 项" % (len(cases) + len(checks), bad))
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="J3b §8.6 配对实验判分")
    ap.add_argument("--root", help="含 p01..p25/{base,gov}/findings.json 的目录")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="只跑判据自测")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.root:
        print("需要 --root（或 --selftest）", file=sys.stderr)
        return 2

    root = Path(args.root)
    if not root.exists():
        print("根目录不存在：%s" % root, file=sys.stderr)
        return 2

    rows = collect(root)
    incomplete = [p for p, v in sorted(rows.items()) if len(v) < 2]

    print("J3b §8.6 配对实验判分")
    print("根目录：%s" % root)
    print("发现 %d 组，其中 %d 组两臂齐全，缺臂：%s"
          % (len(rows), len(rows) - len(incomplete), ", ".join(incomplete) or "无"))
    print()

    out = {}
    for key, label in (("line", "主口径：行号 738-752（单独成条）"),
                       ("text", "敏感性：文本提及 ExportError+不终止")):
        a, b, c, d, complete = pair_table(rows, key)
        n = a + b + c + d
        if n < MIN_PAIRS:
            print("%s：有效配对 %d < %d，无法判分" % (label, n, MIN_PAIRS))
            continue
        # 配对表语义：a=both 命中，b=仅 gov 命中，c=仅 base 命中，d=都不中
        # base 命中 = both + base_only = a + c
        # gov  命中 = both + gov_only  = a + b
        rate_base = (a + c) / n
        rate_gov = (a + b) / n
        p = mcnemar_exact(b, c)
        ceiling = rate_base >= CEILING
        print("%s" % label)
        print("  配对表  both=%-2d  gov_only(b)=%-2d  base_only(c)=%-2d  neither=%-2d   n=%d"
              % (a, b, c, d, n))
        print("  命中率  base=%.2f (%d/%d)   gov=%.2f (%d/%d)"
              % (rate_base, a + c, n, rate_gov, a + b, n))
        print("  McNemar b=%d c=%d  p=%.4f" % (b, c, p))
        if ceiling:
            verdict = "天花板：基线命中率 %.2f >= %.1f，本轮不具备检测提升的能力" % (rate_base, CEILING)
        elif p < 0.05 and b > c:
            verdict = "条款有效（p=%.4f < 0.05，方向偏向 gov）" % p
        elif p < 0.05 and c > b:
            verdict = "条款有害（p=%.4f < 0.05，方向偏向 base）" % p
        else:
            verdict = "无显著差异（p=%.4f >= 0.05）" % p
        print("  判定：%s" % verdict)
        print()
        out[key] = {"a": a, "b": b, "c": c, "d": d, "n": n,
                    "base_rate": round(rate_base, 4), "gov_rate": round(rate_gov, 4),
                    "p_value": round(p, 6), "ceiling": ceiling, "verdict": verdict}

    if len(out) == 2 and out["line"]["verdict"] != out["text"]["verdict"]:
        print("⚠ 两个口径结论不一致。预注册写的是「单独成条」，主口径取行号锚定；")
        print("  但必须并列报告敏感性——口径决定结论，这本身就是结论的一部分。")

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out else 2


if __name__ == "__main__":
    sys.exit(main())
