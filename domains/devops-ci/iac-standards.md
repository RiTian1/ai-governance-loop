# 基础设施即代码（IaC）标准

## 1. IaC 工具选择

### 1.1 推荐工具
- **Terraform**：跨云平台资源管理
- **Pulumi**：使用通用编程语言定义基础设施
- **CloudFormation**：AWS 原生 IaC
- **Bicep**：Azure 原生 IaC
- **Ansible**：配置管理和应用部署
- **Kubernetes Manifests/Helm**：容器编排

### 1.2 工具选择原则
- 优先选择声明式工具（Terraform, CloudFormation）而非命令式工具
- 跨云场景优先选择 Terraform 或 Pulumi
- 单云场景可选择云原生工具（CloudFormation, Bicep）
- 配置管理优先选择 Ansible 或 Kubernetes ConfigMaps

## 2. 代码组织结构

### 2.1 目录结构
```
infrastructure/
├── modules/           # 可复用模块
│   ├── vpc/
│   ├── database/
│   └── compute/
├── environments/      # 环境特定配置
│   ├── dev/
│   ├── staging/
│   └── prod/
├── global/            # 全局资源（如 IAM, DNS）
└── scripts/           # 辅助脚本
```

### 2.2 模块化原则
- 每个模块应职责单一（如 VPC 模块只管理网络）
- 模块应可复用，通过参数化支持不同环境
- 模块应有清晰的输入（variables）和输出（outputs）
- 模块应有 README 说明用途和使用方法

### 2.3 环境隔离
- 不同环境应使用独立的状态文件（Terraform State）
- 不同环境应使用独立的云账号或项目（推荐）
- 环境差异应通过变量文件（tfvars, parameters）配置

## 3. 状态管理

### 3.1 远程状态存储
- 状态文件必须存储在远程后端（S3, Azure Blob, GCS, Terraform Cloud）
- 禁止将状态文件提交到版本控制系统
- 状态文件应启用版本控制和加密
- 状态文件应配置访问控制，仅授权人员可访问

### 3.2 状态锁定
- 必须启用状态锁定（DynamoDB, Azure Blob Lease, GCS）
- 防止并发修改导致状态不一致
- 锁定超时应合理配置（如 10 分钟）

### 3.3 状态备份
- 状态文件应定期备份
- 备份应保留至少 30 天
- 应定期演练状态恢复流程

## 4. 代码质量

### 4.1 代码审查
- 所有 IaC 变更必须经过 Code Review
- 应使用 IaC 扫描工具（Checkov, tfsec, Terrascan）检测安全问题
- 应使用 Linter（terraform fmt, tflint）保持代码风格一致

### 4.2 测试
- 应编写 IaC 单元测试（Terratest, Pulumi Test）
- 应在非生产环境验证变更
- 应使用 `terraform plan` 或等效命令预览变更

### 4.3 文档
- 每个模块应有 README 说明：
  - 用途和功能
  - 输入变量说明
  - 输出值说明
  - 使用示例
- 复杂模块应有架构图

## 5. 安全最佳实践

### 5.1 密钥管理
- 禁止在 IaC 代码中硬编码密钥、密码、API Token
- 应使用密钥管理服务（AWS Secrets Manager, Azure Key Vault, HashiCorp Vault）
- 应使用环境变量或 CI/CD 密钥注入机制

### 5.2 最小权限原则
- IaC 执行账号应遵循最小权限原则
- 应为不同环境配置不同的执行权限
- 应定期审计 IaC 执行账号的权限

### 5.3 合规性
- 应使用 Policy as Code 工具（OPA, Sentinel）强制合规策略
- 应扫描 IaC 代码中的合规问题（如公开 S3 桶、未加密数据库）
- 应记录所有 IaC 变更的审计日志

## 6. CI/CD 集成

### 6.1 自动化流程
- IaC 变更应通过 CI/CD 流水线执行
- 流水线应包含：
  - 代码格式检查（terraform fmt -check）
  - 静态分析（tfsec, Checkov）
  - Plan 预览（terraform plan）
  - 人工审批（生产环境）
  - Apply 执行（terraform apply）

### 6.2 变更可追溯
- 每次 IaC 变更应关联 Git Commit 和 PR
- 应记录变更执行人、时间、变更内容
- 应保留 Plan 输出日志

## 7. 验证重点

- IaC 代码是否模块化且可复用
- 状态文件是否存储在远程后端并启用锁定
- 是否启用了 IaC 安全扫描
- 是否禁止硬编码密钥
- IaC 变更是否通过 CI/CD 流水线执行
- 是否有 Plan 预览和人工审批机制
