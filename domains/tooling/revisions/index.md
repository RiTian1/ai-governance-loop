# Revisions 接入与状态机

`revisions/` 在本治理母版的角色：**全局基线变更的候选 → 评审 → 合并通道**——为升格到 `foundations/` / `domains/` / 主文档（`01-08`）的规则提供可追溯路径。

它与 OpenSpec change 互补：OpenSpec 管"变更级 spec delta"，Revisions 管"全局基线变更"。

## 1. 状态机（升级版，含 benchmarked 与 implementing 中间态）

| 状态 | 含义 | 文件位置 |
|------|------|----------|
| `candidate` | 已记录、待评测 | `revisions/<YYYY-MM-DD-slug>/` 或单 md |
| `benchmarked` | 已产出评测证据或登记豁免、待评审 | 同上，`meta.yaml.status: benchmarked` |
| `accepted` | 评审通过、待实施 | 同上，`meta.yaml.status: accepted` |
| `implementing` | 实施中（关联 OpenSpec change.status: Implementing） | 同上 |
| `merged` | 已写入基线文件，等待归档 | 同上 |
| `archived` | 已移到 `revisions/archive/<year>/` | `revisions/archive/<year>/<id>/` |
| `rejected` | 不进入基线 | 保留作依据，可在 archive |

合法转换由 `scripts/check_progress_consistency.py` 校验。

## 2. 结构化目录协议（与单文件兼容）

新立 candidate **应**采用结构化目录形态（继承 OpenSpec change 的 idea，但一级目录在 `revisions/` 下）：

```
revisions/<YYYY-MM-DD-slug>/
  meta.yaml          ← frontmatter + 反向引用（必须）
  proposal.md        ← why / what / non-goals
  tasks.md           ← 执行清单（可机器勾）
  design.md          ← 技术设计（可选）
  delta/             ← 实际改动的基线文件 ADDED/MODIFIED/REMOVED 描述
    foundations/<file>.md.added.md
    domains/<path>/<file>.modified.md
    02-engineering-principles.md.modified.md
  evidence/          ← 验证证据
    health-report-before.md
    health-report-after.md
    commits.txt      ← 由 link_revision_to_commits.py 自动 fill
```

历史已存在的单 markdown 形态（如 `2026-03-25-bootstrap-adoption-layer.md`）可继续以单文件存在，但**新立 candidate 优先用结构化目录**。

## 3. 与 OpenSpec archive 的衔接（必读）

执行 `/opsx:archive` 前必检（继承 `revisions/WORKFLOW.md §6`）：

```
/opsx:archive 触发
  ↓ 自问：是否产生可复用全局规则？
  ├─ 否 → 仅 archive change（OpenSpec 内闭环）
  └─ 是 → 先创建/更新 revisions/<id>/candidate，再 archive
            ↓
            revision.linked_changes += [<change_id>]
            change.linked_revision = <revision_id>
```

不得拖过 1 个迭代补 revision（违反 `tool.openspec.r4`）。

## 4. revisions/index.yaml 协议

机器可读索引必须列出**全部** candidate / benchmarked / accepted / implementing / merged / archived 的 revision；每条含：

```yaml
- id: <revision_id>
  title: <title>
  status: <state>
  path: <相对路径>
  trigger_summary: <一句话>
  linked_stories: [...]      # 可空
  linked_changes: [...]      # 可空
  introduces_rules: [...]    # 可空
```

由 `scripts/check_progress_consistency.py` 校验：
- index.yaml 中每条 path 必须真实存在
- index 中 status=merged 的 revision 实际位置必须在 `revisions/archive/<year>/`
- 文件系统中存在的 revision 必须在 index 中（无孤儿）

## 5. 反模式

- 立 candidate 但不在 `revisions/index.yaml` 登记
- merged 状态的 revision 长期堆在 `revisions/` 根（未归档）
- revision 引入新 rule 但 `_summary.yaml` 中 rule 的 `introduced_by` 不指回该 revision
- candidate 写"应该层级化"但不给 promote/split 具体目标（违反 11.8）
- candidate > 30 天未推进且未标 rejected（由 `check_knowledge_health.py --check-stale-revisions` 报警）

## 6. 验证点

- index.yaml 完整且无孤儿
- merged 在 archive，candidate 在根
- 状态机合法转换（无 candidate → archived 等跳跃）
- rule 反向引用一致
