---
name: openspec-onboard
description: OpenSpec 引导式入门——带讲解、用真实代码库工作走完一次完整工作流循环。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.5.0"
  localization: zh-CN governance-overlay
---

带用户走完第一个完整的 OpenSpec 工作流循环。这是一次教学体验——你会在其真实代码库中做真实工作，同时讲解每一步。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

---

## 预检

开始前检查 OpenSpec CLI 是否已安装：

```bash
# Unix/macOS
openspec --version 2>&1 || echo "CLI_NOT_INSTALLED"
# Windows (PowerShell)
# if (Get-Command openspec -ErrorAction SilentlyContinue) { openspec --version } else { echo "CLI_NOT_INSTALLED" }
```

**CLI 未安装时：**
> OpenSpec CLI 尚未安装。先安装，再回来运行 `/opsx:onboard`。

未安装则到此为止。

---

## 阶段 1：欢迎

展示：

```
## 欢迎使用 OpenSpec！

我会用你代码库里的一个真实任务，带你走完一次完整的变更循环——从想法到实现。边做边学工作流。

**我们要做的事：**
1. 在你的代码库中挑一个小而真实的任务
2. 简短探索问题
3. 创建一个 change（承载工作的容器）
4. 构建 artifact：proposal → specs → design → tasks
5. 实施任务
6. 归档完成的 change

**耗时：** 约 15-20 分钟

先找点事做吧。
```

---

## 阶段 2：任务挑选

### 代码库分析

扫描代码库寻找小的改进机会，关注：

1. **TODO/FIXME 注释** —— 搜代码里的 `TODO`、`FIXME`、`HACK`、`XXX`
2. **缺失的错误处理** —— 吞错的 `catch` 块、无 try-catch 的高危操作
3. **没有测试的函数** —— 对照 `src/` 与测试目录
4. **类型问题** —— TypeScript 里的 `any`（`: any`、`as any`）
5. **调试残留** —— 非调试代码里的 `console.log`、`console.debug`、`debugger`
6. **缺失的校验** —— 未校验用户输入的处理器

同时看看最近的 git 活动：
```bash
# Unix/macOS
git log --oneline -10 2>/dev/null || echo "No git history"
# Windows (PowerShell)
# git log --oneline -10 2>$null; if ($LASTEXITCODE -ne 0) { echo "No git history" }
```

### 给出建议

基于分析给出 3-4 个具体建议：

```
## 任务建议

扫描你的代码库后，这些是不错的入门任务：

**1. [最有价值的任务]**
   位置：`src/path/to/file.ts:42`
   规模：约 1-2 个文件、20-30 行
   为什么合适：[简短理由]

**2. [第二个任务]**
   位置：`src/another/file.ts`
   规模：约 1 个文件、15 行
   为什么合适：[简短理由]

**3. [第三个任务]**
   位置：[位置]
   规模：[估计]
   为什么合适：[简短理由]

**4. 别的？**
   告诉我你想做什么。

哪个感兴趣？（选个编号，或描述你自己的任务）
```

**什么都没找到时：** 退回去问用户想做什么：
> 我没在你的代码库里找到明显的速赢项。有什么一直想加或想修的小东西吗？

### 规模护栏

用户挑了或描述了过大的任务（大功能、需要好几天）时：

```
这个任务很有价值，但作为第一次 OpenSpec 演练可能偏大了。

学工作流时越小越好——能看完整个循环而不陷进实现细节。

**可选项：**
1. **切小一点** —— [该任务]里最小的有用切片是什么？也许就 [具体切片]？
2. **换一个** —— 其它建议之一，或另一个小任务？
3. **照做不误** —— 真想啃这个也行，只是会更久。

你想怎么选？
```

用户坚持就放行——这是软护栏。

---

## 阶段 3：探索演示

任务选定后，简短演示探索模式：

```
创建 change 之前，先快速展示一下**探索模式**——在选定方向之前，用它来思考问题。
```

花 1-2 分钟调查相关代码：
- 读涉及的文件
- 有帮助就画个简单 ASCII 图
- 记下注意点

```
## 快速探索

[你的简短分析——发现了什么、要注意什么]

┌─────────────────────────────────────────┐
│   [可选：有帮助就放 ASCII 图]           │
└─────────────────────────────────────────┘

探索模式（`/opsx:explore`）就是干这个的——先调查再实现。任何需要想清楚问题的时候都能用。

现在创建一个 change 来承载我们的工作。
```

**暂停** —— 等用户回应后再继续。

