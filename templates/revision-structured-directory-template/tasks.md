# Tasks — <revision-title>

> 可机器勾选的执行清单。每条 task 完成后改 `[ ]` 为 `[x]`，并在 commit message 引用本 revision_id。

## 阶段 1：foundations / domains 主体

- [ ] T1.1 ...
- [ ] T1.2 ...

## 阶段 2：脚本与工具

- [ ] T2.1 ...

## 阶段 3：模板

- [ ] T3.1 ...

## 阶段 4：路由 / 索引同步

- [ ] T4.1 更新 `00-index.yaml`
- [ ] T4.2 更新 `AGENTS.md` / `CLAUDE.md` / `README.md`
- [ ] T4.3 更新 `revisions/index.yaml`

## 阶段 5：dogfood / 反向 fit

- [ ] T5.1 ...

## 阶段 6：验证

- [ ] T6.1 `scripts/check_encoding.py` 通过
- [ ] T6.2 `scripts/check_knowledge_health.py --all` 通过
- [ ] T6.3 `scripts/check_progress_consistency.py --strict` 通过
- [ ] T6.4 `scripts/gen_progress_matrix.py` 输出符合预期

## 阶段 7：提交

- [ ] T7.1 按 02 §10 原子提交（commit msg 含 Story/Change/Revision/Rules）
- [ ] T7.2 push 到主协作分支
