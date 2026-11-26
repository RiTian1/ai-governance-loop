#!/usr/bin/env bash
#
# bootstrap.sh - Copy governance mother repo into a target project
#
# Usage:
#   ./scripts/bootstrap.sh [target_dir] [--create-dir-from-name]
#   ./scripts/bootstrap.sh --tools claude,cursor,codex,opencode,qwen,trae
#   ./scripts/bootstrap.sh --tools all --skip-ide-tools
#   ./scripts/bootstrap.sh --enable-bmad
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

info() { echo -e "${BLUE}i${NC} $*"; }
success() { echo -e "${GREEN}OK${NC} $*"; }
warn() { echo -e "${YELLOW}WARN${NC} $*"; }
die() { echo -e "${RED}ERR${NC} $*" >&2; exit 1; }

header() {
    echo ""
    echo -e "${BOLD}${CYAN}========================================${NC}"
    echo -e "${BOLD}  $*${NC}"
    echo -e "${BOLD}${CYAN}========================================${NC}"
    echo ""
}

copy_dir_merge() {
    local src="$1"
    local dst="$2"
    [ -d "$src" ] || return 0
    mkdir -p "$dst"
    cp -r "$src"/. "$dst"/
}

has_standard_code_layout() {
    local root="$1"
    local markers=(
        ".git" "src" "app" "lib" "cmd" "pkg" "internal" "server" "client"
        "api" "services" "backend" "frontend" "test" "tests"
        "package.json" "pnpm-workspace.yaml" "pyproject.toml" "requirements.txt"
        "go.mod" "Cargo.toml" "pom.xml" "build.gradle" "build.gradle.kts"
        "Gemfile" "composer.json" "CMakeLists.txt" "Makefile"
    )
    local marker
    for marker in "${markers[@]}"; do
        if [ -e "$root/$marker" ]; then
            return 0
        fi
    done
    return 1
}

to_dir_name() {
    local text="$1"
    text="$(echo "$text" | tr '[:upper:]' '[:lower:]')"
    text="$(echo "$text" | sed 's/[^a-z0-9._-]/-/g')"
    text="$(echo "$text" | sed 's/-\+/-/g; s/^-//; s/-$//')"
    [ -n "$text" ] || text="my-project"
    echo "$text"
}

# rev-2026-05-26-bootstrap-script-overhaul D2: simple {{VAR}} template renderer (Linux/macOS).
# Usage: render_template <template_path> <out_path>
# Variables come from env vars: TPL_PROJECT_NAME, TPL_GOVERNANCE_ROOT, etc.
render_template() {
    local tpl="$1"
    local out="$2"
    [ -f "$tpl" ] || { warn "Template not found: $tpl"; return 1; }
    # Use a perl one-liner for robust {{VAR}} replacement with multi-line content
    # All variables prefixed with TPL_<NAME>; placeholder is {{<NAME>}}.
    perl -pe '
        s/\{\{PROJECT_NAME\}\}/$ENV{TPL_PROJECT_NAME}/g;
        s/\{\{PROJECT_DESCRIPTION\}\}/$ENV{TPL_PROJECT_DESCRIPTION}/g;
        s/\{\{PROJECT_ID\}\}/$ENV{TPL_PROJECT_ID}/g;
        s/\{\{PROFILE\}\}/$ENV{TPL_PROFILE}/g;
        s/\{\{GOVERNANCE_LAYOUT\}\}/$ENV{TPL_GOVERNANCE_LAYOUT}/g;
        s/\{\{GOVERNANCE_ROOT\}\}/$ENV{TPL_GOVERNANCE_ROOT}/g;
        s/\{\{MASTER_REPO_COMMIT\}\}/$ENV{TPL_MASTER_REPO_COMMIT}/g;
        s/\{\{MASTER_REPO_BRANCH\}\}/$ENV{TPL_MASTER_REPO_BRANCH}/g;
        s/\{\{ADOPTED_AT\}\}/$ENV{TPL_ADOPTED_AT}/g;
    ' "$tpl" > "$out"
}

