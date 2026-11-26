---
name: openspec-verify-change
description: 验证实现与 change artifact 是否匹配。当用户想在归档前确认实现完整、正确且一致时使用。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.5.0"
  localization: zh-CN governance-overlay
---

验证实现是否与 change 的 artifact（specs、tasks、design）匹配。

**Store 选择**：若用户点名某个 store（store = 本机注册的独立 OpenSpec 仓库），或工作位于某个 store 中，先运行 `openspec store list --json` 获取已注册的 store id，然后在读写 specs 与 changes 的命令（`new change`、`status`、`instructions`、`list`、`show`、`validate`、`archive`、`doctor`、`context`）上传 `--store <id>`。其它命令不接受该 flag。命令输出中的提示已带该 flag；后续操作请保持。未指定 store 时，命令作用于最近的本地 `openspec/` 根。

**输入**：可在 `openspec-verify-change` 后指定 change 名称。省略时先尝试从对话上下文推断；模糊或有歧义时 MUST 列出可选 changes 让用户选择。

**步骤**

1. **未提供 change 名称时，让用户选择**

   运行 `openspec list --json` 获取可选 changes，用 **AskUserQuestion 工具**让用户选择。

   只展示有实施任务（存在 tasks artifact）的 change。
   如有 schema 信息一并展示。
   任务未完成的标注 "(In Progress)"。

   **重要**：不要猜、不要自动选。始终让用户选。

2. **查状态、确认 schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 确认：
   - `schemaName`：所用工作流（如 "spec-driven"）
   - `planningHome`、`changeRoot`、`artifactPaths`、`actionContext`：路径与范围上下文
   - 该 change 有哪些 artifact

3. **获取规划上下文并加载 artifact**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   返回 change 目录与 `contextFiles`（artifact ID → 具体文件路径数组）。读取 `contextFiles` 中全部可用 artifact。

4. **初始化验证报告结构**

   报告分三个维度：
   - **完备性（Completeness）**：任务与 spec 覆盖
   - **正确性（Correctness）**：需求实现与场景覆盖
   - **一致性（Coherence）**：设计遵循与模式一致

   每个维度的问题分 CRITICAL、WARNING、SUGGESTION 三级。

5. **验证完备性**

   **任务完成度**：
   - `contextFiles.tasks` 存在则逐个读取其中文件
   - 解析 checkbox：`- [ ]`（未完成）与 `- [x]`（已完成）
   - 统计完成/总数
   - 存在未完成任务时：
     - 每个未完成任务记一条 CRITICAL
     - 建议："完成任务：<描述>"，或"若已实现则勾掉"

   **Spec 覆盖**：
   - `contextFiles.specs` 中存在 delta spec 时：
     - 提取全部需求（"### Requirement:" 标记）
     - 对每个需求：
       - 按需求关键词搜索代码库
       - 评估实现是否可能存在
     - 需求疑似未实现时：
       - 记 CRITICAL："未找到需求实现：<需求名>"
       - 建议："实现需求 X：<描述>"

6. **验证正确性**

   **需求-实现映射**：
   - 对 delta spec 中每个需求：
     - 在代码库搜索实现证据
     - 找到则记录文件路径与行号范围
     - 评估实现是否符合需求意图
     - 发现偏差时：
       - 记 WARNING："实现可能偏离 spec：<细节>"
       - 建议："对照需求 X 复查 <file>:<lines>"

   **场景覆盖**：
   - 对 delta spec 中每个场景（"#### Scenario:" 标记）：
     - 检查代码是否处理了对应条件
     - 检查是否有测试覆盖该场景
     - 场景疑似未覆盖时：
       - 记 WARNING："场景未覆盖：<场景名>"
       - 建议："为场景补测试或实现：<描述>"

7. **验证一致性**

   **设计遵循**：
   - `contextFiles.design` 存在时：
     - 提取关键决策（找 "Decision:"、"Approach:"、"Architecture:" 等小节）
     - 核对实现是否遵循这些决策
     - 发现矛盾时：
       - 记 WARNING："未遵循设计决策：<决策>"
       - 建议："修正实现，或修订 design.md 使其符合现实"
   - 无 design.md：跳过该项检查，注明"无 design.md 可对照"

   **代码模式一致性**：
   - 检查新代码与项目既有模式的一致性
   - 看文件命名、目录结构、编码风格
   - 有明显偏离时：
     - 记 SUGGESTION："代码模式偏离：<细节>"
     - 建议："考虑遵循项目模式：<示例>"

8. **生成验证报告**

   **摘要计分卡**：
   ```
   ## 验证报告：<change-name>

   ### 摘要
   | 维度   | 状态               |
   |--------|--------------------|
   | 完备性 | X/Y 任务，N 需求   |
   | 正确性 | M/N 需求已覆盖     |
   | 一致性 | 遵循 / 有问题      |
   ```

   **按优先级列问题**：

   1. **CRITICAL**（归档前必须修）：
      - 未完成的任务
      - 缺失的需求实现
      - 每条都给出具体可执行的建议

   2. **WARNING**（应该修）：
      - spec/design 偏差
      - 场景覆盖缺失
      - 每条都给出具体建议

   3. **SUGGESTION**（修了更好）：
      - 模式不一致
      - 小改进
      - 每条都给出具体建议

   **最终评估**：
   - 有 CRITICAL："发现 X 个关键问题。归档前先修复。"
   - 只有 WARNING："无关键问题。有 Y 个警告可斟酌。可归档（附带上述改进项）。"
   - 全部通过："全部检查通过。可以归档。"

**验证启发式**

- **完备性**：聚焦客观清单项（checkbox、需求列表）
- **正确性**：用关键词搜索、文件路径分析、合理推断——不要求绝对确定
- **一致性**：找显眼的不一致，不吹毛求疵抠风格
- **误报控制**：拿不准时，宁记 SUGGESTION 不记 WARNING、宁记 WARNING 不记 CRITICAL
- **可执行性**：每个问题必须带具体建议，能给文件/行号就给

**优雅降级**

- 只有 tasks.md：只验任务完成度，跳过 spec/design 检查
- tasks + specs：验完备性与正确性，跳过 design
- artifact 齐全：验全部三个维度
- 始终注明跳过了哪些检查及原因

**输出格式**

用清晰的 markdown：
- 摘要计分卡用表格
- 问题按 CRITICAL/WARNING/SUGGESTION 分组列出
- 代码引用格式：`file.ts:123`
- 建议具体可执行
- 不写"建议复查一下"这类空话
