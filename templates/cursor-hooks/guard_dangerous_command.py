#!/usr/bin/env python3
"""Cursor beforeShellExecution 硬闸：拦截危险 / 高强度命令（跨平台、仅标准库、不依赖 jq）。

治理依据：domains/agent-tooling-mcp.md §9（危险命令资源护栏）+ §10（确定性生命周期闸）。
把「工具能不能调、调用强度会不会拖垮共驻服务」从纪律升级为模型无法忽略的确定性脚本。

行为：
  - 读 stdin 的 JSON（含 .command）
  - 命中 DENY 模式（不可逆破坏）→ permission=deny
  - 命中 ASK 模式（高强度 / 需人复核）→ permission=ask + 说明
  - 否则 → allow
hooks.json 中本 hook 建议 failClosed: true；故本脚本务必稳健（任何异常都显式 allow 兜底以免误伤，
除非你更保守地改为 deny）。
"""
import json
import re
import sys

# 不可逆破坏 → 直接拒绝
DENY_PATTERNS = [
    r"\brm\s+-rf\s+/(?:\s|$)",                 # rm -rf /
    r"\bgit\s+push\b.*--force\b.*\b(main|master)\b",  # 强推主分支
    r"\bmkfs\.",                                # 格式化
    r"\bdd\s+if=.*of=/dev/",                    # 裸写块设备
    r":\(\)\s*\{\s*:\|:&\s*\};:",              # fork bomb
]

# 高强度 / 需人工复核 → ask（对齐 §9：高频扫描拖垮共驻 LLM）
ASK_PATTERNS = [
    r"\bmasscan\b",
    r"\bnmap\b.*(-T5|--min-rate\s*\d{4,})",
    r"\bdnsrecon\b.*-t\s*brt",
    r"--rate=?\s*\d{4,}",                       # 每秒 >=1000 的高频
    r"\bhydra\b|\bmedusa\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-z]*f",
    r"\bdocker\s+system\s+prune\b",
]


def decide(command: str):
    for p in DENY_PATTERNS:
        if re.search(p, command):
            return ("deny", p)
    for p in ASK_PATTERNS:
        if re.search(p, command):
            return ("ask", p)
    return ("allow", None)


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        command = str(data.get("command", ""))
    except Exception:
        # 解析失败：不误伤，放行（如需更严可改为 deny）
        print(json.dumps({"permission": "allow"}))
        return 0

    perm, pattern = decide(command)
    if perm == "deny":
        print(json.dumps({
            "permission": "deny",
            "user_message": f"治理硬闸拦截：命令匹配不可逆破坏模式 /{pattern}/，已拒绝执行。",
            "agent_message": "该命令被 governance beforeShellExecution 硬闸判定为不可逆破坏，禁止执行；请改用更安全的方式或请用户手动确认。",
        }))
    elif perm == "ask":
        print(json.dumps({
            "permission": "ask",
            "user_message": f"高强度/敏感命令（匹配 /{pattern}/）。请确认强度与资源隔离（见 agent-tooling-mcp §9）后再执行。",
            "agent_message": "该命令为高强度或敏感操作，已交用户复核；执行前应声明限速/资源隔离。",
        }))
    else:
        print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
