#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""opencode / lab 模型端点预检 —— 判"能不能真的推理"，不是"网关在不在"。

## 为什么需要这个

2026-11-24 补跑 6 个实验臂，两轮全部失败。诊断过程暴露一个口径错误：

    curl http://<host>:8080/v1/models   → HTTP 401 API_KEY_REQUIRED
    结论：服务在线，是模型不写文件

实际是**推理端点 100% 返回 502 Upstream service temporarily unavailable**。
`/v1/models` 由网关直接应答，不经过后端模型，它返回 401 只证明"网关活着"，
对"这次实验能不能跑"没有任何信息量。

于是一整轮 6 臂 × 2 次 = 12 次尝试全部空转，每次都写完 753 字节的错误日志才退出。

## 判据

**必须打到 `/v1/chat/completions`，且要求一次真实生成返回**：
- HTTP 200
- `choices[0].message.content`（或 `choices[0].text`）非空

只看到 200 不够——有的网关会把上游错误包成 `200 {"error":...}`；
只看到 `choices` 键不够——空数组也算"结构对但没内容"。

## 为什么要 --probe 全部成功才算通过

实验是长跑（50 臂 × ~9 分钟 ≈ 7.5 小时）。若单次成功率是 p，
50 臂全部成功的概率是 p^50。p=0.95 时只有 7.7%。所以"3 次里挂 1 次"
不是可接受抖动，是**整批实验几乎必然留缺口**的信号。

--probe 默认 3，要求全部成功；不满足就 exit 1，让外层批量脚本**拒绝启动**，
而不是跑完两小时才发现缺了 6 个臂。

## 用法

    python scripts/opencode_preflight.py --base-url http://<推理端点A>:8080/v1 \
        --model <模型> --api-key-env <推理端点>_KEY

    # 从 opencode 的 auth.json 直接读 provider 的 key
    python scripts/opencode_preflight.py --provider <推理端点> \
        --base-url http://<推理端点A>:8080/v1 --model <模型>

退出码：0 可用 / 1 不可用 / 2 参数或环境问题。
零依赖（urllib），Python 3.8+。
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _post(url, payload, api_key, timeout):
    """返回 (status, body_text)。网络异常时抛 RuntimeError。"""
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:                       # DNS / 拒绝 / 超时
        raise RuntimeError("%s: %s" % (type(e).__name__, e))


def _extract_text(body):
    """从 chat/completions 响应里取生成的文本；结构异常返回 None。"""
    try:
        d = json.loads(body)
    except ValueError:
        return None
    if isinstance(d.get("error"), dict):         # 网关把错误包成 200
        return None
    choices = d.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    c0 = choices[0] or {}
    msg = c0.get("message") or {}
    text = msg.get("content") or c0.get("text") or ""
    return text.strip() or None


def _classify(status, body):
    """把失败归到可操作的类别上，避免"服务挂了"这种没用的结论。"""
    if status in (401, 403):
        return "凭证失效（401/403）——检查 api key"
    if status == 404:
        return "端点或模型名不存在（404）——检查 --model 与 URL 路径"
    if status == 429:
        return "限流或欠费（429）"
    if status is not None and 500 <= status < 600:
        return "上游不可用（%d）——后端模型未加载或已挂" % status
    if status == 200:
        return "返回 200 但没有生成内容——契约异常或网关吞掉了错误"
    return "未预期的响应"


def _read_provider_key(provider):
    """从 opencode 的 auth.json 取 provider key。找不到返回 (None, 说明)。"""
    cands = [
        os.path.join(os.path.expanduser("~"), ".local", "share", "opencode", "auth.json"),
        os.path.join(os.path.expanduser("~"), ".config", "opencode", "auth.json"),
    ]
    for p in cands:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError) as e:
            return None, "读取 %s 失败：%s" % (p, e)
        entry = d.get(provider)
        if not isinstance(entry, dict):
            return None, "%s 里没有 provider %r（有：%s）" % (
                p, provider, ", ".join(sorted(d)) or "空")
        key = entry.get("key") or entry.get("apiKey")
        if not key:
            return None, "%s 的 %r 条目里没有 key 字段" % (p, provider)
        return key, p
    return None, "未找到 opencode auth.json"


def main(argv=None):
    ap = argparse.ArgumentParser(description="模型端点推理可用性预检")
    ap.add_argument("--base-url", required=True,
                    help="形如 http://host:8080/v1（不含 /chat/completions）")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=None, help="明文 key（尽量不用，优先 env/provider）")
    ap.add_argument("--api-key-env", default=None, help="从该环境变量读 key")
    ap.add_argument("--provider", default=None,
                    help="从 opencode auth.json 读该 provider 的 key")
    ap.add_argument("--probe", type=int, default=3,
                    help="探测次数，必须全部成功（默认 3）")
    ap.add_argument("--timeout", type=float, default=45.0, help="单次超时秒数")
    ap.add_argument("--interval", type=float, default=2.0, help="探测间隔秒数")
    args = ap.parse_args(argv)

    if args.probe < 1:
        print("ERROR: --probe 必须 >= 1", file=sys.stderr)
        return 2

    key = args.api_key
    key_src = "命令行参数" if key else None
    if not key and args.api_key_env:
        key = os.environ.get(args.api_key_env)
        key_src = "环境变量 %s" % args.api_key_env if key else None
        if not key:
            print("ERROR: 环境变量 %s 为空或未设置" % args.api_key_env, file=sys.stderr)
            return 2
    if not key and args.provider:
        key, src = _read_provider_key(args.provider)
        key_src = src if key else None
        if not key:
            print("ERROR: %s" % src, file=sys.stderr)
            return 2

    url = args.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
        "temperature": 0,
    }

    print("端点：%s" % url)
    print("模型：%s" % args.model)
    print("凭证：%s" % ("有（来源：%s，长度 %d）" % (key_src, len(key)) if key else "无"))
    print("要求：%d 次探测全部成功\n" % args.probe)

    ok_n = fail_n = 0
    reason = None
    for i in range(1, args.probe + 1):
        t0 = time.time()
        try:
            status, body = _post(url, payload, key, args.timeout)
        except RuntimeError as e:
            ok_n = 0
            fail_n = args.probe
            reason = "连接失败：%s" % e
            print("  try%d  连接失败  %s" % (i, e))
            break
        dt = time.time() - t0
        text = _extract_text(body) if status == 200 else None
        if status == 200 and text:
            ok_n += 1
            preview = text.replace("\n", " ")[:40]
            print("  try%d  200  %.2fs  -> %r" % (i, dt, preview))
        else:
            fail_n += 1
            if reason is None:
                reason = _classify(status, body)
            snippet = " ".join(body.split())[:110]
            print("  try%d  %-4s %.2fs  %s" % (i, status, dt, snippet))
        if i < args.probe:
            time.sleep(args.interval)

    print()
    if fail_n == 0 and ok_n == args.probe:
        print("结论：可用（%d/%d）" % (ok_n, args.probe))
        return 0

    print("结论：不可用（%d/%d 成功）" % (ok_n, args.probe))
    if reason:
        print("归因：%s" % reason)
    print("处置：不要启动批量实验。先修后端，或换 provider 并接受"
          "「换模型等于换实验」——旧结果不可与新结果合并。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