rewrite_governance_index_layout() {
    local index_path="$1"
    local layout="$2"
    [ -f "$index_path" ] || return 0
    python3 - "$index_path" "$layout" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
layout = sys.argv[2]
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
changed = False
for i, line in enumerate(lines):
    if line.startswith("governance_layout:"):
        newline = f"governance_layout: {layout}\n"
        if line.endswith("\r\n"):
            newline = f"governance_layout: {layout}\r\n"
        lines[i] = newline
        changed = True
        break
if not changed:
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("schema_version:"):
            insert_at = i + 1
            break
    lines.insert(insert_at, f"governance_layout: {layout}\n")
path.write_text("".join(lines), encoding="utf-8")
PY
}

# rev-2026-05-26-bootstrap-script-overhaul D2.7: detect master repo commit + branch.
get_master_repo_meta() {
    local fw_dir="$1"
    MASTER_REPO_COMMIT="unknown"
    MASTER_REPO_BRANCH="unknown"
    if command -v git >/dev/null 2>&1; then
        local c b
        c="$(cd "$fw_dir" && git rev-parse --short HEAD 2>/dev/null || true)"
        b="$(cd "$fw_dir" && git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
        [ -n "$c" ] && MASTER_REPO_COMMIT="$c"
        [ -n "$b" ] && MASTER_REPO_BRANCH="$b"
    fi
    # set -e 防护：框架目录无 .git 时 b 为空，上面的 && 列表返回 1 会中止整个脚本
    return 0
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TARGET_SPECIFIED=false
CREATE_DIR_FROM_NAME=false
TARGET_DIR="$PWD"
TOOLS_ARG=""
SKIP_IDE_TOOLS=false
ENABLE_BMAD=false

# rev-2026-05-26-bootstrap-script-overhaul D1+D2: non-interactive CLI args
CLI_PROFILE=""
CLI_MODE=""
CLI_GOVERNANCE_LAYOUT="auto"
CLI_PROJECT_NAME=""
CLI_PROJECT_DESCRIPTION=""
NO_GIT_INIT=false
NO_RUNTIME_CONTEXT=false
NO_INTAKE_BOOTSTRAP=false

while [ $# -gt 0 ]; do
    case "$1" in
        --create-dir-from-name)
            CREATE_DIR_FROM_NAME=true
            ;;
        --tools)
            shift
            TOOLS_ARG="${1:-}"
            [ -n "$TOOLS_ARG" ] || die "--tools requires a value (e.g. all or claude,cursor)"
            ;;
        --skip-ide-tools)
            SKIP_IDE_TOOLS=true
            ;;
        --enable-bmad)
            ENABLE_BMAD=true
            ;;
        --profile)
            shift
            CLI_PROFILE="${1:-}"
            [ -n "$CLI_PROFILE" ] || die "--profile requires a value"
            ;;
        --mode)
            shift
            CLI_MODE="${1:-}"
            case "$CLI_MODE" in
                greenfield|brownfield) ;;
                *) die "--mode must be greenfield or brownfield (got: $CLI_MODE)" ;;
            esac
            ;;
        --governance-layout)
            shift
            CLI_GOVERNANCE_LAYOUT="${1:-}"
            case "$CLI_GOVERNANCE_LAYOUT" in
                mother-repo-root|docs-governance-subtree|auto) ;;
                *) die "--governance-layout must be mother-repo-root | docs-governance-subtree | auto (got: $CLI_GOVERNANCE_LAYOUT)" ;;
            esac
            ;;
        --project-name)
            shift
            CLI_PROJECT_NAME="${1:-}"
            ;;
        --project-description)
            shift
            CLI_PROJECT_DESCRIPTION="${1:-}"
            ;;
        --no-git-init)
            NO_GIT_INIT=true
            ;;
        --no-runtime-context)
            NO_RUNTIME_CONTEXT=true
            ;;
        --no-intake-bootstrap)
            NO_INTAKE_BOOTSTRAP=true
            ;;
        -h|--help)
            cat <<'EOF'
Usage:
  ./scripts/bootstrap.sh [target_dir] [options]

