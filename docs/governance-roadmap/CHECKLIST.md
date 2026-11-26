# 治理迭代清单

> 用法：按阶段勾选。**任何一项标「阻断」的未通过，不得提交、不得标完成。**
> 机器可校验的部分都给了命令；其余是判断项，需要留证据（贴输出或链接）。

---

## A. 迭代前：先确认这件事该不该做

- [ ] **A1 归到 FR**：在 `_bmad/gov/prd.md` 找到它服务的 FR / NFR；找不到 → 先讨论是否新增 FR，不要直接立 Story
- [ ] **A2 查是否已做过**：查 `CAPABILITY-MAP.yaml` 的 `deferred`，确认不是已决定暂缓的项
      （若是，先看 `trigger` 是否已满足；未满足则停）
- [ ] **A3 判定类型**：属"补机制"进 `gov.E04`；属"验证机制有没有用"进 `gov.E05`。
      两者失败模式不同，混在一起会让"做完了"和"有用"难以区分
- [ ] **A4 查依赖**：目标能力是否依赖另一个能力先到某成熟度（例：谈"装多深"前先确认"装哪些域"没坏）
- [ ] **A5 估成本并写进 Story**：单轮时间 / token / 是否需远端。J3 系列每轮 5–25 分钟、300–1800 万 token，
      报告型任务约 10 万 token——差 30–100 倍，不估就会低估

**产出**：一个 `status: draft|approved` 的 Story，`prd_refs` 非空。

---

## B. 改治理能力本身（改地图 → 改实现，顺序不可反）

> `tool.r13`：能力面的任何增删改 **MUST 先改地图**。反了就会出现"实现改了但地图没改"，
> 而地图是唯一权威——那等于把权威变成过期快照。

- [ ] **B1 改 `CAPABILITY-MAP.yaml`**：加/改 `cap.*` 条目，写清 `fr` / `current` / `target` / `next`
- [ ] **B2 补 `evidence`**：如果这次让成熟度上升，必须补对应类型的证据
      （M2 要 `defect_found`/`destructive_test`，M3 要 `effect_size`）——**没有证据就把 current 留在原级**
- [ ] **B3 立载体**：Story（+ 有 spec 增量时立 OpenSpec change），两边 `linked_*` 必须对称
- [ ] **B4 改实现**：脚本 / 规则 / 基线文档
- [ ] **B5 反向引用**：新规则写进 `_summary.yaml` 的 `introduced_by`，并在 revision 的 `introduces_rules` 里列出
- [ ] **B6 更新地图的 `story`/`change`/`revision` 字段**，让四端闭合
- [ ] **B7 阻断｜跑校验**：
      ```bash
      python scripts/check_capability_map.py          # 必须 errors=0
      python scripts/check_progress_consistency.py --strict
      python scripts/check_declaration_fact.py
      python scripts/check_index_freshness.py
      ```

---

## C. 规则晋升（candidate → benchmarked → accepted）

- [ ] **C1 状态停在 `candidate`**，直到有证据。`benchmark.status: not_run` 是合法的，
      先标 `benchmarked` 再补证据是违规（`tool.revisions.r6`）
- [ ] **C2 三选一给证据**：前后对比（效应量 + 方向一致数 x/n + 样本量）/ 回归测试（红转绿 + 命令输出）/ waiver（理由 + 批准人）
- [ ] **C3 fresh context**：不得用"写规则时看到的材料"去评测自己写的规则。这条是 RSI 实验的直接教训
- [ ] **C4 失败判据写在跑之前**：先写"什么结果算无效"，避免事后解释（例：`PAIRED-25-PREREG.md`）
- [ ] **C5 允许驳回**：若证据显示无效或有害，标 `rejected` 并留在 `rejected_items`，
      **不要悄悄删掉**——驳回记录比结论更有信息量（已有 6 次 GT 被模型反推纠正）

---

## D. 做评测（判据会被算错，默认它错）

