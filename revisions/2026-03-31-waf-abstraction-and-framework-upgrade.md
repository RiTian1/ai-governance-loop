---
revision_id: rev-2026-03-31-waf-abstraction-and-framework-upgrade
title: WAF 抽象化与通用 AI 智能体框架升级
status: candidate
linked_stories: []
linked_changes: []
prd_refs: []
introduces_rules: []
modifies_rules: []
removes_rules: []
affected_baselines:
  - profiles/
  - frameworks/
  - .claude/skills/
commits: []
created_at: 2026-03-31
created_by: legacy
reviewed_by: null
reviewed_at: null
merged_at: null
archived_at: null
trigger_summary: |
  通用化阶段治理与平台约束；移除 WAF 专用内容；整合 OpenSpec/BMAD/Superpowers 三框架。
---

# 治理修订单

## 1. 修订标题

治理基线 WAF 抽象化与通用 AI 智能体框架升级

## 2. 触发来源

- 用户要求将当前 WAF 专用治理仓库改造为通用 AI 辅助开发框架
- 需要支持任意项目类型的 0→1 开发和 1→2 重构
- 需要整合 OpenSpec、BMAD、Superpowers 三大框架

## 3. 问题现象

- 治理基线中混入了 WAF 项目专用内容（nginx/apache/ylwaf/ModSecurity 引用）
- 142+ 代理库中约 85% 对独立开发者无实际价值
- 缺少统一的多框架整合架构
- 缺少通用项目激活流程

## 4. 为什么上升为项目级规则

- 治理基线如果绑定特定项目，就失去了母版可复用性
- 框架整合方式如果不标准化，每个新项目都要重新配置
- 代理选择如果没有分层指引，142+ 代理反而变成噪音

## 5. 变更清单

### 5.1 WAF 内容清理（8 个文件编辑 + 1 个文件删除）

| 文件 | 操作 | 变更内容 |
|------|------|---------|
| `domains/soft-waf-platform-adaptation.md` | 删除 | 纯 WAF 专用文件 |
| `00-index.md` | 编辑 | 删除 7 条 WAF 路由，通用化安全语义措辞 |
| `00-index.yaml` | 编辑 | 删除 5 个 WAF 条目 |
| `01-charter.md` | 编辑 | 通用化定位和产品边界描述 |
| `02-phase-governance.md` | 编辑 | 通用化技术可行性分析目标和平台适配约束 |
| `03-document-workflow.md` | 编辑 | 实现主体从硬编码路径改为占位符 |
| `04-verification-policy.md` | 编辑 | 仓库级最小要求从硬编码路径改为占位符 |
| `domains/security.md` | 编辑 | 通用化安全设计要求和验证重点措辞 |
| `profiles/native-security-runtime.md` | 编辑 | 通用化适用范围，删除项目专用编码要求 |

### 5.2 代理系统重构

- 从 142+ 代理中精选 22 个，按 core/specialists/design/meta 分层
- 完整代理库移至 `_reference/agency-agents-main/` 保留参考
- 新增 `profiles/solo-developer.md` 项目类型

### 5.3 三大框架整合

- OpenSpec: 增强 `config.yaml` 加入治理上下文和规则
- BMAD: 完整安装 + `governance-bridge.yaml` 三方映射
- Superpowers: 安装核心技能包

### 5.4 框架入口与激活

- 新增 `CLAUDE.md` 框架入口
- 新增 `README.md` 框架总览
- 新增 `scripts/bootstrap.sh` 项目初始化脚本

## 6. 影响面

- 所有治理文档的通用性提升
- 代理系统从散装库变为精选分层体系
- 新增三框架并存的命名空间隔离机制
- 项目激活从手动流程变为脚本辅助

## 7. 验证要点

- `grep -ri "waf\|modsecurity\|ylwaf"` 在治理文档中应返回零结果
- 22 个代理文件完整可读
- OpenSpec、BMAD、Superpowers 技能命名空间无冲突
- `bootstrap.sh` 可执行
