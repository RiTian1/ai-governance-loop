---
name: openspec-apply-change
description: 实施 OpenSpec change 中的任务。当用户想开始实施、继续实施或逐个推进任务时使用。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.5.0"
  localization: zh-CN governance-overlay
---

实施 OpenSpec change 中的任务。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：可选指定 change 名称。省略时先尝试从对话上下文推断；模糊或有歧义时 MUST 列出可选 changes 让用户选择。

**步骤**

1. **选定 change**

   有名称直接用。否则：
   - 用户在对话中提到过 → 从上下文推断
   - 只有一个活跃 change → 自动选中
   - 有歧义 → 运行 `openspec list --json` 获取可选 changes，用 **AskUserQuestion 工具**让用户选择

   始终告知："正在使用 change：<name>"，并说明如何切换。

2. **查状态、确认 schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 确认：
   - `schemaName`：所用工作流（如 "spec-driven"）
   - `planningHome`、`changeRoot`、`actionContext`：规划范围与编辑约束
   - 任务在哪个 artifact 中（spec-driven 通常是 "tasks"，其它 schema 以 status 为准）

3. **获取 apply 指令**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   返回内容：
   - `contextFiles`：artifact ID → 具体文件路径数组（随 schema 而异）
   - 进度（total、complete、remaining）
   - 带状态的任务列表
   - 基于当前状态的动态指令

   **状态处理：**
   - `state: "blocked"`（缺 artifact）→ 展示提示，建议用 `openspec-continue-change`
   - `state: "all_done"` → 祝贺，建议归档
   - 其它 → 进入实施

4. **读取上下文文件**

   逐一读取 apply 指令输出中 `contextFiles` 列出的每个文件。
   文件构成取决于所用 schema：
   - **spec-driven**：proposal、specs、design、tasks
   - 其它 schema：以 CLI 输出的 contextFiles 为准

5. **展示当前进度**

   展示：
   - 所用 schema
   - 进度："N/M 任务已完成"
   - 剩余任务概览
   - CLI 给出的动态指令

6. **实施任务（循环直至完成或受阻）**

   对每个待办任务：
   - 说明正在做哪个任务
   - 完成所需代码改动
   - 改动保持最小、聚焦
   - 在任务文件中勾掉该任务：`- [ ]` → `- [x]`
   - 继续下一个

   **以下情况暂停：**
   - 任务不清晰 → 请求澄清
   - 实施中发现设计问题 → 建议更新 artifact
   - 遇到错误或阻塞 → 报告并等待指示
   - 用户打断

7. **完成或暂停时展示状态**

   展示：
   - 本次会话完成的任务
   - 总进度："N/M 任务已完成"
   - 全部完成 → 建议归档
   - 暂停 → 说明原因并等待指示

**实施过程输出**

```
## 实施中：<change-name>（schema：<schema-name>）

正在处理任务 3/7：<任务描述>
[...实施中...]
✓ 任务完成

正在处理任务 4/7：<任务描述>
[...实施中...]
✓ 任务完成
```

**完成时输出**

```
## 实施完成

**Change：** <change-name>
**Schema：** <schema-name>
**进度：** 7/7 任务完成 ✓

### 本次会话完成
- [x] 任务 1
- [x] 任务 2
...

全部任务完成！可用 `openspec-archive-change` 归档该 change。
```

**暂停时输出（遇到问题）**

```
## 实施暂停

**Change：** <change-name>
**Schema：** <schema-name>
**进度：** 4/7 任务完成

### 遇到的问题
<问题描述>

**可选项：**
1. <选项 1>
2. <选项 2>
3. 其它方案

你想怎么处理？
```

**护栏**
- 持续推进任务，直到完成或受阻
- 开工前必读上下文文件（来自 apply 指令输出）
- 任务有歧义 → 先问再做
- 实施暴露设计问题 → 暂停并建议更新 artifact
- 代码改动保持最小、限定在任务范围内
- 每完成一个任务立即更新 checkbox
- 遇到错误、阻塞或需求不清 → 暂停，不要猜
- 使用 CLI 输出的 contextFiles，不要假设固定文件名

**流式工作流集成**

本技能支持"对 change 施加动作"模型：

- **随时可调用**：artifact 未全部完成（只要 tasks 存在）、部分实施后、与其它动作穿插
- **允许更新 artifact**：实施发现设计问题时建议更新 artifact——不锁阶段，流式工作
