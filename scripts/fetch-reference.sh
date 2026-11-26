#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REFERENCE_ROOT="$PROJECT_ROOT/_reference"
TARGET_DIR="$REFERENCE_ROOT/agency-agents-main"
# 上游已迁移：The-Agency-Agents/agency-agents -> msitarzewski/agency-agents（2026-07 核实）
REPO_URL="${AGENCY_AGENTS_REPO:-https://github.com/msitarzewski/agency-agents.git}"

mkdir -p "$REFERENCE_ROOT"

if [ -d "$TARGET_DIR/.git" ]; then
    echo "Updating existing reference bundle: $TARGET_DIR"
    git -C "$TARGET_DIR" pull --ff-only
elif [ -d "$TARGET_DIR" ]; then
    echo "Target exists but is not a git repository: $TARGET_DIR" >&2
    echo "Please remove it manually, then rerun this script." >&2
    exit 1
else
    echo "Cloning reference bundle into: $TARGET_DIR"
    git clone --depth 1 "$REPO_URL" "$TARGET_DIR"
fi

echo "Done. Reference bundle is available at: $TARGET_DIR"