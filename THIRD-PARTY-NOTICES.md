# Third-Party Notices / 第三方组件声明

本仓库整合并再分发了以下上游开源组件的内容（版本锁定见 `UPSTREAM-VERSIONS.yaml`）。
三者均为 MIT 许可证，再分发时依其条款保留版权声明与许可文本。

This repository integrates and redistributes content from the following upstream
open-source projects (version pins in `UPSTREAM-VERSIONS.yaml`). All are MIT-licensed;
their copyright notices and license texts are preserved below as required.

---

## 1. BMAD-METHOD

- Upstream: <https://github.com/bmad-code-org/BMAD-METHOD>（tag v6.10.0）
- 本仓库分发物：`.claude/skills/bmad-*/`（安装器产物）、`_bmad/`（配置与桥接）
- 本地修改：输出语言 pin 为中文（`_bmad/custom/config.toml` 等三处）、
  `_bmad/governance-bridge.yaml` 治理桥接（自研）

```
MIT License

Copyright (c) 2025 BMad Code, LLC
```

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following
conditions: The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED
"AS IS", WITHOUT WARRANTY OF ANY KIND.

## 2. OpenSpec

- Upstream: <https://www.npmjs.com/package/@fission-ai/openspec>（v1.5.0）
- 本仓库分发物：`.claude/commands/opsx/*.md`、`.claude/skills/openspec-*/`
- 本地修改：正文为**中文化维护版**（zh-CN governance-overlay，语义与上游 1.5.0
  生成物一致）；`openspec-bootstrap` 为自研治理定制技能，非上游生成物

```
MIT License

Copyright (c) 2024 OpenSpec Contributors
```

（许可条款同上，MIT 标准文本。）

## 3. agency-agents

- Upstream: <https://github.com/msitarzewski/agency-agents>
- 本仓库分发物：**不 vendored**（按需 `scripts/fetch-reference.*` 拉取到
  gitignored 的 `_reference/`）。`agents/` 下 20 个代理为治理定制策展版，
  角色设定参考了上游生态，正文与 `governance:` 绑定为自研

```
MIT License

Copyright (c) 2025 AgentLand Contributors
```

（许可条款同上，MIT 标准文本。）

## 4. Z-Blog v2.2（benchmark 素材）

- Upstream: <https://www.rainbowsoft.org>
- 本仓库分发物：`benchmark/tasks/J3b-filemanage-plugin/source/`（4 个 ASP，
  共 1,725 行，用于代码审计基准任务的离线静态分析）
- 授权：Z-Blog 最终用户授权协议（v2.X）——**完全开源，允许任意分发**；
  再分发时须保留官方署名与官方网站链接标识（http://www.rainbowsoft.org）。
  该授权协议**非** MIT，故本节单独列出；本仓库对其代码**未做任何修改**。
- 用途：仅作离线安全审计基准样本，不构成对其功能或安全性的背书。

> 注：Z-Blog 采用自有 EULA 而非 MIT。引用其源码时请同时保留本声明与
> 其官方署名要求。

---

除上述组件外，本仓库其余内容（治理文档、脚本、模板、技能定制）依根目录
`LICENSE`（MIT, Copyright (c) 2026 RiTian1）发布。

All other content in this repository (governance documents, scripts, templates,
skill customizations) is released under the root `LICENSE` (MIT).
