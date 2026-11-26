# 原生优先的 CLI 兼容协议（候选）

本协议处理 Codex、Cursor、Claude Code 等会话恢复能力与外挂 RSI 索引的边界。CLI 自己管理 session、压缩、历史搜索、权限与交互；governance 管项目规则、可验证工件、派生摘要和定位。不同版本与部署形态的功能可能变化，接入时用本机能力核对，未知功能按不可用处理。

## 权威与调用顺序

1. 同一会话继续：先使用当前 CLI 的原生上下文、resume 和压缩结果。不要因为普通“继续”、自动压缩或上下文指标变化而启动外部恢复，也不要改写、重放或替换 CLI 内部压缩状态。
2. 需要查漏：先用 CLI 自带的本会话搜索、历史定位或回溯；只按确切疑点取必要片段。找不到来源时，再检索 governance/rsi 的派生索引，得到原生 session ID、机器和定位器，再由原 CLI 打开原文。
3. 跨会话或跨机器：RSI 索引用来发现来源；如果原生 session 在目标机器不可达，明确标记“原文不可核实”。由项目 Git 中的代码、Story、Change、测试证据和经核实的事实清单继续工作；对关键决策有歧义时才请求人机澄清。
4. 恢复任务执行：可选读取外部检查点，但必须先比对当前 Git HEAD、工作树和引用工件。冲突时以原生会话、当前用户输入和可验证工件为准；检查点只提示“曾经计划什么”，不得自动覆盖较新的状态。
5. 涉及归档、提交或终态变更：只有明确收尾条件满足时才调用治理收尾检查点。用户说“继续”只意味着推进当前目标，不代表归档授权。

## 能力矩阵（接入时核对，不假设所有安装一致）

| CLI | 原生优先能力 | RSI 外挂只做 | 不应做 |
|---|---|---|---|
| Codex | 当前会话状态、原生恢复、原生压缩 | 索引 session ID 与工程证据 | 解析或改写不透明压缩项；替代原生恢复 |
| Cursor | 现有 chat、原生 resume、按需 summarize/rewind；历史搜索能力以当前安装核对为准 | 跨项目导航与来源锚点 | 重复自动摘要、复制历史数据库或强迫每轮加载索引 |
| Claude Code | 原生 continue/resume、compact、项目 memory | 会话定位与工件验证 | 覆盖 compact 摘要、强迫清空或新开会话 |
| 其他 CLI | 先探测 resume/history/search/compaction 能力 | 仅使用其公开稳定入口 | 猜测私有目录结构、改写会话数据库 |

## 轻量适配要求

- 常驻入口仅声明此路由，不要求每轮读取 rsi/sessions 或完整 governance。对任务相关规则使用按需检索。
- CLI 适配器是能力声明，不是统一劫持层：native_resume、native_history_search、native_compaction、pre_compact_event、session_locator、export 的值为 supported/unsupported/unknown，并标明来源与测试日期。unknown 只能走保守路径。
- 如 CLI 提供稳定事件钩子，可在阶段边界**异步**写派生摘要；钩子缺失时用阶段完成后的显式命令。不要拦截压缩或阻塞其执行。
- 同一事实只保留一个权威位置。会话原文在 CLI，代码与验收在项目 Git，治理规则在 governance Git；RSI 条目含来源 ID 与可达性，不保存原文。
- 记录 provenance：CLI、版本、host、session ID、原生 locator、索引生成时间、原生来源校验状态。未经原文核对的摘要明确显示 unverified。
- 不能宣称对所有 CLI 完美自动适配；每个 CLI/版本必须做压缩后续跑、历史回查、跨机不可达、权限受限和重复索引五项契约测试。

## 本次核对的官方依据

- OpenAI Codex CLI 文档：codex resume 可回到已保存的本地会话；本机 codex 0.163.0 的 --help 亦显示 resume 入口。https://learn.chatgpt.com/docs/cli/reference
- OpenAI Responses API 文档：压缩项不透明，应用应按接口约定传递；这是 API 行为，不能推定为 Codex CLI 内部实现。https://developers.openai.com/api/docs/guides/compaction
- Cursor CLI 文档：提供 /resume、/summarize 和 /rewind；本机未安装 Cursor CLI，未实测其历史全文搜索。https://prod.cursor.com/docs/cli/reference/slash-commands
- Claude Code 文档：原生命令包括 /compact、/resume、/clear 与 /rewind；实际功能仍以本机版本为准。https://code.claude.com/docs/zh-CN/commands
