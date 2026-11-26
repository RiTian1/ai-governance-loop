#!/usr/bin/env python3
"""直连 LLM 端点测纯推理性能：TTFT / 生成速率 / token 分解。

用途
----
配对测评里"总耗时"混杂了模型生成与编排开销（工具执行、上下文组装、决策往返）。
要判断治理效应，必须先把模型自身的速度测出来，再用它校准 case 耗时：

    编排开销 ≈ 总耗时 − output_tokens / TPS − steps × TTFT

opencode 的事件流只有事件级时间戳（`step_start`/`text`/`step_finish` 的
`timestamp` 在 tool-call 步还常常相等），无法算 token 级 TPS。因此本探针绕过
opencode，直接对 `/v1/chat/completions` 发 `stream=true` 请求。

凭据
----
不在本文件保存任何密钥。运行时通过环境变量注入：

    export LLM_BASE_URL=http://<host>:<port>
    export LLM_API_KEY=<redacted>
    export LLM_MODEL=<model-id>
    python3 scripts/probe_llm_perf.py

输出
----
默认写 `probe-perf.json`（可用 --out 覆盖）。每条记录含：

    total_ms / ttft_any_ms / ttft_content_ms / gen_ms
    prompt_tokens / completion_tokens / reasoning_tokens / content_tokens
    tps_content / tps_total / chunks / fingerprint

`ttft_any_ms` 是首个增量（含 reasoning）的时间，`ttft_content_ms` 是首个正式
正文的时间。reasoning 模型两者可能相差数秒。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

CASES = [
    ("short", "用一句话说明什么是向量检索。", 256),
    ("medium", "请用 200 字左右解释 Agent 记忆的四种主要路径（原生会话、外部检查点、"
               "事实检索、可晋升技能），并说明各自的适用场景。", 512),
    ("long", ("以下是一段技术材料，请用三句话总结其核心主张：\n\n"
              "Agent memory systems can be categorized along two axes: construction pipeline "
              "and retrieval pipeline. Empirical measurements show that long-context approaches "
              "incur latency growing linearly with history length, while embedded retrieval stays "
              "sub-linear. Retrieval-based approaches are inherently lossy for agent trajectories: "
              "atomic fact extraction discards action-state causation. Systems that mutate memory "
              "stores carry the highest poisoning risk—below a certain model capability threshold, "
              "the store can become corrupted. None of the evaluated systems prune or forget by "
              "default, so stale-but-relevant fragments can keep an agent following an already "
              "invalidated plan."), 512),
]


def probe(url: str, key: str, model: str, prompt: str, max_tokens: int, timeout: int) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    first_any = None
    first_content = None
    usage = None
    fingerprint = None
    chunks = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            chunks += 1
            if fingerprint is None and event.get("system_fingerprint"):
                fingerprint = event["system_fingerprint"]
            if event.get("usage"):
                usage = event["usage"]
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            has_reason = bool(delta.get("reasoning"))
            has_content = bool(delta.get("content"))
            if (has_reason or has_content) and first_any is None:
                first_any = time.time()
            if has_content and first_content is None:
                first_content = time.time()
    t_end = time.time()

    usage = usage or {}
    out_tokens = usage.get("completion_tokens") or 0
    reason_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    gen_anchor = first_content or first_any or t0
    rec = {
        "total_ms": round((t_end - t0) * 1000),
        "ttft_any_ms": round((first_any - t0) * 1000) if first_any else None,
        "ttft_content_ms": round((first_content - t0) * 1000) if first_content else None,
        "gen_ms": round((t_end - gen_anchor) * 1000),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": out_tokens,
        "reasoning_tokens": reason_tokens,
        "content_tokens": (out_tokens - reason_tokens) if out_tokens else None,
        "chunks": chunks,
        "fingerprint": fingerprint,
    }
    gen_s = rec["gen_ms"] / 1000 if rec["gen_ms"] else 0
    if gen_s > 0.05:  # 低于 50ms 视为缓冲抖动，不计算速率
        if rec["content_tokens"]:
            rec["tps_content"] = round(rec["content_tokens"] / gen_s, 2)
        if out_tokens:
            rec["tps_total"] = round(out_tokens / gen_s, 2)
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="直连 LLM 端点测 TTFT/TPS")
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("LLM_API_KEY"))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL"))
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", default="probe-perf.json")
    args = ap.parse_args(argv)

    missing = [n for n, v in (("--base-url/LLM_BASE_URL", args.base_url),
                              ("--api-key/LLM_API_KEY", args.api_key),
                              ("--model/LLM_MODEL", args.model)) if not v]
    if missing:
        print(f"缺少参数: {', '.join(missing)}", file=sys.stderr)
        return 2

    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    results = []
    for name, prompt, max_tokens in CASES:
        for i in range(args.repeat):
            try:
                rec = probe(url, args.api_key, args.model, prompt, max_tokens, args.timeout)
                rec.update({"case": name, "run": i + 1})
            except Exception as ex:  # noqa: BLE001
                rec = {"case": name, "run": i + 1, "error": f"{type(ex).__name__}: {ex}"}
            results.append(rec)
            print(json.dumps(rec, ensure_ascii=False))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ok = [r for r in results if "error" not in r and r.get("ttft_any_ms")]
    if ok:
        ttft = sorted(r["ttft_any_ms"] for r in ok)
        tps = sorted(r["tps_content"] for r in ok if r.get("tps_content"))
        print(f"\n有效样本 {len(ok)}/{len(results)}")
        print(f"TTFT(any) ms: min={ttft[0]} median={ttft[len(ttft)//2]} max={ttft[-1]}")
        if tps:
            print(f"TPS(content): min={tps[0]} median={tps[len(tps)//2]} max={tps[-1]}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
