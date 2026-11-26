# 文档工作流

本文档定义当前仓库的默认分层关系：治理入口 -> 变更工件 -> 实现 -> 验证 -> 归档。

## 1. 默认文档栈

```text
project-governance.yaml  (governance_root → 见 LAYOUT.md)
  -> {governance_root}/*
    -> openspec/changes/<change>/*
      -> code / tests / build artifacts
        -> verify evidence
          -> archive / revisions
```

## 2. 各层职责

### 2.1 项目激活层

- 定义当前项目启用了哪些治理文档
- 定义当前项目仍受哪些本地规则约束

### 2.2 项目级治理层

- 定义长期稳定边界、验证政策和 agent 协作纪律
- 不承担单次变更的局部实现方案

### 2.3 变更级工件

- 放在 `openspec/changes/`
- 负责承接某次变更的 proposal、design、tasks 与验证计划

### 2.4 实现与验证层

- 代码、测试、构建脚本与文档更新必须能回指到变更工件或项目级规则
- 验证输出必须能支撑交付，不应只留在口头描述

### 2.5 阶段治理映射

- 技术可行性分析：判断可行边界、风险、平台矩阵和前置条件
- PRD 制定：定义目标、范围、非目标、验收边界和适配对象
- 方案设计：定义职责划分、模块边界、兼容性与验证路径
- 详细设计：定义实现切片、配置来源、安装编译步骤、测试前置动作
- 工程实施落地：完成代码、脚本、配置、文档和回注
- 测试集成：完成环境准备、矩阵验证、回归与降级说明
- CI 流水与交付：完成门禁、制品、回滚与交付证据

## 3. 与当前仓库的映射

- 项目级入口：`project-governance.yaml`、`AGENTS.md`、`docs/governance/`
- 变更工件：`openspec/changes/`
- 实现主体：[主要源码目录] 及相关集成目录
- 项目局部规则：`docs/project-rules.md`

## 4. 写作准入规则

- 如果说不清变更是规则语义变化、运行时实现变化还是制品变化，就不应直接编码。
- 如果验证策略仍未明确，任务不能只剩“改代码”。
- 如果新全局规则只存在于变更说明里，归档不应视为完成。


## 5. 跨阶段回注要求

- 在 `explore`、`proposal`、`design`、`tasks`、`apply`、`verify`、`archive` 任意阶段，只要发现新的项目级约束、需求变化、静态测试描述、前置功能概括或全局规则变更，都必须立即回注。
- change-local 内容回写到 `openspec/changes/<change>/` 对应工件。
- 可复用、跨变更、跨模块的规则回写到 `docs/governance/`、`docs/project-rules.md` 或 `docs/governance/revisions/`。
- 不允许等到归档阶段才集中补写已经明确出现的全局信息。
- 如果实现或验证过程中才暴露出前置动作、静态检查口径或适配矩阵，这些内容也必须在当轮同步更新，而不是只放在执行记录里。

## 6. 归档与 Git 交付（含闭环 STOP 门）

- 归档完成判定除工件齐全外，还须满足 `02-engineering-principles.md` §10（归档与提交原子约束）。
- 典型原子提交范围：`openspec/changes/archive/<date>-<change>/` + 该 change 对应的源码/测试/配置/验证记录。
- 提交后推送到 `origin/master`（或 `project-governance.yaml` 声明的主协作分支），并在 PR/变更说明中注明 change 名与验证摘要。

### 6.1 状态变更 = 同步事件（硬判定，MUST/STOP）

> 归档 / 标完成 / 写 `active_sprint` 都是高风险状态变更。规则文本不够，执行点必须落在 agent 自身的不可跳过动作链上。

- **STOP**：在 `python scripts/check_progress_consistency.py` 通过（exit 0）之前，**禁止**把任何 Story 标 `done`/`completed`、
  禁止把 change/revision 标 `archived`/`merged`、禁止写 `active_sprint`。状态字段是**最后一步**，且必须与其它工件联动。
- 新增收敛 / 修补工作 MUST 新建 story/change，**禁止挂到已 `done`/`archived` 的 Story**（否则"已完成"失真）。
- 收尾（含归档）前 MUST 贴出 `check_progress_consistency.py` 的通过输出；任一检查失败（exit != 0）→ **不许 commit、不许标完成、不许归档**。
- 该自检零依赖、git-optional：无 pyyaml / 无 `.git` 亦可运行；有 `.git` 时由 `scripts/install_git_hooks.py` 额外加挂 pre-commit 门作为附加层。
