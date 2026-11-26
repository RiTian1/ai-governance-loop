# 异地机器同步 governance（可直接交 AI 执行）

适用：已通过**节点小宝**组网、本机已有 governance 副本、需要拉到 NAS 最新版的机器。
首次接入（还没有副本）请改读 `GIT-ACCESS.md`。

执行者须逐条核对本文件的**判断条件**与**验证输出**，不得跳过验证直接报告完成。

## 0. 事实基线（不要自行改写）

| 项 | 值 |
|---|---|
| GitLab 网页 | `http://<内网网关>:8929` |
| Git SSH | `<内网网关>:2222`，用户 `git` |
| 治理权威仓 | `ssh://git@<内网网关>:2222/root/governance.git`，分支 `main` |
| 唯一权威声明 | 本仓 `main` 是治理材料唯一权威来源；其它副本只读或不作提交目标 |

`127.0.0.1:18929`、`governance-nas` 只是某台机器上的隧道与 SSH 别名，**不能**当作通用地址。若本机没有这两个别名，用上表地址。

## 0.5 最快上手：五条命令

如果本机已装 git、已有 SSH 密钥并已登记到 GitLab，只需：

```bash
# 1. 确认能连（应回 Welcome to GitLab, @<user>）
ssh -p 2222 -T git@<内网网关>

# 2. 已有副本时更新
cd <governance 目录>
git fetch origin main && git merge --ff-only origin/main

# 3. 首次克隆
git clone ssh://git@<内网网关>:2222/root/governance.git governance

# 4. 确认拿到最新
git log --oneline -1        # 期望 7fa1178 或更新

# 5. 项目子树布局时，另跑自检
python docs/governance/scripts/check_progress_consistency.py --strict
```

以下三种情况会卡住，按对应步骤处理。

### 卡点 1：`ssh` 报 `Permission denied (publickey)`

说明本机没有可用的 SSH 密钥，或公钥没登记到 GitLab。

```bash
# 看有没有现成的
ls -l ~/.ssh/id_*.pub

# 没有就生成（一路回车，不设 passphrase 便于自动化）
ssh-keygen -t ed25519 -C "$(hostname)-$(date +%Y%m%d)"
cat ~/.ssh/id_ed25519.pub
```

复制输出的整行（`ssh-ed25519 AAAA...` 开头），在浏览器打开
`http://<内网网关>:8929/-/profile/keys` 登录后粘贴保存。

然后重跑 `ssh -p 2222 -T git@<内网网关>` 验证。

### 卡点 2：`ping <内网网关>` 不通

节点小宝未连通，或本机未加入该组网。先在节点小宝客户端确认设备在线、网络互通，
再重试。**不要**改用其它 IP 试探。

### 卡点 3：`git merge --ff-only` 报 `Not possible to fast-forward`

本机与远端分叉。先看清本地有什么：

```bash
git log --oneline origin/main..HEAD     # 本地独有的提交
git status --porcelain                  # 未提交的改动
```

把这两条输出交回人类决定 rebase 还是 merge。**不要**自行 `rebase`、`merge --no-ff`
或 `reset --hard`。

## 1. 前提检查（三项全过才继续）

```bash
# 1.1 组网可达
ping -c 2 <内网网关>          # Windows: ping -n 2 <内网网关>

# 1.2 Git SSH 端口通
nc -z -w 5 <内网网关> 2222 && echo OK || echo FAIL

# 1.3 身份可用（应回 "Welcome to GitLab, @<user>"）
ssh -p 2222 -T git@<内网网关>
```

任一项失败即停止，报告哪一项失败及原始输出。**不要**尝试关闭主机密钥校验或改用 root。

## 2. 判断本机布局（决定后续走 A 还是 B）

```bash
cd <本地治理目录>
cat project-governance.yaml | grep -E 'governance_layout|governance_root'
```

| 输出 | 布局 | 走 |
|---|---|---|
| `governance_layout: mother-repo-root` | 治理在仓库根 | **方案 A** |
| `governance_layout: docs-governance-subtree` | 治理在子目录（通常 `docs/governance`） | **方案 B** |

若文件不存在或字段缺失，按方案 B 处理并在报告中注明"布局未声明，按子树处理"。

## 方案 A：母版仓整体快进

适用：本机目录**就是**治理仓工作树（根目录有 `00-index.yaml`、`scripts/` 等）。

```bash
cd <repo>
git remote -v | grep -q 'root/governance.git' || git remote add origin ssh://git@<内网网关>:2222/root/governance.git
git fetch origin main
git log --oneline -1 origin/main          # 记录目标 commit
git status --porcelain                    # 记录本地改动
```

分三种情况处理：

**A1 工作树干净**
```bash
git merge --ff-only origin/main
```

**A2 有本地改动，但都未提交**
```bash
git stash push -u -m "pre-sync-$(date +%Y%m%d-%H%M)"
git merge --ff-only origin/main
git stash pop          # 可能冲突，见 §4
```

