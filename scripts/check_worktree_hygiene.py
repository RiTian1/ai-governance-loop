#!/usr/bin/env python3
"""工作树卫生自检：把「工具生成的预期 churn」与「真实改动」分开（git-optional、零依赖）。

规范：domains/operations/housekeeping/index.md §7（ops.housekeeping.r10 / r11）。

它回答字段实战反复踩的一个问题：「推进到一半 git 又冒出几百条脏改动，这些是我改的、
还是工具（BMAD sync / OpenSpec init / 规则导出）重写出来的？能不能安全清掉？」

机制：
  - 读 project-governance.yaml 的 `generated_artifacts:`（glob 列表）；无则用内置默认，
    覆盖本母版已知的生成产物：BMAD 薄壳 / OpenSpec 命令壳 / 导出的 IDE 规则。
  - 跑 `git status --porcelain`，把每条脏路径分类为 generated（预期，可 regenerate/checkout 丢弃）
    或 real（真实改动，需人工判断是否提交）。

用法:
  python scripts/check_worktree_hygiene.py
  python scripts/check_worktree_hygiene.py --assert-clean              # 有任何脏 = 退出 1
  python scripts/check_worktree_hygiene.py --assert-no-generated-churn # 仅当出现生成产物 churn = 退出 1
  python scripts/check_worktree_hygiene.py --assert-staged-pure        # pre-commit：staged 混入生成产物 churn = 退出 1

退出码:
  0 = 通过（默认仅报告；或断言满足）
  1 = 断言失败 / 无法运行
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

# Windows 管道/重定向下默认 locale 编码（GBK）会把中文输出写成乱码；统一 UTF-8
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402

# 内置默认：本母版已知的「工具生成/同步产物」——从 canonical 源确定性重生成，
# 不应手改、也不应把其 churn 混进无关任务的提交。
DEFAULT_GENERATED_GLOBS = [
    ".claude/skills/bmad-*/**",          # BMAD v6.10 安装器产物（sync-upstream.ps1 替换）
    ".claude/skills/openspec-*/**",      # 由 OpenSpec CLI 安装/更新
    ".claude/commands/opsx/*.md",        # 由 OpenSpec init 写入
    ".agents/skills/**",                 # 由 scripts/sync-agent-skills.py 从 .claude/skills 镜像
    ".cursor/rules/governance-*.mdc",    # 由 scripts/export-governance-rules.py 生成
    ".github/copilot-instructions.md",   # 同上
]


def load_generated_globs(root: Path) -> tuple[list[str], str]:
    pg = root / "project-governance.yaml"
    if pg.exists():
        try:
            data = _yaml_safe_load(pg.read_text(encoding="utf-8")) or {}
            globs = data.get("generated_artifacts")
            if isinstance(globs, list) and globs:
                return [str(g) for g in globs], "project-governance.yaml:generated_artifacts"
        except Exception:
            pass
    return list(DEFAULT_GENERATED_GLOBS), "内置默认（未在 project-governance.yaml 声明 generated_artifacts）"


def git_porcelain(root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def git_staged_paths(root: Path) -> list[str] | None:
    """当前 staged（--cached）文件路径列表（posix 风格）。无 git / 出错返回 None。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "--cached", "--name-only"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return [ln.strip().replace("\\", "/") for ln in proc.stdout.splitlines() if ln.strip()]


def parse_path(porcelain_line: str) -> str:
    """从 `XY path` 或 `XY old -> new` 取路径（重命名取新名）。"""
    rest = porcelain_line[3:] if len(porcelain_line) > 3 else porcelain_line
    if " -> " in rest:
        rest = rest.split(" -> ", 1)[1]
    return rest.strip().strip('"').replace("\\", "/")


