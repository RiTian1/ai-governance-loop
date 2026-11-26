# OpenSpec 接入与边界

OpenSpec（`@fission-ai/openspec`）在本治理母版的角色：**变更级 spec 变更管理**——为每个独立功能/修复立 change，含 proposal、tasks、spec delta，archive 时合并 delta 到主 spec。

## 1. 启用条件

| 条件 | 说明 |
|------|------|
| `frameworks.openspec.enabled: true` | 母版默认 true，业务项目继承 |
| `openspec/` 目录存在 | 含 `specs/` 与 `changes/` |
| OpenSpec CLI 可执行 | `npm exec openspec` 或 `/opsx:*` 命令 |

## 2. 工作流（继承 `AGENTS.md` 默认工作流）

```
/opsx:propose | /opsx:new   ← 立 change
        ↓
/opsx:apply                  ← 实施 tasks
        ↓
/opsx:verify                 ← 验证 acceptance
        ↓
/opsx:archive                ← 归档到 specs/
```

## 3. 与 Revisions 的衔接（关键）

OpenSpec change archive **前**必须自问（继承 `revisions/WORKFLOW.md §6`）：

> 本次是否产生可复用全局规则？
> - 否 → 仅 archive change
> - 是 → 先创建或更新 `revisions/<id>/` candidate，再 archive

具体协议见 `tooling/revisions/index.md §3` 与 `openspec/ARCHIVE-CHECKLIST.md`。

## 4. 与 progress-binding 的衔接

每个 OpenSpec change 的 `proposal.md` **必须**含 `foundations/progress-traceability-and-binding.md §3.2` 定义的 frontmatter：

- `change_id`（格式 `<project_id>.C<NN>.<MM>`）
- `linked_story` / `linked_revision`
- `prd_refs`、`status`、`spec_delta_hash`

## 5. archive 必检（继承 02 §10）

OpenSpec archive 与配套实现代码必须**原子提交**（同一 commit 含归档工件 + 代码 + 测试），并**push 到主协作分支**（默认 `origin/master`）。

具体检查清单见 `openspec/ARCHIVE-CHECKLIST.md`。

## 6. 与 BMAD 的边界

见 `tooling/bmad/index.md §3`。BMAD 负责规划层产出，OpenSpec 负责 spec 变更与 archive。**禁止双轨记录同一份 spec**（`tool.r2`）。

## 7. 验证点

- 每个 change 目录含 `proposal.md` + `tasks.md` + 必要时的 `design.md`
- archive 完成后该 change 移到 `openspec/changes/archive/`，且对应 spec 文件确实更新
- proposal.md frontmatter 完整（由 `scripts/check_progress_consistency.py` 校验）

## 8. 反模式

- archive 完成但配套代码在另一个 commit（违反 02 §10）
- archive 完但未 push（违反 02 §10）
- proposal.md 无 frontmatter
- change 目录长期 candidate 状态（> 30 天 → 由 `check_knowledge_health.py --check-stale-revisions` 类比延伸覆盖）
