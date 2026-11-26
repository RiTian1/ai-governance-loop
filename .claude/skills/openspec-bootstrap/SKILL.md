---
name: openspec-bootstrap
description: 智能项目分析与治理框架采用。扫描项目代码结构、分析技术栈、推荐 profile 和 domains 组合、生成 project-governance.yaml 和 AGENTS.md。支持 0→1 新项目和 1→2 已有项目。
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: governance-framework
  version: "1.1"
  generatedBy: "governance-overlay"
  openspecCli: "1.5.0"
---

智能分析当前项目，推荐治理配置，生成项目激活文件。

**IMPORTANT**: 这是一个分析和配置技能，不是实现技能。你可以读取文件、搜索代码、分析结构，但只生成治理配置文件，不修改项目代码。

---

## 步骤 1: 判断项目状态

检查项目根目录：

```bash
ls -la project-governance.yaml AGENTS.md 2>/dev/null
```

- 如果 `project-governance.yaml` 已存在 → 提示用户已初始化，询问是否要重新分析
- 如果不存在 → 继续

**判断 greenfield vs brownfield：**

```bash
# 检查是否有实质性代码
find . -maxdepth 3 -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.go" -o -name "*.rs" -o -name "*.java" -o -name "*.c" -o -name "*.cpp" -o -name "*.rb" -o -name "*.php" -o -name "*.swift" -o -name "*.kt" \) 2>/dev/null | head -20
```

- 如果找到源码文件 → **brownfield**（已有项目）
- 如果没有或极少 → **greenfield**（新项目）

向用户确认判断结果。

---

## 步骤 2: 扫描项目结构

并行执行以下扫描：

**2a. 技术栈探测**

```bash
# 包管理器和语言
ls package.json Cargo.toml go.mod pyproject.toml setup.py pom.xml build.gradle Gemfile composer.json Podfile *.sln *.csproj CMakeLists.txt Makefile 2>/dev/null

# 框架配置
ls next.config.* nuxt.config.* vite.config.* webpack.config.* tsconfig.json angular.json vue.config.* .eslintrc* tailwind.config.* 2>/dev/null

# 基础设施
ls Dockerfile docker-compose.yml terraform/ k8s/ .github/workflows/ .gitlab-ci.yml Jenkinsfile serverless.yml 2>/dev/null

# ML/AI
ls requirements.txt *.ipynb model/ models/ training/ datasets/ .env 2>/dev/null
```

**2b. 目录结构分析**

```bash
# 顶层结构
ls -la

# 关键目录
ls src/ lib/ app/ pages/ components/ api/ server/ client/ public/ static/ tests/ test/ spec/ docs/ 2>/dev/null
```

**2c. 已有文档扫描（brownfield 专用）**

```bash
# 已有规范文档
find . -maxdepth 3 -name "*.md" -path "*/docs/*" 2>/dev/null | head -30
ls README.md CONTRIBUTING.md CHANGELOG.md ARCHITECTURE.md docs/ 2>/dev/null

# 已有 AI 配置
ls .cursorrules .cursor/rules/ CLAUDE.md .claude/ .cursor/ .codex/ .opencode/ .qwen/ .trae/ .agents/skills/ .aider* 2>/dev/null
```

**2d. IDE 接入状态（只读）**

本技能**不**运行 `openspec init`。若项目尚无 OpenSpec 工具目录，在总结中建议用户执行：

```bash
# 从母版复制后（推荐）
./scripts/bootstrap.sh . --tools claude,cursor,codex,opencode,qwen,trae

# 或仅补装 IDE 适配器
./scripts/bootstrap-ide-tools.sh . --tools all
```

| 用户环境 | 建议在 `ai_ide_tools.tools` 中记录 |
|----------|-----------------------------------|
| Cursor | `cursor` |
| Claude Code | `claude` |
| Codex CLI | `codex` |
| OpenCode | `opencode` |
| Qwen Code | `qwen` |
| Trae | `trae` |

---

## 步骤 3: 推荐 Profile

根据扫描结果，使用以下决策矩阵推荐 profile：

### 决策矩阵

