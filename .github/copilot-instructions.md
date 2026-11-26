# Copilot instructions (generated)
Do not edit by hand; run `python scripts/export-governance-rules.py`.
Governance root: `.`

# Closed-loop CRUD protocol (MUST / STOP)

任何对 BMAD Story / OpenSpec change / Revision / Rule / PRD-FR 的创建 / 修改 / 状态变更（CRUD）都是一次同步事件，MUST：

1. 动手前先产出"受影响工件清单"（Story / Change / Revision / Rule / PRD-FR），确认三端反向引用对齐。
2. STOP：`completed` / `done` / `archived` / `active_sprint` / `status=merged` 为高风险字段，
   在 `python scripts/check_progress_consistency.py` 通过前禁止写入；状态字段是最后一步且必须联动其它工件。
3. 新增收敛工作必须新建 story/change，禁止挂到已 `done`/`archived` 的 Story。
4. 收尾前必须贴出 `check_progress_consistency.py` 的通过输出（exit 0）作为完成证据（脚本零依赖、无 .git 亦可跑）。
5. fail-closed：任一检查失败（exit != 0）→ 不许 commit、不许标完成、不许归档；先消除漂移或登记合法豁免。
6. 检查点协议（`tool.binding.r10`，全文见 `05-ai-collaboration-policy.md` §7.3）：用户明确要求收尾、归档、提交，或当前变更已达到收尾阶段且即将开启
   新 OpenSpec 变更时，MUST 依次——查工作区变动并归因（`scripts/check_worktree_hygiene.py`）→
   判当前 change 可否归档 → 可归档则询问用户是否勾选人工验证标志、确认后归档 → 归档与代码工件同一次提交 →
   校验 BMAD PRD ↔ OpenSpec 双向同步 → 以 `<type>(<scope>): <中文描述>` + trailers 提交并 push →
   分支从主分支新拉、解冲突后 push，merge 由用户执行。普通继续、CLI 原生 resume 和压缩不触发此检查点。

git 门禁（`scripts/install_git_hooks.py`）仅"有 .git 才加分"；地基 = 零依赖自检 + 本协议 + `_logs/sync-ledger.md` 台账。
## Authority
- Verification policy overrides agent defaults.
- Load `project-governance.yaml` before large changes.
## Enabled domains

### agent-tooling-mcp

# Agent 工具与 MCP 治理

## 1. 目标

- 规范 AI Agent 通过 Model Context Protocol（MCP）访问外部工具、数据与系统的方式。
- 降低工具投毒、越权调用、命令注入与秘密泄露风险。
- 使 PR / 变更可审计：用了哪些 MCP、谁批准、作用范围是什么。

## 2. 适用范围

- 使用 Cursor、Claude Code、Copilot、Codex 等且启用 MCP 的项目。
- 涉及生产数据、内网 API、部署、密钥、客户数据的连接器。

## 3. 默认原则

- **最小权限**：仅启用完成当前任务所需的 MCP server；禁止「为了方便」默认全开。
- **显式披露**：变更 PR 正文须列出新增/修改的 MCP server 与用途（见 §6）。
- **人类可批准**：写生产、发版、改权限类操作须有人工确认，不得由 Agent 单独闭环。
- **可复现**：关键 Agent 任务保留 intent → 工具调用摘要 → diff 的追溯链（与 `04-verification-policy.md` 一致）。

## 4. 连接器登记（项目级）

在 `project-governance.yaml` 或 `docs/project-rules.md` 维护 `mcp_connectors`（可选块）：

