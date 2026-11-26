#!/usr/bin/env python3
"""常驻上下文 token 预算闸（零依赖、git-optional、跨平台）。

规范：domains/tooling/_summary.yaml（tool.r8）、02-engineering-principles.md §11、
domains/operations/runtime-context/index.md §4.1（r10 触发式装载）。

它拦一种慢性漂移：AGENTS.md / CLAUDE.md / `.cursor/rules/*.mdc`(alwaysApply) /
copilot-instructions 这些**每轮必进上下文**的文件被一轮轮"加几行"撑大。
200k 窗口是常见上限，治理常驻面必须有硬预算——事实/规则内容应走触发式装载
（context_loader / 按需读文件），不许堆进常驻面。

预算来源（优先级）：
  1. --budget 参数
  2. project-governance.yaml 的 resident_token_budget 键
  3. 默认 6000

token 估算（无 tokenizer 依赖的保守近似）：CJK 字符按 1 字符 ≈ 1 token，
其余按 4 字符 ≈ 1 token。系统性偏差对"预算门"场景可接受（阈值可调）。

用法:
  python scripts/check_context_budget.py                     # 项目根自动探测
  python scripts/check_context_budget.py --budget 8000
  python scripts/check_context_budget.py --project-root DIR

退出码:
  0 = 常驻面总量在预算内
  1 = 超预算（先精简/下沉到触发式装载，再收尾）
  2 = 调用错误
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BUDGET = 6000

# 各工具的常驻装载面（相对项目根）。闸门口径 = 最坏情况工具组：
# 每个 agent 只装载自己的入口，把所有入口求和会系统性高估。
# Cursor 会把 AGENTS.md / CLAUDE.md / alwaysApply mdc 全部作为 workspace rules 注入，是最重组。
TOOL_GROUPS: dict[str, list[str]] = {
    "cursor": ["AGENTS.md", "CLAUDE.md"],          # + .cursor/rules/*.mdc(alwaysApply) 动态加入
    "claude-code": ["CLAUDE.md"],
    "codex": ["AGENTS.md"],
    "copilot": [".github/copilot-instructions.md"],
}
CURSOR_RULES_GLOB = ".cursor/rules/*.mdc"

CJK_RE = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]")


def estimate_tokens(text: str) -> int:
    cjk = len(CJK_RE.findall(text))
    other = len(text) - cjk
    return cjk + max(0, other) // 4


def is_always_apply(text: str) -> bool:
    """mdc frontmatter 含 alwaysApply: true 才计入常驻面。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    frontmatter = m.group(1) if m else ""
    if re.search(r"^alwaysApply:\s*true\b", frontmatter, re.M):
        return True
    # 治理导出的 governance-*.mdc 历史上未写 frontmatter 时默认视为常驻（保守）
    return not m


def read_budget(root: Path) -> int:
    manifest = root / "project-governance.yaml"
    if manifest.exists():
        text = manifest.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^resident_token_budget:\s*(\d+)", text, re.M)
        if m:
            return int(m.group(1))
    return DEFAULT_BUDGET


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="常驻上下文 token 预算闸")
    p.add_argument("--project-root", default=".")
    p.add_argument("--budget", type=int, default=None,
                   help="覆盖预算（省略时读 manifest resident_token_budget，再默认 6000）")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.project_root).resolve()
    budget = args.budget if args.budget is not None else read_budget(root)

    def tokens_of(rel: str) -> int | None:
        f = root / rel
        if not f.exists():
            return None
        return estimate_tokens(f.read_text(encoding="utf-8", errors="replace"))

    cursor_rules: list[tuple[str, int]] = []
    for f in sorted(root.glob(CURSOR_RULES_GLOB)):
        text = f.read_text(encoding="utf-8", errors="replace")
        if is_always_apply(text):
            cursor_rules.append((f.relative_to(root).as_posix(), estimate_tokens(text)))

    groups: dict[str, list[tuple[str, int]]] = {}
    for tool, rels in TOOL_GROUPS.items():
        entries = [(rel, n) for rel in rels if (n := tokens_of(rel)) is not None]
        if tool == "cursor":
            entries += cursor_rules
        if entries:
            groups[tool] = entries

    if not groups:
        print("[i] 未发现常驻入口文件（AGENTS.md / CLAUDE.md / copilot-instructions），跳过")
        return 0

    worst_tool, worst_total = "", 0
    if not args.quiet:
        print(f"# 常驻上下文预算闸（budget={budget} tokens/工具，估算=CJK 1:1 + 其余 4:1）")
    for tool, entries in groups.items():
        total = sum(n for _, n in entries)
        if total > worst_total:
            worst_tool, worst_total = tool, total
        if not args.quiet:
            mark = "X" if total > budget else "OK"
            print(f"  [{mark}] {tool}: ≈{total}")
            for rel, n in sorted(entries, key=lambda x: -x[1]):
                print(f"        {n:6d}  {rel}")

    if worst_total > budget:
        print(f"\n[X] 最重工具组 {worst_tool} 常驻面 ≈{worst_total} tokens 超预算 {budget}（tool.r8）。",
              file=sys.stderr)
        print("    -> 精简入口文件为路标；把规则/事实内容下沉到 domains/ 触发式装载"
              "（context_loader）或 runtime-context / project-rules 按需读取。", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"\n[OK] 所有工具组常驻面 ≤ 预算 {budget}（最重 {worst_tool} ≈{worst_total}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
