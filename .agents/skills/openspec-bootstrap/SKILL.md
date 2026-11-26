---
name: openspec-bootstrap
description: 智能项目分析与治理框架采用。扫描项目代码结构、分析技术栈、推荐 profile 和 domains 组合、生成 project-governance.yaml 和 AGENTS.md。支持 0→1 新项目和 1→2 已有项目。
canonical_source: .claude/skills/openspec-bootstrap
---

# Agent Skills 镜像入口（跨工具兼容层，勿手改）

本文件由 `scripts/sync-agent-skills.py` 从 `.claude/skills/openspec-bootstrap` 确定性生成，供 Codex / 其它读取
`.agents/skills/` 的 agent 发现本技能。**权威工作流在 canonical 源，不在此处。**

## Activation

1. 读取 canonical 源：`.claude/skills/openspec-bootstrap`
2. 按其中的 `SKILL.md` / `workflow.md` 执行；如需配置见治理入口 `AGENTS.md`。

Regenerate: `python scripts/sync-agent-skills.py --prune`
