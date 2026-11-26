# 环境变量命名与管理规范

## 1. 命名规范

### 1.1 通用规则
- 环境变量名必须全大写，单词间使用下划线分隔（UPPER_SNAKE_CASE）
- 禁止使用连字符（-）、点号（.）或空格
- 名称应具有描述性，避免过度缩写

### 1.2 命名结构
推荐结构：`[前缀]_[模块]_[属性]`

| 层级 | 示例 | 说明 |
|------|------|------|
| 应用前缀 | `APP_` | 应用级配置 |
| 数据库 | `DB_HOST`, `DB_PORT`, `DB_NAME` | 数据库连接 |
| 缓存 | `REDIS_HOST`, `REDIS_PORT` | 缓存配置 |
| 第三方服务 | `STRIPE_API_KEY`, `AWS_ACCESS_KEY_ID` | 外部服务 |
| 特性开关 | `FEATURE_*_ENABLED` | 见 `feature-flags.md` |
| 日志 | `LOG_LEVEL`, `LOG_FORMAT` | 日志配置 |
| 服务端口 | `PORT`, `APP_PORT` | 服务监听端口 |

### 1.3 常用约定
- `*_HOST` — 主机名或 IP 地址
- `*_PORT` — 端口号（数值）
- `*_URL` — 完整 URL
- `*_KEY` — API 密钥或标识符
- `*_SECRET` — 密钥或密码（敏感）
- `*_ENABLED` — 布尔开关（true/false, 1/0）
- `*_TIMEOUT` — 超时时间（毫秒或秒，需注明单位）
- `*_MAX_*` — 最大值限制
- `*_MIN_*` — 最小值限制

## 2. .env 文件管理

### 2.1 文件层级
```
.env.example    # 模板文件，列出所有变量名和默认值/占位符（纳入 Git）
.env            # 本地默认配置（加入 .gitignore）
.env.local      # 本地覆盖（加入 .gitignore）
.env.test       # 测试环境配置（可纳入 Git，不含敏感值）
.env.production # 生产模板（仅结构，不含实际值，可纳入 Git）
```

### 2.2 .env.example 要求
- 必须列出所有环境变量
- 每个变量必须附带注释说明用途
- 敏感变量使用占位符：`API_KEY=<your-api-key-here>`
- 非敏感变量提供合理默认值：`PORT=3000`
- 格式示例：
```
# --- 应用配置 ---
APP_NAME=myapp
APP_PORT=3000
APP_ENV=development  # development | staging | production

# --- 数据库配置 ---
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp_dev
DB_USER=<your-db-user>
DB_PASSWORD=<your-db-password>

# --- 第三方服务 ---
STRIPE_API_KEY=<your-stripe-api-key>
```

## 3. 类型约定

- 布尔值：统一使用 `true`/`false`（不使用 0/1, yes/no）
- 数值：纯数字，不含单位后缀（在注释中说明单位）
- 列表：使用逗号分隔（`ALLOWED_ORIGINS=http://localhost:3000,http://example.com`）
- 嵌套配置：使用双下划线分隔（`APP__DATABASE__HOST`），或改用配置文件

## 4. 优先级与覆盖

### 4.1 加载顺序（从低到高）
1. `.env` 文件中的值
2. `.env.local` 文件中的值
3. 系统环境变量
4. 命令行参数
5. 远程配置中心

### 4.2 覆盖原则
- 高优先级源的值覆盖低优先级源
- 应有机制打印最终生效的配置值（脱敏后）用于调试
- 禁止在代码中直接使用 `process.env.*` 或 `os.environ[*]`，应通过统一的配置加载模块

## 5. 安全要求

- 包含 `SECRET`, `KEY`, `PASSWORD`, `TOKEN` 的变量一律视为敏感变量
- 敏感变量不得出现在日志、错误消息、监控指标中
- 配置加载模块应自动识别并掩码敏感变量的日志输出
- CI/CD 中的敏感变量必须标记为 Protected/Masked

## 6. 验证重点

- 环境变量命名是否符合 UPPER_SNAKE_CASE
- .env.example 是否完整且附带注释
- .env 和 .env.local 是否在 .gitignore 中
- 敏感变量是否使用占位符
- 代码中是否通过统一模块访问环境变量
