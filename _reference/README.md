# Reference Bundle (Optional)

This repository keeps `_reference/` minimal by default to avoid committing large, duplicated content.

If you need the full Agency reference bundle, run one of the scripts below:

- Bash/macOS/Linux: `./scripts/fetch-reference.sh`
- Windows PowerShell: `./scripts/fetch-reference.ps1`

By default, scripts download:

- `https://github.com/msitarzewski/agency-agents.git`
  （原 `The-Agency-Agents/agency-agents` 已迁移至该地址，2026-07 核实；147 agents / 12 divisions）

Target path:

- `_reference/agency-agents-main`

You can override repo URL with:

- Bash: `AGENCY_AGENTS_REPO=<repo-url> ./scripts/fetch-reference.sh`
- PowerShell: `./scripts/fetch-reference.ps1 -RepoUrl <repo-url>`