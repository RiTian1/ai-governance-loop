#!/usr/bin/env python3
"""内容闸对抗测试集（cap.evidence.content，M3 证据）。

为什么不能只测"抓得住"
----------------------
内容闸有两个失败方向，任一都会让它形同虚设：

  漏报（false negative）—— 真凭据写进去了没拦住。**这是安全事件。**
  误报（false positive）—— 把口令哈希、示例值、类型注解判成凭据。
                            开发者被误报烦到忍无可忍时，会给整行加
                            `gov:allow-secret`，从此这道闸对该文件失效。

所以本测试集是**双向**的：`MUST_HIT` 的每一条都必须被抓，
`MUST_PASS` 的每一条都必须放行。只报一个方向的数字没有意义。

覆盖的是"真凭据在真实代码里的写法"，不是"正则能不能匹配我编的样例"。
每一条的形态都对应某种实际出现过的泄露方式（CI 配置、.env、脚本参数、
连接串、密钥文件、注释掉的旧密码）。

用法：
  python scripts/check_content_bypass.py          # 全部
  python scripts/check_content_bypass.py --list   # 只列样本
  python scripts/check_content_bypass.py --json

退出码：0 双向全对 / 1 有漏报或误报
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
cc = importlib.import_module("check_staged_content")

PROBE = "probe.txt"          # 非自扫描文件名，走完整规则

# ---------------------------------------------------------------- 必须抓到
# (编号, 场景说明, 单行内容)
MUST_HIT = [
    ("H01", "shell 赋值（最常见）",        'DB_PASSWORD="hunter2xyz"'),
    ("H02", "大写变量名",                  'PASSWORD="hunter2xyz"'),
    ("H03", "passwd 变体",                 'db_passwd: hunter2xyz'),
    ("H04", "api_key（下划线）",           'api_key = "sk-9f2b7c1d4e6a"'),
    ("H05", "apiKey（驼峰）",              'apiKey: "sk-9f2b7c1d4e6a"'),
    ("H06", "auth_token",                  'auth_token = "eyJhbGciOiJIUzI1NiJ9"'),
    ("H07", "client_secret",               'client_secret = "a1b2c3d4e5f6g7"'),
    ("H08", "JSON 配置",                   '  "password": "hunter2xyz",'),
    ("H09", "YAML 配置",                   'password: hunter2xyz'),
    ("H10", "单引号无空格",                "pwd='hunter2xyz'"),
    ("H11", "注释掉的旧密码（照样要拦）",  '# password = "hunter2xyz-legacy"'),
    ("H12", "AWS Access Key ID",           'aws_access_key_id = AKIAQWERTYUIOPASDFGH'),
    ("H13", "GitHub PAT",                  'token: ghp_0123456789abcdefghijklmnopqrstuvwxyz'),
    ("H14", "GitLab PAT",                  'CI_JOB_TOKEN=glpat-0123456789abcdefghij'),
    ("H15", "Authorization 头",            'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9abc'),
    ("H16", "连接串内嵌口令",               'url = "postgres://admin:p4ssw0rd@db.internal:5432"'),
    ("H17", "RSA 私钥头",                   '-----BEGIN RSA PRIVATE KEY-----'),
    ("H18", "OpenSSH 私钥头",               '-----BEGIN OPENSSH PRIVATE KEY-----'),
]

# ---------------------------------------------------------------- 必须放行
# 这些形态长得像凭据但不是。误报会让人加豁免标记，之后真泄露也拦不住。
MUST_PASS = [
    ("P01", "占位符尖括号",        'password = "<REDACTED>"'),
    ("P02", "枚举类型值",          'password = "string"'),
    ("P03", "显式示例值",          'password = "changeme"'),
    ("P04", "成员表达式引用",      'password = config.db_password'),
    ("P05", "环境变量引用",        'password = $DB_PASSWORD'),
    ("P06", "口令哈希描述",        'md5(password) = 5f4dcc3b5aa765d61d8327deb882cf99'),
    ("P07", "通配掩码",            'password: ******'),
    ("P08", "类型注解",            'def login(username: str, password: str) -> bool:'),
    ("P09", "掩码短值",            'pwd=***'),
    ("P10", "模板占位",            'password: {{ vault.db_password }}'),
]


def scan(text: str) -> list:
    return cc.scan_lines(PROBE, [(1, text)], {})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="内容闸对抗测试集（双向：漏报与误报都必须为 0）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true", help="只列样本")
    args = ap.parse_args(argv)

    if args.list:
        print("必须抓到：")
        for cid, why, text in MUST_HIT:
            print("  %-4s %-26s %s" % (cid, why, text.strip()))
        print("\n必须放行：")
        for cid, why, text in MUST_PASS:
            print("  %-4s %-26s %s" % (cid, why, text.strip()))
        return 0

    print("内容闸对抗测试集（双向）")
    print("样本：必须抓到 %d 条，必须放行 %d 条\n" % (len(MUST_HIT), len(MUST_PASS)))

    rows = []
    fn = []      # 漏报
    fp = []      # 误报

    for cid, why, text in MUST_HIT:
        hits = scan(text)
        ok = bool(hits)
        if not ok:
            fn.append(cid)
        rows.append({"id": cid, "expect": "hit", "ok": ok, "why": why})
        print("  %-4s 应抓  %-26s %s%s"
              % (cid, why, "命中" if ok else "!! 漏报",
                 ("  (%s)" % hits[0].kind) if ok else ""))

    print()
    for cid, why, text in MUST_PASS:
        hits = scan(text)
        ok = not hits
        if not ok:
            fp.append(cid)
        rows.append({"id": cid, "expect": "pass", "ok": ok, "why": why})
        print("  %-4s 应放  %-26s %s%s"
              % (cid, why, "放行" if ok else "!! 误报",
                 ("  (%s)" % hits[0].kind) if hits else ""))

    hit_ok = len(MUST_HIT) - len(fn)
    pass_ok = len(MUST_PASS) - len(fp)
    print("\n" + "=" * 70)
    print("抓得住：%d/%d   放得开：%d/%d" % (hit_ok, len(MUST_HIT), pass_ok, len(MUST_PASS)))
    if fn:
        print("漏报（安全事件）：%s" % ", ".join(fn))
    if fp:
        print("误报（会被加豁免标记，等于永久关闸）：%s" % ", ".join(fp))
    if args.json:
        print(json.dumps({"hit": [hit_ok, len(MUST_HIT)],
                          "pass": [pass_ok, len(MUST_PASS)],
                          "false_negative": fn, "false_positive": fp,
                          "cases": rows}, ensure_ascii=False, indent=1))
    print("=" * 70)
    return 0 if (not fn and not fp) else 1


if __name__ == "__main__":
    sys.exit(main())
