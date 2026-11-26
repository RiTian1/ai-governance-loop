#!/usr/bin/env bash
#
# bootstrap-ide-tools.sh — Install OpenSpec + optional BMAD adapters for AI IDEs/CLIs
#
# Usage:
#   ./scripts/bootstrap-ide-tools.sh <project_root> [--tools LIST|all] [--skip-openspec] [--enable-bmad] [--skip-bmad]
#
# Tool aliases (governance names → upstream):
#   claude → openspec: claude, bmad: claude-code
#   cursor, codex, opencode, qwen, trae — same IDs on both sides
#

set -euo pipefail

OPENSPEC_PKG="${OPENSPEC_PKG:-@fission-ai/openspec@1.5.0}"
BMAD_PKG="${BMAD_PKG:-bmad-method@6.10.0}"
DEFAULT_TOOLS="claude,cursor,codex,opencode,qwen,trae"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${YELLOW}i${NC} $*"; }
ok() { echo -e "${GREEN}OK${NC} $*"; }
die() { echo -e "${RED}ERR${NC} $*" >&2; exit 1; }

usage() {
    cat <<'EOF'
Usage:
  ./scripts/bootstrap-ide-tools.sh <project_root> [options]

Options:
  --tools LIST|all     Comma-separated IDE tools (default: claude,cursor,codex,opencode,qwen,trae)
  --skip-openspec      Do not run openspec init
  --enable-bmad        Run bmad-method install (overwrites _bmad from upstream; use only when enabling BMAD)
  --skip-bmad          Skip BMAD install even if --enable-bmad was set elsewhere

Supported governance tool IDs:
  claude, cursor, codex, opencode, qwen, trae
EOF
}

normalize_tools_csv() {
    local raw="$1"
    raw="$(echo "$raw" | tr '[:upper:]' '[:lower:]' | tr -d ' ')"
    if [ "$raw" = "all" ]; then
        echo "$DEFAULT_TOOLS"
        return
    fi
    echo "$raw" | tr ',' '\n' | sed 's/^claude-code$/claude/; s/^claude_code$/claude/' | sort -u | paste -sd, -
}

to_openspec_tools() {
    local csv="$1"
    echo "$csv"
}

to_bmad_tools() {
    local csv="$1"
    local out=""
    local t
    IFS=',' read -ra parts <<< "$csv"
    for t in "${parts[@]}"; do
        t="$(echo "$t" | xargs)"
        [ -n "$t" ] || continue
        case "$t" in
            claude) t="claude-code" ;;
        esac
        if [ -n "$out" ]; then out="${out},${t}"; else out="$t"; fi
    done
    echo "$out"
}

PROJECT_ROOT=""
TOOLS_CSV="$DEFAULT_TOOLS"
SKIP_OPENSPEC=false
ENABLE_BMAD=false
SKIP_BMAD=false

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --tools) shift; TOOLS_CSV="${1:-}"; [ -n "$TOOLS_CSV" ] || die "--tools requires a value" ;;
        --skip-openspec) SKIP_OPENSPEC=true ;;
        --enable-bmad) ENABLE_BMAD=true ;;
        --skip-bmad) SKIP_BMAD=true ;;
        --*) die "Unknown option: $1" ;;
        *)
            if [ -z "$PROJECT_ROOT" ]; then
                PROJECT_ROOT="$1"
            else
                die "Unexpected argument: $1"
            fi
            ;;
    esac
    shift
done

[ -n "$PROJECT_ROOT" ] || { usage; die "project_root is required"; }
[ -d "$PROJECT_ROOT" ] || die "Not a directory: $PROJECT_ROOT"

TOOLS_CSV="$(normalize_tools_csv "$TOOLS_CSV")"
OPENSPEC_TOOLS="$(to_openspec_tools "$TOOLS_CSV")"
BMAD_TOOLS="$(to_bmad_tools "$TOOLS_CSV")"

info "Project: $PROJECT_ROOT"
info "Tools: $TOOLS_CSV"

if [ "$SKIP_OPENSPEC" = false ]; then
    if ! command -v npx >/dev/null 2>&1; then
        die "npx not found. Install Node.js 18+ or pass --skip-openspec to bootstrap."
    fi
    info "OpenSpec init ($OPENSPEC_PKG) tools=$OPENSPEC_TOOLS"
    (
        cd "$PROJECT_ROOT"
        npx --yes "$OPENSPEC_PKG" init . --tools "$OPENSPEC_TOOLS" --force --profile custom
    )
    ok "OpenSpec adapters installed (skills/commands per tool)"
else
    info "Skipped OpenSpec install"
fi

if [ "$ENABLE_BMAD" = true ] && [ "$SKIP_BMAD" = false ]; then
    if ! command -v npx >/dev/null 2>&1; then
        die "npx not found (required for BMAD install)"
    fi
    # rev-2026-05-26-bootstrap-script-overhaul B2 fix:
    # bootstrap.sh Step 3 已从母版仓复制 _bmad/ 到项目；BMAD CLI 检测到 _bmad/ 存在
    # 会拒绝 --action install（仅接受 update / quick-update）。auto-detect 兼顾首次干净接入。
    if [ -d "$PROJECT_ROOT/_bmad" ]; then
        BMAD_ACTION="update"
    else
        BMAD_ACTION="install"
    fi
    # P0 (i18n): BMAD v6 官方支持 --communication-language / --document-output-language
    # 让 Agent 对话 + 写出的 PRD / 计划 / 文档默认走中文。
    info "BMAD install ($BMAD_PKG) tools=$BMAD_TOOLS action=$BMAD_ACTION lang=Chinese"
    (
        cd "$PROJECT_ROOT"
        npx --yes "$BMAD_PKG" install --yes --tools "$BMAD_TOOLS" --modules core,bmm \
            --directory . --action "$BMAD_ACTION" \
            --communication-language Chinese --document-output-language Chinese
    )
    ok "BMAD skill adapters installed (zh-CN)"
elif [ "$ENABLE_BMAD" = true ]; then
    info "Skipped BMAD install (--skip-bmad)"
else
    info "BMAD install skipped (frameworks.bmad.enabled defaults to false; use --enable-bmad to run upstream installer)"
fi

ok "IDE tool bootstrap finished"
