#!/usr/bin/env python3
"""Commit message 协议校验（pre-commit / commit-msg hook 用）

按 foundations/progress-traceability-and-binding.md §3.5 与
domains/tooling/progress-binding/_summary.yaml tool.binding.r4。

要求格式（必须）：
  Story: <story_id> [<status-from> -> <status-to>]
  Change: <change_id|none>
  Revision: <revision_id|none>
  Rules: <rule_id_1>+, <rule_id_2>~, <rule_id_3>-     # + 新增 / ~ 修改 / - 删除
  PRD: <fr_id_1>, <fr_id_2>

至少满足：
  - 含 Story: 行
  - Change/Revision/Rules 中至少一行非 none

本检查是**可选附加层**：commit / git 历史校验只在"目标项目自己有 .git"时才跑。
无 .git 的项目（便携治理的默认场景之一）由同步台账（P2 `_logs/sync-ledger.md`）
承担同等审计职责，本脚本直接豁免返回 0。零依赖：不依赖 pyyaml。

豁免（不强制 trailer）：
  - 项目无 .git（commit 协议不适用，由同步台账替代）
  - merge commit (parent count >= 2)
  - revert commit (subject 以 "Revert " 开头)
  - bot commit (subject 含 [skip-trailer])
  - WIP commit (subject 以 "wip:" 开头)，但本地推送前必须修
  - 项目尚未启用 tooling/progress-binding（由 project-governance.yaml 控制）

用法:
  # 由 git commit-msg hook 调用，传入 commit message 文件路径
  python scripts/check_commit_message.py .git/COMMIT_EDITMSG

  # 校验任意 commit (从 stdin / 字符串 / git rev)
  python scripts/check_commit_message.py --rev HEAD
  echo "Subject..." | python scripts/check_commit_message.py -

退出码:
  0 = OK 或豁免
  1 = 违规
  2 = 调用错误
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402


def has_git(root: Path) -> bool:
    """commit-message 协议是**可选附加层**，仅当目标项目自己有 git 时才适用。
    无 git 时由同步台账检查（P2 _logs/sync-ledger.md）替代。"""
    p = root
    for _ in range(40):
        if (p / ".git").exists():
            return True
        if p.parent == p:
            break
        p = p.parent
    return False


STORY_LINE = re.compile(r"^Story:\s*([a-z][a-z0-9-]*\.S\d{2}\.\d{2})\b", re.M)
CHANGE_LINE = re.compile(r"^Change:\s*(\S+)", re.M)
REVISION_LINE = re.compile(r"^Revision:\s*(\S+)", re.M)
RULES_LINE = re.compile(r"^Rules:\s*(.+)$", re.M)


def is_exempt(msg: str, rev: str | None, root: Path) -> tuple[bool, str]:
    first = msg.split("\n", 1)[0].strip()
    if first.startswith("Revert "):
        return True, "revert"
    if first.lower().startswith("wip:"):
        return True, "wip"
    if "[skip-trailer]" in msg:
        return True, "skip-trailer marker"
    if rev:
        try:
            r = subprocess.run(["git", "rev-list", "--parents", "-n", "1", rev],
                               cwd=root, capture_output=True, text=True, check=False)
            parents = (r.stdout or "").split()
            if len(parents) > 2:
                return True, "merge commit"
        except Exception:
            pass

    # 项目开关豁免（零依赖解析 project-governance.yaml）。
    # L1 域隐含其 L2 子域（00-index.yaml 层级语义）：enabled_domains 列出
    # "tooling" 即视为启用 tooling/progress-binding，无需显式列子域。
    manifest = root / "project-governance.yaml"
    if manifest.exists():
        try:
            data = _yaml_safe_load(manifest.read_text(encoding="utf-8")) or {}
            domains = {str(d).strip() for d in (data.get("enabled_domains") or [])}
            if not domains & {"tooling", "tooling/progress-binding"}:
                return True, "tooling (progress-binding) not enabled in project-governance.yaml"
        except Exception:
            pass

    return False, ""


def load_code_paths(root: Path) -> list[str]:
    """manifest code_paths glob 列表（tool.binding.r11）；缺失/为空 = 不启用代码硬闸。"""
    manifest = root / "project-governance.yaml"
    if not manifest.exists():
        return []
    try:
        data = _yaml_safe_load(manifest.read_text(encoding="utf-8")) or {}
        return [str(g).strip() for g in (data.get("code_paths") or []) if str(g).strip()]
    except Exception:
        return []


def changed_files(root: Path, rev: str | None) -> list[str]:
    """本次提交涉及的文件：--rev 用该 commit 的 diff-tree；否则用 staged 集合（commit-msg hook 时点）。"""
    if rev:
        args = ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", rev]
    else:
        args = ["git", "diff", "--cached", "--name-only"]
    try:
        r = subprocess.run(args, cwd=root, capture_output=True, text=True,
                           check=False, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return []
        return [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    except Exception:
        return []


def hits_code_paths(files: list[str], globs: list[str]) -> list[str]:
    import fnmatch
    hits = []
    for f in files:
        for g in globs:
            if fnmatch.fnmatch(f, g) or (g.endswith("/**") and f.startswith(g[:-3] + "/")):
                hits.append(f)
                break
    return hits


# trailer 的"空值"写法。git 世界里写 none 的人也会写 NULL / N/A / -，
# 只认字面 "none" 会让 `Change: NULL` 冒充一个真实 change（对抗集 K11/K12 抓到）。
NONE_VALUES = {"none", "null", "nil", "n/a", "na", "-", "—", ""}


def trailer_block(msg: str) -> str:
    """按 git 语义取 trailer 区：最后一个空行之后的连续非空行。

    原实现用 `^Story:` 全文搜索，于是**正文里任意一行**以 `Story:` 开头都算数——
    引用别人的 commit message 就能凑齐 trailer（对抗集 K10/K13 抓到）。
    git 的 trailer 是"最后一段连续 Key: Value 行"，按这个语义取才不会被正文污染。
    """
    lines = msg.rstrip().splitlines()
    block: list = []
    for ln in reversed(lines):
        if not ln.strip():
            break
        block.append(ln)
    return "\n".join(reversed(block))


def _is_none(value: str) -> bool:
    return value.strip().strip('"\'`').lower() in NONE_VALUES


def validate(msg: str, code_hits: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    block = trailer_block(msg)

    story_ids = STORY_LINE.findall(block)
    if not story_ids:
        errors.append("missing 'Story: <story_id>' trailer")
    elif len(set(story_ids)) > 1:
        # 多写一行伪造的 Story 就能"覆盖"真实意图——必须报冲突而不是取第一个
        errors.append("conflicting 'Story:' trailers: %s"
                      % ", ".join(sorted(set(story_ids))))

    chg = CHANGE_LINE.search(block)
    rev = REVISION_LINE.search(block)
    rls = RULES_LINE.search(block)

    have_non_none = False
    for m in (chg, rev, rls):
        if m and not _is_none(m.group(1)):
            have_non_none = True
    if not (chg or rev or rls):
        errors.append("missing all of Change/Revision/Rules trailers (at least one required)")
    elif not have_non_none:
        errors.append("Change/Revision/Rules all 'none' — at least one must be non-none")

    # tool.binding.r11：业务代码变更必须挂 OpenSpec change（双载体，防 PRD/spec 落后实现）
    if code_hits:
        change_ok = bool(chg and not _is_none(chg.group(1)))
        if not change_ok:
            sample = ", ".join(code_hits[:3]) + ("…" if len(code_hits) > 3 else "")
            errors.append(
                f"commit touches code_paths ({sample}) but 'Change:' is missing/none — "
                f"业务代码变更必须挂 OpenSpec change（tool.binding.r11 双载体）")
    return errors


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path_or_dash", nargs="?", default="-",
                   help="commit-msg file path, or '-' to read stdin, or omit when using --rev")
    p.add_argument("--rev", default=None, help="check given git revision instead")
    p.add_argument("--governance-root", default=".")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.governance_root).resolve()

    if not has_git(root):
        if not args.quiet:
            print("[skip] no .git found — commit-message check not applicable "
                  "(superseded by sync-ledger check, see P2)")
        return 0

    if args.rev:
        try:
            r = subprocess.run(["git", "log", "--format=%B", "-n", "1", args.rev],
                               cwd=root, capture_output=True, text=True, check=False, encoding="utf-8")
            msg = r.stdout
        except Exception as e:
            print(f"ERROR reading rev {args.rev}: {e}", file=sys.stderr)
            return 2
    elif args.path_or_dash == "-":
        msg = sys.stdin.read()
    else:
        f = Path(args.path_or_dash)
        if not f.exists():
            print(f"ERROR: file not found: {f}", file=sys.stderr)
            return 2
        msg = f.read_text(encoding="utf-8", errors="replace")

    exempt, reason = is_exempt(msg, args.rev, root)
    if exempt:
        if not args.quiet:
            print(f"[skip] commit message check exempt: {reason}")
        return 0

    code_globs = load_code_paths(root)
    code_hits = hits_code_paths(changed_files(root, args.rev), code_globs) if code_globs else []

    errors = validate(msg, code_hits)
    if errors:
        print("Commit message FAILED progress-binding check:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\nExpected trailers (see foundations/progress-traceability-and-binding.md §3.5):", file=sys.stderr)
        print("  Story: <project_id>.S<NN>.<MM> [<status-from> -> <status-to>]", file=sys.stderr)
        print("  Change: <change_id|none>", file=sys.stderr)
        print("  Revision: <revision_id|none>", file=sys.stderr)
        print("  Rules: <rule_id>+, <rule_id>~          # +new, ~modify, -remove", file=sys.stderr)
        print("  PRD: <fr_id>, ...", file=sys.stderr)
        return 1

    if not args.quiet:
        print("[ok] commit message passes progress-binding check")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
