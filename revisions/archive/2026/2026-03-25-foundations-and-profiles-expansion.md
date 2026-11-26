---
revision_id: rev-2026-03-25-foundations-and-profiles-expansion
title: Foundations 与 Profiles 扩展
status: merged
linked_stories: []
linked_changes: []
prd_refs: []
introduces_rules: []
modifies_rules: []
removes_rules: []
affected_baselines:
  - foundations/
  - profiles/
  - 00-index.yaml
commits: []
created_at: 2026-03-25
created_by: legacy
reviewed_by: null
reviewed_at: null
merged_at: 2026-03-25
archived_at: 2026-05-26
trigger_summary: |
  扩大可组合约束覆盖；引入数学/建模/形式化基础方法论。
---

# 治理修订单

## 1. 修订标题

新增基础方法论层 `foundations/` 与项目类型组合层 `profiles/`，把数学原语、建模方法论和工匠型设计约束显式纳入治理基线。

## 2. 触发来源

- 现有治理骨架已经具备工程领域与流程治理，但缺少“上位方法论层”。
- 用户要求将离散数学、概率论、统计学、线性代数、群论、图论、高等代数等逻辑原语所沉淀的方法论与经验论纳入项目级约束。

## 3. 问题现象

- 现有目录主要是工程流程与专业领域约束，基础学科与形式化思维仍是隐式存在。
- 缺少面向桌面、后端、嵌入式、ML 等项目类型的一揽子组合入口。

## 4. 为什么上升为项目级规则

- 这些方法论不依赖某个具体业务领域，但会持续影响建模、抽象、验证、优化与实验设计质量。
- 如果不显式进入基线，后续会再次退回“凭感觉设计”“凭经验验证”的工作方式。

## 5. 适用范围

- 通用软件项目
- 软硬件协同项目
- 算法、建模、仿真、机器学习项目

## 6. 影响文档

- `docs/governance/00-index.md`
- `docs/governance/00-index.yaml`
- `docs/governance/foundations/*`
- `docs/governance/profiles/*`
- `docs/governance/templates/*`

## 7. 影响实现

- 无直接业务代码影响。
- 影响后续架构设计、实验设计、评审、文档编写和验证口径。

## 8. 影响测试

- 要求后续在需要时显式区分结构证明、统计证明、数值稳定性证明、实验设计证明。

## 9. 证据与样例

- 当前目录能表达工程治理，但还不能显式回答“不变量如何建模”“随机性如何验证”“线性空间与图结构如何约束设计”等基础问题。

## 10. 修订前

- 目录以工程领域和流程治理为主。

## 11. 修订后

- 增加 `foundations/` 用于承载上位方法论。
- 增加 `profiles/` 用于承载项目类型组合约束。

## 12. 迁移要求

- 后续讨论方法论、建模和项目类型时，优先从 `foundations/` 与 `profiles/` 进入，而不是把此类规则继续塞回 `domains/`。

## 13. 生效状态

已采纳并落地到治理基线。
