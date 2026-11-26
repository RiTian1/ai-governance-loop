#!/usr/bin/env python3
"""把 templates/cursor-hooks/ 安装到 .cursor/hooks(.json)（跨平台、仅标准库）。

规范：domains/agent-tooling-mcp.md §10（确定性生命周期闸，tool.r6）。

Cursor hooks 是**模型无法忽略**的确定性脚本，用来把治理的 STOP 门 / 危险命令拦截
落成物理闸。本脚本把模板 hook（Python 实现，不依赖 jq）安装到项目 `.cursor/` 下，
并按当前解释器改写 hooks.json 中的 `python` 前缀。

用法:
  python scripts/install_cursor_hooks.py                       # 安装/更新（自动探测项目根）
  python scripts/install_cursor_hooks.py --project-root DIR     # 显式指定项目根
  python scripts/install_cursor_hooks.py --dry-run
  python scripts/install_cursor_hooks.py --uninstall

说明:
  - `.cursor/` 装到**项目根**（而非治理内容目录）。brownfield 布局下脚本位于
    `docs/governance/scripts/`，`.cursor/` 仍落在项目根（自动向上探测
    project-governance.yaml / git root；探测不到时用当前工作目录）。
  - 模板（templates/cursor-hooks/）随治理内容走，相对脚本自身定位。
  - `.cursor/` 默认被 .gitignore 忽略 → hooks 是每个克隆本地安装一次的本地闸；
    团队共享的可复用逻辑保留在 templates/cursor-hooks/（进版本库）。
  - 安装后需在 Cursor 重新加载（保存 hooks.json 会自动 reload；必要时重启）。
退出码: 0 成功 / 2 模板缺失
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
# 模板随治理内容走：相对脚本自身（scripts/ 的上一级 = 治理内容根）
TPL_DIR = SCRIPTS_DIR.parent / "templates" / "cursor-hooks"

HOOK_SCRIPTS = ["guard_dangerous_command.py", "checkpoint_consistency.py"]


def interpreter() -> str:
    # hooks.json 的 command 以字符串在 shell 里执行；用当前解释器名保证跨平台
    exe = Path(sys.executable).name
    return exe or "python"


def detect_project_root(explicit: str | None) -> Path:
    """定位 .cursor/ 应落在哪：显式优先 → 向上探测 project-governance.yaml / .git → cwd。"""
    if explicit:
        return Path(explicit).resolve()
    start = Path.cwd().resolve()
    for p in [start, *start.parents]:
        if (p / "project-governance.yaml").exists() or (p / ".git").exists():
            return p
    return start


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=None,
                    help="项目根（.cursor/ 落点）；省略时自动探测")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()

    project_root = detect_project_root(args.project_root)
    cursor_dir = project_root / ".cursor"
    hooks_dir = cursor_dir / "hooks"
    hooks_json = cursor_dir / "hooks.json"

    def rel(p: Path) -> str:
        try:
            return p.relative_to(project_root).as_posix()
        except ValueError:
            return p.as_posix()

    if args.uninstall:
        for f in [hooks_json] + [hooks_dir / s for s in HOOK_SCRIPTS]:
            if f.exists():
                print(f"{'would remove' if args.dry_run else 'removed'} {rel(f)}")
                if not args.dry_run:
                    f.unlink()
        return 0

    tpl_json = TPL_DIR / "hooks.json.example"
    if not tpl_json.exists():
        print(f"ERROR: missing {tpl_json}", file=sys.stderr)
        return 2

    py = interpreter()
    hooks_conf = json.loads(tpl_json.read_text(encoding="utf-8"))
    # 按当前解释器改写 "python ..." 前缀
    for _evt, entries in hooks_conf.get("hooks", {}).items():
        for e in entries:
            cmd = e.get("command", "")
            if cmd.startswith("python "):
                e["command"] = py + cmd[len("python"):]

    if args.dry_run:
        print(f"would write {rel(hooks_json)} (interpreter={py}, project-root={project_root})")
        for s in HOOK_SCRIPTS:
            print(f"would copy templates/cursor-hooks/{s} -> {rel(hooks_dir / s)}")
        return 0

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hooks_json.write_text(json.dumps(hooks_conf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for s in HOOK_SCRIPTS:
        src = TPL_DIR / s
        if src.exists():
            dst = hooks_dir / s
            shutil.copyfile(src, dst)
            try:
                dst.chmod(0o755)
            except Exception:
                pass
    print(f"Installed Cursor hooks -> {rel(hooks_json)} (interpreter={py})")
    print("在 Cursor 中保存 hooks.json 会自动 reload；如未生效请重启。设置 → Hooks 可查看状态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
