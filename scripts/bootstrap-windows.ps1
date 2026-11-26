#!/usr/bin/env pwsh
#
# bootstrap-windows.ps1 - Copy governance mother repo into a target project (Windows)
#
# Usage:
#   ./scripts/bootstrap-windows.ps1
#   ./scripts/bootstrap-windows.ps1 -TargetPath D:\path\to\project
#   ./scripts/bootstrap-windows.ps1 -Tools "claude,cursor,codex,opencode,qwen,trae"
#   ./scripts/bootstrap-windows.ps1 -SkipIdeTools
#   ./scripts/bootstrap-windows.ps1 -EnableBmad
#

param(
    [string]$TargetPath,
    [switch]$CreateDirFromName,
    [string]$Tools = "claude,cursor,codex,opencode,qwen,trae",
    [switch]$SkipIdeTools,
    [switch]$EnableBmad,

    # rev-2026-05-26-bootstrap-script-overhaul D1+D2 fix:
    # 新增 CLI 参数让脚本可以无交互一行跑通，同时解耦 stage / layout。
    [ValidateSet('solo-developer','backend-service','desktop-application','embedded-system','ml-system','native-security-runtime','security-research')]
    [string]$ProjectProfile,

    [ValidateSet('greenfield','brownfield')]
    [string]$Mode,

    [ValidateSet('mother-repo-root','docs-governance-subtree','auto')]
    [string]$GovernanceLayout = 'auto',

    [string]$ProjectName,
    [string]$ProjectDescription,

    [switch]$NoGitInit,
    [switch]$NoRuntimeContext,
    [switch]$NoIntakeBootstrap
)

$ErrorActionPreference = "Stop"

function Normalize-Path {
    param([string]$PathValue)
    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd('\', '/')
}

function Convert-ToDirName {
    param([string]$Text)
    $name = $Text.ToLowerInvariant() -replace '[^a-z0-9._-]', '-'
    $name = $name -replace '-+', '-'
    $name = $name.Trim('-')
    if ([string]::IsNullOrWhiteSpace($name)) { $name = "my-project" }
    return $name
}

function Info { param([string]$Message) Write-Host "i $Message" -ForegroundColor Blue }
function Success { param([string]$Message) Write-Host "OK $Message" -ForegroundColor Green }
function Warn { param([string]$Message) Write-Host "WARN $Message" -ForegroundColor Yellow }

function Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Copy-DirMerge {
    param([string]$SourceDir, [string]$DestDir)
    if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) { return }
    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    Get-ChildItem -LiteralPath $SourceDir -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $DestDir -Recurse -Force
    }
}

function Test-StandardCodeLayout {
    param([string]$RootDir)
    $markers = @(
        ".git", "src", "app", "lib", "cmd", "pkg", "internal", "server", "client",
        "api", "services", "backend", "frontend", "test", "tests",
        "package.json", "pnpm-workspace.yaml", "pyproject.toml", "requirements.txt",
        "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
        "Gemfile", "composer.json", "CMakeLists.txt", "Makefile"
    )
    foreach ($marker in $markers) {
        if (Test-Path -LiteralPath (Join-Path $RootDir $marker)) { return $true }
    }
    return $false
}

# rev-2026-05-26-bootstrap-script-overhaul D2 fix:
# 简单 {{VAR}} 占位替换；templates/<file>.template → 渲染后写入目标。
function Render-Template {
    param(
        [Parameter(Mandatory = $true)][string]$TemplatePath,
        [Parameter(Mandatory = $true)][hashtable]$Variables
    )
    if (-not (Test-Path -LiteralPath $TemplatePath -PathType Leaf)) {
        throw "Template not found: $TemplatePath"
    }
    $content = [System.IO.File]::ReadAllText($TemplatePath, [System.Text.Encoding]::UTF8)
    foreach ($key in $Variables.Keys) {
        $placeholder = "{{${key}}}"
        $content = $content.Replace($placeholder, [string]$Variables[$key])
    }
    return $content
}

