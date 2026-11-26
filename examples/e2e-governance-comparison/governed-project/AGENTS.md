# AGENTS.md

本项目已接入 governance 基线。

AI agent 在进入 `explore`、`proposal`、`design`、`apply`、`verify`、`archive` 前必须：

1. 先读取项目根目录 `project-governance.yaml`
2. 再读取 `docs/governance/00-index.yaml`（路径相对于 `governance_root`）
3. 按 `project_type_profile`、`enabled_foundations`、`enabled_domains` 加载对应治理文档（勿全量加载）
4. 若本次变更涉及规则语义、验证策略、E2E、CI 或交付证据，必须读取验证政策与自动化领域文档
5. 新发现的跨项目规则不得只留在聊天中，必须回写到 `docs/governance/revisions/`（见 `WORKFLOW.md`）或正式基线
6. OpenSpec 归档前对照 `openspec/ARCHIVE-CHECKLIST.md`

禁止：

- 跳过 `project-governance.yaml` 直接猜测项目现行规则
- 只根据用户一句话直接改代码而不判断是否触发验证门禁
- 规则语义变化时，只补接口测试，不复审 E2E 基线
- 交付时只给结论，不给结构化证据和变更影响范围
