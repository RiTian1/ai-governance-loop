# 配置文件格式标准

## 1. 格式选择矩阵

| 格式 | 适用场景 | 优势 | 限制 |
|------|---------|------|------|
| YAML | 应用配置、Kubernetes manifests、CI/CD | 可读性高、支持注释、层级清晰 | 缩进敏感、大文件易出错 |
| JSON | API 配置、JSON Schema、工具链配置 | 通用性强、机器可解析、schema 验证 | 不支持注释、冗余大 |
| TOML | Rust/Go 项目配置、Cargo.toml、pyproject.toml | 简洁、表达力强、错误提示友好 | 嵌套层级深时可读性下降 |
| ENV | 环境变量注入、Docker .env | 简单、通用 | 仅支持 K=V、无层级 |
| INI | 遗留系统、简单 Section 配置 | 简单 | 类型有限、无标准化 |

## 2. 格式规范

### 2.1 YAML 规范
- 缩进必须使用 2 空格，禁止使用 Tab
- 字符串值如包含特殊字符应使用引号包裹
- 文件必须以 `---` 开头
- 注释应解释 "为什么" 而非 "是什么"
- 复杂配置应附带 JSON Schema 用于验证
- 多文档 YAML 文件应以 `---` 分隔

### 2.2 JSON 规范
- 必须使用 2 空格缩进进行格式化（不得压缩为单行）
- 应提供配套的 JSON Schema 文件用于 IDE 校验和 CI 验证
- JSON 文件名应使用 kebab-case

### 2.3 TOML 规范
- Section 使用方括号 `[section]`，嵌套使用点号 `[section.subsection]`
- 日期时间使用 RFC 3339 格式
- 数组跨行时每个元素独占一行

### 2.4 ENV 规范
- 变量名必须全大写，单词间使用下划线分隔
- 文件名使用 `.env`, `.env.example`, `.env.local`
- `.env` 文件必须在 `.gitignore` 中
- 必须提供 `.env.example` 文件列出所有变量名（不含实际值）

### 2.5 INI 规范
- Section 名使用小写 kebab-case
- 键名使用 snake_case
- 仅在维护遗留系统时使用，新项目不推荐

## 3. 配置模板要求

- 每个配置文件应有对应的模板或示例文件
- 模板文件命名约定：`[config-name].example.[ext]`
- 模板中必须包含所有配置项，并附带注释说明
- 模板中的敏感值应使用占位符（如 `<YOUR_API_KEY>`, `changeme`）

## 4. Schema 验证

- 复杂配置文件（YAML/JSON）应有配套的 JSON Schema
- CI 流水线应包含配置文件校验步骤
- IDE 应配置 Schema 关联，提供自动补全和校验

## 5. 验证重点

- 配置文件格式是否符合对应规范
- 是否提供了模板或示例文件
- 复杂配置是否有 Schema 验证
- .env 文件是否在 .gitignore 中
- 配置注释是否说明了 "为什么"
