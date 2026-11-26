---
name: openspec-archive-change
description: 在实验性工作流中归档已完成的 change。实现完成后需要收尾归档时使用。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.5.0"
  localization: zh-CN governance-overlay
---

归档实验性工作流中一个已完成的 change。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：可在 `openspec-archive-change` 后指定 change 名称。省略时先尝试从对话上下文推断；模糊或有歧义时 MUST 列出可选 changes 让用户选择。

**步骤**

1. **未提供 change 名称时，让用户选择**

   运行 `openspec list --json` 获取可选 changes，用 **AskUserQuestion 工具**让用户选择。

   只展示活跃（未归档）的 change。
   如有 schema 信息一并展示。

   **重要**：不要猜、不要自动选。始终让用户选。

2. **检查 artifact 完成状态**

   运行 `openspec status --change "<name>" --json` 检查 artifact 完成度。

   解析 JSON 确认：
   - `schemaName`：所用工作流
   - `planningHome`、`changeRoot`、`artifactPaths`、`actionContext`：路径与范围上下文
   - `artifacts`：artifact 列表及状态（`done` 或其它）

   **若有 artifact 未 `done`：**
   - 显示警告，列出未完成的 artifact
   - 请用户确认是否继续
   - 用户确认后再继续

3. **检查任务完成状态**

   读任务文件（通常是 `tasks.md`）检查未完成任务。

   统计 `- [ ]`（未完成）与 `- [x]`（已完成）数量。

   **发现未完成任务：**
   - 显示警告及未完成数量
   - 请用户确认是否继续
   - 用户确认后再继续

   **无任务文件：** 跳过任务相关警告，直接继续。

4. **评估 delta spec 同步状态**

   用 status JSON 的 `artifactPaths.specs.existingOutputPaths` 检查是否存在 delta spec。不存在则跳过同步询问。

   **存在 delta spec 时：**
   - 逐个对比 delta spec 与主 spec（`openspec/specs/<capability>/spec.md`）
   - 判断将应用哪些变化（新增、修改、删除、重命名）
   - 先展示合并摘要再询问

   **询问选项：**
   - 需要同步："立即同步（推荐）"、"不同步直接归档"
   - 已同步："立即归档"、"仍要同步"、"取消"

   用户选择同步时，用 Task 工具（subagent_type: "general-purpose"，prompt: "Use Skill tool to invoke openspec-sync-specs for change '<name>'. Delta spec analysis: <附上已分析的 delta spec 摘要>"）。无论选哪项，之后都继续归档。

5. **执行归档**

   若 `planningHome.changesDir` 下无 `archive` 目录则创建：
   ```bash
   mkdir -p "<planningHome.changesDir>/archive"
   ```

   用当前日期生成目标名：`YYYY-MM-DD-<change-name>`

   **检查目标是否已存在：**
   - 存在：报错失败，建议重命名既有归档或换日期
   - 不存在：把 `changeRoot` 移入归档目录

   ```bash
   mv "<changeRoot>" "<planningHome.changesDir>/archive/YYYY-MM-DD-<name>"
   ```

6. **展示摘要**

   归档完成摘要包含：
   - change 名称
   - 所用 schema
   - 归档位置
   - spec 同步状态（已同步 / 跳过同步 / 无 delta spec）
   - 警告说明（未完成 artifact/任务）

**成功输出**

```
## 归档完成

**Change：** <change-name>
**Schema：** <schema-name>
**归档到：** 由 `planningHome.changesDir`/YYYY-MM-DD-<name>/ 推导出的归档路径
**Specs：** ✓ 已同步到主 specs

全部 artifact 完成。全部任务完成。
```

**成功输出（无 delta spec）**

```
## 归档完成

**Change：** <change-name>
**Schema：** <schema-name>
**归档到：** 由 `planningHome.changesDir`/YYYY-MM-DD-<name>/ 推导出的归档路径
**Specs：** 无 delta spec

全部 artifact 完成。全部任务完成。
```

**带警告的成功输出**

```
## 归档完成（含警告）

**Change：** <change-name>
**Schema：** <schema-name>
**归档到：** 由 `planningHome.changesDir`/YYYY-MM-DD-<name>/ 推导出的归档路径
**Specs：** 跳过同步（用户选择跳过）

**警告：**
- 归档时有 2 个 artifact 未完成
- 归档时有 3 个任务未完成
- 跳过了 delta spec 同步（用户选择跳过）

若非有意为之，请复查该归档。
```

**失败输出（归档已存在）**

```
## 归档失败

**Change：** <change-name>
**目标：** 由 `planningHome.changesDir`/YYYY-MM-DD-<name>/ 推导出的归档路径

目标归档目录已存在。

**可选项：**
1. 重命名既有归档
2. 若是重复项，删除既有归档
3. 换个日期再归档
```

**护栏**
- 未提供 change 时必须让用户选择
- 用 artifact 图（openspec status --json）做完成度检查
- 警告不阻断归档——告知并确认即可
- 移入归档时保留 .openspec.yaml（随目录一起移动）
- 清晰总结发生了什么
- 需要同步时用 Skill 工具调 `openspec-sync-specs`（agent 驱动）
- 存在 delta spec 时，必先做同步评估并展示合并摘要再询问
