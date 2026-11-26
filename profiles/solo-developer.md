# 独立开发者 Profile

适用于独立开发者（或小团队）使用 AI 辅助工具进行 0→1 开发或 1→2 重构的项目。

## 1. 默认组合

- foundations：架构与设计工匠精神、失败与可靠性思维、离散数学与结构思维
- domains：编码标准、后端、前端、DevOps/CI、自动化、文档与 API、Agent 工具与 MCP（`agent-tooling-mcp`）
- agents：core/ 全部（6 个），specialists/ 按项目类型选择

## 2. 默认重点

- 架构决策先于实现
- 验证证据而非口头确认
- 变更可追踪、可回溯
- 文档与代码同步更新
- 反幻觉 QA 机制

## 3. 推荐工作流

- 小变更 / 快速原型：直接 `/opsx:ff` 快进生成全部产出物
- 新功能开发：`/opsx:explore` → `/opsx:new` → `/opsx:continue` → `/opsx:apply`
- 大型重构：BMAD 全流程 + OpenSpec 记录
- 代码审查：激活 `code-reviewer` 代理或 BMAD code-review 技能

## 4. 代理激活建议

| 项目类型 | 核心代理 | 按需专家 |
|---------|---------|---------|
| Web 全栈 | 全部 core/ | backend-architect, frontend-developer, devops-automator |
| API 服务 | software-architect, senior-developer, code-reviewer, evidence-collector | backend-architect, api-tester, database-optimizer |
| 移动应用 | 全部 core/ | mobile-app-builder, frontend-developer, ui-designer |
| AI 应用 | software-architect, senior-developer, evidence-collector | ai-engineer, backend-architect, performance-benchmarker |
| 桌面应用 | 全部 core/ | frontend-developer, ux-architect, performance-benchmarker |

## 5. 治理精简建议

独立开发者可以跳过的治理步骤（降级验证）：
- 形式化的 PRD 可简化为 OpenSpec proposal
- 方案设计可简化为 OpenSpec design + ADR
- 详细设计可合并到 tasks 中
- 测试集成可使用 evidence-collector 自动验证

独立开发者**不应跳过**的治理步骤：
- 架构决策记录（ADR）
- 验证证据收集
- 变更归档（保留决策上下文）
