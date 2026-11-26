# Progress-binding（跨工具绑定）

本子域是 `foundations/progress-traceability-and-binding.md` 的工程构件层：把绑定从"软规则"变为"机器闸口"。

## 1. 工程构件清单

| 构件 | 文件 | 用途 |
|------|------|------|
| 标识协议 | foundation §2 | Story / Change / Revision / Rule / FR / Test 的 ID 形式 |
| 三向反向引用 | foundation §3 | Story / change / revision / rule frontmatter 必填字段 |
| 状态机 | foundation §4 | 三端合法对齐表 + 漂移定义 |
| 一致性校验 | `scripts/check_progress_consistency.py` | 状态机 + 反向引用 + 哈希一致性 |
| Matrix 生成器 | `scripts/gen_progress_matrix.py` | 自动生成 traceability matrix |
| Commit 校验 | `scripts/check_commit_message.py` | pre-commit 阻断违规 commit message |
| Revision-commit 关联 | `scripts/link_revision_to_commits.py` | post-merge 自动 fill commits 字段 |
| CI workflow 模板 | `templates/github-workflows/progress-traceability.yml.example` | GitHub Actions 接入 |
| pre-commit 模板 | `templates/pre-commit/governance-progress.yaml.example` | 本地阻断模板 |

## 2. 双闸口

```
pre-commit (本地, < 5s):
  ├─ check_encoding.py（编码闸，已有）
  ├─ check_commit_message.py（新：Story/Change/Revision/Rules 行）
  └─ check_progress_consistency.py --staged
                                    --quick（仅 staged 文件 frontmatter 完整性）

CI (PR / monthly):
  ├─ check_progress_consistency.py --strict
  ├─ gen_progress_matrix.py --report _logs/progress-matrix.md（PR 上 bot 评论）
  ├─ check_knowledge_health.py --all
  └─ check_encoding.py
```

## 3. 项目启用矩阵

| 项目规模 | bmad | openspec | revisions | progress-binding |
|----------|------|----------|-----------|------------------|
| 母版 | dogfood | ✓ | ✓ | ✓ |
| 大型平台型 | ✓ | ✓ | ✓ | ✓ |
| 中型业务（3-10 人月） | 按需 | ✓ | ✓ | ✓ |
| 小项目（≤ 3 人月） | ✗ | ✓ | 仅引入全局规则时 | ✓（最小集：commit msg + matrix） |

## 4. 哈希算法约定

- `acceptance_criteria_hash`：Story 文件中 `## Acceptance Criteria` 标题下到下一个 `## ` 之间的文本，去首尾空白后 SHA-1
- `spec_delta_hash`：OpenSpec change `specs/**/spec.md` 中所有 `## ADDED Requirements` `## MODIFIED Requirements` `## REMOVED Requirements` 块文本拼接后 SHA-1

由 `check_progress_consistency.py` 实现并校验。

## 5. 漂移分类与处理

| 漂移类型 | 检测点 | 处理 |
|----------|--------|------|
| 状态漂移 | check_progress_consistency.py | CI error，阻断 |
| AC ↔ spec 内容漂移 | 同上 | CI error，要求 PM/Dev 协商更新一端 |
| 反向引用缺失 | 同上 | CI error |
| commit message 缺关键行 | check_commit_message.py（pre-commit） | 本地拒，要求修订 |
| 孤立 Story / change / revision | check_progress_consistency.py | CI warn，月度提单 |
| commits 字段未 fill | post-merge hook 跑 link_revision_to_commits.py | 自动修复 |

## 6. 与 self-governance 的咬合

- Observe：月度跑 `gen_progress_matrix.py` 输出 matrix.md
- Diagnose：matrix 中所有 drift 列入 health report
- Decide：drift 修复或规则升级走 candidate revision
- Execute：修复后 status 转 accepted / merged
- Regress：下一轮 matrix drift 数为 0

## 7. 反模式

- 在 governance 项目里实际做了 BMAD/OpenSpec 工作但不接入本子域
- 跑 matrix 但不读 drift 列；放任 drift 数 > 0 持续多轮
- pre-commit hook 被 `--no-verify` 绕过（CI 必须二次校验，不允许只靠本地）
- 项目 manifest 不声明 `enabled_domains: [tooling/progress-binding]`，期望工具自己发现（Loader 不会给）
