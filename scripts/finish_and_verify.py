#!/usr/bin/env python3
"""收尾组合校验（一条命令跑完闭环自检 + 生成 matrix + 打印完成清单）。

字段实战教训：「跑一致性自检 -> 生成 progress matrix -> 确认可归档/提交」这套收尾动作
在长会话里被反复人肉念一遍，容易漏。本脚本把它固化成一条命令，作为 CRUD 收尾的标准出口。

它是**编排器**：按序调用既有零依赖脚本，聚合退出码，任一硬门失败即整体 fail（退出 1）。
不重复实现任何检查逻辑，只负责「一次性跑完 + 汇总 + 给出下一步」。

用法:
  python scripts/finish_and_verify.py
  python scripts/finish_and_verify.py --strict          # 一致性自检用 --strict
  python scripts/finish_and_verify.py --no-matrix        # 跳过 matrix 生成

退出码:
  0 = 所有硬门通过（可收尾：commit / archive / 标完成）
  1 = 任一硬门失败（不许收尾，先消除漂移）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def run_step(title: str, cmd: list[str], required: bool) -> tuple[bool, bool]:
    """返回 (passed, is_hard_gate)。"""
    print(f"\n{'='*60}\n[步骤] {title}\n{'='*60}")
    try:
        proc = subprocess.run(cmd, cwd=str(SCRIPTS.parent))
        ok = proc.returncode == 0
    except Exception as e:  # noqa: BLE001
        print(f"[X] 无法执行 {cmd}: {e!r}")
        ok = False
    if not ok and required:
        print(f"[X] {title} 未通过（硬门）")
    elif not ok:
        print(f"[!] {title} 未通过（非硬门，仅告警）")
    else:
        print(f"[OK] {title} 通过")
    return ok, required


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="CRUD 收尾组合校验编排器")
    p.add_argument("--strict", action="store_true", help="一致性自检使用 --strict")
    p.add_argument("--no-matrix", action="store_true", help="跳过 progress matrix 生成")
    p.add_argument("--no-health", action="store_true", help="跳过知识库健康自检（缺 pyyaml 时可跳）")
    p.add_argument("--no-hygiene", action="store_true", help="跳过工作树卫生检查")
    args = p.parse_args(argv)

    py = sys.executable
    hard_failures = 0

    # 1) 进度一致性自检（硬门，零依赖，fail-closed）
    consistency_cmd = [py, str(SCRIPTS / "check_progress_consistency.py")]
    if args.strict:
        consistency_cmd.append("--strict")
    ok, _ = run_step("进度一致性自检 check_progress_consistency", consistency_cmd, required=True)
    if not ok:
        hard_failures += 1

    # 2) 知识库健康自检（软门：依赖 pyyaml；缺依赖时可 --no-health 跳过）
    if not args.no_health:
        ok, _ = run_step(
            "知识库健康自检 check_knowledge_health --all",
            [py, str(SCRIPTS / "check_knowledge_health.py"), "--all"],
            required=False,
        )

    # 3) 工作树卫生（软门：git-optional；报告 generated vs real churn，收尾前须归因）
    if not args.no_hygiene:
        run_step(
            "工作树卫生 check_worktree_hygiene（generated vs real churn 归因）",
            [py, str(SCRIPTS / "check_worktree_hygiene.py")],
            required=False,
        )

    # 4) 生成 progress matrix（软门：产出物，便于人工复核）
    if not args.no_matrix:
        run_step(
            "生成 progress matrix",
            [py, str(SCRIPTS / "gen_progress_matrix.py"), "--report", "_logs/progress-matrix.md"],
            required=False,
        )

    print(f"\n{'='*60}\n[收尾判定]\n{'='*60}")
    if hard_failures:
        print("[X] 硬门未通过：禁止 commit / archive / 标完成。先消除漂移或登记合法豁免，再重跑本脚本。")
        return 1

    print("[OK] 硬门全部通过。收尾清单：")
    print("  1. 状态字段（done/archived/merged/active_sprint）现在才可写入（且须三端联动）")
    print("  2. 若走 git：commit message 含 Story: 行，Change/Revision/Rules 至少一行非 none")
    print("  3. 归档 OpenSpec 变更 / 晋升 revision 时，确认 index.yaml 与文件系统一致")
    print("  4. matrix 报告见 _logs/progress-matrix.md（如已生成）")
    print("  5. 工作树残留脏改动须已归因（真实改动 vs 生成产物 churn，见上方 hygiene 输出）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
