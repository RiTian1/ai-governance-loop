#!/usr/bin/env python3
"""
Sync .claude/skills/bmad-* stubs to canonical _bmad/ sources.

Reads _bmad/_config/skill-manifest.csv and writes thin SKILL.md entrypoints.
Optionally prunes duplicate files under .claude/skills (see --prune).

Usage:
  python scripts/sync-bmad-skills.py [--prune] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "_bmad" / "_config" / "skill-manifest.csv"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

STUB_TEMPLATE = """---
name: {name}
description: {description}
canonical_source: {canonical_dir}
---

# BMAD skill stub (do not edit workflow here)

**Canonical source:** `{canonical_dir}/`

Edits to workflow steps, templates, and data belong under `_bmad/` only.
Regenerate this stub: `python scripts/sync-bmad-skills.py`

## Activation

1. Read `{canonical_skill}` from the canonical directory.
2. If the skill needs config, run `bmad-init` (`_bmad/core/bmad-init/`).
3. Follow `workflow.md` in the canonical directory when present.

Do **not** follow `./workflow.md` in this stub folder — it may have been pruned.
"""


def load_manifest() -> list[dict]:
    rows = []
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def prune_skill_dir(skill_dir: Path, dry_run: bool) -> int:
    removed = 0
    if not skill_dir.is_dir():
        return 0
    for item in skill_dir.iterdir():
        if item.name in ("SKILL.md", ".bmad-stub"):
            continue
        if dry_run:
            print(f"  would remove {item.relative_to(REPO_ROOT)}")
        else:
            if item.is_dir():
                import shutil
                shutil.rmtree(item)
            else:
                item.unlink()
        removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prune", action="store_true", help="Remove duplicate files under skill dirs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"ERROR: missing {MANIFEST}", file=sys.stderr)
        return 2

    rows = load_manifest()
    synced = 0
    pruned = 0

    for row in rows:
        name = row["name"].strip()
        description = row["description"].strip().replace('"', "'")
        canonical_skill = row["path"].strip()
        canonical_dir = str(Path(canonical_skill).parent).replace("\\", "/")

        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        content = STUB_TEMPLATE.format(
            name=name,
            description=description,
            canonical_dir=canonical_dir,
            canonical_skill=canonical_skill,
        )

        skill_md = skill_dir / "SKILL.md"
        if args.dry_run:
            print(f"Would write {skill_md.relative_to(REPO_ROOT)}")
        else:
            skill_md.write_text(content, encoding="utf-8")
            (skill_dir / ".bmad-stub").write_text(canonical_dir + "\n", encoding="utf-8")

        if args.prune:
            pruned += prune_skill_dir(skill_dir, args.dry_run)

        synced += 1

    print(f"Synced {synced} skill stub(s); pruned {pruned} path(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
