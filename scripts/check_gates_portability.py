#!/usr/bin/env python3
"""门禁可移植性自测（cap.exec.portable / gov.NFR01）。

为什么需要它
------------
治理门禁的价值前提是"在任何一台机器上都跑得起来"。一旦某个 check 脚本
在缺依赖的机器上直接 traceback，那台机器上的整套治理就是**静默失效**——
没人会发现，因为没人会去看一个崩掉的脚本。

本脚本把"换台机器就崩"变成可自动检出的事实。四种环境：

  base    真实仓库（有 .git、有 pyyaml）——基线，应当全绿
  nogit   `git archive` 导出的快照（**无 .git**）——模拟 CI 容器 / 压缩包分发
  noyaml  nogit + 屏蔽 pyyaml——模拟没装第三方库的新机器（如新 macOS）
  ro      nogit + 整树只读——模拟只读挂载 / 受保护目录

判定标准（不是"跑出 0"）：
- 退出码 MUST ∈ {0, 1}。`2` 表示"调用/环境错误"，在参数正确时等同于不可用。
- stderr MUST NOT 含 `Traceback (most recent call last)`。裸异常即崩溃。

允许的降级形态：打印一行"跳过 X（原因）"并 exit 0，或报告 findings 后 exit 1。
这正是"零依赖、随处可跑"的含义——不是"功能全有"，而是"缺什么说清楚，别崩"。

用法：
  python scripts/check_gates_portability.py              # 全部四环境
  python scripts/check_gates_portability.py --env nogit  # 只跑一个
  python scripts/check_gates_portability.py --list       # 只列脚本与参数
  python scripts/check_gates_portability.py --keep       # 保留临时目录排查

退出码：0 全部优雅 / 1 有脚本崩溃 / 2 调用错误
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

SELF = "check_gates_portability.py"
TIMEOUT_SEC = 90

# 能安全无参（或已知参数）真实运行的脚本 —— 覆盖运行期路径，不只是 --help。
RUN_ARGS = {
    "check_capability_map.py": [],
    "check_declaration_fact.py": [],
    "check_index_freshness.py": [],
    "check_staged_content.py": ["--all"],
    "check_progress_consistency.py": ["--strict"],
    "check_knowledge_health.py": ["--all"],
    "check_worktree_hygiene.py": [],
}

# 需要必填参数、只验证"能启动"的脚本
HELP_ONLY = {
    "check_commit_message.py",
    "check-agent-evals.py",
    "check_context_budget.py",
    "check_review_gate.py",
    "finish_and_verify.py",
    "preflight_check.py",
}

YAML_BLOCKER = '''\
# 由 check_gates_portability.py 注入：模拟"这台机器没装 pyyaml"
raise ImportError("blocked by check_gates_portability (simulating missing pyyaml)")
'''

# 实际部署最低版本 = macOS 14 自带的 3.9.6。以下 API 在 3.10+ 才有，
# 用了就会在那类机器上直接 TypeError / SyntaxError。
PY310_API = [
    (re.compile(r"\.write_text\([^)]*newline\s*="), "Path.write_text(newline=) 需 3.10+"),
    (re.compile(r"\.read_text\([^)]*newline\s*="), "Path.read_text(newline=) 需 3.10+"),
    (re.compile(r"\bitertools\.pairwise\("), "itertools.pairwise 需 3.10+"),
    (re.compile(r"\bzip\([^)]*\bstrict\s*="), "zip(strict=) 需 3.10+"),
]


def scan_py_compat(root: Path, min_ver=(3, 9)) -> list:
    """静态扫描 scripts/*.py：语法与 API 都不得超出 min_ver。

    这一类 bug 有复发性——gov_vault.py 修过一次 `write_text(newline=)`，
    新写的 bypass 脚本第一版又踩了一次，而 Windows 3.13 上根本测不出来。
    只有 macOS 那台系统 Python 3.9.6 会暴露。所以必须是确定性检查。
    """
    out = []
    for p in sorted((root / "scripts").glob("*.py")):
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            ast.parse(src, filename=str(p), feature_version=min_ver)
        except SyntaxError as exc:
            out.append((p.name, exc.lineno or 0,
                        "语法超出 Python %d.%d：%s" % (min_ver[0], min_ver[1], exc.msg)))
            continue
        for i, line in enumerate(src.splitlines(), 1):
            if p.name == SELF:
                break       # 本文件定义了这些正则，必然自匹配；语法检查已覆盖它
            code = line.split("#", 1)[0]        # 注释里的示例不算
            if not code.strip():
                continue
            for pat, why in PY310_API:
                if pat.search(code):
                    out.append((p.name, i, why))
    return out


def repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "project-governance.yaml").exists():
            return p
    return Path(__file__).resolve().parent.parent


def discover(root: Path) -> list:
    out = []
    for p in sorted((root / "scripts").glob("*.py")):
        n = p.name
        if n == SELF or n.startswith("_"):
            continue
        if n.startswith("check") or n in HELP_ONLY:
            out.append(n)
    return out


def _run(py: str, script: Path, args: list, cwd: Path, env: dict, timeout: int):
    t0 = time.monotonic()
    try:
        r = subprocess.run([py, str(script), *args], cwd=str(cwd), env=env,
                           capture_output=True, timeout=timeout)
        out = (r.stdout or b"").decode("utf-8", "replace")
        err = (r.stderr or b"").decode("utf-8", "replace")
        return r.returncode, out, err, time.monotonic() - t0
    except subprocess.TimeoutExpired:
        return -9, "", "TIMEOUT after %ds" % timeout, time.monotonic() - t0


def judge(rc: int, err: str) -> tuple:
    """返回 (是否优雅, 原因)。"""
    if rc == -9:
        return False, "超时"
    if "Traceback (most recent call last)" in err:
        line = [l for l in err.strip().splitlines() if l.strip()]
        tail = line[-1] if line else ""
        return False, "崩溃：%s" % tail[:70]
    if rc not in (0, 1):
        first = (err.strip().splitlines() or [""])[0]
        return False, "退出码 %d：%s" % (rc, first[:70])
    return True, "ok(rc=%d)" % rc


def overlay_worktree(root: Path, snap: Path) -> int:
    """把工作区已改/未跟踪的文件覆盖到快照上。

    只用 `git archive HEAD` 会测到**上次提交的**代码，拿不到刚写完的修复——
    那样自测就变成"验证历史"而不是"验证现状"。
    """
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    n = 0
    for line in (r.stdout or "").splitlines():
        if len(line) < 4:
            continue
        status, path = line[:2], line[3:].strip().strip('"')
        if "D" in status or "->" in path:
            continue
        src = root / path
        dst = snap / path
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            n += 1
    return n


def make_snapshot(root: Path, dest: Path) -> tuple:
    """用 git archive 导出 HEAD 快照到 dest（天然不含 .git），再覆盖工作区改动。"""
    tar = dest / "_snapshot.tar"
    r = subprocess.run(["git", "-C", str(root), "archive", "--format=tar",
                        "-o", str(tar), "HEAD"], capture_output=True)
    if r.returncode != 0 or not tar.exists():
        return False, (r.stderr or b"").decode("utf-8", "replace")[:200]
    with tarfile.open(str(tar)) as t:
        try:
            t.extractall(str(dest), filter="data")     # py3.12+
        except TypeError:
            t.extractall(str(dest))
    tar.unlink()
    overlay_worktree(root, dest)
    return True, ""


def block_yaml(sandbox: Path) -> None:
    mock = sandbox / "_mock"
    mock.mkdir(exist_ok=True)
    (mock / "yaml.py").write_text(YAML_BLOCKER, encoding="utf-8")


def set_readonly(tree: Path, readonly: bool) -> None:
    """整树设为只读 / 恢复可写。Windows 上 chmod 只切只读位，但足以让写入失败。"""
    for dirpath, dirnames, filenames in os.walk(str(tree), topdown=False):
        targets = [Path(dirpath) / f for f in filenames]
        targets += [Path(dirpath) / d for d in dirnames]
        targets.append(Path(dirpath))
        for p in targets:
            try:
                if readonly:
                    os.chmod(str(p), stat.S_IREAD | stat.S_IEXEC
                             if p.is_dir() else stat.S_IREAD)
                else:
                    os.chmod(str(p), stat.S_IWRITE | stat.S_IREAD
                             | (stat.S_IEXEC if p.is_dir() else 0))
            except OSError:
                pass


def run_env(name: str, sandbox: Path, py: str, scripts: list, root: Path):
    """在一个环境里跑全部脚本，返回 [(script, ok, reason, secs)]。"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("GOV_VAULT_PASSPHRASE", None)
    env.pop("GOV_VAULT_PASSPHRASE_CMD", None)

    if name in ("noyaml", "ro"):
        mock = sandbox / "_mock"
        env["PYTHONPATH"] = str(mock) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    results = []
    for s in scripts:
        path = sandbox / "scripts" / s
        if not path.exists():
            results.append((s, True, "跳过（快照中不存在）", 0.0))
            continue

        # L1：启动检查
        rc, _, err, secs = _run(py, path, ["--help"], sandbox, env, 60)
        if rc == 0 and "Traceback" not in err:
            # L2：运行检查（仅对有已知参数的脚本）
            if s in RUN_ARGS:
                rc2, _, err2, secs2 = _run(py, path, RUN_ARGS[s], sandbox, env, TIMEOUT_SEC)
                ok, why = judge(rc2, err2)
                results.append((s, ok, why, secs + secs2))
            else:
                results.append((s, True, "ok(--help)", secs))
        else:
            ok, why = judge(rc, err)
            results.append((s, ok, "启动失败 → " + why, secs))
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="门禁可移植性自测：四种降级环境下门禁脚本必须优雅降级")
    ap.add_argument("--env", action="append",
                    choices=["base", "nogit", "noyaml", "ro"],
                    help="只跑指定环境（可多次）")
    ap.add_argument("--list", action="store_true", help="只列脚本与调用参数")
    ap.add_argument("--keep", action="store_true", help="保留临时目录")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(argv)

    root = repo_root()
    py = sys.executable
    scripts = discover(root)

    if args.list:
        for s in scripts:
            mode = ("运行 " + " ".join(RUN_ARGS[s])) if s in RUN_ARGS else "--help"
            print("%-34s %s" % (s, mode))
        return 0

    envs = args.env or ["base", "nogit", "noyaml", "ro"]
    print("仓库：%s" % root)
    print("Python：%s  平台：%s" % (sys.version.split()[0], sys.platform))
    print("脚本：%d 个   环境：%s" % (len(scripts), ", ".join(envs)))

    tmp = Path(tempfile.mkdtemp(prefix="gates-portability-"))
    failures = []
    summary = {}
    try:
        # 先做静态扫描：3.10+ 专有 API 在 Windows 3.13 上测不出来，
        # 只有 macOS 的系统 Python 3.9 才暴露，所以必须确定性检查。
        print("\n=== 兼容性静态扫描（基线 Python 3.9 = macOS 14 系统自带）===")
        compat = scan_py_compat(root)
        if compat:
            for f, ln, why in compat:
                print("  %-32s :%-5d %s" % (f, ln, why))
                failures.append(("static", f, why))
        else:
            print("  scripts/*.py 全部通过（无 3.10+ 专有 API，语法不超 3.9）")
        summary["static"] = {"total": len(list((root / "scripts").glob("*.py"))),
                             "fail": len(compat)}

        snap = tmp / "snap"
        snap.mkdir()
        ok, why = make_snapshot(root, snap)
        if not ok:
            print("无法创建快照：%s" % why, file=sys.stderr)
            return 2

        for name in envs:
            sandbox = root if name == "base" else snap
            if name in ("noyaml", "ro"):
                block_yaml(snap)
            if name == "ro":
                set_readonly(snap, True)
            try:
                res = run_env(name, sandbox, py, scripts, root)
            finally:
                if name == "ro":
                    set_readonly(snap, False)

            print("\n=== %s ===" % name)
            for s, ok2, reason, secs in res:
                print("  %-34s %-6s %5.1fs  %s" % (s, "ok" if ok2 else "FAIL", secs, reason))
                if not ok2:
                    failures.append((name, s, reason))
            summary[name] = {"total": len(res),
                             "fail": sum(1 for x in res if not x[1])}
    finally:
        shutil.rmtree(str(tmp), ignore_errors=args.keep)
        if args.keep:
            print("\n临时目录保留：%s" % tmp)

    print("\n" + "=" * 60)
    if args.json:
        print(json.dumps({"summary": summary,
                          "failures": [{"env": e, "script": s, "reason": r}
                                       for e, s, r in failures]},
                         ensure_ascii=False, indent=1))
    if failures:
        print("失败 %d 项：" % len(failures))
        for e, s, r in failures:
            print("  [%s] %s：%s" % (e, s, r))
        print("=" * 60)
        return 1
    print("全部优雅降级（退出码 ∈ {0,1}，无 Traceback）")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
