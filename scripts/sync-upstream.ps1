# Sync OpenSpec + BMAD upstream into governance mother repo
# 版本 pin 见 UPSTREAM-VERSIONS.yaml；升级后必须重做的本地化步骤见文末提示
param(
    [switch]$SkipBmad,
    [switch]$SkipOpenSpec,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Upstream = Join-Path $Root "_upstream"

$OpenSpecVersion = "1.5.0"
$BmadTag = "v6.10.0"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $Upstream | Out-Null }

# --- OpenSpec ---
if (-not $SkipOpenSpec) {
    Write-Step "OpenSpec @$OpenSpecVersion"
    $configPath = Join-Path $env:APPDATA "openspec\config.json"
    $workflows = @(
        "propose", "explore", "new", "continue", "apply", "ff", "sync",
        "archive", "bulk-archive", "verify", "onboard"
    )
    if (-not $DryRun) {
        $cfg = @{
            featureFlags = @{}
            profile      = "custom"
            delivery     = "both"
            workflows    = $workflows
        }
        if (Test-Path $configPath) {
            $existing = Get-Content $configPath -Raw | ConvertFrom-Json
            $cfg.telemetry = $existing.telemetry
        }
        $cfg | ConvertTo-Json -Depth 5 | Set-Content $configPath -Encoding UTF8
        Set-Location $Root
        npx --yes "@fission-ai/openspec@$OpenSpecVersion" update --force | Write-Host
        Write-Host ""
        Write-Host "⚠ update --force 已用英文原文覆盖 opsx 命令与 openspec-* skills；" -ForegroundColor Yellow
        Write-Host "  本仓要求中文版（见 UPSTREAM-VERSIONS.yaml openspec.localization），需重做中文化。" -ForegroundColor Yellow
    } else {
        Write-Host "Would update global config and run: npx openspec update --force"
    }
}

# --- BMAD ---
if (-not $SkipBmad) {
    Write-Step "BMAD $BmadTag"
    $bmadRepo = Join-Path $Upstream "BMAD-METHOD"
    $staging = Join-Path $Upstream "bmad-staging"
    $bridgeBackup = Join-Path $Root "_bmad-governance-bridge.yaml.bak"
    $customBackup = Join-Path $Root "_bmad-custom.bak"

    if (-not $DryRun) {
        if (-not (Test-Path $bmadRepo)) {
            git clone --depth 1 --branch $BmadTag https://github.com/bmad-code-org/BMAD-METHOD $bmadRepo
        } else {
            git -C $bmadRepo fetch --depth 1 origin tag $BmadTag
            git -C $bmadRepo checkout $BmadTag
        }
        if (-not (Test-Path (Join-Path $bmadRepo "node_modules"))) {
            Set-Location $bmadRepo
            npm install --silent | Out-Null
        }
        if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $staging | Out-Null
        $cli = Join-Path $bmadRepo "tools\installer\bmad-cli.js"
        node $cli install --yes --tools claude-code --modules core,bmm `
            --directory $staging --action install | Write-Host

        # v6.10：技能全文在 .claude/skills，_bmad 仅配置层
        $bridge = Join-Path $Root "_bmad\governance-bridge.yaml"
        $custom = Join-Path $Root "_bmad\custom"
        if (Test-Path $bridge) { Copy-Item $bridge $bridgeBackup -Force }
        if (Test-Path $custom) {
            if (Test-Path $customBackup) { Remove-Item $customBackup -Recurse -Force }
            Copy-Item $custom $customBackup -Recurse -Force
        }
        Remove-Item (Join-Path $Root "_bmad") -Recurse -Force
        Copy-Item (Join-Path $staging "_bmad") (Join-Path $Root "_bmad") -Recurse -Force
        if (Test-Path $bridgeBackup) {
            Copy-Item $bridgeBackup $bridge -Force
            Remove-Item $bridgeBackup -Force
        }
        if (Test-Path $customBackup) {
            Remove-Item (Join-Path $Root "_bmad\custom") -Recurse -Force -ErrorAction SilentlyContinue
            Copy-Item $customBackup (Join-Path $Root "_bmad\custom") -Recurse -Force
            Remove-Item $customBackup -Recurse -Force
        }

        # 替换 .claude/skills 下的 bmad-* 技能（v6.10 起为全文安装产物）
        Get-ChildItem (Join-Path $Root ".claude\skills") -Directory |
            Where-Object { $_.Name -like "bmad-*" } |
            ForEach-Object { Remove-Item $_.FullName -Recurse -Force }
        Get-ChildItem (Join-Path $staging ".claude\skills") -Directory |
            ForEach-Object {
                Copy-Item $_.FullName (Join-Path $Root ".claude\skills\$($_.Name)") -Recurse -Force
            }
        Write-Host ""
        Write-Host "⚠ 升级后需人工恢复中文输出配置：_bmad/core/config.yaml 与 _bmad/bmm/config.yaml 的" -ForegroundColor Yellow
        Write-Host "  communication_language / document_output_language = 中文（简体）；" -ForegroundColor Yellow
        Write-Host "  持久 pin 已由 _bmad/custom/config.toml 保留（本脚本已备份恢复）。" -ForegroundColor Yellow
    } else {
        Write-Host "Would install BMAD to _upstream/bmad-staging, swap _bmad/ (keep bridge+custom), replace .claude/skills/bmad-*"
    }

    Write-Step "Agent skills mirror"
    if (-not $DryRun) {
        Set-Location $Root
        python (Join-Path $PSScriptRoot "sync-agent-skills.py") --prune | Write-Host
    }
}

Write-Step "Done"
Write-Host "Versions: UPSTREAM-VERSIONS.yaml"
Write-Host "Preserve manually: openspec-bootstrap SKILL, openspec/config.yaml rules, _bmad/governance-bridge.yaml,"
Write-Host "  _bmad/custom/config.toml (中文 pin), opsx 命令/openspec-* skills 中文化正文, agents/README.md 输出语言约束"
