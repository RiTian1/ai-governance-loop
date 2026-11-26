---
name: "OPSX: Bootstrap"
description: 智能项目分析与治理框架采用 — 扫描项目结构、推荐 profile 和 domains、生成配置文件
category: Workflow
tags: [workflow, bootstrap, governance]
---

智能分析当前项目，推荐治理配置，生成项目激活文件。支持 0→1 新项目和 1→2 已有项目。

**Input**: 可选参数 — 项目名称或简述。无参数时自动从项目配置文件读取或询问。

**Steps**

1. **判断项目状态**

   检查 `project-governance.yaml` 是否已存在。
   扫描源码文件判断 greenfield 或 brownfield。
   向用户确认判断结果。

2. **扫描项目结构**

   并行探测：
   - 技术栈（包管理器、框架、基础设施）
   - 目录结构（src/lib/app/pages/api 等）
   - 已有文档（brownfield 专用）
   - 已有 AI 配置（.cursorrules、CLAUDE.md 等）

3. **推荐 Profile 与组合**

   根据技术栈决策矩阵推荐：
   - 最匹配的 profile
   - 应加载的 foundations
   - 应加载的 domains
   - 应激活的代理
   - 置信度评估

   使用 AskUserQuestion 让用户确认或调整。

4. **生成配置文件**

   - Greenfield: 生成 `project-governance.yaml`
   - Brownfield: 生成 `project-governance.yaml`（含 `authority_map`）+ `AGENTS.md`

   `authority_map` 通过扫描已有文档自动生成草稿：
   - 能匹配到 governance domain 的 → 标记 `authority: governance`
   - 不能匹配的 → 标记 `authority: legacy`
   - 所有映射标注为建议，由用户确认

5. **输出总结与后续步骤**

   展示生成的文件和建议的下一步操作：
   - Greenfield → 编辑 charter → `/opsx:explore` → `/opsx:new`
   - Brownfield → 审查 authority_map → 编辑 charter → `/opsx:new`

**Guardrails**

- 只生成治理配置文件，不修改项目代码
- 所有推荐需用户确认
- brownfield 不删除任何已有文档
- 低置信度时主动说明局限

详细的分析逻辑和决策矩阵见 `openspec-bootstrap` 技能。
