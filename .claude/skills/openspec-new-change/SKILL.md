---
name: openspec-new-change
description: 用实验性 artifact 工作流开启一个新的 OpenSpec change。当用户想以结构化分步方式创建新功能、修复或改动时使用。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.5.0"
  localization: zh-CN governance-overlay
---

用实验性 artifact 驱动方式开启一个新 change。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：`openspec-new-change` 后的参数是 change 名称（kebab-case），或用户想构建内容的一段描述。

**步骤**

1. **未提供输入时，先问用户要做什么**

   用 **AskUserQuestion 工具**（开放式，不给预设选项）询问：
   > "这次要做什么变更？描述你想构建或修复的内容。"

   从描述中派生 kebab-case 名称（如 "添加用户认证" → `add-user-auth`）。

   **重要**：没弄清用户要构建什么之前，不得继续。

2. **确定工作流 schema**

   除非用户明确要求其它工作流，否则用默认 schema（省略 `--schema`）。

   **仅在用户提到以下内容时换 schema：**
   - 指名某个 schema → 用 `--schema <name>`
   - "show workflows" / "有哪些工作流" → 运行 `openspec schemas --json` 让用户选

   **其它情况**：省略 `--schema` 用默认。

3. **创建 change 目录**
   ```bash
   openspec new change "<name>"
   ```
   仅当用户要求特定工作流时加 `--schema <name>`。
   这会在 CLI 解析出的 planning home 中创建 change 脚手架。

4. **展示 artifact 状态**
   ```bash
   openspec status --change "<name>" --json
   ```
   使用返回的 `planningHome`、`changeRoot`、`artifactPaths`、`nextSteps`，不要假设仓库本地路径。

5. **获取第一个 artifact 的指令**
   第一个 artifact 取决于 schema。从 status 输出中找第一个状态为 "ready" 的 artifact。
   ```bash
   openspec instructions <first-artifact-id> --change "<name>"
   ```
   输出创建第一个 artifact 所需的模板与上下文。

6. **STOP，等待用户指示**

**输出**

完成上述步骤后，总结：
- change 名称与位置
- 所用 schema/工作流及其 artifact 顺序
- 当前状态（0/N artifact 完成）
- 第一个 artifact 的模板
- 提示："准备好创建第一个 artifact 了吗？运行 `openspec-continue-change`，或直接描述这次变更是做什么的，我来起草。"

**护栏**
- 还不要创建任何 artifact——只展示指令
- 不要越过"展示第一个 artifact 模板"这一步
- 名称不合法（非 kebab-case）→ 要求给出合法名称
- 同名 change 已存在 → 建议改用 `openspec-continue-change`
- 使用非默认工作流时传 --schema
