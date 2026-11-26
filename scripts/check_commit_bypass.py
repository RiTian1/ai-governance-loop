#!/usr/bin/env python3
"""commit 协议校验的对抗测试集（cap.evidence.commit）。

测什么
------
`check_commit_message.py` 的 `validate()` 是个纯函数：给它一段 message
和（可选的）受影响代码文件列表，它返回错误清单。本脚本拿对抗样例喂它，
断言"该拒的拒、该放的放"。

为什么要双向
------------
单边测"能不能拒"会演变成正则越写越严，最后正常的 commit 也被拦——
那时人的反应是 `--no-verify`，闸就永久失效了（和内容闸被加豁免标记同理）。

所以每条样例都标了预期：`reject` 或 `pass`。

覆盖的绕过形态
--------------
- 完全没有 trailer（"先做事后补账"的典型）
- 有 Story 但 Change/Revision/Rules 三行全 none（凑格式）
- Story ID 格式错（缺项目前缀 / 大写 / 段数不对 / 下划线分隔）
- 碰了 code_paths 却把 Change 写成 none（tool.binding.r11 双载体）

用法：
  python scripts/check_commit_bypass.py [--json] [--list]
退出码：0 全部符合预期 / 1 有误判
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
cm = importlib.import_module("check_commit_message")

GOOD = """feat(gov): 示例变更

正文若干行。

Story: gov.S05.07
Change: none
Revision: rev-2026-11-20-gate-bypass-suites
Rules: none
"""

# (编号, 说明, message, code_hits, 期望是否有错)
CASES = [
    ("K01", "完全没有 trailer", "fix: 改了点东西\n",
     None, True),
    ("K02", "只有正文没有 Story", "feat: 加功能\n\nChange: gov.C04.26\n",
     None, True),
    ("K03", "三个 trailer 全 none", "chore: 杂项\n\nStory: gov.S05.07\n"
     "Change: none\nRevision: none\nRules: none\n", None, True),
    ("K04", "Story 缺项目前缀", "feat: x\n\nStory: S05.07\nRevision: r1\n",
     None, True),
    ("K05", "story 小写", "feat: x\n\nstory: gov.S05.07\nRevision: r1\n",
     None, True),
    ("K06", "段号不足两位", "feat: x\n\nStory: gov.S5.7\nRevision: r1\n",
     None, True),
    ("K07", "下划线分隔", "feat: x\n\nStory: gov_S05_07\nRevision: r1\n",
     None, True),
    ("K08", "碰了 code_paths 但 Change 为 none",
     "feat: 改代码\n\nStory: gov.S05.07\nChange: none\n"
     "Revision: rev-x\nRules: none\n", ["src/app.py"], True),
    ("K09", "Story 只写了一半（缺段号）", "feat: x\n\nStory: gov.S05\nRevision: r1\n",
     None, True),
    ("K10", "重复 Story 行（第二个伪造）",
     "feat: x\n\nStory: gov.S05.06\nStory: gov.S99.99\nRevision: r1\n", None, True),
    ("K11", "Change: NULL 冒充非 none",
     "feat: x\n\nStory: gov.S05.07\nChange: NULL\n", None, True),
    ("K12", "Change: - 冒充非 none",
     "feat: x\n\nStory: gov.S05.07\nChange: -\n", None, True),
    ("K13", "正文中间出现 Story: 行（trailer 区无 Story）",
     "feat: x\n\n这里引用别人的提交\nStory: gov.S99.99\n\nChange: gov.C04.26\n",
     None, True),
    ("K14", "把 Story 写在 subject 里冒充 trailer",
     "Story: gov.S99.99 的后续修复\n\nChange: gov.C04.26\n", None, True),
    # ---- 以下应放行：防"正则越写越严，正常提交也被拦" ----
    ("P01", "标准三行齐全", GOOD, None, False),
    ("P02", "只有 Story + Revision", "fix: x\n\nStory: gov.S05.07\nRevision: rev-y\n",
     None, False),
    ("P03", "Rules 非 none", "fix: x\n\nStory: gov.S05.07\nRules: tool.r14+\n",
     None, False),
    ("P04", "Story 带状态转换", "feat: x\n\nStory: gov.S05.07 [approved -> done]\n"
     "Revision: rev-y\n", None, False),
    ("P05", "碰代码且 Change 非 none",
     "feat: 改代码\n\nStory: gov.S05.07\nChange: gov.C04.26\nRevision: rev-y\n",
     ["src/app.py"], False),
    ("P06", "Rules 混写 none 与真实号",
     "fix: x\n\nStory: gov.S05.07\nRules: none, tool.r14+\n", None, False),
    ("P07", "Story 行尾带空格", "fix: x\n\nStory: gov.S05.07   \nRevision: rev-y\n",
     None, False),
    ("P08", "trailer 顺序颠倒", "fix: x\n\nRevision: rev-y\nStory: gov.S05.07\n",
     None, False),
    ("P09", "正文提到 story 但不在行首",
     "fix: x\n\n这次沿用 Story: gov.S99.99 的做法\n\nStory: gov.S05.07\nRevision: rev-y\n",
     None, False),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="commit 协议校验的对抗测试集")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for cid, why, _, hits, expect in CASES:
            print("%-4s %-34s 期望%s%s" % (cid, why, "报错" if expect else "通过",
                                           "  code_hits=%s" % hits if hits else ""))
        return 0

    print("commit 协议校验对抗测试集")
    print("样本：期望报错 %d 条，期望通过 %d 条\n"
          % (sum(1 for c in CASES if c[4]), sum(1 for c in CASES if not c[4])))

    bad = []
    rows = []
    for cid, why, msg, hits, expect in CASES:
        errs = cm.validate(msg, hits)
        got = bool(errs)
        ok = got == expect
        rows.append({"id": cid, "why": why, "expect_error": expect,
                     "got_error": got, "ok": ok, "errors": errs})
        if not ok:
            bad.append(cid)
        print("  %-4s %-34s %s%s"
              % (cid, why, "报错" if got else "通过", "" if ok else "   !! 不符预期"))
        if errs and (not expect or not ok):
            print("       └ %s" % errs[0][:78])

    print("\n" + "=" * 70)
    print("符合预期：%d/%d" % (len(CASES) - len(bad), len(CASES)))
    if bad:
        print("不符预期：%s" % ", ".join(bad))
    rejected = sum(1 for r in rows if r["expect_error"] and r["got_error"])
    attempts = sum(1 for r in rows if r["expect_error"])
    print("应拒样本中被正确拒绝：%d/%d" % (rejected, attempts))
    if args.json:
        print(json.dumps({"correct": len(CASES) - len(bad), "total": len(CASES),
                          "attempts": attempts, "rejected": rejected,
                          "mismatch": bad, "cases": rows}, ensure_ascii=False, indent=1))
    print("=" * 70)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
