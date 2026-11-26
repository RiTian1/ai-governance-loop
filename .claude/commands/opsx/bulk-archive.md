---
name: "OPSX: Bulk Archive"
description: 一次归档多个已完成的 change
category: Workflow
tags: [workflow, archive, experimental, bulk]
---

在一次操作中归档多个已完成的 change。

本技能支持批量归档，并通过检查代码库确认实际实现情况来智能处理 spec 冲突。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：无必填参数（交互式选择）

**步骤**

1. **获取活跃 changes**

   运行 `openspec list --json` 获取全部活跃 change。

   没有活跃 change 就告知用户并停止。

2. **让用户选择 change**

   用 **AskUserQuestion 工具**（多选）让用户挑选：
   - 每个 change 附带其 schema
   - 提供 "All changes" 选项
   - 数量不限（1 个也行，2 个以上是典型场景）

   **重要**：不要自动选。始终让用户选。

3. **批量校验——收集所有选中 change 的状态**

   对每个选中的 change 收集：

   a. **artifact 状态** —— 运行 `openspec status --change "<name>" --json`
      - 解析 `schemaName`、`artifacts`、`planningHome`、`changeRoot`、`artifactPaths`、`actionContext`
      - 记录哪些 artifact 是 `done`、哪些不是

   b. **任务完成度** —— 读 status JSON 的 `artifactPaths.tasks.existingOutputPaths`
      - 统计 `- [ ]`（未完成）与 `- [x]`（已完成）
      - 无任务文件记为 "No tasks"

   c. **delta specs** —— 查 status JSON 的 `artifactPaths.specs.existingOutputPaths`
      - 列出有哪些 capability spec
      - 逐个提取需求名（匹配 `### Requirement: <name>` 的行）

4. **检测 spec 冲突**

   构建 `capability -> [触碰它的 changes]` 映射：

   ```
   auth -> [change-a, change-b]  <- 冲突（2+ 个 change）
   api  -> [change-c]            <- 正常（只有 1 个）
   ```

   2 个以上选中 change 对同一 capability 有 delta spec 即为冲突。

5. **agent 方式解决冲突**

   **对每个冲突**，调查代码库：

   a. **读各冲突 change 的 delta spec**，弄清各自声称要加/改什么

   b. **搜索代码库**找实现证据：
      - 找实现各 delta spec 需求的代码
      - 查相关文件、函数、测试

   c. **确定解决方案**：
      - 只有一个 change 真正实现了 → 只同步它的 specs
      - 两个都实现了 → 按时间顺序应用（旧的先、新的覆盖）
      - 都没实现 → 跳过 spec 同步，警告用户

   d. **记录每个冲突的解决方案**：
      - 应用哪个 change 的 specs
      - 什么顺序（若两个都用）
      - 依据（代码库里发现了什么）

6. **展示汇总状态表**

   用表格总结所有 change：

   ```
   | Change              | Artifacts | Tasks | Specs   | 冲突      | 状态   |
   |---------------------|-----------|-------|---------|-----------|--------|
   | schema-management   | Done      | 5/5   | 2 delta | 无        | Ready  |
   | project-config      | Done      | 3/3   | 1 delta | 无        | Ready  |
   | add-oauth           | Done      | 4/4   | 1 delta | auth (!)  | Ready* |
   | add-verify-skill    | 差 1 个   | 2/5   | 无      | 无        | Warn   |
   ```

   有冲突时展示解决方案：
   ```
   * 冲突解决：
     - auth spec：先应用 add-oauth 再应用 add-jwt（两者都已实现，按时间顺序）
   ```

   有未完成的 change 时展示警告：
   ```
   警告：
   - add-verify-skill：1 个 artifact 未完成，3 个任务未完成
   ```

7. **确认批量操作**

   用 **AskUserQuestion 工具**做一次性确认：

   - "归档 N 个 change？"，按状态给选项
   - 选项可包括：
     - "归档全部 N 个"
     - "只归档 N 个就绪的（跳过未完成）"
     - "取消"

   有未完成的 change 时，明确说明它们会带警告归档。

