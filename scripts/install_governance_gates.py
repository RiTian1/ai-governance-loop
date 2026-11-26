#!/usr/bin/env python3
"""统一确定性门禁安装入口（接入任意项目即具备；无 git 自动降级）。

规范：domains/tooling/_summary.yaml（tool.r7）、domains/agent-tooling-mcp.md §10、
      docs/governance/INTEGRATION-GUIDE.md §3.3。

它把散落的确定性闸安装动作收敛成一条命令，作为集成/升级的标准出口：
  1. git 门禁（跨 agent 通用、模型无法忽略的主干层）——有 .git 才装，无 .git 优雅降级。
  2. Cursor hooks（仅 Cursor 内有效的本地闸）——可选（--with-cursor-hooks）。
  3. 强制跑一次零依赖进度一致性自检，证明闭环已激活（地基门禁，必能跑）。

设计定位：
  - git 钩子是唯一在 Cursor / Codex / 命令行提交时都会触发的确定性层；Cursor hooks 只在
    Cursor 内生效，Codex 无生命周期 hook。因此本入口以 git 门禁为主干、Cursor 为可选加分。
  - "没有 git 管理的项目就不载入 git hook"——find_git_root 探测不到 .git 即跳过并显式说明，
    闭环仍由基线保证（零依赖自检 + agent 入口协议 + 同步台账）。
  - 编排器：只调既有零依赖脚本、聚合结果，不重复实现任何检查逻辑。

用法:
  python scripts/install_governance_gates.py                       # 装 git 门禁 + 自检
  python scripts/install_governance_gates.py --with-cursor-hooks   # 另装 Cursor 本地闸
  python scripts/install_governance_gates.py --project-root DIR    # 显式项目根
  python scripts/install_governance_gates.py --skip-selfcheck      # 跳过收尾自检（不推荐）

退出码:
  0 = 全部可用闸已装好（或无 .git 已优雅降级）且自检通过
  1 = 自检未通过（闭环已激活并立即暴露漂移；先消除再收尾）
  3 = git 门禁应装却装不上（显式告警，非阻断——基线仍生效）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Windows 管道/重定向下默认 locale 编码（GBK）会把中文输出写成乱码；统一 UTF-8
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
# 治理内容根：scripts/ 的上一级（含 00-index.yaml / revisions/ / project-governance.yaml 等）
GOVERNANCE_ROOT = SCRIPTS_DIR.parent


def _run(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd).returncode
    except Exception as e:  # noqa: BLE001
        print(f"[X] 无法执行 {cmd}: {e!r}", file=sys.stderr)
        return 1


def find_git_root(start: Path) -> Path | None:
    p = start.resolve()
    for _ in range(40):
        if (p / ".git").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return None


def detect_project_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    git_root = find_git_root(GOVERNANCE_ROOT)
    if git_root:
        return git_root
    # 无 git：治理内容根的上层若有 project-governance.yaml 则用之，否则用治理内容根
    for p in [GOVERNANCE_ROOT, *GOVERNANCE_ROOT.parents]:
        if (p / "project-governance.yaml").exists():
            return p
    return GOVERNANCE_ROOT


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="统一确定性门禁安装入口")
    ap.add_argument("--project-root", default=None, help="项目根；省略时探测 .git / project-governance.yaml")
    ap.add_argument("--governance-root", default=None,
                    help="治理内容根（自检 --governance-root）；省略时用脚本上一级（subtree 布局可显式传入）")
    ap.add_argument("--with-cursor-hooks", action="store_true", help="另装 Cursor 本地闸（仅 Cursor 内有效）")
    ap.add_argument("--skip-selfcheck", action="store_true", help="跳过收尾一致性自检（不推荐）")
    ap.add_argument("--strict", action="store_true", help="收尾自检使用 --strict")
    args = ap.parse_args(argv)

    py = sys.executable
    project_root = detect_project_root(args.project_root)
    git_root = find_git_root(project_root)
    governance_root = Path(args.governance_root).resolve() if args.governance_root else GOVERNANCE_ROOT

    summary: list[str] = []
    rc_final = 0

    print(f"# 统一确定性门禁安装（project-root={project_root}, governance-root={governance_root}）\n")

    # 1) git 门禁（主干层，git-optional）
    print("=" * 60)
    print("[1/3] git 门禁（跨 agent 通用主干层）")
    print("=" * 60)
    if git_root is None:
        print("[skip] 未探测到 .git —— git 门禁不适用，优雅降级。")
        print("       闭环仍由基线保证：零依赖自检 + 入口协议 + 同步台账。")
        summary.append("git 门禁：跳过（无 .git，已降级）")
    else:
        rc = _run([py, str(SCRIPTS_DIR / "install_git_hooks.py"), "--project-root", str(project_root)])
        if rc == 0:
            summary.append("git 门禁：已安装（pre-commit 一致性 + staged-pure 卫生 + 内容闸[凭证/UTF-8] + token 预算闸；commit-msg 协议）")
        elif rc == 3:
            summary.append("git 门禁：未能自动装上（显式告警，基线仍生效）")
            rc_final = 3 if rc_final == 0 else rc_final
        else:
            summary.append(f"git 门禁：安装返回 {rc}")
            rc_final = 3 if rc_final == 0 else rc_final

    # 2) Cursor hooks（可选本地闸）
    print("\n" + "=" * 60)
    print("[2/3] Cursor 本地闸（可选，仅 Cursor 内有效）")
    print("=" * 60)
    if args.with_cursor_hooks:
        rc = _run([py, str(SCRIPTS_DIR / "install_cursor_hooks.py"), "--project-root", str(project_root)])
        summary.append("Cursor hooks：已安装" if rc == 0 else f"Cursor hooks：返回 {rc}")
    else:
        print("[skip] 未指定 --with-cursor-hooks（Cursor 本地闸不影响跨 agent 主干）。")
        summary.append("Cursor hooks：跳过（未指定 --with-cursor-hooks）")

    # 3) 强制自检，证明闭环已激活
    print("\n" + "=" * 60)
    print("[3/3] 闭环激活自检 check_progress_consistency（地基门禁）")
    print("=" * 60)
    if args.skip_selfcheck:
        print("[skip] --skip-selfcheck（不推荐）")
        summary.append("闭环自检：跳过")
    else:
        cmd = [py, str(SCRIPTS_DIR / "check_progress_consistency.py"),
               "--governance-root", str(governance_root)]
        if args.strict:
            cmd.append("--strict")
        rc = _run(cmd)
        if rc == 0:
            summary.append("闭环自检：通过（exit 0）—— 闭环 ACTIVE")
        else:
            summary.append(f"闭环自检：未通过（exit {rc}）—— 先消除漂移再收尾")
            rc_final = 1

    print("\n" + "=" * 60)
    print("[安装清单]")
    print("=" * 60)
    for s in summary:
        print("  - " + s)
    if rc_final == 1:
        print("\n[X] 闭环自检未通过：漂移已立即可见，先消除或登记合法豁免。")
    elif rc_final == 3:
        print("\n[!] git 门禁未完全装上（仅丢加分项，基线门禁照常拦截）。")
    else:
        print("\n[OK] 可用确定性闸已就位；闭环已激活。")
    return rc_final


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
