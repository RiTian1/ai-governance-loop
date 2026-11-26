#!/usr/bin/env python3
"""零依赖 YAML 子集解析器（便携治理门禁的地基）。

为什么存在：治理母版会以 subtree 接入各类项目，**不能**要求每个项目都装
pyyaml。门禁脚本必须在"只有 python 标准库"的裸环境下也能跑。本模块提供
`safe_load(text)`：

  - 若环境已安装 pyyaml → 直接用它（更快、更全），作为"可选加速"；
  - 否则 → 退回到本文件的纯标准库解析器，覆盖治理工件实际使用的 YAML 子集：
      * 注释（整行 `#` 与行尾 ` #`）
      * 平铺 / 嵌套映射 `key: value`
      * 块列表  `- item`
      * 字典列表 `- key: value` + 后续同缩进键
      * 内联流式列表 `[a, b]` / 空列表 `[]`
      * 块标量 `|`（保留换行）与 `>`（折叠为空格）
      * 标量类型推断：int / float / bool / null / 字符串（含引号）

它**不是**完整 YAML 实现，只保证覆盖 `revisions/**/meta.yaml`、
`domains/**/_summary.yaml`、`revisions/index.yaml`、frontmatter 等现用结构。
"""
from __future__ import annotations

try:  # 可选加速：装了就用，没装走纯标准库回退（绝不因缺它而失效）
    import yaml as _pyyaml
except ImportError:  # pragma: no cover - 环境相关
    _pyyaml = None


def has_pyyaml() -> bool:
    return _pyyaml is not None


def safe_load(text: str):
    """解析 YAML 文本为 dict / list / 标量 / None。失败抛异常由调用方兜底。"""
    if _pyyaml is not None:
        return _pyyaml.safe_load(text)
    return _MiniYaml(text.splitlines()).parse_document()


# =============================================================
# 纯标准库回退解析器
# =============================================================

_NULLS = {"null", "Null", "NULL", "~", ""}
_TRUES = {"true", "True", "TRUE"}
_FALSES = {"false", "False", "FALSE"}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_trailing_comment(s: str) -> str:
    in_s = in_d = False
    depth = 0
    for idx, ch in enumerate(s):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch in "[{" and not in_s and not in_d:
            depth += 1
        elif ch in "]}" and not in_s and not in_d:
            depth -= 1
        elif ch == "#" and not in_s and not in_d and depth == 0:
            if idx == 0 or s[idx - 1] in (" ", "\t"):
                return s[:idx].rstrip()
    return s


def _split_flow(inner: str) -> list[str]:
    """按逗号切分内联流式集合内容，忽略括号 / 引号内的逗号。"""
    parts: list[str] = []
    buf: list[str] = []
    in_s = in_d = False
    depth = 0
    for ch in inner:
        if ch == "'" and not in_d:
            in_s = not in_s
            buf.append(ch)
        elif ch == '"' and not in_s:
            in_d = not in_d
            buf.append(ch)
        elif ch in "[{" and not in_s and not in_d:
            depth += 1
            buf.append(ch)
        elif ch in "]}" and not in_s and not in_d:
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0 and not in_s and not in_d:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_scalar(raw: str):
    s = raw.strip()
    if s in _NULLS:
        return None
    if s in _TRUES:
        return True
    if s in _FALSES:
        return False
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [] if not inner else [_parse_scalar(x) for x in _split_flow(inner)]
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        out: dict = {}
        if inner:
            for part in _split_flow(inner):
                k, sep, v = part.partition(":")
                if sep:
                    out[k.strip()] = _parse_scalar(v)
        return out
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


