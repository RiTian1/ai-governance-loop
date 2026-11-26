#!/usr/bin/env python3
"""跨工具进度一致性自检（BMAD / OpenSpec / Revisions / Rules）

按 foundations/progress-traceability-and-binding.md §3-§4 与
domains/tooling/progress-binding/_summary.yaml 检查项：

  T1  反向引用存在且双向一致 (Story.linked_change ↔ change.linked_story)
  T2  rule.introduced_by 指向合法且真实存在的 revision_id
  T3  状态机合法对齐 (Story / change / revision 三端)
  T4  revisions/index.yaml 与文件系统一致 (无孤儿、无残缺)
  T5  status=merged 的 revision 必须在 revisions/archive/
  T6  acceptance_criteria_hash ↔ spec_delta_hash 一致性
       (任一端变化时另一端 hash 也必须更新；git-free：直接从当前文件内容
        重算 hash 并与 frontmatter 声明值比对，无需 git 历史)
  T7  ID 格式合法 (story_id / change_id / revision_id / rule_id)
  T8  孤立检测 (Story 无 change/revision 反向引用 / change 无 Story / revision 无 stories)
  T9  禁挂已完成 Story (active change 的 linked_story 指向 done/archived = tool.binding.r8 违例)
  T10 状态字段最后一步 (终态 Story 指向 candidate revision = 状态提前写入 = tool.binding.r9 违例)
  T11 同步台账一致 (_logs/sync-ledger.md 引用的 story/change/revision 必须真实存在)

用法:
  python scripts/check_progress_consistency.py --strict             # CI 模式
  python scripts/check_progress_consistency.py --project-root <dir> # 显式指定项目根
  python scripts/check_progress_consistency.py --staged             # pre-commit 模式 (仅 staged 文件)
  python scripts/check_progress_consistency.py --quick              # 仅快速检查 (T1+T7)
  python scripts/check_progress_consistency.py --report _logs/progress-consistency.md

退出码（fail-closed）:
  0 = 全 pass / 仅 warning
  1 = 有 error / 有 drift / 任何无法运行（缺依赖、解析失败、未捕获异常）
  2 = 仅 CLI 用法错误（argparse）

设计铁律：本检查是便携治理的"地基门禁"，必须在**无 pyyaml、无 .git** 的
裸环境下可跑。绝不因缺少 pyyaml 而退出 2（那会被 agent 当成"环境问题跳过"）。
缺依赖时走 scripts/_governance_yaml.py 的纯标准库回退；任何运行失败一律 = 1（阻断）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402


# ID 模式
STORY_ID_RE = re.compile(r"^[a-z][a-z0-9-]*\.S\d{2}\.\d{2}$")
EPIC_ID_RE = re.compile(r"^[a-z][a-z0-9-]*\.E\d{2}$")
CHANGE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*\.C\d{2}\.\d{2}$")
REVISION_ID_RE = re.compile(r"^rev-\d{4}-\d{2}-\d{2}-[a-z][a-z0-9-]*$")
RULE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z0-9-]+)*\.r\d+$")
FR_ID_RE = re.compile(r"^[a-z][a-z0-9-]*\.(?:NFR|NR|FR)\d+$")
# 原为 \.(F|N)R\d+ —— 匹配不了 gov.NFR03（N 后要求 R，实际是 FR）。
# 该常量此前从未被引用，所以 bug 一直没暴露。

# 状态机：Story / Change / Revision 三端合法对齐
LEGAL_TRIPLES = {
    # (story, change, revision)；None 表示该端未立
    ("draft", None, None),
    ("approved", "proposed", "candidate"),
    ("approved", "approved", "accepted"),
    ("inprogress", "implementing", "accepted"),
    ("review", "implemented", "accepted"),
    ("done", "implemented", "accepted"),
    ("done", "archived", "merged"),
    ("archived", "archived", "archived"),
    # benchmarked：评测完成、待评审。是 revision 自有状态，不推动 Story/change 端
    ("approved", "proposed", "benchmarked"),
    ("approved", "approved", "benchmarked"),
    ("inprogress", "implementing", "benchmarked"),
    ("inprogress", "implemented", "benchmarked"),
    # 允许 Story 不立 change（小工作）
    ("draft", None, None),
    ("approved", None, None),
    ("inprogress", None, None),
    ("review", None, None),
    ("done", None, None),
    ("archived", None, None),
    # 允许 Story 不立 revision
    ("approved", "proposed", None),
    ("approved", "approved", None),
    ("inprogress", "implementing", None),
    ("review", "implemented", None),
    ("done", "implemented", None),
    ("done", "archived", None),
    ("archived", "archived", None),
    # 允许 Story 不立 change（仅 revision）：边实施边立候选 revision 等正常状态
    # 注意：终态 Story（done/archived）指向 candidate revision 由 T10 单独判为漂移
    ("draft", None, "candidate"),
    ("approved", None, "candidate"),
    ("approved", None, "benchmarked"),
    ("approved", None, "accepted"),
    ("inprogress", None, "candidate"),
    ("inprogress", None, "benchmarked"),
    ("inprogress", None, "accepted"),
    ("review", None, "accepted"),
    ("done", None, "accepted"),
    ("done", None, "merged"),
    ("archived", None, "archived"),
}

# Story 终态集合（用于 T9/T10）
TERMINAL_STORY_STATUSES = {"done", "archived"}
ACTIVE_CHANGE_STATUSES = {"proposed", "approved", "implementing", "implemented"}

CURRENT_YEAR = dt.date.today().year


class Finding:
    __slots__ = ("level", "check", "where", "message")

    def __init__(self, level: str, check: str, where: str, message: str):
        self.level = level
        self.check = check
        self.where = where
        self.message = message

    def fmt(self) -> str:
        return f"[{self.level}] {self.check} :: {self.where} :: {self.message}"


def git_staged_paths(root: Path) -> set[str] | None:
    """Return staged paths relative to root in posix form; None when git is unavailable.

    pre-commit 只应拦截"本次改动引入的漂移"。存量债务若也阻断，hook 会永久失效，
    最终被绕过（--no-verify）。因此这里返回 None 表示无法判定，调用方退回全量严格模式。
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return None
        return {ln.strip().replace("\\", "/") for ln in out.stdout.splitlines() if ln.strip()}
    except Exception:  # noqa: BLE001
        return None


