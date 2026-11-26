#!/usr/bin/env bash
#
# bootstrap-macos.sh - macOS 入口脚本（逻辑复用 bootstrap.sh）
#
# 用法：
#   ./scripts/bootstrap-macos.sh [目标目录]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/bootstrap.sh" "$@"