def is_generated(path: str, globs: list[str]) -> bool:
    for g in globs:
        gg = g.replace("\\", "/")
        if fnmatch.fnmatch(path, gg):
            return True
        # 支持 dir/** 命中 dir 下任意深度
        if gg.endswith("/**") and (path == gg[:-3] or path.startswith(gg[:-2])):
            return True
    return False


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="工作树卫生自检（generated vs real churn）")
    p.add_argument("--governance-root", default=".")
    p.add_argument("--assert-clean", action="store_true", help="有任何脏改动即退出 1")
    p.add_argument("--assert-no-generated-churn", action="store_true",
                   help="出现工具生成产物 churn 即退出 1（提示先 regenerate/checkout）")
    p.add_argument("--assert-staged-pure", action="store_true",
                   help="pre-commit：staged 集合同时含生成产物 churn 与真实改动即退出 1（提示分组提交）")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.governance_root).resolve()
    globs, src = load_generated_globs(root)

    # --assert-staged-pure：只看 staged 集合，阻断"生成产物 churn 与真实改动混在同一次提交"。
    # 工作区其余未 staged 的脏改动不在本闸范围（仅由默认报告/其它断言覆盖），不影响正常 WIP。
    if args.assert_staged_pure:
        staged = git_staged_paths(root)
        if staged is None:
            if not args.quiet:
                print("[i] 无 .git 或 git 不可用：--assert-staged-pure 跳过（git-optional，不阻断）")
            return 0
        if not staged:
            if not args.quiet:
                print("[OK] --assert-staged-pure：无 staged 文件，通过")
            return 0
        staged_generated = [p for p in staged if is_generated(p, globs)]
        staged_real = [p for p in staged if not is_generated(p, globs)]
        if staged_generated and staged_real:
            print("[X] --assert-staged-pure：本次提交把生成产物 churn 与真实改动混在了一起（ops.housekeeping.r12）",
                  file=sys.stderr)
            print(f"    生成产物 churn（{len(staged_generated)}）：", file=sys.stderr)
            for g in staged_generated[:15]:
                print(f"      ~ {g}", file=sys.stderr)
            if len(staged_generated) > 15:
                print(f"      ... 及另外 {len(staged_generated) - 15} 条", file=sys.stderr)
            print(f"    真实改动（{len(staged_real)}）：", file=sys.stderr)
            for r in staged_real[:15]:
                print(f"      * {r}", file=sys.stderr)
            if len(staged_real) > 15:
                print(f"      ... 及另外 {len(staged_real) - 15} 条", file=sys.stderr)
            print("    -> 请分组提交：生成产物用 `sync-*/export-*` 重生成后单独成组提交，"
                  "或先 `git restore --staged <生成产物路径>` 再提交真实改动。", file=sys.stderr)
            return 1
        if not args.quiet:
            kind = "生成产物 churn" if staged_generated else "真实改动"
            print(f"[OK] --assert-staged-pure：staged 集合纯净（全部为{kind}），通过")
        return 0

    lines = git_porcelain(root)
    if lines is None:
        if not args.quiet:
            print("[i] 无 .git 或 git 不可用：工作树卫生检查跳过（git-optional，不阻断）")
        return 0

    generated: list[str] = []
    real: list[str] = []
    for ln in lines:
        path = parse_path(ln)
        (generated if is_generated(path, globs) else real).append(f"{ln[:2]} {path}")

    if not args.quiet:
        print(f"# 工作树卫生（生成产物 glob 来源：{src}）")
        print(f"生成产物 churn（可 regenerate/checkout 丢弃）：{len(generated)}")
        for g in generated[:15]:
            print(f"  ~ {g}")
        if len(generated) > 15:
            print(f"  ... 及另外 {len(generated) - 15} 条")
        print(f"真实改动（需人工判断是否提交）：{len(real)}")
        for r in real[:30]:
            print(f"  * {r}")
        if len(real) > 30:
            print(f"  ... 及另外 {len(real) - 30} 条")
        print()
        if generated:
            print("-> 生成产物 churn 建议：`python scripts/sync-agent-skills.py --prune` /"
                  " `python scripts/export-governance-rules.py` 重生成后一并提交，"
                  "或 `git checkout -- <路径>` 丢弃；勿混入无关任务提交（ops.housekeeping.r10）")

    rc = 0
    if args.assert_clean and (generated or real):
        if not args.quiet:
            print("[X] --assert-clean：工作树非干净")
        rc = 1
    if args.assert_no_generated_churn and generated:
        if not args.quiet:
            print("[X] --assert-no-generated-churn：存在工具生成产物 churn，先重生成或丢弃再收尾")
        rc = 1
    return rc


def _main_failclosed(argv: list[str]) -> int:
    try:
        return main(argv)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"[BLOCKED] check_worktree_hygiene 无法完成运行: {e!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main_failclosed(sys.argv[1:]))
