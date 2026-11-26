# 任务：把 macOS 本机特有的治理内容 rebase 回 governance 并推送

> 交给 Cursor 执行。执行前请完整读一遍，尤其「禁止事项」与「判断分支」。
> 本文档所有命令在 macOS 终端（Cursor 内置终端）执行。

## 一、背景

这台 Mac 上的治理仓 `/Volumes/Harness/governance` 是共享治理材料的一份副本。
它曾经包含**本机特有的运维参考与约束**（例如 `runtime-context.yaml` 里的 macOS 条目、
`domains/operations/` 下的本机事实、`docs/project-rules.md` 里的本机约束等）。

近期该目录经历过"路径搬迁 / 重新拉取"，需要确认：**这些本机特有内容是否还在**。
如果在，把它们保留并推到远端权威仓；如果已丢失，从 git 历史或 stash 里找回。

远端权威仓（唯一权威，不要怀疑）：
```
ssh://git@<内网网关>:2222/root/governance.git   分支 main
```
本机已具备访问能力（`ssh -p 2222 -T git@<内网网关>` 应返回 `Welcome to GitLab, @governance-admin`）。

## 二、目标（按优先级）

1. **不丢任何本机特有内容**。宁可停在中间报告，也不要为了"干净"而丢弃。
2. 把本机特有内容作为**独立提交**推到远端 `main`。
3. 若本机与远端已分叉，用 **rebase 到 origin/main** 的方式整理，不使用 merge commit。

## 三、执行步骤

### Step 0：先备份，再动手

```bash
cd /Volumes/Harness/governance
STAMP=$(date +%Y%m%d-%H%M)
git bundle create ~/gov-backup-$STAMP.bundle --all
cp -a .git ~/gov-gitdir-backup-$STAMP
echo "备份完成: ~/gov-backup-$STAMP.bundle  ~/gov-gitdir-backup-$STAMP"
```

**备份失败就不要继续**。`git bundle` 会包含所有分支与引用，是最可靠的还原点。

### Step 1：诊断（把结果原样保留在回答里）

```bash
cd /Volumes/Harness/governance

echo "=== 1.1 remote ==="
git remote -v

echo "=== 1.2 当前分支与 HEAD ==="
git branch --show-current
git log --oneline -5

echo "=== 1.3 远端最新 ==="
git fetch origin main
git log --oneline -3 origin/main

echo "=== 1.4 工作树改动 ==="
git status --porcelain

echo "=== 1.5 stash ==="
git stash list

echo "=== 1.6 本机独有提交（相对远端）==="
git log --oneline origin/main..HEAD

echo "=== 1.7 远端独有提交（相对本机）==="
git log --oneline HEAD..origin/main
```

根据这七项的输出，走下面四个分支之一。**不要跳过诊断直接 rebase。**

### Step 2：按情况处理

#### 分支 A：工作树有改动（`1.4` 非空），且 `1.6`、`1.5` 都为空

含义：本机特有内容还在工作树里，只是没提交。

```bash
git add -A
git commit -m "feat(macos): 恢复本机特有的运维参考与约束

本机经历路径搬迁后，把此前仅存在于工作树的 macOS 相关治理内容
（运维参考、本机约束、运行时事实）作为独立提交固化，
避免再次搬迁时丢失。"
```

然后跳到 Step 3。

⚠️ 提交前先 `git diff --stat` 看一眼改了哪些文件，确认没有把 `.DS_Store`、
临时文件、私钥之类的东西提交进去。若有，先加进 `.gitignore` 或 `git reset` 掉。

#### 分支 B：`1.6` 有本机独有提交，`1.4` 为空

含义：本机内容已提交，但与远端分叉。

```bash
git rebase origin/main
```

- 如果**无冲突**：直接进入 Step 3。
- 如果**有冲突**：逐个文件人工合并，保留双方语义。**不要** `git checkout --theirs`。
  解决后 `git add <file>` 然后 `git rebase --continue`。
- 如果**冲突难以判断**：`git rebase --abort` 回到起点，把 `git status` 与冲突文件列表报告出来，不要硬推。

#### 分支 C：`1.5` 有 stash

含义：之前 pull 时被 stash 过。

```bash
git stash list
git stash show -p stash@{0} | head -100     # 先看内容
git stash pop
```

- 若 `pop` 顺利且有改动：按**分支 A** 处理（add + commit）。
- 若 `pop` 冲突：先 `git checkout -- .` 撤销，然后改用 `git stash apply` 再手工合并；
  或停下报告，附 `git stash show -p stash@{0}` 的摘要。

