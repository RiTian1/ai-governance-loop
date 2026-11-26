#!/usr/bin/env python3
"""Cursor stop 钩子：agent 收尾时确定性跑闭环一致性自检（跨平台、仅标准库）。

治理依据：05-ai-collaboration-policy.md §6 完成判定 + §7.3 检查点协议；
domains/tooling/progress-binding（tool.binding.r9）。把「收尾前必须过 check_progress_consistency」
从人肉纪律升级为模型无法忽略的生命周期闸。

行为：agent 停止时运行 `python scripts/check_progress_consistency.py`；
  - exit 0：静默通过（stderr 记一行，进 Hooks 输出频道）
  - exit != 0：返回 followup_message，提示 agent 继续消除漂移后再收尾（不物理阻断，避免死循环）
本 hook 不设 failClosed：自检脚本本身异常时放行，避免卡死收尾。
"""
import json
import subprocess
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    p = start
    for _ in range(40):
        if (p / "scripts" / "check_progress_consistency.py").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return start


def main() -> int:
    try:
        _ = sys.stdin.read()  # 消费 stdin（内容不需要）
    except Exception:
        pass

    root = find_repo_root(Path.cwd())
    script = root / "scripts" / "check_progress_consistency.py"
    if not script.exists():
        print(json.dumps({}))
        return 0

    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(root), capture_output=True, text=True, timeout=55,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[checkpoint hook] 自检无法运行，放行收尾: {e!r}\n")
        print(json.dumps({}))
        return 0

    if proc.returncode == 0:
        sys.stderr.write("[checkpoint hook] check_progress_consistency 通过（exit 0）\n")
        print(json.dumps({}))
        return 0

    tail = (proc.stdout or "").strip().splitlines()[-8:]
    detail = "\n".join(tail)
    sys.stderr.write(f"[checkpoint hook] 一致性自检未通过（exit {proc.returncode}）:\n{detail}\n")
    print(json.dumps({
        "followup_message": (
            "收尾前检查点未通过：`python scripts/check_progress_consistency.py` 返回非 0。"
            "按 05-ai-collaboration-policy §6/§7.3，先消除三端绑定漂移或登记合法豁免，"
            "再标完成/归档/提交。自检输出尾部：\n" + detail
        )
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
