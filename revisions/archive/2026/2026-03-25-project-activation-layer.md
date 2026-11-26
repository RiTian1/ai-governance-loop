---
revision_id: rev-2026-03-25-project-activation-layer
title: 项目激活层
status: merged
linked_stories: []
linked_changes: []
prd_refs: []
introduces_rules: []
modifies_rules: []
removes_rules: []
affected_baselines:
  - 08-project-activation-model.md
  - project-governance.yaml
  - 07-bootstrap-and-adoption-guide.md
commits: []
created_at: 2026-03-25
created_by: legacy
reviewed_by: null
reviewed_at: null
merged_at: 2026-03-25
archived_at: 2026-05-26
trigger_summary: |
  agent 无法判定项目启用的规则子集；新增 project-governance.yaml 与激活模型。
---

# 治理修订单

## 1. 修订标题

新增项目激活层，使 AI agent 能基于 `project-governance.yaml` 自动加载当前项目启用的全局基线。

## 2. 触发来源

- 用户明确要求这套治理基线既适配空项目，也适配成熟项目。
- 用户要求 AI agent 能根据项目治理目录自动找到对应全局基线约束。

## 3. 问题现象

- 仅有母版索引还不足以表达“当前项目到底启用了哪些规则”。
- 成熟项目如果没有 authority map，agent 无法判断母版与本地历史规则谁优先。

## 4. 为什么上升为项目级规则

- 这是治理母版真正可落地到多项目、多阶段场景的关键层。
- 没有激活层，agent 只能猜或全量加载，都会增加错误率和上下文成本。

## 5. 适用范围

- greenfield 项目
- brownfield 项目
- legacy-modernization 项目

## 6. 影响文档

- `docs/governance/07-bootstrap-and-adoption-guide.md`
- `docs/governance/08-project-activation-model.md`
- `docs/governance/00-index.md`
- `docs/governance/00-index.yaml`
- 新增相关模板

## 7. 影响实现

- 无直接业务代码影响。
- 影响 agent 启动顺序、项目治理装配方式与成熟项目迁移策略。

## 8. 影响测试

- 影响 agent 是否能稳定加载正确基线与 authority map。

## 9. 证据与样例

- 母版可安装不等于 agent 可正确激活。
- 需要机器可判定文件来表达“当前项目启用了哪些约束”。

## 10. 修订前

- 具备母版与 bootstrap 指南，但缺少项目激活清单。

## 11. 修订后

- 增加 `08-project-activation-model.md`
- 增加 `project-governance` 清单模板
- 增加 authority map 与 AGENTS 接入模板

## 12. 迁移要求

- 新项目默认从 `project-governance.yaml` 启动
- 成熟项目必须显式维护 authority map

## 13. 生效状态

已采纳并落地到治理基线。
