---
name: "OPSX: Sync"
description: 把 change 的 delta specs 同步到主 specs
category: Workflow
tags: [workflow, specs, experimental]
---

把 change 中的 delta specs 同步到主 specs。

这是一个 **agent 驱动**的操作——由你读取 delta spec 并直接编辑主 spec 来应用变化。这样才能智能合并（例如新增一个场景而不必复制整个 requirement）。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：可在 `/opsx:sync` 后指定 change 名称（如 `/opsx:sync add-auth`）。省略时先尝试从对话上下文推断；模糊或有歧义时 MUST 列出可选 changes 让用户选择。

**步骤**

1. **未提供 change 名称时，让用户选择**

   运行 `openspec list --json` 获取可选 changes，用 **AskUserQuestion 工具**让用户选择。

   只展示带 delta spec（`specs/` 目录下有文件）的 change。

   **重要**：不要猜、不要自动选。始终让用户选。

2. **解析 change 上下文**

   运行：
   ```bash
   openspec status --change "<name>" --json
   ```

3. **找到 delta specs**

   以 status JSON 的 `artifactPaths.specs.existingOutputPaths` 作为 delta spec 文件列表。

   每个 delta spec 文件包含这些小节：
   - `## ADDED Requirements` —— 要新增的需求
   - `## MODIFIED Requirements` —— 对既有需求的修改
   - `## REMOVED Requirements` —— 要删除的需求
   - `## RENAMED Requirements` —— 要重命名的需求（FROM:/TO: 格式）

   没有 delta spec 就告知用户并停止。

4. **逐个 delta spec 应用到主 spec**

   对 CLI 返回的每个 capability delta spec 路径：

   a. **读 delta spec**，理解变更意图

   b. **读主 spec**（`openspec/specs/<capability>/spec.md`，可能还不存在）

   c. **智能应用变化**：

      **ADDED Requirements：**
      - 主 spec 中不存在 → 新增
      - 已存在 → 更新为 delta 版本（按隐式 MODIFIED 处理）

      **MODIFIED Requirements：**
      - 在主 spec 中找到该需求
      - 应用变化，可能是：
        - 新增场景（无需复制既有场景）
        - 修改既有场景
        - 修改需求描述
      - 保留 delta 中未提及的场景/内容

      **REMOVED Requirements：**
      - 从主 spec 删除整个需求块

      **RENAMED Requirements：**
      - 找到 FROM 需求，重命名为 TO

   d. **capability 尚不存在时创建新主 spec**：
      - 创建 `openspec/specs/<capability>/spec.md`
      - 加 Purpose 一节（可以简短，标 TBD）
      - 加 Requirements 一节，写入 ADDED 的需求

5. **展示摘要**

   应用完毕后总结：
   - 更新了哪些 capability
   - 做了哪些变化（需求的新增/修改/删除/重命名）

**Delta Spec 格式参考**

```markdown
## ADDED Requirements

### Requirement: New Feature
The system SHALL do something new.

#### Scenario: Basic case
- **WHEN** user does X
- **THEN** system does Y

## MODIFIED Requirements

### Requirement: Existing Feature
#### Scenario: New scenario to add
- **WHEN** user does A
- **THEN** system does B

## REMOVED Requirements

### Requirement: Deprecated Feature

## RENAMED Requirements

- FROM: `### Requirement: Old Name`
- TO: `### Requirement: New Name`
```

**核心原则：智能合并**

与程序化合并不同，你可以做**局部更新**：
- 要加场景，只需把该场景放在 MODIFIED 下——不必复制既有场景
- delta 表达的是*意图*，不是整体替换
- 用你的判断合理地合并变化

**成功输出**

```
## Specs 已同步：<change-name>

已更新主 specs：

**<capability-1>**：
- 新增需求："New Feature"
- 修改需求："Existing Feature"（新增 1 个场景）

**<capability-2>**：
- 创建了新 spec 文件
- 新增需求："Another Feature"

主 specs 已更新。该 change 仍处于活跃状态——实现完成后再归档。
```

**护栏**
- 改动前必读 delta 与主 spec 两边
- 保留 delta 未提及的既有内容
- 有不清楚的地方先澄清
- 边改边展示改了什么
- 操作应幂等——跑两次结果一致
