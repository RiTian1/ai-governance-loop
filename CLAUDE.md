# AI 智能体框架入口

本仓库是通用 AI 辅助开发框架，适用于任意项目的 0→1 开发和 1→2 重构。

**本仓库为治理母版**：已包含根目录 `project-governance.yaml`（`governance_layout: mother-repo-root`）。业务项目请先 `/opsx:bootstrap` 或复制到 `docs/governance/`。路径说明见 `LAYOUT.md`；Agent 短入口见 `AGENTS.md`。

## 加载顺序

1. 读取本文件
2. 读取 `project-governance.yaml` 确认 `governance_layout`、`governance_root`、`token_budget`、`runtime_context`
3. 读取 `{governance_root}/00-index.yaml`（schema v2）：优先看 `levels.L1`；按 trigger 命中度下钻
4. 读取 `profiles/` 中匹配的项目 profile（独立开发者推荐 `solo-developer.md`）
5. 加载 profile 指定的 foundations 和 domains（**按 token 预算稀疏装载**，见下）
6. 了解 `agents/` 中的可用代理
7. 使用 OpenSpec 或 BMAD 管理变更流

### Token 预算与稀疏装载（强制）

默认单任务治理上下文预算 **8 k tokens**。装载由 `scripts/context_loader.py` 控制：
- 高分（≥ 6）域装 `index.md` 全文
- 中分（3 ~ 5）域仅装 `_summary.yaml`
- 低分跳过；trace 日志写到 `revisions/_logs/context-trace/<date>.jsonl`

**禁止全量加载所有 domains**。完整协议：`02-engineering-principles.md §11`；长期循环：`foundations/self-governance-and-knowledge-evolution.md`。

## 框架四层架构

```
┌─ 治理层（Authority）── "什么不能做、什么必须做"
│   foundations/ → 方法论约束（8 个）
│   domains/ → 领域约束（22 个）
│   profiles/ → 项目类型组合（7 个）
│
├─ 代理层（Capability）── "谁来做、怎么做"
│   agents/core/ → 核心开发循环（5 个代理）
│   agents/specialists/ → 按需专家（10 个代理）
│   agents/design/ → 设计专家（2 个代理）
│   agents/meta/ → 元代理与协调（3 个代理）
│
├─ 工作流层（Process）── "变更如何流转"
│   OpenSpec → 规范驱动的变更管理（11 个技能）
│   BMAD → 生命周期阶段引导（43 个技能）
│
└─ 技能层（Behavior）── "如何做得更好"
    Superpowers → TDD、调试、协作模式（按需安装）
```

---

## ⚠️ 权威优先级规则（强制）

当代理规则与治理约束冲突时，**治理约束永远优先**。优先级排序：

```
1. 04-verification-policy.md        ← 最高：验证政策
2. foundations/*.md                  ← 方法论约束
3. domains/*.md                     ← 领域约束
4. profiles/*.md                    ← 项目组合约束
5. agents/*.md (governance: 字段)    ← 代理自带的治理绑定
6. agents/*.md (正文规则)            ← 最低：代理行为细节
```

**实际含义**：
- 如果 `domains/coding-standards.md` 要求"函数不超过 50 行"，而 `agents/core/senior-developer.md` 中的模板示例使用了 80 行函数 → 以 domain 为准
- 如果 `foundations/failure-and-reliability-thinking.md` 要求"所有错误路径必须有显式处理"，而代理实现省略了 → 必须补充
- 代理文件中的 `governance:` 字段声明了该代理受哪些治理文档约束 — 执行任务前必须先加载这些文档

---

## 🔒 CRUD = 同步事件（不可跳过闭环 · STOP 门 · 强制）

> 便携治理的真正执行点。无外部硬闸时，LLM 在长会话里必然回到"先做事后补账"惯性，
> 造成 PRD / Story / Change / Revision 状态与内容多处偏移。下列是**命令语气**的硬动作链。

**任何**对 BMAD Story / OpenSpec change / Revision / Rule / PRD-FR 的 **创建 / 修改 / 状态变更（CRUD）**，
都是一次**同步事件**，MUST：

1. **动手前** 先产出"受影响工件清单"（Story / Change / Revision / Rule / PRD-FR），并确认三端反向引用对齐。
2. **高风险状态字段** `completed` / `done` / `archived` / `active_sprint` / `status=merged`：
   **STOP** —— 在 `python scripts/check_progress_consistency.py` 通过前**禁止写入**；状态字段是最后一步且必须联动其它工件。
3. **新增收敛工作必须新建 story/change**，**禁止挂到已 `done`/`archived` 的 Story** 上。
4. **收尾前必须贴出** `check_progress_consistency.py` 的**通过输出（exit 0）** 作为完成证据（脚本零依赖、无 .git 亦可跑）。
5. **fail-closed**：任一检查失败（exit != 0）→ 不许 commit、不许标完成、不许归档；先消除漂移或登记合法豁免。
6. **检查点协议**（`tool.binding.r10`，全文见 `05-ai-collaboration-policy.md` §7.3）：用户明确要求收尾/归档/提交，或在当前变更收尾后开启
 下一个新 OpenSpec 变更前，MUST 依次——查工作区变动并归因 → 判当前 change 可否归档 → 可归档则**询问用户
 是否勾选人工验证标志**、确认后归档 → 归档与代码工件**同一次提交** → 校验 BMAD PRD ↔ OpenSpec 双向同步 →
 以 `<type>(<scope>): <中文描述>` + trailers 提交并 push → 分支从主分支新拉、解冲突后 push，**merge 由用户执行**。

