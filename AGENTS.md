# AGENTS.md — 治理母版仓库（路由表）

本文件遵循 [AGENTS.md](https://agents.md/) 约定：简短、可发现。完整约束见 `project-governance.yaml` 与 `00-index.yaml`，**不要**在此重复长文。

## 布局

- `governance_layout: mother-repo-root`（见 `LAYOUT.md`）
- 业务项目通常为 `docs-governance-subtree`，路径以该项目 manifest 为准

## 强制启动顺序

1. `project-governance.yaml`（含 `token_budget`、`runtime_context`）
2. `LAYOUT.md`（路径模式）
3. `00-index.yaml`（schema v2）→ 优先看 `levels.L1`；按 trigger 命中度下钻 L2/L3
4. `profiles/<profile>.md` → 再加载其列出的 foundations / domains
5. 变更实施：`openspec/changes/<change>/` + `04-verification-policy.md`

**Token 预算与稀疏装载**：默认单任务治理上下文预算 8 k tokens（详见 `02-engineering-principles.md §11`、`foundations/self-governance-and-knowledge-evolution.md`）。装载行为由 `scripts/context_loader.py` 控制：高分域装 `index.md` 全文，中分仅装 `_summary.yaml`，低分跳过。**禁止全量加载所有 domain**。

RSI：原生恢复优先；阶段边界按需存任务态。见 rsi/native-cli-compatibility.md。

## 权威优先级（冲突时）

`04-verification-policy.md` → `foundations/*` → `domains/*` → `profiles/*` → `agents/*`（governance 字段）→ 代理正文

## 默认工作流

| 场景 | 使用 |
|------|------|
| **功能迭代 / 代码变更** | **双载体（MUST，`tool.binding.r11`）**：BMAD Story（挂 PRD FR）+ OpenSpec change 双向绑定，动代码前先建载体；`/opsx:propose` → `/opsx:apply` → `/opsx:verify` → 检查点归档 |
| 探索 | `/opsx:explore` |
| 治理 / 文档 / 知识库 | Story + Revision（允许替代 change） |

命中 manifest `code_paths` 的提交强制 `Change:` 非 none（防 PRD 进度落后于实现）。

## 禁止

- 跳过 manifest / 索引，全量加载所有 `domains/` 与 `foundations/`
- 可复用规则只写聊天；按范围写入 change / `project-rules` / `domains/` / `revisions/`（见 `02-engineering-principles.md` §7）
- 验证降级不说明原因与未覆盖项
- 非 UTF-8 写文件或在 Windows 终端忽略中文乱码
- 归档与实现分两次提交、或归档后不 push 本仓 NAS GitLab `origin/main`

## 经验回写

- 仅本变更：`openspec/changes/<name>/`（每个 change 有 `proposal.md` frontmatter 含 `change_id` `linked_story` `linked_revision` `spec_delta_hash`）
- 可复用：`revisions/`（候选）→ **评测（`benchmarked`）** → 评审 → 晋升后写入 `domains/` / `foundations/` / 主文档；新建 candidate 优先用结构化目录形态（`templates/revision-structured-directory-template/`）
- **执行事实**（凭证引用/地址/端口/环境）：问使用者前先查 `runtime-context.yaml`，答后当轮写回；开发域事实写 `docs/project-rules.md`（`ops.runtime-context.r8/r9`，按需读取不常驻）

**change 工件不是基线**：`openspec/changes/<name>/` 下的 design / tasks / 测试模板属于**变更局部工件**，
MUST NOT 被当作项目级基线引用（`tool.binding.r12`）。只有抽象后经 `revisions/` 晋升到
`domains/` / `foundations/` / 主文档的内容才算基线。读到 change 里的设计时，先确认它是否已晋升。

**规则晋升要过评测门**：`candidate → benchmarked → accepted`，`benchmarked` 需给出前后对比 /
回归测试 / waiver（`tool.revisions.r6`，详见 `revisions/WORKFLOW.md §4`）。评测须用 fresh context。

## 凭据与密钥（保险箱，`tool.r14`）

凭据/私钥/证书 MUST NOT 以明文出现在任何**入库文件**（源码、配置、文档、注释、
测试 fixture、commit message）；示例值一律写 `REDACTED`。取用 MUST 走保险箱，
且每次都要写清用途——审计日志要能回答"为什么取"。

```bash
python scripts/gov_vault.py ls                                       # 看有什么（永不显示值）
python scripts/gov_vault.py put <域/用途> --type <password|private_key|certificate|token|note|bundle> --stdin
python scripts/gov_vault.py get <域/用途> --purpose "这次要做什么"      # 缺 purpose 直接拒绝
python scripts/gov_vault.py get <名称> --purpose "..." --cert-info     # 证书附 subject/有效期/指纹
python scripts/gov_vault.py audit --tail 20                          # 谁在何时为何取用
python scripts/gov_vault.py doctor                                   # 依赖/权限/轮换/多端状态自检
python scripts/gov_vault.py share                                    # 多端协同：打印入库清单
python scripts/gov_vault.py migrate                                  # v1 单文件库 → v2 多条目
```

- **跨平台**：Windows / macOS / Linux 命令完全一致，需 Python 3.8+ 与 `cryptography`。
- 口令不落盘：`GOV_VAULT_PASSPHRASE` / `--passphrase-file` / `GOV_VAULT_PASSPHRASE_CMD`，
  MUST NOT 写进仓库。接钥匙串优先用 `_CMD`（macOS `security find-generic-password`、
  Linux `pass show` / `secret-tool`）。
- **不得在对话里回显明文**；需要确认时贴指纹/长度/摘要，不贴原文。
- 临时文件用完即删，且落仓库外（本机：`<workspace>/workspace/`）。
- **多端共享库**（密文随 governance 仓走）：新机器 clone 后**直接 `ls`，不要 `init`**——
  重新 `init` 会换 salt 使旧密文全部作废。`local/` 与 `audit.log` 永不入库。
- 完整说明（多端协同、目录布局、**威胁模型"不防什么"**）：`docs/governance/VAULT.md`；
  跨平台自测：`python scripts/gov_vault_selftest.py`。

## CRUD = 同步事件（不可跳过闭环 · STOP 门）

> 这是便携治理的执行点。无外部硬闸时，LLM 在长会话里必然回到"先做事后补账"惯性，
> 导致 PRD / Story / Change / Revision 多处偏移。下列为**命令语气**的硬动作链，**不是建议**。

**任何**对 Story / OpenSpec change / Revision / Rule / PRD-FR 的创建、修改、状态变更（CRUD），
都是一次**同步事件**，MUST 按下面执行：

1. **动手前**：先产出一份"受影响工件清单"（列出本次会触碰的 Story / Change / Revision / Rule / PRD-FR），
   并确认它们的反向引用三端对齐（Story ↔ change ↔ revision）。
2. **高风险状态字段**：`completed` / `done` / `archived` / `active_sprint` / `status=merged` 为高风险字段。
   **STOP**：在 `python scripts/check_progress_consistency.py` 通过之前，**禁止写入**这些字段。
   状态字段是**最后一步**，且必须与其它工件联动（不得单端先行）。
3. **新增收敛工作**：任何新发现 / 修补 / 收敛工作，MUST 新建 story 或 change 承载；
   **禁止把新工作挂到一个已 `done`/`archived` 的 Story 上**（那会让"已完成"失真）。
4. **收尾前**：MUST 贴出 `python scripts/check_progress_consistency.py` 的**通过输出**（exit 0）作为完成证据。
   该脚本零依赖、随处可跑（无 pyyaml / 无 .git 亦可）。
5. **fail-closed**：上述任一检查失败（exit != 0）→ **不许 commit、不许标完成、不许归档**。
 先消除漂移或登记合法豁免，再收尾。
6. **检查点协议**（`tool.binding.r10`，全文见 `05-ai-collaboration-policy.md` §7.3）：用户明确要求收尾/归档/提交，
 或开启下一个新 OpenSpec 变更且当前变更已达到收尾阶段时，MUST 依次——查工作区变动并归因（`scripts/check_worktree_hygiene.py`）→
 判当前 change 可否归档 → 可归档则**询问用户是否勾选人工验证标志**、确认后归档 → 归档与代码工件
 **同一次提交** → 校验 BMAD PRD ↔ OpenSpec 双向同步 → 以 `<type>(<scope>): <中文描述>` + trailers
 提交并 push → 涉及分支管理时从 `main` 拉新分支、解冲突后 push；具备 GitLab 写入权限且项目允许时也可直接推送 `main`。跨机器入口与并发处理见 `GIT-ACCESS.md`。

> 诚实边界：不依赖 hook/CI 时无法物理 100% 拦截跑偏的 agent；本协议把漂移概率压到很低且**立刻可见**，
> 是便携治理的执行力上限。git 门禁（`scripts/install_git_hooks.py`）只是"有 .git 才加分"的附加层。

## 进度可追溯硬约束（接入 progress-binding 子域后强制）

- 任何 commit message 必须含 `Story:` 行；`Change:` `Revision:` `Rules:` 至少一行非 `none`（豁免见 `scripts/check_commit_message.py`）
- 引入新 `_summary.yaml` rule 必须在 `introduced_by` 字段写规范的 `rev-<YYYY-MM-DD>-<slug>` 格式
- 改 BMAD Story 的 acceptance criteria 必须同步更新对应 OpenSpec change 的 spec delta（`acceptance_criteria_hash` ↔ `spec_delta_hash`）
- merged 状态的 revision 必须真实存在于 `revisions/archive/<year>/`

## 关键路径（母版仓根目录）

| 用途 | 路径 |
|------|------|
| 机器索引（schema v2） | `00-index.yaml` |
| 阶段治理 | `02-phase-governance.md` |
| 工程原则（含 §11 知识层级与 token 预算） | `02-engineering-principles.md` |
| 验证政策 | `04-verification-policy.md` |
| 修订流程（升级版含 implementing） | `revisions/WORKFLOW.md` |
| 长期自治理循环 | `foundations/self-governance-and-knowledge-evolution.md` |
| **进度可追溯与跨工具绑定** | `foundations/progress-traceability-and-binding.md` |
| **Tooling L1 域**（BMAD/OpenSpec/Revisions/Binding） | `domains/tooling/` |
| 框架入口 | `CLAUDE.md` |
| 上下文 Loader | `scripts/context_loader.py` |
| 知识库健康自检 | `scripts/check_knowledge_health.py` |
| **进度一致性自检** | `scripts/check_progress_consistency.py` |
| **进度 matrix 生成** | `scripts/gen_progress_matrix.py` |
| **commit message 校验** | `scripts/check_commit_message.py` |
| **revision-commit 关联** | `scripts/link_revision_to_commits.py` |

## 工具命令

| 命令 | 用途 |
|------|------|
| `python scripts/context_loader.py --phase <p> --keywords "..." --budget 8000` | 按 token 预算装配治理上下文 |
| `python scripts/check_knowledge_health.py --all` | 知识库健康自检（占位/三件套/rule_id/size 漂移/orphan/stale） |
| `python scripts/check_progress_consistency.py --strict` | 进度一致性（BMAD ↔ OpenSpec ↔ Revisions 三向反向引用 + 状态机 + 哈希） |
| `python scripts/gen_progress_matrix.py --report _logs/progress-matrix.md` | 生成 traceability matrix |
| `python scripts/check_commit_message.py <commit-msg-path>` | commit message 协议校验（pre-commit/commit-msg hook） |
| `python scripts/link_revision_to_commits.py` | 扫 git log 自动 fill revision.commits 字段 |
| `python scripts/export-governance-rules.py` | 导出 Cursor / Copilot 规则 |
| `/governance-continue`（skill） | 仅明确收尾时检查归因、人工验证、归档、同步及提交（tool.binding.r10） |
| `python scripts/sync-agent-skills.py --prune` | 把 .claude/skills 镜像到 .agents/skills（Codex/Cursor 跨工具发现，tool.r5） |
| `python scripts/install_cursor_hooks.py` | 安装 Cursor 确定性闸（危险命令拦截 + 收尾一致性自检，tool.r6） |
| `python scripts/install_governance_gates.py --project-root <项目根>` | 统一门禁入口：装 git 门禁（无 .git 优雅降级）+ 收尾自检；接入即具备（tool.r7） |
| `python scripts/upgrade_project_gates.py --target <项目根>` | 存量项目一键补装门禁 bundle 并激活（tool.r7） |
| `python scripts/check_worktree_hygiene.py` | 工作树卫生：generated vs real churn 归因（ops.housekeeping.r10/r11） |
| `python scripts/check_context_budget.py` | 常驻上下文 token 预算闸（tool.r8，默认 6k/工具组） |
| `python scripts/check_staged_content.py --staged` | 内容闸：明文凭证+UTF-8（tool.r9；CI 用 --all） |
| `python scripts/check_declaration_fact.py` | 声明-事实一致性：规则号/路径/脚本/状态机正典与副本（`tool.r11`） |
| `python scripts/check_index_freshness.py` | 索引新鲜度：`00-index.yaml` 与实际 `domains/` 结构是否对得上（`tool.r12`） |
| `python scripts/check_capability_map.py` | 能力地图四端闭合（PRD FR ↔ Story ↔ Change ↔ Revision）+ 成熟度诚实性 + 编号唯一（`tool.r13`） |
| `powershell -File scripts/sync-upstream.ps1` | 同步 OpenSpec 1.5.0 + BMAD 6.10.0（升级后重做中文化） |
| `python scripts/sync-bmad-skills.py --prune` | （v6.7 遗留）v6.10 起技能全文在 `.claude/skills/`，配置见 `_bmad/custom/config.toml` |
| `python scripts/check-agent-evals.py` | 校验 eval 通过率门禁 |

## 新项目

GitLab: projects/NAS-GITLAB-REPOSITORIES.md

运行 `/opsx:bootstrap` 或阅读 `07-bootstrap-and-adoption-guide.md`、`docs/governance/INTEGRATION-GUIDE.md`。
