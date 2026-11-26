#!/usr/bin/env python3
"""
Export governance domains to IDE rule files.

Outputs:
  .cursor/rules/governance-*.mdc
  .github/copilot-instructions.md (summary, review-safe length)

Usage:
  python scripts/export-governance-rules.py [--project-root .] [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402

COPILOT_REVIEW_LIMIT = 4000
CURSOR_RULE_MAX_LINES = 120

# 便携闭环治理的"入口不可跳过协议"——作为 always-applied 的导出产物，
# 与 AGENTS.md / CLAUDE.md 的 STOP 门保持同源同步（改这里 + 重跑导出）。
CLOSED_LOOP_PROTOCOL = """# Closed-loop CRUD protocol (MUST / STOP)

任何对 BMAD Story / OpenSpec change / Revision / Rule / PRD-FR 的创建 / 修改 / 状态变更（CRUD）都是一次同步事件，MUST：

1. 动手前先产出"受影响工件清单"（Story / Change / Revision / Rule / PRD-FR），确认三端反向引用对齐。
2. STOP：`completed` / `done` / `archived` / `active_sprint` / `status=merged` 为高风险字段，
   在 `python scripts/check_progress_consistency.py` 通过前禁止写入；状态字段是最后一步且必须联动其它工件。
3. 新增收敛工作必须新建 story/change，禁止挂到已 `done`/`archived` 的 Story。
4. 收尾前必须贴出 `check_progress_consistency.py` 的通过输出（exit 0）作为完成证据（脚本零依赖、无 .git 亦可跑）。
5. fail-closed：任一检查失败（exit != 0）→ 不许 commit、不许标完成、不许归档；先消除漂移或登记合法豁免。
6. 检查点协议（`tool.binding.r10`，全文见 `05-ai-collaboration-policy.md` §7.3）：用户明确要求收尾、归档、提交，或当前变更已达到收尾阶段且即将开启
   新 OpenSpec 变更时，MUST 依次——查工作区变动并归因（`scripts/check_worktree_hygiene.py`）→
   判当前 change 可否归档 → 可归档则询问用户是否勾选人工验证标志、确认后归档 → 归档与代码工件同一次提交 →
   校验 BMAD PRD ↔ OpenSpec 双向同步 → 以 `<type>(<scope>): <中文描述>` + trailers 提交并 push →
   分支从主分支新拉、解冲突后 push，merge 由用户执行。普通继续、CLI 原生 resume 和压缩不触发此检查点。

git 门禁（`scripts/install_git_hooks.py`）仅"有 .git 才加分"；地基 = 零依赖自检 + 本协议 + `_logs/sync-ledger.md` 台账。
"""


def load_manifest(root: Path) -> dict:
    path = root / "project-governance.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return _yaml_safe_load(path.read_text(encoding="utf-8")) or {}


def governance_root(root: Path, manifest: dict) -> Path:
    gr = manifest.get("governance_root", ".")
    layout = manifest.get("governance_layout", "docs-governance-subtree")
    if layout == "mother-repo-root":
        return root
    return root / gr


def resolve_domain_path(groot: Path, domain: str) -> Path | None:
    direct = groot / "domains" / f"{domain}.md"
    if direct.exists():
        return direct
    index = groot / "domains" / domain / "index.md"
    if index.exists():
        return index
    # 顶层树（与 domains/ 同级）：projects/ business-references/ 等
    tree_index = groot / domain / "index.md"
    if tree_index.exists():
        return tree_index
    return None


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def trim_for_copilot(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    note = (
        "\n\n<!-- TRUNCATED: full rules in .cursor/rules/governance-*.mdc "
        "and domains/ — regenerate with scripts/export-governance-rules.py -->\n"
    )
    return text[: limit - len(note)] + note


def build_cursor_rule(domain: str, body: str) -> str:
    lines = body.strip().splitlines()
    if len(lines) > CURSOR_RULE_MAX_LINES:
        body = "\n".join(lines[:CURSOR_RULE_MAX_LINES]) + "\n\n<!-- truncated -->\n"
    return (
        "---\n"
        f"description: Governance domain — {domain}\n"
        "alwaysApply: false\n"
        "globs:\n"
        "  - \"**/*\"\n"
        "---\n\n"
        f"{body.strip()}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    manifest = load_manifest(root)
    groot = governance_root(root, manifest)
    domains = manifest.get("enabled_domains") or []

    if not domains:
        print("WARN: enabled_domains empty — export core policies only", file=sys.stderr)
        domains = ["coding-standards"]

    cursor_dir = root / ".cursor" / "rules"
    copilot_path = root / ".github" / "copilot-instructions.md"

    # always-applied 闭环协议规则（入口不可跳过 STOP 门）
    closed_loop_rule = (
        "---\n"
        "description: Governance closed-loop CRUD protocol (MUST/STOP)\n"
        "alwaysApply: true\n"
        "globs:\n"
        "  - \"**/*\"\n"
        "---\n\n"
        f"{CLOSED_LOOP_PROTOCOL.strip()}\n"
    )
    if args.dry_run:
        print(f"Would write {cursor_dir / 'governance-closed-loop.mdc'} ({len(closed_loop_rule)} bytes)")
    else:
        cursor_dir.mkdir(parents=True, exist_ok=True)
        (cursor_dir / "governance-closed-loop.mdc").write_text(closed_loop_rule, encoding="utf-8")
        print(f"Wrote {cursor_dir / 'governance-closed-loop.mdc'}")

    sections: list[str] = [
        "# Copilot instructions (generated)\n",
        "Do not edit by hand; run `python scripts/export-governance-rules.py`.\n",
        f"Governance root: `{groot.relative_to(root)}`\n",
        f"\n{CLOSED_LOOP_PROTOCOL.strip()}\n",
        "## Authority\n",
        "- Verification policy overrides agent defaults.\n",
        "- Load `project-governance.yaml` before large changes.\n",
        "## Enabled domains\n",
    ]

    exported = 0  # 已启用 domain 计数（闭环协议规则单独始终导出）
    for domain in domains:
        path = resolve_domain_path(groot, domain)
        if not path:
            print(f"SKIP: domain not found: {domain}", file=sys.stderr)
            continue
        body = path.read_text(encoding="utf-8")
        slug = slugify(domain)
        rule_name = f"governance-{slug}.mdc"
        rule_content = build_cursor_rule(domain, body)

        if args.dry_run:
            print(f"Would write {cursor_dir / rule_name} ({len(rule_content)} bytes)")
        else:
            cursor_dir.mkdir(parents=True, exist_ok=True)
            (cursor_dir / rule_name).write_text(rule_content, encoding="utf-8")
            print(f"Wrote {cursor_dir / rule_name}")

        sections.append(f"\n### {domain}\n\n{body[:800]}\n")
        exported += 1

    # Core verification excerpt
    ver = groot / "04-verification-policy.md"
    if ver.exists():
        sections.append("\n## Verification (excerpt)\n\n")
        sections.append(ver.read_text(encoding="utf-8")[:1500])

    copilot_body = trim_for_copilot("".join(sections), COPILOT_REVIEW_LIMIT)

    if args.dry_run:
        print(f"Would write {copilot_path} ({len(copilot_body)} bytes)")
    else:
        copilot_path.parent.mkdir(parents=True, exist_ok=True)
        copilot_path.write_text(copilot_body, encoding="utf-8")
        print(f"Wrote {copilot_path}")

    print(f"Exported {exported} domain(s) + closed-loop protocol rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
