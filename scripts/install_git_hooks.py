#!/usr/bin/env python3
"""幂等、非破坏、可降级的 git 门禁安装器（便携治理的"加分层"）。

设计定位（见 handoff §2 / §3.3）：
  - git 门禁是**可选附加层**，不是地基。地基 = 零依赖自检 + 入口协议 + 同步台账。
  - 本安装器仅在"目标项目自己有 .git"时把 hook 挂上去；hook 只是壳，内部调用
    subtree 进来的 scripts/check_*.py（自定位相对路径，不写死绝对路径）。
  - 四条铁律：
      1. 幂等   —— 写入段带哨兵注释，重复跑只更新自己那段。
      2. 非破坏 —— 已有 core.hooksPath / husky / pre-commit 框架 / 既有 hook 时
                   追加成调用链，绝不覆盖别人。
      3. 自定位 —— hook 按 git 根到 scripts/ 的相对路径调用，可移植。
      4. 可降级 —— 装不上只丢"加分项"，并**显式告警**（绝不静默放过）；
                   基线门禁照常拦截。

用法:
  python scripts/install_git_hooks.py [--project-root DIR]
  # DIR 省略时用当前工作目录（路径乙 / bootstrap 都从项目根调用）

退出码:
  0 = 已装好 / 不适用（无 .git，已优雅降级）
  3 = git 门未能自动装上（显式告警，非阻断——基线仍生效）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SENTINEL_START = "# >>> governance-managed >>>"
SENTINEL_END = "# <<< governance-managed <<<"


def _run_git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True,
                           text=True, check=False, encoding="utf-8")
        return r.returncode, (r.stdout or "").strip()
    except Exception:
        return 1, ""


def find_git_root(start: Path) -> Path | None:
    if shutil.which("git"):
        code, out = _run_git(start, "rev-parse", "--show-toplevel")
        if code == 0 and out:
            return Path(out).resolve()
    p = start.resolve()
    for _ in range(40):
        if (p / ".git").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return None


def find_scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def rel_invocation(git_root: Path, scripts_dir: Path) -> str:
    """git 根到 check 脚本的可移植相对路径（posix 风格，hook 内 sh 友好）。"""
    try:
        rel = scripts_dir.relative_to(git_root)
        return rel.as_posix()
    except ValueError:
        return scripts_dir.as_posix()


def _managed_block(kind: str, scripts_rel: str) -> str:
    """生成带哨兵的 governance hook 段。kind: pre-commit | commit-msg。"""
    if kind == "commit-msg":
        body = (
            f'python "$GOV_SCRIPTS/check_commit_message.py" "$1" '
            f'--governance-root "$GOV_ROOT" || exit 1'
        )
    else:
        # pre-commit 四道闸：
        #   1) 进度一致性（staged frontmatter 完整性，零依赖）
        #   2) 工作树卫生 staged-pure：阻断"生成产物 churn 与真实改动混在同一次提交"
        #      （ops.housekeeping.r12；仅看 staged 集合，不影响未 staged 的 WIP 脏改动）
        #   3) staged 内容闸：明文凭证 + UTF-8 合法性（tool.r9 / ops.runtime-context.r9）
        #   4) 常驻上下文 token 预算闸（tool.r8；缺脚本时静默跳过，兼容旧 bundle）
        body = "\n".join([
            f'python "$GOV_SCRIPTS/check_progress_consistency.py" '
            f'--governance-root "$GOV_ROOT" --staged || exit 1',
            f'python "$GOV_SCRIPTS/check_worktree_hygiene.py" '
            f'--governance-root "$GOV_ROOT" --assert-staged-pure || exit 1',
            f'if [ -f "$GOV_SCRIPTS/check_staged_content.py" ]; then '
            f'python "$GOV_SCRIPTS/check_staged_content.py" '
            f'--project-root "$GOV_ROOT" --staged || exit 1; fi',
            f'if [ -f "$GOV_SCRIPTS/check_context_budget.py" ]; then '
            f'python "$GOV_SCRIPTS/check_context_budget.py" '
            f'--project-root "$GOV_ROOT" --quiet || exit 1; fi',
        ])
    return "\n".join([
        SENTINEL_START,
        '# governance closed-loop gate (optional add-on layer). Edit via',
        '# scripts/install_git_hooks.py — manual edits inside this block are overwritten.',
        'GOV_ROOT="$(git rev-parse --show-toplevel)"',
        f'GOV_SCRIPTS="$GOV_ROOT/{scripts_rel}"',
        body,
        SENTINEL_END,
        "",
    ])


def _upsert_block(existing: str, block: str) -> str:
    """幂等写入：有哨兵段就替换，没有就追加（调用链：原有在前，governance 在后）。"""
    if SENTINEL_START in existing and SENTINEL_END in existing:
        pre = existing.split(SENTINEL_START, 1)[0]
        post = existing.split(SENTINEL_END, 1)[1]
        return pre.rstrip("\n") + "\n\n" + block + post.lstrip("\n")
    base = existing.rstrip("\n")
    if not base:
        return "#!/usr/bin/env sh\n" + block
    return base + "\n\n" + block


def _write_hook(hook_path: Path, kind: str, scripts_rel: str) -> None:
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    existing = hook_path.read_text(encoding="utf-8", errors="replace") if hook_path.exists() else ""
    new = _upsert_block(existing, _managed_block(kind, scripts_rel))
    hook_path.write_text(new, encoding="utf-8")
    try:
        os.chmod(hook_path, 0o755)
    except OSError:
        pass


def install(project_root: Path) -> int:
    git_root = find_git_root(project_root)
    if git_root is None:
        print("[skip] 目标项目无 .git —— git 门禁（可选附加层）不适用。")
        print("       闭环仍由基线保证：零依赖自检 + 入口协议 + 同步台账。")
        return 0

    scripts_dir = find_scripts_dir()
    scripts_rel = rel_invocation(git_root, scripts_dir)

    # 探测 hooks 目录：core.hooksPath 优先（追加，不覆盖）
    code, hooks_path_cfg = _run_git(git_root, "config", "--get", "core.hooksPath")
    if code == 0 and hooks_path_cfg:
        hooks_dir = (git_root / hooks_path_cfg).resolve()
        print(f"[info] 检测到 core.hooksPath={hooks_path_cfg} → 写入该目录（追加，不覆盖）")
    else:
        hooks_dir = (git_root / ".git" / "hooks").resolve()

    husky_dir = git_root / ".husky"
    precommit_cfg = git_root / ".pre-commit-config.yaml"
    warnings: list[str] = []

    # husky：往 .husky/pre-commit 注册 governance 步骤（不动 .git/hooks）
    if husky_dir.is_dir():
        _write_hook(husky_dir / "pre-commit", "pre-commit", scripts_rel)
        _write_hook(husky_dir / "commit-msg", "commit-msg", scripts_rel)
        print("[ok] 已向 husky (.husky/) 注册 governance pre-commit + commit-msg 步骤。")

    # pre-commit 框架：不自动改其 YAML（避免破坏），给出显式告警 + 可粘贴片段
    if precommit_cfg.exists():
        warnings.append(
            "检测到 .pre-commit-config.yaml（pre-commit 框架）。为避免破坏其配置，"
            "未自动注册。请手动把以下 local hook 加入 repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: governance-progress-consistency\n"
            "        name: governance progress consistency\n"
            "        entry: python " + scripts_rel + "/check_progress_consistency.py --staged\n"
            "        language: system\n"
            "        pass_filenames: false"
        )

    # 标准 hooks 目录（plain git 或 core.hooksPath）
    installed_dir = False
    try:
        _write_hook(hooks_dir / "pre-commit", "pre-commit", scripts_rel)
        _write_hook(hooks_dir / "commit-msg", "commit-msg", scripts_rel)
        installed_dir = True
        print(f"[ok] 已安装 governance pre-commit + commit-msg hook → {hooks_dir}")
        print(f"     hook 自定位调用: {scripts_rel}/check_*.py（相对 git 根）")
    except OSError as e:
        warnings.append(f"写入 {hooks_dir} 失败（权限/冲突）: {e}")

    if warnings:
        print("\n[WARN] git 门禁部分未能自动装上（仅丢失'加分项'，基线门禁照常拦截）：",
              file=sys.stderr)
        for w in warnings:
            print("  - " + w, file=sys.stderr)
        if not (installed_dir or husky_dir.is_dir()):
            return 3
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=".")
    args = p.parse_args(argv)
    return install(Path(args.project_root).resolve())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
