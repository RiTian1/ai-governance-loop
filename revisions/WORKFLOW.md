# 候选修订与晋升流程

本文档闭合「实践中发现规则 → 候选修订 → 正式基线」链路。与 `05-ai-collaboration-policy.md` 即时回注纪律配合使用。

## 1. 状态定义

| 状态 | 含义 | 存放位置 |
|------|------|----------|
| `candidate` | 已记录，待评测 | `revisions/YYYY-MM-DD-*.md` 或结构化目录 `revisions/YYYY-MM-DD-<slug>/` |
| `benchmarked` | 已产出评测证据或登记豁免，待评审 | 同上，frontmatter 或 `meta.yaml` `status: benchmarked` |
| `accepted` | 评审通过，待实施 | 同上，`status: accepted` |
| `implementing` | 实施进行中（与 OpenSpec change.status: Implementing 联动） | 同上 |
| `rejected` | 不进入基线，保留依据 | 同上，`status: rejected` |
| `merged` | 已写入 domains/foundations/主文档 | 原文移至 `revisions/archive/<year>/`，`revisions/index.yaml` 更新 |
| `archived` | 长期归档 | `revisions/archive/<year>/<slug>/` |

合法状态机：`candidate → benchmarked → accepted | rejected → implementing → merged → archived`。
逆向回退须新立 revision 解释（违反 `tool.revisions.r5`）。

### 1.0 为什么 `benchmarked` 是评审的前置而非并行

`benchmarked` 回答的是「这条规则有没有用」，`accepted` 回答的是「这条规则该不该进基线」。
两问必须分开：先有证据，再谈取舍。没有评测就评审，评的只是措辞和直觉。

`benchmarked` 允许 `waiver` 通道（见 §4），但**不允许跳过** —— 状态必须经过，
哪怕只写一句「无法评测，理由 X，批准人 Y」。


## 1.1 形态：结构化目录（推荐） vs 单 markdown（兼容）

新立 candidate **应**优先采用结构化目录形态：

```
revisions/<YYYY-MM-DD>-<slug>/
  meta.yaml          ← frontmatter（必须，含 revision_id / status / linked_stories / linked_changes / introduces_rules / 等）
  proposal.md        ← why / what / non-goals
  tasks.md           ← 执行清单
  design.md          ← 技术决策（可选）
  delta/             ← 基线文件 ADDED/MODIFIED/REMOVED 描述
  evidence/          ← 验证证据（health-report / progress-matrix / commits.txt）
```

模板：`templates/revision-structured-directory-template/`。

历史单 markdown 形态保留兼容；新建优先用目录形态。

## 2. 沉淀范围（先分级再写入）

| 范围 | 目标位置 | 是否走本目录 `revisions/` |
|------|----------|---------------------------|
| 变更级 | `openspec/changes/<name>/` | 否 |
| 项目级 | `docs/project-rules.md`、`project-governance.yaml` | 否（除非上升母版） |
| 领域级 | `domains/<domain>/` 查漏补缺 | 否；直接改 domain，母版修订单可选 |
| 全局级 | 主文档 / `foundations/` | **是**（candidate → merged） |

详见 `02-engineering-principles.md` §7–§8。

## 3. 何时写 candidate

- 跨 2 次以上变更仍适用的**全局**约束
- 验证/安全/CI 口径被反复澄清且适用于所有项目类型
- 与现有 domain 冲突或需升格为全局默认

**不要**写 candidate：仅对单个 OpenSpec change 有效、一次性的实现细节（留在 `openspec/changes/<name>/`）。**领域级**规则应直接写入对应 `domains/` 文件。

## 4. 晋升检查表（merged 前）

- [ ] 规则可用一句话陈述，且无项目私有路径硬编码
- [ ] **有评测证据或已登记豁免**（见下方 §4.1，`benchmarked` 态的准入条件）
- [ ] 已标明影响的 `domains/` 或 `foundations/` 目标文件
- [ ] `authority_map` / 旧平行文档已更新或列入 `deprecated_parallel_rules`
- [ ] OpenSpec 相关变更已 archive（若规则来自某次 change）

### 4.1 评测证据的三种合法形式

