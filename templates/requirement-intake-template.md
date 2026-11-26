# Requirement Intake Protocol（需求接入协议）— 通用模板

> 本模板供项目层 fork 为 `_bmad/<project_id>/intake.md` 后填充使用。
> 通用 SOP 框架不改；项目特有的「关键词速查表」「Epic 列表」「拒收清单」由项目填。

---

## 1. 用途

让使用者**用业务语言**描述需求（不需要懂治理结构），由 agent 自动分诊到：

- 对应的 Epic / Sprint / AST 节点（如果有）
- 命中的 rule_id（项目硬约束 / 通用治理规则）
- 4 种处置选项之一（接入主线 / 立 candidate revision / backlog / 拒收）

**目标**：把"使用者不知道改的东西属于哪里"的负担转移给 agent + governance 体系。

---

## 2. 何时触发分诊（强制 / 非强制）

### 强制触发分诊

agent 接到以下信号时**必须**先走分诊，不得直接动手：

- 业务语言描述（"我希望……" / "这个 XX 不好用" / "想加 YY 功能"）
- 现象描述（"点击没反应" / "拖动卡" / "看不到效果"）
- 开放式任务（"优化 X" / "重构 Y" / "把 Z 做完整"）—— 这类**默认拒收**，按本协议 §6
- 涉及 ≥ 2 文件或行为变更的改动

### 可跳过分诊的场景（豁免清单）

- 改注释 / 改变量名 / 改 typo / 改格式（< 20 行单文件）
- 文档勘误
- 实验性 spike（使用者明确说"这是 spike 不归档"）
- 跑命令 / 看 log / debug 探查（不写文件）
- 使用者已经**主动指定** Epic / Story / Sprint / Rule（视为分诊已完成）

---

## 3. 分诊 5 步流程

agent 接到需求后**按顺序**执行：

1. **抽取关键词**（从需求描述里提取名词 / 动词 / 现象词）
2. **匹配 Epic / AST 子节点**（用关键词速查表 § 8 + Epic 描述语义匹配）
3. **匹配项目硬约束**（domains/project/_summary.yaml 的 rule_id；命中越多越要慎重）
4. **判断与当前 sprint 的关系**（强相关 / 弱相关 / 无关）
5. **回写 4 选项**（按本协议 §5 模板）

**禁止跳步**。即使关键词命中度高、看起来明显属于某 Epic，也必须给出 4 选项让使用者拍板。

---

## 4. 4 选项分类（A/B/C/D）

agent 回写时**必须**给出以下 4 个选项中至少一个可行项：

| 选项 | 含义 | 触发条件 | 后续动作 |
|------|------|---------|---------|
| **A. 接入当前 sprint** | 作为当前 active_sprint 的子 Story | 命中当前 sprint 的主线 Epic / 子节点 | 起 Story + 进 sprint backlog（不一定立刻起 OpenSpec change） |
| **B. 立 candidate revision** | 引入或修改一条 rule_id | 需求暴露出新的跨项目规则 / 新的项目硬约束 | 立结构化 revision 目录；rule 落 `delta/` |
| **C. 放入 backlog** | 不进入当前 sprint，留待后续 | 与当前 sprint 弱相关或无关，但属于已知 Epic | 记在 `_bmad/<project_id>/backlog.md` 或 Epic 子节点 `status: pending` |
| **D. 拒收** | 超出项目范围或违反 scope-guard | 命中拒收清单（§6） | 给出理由 + 引用违反的 rule_id；不写任何工件 |

**特殊情况**：

- 同一个需求可能同时建议 A + B（先 backlog 一个 Story、同时立 candidate revision）
- 如果命中多个 Epic，必须**明示哪个是主、哪个是协**
- 如果不确定，必须**列出多个候选 Epic 让用户选**，不要自己拍板

---

## 5. 分诊回写格式（agent → 使用者）

agent 必须按以下结构回写，不得自由发挥：

```
分诊结果

1. 抽取关键词：「<词1> / <词2> / ...」
2. 命中 Epic：<project_id>.E<NN> <Epic 名> [+ <project_id>.E<NN> <Epic 名> 如有]
3. 命中子节点：<AST 子节点路径或 Story ID>
4. 命中硬约束：<rule_id1>（<rule 简述>），<rule_id2>，... [无则写"无"]
5. 当前 sprint：<sprint_id>（<主线名>） — <强/弱/无>相关
6. 建议走法：
   A) <选项 A 具体描述> [可选项 / 推荐 ✓]
   B) <选项 B 具体描述> [如适用]
   C) <选项 C 具体描述> [如适用]
   D) <选项 D 具体描述> [如适用]

请选 A / B / C / D（或要求 agent 给更多信息）。
```

