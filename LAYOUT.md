# 治理目录布局说明

本文件说明**母版仓库**与**已集成项目**的路径差异。Agent 必须先读 `project-governance.yaml` 中的 `governance_layout`，再解析 `00-index.yaml` 与各文档中的路径。

## 两种布局

| 模式 | `governance_layout` | 治理主文档位置 | 典型场景 |
|------|---------------------|----------------|----------|
| 母版仓根目录 | `mother-repo-root` | 仓库根目录（本仓库） | `governance` 母版维护、框架开发 |
| 项目子树 | `docs-governance-subtree` | `docs/governance/` | 复制母版到业务仓库后的标准布局 |

## 路径解析规则

1. 读取 `project-governance.yaml` → 确认 `governance_layout` 与 `governance_root`（默认 `.` 或 `docs/governance`）。
2. 读取 `{governance_root}/00-index.yaml`（母版仓为根目录的 `00-index.yaml`）。
3. 索引中的 `path` 均相对于 `governance_root`。
4. `profiles/`、`domains/`、`foundations/`、`revisions/`、`templates/`、`agents/` 在母版仓位于**仓库根**；集成到业务项目时，随 `docs/governance/` 一并复制或按 bootstrap 裁剪。
5. `projects/` 与 `business-references/` 是**顶层树**（不在 `domains/` 下），解析方式与 `domains/` 同级：`<governance_root>/<tree>/index.md` 与 `<tree>/_index.yaml`。

RSI 对话回溯索引位于 rsi/，只存 CLI 原生 session 的派生摘要与定位；它不是下面三条实体分类轴，也不保存原文。

## 三条轴与三条顶层树

| 轴 | 顶层树 | 语义 | 与其它轴的关系 |
|----|--------|------|----------------|
| 关切轴 | `domains/` | 能力/领域约束（运维、安全、前端…） | 全部项目共用；与项目无关 |
| 项目轴 | `projects/` | 产品实例台账（身份 / 真源 / 入口） | 一个项目可被多个业务参考关联 |
| 业务参考轴 | `business-references/` | 客户现场 / 靶标 / 竞品等场景 | 与 `projects/` **同级**；`related_projects` 多值 |

> 只有 `domains/` 是「多少能力就多少域」。`projects/` 与 `business-references/` 是**登记册**，条目随后续产品与现场增减而堆叠。
> 三棵树都走三件套协议（`index.md` / `_index.yaml` / `_summary.yaml`），`levels.L1` 注册，`00-index.yaml` 索引。


## 母版仓（当前仓库）

- `governance_layout: mother-repo-root`
- `governance_root: .`
- 主文档：`01-charter.md` … `09-securitybuddy-development.md`（根目录）
- 机器索引：根目录 `00-index.yaml`
- 代理与技能：`agents/`、`.claude/skills/`（仓库根，不随 `docs/governance` 复制）

## 已集成项目（推荐）

- `governance_layout: docs-governance-subtree`
- `governance_root: docs/governance`
- 从母版复制 `00-index.*`、`01`–`08`、`profiles/`、`domains/`、`foundations/`、`revisions/`、`templates/` 到 `docs/governance/`
- 项目树按需：`projects/` 只放**本项目自己**那一条（把母版的多项目台账裁成单条）；`business-references/` 只放与本项目相关的参考
- 项目根保留 `project-governance.yaml` 与简短 `AGENTS.md`

## 02 文档契约（避免混淆）

| 键名（manifest） | 文件 | 用途 |
|------------------|------|------|
| `engineering_principles` | `02-engineering-principles.md` | 通用工程与架构原则 |
| `phase_governance` | `02-phase-governance.md` | 阶段准入、产出物、回注纪律 |

二者并存，**不可**再用单一 `engineering` 键指向其中一份。

## 工具链（P2）

| 脚本 | 用途 |
|------|------|
| `scripts/export-governance-rules.py` / `.ps1` | 生成 `.cursor/rules/`、`.github/copilot-instructions.md` |
| `scripts/check-agent-evals.py` | Eval 通过率门禁 |
| `scripts/sync-bmad-skills.py` / `.ps1` | BMAD 薄壳同步 + `--prune` |

## 采用后自检

- [ ] `project-governance.yaml` 存在且 `governance_layout` 正确
- [ ] `AGENTS.md` 不超过约 150 行（路由表）
- [ ] `00-index.yaml` 中每条 `path` 在 `governance_root` 下存在
- [ ] bootstrap 默认 `frameworks.bmad.enabled: false`（大项目再开启）
- [ ] 已运行 `export-governance-rules`（若使用 Cursor/Copilot）
- [ ] 启用 MCP 时已配置 `mcp_connectors` 并加载 `domains/agent-tooling-mcp.md`
