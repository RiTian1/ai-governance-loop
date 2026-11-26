# 指标与 SLO/SLI 标准

## 1. 指标命名规范

### 1.1 命名格式
遵循 Prometheus/OpenMetrics 命名约定：
- 格式：`[命名空间]_[子系统]_[指标名]_[单位]`
- 使用 snake_case，全小写
- 单位后缀：`_seconds`, `_bytes`, `_total`, `_ratio`

### 1.2 命名示例
```
# 计数器（Counter）— 只增不减
http_requests_total{method="GET", status="200"}
order_created_total{channel="web"}
error_occurrences_total{type="timeout"}

# 直方图（Histogram）— 分布统计
http_request_duration_seconds{endpoint="/api/orders"}
db_query_duration_seconds{query_type="select"}

# 仪表盘（Gauge）— 可增可减
active_connections{service="api-gateway"}
queue_depth{queue="orders"}
memory_usage_bytes{instance="web-01"}

# 摘要（Summary）— 分位统计
http_response_size_bytes{quantile="0.99"}
```

### 1.3 标签（Labels）规范
- 标签名使用 snake_case
- 标签值应有界（cardinality），禁止使用用户 ID、请求 ID 等高基数值
- 推荐标签：`service`, `instance`, `method`, `status`, `endpoint`
- 标签数量建议不超过 7 个

## 2. 四大黄金指标

每个服务应至少覆盖以下四类指标（Google SRE 四大黄金信号）：

| 指标类型 | 说明 | 示例 |
|---------|------|------|
| 延迟（Latency） | 请求处理时间 | `http_request_duration_seconds` |
| 流量（Traffic） | 请求吞吐量 | `http_requests_total` |
| 错误（Errors） | 错误率/错误数 | `http_requests_total{status=~"5.."}` |
| 饱和度（Saturation） | 资源使用率 | `cpu_usage_ratio`, `memory_usage_bytes` |

## 3. SLO/SLI 定义

### 3.1 SLI（Service Level Indicator）
- 定义格式：`[指标名] [聚合方式] [时间窗口]`
- 示例：
  - 可用性 SLI：`成功请求数 / 总请求数`（28 天滚动窗口）
  - 延迟 SLI：`P99 请求延迟 < 500ms 的请求占比`
  - 错误率 SLI：`5xx 错误数 / 总请求数`

### 3.2 SLO（Service Level Objective）
- SLO 定义格式（YAML）：
```yaml
slos:
  - name: api-availability
    description: "API 服务可用性"
    sli: "successful_requests / total_requests"
    target: 99.9%
    window: 28d

  - name: api-latency
    description: "API 响应延迟"
    sli: "requests with latency < 500ms / total_requests"
    target: 99.0%
    window: 28d
```

### 3.3 错误预算
- SLO = 99.9% → 每 28 天允许 ~40 分钟不可用
- SLO = 99.99% → 每 28 天允许 ~4 分钟不可用
- 错误预算消耗超过 50% 应触发审查
- 错误预算耗尽应冻结新功能发布，优先修复稳定性

## 4. 指标采集

### 4.1 采集方式
- Pull 模式（Prometheus 推荐）：暴露 `/metrics` 端点
- Push 模式（适用于短生命周期任务）：通过 Pushgateway
- 自动发现：使用服务发现（K8s, Consul）自动注册采集目标

### 4.2 采集频率
- 基础设施指标：15 秒
- 应用指标：15-30 秒
- 业务指标：30-60 秒
- 长周期指标（如日报）：通过聚合计算

## 5. Dashboard 标准

### 5.1 Dashboard 层级
- L0（全局）：所有服务的关键指标概览
- L1（服务级）：单个服务的四大黄金指标
- L2（细节级）：特定功能模块的详细指标
- L3（调试级）：排查问题时的深度指标

### 5.2 Dashboard 命名
- 格式：`[层级]-[服务/系统]-[主题]`
- 示例：`L1-order-service-overview`, `L2-payment-latency`

## 6. 验证重点

- 指标命名是否符合 Prometheus/OpenMetrics 规范
- 是否覆盖四大黄金指标
- 是否定义了 SLO/SLI 及错误预算
- 标签基数是否可控
- Dashboard 是否分层组织
