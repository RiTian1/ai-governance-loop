#!/usr/bin/env python3
"""能力地图一致性检查：四端绑定（PRD FR ↔ Story ↔ Change ↔ Revision）与成熟度诚实性。

为什么需要这个脚本
------------------
`foundations/progress-traceability-and-binding.md §2` 声明了四端绑定，
但 2026-11-20 之前只接了三端：`_bmad/gov/prd.md` 不存在、`prd_refs` 全为 `[]`、
`FR_ID_RE` 定义了却从未被任何检查使用。结果是"为什么要做这件事"只留在
commit message 和聊天里——正是 charter §3 禁止的状态。

本脚本补上第四端，并把"能力成熟度"变成不可自评升级的字段：
说自己是 M3 就必须拿得出效应量，否则自动判 error。

检查项
------
正向（规划→落地）：
  F1  cap.fr 每个 FR 都在 PRD 里定义
  F2  cap.story 存在，且该 Story 的 prd_refs 含 cap.fr（双向一致，防挂错）
  F3  cap.change 存在，且 change.linked_story == cap.story
  F4  cap.revision 存在
  F5  cap.rules 每条都在 _summary.yaml 里定义
  F6  cap.checks 每个脚本文件存在
  F7  cap.evidence.ref 指向的路径存在

反向（代码→意图）：
  R1  PRD 里每个 FR 至少被一个能力覆盖（否则是"规划了没落地"）
  R2  任何 Story 的 prd_refs 非空时，必须能在地图里找到对应能力
  R3  任何 Story 的 epic_id 必须有对应 epic 文件

成熟度诚实性：
  M1  current / target ∈ {M0..M4}，且 current ≤ target
  M2  current ≥ M2 必须至少有一条 defect_found / destructive_test 证据
  M3  current ≥ M3 必须有 effect_size，或有合格的 bypass_attempt
      （约束型能力：attempts ≥ 8 且 rejected == attempts；
       约束型能力的价值是"挡得住"，硬套 effect_size 会让它们永远卡在 M2）
  M4  current = M4 必须 ≥2 个不同任务来源的 effect_size
      （bypass_attempt 不替代跨任务复现）

暂缓项：
  D1  deferred 每条必须有 reason 与 trigger（否则"暂缓"会变成"忘记"）

退出码：0 通过；1 有 error；2 仅 CLI 用法错误。
零依赖：只用标准库 + 仓库自带 `_governance_yaml`（无 pyyaml 时走纯标准库回退）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402

CAP_ID_RE = re.compile(r"^cap\.[a-z0-9-]+(\.[a-z0-9-]+)+$")
FR_TOKEN_RE = re.compile(r"gov\.(?:NFR|NR|FR)\d+")
MATURITY_RE = re.compile(r"^M([0-4])$")

# M3 的第二种证据：约束型能力的系统性绕过测试。
# 门槛故意写死——"我试过几次都失败了"不构成证据，必须给出可核对的数量。
MIN_BYPASS_ATTEMPTS = 8

SKIP_PARTS = {"node_modules", ".git", "projects", "__pycache__", ".venv"}


class Finding:
    __slots__ = ("level", "code", "where", "msg")

    def __init__(self, level: str, code: str, where: str, msg: str) -> None:
        self.level = level
        self.code = code
        self.where = where
        self.msg = msg

    def render(self) -> str:
        return f"[{self.level}] {self.code:<14} {self.where}: {self.msg}"


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------- 数据装载
def load_prd_frs(root: Path, prd_rel: str) -> tuple[set[str], list[Finding]]:
    out: list[Finding] = []
    p = root / prd_rel
    if not p.exists():
        out.append(Finding("error", "F0-prd-missing", prd_rel,
                           "PRD 文件不存在；四端绑定的顶层缺失"))
        return set(), out
    frs = set(FR_TOKEN_RE.findall(read(p)))
    if not frs:
        out.append(Finding("error", "F0-prd-empty", prd_rel, "PRD 里没有任何 FR/NFR 编号"))
    return frs, out


def load_stories(root: Path) -> dict[str, dict]:
    """返回 story_id -> {path, epic_id, prd_refs, status, linked_change}。"""
    stories: dict[str, dict] = {}
    for p in (root / "_bmad").rglob("*.md"):
        if SKIP_PARTS & set(p.parts):
            continue
        text = read(p)
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end < 0:
            continue
        fm = text[3:end]
        d: dict = {}
        for line in fm.splitlines():
            m = re.match(r"^([a-z_]+):\s*(.*)$", line)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip()
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                d[k] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()] if inner else []
            elif v in ("null", "~", ""):
                d[k] = None
            else:
                d[k] = v.strip("\"'")
        sid = d.get("story_id")
        if sid:
            d["__path"] = str(p.relative_to(root))
            stories[sid] = d
    return stories


def load_changes(root: Path) -> dict[str, dict]:
    changes: dict[str, dict] = {}
    base = root / "openspec" / "changes"
    if not base.exists():
        return changes
    for p in base.rglob("proposal.md"):
        text = read(p)
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        fm = text[3:end] if end > 0 else text[3:]
        d: dict = {}
        for line in fm.splitlines():
            m = re.match(r"^([a-z_]+):\s*(.*)$", line)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip()
            d[k] = None if v in ("null", "~", "") else v.strip("\"'")
        cid = d.get("change_id")
        if cid:
            d["__path"] = str(p.relative_to(root))
            d["__dir"] = str(p.parent.relative_to(root))
            changes[cid] = d
    return changes


def load_revisions(root: Path) -> dict[str, dict]:
    revs: dict[str, dict] = {}
    base = root / "revisions"
    if not base.exists():
        return revs
    for p in base.rglob("meta.yaml"):
        if "archive" in p.parts:
            continue
        d = _yaml_safe_load(read(p))
        if not isinstance(d, dict):
            continue
        rid = d.get("revision_id")
        if rid:
            d["__path"] = str(p.relative_to(root))
            revs[rid] = d
    return revs


def load_rules(root: Path) -> set[str]:
    ids: set[str] = set()
    for p in (root / "domains").rglob("_summary.yaml"):
        if SKIP_PARTS & set(p.parts):
            continue
        for m in re.finditer(r"^\s*-\s*id:\s*([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*\.r\d+)\s*$",
                             read(p), re.M):
            ids.add(m.group(1))
    return ids


# ---------------------------------------------------------------- 检查
def check_forward(cap: dict, idx: int, ctx: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = cap.get("id") or f"<cap#{idx}>"
    where = f"docs/governance-roadmap/CAPABILITY-MAP.yaml#{cid}"

    if not CAP_ID_RE.match(cid):
        out.append(Finding("error", "S0-cap-id", where, f"能力 id 不符合 cap.<layer>.<name>：{cid}"))

    frs = cap.get("fr") or []
    if not isinstance(frs, list):
        frs = [frs]
    if not frs:
        out.append(Finding("error", "F1-no-fr", where, "能力未归属任何 FR；无 FR 归属的能力不得进地图"))
    for fr in frs:
        if fr not in ctx["prd_frs"]:
            out.append(Finding("error", "F1-fr-undefined", where,
                               f"fr={fr} 未在 {ctx['prd_rel']} 里定义"))

    sid = cap.get("story")
    if sid:
        st = ctx["stories"].get(sid)
        if not st:
            out.append(Finding("error", "F2-story-missing", where, f"story={sid} 不存在"))
        else:
            refs = st.get("prd_refs") or []
            if not refs:
                out.append(Finding("error", "F2-story-no-prd", where,
                                   f"story={sid} 的 prd_refs 为空，与地图声称的归属不一致"))
            elif not set(frs) & set(refs):
                out.append(Finding("error", "F2-fr-mismatch", where,
                                   f"地图 fr={frs} 与 story={sid} 的 prd_refs={refs} 无交集"))

    chid = cap.get("change")
    if chid:
        ch = ctx["changes"].get(chid)
        if not ch:
            out.append(Finding("error", "F3-change-missing", where, f"change={chid} 不存在"))
        elif sid and ch.get("linked_story") != sid:
            out.append(Finding("error", "F3-change-link", where,
                               f"change={chid}.linked_story={ch.get('linked_story')} 与地图 story={sid} 不一致"))

    rid = cap.get("revision")
    if rid and rid not in ctx["revisions"]:
        out.append(Finding("error", "F4-revision-missing", where, f"revision={rid} 不存在"))

    for r in (cap.get("rules") or []):
        if r not in ctx["rules"]:
            out.append(Finding("error", "F5-rule-missing", where, f"rule={r} 未在任何 _summary.yaml 定义"))

    for s in (cap.get("checks") or []):
        if not (ctx["root"] / s).exists():
            out.append(Finding("error", "F6-check-missing", where, f"checks 引用的脚本不存在：{s}"))

    for ev in (cap.get("evidence") or []):
        ref = (ev or {}).get("ref")
        if not ref:
            out.append(Finding("warn", "F7-evidence-noref", where, "evidence 条目缺 ref"))
            continue
        if ("/" in ref or ref.endswith((".md", ".py", ".yaml", ".json"))) and not (ctx["root"] / ref).exists():
            out.append(Finding("error", "F7-evidence-missing", where, f"evidence.ref 不存在：{ref}"))

    return out


def _int_or_zero(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def check_maturity(cap: dict, idx: int) -> list[Finding]:
    out: list[Finding] = []
    cid = cap.get("id") or f"<cap#{idx}>"
    where = f"docs/governance-roadmap/CAPABILITY-MAP.yaml#{cid}"
    cur, tgt = cap.get("current"), cap.get("target")
    mc = MATURITY_RE.match(str(cur or ""))
    mt = MATURITY_RE.match(str(tgt or ""))
    if not mc or not mt:
        out.append(Finding("error", "M1-maturity-format", where,
                           f"current={cur} / target={tgt} 不符合 M0–M4"))
        return out
    if int(mc.group(1)) > int(mt.group(1)):
        out.append(Finding("error", "M1-maturity-invert", where,
                           f"current={cur} 高于 target={tgt}"))
    kinds = [(e or {}).get("kind") for e in (cap.get("evidence") or [])]
    evidence = [e for e in (cap.get("evidence") or []) if e]
    if int(mc.group(1)) >= 2 and not ({"defect_found", "destructive_test"} & set(kinds)):
        out.append(Finding("error", "M2-maturity-claim", where,
                           f"自称 {cur} 但无 defect_found / destructive_test 证据（M2 必须证伪过）"))

    # M3 两条路径：
    #   ① effect_size —— 配对实验的量化效应量（产出质量类能力）
    #   ② bypass_attempt —— 系统性绕过尝试全被拒（约束型能力：保险箱、内容闸、门禁）
    # 约束型能力的价值是"挡得住"，不是"提升多少分"，硬套 effect_size 会让它们永远卡在 M2。
    # 但 bypass 必须可校验：带 attempts/rejected 计数，且全拒、且样本量够。
    bypass_ok = [e for e in evidence
                 if e.get("kind") == "bypass_attempt"
                 and _int_or_zero(e.get("attempts")) >= MIN_BYPASS_ATTEMPTS
                 and _int_or_zero(e.get("rejected")) == _int_or_zero(e.get("attempts"))
                 and _int_or_zero(e.get("rejected")) > 0]
    if int(mc.group(1)) >= 3 and "effect_size" not in kinds and not bypass_ok:
        out.append(Finding("error", "M3-maturity-claim", where,
                           f"自称 {cur} 但既无 effect_size，也无合格的 bypass_attempt"
                           f"（需 attempts≥{MIN_BYPASS_ATTEMPTS} 且 rejected==attempts）"))
    if int(mc.group(1)) == 4:
        refs = {(e or {}).get("ref") for e in evidence
                if (e or {}).get("kind") == "effect_size"}
        if len(refs) < 2:
            out.append(Finding("error", "M4-maturity-claim", where,
                               f"自称 M4 但 effect_size 来源只有 {len(refs)} 个"
                               f"（M4 需 ≥2 个独立任务；bypass_attempt 不能替代跨任务复现）"))
    return out


def check_reverse(caps: list[dict], ctx: dict) -> list[Finding]:
    out: list[Finding] = []
    covered_frs: set[str] = set()
    cited_stories: set[str] = set()
    for c in caps:
        for fr in (c.get("fr") or []):
            covered_frs.add(fr)
        if c.get("story"):
            cited_stories.add(c["story"])

    for fr in sorted(ctx["prd_frs"] - covered_frs):
        out.append(Finding("error", "R1-fr-uncovered", ctx["prd_rel"],
                           f"{fr} 未被任何能力覆盖（规划了但没落地）"))

    for sid, st in ctx["stories"].items():
        refs = st.get("prd_refs") or []
        if refs and sid not in cited_stories:
            out.append(Finding("warn", "R2-story-orphan", st["__path"],
                               f"story={sid} 声明了 prd_refs={refs}，但地图里没有引用它"))

    epics_dir = ctx["root"] / "_bmad" / "gov" / "epics"
    for sid, st in ctx["stories"].items():
        eid = st.get("epic_id")
        if not eid:
            out.append(Finding("warn", "R3-epic-missing-field", st["__path"], "story 缺 epic_id"))
            continue
        num = eid.split(".")[-1] if "." in eid else ""
        if not num or not list(epics_dir.glob(f"{num}-*.md")):
            out.append(Finding("error", "R3-epic-file-missing", st["__path"],
                               f"epic_id={eid} 没有对应的 _bmad/gov/epics/{num}-*.md"))
    return out


def check_deferred(doc: dict) -> list[Finding]:
    out: list[Finding] = []
    for i, d in enumerate(doc.get("deferred") or []):
        did = (d or {}).get("id") or f"<deferred#{i}>"
        where = f"docs/governance-roadmap/CAPABILITY-MAP.yaml#{did}"
        if not (d or {}).get("reason"):
            out.append(Finding("error", "D1-no-reason", where, "暂缓项缺 reason：会被后来者当成遗漏"))
        if not (d or {}).get("trigger"):
            out.append(Finding("error", "D1-no-trigger", where,
                               "暂缓项缺 trigger：没有重新评估条件等于永久放弃"))
        for fr in (d or {}).get("fr") or []:
            if not FR_TOKEN_RE.match(fr):
                out.append(Finding("error", "D1-bad-fr", where, f"fr 格式不合法：{fr}"))
    return out


def check_story_id_unique(root: Path) -> list[Finding]:
    """Story 编号唯一性。

    2026-11-20 实测：`gov.S04.18` 被两个文件同时占用
    （<业务域>-ops-capacity-cleanup 与 rsi-runner-harness-defects），
    两个检查器都没报——因为都是按 id 建字典，后一个静默覆盖前一个。
    编号是四端绑定的连接键，重复会让反向引用指向不确定的对象。
    """
    out: list[Finding] = []
    seen: dict[str, str] = {}
    for p in sorted((root / "_bmad").rglob("*.md")):
        if SKIP_PARTS & set(p.parts):
            continue
        text = read(p)
        if not text.startswith("---"):
            continue
        m = re.search(r"^story_id:\s*(\S+)\s*$", text[:2000], re.M)
        if not m:
            continue
        sid, rel = m.group(1), str(p.relative_to(root))
        if sid in seen:
            out.append(Finding("error", "S2-dup-story", rel,
                               f"story_id={sid} 已被 {seen[sid]} 占用（编号必须唯一）"))
        else:
            seen[sid] = rel
    return out


def check_duplicates(caps: list[dict], doc: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for c in caps:
        cid = c.get("id")
        if cid in seen:
            out.append(Finding("error", "S1-dup-cap", f"MAP#{cid}", "能力 id 重复"))
        seen.add(cid)
    has_prd = any((c.get("fr") or []) for c in caps)
    if not has_prd:
        out.append(Finding("error", "S1-no-fr-anywhere", "MAP", "整张地图没有任何 FR 归属"))
    return out


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="治理能力地图一致性检查")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--map", default="docs/governance-roadmap/CAPABILITY-MAP.yaml")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    map_path = root / args.map
    if not map_path.exists():
        print(f"[error] S0-map-missing {args.map}: 能力地图不存在", file=sys.stderr)
        return 1

    doc = _yaml_safe_load(read(map_path))
    if not isinstance(doc, dict):
        print(f"[error] S0-map-parse {args.map}: 无法解析为映射", file=sys.stderr)
        return 1

    prd_rel = doc.get("prd") or "_bmad/gov/prd.md"
    prd_frs, findings = load_prd_frs(root, prd_rel)

    ctx = {
        "root": root,
        "prd_rel": prd_rel,
        "prd_frs": prd_frs,
        "stories": load_stories(root),
        "changes": load_changes(root),
        "revisions": load_revisions(root),
        "rules": load_rules(root),
    }

    caps = doc.get("capabilities") or []
    if not caps:
        findings.append(Finding("error", "S1-no-cap", args.map, "capabilities 为空"))
    for i, cap in enumerate(caps):
        cap = cap or {}
        findings += check_forward(cap, i, ctx)
        findings += check_maturity(cap, i)
    findings += check_reverse(caps, ctx)
    findings += check_story_id_unique(root)
    findings += check_deferred(doc)
    findings += check_duplicates(caps, doc)

    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]

    for f in errors + warns:
        print(f.render())

    m_cur = {}
    for c in caps:
        m = MATURITY_RE.match(str((c or {}).get("current") or ""))
        if m:
            m_cur[int(m.group(1))] = m_cur.get(int(m.group(1)), 0) + 1
    dist = " ".join(f"M{i}={m_cur.get(i, 0)}" for i in range(5))
    print(f"\ncapabilities={len(caps)} deferred={len(doc.get('deferred') or [])} "
          f"frs={len(prd_frs)} stories={len(ctx['stories'])} changes={len(ctx['changes'])}")
    print(f"maturity: {dist}")
    print(f"errors={len(errors)} warnings={len(warns)}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