# rev-2026-05-26-bootstrap-script-overhaul D2.7 fix:
# 自动检测母版仓 commit + branch 作为 adoption baseline。
function Get-MasterRepoMeta {
    param([string]$FrameworkDir)
    $result = @{ Commit = "unknown"; Branch = "unknown" }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return $result }
    Push-Location $FrameworkDir
    try {
        $c = (& git rev-parse --short HEAD 2>$null | Out-String).Trim()
        $b = (& git rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
        if ($c) { $result.Commit = $c }
        if ($b) { $result.Branch = $b }
    } catch { } finally {
        Pop-Location
    }
    return $result
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrameworkDir = Normalize-Path (Join-Path $ScriptDir "..")
$TargetSpecified = $PSBoundParameters.ContainsKey("TargetPath")
if ($TargetSpecified) { $TargetDir = Normalize-Path $TargetPath }
else { $TargetDir = Normalize-Path (Get-Location).Path }

Header "Universal AI Governance Bootstrap (Windows)"
Write-Host "Framework: $FrameworkDir" -ForegroundColor Cyan
Write-Host "Target:    $TargetDir" -ForegroundColor Cyan
Write-Host ""

Header "Step 1/6: Select Project Profile"

# rev-2026-05-26-bootstrap-script-overhaul D1: CLI-first, fall back to Read-Host.
$ProfileMap = [ordered]@{
    "1" = "solo-developer"
    "2" = "backend-service"
    "3" = "desktop-application"
    "4" = "embedded-system"
    "5" = "ml-system"
    "6" = "native-security-runtime"
    "7" = "security-research"
}

if ($ProjectProfile) {
    $Profile = $ProjectProfile
    Info "Profile (from -ProjectProfile): $Profile"
} else {
    foreach ($k in $ProfileMap.Keys) { Write-Host "  $k) $($ProfileMap[$k])" }
    Write-Host ""
    $ProfileChoice = Read-Host "Choose profile [1-7, default 1]"
    if ([string]::IsNullOrWhiteSpace($ProfileChoice)) { $ProfileChoice = "1" }
    if ($ProfileMap.Contains($ProfileChoice)) {
        $Profile = $ProfileMap[$ProfileChoice]
    } else {
        $Profile = "solo-developer"
    }
}
Success "Profile: $Profile"

Header "Step 2/6: Project Stage + Governance Layout"

# rev-2026-05-26-bootstrap-script-overhaul D1 fix: 拆解 stage / layout，CLI 优先，auto 推导。
# 2.a — Mode (greenfield / brownfield)
if ($Mode) {
    Info "Mode (from -Mode): $Mode"
} else {
    $DefaultMode = "1"
    if (-not $TargetSpecified) {
        if (Test-StandardCodeLayout -RootDir $TargetDir) {
            $DefaultMode = "2"
            Info "Standard code layout detected; defaulting to Brownfield."
        } else {
            Info "No standard code layout detected; defaulting to Greenfield."
        }
    }
    Write-Host "  1) Greenfield (new project)"
    Write-Host "  2) Brownfield (existing project)"
    Write-Host ""
    $ModeChoice = Read-Host "Choose mode [1-2, default $DefaultMode]"
    if ([string]::IsNullOrWhiteSpace($ModeChoice)) { $ModeChoice = $DefaultMode }
    if ($ModeChoice -eq "2") { $Mode = "brownfield" } else { $Mode = "greenfield" }
}

$ProjectRoot = $TargetDir
$DefaultProjectName = Split-Path -Leaf $ProjectRoot
if ([string]::IsNullOrWhiteSpace($DefaultProjectName)) { $DefaultProjectName = "my-project" }

# 2.b — Governance Layout (mother-repo-root / docs-governance-subtree / auto)
# auto rules:
#   target == framework itself              → mother-repo-root (treat as governance repo dogfood)
#   brownfield (existing project)           → docs-governance-subtree
#   greenfield + standard code layout       → docs-governance-subtree
#   greenfield + empty business project     → docs-governance-subtree (the safe business-project default)
if ($GovernanceLayout -eq 'auto') {
    $InPlaceCheck = ($TargetDir -eq $FrameworkDir)
    if ($InPlaceCheck) {
        $GovernanceLayout = 'mother-repo-root'
        Info "Governance layout (auto): mother-repo-root (target is framework itself)"
    } else {
        $GovernanceLayout = 'docs-governance-subtree'
        Info "Governance layout (auto): docs-governance-subtree (default for business projects; avoids polluting repo root)"
    }
} else {
    Info "Governance layout (from -GovernanceLayout): $GovernanceLayout"
}

# 2.c — Project name + description
if ($ProjectName) {
    Info "Project name (from -ProjectName): $ProjectName"
} else {
    $ProjectName = Read-Host "Project name [$DefaultProjectName]"
    if ([string]::IsNullOrWhiteSpace($ProjectName)) { $ProjectName = $DefaultProjectName }
}
if ($ProjectDescription) {
    $ProjectDesc = $ProjectDescription
    Info "Project description (from -ProjectDescription)."
} else {
    $ProjectDesc = Read-Host "Project description (optional)"
    if ([string]::IsNullOrWhiteSpace($ProjectDesc)) { $ProjectDesc = "A project initialized with the AI governance framework" }
}

$SuggestedDirName = Convert-ToDirName $ProjectName
$CurrentDirName = Split-Path -Leaf $ProjectRoot

if (-not $TargetSpecified) {
    if ($CreateDirFromName) {
        $ProjectRoot = Join-Path $ProjectRoot $SuggestedDirName
        Info "Using subdirectory: $ProjectRoot"
    } elseif ($SuggestedDirName -ne $CurrentDirName) {
        Warn "Current directory '$CurrentDirName' differs from suggested '$SuggestedDirName'."
        Warn "Use -CreateDirFromName to create a subdirectory from the project name."
    }
} elseif ($CreateDirFromName) {
    Warn "-CreateDirFromName is ignored when -TargetPath is explicitly provided."
}

# rev-2026-05-26-bootstrap-script-overhaul D1 fix:
# $GovernanceLayout 已在 Step 2.b 解耦解析（不再 derive from $Mode）
if ($GovernanceLayout -eq 'docs-governance-subtree') {
    $GovernanceDir = Join-Path $ProjectRoot "docs/governance"
    $GovPath = "docs/governance"
} else {
    # mother-repo-root
    $GovernanceDir = $ProjectRoot
    $GovPath = "."
}

$InPlace = ($ProjectRoot -eq $FrameworkDir)
if ($InPlace) {
    Warn "Target is the framework directory; in-place mode skips file copy."
}
Success "Mode: $Mode | Root: $ProjectRoot | Governance: $GovernanceDir"

Header "Step 3/6: Copy Framework Files"
if ($InPlace) {
    Info "Skipping copy stage (in-place)."
} else {
    New-Item -ItemType Directory -Path $GovernanceDir -Force | Out-Null

    $governanceFiles = @(
        "00-index.md","00-index.yaml","01-charter.md","02-engineering-principles.md",
        "02-phase-governance.md","03-document-workflow.md","04-verification-policy.md",
        "05-ai-collaboration-policy.md","06-reference-and-standards-policy.md",
        "07-bootstrap-and-adoption-guide.md","08-project-activation-model.md",
        "LAYOUT.md","CLAUDE.md","README.md","UPSTREAM-VERSIONS.yaml"
    )
    foreach ($fileName in $governanceFiles) {
        $src = Join-Path $FrameworkDir $fileName
        if (Test-Path -LiteralPath $src -PathType Leaf) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $GovernanceDir $fileName) -Force
        }
    }
    $agentsSrc = Join-Path $FrameworkDir "AGENTS.md"
    if (Test-Path -LiteralPath $agentsSrc) {
        Copy-Item -LiteralPath $agentsSrc -Destination (Join-Path $ProjectRoot "AGENTS.md") -Force
    }
    Success "Copied governance primary documents"

    foreach ($dirName in @("foundations","domains","profiles","templates","revisions","agents")) {
        Copy-DirMerge -SourceDir (Join-Path $FrameworkDir $dirName) -DestDir (Join-Path $GovernanceDir $dirName)
    }
    Success "Copied governance subdirectories"

    # RSI session entries are project-specific; copy only the index protocol.
    $rsiDir = Join-Path $GovernanceDir "rsi"
    New-Item -ItemType Directory -Path $rsiDir -Force | Out-Null
    foreach ($fileName in @("README.md","_index.yaml","native-cli-compatibility.md")) {
        $src = Join-Path $FrameworkDir "rsi/$fileName"
        if (Test-Path -LiteralPath $src -PathType Leaf) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $rsiDir $fileName) -Force
        }
    }

    foreach ($dirName in @("openspec","_bmad",".claude")) {
        Copy-DirMerge -SourceDir (Join-Path $FrameworkDir $dirName) -DestDir (Join-Path $ProjectRoot $dirName)
        if (Test-Path -LiteralPath (Join-Path $FrameworkDir $dirName) -PathType Container) {
            Success "Copied $dirName"
        }
    }

    if ($SkipIdeTools) {
        $claudeSrc = Join-Path $FrameworkDir ".claude"
        if (Test-Path -LiteralPath $claudeSrc -PathType Container) {
            Copy-DirMerge -SourceDir (Join-Path $claudeSrc "commands") -DestDir (Join-Path $ProjectRoot ".cursor/commands")
            Copy-DirMerge -SourceDir (Join-Path $claudeSrc "skills") -DestDir (Join-Path $ProjectRoot ".cursor/skills")
            Copy-DirMerge -SourceDir (Join-Path $claudeSrc "commands") -DestDir (Join-Path $ProjectRoot ".codex/commands")
            Copy-DirMerge -SourceDir (Join-Path $claudeSrc "skills") -DestDir (Join-Path $ProjectRoot ".codex/skills")
            Warn "Legacy mirror: .cursor / .codex from .claude (-SkipIdeTools)."
        }
    }

    Copy-DirMerge -SourceDir (Join-Path $FrameworkDir "examples") -DestDir (Join-Path $GovernanceDir "examples")
    Copy-DirMerge -SourceDir (Join-Path $FrameworkDir "scripts") -DestDir (Join-Path $ProjectRoot "scripts")
    Success "Copied examples and scripts"
}