优先级从高到低。**至少给出一种**，并写进 `evidence/` 或 `meta.yaml` 的
`benchmark` 字段。

**① 前后对比（最强）**

同一任务集，有规则 vs 无规则，配对比较。必须同时给出：

- 效应量与显著性（配对 t 或 Cohen's d）
- **方向一致数**（x/n，不能只给均值）
- 样本量 n（并说明为何这个 n 足够）

> 反例警示：2026-11-19 的 RSI 实验中，同一个指标三次出现"n=6 时 |t|>2、
> n=10 时跌回 1.5"。**只报 n≤6 的显著性视为证据不足**，除非说明该指标方差天然极小。

**② 回归测试（次强）**

明确指出哪条测试从红转绿，附命令与输出。适用于"规则约束的行为可被测试断言"的场景。

**③ 豁免 waiver（兜底）**

无法评测时（规则涉及罕见场景、评测成本远超收益、或属安全底线不需要证明收益），
在 `meta.yaml` 写：

```yaml
benchmark:
  mode: waiver
  reason: <为什么无法评测>
  approved_by: <人名或 handle>
  approved_at: <YYYY-MM-DD>
  expires_at: <YYYY-MM-DD>   # 可选，到期需重新评估
```

**`waiver` 不是免死金牌**：连续两条以上规则走 waiver，须在下一次治理回顾中说明原因。

### 4.2 评测必须用 fresh context

评测**不得复用**规则作者或执行者的会话上下文。理由：用自己写规则时看到的材料
去评测自己写出来的规则，结论必然偏向"有效"。

可接受的做法：

- 另起一个干净会话，只给它规则文本 + 任务 + 源材料
- 用历史归档数据做离线对比（规则生效前 vs 生效后的同类任务）
- 由不同 agent / 不同人执行评测

不可接受：在同一次会话里"我想想这条规则好不好用"就写结论。


## 5. 操作步骤

1. **新建**：复制 `templates/revision-structured-directory-template/`（推荐）或单 md 模板 `templates/governance-revision-template.md` → `revisions/YYYY-MM-DD-<slug>/` 或 `revisions/YYYY-MM-DD-<slug>.md`，`status: candidate`。frontmatter 必须含 `revision_id: rev-<YYYY-MM-DD>-<slug>`（严格格式）。
2. **登记**：在 `revisions/index.yaml` 增加条目（id 用规范 `rev-` 前缀；含 `linked_stories` `linked_changes` `introduces_rules` 字段）。
3. **评测**：`status: benchmarked`；按 §4.1 产出评测证据（前后对比 / 回归测试 / waiver），
   写进 `evidence/` 或 `meta.yaml` 的 `benchmark` 字段。**评测过程须遵守 §4.2 fresh context**。
4. **评审**：`status: accepted | rejected`；记录 `reviewed_by` `reviewed_at`。
   评审时先看评测证据，再看措辞。
5. **实施**：`status: implementing`；编辑目标基线文件；若引入新 rule，需在对应 `_summary.yaml` 的 rule.introduced_by 反向引用本 `revision_id`。
6. **合并**：实施完毕 `status: merged`；移至 `revisions/archive/<year>/`；更新 index 中 path。
7. **关联**：若来自 OpenSpec change，meta.yaml 写 `linked_changes: [<change_id>]`；若来自 BMAD Story，写 `linked_stories: [<story_id>]`。
8. **commit 关联**：post-merge 由 `scripts/link_revision_to_commits.py` 自动 fill `commits` 字段（也可手工跑 `python scripts/link_revision_to_commits.py --revision rev-<id>`）。

## 6. 与 OpenSpec archive 的关系

执行 `/opsx:archive` 前自问：

- 本次是否产生可复用全局规则？
  - **否** → 仅 archive change
  - **是** → 先创建或更新 `revisions/` candidate，再 archive（或 archive 后立即补 candidate，不得拖过 1 个迭代）

详见 `openspec/ARCHIVE-CHECKLIST.md`。

## 7. 废弃平行规范

`project-governance.yaml` 的 `authority_map.deprecated_parallel_rules` 列出旧入口后：

- 旧文档文首加「已废弃，见 xxx」
- 一个发布周期后删除或移入 `docs/archive/`，并从索引移除
