# 治理索引

本目录是当前仓库的治理入口。路径解析见 `LAYOUT.md`；母版仓 `governance_root` 为仓库根目录。

## 建议读取顺序

1. `project-governance.yaml`
2. `LAYOUT.md`
3. `01-charter.md`
4. `02-engineering-principles.md`（工程原则）
5. `02-phase-governance.md`（阶段治理）
6. `03-document-workflow.md`
7. `04-verification-policy.md`
8. `05-ai-collaboration-policy.md`
9. `08-project-activation-model.md`
10. `profiles/<your-profile>.md`
11. `enabled` 的 `foundations/`、`domains/`
12. `projects/`（项目轴）、`business-references/`（业务参考轴）—— 只在任务落在具体产品或现场时读
13. `docs/project-rules.md`（业务项目）

## 机器索引

- 人读：本文件
- Agent：`00-index.yaml`（含 `when_to_read` 阶段标签）

## 最小加载建议

- 任意阶段：先读 `project-governance.yaml`，勿全量加载所有 domain
- 阶段准入与回注： `02-phase-governance.md`
- 验证与证据： `04-verification-policy.md`
- 经验晋升： `revisions/WORKFLOW.md`
- OpenSpec 归档： `openspec/ARCHIVE-CHECKLIST.md`
- NAS GitLab 项目建仓、连接与迁移：按需读 projects/NAS-GITLAB-REPOSITORIES.md

## 三条轴（别混）

| 轴 | 树 | 回答的问题 | 粒度 |
|---|---|---|---|
| **关切轴** | `domains/` | 这件事该怎么做（运维/安全/前端…） | 1 套规则，全部项目共用 |
| **项目轴** | `projects/` | 这是哪个产品、真源在哪、去哪看它的历史 | 一个产品实例一份 |
| **业务参考轴** | `business-references/` | 产品在什么业务场景/现场被用（客户/靶标/竞品） | 一份参考**可关联多个项目** |

项目轴与业务参考轴同级、互相反查：权威关联写在业务参考的 `related_projects`，项目侧只放反向引用。
入口：[`projects/index.md`](projects/index.md)、[`business-references/index.md`](business-references/index.md)。

## 本机实验台

Mac 上的实验事实不写进上面的治理正文，集中在 `lab/`：`lab/README.md`、`lab/machines.md`、`lab/ops-facts.md`、`lab/test-method.md`。口令只在 `lab/secrets/`，该目录不入库。

## 目录说明（母版仓）

```text
./
  AGENTS.md                 # 短路由（<150 行）
  project-governance.yaml   # 激活清单
  LAYOUT.md                 # 母版 vs docs/governance 布局
  00-index.md / 00-index.yaml
  01-charter.md … 09-*.md
  domains/                  # 关切轴（能力/领域）
  projects/                 # 项目轴（产品实例台账）
  business-references/      # 业务参考轴（现场/靶标/竞品，可关联多个项目）
  profiles/ foundations/ revisions/ templates/
  agents/                   # 代理（仓库根）
  openspec/                 # 变更工作流
```

已集成到业务项目时，上述主文档通常位于 `docs/governance/`，见 `LAYOUT.md`。
