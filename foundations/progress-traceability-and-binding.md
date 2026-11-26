# 进度可追溯与跨工具绑定（Progress Traceability & Cross-Tool Binding）

本 foundation 定义**任何采用本治理母版的项目（包括母版自身）必须遵守的进度自洽规则**：在 BMAD（规划层）、OpenSpec（变更层）、`revisions/`（全局基线变更层）三套工具并存时，如何让三者的状态、内容、提交记录**强绑定、自动校验、永远可双向追溯**，而不是依赖人工对账。

它与 `02-engineering-principles.md §7`（经验沉淀范围）、`foundations/self-governance-and-knowledge-evolution.md`（长期循环）、`revisions/WORKFLOW.md`（基线变更状态机）正交：

- §7 解决「规则写到哪一层」
- self-governance 解决「层级体系本身如何持续演化」
- WORKFLOW 解决「全局基线变更的状态流转」
- **本 foundation 解决「跨工具的进度与内容必须实时互相印证」**

> 任何"靠人对账"的绑定都不能算绑定。本 foundation 强制以工具校验闸口取代人工自觉。

---

## 1. 核心命题

- **绑定 ≥ 同步**：仅工具镜像（如 `sync-bmad-skills.py`）只解决"工具自身镜像"，不解决"语义层进度一致"
- **任意一端可无声漂移即视为治理失败**：必须由工具检测 drift（状态不一致 / 内容哈希不一致 / 反向引用缺失）
- **追溯必须双向**：从 PRD 任意 FR 必须能反向定位实际 commit 与 spec delta；从任意 commit 必须能正向定位规划上下文与决策依据
- **只有可机器追溯的改动才算改动**：commit 不引用 Story / Revision / Rule 视为违规
- **母版自身必须 dogfood**：母版的演化也走 BMAD → revisions / OpenSpec 的双向绑定，否则规则没有信用

---

## 2. 标识协议（identifier protocol）

每个项目必须在 `project-governance.yaml` 顶层声明 `project_id`（kebab-case），所有跨工具 ID 以 `<project_id>` 为前缀。

| 实体 | ID 格式 | 例子 | 主仓位置 |
|------|---------|------|----------|
| **Epic** | `<project_id>.E<NN>` | `gov.E04` | `_bmad/<project>/epics/E04-*.md` |
| **Story** | `<project_id>.S<NN>.<MM>` | `gov.S04.01` | `_bmad/<project>/stories/04.01-*.md` |
| **PRD FR** | `<project_id>.FR<N>` | `gov.FR12` | `_bmad/<project>/prd.md` |
| **PRD NFR** | `<project_id>.NFR<N>` | `gov.NFR03` | 同上 |
| **OpenSpec change** | `<project_id>.C<NN>.<MM>` | `gov.C04.01` | `openspec/changes/<change-name>/` |
| **Revision** | `rev-<YYYY-MM-DD>-<slug>` | `rev-2026-05-26-progress-traceability-binding` | `revisions/<id>/` 或 `revisions/<YYYY-MM-DD>-<slug>.md` |
| **Rule** | `<domain-flat-path>.r<n>` | `tool.binding.r3` | `_summary.yaml` 的 `rules[].id` |
| **Test** | `<project_id>.T<NN>.<MM>.<KKK>` | `gov.T04.01.001` | 测试代码内部 |

母版自身使用 `project_id: gov`。

### 2.1 强约束

- 一个 **Story 必须对应 0 或 1 个 OpenSpec change**（小于一个 change 的工作不立 change，但仍立 Story）
- 一个 **Story 必须对应 0 或 1 个 Revision**（仅当 Story 引入"全局级"规则时才立 Revision；按 `02-engineering-principles.md §7`）
- 一个 **Revision 可对应 1 或多个 Story**（一次 revision 可能由多个 Story 共同推进而成）
- 一个 **Rule 必须由唯一的 Revision 引入**（`introduced_by` 字段格式：`rev-<YYYY-MM-DD>-<slug>`，不再允许任意字符串）

---

## 3. 三向反向引用（必填字段）

### 3.1 Story frontmatter（写在 BMAD story 文件顶部）

```yaml
---
story_id: gov.S04.01
epic_id: gov.E04
title: progress traceability matrix CLI
prd_refs: [gov.FR05, gov.FR06, gov.NFR03]
status: in-progress           # Draft | Approved | InProgress | Review | Done | Archived
created_at: 2026-05-26
last_updated: 2026-05-27
acceptance_criteria_hash: <sha1-of-AC-block>
linked_change: gov.C04.01     # 可空（小工作不立 change）
linked_revision: rev-2026-05-26-progress-traceability-binding
introduces_rules: [tool.binding.r1, tool.binding.r2]
test_refs: [gov.T04.01.001]
commits: []                   # 由 link_revision_to_commits.py 自动 fill
---
```