#### 分支 D：三者都空，且 `1.7` 非空（本机落后于远端）

含义：本机内容可能已经在历史里，或者压根没提交过就被覆盖了。

```bash
git merge --ff-only origin/main
```

然后**必须**做一次内容核对，确认本机特有内容是否还在：

```bash
# 检查 macOS 相关事实是否存在于当前树
grep -rn -i "macos\|/Volumes/Harness\|osxs-Mac" \
  runtime-context.yaml docs/project-rules.md domains/operations/ 2>/dev/null | head -20
```

- 有输出 → 内容还在，进入 Step 3。
- 无输出 → 内容已丢失。**停下**，报告"本机特有内容未找到"，并给出
  `git log --all --oneline -- runtime-context.yaml | head -10` 的输出，
  由人类决定是否从历史恢复（不要自行 `git revert` 或猜测内容）。

#### 分支 E：`1.4` 非空 **且** `1.6` 非空（既有改动又有本地提交）

先处理工作树，再做 rebase：

```bash
git stash push -u -m "pre-rebase-$STAMP"
git rebase origin/main
git stash pop
```

`stash pop` 后若有冲突，按分支 C 的方式处理。

### Step 3：验证（四项全过才能推）

```bash
cd /Volumes/Harness/governance

# 3.1 干净
git status --porcelain          # 期望：无输出

# 3.2 历史线性（rebase 后不应有 merge commit）
git log --oneline --graph -8

# 3.3 内容核对：本机特有内容确实在
grep -rn -i "macos\|/Volumes/Harness\|osxs-Mac" \
  runtime-context.yaml docs/project-rules.md domains/operations/ 2>/dev/null | head -10

# 3.4 治理自检（零依赖）
python3 scripts/check_progress_consistency.py --strict 2>&1 | tail -5
```

- `3.4` 期望 `errors=0`。
- 若报大量存量债务（几十上百条），改用 `--staged` 看是否只报本次改动，并在报告中说明。
- `3.3` 若为空，说明本机内容没恢复，**不要推**。

### Step 4：推送

```bash
git push origin main
```

**只能普通 push**。若被拒绝（non-fast-forward），说明远端在你这期间又有新提交：

```bash
git fetch origin main
git rebase origin/main     # 再解一次冲突
git push origin main
```

**禁止 `--force` / `--force-with-lease`**。这是共享权威仓，强推会让其他人的提交消失。

## 四、禁止事项

1. **禁止** `git push --force` 或 `--force-with-lease`。
2. **禁止** `git reset --hard` 到任何远端提交（会丢本机内容）。
3. **禁止** `git checkout --theirs` / `--ours` 批量解决冲突。
4. **禁止**为了"让自检通过"而删除或改写历史文件。
5. **禁止**跳过 Step 0 的备份。
6. **禁止**在 `3.3` 内容核对为空的情况下推送。
7. **禁止**把 `.DS_Store`、`~/.ssh/` 下的私钥、任何 `sk-` 开头的密钥提交进仓。

## 五、完成后的报告格式

请按此格式回答，缺项视为未完成：

```
【备份】~/gov-backup-<stamp>.bundle（大小 X MB）
【诊断】分支：<main>  HEAD：<sha>  远端：<sha>
        工作树：<N> 个改动  stash：<N> 条  本地独有提交：<N> 个
【处理】走分支 <A/B/C/D/E>：<一句话说明做了什么>
【验证】3.1 干净 ✓  3.2 线性 ✓  3.3 本机内容 <N> 处命中  3.4 errors=0
【推送】git push origin main 结果：<成功 / 被拒后 rebase 再推成功>
【最终】远端 main = <sha>
【遗留】无 / <具体说明>
```

## 六、已知事实（避免重复排查）

| 项 | 值 |
|---|---|
| 远端地址 | `ssh://git@<内网网关>:2222/root/governance.git` |
| 分支 | `main` |
| 本机 SSH 身份 | `governance-admin`（已验证可用，无需再配密钥） |
| 本机路径 | `/Volumes/Harness/governance`（独立 APFS 卷） |
| 远端最新参考 | `2f4c4f4`（2026-11-18，若已更晚则以 `origin/main` 为准） |

注意：`/Volumes/Harness` 是独立卷，**从 SSH 会话访问会被 macOS TCC 拦截**（`Operation not permitted`），
但 **Cursor 作为 GUI 应用有权限**，在其内置终端里操作不受影响。这也是本任务交给 Cursor 而不是远程 SSH 的原因。
