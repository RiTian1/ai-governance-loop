# 验证政策

本文档定义当前仓库在验证阶段应遵循的证据、口径与准入规则。

## 1. 验证目标

验证不仅证明“能编译”，还要证明：

- 规则或运行时行为符合预期
- 结构边界没有被意外破坏
- 证据可追踪、可复核、可交付

## 2. 默认验证维度

- 编译或构建完整性
- 规则语义与运行时行为
- 跨集成兼容性
- 自动化回归与人工验证证据
- 打包、制品、发布与回滚可执行性
- 安全与审计边界

## 3. 证据优先级

1. 结构化自动化输出
2. 可复现的构建或测试日志
3. 人工验证的结构化记录
4. 临时日志或截图
5. 口头描述

## 4. 降级验证

出现以下情况时，只能判定为降级验证：

- 无法在当前环境运行目标构建或关键回归
- 只验证了局部模块，未覆盖受影响集成面
- 缺少结构化证据，只能给出人工结论
- 涉及制品或发布路径，但未验证回滚或兼容性

## 5. 仓库级最小要求

- 涉及 [核心模块] 规则与行为语义的改动，应至少说明受影响测试或回归路径
- 涉及 [第三方依赖] 的改动，应至少说明是否影响第三方基线偏移
- 涉及构建、安装、打包的改动，应至少说明制品影响与回滚路径
- 交付时必须说明已验证项、未验证项和降级原因

### 5.1 进度闭环自检 = 完成判定（硬门，fail-closed）

> 验证不仅针对代码，也针对**治理工件自身的进度一致性**。这是便携闭环治理的硬完成判定。

- 涉及 BMAD Story / OpenSpec change / Revision / Rule / PRD-FR 的任何创建 / 修改 / 状态变更，
  收尾前 MUST 跑 `python scripts/check_progress_consistency.py`（零依赖、git-optional，随处可跑）。
- **完成判定**：`check_progress_consistency.py` 返回 **exit 0**（或所有 drift 已登记合法豁免）才算"验证通过"；
  **未过自检 = 未完成 = 不许收尾**（不许 commit、不许标 `done`/`completed`、不许 `archived`/`merged`、不许写 `active_sprint`）。
- 状态字段（`completed`/`archived`/`active_sprint`/`status=merged`）是**最后一步**，必须在自检通过之后、且与其它工件联动后才写入。
- 降级豁免：确有合法理由时，须在交付说明里显式登记豁免项与原因（等同 §4 降级验证的记录要求），不得静默跳过。

## 6. Agent 评估门禁（Eval CI）

当 `project-governance.yaml` 启用 `agent_evals` 时，PR 合并前除常规测试外还须满足：

| 门禁类型 | 说明 | 默认阈值 |
|----------|------|----------|
| 通过率门 | 代表性 Agent 任务集 eval | `min_pass_rate: 0.85` |
| 严格门 | 预发布 / release 分支 | `min_pass_rate_strict: 0.92`（可选） |
| 红队门 | 注入、越权、秘密泄露探针 | `red_team.enabled` 时必跑 |
| 成本门 | 单任务 token 增幅 | 超 `cost_gate.max_token_delta_percent` 需人工批准 |

### 6.1 证据格式

- 优先提交 `evals/output/latest.json`（或 CI artifact）
- qa-verifier 输出须引用 eval 报告路径与通过率，不得仅写「已手动试过」

### 6.2 落地文件

- 配置模板：`templates/agent-evals-manifest-template.yaml`
- Promptfoo 示例：`templates/promptfoo/promptfooconfig.yaml.example`
- CI 示例：`templates/github-workflows/agent-evals.yml.example`
- 校验脚本：`scripts/check-agent-evals.py`

### 6.3 与 MCP 的关系

涉及 MCP 的变更须跑 `mcp-safety` 套件（见 `domains/agent-tooling-mcp.md`）。

### 6.4 规则晋升的评测要求（`tool.revisions.r6`）

本节与 §6 的 Eval CI **分工不同**，不要混用：

| | 管什么 | 何时跑 | 判据 |
|---|---|---|---|
| §6 Eval CI | **代码/Agent 行为**有没有退化 | PR 合并前 | 通过率、红队、成本门 |
| §6.4 规则评测 | **治理规则本身**有没有用 | revision `candidate → benchmarked` | 效应量 + 方向一致数 / 回归 / waiver |

**为什么需要这一层**：规则从 candidate 到 merged 若只有"我按流程做了"，
没有"做了之后结果变好"，基线的质量只能靠评审者的直觉。2026-11-19 的 RSI 真实工作基准
给出过反例——五条被广泛相信的治理假设（更快、更省、追溯率普适提升、减少空话、全面更优），
在同一批数据上四条被推翻。

**最小证据格式**（三选一，详见 `revisions/WORKFLOW.md §4.1`）：

```yaml
benchmark:
  mode: paired_comparison          # paired_comparison | regression | waiver
  n: 10                             # 配对样本量
  metric: citation_rate             # 被评测的指标
  effect: {baseline: 0.602, governance: 0.917, delta_pct: +52.2}
  test: {type: paired_t, value: 2.11, df: 9}
  direction_consistency: 4/7        # 方向一致数，必填
  notes: "<被测任务/材料/模型，确保可复现>"
```

```yaml
benchmark:
  mode: regression
  test: tests/test_gate.py::test_blocks_unsafe_write
  before: failed
  after: passed
  command: pytest -q tests/test_gate.py -k unsafe_write
```

```yaml
benchmark:
  mode: waiver
  reason: "<为什么无法评测>"
  approved_by: "<handle>"
  approved_at: 2026-11-19
```

**硬约束**：

1. **`direction_consistency` 必填**。只报均值差会掩盖"同一效应在部分轮次反向"的事实。
2. **`n ≤ 6` 的显著性不作为充分证据**，除非说明该指标方差天然极小并给出理由。
3. **评测必须用 fresh context**：不得复用规则作者的会话上下文（`revisions/WORKFLOW.md §4.2`）。
4. **`waiver` 连续使用两条以上**，须在下次治理回顾中说明原因。

## 7. 长任务与资源门（执行期护栏）

> 验证不仅针对「结果对不对」，也针对「执行过程会不会失控」。字段实战证明：不设执行期护栏时，
> 长任务被反复人为中断、E2E 打满宿主机、扫描命令拖垮共驻 LLM——这些都是可预防的验证缺口。
> 完整约束见 `domains/operations/long-running-task/`。

- **重型闭环执行前必须过预检**：部署 / 镜像 load / 大批量 E2E / flow 跑批等，执行前跑
  `python scripts/preflight_check.py --loop <id>`（校验磁盘/内存/网络/env/工具），退出非 0 即阻断，
  不许「先跑起来再说」（`ops.long-running-task.r2`）。
- **批量/并行验证并行度受资源约束**：E2E 与批量任务并行度默认 **≤ 可用资源 70%**，禁止无脑全并行；
  并行度默认值须显式声明且可覆盖（`ops.long-running-task.r3`）。这是「E2E 打满 CPU 致宿主无响应」的直接对策。
- **长任务后台化 + 可续跑**：预计 > 阈值（默认 10min）的验证任务后台执行并输出结构化进度，
  被中断须幂等重入或 checkpoint 续跑，不得留下无法续的半成品（`ops.long-running-task.r1/r5`）。
- **降级说明**：无法执行预检或护栏时，须在交付说明按 §4 记录未覆盖项与原因，不得静默跳过。
