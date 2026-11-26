# Export governance domains to .cursor/rules and .github/copilot-instructions.md
param(
    [string]$ProjectRoot = ".",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path $ProjectRoot
$ManifestPath = Join-Path $Root "project-governance.yaml"

if (-not (Test-Path $ManifestPath)) { throw "Missing $ManifestPath" }

# Minimal YAML parsing for enabled_domains and governance_root
$text = Get-Content $ManifestPath -Raw
$groot = "."
if ($text -match 'governance_root:\s*([^\r\n]+)') { $groot = $Matches[1].Trim().Trim('"') }
$layout = "mother-repo-root"
if ($text -match 'governance_layout:\s*([^\r\n]+)') { $layout = $Matches[1].Trim() }

$grootPath = if ($layout -eq "mother-repo-root") { $Root } else { Join-Path $Root $groot }

$domains = @()
$inDomains = $false
foreach ($line in (Get-Content $ManifestPath)) {
    if ($line -match '^\s*enabled_domains:\s*$') { $inDomains = $true; continue }
    if ($inDomains) {
        if ($line -match '^\s*-\s+(.+)$') { $domains += $Matches[1].Trim() }
        elseif ($line -match '^\S') { $inDomains = $false }
    }
}
if ($domains.Count -eq 0) { $domains = @("coding-standards") }

$cursorDir = Join-Path $Root ".cursor\rules"
$copilotPath = Join-Path $Root ".github\copilot-instructions.md"
$sections = @(
    "# Copilot instructions (generated)",
    "Regenerate: scripts/export-governance-rules.ps1",
    ""
)

$exported = 0
foreach ($domain in $domains) {
    $path = Join-Path $grootPath "domains\$domain.md"
    if (-not (Test-Path $path)) {
        $path = Join-Path $grootPath "domains\$domain\index.md"
    }
    if (-not (Test-Path $path)) {
        Write-Warning "SKIP $domain"
        continue
    }
    $body = Get-Content $path -Raw
    $slug = ($domain -replace '[^a-zA-Z0-9]+', '-').ToLower().Trim('-')
    $rule = @"
---
description: Governance domain — $domain
alwaysApply: false
globs:
  - "**/*"
---

$($body.Trim())

"@
    $ruleFile = Join-Path $cursorDir "governance-$slug.mdc"
    if ($DryRun) { Write-Host "Would write $ruleFile" }
    else {
        New-Item -ItemType Directory -Force -Path $cursorDir | Out-Null
        Set-Content -Path $ruleFile -Value $rule -Encoding UTF8
        Write-Host "Wrote $ruleFile"
    }
    $sections += "### $domain", "", $body.Substring(0, [Math]::Min(800, $body.Length)), ""
    $exported++
}

$copilot = ($sections -join "`n")
if ($copilot.Length -gt 4000) {
    $copilot = $copilot.Substring(0, 3900) + "`n`n<!-- TRUNCATED: see .cursor/rules/governance-*.mdc -->"
}

if ($DryRun) { Write-Host "Would write $copilotPath ($($copilot.Length) bytes)" }
else {
    New-Item -ItemType Directory -Force -Path (Split-Path $copilotPath) | Out-Null
    Set-Content -Path $copilotPath -Value $copilot -Encoding UTF8
    Write-Host "Wrote $copilotPath"
}
Write-Host "Exported $exported domain(s)"
