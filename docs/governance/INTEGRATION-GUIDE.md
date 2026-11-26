# Governance 框架集成指南

本文档整理治理框架如何集成到一个项目中，覆盖从集成模型到完成判定的全流程。

---

## 目录

1. [集成架构概览](#1-集成架构概览)
2. [三层激活模型](#2-三层激活模型)
3. [集成路径选择](#3-集成路径选择)
4. [Greenfield 集成（0→1）](#4-greenfield-集成01)
5. [Brownfield 集成（1→2）](#5-brownfield-集成12)
6. [核心集成产物](#6-核心集成产物)
7. [Profile / Foundation / Domain 装配](#7-profile--foundation--domain-装配)
8. [AI Agent 加载顺序](#8-ai-agent-加载顺序)
9. [工作流集成](#9-工作流集成)
10. [多项目共享治理](#10-多项目共享治理)
11. [集成完成判定](#11-集成完成判定)
12. [反模式与常见问题](#12-反模式与常见问题)

---

## 1. 集成架构概览

### 1.1 分发模型

治理框架采用**分布式复制模型**，而非 Git Submodule 或包管理器：

```
governance-repo（母版）
       │
       ├──复制──→ project-A/docs/governance/    （Brownfield）
       ├──复制──→ project-B/                    （Greenfield）
       └──复制──→ project-C/docs/governance/    （Brownfield）
```

**为什么不用 Submodule？**
- 每个项目需要本地裁剪和演进
- 避免上游变更意外破坏项目基线
- 保持项目自治，减少外部依赖
- 通过 `adoption_source` 字段追踪母版来源

### 1.2 四层架构在项目中的映射

```
项目仓库/
│
├── project-governance.yaml          ← 激活层（单一集成入口）
├── AGENTS.md                        ← AI 行为约束（Brownfield 必须）
│
├── docs/governance/                 ← 治理层（Authority）
│   ├── 00-index.md/yaml            ← 索引入口
│   ├── 01-charter.md               ← 项目宪章
│   ├── 02~08 主文档                ← 工程原则、验证策略等
│   ├── profiles/                    ← 项目类型组合
│   ├── foundations/                 ← 方法论约束
│   ├── domains/                     ← 领域约束
│   └── agents/                      ← 代理层（Capability）
│       ├── core/                    ← 核心开发循环代理
│       └── specialists/             ← 按需专家代理
│
├── openspec/                        ← 工作流层（Process）
│   ├── config.yaml
│   ├── changes/                     ← 变更工作区
│   └── specs/                       ← 合并后的规范
│
├── .claude/commands/opsx/           ← 技能层（Behavior）
│   ├── bootstrap.md
│   ├── new.md
│   ├── apply.md
│   └── ...
│
└── src/                             ← 项目代码
```

---

## 2. 三层激活模型

```
┌──────────────────────────────────────────────────┐
│ 母版层（Master Templates）                        │
│   docs/governance/ 中的通用治理文档                 │
│   可跨项目复用的基线                               │
├──────────────────────────────────────────────────┤
│ 激活层（Project Activation）                      │
│   project-governance.yaml                        │
│   声明本项目启用哪些 profile/foundation/domain     │
│   解决母版与项目特殊规则的冲突                      │
├──────────────────────────────────────────────────┤
│ 项目专属层（Project-Specific）                     │
│   docs/project-rules.md                          │
│   现有模块文档、API 规范等                         │
│   项目独有的约束和覆盖                              │
└──────────────────────────────────────────────────┘
```

**权威优先级**（高 → 低）：
1. `04-verification-policy.md` — 验证政策
2. `foundations/*.md` — 方法论约束
3. `domains/*.md` — 领域约束
4. `profiles/*.md` — 项目组合约束
5. `agents/*.md (governance:)` — 代理治理绑定
6. `agents/*.md (正文)` — 代理行为细节

---

## 3. 集成路径选择

### 3.1 两种集成工具

| 工具 | 适用场景 | 交互方式 |
|------|---------|---------|
| `scripts/bootstrap.sh` | 命令行环境、CI/CD | 复制母版 + OpenSpec 多工具安装 |
| `scripts/bootstrap-windows.ps1` | Windows PowerShell | 同上 |
| `/opsx:bootstrap` | 已有仓库、仅需配置分析 | 只生成 YAML/AGENTS，**不**复制母版、**不**安装 IDE |

### 3.2 决策树

```
项目是否存在？
├── 否（全新项目）→ Greenfield 模式
│   ├── 有终端 → ./scripts/bootstrap.sh /path/to/new-project
│   └── 有 AI IDE → /opsx:bootstrap
│
└── 是（已有代码）→ Brownfield 模式
    ├── 已有文档体系 → Brownfield + Authority Map
    ├── 无文档体系 → Brownfield（按 Greenfield 裁剪）
    └── 多个项目 → 共享母版 + 各项目独立激活
```

### 3.3 闭环门禁集成 checklist（两条路径**完全一致**）

> 治理是**可移植母版**，强制力不能寄托在"每个项目去装 git 钩子 / 配 CI"上。
> 因此闭环的地基是 **git-optional** 的：零依赖自检 + agent 入口协议 + 同步台账；
> git 门禁只是"有 .git 才加分"的附加层。详见 `foundations/portable-closed-loop-enforcement.md`（如有）。

无论用 **路径甲（`scripts/bootstrap*.{sh,ps1}`）** 还是 **路径乙（在目标项目里直接与 agent 对话集成）**，
集成都必须完成下列**同一套**动作，且**集成本身受门禁约束**——集成完成后自检不通过即视为集成未完成：

- [ ] **复制治理内容**（foundations / domains / profiles / templates / revisions / scripts / openspec / _bmad / AGENTS.md / CLAUDE.md）；**绝不继承或拷贝母版的 `.git`**（`.git` 是仓库身份，治理是内容）。
- [ ] **生成 `project-governance.yaml`**（声明 `project_id` / profile / enabled_domains 等）。
- [ ] **激活确定性门禁（统一入口）**：跑 `python scripts/install_governance_gates.py --project-root <项目根> --governance-root <治理内容根>`。这一条命令收敛了下面三件事（`tool.r7`）：
      - **git 门禁（跨 agent 通用主干层）**：有 `.git` → 幂等、非破坏地把 hook 挂到**目标自己的 `.git`**（pre-commit 跑一致性自检 + `--assert-staged-pure` 工作树卫生闸；commit-msg 校验协议；`core.hooksPath` / husky / pre-commit 框架 / 既有 hook 的四条铁律见 `install_git_hooks.py` 内注释）。**目标无 `.git` → 优雅降级、退出 0**，闭环靠基线保证；可 opt-in `git init` 但**不强制**。
      - **Cursor 本地闸（可选）**：加 `--with-cursor-hooks` 装 `.cursor/hooks`（仅 Cursor 内有效，不影响 Codex/命令行提交的跨 agent 主干）。
      - **强制自检**：收尾自动跑 `check_progress_consistency.py`，退出码必须为 `0`（或所有 drift 已登记合法豁免）。**未过自检 = 集成未完成**。
- [ ] **导出 IDE 规则**：跑 `python scripts/export-governance-rules.py` 生成 `.cursor/rules/` 与 `.github/copilot-instructions.md`。

> **为什么以 git 钩子为主干**：git pre-commit/commit-msg 是唯一在 Cursor / Codex / 命令行提交时**都会触发**、
> 模型无法忽略的确定性层；Cursor hooks 只在 Cursor 内生效，Codex 无生命周期 hook。因此"没有 git 管理的项目
> 就不载入 git hook"是设计内的降级路径，而非缺陷——统一入口对无 `.git` 目标直接优雅退出 0。

**路径乙（agent 对话式集成）的硬约束**：agent 必须按上面逐项执行，**不得**用"先集成、自检留待以后"的方式收尾；
最后一步必须贴出 `check_progress_consistency.py` 的**通过输出**作为集成完成证据。这与 `bootstrap*.{sh,ps1}` 的
**Step 5.5（Activate Closed-Loop Governance Gate）** 是同一套逻辑——脚本只是把它自动化。

### 3.4 存量项目升级（补装缺失的门禁）

早期集成的项目用的是旧治理快照，往往缺少后来新增的门禁脚本（`install_governance_gates.py` /
`check_worktree_hygiene.py` / 各安装器 / Cursor hooks 模板）。**从母版侧**一键补装：

```bash
python scripts/upgrade_project_gates.py --target <目标项目根> --dry-run   # 先预览
python scripts/upgrade_project_gates.py --target <目标项目根>             # 同步 + 激活
```

- 幂等、非破坏：只同步显式 bundle 清单内的文件，绝不动目标已裁剪的治理文档 / 业务代码。
- 新门禁文件始终同步；**引擎脚本**（`check_progress_consistency` / `check_commit_message` / `_governance_yaml`）
  默认「仅缺失时补齐」，目标已有版本默认保留，需与母版对齐时显式加 `--force-engine`。
- 同步后自动在目标项目跑统一入口安装 hook + 自检；无 `.git` 目标同样优雅降级。

---

## 4. Greenfield 集成（0→1）

### 步骤 1：运行 Bootstrap

**方式 A — Bash 脚本：**
```bash
# 从母版仓库运行
cd /path/to/governance
./scripts/bootstrap.sh /path/to/new-project

# 交互式选择：
# 1. Profile → solo-developer / backend-service / ...
# 2. Mode → Greenfield
# 3. 项目名称和描述

# 多 IDE/CLI（默认安装 6 种）：
./scripts/bootstrap.sh /path/to/new-project --tools claude,cursor,codex,opencode,qwen,trae
./scripts/bootstrap.sh /path/to/new-project --tools all
./scripts/bootstrap.sh /path/to/new-project --skip-ide-tools   # 离线/无 Node 时

# Windows:
./scripts/bootstrap-windows.ps1 -TargetPath D:\proj -Tools "all"
```

### 步骤 1b：多 IDE / CLI 接入矩阵

Bootstrap **Step 5** 调用 `scripts/bootstrap-ide-tools.*`，内部执行 **OpenSpec 1.5.0** `init --tools … --profile custom`，按官方目录写入 skills/commands：

| 工具 | OpenSpec 目录 | 治理技能（母版复制） |
|------|---------------|----------------------|
| Claude Code | `.claude/` | `.claude/skills/openspec-*`、`bmad-*` stub |
| Cursor | `.cursor/` | 同上 + 需 `export-governance-rules` 生成 `.cursor/rules/` |
| Codex | `.codex/` | OpenSpec 生成；BMAD 启用时另有 `.agents/skills` |
| OpenCode | `.opencode/` | OpenSpec 生成 |
| Qwen Code | `.qwen/` | OpenSpec 生成 |
| Trae | `.trae/` | OpenSpec 生成 |

**BMAD** 默认启用（`frameworks.bmad.enabled: true`，`tool.binding.r11` 双载体：功能迭代必须
Story(PRD FR) + OpenSpec change 双向绑定，防 PRD 进度落后）。安装上游 BMAD 安装器：

```bash
./scripts/bootstrap.sh /path/to/project --enable-bmad
# 或事后：
./scripts/bootstrap-ide-tools.sh /path/to/project --tools claude,cursor --enable-bmad
```

**`/opsx:bootstrap` 与脚本分工：**

- 脚本：复制文件 + `project-governance.yaml` + OpenSpec init
- `/opsx:bootstrap`：brownfield 分析、authority_map、不调 `npx`

**方式 B — AI 驱动（仅配置）：**
```
# 在目标项目目录打开 Claude Code / Claude Code
/opsx:bootstrap
# AI 自动：扫描技术栈 → 推荐 Profile → 生成配置
```

### 步骤 2：编辑项目宪章

```bash
# 填入项目定位、长期目标、架构禁区
vim docs/governance/01-charter.md
# 或
vim 01-charter.md  # Greenfield 模式下在根目录
```

**必须填写的内容：**
- 项目名称和一句话描述
- 长期目标（3-5 条）
- 架构禁区（不做什么）
- 技术栈声明

### 步骤 3：确认 Profile 和域选择

```bash
# 查看选择的 Profile
cat profiles/solo-developer.md

# 确认启用的 foundations 和 domains
cat project-governance.yaml
```

### 步骤 4：开始工作

```
/opsx:explore  → 探索想法（不写代码）
/opsx:new      → 创建第一个变更
/opsx:ff       → 快进生成全部产出物
```

### Greenfield 最终目录结构

```
new-project/
├── project-governance.yaml          ✓ 自动生成
├── CLAUDE.md                        ✓ 复制
├── 00-index.md                      ✓ 复制
├── 00-index.yaml                    ✓ 复制
├── 01-charter.md                    ✓ 复制（需编辑）
├── 02~08 主文档                      ✓ 复制
├── foundations/                      ✓ 复制
├── domains/                         ✓ 复制
├── profiles/                        ✓ 复制
├── templates/                       ✓ 复制
├── agents/                          ✓ 复制
├── openspec/                        ✓ 复制
│   ├── config.yaml
│   ├── changes/
│   └── specs/
├── .claude/                         ✓ 复制 + OpenSpec init 刷新
├── .cursor/                         ✓ OpenSpec init（非仅镜像）
├── .codex/ .opencode/ .qwen/ .trae/ ✓ OpenSpec init（--tools 选用）
├── scripts/bootstrap-ide-tools.*    ✓ 复制
├── _bmad/                           ✓ 复制
└── examples/                        ✓ 复制（可选）
```

---

## 5. Brownfield 集成（1→2）

### 阶段一：只挂索引，不改旧文档

**最小必装文件：**
```
existing-project/
├── project-governance.yaml          ← 新建
├── AGENTS.md                        ← 新建
└── docs/governance/                 ← 新建目录
    ├── 00-index.md
    ├── 00-index.yaml
    ├── 01-charter.md               ← 需编辑
    ├── 02-engineering-principles.md
    ├── 03-document-workflow.md
    ├── 04-verification-policy.md
    ├── 05-ai-collaboration-policy.md
    ├── 06-reference-and-standards-policy.md
    ├── 08-project-activation-model.md
    ├── templates/
    └── revisions/README.md
```

**关键动作：声明 Authority Map**

在 `project-governance.yaml` 中明确：
```yaml
authority_map:
  # 已按治理框架组织的规则
  active_project_rules:
    - docs/project-rules.md

  # 项目既有文档（仍有效，但未迁入治理框架）
  project_specific_docs:
    - docs/api/rest-spec.md
    - docs/architecture/system-design.md
    - CONTRIBUTING.md

  # 旧规范（已过时，计划废弃）
  deprecated_parallel_rules:
    - old-coding-guidelines.md
    - legacy-review-checklist.md
```

### 阶段二：把长期规则提升到治理骨架

按需逐步迁移：
- 将零散编码规范 → `domains/coding-standards.md`
- 将 API 设计规范 → `domains/backend/api-design.md`
- 将测试规范 → `domains/automation/`
- 将安全规范 → `domains/security/`
- 新规则记录到 `revisions/`

### 阶段三：收敛旧平行体系

- 旧文档开头挂接新索引
- 删除重复/冲突/无人维护的平行规范
- 更新 `authority_map`：将已迁移文档移入 `deprecated_parallel_rules`

---

## 6. 核心集成产物

### 6.1 project-governance.yaml（必须）

**单一集成入口，所有治理配置的声明中心。**

```yaml
# ===== 项目基本信息 =====
project_id: my-api-service
project_name: My API Service
project_stage: brownfield            # greenfield | brownfield

# ===== 项目类型 =====
project_type_profile:
  - backend-service                  # 从 7 个 profile 中选择

# ===== 治理主文档（路径声明）=====
active_baseline:
  charter: docs/governance/01-charter.md
  engineering: docs/governance/02-engineering-principles.md
  workflow: docs/governance/03-document-workflow.md
  verification: docs/governance/04-verification-policy.md
  ai_collaboration: docs/governance/05-ai-collaboration-policy.md
  references: docs/governance/06-reference-and-standards-policy.md
  activation: docs/governance/08-project-activation-model.md

# ===== 启用的方法论约束 =====
enabled_foundations:
  - architecture-and-design-craftsmanship
  - failure-and-reliability-thinking
  - modeling-and-state-machine-thinking

# ===== 启用的领域约束 =====
enabled_domains:
  - coding-standards
  - backend                          # 目录型域：backend/
  - database
  - security                         # 目录型域：security/
  - devops-ci                        # 目录型域：devops-ci/
  - automation                       # 目录型域：automation/
  - documentation-and-api            # 目录型域：documentation-and-api/
  - configuration                    # 目录型域：configuration/
  - observability                    # 目录型域：observability/
  - architecture                     # 目录型域：architecture/

# ===== 启用的模板 =====
enabled_templates:
  - prd-template
  - summary-design-template
  - test-plan-template

# ===== 项目专属覆盖 =====
local_overrides:
  - docs/project-rules.md

# ===== 权威映射（Brownfield 必须）=====
authority_map:
  active_project_rules:
    - docs/project-rules.md
  project_specific_docs:
    - docs/api/rest-spec.md
  deprecated_parallel_rules: []

# ===== 迁移状态 =====
migration_mode:
  status: brownfield
  notes: "现有代码和文档并存，增量迁移中"

# ===== 采用来源追踪 =====
adoption_source:
  governance_template_origin: /path/to/governance-repo
  adopted_at: 2025-01-15
```

### 6.2 AGENTS.md（Brownfield 必须）

AI Agent 的行为约束声明，确保 Agent 不跳过治理。

```markdown
# AGENTS.md

本项目已接入 governance 基线。

AI agent 在进入 explore、proposal、design、apply、verify、archive 前必须：

1. 先读取 `project-governance.yaml`
2. 再读取 `docs/governance/00-index.yaml`
3. 按 `project_type_profile`/`enabled_foundations`/`enabled_domains` 加载治理文档
4. 若涉及规则语义、验证策略、E2E、CI 或交付证据，读取验证政策和自动化域
5. 新发现的规则回写到 `docs/governance/revisions/`

禁止：
- 跳过 `project-governance.yaml` 直接猜测规则
- 只改代码不判断验证门禁
- 规则语义变化时只补接口测试不复审 E2E
- 交付时只给结论不给结构化证据
```

### 6.3 01-charter.md（必须编辑）

```markdown
# 项目宪章

## 项目名称
My API Service

## 一句话定位
面向中小企业的订单管理 REST API 服务

## 长期目标
1. 提供高可用的订单 CRUD 和查询服务
2. 支持多租户隔离
3. 可横向扩展至 10,000 TPS

## 架构禁区
- 不引入 GraphQL（团队无经验）
- 不使用 NoSQL 作为主存储
- 不做前端，仅提供 API

## 技术栈
- Go 1.22+
- PostgreSQL 16
- Redis 7 (缓存)
- Docker + Kubernetes
```

---

## 7. Profile / Foundation / Domain 装配

### 7.1 Profile 选择矩阵

| Profile | 适用项目 | 默认 Foundation | 核心 Domain |
|---------|---------|----------------|-------------|
| **solo-developer** | 独立开发者通用 | architecture, modeling, failure | coding-standards, backend, frontend, database, security, devops-ci, automation, doc-api |
| **backend-service** | 后端 API 服务 | architecture, failure, modeling | coding-standards, backend, database, security, infra, devops-ci, observability |
| **desktop-application** | 桌面 GUI 应用 | architecture, modeling, discrete-math | gui, frontend, performance, doc-api |
| **embedded-system** | 嵌入式/实时系统 | modeling, failure, discrete-math | hardware-embedded, driver-kernel, base-runtime, performance |
| **ml-system** | 机器学习系统 | probability, modeling, mathematical | ml-data-science, data-governance, performance, automation |
| **native-security-runtime** | 安全关键运行时 | all 8 foundations | base-runtime, security, driver-kernel, automation, devops-ci |
| **security-research** | 安全研究/渗透 | discrete-math, failure, modeling | pentest, reverse-engineering, security |

### 7.2 装配流程

```
1. 选择 Profile
   ↓
2. Profile 声明推荐的 Foundations 和 Domains
   ↓
3. 在 project-governance.yaml 中填入
   ↓
4. 按项目实际需要增减
   - 增加：项目涉及但 Profile 未默认包含的域
   - 删减：Profile 默认包含但项目不涉及的域
   ↓
5. 确认最终组合
```

### 7.3 域的加载规则

| 域类型 | 加载方式 | 示例 |
|--------|---------|------|
| 单文件域 | 直接加载 `.md` | `coding-standards.md` |
| 目录型域 | `index.md` + 所有子文件全部生效 | `backend/index.md` + `api-design.md` + ... |

---

## 8. AI Agent 加载顺序

### 8.1 启动时加载

```
1. CLAUDE.md（项目级 AI 指令）
2. AGENTS.md（Brownfield 行为约束）
3. project-governance.yaml（激活配置）
4. docs/governance/00-index.yaml（结构化索引）
5. profiles/[selected-profile].md（项目组合）
```

### 8.2 任务时按需加载

```
当前任务阶段               加载的治理文档
─────────────────────────────────────────
explore（探索）           → 01-charter.md, profile
proposal（提案）          → 02-engineering-principles, 03-workflow
design（设计）            → foundations/*, domains/architecture/*
apply（实施）             → domains/coding-standards, domains/backend/*, domains/automation/*
verify（验证）            → 04-verification-policy, domains/automation/test-evidence
archive（归档）           → 03-document-workflow, domains/documentation-and-api/*
```

### 8.3 00-index.yaml 的 when_to_read 机制

```yaml
- id: verification-policy
  path: docs/governance/04-verification-policy.md
  when_to_read: [design, apply, verify]
  # → AI 仅在 design/apply/verify 阶段加载此文档
```

**好处**：避免一次性加载所有治理文档，减少上下文噪声。

---

## 9. 工作流集成

### 9.1 三种工作流入口

```
┌─────────────────────────────────────────────────────┐
│                     用户选择                         │
├─────────────┬─────────────────┬─────────────────────┤
│  OpenSpec    │     BMAD        │      混合           │
│  (轻量级)    │   (全生命周期)    │  (最灵活)           │
├─────────────┼─────────────────┼─────────────────────┤
│/opsx:explore│bmad-brainstorm  │/opsx:explore        │
│/opsx:new    │bmad-create-prd  │bmad-create-prd      │
│/opsx:continue│bmad-create-arch│/opsx:continue       │
│/opsx:apply  │bmad-dev-story   │/opsx:apply          │
│/opsx:verify │bmad-code-review │/opsx:verify         │
│/opsx:archive│                 │/opsx:archive        │
├─────────────┴─────────────────┴─────────────────────┤
│          所有路径最终收敛于治理验证                     │
│          04-verification-policy.md                   │
└─────────────────────────────────────────────────────┘
```

### 9.2 推荐选择

| 场景 | 推荐 | 原因 |
|------|------|------|
| 快速原型 / 小变更 | `/opsx:ff` | 一步到位 |
| 全新产品 / 复杂功能 | BMAD 全流程 + OpenSpec | 完整生命周期引导 |
| 探索阶段 | `/opsx:explore` | 不写代码，纯思考 |
| 独立开发者日常 | OpenSpec | 轻量，适合一人团队 |

### 9.3 变更在项目中的存储

```
project/
├── openspec/
│   ├── changes/
│   │   ├── feature-user-auth/       ← 一个变更一个目录
│   │   │   ├── 01-proposal.md
│   │   │   ├── 02-design.md
│   │   │   ├── 03-tasks.md
│   │   │   └── delta-specs/         ← 增量规范
│   │   └── fix-payment-bug/
│   │       └── ...
│   ├── specs/                       ← 合并后的主规范
│   └── archive/                     ← 已归档的变更
```

---

## 10. 多项目共享治理

### 10.1 推荐模式

```
governance-master/                   ← 母版仓库（本仓库）
├── foundations/
├── domains/
├── profiles/
├── templates/
└── ...

project-A/                           ← 项目 A（后端服务）
├── project-governance.yaml
│   └── adoption_source:
│       governance_template_origin: governance-master
│       adopted_at: 2025-01-15
├── docs/governance/                 ← 复制后独立演进
│   └── ...（裁剪后的子集）
└── src/

project-B/                           ← 项目 B（桌面应用）
├── project-governance.yaml
│   └── adoption_source:
│       governance_template_origin: governance-master
│       adopted_at: 2025-02-01
├── docs/governance/
│   └── ...（不同的裁剪子集）
└── src/
```

### 10.2 同步策略

- **不自动同步**（设计决策）
- 各项目独立演进
- 定期人工比对母版变更
- 通过 `adoption_source.adopted_at` 追踪最后同步时间
- 母版更新后各项目自行评估是否采纳

---

## 11. 集成完成判定

### 11.1 最低标准

一个项目可视为"成功采用"的最低标准：

- [ ] 存在 `project-governance.yaml`
- [ ] 存在 `AGENTS.md`（Brownfield）
- [ ] `00-index.yaml` 指向启用的治理资产
- [ ] 已编辑 `01-charter.md` 填入项目信息
- [ ] Profile 已选择且 foundations/domains 已装配
- [ ] 新成员能从索引快速定位规则
- [ ] 评审与验证开始引用模板
- [ ] 新规则通过 `revisions/` 进入基线
- [ ] 旧平行规范开始收敛

### 11.2 采用后最小动作

完成初始化后，至少应补齐：
- [ ] 一份项目宪章（01-charter.md）
- [ ] 一份 `project-governance.yaml`
- [ ] 一份项目术语表
- [ ] 一份 PRD 模板落地样例
- [ ] 一份测试计划落地样例
- [ ] 一份修订单样例

---

## 12. 反模式与常见问题

### 12.1 反模式

| 反模式 | 问题 | 正确做法 |
|--------|------|---------|
| 全量复制不裁剪 | 治理噪声，不相关域增加认知负担 | 按 Profile 选择性启用 |
| 只复制模板不复制索引 | 失去导航能力 | 至少复制 00-index + 主文档 |
| 规则只留在聊天中 | 不可追溯、不可复用 | 回写到 `revisions/` |
| 不声明 Authority Map | Brownfield 冲突无法解决 | 明确声明哪些文档说了算 |
| AI 跳过治理直接写码 | 绕过门禁和验证 | AGENTS.md 强制加载顺序 |
| 把母版当唯一真理 | 项目无法独立演进 | 复制后独立演进，定期比对 |

### 12.2 常见问题

**Q: 治理框架和项目代码在同一个仓库吗？**
A: Brownfield 模式下在 `docs/governance/` 子目录；Greenfield 可在项目根目录。

**Q: 我只是个人开发者，需要这么复杂吗？**
A: 选择 `solo-developer` Profile，用 `/opsx:ff` 快进模式，最轻量。

**Q: 母版更新了怎么办？**
A: 不自动同步。各项目通过 `adoption_source` 追踪来源，自行评估采纳。

**Q: 可以只用 OpenSpec 不用 BMAD 吗？**
A: 可以。两个工作流独立，按需选择。

**Q: 可以只用部分域吗？**
A: 可以。在 `project-governance.yaml` 的 `enabled_domains` 中只列需要的域。

**Q: 治理框架会影响 CI/CD 吗？**
A: 框架本身是文档层面的约束。如需落地到 CI，需要你自己配置门禁（参考 `domains/devops-ci/pipeline-gates.md`）。

---

## 附录 A：快速参考卡片

```
# === Greenfield 快速启动（3 分钟）===

1. ./scripts/bootstrap.sh /path/to/project
2. 编辑 01-charter.md
3. /opsx:explore

# === Brownfield 快速启动（5 分钟）===

1. ./scripts/bootstrap.sh /path/to/project  → 选 Brownfield
2. 编辑 project-governance.yaml 的 authority_map
3. 编辑 01-charter.md
4. /opsx:explore

# === AI 驱动启动（1 分钟）===

1. 在项目目录打开 Claude Code
2. /opsx:bootstrap
3. 按 AI 推荐确认
```

## 附录 B：文件清单速查

| 文件 | 必须性 | 谁创建 | 需要编辑 |
|------|--------|--------|---------|
| `project-governance.yaml` | 必须 | bootstrap 自动 | 需微调 |
| `AGENTS.md` | Brownfield 必须 | bootstrap 自动 | 通常不需要 |
| `01-charter.md` | 必须 | 复制 | 必须编辑 |
| `00-index.md/yaml` | 必须 | 复制 | 通常不需要 |
| `02~08 主文档` | 推荐 | 复制 | 按需 |
| `profiles/*.md` | 推荐 | 复制 | 不需要 |
| `foundations/*.md` | 按 Profile | 复制 | 不需要 |
| `domains/*.md` | 按 Profile | 复制 | 不需要 |
| `agents/` | 推荐 | 复制 | 不需要 |
| `openspec/` | 推荐 | 复制 | 不需要 |
| `_bmad/` | 可选 | 复制 | 不需要 |
| `templates/` | 推荐 | 复制 | 不需要 |
