---
name: openspec-propose
description: 提案一个新 change：一步生成全部 artifact。当用户想快速描述要构建什么并得到带 design/specs/tasks 的完整提案时使用。
canonical_source: .claude/skills/openspec-propose
---

# Agent Skills 镜像入口（跨工具兼容层，勿手改）

本文件由 `scripts/sync-agent-skills.py` 从 `.claude/skills/openspec-propose` 确定性生成，供 Codex / 其它读取
`.agents/skills/` 的 agent 发现本技能。**权威工作流在 canonical 源，不在此处。**

## Activation

1. 读取 canonical 源：`.claude/skills/openspec-propose`
2. 按其中的 `SKILL.md` / `workflow.md` 执行；如需配置见治理入口 `AGENTS.md`。

Regenerate: `python scripts/sync-agent-skills.py --prune`
