#!/usr/bin/env python3
r"""声明-事实一致性检查：文档里声称的东西，实际存不存在、对不对得上。

为什么需要这个脚本
------------------
治理文档有一个特有的失败模式：**文档自我漂移**。

规则改了，但同一概念在其他 5 处仍写着旧说法。读者（尤其是 AI）读到哪一处，
就以哪一处为准，于是治理本身变成矛盾源。2026-11-19 加 `benchmarked` 状态时
就踩到过：改完 `WORKFLOW.md` 后，还有 `revisions/_summary.yaml`、
`tooling/revisions/index.md`、`foundations/progress-traceability-and-binding.md`
三处写着旧状态机 —— 全靠人工 grep 才找齐。

这个脚本把「找人 grep」变成「每次提交自动查」。

四类检查
--------
1. `rule_ref`     文档引用的 `xxx.rN` 规则号，是否真存在于某个 `_summary.yaml` 或单文件域
2. `path_ref`     文档反引号里的仓库路径，文件/目录是否真实存在
3. `script_cmd`   文档里的 `python scripts/foo.py`，脚本是否存在
4. `status_enum`  状态机正典（`revisions/WORKFLOW.md`）vs 实际 status 值 vs 各副本

**已知边界**（不要误以为已全覆盖）

- `status_enum` 只识别**箭头链**形式（`a → b → c`）。表格形式的状态枚举
  （`| \`benchmarked\` | 含义 |`）目前不检查 —— 硬做会与"表格里顺便提到状态词"混淆，
  误报率过高。要查表格只能人工或另写白名单。
- `path_ref` 不查 `docs/`（下游项目约定路径）与 `templates/`（示例占位）。
- `rule_ref` 不查 `projects.*`（下游命名空间），其余跨项目引用降为 warn。

范围
----
只扫治理实体（根文档 / foundations / domains / profiles / agents / revisions /
templates），跳过 `projects/`（下游快照）、`_bmad/`（上游框架）、`archive/`。

用法
----
    python scripts/check_declaration_fact.py            # 全量
    python scripts/check_declaration_fact.py --strict   # finding 也非 0 退出
    python scripts/check_declaration_fact.py --only rule_ref,path_ref
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---- 扫描范围 ----
ROOT_DOCS = ["AGENTS.md", "CLAUDE.md", "LAYOUT.md", "README.md", "README.zh-CN.md",
             "GIT-ACCESS.md", "BMAD-SINGLE-SOURCE.md", "BASELINE-SUPPLEMENT-REPORT.md"]
SCAN_DIRS = ["foundations", "domains", "profiles", "agents", "revisions", "templates"]
SCAN_SUFFIX = {".md", ".yaml", ".yml"}
SKIP_PARTS = {"projects", "node_modules", "_bmad", "archive", ".git", "__pycache__"}

# ---- 引用模式 ----
RULE_REF_RE = re.compile(r"\b([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*\.r\d+)\b")
PATH_REF_RE = re.compile(r"`([A-Za-z0-9_.\-/]+/[A-Za-z0-9_.\-/]+)`")
# 只认"行首命令"（允许缩进，覆盖代码块内），不认行内引用。
# 否则表格里的说明 ``| `python scripts/foo.py` |`` 会被当成真命令（实测误报过）。
SCRIPT_CMD_RE = re.compile(r"^[ \t]*python3?\s+(scripts/[A-Za-z0-9_.\-]+\.py)", re.M)
STATUS_CHAIN_RE = re.compile(r"^[^\n]*candidate[^\n]*→[^\n]*merged[^\n]*$", re.M)
STATUS_TOKEN_RE = re.compile(r"\b(candidate|benchmarked|accepted|rejected|implementing|merged|archived)\b")

# 路径引用只检查这些前缀，避免把 "a/b" 这类普通词组误判为路径
# 路径引用只检查这些前缀，避免把 "a/b" 这类普通词组误判为路径。
# `docs/` 与 `templates/` 刻意不查：
#   - `docs/project-rules.md` 是**下游项目**的约定路径，本仓没有是本分
#   - `templates/` 里是示例（如 `docs/openapi.yaml`），占位路径不该报错
PATH_PREFIXES = ("domains/", "foundations/", "profiles/", "agents/", "scripts/",
                 "revisions/", "openspec/", "rsi/", "_bmad/",
                 "business-references/", "infrastructure/", "examples/",
                 "data/", "lab/")


class Finding:
    __slots__ = ("level", "check", "where", "message")

    def __init__(self, level: str, check: str, where: str, message: str):
        self.level = level
        self.check = check
        self.where = where
        self.message = message

    def __str__(self) -> str:
        return f"[{self.level}] {self.check} :: {self.where} :: {self.message}"


def iter_docs(root: Path):
    for name in ROOT_DOCS:
        p = root / name
        if p.is_file():
            yield p
    for d in SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in SCAN_SUFFIX:
                continue
            if SKIP_PARTS & set(p.parts):
                continue
            yield p


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collect_known_rules(root: Path) -> set[str]:
    """收集"已登记"的 rule id。

    两个来源，缺一不可：
    1. `_summary.yaml` 里的 `- id: xxx.rN`（机器索引）
    2. 单文件域（如 `domains/ai-code-review.md`）里的 `- \\`xxx.rN\\`：**...**`（人读定义）

    早期只扫 (1)，导致单文件域内定义的 `review.r1..r11` 全被判成"未登记"。
    """
    ids: set[str] = set()
    summary_re = re.compile(r"^\s*-\s*id:\s*([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*\.r\d+)\s*$", re.M)
    inline_re = re.compile(
        r"^\s*[-*]\s*`([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*\.r\d+)`\s*[：:]", re.M)

    for p in root.rglob("_summary.yaml"):
        if SKIP_PARTS & set(p.parts):
            continue
        ids |= set(summary_re.findall(read_text(p)))

    domains_dir = root / "domains"
    if domains_dir.is_dir():
        for p in domains_dir.rglob("*.md"):
            if SKIP_PARTS & set(p.parts):
                continue
            ids |= set(inline_re.findall(read_text(p)))

    return ids


def collect_status_values(root: Path) -> set[str]:
    """实际用到的 revision 状态：来自 revisions/*/meta.yaml 与 revisions/index.yaml。"""
    vals: set[str] = set()
    rev_dir = root / "revisions"
    if not rev_dir.is_dir():
        return vals
    for p in rev_dir.glob("*/meta.yaml"):
        m = re.search(r"^status:\s*([a-z_]+)", read_text(p), re.M)
        if m:
            vals.add(m.group(1))
    idx = rev_dir / "index.yaml"
    if idx.is_file():
        for m in re.finditer(r"^\s*status:\s*([a-z_]+)\s*$", read_text(idx), re.M):
            vals.add(m.group(1))
    return vals


