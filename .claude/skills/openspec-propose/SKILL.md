---
name: openspec-propose
description: 提案一个新 change：一步生成全部 artifact。当用户想快速描述要构建什么并得到带 design/specs/tasks 的完整提案时使用。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.5.0"
  localization: zh-CN governance-overlay
---

提案一个新 change——一步完成创建 change 与生成全部 artifact。

我会创建一个带 artifact 的 change：
- proposal.md（做什么、为什么）
- design.md（怎么做）
- tasks.md（实施步骤）

准备实施时运行 openspec-apply-change

---

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：`openspec-propose` 后的参数是 change 名称（kebab-case），或用户想构建内容的一段描述。

**步骤**

1. **未提供输入时，先问用户要做什么**

   用 **AskUserQuestion 工具**（开放式，不给预设选项）询问：
   > "这次要做什么变更？描述你想构建或修复的内容。"

   从描述中派生 kebab-case 名称（如 "添加用户认证" → `add-user-auth`）。

   **重要**：没弄清用户要构建什么之前，不得继续。

2. **创建 change 目录**
   ```bash
   openspec new change "<name>"
   ```
   这会在 CLI 解析出的 planning home 中创建带 `.openspec.yaml` 的 change 脚手架。

3. **获取 artifact 构建顺序**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 获取：
   - `applyRequires`：实施前必须完成的 artifact ID 数组（如 `["tasks"]`）
   - `artifacts`：全部 artifact 及其状态与依赖
   - `planningHome`、`changeRoot`、`artifactPaths`、`actionContext`：路径与范围上下文，用它们，不要假设仓库本地路径。

4. **按序创建 artifact，直到满足 apply 条件**

   用 **TodoWrite 工具**跟踪 artifact 进度。

   按依赖顺序循环（无未决依赖的 artifact 优先）：

   a. **对每个 `ready`（依赖已满足）的 artifact**：
      - 获取指令：
        ```bash
        openspec instructions <artifact-id> --change "<name>" --json
        ```
      - 指令 JSON 包含：
        - `context`：项目背景（对你的约束——不要写进输出）
        - `rules`：artifact 专属规则（对你的约束——不要写进输出）
        - `template`：输出文件应采用的结构
        - `instruction`：该 artifact 类型的 schema 专属指引
        - `resolvedOutputPath`：artifact 写入路径或模式
        - `dependencies`：需先读的已完成 artifact
      - 先读完已完成的依赖文件获取上下文
      - 以 `template` 为结构创建 artifact 文件，写到 `resolvedOutputPath`
      - 写作时应用 `context` 与 `rules` 约束——但不得复制进文件
      - 简要报进度："已创建 <artifact-id>"

   b. **持续到 `applyRequires` 全部完成**
      - 每创建一个 artifact 后重跑 `openspec status --change "<name>" --json`
      - 检查 `applyRequires` 中每个 artifact ID 在 artifacts 数组中是否已 `status: "done"`
      - 全部完成即停止

   c. **某个 artifact 需要用户输入**（上下文不清）：
      - 用 **AskUserQuestion 工具**澄清
      - 然后继续创建

5. **展示最终状态**
   ```bash
   openspec status --change "<name>"
   ```

**输出**

全部 artifact 完成后，总结：
- change 名称与位置
- 已创建的 artifact 列表及简述
- 就绪说明："全部 artifact 已创建！可以开始实施。"
- 提示："运行 `openspec-apply-change` 开始实施。"

**Artifact 撰写指引**

- 每种 artifact 以 `openspec instructions` 输出的 `instruction` 字段为准
- schema 定义了每个 artifact 应包含什么——照做
- 创建前先读依赖 artifact 获取上下文
- 以 `template` 为输出文件结构——填写其各节
- **重要**：`context` 与 `rules` 是对你的约束，不是文件内容
  - 不得把 `<context>`、`<rules>`、`<project_context>` 块复制进 artifact
  - 它们指导你怎么写，但绝不应出现在输出中

**护栏**
- 创建实施所需的**全部** artifact（以 schema 的 `apply.requires` 为准）
- 创建前必读依赖 artifact
- 上下文严重不清时问用户——但优先做出合理决定保持推进节奏
- 同名 change 已存在 → 问用户是继续它还是新建
- 每个 artifact 写完确认文件存在再进行下一个
