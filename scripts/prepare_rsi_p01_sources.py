#!/usr/bin/env python3
"""Freeze identical primary-source payloads for a paired P01 benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests
from pypdf import PdfReader

SOURCES = (
    ("anthropic-harness.html",
     "https://www.anthropic.com/research/effective-harnesses-for-long-running-agents",
     "2025-11-26", b"Effective harnesses for long-running agents"),
    ("ama-bench-2602.22769v4.html", "https://arxiv.org/html/2602.22769v4",
     "2026-05-27", b"AMA-Bench: Evaluating Long-Horizon Memory"),
)


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "svg"):
            self.hidden += 1
        if tag in ("h1", "h2", "h3", "p", "li", "tr", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "svg") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def text_derivative(name: str, payload: bytes) -> bytes:
    if name.endswith(".pdf"):
        from io import BytesIO
        pages = PdfReader(BytesIO(payload)).pages
        text = "\n".join(f"\n[PDF page {i}]\n" + (page.extract_text() or "")
                         for i, page in enumerate(pages, 1))
    else:
        parser = VisibleText()
        parser.feed(payload.decode("utf-8", errors="replace"))
        text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--governance", required=True, type=Path)
    parser.add_argument("--input-bundle", type=Path,
                        help="reuse a verified frozen bundle when source sites are unreachable")
    args = parser.parse_args()
    destinations = (args.baseline.resolve(), args.governance.resolve())
    for work in destinations:
        if not work.is_dir() or (work / "sources").exists():
            raise ValueError(f"work directory missing or sources already exist: {work}")
    entries = []
    payloads = {}
    if args.input_bundle:
        source_dir = args.input_bundle.resolve()
        old = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8-sig"))
        for item in old["sources"]:
            if item.get("kind", "primary") != "primary":
                continue
            name = item["file"]
            content = (source_dir / name).read_bytes()
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError(f"input bundle checksum mismatch: {name}")
            payloads[name] = content
            if name == "ama-bench-2602.22769.pdf":
                item = dict(item, published_at="2026-05-27",
                            first_submitted_at="2026-02-26", version="v4")
            entries.append(dict(item, kind="primary"))
    else:
        for name, url, published_at, marker in SOURCES:
            response = requests.get(url, headers={"User-Agent": "rsi-benchmark-source-freeze/1.0"},
                                    timeout=90)
            response.raise_for_status()
            content = response.content
            resolved = response.url
            if marker not in content or len(content) < 1000:
                raise ValueError(f"source content did not match expectation: {url}")
            payloads[name] = content
            entries.append({"file": name, "url": url, "resolved_url": resolved,
                            "published_at": published_at,
                            "downloaded_at": datetime.now(timezone.utc).isoformat(),
                            "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
                            "kind": "primary"})
    if len(entries) < 2:
        raise ValueError("bundle needs two primary sources")
    for item in list(entries):
        name = item["file"]
        text_name = name.rsplit(".", 1)[0] + ".txt"
        content = text_derivative(name, payloads[name])
        if len(content) < 1000:
            raise ValueError(f"empty extracted source: {name}")
        payloads[text_name] = content
        entries.append({"file": text_name, "url": item["url"],
                        "published_at": item["published_at"],
                        "downloaded_at": item["downloaded_at"],
                        "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
                        "kind": "derivative", "derived_from": name,
                        "extractor": "pypdf or Python HTMLParser"})
    manifest = (json.dumps({"sources": entries}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for work in destinations:
        folder = work / "sources"
        folder.mkdir()
        for name, content in payloads.items():
            (folder / name).write_bytes(content)
        (folder / "manifest.json").write_bytes(manifest)
    print(json.dumps({"manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                      "sources": entries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
