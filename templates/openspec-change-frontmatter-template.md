---
# OpenSpec change proposal.md frontmatter 模板
# 规范: foundations/progress-traceability-and-binding.md §3.2
# 文件位置: openspec/changes/<change-name>/proposal.md

change_id: <project_id>.C<NN>.<MM>           # 例: gov.C04.01
linked_story: <project_id>.S<NN>.<MM>        # 必填（与 story.linked_change 对齐）
linked_revision: null                         # 可空：仅当引入全局规则时

prd_refs: []                                  # [<project_id>.FR<N>, ...]

status: proposed                              # proposed | approved | implementing | implemented | archived

# 由 check_progress_consistency.py 计算并校验
spec_delta_hash: null
---

# <change-title>

## Why

- 

## What Changes

- ## ADDED ...
- ## MODIFIED ...
- ## REMOVED ...

## Non-goals

- 

## Risk

- 

## Tasks (see tasks.md)

详见 `tasks.md`。
