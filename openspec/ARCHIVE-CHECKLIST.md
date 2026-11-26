# OpenSpec 归档检查清单

在 `/opsx:archive` 或 `openspec-archive-change` 技能结束前逐项确认。

## 变更工件

- [ ] `tasks.md` 中任务已完成或已注明有意遗留
- [ ] delta specs 已同步到 `openspec/specs/`（或已确认无需同步）
- [ ] 验证证据已记录（命令、日志、降级原因）

## 治理回写

- [ ] 是否产生**可复用**全局规则？
  - 否 → 仅归档到 `openspec/changes/archive/`
  - 是 → 已创建/更新 `revisions/`（`status: candidate` 或已 `merged`）
- [ ] 若更新 `authority_map` 或废弃旧文档，已写入 `project-governance.yaml`

## 索引

- [ ] 新 domain/foundation 已加入 `project-governance.yaml` 的 `enabled_*`（如适用）
- [ ] `revisions/index.yaml` 已登记（如有新修订单）

## 原子提交与推送（强制）

见 `02-engineering-principles.md` §10。

- [ ] 本 change 的 `openspec/changes/archive/` 与配套代码/脚本/配置/验证物料在**同一 commit**
- [ ] 未拆分为「仅归档」与「后续补代码」两次提交
- [ ] 已 push 到远端主协作分支（默认 `origin/master`）
- [ ] 多 change 批次时：每个 change 各自满足「一 change 一原子提交」
