#!/usr/bin/env python3
"""把 .claude/skills/*/SKILL.md 镜像到 .agents/skills/ 的跨工具兼容层（零依赖、跨平台）。

规范：domains/tooling/_summary.yaml tool.r5；domains/agent-tooling-mcp.md §10。

动机：Cursor 会兼容加载 `.claude/skills/`，但 OpenAI Codex（2025-12 起 skills 化）
只发现 `.agents/skills/`（repo）与 `~/.agents/skills/`（global），发现不了 `.claude/skills/`。
两侧都遵循 Agent Skills 开放标准。本脚本把 `.claude/skills`（含 BMAD 薄壳 + OpenSpec 技能）
确定性镜像成 `.agents/skills` 下的薄入口，让 Codex 与 Cursor 获得同等的技能发现能力。

生成物属于 `generated_artifacts`（ops.housekeeping.r10）：不手改，改源后重跑本脚本。

用法:
  python scripts/sync-agent-skills.py [--prune] [--dry-run]

退出码: 0 成功 / 2 源目录缺失
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / ".claude" / "skills"
DST_DIR = REPO_ROOT / ".agents" / "skills"
MARKER = ".agents-mirror"

STUB_TEMPLATE = """---
name: {name}
description: {description}
canonical_source: {canonical}
---

# Agent Skills 镜像入口（跨工具兼容层，勿手改）

本文件由 `scripts/sync-agent-skills.py` 从 `{src}` 确定性生成，供 Codex / 其它读取
`.agents/skills/` 的 agent 发现本技能。**权威工作流在 canonical 源，不在此处。**

## Activation

1. 读取 canonical 源：`{canonical}`
2. 按其中的 `SKILL.md` / `workflow.md` 执行；如需配置见治理入口 `AGENTS.md`。

Regenerate: `python scripts/sync-agent-skills.py --prune`
"""


def parse_frontmatter(text: str) -> dict:
    text = text.lstrip("\ufeff")  # 源文件可能带 UTF-8 BOM
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip("\n")
    try:
        data = _yaml_safe_load(block) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def canonical_of(skill_dir: Path, fm: dict) -> str:
    cs = fm.get("canonical_source")
    if cs:
        return str(cs).replace("\\", "/")
    # 无声明（如 OpenSpec 技能本身即 canonical）→ 指回 .claude/skills 源目录
    return skill_dir.relative_to(REPO_ROOT).as_posix()


def prune(known: set[str], dry_run: bool) -> int:
    removed = 0
    if not DST_DIR.is_dir():
        return 0
    import shutil
    for item in DST_DIR.iterdir():
        if not item.is_dir():
            continue
        if item.name in known:
            continue
        # 只删本脚本生成的镜像（带 marker），避免误删手工技能
        if not (item / MARKER).exists():
            continue
        if dry_run:
            print(f"  would prune {item.relative_to(REPO_ROOT).as_posix()}")
        else:
            shutil.rmtree(item)
        removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true", help="删除源已不存在的镜像技能")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not SRC_DIR.is_dir():
        print(f"ERROR: missing source {SRC_DIR}", file=sys.stderr)
        return 2

    synced = 0
    known: set[str] = set()
    for skill_dir in sorted(SRC_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue
        fm = parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
        name = str(fm.get("name") or skill_dir.name).strip()
        desc = str(fm.get("description") or "").strip().replace("\n", " ")
        canonical = canonical_of(skill_dir, fm)
        src_rel = skill_dir.relative_to(REPO_ROOT).as_posix()

        known.add(name)
        dst = DST_DIR / name
        content = STUB_TEMPLATE.format(name=name, description=desc, canonical=canonical, src=src_rel)
        if args.dry_run:
            print(f"Would write {(dst / 'SKILL.md').relative_to(REPO_ROOT).as_posix()}")
        else:
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "SKILL.md").write_text(content, encoding="utf-8")
            (dst / MARKER).write_text(src_rel + "\n", encoding="utf-8")
        synced += 1

    pruned = prune(known, args.dry_run)
    print(f"Mirrored {synced} skill(s) to .agents/skills; pruned {pruned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
