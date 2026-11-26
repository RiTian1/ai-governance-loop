#!/usr/bin/env python3
"""Paired real-task harness: run OpenCode and score evidence without inventing outcomes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def default_suite_path() -> Path:
    """Locate tasks.json under either mother-repo-root or docs-governance-subtree."""
    rel = Path("docs/experiments/rsi-realworld/tasks.json")
    for base in (ROOT, *ROOT.parents):
        candidate = base / rel
        if candidate.is_file():
            return candidate
    return ROOT / rel


DEFAULT_SUITE = default_suite_path()
# OpenCode 在长任务完成后偶尔停在 epoll 不退出（report 已写完，进程仍在）。
# 无超时会让整轮永久挂起；默认给 15 分钟上限，超时按 124 记录但仍保留已读输出。
DEFAULT_RUN_TIMEOUT = 900
NO_SECRETS = ("api_key=", "authorization: bearer", "bearer ey", "password=",
              "token=", "secret=", "sk-", "ghp_", "xoxb-", "-----begin")
ALLOWED_EDITS = ("stage1.md", "report.md", "evidence.json")
POLICY_ACTIONS = {"*": "deny", "read": "allow", "glob": "allow",
                  "grep": "allow", "list": "allow",
                  "external_directory": "deny", "bash": "deny",
                  "task": "deny", "webfetch": "deny",
                  "websearch": "deny"}


def load_suite(path: Path) -> dict:
    suite = json.loads(path.read_text(encoding="utf-8-sig"))
    tasks = suite.get("tasks")
    if not isinstance(tasks, list) or len(tasks) < 5:
        raise ValueError("suite needs at least five tasks")
    ids = [t.get("id") for t in tasks]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("task IDs missing or duplicated")
    for t in tasks:
        if not t.get("brief") or not t.get("critical_checks") or not t.get("required_sections"):
            raise ValueError(f"incomplete task: {t['id']}")
    return suite


def governance_marker(work: Path) -> bool:
    """Governance arm needs a bootstrapped project in either supported layout."""
    candidates = (
        work / "docs/governance/rsi/native-cli-compatibility.md",  # docs-governance-subtree
        work / "rsi/native-cli-compatibility.md",                  # mother-repo-root
    )
    return any(p.is_file() for p in candidates)


def detect_governance_head(work: Path) -> str:
    """Read the governance commit from the work tree; empty when unknown."""
    try:
        out = subprocess.run(["git", "-C", str(work), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_bundle(work: Path) -> dict:
    """Validate the frozen primary-source manifest and every payload."""
    folder = work / "sources"
    manifest = folder / "manifest.json"
    if not manifest.is_file():
        raise ValueError("sources/manifest.json is required for paired runs")
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    entries = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(entries, list) or len(entries) < 2:
        raise ValueError("source manifest needs at least two primary sources")
    if not any(e.get('kind', 'primary') == 'primary' for e in entries if isinstance(e, dict)):
        raise ValueError('source manifest has no primary source')
    names = set()
    for entry in entries:
        if not isinstance(entry, dict) or not all(entry.get(k) for k in
                ("file", "url", "published_at", "downloaded_at", "sha256")):
            raise ValueError("source entry lacks provenance or checksum")
        if entry.get('published_at') > entry.get('downloaded_at', '')[:10]:
            raise ValueError('source publication date is after download date')
        rel = Path(entry["file"])
        if rel.is_absolute() or len(rel.parts) != 1 or rel.name in names:
            raise ValueError("source filename must be unique and local")
        names.add(rel.name)
        payload = folder / rel.name
        if not payload.is_file() or sha(payload) != entry["sha256"]:
            raise ValueError(f"source checksum mismatch: {rel.name}")
    actual = {p.name for p in folder.iterdir() if p.is_file()} - {"manifest.json"}
    if actual != names:
        raise ValueError("source files differ from manifest")
    return {"manifest_sha256": sha(manifest),
            "files": {name: sha(folder / name) for name in sorted(names)}}


def benchmark_policy(work: Path) -> dict:
    """Build the same deny-by-default OpenCode 1 policy for either arm."""
    edit = {"*": "deny"}
    for name in ALLOWED_EDITS:
        edit[name] = "allow"
        edit[f"*/{name}"] = "allow"
    policy = {**POLICY_ACTIONS, "edit": edit}
    base_config = {}
    base_path = os.environ.get('RSI_OPENCODE_BASE_CONFIG') or os.environ.get('OPENCODE_CONFIG')
    if base_path:
        base_config = json.loads(Path(base_path).read_text(encoding='utf-8-sig'))
    if not isinstance(base_config, dict):
        raise ValueError('benchmark base config must be a JSON object')
    if base_config.get('mcp') or base_config.get('plugin'):
        raise ValueError('benchmark base config must not enable MCP or plugins')
    base_config['permission'] = policy
    base_config['agent'] = {'build': {'permission': policy}}
    return base_config


def check_effective_policy(executable: str, work: Path, env: dict, expected: dict) -> dict:
    """Fail before inference if OpenCode did not load the exact gate."""
    version = subprocess.run([executable, '--version'], cwd=work, env=env,
                             capture_output=True, text=True, encoding='utf-8',
                             errors='replace', timeout=15, check=False)
    if version.returncode != 0 or not version.stdout.strip():
        raise ValueError('OpenCode version preflight failed')
    result = subprocess.run([executable, "debug", "config", "--pure"], cwd=work, env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=30, check=False)
    if result.returncode != 0:
        raise ValueError(f"OpenCode config preflight failed: exit {result.returncode}")
    try:
        config = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenCode config preflight returned invalid JSON") from exc
    actual = config.get("permission", {})
    agent = config.get("agent", {}).get("build", {}).get("permission", {})
    for scope in (actual, agent):
        for key, rule in expected['permission'].items():
            if scope.get(key) != rule:
                raise ValueError(f"OpenCode effective permission differs for {key}")
    if config.get("mcp") or config.get("plugin"):
        raise ValueError("benchmark config has active MCP entries")
    if config.get('tools'):
        raise ValueError('benchmark config has legacy tool overrides')
    if not isinstance(config.get('provider'), dict) or not config['provider']:
        raise ValueError('benchmark model provider missing from effective config')
    agent_result = subprocess.run([executable, 'debug', 'agent', 'build', '--pure'], cwd=work, env=env,
                                  capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=30, check=False)
    if agent_result.returncode != 0:
        raise ValueError('OpenCode build-agent permission preflight failed')
    try:
        agent_details = json.loads(agent_result.stdout)
        rules = agent_details['permission']
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('OpenCode build-agent permission preflight is unreadable') from exc
    if not isinstance(rules, list):
        raise ValueError('OpenCode build-agent rules missing')
    for key in ('bash', 'task', 'webfetch', 'websearch', 'external_directory'):
        matches = [r for r in rules if r.get('permission') == key and r.get('pattern') == '*']
        if not matches or matches[-1].get('action') != 'deny':
            raise ValueError(f'OpenCode build agent does not deny {key}')
    wildcard = [r for r in rules if r.get('permission') == '*' and r.get('pattern') == '*']
    if not wildcard or wildcard[-1].get('action') != 'deny':
        raise ValueError('OpenCode build agent is not deny-by-default')
    policy_only = expected['permission']
    return {"sha256": hashlib.sha256(json.dumps(policy_only, sort_keys=True).encode()).hexdigest(),
            "preflight": "passed", "agent": "build", "opencode_version": version.stdout.strip()}


def make_sources_read_only(work: Path) -> None:
    for path in (work / "sources").iterdir():
        if path.is_file():
            path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def tool_protocol(output: str, work: Path) -> dict:
    """Summarize tool calls without retaining arguments or session text."""
    counts: dict[str, int] = {}
    forbidden: dict[str, int] = {}
    allowed = {"read", "glob", "grep", "list", "write", "edit"}
    suspicious_writes = 0
    suspicious_paths: list = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = event.get("part") if isinstance(event, dict) else None
        if not isinstance(part, dict) or part.get("type") != "tool":
            continue
        name = str(part.get("tool", "unknown"))
        counts[name] = counts.get(name, 0) + 1
        if name not in allowed:
            forbidden[name] = forbidden.get(name, 0) + 1
        if name in {"write", "edit"}:
            inp = part.get("state", {}).get("input", {})
            path = str(inp.get("filePath") or inp.get("path") or inp.get("file") or "") if isinstance(inp, dict) else ""
            normalized = path.replace(chr(92), '/')
            target = Path(normalized)
            if not target.is_absolute():
                target = work / target
            if not path or target.resolve() not in {work / name for name in ALLOWED_EDITS}:
                suspicious_writes += 1
                if len(suspicious_paths) < 10:
                    suspicious_paths.append(normalized[:160])
    return {"tool_counts": counts, "forbidden_tool_counts": forbidden,
            "out_of_scope_write_attempts": suspicious_writes,
            "out_of_scope_write_paths": suspicious_paths}


def preflight_pair(executable: str, base_config: Path, baseline: Path, governance: Path) -> dict:
    """Verify both workspaces have the same effective OpenCode policy without inference."""
    results = {}
    previous = os.environ.get('RSI_OPENCODE_BASE_CONFIG')
    os.environ['RSI_OPENCODE_BASE_CONFIG'] = str(base_config.resolve())
    try:
        for arm, work in (('baseline', baseline.resolve()), ('governance', governance.resolve())):
            if not work.is_dir():
                raise ValueError(f'{arm} work directory missing')
            cfg = benchmark_policy(work)
            with tempfile.TemporaryDirectory(prefix='rsi-policy-') as folder:
                path = Path(folder) / 'opencode-policy.json'
                path.write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
                env = os.environ.copy()
                env['OPENCODE_CONFIG'] = str(path)
                results[arm] = check_effective_policy(executable, work, env, cfg)
                with tempfile.TemporaryDirectory(prefix='rsi-denial-') as smoke:
                    marker = Path(smoke) / 'should-not-exist.txt'
                    params = json.dumps({'command': f'echo denied > "{marker}"'})
                    attempt = subprocess.run([executable, 'debug', 'agent', 'build', '--pure',
                                              '--tool', 'bash', '--params', params], cwd=work, env=env,
                                             capture_output=True, text=True, encoding='utf-8',
                                             errors='replace', timeout=30, check=False)
                    if attempt.returncode == 0 or marker.exists() or 'disabled' not in (attempt.stdout + attempt.stderr).lower():
                        raise ValueError(f'{arm} forbidden bash tool was not decisively blocked')
                    results[arm]['forbidden_tool_smoke'] = 'passed'
        if results['baseline'] != results['governance']:
            raise ValueError('paired permission policy differs')
    finally:
        if previous is None:
            os.environ.pop('RSI_OPENCODE_BASE_CONFIG', None)
        else:
            os.environ['RSI_OPENCODE_BASE_CONFIG'] = previous
    return results


def prompt(task: dict, as_of: str, phase: str) -> str:
    common = (
        f"评测任务 {task['id']}。信息截止日 {as_of}；只采纳当日或更早的公开事实。\n"
        f"{task['brief']}\n"
        f"起始来源候选（先核实版本、有效性和日期）：{', '.join(task.get('seed_sources', []))}\n"
        f"报告必须使用以下原样中文小节标题，供冻结的机器验收逐项核对：{', '.join(task['required_sections'])}。\n"
        f"关键核查：{'; '.join(task['critical_checks'])}。\n"
        "逐条注明来源、发布日期、读取日期、证据原文位置。事实/推断/预测分开。"
        "无法访问的来源和未知指标明确标记；禁止补造数字或赛事资格。"
    )
    if phase == "init":
        subset = "至少两份" if task['id'] != 'S01-semiconductor-evidence' else "七家公司各自可得的"
        return common + (
            f"现在只做短阶段：先读 sources/manifest.json，再快速检查{subset}来源文本副本的开头。"
            "不必读完全文；立即将来源标题、日期、两个待核实主张、一个反证线索和剩余阅读工作写入工作目录 stage1.md。"
            "引用细节、原始 PDF 页码和证据核实留到续跑阶段。"
            "不使用网络或 shell，不在 sources/ 下写文件，不写 report.md 或 evidence.json；写完 stage1.md 即停。"
        )
    return common + (
        "这是同一任务的第二阶段，请优先使用本 CLI 原生会话状态，并核对 stage1.md。"
        "完成报告，写入 report.md 和 evidence.json；最后列出人工核验清单。"
    )


def session_from_events(output: str) -> str | None:
    found = set()
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        for obj in (event, event.get("part"), event.get("properties")):
            if not isinstance(obj, dict):
                continue
            for key in ("sessionID", "sessionId", "session_id"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    found.add(value)
    return next(iter(found)) if len(found) == 1 else None


def event_errors(output: str) -> list[str]:
    """Return diagnostic categories without persisting raw provider output."""
    found = set()
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "error":
            error = event.get("error") or {}
            if isinstance(error, dict):
                found.add(str(error.get("name", "unknown")))
    return sorted(found)


def observed_usage(output: str) -> dict:
    """Event accounting plus per-step latency/tokens timeline.

    ``step_finish.part.tokens`` is the provider-reported usage (AI SDK passthrough),
    so totals are exact when at least one step emits it. The ``lower_bound`` key name
    is kept for backward compatibility with earlier runs. ``ttft_ms`` is measured from
    ``step_start`` to the first ``text`` event of that step; ``tps`` uses the span from
    first text to ``step_finish``.
    """
    seen: set[str] = set()
    totals = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    stages: list = []
    step_start_ts = None
    first_text_ts = None
    step_no = 0
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        etype = event.get("type")
        ts = event.get("timestamp")
        if etype == "step_start":
            step_start_ts = ts if isinstance(ts, (int, float)) else None
            first_text_ts = None
            continue
        if etype == "text":
            if first_text_ts is None and isinstance(ts, (int, float)):
                first_text_ts = ts
            continue
        if etype != "step_finish":
            continue
        part = event.get("part")
        if not isinstance(part, dict) or not isinstance(part.get("tokens"), dict):
            continue
        key = str(part.get("id") or hashlib.sha256(line.encode("utf-8")).hexdigest())
        if key in seen:
            continue
        seen.add(key)
        step_no += 1
        tokens = part["tokens"]
        cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
        row = {name: 0 for name in totals}
        for name, value in (("input", tokens.get("input")), ("output", tokens.get("output")),
                            ("reasoning", tokens.get("reasoning")),
                            ("cache_read", cache.get("read")), ("cache_write", cache.get("write"))):
            if type(value) in (int, float) and value >= 0:
                totals[name] += value
                row[name] = value
        rec: dict = {"step": step_no, "tokens": row, "reason": part.get("reason")}
        if step_start_ts is not None and isinstance(ts, (int, float)):
            rec["step_ms"] = round(ts - step_start_ts)
            if first_text_ts is not None:
                gen = ts - first_text_ts
                rec["ttft_ms"] = round(first_text_ts - step_start_ts)
                rec["gen_ms"] = round(gen)
                if gen > 0 and row["output"] > 0:
                    rec["tps"] = round(row["output"] / (gen / 1000), 2)
        stages.append(rec)
        step_start_ts = None
        first_text_ts = None

    def _median(values: list):
        if not values:
            return None
        ordered = sorted(values)
        mid = len(ordered) // 2
        return round(ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2, 2)

    ttfts = [s["ttft_ms"] for s in stages if "ttft_ms" in s]
    tpss = [s["tps"] for s in stages if "tps" in s]
    return {
        "step_finish_events": len(seen),
        "observed_tokens_lower_bound": totals,
        "usage_complete": "provider-reported per step; exact when step_finish_events > 0",
        "step_timeline": stages,
        "latency_summary": {
            "steps": len(stages),
            "ttft_ms_median": _median(ttfts),
            "tps_median": _median(tpss),
            "tps_values": tpss,
        },
    }


def sources_unverified(data: object) -> int | None:
    """Flag explicit unverified sources; never use absence as proof of accuracy."""
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        return None
    count = 0
    for source in data["sources"]:
        if not isinstance(source, dict):
            count += 1
            continue
        if source.get("content_verified") is False:
            count += 1
        elif source.get("verification_status") in ("unverified", "unknown"):
            count += 1
        elif "unknown" in str(source.get("title", "")).lower():
            count += 1
    return count


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    task = next((t for t in suite["tasks"] if t["id"] == args.task), None)
    if task is None:
        raise ValueError(f"unknown task: {args.task}")
    work = args.work.resolve()
    if not work.is_dir():
        raise ValueError("work directory must already exist")
    if args.arm not in ("baseline", "governance"):
        raise ValueError("arm must be baseline or governance")
    if args.arm == "governance" and not governance_marker(work):
        raise ValueError("governance arm needs bootstrapped project")
    if args.arm == "baseline" and (work / "docs/governance").exists():
        raise ValueError("baseline arm contains governance")
    out = args.out.resolve()
    if out == work or work in out.parents:
        raise ValueError("result directory must not be inside work")
    bundle = source_bundle(work)
    if args.phase == "init" and args.arm == "baseline" and any(
            p.name != "sources" for p in work.iterdir()):
        raise ValueError("baseline work directory must contain sources only")
    if args.phase == "init" and out.exists():
        raise ValueError("output directory already exists; use a fresh run ID")
    if args.phase == "resume" and not (out / "init.json").is_file():
        raise ValueError("resume needs the same run directory with init.json")
    executable = shutil.which(args.opencode)
    if executable is None:
        raise ValueError(f"OpenCode executable not found: {args.opencode}")
    if args.model != suite["model_id_expected"] and not args.allow_model_override:
        raise ValueError("model differs from suite model; explicit --allow-model-override required")
    if args.timeout < 0:
        raise ValueError("timeout must be non-negative; 0 disables the task deadline")
    make_sources_read_only(work)
    policy_config = benchmark_policy(work)
    policy_path = out / 'opencode-policy.json'
    if args.phase == 'resume':
        if not policy_path.is_file() or json.loads(policy_path.read_text(encoding='utf-8')) != policy_config:
            raise ValueError('policy changed after initial phase')
    else:
        out.mkdir(parents=True)
        policy_path.write_text(json.dumps(policy_config, ensure_ascii=False, indent=2), encoding='utf-8')
    env = os.environ.copy()
    env['OPENCODE_CONFIG'] = str(policy_path)
    policy_meta = check_effective_policy(executable, work, env, policy_config)
    expected = ("stage1.md",) if args.phase == "init" else ("report.md", "evidence.json")
    for name in ("stage1.md", "report.md", "evidence.json") if args.phase == "init" else expected:
        if (work / name).exists():
            raise ValueError(f"stale artifact in work directory: {name}")
    if args.phase == "resume":
        previous = json.loads((out / "init.json").read_text(encoding="utf-8-sig"))
        if (previous.get("suite") != suite["suite_id"] or previous.get("task_id") != task["id"] or
                previous.get("arm") != args.arm or previous.get("model_requested") != args.model or
                previous.get("work") != str(work)):
            raise ValueError("resume identity differs from initial run")
        if previous.get("source_bundle") != bundle:
            raise ValueError("source bundle changed after initial phase")
        if previous.get("exit_code") != 0 or not previous.get("stage1_present"):
            raise ValueError("initial phase did not complete")
        if not (work / "stage1.md").is_file():
            raise ValueError("stage1.md missing from work directory")
        if sha(work / "stage1.md") != previous.get("stage1.md_sha256"):
            raise ValueError("stage1.md changed after initial phase")
        session = args.session or previous.get("session_id")
        if not session or (previous.get("session_id") and session != previous["session_id"]):
            raise ValueError("native session ID missing; use --session after verifying OpenCode session")
    else:
        session = None
    as_of = args.as_of or (previous["as_of"] if args.phase == "resume" else datetime.now(timezone.utc).date().isoformat())
    if args.phase == "resume" and as_of != previous["as_of"]:
        raise ValueError("as-of date must match initial phase; pass --as-of explicitly")
    manifest = json.loads((work / 'sources' / 'manifest.json').read_text(encoding='utf-8-sig'))
    if any(e['published_at'] > as_of for e in manifest['sources']):
        raise ValueError('source bundle contains post-cutoff material')
    p = prompt(task, as_of, args.phase)
    # work_from_abs_hint: 模型会把"工作目录"推断成父目录，必须给出绝对路径。
    p += ("\nWRITE TARGETS (absolute): " + (work / "stage1.md").as_posix()
          + " | " + (work / "report.md").as_posix() + " | " + (work / "evidence.json").as_posix() + "\n")
    p += ("\nPrimary sources, extracted text derivatives and provenance are in sources/manifest.json. "
          "Read both frozen sources and verify each claim against them using page, section, or quoted locators. "
          "Treat the entire sources directory as read-only. "
          "For this paired run, use only workspace read, glob, grep, and write/edit tools. "
          "Do not use shell commands or network fetches; report any unavailable source as a limitation.\n")
    prompt_path = work / f".rsi-prompt-{args.phase}.txt"
    if prompt_path.exists():
        raise ValueError("stale prompt in work directory")
    prompt_path.write_text(p, encoding="utf-8")
    (out / f"prompt-{args.phase}.txt").write_text(p, encoding="utf-8")
    # Windows .cmd launchers truncate multiline positional arguments. Attach UTF-8
    # instructions as a file and keep the positional message single-line.
    # A local write smoke test confirms default permissions suffice.
    cmd = [executable, "run", "--pure", "--agent", "build", "--model", args.model, "--format", "json"]
    if session:
        cmd += ["--session", session]
    cmd += ["Read the attached UTF-8 task file in full and execute its instructions.",
            "--file", str(prompt_path)]
    meta = {"suite": suite["suite_id"], "task_id": task["id"], "arm": args.arm,
            "phase": args.phase, "session_id": session,
            "model_requested": args.model, "work": str(work), "started_at": utc(),
            "prompt_sha256": sha(prompt_path),
            "governance_head": (args.governance_head
                                or (detect_governance_head(work) if args.arm == "governance" else "")),
            "opencode_path": executable, "as_of": as_of,
            "timeout_seconds": args.timeout or None, "source_bundle": bundle,
            "permission_policy": policy_meta}
    start = time.monotonic()
    proc = None
    try:
        # OpenCode's `run` reads stdin; without an explicit DEVNULL the child blocks
        # waiting for terminal input under a non-interactive parent and looks like a hang.
        proc = subprocess.Popen(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # 流式读取：communicate() 超时会丢弃已达 stdout，而 step_finish 事件正是
        # token/时延采样的来源。用线程边读边存，超时后仍保留已产生的部分。
        out_chunks: list = []
        err_chunks: list = []

        def _drain(stream, sink):
            try:
                while True:
                    block = stream.read(8192)
                    if not block:
                        break
                    sink.append(block)
            except Exception:  # noqa: BLE001
                pass

        readers = [threading.Thread(target=_drain, args=(proc.stdout, out_chunks), daemon=True),
                   threading.Thread(target=_drain, args=(proc.stderr, err_chunks), daemon=True)]
        for reader in readers:
            reader.start()
        timed_out = False
        try:
            proc.wait(timeout=args.timeout or DEFAULT_RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        for reader in readers:
            reader.join(timeout=15)
        stdout_bytes = b"".join(out_chunks)
        stderr_bytes = b"".join(err_chunks)
        output = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        meta["exit_code"] = 124 if timed_out else proc.returncode
        if timed_out:
            meta["timed_out"] = True
        if args.phase == "init":
            meta["session_id"] = session_from_events(output)
        meta.update(observed_usage(output))
        meta.update(tool_protocol(output, work))
        meta["event_error_types"] = event_errors(output)
        # Raw CLI output can contain credentials or private session text. Keep digests only.
        meta["stdout_sha256"] = hashlib.sha256(stdout_bytes).hexdigest()
        meta["stderr_sha256"] = hashlib.sha256(stderr_bytes).hexdigest()
    except subprocess.TimeoutExpired as exc:
        if proc is not None:
            proc.kill()
            proc.communicate()
        meta["exit_code"] = 124
        meta["timed_out"] = True
        if args.phase == "init" and exc.stdout:
            partial = exc.stdout.decode("utf-8", errors="replace")
            meta["session_id"] = session_from_events(partial)
            meta.update(tool_protocol(partial, work))
            meta["stdout_sha256"] = hashlib.sha256(exc.stdout).hexdigest()
    meta["finished_at"] = utc()
    try:
        meta["source_bundle_unchanged"] = source_bundle(work) == bundle
    except (ValueError, OSError, json.JSONDecodeError):
        meta["source_bundle_unchanged"] = False
    meta["elapsed_seconds"] = round(time.monotonic() - start, 3)
    if args.phase == "resume":
        meta["resume_gap_seconds"] = round((datetime.fromisoformat(meta["started_at"]) -
                                            datetime.fromisoformat(previous["finished_at"])).total_seconds(), 3)
    meta["stage1_present"] = (work / "stage1.md").is_file()
    meta["report_present"] = (work / "report.md").is_file()
    meta["evidence_present"] = (work / "evidence.json").is_file()
    for name in expected:
        source = work / name
        if source.is_file():
            content = source.read_text(encoding="utf-8", errors="replace")
            if any(marker in content.lower() for marker in NO_SECRETS):
                meta["artifact_review_required"] = True
                continue
            meta[name + "_sha256"] = sha(source)
            (out / name).write_text(content, encoding="utf-8")
    present = meta["stage1_present"] if args.phase == "init" else (meta["report_present"] and meta["evidence_present"])
    if meta["exit_code"] == 124:
        meta["status"] = "timeout"
    elif meta["exit_code"] != 0:
        meta["status"] = "cli_error"
    elif not meta["source_bundle_unchanged"]:
        meta["status"] = "source_changed"
    elif meta.get("forbidden_tool_counts") or meta.get("out_of_scope_write_attempts"):
        meta["status"] = "protocol_violation"
    elif not present:
        meta["status"] = "artifact_missing"
    elif meta.get("artifact_review_required"):
        meta["status"] = "artifact_review_required"
    else:
        meta["status"] = "stage_complete"
    (out / f"{args.phase}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0 if meta["status"] == "stage_complete" else 1


def inspect_command(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    rows = []
    for task in suite["tasks"]:
        task_id = task["id"]
        roots = {arm: args.runs / arm / task_id for arm in ("baseline", "governance")}
        run_ids = set()
        for root in roots.values():
            if root.is_dir():
                run_ids.update(p.name for p in root.iterdir() if p.is_dir() and
                               (p / "init.json").is_file())
        if args.run_id:
            run_ids = {args.run_id}
        for run_id in sorted(run_ids):
            pair = {}
            for arm in ("baseline", "governance"):
                folder = roots[arm] / run_id
                init = folder / "init.json"
                resume = folder / "resume.json"
                report = folder / "report.md"
                evidence = folder / "evidence.json"
                row = {"arm": arm, "task_id": task_id, "run_id": run_id,
                       "init": init.is_file(), "resume": resume.is_file(),
                       "report": report.is_file(), "evidence": evidence.is_file()}
                if init.is_file() and resume.is_file():
                    a = json.loads(init.read_text(encoding="utf-8-sig"))
                    b = json.loads(resume.read_text(encoding="utf-8-sig"))
                    row["identity_ok"] = all(a.get(k) == b.get(k) for k in
                        ("suite", "task_id", "arm", "model_requested", "work", "as_of", "source_bundle"))
                    row["session_continuity"] = bool(a.get("session_id") and a.get("session_id") == b.get("session_id"))
                    row["execution_ok"] = (a.get("status") == "stage_complete" and
                                           b.get("status") == "stage_complete" and
                                           a.get("source_bundle_unchanged") is True and
                                           b.get("source_bundle_unchanged") is True and
                                           not a.get("forbidden_tool_counts") and
                                           not b.get("forbidden_tool_counts"))
                    row["policy_equal"] = (a.get("permission_policy") == b.get("permission_policy") and
                                          a.get("permission_policy", {}).get("preflight") == "passed")
                    row["permission_policy"] = a.get("permission_policy")
                    row["source_bundle"] = a.get("source_bundle")
                    row["as_of"] = a.get("as_of")
                    row["model_requested"] = a.get("model_requested")
                if report.is_file():
                    report_text = report.read_text(encoding="utf-8", errors="replace")
                    row["missing_sections"] = [s for s in task["required_sections"] if s not in report_text]
                if evidence.is_file():
                    try:
                        data = json.loads(evidence.read_text(encoding="utf-8-sig"))
                        row["evidence_json_valid"] = isinstance(data, (dict, list))
                        row["explicitly_unverified_sources"] = sources_unverified(data)
                    except json.JSONDecodeError:
                        row["evidence_json_valid"] = False
                rows.append(row)
                pair[arm] = row
            left, right = pair["baseline"], pair["governance"]
            equal = bool(left.get("source_bundle") and
                         left["source_bundle"] == right.get("source_bundle") and
                         left.get("as_of") == right.get("as_of") and
                         left.get("model_requested") == right.get("model_requested") and
                         left.get("policy_equal") and right.get("policy_equal") and
                         left.get("permission_policy") == right.get("permission_policy"))
            left["paired_inputs_equal"] = right["paired_inputs_equal"] = equal
    complete = bool(args.run_id) and bool(rows) and len({r["task_id"] for r in rows if r.get("paired_inputs_equal")}) == len(suite["tasks"]) and all(
                   r["init"] and r["resume"] and r["report"] and r["evidence"] and
                   r.get("identity_ok") and r.get("session_continuity") and r.get("execution_ok") and
                   r.get("paired_inputs_equal") and not r.get("missing_sections") and
                   r.get("evidence_json_valid") for r in rows)
    print(json.dumps({"suite": suite["suite_id"], "paired_tasks": len(suite["tasks"]),
                      "artifacts_complete": complete, "quality_review_required": True,
                      "rows": rows}, ensure_ascii=False, indent=2))
    return 0 if complete else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--task", required=True)
    run.add_argument("--phase", required=True, choices=("init", "resume"))
    run.add_argument("--session", default="")
    run.add_argument("--arm", required=True, choices=("baseline", "governance"))
    run.add_argument("--work", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--model", default="<推理端点>/<模型>")
    run.add_argument("--opencode", default="opencode-lab")
    run.add_argument("--governance-head", default="")
    run.add_argument("--as-of", default="")
    run.add_argument("--timeout", type=int, default=0,
                     help="task deadline in seconds; 0 (default) waits for natural completion")
    run.add_argument("--allow-model-override", action="store_true")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--runs", type=Path, required=True)
    inspect.add_argument("--run-id", default="", help="shared result-folder name for both arms")
    gate = sub.add_parser('preflight-pair')
    gate.add_argument('--baseline', required=True, type=Path)
    gate.add_argument('--governance', required=True, type=Path)
    gate.add_argument('--base-config', required=True, type=Path)
    gate.add_argument('--opencode', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'run':
            return run_command(args)
        if args.command == 'inspect':
            return inspect_command(args)
        executable = shutil.which(args.opencode)
        if not executable:
            raise ValueError(f'OpenCode executable not found: {args.opencode}')
        print(json.dumps(preflight_pair(executable, args.base_config, args.baseline,
                                        args.governance), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
