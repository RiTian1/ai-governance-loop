#!/usr/bin/env python3
"""staged 内容闸：明文凭证扫描 + UTF-8 合法性（零依赖、git-optional）。

规范：domains/tooling/_summary.yaml（tool.r9）、ops.runtime-context.r9（凭证只存引用）、
AGENTS.md 禁止项（非 UTF-8 写文件）。

背景（实证）：
  - 事实落账机制（r9）让凭证类事实开始流向文件（runtime-context.yaml / project-rules.md），
    "禁明文"此前只是软约束；
  - Windows 终端 GBK 乱码反复复现，"非 UTF-8 禁写"同样无确定性拦截。

两种模式：
  --staged   pre-commit 场景：只扫 staged 新增行（凭证）+ staged 文本文件（UTF-8）。
             无 .git / 无 staged 优雅通过（git-optional）。
  --all      CI / 手动全量：扫描仓内全部文本文件（跳过生成产物与二进制）。

豁免：
  - 行内标记 `gov:allow-secret`（写在命中行或其上一行注释里）——用于示例/文档中的假值；
  - 占位符值（<...>、{{...}}、$VAR、***、your-*、example/dummy/changeme 等）自动放行。

退出码:
  0 = 通过
  1 = 命中明文凭证 / 非 UTF-8 文件
  2 = 调用错误
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ALLOW_MARK = "gov:allow-secret"

# 明文凭证模式（保守集：宁可漏报不误伤日常提交；重型扫描由项目叠加 gitleaks 等）
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    # key 两侧允许引号：JSON / YAML 里 {"password": "xxx"} 是最常见的写法之一。
    # 第一版没写这两处 ['"]?，导致带引号的 key 完全绕过（由 check_content_bypass.py H08 抓到）。
    ("password-assign", re.compile(
        r"""(?ix)['"]?[A-Za-z0-9_.-]*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token)
            [A-Za-z0-9_.-]*['"]?\s*[:=]\s*['"]?(?!\s*$)([^\s'"]{6,})""")),
    ("bearer-token", re.compile(r"(?i)\bbearer\s+[a-z0-9_\-\.=]{20,}")),
    ("aws-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("url-userinfo", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:([^@\s/]{4,})@")),
]

PLACEHOLDER_RE = re.compile(
    r"""(?ix)^(?:
        <[^>]*> | \{\{[^}]*\}\} | \$\{?[A-Z_][A-Z0-9_]*\}? | \*{3,} | x{4,} |
        (?:your|my|the|a)[-_].* | .*(?:example|sample|dummy|placeholder|changeme|redacted).* |
        none | null | true | false |
        string | number | boolean | integer | object | str | int | bytes |   # 类型注解
        .*(?:password|passwd|secret|token).* |                                # 值本身含关键词=示例假值
        [A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z0-9_$()]+)+ |                     # 成员表达式引用
        (?-i:[A-Z][A-Z0-9_]*)                                                 # 全大写常量/变量引用（PWD、DB_PASSWORD）
                                                                              # 必须关掉 (?i)：否则会放行任何标识符，
                                                                              # 包括 hunter2xyz 这样的真口令
    )$""")


def clean_value(value: str) -> str:
    return value.strip().strip("`'\",;)]}")

SKIP_DIR_PARTS = {".git", "node_modules", "_upstream", "_reference", "__pycache__",
                  ".agents", "_archive"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
                 ".tgz", ".gz", ".jar", ".exe", ".dll", ".so", ".woff", ".woff2", ".ttf"}
# 本脚本自身含模式字符串，豁免
# 本脚本含规则字面量、测试集含攻击样本，两者都不是真凭证，整体跳过扫描。
# 用精确文件名集合而不是目录/前缀匹配，避免把这个豁免扩大到别的文件。
SELF_NAMES = {"check_staged_content.py", "check_content_bypass.py"}


class Finding:
    __slots__ = ("kind", "path", "line", "message")

    def __init__(self, kind: str, path: str, line: int, message: str):
        self.kind = kind
        self.path = path
        self.line = line
        self.message = message

    def fmt(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"[X] {self.kind} :: {loc} :: {self.message}"


def is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.match(clean_value(value)))


def scan_lines(path: str, lines: list[tuple[int, str]], prev_lines: dict[int, str]) -> list[Finding]:
    """lines: [(行号, 内容)]；prev_lines: 行号→上一行内容（豁免标记可写在上一行）。"""
    out: list[Finding] = []
    if Path(path).name in SELF_NAMES:
        return out
    for lineno, text in lines:
        if ALLOW_MARK in text or ALLOW_MARK in prev_lines.get(lineno, ""):
            continue
        for kind, pat in SECRET_PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            value = m.group(1) if m.groups() else m.group(0)
            if m.groups() and is_placeholder(value):
                continue
            shown = (value[:4] + "…") if len(value) > 4 else "…"
            out.append(Finding(f"secret:{kind}", path, lineno,
                               f"疑似明文凭证（{shown}）；只存引用（source+id），"
                               f"确属假值加行内标记 {ALLOW_MARK}"))
            break
    return out


def check_utf8(path: Path, rel: str) -> Finding | None:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:  # 二进制启发式
        return None
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return Finding("encoding", rel, 0,
                       f"非 UTF-8 文本（offset {e.start}: {e.reason}）；治理仓一律 UTF-8 无 BOM")
    return None


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout or ""
    except FileNotFoundError:
        return 127, ""


def scan_staged(root: Path) -> list[Finding] | None:
    """扫 staged 新增行 + staged 文件编码。无 git 返回 None（调用方降级）。"""
    code, out = _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACM")
    if code == 127:
        return None
    if code != 0:
        return None
    files = [f for f in out.splitlines() if f.strip()]
    findings: list[Finding] = []
    for f in files:
        if any(part in SKIP_DIR_PARTS for part in f.split("/")):
            continue
        # 编码闸：以 staged blob 为准
        code2, _ = _git(root, "cat-file", "-e", f":{f}")
        if code2 == 0:
            r = subprocess.run(["git", "-C", str(root), "show", f":{f}"], capture_output=True)
            raw = r.stdout or b""
            if b"\x00" not in raw[:8192] and Path(f).suffix.lower() not in SKIP_SUFFIXES:
                try:
                    raw.decode("utf-8")
                except UnicodeDecodeError as e:
                    findings.append(Finding("encoding", f, 0,
                                            f"非 UTF-8 文本（offset {e.start}: {e.reason}）；治理仓一律 UTF-8 无 BOM"))
        # 凭证闸：只看本次新增行（不翻旧账）
        code3, diff = _git(root, "diff", "--cached", "-U1", "--", f)
        if code3 != 0:
            continue
        added: list[tuple[int, str]] = []
        prev: dict[int, str] = {}
        lineno = 0
        last_line_text = ""
        for dl in diff.splitlines():
            if dl.startswith("@@"):
                m = re.search(r"\+(\d+)", dl)
                lineno = int(m.group(1)) - 1 if m else 0
            elif dl.startswith("+") and not dl.startswith("+++"):
                lineno += 1
                added.append((lineno, dl[1:]))
                prev[lineno] = last_line_text
                last_line_text = dl[1:]
            elif not dl.startswith("-"):
                lineno += 1
                last_line_text = dl[1:] if dl else ""
        findings.extend(scan_lines(f, added, prev))
    return findings


def scan_all(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(part in SKIP_DIR_PARTS for part in p.parts):
            continue
        enc = check_utf8(p, rel)
        if enc:
            findings.append(enc)
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = list(enumerate(text.splitlines(), start=1))
        prev = {i: (lines[i - 2][1] if i >= 2 else "") for i, _ in lines}
        findings.extend(scan_lines(rel, lines, prev))
    return findings


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="staged 内容闸：明文凭证 + UTF-8")
    p.add_argument("--project-root", default=".")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="pre-commit：只扫 staged（默认）")
    mode.add_argument("--all", action="store_true", help="CI/手动：全量扫描")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.project_root).resolve()
    if args.all:
        findings = scan_all(root)
    else:
        staged = scan_staged(root)
        if staged is None:
            if not args.quiet:
                print("[i] 无 git 或 git 不可用：--staged 内容闸跳过（git-optional，不阻断）")
            return 0
        findings = staged

    for f in findings:
        print(f.fmt(), file=sys.stderr)
    n_secret = sum(1 for f in findings if f.kind.startswith("secret"))
    n_enc = sum(1 for f in findings if f.kind == "encoding")
    if findings:
        print(f"\n[X] 内容闸未通过：明文凭证 {n_secret}，非 UTF-8 {n_enc}（tool.r9）", file=sys.stderr)
        return 1
    if not args.quiet:
        print("[OK] 内容闸通过（无明文凭证、UTF-8 合法）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
