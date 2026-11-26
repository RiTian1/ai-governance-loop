---
name: bmad-dev-story
description: Execute story implementation following a context filled story spec file. Use when the user says "dev this story [story file]" or "implement the next story in the sprint plan"
canonical_source: .claude/skills/bmad-dev-story
---

# Agent Skills 镜像入口（跨工具兼容层，勿手改）

本文件由 `scripts/sync-agent-skills.py` 从 `.claude/skills/bmad-dev-story` 确定性生成，供 Codex / 其它读取
`.agents/skills/` 的 agent 发现本技能。**权威工作流在 canonical 源，不在此处。**

## Activation

1. 读取 canonical 源：`.claude/skills/bmad-dev-story`
2. 按其中的 `SKILL.md` / `workflow.md` 执行；如需配置见治理入口 `AGENTS.md`。

Regenerate: `python scripts/sync-agent-skills.py --prune`
