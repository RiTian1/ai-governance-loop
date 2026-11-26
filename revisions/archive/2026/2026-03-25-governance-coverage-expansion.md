---
revision_id: rev-2026-03-25-governance-coverage-expansion
title: 治理覆盖扩展
status: merged
linked_stories: []
linked_changes: []
prd_refs: []
introduces_rules: []
modifies_rules: []
removes_rules: []
affected_baselines:
  - domains/
  - templates/
commits: []
created_at: 2026-03-25
created_by: legacy
reviewed_by: null
reviewed_at: null
merged_at: 2026-03-25
archived_at: 2026-05-26
trigger_summary: |
  补齐安全 / CI/CD / 运维 / 可观测性 / 代码规范 / 文档与 API / 开源合规 / 硬件开发的领域与模板覆盖。
---

# 治理修订单

## 1. 修订标题

扩展通用治理骨架覆盖范围，补齐安全、CI/CD、发布运维、可观测性、代码规范、文档/API 规范、开源合规与硬件开发基线。

## 2. 触发来源

- 在审查 `docs/governance/` 现有目录时发现其主要覆盖需求、设计、验证和 AI 协作前半段。
- 用户明确要求治理骨架尽可能覆盖大多数软、硬件开发场景，并包含代码规范、参考链接、文档规范、API 标注规范、开源规范等横切约束。

## 3. 问题现象

- 当前目录缺少 DevOps / CI、发布运维、可观测性、安全工程等工程后半段基线。
- 缺少代码规范、文档规范、API 标注规范、开源治理与硬件开发这类跨业务领域通用约束。
- 模板目录缺少威胁建模、CI 流水线、发布检查、事故复盘、API 文档等复用模板。

## 4. 为什么上升为项目级规则

- 这些约束不依赖具体业务，属于工程组织能力和长期质量基线。
- 如果不进入项目级治理，会导致不同 change、不同仓库、不同代理会话反复重新约定。
- 这些约束直接影响实施、验证、发布、审计与归档闭环。

## 5. 适用范围

- 通用软件项目
- 桌面端、Web、服务端、CLI、平台型项目
- 嵌入式、驱动、固件、软硬件协同项目

## 6. 影响文档

- `docs/governance/00-index.md`
- `docs/governance/00-index.yaml`
- `docs/governance/01-charter.md`
- `docs/governance/03-document-workflow.md`
- `docs/governance/04-verification-policy.md`
- `docs/governance/05-ai-collaboration-policy.md`
- `docs/governance/domains/*`
- `docs/governance/templates/*`

## 7. 影响实现

- 无直接业务代码影响。
- 会影响后续 OpenSpec、PRD、设计、测试计划、CI、发布和审计工件的写法。

## 8. 影响测试

- 后续测试计划需要显式覆盖安全、发布、可观测性、流水线门禁和合规验证。
- 安全审计、发布检查、事故复盘等将进入正式模板。

## 9. 证据与样例

- 当前 `docs/governance/` 缺少上述领域文件。
- 当前机器索引无法为 AI / 代理定位这些领域基线。

## 10. 修订前

- 目录覆盖研发治理前半段较完整。
- 工程后半段和横切规范覆盖不足。

## 11. 修订后

- 增加相关领域文档与模板。
- 增加机器索引与人读索引入口。
- 在主文档中补齐对这些领域的边界说明。

## 12. 迁移要求

- 后续涉及安全、CI/CD、发布、开源、硬件、API 文档等话题时，默认优先从新索引入口加载对应文档。
- 若旧项目已有对应规范，可在新目录下挂接或映射，而不是平行重复。

## 13. 生效状态

已采纳并落地到治理基线。
