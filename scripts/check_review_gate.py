#!/usr/bin/env python3
"""AI 评审门禁：检查 PR 描述是否满足 review.r3/r4/r6/r9/r10/r11。

零依赖（无 pyyaml），可挂在 CI / pre-push / Nexus 的对话产出验收上。

用法:
  python scripts/check_review_gate.py --text-file pr-body.md
  python scripts/check_review_gate.py --text-file pr-body.md --base-ref origin/main

退出码: 0=通过  1=有 error  2=调用错误
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_SECTIONS = {
    "意图": "review.r6：缺少「## 意图」——评审无法判断这次改动为什么存在",
    "影响面": "review.r6：缺少「## 影响面」——评审无法判断波及范围",
    "验证": "review.r6：缺少「## 验证」——无法确认跑过什么",
    "风险分级": "review.r3：缺少「## 风险分级」——未声明级别按 high 处理",
    "签字": "review.r11：缺少「## 签字」——合入前必须有签字记录",
}

VALID_RISK = {"low", "medium", "high"}
# 这些取值说明签字人不是自然人，直接判红（review.r9）
NON_HUMAN_SIGNOFF = {"ai", "agent", "bot", "codex", "claude", "cursor", "项目A", "automation"}


class Finding:
    def __init__(self, level: str, rule: str, message: str):
        self.level = level
        self.rule = rule
        self.message = message

    def fmt(self) -> str:
        return f"[{self.level}] {self.rule} :: {self.message}"


def field(text: str, name: str) -> str | None:
    """取 `name: value` 形式的字段值（取第一次出现）。"""
    match = re.search(rf"^{re.escape(name)}:[ \t]*(.*)$", text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def signers(text: str) -> list[str]:
    """解析签字人：支持 `signed_by: a, b` 与多行 `signed_by: a` + `signed_by: b`。"""
    raw = re.findall(r"^signed_by:[ \t]*(.*)$", text, re.MULTILINE)
    people: list[str] = []
    for line in raw:
        for part in re.split(r"[,，、]", line):
            cleaned = part.strip().strip("`'\"")
            if cleaned and cleaned not in people:
                people.append(cleaned)
    return people


def check(text: str) -> list[Finding]:
    findings: list[Finding] = []

    for section, message in REQUIRED_SECTIONS.items():
        if not re.search(rf"^##\s*{re.escape(section)}\s*$", text, re.MULTILINE):
            findings.append(Finding("error", "review.r6", message))

    risk = (field(text, "risk_level") or "").strip().lower()
    if not risk:
        findings.append(
            Finding("error", "review.r3", "未声明 risk_level；判不准必须按 high 处理")
        )
        risk = "high"
    elif risk not in VALID_RISK:
        findings.append(
            Finding("error", "review.r3", f"risk_level 取值非法：{risk}（只允许 low/medium/high）")
        )
        risk = "high"

    ai = field(text, "ai-assisted")
    if ai is None:
        findings.append(
            Finding("error", "review.r2", "未声明 ai-assisted（没用写 none），隐瞒 AI 参与视为违规")
        )

    people = signers(text)
    if not people:
        findings.append(Finding("error", "review.r11", "没有 signed_by —— 合入前必须有人签字"))
    else:
        for person in people:
            if person.lower() in NON_HUMAN_SIGNOFF:
                findings.append(
                    Finding(
                        "error",
                        "review.r9",
                        f"signed_by 出现了非自然人「{person}」；AI 不可作为责任主体",
                    )
                )
    if risk == "high":
        if len(people) < 2:
            findings.append(
                Finding(
                    "error",
                    "review.r4",
                    f"risk_level=high 需要双人签字，当前 {len(people)} 人",
                )
            )

    if not field(text, "signed_at"):
        findings.append(Finding("warn", "review.r11", "缺 signed_at（建议 ISO 8601）"))
    if not field(text, "evidence_refs"):
        findings.append(Finding("warn", "review.r11", "缺 evidence_refs（验证证据指向）"))

    # 声明是 high 却写着"无破坏性变更"，八成是懒得判
    if risk == "high" and re.search(r"破坏性变更[：:]\s*否", text):
        findings.append(
            Finding("warn", "review.r3", "判为 high 但声明无破坏性变更，确认级别是否判高了")
        )

    return findings


def changed_files(base_ref: str | None) -> list[str]:
    if not base_ref:
        return []
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line for line in out.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="AI 评审门禁（review.r*）")
    parser.add_argument("--text-file", required=True, help="PR 描述或评审单文件路径")
    parser.add_argument("--base-ref", default=None, help="可选：用来判断是否触及高风险路径")
    args = parser.parse_args(argv[1:])

    path = Path(args.text_file)
    if not path.is_file():
        print(f"找不到输入文件：{path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    findings = check(text)

    # 触及高风险路径却没判 high，提示复核（不直接判错，避免误伤）
    risky_prefixes = ("migrations/", "src/auth", "security/", ".github/workflows/")
    if any(f.startswith(risky_prefixes) for f in changed_files(args.base_ref)):
        if (field(text, "risk_level") or "").strip().lower() != "high":
            findings.append(
                Finding(
                    "warn",
                    "review.r3",
                    "变更触及鉴权/迁移/CI 路径，建议复核 risk_level 是否应为 high",
                )
            )

    for finding in findings:
        print(finding.fmt())

    errors = [f for f in findings if f.level == "error"]
    if errors:
        print(f"\nFAIL：{len(errors)} 个 error（规范见 domains/ai-code-review.md）")
        return 1
    print("\nPASS：评审单齐备")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