Options:
  --create-dir-from-name        Create subdirectory from project name (only when target_dir omitted)
  --tools LIST|all              IDE/CLI tools for OpenSpec init (default: claude,cursor,codex,opencode,qwen,trae)
  --skip-ide-tools              Skip openspec init (keeps legacy .claude → .cursor/.codex mirror)
  --enable-bmad                 Also run bmad-method install (replaces _bmad from upstream)

  --profile NAME                solo-developer | backend-service | desktop-application | embedded-system
                                | ml-system | native-security-runtime | security-research
  --mode MODE                   greenfield | brownfield
  --governance-layout LAYOUT    mother-repo-root | docs-governance-subtree | auto (default)
  --project-name NAME           Project name (skips interactive prompt)
  --project-description TEXT    Project description (skips interactive prompt)
  --no-git-init                 Skip auto git init
  --no-runtime-context          Skip generating runtime-context.yaml
  --no-intake-bootstrap         Skip creating _bmad/<project_id>/ namespace

Examples (no interaction):
  ./scripts/bootstrap.sh /opt/myapp \
      --profile backend-service --mode greenfield \
      --governance-layout docs-governance-subtree \
      --project-name myapp --project-description "REST API" \
      --tools codex,cursor --enable-bmad

After bootstrap:
  python scripts/export-governance-rules.py   # Cursor / Copilot governance rules
EOF
            exit 0
            ;;
        -*)
            die "Unknown option: $1"
            ;;
        *)
            if [ "$TARGET_SPECIFIED" = true ]; then
                die "Only one target directory can be specified: $1"
            fi
            TARGET_SPECIFIED=true
            TARGET_DIR="$1"
            ;;
    esac
    shift
done

[ -z "$TOOLS_ARG" ] && TOOLS_ARG="claude,cursor,codex,opencode,qwen,trae"

if [ -d "$TARGET_DIR" ]; then
    TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd || echo "$TARGET_DIR")"
