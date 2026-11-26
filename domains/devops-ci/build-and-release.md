# 构建与发布标准

## 1. 构建可复现性

- 构建环境必须容器化或使用声明式构建工具（Dockerfile, Nix, Bazel）。
- 依赖版本必须锁定（package-lock.json, Cargo.lock, go.sum, requirements.txt）。
- 构建脚本必须幂等：多次执行产出相同结果。
- 禁止在构建过程中依赖外部不稳定资源（latest 标签、未固定版本的依赖）。

## 2. 制品命名与版本管理

- 制品命名格式：`[项目名]-[版本号]-[平台]-[架构].[扩展名]`
  - 示例：`myapp-1.2.3-linux-amd64.tar.gz`
- 版本号必须遵循语义化版本（SemVer）：MAJOR.MINOR.PATCH
- 每个制品必须附带元数据文件（JSON/YAML），包含：
  - 源码 commit hash
  - 构建时间（ISO 8601 格式）
  - 构建环境信息（OS, 编译器版本）
  - 依赖清单（SBOM）

## 3. SBOM（软件物料清单）

- 每次构建必须生成 SBOM，格式为 SPDX 或 CycloneDX。
- SBOM 必须包含所有直接和传递依赖的名称、版本、许可证。
- SBOM 应与制品一同发布到制品仓库。
- CI 流水线应自动扫描 SBOM 中的已知漏洞（CVE）。

## 4. 制品仓库管理

- 本 NAS 的文件制品存储落点与版本/形态/升级包/完整包结构见 [NAS 物料布局](../../infrastructure/nas-materials-layout.md)。文件目录承担归档和交付，不替代项目 Git 真源、发布记录与质量门禁。

- 制品应存储在专用制品仓库（Artifactory, Harbor, AWS ECR）。
- 制品仓库应按环境分层：dev, staging, prod。
- 生产制品不得删除，应设置保留策略（如保留最近 10 个版本）。
- 制品应签名验证（GPG, Cosign），确保完整性和来源可信。

## 5. 发布流程

- 发布必须基于已构建的制品，禁止在发布时重新构建。
- 发布前必须通过所有质量门禁（见 `pipeline-gates.md`）。
- 发布应生成 Release Notes，关联 CHANGELOG.md 和相关 Issue/PR。
- 发布应打 Git Tag，Tag 名称与版本号一致。

## 6. 验证重点

- 构建环境是否容器化或声明式
- 依赖版本是否锁定
- 制品命名是否符合规范
- 是否生成 SBOM 并扫描漏洞
- 制品是否签名验证
- 发布是否基于已构建制品而非重新构建