Header "Step 4/6: Generate Project Configuration"
$generatedDate = Get-Date -Format "yyyy-MM-dd"
$projectId = Convert-ToDirName $ProjectName
$bmadEnabled = if ($EnableBmad) { "true" } else { "false" }
$skipInstall = if ($SkipIdeTools) { "true" } else { "false" }

# rev-2026-05-26-bootstrap-script-overhaul D2.7: capture master commit + branch
$masterMeta = Get-MasterRepoMeta -FrameworkDir $FrameworkDir
$masterCommit = $masterMeta.Commit
$masterBranch = $masterMeta.Branch
Info "Master repo baseline: governance @ $masterCommit (branch $masterBranch)"

$toolsList = ($Tools -replace '\s', '').ToLowerInvariant()
if ($toolsList -eq "all") { $toolsList = "claude,cursor,codex,opencode,qwen,trae" }
$toolsYaml = ($toolsList -split ',') | Where-Object { $_ } | ForEach-Object { "    - $_" }

$yaml = @"
# Generated by bootstrap-windows.ps1 on $generatedDate

project_id: $projectId
project_name: "$ProjectName"
project_stage: $Mode

governance_layout: $GovernanceLayout
governance_root: $GovPath

project_type_profile:
  - $Profile

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
    installer_ran: $bmadEnabled
    note: "默认双载体（tool.binding.r11）：功能迭代必须 Story(PRD FR)+change 双向绑定；上游安装器另用 -EnableBmad"
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
$($toolsYaml -join "`n")
  openspec_package: "@fission-ai/openspec@1.5.0"
  skip_install: $skipInstall

