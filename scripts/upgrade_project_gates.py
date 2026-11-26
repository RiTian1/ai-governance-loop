#!/usr/bin/env python3
"""存量项目一键升级：把母版的"确定性门禁 bundle"同步进目标项目并当场激活。

规范：docs/governance/INTEGRATION-GUIDE.md §3.3（存量项目升级）、
      domains/tooling/_summary.yaml（tool.r7）。

它解决的问题：早期集成的项目用的是旧治理快照，缺少后来新增的门禁脚本
（install_governance_gates / check_worktree_hygiene / 各安装器 / Cursor hooks 模板），
导致新写的确定性闸在存量项目里"根本不存在"。本脚本从**母版侧**运行，把这批
门禁 bundle 幂等同步到目标项目的治理内容根，然后调用统一入口安装 hook + 自检。

设计定位：
  - 幂等、非破坏：只覆盖 bundle 清单内的文件，绝不动目标已裁剪的治理文档 / 业务代码。
  - 显式清单：只同步下面 GATE_BUNDLE 明确列出的文件，不做全量覆盖。
  - 无 git 目标：同步后统一入口会优雅降级（不装 git hook），闭环仍由基线保证。

用法:
  python scripts/upgrade_project_gates.py --target D:\\path\\to\\project
  python scripts/upgrade_project_gates.py --target . --dry-run
  python scripts/upgrade_project_gates.py --target ../proj --with-cursor-hooks

退出码:
  0 = bundle 已同步且目标闭环自检通过
  1 = 无法定位目标治理内容根 / 同步失败 / 目标自检未通过
  2 = CLI 用法错误
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
MOTHER_GOV_ROOT = SCRIPTS_DIR.parent  # 母版治理内容根

sys.path.insert(0, str(SCRIPTS_DIR))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402

# 新门禁文件：存量项目通常缺失，始终同步（覆盖差异版本，保证门禁引擎一致）。
GATE_NEW = [
    "scripts/install_governance_gates.py",
    "scripts/install_git_hooks.py",
    "scripts/install_cursor_hooks.py",
    "scripts/check_worktree_hygiene.py",
    "scripts/check_staged_content.py",
    "scripts/check_context_budget.py",
    "templates/cursor-hooks/hooks.json.example",
    "templates/cursor-hooks/guard_dangerous_command.py",
    "templates/cursor-hooks/checkpoint_consistency.py",
    "templates/ci/github-actions-governance-gates.yml",
    "templates/ci/gitlab-ci-governance-gates.yml",
]

# 引擎脚本：目标可能已裁剪定制。默认「仅在缺失时添加」，不覆盖既有；
# 需要与母版对齐版本时用 --force-engine 显式覆盖。
GATE_ENGINE = [
    "scripts/check_progress_consistency.py",
    "scripts/check_commit_message.py",
    "scripts/_governance_yaml.py",
]


def resolve_target_gov_root(target_root: Path) -> Path | None:
    """定位目标治理内容根：读 project-governance.yaml 的 governance_root；兜底 docs/governance/ / 目标根。"""
    pg = target_root / "project-governance.yaml"
    if pg.exists():
        try:
            data = _yaml_safe_load(pg.read_text(encoding="utf-8")) or {}
            gr = data.get("governance_root")
            if gr:
                cand = (target_root / gr).resolve() if gr != "." else target_root
                if cand.exists():
                    return cand
        except Exception:
            pass
    if (target_root / "docs" / "governance").is_dir():
        return (target_root / "docs" / "governance").resolve()
    # mother-repo-root 布局或无声明：治理内容就在目标根
    if (target_root / "00-index.yaml").exists() or (target_root / "scripts").is_dir():
        return target_root
    return None


def _copy(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    try:
        dst.chmod(0o755)
    except OSError:
        pass


def sync_bundle(dst_gov_root: Path, dry_run: bool, force_engine: bool
                ) -> tuple[int, int, list[str], list[str]]:
    """返回 (written, unchanged, missing_sources, engine_drift_kept)。"""
    written = unchanged = 0
    missing: list[str] = []
    engine_drift_kept: list[str] = []

    # 1) 新门禁文件：始终同步（覆盖差异版本）
    for rel in GATE_NEW:
        src = MOTHER_GOV_ROOT / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst = dst_gov_root / rel
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            unchanged += 1
            continue
        action = ("would update" if dst.exists() else "would add") if dry_run else \
                 ("updated" if dst.exists() else "added")
        _copy(src, dst, dry_run)
        written += 1
        print(f"  [{action}] {rel}")

    # 2) 引擎脚本：缺失才加；已存在且有差异默认保留（除非 --force-engine）
    for rel in GATE_ENGINE:
        src = MOTHER_GOV_ROOT / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst = dst_gov_root / rel
        if not dst.exists():
            _copy(src, dst, dry_run)
            written += 1
            print(f"  [{'would add' if dry_run else 'added'}] {rel}（引擎缺失，补齐）")
            continue
        if dst.read_bytes() == src.read_bytes():
            unchanged += 1
            continue
        if force_engine:
            _copy(src, dst, dry_run)
            written += 1
            print(f"  [{'would overwrite' if dry_run else 'overwritten'}] {rel}（--force-engine）")
        else:
            engine_drift_kept.append(rel)
            print(f"  [kept] {rel}（目标版本与母版不同，默认保留；如需对齐加 --force-engine）")
    return written, unchanged, missing, engine_drift_kept


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="存量项目门禁 bundle 一键升级")
    ap.add_argument("--target", required=True, help="目标项目根目录")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写文件、不安装")
    ap.add_argument("--with-cursor-hooks", action="store_true", help="同时装 Cursor 本地闸")
    ap.add_argument("--skip-activate", action="store_true", help="只同步 bundle，不调统一入口安装/自检")
    ap.add_argument("--force-engine", action="store_true",
                    help="引擎脚本（consistency/commit-msg/_governance_yaml）即使已存在也用母版覆盖")
    args = ap.parse_args(argv)

    target_root = Path(args.target).resolve()
    if not target_root.is_dir():
        print(f"[X] 目标不是目录: {target_root}", file=sys.stderr)
        return 1
    if target_root == MOTHER_GOV_ROOT:
        print("[X] 目标即母版自身；升级 bundle 无意义（母版是 canonical 源）。", file=sys.stderr)
        return 1

    gov_root = resolve_target_gov_root(target_root)
    if gov_root is None:
        print(f"[X] 无法定位目标治理内容根（缺 project-governance.yaml/governance_root、"
              f"也无 docs/governance 或 00-index.yaml）: {target_root}", file=sys.stderr)
        return 1

    print(f"# 门禁 bundle 升级")
    print(f"  母版源:   {MOTHER_GOV_ROOT}")
    print(f"  目标项目: {target_root}")
    print(f"  目标治理根: {gov_root}")
    print(f"  模式:     {'dry-run（只报告）' if args.dry_run else '写入'}\n")

    written, unchanged, missing, engine_kept = sync_bundle(gov_root, args.dry_run, args.force_engine)
    print(f"\n同步结果：写入/更新 {written}，未变 {unchanged}，"
          f"引擎保留 {len(engine_kept)}，母版缺失源 {len(missing)}")
    if missing:
        for m in missing:
            print(f"  [!] 母版缺少源文件（跳过）: {m}", file=sys.stderr)
    if engine_kept:
        print("  [i] 引擎脚本保留了目标既有版本；若门禁自检报"
              "「不认识 --governance-root/--staged」等旧接口错误，重跑时加 --force-engine。")

    if args.dry_run or args.skip_activate:
        print("\n[i] 未执行门禁激活（dry-run / --skip-activate）。"
              "手动激活：python <目标治理根>/scripts/install_governance_gates.py "
              "--project-root <目标根> --governance-root <目标治理根>")
        return 0

    print("\n" + "=" * 60)
    print("[激活] 在目标项目跑统一门禁入口")
    print("=" * 60)
    # 自检 --governance-root 传目标项目根（与 git hook 内 $GOV_ROOT 同一约定）：
    # 各项目引擎（项目定制版 checker）以项目根为入参、自行解析 subtree 布局。
    cmd = [sys.executable, str(gov_root / "scripts" / "install_governance_gates.py"),
           "--project-root", str(target_root), "--governance-root", str(target_root)]
    if args.with_cursor_hooks:
        cmd.append("--with-cursor-hooks")
    try:
        rc = subprocess.run(cmd).returncode
    except Exception as e:  # noqa: BLE001
        print(f"[X] 激活失败: {e!r}", file=sys.stderr)
        return 1
    if rc == 1:
        print("\n[X] 目标闭环自检未通过（漂移已可见）；bundle 已同步，先在目标消除漂移。")
        return 1
    print("\n[OK] bundle 已同步且门禁已激活。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