class _MiniYaml:
    def __init__(self, lines: list[str]):
        self.lines = lines
        self.n = len(lines)
        self.i = 0

    def _skip_insig(self, start: int):
        j = start
        while j < self.n:
            l = self.lines[j]
            if l.strip() == "" or l.lstrip().startswith("#"):
                j += 1
                continue
            return j
        return None

    def parse_document(self):
        j = self._skip_insig(0)
        if j is None:
            return None
        self.i = j
        indent = _indent(self.lines[j])
        if self.lines[j].strip().startswith("- "):
            return self._parse_list(indent)
        return self._parse_map(indent)

    def _parse_map(self, indent: int) -> dict:
        d: dict = {}
        while True:
            j = self._skip_insig(self.i)
            if j is None:
                break
            cur = _indent(self.lines[j])
            if cur != indent:
                break
            content = self.lines[j].strip()
            if content.startswith("- "):
                break
            self.i = j + 1
            self._consume_pair(d, content, indent)
        return d

    def _consume_pair(self, d: dict, content: str, indent: int) -> None:
        key, sep, rest = content.partition(":")
        if not sep:
            d[key.strip()] = None
            return
        key = key.strip()
        if len(key) >= 2 and key[0] == key[-1] and key[0] in ("'", '"'):
            key = key[1:-1]
        rest = rest.strip()
        if rest and rest[0] in ("|", ">"):
            d[key] = self._parse_block_scalar(indent, rest)
        elif rest == "":
            d[key] = self._parse_nested(indent)
        else:
            d[key] = _parse_scalar(_strip_trailing_comment(rest))

    def _parse_nested(self, parent_indent: int):
        j = self._skip_insig(self.i)
        if j is None:
            return None
        cur = _indent(self.lines[j])
        content = self.lines[j].strip()
        if content.startswith("- "):
            if cur >= parent_indent:
                return self._parse_list(cur)
            return None
        if cur > parent_indent:
            return self._parse_map(cur)
        return None

    def _parse_list(self, indent: int) -> list:
        items: list = []
        while True:
            j = self._skip_insig(self.i)
            if j is None:
                break
            cur = _indent(self.lines[j])
            if cur != indent:
                break
            raw = self.lines[j]
            content = raw.strip()
            if not content.startswith("-"):
                break
            after_dash = raw[cur + 1:]
            inline_col = cur + 1 + (len(after_dash) - len(after_dash.lstrip(" ")))
            after = content[1:].strip()
            self.i = j + 1
            if after == "":
                items.append(self._parse_nested(indent))
            elif _is_mapping_item(after):
                item: dict = {}
                self._consume_pair(item, after, inline_col)
                while True:
                    k2 = self._skip_insig(self.i)
                    if k2 is None:
                        break
                    c2 = _indent(self.lines[k2])
                    if c2 != inline_col:
                        break
                    l2 = self.lines[k2].strip()
                    if l2.startswith("- ") or ":" not in l2:
                        break
                    self.i = k2 + 1
                    self._consume_pair(item, l2, inline_col)
                items.append(item)
            else:
                items.append(_parse_scalar(_strip_trailing_comment(after)))
        return items

    def _parse_block_scalar(self, parent_indent: int, indicator: str) -> str:
        fold = indicator.lstrip()[0:1] == ">"
        collected: list[str] = []
        block_indent: int | None = None
        while self.i < self.n:
            line = self.lines[self.i]
            if line.strip() == "":
                collected.append("")
                self.i += 1
                continue
            ind = _indent(line)
            if ind <= parent_indent:
                break
            if block_indent is None:
                block_indent = ind
            collected.append(line[block_indent:] if len(line) >= block_indent else line.lstrip(" "))
            self.i += 1
        while collected and collected[-1] == "":
            collected.pop()
        if fold:
            return " ".join(collected)
        return "\n".join(collected)


def _is_mapping_item(after: str) -> bool:
    """判断 list item 文本是 `key: value` 映射还是普通标量。"""
    if after.startswith("[") or after.startswith("{"):
        return False
    if len(after) >= 1 and after[0] in ("'", '"'):
        return False
    idx = after.find(":")
    if idx < 0:
        return False
    rest = after[idx + 1:]
    return rest == "" or rest[0] in (" ", "\t")
