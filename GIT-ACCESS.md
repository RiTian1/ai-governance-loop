# Governance Git 跨机器维护入口

NAS GitLab 的 `root/governance` 项目是共享治理材料的 Git 权威仓，默认分支为 `main`。任何时间、地点、终端或 agent，只要能连通节点小宝异地网络，并持有已获该项目写入权限的 GitLab 身份及 SSH 密钥，就可以从同一远端拉取、维护、提交和迭代治理材料。访问能力由网络连通性和 GitLab 权限决定，不因使用哪台机器或哪种 agent 而变化。

## 唯一权威声明（2026-11-16 起）

本仓（NAS `root/governance` 的 `main`）是治理材料**唯一**的权威来源。此前存在的其它副本已明确让位：

| 位置 | 状态 | 说明 |
|---|---|---|
| 本机旧母版 `<workspace>\governance` | **已降级为只读历史归档** | 原 `origin` 指向公司内网 GitLab，2026-11-16 停止维护并阻断推送；详见该目录 `ARCHIVE-NOTICE.md` |
| 公司内网 `gitlab.int-guoyutec.com/yulingsec/csp/governance.git` | **停止维护** | 不再接收推送，也不再作为分发对象；仅保留可追溯的历史引用 |
| NAS `source/mother/` | 历史来源快照 | 保留早期母版工作树，不作日常提交目标 |

由此产生的约束：

- 治理修订只在本仓 `main`（或其短分支）上发生，其它目录不得作为提交源头。
- 新机器接入一律从本仓克隆，不复制其它机器的本地治理目录。
- 本仓内容不再镜像到共有 GitHub 远端或公司内网 GitLab。

## 固定入口

| 用途 | 地址 |
|---|---|
| GitLab 网页 | `http://<内网网关>:8929/root/governance` |
| Git SSH remote | `ssh://git@<内网网关>:2222/root/governance.git` |
| 默认分支 | `main` |
| NAS 服务目录 | `/data_n002/data/udata/real/18750766892/governance/gitlab/` |

`127.0.0.1:18929` 和 `governance-nas` 仅是某台机器配置的本地隧道与 SSH 别名，不能当作所有机器通用地址。项目接入时以表中地址为准。GitLab 内部的 `gitlab/data/` 由服务管理，不直接编辑其仓库文件。NAS 的 `source/mother/` 保留早期母版工作树及其本地改动，不作为各机器日常提交的远端。

## 每台机器首次接入

1. 确认节点小宝已连通，且本机可访问 `<内网网关>` 的 Web 端口 `8929` 和 Git SSH 端口 `2222`。
2. 给使用该机器的 GitLab 用户配置自己的 SSH 密钥，并把公钥添加到该用户的 GitLab SSH Keys。每个 agent 使用获授权的用户或服务身份；私钥留在本机密钥管理器，不写入仓库，也不在机器间共用。
3. 核对服务器 SSH 主机密钥后，验证身份，再从 `main` 克隆：

```bash
ssh -p 2222 -T git@<内网网关>
git clone --branch main ssh://git@<内网网关>:2222/root/governance.git governance
cd governance
git remote -v
git status -sb
```

已有本地治理目录若与此 GitLab 仓无共同历史，先保留原目录并另行克隆；不要直接把旧目录强推到 `main`。业务项目读取母版时可固定某个已审查提交；需要更新基线时，再显式拉取新版。

## 日常维护与并发提交

开始编辑前先 `git fetch origin`，检查 `git status -sb`，并以最新 `origin/main` 为基线。对同一文件的并发修改，按 Git 的提交历史和冲突标记人工核对，不以“最后写入”覆盖另一台机器的工作。

每次治理改动按本仓 `AGENTS.md`、Story/Revision 绑定和提交 trailer 约定执行。提交前至少运行：

```bash
python scripts/check_progress_consistency.py --strict
python scripts/check_staged_content.py --staged
git diff --cached --check
```

已获授权且当前项目规则允许直接推送 `main` 时，可在本地提交后执行 `git push origin main`。若远端在编辑期间更新，推送会被拒绝；此时先 `git fetch origin`，在干净工作树中运行 `git rebase origin/main`，逐项解决冲突并复跑门禁，再推送。需要撤销未完成的 rebase 时使用 `git rebase --abort`。多人同时改同一治理域时，建议建短分支并通过 GitLab MR 审查，但维护入口仍是同一个远端 `main`。不要强推或重写共享历史。

网络中断时，本机可以继续提交到本地 Git 分支；这些提交在成功推送前**尚未共享**。重新连通后先获取远端变动并解决冲突，再推送。需要别的机器立即接续时，离开原机器前应完成提交和推送。

网页编辑器、命令行、IDE 与 agent 的提交最终都进入同一 GitLab 仓库。是否可以直接推 `main` 由 GitLab 项目成员和受保护分支设置决定；“任何 agent 可维护”指获授权的 agent，不等于开放匿名写入。