upstream_versions: UPSTREAM-VERSIONS.yaml

migration_mode:
  status: none
  notes: ""

adoption_source:
  governance_template_origin: $GovPath
  adopted_at: $generatedDate
  master_repo_commit_at_adoption: $masterCommit
  master_repo_branch_at_adoption: $masterBranch
"@

$govYamlPath = Join-Path $ProjectRoot "project-governance.yaml"
[System.IO.File]::WriteAllText($govYamlPath, $yaml, (New-Object System.Text.UTF8Encoding $false))
Success "Generated project-governance.yaml"

# rev-2026-05-26-bootstrap-script-overhaul D2.2-D2.4 fix:
# 用 templates/ 渲染项目特有产物，覆盖 Step 3 直接复制的母版版本（如 AGENTS.md），
# 并新增 Step 3 不生成的工件（.gitignore / runtime-context.yaml）。
$renderVars = @{
    PROJECT_NAME        = $ProjectName
    PROJECT_DESCRIPTION = $ProjectDesc
    PROJECT_ID          = $projectId
    PROFILE             = $Profile
    GOVERNANCE_LAYOUT   = $GovernanceLayout
    GOVERNANCE_ROOT     = $GovPath
    MASTER_REPO_COMMIT  = $masterCommit
    MASTER_REPO_BRANCH  = $masterBranch
    ADOPTED_AT          = $generatedDate
}

