# 自治理与知识演化

本方法论定义治理母版自身的长期演化机制：当知识库随时间膨胀、参与者增加、领域细化时，如何让知识库保持**单任务上下文负担恒定**、**召回率稳定**、**结构持续收敛**，而不是逐年劣化为重复、漂移、孤儿的堆积。

它与 `02-engineering-principles.md §7`（经验沉淀范围）和 `revisions/WORKFLOW.md`（候选修订流程）正交：§7 解决「规则写到哪一层」，本文件解决「整个层级体系如何持续保持可用」。

## 1. 核心命题

- **知识 O(N) 增长，单任务上下文 O(log N) 或近似常数**：靠分层索引、按需下钻、稀疏激活、双轨摘要实现。
- **知识只增不减是劣化的根源**：必须建立 dormancy / merge / split / archive 的反向通道，否则任何治理体系都会被自身重量压垮。
- **治理母版必须 dogfood 自身规则**：母版自己的占位符、孤儿目录、空壳子文件，是体系是否健康的第一面镜子。
- **token 是工程预算项，不是抽象资源**：必须可观测、可回归、可问责，与构建时间、存储成本同等对待。

## 2. 五步循环

```text
观察 (Observe)
  ↓ scripts/context_loader.py 装载日志 + scripts/check_knowledge_health.py CI
诊断 (Diagnose)
  ↓ 月度 health report：dormancy / orphan / size 漂移 / 命中率低 / 占位残留
决策 (Decide)
  ↓ 自动生成 revisions/<date>-<slug>-candidate.md，按 §7 分级
执行 (Execute)
  ↓ 按层级协议执行 split / merge / promote / demote / archive
回归 (Regress)
  ↓ token cost 基线、命中率、违规率不退化
（回到观察）
```

每一步都必须有**结构化产物**（日志、报告、修订单、提交），不允许只在聊天或个人记忆里。

## 3. 五种结构调整动作

| 动作 | 触发条件 | 目标位置 | 后续 |
|------|----------|----------|------|
| **promote**（晋升） | 子文件超过 300 行或子主题 ≥ 5；同主题在多个域重复出现 | 升级为目录型域；旧文件留 redirect stub | 更新 `_index.yaml`、上级 `_summary.yaml` |
| **demote**（降级） | L1 域内容萎缩到单文件可容纳；与同级域语义合并 | 降为子文件或 alias | 更新父域索引 |
| **split**（拆分） | 单域承载多个职责，命中度高但内容混杂 | 按职责切分成多个 L2 子域 | 各自三件套 |
| **merge**（合并） | 多域内容高度重复，规则交叉引用频繁 | 合并为新域，原位置留 redirect | 同步更新所有引用 |
| **archive**（归档休眠） | 90 天未被任何 task 命中 → dormant；365 天 dormant → archived | `domains/_archive/<year>/` | 从默认 bundle 移除，仅显式 `--include` 加载 |

每个动作必须经过 `revisions/` candidate → 评审 → merged 的完整链路（按 `revisions/WORKFLOW.md`），不允许「直接改完不留痕」。

## 4. 三件套协议（与 §11 对接）

L1 / L2（有子节点）域必备：

| 文件 | 受众 | 用途 | 大小硬上限 |
|------|------|------|-----------|
| `index.md` | 人 + LLM | 域门面、规则总论、子文件目录 | ≤ 200 行 / 4 k tokens |
| `_summary.yaml` | 机器 / Loader | 规则要点 bullet（≤ 30 条），分配 rule_id | ≤ 50 KB |
| `_index.yaml` | 机器 / Loader | 子节点路由、triggers、size_tokens | ≤ 100 KB |

叶子（无子节点）允许仅 `index.md` 或单个 `.md`，规则直接写在正文中。

## 5. rule_id 协议

格式：`<domain-flat-path>.r<n>`

- `<domain-flat-path>` 用 `.` 连接路径（不含 `domains/` 前缀）：`ops.runbook` / `ui.webui.a11y` / `automation.test-data`
- `r<n>` 在该 `_summary.yaml` 内单调递增，**不重排、不复用**
- 全局唯一性由 `scripts/check_knowledge_health.py` 校验
- PR / commit / revisions / Agent 输出可直接引用：「违反 `ops.runbook.r2`」

