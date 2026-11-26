#!/usr/bin/env pwsh
param(
    # 上游已迁移：The-Agency-Agents/agency-agents -> msitarzewski/agency-agents（2026-07 核实）
    [string]$RepoUrl = "https://github.com/msitarzewski/agency-agents.git"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir ".."))
$referenceRoot = Join-Path $projectRoot "_reference"
$targetDir = Join-Path $referenceRoot "agency-agents-main"

New-Item -ItemType Directory -Path $referenceRoot -Force | Out-Null

if (Test-Path -LiteralPath (Join-Path $targetDir ".git") -PathType Container) {
    Write-Host "Updating existing reference bundle: $targetDir" -ForegroundColor Cyan
    & git -C $targetDir pull --ff-only
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
elseif (Test-Path -LiteralPath $targetDir -PathType Container) {
    throw "Target exists but is not a git repository: $targetDir`nPlease remove it manually, then rerun this script."
}
else {
    Write-Host "Cloning reference bundle into: $targetDir" -ForegroundColor Cyan
    & git clone --depth 1 $RepoUrl $targetDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Done. Reference bundle is available at: $targetDir" -ForegroundColor Green