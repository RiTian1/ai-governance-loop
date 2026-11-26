---
# BMAD Story frontmatter 模板
# 规范: foundations/progress-traceability-and-binding.md §3.1
# 文件位置: _bmad/<project_id>/stories/<NN.MM>-<slug>.md

story_id: <project_id>.S<NN>.<MM>          # 例: gov.S04.01
epic_id: <project_id>.E<NN>                # 例: gov.E04
title: <story 标题>
prd_refs: []                                # [<project_id>.FR<N>, <project_id>.NFR<N>, ...]

status: draft                               # draft | approved | inprogress | review | done | archived

created_at: YYYY-MM-DD
last_updated: YYYY-MM-DD

# 内容哈希（由 check_progress_consistency.py 计算填回）
acceptance_criteria_hash: null

# 反向引用
linked_change: null                         # 例: <project_id>.C<NN>.<MM>，可空
linked_revision: null                       # 例: rev-YYYY-MM-DD-<slug>，可空（仅当引入全局规则时）

# 影响声明
introduces_rules: []                        # 仅当对应 revision merged 后引入（与 revision.introduces_rules 对齐）
test_refs: []                               # [<project_id>.T<NN>.<MM>.<KKK>, ...]

# 关联 commits（由 link_revision_to_commits.py 自动 fill）
commits: []
---

# <Story 标题>

## Story

As a <role>, I want <capability> so that <outcome>.

## Acceptance Criteria

> 每条 AC 单独一行；本节文本会被 hash 进 acceptance_criteria_hash。改 AC = 改 hash。

- AC1: ...
- AC2: ...
- AC3: ...

## Dev Notes

> 给执行 agent 的上下文：架构提示、相关代码位置、已知约束。

- 

## Tasks（实施清单）

> 与对应 OpenSpec change 的 tasks.md 同步；本节用于 story 内部跟踪。

- [ ] T1 ...

## Validation

- [ ] V1 ...

## Definition of Done

- [ ] DoD1 ...
