# Tooling 域（L1）

本 L1 域定义**治理母版认可的规划与变更工具的接入协议**：BMAD（产品/项目规划）、OpenSpec（变更级 spec change）、Revisions（全局基线变更）三者的角色边界、衔接点、跨工具绑定的工程构件。它是 `foundations/progress-traceability-and-binding.md` 在工具维度的执行规范。

## 范围

| 工具 | 用途 | 母版默认 | 母版位置 |
|------|------|----------|----------|
| BMAD | 项目级 PRD / Epic / Story 规划层 | `frameworks.bmad.enabled: false`（业务项目按需开） | `_bmad/`、`.claude/skills/bmad-*/`（薄壳） |
| OpenSpec | change-local spec delta + 任务清单 | `frameworks.openspec.enabled: true` | `openspec/changes/`、`openspec/specs/` |
| Revisions | 全局基线规则的候选 → 评审 → 合并 | 强制启用 | `revisions/` |
| Progress-binding | 跨工具绑定的工程构件（脚本 / 状态机 / matrix） | 强制启用 | `scripts/check_progress_consistency.py` 等 |

## L2 子域目录

| 子域 | 用途 | rule_id 前缀 |
|------|------|------------|
| `bmad/` | BMAD 在母版的角色与开启条件 | `tool.bmad.r*` |
| `openspec/` | OpenSpec 接入与 archive 协议 | `tool.openspec.r*` |
| `revisions/` | Revisions 工作流与结构化目录协议 | `tool.revisions.r*` |
| `progress-binding/` | 跨工具的标识、状态机、反向引用、CI 闸口 | `tool.binding.r*` |

## 域级核心规则（rule_id `tool.r*`）

详见 `_summary.yaml`。

## 与 §7 / self-governance 的关系

- §7 的「全局级 → 走 revisions 候选」由 `revisions/` 子域规范化
- §7 的「变更级 → 走 OpenSpec change」由 `openspec/` 子域规范化
- §7 的「项目级 → 写入 `project-rules` / `project-governance.yaml`」**不在本域范围**（属业务项目自治）
- self-governance 的五步循环每轮 Observe 阶段必须跑 progress matrix（由 `progress-binding/` 子域规定）

## 启用建议

| 项目规模 | bmad | openspec | revisions | progress-binding |
|----------|------|----------|-----------|------------------|
| 母版本身 | ✓ dogfood | ✓ | ✓ | ✓ |
| 大型平台型 / 多团队 | ✓ | ✓ | ✓ | ✓ |
| 中型业务（3-10 人月） | 按 PM 决定 | ✓ | ✓ | ✓ |
| 小项目（≤ 3 人月） | ✗ | ✓ | 仅引入全局规则时 | ✓（最小集：commit msg + matrix） |

## 反模式（域级）

- 母版自身演化绕过 BMAD/OpenSpec/Revisions 三层，直接 commit 改 foundation/domain
- 在 `_summary.yaml` 增删 rule 但不立 revision
- BMAD 与 OpenSpec 双轨记录同一份 spec（造成漂移源）
- 业务项目在 `frameworks.bmad.enabled: true` 但 `_bmad/<project>/` 目录为空