$tplAgents     = Join-Path $FrameworkDir "templates/AGENTS.md.template"
$tplGitignore  = Join-Path $FrameworkDir "templates/project-gitignore.template"
$tplRuntimeCtx = Join-Path $FrameworkDir "templates/runtime-context-manifest-template.yaml"
$utf8NoBom     = New-Object System.Text.UTF8Encoding $false

if (Test-Path -LiteralPath $tplAgents -PathType Leaf) {
    $rendered = Render-Template -TemplatePath $tplAgents -Variables $renderVars
    [System.IO.File]::WriteAllText((Join-Path $ProjectRoot "AGENTS.md"), $rendered, $utf8NoBom)
    Success "Rendered AGENTS.md (project-specific; replaces framework copy)"
}

if (Test-Path -LiteralPath $tplGitignore -PathType Leaf) {
    $rendered = Render-Template -TemplatePath $tplGitignore -Variables $renderVars
    [System.IO.File]::WriteAllText((Join-Path $ProjectRoot ".gitignore"), $rendered, $utf8NoBom)
    Success "Rendered .gitignore"
}

if (-not $NoRuntimeContext -and (Test-Path -LiteralPath $tplRuntimeCtx -PathType Leaf)) {
    $rendered = Render-Template -TemplatePath $tplRuntimeCtx -Variables $renderVars
    [System.IO.File]::WriteAllText((Join-Path $ProjectRoot "runtime-context.yaml"), $rendered, $utf8NoBom)
    Success "Rendered runtime-context.yaml"
}

# rev-2026-07-20-fact-persistence: docs/project-rules.md（开发域事实标准位，存在则不覆盖）
$tplProjectRules = Join-Path $FrameworkDir "templates/project-rules-template.md"
$projectRulesOut = Join-Path $ProjectRoot "docs/project-rules.md"
if ((Test-Path -LiteralPath $tplProjectRules -PathType Leaf) -and -not (Test-Path -LiteralPath $projectRulesOut -PathType Leaf)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "docs") | Out-Null
    $rendered = Render-Template -TemplatePath $tplProjectRules -Variables $renderVars
    [System.IO.File]::WriteAllText($projectRulesOut, $rendered, $utf8NoBom)
    Success "Rendered docs/project-rules.md (dev-domain fact store)"
}

