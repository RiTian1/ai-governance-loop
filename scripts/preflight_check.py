#!/usr/bin/env python3
"""重型/长耗时闭环执行前的资源与依赖预检（零依赖、git-optional、跨平台）。

规范：domains/operations/long-running-task/index.md §3（ops.long-running-task.r2）
与 domains/operations/runtime-context/index.md（ops.runtime-context.r5）。

它回答一个字段实战反复踩的问题：「这个 deploy / 镜像 load / 大批量 E2E 现在能不能跑起来」——
在执行前一次性暴露 磁盘不足 / 内存不足 / 网络不可达 / env 缺失 / 工具缺失，
而不是「跑起来两小时后才发现磁盘满了」。

用法:
  python scripts/preflight_check.py --loop deploy-staging
  python scripts/preflight_check.py --loop ci-e2e --env customer-x
  python scripts/preflight_check.py --loop deploy --manifest runtime-context.yaml --json

runtime-context.yaml 中每个 loop 可选声明 preflight 阈值:
  loops:
    - id: deploy-staging
      preflight:
        min_disk: 60G          # 目标路径可用空间下限（含解压/镜像 load 峰值放大）
        disk_path: /www        # 检查哪个路径的可用空间（默认当前工作目录）
        min_mem: 8G            # 可用内存下限
      requires_env: [DEPLOY_ROOT, FTP_URL]
      requires_tools: [{id: docker}, {id: rsync}]
      requires_network: [{host: registry.internal, port: 5000}]

environments 段（多环境矩阵，ops.long-running-task.r6）:
  environments:
    - name: customer-x
      disk_path: /home/aired/someapp-deploy
      image_version: V2.0.2.8
      report_template_version: risk-tagged-v2

退出码（fail-closed）:
  0 = 所有阻断项通过（可能有 warn）
  1 = 任一阻断项失败 / 无法运行（缺 loop、解析失败、未捕获异常）
  2 = CLI 用法错误
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml_safe_load  # noqa: E402


def parse_size(val) -> int | None:
    """'60G' / '512M' / '1024' -> bytes。无法解析返回 None。"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().upper().replace("IB", "").replace("B", "")
    if not s:
        return None
    units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    mult = 1
    if s[-1] in units:
        mult = units[s[-1]]
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def human(nbytes: int | None) -> str:
    if nbytes is None:
        return "?"
    n = float(nbytes)
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}T"


def available_memory_bytes() -> int | None:
    """跨平台可用内存（best-effort，拿不到返回 None）。"""
    # Linux: /proc/meminfo MemAvailable
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        try:
            for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
        except Exception:
            pass
    # Windows: GlobalMemoryStatusEx via ctypes
    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullAvailPhys)
        except Exception:
            pass
    return None


class Result:
    __slots__ = ("level", "check", "message")

    def __init__(self, level: str, check: str, message: str):
        self.level = level
        self.check = check
        self.message = message

    def fmt(self) -> str:
        icon = {"block": "X", "warn": "!", "ok": "OK"}.get(self.level, "?")
        return f"[{icon}] {self.check}: {self.message}"


def find_loop(manifest: dict, loop_id: str) -> dict | None:
    for lp in (manifest.get("loops") or []):
        if lp.get("id") == loop_id:
            return lp
    return None


def find_env(manifest: dict, env_name: str) -> dict | None:
    for e in (manifest.get("environments") or []):
        if e.get("name") == env_name:
            return e
    return None


def check_disk(path: str, min_disk: int | None) -> Result:
    try:
        usage = shutil.disk_usage(path)
    except Exception as e:  # noqa: BLE001
        return Result("block", "disk", f"无法读取路径 {path} 的磁盘使用: {e!r}")
    free = usage.free
    if min_disk is None:
        return Result("ok", "disk", f"{path} 可用 {human(free)}（未声明 min_disk，仅报告）")
    if free < min_disk:
        return Result("block", "disk",
                      f"{path} 可用 {human(free)} < 要求 {human(min_disk)}（不足以执行，先清理或换盘）")
    return Result("ok", "disk", f"{path} 可用 {human(free)} >= 要求 {human(min_disk)}")


def check_mem(min_mem: int | None) -> Result:
    avail = available_memory_bytes()
    if min_mem is None:
        return Result("ok", "memory",
                      f"可用内存 {human(avail)}（未声明 min_mem，仅报告）")
    if avail is None:
        return Result("warn", "memory", "无法探测可用内存（平台不支持），跳过内存门")
    if avail < min_mem:
        return Result("block", "memory",
                      f"可用内存 {human(avail)} < 要求 {human(min_mem)}")
    return Result("ok", "memory", f"可用内存 {human(avail)} >= 要求 {human(min_mem)}")


def check_env(requires_env) -> list[Result]:
    out: list[Result] = []
    for item in (requires_env or []):
        name = item.get("name") if isinstance(item, dict) else item
        if not name:
            continue
        if os.environ.get(name) in (None, ""):
            out.append(Result("block", "env", f"环境变量 {name} 未注入"))
        else:
            out.append(Result("ok", "env", f"环境变量 {name} 已注入"))
    return out


def check_tools(requires_tools) -> list[Result]:
    out: list[Result] = []
    for item in (requires_tools or []):
        tool = item.get("id") if isinstance(item, dict) else item
        if not tool:
            continue
        if shutil.which(str(tool)):
            out.append(Result("ok", "tool", f"{tool} 可用"))
        else:
            out.append(Result("block", "tool", f"{tool} 不在 PATH（缺工具）"))
    return out


