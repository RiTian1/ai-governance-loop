#!/usr/bin/env python3
"""治理知识库健康自检（MVP）

按 domains/operations/housekeeping/ 与 02-engineering-principles.md §11 检查项：
  --check-placeholders        路径与文件名是否含 {xxx} 未替换占位符
  --check-orphans             无父引用 / 无 README / 无 _summary.yaml.canonical_owner
  --check-size-drift          _index.yaml 中 size_tokens 与实际偏差
  --check-rule-id-uniqueness  所有 _summary.yaml 中 rule_id 全局唯一
  --check-stale-revisions     candidate > 30 天未推进
  --check-three-piece         L1 / L2（含子节点）三件套齐备性
  --check-runtime-context     事实清单健康（声明/三轴字段/secrets 无明文/体量上限，ops.runtime-context.r8~r10）
  --all                       上述所有

用法:
  python scripts/check_knowledge_health.py --all
  python scripts/check_knowledge_health.py --check-placeholders --report _logs/health.md

退出码:
  0 = 全 pass / 仅 warning
  1 = 有 error
  2 = 调用错误
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from collections import defaultdict

try:
    import yaml
    _YAML_ERROR = yaml.YAMLError
except ImportError:
    # 零依赖兜底（cap.exec.portable）：改用仓库自带的 MiniYaml。
    # 这里原本是打印 "pyyaml not installed" 后 sys.exit(2)——等于"没装 pyyaml 的机器上
    # 整套知识库检查直接不可用"，而新 macOS / 精简容器正是这种环境。
    from _governance_yaml import safe_load as _mini_safe_load

    class _YamlShim:
        YAMLError = ValueError
        safe_load = staticmethod(_mini_safe_load)

    yaml = _YamlShim()
    _YAML_ERROR = Exception

PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")
RULE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z0-9-]+)*\.r\d+$")
TOKENS_PER_LINE = 8
DRIFT_RATIO = 0.20
STALE_DAYS = 30

# 受三件套协议与健康检查覆盖的顶层树（关切轴 / 项目轴 / 业务参考轴）
KNOWLEDGE_TREES = ("domains", "projects", "business-references")


def tree_dirs(root: Path) -> list[Path]:
    return [root / t for t in KNOWLEDGE_TREES if (root / t).is_dir()]


class Finding:
    __slots__ = ("level", "check", "path", "message")

    def __init__(self, level: str, check: str, path: str, message: str):
        self.level = level
        self.check = check
        self.path = path
        self.message = message

    def fmt(self) -> str:
        return f"[{self.level}] {self.check} :: {self.path} :: {self.message}"


def repo_root(arg_root: str) -> Path:
    return Path(arg_root).resolve()


def is_skip_dir(p: Path) -> bool:
    parts = set(p.parts)
    skip = {".git", "node_modules", "_upstream", "_reference", "_archive", "_logs"}
    if parts & skip:
        return True
    if "_bmad" in parts or ".claude" in parts or ".cursor" in parts or ".codex" in parts:
        return True
    return False


def check_placeholders(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for p in root.rglob("*"):
        if is_skip_dir(p):
            continue
        if PLACEHOLDER_RE.search(p.name):
            findings.append(Finding("error", "placeholder", str(p.relative_to(root)),
                                    f"path contains unsubstituted placeholder"))
    return findings


def check_three_piece(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    subs = [s for t in tree_dirs(root) for s in t.iterdir()]
    if not subs:
        return findings

    for sub in subs:
        if not sub.is_dir() or is_skip_dir(sub):
            continue
        idx = sub / "_index.yaml"
        if not idx.exists():
            continue
        try:
            data = yaml.safe_load(idx.read_text(encoding="utf-8")) or {}
        except _YAML_ERROR as e:
            findings.append(Finding("error", "three-piece", str(idx.relative_to(root)), f"yaml parse error: {e}"))
            continue

        for need in ("index.md", "_summary.yaml", "_index.yaml"):
            f = sub / need
            if not f.exists():
                findings.append(Finding("error", "three-piece", str(sub.relative_to(root)),
                                        f"L1 missing {need}"))

        for child in (data.get("children") or []):
            child_dir = sub / child["id"]
            if not child_dir.exists() or not child_dir.is_dir():
                findings.append(Finding("error", "three-piece", str(sub.relative_to(root)),
                                        f"declared child '{child['id']}' missing directory"))
                continue

            child_l3 = list(child_dir.glob("*.md"))
            grand_idx = child_dir / "_index.yaml"
            has_grandchildren = grand_idx.exists()

            for need in ("index.md", "_summary.yaml"):
                f = child_dir / need
                if not f.exists():
                    findings.append(Finding("error", "three-piece", str(child_dir.relative_to(root)),
                                            f"L2 missing {need}"))
            if has_grandchildren and not (child_dir / "_index.yaml").exists():
                findings.append(Finding("error", "three-piece", str(child_dir.relative_to(root)),
                                        "L2 with subnodes missing _index.yaml"))
    return findings


def estimate_tokens_for_file(p: Path) -> int:
    if not p.exists():
        return 0
    return max(1, len(p.read_text(encoding="utf-8", errors="replace")) // 4)


def check_size_drift(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for idx in [i for t in tree_dirs(root) for i in t.rglob("_index.yaml")]:
        if is_skip_dir(idx):
            continue
        try:
            data = yaml.safe_load(idx.read_text(encoding="utf-8")) or {}
        except _YAML_ERROR as e:
            findings.append(Finding("error", "size-drift", str(idx.relative_to(root)), f"yaml parse error: {e}"))
            continue
        own_dir = idx.parent
        declared = data.get("size_tokens")
        if declared:
            actual = estimate_tokens_for_file(own_dir / "index.md") + estimate_tokens_for_file(own_dir / "_summary.yaml")
            if actual and abs(declared - actual) / max(declared, actual) > DRIFT_RATIO:
                findings.append(Finding("warn", "size-drift", str(idx.relative_to(root)),
                                        f"declared size_tokens={declared} actual≈{actual} (>20% drift)"))
        for child in (data.get("children") or []):
            child_dir = own_dir / child["id"]
            decl = child.get("size_tokens")
            if not decl:
                continue
            actual = estimate_tokens_for_file(child_dir / "index.md") + estimate_tokens_for_file(child_dir / "_summary.yaml")
            if actual and abs(decl - actual) / max(decl, actual) > DRIFT_RATIO:
                findings.append(Finding("warn", "size-drift",
                                        str((child_dir).relative_to(root)),
                                        f"declared size_tokens={decl} actual≈{actual} (>20% drift)"))
    return findings


def check_rule_id_uniqueness(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, str] = {}
    for s in [i for t in tree_dirs(root) for i in t.rglob("_summary.yaml")]:
        if is_skip_dir(s):
            continue
        try:
            data = yaml.safe_load(s.read_text(encoding="utf-8")) or {}
        except _YAML_ERROR as e:
            findings.append(Finding("error", "rule-id", str(s.relative_to(root)), f"yaml parse error: {e}"))
            continue
        for rule in (data.get("rules") or []):
            rid = rule.get("id")
            if not rid:
                findings.append(Finding("error", "rule-id", str(s.relative_to(root)), "rule missing id"))
                continue
            if not RULE_ID_RE.match(rid):
                findings.append(Finding("error", "rule-id", str(s.relative_to(root)),
                                        f"invalid rule_id format: {rid}"))
            if rid in seen:
                findings.append(Finding("error", "rule-id", str(s.relative_to(root)),
                                        f"duplicate rule_id {rid}; first defined in {seen[rid]}"))
            else:
                seen[rid] = str(s.relative_to(root))
    return findings


def check_stale_revisions(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    rev_dir = root / "revisions"
    if not rev_dir.exists():
        return findings
    cutoff = dt.date.today() - dt.timedelta(days=STALE_DAYS)
    for md in rev_dir.glob("*.md"):
        if md.name == "README.md" or md.name == "WORKFLOW.md":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^---\n(.*?)\n---", text, re.S | re.M)
        status = None
        if m:
            try:
                front = yaml.safe_load(m.group(1)) or {}
                status = (front.get("status") or "").lower()
            except _YAML_ERROR:
                pass
        if status != "candidate":
            continue
        # 解析文件名前 10 字符 YYYY-MM-DD
        try:
            date = dt.date.fromisoformat(md.stem[:10])
        except ValueError:
            continue
        if date < cutoff:
            age = (dt.date.today() - date).days
            findings.append(Finding("warn", "stale-revision", str(md.relative_to(root)),
                                    f"candidate aged {age}d (> {STALE_DAYS}d threshold)"))
    return findings


def check_orphans(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    subs = [s for t in tree_dirs(root) for s in t.iterdir()]
    for sub in subs:
        if not sub.is_dir() or is_skip_dir(sub):
            continue
        has_index = (sub / "index.md").exists() or (sub.with_suffix(".md")).exists()
        has_summary = (sub / "_summary.yaml").exists()
        has_idx = (sub / "_index.yaml").exists()
        if not (has_index or has_summary or has_idx):
            findings.append(Finding("warn", "orphan", str(sub.relative_to(root)),
                                    "directory has no index.md / _summary.yaml / _index.yaml"))
    return findings


RUNTIME_CONTEXT_MAX_BYTES = 20 * 1024  # ops.runtime-context.r10
SECRET_INLINE_KEYS = {"value", "password", "token", "secret"}


def check_runtime_context(root: Path) -> list[Finding]:
    """事实清单健康检查（ops.runtime-context.r1/r2/r4/r10 + r9 无明文约束）。

    root 优先视为项目根：读 project-governance.yaml 的 runtime_context 键定位清单；
    键缺失时兜底找根目录 runtime-context.yaml。清单不存在时给 warn（尚未接入，不阻断）。
    """
    findings: list[Finding] = []
    manifest_rel = "runtime-context.yaml"
    pg = root / "project-governance.yaml"
    declared = False
    if pg.exists():
        try:
            pg_data = yaml.safe_load(pg.read_text(encoding="utf-8")) or {}
            if pg_data.get("runtime_context"):
                manifest_rel = str(pg_data["runtime_context"])
                declared = True
        except _YAML_ERROR:
            pass
    manifest_path = root / manifest_rel
    if not manifest_path.exists():
        findings.append(Finding("warn", "runtime-context", manifest_rel,
                                "事实清单不存在（尚未接入闭环记忆；见 templates/runtime-context-manifest-template.yaml）"))
        return findings
    if not declared and pg.exists():
        findings.append(Finding("warn", "runtime-context", "project-governance.yaml",
                                "存在 runtime-context.yaml 但 manifest 未声明 runtime_context 键（r1）"))

    size = manifest_path.stat().st_size
    if size > RUNTIME_CONTEXT_MAX_BYTES:
        findings.append(Finding("error", "runtime-context", manifest_rel,
                                f"体量 {size} B 超上限 {RUNTIME_CONTEXT_MAX_BYTES} B（r10：拆分或归档过期条目）"))

    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except _YAML_ERROR as e:
        findings.append(Finding("error", "runtime-context", manifest_rel, f"yaml parse error: {e}"))
        return findings

    loops = data.get("loops") or []
    if not loops:
        findings.append(Finding("warn", "runtime-context", manifest_rel, "loops 为空（仅占位，等于零沉淀）"))
    for lp in loops:
        lid = lp.get("id") or "<no-id>"
        for need in ("id", "description", "scope", "lifetime"):
            if not lp.get(need):
                findings.append(Finding("error", "runtime-context", manifest_rel,
                                        f"loop '{lid}' 缺必备字段 {need}（r4）"))
        if not any(lp.get(k) for k in ("requires_env", "requires_secrets", "requires_tools",
                                       "requires_packages", "requires_perms", "requires_network")):
            findings.append(Finding("warn", "runtime-context", manifest_rel,
                                    f"loop '{lid}' 无任何 requires_* 段（r4：仅占位无意义）"))
        if lp.get("lifetime") == "ephemeral" and not lp.get("teardown"):
            findings.append(Finding("error", "runtime-context", manifest_rel,
                                    f"loop '{lid}' lifetime=ephemeral 但缺 teardown（r6）"))
        for sec in (lp.get("requires_secrets") or []):
            if not isinstance(sec, dict):
                continue
            sid = sec.get("id") or "<no-id>"
            if not sec.get("id") or not sec.get("source"):
                findings.append(Finding("error", "runtime-context", manifest_rel,
                                        f"loop '{lid}' secret '{sid}' 缺 id/source 字段"))
            inline = SECRET_INLINE_KEYS & set(sec.keys())
            if inline:
                findings.append(Finding("error", "runtime-context", manifest_rel,
                                        f"loop '{lid}' secret '{sid}' 含疑似明文字段 {sorted(inline)}（r9：只存引用）"))
    return findings


def render_report(findings: list[Finding]) -> str:
    by_level: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_level[f.level].append(f)
    lines = [f"# governance health report ({dt.datetime.now(dt.timezone.utc).isoformat()})\n"]
    for lvl in ("error", "warn", "info"):
        items = by_level.get(lvl) or []
        lines.append(f"\n## {lvl} ({len(items)})\n")
        for f in items:
            lines.append(f"- **{f.check}** `{f.path}`: {f.message}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--governance-root", default=".")
    p.add_argument("--all", action="store_true")
    p.add_argument("--check-placeholders", action="store_true")
    p.add_argument("--check-orphans", action="store_true")
    p.add_argument("--check-size-drift", action="store_true")
    p.add_argument("--check-rule-id-uniqueness", action="store_true")
    p.add_argument("--check-stale-revisions", action="store_true")
    p.add_argument("--check-three-piece", action="store_true")
    p.add_argument("--check-runtime-context", action="store_true")
    p.add_argument("--report", default=None)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    root = repo_root(args.governance_root)

    run_all = args.all or not any([
        args.check_placeholders, args.check_orphans, args.check_size_drift,
        args.check_rule_id_uniqueness, args.check_stale_revisions, args.check_three_piece,
        args.check_runtime_context,
    ])

    findings: list[Finding] = []
    if run_all or args.check_placeholders:
        findings += check_placeholders(root)
    if run_all or args.check_three_piece:
        findings += check_three_piece(root)
    if run_all or args.check_orphans:
        findings += check_orphans(root)
    if run_all or args.check_size_drift:
        findings += check_size_drift(root)
    if run_all or args.check_rule_id_uniqueness:
        findings += check_rule_id_uniqueness(root)
    if run_all or args.check_stale_revisions:
        findings += check_stale_revisions(root)
    if run_all or args.check_runtime_context:
        findings += check_runtime_context(root)

    if args.report:
        out = root / args.report
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_report(findings), encoding="utf-8")
        if not args.quiet:
            print(f"report: {out}")

    err = sum(1 for f in findings if f.level == "error")
    warn = sum(1 for f in findings if f.level == "warn")
    if not args.quiet:
        for f in findings:
            print(f.fmt())
        print(f"\nerrors={err} warnings={warn}")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
