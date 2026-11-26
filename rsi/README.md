# RSI 对话索引域

跨 CLI 接入遵守 native-cli-compatibility.md：先原生恢复、再按疑点查原文、最后才用派生索引定位。

本域只保存 **CLI 原生会话的派生索引**，不接管、不重写、不宣称能恢复完整对话。Cursor、Codex 等各自的 session 记录及其原生回溯方式是对话权威；项目 Git 是代码与工件权威。两类权威相互引用，不互相替代。

## 记录结构

- 一份 CLI 会话对应 rsi/sessions/<project_id>/<cli>-<identity-hash>.json；哈希由 CLI、机器与原生 session ID 派生，避免重名冲突。
- 任务维度用索引记录中的 task_id 搜索；不维护第二份容易漂移的任务文件。
- `rsi/_index.yaml`：路由和体量上限。自动装载仅看这份小索引，只有检索命中才读具体摘要。

索引位置是**治理仓的 rsi 域**；默认的任务检查点脚本仍把快照写在项目的 `_logs/rsi-tasks/`。两者职责不同：前者用于跨机器发现和定位，后者用于本机恢复校验。显式共享快照也不改变对话权威。

在母版仓根目录或业务项目根目录运行索引脚本；默认按项目 manifest 定位治理根，也可显式传 --governance-root。

## 录入与回溯

1. Agent 在阶段检查点由原 CLI 提供 session ID 和原生定位；核实后调用 `scripts/rsi_session_index.py add`，用状态 JSON 生成摘要索引。可选读取可访问的原生 session 文件并计算 SHA-256；不复制原文。
2. 搜索时先运行 `scripts/rsi_session_index.py search`；返回命中摘要和 CLI 原生定位。索引中不存全量对话。
3. 对重要决策、矛盾、遗漏或审计问题，运行 `scripts/rsi_session_index.py locate`，回到原 CLI session 核对原文；原记录不可访问时标记"待核实"，不得把摘要升级为事实。
4. 若原 CLI 无法跨机器读取其 session，应通过该 CLI 支持的同步/导出和访问控制另行解决；RSI 索引不会补出原文。原生文件的哈希仅证明索引生成时读到过该文件，不证明其他机器能访问或内容永久保留。

## 来源与隐私约束

- 必填 `cli/session_id/host/locator`；定位器可为 CLI 原生 ID、已验证的路径或 URI，路径不代表共享可达。
- 无法读取原生文件时，条目标记 unverified，后续回原 CLI 核对。仅记录经核对的短摘要和锚点，不保存原始消息、工具输出全文、口令、会话凭证或用户隐私。
- 摘要变更要保留 Git 历史。原生 session 若被清理或移动，应更新定位状态，不可无声替换来源。
- 同一会话 ID 在同一个 CLI/host 命名空间下只允许一个索引文件；并发写入通过 Git 分支与 MR 消解。

Agent 填写的锚点只是导航提示；即使附有原生文件 SHA-256，摘要正确性仍需回读原文验证。

## 索引契约

参见 `templates/rsi-session-index-template.json`。每条摘要必须明确 `authority: cli-session` 与 `derived: true`；治理仓不对会话原文做可用性保证。
