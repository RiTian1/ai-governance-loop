---
revision_id: rev-2026-05-25-hierarchical-knowledge-and-self-governance
title: 层级化知识架构与长期自治理循环
status: candidate
linked_stories: []
linked_changes: []
prd_refs: []
introduces_rules:
  - ops.r1
  - ops.r2
  - ops.r3
  - ops.r4
  - ops.r5
  - ops.r6
modifies_rules: []
removes_rules: []
affected_baselines:
  - foundations/self-governance-and-knowledge-evolution.md
  - 02-engineering-principles.md
  - 00-index.yaml
  - domains/operations/
  - templates/domain-l1-index-template.yaml
  - templates/domain-summary-template.yaml
  - templates/runtime-context-manifest-template.yaml
  - scripts/context_loader.py
  - scripts/check_knowledge_health.py
commits:
  - 1891adc
  - e524144
created_at: 2026-05-25
created_by: agent
source_change: null
reviewed_by: null
reviewed_at: null
merged_at: null
archived_at: null
trigger_summary: |
  引入树形 domain（L1/L2/L3）+ 三件套协议 + token 预算 loader + 自治理循环 foundation；
  落地 P0 缺口（运行时上下文记忆 / housekeeping / operations 子文件空壳）；删除 {output_folder} 残留。
---

# 治理修订单：层级化知识架构与长期自治理循环

## 1. 修订标题

引入树形 domain（L1/L2/L3）+ 三件套协议（index.md / `_summary.yaml` / `_index.yaml`）+ token 预算 loader + 长期自治理循环 foundation；同步把 P0 缺口（运行时上下文记忆、housekeeping、operations 子文件空壳）落地为试点。

## 2. 触发来源

- 用户对治理母版完整性的元评审（2026-05-25）：`新项目接入 / 老项目接入 / 经验沉淀方法论` 已达生产级，但 `闭环执行所需记忆 / 自动反堆积 / 避免文件堆积` 三块只有零散点。
- 后续诉求：domain 应支持层级化（如 `ui → {gui, webui, ui-testing}`），且知识库随时间膨胀时 token 消耗不应明显增长，仍需保持高效高质量工作流。
- 用户明示缺乏「通用闭环自治理的长期工作流」经验，需要一套可重复的循环。

## 3. 问题现象

1. 22 个 domain 全部扁平共存于 `domains/` 根，`gui.md` / `frontend.md` 等本应同属上位 `ui` 的兄弟没有共同父节点。
2. 单一 `00-index.yaml` 在节点扩到 100+ 时本身就会成为 token 负担。
3. profile + `when_to_read` 二维筛选过粗：同阶段命中的所有 domain 仍可能整文装入。
4. 没有跨域复用机制（如 `ui-testing` 既属 `ui` 又属 `automation`），易出现内容复制与漂移。
5. `domains/operations/index.md` 声明了 5 个子文件（runbook/oncall/capacity/dr/change），实际全部不存在。
6. 母版根目录残留 `{output_folder}/` 占位符未替换目录，违反母版自身倡导的卫生纪律。
7. 没有 token cost 监控、没有命中率回归、没有 dormancy/orphan 检测，知识库只增不减。
8. `02-engineering-principles.md §7` 的「四级范围」覆盖规则的写入位置，但不覆盖闭环执行所需的「环境变量/账号密码/权限/依赖包」这类**运行时上下文记忆**。

## 4. 为什么上升为项目级规则

- 跨 profile、跨项目类型、所有 Agent 必须遵守 → 全局级（按 §7 准则）。
- 影响所有未来新增 domain 与 revision 的写入方式与索引方式。
- 决定 Agent 在所有任务中的上下文加载行为，不能只留在某次 change 或单一 domain 内。

## 5. 适用范围

- 母版仓库（mother-repo-root）：本次直接落地。
- 业务项目（docs-governance-subtree）：随下次 bootstrap / 上游同步获得新协议；旧项目在迁移阶段二「提升到新骨架」时改造。
- 所有 profile：solo-developer / backend-service / desktop-application / embedded-system / ml-system / native-security-runtime / security-research。

## 6. 影响文档

