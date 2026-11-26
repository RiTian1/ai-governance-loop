---
revision_id: rev-2026-03-25-bootstrap-adoption-layer
title: 母版初始化与采用层
status: merged
linked_stories: []
linked_changes: []
prd_refs: []
introduces_rules: []
modifies_rules: []
removes_rules: []
affected_baselines:
  - 07-bootstrap-and-adoption-guide.md
  - docs/governance/INTEGRATION-GUIDE.md
commits: []
created_at: 2026-03-25
created_by: legacy
reviewed_by: null
reviewed_at: null
merged_at: 2026-03-25
archived_at: 2026-05-26
trigger_summary: |
  新项目缺少安装与迁移正式说明；治理母版需要可直接采用为下游项目装配。
---

# 治理修订单

## 1. 修订标题

为通用治理骨架新增“母版初始化与采用层”，使其可直接作为新项目安装母版使用。

## 2. 触发来源

- 当前治理骨架已具备较完整结构，但缺少“如何安装到新项目”的正式说明。
- 用户要求继续推进，使其成为可直接复用的母版。

## 3. 问题现象

- 当前目录适合阅读和扩展，但对新项目采用者来说还缺少安装、裁剪、迁移和完成判定说明。
- 缺少项目初始化检查清单与装配单模板。

## 4. 为什么上升为项目级规则

- 采用方式如果不标准化，治理骨架很容易退化成“只能本仓库用、换仓库就要重新解释”的知识资产。
- 母版可安装性本身属于跨项目复用价值。

## 5. 适用范围

- 任何希望复用本治理骨架的新项目
- 任何从旧平行规范迁移到索引化治理结构的项目

## 6. 影响文档

- `docs/governance/00-index.md`
- `docs/governance/00-index.yaml`
- `docs/governance/07-bootstrap-and-adoption-guide.md`
- `docs/governance/templates/project-bootstrap-checklist-template.md`
- `docs/governance/templates/baseline-selection-template.md`
- `docs/governance/templates/governance-adoption-plan-template.md`

## 7. 影响实现

- 无直接业务代码影响。
- 会影响后续新项目如何采用本治理母版。

## 8. 影响测试

- 新项目初始化过程将具备更明确的治理完成判定。

## 9. 证据与样例

- 当前目录缺少正式“安装与迁移”入口。
- 复制型使用方式若没有装配单与检查清单，容易引入文档冗余和治理漂移。

## 10. 修订前

- 骨架完整，但采用路径不完整。

## 11. 修订后

- 提供初始化指南、迁移策略、检查清单和装配单模板。

## 12. 迁移要求

- 后续复制到新项目时，默认从 `07-bootstrap-and-adoption-guide.md` 开始。

## 13. 生效状态

已采纳并落地到治理基线。