| 信号 | 推荐 Profile | 置信度 |
|------|-------------|--------|
| package.json + React/Vue/Next/Nuxt + 前端目录 | `solo-developer`（Web 全栈） | 高 |
| package.json + Express/Fastify/NestJS（无前端框架） | `backend-service` | 高 |
| go.mod / Cargo.toml + server/api 目录 | `backend-service` | 高 |
| pyproject.toml + model/ 或 *.ipynb | `ml-system` | 高 |
| CMakeLists.txt / Makefile + 嵌入式关键词 | `embedded-system` | 中 |
| Electron / Tauri / Qt / SwiftUI（桌面） | `desktop-application` | 高 |
| 安全工具 / 漏洞研究 / 渗透测试 | `security-research` | 中 |
| 原生运行时 + 安全策略引擎 | `native-security-runtime` | 中 |
| 混合/不确定 | `solo-developer` | 低 |

### 输出格式

向用户展示分析结果：

```
📊 项目分析结果

技术栈检测：
  语言: TypeScript, Python
  框架: Next.js, FastAPI
  基础设施: Docker, GitHub Actions
  测试: Jest, Pytest

推荐 Profile: solo-developer（Web 全栈模式）
置信度: 高

推荐加载的 foundations:
  ✓ architecture-and-design-craftsmanship（架构与设计工匠精神）
  ✓ failure-and-reliability-thinking（失败与可靠性思维）
  ✓ discrete-math-and-structural-thinking（离散数学与结构思维）

推荐加载的 domains:
  ✓ coding-standards（编码标准）
  ✓ backend（后端）
  ✓ frontend（前端）
  ✓ devops-ci（DevOps/CI）
  ✓ automation（自动化）
  ✓ documentation-and-api（文档与 API）
  + database（数据库）  ← 检测到数据库配置
  + security（安全）    ← 检测到认证模块

推荐代理:
  core/: 全部 6 个
  specialists/: backend-architect, frontend-developer, devops-automator
```

使用 **AskUserQuestion** 让用户确认或调整推荐。

---

## 步骤 4: 生成 project-governance.yaml

根据确认后的配置生成文件：

### Greenfield 模式

```yaml
# 项目治理配置
# 由 /opsx:bootstrap 智能生成于 [日期]

project:
  name: "[从 package.json/go.mod 等读取，或询问用户]"
  description: "[询问用户]"
  profile: [推荐的 profile]
  mode: greenfield

governance_layout: mother-repo-root
governance_root: .
governance:
  profile: "profiles/[profile].md"

activated:
  foundations:
    - [推荐的 foundation 列表]
  domains:
    - [推荐的 domain 列表]

frameworks:
  openspec:
    enabled: true
    default: true
    schema: spec-driven
  bmad:
    enabled: false
    note: 全新产品/MVP 需要完整 PRD 流程时再设为 true
  superpowers:
    enabled: false

agents:
  core: [全部核心代理]
  specialists: [根据项目类型推荐]
  design: [如有前端/UI 则推荐]
  meta: []
```

### Brownfield 模式（关键差异）

增加 `authority_map` 和 `migration` 字段：

```yaml
project:
  name: "[项目名]"
  profile: [推荐的 profile]
  mode: brownfield

governance_layout: docs-governance-subtree
governance_root: docs/governance
governance:
  profile: "profiles/[profile].md"

authority_map:
  # === 由新治理框架管辖 ===
  coding_standards:
    authority: governance
    path: docs/governance/domains/coding-standards.md
  verification:
    authority: governance
    path: docs/governance/04-verification-policy.md

  # === 仍由已有文档管辖（待迁移）===
  # [扫描到的已有文档会列在这里]
  # api_documentation:
  #   authority: legacy
  #   path: docs/api-spec.md
  #   migration_plan: "阶段 2 提升到 domains/documentation-and-api.md"
  # deployment:
  #   authority: legacy
  #   path: docs/deploy-guide.md
  #   migration_plan: "阶段 2 提升到 domains/devops-ci.md"

migration:
  stage: 1  # index-only
  started: "[日期]"
  notes: |
    第一阶段：仅建索引
    - 已有文档保持不动
    - 通过 authority_map 声明管辖范围
    - AI 代理必须同时检查两个权威来源
```

**authority_map 的生成逻辑：**

1. 扫描步骤 2c 中发现的已有文档
2. 尝试将每个文档匹配到对应的 governance domain
3. 能匹配的 → `authority: governance`（建议迁移）
4. 不能匹配的 → `authority: legacy`（保留原样）
5. 所有映射都标注为建议，由用户确认

---

## 步骤 5: 生成 AGENTS.md（brownfield 专用）

仅在 brownfield 模式下生成 `AGENTS.md`：

