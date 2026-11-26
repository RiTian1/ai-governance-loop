# 母版初始化与采用指南

本文档用于把当前 `docs/governance/` 当作“新项目治理母版”直接落地到其他仓库。

## 1. 适用场景

- 新建项目，需要快速建立治理基线
- 旧项目治理混乱，需要分阶段迁移
- 多个项目希望共用同一套母版，再按项目类型裁剪

## 2. 最佳实践

最佳实践不是把整个目录无脑复制过去，而是按以下顺序采用：

1. 先复制主文档、索引和模板骨架
2. 再选择一个最接近的 `profile`
3. 再叠加需要的 `domains`
4. 最后按项目特点增补业务与行业专属约束

这样做的原因：

- 可以减少一开始的治理噪声
- 可以避免把不相关领域文档变成负担
- 可以让 AI / 人工协作快速聚焦真正需要的上下文

## 3. 新项目初始化步骤

### 3.1 最小必装

最小建议复制：

- `00-index.md`
- `00-index.yaml`
- `01-charter.md`
- `02-engineering-principles.md`
- `03-document-workflow.md`
- `04-verification-policy.md`
- `05-ai-collaboration-policy.md`
- `06-reference-and-standards-policy.md`
- `08-project-activation-model.md`
- `templates/`
- `revisions/README.md`

### 3.2 按项目类型装配

选择一个主 `profile`：

- 桌面 GUI / 工作台
- 后端 / 平台服务
- 嵌入式 / 实时系统
- 机器学习 / 数据系统
- 安全研究 / 实验室

再加载该 profile 推荐的：

- `foundations/`
- `domains/`
- `templates/`

### 3.3 项目级裁剪

初始化后应立即回答：

- 哪些领域当前不需要
- 哪些文档仅保留骨架即可
- 哪些模板必须成为 CI/评审/发布门禁的一部分
- 哪些规则属于公司级或行业级，不能只留在项目母版里

## 4. 旧项目迁移步骤

建议按三阶段迁移：

### 阶段一：只挂索引，不改旧文档

- 先引入 `00-index.md` / `00-index.yaml`
- 标注现有项目级约束仍以旧文档为准
- 让团队先通过索引找入口

### 阶段二：把长期规则提升到新骨架

- 把零散规则提升到 `foundations/`、`domains/` 或主文档
- 把模板补到 `templates/`
- 把新规则记录到 `revisions/`

### 阶段三：收敛旧平行体系

- 废弃过时入口
- 在旧文档开头挂接新索引
- 删除重复、冲突或无人维护的平行规范

## 5. 采用策略

### 5.1 单仓库

- 直接把 `docs/governance/` 放入仓库
- 把项目专属文档继续放在 `docs/` 其他目录

### 5.2 多仓库共享母版

- 建议保留一个“治理母版仓库”或“治理同步源”
- 各项目复制后可以本地演进，但应保留母版来源说明

### 5.3 单体项目与平台项目

- 单体项目可以保留较少领域包
- 平台项目建议保留完整索引、`foundations/` 与 `profiles/`

## 6. 采用后的最小动作

完成初始化后，至少应补齐：

- 一份项目宪章
- 一份 `project-governance.yaml`
- 一份项目术语表
- 一份 PRD 模板落地样例
- 一份测试计划落地样例
- 一份修订单样例

## 7. 采用粒度（避免过重）

| 团队/仓库 | 最小装配 | 工作流 |
|-----------|----------|--------|
| 个人脚本、无 CI | `AGENTS.md` + `04-verification-policy.md` + 单 profile | OpenSpec 可选 |
| 小团队应用 | 主文档 `01`–`05`、`08` + 裁剪后的 domains | OpenSpec 默认；BMAD 关闭 |
| 企业 brownfield | 全主文档 + authority_map + 安全/自动化 domains | OpenSpec + `revisions/WORKFLOW.md` |
| 全新 MVP | 上项 + 按需开启 BMAD | `frameworks.bmad.enabled: true` |

生成 `project-governance.yaml` 后，应校验 `governance_root` 下每条 `active_baseline` 路径存在（见 `LAYOUT.md`）。

## 7.0 多 IDE / CLI 一键接入（bootstrap 脚本）

`scripts/bootstrap.sh` / `bootstrap-windows.ps1` 在复制母版后默认执行 **Step 5：IDE 适配器安装**（需 Node.js `npx`）。

| 参数 | 作用 |
|------|------|
| `--tools claude,cursor,codex,opencode,qwen,trae` | 传给 OpenSpec `init --tools`（默认即此列表） |
| `--tools all` | 同上（别名） |
| `--skip-ide-tools` | 跳过 OpenSpec；回退为 `.claude` → `.cursor`/`.codex` 镜像（不推荐） |
| `--enable-bmad` | 额外运行 `bmad-method install`（会覆盖 `_bmad`，仅 BMAD 开启时用） |

```bash
./scripts/bootstrap.sh /path/to/project --tools all
./scripts/bootstrap-ide-tools.sh /path/to/project --tools cursor,claude
```

`/opsx:bootstrap` **不**执行上述安装；在仅生成 `project-governance.yaml` 后，应提示用户运行 bootstrap 脚本或 `bootstrap-ide-tools`。

锁定版本见 `UPSTREAM-VERSIONS.yaml`（OpenSpec 1.5.0、BMAD 6.10.0）。

## 7.1 导出 IDE 规则（Cursor / Copilot）

```bash
pip install -r scripts/requirements.txt
python scripts/export-governance-rules.py
```

生成 `.cursor/rules/governance-*.mdc` 与 `.github/copilot-instructions.md`（Review 安全长度）。纳入版本库或 CI 校验「导出物与 manifest 同步」。

## 7.2 Agent Evals（可选）

1. 合并 `templates/agent-evals-manifest-template.yaml` 到 `project-governance.yaml`
2. 复制 `templates/promptfoo/`、`templates/evals/`、`templates/github-workflows/agent-evals.yml.example`
3. 配置 CI secrets 后启用 `agent_evals.pr_gate.enabled: true`

## 7.3 上游同步（OpenSpec + BMAD）

```powershell
powershell -File scripts/sync-upstream.ps1
```

锁定版本见 `UPSTREAM-VERSIONS.yaml`。同步后保留治理定制：`_bmad/governance-bridge.yaml`、`openspec-bootstrap` 技能、`openspec/config.yaml` 的 `rules` 段。

## 7.4 BMAD 单源

启用 BMAD 前阅读 `BMAD-SINGLE-SOURCE.md`；仅改 `_bmad/` 后运行 `scripts/sync-bmad-skills.ps1 -Prune`。

## 9. 反模式

- 把整个母版复制过去却从不裁剪
- 只复制模板，不复制索引和主文档
- 继续把新规则只写在聊天里，不进入 `revisions/`
- 复制后不声明哪些文档是项目级现行基线

## 10. 完成判定

一个项目可视为“成功采用母版”的最低标准：

- 新成员能从索引快速定位规则
- 评审与验证开始引用模板
- 新规则开始通过修订单进入基线
- 旧平行规范开始收敛而不是继续膨胀