def collect_domain_prefixes(root: Path) -> set[str]:
    """本仓已存在的 domain 命名空间（`_summary.yaml` 的 domain 字段第一段）。"""
    prefixes: set[str] = set()
    for p in root.rglob("_summary.yaml"):
        if SKIP_PARTS & set(p.parts):
            continue
        m = re.search(r"^domain:\s*([a-z][a-z0-9-]*)", read_text(p), re.M)
        if m:
            prefixes.add(m.group(1))
    return prefixes


def is_baseline_doc(p: Path, root: Path) -> bool:
    """当前基线文档（可判 error）vs 历史/示例文档（只 warn）。

    历史 revision 目录、templates、revisions/index.yaml 里的跨项目规则引用是合法的，
    不应阻断提交。只有"现在仍然生效、会被 AI 当作规范读"的文档才判 error。

    注意 `revisions/WORKFLOW.md` 本身就是基线（状态机正典在这里），
    但它下面的 `revisions/<date>-<slug>/` 全是历史记录。
    """
    rel = p.relative_to(root).as_posix()
    if rel.startswith(("templates/", "projects/", "_bmad/")):
        return False
    if rel.startswith("revisions/"):
        return rel in ("revisions/WORKFLOW.md",)
    return True


def check_rule_refs(root: Path, known: set[str], docs) -> list[Finding]:
    """未登记的 rule 号分两级：

    - 出现在**基线文档**且前缀（第一段）在本仓有同名 domain → **error**：真缺口
    - 其余（跨项目引用、历史 revision、模板示例） → **warn**
    """
    out: list[Finding] = []
    prefixes = collect_domain_prefixes(root)
    for p in docs:
        text = read_text(p)
        baseline = is_baseline_doc(p, root)
        seen: set[str] = set()
        for m in RULE_REF_RE.finditer(text):
            rid = m.group(1)
            if rid in known or rid in seen:
                continue
            seen.add(rid)
            prefix = rid.split(".")[0]
            # `projects.*` 是下游项目的命名空间，母版仓不定义也不需要定义
            if prefix == "projects":
                continue
            if baseline and prefix in prefixes:
                out.append(Finding("error", "rule_ref", str(p.relative_to(root)),
                                   f"`{rid}` 的命名空间 `{prefix}` 存在于本仓，但该规则号未登记"))
            else:
                out.append(Finding("warn", "rule_ref", str(p.relative_to(root)),
                                   f"引用了本仓未定义的规则号 `{rid}`（跨项目引用或历史记录可忽略）"))
    return out


