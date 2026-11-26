# 工程原则

本文档定义大多数软件项目都应遵循的工程与架构基线。

## 1. 核心原则

- 单一职责：模块、文件、组件、控制器、适配器只承担一个稳定主责。
- 开闭原则：新增能力优先通过扩展点、组合、注册表、抽象、多态接入。
- 依赖倒置：高层策略依赖抽象，不直接依赖底层实现细节。
- 接口隔离：拒绝胖接口、胖上下文、胖 DTO。
- 显式分层：页面、组件、控制器、领域对象、运行时适配器、自动化、诊断应边界清晰。

## 2. 设计默认项

- 设计前先确认业界最佳实践，再确认本项目是否需要偏离。
- 多实现、多平台、多后端、多视图、多验证路径场景下，优先建立稳定抽象。
- 能用共享契约表达的状态，不要靠多个平行字段、多个影子 setter 或多个页面私有副本维持。
- 若问题本质上属于状态机、图、关系、实验设计、数值优化、可靠性建模，应先加载对应 foundations 文档，再决定实现路径。

## 3. 明确禁止项

- God File / God Object 持续膨胀
- 以集中式 `if` / `match` 取代本应存在的抽象边界
- 让页面或脚本层反向吞掉服务层、运行时层、适配层职责
- 把自动化、回放、诊断、审计逻辑无边界塞回单一 UI 总控

## 4. 扩展与复用原则

- 能被多个模块复用的规则，应沉淀为共享契约，不要在调用点重复拼接。
- 能被多个场景复用的交互模型，应沉淀为控制器、状态机或数据驱动配置，不要在视图层复制。
- 能被多个平台复用的系统能力，应沉淀到共享底座，不要在业务层复制条件分支。

## 5. 评审检查项

进入评审时默认检查：

- 新职责是否有明确归属
- 依赖方向是否清晰
- 是否引入影子状态源
- 是否增加了硬编码动态参数
- 是否把新行为落在了错误层级
- 是否缺验证证据或只验证了表面行为

## 6. 文档与实现的关系

- 文档不是实现后的说明书，而是实现前后的约束物。
- 如果实现暴露了更通用的规则，应回写治理文档，而不是只改当前代码。
- 如果 change-local 工件里出现可跨项目复用的规则，应提升为全局基线或模板基线。

## 7. 经验沉淀与适用范围

沉淀新规则时，必须先判断所属范围，再写入对应权威位置；禁止「写进聊天」或写错层级。

| 范围 | 判断标准 | 写入位置 | 操作要求 |
|------|----------|----------|----------|
| **变更级** | 仅对当前 OpenSpec change 有效 | `openspec/changes/<change>/` | 随 change 归档，不晋升 |
| **项目级** | 仅对本仓库路径、团队、分支策略有效 | `docs/project-rules.md`、`project-governance.yaml`（`local_overrides` / `authority_map`） | 不写入母版 `domains/` |
| **领域级** | 对某专业域（安全、CI、编码等）可复用，跨项目类型 | `{governance_root}/domains/<domain>/` 或对应单文件域 | 在域内**查漏补缺**，与现有条目对齐，避免重复 |
| **全局级** | 跨 profile、跨项目类型、所有 Agent 必须遵守 | `{governance_root}/` 主文档（`01`–`08`）、`foundations/`、`revisions/` → 晋升 | 经 `revisions/WORKFLOW.md` 晋升，更新 `00-index.yaml` |
| **事实域**（非规则） | 执行/开发所需的持久化事实：凭证引用、地址、端口、环境、接口约定 | 执行域 → 项目根 `runtime-context.yaml`；开发域 → `docs/project-rules.md` | 问前先查、答后当轮落账（`ops.runtime-context.r8/r9`）；按需读取不常驻，体量上限见 r10 |

默认顺序：能落在领域就不升格全局；能落在项目就不写入母版全局。

## 8. 沉淀操作纪律

- 领域级：编辑目标 `domains/` 文件，在 `domains/README.md` 索引中可检索；必要时补验证检查项。
- 全局级：先 `revisions/` 候选 → 评审 → 合并进主文档或 `foundations/`。
- 项目级：只改项目根 `docs/project-rules.md` 或 `project-governance.yaml`，不回流母版除非发起母版修订单。
- AI / 人工发现规则后须**当轮回写**，不得拖到归档后一次性补写（与 `05-ai-collaboration-policy.md` 一致）。

## 9. 终端编码环境

- 中文字符在 Windows 沙箱或终端中易出现乱码；重写、生成、覆盖文件时须显式保证编码一致。
- **全平台默认**：源码、配置、文档、脚本、OpenSpec 工件、治理 Markdown 一律使用 **UTF-8**（无 BOM，除非工具链强制要求 UTF-8 BOM）。
- 终端与脚本输出中文时：
  - Windows：优先 `chcp 65001` 或 PowerShell `[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8`；Python 写文件使用 `encoding='utf-8'`。
  - 禁止依赖系统本地 ANSI 代码页作为默认写入编码。
- 文件写入须使用带 UTF-8 声明的 API（如 `Set-Content -Encoding utf8`、`open(..., encoding='utf-8')`），不得省略编码参数后依赖平台默认。
- 若发现已写入乱码文件，须以 UTF-8 重新保存并验证终端与 diff 可读，不得将乱码内容原样提交。