| 字段 | 说明 |
|------|------|
| `id` | 稳定标识，如 `gitlab`, `sentry-prod` |
| `owner` | 负责团队或个人 |
| `scope` | `read-only` / `read-write` / `deploy` |
| `allowed_paths` | 可访问仓库路径或环境（如 `staging` only） |
| `se

### coding-standards

# 代码规范约束

## 1. 目标

- 保持代码可读、可审、可扩展、可验证。
- 让不同模块和不同贡献者的代码风格收敛，而不是各写一套。

## 2. 基本规则

- 命名应表达职责，不使用无意义缩写。
- 文件和模块按稳定职责组织，不用单个大文件承接多类责任。
- 注释用于解释“为什么”和“不明显的设计意图”，不解释显而易见的语法。
- 错误处理必须显式，不允许静默吞错。

## 3. 结构规则

- 公共接口、内部实现、测试辅助、平台适配边界应分层清晰。
- 避免复制粘贴式复用，优先抽象共享边界。
- 对动态参数、环境差异、配置差异，应通过结构化来源接入，不靠散落常量。

## 4. 代码评审关注点

- 是否破坏单一职责
- 是否引入影子状态
- 是否增加隐藏耦合
- 是否缺测试或证据
- 是否让代码比需求本身更难理解

## 5. 工具建议

- 格式化、静态检查、Lint、依赖审计和基础测试应尽量纳入 CI 门禁。
- 语言或框架已有标准工具时，优先复用。

## 6. 文本与文件编码（域内落实）

- 本域落实全局要求 `02-engineering-principles.md` §9：所有源码与配置文件 **UTF-8** 保存。
- 编辑器与 CI 建议：`.editorconfig` 中 `charset = utf-8`；禁止将非 UTF-8 源文件提交入库。
- 脚本生成或批量改写文件时，显式指定 UTF-8，并在 Windows 终端验证中文路径与日志可读。


### automation

# 自动化与回归证据

## 1. 默认原则

- 自动化不是零散脚本集合，而是共享验证协议的一部分。
- 回归验证优先依赖可复现命令、结构化输出和稳定证据路径。
- 所有自动化流程必须可在 CI 环境中无人值守执行，禁止依赖本地 GUI 操作。
- 自动化脚本与被测系统之间应保持松耦合，避免因实现变更导致大面积测试失效。
- 自动化覆盖范围应随代码演进持续更新，禁止出现"写完即弃"的一次性脚本。

## 2. 参数与输入

- 动态路径、环境差异、规则集版本和制品位置应来自明确来源。
- 不得把猜测的环境路径、临时阈值或隐藏前置条件静默写死在脚本里。
- 所有可配置参数必须通过环境变量、配置文件或命令行参数注入，禁止硬编码。
- 测试超时、重试次数等运行参数必须显式声明默认值并支持覆盖。
- 输入数据来源必须在脚本头部或配置文件中明确标注。

## 3. 证据约束

- 自动化输出应尽量可机器解析。
- 若只能做人工验证，应明确记录步骤、环境和结果。
- 失败应可解释，而不是只留下"命令失败"。
- 证据格式应与 `04-verification-policy.md` 中定义的证据优先级对齐：自动化输出 > 可复现日志 > 人工记录。
- 每次回归运行的证据必须关联到触发它的变更标识（提交哈希、变更编号等）。

## 4. 测试自动化总原则

- 测试应遵循金字塔结构，单元测试为基础、E2E 测试为顶层，详见 `test-pyramid.md`。
- 测试数据管理应遵循工厂模式与隔离原则，详见 `test-data.md`。
- 不稳定测试（Flaky Test）必须按治理流程处理，详见 `flaky-test-policy.md`。
- 所有测试产出的证据必须满足可追溯、可复现要求，详见 `test-evidence.md`。

## 5. 与验证政策的关系

本域约束

### operations

# 运维与生产保障约束（Operations 域，L1）

本域承载「运维操作 / 值班 / 容量 / 灾备 / 变更管理 / 闭环运行时上下文 / 反堆积治理 / 长任务与资源护栏 / 发版记录 / 环境基线」十类长期约束。是 L1 树化样板（按 `02-engineering-principles.md §11` 三件套协议），也是治理母版自治理循环的首批 dogfoo

<!-- TRUNCATED: full rules in .cursor/rules/governance-*.mdc and domains/ — regenerate with scripts/export-governance-rules.py -->
