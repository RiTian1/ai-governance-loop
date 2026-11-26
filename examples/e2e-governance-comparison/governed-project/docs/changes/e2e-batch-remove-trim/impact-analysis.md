# 影响分析

## 影响范围

- 批量删除接口参数解析逻辑
- URL 黑名单批量删除现有 E2E 语义
- 同类 IP 黑名单、URL 白名单、IP 白名单批量删除路径的语义一致性

## 受影响场景组

- `rasp_exception_url_black_batch_remove_leading_comma_behavior.yaml`
- `rasp_exception_url_black_batch_remove_trailing_comma_behavior.yaml`
- `rasp_exception_url_black_batch_remove_double_comma_behavior.yaml`
- `rasp_exception_url_black_batch_remove_commas_only_behavior.yaml`
- 同构的 `url` / `ip` / `ip_black` 场景族

## 必要动作

- 明确“哪些输入应成功容错，哪些输入应报错”
- 修订现有场景断言而不是只新增一个 happy path
- 输出变更到场景组的映射，供 CI 复用