else
    case "$TARGET_DIR" in
        /*) TARGET_DIR="$TARGET_DIR" ;;
        *) TARGET_DIR="$PWD/$TARGET_DIR" ;;
    esac
fi

header "Universal AI Governance Bootstrap"
echo -e "Framework: ${CYAN}$FRAMEWORK_DIR${NC}"
echo -e "Target:    ${CYAN}$TARGET_DIR${NC}"
echo ""

header "Step 1/6: Select Project Profile"

# rev-2026-05-26-bootstrap-script-overhaul D1: CLI-first, fall back to read.
if [ -n "$CLI_PROFILE" ]; then
    PROFILE="$CLI_PROFILE"
    info "Profile (from --profile): $PROFILE"
else
    echo "Available profiles:"
    echo "  1) solo-developer"
    echo "  2) backend-service"
    echo "  3) desktop-application"
    echo "  4) embedded-system"
    echo "  5) ml-system"
    echo "  6) native-security-runtime"
    echo "  7) security-research"
    echo ""
    read -rp "Choose profile [1-7, default 1]: " PROFILE_CHOICE
    PROFILE_CHOICE="${PROFILE_CHOICE:-1}"
    case "$PROFILE_CHOICE" in
        1) PROFILE="solo-developer" ;;
        2) PROFILE="backend-service" ;;
        3) PROFILE="desktop-application" ;;
        4) PROFILE="embedded-system" ;;
        5) PROFILE="ml-system" ;;
        6) PROFILE="native-security-runtime" ;;
        7) PROFILE="security-research" ;;
        *) PROFILE="solo-developer" ;;
    esac
fi
success "Profile: $PROFILE"

header "Step 2/6: Project Stage + Governance Layout"

# rev-2026-05-26-bootstrap-script-overhaul D1 fix: 拆解 stage / layout，CLI 优先，auto 推导
# 2.a — Mode (greenfield / brownfield)
if [ -n "$CLI_MODE" ]; then
    MODE="$CLI_MODE"
    info "Mode (from --mode): $MODE"
else
    DEFAULT_MODE=1
    if [ "$TARGET_SPECIFIED" = false ]; then
        if has_standard_code_layout "$TARGET_DIR"; then
            DEFAULT_MODE=2
            info "Standard code layout detected; defaulting to Brownfield."
        else
            info "No standard code layout detected; defaulting to Greenfield."
        fi
    fi
    echo "  1) Greenfield (new project)"
    echo "  2) Brownfield (existing project)"
    echo ""
    read -rp "Choose mode [1-2, default $DEFAULT_MODE]: " MODE_CHOICE
    MODE_CHOICE="${MODE_CHOICE:-$DEFAULT_MODE}"
    if [ "$MODE_CHOICE" = "2" ]; then
        MODE="brownfield"
    else
        MODE="greenfield"
    fi
fi

PROJECT_ROOT="$TARGET_DIR"
DEFAULT_PROJECT_NAME="$(basename "$PROJECT_ROOT")"
[ -n "$DEFAULT_PROJECT_NAME" ] || DEFAULT_PROJECT_NAME="my-project"

# 2.b — Governance Layout (auto/explicit)
# auto rules:
#   target == framework itself              → mother-repo-root (governance repo dogfood)
#   else                                    → docs-governance-subtree (business-project default; avoids polluting root)
GOVERNANCE_LAYOUT="$CLI_GOVERNANCE_LAYOUT"
if [ "$GOVERNANCE_LAYOUT" = "auto" ]; then
    if [ "$TARGET_DIR" = "$FRAMEWORK_DIR" ]; then
        GOVERNANCE_LAYOUT="mother-repo-root"
        info "Governance layout (auto): mother-repo-root (target is framework itself)"
    else
        GOVERNANCE_LAYOUT="docs-governance-subtree"
        info "Governance layout (auto): docs-governance-subtree (default for business projects)"
    fi
else
    info "Governance layout (from --governance-layout): $GOVERNANCE_LAYOUT"
fi

# 2.c — Project name + description
if [ -n "$CLI_PROJECT_NAME" ]; then
    PROJECT_NAME="$CLI_PROJECT_NAME"
    info "Project name (from --project-name): $PROJECT_NAME"
else
    read -rp "Project name [$DEFAULT_PROJECT_NAME]: " PROJECT_NAME
    PROJECT_NAME="${PROJECT_NAME:-$DEFAULT_PROJECT_NAME}"
fi
if [ -n "$CLI_PROJECT_DESCRIPTION" ]; then
    PROJECT_DESC="$CLI_PROJECT_DESCRIPTION"
    info "Project description (from --project-description)."
else
    read -rp "Project description (optional): " PROJECT_DESC
    PROJECT_DESC="${PROJECT_DESC:-A project initialized with the AI governance framework}"
fi

SUGGESTED_DIR_NAME="$(to_dir_name "$PROJECT_NAME")"
CURRENT_DIR_NAME="$(basename "$PROJECT_ROOT")"

if [ "$TARGET_SPECIFIED" = false ]; then
    if [ "$CREATE_DIR_FROM_NAME" = true ]; then
        PROJECT_ROOT="$PROJECT_ROOT/$SUGGESTED_DIR_NAME"
        info "Using subdirectory: $PROJECT_ROOT"
    elif [ "$SUGGESTED_DIR_NAME" != "$CURRENT_DIR_NAME" ]; then
        warn "Current directory '$CURRENT_DIR_NAME' differs from suggested '$SUGGESTED_DIR_NAME'."
        warn "Use --create-dir-from-name to create a subdirectory from the project name."
    fi
elif [ "$CREATE_DIR_FROM_NAME" = true ]; then
    warn "--create-dir-from-name is ignored when target_dir is explicitly provided."
fi

# rev-2026-05-26-bootstrap-script-overhaul D1 fix:
# $GOVERNANCE_LAYOUT 已在 Step 2.b 解耦解析（不再 derive from $MODE）
if [ "$GOVERNANCE_LAYOUT" = "docs-governance-subtree" ]; then
    GOVERNANCE_DIR="$PROJECT_ROOT/docs/governance"
    GOV_PATH="docs/governance"
else
    GOVERNANCE_DIR="$PROJECT_ROOT"
    GOV_PATH="."
fi

if [ "$PROJECT_ROOT" = "$FRAMEWORK_DIR" ]; then
    IN_PLACE=true
    warn "Target is the framework directory; in-place mode skips file copy."
else
    IN_PLACE=false
fi
success "Mode: $MODE | Root: $PROJECT_ROOT | Governance: $GOVERNANCE_DIR"

header "Step 3/6: Copy Framework Files"
if [ "$IN_PLACE" = true ]; then
    info "Skipping copy stage (in-place)."
else
    mkdir -p "$GOVERNANCE_DIR"

    for f in \
        00-index.md 00-index.yaml 01-charter.md 02-engineering-principles.md \
        02-phase-governance.md 03-document-workflow.md 04-verification-policy.md \
        05-ai-collaboration-policy.md 06-reference-and-standards-policy.md \
        07-bootstrap-and-adoption-guide.md 08-project-activation-model.md \
        LAYOUT.md CLAUDE.md README.md UPSTREAM-VERSIONS.yaml; do
        [ -f "$FRAMEWORK_DIR/$f" ] && cp "$FRAMEWORK_DIR/$f" "$GOVERNANCE_DIR/$f"
    done
    [ -f "$FRAMEWORK_DIR/AGENTS.md" ] && cp "$FRAMEWORK_DIR/AGENTS.md" "$PROJECT_ROOT/AGENTS.md"
    success "Copied governance primary documents"

    for dir in foundations domains profiles templates revisions agents; do
        copy_dir_merge "$FRAMEWORK_DIR/$dir" "$GOVERNANCE_DIR/$dir"
    done
    success "Copied governance subdirectories"

    # RSI session entries are project-specific; copy only the index protocol.
    mkdir -p "$GOVERNANCE_DIR/rsi"
    for f in README.md _index.yaml native-cli-compatibility.md; do
        [ -f "$FRAMEWORK_DIR/rsi/$f" ] && cp "$FRAMEWORK_DIR/rsi/$f" "$GOVERNANCE_DIR/rsi/$f"
    done

    for rootdir in openspec _bmad .claude; do
        copy_dir_merge "$FRAMEWORK_DIR/$rootdir" "$PROJECT_ROOT/$rootdir"
        [ -d "$FRAMEWORK_DIR/$rootdir" ] && success "Copied $rootdir"
    done

    if [ "$SKIP_IDE_TOOLS" = true ] && [ -d "$FRAMEWORK_DIR/.claude" ]; then
        copy_dir_merge "$FRAMEWORK_DIR/.claude/commands" "$PROJECT_ROOT/.cursor/commands"
        copy_dir_merge "$FRAMEWORK_DIR/.claude/skills" "$PROJECT_ROOT/.cursor/skills"
        copy_dir_merge "$FRAMEWORK_DIR/.claude/commands" "$PROJECT_ROOT/.codex/commands"
        copy_dir_merge "$FRAMEWORK_DIR/.claude/skills" "$PROJECT_ROOT/.codex/skills"
        warn "Legacy mirror: .cursor / .codex from .claude (--skip-ide-tools). Prefer OpenSpec init without --skip-ide-tools."
    fi

    copy_dir_merge "$FRAMEWORK_DIR/examples" "$GOVERNANCE_DIR/examples"
    [ -d "$FRAMEWORK_DIR/examples" ] && success "Copied examples"
    copy_dir_merge "$FRAMEWORK_DIR/scripts" "$PROJECT_ROOT/scripts"
    [ -d "$FRAMEWORK_DIR/scripts" ] && success "Copied scripts (export-governance-rules, bootstrap-ide-tools, …)"

    rewrite_governance_index_layout "$GOVERNANCE_DIR/00-index.yaml" "$GOVERNANCE_LAYOUT"
    success "Rewrote governance index layout: $GOVERNANCE_LAYOUT"
fi

header "Step 4/6: Generate Project Configuration"
GENERATED_DATE="$(date +%Y-%m-%d)"
BMAD_ENABLED="false"
[ "$ENABLE_BMAD" = true ] && BMAD_ENABLED="true"

# rev-2026-05-26-bootstrap-script-overhaul D2.7: capture master commit + branch
get_master_repo_meta "$FRAMEWORK_DIR"
info "Master repo baseline: governance @ ${MASTER_REPO_COMMIT} (branch ${MASTER_REPO_BRANCH})"

PROJECT_ID="$(to_dir_name "$PROJECT_NAME")"

TOOLS_YAML=""
IFS=',' read -ra _TOOL_ARR <<< "$(echo "$TOOLS_ARG" | tr -d ' ')"
for _t in "${_TOOL_ARR[@]}"; do
    [ -n "$_t" ] || continue
    TOOLS_YAML="${TOOLS_YAML}    - ${_t}"$'\n'
done

cat > "$PROJECT_ROOT/project-governance.yaml" << EOF
# Generated by bootstrap.sh on ${GENERATED_DATE}
# Template reference: templates/project-governance-manifest-template.yaml

project_id: $PROJECT_ID
project_name: "$PROJECT_NAME"
project_description: "$PROJECT_DESC"
project_stage: $MODE

governance_layout: $GOVERNANCE_LAYOUT
governance_root: $GOV_PATH

project_type_profile:
  - $PROFILE

active_baseline:
  charter: 01-charter.md
  engineering_principles: 02-engineering-principles.md
  phase_governance: 02-phase-governance.md
  workflow: 03-document-workflow.md
  verification: 04-verification-policy.md
  ai_collaboration: 05-ai-collaboration-policy.md
  references: 06-reference-and-standards-policy.md
  activation: 08-project-activation-model.md
  layout: LAYOUT.md

enabled_foundations: []
enabled_domains: []
enabled_templates: []

local_overrides: []

authority_map:
  active_project_rules:
    - AGENTS.md
  project_specific_docs: []
  deprecated_parallel_rules: []

frameworks:
  openspec:
    enabled: true
    default: true
    schema: spec-driven
  bmad:
    enabled: true
    config: "_bmad/bmm"
    installer_ran: $BMAD_ENABLED
    note: "默认双载体（tool.binding.r11）：功能迭代必须 Story(PRD FR)+change 双向绑定；上游安装器另用 --enable-bmad"
  superpowers:
    enabled: false

agent_evals:
  enabled: false
  provider: promptfoo
  pr_gate:
    enabled: false
    block_merge_on_fail: true
    min_pass_rate: 0.85

mcp_connectors: []

ide_rules_export:
  cursor_rules_dir: .cursor/rules
  copilot_instructions: .github/copilot-instructions.md
  regenerate_command: python scripts/export-governance-rules.py

ai_ide_tools:
  installed_via: bootstrap-ide-tools
  tools:
${TOOLS_YAML}  openspec_package: "@fission-ai/openspec@1.5.0"
  skip_install: $SKIP_IDE_TOOLS

upstream_versions: UPSTREAM-VERSIONS.yaml

migration_mode:
  status: none
  notes: ""

adoption_source:
  governance_template_origin: $GOV_PATH
  adopted_at: $GENERATED_DATE
  master_repo_commit_at_adoption: $MASTER_REPO_COMMIT
  master_repo_branch_at_adoption: $MASTER_REPO_BRANCH
EOF
success "Generated project-governance.yaml"

# rev-2026-05-26-bootstrap-script-overhaul D2.1-D2.4: render project-specific files via templates
export TPL_PROJECT_NAME="$PROJECT_NAME"
export TPL_PROJECT_DESCRIPTION="$PROJECT_DESC"
export TPL_PROJECT_ID="$PROJECT_ID"
export TPL_PROFILE="$PROFILE"
export TPL_GOVERNANCE_LAYOUT="$GOVERNANCE_LAYOUT"
export TPL_GOVERNANCE_ROOT="$GOV_PATH"
export TPL_MASTER_REPO_COMMIT="$MASTER_REPO_COMMIT"
export TPL_MASTER_REPO_BRANCH="$MASTER_REPO_BRANCH"
export TPL_ADOPTED_AT="$GENERATED_DATE"

# D2.1: project AGENTS.md (overrides the raw copy from Step 3)
AGENTS_TPL="$FRAMEWORK_DIR/templates/AGENTS.md.template"
if [ -f "$AGENTS_TPL" ]; then
    render_template "$AGENTS_TPL" "$PROJECT_ROOT/AGENTS.md" \
        && success "Rendered project AGENTS.md from template"
else
    warn "templates/AGENTS.md.template not found; keeping raw AGENTS.md copy"
fi

# D2.2: project .gitignore
GITIGNORE_TPL="$FRAMEWORK_DIR/templates/project-gitignore.template"
if [ -f "$GITIGNORE_TPL" ]; then
    if [ -f "$PROJECT_ROOT/.gitignore" ]; then
        warn "Existing .gitignore detected → not overwriting"
    else
        render_template "$GITIGNORE_TPL" "$PROJECT_ROOT/.gitignore" \
            && success "Generated .gitignore from template"
    fi
fi

# rev-2026-07-20-fact-persistence: docs/project-rules.md（开发域事实标准位，存在则不覆盖）
PR_TPL="$FRAMEWORK_DIR/templates/project-rules-template.md"
if [ -f "$PR_TPL" ]; then
    if [ -f "$PROJECT_ROOT/docs/project-rules.md" ]; then
        info "Existing docs/project-rules.md detected → not overwriting"
    else
        mkdir -p "$PROJECT_ROOT/docs"
        render_template "$PR_TPL" "$PROJECT_ROOT/docs/project-rules.md" \
            && success "Generated docs/project-rules.md (dev-domain fact store)"
    fi
fi

# D2.3: runtime-context.yaml
if [ "$NO_RUNTIME_CONTEXT" = true ]; then
    info "Skip runtime-context.yaml (--no-runtime-context)"
else
    RC_TPL="$FRAMEWORK_DIR/templates/runtime-context-manifest-template.yaml"
    if [ -f "$RC_TPL" ]; then
        render_template "$RC_TPL" "$PROJECT_ROOT/runtime-context.yaml" \
            && success "Generated runtime-context.yaml from template"
    else
        warn "templates/runtime-context-manifest-template.yaml not found"
    fi
fi

header "Step 4.5/6: Local Git + BMAD Namespace"

# rev-2026-05-26-bootstrap-script-overhaul D2.5: ensure local git repo (separate from master)
if [ "$NO_GIT_INIT" = true ]; then
    info "Skip git init (--no-git-init)"
elif [ -d "$PROJECT_ROOT/.git" ]; then
    info "Git repo already exists at $PROJECT_ROOT/.git → not re-initialising"
else
    if command -v git >/dev/null 2>&1; then
        ( cd "$PROJECT_ROOT" && git init -q && git symbolic-ref HEAD refs/heads/main 2>/dev/null || true ) \
            && success "Initialised local git repo (branch: main)"
    else
        warn "git not installed → skipping git init"
    fi
fi

# rev-2026-05-26-bootstrap-script-overhaul D2.6: project-specific BMAD namespace _bmad/<project_id>/
if [ "$NO_INTAKE_BOOTSTRAP" = true ]; then
    info "Skip _bmad/<project_id>/ namespace (--no-intake-bootstrap)"
else
    BMAD_NS_DIR="$PROJECT_ROOT/_bmad/$PROJECT_ID"
    if [ -d "$BMAD_NS_DIR" ]; then
        info "BMAD namespace already exists: _bmad/$PROJECT_ID/"
    else
        mkdir -p "$BMAD_NS_DIR/sprints"
        cat > "$BMAD_NS_DIR/README.md" <<EOF
# BMAD namespace — $PROJECT_NAME

Project-scoped BMAD workspace. Generated by bootstrap.sh on $GENERATED_DATE.

- \`intake.md\`         : requirements intake notes (use Intake Protocol)
- \`sprints/_index.yaml\`: rolling list of sprints (link M+A+D artifacts)

See \`_bmad/bmm/\` for shared methodology, agents, and templates.
EOF
        cat > "$BMAD_NS_DIR/intake.md" <<EOF
# Intake — $PROJECT_NAME

> Capture requests here before promoting to a sprint / change proposal.
> Use the Intake Protocol from \`_bmad/bmm/\` (Break → Make → Assess → Deliver).

## Open intake items

(no items yet)
EOF
        cat > "$BMAD_NS_DIR/sprints/_index.yaml" <<EOF
# Sprint index for $PROJECT_NAME
# Generated by bootstrap.sh on $GENERATED_DATE
project_id: $PROJECT_ID
sprints: []
EOF
        success "Initialised _bmad/$PROJECT_ID/ namespace (README / intake / sprints index)"
    fi
fi

header "Step 5/6: Install IDE / CLI Adapters"
if [ "$SKIP_IDE_TOOLS" = true ]; then
    warn "Skipped OpenSpec init (--skip-ide-tools)."
elif [ "$IN_PLACE" = true ]; then
    info "In-place mode: run manually from project root:"
    info "  ./scripts/bootstrap-ide-tools.sh . --tools $TOOLS_ARG"
else
    IDE_ARGS=(--tools "$TOOLS_ARG")
    [ "$ENABLE_BMAD" = true ] && IDE_ARGS+=(--enable-bmad)
    bash "$SCRIPT_DIR/bootstrap-ide-tools.sh" "$PROJECT_ROOT" "${IDE_ARGS[@]}"
fi

# rev-2026-05-26-bootstrap-script-overhaul P1 (i18n): OpenSpec config localization
# 上游 `npx @fission-ai/openspec init --force` 会把 openspec/config.yaml 重写成英文默认模板。
# 这里在 init 完成后，把母版仓的 openspec/config.yaml（中文 context + 治理规则）覆盖回项目，
# 让 OpenSpec 默认输出中文 proposal/design/tasks（保留英文结构 token: ### Requirement: / SHALL 等）。
if [ "$SKIP_IDE_TOOLS" = false ] && [ "$IN_PLACE" = false ]; then
    FW_OPENSPEC_CONFIG="$FRAMEWORK_DIR/openspec/config.yaml"
    PRJ_OPENSPEC_CONFIG="$PROJECT_ROOT/openspec/config.yaml"
    if [ -f "$FW_OPENSPEC_CONFIG" ] && [ -d "$PROJECT_ROOT/openspec" ]; then
        cp "$FW_OPENSPEC_CONFIG" "$PRJ_OPENSPEC_CONFIG"
        success "Patched openspec/config.yaml (zh-CN governance baseline)"
    else
        warn "Skipped openspec config patch (framework config or project openspec/ missing)"
    fi
fi

header "Step 5.5/6: Activate Closed-Loop Governance Gate"

# rev portable-closed-loop-enforcement P0.5:
# 1) 把 git 门禁（可选附加层）幂等、非破坏地挂到"目标项目自己的 git"上；
# 2) 强制跑一次零依赖自检，证明闭环已激活（地基门禁，必能跑）。
PYTHON_BIN=""
for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON_BIN="$cand"; break; fi
done

if [ "$GOVERNANCE_LAYOUT" = "docs-governance-subtree" ]; then
    SELFCHECK_ROOT="$GOVERNANCE_DIR"
else
    SELFCHECK_ROOT="$PROJECT_ROOT"
fi
HOOK_SCRIPTS_DIR="$PROJECT_ROOT/scripts"
[ "$IN_PLACE" = true ] && HOOK_SCRIPTS_DIR="$SCRIPT_DIR"
[ "$IN_PLACE" = true ] && SELFCHECK_ROOT="$FRAMEWORK_DIR"

if [ -z "$PYTHON_BIN" ]; then
    warn "python not found → cannot install git hooks or run self-check."
    warn "便携治理基线仍要求：手动跑 $HOOK_SCRIPTS_DIR/check_progress_consistency.py 并维护 _logs/sync-ledger.md。"
else
    info "Activating deterministic governance gates (git hooks + closed-loop self-check)…"
    # 统一入口：有 .git 装 git 门禁（无 .git 优雅降级）→ 收尾强制自检证明闭环已激活。
    "$PYTHON_BIN" "$HOOK_SCRIPTS_DIR/install_governance_gates.py" \
        --project-root "$PROJECT_ROOT" --governance-root "$SELFCHECK_ROOT"
    GATE_RC=$?
    if [ "$GATE_RC" = "0" ]; then
        success "Deterministic gates active — governance loop is ACTIVE."
    elif [ "$GATE_RC" = "1" ]; then
        warn "Closed-loop self-check reported drift (exit 1). 闭环已激活并立即可见漂移；"
        warn "请在收尾前消除漂移或登记合法豁免（见 04-verification-policy 完成判定）。"
    else
        warn "git 门禁未完全装上（exit $GATE_RC，仅丢失加分项，基线门禁照常生效）。"
    fi
fi

header "Step 6/6: Bootstrap Complete"
echo -e "${GREEN}${BOLD}Bootstrap completed successfully${NC}"
echo ""
echo "Next steps:"
echo -e "  1. Edit charter: ${CYAN}$GOVERNANCE_DIR/01-charter.md${NC}"
echo -e "  2. Review profile: ${CYAN}$GOVERNANCE_DIR/profiles/${PROFILE}.md${NC}"
echo -e "  3. Export IDE rules: ${CYAN}python scripts/export-governance-rules.py${NC}"
echo -e "  4. Start a change: ${CYAN}/opsx:new${NC} (Claude/Cursor/Codex/OpenCode/Qwen/Trae)"
echo ""
echo "AI tool directories (after OpenSpec init):"
echo -e "  .claude  .cursor  .codex  .opencode  .qwen  .trae  (and .agents/skills when BMAD enabled)"
echo ""
echo "Tools installed: $TOOLS_ARG"
echo ""
