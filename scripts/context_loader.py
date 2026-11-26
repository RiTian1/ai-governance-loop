#!/usr/bin/env python3
"""治理上下文 Loader（MVP）

按 02-engineering-principles.md §11 与 foundations/self-governance-and-knowledge-evolution.md
将 schema v2 的层级化 governance 知识库按 trigger 评分 + token 预算装包。

用法:
  python scripts/context_loader.py \
    --profile solo-developer \
    --phase design \
    --keywords "runtime-context teardown" \
    --files "runtime-context.yaml" \
    --budget 8000 \
    --out _logs/context-bundle.md

输出:
  - <out>: 拼接好的 markdown bundle
  - {governance_root}/revisions/_logs/context-trace/<date>.jsonl: 加载日志（每行一条记录）

退化:
  - schema v1 的 entries 仅按 phase / profile 装载
  - 无 trigger 字段的 v1 节点视为低分（≥ 必装才装）
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(2)

DEFAULT_BUDGET = 8000
HIGH_SCORE = 6
MID_SCORE = 3
TOKENS_PER_LINE = 8  # 粗估，仅用于 size_tokens 缺省回退


def estimate_tokens(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="replace")
    return max(1, len(text) // 4)


def load_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def score_triggers(triggers: dict[str, Any] | None,
                   keywords: set[str],
                   files: list[str],
                   stack: set[str],
                   phase: str | None) -> int:
    if not triggers:
        return 0
    s = 0
    tk = {k.lower() for k in (triggers.get("keywords") or [])}
    s += 2 * len(tk & keywords)

    for pat in (triggers.get("files") or []):
        if any(fnmatch.fnmatch(f, pat) for f in files):
            s += 3

    ts = {x.lower() for x in (triggers.get("stack") or [])}
    s += 2 * len(ts & stack)

    if phase and phase in (triggers.get("phases") or []):
        s += 1
    return s


def collect_v2_l1_entries(index: dict) -> list[dict]:
    """schema v2 顶层 levels.L1 列表"""
    levels = index.get("levels") or {}
    return list(levels.get("L1") or [])


def collect_v1_entries(index: dict) -> list[dict]:
    """schema v1 entries 列表（每条含 path / when_to_read）"""
    return list(index.get("entries") or [])


def load_l2_entries(gov_root: Path, l1: dict) -> list[dict]:
    sub_index_path = gov_root / l1["path"] / "_index.yaml"
    sub = load_yaml(sub_index_path)
    if not sub:
        return []
    return list(sub.get("children") or [])


def emit(bundle_lines: list[str], trace: list[dict],
         label: str, path: Path, kind: str, tokens: int, score: int):
    if not path.exists():
        trace.append({"label": label, "path": str(path), "kind": kind, "score": score, "tokens": 0, "loaded": False, "reason": "missing"})
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    bundle_lines.append(f"\n\n<!-- BEGIN {label} ({kind}, score={score}, tokens≈{tokens}) -->\n")
    bundle_lines.append(text)
    bundle_lines.append(f"\n<!-- END {label} -->\n")
    trace.append({"label": label, "path": str(path), "kind": kind, "score": score, "tokens": tokens, "loaded": True})
    return True


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--profile", default=None, help="项目 profile（可选；用于必装域）")
    p.add_argument("--phase", default=None, choices=[None, "explore", "proposal", "design", "apply", "verify", "archive"])
    p.add_argument("--keywords", default="", help="空格分隔的关键词")
    p.add_argument("--files", default="", help="空格分隔的文件 glob")
    p.add_argument("--stack", default="", help="空格分隔的技术栈")
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    p.add_argument("--governance-root", default=".", help="governance root（默认 cwd）")
    p.add_argument("--manifest", default="project-governance.yaml")
    p.add_argument("--out", default="_logs/context-bundle.md")
    p.add_argument("--include", default="", help="强制包含的 domain 路径（空格分隔），无视分数")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    repo = Path(args.governance_root).resolve()
    manifest_path = repo / args.manifest
    manifest = load_yaml(manifest_path) or {}

    gov_root_decl = manifest.get("governance_root", ".")
    gov_root = (repo / gov_root_decl).resolve() if gov_root_decl != "." else repo

    budget = manifest.get("token_budget") or args.budget

    keywords = {w.lower() for w in args.keywords.split() if w}
    files = [w for w in args.files.split() if w]
    stack = {w.lower() for w in args.stack.split() if w}
    phase = args.phase
    forced_include = {w for w in args.include.split() if w}

    index_path = gov_root / "00-index.yaml"
    index = load_yaml(index_path)
    if not index:
        print(f"ERROR: cannot read {index_path}", file=sys.stderr)
        return 2

    schema_v = index.get("schema_version") or 1

    bundle: list[str] = [f"<!-- governance context bundle, generated {dt.datetime.now(dt.timezone.utc).isoformat()} -->\n"]
    trace: list[dict] = []
    used = 0

    # 必装 0：manifest 自身（裁剪：只装顶层关键字段）
    if manifest_path.exists():
        snippet = "```yaml\n# project-governance.yaml (excerpt)\n"
        for k in ("project_id", "project_stage", "project_type_profile",
                  "governance_layout", "governance_root", "active_baseline",
                  "enabled_foundations", "enabled_domains", "token_budget",
                  "runtime_context"):
            if k in manifest:
                snippet += yaml.safe_dump({k: manifest[k]}, allow_unicode=True, sort_keys=False)
        snippet += "```\n"
        toks = max(1, len(snippet) // 4)
        bundle.append(f"\n<!-- BEGIN manifest (excerpt, tokens≈{toks}) -->\n{snippet}\n<!-- END manifest -->\n")
        trace.append({"label": "manifest", "path": str(manifest_path), "kind": "excerpt", "tokens": toks, "loaded": True})
        used += toks

    # 必装 1：00-index.yaml 本身（路由表，所有任务都要看）
    idx_tokens = estimate_tokens(index_path)
    emit(bundle, trace, "00-index", index_path, "index", idx_tokens, score=99)
    used += idx_tokens

    # 必装 2：profile 文件（如指定）
    if args.profile:
        prof = gov_root / "profiles" / f"{args.profile}.md"
        prof_tokens = estimate_tokens(prof)
        if prof_tokens and used + prof_tokens <= budget:
            emit(bundle, trace, f"profile:{args.profile}", prof, "profile", prof_tokens, score=99)
            used += prof_tokens

    # 收集候选节点（v2 优先，v1 退化）
    candidates: list[dict] = []
    if schema_v >= 2:
        for l1 in collect_v2_l1_entries(index):
            l1_path = gov_root / l1["path"]
            l1_score = score_triggers(l1.get("triggers"), keywords, files, stack, phase)
            l1_size = l1.get("size_tokens") or estimate_tokens(l1_path / "index.md")
            candidates.append({
                "kind": "L1",
                "id": l1["id"],
                "path": l1_path,
                "score": l1_score,
                "size": l1_size,
                "force": l1["id"] in forced_include or l1["path"] in forced_include,
            })

            if l1_score >= MID_SCORE or l1["id"] in forced_include:
                for l2 in load_l2_entries(gov_root, l1):
                    l2_path = l1_path / l2["id"]
                    l2_score = l1_score + score_triggers(l2.get("triggers"), keywords, files, stack, phase)
                    l2_size = l2.get("size_tokens") or estimate_tokens(l2_path / "index.md")
                    candidates.append({
                        "kind": "L2",
                        "id": f"{l1['id']}/{l2['id']}",
                        "path": l2_path,
                        "score": l2_score,
                        "size": l2_size,
                        "force": (f"{l1['id']}/{l2['id']}") in forced_include,
                    })
    else:
        # v1 退化：按 when_to_read 装 _summary 模式（仅 .md）
        for entry in collect_v1_entries(index):
            p_ = gov_root / entry["path"]
            ph = entry.get("when_to_read") or []
            score = (1 if (phase and phase in ph) else 0)
            candidates.append({
                "kind": "v1",
                "id": entry["id"],
                "path": p_,
                "score": score,
                "size": estimate_tokens(p_),
                "force": entry["id"] in forced_include or entry["path"] in forced_include,
            })

    # 按 (force, score) 排序
    candidates.sort(key=lambda c: (not c["force"], -c["score"], c["id"]))

    # 装包
    for c in candidates:
        if used >= budget and not c["force"]:
            trace.append({"label": c["id"], "kind": c["kind"], "score": c["score"], "loaded": False, "reason": "budget-exceeded"})
            continue

        is_l = c["kind"] in ("L1", "L2")
        if is_l:
            summary_path = c["path"] / "_summary.yaml"
            index_md_path = c["path"] / "index.md"
            mode_full = c["force"] or c["score"] >= HIGH_SCORE
            mode_summary = (not mode_full) and c["score"] >= MID_SCORE

            if mode_full and index_md_path.exists():
                toks = estimate_tokens(index_md_path)
                if c["force"] or used + toks <= budget:
                    emit(bundle, trace, c["id"] + ":index.md", index_md_path, "index.md", toks, c["score"])
                    used += toks
            if (mode_full or mode_summary) and summary_path.exists():
                toks = estimate_tokens(summary_path)
                if c["force"] or used + toks <= budget:
                    emit(bundle, trace, c["id"] + ":_summary", summary_path, "_summary.yaml", toks, c["score"])
                    used += toks
            if not (mode_full or mode_summary):
                trace.append({"label": c["id"], "kind": c["kind"], "score": c["score"], "loaded": False, "reason": "low-score"})
        else:
            # v1 单文件
            if c["path"].exists() and (c["force"] or c["score"] > 0):
                if used + c["size"] <= budget or c["force"]:
                    emit(bundle, trace, c["id"], c["path"], "v1.md", c["size"], c["score"])
                    used += c["size"]
                else:
                    trace.append({"label": c["id"], "kind": c["kind"], "score": c["score"], "loaded": False, "reason": "budget-exceeded"})

    # 输出 bundle
    out_path = repo / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(bundle), encoding="utf-8")

    # 输出 trace 日志。业务项目采用 docs-governance-subtree 时，日志属于治理子树，
    # 不能在项目根额外制造 revisions/ 目录。
    log_dir = gov_root / "revisions" / "_logs" / "context-trace"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{dt.date.today().isoformat()}.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        record = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "profile": args.profile,
            "phase": phase,
            "keywords": sorted(keywords),
            "files": files,
            "stack": sorted(stack),
            "budget": budget,
            "used": used,
            "schema_version": schema_v,
            "loaded": [t for t in trace if t.get("loaded")],
            "dropped": [t for t in trace if not t.get("loaded")],
        }
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    if not args.quiet:
        print(f"context bundle: {out_path}")
        print(f"  used: {used} / budget: {budget}")
        loaded_n = sum(1 for t in trace if t.get("loaded"))
        dropped_n = sum(1 for t in trace if not t.get("loaded"))
        print(f"  loaded: {loaded_n}  dropped: {dropped_n}")
        print(f"  trace log: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
