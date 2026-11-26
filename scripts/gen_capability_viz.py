#!/usr/bin/env python3
"""生成治理能力成熟度可视化（雷达图 + 热力矩阵），供 GitHub 页面直接展示。

数据源：docs/governance-roadmap/CAPABILITY-MAP.yaml（唯一权威）
输出：
  docs/assets/capability-radar.svg     —— 六层 A-F 当前 vs 目标 雷达图
  docs/assets/capability-heatmap.svg   —— 逐能力 M0–M4 热力矩阵
  docs/assets/capability-maturity.json —— 机器可读评分（供徽章/CI）

零依赖：不引 pyyaml，用正则解析（结构固定）。纯标准库生成 SVG。

用法:
  python scripts/gen_capability_viz.py
  python scripts/gen_capability_viz.py --outdir docs/assets
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs/governance-roadmap/CAPABILITY-MAP.yaml"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _governance_yaml import safe_load as _yaml  # noqa: E402  零依赖

LEVELS = ["M0", "M1", "M2", "M3", "M4"]
LEVEL_VALUE = {"M0": 0, "M1": 1, "M2": 2, "M3": 3, "M4": 4}

LAYER_NAMES = {
    "A": "装配层 Assemble",
    "B": "载体链 Carrier chain",
    "C": "证据层 Evidence",
    "D": "知识层 Knowledge",
    "E": "执行层 Execution",
    "F": "协作层 Collaboration",
}


def repo_root() -> Path:
    return ROOT


def parse_caps(path: Path) -> list[dict]:
    """从 CAPABILITY-MAP.yaml 抽出 capabilities（id/layer/name/current/target/mechanism）。"""
    text = path.read_text(encoding="utf-8")
    data = _yaml(text)
    raw = data.get("capabilities", []) if isinstance(data, dict) else []
    caps = []
    for c in raw:
        caps.append({
            "id": c.get("id", ""),
            "name": c.get("name", ""),
            "layer": c.get("layer", ""),
            "current": c.get("current", "M0"),
            "target": c.get("target", "M4"),
            "mechanism": c.get("mechanism", []),
        })
    return caps


def layer_scores(caps: list[dict]) -> dict[str, dict]:
    """按层聚合：n / 当前均分 / 目标均分（归一到 0–1）。"""
    out: dict[str, dict] = {}
    for L in "ABCDEF":
        members = [c for c in caps if c["layer"] == L]
        if not members:
            continue
        n = len(members)
        cur = sum(LEVEL_VALUE[c["current"]] for c in members) / n / 4
        tgt = sum(LEVEL_VALUE[c["target"]] for c in members) / n / 4
        dist = {k: sum(1 for c in members if c["current"] == k) for k in LEVELS}
        out[L] = {"n": n, "current": round(cur, 3), "target": round(tgt, 3), "dist": dist}
    return out


# ---------- SVG: 雷达图 ----------
def radar_svg(scores: dict[str, dict]) -> str:
    # 画布加宽加高，标签外推；雷达中心下移+半径收小，
    # 让顶部「A·装配层」标签落在标题/副标题之下，避免与标题重叠。
    W = 900
    H = 700
    cx, cy = W // 2, 340
    R = 160
    layers = sorted(scores.keys())
    n = len(layers)
    import math

    def pt(i, frac, radius=R):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        return (cx + radius * frac * math.cos(ang), cy + radius * frac * math.sin(ang))

    def poly(fracs, radius=R):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, f, radius) for i, f in enumerate(fracs)))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">',
        f'<title id="t">治理能力成熟度雷达（当前 vs 目标）</title>',
        f'<desc id="d">A-F 六层，分数=层内能力平均成熟度归一化 M0=0 M4=1</desc>',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
    ]
    # 网格环
    for k in range(1, 5):
        frac = k / 4
        pts = poly([frac] * n)
        parts.append(f'<polygon points="{pts}" fill="none" stroke="#e5e0f0" stroke-width="1"/>')
        lx, ly = pt(0, frac)
        parts.append(f'<text x="{lx + 4}" y="{ly - 2}" font-size="10" fill="#a49fc0">{int(frac * 4)} ({frac:.2f})</text>')
    # 轴 + 标签（外推到 1.38R，标签用锚点随象限调整避免重叠）
    for i, L in enumerate(layers):
        x, y = pt(i, 1.0)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e5e0f0" stroke-width="1"/>')
        lx, ly = pt(i, 1.34)
        # 根据象限设置 text-anchor：上下居中，左右朝内
        ang = -math.pi / 2 + 2 * math.pi * i / n
        cos, sin = math.cos(ang), math.sin(ang)
        if abs(cos) < 0.3:
            anchor = "middle"
        elif cos > 0:
            anchor = "start"
        else:
            anchor = "end"
        # 标题行 + 数值行（分两行，避免标题盖住数值）
        parts.append(
            f'<text x="{lx:.1f}" y="{ly - 6:.1f}" font-size="14" font-weight="600" fill="#3a3466" text-anchor="{anchor}">'
            f'{L} · {LAYER_NAMES.get(L, "")}</text>'
        )
        s = scores[L]
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 12:.1f}" font-size="12" fill="#6a6390" text-anchor="{anchor}">'
            f'now {s["current"]:.2f} → goal {s["target"]:.2f} · n={s["n"]}</text>'
        )
    # 目标多边形（紫，虚线）
    tgt = [scores[L]["target"] for L in layers]
    parts.append(f'<polygon points="{poly(tgt)}" fill="#a48fe0" fill-opacity="0.10" stroke="#7a5fd0" stroke-width="2" stroke-dasharray="5,3"/>')
    for i, L in enumerate(layers):
        x, y = pt(i, tgt[i])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#7a5fd0"/>')
    # 当前多边形（深蓝紫，实线）
    cur = [scores[L]["current"] for L in layers]
    parts.append(f'<polygon points="{poly(cur)}" fill="#534ab7" fill-opacity="0.25" stroke="#3f3a8f" stroke-width="2.5"/>')
    for i, L in enumerate(layers):
        x, y = pt(i, cur[i])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#534ab7"/>')
        parts.append(f'<text x="{x + 7:.1f}" y="{y - 7:.1f}" font-size="12" font-weight="700" fill="#2f2a6b">{scores[L]["current"]:.2f}</text>')
    # 标题（放最上，避开顶部标签）
    parts.append(f'<text x="{W // 2}" y="46" font-size="19" font-weight="700" fill="#26215c" text-anchor="middle">治理能力成熟度雷达 · A–F 六层</text>')
    parts.append(f'<text x="{W // 2}" y="70" font-size="12" fill="#8a84b0" text-anchor="middle">分数 = 层内能力平均成熟度 / M4（M0=0 M4=1）；数据源 CAPABILITY-MAP.yaml</text>')
    # 图例（放底部，避开底部标签）
    parts.append(f'<rect x="{W // 2 - 110}" y="{H - 56}" width="26" height="16" fill="#534ab7" fill-opacity="0.25" stroke="#3f3a8f"/><text x="{W // 2 - 78}" y="{H - 44}" font-size="13" fill="#3a3466">当前 now</text>')
    parts.append(f'<rect x="{W // 2 + 10}" y="{H - 56}" width="26" height="16" fill="#a48fe0" fill-opacity="0.10" stroke="#7a5fd0" stroke-dasharray="4,2"/><text x="{W // 2 + 42}" y="{H - 44}" font-size="13" fill="#3a3466">目标 target</text>')
    parts.append("</svg>")
    return "\n".join(parts)


# ---------- SVG: 热力矩阵 ----------
# 紫色系（沿用早前"紫色那版"观感）：浅→深 紫/蓝紫 渐变
HEAT = {
    "M0": ("#ece4fb", "#5e4a9e"),   # 极浅紫
    "M1": ("#d6c8f5", "#4a3a86"),   # 浅紫
    "M2": ("#b9a3ec", "#3a2d6e"),   # 中紫
    "M3": ("#8f75dd", "#2a1f56"),   # 深紫
    "M4": ("#534ab7", "#ffffff"),   # 蓝紫（白字）
}


def heatmap_svg(caps: list[dict], scores: dict[str, dict]) -> str:
    layers = sorted(scores.keys())
    cell = 46
    pad_l, pad_t = 250, 110
    rowh = 30
    W = pad_l + len(layers) * cell + 210
    H = pad_t + len(caps) * rowh + 90
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">',
        f'<title id="t">治理能力成熟度热力矩阵（逐能力 M0–M4）</title>',
        f'<desc id="d">每行一个能力，按层分组；单元格颜色=当前成熟度</desc>',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        f'<text x="24" y="40" font-size="18" font-weight="700" fill="#111">治理能力成熟度热力矩阵 · 逐能力 M0–M4</text>',
        f'<text x="24" y="62" font-size="11" fill="#888">蓝框=已达成目标；灰=目标更高（仍有差距）。数据源 CAPABILITY-MAP.yaml</text>',
    ]
    # 表头
    for j, L in enumerate(layers):
        x = pad_l + j * cell
        parts.append(f'<rect x="{x}" y="{pad_t - 28}" width="{cell - 2}" height="24" rx="4" fill="#ece6f8"/>')
        parts.append(f'<text x="{x + (cell - 2) / 2}" y="{pad_t - 11}" font-size="12" font-weight="700" fill="#4a3a86" text-anchor="middle">{L}</text>')
    parts.append(f'<text x="{pad_l}" y="{pad_t - 36}" font-size="12" fill="#6a6390">成熟度 →</text>')
    # 行
    y = pad_t
    for c in caps:
        L = c["layer"]
        j = layers.index(L)
        bg, fg = HEAT.get(c["current"], ("#f1efeb", "#333"))
        reached = c["current"] == c["target"]
        stroke = '#7a5fd0' if reached else '#c9c2e0'
        sw = '2.5' if reached else '1'
        parts.append(f'<rect x="{pad_l + j * cell}" y="{y}" width="{cell - 2}" height="{rowh - 4}" rx="5" fill="{bg}" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(f'<text x="{pad_l + j * cell + (cell - 2) / 2}" y="{y + rowh / 2 - 2}" font-size="13" font-weight="700" fill="{fg}" text-anchor="middle">{c["current"]}</text>')
        name = c["name"]
        parts.append(f'<text x="20" y="{y + rowh / 2 - 1}" font-size="12" fill="#3a3466">{name}</text>')
        parts.append(f'<text x="20" y="{y + rowh / 2 + 12}" font-size="10" fill="#8a84b0">{c["id"]}</text>')
        arrow = '✓' if reached else f'→ {c["target"]}'
        parts.append(f'<text x="{pad_l + len(layers) * cell + 12}" y="{y + rowh / 2 + 4}" font-size="12" fill="{"#7a5fd0" if reached else "#a05a2c"}">{arrow}</text>')
        y += rowh
    # 图例
    ly = y + 30
    parts.append(f'<text x="24" y="{ly}" font-size="12" fill="#3a3466">图例：</text>')
    lx = 70
    for k in LEVELS:
        bg, fg = HEAT[k]
        parts.append(f'<rect x="{lx}" y="{ly - 14}" width="34" height="18" rx="4" fill="{bg}"/>')
        parts.append(f'<text x="{lx + 17}" y="{ly - 1}" font-size="12" font-weight="700" fill="{fg}" text-anchor="middle">{k}</text>')
        lx += 52
    parts.append(f'<rect x="{lx + 6}" y="{ly - 14}" width="20" height="18" rx="4" fill="#fff" stroke="#7a5fd0" stroke-width="2.5"/>')
    parts.append(f'<text x="{lx + 34}" y="{ly - 1}" font-size="12" fill="#3a3466">已达成目标</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def badge_maturity_svg(caps: list[dict]) -> str:
    """flat-style GitHub badge：`maturity | M2·14 M3·4`。"""
    dist = {k: sum(1 for c in caps if c["current"] == k) for k in LEVELS}
    shown = " ".join(f"{k}:{dist[k]}" for k in LEVELS if dist[k])
    label = "maturity"
    lw = len(label) * 7 + 12
    vw = len(shown) * 7 + 12
    W = lw + vw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="20" role="img" '
        f'aria-label="{label}: {shown}"><title>maturity: {shown}</title>'
        f'<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/></linearGradient>'
        f'<clipPath id="r"><rect width="{W}" height="20" rx="3" fill="#fff"/></clipPath>'
        f'<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/>'
        f'<rect x="{lw}" width="{vw}" height="20" fill="#1976d2"/>'
        f'<rect width="{W}" height="20" fill="url(#s)"/></g>'
        f'<g fill="#fff" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="{lw/2}" y="14" text-anchor="middle" font-weight="700">{label}</text>'
        f'<text x="{lw+vw/2}" y="14" text-anchor="middle">{shown}</text></g></svg>'
    )


def badge_layer_svg(scores: dict[str, dict]) -> str:
    """flat-style GitHub badge：`layer-avg | 0.39/1`。"""
    avg = sum(s["current"] for s in scores.values()) / len(scores)
    label = "layer-avg"
    val = f"{avg:.2f}/1"
    lw = len(label) * 7 + 12
    vw = len(val) * 7 + 12
    W = lw + vw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="20" role="img" '
        f'aria-label="{label}: {val}"><title>per-layer average: {val}</title>'
        f'<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/></linearGradient>'
        f'<clipPath id="r"><rect width="{W}" height="20" rx="3" fill="#fff"/></clipPath>'
        f'<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/>'
        f'<rect x="{lw}" width="{vw}" height="20" fill="#00897b"/>'
        f'<rect width="{W}" height="20" fill="url(#s)"/></g>'
        f'<g fill="#fff" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="{lw/2}" y="14" text-anchor="middle" font-weight="700">{label}</text>'
        f'<text x="{lw+vw/2}" y="14" text-anchor="middle">{val}</text></g></svg>'
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="生成治理能力成熟度可视化（雷达+热力矩阵+徽章）")
    p.add_argument("--outdir", default="docs/assets")
    p.add_argument("--check", action="store_true", help="仅校验（CI）：输出存在且新鲜即 0")
    args = p.parse_args(argv)

    if not MAP.exists():
        print(f"[X] 找不到 {MAP}", file=sys.stderr)
        return 2
    caps = parse_caps(MAP)
    if not caps:
        print("[X] 未能从能力地图解析出能力项", file=sys.stderr)
        return 1
    scores = layer_scores(caps)
    outdir = repo_root() / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    radar = outdir / "capability-radar.svg"
    heat = outdir / "capability-heatmap.svg"
    meta = outdir / "capability-maturity.json"
    badge_m = outdir / "badge-maturity.svg"
    badge_l = outdir / "badge-layer.svg"
    radar.write_text(radar_svg(scores), encoding="utf-8")
    heat.write_text(heatmap_svg(caps, scores), encoding="utf-8")
    badge_m.write_text(badge_maturity_svg(caps), encoding="utf-8")
    badge_l.write_text(badge_layer_svg(scores), encoding="utf-8")
    meta.write_text(
        json.dumps({
            "layers": scores,
            "caps_total": len(caps),
            "dist": {k: sum(1 for c in caps if c["current"] == k) for k in LEVELS},
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"[OK] {len(caps)} 能力 · {len(scores)} 层")
    for L in sorted(scores):
        s = scores[L]
        print(f"  {L} {LAYER_NAMES.get(L,''):24s} now {s['current']:.2f} → goal {s['target']:.2f}  (n={s['n']}) {s['dist']}")
    print(f"[i] {radar}\n[i] {heat}\n[i] {badge_m}\n[i] {badge_l}\n[i] {meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
