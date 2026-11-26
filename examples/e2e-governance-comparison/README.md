# E2E Governance 对比环境

这个示例目录用于对比两种项目环境：

- `governed-project/`: 已接入 `governance/`，AI agent 在对话与执行前需要先装载项目治理基线。
- `ungoverned-project/`: 未继承治理基线，AI agent 只依赖仓库局部上下文或即时提示工作。

对比目标不是“谁更会写代码”，而是观察当需求变更落到 `test/e2e` 这种涉及语义、验证、证据与回归门禁的区域时，有无 governance 会带来什么差异。

本示例统一使用同一个需求变更：

- `rasp_exception_url_black_batch_remove_behavior` 相关接口新增语义：
- 服务端在解析 `ids` 时，应自动忽略首尾逗号、重复逗号与空白片段。
- 对于空片段不报错；对于去重后有效 ID 为空，返回参数错误。
- 这是规则语义变更，不只是“修个接口返回值”。

建议阅读顺序：

1. `governed-project/AGENTS.md`
2. `governed-project/project-governance.yaml`
3. `governed-project/docs/changes/e2e-batch-remove-trim/`
4. `ungoverned-project/AGENTS.md`
5. `ungoverned-project/docs/changes/e2e-batch-remove-trim/`