---

## 阶段 4：创建 Change

**讲解：**
```
## 创建 Change

OpenSpec 里的 "change" 是围绕一件工作的全部思考与规划的容器。它位于 `openspec status --change "<name>" --json` 报告的 `changeRoot`，存放你的 artifact——proposal、specs、design、tasks。

我来为我们的任务创建一个。
```

**执行：** 用派生的 kebab-case 名称创建 change：
```bash
openspec new change "<derived-name>"
```

**展示：**
```
已创建：<status JSON 中的 changeRoot>

目录结构：
```
<changeRoot>/
├── proposal.md    ← 为什么做（空的，接下来填）
├── design.md      ← 怎么建（空）
├── specs/         ← 详细需求（空）
└── tasks.md       ← 实施清单（空）
```

现在填第一个 artifact——proposal。
```

---

## 阶段 5：Proposal

**讲解：**
```
## Proposal

proposal 记录我们**为什么**做这个变更、以及它在高层**包含什么**。它是这件工作的"电梯演讲"。

我基于任务起草一份。
```

**执行：** 起草 proposal 内容（先不保存）：

```
草稿如下：

---

## Why

[1-2 句说明问题/机会]

## What Changes

[要点列出会有什么不同]

## Capabilities

### New Capabilities
- `<capability-name>`：[简述]

### Modified Capabilities
<!-- 若修改既有行为 -->

## Impact

- `src/path/to/file.ts`：[改什么]
- [其它涉及文件]

---

这样表达意图对吗？保存前我可以调整。
```

**暂停** —— 等用户认可/反馈。

认可后保存 proposal：
```bash
openspec instructions proposal --change "<name>" --json
```
然后把内容写到 `openspec instructions proposal --change "<name>" --json` 给出的 `resolvedOutputPath`。

```
proposal 已保存。这是你的"为什么"文档——随着理解演进，随时可以回来完善。

接下来：specs。
```

---

## 阶段 6：Specs

**讲解：**
```
## Specs

specs 用精确、可测试的语言定义我们要构建**什么**。它采用 requirement/scenario 格式，把预期行为写得一清二楚。

这么小的任务，可能一个 spec 文件就够。
```

**执行：** 解析 spec 文件应创建的位置：
```bash
openspec instructions specs --change "<name>" --json
# 用 JSON 里的 resolvedOutputPath。若是 glob，结合 schema 指引与 change 上下文确定具体路径。
```

起草 spec 内容：

```
spec 如下：

---

## ADDED Requirements

### Requirement: <名称>

<系统应当做什么的描述>

#### Scenario: <场景名>

- **WHEN** <触发条件>
- **THEN** <预期结果>
- **AND** <如需，附加结果>

---

WHEN/THEN/AND 这个格式让需求可测试——读起来就是测试用例。
```

保存到从 `resolvedOutputPath` 确定的具体文件路径。

---

## 阶段 7：Design

**讲解：**
```
## Design

design 记录我们**怎么**建——技术决策、取舍、方案。

小变更可以很简短。没关系——不是每个变更都需要深度设计讨论。
```

**执行：** 起草 design.md：

```
design 如下：

---

## Context

[当前状态的简短背景]

## Goals / Non-Goals

**Goals：**
- [要达成什么]

**Non-Goals：**
- [明确不做什么]

## Decisions

### 决策 1：[关键决策]

[方案与理由说明]

---

对小任务来说，这样既记录了关键决策又不过度设计。
```

保存到 `openspec instructions design --change "<name>" --json` 给出的 `resolvedOutputPath`。

---

## 阶段 8：Tasks

**讲解：**
```
## Tasks

最后，把工作拆成实施任务——驱动 apply 阶段的 checkbox。

任务要小、要清晰、按逻辑排序。
```

**执行：** 基于 specs 与 design 生成任务：

```
实施任务如下：

---

## 1. [类别或文件]

- [ ] 1.1 [具体任务]
- [ ] 1.2 [具体任务]

## 2. 验证

- [ ] 2.1 [验证步骤]

---

每个 checkbox 都是 apply 阶段的一个工作单元。准备好实施了吗？
```

**暂停** —— 等用户确认可以开始实施。

保存到 `openspec instructions tasks --change "<name>" --json` 给出的 `resolvedOutputPath`。

---

## 阶段 9：Apply（实施）

**讲解：**
```
## 实施

现在逐个实施任务、边做边勾。我会逐一宣布，并顺带说明 specs/design 如何影响做法。
```

