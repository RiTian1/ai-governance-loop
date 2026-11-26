#!/usr/bin/env python3
"""Portable checkpoint for long-running agent tasks. Standard library only."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TASK_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
REQUIRED = ("objective", "next_action", "completed", "decisions", "evidence", "blockers", "artifact_refs")
LISTS = REQUIRED[2:]
SECRET_RE = re.compile(r"(?i)(password|passwd|api[_-]?key|secret|token)\s*[:=]\s*[^\s,;]+")
SECRET_KEYS = {"password", "passwd", "api_key", "apikey", "secret", "token"}


def contains_secret(value: object) -> bool:
    if isinstance(value, dict):
        return any((str(key).lower().replace("-", "_") in SECRET_KEYS and bool(item))
                   or contains_secret(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_secret(item) for item in value)
    return isinstance(value, str) and bool(SECRET_RE.search(value))


def path_in(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("path must be relative to project root")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("path escapes project root")
    return result


def git(root: Path, *args: str) -> bytes | None:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    except FileNotFoundError:
        return None
    return result.stdout if result.returncode == 0 else None


def workspace(root: Path, state_dir: Path | None = None) -> dict:
    if git(root, "rev-parse", "--is-inside-work-tree") is None:
        return {"head": None, "sha256": None}
    head = git(root, "rev-parse", "HEAD")
    # Binary diff covers tracked files, including staged changes and deletes.
    diff = git(root, "diff", "--binary", "HEAD", "--")
    if diff is None:
        diff = git(root, "diff", "--binary", "--") or b""
        diff += git(root, "diff", "--cached", "--binary", "--") or b""
    digest = hashlib.sha256(diff)
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z") or b""
    for raw in untracked.split(b"\0"):
        if raw:
            relative = raw.decode("utf-8", errors="surrogateescape")
            file = path_in(root, relative)
            if state_dir and file.is_relative_to(state_dir.resolve()):
                continue
            if file.is_file() and not file.is_symlink():
                digest.update(raw)
                with file.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
    return {"head": head.decode().strip() if head else None, "sha256": digest.hexdigest()}


def validate(root: Path, state: object) -> dict:
    if not isinstance(state, dict):
        raise ValueError("state must be a JSON object")
    for key in REQUIRED:
        if key not in state:
            raise ValueError(f"missing {key}")
    for key in REQUIRED[:2]:
        if not isinstance(state[key], str) or not state[key].strip():
            raise ValueError(f"{key} must be nonempty text")
    for key in LISTS:
        if not isinstance(state[key], list) or any(not isinstance(x, str) for x in state[key]):
            raise ValueError(f"{key} must be a list of strings")
    if "summary" in state and (not isinstance(state["summary"], str) or not state["summary"].strip()):
        raise ValueError("summary must be nonempty text when supplied")
    if "source_anchors" in state and (not isinstance(state["source_anchors"], list)
                                      or any(not isinstance(x, str) for x in state["source_anchors"])):
        raise ValueError("source_anchors must be a list of strings")
    if "keywords" in state and (not isinstance(state["keywords"], list)
                               or any(not isinstance(x, str) for x in state["keywords"])):
        raise ValueError("keywords must be a list of strings")
    for ref in state["artifact_refs"]:
        path_in(root, ref)
    data = json.dumps(state, ensure_ascii=False).encode("utf-8")
    if len(data) > 65536:
        raise ValueError("checkpoint exceeds 64 KiB; reference artifacts instead")
    if contains_secret(state):
        raise ValueError("possible inline credential; use a vault reference")
    return state


def artifact_hashes(root: Path, refs: list[str]) -> dict[str, str | None]:
    hashes = {}
    for ref in refs:
        file = path_in(root, ref)
        if not file.is_file():
            hashes[ref] = None
            continue
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        hashes[ref] = digest.hexdigest()
    return hashes


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_latest(latest: Path, events: Path, task: str) -> tuple[dict, bool]:
    try:
        record = json.loads(latest.read_text(encoding="utf-8"))
        if record.get("task_id") == task and record.get("schema_version") == 1:
            return record, False
    except (OSError, ValueError):
        pass
    valid = None
    with events.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # A torn final append must not erase earlier valid events.
            if entry.get("task_id") == task and entry.get("schema_version") == 1:
                valid = entry
    if valid is None:
        raise ValueError("no valid task snapshot or event found")
    return valid, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("save", "resume", "verify"))
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--input")
    parser.add_argument("--state-dir", default="_logs/rsi-tasks",
                        help="local default or an explicit shared NAS directory")
    args = parser.parse_args()
    if not TASK_RE.fullmatch(args.task):
        parser.error("--task requires a lowercase slug of 2-64 characters")
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        parser.error("project root does not exist")
    try:
        state_dir = Path(args.state_dir).resolve() if Path(args.state_dir).is_absolute() else path_in(root, args.state_dir)
        latest = state_dir / (args.task + ".json")
        events = state_dir / (args.task + ".jsonl")
        if args.command == "save":
            if not args.input:
                parser.error("save requires --input")
            source = Path(args.input).resolve()
            if source == latest or source.is_relative_to(state_dir):
                raise ValueError("input must be outside checkpoint state directory")
            state = validate(root, json.loads(source.read_text(encoding="utf-8-sig")))
            record = {"schema_version": 1, "task_id": args.task,
                      "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "workspace": workspace(root, state_dir),
                      "artifact_hashes": artifact_hashes(root, state["artifact_refs"]),
                      "state": state}
            state_dir.mkdir(parents=True, exist_ok=True)
            with events.open("a", encoding="utf-8") as out:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())
            atomic_write(latest, record)
            print("saved", latest)
            return 0
        record, replayed = load_latest(latest, events, args.task)
        if replayed:
            print("RECOVERED: latest snapshot unavailable; using last valid event", file=sys.stderr)
        state = validate(root, record["state"])
        issues = []
        now = workspace(root, state_dir)
        for key in ("head", "sha256"):
            if record.get("workspace", {}).get(key) != now[key]:
                issues.append("workspace " + key + " changed")
        for ref in state["artifact_refs"]:
            if not path_in(root, ref).exists():
                issues.append("missing artifact: " + ref)
        current_hashes = artifact_hashes(root, state["artifact_refs"])
        for ref, digest in current_hashes.items():
            if record.get("artifact_hashes", {}).get(ref) != digest:
                issues.append("artifact changed: " + ref)
        if now["sha256"] is None and not state["artifact_refs"]:
            issues.append("no Git repository or artifact references; state cannot be verified")
        if args.command == "resume":
            print(json.dumps(record, ensure_ascii=False, indent=2))
        for issue in issues:
            print("DRIFT:", issue, file=sys.stderr)
        if not issues:
            print("checkpoint verified; use next_action", file=sys.stderr)
        return 1 if issues else 0
    except (OSError, ValueError, KeyError) as exc:
        print("checkpoint error:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