# rev-2026-05-26-bootstrap-script-overhaul D2.1: auto git init
if (-not $NoGitInit -and -not $InPlace) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git") -PathType Container)) {
        try {
            Push-Location $ProjectRoot
            & git init 2>&1 | Out-Null
            & git config core.autocrlf false 2>&1 | Out-Null
            Success "Initialized empty git repository (git init)"
        } catch {
            Warn "git init failed: $($_.Exception.Message)"
        } finally {
            Pop-Location
        }
    } else {
        Info "Existing .git/ detected; skipping git init"
    }
}

# rev-2026-05-26-bootstrap-script-overhaul D2.5 fix: project-specific BMAD namespace
# 必须在 Step 5 之前完成（不依赖 IDE adapter install 成功）
if (-not $NoIntakeBootstrap) {
    Header "Step 4.5/6: Initialize Project BMAD Namespace"
    $projectBmadDir = Join-Path $ProjectRoot "_bmad/$projectId"
    New-Item -ItemType Directory -Path $projectBmadDir -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectBmadDir "epics") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectBmadDir "sprints") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectBmadDir "stories") -Force | Out-Null

    $bmadReadme = @"
# _bmad/$projectId - Project BMAD Workspace

> $ProjectName - $ProjectDesc
> 由 scripts/bootstrap-windows.ps1 (rev-2026-05-26-bootstrap-script-overhaul D2.5) 自动初始化。

## 结构

- ``intake.md``           - 项目特有需求接入协议（fork 自 ``templates/requirement-intake-template.md``，需填充 §8-§11）
- ``epics/``              - Epic 文件
- ``sprints/_index.yaml`` - Sprint 索引
- ``stories/``            - Story 文件

详见 ``$GovPath/domains/tooling/bmad/index.md``。
"@
    [System.IO.File]::WriteAllText((Join-Path $projectBmadDir "README.md"), $bmadReadme, $utf8NoBom)

    $tplIntake = Join-Path $FrameworkDir "templates/requirement-intake-template.md"
    if (Test-Path -LiteralPath $tplIntake -PathType Leaf) {
        $intakeContent = [System.IO.File]::ReadAllText($tplIntake, [System.Text.Encoding]::UTF8)
        $intakeContent = $intakeContent.Replace("<project_id>", $projectId)
        [System.IO.File]::WriteAllText((Join-Path $projectBmadDir "intake.md"), $intakeContent, $utf8NoBom)
    }

    $sprintsIndex = @"
# Sprint 索引 - $ProjectName
# 由 bootstrap-windows.ps1 初始化；按 _bmad/$projectId/sprints/<sprint_id>.md 添加。

active_sprint: null
sprints: []
"@
    [System.IO.File]::WriteAllText((Join-Path $projectBmadDir "sprints/_index.yaml"), $sprintsIndex, $utf8NoBom)

    Success "Initialized _bmad/$projectId/ (README + intake.md + epics/ + sprints/_index.yaml + stories/)"
}