**执行：** 对每个任务：

1. 宣布："正在处理任务 N：[描述]"
2. 在代码库中完成改动
3. 自然地引用 specs/design："spec 里说 X，所以我做 Y"
4. 在 tasks.md 勾掉：`- [ ]` → `- [x]`
5. 简短状态："✓ 任务 N 完成"

讲解保持轻量——别逐行说教。

全部任务完成后：

```
## 实施完成

全部任务已完成：
- [x] 任务 1
- [x] 任务 2
- [x] ...

变更已实现！还差一步——归档。
```

---

## 阶段 10：归档

**讲解：**
```
## 归档

change 完成后就归档。归档路径由 `planningHome.changesDir` 加日期推导。

归档的 change 会成为项目的决策历史——以后随时能翻出来，理解某个东西当初为什么这么建。
```

**执行：**
```bash
openspec archive "<name>"
```

**展示：**
```
已归档到：`<planningHome.changesDir>/archive/YYYY-MM-DD-<name>/`

这个 change 已成为项目历史的一部分。代码在你的代码库里，决策记录也保住了。
```

---

## 阶段 11：回顾与下一步

```
## 恭喜！

你刚完成了一个完整的 OpenSpec 循环：

1. **Explore** —— 想清楚问题
2. **New** —— 创建 change 容器
3. **Proposal** —— 记录为什么（WHY）
4. **Specs** —— 详细定义做什么（WHAT）
5. **Design** —— 决定怎么做（HOW）
6. **Tasks** —— 拆成步骤
7. **Apply** —— 完成实现
8. **Archive** —— 保存记录

这套节奏适用于任何规模的变更——小修小补或大功能都一样。

---

## 命令速查

**核心工作流：**

| 命令            | 作用                             |
|-----------------|----------------------------------|
| `/opsx:propose` | 创建 change 并生成全部 artifact  |
| `/opsx:explore` | 工作前/中想清楚问题              |
| `/opsx:apply`   | 实施 change 中的任务             |
| `/opsx:archive` | 归档完成的 change                |

**其它命令：**

| 命令             | 作用                                   |
|------------------|----------------------------------------|
| `/opsx:new`      | 开启新 change，逐个创建 artifact       |
| `/opsx:continue` | 继续推进既有 change                    |
| `/opsx:ff`       | 快进：一次创建全部 artifact            |
| `/opsx:verify`   | 验证实现与 artifact 是否匹配           |

---

## 接下来？

拿一个你真正想做的东西试试 `/opsx:propose`。节奏你已经掌握了！
```

---

## 优雅退出处理

### 用户中途想停

用户表示要停下、想暂停、或明显走神时：

```
没问题！你的 change 已保存在 `openspec status --change "<name>" --json` 报告的 `changeRoot`。

之后想继续：
- `/opsx:continue <name>` —— 继续创建 artifact
- `/opsx:apply <name>` —— 直接跳到实施（若 tasks 已存在）

工作不会丢。想回来随时回来。
```

不施压，优雅退出。

### 用户只想要命令速查

用户表示只想看命令、跳过教程时：

```
## OpenSpec 速查

**核心工作流：**

| 命令                    | 作用                             |
|-------------------------|----------------------------------|
| `/opsx:propose <name>`  | 创建 change 并生成全部 artifact  |
| `/opsx:explore`         | 想清楚问题（不改代码）           |
| `/opsx:apply <name>`    | 实施任务                         |
| `/opsx:archive <name>`  | 完成后归档                       |

**其它命令：**

| 命令                     | 作用                             |
|--------------------------|----------------------------------|
| `/opsx:new <name>`       | 开启新 change，一步一步来        |
| `/opsx:continue <name>`  | 继续既有 change                  |
| `/opsx:ff <name>`        | 快进：一次生成全部 artifact      |
| `/opsx:verify <name>`    | 验证实现                         |

用 `/opsx:propose` 开始你的第一个 change。
```

优雅退出。

---

## 护栏

- **在关键转折点遵循 讲解 → 执行 → 展示 → 暂停 模式**（探索后、proposal 草稿后、tasks 后、归档后）
- **实施期间讲解保持轻量** —— 教学而不说教
- **不跳阶段**，哪怕变更很小——目标是教会工作流
- **在标记点暂停等待回应**，但别过度暂停
- **优雅处理退出** —— 绝不逼用户继续
- **用真实代码库任务** —— 不模拟、不编假例子
- **温和调整规模** —— 引导选小任务，但尊重用户选择
