#!/usr/bin/env python3
"""扫描 git history，把每个 revision 关联的 commit 列表写回 meta.yaml

按 foundations/progress-traceability-and-binding.md §3.3 commits 字段：
revision merged 后，本脚本通过扫 git log 找出 commit message 中含本 revision_id
的所有提交，写入 revisions/<id>/meta.yaml 的 commits 字段。

也对单 markdown 形态的 revision 做尽力而为：在文件末尾添加 / 更新 commits trailer。

用法:
  python scripts/link_revision_to_commits.py                      # 全量扫描，更新所有 revision
  python scripts/link_revision_to_commits.py --revision rev-...   # 仅指定 revision
  python scripts/link_revision_to_commits.py --dry-run

可作为 git post-merge / post-checkout hook 调用。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed.", file=sys.stderr)
    sys.exit(2)


def find_commits(root: Path, ident: str) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "log", "--all", "--pretty=%h %s", "--grep", ident, "-200"],
            cwd=root, capture_output=True, text=True, check=False, encoding="utf-8",
        )
        commits: list[str] = []
        for line in (r.stdout or "").splitlines():
            sha = line.split(" ", 1)[0].strip()
            if sha:
                commits.append(sha)
        # 去重保序
        seen, out = set(), []
        for c in commits:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out
    except Exception:
        return []


def update_meta_yaml(meta_path: Path, commits: list[str], dry_run: bool) -> bool:
    text = meta_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text) or {}
    except Exception as e:
        print(f"  ! yaml parse error: {meta_path}: {e}", file=sys.stderr)
        return False
    existing = data.get("commits") or []
    if existing == commits:
        return False
    data["commits"] = commits
    if dry_run:
        print(f"  [dry-run] would update commits in {meta_path}: {commits}")
        return True
    meta_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                         encoding="utf-8")
    print(f"  [updated] {meta_path}: {len(commits)} commit(s)")
    return True


def update_md_trailer(md_path: Path, revision_id: str, commits: list[str], dry_run: bool) -> bool:
    text = md_path.read_text(encoding="utf-8")
    trailer_re = re.compile(r"\n\n<!-- commits:.*?-->\s*$", re.S)
    new_trailer = f"\n\n<!-- commits: {','.join(commits)} (auto-fill by link_revision_to_commits.py for {revision_id}) -->\n"
    if trailer_re.search(text):
        new_text = trailer_re.sub(new_trailer.rstrip("\n"), text)
    else:
        new_text = text.rstrip("\n") + new_trailer
    if new_text == text:
        return False
    if dry_run:
        print(f"  [dry-run] would update trailer in {md_path}")
        return True
    md_path.write_text(new_text, encoding="utf-8")
    print(f"  [updated trailer] {md_path}: {len(commits)} commit(s)")
    return True


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--governance-root", default=".")
    p.add_argument("--revision", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.governance_root).resolve()
    rev_root = root / "revisions"
    if not rev_root.exists():
        print("revisions/ not found")
        return 0

    targets: list[tuple[Path, str, str]] = []  # (path, kind, revision_id)
    # 结构化目录形态
    for sub in list(rev_root.rglob("meta.yaml")):
        if "_logs" in sub.parts:
            continue
        try:
            data = yaml.safe_load(sub.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        rid = data.get("revision_id")
        if not rid:
            continue
        targets.append((sub, "yaml", rid))
    # 单 md 兼容
    for md in list(rev_root.rglob("*.md")):
        if md.name in ("README.md", "WORKFLOW.md"):
            continue
        if "_logs" in md.parts:
            continue
        m = re.match(r"^---\s*\n(.*?)\n---", md.read_text(encoding="utf-8", errors="replace"), re.S)
        rid = None
        if m:
            try:
                front = yaml.safe_load(m.group(1)) or {}
                rid = front.get("revision_id") or front.get("id")
            except Exception:
                pass
        if not rid:
            stem = md.stem
            if stem.endswith("-candidate"):
                stem = stem[: -len("-candidate")]
            rid = f"rev-{stem}"
        targets.append((md, "md", rid))

    if args.revision:
        targets = [t for t in targets if t[2] == args.revision]
        if not targets:
            print(f"no revision matched: {args.revision}")
            return 1

    print(f"scanning {len(targets)} revision target(s)...")
    updated = 0
    for path, kind, rid in targets:
        commits = find_commits(root, rid)
        if not commits:
            continue
        print(f"  {rid}: {len(commits)} commit(s) found")
        if kind == "yaml":
            if update_meta_yaml(path, commits, args.dry_run):
                updated += 1
        else:
            if update_md_trailer(path, rid, commits, args.dry_run):
                updated += 1

    print(f"\ndone: {updated} file(s) {'would be ' if args.dry_run else ''}updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