def finding_touches(finding: "Finding", staged: set[str]) -> bool:
    """True when the finding points at a file this commit actually changes."""
    where = (finding.where or "").replace("\\", "/").lstrip("./")
    if not where:
        return False
    for path in staged:
        norm = path.lstrip("./")
        if where == norm or where.startswith(norm + "/") or norm in where:
            return True
    return False


def repo_root(arg_root: str) -> Path:
    return Path(arg_root).resolve()


def resolve_roots(project_root_arg: str, governance_root_arg: str | None) -> tuple[Path, Path]:
    """Resolve project root and governance content root.

    Business projects use `docs-governance-subtree`: BMAD/OpenSpec live at the
    project root, while revisions/domains live under `governance_root`.
    Mother-repo projects use a single root for both.
    """
    project_root = repo_root(project_root_arg)
    manifest_path = project_root / "project-governance.yaml"
    manifest = load_yaml(manifest_path) or {}

    if governance_root_arg:
        gov_root = Path(governance_root_arg)
        if not gov_root.is_absolute():
            gov_root = project_root / gov_root
        gov_root = gov_root.resolve()
        # 容错：git hook 常把"项目根"当作 governance 根传入（模板统一写 $GOV_ROOT）。
        # 若该根下没有 revisions/ 而 docs/governance/revisions/ 存在，则下钻一层，
        # 否则 revisions 会收集为 0，导致反向引用全部误判为 not found。
        if not (gov_root / "revisions").exists():
            nested = gov_root / "docs/governance"
            if (nested / "revisions").exists():
                gov_root = nested
        return project_root, gov_root

    gov_root_decl = manifest.get("governance_root", ".")
    gov_root = project_root if gov_root_decl == "." else project_root / str(gov_root_decl)
    return project_root, gov_root.resolve()


def load_yaml(path: Path) -> dict | None:
    try:
        return _yaml_safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def parse_md_frontmatter(text: str) -> dict | None:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return None
    try:
        data = _yaml_safe_load(m.group(1)) or {}
    except Exception:
        return None
    # 哨兵值规范化：linked_* 写 none/null 的语义是"未立关联"，不是字面 id。
    # 若不规范化，检查会去 revisions/stories 里找名为 "none" 的条目，
    # 产生与事实无关的假错误（项目A 实测 325 条）。
    for key in ("linked_change", "linked_revision", "linked_story"):
        if key in data:
            raw = data[key]
            if raw is None or str(raw).strip().lower() in ("", "none", "null", "-"):
                data[key] = None
    return data


