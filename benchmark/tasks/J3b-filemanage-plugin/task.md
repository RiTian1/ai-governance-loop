# 任务：Z-Blog 插件 FileManage 安全审计

## 背景

一套 ASP 博客系统（Z-Blog v2.2）里有个第三方插件 **FileManage**（文件管理）。
它的定位是"给管理员用的在线文件管理器"——浏览、编辑、上传、下载、删除、重命名站点目录下的文件。

安全评审要回答两个问题：

1. 这个插件**越权**了吗——管理员能不能借它碰到站点目录**之外**的文件？
2. 有没有**绕过身份**的路径——攻击者能不能不登录管理员就触发这些操作？

## 素材与范围（**只审这个目录**）

```
source/zb_users/PLUGIN/FileManage/
├── main.asp              235 行   入口与动作分发
├── function.asp          856 行   全部文件操作实现
├── include_plugin.asp    544 行   插件钩子注册
├── include.asp            90 行   把上面两个 include 进来
├── plugin.xml             元数据（id / level / 依赖）
└── images/               图标，忽略
```

合计约 1,725 行 ASP。**范围外的问题不要报**（`zb_system/`、`zb_users/c_option.asp` 等都不算）。
可以读范围外的文件来判断**数据流是否被截断**——例如某个被调函数是否真的做了校验，
这往往是判断成立与否的关键——但只有上面 4 个 `.asp` 里的问题算数。

## 交付物

在当前目录写 `findings.json`：

```json
{
  "findings": [
    {
      "file": "相对路径，如 function.asp",
      "line": 543,
      "type": "rce | arbitrary_file_write | arbitrary_file_read | arbitrary_file_delete | path_traversal | auth_bypass | csrf | info_leak | other",
      "severity": "critical | high | medium | low",
      "exploitable_without_auth": false,
      "precondition": "攻击者需要什么才能利用：是否需要管理员登录、是否需要插件启用、是否需要诱导受害者",
      "evidence": "触发路径：哪个参数 → 经过哪个函数 → 哪一行校验失效 → 最终到达什么危险操作",
      "fix": "具体改法（改哪个函数、加什么语句），不要写'加强校验'这类空话"
    }
  ]
}
```

另写 `summary.md`（不超过 400 字）：

1. 这个插件对**路径**做了哪些约束，你认为够不够（指出具体的函数与行）
2. 最严重的问题是什么（一句话）
3. 有没有你**没能确认**的，需要什么信息才能确认

## 评审口径

- **位置准确**：`file` + `line` 必须指向真实存在的位置，偏差不超过 20 行
- **必须走完数据流**：看到 `Request.QueryString` 进文件操作只算"可疑"。要确认中间
  **确实有一道生效的校验**才算安全。"有个校验函数被调用了"本身不构成理由——
  必须指出它是怎么挡住数据的。
- **反过来也一样**：判定某处"安全"时，要指出是哪一行、哪条语句挡住的，
  不能靠"应该会有校验"来推断
- **配置依赖要写进 precondition**：需要管理员登录、需要插件启用、需要特定配置的，
  照常报告并写清条件，同时标 `exploitable_without_auth: false`。
  **因为"默认没开"就不报，与漏报同价**——部署方会按你的清单决定要不要开那个功能
- **修复建议可执行**：指出改哪个函数、加什么语句

## 预算

- 范围只有 1,725 行，**足够逐行读完**，不需要抽样
- 静态审计，不要运行系统，不要修改源码

