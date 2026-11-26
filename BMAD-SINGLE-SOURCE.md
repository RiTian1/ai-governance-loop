# BMAD 单源策略

## 现状（v6.10 起）

上游布局已变：**技能全文直接安装在 `.claude/skills/bmad-*/`**（SKILL.md + 附属 csv/模板），
`_bmad/` 仅保留配置层（`core/config.yaml`、`bmm/config.yaml`、`config.toml`、
`custom/` 覆盖层、`scripts/resolve_config.py`、`_config/` 清单）。

```
_bmad/                      ← 配置单源（语言、路径、agent 描述符覆盖）
  custom/config.toml        ← 持久 pin（安装器永不覆盖）：中文输出约束在此
  governance-bridge.yaml    ← 治理桥接（含输出语言约束，升级时手动保留）
.claude/skills/bmad-*/      ← 技能正文（上游安装产物，升级时整体替换）
.agents/skills/             ← 镜像（scripts/sync-agent-skills.py --prune 生成）
```

## 编辑流程

1. **配置/语言/agent 描述符**：改 `_bmad/custom/config.toml`（团队级）——不要直接改
   `_bmad/config.toml`（安装器再生成会覆盖）
2. **技能正文定制**：用 `bmad-customize` 技能生成 override，勿直接改安装产物
3. 改动后运行 `python scripts/sync-agent-skills.py --prune` 刷新 `.agents/skills` 镜像

## 历史提示

- v6.7 及以前为 "`_bmad/` canonical + `.claude/skills` 薄壳（sync-bmad-skills.py 生成）"；
  该脚本对 v6.10 布局已不适用，仅为旧版参考保留。
- `_bmad/_config/skill-manifest.csv` 的 `path` 字段仍指向旧 canonical 路径，属上游遗留。

## 与治理框架

- `project-governance.yaml` → `frameworks.bmad.enabled: false`（默认）
- 开启 BMAD 后仍通过 OpenSpec 归档实现产出物
- **输出语言**：communication_language / document_output_language = 中文（简体），
  三处同源（core/bmm config.yaml + custom/config.toml），详见 `_bmad/governance-bridge.yaml`

## v6.10 迁移提示

| 旧技能 | 新技能 |
|--------|--------|
| `bmad-create-architecture` | `bmad-architecture`（弃用壳保留至 v7） |
| `bmad-create-ux-design` | `bmad-ux` |
| `bmad-create-prd` / `edit` / `validate` | `bmad-prd`（create / update / validate 意图） |
| `bmad-distillator`、`bmad-investigate` | 已移除 |
| — | `bmad-spec`、`bmad-forge-idea`、`bmad-dev-auto`（新增） |

同步上游：`powershell -File scripts/sync-upstream.ps1`