8. **对每个确认的 change 执行归档**

   按既定顺序处理（遵循冲突解决方案）：

   a. **有 delta spec 先同步 specs**：
      - 用 openspec-sync-specs 的方式（agent 驱动智能合并）
      - 冲突按已定顺序应用
      - 记录是否做了同步

   b. **执行归档**：
      ```bash
      mkdir -p "<planningHome.changesDir>/archive"
      mv "<changeRoot>" "<planningHome.changesDir>/archive/YYYY-MM-DD-<name>"
      ```

   c. **记录每个 change 的结果**：
      - 成功：归档完成
      - 失败：归档出错（记录错误）
      - 跳过：用户选择不归档（如适用）

9. **展示总结**

   最终结果：

   ```
   ## 批量归档完成

   已归档 3 个 change：
   - schema-management-cli -> archive/2026-01-19-schema-management-cli/
   - project-config -> archive/2026-01-19-project-config/
   - add-oauth -> archive/2026-01-19-add-oauth/

   跳过 1 个：
   - add-verify-skill（用户选择不归档未完成项）

   Spec 同步摘要：
   - 4 个 delta spec 已同步到主 specs
   - 解决 1 个冲突（auth：按时间顺序应用两者）
   ```

   有失败时：
   ```
   失败 1 个：
   - some-change：归档目录已存在
   ```

**冲突解决示例**

示例 1：只有一个实现了
```
冲突：specs/auth/spec.md 被 [add-oauth, add-jwt] 触碰

检查 add-oauth：
- delta 新增 "OAuth Provider Integration" 需求
- 搜索代码库……找到 src/auth/oauth.ts 实现了 OAuth 流程

检查 add-jwt：
- delta 新增 "JWT Token Handling" 需求
- 搜索代码库……未找到 JWT 实现

结论：只有 add-oauth 已实现。只同步 add-oauth 的 specs。
```

示例 2：两个都实现了
```
冲突：specs/api/spec.md 被 [add-rest-api, add-graphql] 触碰

检查 add-rest-api（创建于 2026-01-10）：
- delta 新增 "REST Endpoints" 需求
- 搜索代码库……找到 src/api/rest.ts

检查 add-graphql（创建于 2026-01-15）：
- delta 新增 "GraphQL Schema" 需求
- 搜索代码库……找到 src/api/graphql.ts

结论：两者都已实现。先应用 add-rest-api 的 specs，
再应用 add-graphql（时间顺序，新者优先生效）。
```

**成功输出**

```
## 批量归档完成

已归档 N 个 change：
- <change-1> -> archive/YYYY-MM-DD-<change-1>/
- <change-2> -> archive/YYYY-MM-DD-<change-2>/

Spec 同步摘要：
- N 个 delta spec 已同步到主 specs
- 无冲突（或：解决 M 个冲突）
```

**部分成功输出**

```
## 批量归档完成（部分）

已归档 N 个：
- <change-1> -> archive/YYYY-MM-DD-<change-1>/

跳过 M 个：
- <change-2>（用户选择不归档未完成项）

失败 K 个：
- <change-3>：归档目录已存在
```

**无 change 时输出**

```
## 没有可归档的 change

未发现活跃 change。先创建一个新 change。
```

**护栏**
- 数量不限（1 个可以，2 个以上是典型场景）
- 必须让用户选择，绝不自动选
- 尽早检测 spec 冲突，并通过查代码库解决
- 两个 change 都实现时按时间顺序应用 specs
- 仅在实现缺失时跳过 spec 同步（并警告用户）
- 确认前按 change 展示清晰状态
- 整批用一次确认
- 记录并汇报全部结果（成功/跳过/失败）
- 移入归档时保留 .openspec.yaml
- 归档目录名用当前日期：YYYY-MM-DD-<name>
- 归档目标已存在时该 change 失败，其余继续
