# AGENTS 治理接入模板

使用 `templates/AGENTS.md.template` 生成项目根目录 `AGENTS.md`（保持简短）。

进入 `explore`、`proposal`、`design`、`apply`、`verify`、`archive` 前：

1. `project-governance.yaml`（含 `governance_layout`、`governance_root`）
2. `{governance_root}/00-index.yaml` — 按阶段加载，禁止全量遍历 `domains/`
3. `{governance_root}/profiles/<profile>.md` → foundations / domains
4. brownfield：读 `authority_map` 中的 legacy 文档
5. 可复用规则 → `{governance_root}/revisions/`（见 `WORKFLOW.md`）
6. 归档前 → `openspec/ARCHIVE-CHECKLIST.md`

禁止：跳过 manifest；母版规则误当作业务项目唯一基线；BMAD 与 OpenSpec 默认双开。