def collect_stories(root: Path) -> list[dict]:
    """扫 _bmad/<project>/stories/*.md（如有）"""
    items: list[dict] = []
    bmad_root = root / "_bmad"
    if not bmad_root.exists():
        return items
    for proj in bmad_root.iterdir():
        if not proj.is_dir() or proj.name.startswith("_"):
            continue
        stories_dir = proj / "stories"
        if not stories_dir.exists():
            continue
        for md in stories_dir.glob("*.md"):
            text = md.read_text(encoding="utf-8", errors="replace")
            front = parse_md_frontmatter(text)
            if front is None:
                continue
            front["__path"] = str(md.relative_to(root))
            front["__ac_hash"] = compute_ac_hash(text)
            items.append(front)
    return items


def collect_changes(root: Path) -> list[dict]:
    """扫 openspec/changes/<change>/proposal.md"""
    items: list[dict] = []
    changes_root = root / "openspec" / "changes"
    if not changes_root.exists():
        return items
    for change_dir in changes_root.iterdir():
        if not change_dir.is_dir() or change_dir.name == "archive":
            continue
        proposal = change_dir / "proposal.md"
        if not proposal.exists():
            continue
        text = proposal.read_text(encoding="utf-8", errors="replace")
        front = parse_md_frontmatter(text)
        if front is None:
            continue
        front["__path"] = str(proposal.relative_to(root))
        front["__delta_hash"] = compute_delta_hash(change_dir)
        items.append(front)
    # archive 也扫一遍
    archive_root = changes_root / "archive"
    if archive_root.exists():
        for change_dir in archive_root.iterdir():
            if not change_dir.is_dir():
                continue
            proposal = change_dir / "proposal.md"
            if not proposal.exists():
                continue
            text = proposal.read_text(encoding="utf-8", errors="replace")
            front = parse_md_frontmatter(text)
            if front is None:
                continue
            front["__path"] = str(proposal.relative_to(root))
            front["__delta_hash"] = compute_delta_hash(change_dir)
            front["__archived"] = True
            items.append(front)
    return items


def collect_revisions(root: Path) -> list[dict]:
    """扫 revisions/<id>/meta.yaml 与单文件 revisions/<YYYY-MM-DD>-<slug>.md"""
    items: list[dict] = []
    rev_root = root / "revisions"
    if not rev_root.exists():
        return items

    # 结构化目录形态：每个子目录含 meta.yaml
    for sub in rev_root.iterdir():
        if not sub.is_dir() or sub.name in ("archive", "_logs"):
            continue
        meta = sub / "meta.yaml"
        if meta.exists():
            data = load_yaml(meta)
            if data is None:
                continue
            data["__path"] = str(meta.relative_to(root))
            data["__form"] = "directory"
            items.append(data)

    # archive 子树
    archive_root = rev_root / "archive"
    if archive_root.exists():
        for year in archive_root.iterdir():
            if not year.is_dir():
                continue
            for sub in year.iterdir():
                if not sub.is_dir():
                    continue
                meta = sub / "meta.yaml"
                if meta.exists():
                    data = load_yaml(meta)
                    if data is None:
                        continue
                    data["__path"] = str(meta.relative_to(root))
                    data["__form"] = "directory-archived"
                    items.append(data)
                else:
                    # 兼容：archive 下的单 md
                    for md in sub.glob("*.md"):
                        text = md.read_text(encoding="utf-8", errors="replace")
                        front = parse_md_frontmatter(text)
                        if front is None:
                            continue
                        front.setdefault("revision_id", _id_from_filename(md.name))
                        front["__path"] = str(md.relative_to(root))
                        front["__form"] = "single-md-archived"
                        items.append(front)

    # 单文件历史形态：revisions/<YYYY-MM-DD>-<slug>.md
    for md in rev_root.glob("*.md"):
        if md.name in ("README.md", "WORKFLOW.md"):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        front = parse_md_frontmatter(text)
        if front is None:
            continue
        front.setdefault("revision_id", _id_from_filename(md.name))
        front["__path"] = str(md.relative_to(root))
        front["__form"] = "single-md"
        items.append(front)

    return items


def _id_from_filename(name: str) -> str:
    """根据文件名 2026-05-25-foo-bar.md 反推 revision_id"""
    stem = name.replace(".md", "")
    if stem.endswith("-candidate"):
        stem = stem[: -len("-candidate")]
    return f"rev-{stem}"


