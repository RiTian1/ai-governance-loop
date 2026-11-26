---
name: governance-continue
description: 治理收尾检查点。仅当用户明确要求收尾、归档或提交，或开启新变更且当前变更已进入收尾时使用。普通继续、原生 resume、上下文压缩均不触发。
---

# governance-continue — 收尾检查点（tool.binding.r10 的可执行封装）

> 本技能只处理真实阶段收尾。CLI 的原生会话恢复、压缩和搜索先运行；普通继续沿当前任务推进。
> 仅在收尾触发条件满足时，执行归档、人工验证和提交步骤。
> 规范同源：`05-ai-collaboration-policy.md` §7.3、`domains/tooling/progress-binding`（`tool.binding.r10`）、
> `foundations/progress-traceability-and-binding.md` §3.5。**冲突时以这些治理文档为准。**

## 触发条件（任一命中即运行本 skill）

1. 用户明确要求收尾、归档或提交当前变更；
2. agent 即将开启**下一个新的 OpenSpec 变更**，且当前变更已达到收尾阶段。

普通“继续”、CLI 原生 resume、上下文压缩和询问进度均不触发此技能。

## 执行步骤（按序，不得跳步）

### 步骤 1 — 查工作区并归因

```
git status
python scripts/check_worktree_hygiene.py
```

把当前变动分成两类：
- **真实改动**（`* real`）：本段任务的产出，候选提交对象。
- **生成产物 churn**（`~ generated`）：BMAD 薄壳 / OpenSpec 壳 / 导出规则 / `.agents/skills` 镜像等。
  这些**不混入本次提交**——要么重生成后成组单独提交，要么 `git checkout -- <路径>` 丢弃
  （`ops.housekeeping.r10`）。

若工作区没有需要收敛的真实改动，也没有待归档的 change → 直接进入下一步任务，无需归档/提交。

**事实落账核对（ops.runtime-context.r9）**：回看本段会话，使用者是否提供过可复用事实
（凭证引用 / 地址 / 端口 / 环境 / 接口约定）？有 → 确认已写入 `runtime-context.yaml`
（执行域）或 `docs/project-rules.md`（开发域），未落账的**现在补写**；凭证只写引用禁明文。
可跑 `python scripts/check_knowledge_health.py --check-runtime-context` 校验清单健康。

### 步骤 2 — 判定当前 change 能否归档

对"当前活跃的 OpenSpec change"检查：
- `openspec/changes/<change>/tasks.md` 是否全部勾选完成；
- verify 是否通过（可跑 `/opsx:verify` 或人工确认验收标准满足）；
- `python scripts/check_progress_consistency.py` 是否 **exit 0**。

任一不满足 → **不归档**，先补齐（继续实施 / 消除漂移），或仅收敛提交进行中的真实改动，然后停在此处说明原因。

### 步骤 3 — 询问用户「人工验证标志」（STOP，等待确认）

**归档是高风险状态变更，必须先经用户确认。** 用提问明确询问：

> "当前变更满足归档条件。是否勾选人工验证标志并归档提交？"

选项建议：`确认归档` / `我先自己验证再说` / `只提交进行中改动、暂不归档`。

- **未得到用户确认前，禁止归档、禁止写 `archived`/`done` 等终态字段**（`tool.binding.r9`）。
- 得到确认后，把用户的验证结论按 `04-verification-policy.md` 结构化留痕（记入 change 的验证记录 /
  commit body），再继续。

### 步骤 4 — 归档 + 代码与工件一并提交

用户确认后：
- 归档 OpenSpec change（`/opsx:archive` 或对应流程）；
- 代码改动与治理工件（`specs/`、`tasks.md`、Story、revision、`_logs/sync-ledger.md`）
  放进**同一次提交**——禁止"归档与实现分两次提交"（见 `AGENTS.md` 禁止项）。

### 步骤 5 — 校验 BMAD PRD ↔ OpenSpec 双向同步

- BMAD PRD 的 FR ↔ change 的 `prd_refs` 互相引用完整；
- Story `acceptance_criteria_hash` ↔ change `spec_delta_hash` 联动一致（`tool.binding.r3`）。
- 有漂移 → **先消除再提交**（更新滞后的一端），不得带漂移归档。

### 步骤 6 — 按规范提交并 push

Commit message：

```
<type>(<scope>): <中文描述>

Story: <story_id> [<status-from> -> <status-to>]
Change: <change_id|none>
Revision: <revision_id|none>
Rules: <rule_id>+, <rule_id>~
PRD: <fr_id>, ...
```

- `<type>` ∈ `feat` / `fix` / `refactor` / `docs` / `chore` / `test`；描述用**中文**。
- `Story:` 行必填；`Change/Revision/Rules` 至少一行非 `none`（`tool.binding.r4`）。
- 提交后 **push 到远端**。

### 步骤 7 — 涉及分支管理时

- 从**主分支拉取新分支**（确保基于最新主分支），在新分支上工作；
- 若有冲突，**解决冲突后**再 `commit` + `push`；
- **merge 由用户执行** —— agent 不得自行把分支 merge 进主分支。

## 完成判定

- 工作区：真实改动已提交或已显式说明保留原因；生成产物 churn 未混入本次提交；
- `check_progress_consistency.py` exit 0；
- 状态字段（archived/done）是在自检通过、用户确认后才写入；
- 已 push；分支场景下已把 merge 交还用户。

## 边界

- 本 skill 是 `tool.binding.r10` 的**执行封装**，不引入新规则；语义以治理文档为准。
- 无 `.git` 的项目：跳过 push/分支步骤，改由 `_logs/sync-ledger.md` 台账承担审计（便携治理默认场景）。
- 破坏性操作、真正的范围变更、只有用户能提供的输入 —— 停下问用户，不擅自推进。
