# 需求变更

## 标题

URL 黑名单批量删除接口支持容错解析 `ids`

## 背景

当前 `rasp_exception_url_black_batch_remove_*` 场景已覆盖：

- leading comma
- trailing comma
- double comma
- commas only
- mixed ids
- duplicate ids
- unknown ids
- second delete

现业务希望服务端统一容错：

- 自动忽略首尾逗号
- 自动忽略重复逗号产生的空片段
- 自动忽略纯空白片段
- 去重后若没有有效 ID，则返回参数错误

## 变更性质判断

这是规则语义变化，不是单纯的实现细节变更。