def collect_rule_definitions(root: Path) -> list[tuple[str, str, dict]]:
    """返回 [(rule_id, summary_yaml_path, rule_dict)]"""
    items: list[tuple[str, str, dict]] = []
    # 三条轴：关切轴 domains/ + 项目轴 projects/ + 业务参考轴 business-references/
    trees = ("domains", "projects", "business-references")
    summaries = [s for t in trees for s in (root / t).rglob("_summary.yaml")]
    if not summaries:
        return items
    for s in summaries:
        data = load_yaml(s)
        if data is None:
            continue
        rel = str(s.relative_to(root))
        for rule in (data.get("rules") or []):
            rid = rule.get("id")
            if rid:
                items.append((rid, rel, rule))
    return items


def collect_revisions_index(root: Path) -> list[dict] | None:
    idx = root / "revisions" / "index.yaml"
    if not idx.exists():
        return None
    data = load_yaml(idx)
    if data is None:
        return None
    return data.get("revisions") or []


def collect_scoped_revision_ids(root: Path) -> dict[tuple[str, str], set[str]]:
    """Load project and business-reference indexes without mixing central revision state."""
    result: dict[tuple[str, str], set[str]] = defaultdict(set)
    for scope in ("projects", "business-references"):
        scope_root = root / scope
        if not scope_root.exists():
            continue
        for owner_root in scope_root.iterdir():
            if not owner_root.is_dir():
                continue
            index = owner_root / "revisions" / "source-index.yaml"
            data = load_yaml(index) if index.exists() else None
            owner_ids = result[(scope, owner_root.name)]
            for entry in (data or {}).get("revisions") or []:
                revision_id = entry.get("id") or entry.get("revision_id")
                if revision_id:
                    owner_ids.add(str(revision_id))
            for revision in collect_revisions(owner_root):
                revision_id = revision.get("revision_id")
                if revision_id:
                    owner_ids.add(str(revision_id))
    return result


def compute_ac_hash(story_text: str) -> str | None:
    m = re.search(r"^##\s+Acceptance\s+Criteria\s*\n(.*?)(?=\n##\s|\Z)", story_text, re.S | re.I | re.M)
    if not m:
        return None
    body = m.group(1).strip()
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]


def compute_delta_hash(change_dir: Path) -> str | None:
    parts: list[str] = []
    specs = change_dir / "specs"
    if not specs.exists():
        return None
    for spec_md in sorted(specs.rglob("spec.md")):
        text = spec_md.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
            r"^##\s+(?:ADDED|MODIFIED|REMOVED)\s+Requirements?\s*\n(.*?)(?=\n##\s|\Z)",
            text, re.S | re.M,
        ):
            parts.append(m.group(1).strip())
    if not parts:
        return None
    blob = "\n---\n".join(parts).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:12]


# =============================================================
# Checks
# =============================================================

def check_id_formats(stories, changes, revisions, rules) -> list[Finding]:
    out: list[Finding] = []
    for s in stories:
        sid = s.get("story_id")
        if not sid:
            out.append(Finding("error", "T7-id-format", s["__path"], "story missing story_id"))
            continue
        if not STORY_ID_RE.match(sid):
            out.append(Finding("error", "T7-id-format", s["__path"], f"invalid story_id format: {sid}"))
        if (eid := s.get("epic_id")) and not EPIC_ID_RE.match(eid):
            out.append(Finding("error", "T7-id-format", s["__path"], f"invalid epic_id format: {eid}"))

    for c in changes:
        cid = c.get("change_id")
        if not cid:
            out.append(Finding("error", "T7-id-format", c["__path"], "change missing change_id"))
            continue
        if not CHANGE_ID_RE.match(cid):
            out.append(Finding("error", "T7-id-format", c["__path"], f"invalid change_id format: {cid}"))

    for r in revisions:
        rid = r.get("revision_id")
        if not rid:
            out.append(Finding("warn", "T7-id-format", r["__path"], "revision missing revision_id (legacy single-md)"))
            continue
        if not REVISION_ID_RE.match(rid):
            out.append(Finding("error", "T7-id-format", r["__path"], f"invalid revision_id format: {rid}"))

    for rid, rel, _ in rules:
        if not RULE_ID_RE.match(rid):
            out.append(Finding("error", "T7-id-format", rel, f"invalid rule_id format: {rid}"))
    return out


