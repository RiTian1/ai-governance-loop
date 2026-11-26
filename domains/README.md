# 领域约束索引

本目录包含项目适用的领域约束文档。由 `profiles/` 中的项目 profile 激活对应的域子集。

## 加载规则

1. **单文件域**：直接加载 `.md` 文件（v1 兼容）
2. **目录型域（L1/L2 树化）**：必备三件套 `index.md` + `_summary.yaml` + `_index.yaml`，按 token budget 装载（详见 `02-engineering-principles.md §11` 与 `foundations/self-governance-and-knowledge-evolution.md`）
3. **优先级**：域约束优先于代理规则（详见 `CLAUDE.md` 权威优先级规则）

## 三件套协议（强制）

L1 域根 与 有子节点的 L2：

| 文件 | 用途 |
|------|------|
| `index.md` | 域门面（人 + LLM 读，≤ 200 行） |
| `_summary.yaml` | 规则要点（机器读，含 rule_id `<domain-flat>.r<n>`） |
| `_index.yaml` | 子节点路由（含 triggers / size_tokens） |

模板：`templates/domain-l1-index-template.yaml`、`templates/domain-summary-template.yaml`。

完整 token 预算与稀疏装载机制由 `scripts/context_loader.py` 实现；健康自检由 `scripts/check_knowledge_health.py` 强制执行。

---

## 目录型域（树级索引）

复杂度较高的域使用目录结构，每个子文件覆盖该域的一个细分维度。

| 域 | 子文件数 | 覆盖范围 |
|----|---------|---------|
| [`documentation-and-api/`](documentation-and-api/index.md) | 7 | 文档写作规范、Markdown、图表(drawio/mermaid)、脑图、表格(Excel/CSV)、API 契约、变更日志 |
| [`security/`](security/index.md) | 6 | 安全原则、认证鉴权、输入校验、密钥管理、依赖安全、安全测试 |
| [`backend/`](backend/index.md) | 5 | 服务设计、API 设计、错误处理、缓存策略、异步模式 |
| [`devops-ci/`](devops-ci/index.md) | 5 | 构建发布、流水线门禁、环境策略、部署模式、IaC |
| [`automation/`](automation/index.md) | 5 | 测试自动化、测试金字塔、测试数据、Flaky 测试、测试证据 |
| [`configuration/`](configuration/index.md) | 5 | 配置文件格式、配置分层、特性开关、密钥管理、环境变量 |
| [`observability/`](observability/index.md) | 5 | 日志规范、指标与 SLO、分布式追踪、告警管理、事故响应 |
| [`architecture/`](architecture/index.md) | 5 | ADR、C4 模型、RFC 流程、技术选型、设计评审 |
| [`operations/`](operations/index.md) | 7 | Runbook、值班、容量、灾备、变更、运行时上下文（`runtime-context/`）、反堆积治理（`housekeeping/`）（**首批 L1 树化样板**） |

## 单文件域

| 域文件 | 行数 | 覆盖范围 |
|--------|------|---------|
| `agent-tooling-mcp.md` | — | MCP 连接器登记、PR 披露、工具安全与 OAuth 边界 |
| `coding-standards.md` | 32 | 命名、模块组织、注释、错误处理、代码评审、工具门禁 |
| `database.md` | 41 | Schema 迁移、索引优化、连接管理、备份恢复 |
| `frontend.md` | 44 | 组件编排、状态分层、本地化、无障碍、性能预算 |
| `infra.md` | 39 | 配置治理、IaC、网络边界、容量灾备 |
| `performance.md` | 40 | 响应性约束、SLO 指标、CI 性能门禁、容量规划 |
| `base-runtime.md` | 39 | 跨集成边界、初始化生命周期、版本兼容、跨平台一致性 |
| `data-governance-and-privacy.md` | 32 | 数据分类分级、隐私保护、生命周期治理 |
| ~~`observability.md`~~ | — | **已升级为目录型域** `observability/`，见上表 |
| `release-operations.md` | 32 | 版本发布、灰度、回滚、值班、RCA |
| `open-source-compliance.md` | 34 | 许可证审查、SBOM、供应链审计 |
| `gui.md` | 41 | 桌面 GUI 交互模型、布局、拖拽、多语言 |
| `driver-and-kernel.md` | 32 | 内核模块、用户态-内核态边界、中断/DMA/锁 |
| `hardware-and-embedded.md` | 34 | 固件/BSP、软硬件协同、量产验证 |
| `industrial-simulation.md` | 31 | 仿真模型、校准、"仿真≠现实"验证 |
| `math-modeling-and-algorithm-research.md` | 31 | 优化建模、算法研究、理论-实验-工程区分 |
| `ml-and-data-science.md` | 31 | ML 全链路可复现、模型治理、漂移监控 |
| `pentest-and-vulnerability-research.md` | 30 | 渗透测试范围/授权/PoC/披露/修复 |
| `reverse-engineering.md` | 30 | 逆向分析授权/证据链/结论分级 |

## 域与 Profile 的关系

每个 `profiles/*.md` 文件声明该项目类型激活哪些域。例如：
- `solo-developer.md` 激活：coding-standards, backend, frontend, database, security, devops-ci, automation, documentation-and-api ...
- `backend-service.md` 激活：coding-standards, backend, database, security, infra, devops-ci, observability ...

详见各 profile 文件中的域列表。

## 扩展域

### 新增单文件域
1. 在本目录创建 `[域名].md`
2. 遵循统一结构：默认原则 → 约束 → 验证重点
3. 在相关 profile 中添加引用
4. 更新本索引
5. **沉淀范围**：仅适用于该领域的规则写在本域；跨域/global 规则见 `02-engineering-principles.md` §7，不得误写入单一 domain

### 将单文件域升级为目录
1. 创建同名目录
2. 将原文件内容移至 `index.md`，添加子文件索引表
3. 创建子文件，每个覆盖一个细分维度
4. 删除原单文件
5. 更新本索引
