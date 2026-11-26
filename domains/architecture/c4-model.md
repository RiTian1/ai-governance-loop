# C4 模型图表标准

## 1. C4 模型概述

C4 模型将系统架构分为四个抽象层级，从最高层概览逐步深入到代码细节：

```
Level 1: System Context — 系统与外部的关系
Level 2: Container     — 系统内的可部署单元
Level 3: Component     — 容器内的模块/组件
Level 4: Code          — 组件内的类/接口（可选）
```

## 2. Level 1: System Context Diagram

### 2.1 用途
- 展示系统与外部系统、用户的关系
- 最高层级的架构视图
- 面向所有利益相关者（包括非技术人员）

### 2.2 要素
- **系统**（System）：当前开发的系统，居中显示
- **人物**（Person）：使用系统的角色/用户类型
- **外部系统**（External System）：交互的第三方系统
- **关系**（Relationship）：箭头 + 标签说明交互内容和协议

### 2.3 规范
- 当前系统使用深色/突出色标注
- 外部系统使用灰色/浅色
- 关系线上必须标注交互协议（HTTP, gRPC, SMTP 等）
- 每张图最多 10-15 个要素
- 必须标注图表标题和创建日期

## 3. Level 2: Container Diagram

### 3.1 用途
- 展示系统内的可部署单元（容器）
- 面向技术人员
- 展示技术选型和通信方式

### 3.2 要素
- **容器**（Container）：可独立部署的单元
  - Web 应用（React SPA）
  - API 服务（Go, Python, Java）
  - 数据库（PostgreSQL, MongoDB）
  - 消息队列（Kafka, RabbitMQ）
  - 缓存（Redis）
- 每个容器应标注：名称、技术栈、简要说明

### 3.3 规范
- 容器应按逻辑分组（前端、后端、数据层、基础设施）
- 容器间关系应标注协议和数据格式（REST/JSON, gRPC/Protobuf）
- 数据存储使用圆柱形
- 外部系统仍可保留在图中作为边界

## 4. Level 3: Component Diagram

### 4.1 用途
- 展示容器内的主要组件/模块
- 面向开发团队
- 展示职责划分和依赖关系

### 4.2 要素
- **组件**（Component）：容器内的逻辑模块
  - Controller / Handler（入口层）
  - Service / UseCase（业务层）
  - Repository / DAO（数据访问层）
  - Gateway / Client（外部调用层）

### 4.3 规范
- 每张图聚焦一个容器
- 组件按分层架构排列
- 依赖方向应自上而下（入口层 → 业务层 → 数据层）
- 每张图最多 15-20 个组件

## 5. Level 4: Code Diagram（可选）

### 5.1 用途
- 展示组件内的类和接口关系
- 仅在复杂模块或核心域模型时使用
- 可使用 UML 类图

### 5.2 规范
- 仅对核心域模型或复杂算法使用
- 应自动生成（IDE 或工具），避免手动维护
- 应标注关键方法和属性

## 6. 图表工具与格式

### 6.1 推荐工具
- **Structurizr**（C4 模型首选）：DSL 定义，自动布局
- **PlantUML**：文本定义，支持 C4 扩展
- **Mermaid**：Markdown 内嵌，版本控制友好
- **drawio**：可视化编辑，支持 C4 模板

### 6.2 文件格式
- 源文件（`.dsl`, `.puml`, `.mmd`, `.drawio`）必须纳入版本控制
- 导出文件（`.svg`, `.png`）应与源文件同步
- 参考 `domains/documentation-and-api/visual-formats.md` 的图表规范

## 7. 命名与组织

### 7.1 文件命名
```
[level]-[主题]-[类型].[ext]
```
示例：
- `L1-system-context.drawio`
- `L2-container-overview.mmd`
- `L3-order-service-components.puml`

### 7.2 存储位置
```
docs/architecture/diagrams/
├── L1-system-context.drawio
├── L1-system-context.svg
├── L2-container-overview.drawio
├── L2-container-overview.svg
├── L3-order-service-components.drawio
└── L3-order-service-components.svg
```

## 8. 验证重点

- 是否至少有 Level 1 和 Level 2 图
- 图表要素是否标注名称、技术栈和交互协议
- 源文件是否纳入版本控制
- 图表是否与系统当前状态一致
- 命名是否符合约定