def check_back_references(stories, changes, revisions) -> list[Finding]:
    out: list[Finding] = []
    change_by_id = {c.get("change_id"): c for c in changes if c.get("change_id")}
    revision_by_id = {r.get("revision_id"): r for r in revisions if r.get("revision_id")}
    story_by_id = {s.get("story_id"): s for s in stories if s.get("story_id")}

    # Story → change/revision 双向
    for s in stories:
        sid = s.get("story_id")
        lc = s.get("linked_change")
        if lc and lc not in change_by_id:
            out.append(Finding("error", "T1-back-ref", s["__path"],
                               f"story.linked_change={lc} not found"))
        elif lc:
            c = change_by_id[lc]
            if c.get("linked_story") != sid:
                out.append(Finding("error", "T1-back-ref", s["__path"],
                                   f"asymmetric: story={sid} linked_change={lc} but change.linked_story={c.get('linked_story')}"))
        lr = s.get("linked_revision")
        if lr and lr not in revision_by_id:
            out.append(Finding("error", "T1-back-ref", s["__path"],
                               f"story.linked_revision={lr} not found"))

    # Change → story 双向
    for c in changes:
        cid = c.get("change_id")
        ls = c.get("linked_story")
        if ls and ls not in story_by_id:
            out.append(Finding("error", "T1-back-ref", c["__path"],
                               f"change.linked_story={ls} not found"))
        elif ls:
            s = story_by_id[ls]
            if s.get("linked_change") != cid:
                out.append(Finding("error", "T1-back-ref", c["__path"],
                                   f"asymmetric: change={cid} linked_story={ls} but story.linked_change={s.get('linked_change')}"))
        lr = c.get("linked_revision")
        if lr and lr not in revision_by_id:
            out.append(Finding("error", "T1-back-ref", c["__path"],
                               f"change.linked_revision={lr} not found"))

    # Revision → stories/changes 双向
    # 跨项目同步来的 revision（如母版的 gov.*）会引用源项目的 story/change，
    # 那不是本项目的缺口，计入漂移只会制造噪音。
    local_story_prefixes = {sid.split('.')[0] for sid in story_by_id if '.' in sid}
    local_change_prefixes = {cid.split('.')[0] for cid in change_by_id if '.' in cid}
    for r in revisions:
        rid = r.get("revision_id")
        for ls in (r.get("linked_stories") or []):
            prefix = ls.split('.')[0] if '.' in ls else ''
            if prefix and prefix not in local_story_prefixes:
                continue
            if ls not in story_by_id:
                out.append(Finding("warn", "T1-back-ref", r["__path"],
                                   f"revision.linked_stories[{ls}] story not found (may be planned)"))
        for lc in (r.get("linked_changes") or []):
            prefix = lc.split('.')[0] if '.' in lc else ''
            if prefix and prefix not in local_change_prefixes:
                continue
            if lc not in change_by_id:
                out.append(Finding("warn", "T1-back-ref", r["__path"],
                                   f"revision.linked_changes[{lc}] change not found (may be planned)"))

    return out


def check_rule_introduced_by(rules, revisions, scoped_revision_ids=None) -> list[Finding]:
    out: list[Finding] = []
    revision_ids = {r.get("revision_id") for r in revisions if r.get("revision_id")}
    scoped_revision_ids = scoped_revision_ids or {}
    for rid, rel, rule in rules:
        ib = rule.get("introduced_by")
        if not ib:
            out.append(Finding("warn", "T2-introduced-by", rel, f"rule {rid} missing introduced_by"))
            continue
        scope_match = re.match(r"(projects|business-references)/([^/]+)/", rel.replace("\\", "/"))
        relevant_revision_ids = revision_ids
        if scope_match:
            scope, owner = scope_match.groups()
            relevant_revision_ids = scoped_revision_ids.get((scope, owner), set()) or revision_ids
        # 兼容历史: introduced_by 是日期-slug 形式（无 rev- 前缀），允许 warn 而非 error
        if ib.startswith("rev-"):
            if ib not in relevant_revision_ids:
                out.append(Finding("error", "T2-introduced-by", rel,
                                   f"rule {rid} introduced_by={ib} revision not found"))
        else:
            # 历史形态：YYYY-MM-DD-slug
            if not re.match(r"^\d{4}-\d{2}-\d{2}-[a-z][a-z0-9-]*$", ib):
                out.append(Finding("error", "T2-introduced-by", rel,
                                   f"rule {rid} introduced_by={ib} invalid format (expect rev-YYYY-MM-DD-slug or legacy YYYY-MM-DD-slug)"))
            else:
                # 转 rev- 前缀对照
                if ib not in relevant_revision_ids and f"rev-{ib}" not in relevant_revision_ids:
                    out.append(Finding("warn", "T2-introduced-by", rel,
                                       f"rule {rid} introduced_by={ib} (legacy form) — corresponding revision not found"))
    return out


