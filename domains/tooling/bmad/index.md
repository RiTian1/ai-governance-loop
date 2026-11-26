# BMAD 接入与边界

BMAD（Breakthrough Method for Agile-driven Development）在本治理母版的角色：**项目级规划层**——产出 Project Brief、PRD、Architecture、Epic、Story（含 acceptance criteria 与 dev notes）。BMAD **不**承担 spec 变更管理与 archive，那是 OpenSpec 的职责。

## 1. 启用条件

| 条件 | 说明 |
|------|------|
| `frameworks.bmad.enabled: true` | 项目 manifest 显式开启 |
| `_bmad/<project>/` 目录存在 | 物理证据：开关启用必须有 brief / prd / architecture / epics / stories |
| 至少存在 1 个 epic 与 1 个 story | 否则视为"开关空转"（违反 `tool.r1`） |

母版自身：`frameworks.bmad.enabled: false`，但 dogfood 时可临时开启用于规划母版自身演化。

## 2. 单源策略（继承 `BMAD-SINGLE-SOURCE.md`）

```
_bmad/_config/skill-manifest.csv
        │
        ▼
scripts/sync-bmad-skills.py --prune
        │
        ▼ 重建 .claude/skills/bmad-*/SKILL.md（薄壳）
```

- 修改 BMAD workflow / steps / templates **只改 `_bmad/`**
- `.claude/skills/bmad-*/` 是机器生成的薄壳，**不进版本控制大块内容**
- 提交时勿"恢复" `.claude/skills/bmad-*/` 目录下的 step 副本

## 3. 与 OpenSpec 的边界

| 责任 | BMAD | OpenSpec |
|------|------|----------|
| Project Brief / PRD | ✓ | — |
| Architecture | ✓ | — |
| Epic / Story 拆分 | ✓ | — |
| Story 中的 dev notes | ✓ | — |
| Spec delta（## ADDED/MODIFIED/REMOVED） | — | ✓ |
| Tasks（执行清单） | — | ✓ |
| Archive（合并到主 spec） | — | ✓ |

**Story 引用 change，不复制 spec 内容**（`tool.r2`）。

## 4. 与 progress-binding 的衔接

每个 BMAD Story 文件**必须**含 `foundations/progress-traceability-and-binding.md §3.1` 定义的 frontmatter：

- `story_id`、`epic_id`、`prd_refs`、`status`
- `linked_change`（指向对应 OpenSpec change）
- `linked_revision`（仅当 Story 引入全局规则时）
- `acceptance_criteria_hash`（自动计算）
- `commits`（由 `link_revision_to_commits.py` 自动 fill）

## 5. 验证点

- BMAD 工件目录无大块 step 副本（由 `scripts/check_knowledge_health.py --check-orphans` 间接覆盖）
- Story frontmatter 完整（由 `scripts/check_progress_consistency.py` 校验）
- 每个 epic 至少 1 个 story；每个 story 至少 1 个 acceptance criterion

## 6. 反模式

- 在 `_bmad/` 与 `.claude/skills/bmad-*/` 双向编辑（违反单源）
- BMAD `enabled: true` 但 `_bmad/<project>/` 为空目录
- Story 文件没 frontmatter，靠 git log 反推归属
- BMAD Story 内复制 OpenSpec spec 块（应只放引用 ID）