rule_id **不是 GUID**，是人类可读、LLM 可记忆、检索友好的稳定标识。

## 6. token 预算

- 默认单任务治理上下文预算：**8 k tokens**
- 来源声明：`project-governance.yaml` 顶层 `token_budget: 8000`
- 实际加载量由 `scripts/context_loader.py` 控制，加载日志写到 `revisions/_logs/context-trace/<date>.jsonl`
- CI 回归（`scripts/check_knowledge_health.py --token-baseline`）：分 profile 跑 N 个代表性任务，平均 cost 不得退化超过 +20%

预算回归是结构性指标，不是软指标。超阈值触发 candidate 修订单。

## 7. 触发器（trigger）评分

`_index.yaml` 中每个子节点声明：

```yaml
triggers:
  keywords: [词1, 词2, ...]      # 任务描述/对话关键词
  files: ["src/ui/**", ...]      # 任务涉及文件 glob
  stack: [react, qt, ...]        # 技术栈
  phases: [design, apply, ...]   # 阶段
```

Loader 计算命中分（简化 BM25）：
- 关键词命中：+2 / 词
- 文件 glob 命中：+3 / 模式
- stack 命中：+2 / 项
- phase 命中：+1 / 项

排序 → budget 内贪心装包：
- 必装：profile.required_domains（无视分数）
- 高分（≥ 6）：装 `index.md` 全文
- 中分（3 ~ 5）：仅装 `_summary.yaml`
- 低分（< 3）：跳过；记录到 dropped 列表

## 8. 跨域复用：tags / aliases / canonical_owner

- 每条规则指定 `canonical_owner`（唯一权威位置）
- 其他域通过 `aliases:` 声明引用，**禁止复制内容**
- `see_also:` 用于双向链接（不影响所有权）
- `tags:` 用于跨域检索（如 `tag: a11y` 跨 ui/webui、ui/testing、automation/ui-tests）

`check_knowledge_health.py` 的 `--check-duplicates` 检测语义重复（按 tag 聚合 + 文本相似度阈值），输出 merge 建议。

## 9. 与 §7（经验沉淀范围）的关系

§7 解决「新规则写到哪一层」（变更级 / 项目级 / 领域级 / 全局级），本文件解决「层级体系本身如何演化」：

- §7 的「领域级」如何在域树中找到正确父域 → 由本文件的 promote / split / merge 协议决定
- §7 的「全局级 → revisions 候选」如何不让 revisions 自身爆炸 → 由本文件的 archive / dormancy 协议决定
- §7 的写入是**单点动作**；本文件是**长期循环**

两者必须同时在场，缺一不可。

## 10. 反模式

- 写新 domain 时不补 `_summary.yaml` 与 `_index.yaml`，只放 `.md`
- 复制规则到多个 domain 而不用 `aliases:`
- 把 dormant / orphan 视为「以后再说」，不进 candidate
- 让 `00-index.yaml` 直接承载 L2/L3 节点（导致索引爆炸）
- 给规则分配语义化 ID（`ops.runbook.environment-validation`），导致 ID 漂移；只允许 `r<n>` 单调编号
- 在 candidate 修订单里只写「应该层级化」而不给出 promote/split 的具体目标

## 11. 完成判定

一个治理母版可视为「具备长期自治理能力」的最低标准：

- [ ] `00-index.yaml` 是 schema v2，含 `level / triggers / size_tokens`
- [ ] 至少一个 L1 域已采用三件套（本仓库 = `domains/operations/`）
- [ ] `scripts/context_loader.py` + `scripts/check_knowledge_health.py` 可执行
- [ ] `_logs/context-trace/` 开始累积加载日志
- [ ] `revisions/` 中存在至少一份基于本机制产生的 candidate（dogfood 证据）
- [ ] `domains/` 根目录无占位符残留（`{output_folder}` 类）
- [ ] `02-engineering-principles.md §11` 与本 foundation 互相引用

## 12. 适用对象

- 治理母版仓库（mother-repo-root）：完整执行
- 业务项目（docs-governance-subtree）：默认仅享受协议（三件套 + 索引 + loader），不强制每个项目都跑月度 health report；大型平台型项目可启用