## 10. 归档与提交原子约束

- 对于任何包含 OpenSpec 变更工件且存在配套代码、脚本、配置或验证物料的变更，进入 `archive` 并确认归档后，必须将**归档工件与该批配套实现**以**原子提交**方式一起提交。
- 归档相关原子提交必须推送到远端主协作分支（默认 `origin/master`），不得只在本地停留。
- 若同一批次含多个独立 change，允许按「每个 change 一个原子提交」执行，但每个提交都必须同时包含该 change 的归档工件与对应代码/物料，不得拆成「先归档后补代码」的分离提交。
- 禁止：工作区仅剩 `openspec/changes/archive/` 更新而实现代码在另一次提交；禁止归档完成却不 push。

## 11. 知识层级与 token 预算

本节是 §7（经验沉淀范围）的正交补充：§7 解决「规则写在哪一层」，本节解决「整个层级体系如何收敛、如何控制单任务上下文负担」。完整长期循环见 `foundations/self-governance-and-knowledge-evolution.md`。

### 11.1 树形 domain（L1 / L2 / L3）

- 默认 domain 必须支持三层：L1 域根（如 `domains/ui/`）、L2 子域（如 `domains/ui/webui/`）、L3 叶子文件（如 `webui/a11y.md`）。
- 同上位概念的 domain 必须组织为同一 L1 父目录下的 L2 兄弟（例：`gui` 与 `webui` 同属 `ui` L1）。
- 单一 `.md` 文件子主题数 ≥ 5 或行数 > 300 → 必须 promote 为目录型 domain（按自治理循环 §3）。

### 11.2 三件套协议

L1 与有子节点的 L2 域必备：

| 文件 | 受众 | 用途 | 大小硬上限 |
|------|------|------|-----------|
| `index.md` | 人 + LLM | 域门面、规则总论、子文件目录 | ≤ 200 行 / 4 k tokens |
| `_summary.yaml` | 机器 / Loader | 规则要点 bullet（≤ 30 条） + rule_id | ≤ 50 KB |
| `_index.yaml` | 机器 / Loader | 子节点路由、triggers、size_tokens、aliases | ≤ 100 KB |

叶子层（无子节点）允许仅 `index.md` 或单 `.md`，规则直接写在正文中。

### 11.3 rule_id 协议

- 格式：`<domain-flat-path>.r<n>`（路径用 `.` 连接，如 `ops.runbook.r1`、`ui.webui.a11y.r3`）
- 在 `_summary.yaml` 中分配，**单调递增、不重排、不复用**
- 全局唯一性由 `scripts/check_knowledge_health.py` 校验
- PR / commit / revisions / Agent 输出可直接引用（如「违反 `ops.runbook.r2`」）
- **禁止使用语义化 ID**（如 `ops.runbook.environment-check`），避免 ID 漂移

### 11.4 三层索引

- L0：`00-index.yaml`（schema v2）只列 L1 域
- L1：`domains/<l1>/_index.yaml` 列 L2 子域
- L2：`domains/<l1>/<l2>/_index.yaml` 列 L3 叶子（如有）

每个 entry 必备：`id / path / summary / size_tokens / triggers`，可选 `aliases / see_also / canonical_owner`。

### 11.5 token 预算（强制）

- 默认 Agent 单任务治理上下文预算：**8 k tokens**
- 项目可在 `project-governance.yaml` 顶层覆盖：`token_budget: <n>`
- 实际加载由 `scripts/context_loader.py` 控制，加载日志写到 `revisions/_logs/context-trace/<date>.jsonl`
- 装载策略：profile 必装 → trigger 高分（≥ 6）装 `index.md` 全文 → 中分（3 ~ 5）仅装 `_summary.yaml` → 低分跳过
- CI 回归基线：分 profile 跑代表性任务集，平均 cost 不得退化超过 +20%；超阈值触发 `revisions/` candidate

### 11.6 跨域复用约束

- 每条规则有唯一 `canonical_owner`（声明在 `_summary.yaml`）
- 其他域通过 `aliases:` 引用，**严禁复制内容**
- `tags:` 用于跨域检索（如 `tag: a11y` 跨 `ui/webui`、`ui/testing`、`automation/ui-tests`）

### 11.7 生命周期五动作

- **promote**：子文件超阈值 → 目录化
- **demote**：内容萎缩 → 降为单文件或 alias
- **split**：单域职责混杂 → 拆为多个 L2
- **merge**：高度重复 → 合并并留 redirect
- **archive**：90 天 dormant → 默认 bundle 移除；365 天 → `domains/_archive/<year>/`

每个动作必须经 `revisions/` candidate → merged 完整链路，不允许「直接改完不留痕」。

### 11.8 反模式

- 写新 domain 只放 `.md`，不补 `_summary.yaml` / `_index.yaml`
- 给 rule_id 用语义化命名导致漂移
- 复制规则到多个 domain 而不用 `aliases:`
- 让 `00-index.yaml` 直接承载 L2/L3 节点
- 知识库膨胀但不跑月度 health 自检
- 在 candidate 中只写「应该层级化」而不给出 promote/split 具体目标
