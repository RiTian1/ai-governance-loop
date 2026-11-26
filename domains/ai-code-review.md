# AI 代码评审域（L1）

rule_id 前缀：`review.r*`

本域定义**AI 生成代码进入主干前后的评审纪律**。它不是风格指南，是**责任分配协议**——解决的是
"AI 写得比人读得快"之后，团队如何在不降低速度的前提下，仍然知道改动是什么、谁为它负责。

关联：`foundations/ai-assisted-review-and-accountability.md`（原理）、
`04-verification-policy.md`（验证层级）、`foundations/progress-traceability-and-binding.md`（可追溯）。

## 为什么需要这个域

三个事实，缺一个这套规则都不成立：

1. **产能不对称**：AI 一天能产出人一周读不完的 diff。传统"逐行读"的评审方式在量上已经失效。
2. **上下文缺失**：AI 生成的改动天然缺少"为什么这么改"的背景。没有背景的 diff，评审只能审语法。
3. **责任真空**：出事要回滚、要停机、要交代时，AI 不承担任何责任。责任必须落在自然人身上。

对应三条支柱：**分层校验（Double Check）**、**上下文对齐（Cross Check）**、**签字担责（Accountability）**。

## 核心规则

### 分层校验（Double Check）

- `review.r1`：**机器能判的必须机器判**。lint / 单测 / 类型检查 / 静态分析能覆盖的项，人工 MUST NOT 重复核对。
  人工评审只审机器判不了的三类：设计是否合理、是否符合业务预期、是否存在跨模块风险。
- `review.r2`：**AI 参与必须留痕**。AI 生成或大幅改写的变更 MUST 在提交信息或 PR 描述中标注
  （`ai-assisted: <tool>` 或 `Co-authored-by:` trailer）。未标注视为隐瞒，按违规处理。
- `review.r3`：**风险必须分级**。每个变更 MUST 声明 `risk_level: low | medium | high`，判据见下表。
  未声明级别的变更按 `high` 处理（fail-closed）。
- `review.r4`：**放行标准按级配置**，不得一律走人工全审：

  | risk_level | 机器校验 | AI 评审 | 人工 |
  |---|---|---|---|
  | low（文档 / 测试 / 注释 / 配置注释） | 必过 | 可选 | 免签（记录自动化放行） |
  | medium（业务逻辑 / 单模块重构） | 必过 | MUST | MUST 至少 1 人 |
  | high（数据迁移 / 权限 / 鉴权 / 删除 / 公共接口破坏性变更） | 必过 | MUST | MUST 双人，且至少 1 人非作者 |

- `review.r5`：**收窄优先**。规则默认只约束"必须对"的部分（安全、数据、权限、可回滚），
  不追求"全部风格统一"。扩大规则覆盖面 MUST 走 revision，不得在评审里临时加码。

### 上下文对齐（Cross Check）

- `review.r6`：**意图与影响面是评审前提**。PR 描述 MUST 包含三节：
  `## 意图`（为什么改、解决什么问题）、`## 影响面`（改了哪些模块、可能波及什么）、
  `## 验证`（跑了什么、证据在哪）。缺任一节，评审 MUST NOT 开始。
- `review.r7`：**变更必须可追溯**。PR MUST 关联到已有的 Story / Change / Revision 之一
  （复用 `tool.binding.r*` 的绑定协议）；无载体的变更视为计划外变更，MUST NOT 合入。
- `review.r8`：**历史评审可检索**。同一模块的历史 PR 结论 MUST 能被后续评审查到
  （沉淀到 `_logs/review-index.md` 或等价索引），避免重复踩坑。

### 签字担责（Accountability）

- `review.r9`：**AI 不可作为责任主体**。签字人 MUST 是自然人；AI 可以产出、可以初审、可以给建议，
  MUST NOT 出现在 `signed_by` 字段里。
- `review.r10`：**签字语义是"接受风险"，不是"已读懂"**。签字表示：
  "我已看到这次变更的意图、影响面与验证证据，并接受它上线后的风险——**包括我没有逐行读完的部分**。"
  这是审计责任链的一环，不是能力背书。
- `review.r11`：**签字必须留痕且可机检**。合入前 MUST 存在签字记录，字段至少包含
  `signed_by`（自然人）、`signed_at`（ISO 8601）、`risk_level`、`evidence_refs`。
  记录位置：PR 描述末尾的 `## 签字` 段，或 `.项目A/reviews/<change>.yaml`。

## 落地机制

| 机制 | 载体 | 强制方式 |
|---|---|---|
| 评审模板 | `templates/pr-review-template.md` | PR 模板必填，缺项即红（`review.r6`/`r11`） |
| 门禁校验 | `scripts/check_review_gate.py` | CI / pre-push 调用，缺项 exit 1 |
| 风险分级 | 模板 `risk_level` 字段 | 未填按 high（`review.r3`） |
| 双签规则 | 模板 `signed_by` 数量 | high 少于 2 人 exit 1（`review.r4`） |
| 人工兜底 | 评审人 | MUST 有"拒绝合入"权，且该权力不得被自动化绕过（`review.r4`） |

## 与既有域的关系

- **不替代** `04-verification-policy.md`：验证回答"跑没跑过"，本域回答"谁看了、看懂到什么程度、谁担责"。
- **不替代** `tool.binding.r*`：绑定协议管"变更挂在哪"，本域管"挂在正确载体的变更如何被审"。
- **扩展** `check_commit_message.py`：本域新增 `risk_level` / `ai-assisted` / `signed_by` 三项 trailer 校验，
  由 `check_review_gate.py` 承担，不改动既有 commit 协议。

## 常见误用

| 误用 | 为什么不行 | 正确做法 |
|---|---|---|
| "AI 写的，所以不用审" | 责任没转移，出事还是人担 | 按 `review.r4` 分级审，AI 初审 + 人签字 |
| "AI 审过就行了" | AI 不承担后果，且缺少业务上下文 | AI 评审作为第一道，人工审设计合理性（`review.r1`） |
| "全部高风险，全部双签" | 规则过宽会导致绕过，实际等于没有规则 | 按 `review.r3` 如实分级，收窄优先（`review.r5`） |
| "签字 = 我读过了每一行" | 这个承诺在 AI 时代不可能兑现，等于虚假背书 | 签字 = 接受风险（`review.r10`），并说明没读的部分 |
