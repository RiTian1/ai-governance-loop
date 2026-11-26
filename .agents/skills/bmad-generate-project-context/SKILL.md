---
name: bmad-generate-project-context
description: Create project-context.md with AI rules. Use when the user says "generate project context" or "create project context"
canonical_source: .claude/skills/bmad-generate-project-context
---

# Agent Skills 镜像入口（跨工具兼容层，勿手改）

本文件由 `scripts/sync-agent-skills.py` 从 `.claude/skills/bmad-generate-project-context` 确定性生成，供 Codex / 其它读取
`.agents/skills/` 的 agent 发现本技能。**权威工作流在 canonical 源，不在此处。**

## Activation

1. 读取 canonical 源：`.claude/skills/bmad-generate-project-context`
2. 按其中的 `SKILL.md` / `workflow.md` 执行；如需配置见治理入口 `AGENTS.md`。

Regenerate: `python scripts/sync-agent-skills.py --prune`