### 3.2 OpenSpec change `proposal.md` frontmatter

```yaml
---
change_id: gov.C04.01
linked_story: gov.S04.01
linked_revision: rev-2026-05-26-progress-traceability-binding
prd_refs: [gov.FR05, gov.FR06]
status: implementing          # Proposed | Approved | Implementing | Implemented | Archived
spec_delta_hash: <sha1-of-ADDED-MODIFIED-blocks>
---
```

### 3.3 Revision `meta.yaml`（结构化目录形态）

```yaml
revision_id: rev-2026-05-26-progress-traceability-binding
title: 进度可追溯与跨工具绑定
status: candidate             # candidate | benchmarked | accepted | rejected | implementing | merged | archived
linked_stories: [gov.S04.01, gov.S04.02]
linked_changes: [gov.C04.01]
prd_refs: [gov.FR05, gov.FR06, gov.NFR03]
introduces_rules: [tool.binding.r1, tool.binding.r2, tool.binding.r3]
modifies_rules: []
removes_rules: []
affected_baselines:
  - foundations/progress-traceability-and-binding.md
  - domains/tooling/
  - revisions/WORKFLOW.md
commits: []                   # 由 link_revision_to_commits.py 自动 fill (post-merge)
created_at: 2026-05-26
reviewed_by: null
reviewed_at: null
merged_at: null
```

### 3.4 Rule `_summary.yaml` 反向引用

```yaml
rules:
  - id: tool.binding.r1
    text: 一个 Story 与一个 OpenSpec change 必须 1:0..1 对应
    severity: must
    introduced_at: 2026-05-26
    introduced_by: rev-2026-05-26-progress-traceability-binding   # 必须是合法 revision_id
    introduced_by_story: gov.S04.01                                # 可空：仅当来自 BMAD 时填
```

### 3.5 Commit message 协议

```
<type>(<story_id>): <subject>

Story: <story_id> [<status-from> -> <status-to>]
Change: <change_id|none>
Revision: <revision_id|none>
Rules: <rule_id_1>+, <rule_id_2>~      ← + 新增, ~ 修改, - 删除
PRD: <fr_id_1>, <fr_id_2>
```

`Story:` 行**必填**；`Change:` `Revision:` `Rules:` 至少一行非 `none`。`pre-commit` 阻断违规。

约定：`<type>` ∈ `feat` / `fix` / `refactor` / `docs` / `chore` / `test`；`<subject>` 用**中文**描述。
提交后必须 push 远端；涉及分支管理时从主分支拉新分支、解决冲突后再 commit + push，
**merge 由用户执行**（完整检查点动作链见 `05-ai-collaboration-policy.md` §7.3 / `tool.binding.r10`）。

---

## 4. 状态机（state machine）

### 4.1 三端合法对齐表

| Story 状态 | OpenSpec change 状态 | Revision 状态 | 备注 |
|-----------|---------------------|---------------|------|
| Draft | — | — | 仅规划层，未立 change/revision |
| Approved | Proposed | candidate | change/revision 同步立项 |
| Approved | Proposed | benchmarked | 评测完成、待评审（revision 自有状态，不推动 change 端） |
| Approved | Approved | accepted | 评审通过 |
| InProgress | Implementing | accepted | 实施中 |
| Review | Implemented | accepted | 实施完毕，PR 评审 |
| Done | Implemented | accepted | 代码已 merge 到主分支 |
| Done | Archived | merged | OpenSpec archive 完成，revision 合并到基线 |
| Archived | Archived | archived | 长期归档 |

> **Story 可不立 change**（小工作或仅规则演化）：此时 change 端为 `—`，revision 端按其自身生命周期推进。
> 例如"边实施边立候选 revision、未立 OpenSpec change"是合法状态：`(InProgress, —, candidate)` / `(Approved, —, candidate)` /
> `(Review/Done, —, accepted)` / `(Done, —, merged)` / `(Archived, —, archived)`。`check_progress_consistency` 的 T3 接受这些三元组。

### 4.2 漂移定义

- **状态漂移**：三端状态不在合法对齐表里的任意组合
- **内容漂移**：`acceptance_criteria_hash` 与对应 change 的 `spec_delta_hash` 任一端变更而另一端未跟随更新
- **反向引用漂移**：Story 引用的 change/revision 不存在；revision 引用的 story 不存在；rule 引用的 revision 不存在
- **commit 漂移**：commit message 缺 Story/Revision/Rules 行；引用的 ID 不存在

