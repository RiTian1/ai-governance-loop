# Agent 工具与 MCP 治理

## 1. 目标

- 规范 AI Agent 通过 Model Context Protocol（MCP）访问外部工具、数据与系统的方式。
- 降低工具投毒、越权调用、命令注入与秘密泄露风险。
- 使 PR / 变更可审计：用了哪些 MCP、谁批准、作用范围是什么。

## 2. 适用范围

- 使用 Cursor、Claude Code、Copilot、Codex 等且启用 MCP 的项目。
- 涉及生产数据、内网 API、部署、密钥、客户数据的连接器。

## 3. 默认原则

- **最小权限**：仅启用完成当前任务所需的 MCP server；禁止「为了方便」默认全开。
- **显式披露**：变更 PR 正文须列出新增/修改的 MCP server 与用途（见 §6）。
- **人类可批准**：写生产、发版、改权限类操作须有人工确认，不得由 Agent 单独闭环。
- **可复现**：关键 Agent 任务保留 intent → 工具调用摘要 → diff 的追溯链（与 `04-verification-policy.md` 一致）。

## 4. 连接器登记（项目级）

在 `project-governance.yaml` 或 `docs/project-rules.md` 维护 `mcp_connectors`（可选块）：

| 字段 | 说明 |
|------|------|
| `id` | 稳定标识，如 `gitlab`, `sentry-prod` |
| `owner` | 负责团队或个人 |
| `scope` | `read-only` / `read-write` / `deploy` |
| `allowed_paths` | 可访问仓库路径或环境（如 `staging` only） |
| `secrets` | 引用密钥名，**禁止**明文写进仓库 |

未登记的 connector 不得用于生产相关任务。

## 5. 安全约束

- 禁止将 MCP 返回的不可信内容直接拼进 shell、SQL、部署命令（先结构化校验）。
- 禁止通过 MCP 读取或写入未在 `allowed_paths` 内的路径。
- 禁止把 token、cookie、私钥写入 MCP 配置、AGENTS.md、规则导出文件或聊天日志。
- 优先使用组织批准的 MCP registry / 网关；公共 server 须经过安全评审。
- 遵循 MCP OAuth 2.1 与 RFC 8707 resource indicator（企业环境）。

## 6. PR 与变更披露模板

PR 描述中增加（无 MCP 变更可写「无」）：

```markdown
## MCP 使用披露
- Servers: [id 列表]
- 新增减: [无 / 新增 xxx]
- 数据敏感级别: [无 / 内部 / 客户 / 生产]
- 人工确认项: [无 / 列表]
```

## 7. 验证重点

- [ ] 新 MCP 已在项目登记表中
- [ ] 无 broad `filesystem` / `shell` 类权限扩大
- [ ] CI/评审能发现未披露的 MCP 配置变更（`.cursor/mcp.json`、`.mcp.json` 等）
- [ ] Agent evals（若启用）覆盖工具误用类用例

## 8. 与验证政策的关系

MCP 相关回归与红队用例纳入 `agent_evals`（见 `templates/agent-evals-manifest-template.yaml`）。证据优先级不低于人工「我觉得没问题」。

## 9. 危险命令资源护栏

> 字段实战教训：子 Agent 在容器内执行 `masscan -p1-65535 --rate=5000`、`dnsrecon -t brt` 等高强度命令，
> 占满宿主机网络/协议栈资源，导致**同机的 LLM 推理调用超时 → flow 失败**。工具「能不能调」之外，
> 还必须管「调用强度会不会拖垮共驻服务」。

- **速率与并发上限**：高强度扫描/枚举/压测/递归爬取类命令必须声明并遵守速率与并发上限
  （如 `masscan --rate` 限值、输出走文件而非无界 stdout）。
- **资源隔离**：这类命令与共驻的 LLM 推理、数据库、宿主关键服务**资源隔离**
  （独立 cgroup / 容器资源限额 / 独立网络命名空间），不得与推理链路争抢同一资源池。
- **提示词内建约束**：子 Agent 的系统提示词必须内建上述限制，不允许「为拿结果」放开速率。
- **与长任务护栏联动**：执行强度与资源阈值的完整规约见 `domains/operations/long-running-task/`（`ops.long-running-task.r4`）；
  渗透场景的额外约束见 `domains/pentest-and-vulnerability-research.md`。

## 10. 跨 agent 运行时兼容与确定性生命周期闸

> 背景：治理入口（`AGENTS.md` / `CLAUDE.md`）与规则是「软约束」——模型可以忽略。字段实战与本框架
> 自身都承认「无外部硬闸时无法物理 100% 拦截跑偏的 agent」。本节把两件事补齐：让**不同 agent 都能发现
> 治理技能**，并给出**模型无法忽略的确定性闸**。

### 10.1 技能的跨工具发现（`tool.r5`）

- Cursor 兼容加载 `.claude/skills/`；OpenAI Codex（2025-12 起 skills 化）只发现 `.agents/skills/`（repo）
  与 `~/.agents/skills/`（global）。二者同遵 Agent Skills 开放标准。
- 因此 `.claude/skills` 必须镜像到 `.agents/skills`：`python scripts/sync-agent-skills.py --prune`
  确定性生成薄入口（frontmatter name/description + 指回 canonical 源），并登记进 `generated_artifacts`
  （`ops.housekeeping.r10`）。改源后重跑，勿手改镜像。

### 10.2 Cursor hooks 确定性闸（`tool.r6`，should）

- Cursor hooks（`.cursor/hooks.json` + `.cursor/hooks/`）是**模型无法忽略**的生命周期脚本，用来把治理
  硬约束落成物理闸。母版提供两个零依赖（纯 Python、不依赖 jq）模板：
  - `beforeShellExecution` → `guard_dangerous_command.py`：拦截不可逆破坏（deny）与高强度/敏感命令（ask），
    落实 §9 的强度护栏。
  - `stop` → `checkpoint_consistency.py`：收尾时跑 `check_progress_consistency.py`，未过则回注 followup，
    落实 `05-ai-collaboration-policy.md` §6 完成判定 / §7.3 检查点协议。
- 模板在 `templates/cursor-hooks/`（进版本库、团队共享）；安装用 `python scripts/install_cursor_hooks.py`
  （按当前解释器改写命令前缀）。`.cursor/` 默认被 `.gitignore` 忽略 → hooks 是**每次克隆本地装一次的本地闸**，
  **不替代** CI 双闸与同步台账（见 `tooling/progress-binding` §2）。
- 其它运行时（Codex `config.toml` 角色/MCP、Copilot `.agent.md`）按需接入，但治理主干始终以 `AGENTS.md`
  + 零依赖自检为准，保证便携性。
