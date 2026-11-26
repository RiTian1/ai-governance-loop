# 治理路线图 — 冷启动入口

> 新会话接手本仓库时，**只读这一个文件**就能说出：目标是什么、现在在哪、下一步做什么、
> 哪些事已经决定不做。目标态与机器校验在 `CAPABILITY-MAP.yaml`，本文件是它的导读。

## 1. 三十秒恢复

| 项 | 内容 |
|---|---|
| **长期目标** | 让 agent 能通过根目录入口自动定位约束（`01-charter.md §6` → `gov.FR01`）；让治理能力的成熟度从"能跑"推到"有量化证据" |
| **当前瓶颈** | 29 个在用能力里，**只有 1 个**有对照效应量（`cap.collab.output`）。能运行 29/29，抓到过真实缺陷 11/29 |
| **正在跑** | `§8.6 共享根因` 的 n=25 配对实验（远端 `<跳板>:/root/<配对实验>`，约 16:40 完成） |
| **下一步 P0** | `gov.S05.01` 根目录入口定位实测 —— 成本最低、且 charter 那条最硬的标准从未被测过 |
| **明确不做** | 热修 TTL 通道 / Tool Gate 七字段 / 工作包 DAG（见地图 `deferred`，各有 trigger） |

## 2. 三条阅读路径

| 你想做什么 | 读什么 | 改什么 |
|---|---|---|
| 推进已有工作 | `CAPABILITY-MAP.yaml` 里 `story` 非空的能力 | 只动 Story / Change，不动地图 |
| **改治理能力本身** | 地图里该能力的 `fr` / `current` / `target` | **先改地图**，再改实现（`tool.r13`） |
| 加一个新的量化证据 | 对应 Story 的"实验设计"节 | 产出落到 `docs/experiments/`，再回写 `evidence` |

## 3. 四端绑定长什么样

```
_bmad/gov/prd.md           gov.FR01..14 / NFR01..03       ← 目标（为什么做）
        ↓ prd_refs
_bmad/gov/stories/*.md     gov.S04.26 / S05.01..04         ← 工作单元（做什么）
        ↓ linked_change
openspec/changes/*/        gov.C04.26                      ← 规格增量（改成什么样）
        ↓ linked_revision
revisions/<date>-<slug>/   rev-2026-11-20-...              ← 基线改动（沉淀成规则）
        ↓ introduces_rules
domains/**/_summary.yaml   tool.r13                        ← 可执行规则
        ↓ cross_refs
scripts/*.py               check_capability_map.py         ← 校验
```

**双向**：从任意 `check_*.py` 能回溯到 rule → revision → story → FR；
从任意 FR 能查到它被哪些能力覆盖、成熟度到哪、下一个动作是什么。

校验命令（任一失败即阻断）：

```bash
python scripts/check_capability_map.py          # 四端闭合 + 成熟度诚实性 + 编号唯一
python scripts/check_progress_consistency.py --strict
python scripts/check_declaration_fact.py
python scripts/check_index_freshness.py
```

## 4. 成熟度口径（不可自评升级）

| 级 | 含义 | 硬门槛 |
|---|---|---|
| M0 | 仅声明 | 有文档或规则 |
| M1 | 可执行 | 有脚本/门禁能跑 |
| **M2** | 已证伪能力 | **必须有 `defect_found` 或 `destructive_test` 证据** |
| **M3** | 有对照效应量 | **必须有 `effect_size` 证据** |
| **M4** | 跨任务复现 | **≥2 个独立任务的 `effect_size`** |

当前分布：`M0=1 M1=16 M2=11 M3=1 M4=0`。

M0 那一个是 `cap.collab.orch`（8 条编排规则零执行面）。**留在那里是为了让它可见**，
而不是假装已被治理。

## 5. 这份地图是怎么被验证的

首跑 `check_capability_map.py` 报 **9 个 error**，补全后 **0**。这 9 个里有 2 个是
写地图时新引入的不一致（revision 日期笔误、NFR03 漏覆盖），被校验器**在同一轮内**抓到：

```
F2-story-missing    ×4   四个 Story 尚未创建
F3-change-missing   ×1   gov.C04.26 不存在
F4-revision-missing ×2   一条未创建 + 一条我写成 11-18（实际 11-19）
F2-story-no-prd     ×1   gov.S04.25 的 prd_refs 为空
R1-fr-uncovered     ×1   gov.NFR03 无能力覆盖
```

加唯一性检查后又抓到一处**存量缺陷**：`gov.S04.18` 被两个 Story 同时占用
（`<业务域>-ops-capacity-cleanup` 与 `rsi-runner-harness-defects`），
两个检查器都因为"按 id 建字典"而静默覆盖。已把前者重编号为 `gov.S04.27`。

> 一个未使用的校验等于没有校验：`FR_ID_RE` 定义了两年却没被引用过，
> 所以它连"匹配不了 `NFR03`"这个 bug 都没机会暴露。

## 6. 上下文丢失的防线（本文件存在的理由）

长会话被压缩后，模型只会记得最近几轮。这份地图用三个机制对抗：

1. **目标写在 PRD 里，不写在对话里**：FR 编号不复用，废弃标 `deprecated` 但保留行。
2. **"不做"也要留证**：`deferred` 必须带 `reason` + `trigger`，
   缺 trigger 校验器直接报错——否则"暂缓"会退化成"遗忘"。
3. **进度由脚本判定，不由记忆判定**：任何时候跑一次校验，就知道有没有漂。

## 7. 相关文件

| 用途 | 路径 |
|---|---|
| 能力地图（唯一权威） | `docs/governance-roadmap/CAPABILITY-MAP.yaml` |
| 每次迭代清单 | `docs/governance-roadmap/CHECKLIST.md` |
| 目标态 PRD | `_bmad/gov/prd.md` |
| Epic 定义 | `_bmad/gov/epics/E04-*.md`、`E05-*.md` |
| 四端协议原文 | `foundations/progress-traceability-and-binding.md` |
| 能力现状总览（证据侧） | `docs/experiments/GOVERNANCE-BENCHMARK-OVERVIEW.md` |
| 规则晋升流程 | `revisions/WORKFLOW.md` |
