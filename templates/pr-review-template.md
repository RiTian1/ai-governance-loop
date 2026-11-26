# PR 评审模板（AI 参与场景必填）

> 用法：复制到 PR 描述，**每一节都必须填**。缺节由 `scripts/check_review_gate.py` 判红。
> 规范：`domains/ai-code-review.md`（`review.r3` / `r6` / `r9`~`r11`）。

## 意图

<!-- 为什么改？解决什么问题？不写"优化了一些代码"这种话。 -->

## 影响面

<!-- 改了哪些模块 / 可能波及什么 / 会不会影响已有行为。 -->

- 影响模块：
- 破坏性变更：是 / 否（是则必须判 high）
- 数据迁移：是 / 否（是则必须判 high）

## 验证

<!-- 跑了什么？证据在哪？（命令输出、测试名、截图路径） -->

- 命令：
- 结果：
- 未覆盖项：（没有就写"无"，不许留空）

## 风险分级

risk_level: medium

<!-- low | medium | high，判据见 domains/ai-code-review.md「核心规则 review.r3」
     low：改坏也不造成不可逆损失（文档/注释/测试/纯展示）
     high：数据迁移、鉴权、删除、破坏性接口
     其余 medium；判不准按 high -->

## AI 参与声明

ai-assisted: none

<!-- 用了就写工具名（codex / claude-code / cursor / 项目A），没用写 none。
     隐瞒视为违规（review.r2）。 -->

## 签字

<!-- risk_level=high 时必须两人，且至少一人非作者（review.r4 / r11）。
     签字 = 接受风险，包含没有全部读懂的部分（review.r10）。
     AI 不得出现在 signed_by 里（review.r9）。 -->

signed_by: 
signed_at: 
evidence_refs: 