**A3 有本地提交（分叉）**
```bash
git log --oneline origin/main..HEAD    # 列出本地独有的提交
```
**停止**，把这份列表交回人类决定 rebase 还是 merge。**不要**自动 rebase 或强推。

## 方案 B：业务项目更新治理子树

适用：项目根有 `project-governance.yaml`，治理内容在 `docs/governance/`（如 项目A）。

要点：`docs/governance/` 是**项目仓的一部分**，不是子模块。同步 = 取母版最新内容覆盖该子树，再由项目仓自行提交。

```bash
# B1 取一份干净的最新母版（浅克隆到临时目录，避免污染项目）
rm -rf /tmp/gov-latest
git clone --depth 1 --branch main ssh://git@<内网网关>:2222/root/governance.git /tmp/gov-latest
git -C /tmp/gov-latest rev-parse --short HEAD    # 记录来源 commit，写进报告

# B2 备份当前子树（可回滚）
cp -r docs/governance /tmp/gov-backup-$(date +%Y%m%d-%H%M)

# B3 覆盖（保留项目本地定制，见下方排除清单）
rsync -a \
  --exclude='.git/' \
  --exclude='projects/' \
  --exclude='_logs/' \
  --exclude='.workbuddy/' \
  --exclude='openspec/config.yaml' \
  /tmp/gov-latest/ docs/governance/
```

Windows 无 rsync 时用 PowerShell：

```powershell
robocopy C:\tmp\gov-latest .\docs\governance /E /XD .git projects _logs .workbuddy /XF config.yaml
```

**不得排除**的目录：`scripts/`、`rsi/`、`foundations/`、`domains/`、`templates/`、`agents/`。这些是治理本体。

**必须排除**的本地定制（按项目实际）：

| 路径 | 原因 |
|---|---|
| `openspec/config.yaml` | 项目自有 OpenSpec 配置 |
| `.claude/`、`.agents/`、`.github/` | 工具配置，由项目自行管理 |
| `_bmad/<project>/stories/`、`openspec/changes/` | 项目自己的进度记录，不是母版的 |

## 3. 验证（四项全过才算完成）

```bash
# 3.1 内容确实变了
git status --porcelain docs/governance | wc -l      # 方案 B；方案 A 用 git log --oneline -1

# 3.2 关键文件在位（按布局选一行执行）
# 方案 A（母版根）：路径不带前缀
for f in AGENTS.md GIT-ACCESS.md LAYOUT.md rsi/native-cli-compatibility.md \
         scripts/rsi_realworld_benchmark.py scripts/check_progress_consistency.py; do
  [ -f "$f" ] && echo "OK   $f" || echo "MISS $f"
done
# 方案 B（子树）：路径带 docs/governance/ 前缀
for f in AGENTS.md GIT-ACCESS.md LAYOUT.md rsi/native-cli-compatibility.md \
         scripts/rsi_realworld_benchmark.py scripts/check_progress_consistency.py; do
  [ -f "docs/governance/$f" ] && echo "OK   $f" || echo "MISS $f"
done

# 3.3 进度一致性自检（零依赖，无 pyyaml 也能跑）
# 方案 A
python scripts/check_progress_consistency.py --strict
# 方案 B
python docs/governance/scripts/check_progress_consistency.py --strict
# 期望 errors=0；若 project 有存量债务，改跑 --staged 看是否只报本次改动
```

3.2 有 MISS 或 3.3 返回非 0 → 停止，报告缺哪个文件、错误类型分布，不要自行"修一下让它过"。

## 4. 冲突处理

| 情况 | 正确做法 | 禁止 |
|---|---|---|
| `stash pop` 冲突 | 逐个文件人工合并，保留双方语义 | 直接 `checkout --theirs` 丢掉本地改动 |
| `merge --ff-only` 失败 | 说明本地与远端分叉，交人类决定 | `--no-ff` 强合、`reset --hard` |
| `docs/governance` 出现删除 | 核对是否母版真的删了该文件（`git -C /tmp/gov-latest log --oneline -3 -- <path>`） | 用 `--delete` 批量删除 |

## 5. 报告格式（执行完必须给出）

```
前提检查: 网络 OK / 端口 OK / 身份 OK（<user>）
布局判定: mother-repo-root | docs-governance-subtree
来源 commit: <sha>
同步方式: A1 快进 | A2 stash+pull | B3 rsync（排除项：...）
改动规模: N 个文件
关键文件: 6/6 在位
自检: errors=0 warnings=0
失败/跳过项: 无 | <具体说明>
```

## 6. 禁止事项

1. 不得把治理内容提交到 `main` 之外的机器副本后宣称"已更新"——权威只有 NAS 那一个。
2. 不得在没跑 §3.3 自检的情况下报告完成。
3. 不得关闭 `StrictHostKeyChecking`、不得共用他人私钥。
4. 不得用 `git push --force` 或 `reset --hard` 处理分叉。
5. 不得把 `openspec/config.yaml`、`_bmad/<project>/stories/` 当作母版内容覆盖。
6. 不得只同步 `docs/governance` 而漏掉项目根的 `project-governance.yaml`（若母版也更新了它）。