_STATUS_ALIASES = {
    "in-progress": "inprogress",
    "in_progress": "inprogress",
    "wip": "inprogress",
    "doing": "inprogress",
}


def normalize_status(value) -> str:
    """状态别名归一。历史项目里 in-progress / in_progress 与 inprogress 混用。"""
    s = (value or "").strip().lower()
    return _STATUS_ALIASES.get(s, s)


def check_state_machine(stories, changes, revisions) -> list[Finding]:
    out: list[Finding] = []
    change_by_id = {c.get("change_id"): c for c in changes if c.get("change_id")}
    revision_by_id = {r.get("revision_id"): r for r in revisions if r.get("revision_id")}

    for s in stories:
        s_status = normalize_status(s.get("status"))
        if not s_status:
            continue
        c_status = None
        r_status = None
        if (lc := s.get("linked_change")) and lc in change_by_id:
            c_status = normalize_status(change_by_id[lc].get("status")) or None
        if (lr := s.get("linked_revision")) and lr in revision_by_id:
            r_status = normalize_status(revision_by_id[lr].get("status")) or None
        triple = (s_status, c_status, r_status)
        if triple not in LEGAL_TRIPLES:
            out.append(Finding("error", "T3-state-machine", s["__path"],
                               f"illegal triple (story={s_status}, change={c_status}, revision={r_status})"))
    return out


def check_revisions_index(root: Path, revisions, idx_revisions) -> list[Finding]:
    out: list[Finding] = []
    if idx_revisions is None:
        out.append(Finding("error", "T4-revisions-index", "revisions/index.yaml", "missing or invalid"))
        return out
    indexed_ids = set()
    for entry in idx_revisions:
        eid = entry.get("id")
        epath = entry.get("path")
        estatus = entry.get("status")
        if not eid:
            out.append(Finding("error", "T4-revisions-index", "revisions/index.yaml", f"entry missing id: {entry}"))
            continue
        indexed_ids.add(eid)
        if epath:
            full = root / epath
            if not full.exists():
                out.append(Finding("error", "T4-revisions-index", f"revisions/index.yaml#{eid}",
                                   f"declared path does not exist: {epath}"))
        if estatus == "merged":
            # T5: merged 必须在 archive
            if epath and "/archive/" not in epath.replace("\\", "/"):
                out.append(Finding("warn", "T5-merged-archive", f"revisions/index.yaml#{eid}",
                                   f"status=merged but path not under revisions/archive/: {epath}"))

    fs_ids = set()
    for r in revisions:
        rid = r.get("revision_id")
        if not rid:
            continue
        # 转 rev- 前缀去掉以匹配 index
        norm = rid[len("rev-"):] if rid.startswith("rev-") else rid
        # 兼容历史 index 中 id 可能是裸 slug 形式
        canonical = rid
        legacy = norm
        if rid in indexed_ids or legacy in indexed_ids:
            fs_ids.add(rid)
            continue
        out.append(Finding("warn", "T4-revisions-index", r["__path"],
                           f"revision exists on filesystem but missing in revisions/index.yaml: {rid}"))

    return out


def check_orphans(stories, changes, revisions) -> list[Finding]:
    out: list[Finding] = []
    referenced_changes = {s.get("linked_change") for s in stories if s.get("linked_change")}
    referenced_changes |= {lc for r in revisions for lc in (r.get("linked_changes") or [])}
    referenced_revisions = {s.get("linked_revision") for s in stories if s.get("linked_revision")}
    referenced_revisions |= {c.get("linked_revision") for c in changes if c.get("linked_revision")}

    for c in changes:
        cid = c.get("change_id")
        if not cid:
            continue
        if c.get("linked_story") is None and cid not in referenced_changes:
            out.append(Finding("warn", "T8-orphan", c["__path"],
                               f"change {cid} has no linked_story and not referenced by any revision"))

    return out


