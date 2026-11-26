#!/usr/bin/env python3
"""Freeze identical P02 primary-source bundles for paired runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from prepare_rsi_p01_sources import text_derivative


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", required=True, type=Path)
    p.add_argument("--governance", required=True, type=Path)
    p.add_argument("--ama-bundle", required=True, type=Path)
    p.add_argument("--paper-file", type=Path, help="pre-downloaded verified v1 PDF")
    args = p.parse_args()
    targets = (args.baseline.resolve(), args.governance.resolve())
    for target in targets:
        if not target.is_dir() or (target / "sources").exists():
            raise ValueError(f"target missing or sources already exist: {target}")

    url = "https://arxiv.org/pdf/2608.15008v1"
    if args.paper_file:
        paper = args.paper_file.resolve().read_bytes()
        resolved_url = url
    else:
        res = requests.get(url, headers={"User-Agent": "rsi-benchmark-source-freeze/1.0"}, timeout=90)
        res.raise_for_status()
        paper = res.content
        resolved_url = res.url
    if not paper.startswith(b"%PDF") or len(paper) < 1000:
        raise ValueError("unexpected paper response")
    old_dir = args.ama_bundle.resolve()
    manifest = json.loads((old_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    old = next(x for x in manifest["sources"] if x["file"] == "ama-bench-2602.22769.pdf")
    ama = (old_dir / old["file"]).read_bytes()
    if not ama.startswith(b"%PDF") or sha(ama) != old["sha256"]:
        raise ValueError("AMA-Bench input failed checksum")

    now = datetime.now(timezone.utc).isoformat()
    name = "harness-memory-2608.15008v1.pdf"
    payloads = {name: paper, old["file"]: ama}
    entries = [
        {"file": name, "url": url, "resolved_url": resolved_url,
         "published_at": "2026-08-15", "downloaded_at": now,
         "sha256": sha(paper), "bytes": len(paper), "version": "v1", "kind": "primary"},
        {"file": old["file"], "url": old["url"],
         "published_at": "2026-05-27", "first_submitted_at": "2026-02-26",
         "downloaded_at": old["downloaded_at"], "sha256": sha(ama),
         "bytes": len(ama), "version": "v4", "kind": "primary"},
    ]
    for primary in list(entries):
        filename = primary["file"]
        txt = filename.rsplit(".", 1)[0] + ".txt"
        extracted = text_derivative(filename, payloads[filename])
        if len(extracted) < 1000:
            raise ValueError(f"text extraction failed: {filename}")
        payloads[txt] = extracted
        entries.append({"file": txt, "url": primary["url"],
                        "published_at": primary["published_at"],
                        "downloaded_at": primary["downloaded_at"],
                        "sha256": sha(extracted), "bytes": len(extracted),
                        "kind": "derivative", "derived_from": filename,
                        "extractor": "pypdf"})
    encoded = (json.dumps({"sources": entries}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for target in targets:
        folder = target / "sources"
        folder.mkdir()
        for filename, data in payloads.items():
            (folder / filename).write_bytes(data)
        (folder / "manifest.json").write_bytes(encoded)
    print(json.dumps({"manifest_sha256": sha(encoded),
                      "files": {k: sha(v) for k, v in payloads.items()}}, indent=2))


if __name__ == "__main__":
    main()