---

## 6. 拒收开放式任务

agent **必须拒收**以下形式的需求，并要求使用者改写：

- "优化 X" / "把 Y 做好" / "完善 Z" / "提升 W"
- "重构架构" / "做 AI 能力" / "把体验做高级"
- "搞一下" / "弄一弄"
- 任何**没有可验证目标**或**没有完成判据**的描述

**改写要求**（agent 应主动建议使用者按这个三段式重说）：

```
[现象] + [影响范围] + [我希望的结果]
```

**示例改写**：

- ❌ "优化拖动体验" → ✅ "拖动 NodeEdgeView 节点时，鼠标跟随有可见延迟（约 100ms） → 影响交互演示真实感 → 希望延迟 < 16ms 且性能测试套件有证据"
- ❌ "做完整 AI 能力" → ✅ "希望对选中模块自动生成职责摘要 → 仅展示在右侧面板 → AI 输出走 DSL Patch 不直接改 UI"

---

## 7. 项目层填充模板说明（给 fork 本模板的项目）

项目层在 `_bmad/<project_id>/intake.md` 至少要替换 / 填充以下 4 个章节：

1. **§8 关键词速查表**：列出本项目特有的业务关键词 → Epic / 子节点 / rule 的映射
2. **§9 Epic 一览**：列出本项目所有 Epic ID + 名称 + 主要 owner / sprint 关联
3. **§10 项目级拒收清单**：列出本项目特有的「不做」项（如项目级 scope-guard `proj.scope.r*`）
4. **§11 当前 sprint 速读**：active_sprint 与主线名（可由 `sprints/_index.yaml` 派生）

不要改 §1-§6 的通用 SOP；如要改请走 candidate revision。

---

## 8. 关键词速查表（项目填充）

**模板格式**（项目按需扩展）：

```yaml
# _bmad/<project_id>/intake-keywords.yaml 或本文件内嵌
keywords:
  - words: [关键词1, 同义词1, 同义词2]
    epic: <project_id>.E<NN>
    children: [<AST 子节点路径>]
    rules: [<rule_id>]
    notes: <可选简述>
```

**示例**（来自某图形编辑器项目）：

```yaml
keywords:
  - words: [拖动, 点击, hover, 鼠标, 交互, drag, click]
    epic: proj.E05
    children: [E.E8 InteractionContract]
    rules: [proj.ui.r1, proj.resp.r3]
    notes: 重复 UI 交互 bug 必须按交互架构缺陷诊断
```

---

## 9. Epic 一览（项目填充）

**模板格式**：

| Epic ID | 名称 | 主要 owner | 当前关联 sprint | 状态 |
|---------|------|----------|---------------|------|

---

## 10. 项目级拒收清单（项目填充）

**模板格式**：

| 拒收项 | 引用 rule | 建议改写为 |
|--------|----------|----------|

---

## 11. 当前 sprint 速读（项目填充）

由 `_bmad/<project_id>/sprints/_index.yaml` 派生：

```
active_sprint: <sprint_id>
stage: <stage_code>
name: <主线名>
main_ast_nodes: [...]
selection_change: <change_id>
activation_change: <change_id>
```

---

## 12. 与其它治理工件的关系

- 本协议是 **agent 行为规范**（SOP 级），不是 rule（不属于 `<project_id>.r*` / `<L1>.r*`）
- 若项目验证后认为应升级为强制规则，立 candidate revision 加 `proj.intake.r1`
- 本协议**先于**所有 Story / OpenSpec change / candidate revision 触发
- 分诊产物（关键词命中 + 4 选项回写）应记录到 **agent 输出**，无需独立工件

---

## 13. 维护规则

- 关键词速查表（§8）应在每次新增 Epic / 重大需求时更新
- 拒收清单（§10）应在每次发现新「scope 越界」时追加
- 当前 sprint 速读（§11）应与 `sprints/_index.yaml` 保持同步（建议脚本生成）
- 修改 §1-§6 通用 SOP 须走 candidate revision；修改 §8-§11 项目填充节属于项目自治