- [ ] **D1 判据自测 ≥4 组**：全对 / 漏 N / 多报 / 空输入。少一组就可能漏掉"完美答案被判不完美"这类 bug
- [ ] **D2 GT 先让被测模型跑一遍再定稿**：已发生 6 次由模型纠正 GT，其中 1 次直接翻转达成结论
- [ ] **D3 驳回项留证据链**：写 `rejected_items`（原主张 / 驳回理由 / 残余风险 / 教训）
- [ ] **D4 一对一匹配**：多个 GT 同文件相邻行时，一个 finding 只能命中一个 GT，否则 precision 会被低估
- [ ] **D5 权重和 = 1.0**：超过 1 会被 clamp 掩盖差异（曾导致"漏 1 条"与"全对+1 误报"同分）
- [ ] **D6 改判据必回归全部历史产物**：贴出"分数未变"的证据，否则等于换尺子重写结论
- [ ] **D7 主指标选对**：二元达成用 McNemar；连续用配对 t + 方向一致数；**耗时/token 不作效应判据**
- [ ] **D8 n 足够**：二元配对 n≥25（n=15 时 p≈0.07 临界）；连续指标 n≥15
- [ ] **D9 单轮不算基线**：同一任务书两次可能跑出 precision 1.0 / 0.43
- [ ] **D10 报范围与预算**：审计类结果必须同时报"文件数/行数/单轮 token"，
      否则与别的实验不可比（J3 全量 vs J3a 的精确率差 8 倍，原因是范围不是能力）

---

## E. 收尾（检查点协议，`tool.binding.r10`）

- [ ] **E1 归因工作区变动**：`python scripts/check_worktree_hygiene.py`，区分生成物与真实改动
- [ ] **E2 内容闸**：`python scripts/check_staged_content.py --staged`
- [ ] **E3 声明-事实**：`python scripts/check_declaration_fact.py`（改过状态机/规则号/脚本路径时必跑）
- [ ] **E4 四端闭合**：`python scripts/check_capability_map.py`
- [ ] **E5 进度一致性**：`python scripts/check_progress_consistency.py --strict`
- [ ] **E6 人工验证标志**：可归档的 change 需用户确认是否勾选，不得自行勾
- [ ] **E7 归档与实现同一次提交**，归档后 push `origin/main`
- [ ] **E8 commit message 三段非空**：`Story:` / `Change:`|`Revision:`|`Rules:` 至少一项非 none
- [ ] **E9 贴出通过输出**：把 `errors=0` 的实际输出贴进对话，作为完成证据

---

## F. 季度复核（防止地图变成化石）

- [ ] **F1 只看变化项**：扫 `CAPABILITY-MAP.yaml` 的 `maturity`，核对是否有能力被悄悄升/降
- [ ] **F2 查 deferred 的 trigger 是否已满足**（3 条：热修 TTL / Tool Gate / 工作包 DAG）
- [ ] **F3 查"长期停在 M1"的能力**：M1 且 90 天未动的，要么降级为"参考"，要么立 Story 推一把
- [ ] **F4 复核 `cap.collab.orch`**：8 条规则零执行面已持续存在，每季度确认一次是否还要保留

---

## G. 已知易漏项（全部来自实际踩坑）

| # | 漏什么 | 后果 | 对应检查 |
|---|---|---|---|
| 1 | 只改实现不改地图 | 地图变成过期快照，权威失效 | B1 / `check_capability_map` |
| 2 | 判据没自测 | 完美答案被判不完美，结论反向 | D1 |
| 3 | GT 没让模型跑过 | 6 次里有 1 次直接翻转达成结论 | D2 |
| 4 | 权重和超 1 | clamp 掩盖差异，判据失去区分度 | D5 |
| 5 | 改判据不回归 | 旧结论被新尺子重写，无法比较 | D6 |
| 6 | 单轮当基线 | precision 1.0 / 0.43 是同一个任务书 | D9 |
| 7 | 用耗时/token 作判据 | 三次推翻，方差源与治理无关 | D7 |
| 8 | 编号重复 | 反向引用指向不确定对象（实测 `S04.18` 撞号） | `S2-dup-story` |
| 9 | "暂缓"不写 trigger | 暂缓退化成遗忘 | `D1-no-trigger` |
| 10 | 未使用的校验当已生效 | `FR_ID_RE` 定义了两年，连自己的 bug 都没暴露 | B7 |

---

## 附：一条元规则

**本清单本身也是治理对象。** 如果某次迭代发现清单漏了一项，处理方式不是"下次记得"，
而是走 B 节把它加进来——否则这份清单会和被它约束的东西一起漂。
