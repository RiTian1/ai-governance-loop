# 精选代理

本目录包含从 142+ 代理库中精选的 20 个代理，按职责分为四层。完整代理库按需拉取到 `_reference/agency-agents-main/`（运行 `scripts/fetch-reference.ps1` / `.sh`；上游已迁移至 [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)，2026-07 核实为 147 agents / 12 divisions）。

## ⚠️ 输出语言约束（强制，MUST）

以本目录任一代理角色开展工作时：

1. **对话沟通、过程叙述、提问一律使用中文（简体）**；
2. **产出文档正文一律使用中文（简体）**——ADR、评审意见、验证报告、设计文档等；
   代码、命令、路径、API 标识符、专有名词可保留英文原文；
3. 代理文件正文为英文**不构成豁免**——那是角色能力定义，不是输出语言授权；
4. 本约束与 BMAD 侧同源：见 `_bmad/governance-bridge.yaml`「输出语言约束」节；
   冲突时按权威优先级以治理文档为准。

## 架构定位

```
┌─ 治理层（Authority）── "什么不能做、什么必须做"
│   foundations/ → 思维约束
│   domains/ → 技术边界
│   profiles/ → 项目组合
│
├─ 代理层（Capability）── "谁来做、怎么做"  ← 本目录
│   agents/core/ → 核心开发循环
│   agents/specialists/ → 按需专家
│   agents/design/ → 设计专家
│   agents/meta/ → 元代理与协调
│
├─ 工作流层（Process）── "变更如何流转"
│   OpenSpec → 规范驱动的变更管理
│   BMAD → 生命周期阶段引导
│
└─ 技能层（Behavior）── "如何做得更好"
    Superpowers → TDD、调试、协作模式
```

## 治理绑定

**所有代理均已注入 `governance:` 字段**，声明受哪些 foundations 和 domains 约束。执行代理角色前，必须先加载对应的治理文档。

**权威优先级**：`04-verification-policy` > `foundations/` > `domains/` > `agents/ (governance:)` > `agents/ (正文)`

详见 `CLAUDE.md` 中的完整优先级规则。

## 核心循环代理 (`core/`，每次开发都用)

| 代理 | 职责 | 激活时机 |
|------|------|---------|
| `software-architect` | 架构决策、ADR、C4 模型、选型矩阵 | 设计阶段 |
| `senior-developer` | 技术栈无关的全栈实现（已通用化） | 实施阶段 |
| `code-reviewer` | PR 级代码审查（blocker/suggestion/nit 三级） | 实施后 |
| `qa-verifier` | 证据驱动验证 — standard(常规) / strict(预发布) | 验证阶段 |
| `rapid-prototyper` | 0→1 快速原型，最小可行验证 | 原型阶段 |

> **变更说明**：`evidence-collector` 和 `reality-checker` 已合并为 `qa-verifier`，通过严格级别配置适应不同场景。`senior-developer` 已重写为技术栈无关版本。

## 按需专家代理 (`specialists/`，根据项目类型激活)

| 代理 | 职责 | 适用场景 |
|------|------|---------|
| `backend-architect` | API 设计、数据建模、SQL 优化 | 后端服务 |
| `frontend-developer` | React/、性能优化、无障碍 | 前端应用 |
| `devops-automator` | CI/CD、Terraform、K8s、混沌工程 | 基础设施 |
| `security-engineer` | 认证、加密、OWASP、威胁建模 | 安全相关 |
| `database-optimizer` | 查询优化、索引策略、分区 | 数据密集 |
| `api-tester` | API 合约测试、负载测试 | API 服务 |
| `ai-engineer` | ML/LLM 集成、向量数据库、MLOps | AI 应用 |
| `mobile-app-builder` | iOS/Android、跨平台 | 移动应用 |
| `technical-writer` | 技术文档、API 文档编写 | 文档交付 |
| `performance-benchmarker` | 性能测试、基准对比、瓶颈分析 | 性能敏感 |

## 设计代理 (`design/`，涉及用户体验时激活)

| 代理 | 职责 | 适用场景 |
|------|------|---------|
| `design-system-architect` | 设计系统 + UX 架构 + 视觉设计（三合一） | 设计系统 |
| `ux-researcher` | 用户研究、可用性测试、用户画像 | 用户研究 |

> **变更说明**：`ux-architect` 和 `ui-designer` 已合并为 `design-system-architect`，消除了设计令牌重复定义。

## 元代理 (`meta/`，项目管理与协调)

| 代理 | 职责 | 适用场景 |
|------|------|---------|
| `agents-orchestrator` | 多代理管线协调、Dev-QA 循环 | 复杂流程 |
| `product-manager` | 需求分析、优先级排序、PRD 编写 | 产品规划 |
| `sprint-prioritizer` | 冲刺规划、任务排序、MoSCoW 分级 | 迭代管理 |

## 使用方式

### 在 Claude Code 中

```
请以 software-architect 的角色，为本项目设计后端架构...
```

### 代理与治理的协作

每个代理文件包含 `governance:` 字段，列出其受约束的 domains 和 foundations。执行代理角色时：

1. 读取代理文件的 `governance:` 字段
2. 加载列出的 foundations 和 domains 文档
3. 以治理约束为边界执行代理任务
4. 冲突时以治理文档为准（详见 CLAUDE.md 优先级规则）

### 与 BMAD 代理的对应关系

见 `_bmad/governance-bridge.yaml` 中的 `agent_mapping` 字段。

### 扩展代理

如需更多代理，先运行 `scripts/fetch-reference.ps1`（或 `.sh`）拉取上游库，再从 `_reference/agency-agents-main/` 复制到对应子目录，并添加 `governance:` 字段绑定到适用的治理文档。新引入的代理同样受上文「输出语言约束」管辖。