```markdown
# AI 代理启动约束

本项目使用治理基线框架。AI 代理在执行任何任务前必须遵循以下约束。

## 强制启动顺序

1. 读取 `project-governance.yaml` 确认项目配置
2. 读取 `docs/governance/00-index.yaml` 确认适用治理文档
3. 读取 `docs/governance/profiles/[profile].md` 加载项目约束
4. 检查 `authority_map` 确认当前任务受哪个权威文档管辖
5. 加载对应的 foundations 和 domains
6. 明确验证路径后再进入实现

## 双轨权威规则

本项目处于迁移阶段 [X]，部分领域由治理框架管辖，部分仍由已有文档管辖。

- 查看 `project-governance.yaml` 中的 `authority_map` 确认权威来源
- 如果 `authority: governance` → 遵循 `docs/governance/` 中的规则
- 如果 `authority: legacy` → 遵循原有文档中的规则
- 冲突时以 `authority_map` 中声明的权威来源为准

## 禁止行为

- 跳过 `project-governance.yaml` 直接猜测项目规则
- 忽略 `authority_map`，只看新框架或只看旧文档
- 发现新的跨项目规则后只留在聊天里，不回写到治理基线
- 把验证降级当作默认行为而不说明原因
```

---

## 步骤 5.5: 激活确定性门禁（接入即具备，无 git 自动降级）

> 规范：`docs/governance/INTEGRATION-GUIDE.md §3.3`、`domains/tooling/_summary.yaml`（`tool.r7`）。
> 这是**路径乙（agent 对话式集成）的硬约束**——集成不得"先配置、门禁留待以后"。

治理内容（`scripts/`）已就位时，跑统一入口一次性激活全部可用硬闸：

```bash
# governance_root 取 project-governance.yaml 的 governance_root（subtree 布局为 docs/governance）
python <governance_root>/scripts/install_governance_gates.py \
    --project-root . --governance-root <governance_root>
```

它会：
1. 有 `.git` → 幂等、非破坏地装 git 门禁（pre-commit 跑一致性 + staged-pure 卫生闸；commit-msg 校验协议）；
   **无 `.git` → 优雅降级、退出 0**，闭环仍由零依赖自检 + 入口协议 + 同步台账保证。
2. 收尾强制跑 `check_progress_consistency.py`，**必须贴出通过输出（exit 0）作为集成完成证据**。

若治理内容尚未从母版复制（本技能只生成 YAML，不复制母版），在总结中提示用户改走
`./scripts/bootstrap.sh . --tools all`——其 Step 5.5 已内置同一套门禁激活逻辑。

Cursor 用户可另加 `--with-cursor-hooks` 安装 Cursor 本地闸（仅 Cursor 内有效，不影响跨 agent 主干）。

---

## 步骤 6: 输出总结

展示生成的文件列表和后续步骤：

### Greenfield

```
✓ 生成了 project-governance.yaml
✓ 治理框架已就绪

后续步骤：
  1. 若未复制母版：./scripts/bootstrap.sh . --tools all
  2. 若仅有本技能生成的 YAML：./scripts/bootstrap-ide-tools.sh . --tools all
  3. 编辑 01-charter.md 填入项目定位
  4. python scripts/export-governance-rules.py（或 .ps1）导出 Cursor/Copilot 治理规则
  5. 运行 /opsx:explore 探索项目方向
  6. 运行 /opsx:new 创建第一个变更
```

### Brownfield

```
✓ 生成了 project-governance.yaml（含 authority_map）
✓ 生成了 AGENTS.md
✓ 治理框架已复制到 docs/governance/

当前迁移阶段: 1（仅索引）

后续步骤：
  1. 审查 project-governance.yaml 中的 authority_map
  2. 确认哪些已有文档仍需保留权威性
  3. 编辑 docs/governance/01-charter.md 填入项目定位
  4. 运行 /opsx:new 为第一个改进目标创建变更

迁移路线图：
  阶段 1 (当前): 仅建索引，已有文档不动
  阶段 2: 逐步将散落规则提升到 domains/foundations/
  阶段 3: 退役旧入口，统一权威来源
```

---

## 守卫规则

- **永远不自动修改项目代码** — 只生成治理配置文件
- **所有推荐都需用户确认** — 使用 AskUserQuestion，不自动决策
- **brownfield 不删除任何已有文档** — 只添加新文件，通过 authority_map 声明关系
- **低置信度时主动说明** — 如果项目结构不典型，坦诚说明推荐理由和局限
- **profile 建议可组合** — 如果项目跨多个 profile（如后端+ML），建议以一个为基础并补充另一个的 domains
