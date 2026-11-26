---
name: openspec-continue-change
description: 继续推进 OpenSpec change：创建下一个 artifact。当用户想推进变更、创建下一个 artifact 或继续工作流时使用。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.5.0"
  localization: zh-CN governance-overlay
---

继续推进一个 change：创建下一个 artifact。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：可在 `openspec-continue-change` 后指定 change 名称。省略时先尝试从对话上下文推断；模糊或有歧义时 MUST 列出可选 changes 让用户选择。

**步骤**

1. **未提供 change 名称时，让用户选择**

   运行 `openspec list --json` 获取按最近修改排序的 changes，再用 **AskUserQuestion 工具**让用户选择。

   展示最近修改的 3-4 个 change 作为选项，包含：
   - change 名称
   - schema（取 `schema` 字段，缺省为 "spec-driven"）
   - 状态（如 "0/5 tasks"、"complete"、"no tasks"）
   - 最近修改时间（取 `lastModified` 字段）

   最近修改的那个标注 "(Recommended)"——大概率是用户想继续的。

   **重要**：不要猜、不要自动选。始终让用户选。

2. **查当前状态**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 了解当前状态。响应包含：
   - `schemaName`：所用工作流 schema（如 "spec-driven"）
   - `artifacts`：artifact 数组及各自状态（"done"、"ready"、"blocked"）
   - `isComplete`：是否全部 artifact 已完成
   - `planningHome`、`changeRoot`、`artifactPaths`、`actionContext`：路径与范围上下文，用它们，不要假设仓库本地路径。

3. **按状态行动**：

   ---

   **全部 artifact 已完成（`isComplete: true`）**：
   - 祝贺用户
   - 展示最终状态（含所用 schema）
   - 建议："全部 artifact 已创建！可以用 `openspec-apply-change` 实施，或用 `openspec-archive-change` 归档。"
   - STOP

   ---

   **有 artifact 可创建**（status 中存在 `status: "ready"`）：
   - 取 status 输出中**第一个** `status: "ready"` 的 artifact
   - 获取其指令：
     ```bash
     openspec instructions <artifact-id> --change "<name>" --json
     ```
   - 解析 JSON，关键字段：
     - `context`：项目背景（对你的约束——不要写进输出）
     - `rules`：artifact 专属规则（对你的约束——不要写进输出）
     - `template`：输出文件应采用的结构
     - `instruction`：schema 专属指引
     - `resolvedOutputPath`：artifact 写入路径或模式
     - `dependencies`：需先读的已完成 artifact
   - **创建 artifact 文件**：
     - 先读完已完成的依赖文件获取上下文
     - 以 `template` 为结构填写各节
     - 写作时应用 `context` 与 `rules` 约束——但不得复制进文件
     - 写到指令给出的 `resolvedOutputPath`；若是 glob 模式，结合 schema 指引与 change 上下文确定具体路径
   - 展示创建了什么、解锁了什么
   - 创建**一个** artifact 后即 STOP

   ---

   **没有 ready 的 artifact（全部 blocked）**：
   - 合法 schema 不应出现
   - 展示状态并建议排查

4. **创建 artifact 后展示进度**
   ```bash
   openspec status --change "<name>"
   ```

**输出**

每次调用后展示：
- 创建了哪个 artifact
- 所用 schema 工作流
- 当前进度（N/M 完成）
- 现在解锁了哪些 artifact
- 提示："运行 `openspec-continue-change` 创建下一个 artifact"

**Artifact 撰写指引**

artifact 类型与用途取决于 schema。以指令输出的 `instruction` 字段为准。

常见 artifact 模式：

**spec-driven schema**（proposal → specs → design → tasks）：
- **proposal.md**：变更意图不清就先问用户。填写 Why、What Changes、Capabilities、Impact。
  - Capabilities 一节至关重要——列出的每个 capability 都需要一个 spec 文件。
- **specs/<capability>/spec.md**：按 proposal 的 Capabilities 逐个建 spec（用 capability 名，不是 change 名）。
- **design.md**：记录技术决策、架构与实现方案。
- **tasks.md**：把实现拆成带 checkbox 的任务。

其它 schema 以 CLI 输出的 `instruction` 字段为准。

**护栏**
- 每次调用只创建**一个** artifact
- 创建前必读依赖 artifact
- 不跳过、不乱序
- 上下文不清 → 先问用户再创建
- 写完后确认文件存在再报进度
- 按 schema 的 artifact 顺序走，不要假设固定名称
- **重要**：`context` 与 `rules` 是对你的约束，不是文件内容
  - 不得把 `<context>`、`<rules>`、`<project_context>` 块复制进 artifact
  - 它们指导你怎么写，但绝不应出现在输出中