def check_secrets(requires_secrets, defaults: dict) -> list[Result]:
    """凭证可解析性（不读出值）：source=env 查注入；file 查存在；vault/github-secrets 仅回显引用。"""
    out: list[Result] = []
    default_source = (defaults or {}).get("secret_source")
    for item in (requires_secrets or []):
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        if not sid:
            out.append(Result("block", "secret", "requires_secrets 条目缺 id"))
            continue
        source = item.get("source") or default_source
        if source == "env":
            if os.environ.get(str(sid)) in (None, ""):
                out.append(Result("block", "secret", f"{sid} 声明 source=env 但环境变量未注入"))
            else:
                out.append(Result("ok", "secret", f"{sid} 已注入（env）"))
        elif source == "file":
            path = item.get("path")
            if path and Path(path).expanduser().exists():
                out.append(Result("ok", "secret", f"{sid} 文件存在（{path}）"))
            else:
                out.append(Result("block", "secret", f"{sid} 声明 source=file 但文件缺失（path={path}）"))
        elif source in ("vault", "github-secrets"):
            out.append(Result("warn", "secret", f"{sid} 由 {source} 托管（本机不校验可达性，执行环境须可解析）"))
        else:
            out.append(Result("block", "secret", f"{sid} 未声明合法 source（vault/github-secrets/env/file）"))
    return out


def check_perms(requires_perms) -> list[Result]:
    """权限范围仅声明回显（本机无法验证授权系统），提醒执行者确认。"""
    perms = [str(p) for p in (requires_perms or []) if p]
    if not perms:
        return []
    return [Result("warn", "perms", f"需要权限: {', '.join(perms)}（本机不校验，执行前人工/CI 确认）")]


def check_network(requires_network, timeout: float = 4.0) -> list[Result]:
    out: list[Result] = []
    for item in (requires_network or []):
        if not isinstance(item, dict):
            continue
        host = item.get("host")
        port = item.get("port")
        if not host or not port:
            continue
        try:
            with socket.create_connection((str(host), int(port)), timeout=timeout):
                out.append(Result("ok", "network", f"{host}:{port} 可达"))
        except Exception as e:  # noqa: BLE001
            out.append(Result("block", "network", f"{host}:{port} 不可达: {e!r}"))
    return out


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="重型闭环执行前资源/依赖预检")
    p.add_argument("--governance-root", default=".")
    p.add_argument("--manifest", default="runtime-context.yaml")
    p.add_argument("--loop", required=True, help="runtime-context.yaml 中的 loop id")
    p.add_argument("--env", default=None, help="environments 段中的环境名（多环境矩阵）")
    p.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = p.parse_args(argv)

    root = Path(args.governance_root).resolve()
    manifest_path = root / args.manifest
    if not manifest_path.exists():
        print(f"[X] manifest 不存在: {manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = _yaml_safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        print(f"[X] manifest 解析失败: {e!r}", file=sys.stderr)
        return 1

    loop = find_loop(manifest, args.loop)
    if loop is None:
        print(f"[X] 未找到 loop '{args.loop}'（检查 {args.manifest} 的 loops 段）", file=sys.stderr)
        return 1

    pf = loop.get("preflight") or {}
    disk_path = pf.get("disk_path")
    min_disk = parse_size(pf.get("min_disk"))
    min_mem = parse_size(pf.get("min_mem"))

    env_info: dict = {}
    if args.env:
        env_info = find_env(manifest, args.env) or {}
        if not env_info:
            print(f"[!] 未找到环境 '{args.env}'（environments 段）；仅按 loop 默认预检", file=sys.stderr)
        # 环境矩阵可覆盖 disk_path
        disk_path = env_info.get("disk_path", disk_path)

    if not disk_path:
        disk_path = str(root)

    results: list[Result] = []
    results.append(check_disk(disk_path, min_disk))
    results.append(check_mem(min_mem))
    results.extend(check_env(loop.get("requires_env")))
    results.extend(check_secrets(loop.get("requires_secrets"), manifest.get("defaults") or {}))
    results.extend(check_perms(loop.get("requires_perms")))
    results.extend(check_tools(loop.get("requires_tools")))
    results.extend(check_network(loop.get("requires_network")))

    blocks = [r for r in results if r.level == "block"]
    warns = [r for r in results if r.level == "warn"]

    if args.json:
        print(json.dumps({
            "loop": args.loop,
            "env": args.env,
            "disk_path": disk_path,
            "environment_matrix": env_info,
            "results": [{"level": r.level, "check": r.check, "message": r.message} for r in results],
            "blocked": bool(blocks),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"# preflight: loop={args.loop}" + (f" env={args.env}" if args.env else ""))
        for r in results:
            print("  " + r.fmt())
        if env_info:
            versions = {k: v for k, v in env_info.items() if k != "name"}
            print(f"  [i] environment 声明: {versions}")
        print(f"\n阻断={len(blocks)} 警告={len(warns)}")
        if blocks:
            print("-> 预检未通过：先消除上述阻断项再执行长任务（ops.long-running-task.r2）")
        else:
            print("-> 预检通过：可以执行")

    return 1 if blocks else 0


def _main_failclosed(argv: list[str]) -> int:
    try:
        return run(argv)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"[BLOCKED] preflight_check 无法完成运行（视为不通过）: {e!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main_failclosed(sys.argv[1:]))