def check_path_refs(root: Path, docs) -> list[Finding]:
    out: list[Finding] = []
    for p in docs:
        text = read_text(p)
        for m in PATH_REF_RE.finditer(text):
            ref = m.group(1).rstrip("/")
            if not ref.startswith(PATH_PREFIXES):
                continue
            if any(tok in ref for tok in ("<", ">", "*", "YYYY", "NN", "{", "}")):
                continue
            target = root / ref
            if target.exists():
                continue
            # 形如 domains/xxx/ 的目录级引用，或带占位符的，跳过
            if ref.endswith(("/", ".md", ".yaml", ".yml", ".py", ".json", ".sh", ".ps1")) or "." not in ref.rsplit("/", 1)[-1]:
                out.append(Finding("warn", "path_ref", str(p.relative_to(root)),
                                   f"引用的路径不存在：`{ref}`"))
    return out


def check_script_cmds(root: Path, docs) -> list[Finding]:
    out: list[Finding] = []
    for p in docs:
        text = read_text(p)
        for m in SCRIPT_CMD_RE.finditer(text):
            ref = m.group(1)
            if (root / ref).is_file():
                continue
            out.append(Finding("error", "script_cmd", str(p.relative_to(root)),
                               f"命令里引用的脚本不存在：`{ref}`"))
    return out


CANON_STATUS_DOC = "revisions/WORKFLOW.md"


def check_status_enum(root: Path, docs) -> list[Finding]:
    """状态机声明的一致性，分两个方向：

    **方向一（正典 vs 实际）**：`revisions/WORKFLOW.md` 是状态机正典。
    实际用到的 status 值必须都在正典里声明。

    **方向二（副本 vs 正典）**：其他基线文档若复述状态链，不得出现正典里没有的状态。
    子集允许（简述场景，如 README 的 `candidate → merged`）。

    为什么不能用"所有文档的并集"作声明源：2026-11-19 实测过 —— 把 WORKFLOW.md
    改回旧状态机后，因为 `domains/tooling/revisions/index.md` 里还留着 `benchmarked`，
    并集仍然包含它，检查报 0 error，等于失效。正典必须唯一。
    """
    out: list[Finding] = []
    canonical: set[str] | None = None
    copies: list[tuple[str, set[str], str]] = []

    for p in docs:
        if not is_baseline_doc(p, root):
            continue
        rel = p.relative_to(root).as_posix()
        for m in STATUS_CHAIN_RE.finditer(read_text(p)):
            toks = set(STATUS_TOKEN_RE.findall(m.group(0)))
            if not toks:
                continue
            if rel == CANON_STATUS_DOC and canonical is None:
                canonical = toks
            elif rel != CANON_STATUS_DOC:
                copies.append((rel, toks, m.group(0).strip()[:100]))

    if canonical is None:
        return [Finding("error", "status_enum", CANON_STATUS_DOC,
                        "找不到状态机正典（含 candidate→…→merged 的行）")]

    actual = collect_status_values(root)
    missing = actual - canonical
    if missing:
        out.append(Finding("error", "status_enum", CANON_STATUS_DOC,
                           f"实际使用的 revision 状态 {sorted(missing)} 未出现在状态机正典中"))

    for rel, toks, line in copies:
        extra = toks - canonical
        if extra:
            out.append(Finding("error", "status_enum", rel,
                               f"状态机副本出现正典中没有的状态 {sorted(extra)}：`{line}`"))

    unused = canonical - actual - {"rejected"}
    if unused:
        out.append(Finding("info", "status_enum", CANON_STATUS_DOC,
                           f"状态机声明了 {sorted(unused)} 但当前无 revision 使用"))
    return out


CHECKS = {
    "rule_ref": None,       # 需要 known 参数，单独调度
    "path_ref": check_path_refs,
    "script_cmd": check_script_cmds,
    "status_enum": check_status_enum,
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="声明-事实一致性检查")
    ap.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    ap.add_argument("--strict", action="store_true", help="warning 也非 0 退出")
    ap.add_argument("--only", default=None, help="逗号分隔，限定检查项")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    docs = list(iter_docs(root))
    if not docs:
        print(f"[error] 在 {root} 下没有扫到治理文档，检查 --root", file=sys.stderr)
        return 2

    enabled = set(args.only.split(",")) if args.only else set(CHECKS) | {"rule_ref"}
    findings: list[Finding] = []

    known = collect_known_rules(root)
    if "rule_ref" in enabled:
        findings += check_rule_refs(root, known, docs)
    if "path_ref" in enabled:
        findings += check_path_refs(root, docs)
    if "script_cmd" in enabled:
        findings += check_script_cmds(root, docs)
    if "status_enum" in enabled:
        findings += check_status_enum(root, docs)

    order = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (order.get(f.level, 3), f.check, f.where))
    for f in findings:
        print(f)

    n_err = sum(1 for f in findings if f.level == "error")
    n_warn = sum(1 for f in findings if f.level == "warn")
    n_info = sum(1 for f in findings if f.level == "info")
    print(f"\ndocs={len(docs)} rules={len(known)} errors={n_err} warnings={n_warn} info={n_info}")

    if n_err:
        return 1
    if args.strict and n_warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
