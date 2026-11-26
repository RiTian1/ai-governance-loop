# Sync .claude/skills/bmad-* stubs from _bmad/_config/skill-manifest.csv
param(
    [switch]$Prune,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Manifest = Join-Path $Root "_bmad\_config\skill-manifest.csv"
$SkillsDir = Join-Path $Root ".claude\skills"

if (-not (Test-Path $Manifest)) { throw "Missing $Manifest" }

    # Support v6.7+ manifest (canonicalId,name,...) without install_to_bmad column
    $rows = Import-Csv $Manifest
$synced = 0
$pruned = 0

foreach ($row in $rows) {
    $name = $row.name.Trim()
    $desc = $row.description.Trim().Replace('"', "'")
    $canonicalSkill = $row.path.Trim() -replace '\\', '/'
    $canonicalDir = (Split-Path $canonicalSkill -Parent) -replace '\\', '/'

    $skillDir = Join-Path $SkillsDir $name
    if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $skillDir | Out-Null }

    $content = @"
---
name: $name
description: $desc
canonical_source: $canonicalDir
---

# BMAD skill stub (do not edit workflow here)

**Canonical source:** ``$canonicalDir/``

Edits belong under ``_bmad/`` only. Regenerate: ``scripts/sync-bmad-skills.ps1`` or ``.py --prune``

## Activation

1. Read ``$canonicalSkill`` from the canonical directory.
2. Follow ``workflow.md`` in the canonical directory when present.
"@

    $skillMd = Join-Path $skillDir "SKILL.md"
    if ($DryRun) {
        Write-Host "Would write $skillMd"
    } else {
        Set-Content -Path $skillMd -Value $content -Encoding UTF8
        Set-Content -Path (Join-Path $skillDir ".bmad-stub") -Value "$canonicalDir`n" -Encoding UTF8
    }

    if ($Prune -and (Test-Path $skillDir)) {
        Get-ChildItem $skillDir -Force | Where-Object { $_.Name -notin @('SKILL.md', '.bmad-stub') } | ForEach-Object {
            if ($DryRun) {
                Write-Host "  would remove $($_.FullName)"
            } else {
                if ($_.PSIsContainer) { Remove-Item $_.FullName -Recurse -Force }
                else { Remove-Item $_.FullName -Force }
            }
            $pruned++
        }
    }
    $synced++
}

Write-Host "Synced $synced skill stub(s); pruned $pruned item(s)"
