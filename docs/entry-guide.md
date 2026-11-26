# 入口扩展指南（按需读取，不常驻）

> 从 `CLAUDE.md` 下沉的说明性内容（tool.r8 常驻面预算）。需要选工作流 / 选代理 / 快速开始时再读本文件。

## 代理 vs 技能：什么时候用什么？

### 代理（agents/）— 角色模式

代理是**身份** — 让 AI 以特定专家的视角和优先级工作。

| 用法 | 示例 |
|------|------|
| 需要持续的角色视角 | "请以 software-architect 的角色审查这个设计" |
| 需要专业知识判断 | "以 security-engineer 的角色分析这个认证流程" |
| 需要多角色协作 | 先 architect 设计 → 再 senior-developer 实现 → 最后 qa-verifier 验证 |

### 技能（skills/）— 操作流程

技能是**动作** — 执行具体的、有明确输入输出的工作流。

| 用法 | 示例 |
|------|------|
| OpenSpec 变更管理 | `/opsx:new` 创建变更、`/opsx:apply` 实施任务 |
| BMAD 生命周期 | `bmad-create-prd` 创建 PRD、`bmad-create-architecture` |
| 项目初始化 | `/opsx:bootstrap` 智能分析并推荐配置 |

### 组合使用

```
场景：实现一个新功能
1. /opsx:new → 创建变更容器（技能）
2. 以 software-architect 角色设计（代理）
3. /opsx:continue → 生成设计文档（技能）
4. 以 senior-developer 角色实现（代理）
5. /opsx:apply → 实施编码（技能）
6. 以 qa-verifier (strict) 角色验证（代理）
7. /opsx:verify → 验证合规性（技能）
```

## 工作流选择指引

| 场景 | 推荐工作流 | 原因 |
|------|-----------|------|
| 功能迭代 / 代码变更 | **双载体（默认，`tool.binding.r11`）**：BMAD Story（PRD FR）+ OpenSpec change 双向绑定 | 纯 OpenSpec 会让 PRD 进度落后 |
| 治理 / 文档 / 知识库 | Story + Revision（可替代 change） | 无业务代码，轻量路径 |
| 探索阶段 | `/opsx:explore` 或 `bmad-brainstorming` | 不写代码，纯思考 |
| 代码审查 | `agents/core/code-reviewer` 或 `bmad-code-review` | 视深度需求选择 |
| 质量验证 | `agents/core/qa-verifier`（standard/strict） | 证据驱动的验证 |
| 架构设计 | `agents/core/software-architect` + `/opsx:continue` | 角色 + 工作流结合 |

## 快速开始

### 0→1 全新项目
1. 运行 `/opsx:bootstrap` 自动分析并推荐配置
2. 编辑 `01-charter.md` 填入项目定位
3. 运行 `/opsx:explore` 探索项目方向
4. 运行 `/opsx:new` 创建第一个变更

### 1→2 已有项目重构
1. 运行 `/opsx:bootstrap` 自动分析、生成 `project-governance.yaml` 和 `AGENTS.md`
2. 审查 `authority_map`，确认治理权威来源
3. 编辑 charter 填入项目定位
4. 运行 `/opsx:new` 为每个重构目标创建变更

## 项目类型 Profiles

| Profile | 适用场景 |
|---------|---------|
| `solo-developer.md` | 独立开发者通用（推荐起步） |
| `backend-service.md` | 后端服务 |
| `desktop-application.md` | 桌面应用 |
| `embedded-system.md` | 嵌入式系统 |
| `ml-system.md` | 机器学习系统 |
| `native-security-runtime.md` | 原生安全运行时 |
| `security-research.md` | 安全研究 |