> git 门禁（`scripts/install_git_hooks.py`）仅"有 .git 才加分"；地基 = 零依赖自检 + 本协议 + `_logs/sync-ledger.md` 台账。

---

## 🤖 代理 vs 技能

代理（agents/）= 角色身份，技能（skills/）= 操作流程。选择方法、组合示例与工作流指引见 `docs/entry-guide.md`（按需读取，不常驻）。

---

## 可用命令

### OpenSpec（变更管理，CLI v1.5.0，中文版命令/技能）
- `/opsx:bootstrap` — 智能分析项目，推荐 profile 和配置（治理母版定制）
- `/opsx:propose` — **推荐** 一步创建变更并生成 proposal/design/tasks/specs
- `/opsx:explore` — 探索模式，思考和调研，不写代码
- `/opsx:new` — 分步创建变更（legacy 扩展工作流）
- `/opsx:ff` — 快进：一次性生成全部产出物
- `/opsx:continue` — 创建下一个产出物
- `/opsx:apply` — 实施任务，实际编码
- `/opsx:verify` — 验证实现是否匹配规范
- `/opsx:archive` — 归档已完成的变更

### BMAD（生命周期引导）
- `bmad-brainstorming` — 头脑风暴
- `bmad-create-prd` — 创建 PRD
- `bmad-create-architecture` — 创建架构
- `bmad-dev-story` — 开发用户故事
- `bmad-code-review` — 代码审查
- `bmad-help` — BMAD 帮助与引导

### 框架桥接
见 `_bmad/governance-bridge.yaml` 了解 BMAD ↔ OpenSpec ↔ 治理基线的映射关系。

### 治理工具链
- **上下文 Loader**：`python scripts/context_loader.py --phase <p> --keywords "..." --budget 8000` — 按 trigger 评分与预算装配 governance bundle（schema v2 树化索引）
- **知识库健康自检**：`python scripts/check_knowledge_health.py --all` — 占位符 / 三件套 / rule_id 唯一 / size 漂移 / orphan / stale candidate
- **进度一致性自检**：`python scripts/check_progress_consistency.py --strict` — BMAD ↔ OpenSpec ↔ Revisions 三向反向引用 + 状态机 + 哈希一致性
- **进度 matrix 生成**：`python scripts/gen_progress_matrix.py --report _logs/progress-matrix.md` — 自动生成 traceability matrix（Story × Change × Revision × Rules × Commits）
- **commit message 校验**：`python scripts/check_commit_message.py` — pre-commit/commit-msg hook 阻断违规 commit
- **revision-commit 关联**：`python scripts/link_revision_to_commits.py` — post-merge 自动 fill `meta.yaml.commits` 字段
- **长期自治理循环**：`foundations/self-governance-and-knowledge-evolution.md` — 观察 / 诊断 / 决策 / 执行 / 回归
- **进度可追溯与跨工具绑定**：`foundations/progress-traceability-and-binding.md` + `domains/tooling/` — BMAD/OpenSpec/Revisions 三层语义层强绑定
- **运行时上下文清单**：`templates/runtime-context-manifest-template.yaml` — 闭环执行所需 env / 凭据 / 权限 / 依赖 / 网络声明
- **统一门禁激活**：`python scripts/install_governance_gates.py --project-root <项目根>` — 接入任意项目即具备确定性门禁：有 .git 装 git 钩子（pre-commit 一致性+staged-pure 卫生，commit-msg 协议），无 .git 优雅降级；收尾强制自检（tool.r7）
- **存量项目门禁升级**：`python scripts/upgrade_project_gates.py --target <项目根>` — 从母版侧把门禁 bundle 幂等同步进旧集成项目并激活（tool.r7）
- **上游同步**：`powershell -File scripts/sync-upstream.ps1`（OpenSpec 1.5.0 + BMAD 6.10.0；升级后需重做中文化，见 UPSTREAM-VERSIONS.yaml）
- **IDE 规则导出**：`python scripts/export-governance-rules.py`
- **Agent Evals**：`templates/agent-evals-manifest-template.yaml` + `scripts/check-agent-evals.py`
- **MCP 约束**：`domains/agent-tooling-mcp.md`
- **BMAD 单源**：`BMAD-SINGLE-SOURCE.md` — v6.10 起技能正文在 `.claude/skills/`，配置改 `_bmad/custom/config.toml`；中文输出约束见 `_bmad/governance-bridge.yaml`

### 工作流选择 / 快速开始 / Profiles

工作流选择指引、0→1 与 1→2 快速开始、项目类型 profiles 对照表 → `docs/entry-guide.md`（按需读取）。

## 目录结构

详见 `00-index.md` 和 `agents/README.md`。
