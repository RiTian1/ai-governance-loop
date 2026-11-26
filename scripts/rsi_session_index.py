#!/usr/bin/env python3
"""Index CLI session summaries without copying or changing native conversations."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SLUG = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
CLI = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
SECRET = re.compile(r"(?i)(password|passwd|api[_-]?key|secret|token)\s*[:=]\s*[^\s,;]+|://[^/\s:@]+:[^@\s/]+@")
MAX_BYTES = 16 * 1024


def safe_text(value: str, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be 1-{maximum} characters")
    if SECRET.search(value) or re.search(r"(?i)(bearer\s+[A-Za-z0-9._-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,})", value):
        raise ValueError(f"{name} may contain a credential; use a redacted reference")
    return value.strip()


def source_locator(value: str, session: str) -> str:
    locator = safe_text(value, "locator", 1024)
    if not (locator == session or locator.startswith(("/", "./", "../", "~", "file:", "codex:", "cursor:", "ssh:"))
            or re.match(r"^[A-Za-z]:[\\/]", locator)):
        raise ValueError("locator must be a native session ID or a path/URI; never paste transcript content")
    return locator


def slug(value: str, name: str, pattern: re.Pattern = SLUG) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase slug")
    return value


def read_state(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or not isinstance(value.get("state", value), dict):
        raise ValueError("input must be an RSI state JSON object")
    return value.get("state", value)


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".rsi-index-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def index_path(root: Path, project: str, cli: str, host: str, session: str) -> Path:
    name = hashlib.sha256(f"{cli}\0{host}\0{session}".encode("utf-8")).hexdigest()[:24]
    return root / "rsi" / "sessions" / project / f"{cli}-{name}.json"


def entries(root: Path, project: str | None = None):
    base = root / "rsi" / "sessions"
    if project:
        files = (base / project).glob("*.json")
    else:
        files = base.glob("*/*.json")
    for path in sorted(files):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("entry must be an object")
            if record.get("authority") == "cli-session" and record.get("derived") is True:
                yield path, record
        except (OSError, ValueError) as exc:
            raise ValueError(f"unreadable RSI index {path}: {exc}") from exc


def governance_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).resolve()
    else:
        project = Path.cwd().resolve()
        manifest = project / "project-governance.yaml"
        declared = "."
        if manifest.is_file():
            text = manifest.read_text(encoding="utf-8-sig")
            match = re.search(r"(?m)^governance_root:\s*['\"]?([^\s'\"#]+)", text)
            if match:
                declared = match.group(1)
        root = (project / declared).resolve()
        if not root.is_relative_to(project):
            raise ValueError("governance_root escapes project root")
    if not root.is_dir() or not (root / "rsi" / "_index.yaml").is_file():
        raise ValueError("RSI protocol missing; pass --governance-root or bootstrap the project")
    return root


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("add", "search", "locate"))
    p.add_argument("--governance-root", default=None,
                   help="defaults to project-governance.yaml governance_root")
    p.add_argument("--input", help="short RSI state JSON, not a transcript")
    p.add_argument("--project-id")
    p.add_argument("--task-id")
    p.add_argument("--cli", help="CLI name, e.g. codex or cursor")
    p.add_argument("--host", help="machine identifier")
    p.add_argument("--session-id", help="native CLI session ID")
    p.add_argument("--locator", help="native resume ID, path or verified URI")
    p.add_argument("--query", help="text to find in summary, tags and anchors")
    p.add_argument("--source-file", help="optional readable native session file; hash only")
    args = p.parse_args()
    try:
        root = governance_root(args.governance_root)
        project = slug(args.project_id, "project_id") if args.project_id else None
        task = slug(args.task_id, "task_id") if args.task_id else None
        if args.command == "add":
            for key in ("input", "project_id", "task_id", "cli", "host", "session_id", "locator"):
                if not getattr(args, key):
                    p.error(f"add requires --{key.replace('_', '-')}")
            cli = slug(args.cli, "cli", CLI)
            host = safe_text(args.host, "host", 128)
            session = safe_text(args.session_id, "session_id", 256)
            locator = source_locator(args.locator, session)
            source = read_state(Path(args.input))
            summary = safe_text(source.get("summary"), "summary", 1200)
            keywords = source.get("keywords", [])
            if not isinstance(keywords, list) or len(keywords) > 12:
                raise ValueError("keywords must have at most 12 entries")
            for word in keywords:
                safe_text(word, "keyword", 64)
            anchors = source.get("source_anchors", [])
            refs = source.get("artifact_refs", [])
            for field, values in (("source_anchors", anchors), ("artifact_refs", refs)):
                if not isinstance(values, list) or len(values) > 20:
                    raise ValueError(f"{field} must have at most 20 entries")
                for value in values:
                    safe_text(value, field, 256)
            digest = None
            access = "unverified"
            if args.source_file:
                native = Path(args.source_file).resolve(strict=True)
                if not native.is_file():
                    raise ValueError("source file is not a regular file")
                sha = hashlib.sha256()
                with native.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        sha.update(block)
                digest = sha.hexdigest()
                access = "verified-on-source-host"
            record = {
                "schema_version": 1, "authority": "cli-session", "derived": True,
                "project_id": project, "task_id": task, "cli": cli, "host": host,
                "session_id": session, "locator": locator,
                "source_access": access, "source_sha256": digest,
                "summary": summary, "keywords": keywords,
                "source_anchors": anchors, "artifact_refs": refs,
                "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            if len(json.dumps(record, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
                raise ValueError("index entry exceeds 16 KiB")
            path = index_path(root, project, cli, host, session)
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                if (old.get("cli"), old.get("host"), old.get("session_id")) != (cli, host, session):
                    raise ValueError("index hash collision or source identity changed")
                if old.get("source_sha256") and digest and old["source_sha256"] != digest:
                    raise ValueError("native session hash changed; inspect source before replacing index")
                if old.get("source_sha256") and not digest:
                    raise ValueError("cannot downgrade verified source to unverified index")
            atomic_json(path, record)
            print(path.relative_to(root).as_posix())
            return 0
        if args.command == "locate":
            if not args.session_id:
                p.error("locate requires --session-id")
            matches = [(path, row) for path, row in entries(root, project) if row.get("session_id") == args.session_id
                       and (not args.cli or row.get("cli") == args.cli)
                       and (not args.host or row.get("host") == args.host)]
        else:
            if not args.query and not task and not project:
                p.error("search requires --query, --task-id or --project-id")
            needle = (args.query or "").casefold()
            matches = [(path, row) for path, row in entries(root, project)
                       if (not task or row.get("task_id") == task)
                       and (not needle or needle in json.dumps([row.get("summary"), row.get("keywords"), row.get("source_anchors")], ensure_ascii=False).casefold())]
        for path, row in matches:
            print(json.dumps({"index": path.relative_to(root).as_posix(), "project_id": row["project_id"],
                              "task_id": row["task_id"], "cli": row["cli"], "host": row["host"],
                              "session_id": row["session_id"], "locator": row["locator"],
                              "summary": row["summary"], "source_access": row["source_access"],
                              "source_anchors": row["source_anchors"]}, ensure_ascii=False))
        return 0 if matches else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"RSI index error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
