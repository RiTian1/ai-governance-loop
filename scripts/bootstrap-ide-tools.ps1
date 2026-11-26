#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Install OpenSpec (+ optional BMAD) IDE/CLI adapters after governance bootstrap.

.PARAMETER ProjectRoot
  Target project directory.

.PARAMETER Tools
  Comma-separated tool list, or "all" (default: claude,cursor,codex,opencode,qwen,trae).

.PARAMETER SkipOpenSpec
  Skip openspec init.

.PARAMETER EnableBmad
  Run bmad-method install (may replace _bmad from upstream).

.PARAMETER SkipBmad
  Skip BMAD even when EnableBmad is set.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [string]$Tools = "claude,cursor,codex,opencode,qwen,trae",
    [switch]$SkipOpenSpec,
    [switch]$EnableBmad,
    [switch]$SkipBmad
)

$ErrorActionPreference = "Stop"

$OpenSpecPkg = if ($env:OPENSPEC_PKG) { $env:OPENSPEC_PKG } else { "@fission-ai/openspec@1.5.0" }
$BmadPkg = if ($env:BMAD_PKG) { $env:BMAD_PKG } else { "bmad-method@6.10.0" }
$DefaultTools = "claude,cursor,codex,opencode,qwen,trae"

function Write-Info($msg) { Write-Host "i $msg" -ForegroundColor Yellow }
function Write-Ok($msg) { Write-Host "OK $msg" -ForegroundColor Green }
function Write-Err($msg) { Write-Host "ERR $msg" -ForegroundColor Red; exit 1 }

function Normalize-ToolsCsv([string]$Raw) {
    $r = $Raw.ToLowerInvariant() -replace '\s', ''
    if ($r -eq "all") { return $DefaultTools }
    $ids = $r -split ',' | ForEach-Object {
        $_ -replace '^claude-code$', 'claude' -replace '^claude_code$', 'claude'
    } | Where-Object { $_ } | Sort-Object -Unique
    return ($ids -join ',')
}

function To-BmadTools([string]$Csv) {
    # rev-2026-05-26-bootstrap-script-overhaul B1 fix:
    # Save the pipeline result before -join; Windows PowerShell rejects a trailing pipeline in nested parentheses.
    $items = @($Csv -split ',' | ForEach-Object {
        $t = $_.Trim()
        if ($t -eq 'claude') { 'claude-code' } else { $t }
    } | Where-Object { $_ })
    return ($items -join ',')
}

$root = [System.IO.Path]::GetFullPath($ProjectRoot)
if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    Write-Err "Not a directory: $root"
}

$toolsCsv = Normalize-ToolsCsv $Tools
$bmadTools = To-BmadTools $toolsCsv

Write-Info "Project: $root"
Write-Info "Tools: $toolsCsv"

if (-not $SkipOpenSpec) {
    if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
        Write-Err "npx not found. Install Node.js 18+ or use -SkipOpenSpec."
    }
    Write-Info "OpenSpec init ($OpenSpecPkg) tools=$toolsCsv"
    Push-Location $root
    # rev-2026-05-26-bootstrap-script-overhaul B3 fix:
    # PowerShell EAP=Stop 会把 npx stderr 进度 log（如 "- Setting up Codex..."）
    # 当作 NativeCommandError 抛出。临时切 Continue 并通过 $LASTEXITCODE 判定。
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & npx --yes $OpenSpecPkg init . --tools $toolsCsv --force --profile custom 2>&1 | ForEach-Object { Write-Host $_ }
        $exitOpenSpec = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEAP
        Pop-Location
    }
    if ($exitOpenSpec -ne 0) {
        Write-Err "OpenSpec init failed (exit $exitOpenSpec)"
    }
    Write-Ok "OpenSpec adapters installed"
} else {
    Write-Info "Skipped OpenSpec install"
}

if ($EnableBmad -and -not $SkipBmad) {
    if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
        Write-Err "npx not found (required for BMAD install)"
    }
    # rev-2026-05-26-bootstrap-script-overhaul B2 fix:
    # bootstrap-windows.ps1 Step 3 已经从母版仓复制 _bmad/ 到目标项目；
    # BMAD CLI 检测到 _bmad/ 存在会拒绝 `--action install`，必须用 update。
    # 同时保留首次干净接入时 install 的能力，因此 auto-detect。
    $bmadAction = if (Test-Path -LiteralPath (Join-Path $root '_bmad') -PathType Container) { 'update' } else { 'install' }
    # P0 (i18n): BMAD v6 官方 flag —— Agent 对话 + 文档输出走中文
    Write-Info "BMAD install ($BmadPkg) tools=$bmadTools action=$bmadAction lang=Chinese"
    Push-Location $root
    # B3 fix: 同 OpenSpec init 处理，临时切 EAP=Continue
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & npx --yes $BmadPkg install --yes --tools $bmadTools --modules core,bmm `
            --directory . --action $bmadAction `
            --communication-language Chinese --document-output-language Chinese 2>&1 | ForEach-Object { Write-Host $_ }
        $exitBmad = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEAP
        Pop-Location
    }
    if ($exitBmad -ne 0) {
        Write-Err "BMAD install failed (exit $exitBmad)"
    }
    Write-Ok "BMAD skill adapters installed (zh-CN)"
} elseif ($EnableBmad) {
    Write-Info "Skipped BMAD install (-SkipBmad)"
} else {
    Write-Info "BMAD install skipped (default; use -EnableBmad when frameworks.bmad.enabled is true)"
}

Write-Ok "IDE tool bootstrap finished"