新增：
- `foundations/self-governance-and-knowledge-evolution.md`（长期自治理循环）
- `templates/domain-l1-index-template.yaml`
- `templates/domain-summary-template.yaml`
- `templates/runtime-context-manifest-template.yaml`
- `domains/operations/{index.md,_index.yaml,_summary.yaml}`（重写）
- `domains/operations/{runbook,oncall,capacity,dr,change,runtime-context,housekeeping}/{index.md,_summary.yaml}`
- `scripts/context_loader.py`、`scripts/check_knowledge_health.py`

修改：
- `02-engineering-principles.md`（新增 §11）
- `00-index.yaml`（schema v2，operations 升级条目）
- `domains/README.md`（反映 operations 树化）
- `scripts/requirements.txt`（加 pyyaml）
- `revisions/index.yaml`（登记本 candidate）

删除：
- `{output_folder}/`（母版残留污点）

## 7. 影响实现

- 现有扁平域不强制立即重构（向后兼容）：本次仅在 `operations/` 试点验证协议；ui / automation / security 等高频域留 Stage B/C。
- `00-index.yaml` schema v2 同时兼容 v1 条目；旧条目保留，新增 `level: L1` 与 `triggers/size_tokens` 字段。
- `context_loader.py` 在仅有 v1 条目的环境下退化为 profile + phase 装载。

## 8. 影响测试

- `scripts/check_knowledge_health.py` 自检：占位符、size 漂移、orphan、rule_id 唯一性、`{output_folder}` 残留。
- 后续（Stage B+）：`scripts/context_loader.py` 在 `operations/` 试点上跑命中率回归（命中 ≥ 90%、单任务装载 ≤ 8 k tokens）。

## 9. 证据与样例

- `domains/operations/runtime-context/manifest-template.yaml` 给出闭环上下文示例。
- `_summary.yaml` rule_id 体系：`ops.runbook.r1` / `ops.runtime-context.r2` 等。
- 三层索引下钻路径：`00-index.yaml (1.5k) → domains/operations/_index.yaml (0.5k) → domains/operations/runbook/index.md (2.5k) ≈ 4.5k`，对比扁平全装 ~30k+。

## 10. 修订前

- 22 个扁平 domain；唯一索引 `00-index.yaml`；无 token budget；无生命周期治理。
- `02-engineering-principles.md §7` 仅覆盖规则范围，不覆盖运行时上下文记忆。
- `domains/operations/` 是只有 `index.md` 的空壳。
- 母版根目录有 `{output_folder}/` 残留。

## 11. 修订后

- 树形 domain（L1/L2/L3）协议成立，`operations/` 落地为首批试点。
- 三件套协议：L1/L2 域必备 `index.md` + `_summary.yaml` + `_index.yaml`；叶子允许仅 `index.md`。
- `00-index.yaml` schema v2：增加 `level / triggers / size_tokens / aliases`。
- rule_id 协议：`<domain-flat-path>.r<n>`，由 `_summary.yaml` 分配，`check_knowledge_health.py` 校验唯一性。
- `context_loader.py` 按 trigger 评分 + budget 装包；默认 8 k token budget。
- 自治理循环 foundation：观察 → 诊断 → 决策 → 执行 → 回归。
- `runtime-context/` 子域承载闭环执行记忆（env/账号/权限/依赖），含 `manifest-template.yaml`。
- `housekeeping/` 子域承载反堆积政策（dormancy / orphan / size 漂移 / 占位符）。
- `{output_folder}/` 残留删除。

## 12. 迁移要求

- 业务项目下次 `scripts/sync-upstream.ps1` 后：
  - 复制新增 templates；
  - operations 域内容随母版重置（确认无本地定制后）；
  - 在 `project-governance.yaml` 增加（可选）`token_budget: 8000`、`runtime_context: <path>`。
- 现有扁平 domain 留待后续 Stage B/C 改造，不强制立即拆分。
- rule_id 仅在新 `_summary.yaml` 内强制；旧 `.md` 不追溯分配。

## 13. 晋升目标（merged 时填写）

- 目标文件：
  - `02-engineering-principles.md` §11
  - `foundations/self-governance-and-knowledge-evolution.md`
  - `domains/operations/`（含 7 子域）
  - `templates/domain-l1-index-template.yaml`
  - `templates/domain-summary-template.yaml`
  - `templates/runtime-context-manifest-template.yaml`
  - `00-index.yaml` schema v2
- 合并 PR / 变更：（待补 PR 链接）
