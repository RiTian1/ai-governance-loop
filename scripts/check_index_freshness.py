#!/usr/bin/env python3
r"""索引新鲜度检查：`00-index.yaml` 与实际目录结构是否对得上。

为什么需要
----------
`00-index.yaml` 是 AI 装载治理上下文的**唯一入口**（`scripts/context_loader.py` 按它
决定装哪些 domain）。索引没登记的 domain，等于对 AI 不存在 —— 不是"读得慢"，
是"根本读不到"。

2026-11-19 实测的现状：

- `levels.L1` 只登记 4 条（operations / projects / business-references / tooling）
- `legacy_domains` 登记 10 条，其中 4 条指向已迁移的旧单文件
  （`domains/security.md` 实际已拆成 `domains/security/`）
- `domains/` 下 9 个目录**完全没有出现在索引里**：
  architecture / automation / backend / configuration / devops-ci /
  documentation-and-api / observability / orchestration / security

没有任何脚本能发现这件事 —— `check_knowledge_health.py` 的 orphan 查的是
"目录有没有三件套"，不是"目录有没有被索引收录"。

检查项
------
1. `dangling`      索引登记的 path 不存在（多为单文件迁移成目录后未更新）
2. `unregistered`  `domains/` 下目录未出现在索引任何一处
3. `mtime_stale`   索引文件的 mtime 早于其描述目录里最新的 `.md`（仅供提示）

用法
----
    python scripts/check_index_freshness.py
    python scripts/check_index_freshness.py --strict   # warning 也非 0 退出
    python scripts/check_index_freshness.py --only unregistered
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INDEX_FILE = "00-index.yaml"

# YAML 片段的正则（不引 yaml 依赖：本脚本要能在无 pyyaml 的项目里跑）
SECTION_LEVELS = "levels:"
SECTION_LEGACY = "legacy_domains:"

# `- id: xxx` 紧跟 `path: yyy`（中间可能有 title/summary 等字段）
ENTRY_RE = re.compile(
    r"-\s+id:\s*([A-Za-z0-9_.-]+)\s*\n"
    r"(?:[ \t]+[A-Za-z_]+:[^\n]*\n)*?"
    r"[ \t]+path:\s*([^\s#]+)",
    re.M,
)


class Finding:
    __slots__ = ("level", "check", "where", "message")

    def __init__(self, level: str, check: str, where: str, message: str):
        self.level = level
        self.check = check
        self.where = where
        self.message = message

    def __str__(self) -> str:
        return f"[{self.level}] {self.check} :: {self.where} :: {self.message}"


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def parse_index(root: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """返回 (L1 条目, legacy 条目)，每项 (id, path)。"""
    text = read(root / INDEX_FILE)
    if not text:
        return [], []

    i = text.find(SECTION_LEVELS)
    j = text.find(SECTION_LEGACY)
    if i < 0:
        return [], []
    levels_seg = text[i:j] if j > i else text[i:]
    legacy_seg = text[j:] if j > i else ""

    return ENTRY_RE.findall(levels_seg), ENTRY_RE.findall(legacy_seg)


def registry_paths(entries) -> set[str]:
    return {p.rstrip("/") for _, p in entries}


def is_glob(p: str) -> bool:
    return any(ch in p for ch in "*?[")


def check_dangling(root: Path, entries) -> list[Finding]:
    out: list[Finding] = []
    for rid, path in entries:
        if is_glob(path):
            continue
        if not (root / path).exists():
            hint = ""
            stem = path[:-3] if path.endswith(".md") else None
            if stem and (root / stem).is_dir():
                hint = f"（同名目录 `{stem}/` 已存在，多半是单文件已拆分但索引未更新）"
            out.append(Finding("error", "dangling", INDEX_FILE,
                               f"`{rid}` 登记的路径不存在：`{path}`{hint}"))
    return out


def check_unregistered(root: Path, registered: set[str]) -> list[Finding]:
    out: list[Finding] = []
    dom = root / "domains"
    if not dom.is_dir():
        return out
    for d in sorted(dom.iterdir()):
        if not d.is_dir():
            continue
        rel = f"domains/{d.name}"
        if rel in registered:
            continue
        out.append(Finding("error", "unregistered", rel,
                           f"`{rel}` 未出现在 {INDEX_FILE} 的 levels 或 legacy_domains 中"
                           f"（AI 按索引装载时读不到这个域）"))
    return out


def check_mtime(root: Path, entries) -> list[Finding]:
    """索引 mtime 早于其描述目录里最新 md → 提示可能过期。"""
    out: list[Finding] = []
    idx = root / INDEX_FILE
    try:
        idx_mtime = idx.stat().st_mtime
    except OSError:
        return out

    stale: list[tuple[float, str, str]] = []
    for rid, path in entries:
        if is_glob(path):
            continue
        target = root / path
        if not target.exists():
            continue
        pats = ["*.md", "*.yaml", "*.yml"] if target.is_dir() else []
        newest = 0.0
        newest_f = ""
        if target.is_dir():
            for pat in pats:
                for f in target.rglob(pat):
                    try:
                        m = f.stat().st_mtime
                    except OSError:
                        continue
                    if m > newest:
                        newest, newest_f = m, str(f.relative_to(root))
        if newest > idx_mtime:
            stale.append((newest - idx_mtime, f"{rid} ({newest_f})", path))

    if stale:
        stale.sort(reverse=True)
        top = stale[0]
        days = top[0] / 86400
        out.append(Finding("warn", "mtime_stale", INDEX_FILE,
                           f"索引比 {len(stale)} 处被索引内容旧，最旧差距 {days:.0f} 天（{top[1]}）；"
                           f"索引内容可能未反映最新结构"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="索引新鲜度检查")
    ap.add_argument("--root", default=".")
    ap.add_argument("--strict", action="store_true", help="warning 也非 0 退出")
    ap.add_argument("--only", default=None, help="dangling,unregistered,mtime_stale")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / INDEX_FILE).is_file():
        print(f"[error] 找不到 {INDEX_FILE}（--root={root}）", file=sys.stderr)
        return 2

    l1, legacy = parse_index(root)
    entries = l1 + legacy
    registered = registry_paths(entries)

    enabled = set(args.only.split(",")) if args.only else {
        "dangling", "unregistered", "mtime_stale"}
    findings: list[Finding] = []
    if "dangling" in enabled:
        findings += check_dangling(root, entries)
    if "unregistered" in enabled:
        findings += check_unregistered(root, registered)
    if "mtime_stale" in enabled:
        findings += check_mtime(root, entries)

    order = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (order.get(f.level, 3), f.check, f.where))
    for f in findings:
        print(f)

    n_err = sum(1 for f in findings if f.level == "error")
    n_warn = sum(1 for f in findings if f.level == "warn")
    print(f"\nL1={len(l1)} legacy={len(legacy)} "
          f"errors={n_err} warnings={n_warn}")
    if n_err:
        return 1
    if args.strict and n_warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