任一漂移由 `scripts/check_progress_consistency.py` 检测，CI 阻断。

### 4.3 两条强制规则（MUST）

> 这两条对症"已完成 Story 仍挂活跃工作"与"completed/archived 提前写入"两类实战漂移（见 `domains/tooling/progress-binding/_summary.yaml` r8 / r9）。

1. **新工作不得挂已完成 Story（`tool.binding.r8`，MUST）**：任何新增 / 收敛 / 修补工作 MUST 新建 story 或 change 承载；
   **禁止把新工作挂到状态为 `done` / `archived` 的 Story 上**。`check_progress_consistency` 的 **T9** 检出
   "active change（proposed/approved/implementing/implemented）的 `linked_story` 指向 done/archived Story" 的违例。
2. **状态字段是最后一步且必须联动（`tool.binding.r9`，MUST）**：`completed` / `done` / `archived` / `active_sprint` / `status=merged`
   是闭环的**最后一步**，MUST 在 `check_progress_consistency.py` 通过（exit 0）后、且与其它工件联动后才写入。
   终态 Story（done/archived）**不得**指向仍为 `candidate` 的 revision（状态提前写入 = 漂移）。`check_progress_consistency` 的 **T10** 检出。

---

## 5. 与 self-governance 五步循环的咬合

| self-governance 步 | 本 foundation 强制动作 |
|--------------------|------------------------|
| 观察（Observe） | 月度跑 `scripts/gen_progress_matrix.py` 出 traceability matrix |
| 诊断（Diagnose） | matrix 中所有 drift 行 + state-machine 违规 + 孤立 Story / change / revision 列入 health report |
| 决策（Decide） | drift 修复或规则升级走 candidate revision；revision 自身按本 foundation 立结构化目录 |
| 执行（Execute） | 修复后 status 转 accepted/merged；archive 时由脚本核验三端对齐 |
| 回归（Regress） | 下一轮 matrix 中 drift 数应回归到 0 |

---

## 6. 适用范围

- **母版仓库**（`mother-repo-root`）：完整执行；母版自身的演化即受 BMAD/OpenSpec/Revision 三向绑定
- **业务项目**（`docs-governance-subtree`）：默认开启 Story+Commit 绑定；revision 仅在引入"全局级"规则时使用；OpenSpec change 与 BMAD 按项目 manifest 决定
- **小项目（≤ 3 人月）**：可关闭 BMAD（同 `frameworks.bmad.enabled: false` 默认），仅保留 OpenSpec change ↔ commit 绑定 + 本 foundation 的 §3.4 §3.5 §4 部分

具体启用矩阵在 `domains/tooling/progress-binding/index.md` §3。

---

## 7. 反模式

- 在多个文件用不同的命名风格写 Story / change / revision ID（如 `S001` `S-04-01` `gov-04-01`）
- commit message 不写 Story / Revision 行，只靠 git log 模糊溯源
- Rule 的 `introduced_by` 字段写非 revision_id 的自由文本
- 改了 Story AC 但不更新对应 change 的 spec delta（"PM 说我更新了，工程没看到"）
- merged 状态的 revision 不归档，长期堆在 `revisions/` 根目录
- BMAD `frameworks.bmad.enabled: true` 但项目没建任何 Epic / Story 文件（开关与产出不一致）
- 在 `_summary.yaml` 加 rule 但不立 revision（违反 §11.7 生命周期五动作）

---

## 8. 完成判定

一个项目（含母版）可视为「具备本 foundation 完整能力」的最低标准：

- [ ] `project-governance.yaml` 顶层声明 `project_id`
- [ ] 启用 `enabled_foundations: [progress-traceability-and-binding]`
- [ ] 启用 `enabled_domains: [tooling/progress-binding, tooling/revisions]`（按项目规模可选 `tooling/bmad` `tooling/openspec`）
- [ ] `scripts/check_progress_consistency.py` 与 `scripts/gen_progress_matrix.py` 在 CI 中可执行
- [ ] `scripts/check_commit_message.py` 在 pre-commit 中阻断
- [ ] 至少一份 revision 采用结构化目录形态（`revisions/<id>/meta.yaml + proposal.md + tasks.md + delta/`）
- [ ] traceability matrix 第一次跑出，drift 数为 0 或全部有合法豁免

完成判定与 self-governance §11 的母版健康标准合并构成"治理母版长期可用"的双重门禁。