Header "Step 5/6: Install IDE / CLI Adapters"
if ($SkipIdeTools) {
    Warn "Skipped OpenSpec init (-SkipIdeTools)."
} elseif ($InPlace) {
    Info "In-place mode: run manually:"
    Info "  .\scripts\bootstrap-ide-tools.ps1 -ProjectRoot . -Tools `"$Tools`""
} else {
    $ideArgs = @{
        ProjectRoot = $ProjectRoot
        Tools       = $Tools
    }
    if ($EnableBmad) { $ideArgs.EnableBmad = $true }
    & (Join-Path $ScriptDir "bootstrap-ide-tools.ps1") @ideArgs
}

# rev-2026-05-26-bootstrap-script-overhaul P1 (i18n): OpenSpec config localization
# 上游 `npx @fission-ai/openspec init --force` 会把 openspec/config.yaml 重写成英文默认模板。
# 这里在 init 完成后，把母版仓的 openspec/config.yaml（中文 context + 治理规则）覆盖回项目，
# 让 OpenSpec 默认输出中文 proposal/design/tasks（保留英文结构 token: ### Requirement: / SHALL 等）。
if (-not $SkipIdeTools -and -not $InPlace) {
    $fwOpenSpecCfg  = Join-Path $FrameworkDir 'openspec\config.yaml'
    $prjOpenSpecDir = Join-Path $ProjectRoot 'openspec'
    $prjOpenSpecCfg = Join-Path $prjOpenSpecDir 'config.yaml'
    if ((Test-Path -LiteralPath $fwOpenSpecCfg -PathType Leaf) -and (Test-Path -LiteralPath $prjOpenSpecDir -PathType Container)) {
        Copy-Item -LiteralPath $fwOpenSpecCfg -Destination $prjOpenSpecCfg -Force
        Success "Patched openspec/config.yaml (zh-CN governance baseline)"
    } else {
        Warn "Skipped openspec config patch (framework config or project openspec/ missing)"
    }
}

Header "Step 5.5/6: Activate Closed-Loop Governance Gate"

# rev portable-closed-loop-enforcement P0.5:
# 1) 把 git 门禁（可选附加层）幂等、非破坏地挂到"目标项目自己的 git"上；
# 2) 强制跑一次零依赖自检，证明闭环已激活（地基门禁，必能跑）。
$PythonBin = $null
foreach ($cand in @('python', 'python3', 'py')) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $PythonBin = $cand; break }
}

if ($GovernanceLayout -eq 'docs-governance-subtree') {
    $SelfCheckRoot = $GovernanceDir
} else {
    $SelfCheckRoot = $ProjectRoot
}
$HookScriptsDir = Join-Path $ProjectRoot 'scripts'
if ($InPlace) { $HookScriptsDir = $ScriptDir; $SelfCheckRoot = $FrameworkDir }

if (-not $PythonBin) {
    Warn "python not found -> cannot install git hooks or run self-check."
    Warn "便携治理基线仍要求：手动跑 $HookScriptsDir/check_progress_consistency.py 并维护 _logs/sync-ledger.md。"
} else {
    Info "Activating deterministic governance gates (git hooks + closed-loop self-check)..."
    # 统一入口：有 .git 装 git 门禁（无 .git 优雅降级）→ 收尾强制自检证明闭环已激活。
    & $PythonBin (Join-Path $HookScriptsDir 'install_governance_gates.py') `
        --project-root $ProjectRoot --governance-root $SelfCheckRoot
    $GateRc = $LASTEXITCODE
    if ($GateRc -eq 0) {
        Success "Deterministic gates active - governance loop is ACTIVE."
    } elseif ($GateRc -eq 1) {
        Warn "Closed-loop self-check reported drift (exit 1). 闭环已激活并立即可见漂移；"
        Warn "请在收尾前消除漂移或登记合法豁免（见 04-verification-policy 完成判定）。"
    } else {
        Warn "git 门禁未完全装上（exit $GateRc，仅丢失加分项，基线门禁照常生效）。"
    }
}

Header "Step 6/6: Bootstrap Complete"
Write-Host "Bootstrap completed successfully" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit charter: $GovernanceDir/01-charter.md" -ForegroundColor Cyan
Write-Host "  2. Review profile: $GovernanceDir/profiles/$Profile.md" -ForegroundColor Cyan
Write-Host "  3. Export IDE rules: python scripts/export-governance-rules.py" -ForegroundColor Cyan
Write-Host "  4. Start a change: /opsx:new" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tools: $Tools"
Write-Host ""
