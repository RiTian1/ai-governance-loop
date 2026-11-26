# 项目局部规则与开发域事实 — {{PROJECT_NAME}}

> 标准位：`docs/project-rules.md`（`02-engineering-principles.md §7` 项目级 + 事实域）。
> 与 `runtime-context.yaml` 分工：那边存**执行域**事实（凭证引用/地址/端口/环境），
> 这边存**开发域**事实与项目级规则。凭证一律只写引用，禁明文。
>
> Token 纪律（`ops.runtime-context.r10`）：本文件 ≤ 300 行，按需读取、不常驻上下文；
> 超限时把过期条目移到 `docs/project-rules-archive.md` 或晋升到治理层。

## 1. 项目级规则

<!-- 仅对本仓库有效的硬规则，一条一行，写清楚判定标准。示例：
- 所有 GraphQL resolver 必须经 `src/auth/guard.ts` 鉴权装饰器，禁止裸 resolver。
-->

（暂无）

## 2. 开发域事实

### 2.1 接口与外部系统约定

<!-- 示例：
- 后端 API 基址（dev）：`http://localhost:8080/api`；契约文件 `docs/openapi.yaml`
- 上游订单系统对接走 MQ topic `order.events.v2`，schema 见 `docs/contracts/order-event.json`
-->

（暂无）

### 2.2 构建 / 测试口径

<!-- 示例：
- 单测：`pnpm test`；E2E：`pnpm e2e`（需先 `docker compose up -d`，见 runtime-context loop ci-e2e）
- 测试数据库用 `test_` 前缀 schema，禁止连生产库
-->

（暂无）

### 2.3 已回答的使用者决策（防重复询问）

<!-- 使用者在会话中拍板过的决策，记录结论与日期，agent 问前必查。示例：
- 2026-07-20 部署目标只有 staging 与 customer 两套，没有独立 QA 环境
-->

（暂无）

## 3. 变更纪律

- 新增/修改条目须在当轮会话完成（答后落账，`ops.runtime-context.r9`）。
- 条目升级为跨项目规则时，走 `{{GOVERNANCE_ROOT}}/revisions/` 晋升，本文件留一行指针。