def check_content_drift(stories, changes) -> list[Finding]:
    """T6: AC hash 与 spec delta hash 在 frontmatter 与实际内容是否漂移"""
    out: list[Finding] = []
    for s in stories:
        decl = s.get("acceptance_criteria_hash")
        actual = s.get("__ac_hash")
        if decl and actual and decl != actual:
            out.append(Finding("error", "T6-content-drift", s["__path"],
                               f"acceptance_criteria_hash declared={decl} actual={actual} (frontmatter not updated after AC edit)"))
    for c in changes:
        decl = c.get("spec_delta_hash")
        actual = c.get("__delta_hash")
        if decl and actual and decl != actual:
            out.append(Finding("error", "T6-content-drift", c["__path"],
                               f"spec_delta_hash declared={decl} actual={actual} (frontmatter not updated after spec edit)"))
    return out


def check_no_new_work_on_completed_story(stories, changes) -> list[Finding]:
    """T9 (tool.binding.r8): 禁止把新工作（active change）挂到已完成 Story 上。"""
    out: list[Finding] = []
    story_by_id = {s.get("story_id"): s for s in stories if s.get("story_id")}
    for c in changes:
        cid = c.get("change_id")
        c_status = (c.get("status") or "").lower()
        ls = c.get("linked_story")
        if not ls or c_status not in ACTIVE_CHANGE_STATUSES:
            continue
        s = story_by_id.get(ls)
        if not s:
            continue
        s_status = (s.get("status") or "").lower()
        if s_status in TERMINAL_STORY_STATUSES:
            out.append(Finding("error", "T9-completed-story", c["__path"],
                               f"active change {cid} (status={c_status}) linked to completed story "
                               f"{ls} (status={s_status}); 新工作不得挂已完成 Story（tool.binding.r8）—新建 story/change"))
    return out


def check_status_field_coupling(stories, revisions) -> list[Finding]:
    """T10 (tool.binding.r9): 终态 Story 不得指向尚未进入 accepted 及之后的 revision（状态提前写入）。

    candidate 与 benchmarked 都是"未评审"态，同样属于提前写入。
    """
    out: list[Finding] = []
    revision_by_id = {r.get("revision_id"): r for r in revisions if r.get("revision_id")}
    for s in stories:
        s_status = (s.get("status") or "").lower()
        if s_status not in TERMINAL_STORY_STATUSES:
            continue
        lr = s.get("linked_revision")
        if not lr or lr not in revision_by_id:
            continue
        r_status = (revision_by_id[lr].get("status") or "").lower()
        if r_status in {"candidate", "benchmarked"}:
            out.append(Finding("error", "T10-status-coupling", s["__path"],
                               f"story status={s_status} (terminal) but linked_revision {lr} still {r_status}; "
                               f"状态字段是最后一步，须在 revision 生命周期推进后才写终态（tool.binding.r9）"))
    return out


_LEDGER_FIELD_RE = re.compile(r"(story|change|revision|rules|prd)\s*=\s*([^|]*)")


def check_sync_ledger(root: Path, stories, changes, revisions) -> list[Finding]:
    """T11: `_logs/sync-ledger.md` 台账与工件一致性（git-free 系统记录）。

    - 台账缺失：info（非阻断；它是便携兜底，非所有项目都用 git-free）。
    - 台账某行引用的 story/change/revision ID 在工件中不存在：warn（漂移）。
    """
    out: list[Finding] = []
    ledger = root / "_logs" / "sync-ledger.md"
    if not ledger.exists():
        out.append(Finding("info", "T11-sync-ledger", "_logs/sync-ledger.md",
                           "no sync-ledger found; git-free 审计兜底未启用（有 .git/CI 时可选）"))
        return out

    story_ids = {s.get("story_id") for s in stories if s.get("story_id")}
    change_ids = {c.get("change_id") for c in changes if c.get("change_id")}
    revision_ids = {r.get("revision_id") for r in revisions if r.get("revision_id")}

    text = ledger.read_text(encoding="utf-8", errors="replace")
    in_fence = False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not s.startswith("- ") or "story=" not in s:
            continue
        # 跳过格式说明里的占位行（含 < > 尖括号）
        if "<" in s or ">" in s:
            continue
        fields = {k: v.strip() for k, v in _LEDGER_FIELD_RE.findall(s)}

        def _none(v: str | None) -> bool:
            return (not v) or v.lower() == "none"

        sid = fields.get("story")
        if not _none(sid) and sid not in story_ids:
            out.append(Finding("warn", "T11-sync-ledger", "_logs/sync-ledger.md",
                               f"ledger references story={sid} not found among artifacts"))
        cid = fields.get("change")
        if not _none(cid) and cid not in change_ids:
            out.append(Finding("warn", "T11-sync-ledger", "_logs/sync-ledger.md",
                               f"ledger references change={cid} not found among artifacts"))
        rid = fields.get("revision")
        if not _none(rid) and rid not in revision_ids:
            out.append(Finding("warn", "T11-sync-ledger", "_logs/sync-ledger.md",
                               f"ledger references revision={rid} not found among artifacts"))
    return out


