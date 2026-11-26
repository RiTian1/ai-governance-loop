# 项目激活模型

本文档定义如何把通用治理母版激活为当前仓库的现行基线。

## 1. 三层结构

- 母版层：通用治理文档（业务项目通常在 `docs/governance/`；母版维护仓见 `LAYOUT.md` 的 `mother-repo-root`）
- 激活层：`project-governance.yaml`，负责声明 `governance_layout`、`governance_root` 与启用的组合
- 项目专属层：`docs/project-rules.md` 与现有模块文档，负责承接 brownfield 现实

### 1.1 布局模式（`governance_layout`）

| 值 | `governance_root` | 说明 |
|----|-------------------|------|
| `mother-repo-root` | `.` | 治理母版仓库自身 |
| `docs-governance-subtree` | `docs/governance` | 复制母版到业务仓库后的推荐布局 |

详见 `LAYOUT.md`。`active_baseline` 中须同时声明 `engineering_principles` 与 `phase_governance`（对应 `02-engineering-principles.md` 与 `02-phase-governance.md`）。

## 2. 当前项目状态

- 当前仓库属于 `brownfield`
- 已有历史代码、第三方源码和模块文档并存
- 治理基线用于建立统一入口，不用于一次性重写历史结构

## 3. Agent 启动顺序

1. `AGENTS.md`
2. `project-governance.yaml`
3. `{governance_root}/00-index.yaml`
4. `{governance_root}/profiles/<profile>.md`
5. `enabled_foundations`
6. `enabled_domains`
7. `docs/project-rules.md`

## 4. authority map 的用途

authority map 用于声明：

- 当前仓库里哪些治理文档说了算
- 哪些既有项目文档仍然有效
- 哪些规则只是局部覆盖，而不是全局默认

## 5. 完成判定

只要以下条件同时满足，即可视为激活层已落地：

- 存在 `project-governance.yaml`
- 存在 `AGENTS.md`
- `docs/governance/00-index.yaml` 能指向启用的治理资产
- 局部规则与 brownfield 说明已明确
