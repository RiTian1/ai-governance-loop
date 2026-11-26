---
name: governance-continue
description: 治理收尾检查点。仅当用户明确要求收尾、归档或提交，或开启新变更且当前变更已进入收尾时使用。普通继续、原生 resume、上下文压缩均不触发。
canonical_source: .claude/skills/governance-continue
---

# Agent Skills 镜像入口（跨工具兼容层，勿手改）

本文件由 `scripts/sync-agent-skills.py` 从 `.claude/skills/governance-continue` 确定性生成，供 Codex / 其它读取
`.agents/skills/` 的 agent 发现本技能。**权威工作流在 canonical 源，不在此处。**

## Activation

1. 读取 canonical 源：`.claude/skills/governance-continue`
2. 按其中的 `SKILL.md` / `workflow.md` 执行；如需配置见治理入口 `AGENTS.md`。

Regenerate: `python scripts/sync-agent-skills.py --prune`