def render_report(findings: list[Finding]) -> str:
    by_level: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_level[f.level].append(f)
    lines = [f"# progress consistency report ({dt.datetime.now(dt.timezone.utc).isoformat()})\n"]
    for lvl in ("error", "warn", "info"):
        items = by_level.get(lvl) or []
        lines.append(f"\n## {lvl} ({len(items)})\n")
        for f in items:
            lines.append(f"- **{f.check}** `{f.where}`: {f.message}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=".", help="项目根；默认 cwd")
    p.add_argument("--governance-root", default=None,
                   help="治理内容根；默认读取 project-governance.yaml:governance_root")
    p.add_argument("--strict", action="store_true", help="CI 模式：所有 warn 升级为 error")
    p.add_argument("--quick", action="store_true", help="仅快速检查（T1+T7）")
    p.add_argument("--staged", action="store_true", help="pre-commit：仅校验 staged 文件的 frontmatter 完整性")
    p.add_argument("--report", default=None)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    project_root, governance_root = resolve_roots(args.project_root, args.governance_root)

    stories = collect_stories(project_root)
    changes = collect_changes(project_root)
    revisions = collect_revisions(governance_root)
    rules = collect_rule_definitions(governance_root)
    idx_revisions = collect_revisions_index(governance_root)
    scoped_revision_ids = collect_scoped_revision_ids(governance_root)

    findings: list[Finding] = []
    findings += check_id_formats(stories, changes, revisions, rules)
    findings += check_back_references(stories, changes, revisions)
    if not args.quick:
        findings += check_rule_introduced_by(rules, revisions, scoped_revision_ids)
        findings += check_state_machine(stories, changes, revisions)
        findings += check_revisions_index(governance_root, revisions, idx_revisions)
        findings += check_orphans(stories, changes, revisions)
        findings += check_content_drift(stories, changes)
        findings += check_no_new_work_on_completed_story(stories, changes)
        findings += check_status_field_coupling(stories, revisions)
        findings += check_sync_ledger(project_root, stories, changes, revisions)

    if args.strict:
        for f in findings:
            if f.level == "warn":
                f.level = "error"

    if args.report:
        out = project_root / args.report
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_report(findings), encoding="utf-8")
        if not args.quiet:
            print(f"report: {out}")

    err = sum(1 for f in findings if f.level == "error")
    warn = sum(1 for f in findings if f.level == "warn")

    # pre-commit 分层：只阻断本次改动引入的漂移，存量债务单列不阻断。
    preexisting_errors = 0
    if args.staged:
        staged = git_staged_paths(project_root)
        if staged is None:
            print("[warn] --staged 无法读取 git 暂存区，退回全量严格模式", file=sys.stderr)
        else:
            scoped = [f for f in findings if finding_touches(f, staged)]
            preexisting_errors = sum(1 for f in findings
                                     if f.level == "error" and not finding_touches(f, staged))
            findings = scoped
            err = sum(1 for f in findings if f.level == "error")
            warn = sum(1 for f in findings if f.level == "warn")

    if not args.quiet:
        for f in findings:
            print(f.fmt())
        print(f"\nstories={len(stories)} changes={len(changes)} revisions={len(revisions)} rules={len(rules)}")
        print(f"errors={err} warnings={warn}")
        if args.staged and preexisting_errors:
            print(f"preexisting_errors={preexisting_errors}（存量债务，不阻断本次提交；"
                  f"全量核对请用 --strict）")
    return 1 if err else 0


def _main_failclosed(argv: list[str]) -> int:
    """fail-closed 包装：任何未捕获异常 = 1（阻断），绝不让 agent 当'环境问题'跳过。"""
    try:
        return main(argv)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"[BLOCKED] check_progress_consistency 无法完成运行（视为不通过）: {e!r}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main_failclosed(sys.argv[1:]))
