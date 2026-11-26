# 分布式追踪标准

## 1. 追踪协议

### 1.1 推荐协议
- **OpenTelemetry**（推荐）：统一标准，支持 Trace/Metrics/Logs
- **Jaeger**：CNCF 项目，成熟稳定
- **Zipkin**：Twitter 开源，广泛支持

### 1.2 协议选择原则
- 新项目优先选择 OpenTelemetry
- 已有项目可继续使用 Jaeger/Zipkin，但应规划迁移
- 跨团队/跨系统应统一追踪协议

## 2. Trace 与 Span 结构

### 2.1 Trace ID
- 全局唯一标识一次完整请求链路
- 格式：128-bit 或 64-bit 十六进制字符串
- 应在请求入口生成，并在整个调用链中传播
- HTTP 请求应通过 Header 传播：`traceparent` (W3C Trace Context)

### 2.2 Span 结构
每个 Span 应包含：
```json
{
  "trace_id": "abc123def456",
  "span_id": "789ghi",
  "parent_span_id": "456jkl",
  "name": "POST /api/orders",
  "kind": "SERVER",
  "start_time": "2025-01-15T10:30:00.123Z",
  "end_time": "2025-01-15T10:30:00.456Z",
  "status": "OK",
  "attributes": {
    "http.method": "POST",
    "http.url": "/api/orders",
    "http.status_code": 200,
    "user.id": "u-12345"
  },
  "events": [
    {
      "name": "db.query",
      "timestamp": "2025-01-15T10:30:00.200Z",
      "attributes": {"query": "INSERT INTO orders..."}
    }
  ]
}
```

### 2.3 Span 命名规范
- 格式：`[操作类型] [资源]`
- HTTP 请求：`GET /api/users/:id`
- 数据库查询：`SELECT users`
- 消息队列：`SEND orders.created`
- RPC 调用：`UserService.GetUser`

## 3. Span 类型（Kind）

| Kind | 说明 | 示例 |
|------|------|------|
| SERVER | 服务端处理请求 | HTTP 服务器接收请求 |
| CLIENT | 客户端发起请求 | HTTP 客户端调用外部 API |
| PRODUCER | 消息生产者 | 发送消息到 Kafka |
| CONSUMER | 消息消费者 | 从 Kafka 消费消息 |
| INTERNAL | 内部操作 | 业务逻辑处理 |

## 4. 上下文传播

### 4.1 HTTP 传播
- 使用 W3C Trace Context 标准：
  - `traceparent: 00-abc123def456-789ghi-01`
  - `tracestate: vendor1=value1,vendor2=value2`
- 兼容旧标准：`X-B3-TraceId`, `X-B3-SpanId`（Zipkin）

### 4.2 消息队列传播
- 将 Trace Context 注入消息 Header/Metadata
- Kafka：使用 Record Headers
- RabbitMQ：使用 Message Properties
- 消费者应从 Header 中提取并继续传播

### 4.3 异步任务传播
- 任务入队时注入 Trace Context
- 任务执行时恢复 Trace Context
- 使用 Baggage 传递业务上下文（如 user_id）

## 5. 采样策略

### 5.1 采样类型
- **全量采样**：开发/测试环境，100% 采样
- **固定比例采样**：生产环境，1%-10% 采样
- **自适应采样**：根据流量动态调整采样率
- **尾部采样**：仅保留错误或慢请求的 Trace

### 5.2 采样决策
- 采样决策应在 Trace 入口做出
- 采样标志应在整个链路中传播
- 错误请求应强制采样（100%）
- 慢请求（超过 P99）应强制采样

## 6. Span 属性（Attributes）

### 6.1 标准属性（OpenTelemetry Semantic Conventions）
- HTTP：`http.method`, `http.url`, `http.status_code`, `http.user_agent`
- 数据库：`db.system`, `db.name`, `db.statement`, `db.operation`
- RPC：`rpc.system`, `rpc.service`, `rpc.method`
- 消息队列：`messaging.system`, `messaging.destination`, `messaging.operation`

### 6.2 自定义属性
- 业务上下文：`user.id`, `order.id`, `tenant.id`
- 环境信息：`deployment.environment`, `service.version`
- 禁止在属性中存储敏感信息（密码、密钥）

## 7. 验证重点

- 是否使用统一的追踪协议（OpenTelemetry 推荐）
- Trace ID 是否在整个调用链中传播
- Span 命名是否符合规范
- 是否配置了合理的采样策略
- 错误和慢请求是否强制采样
- 是否使用标准属性（Semantic Conventions）
