#!/usr/bin/env python3
r"""J3 代码审计任务的判据脚本。

用法
----
    python grade.py --findings <findings.json> --truth ground-truth.yaml
    python grade.py --findings f.json --truth gt.yaml --review   # 输出待复核项

判据（v2：分层）
---------------
GT 分 L1（必中）与 L2（加分）两层，见 ground-truth.yaml 顶部说明。

- 匹配：file 后缀一致 + |line - gt.line| ≤ 容差 + type 命中别名列表
- recall       = L1 命中数 / L1 总数          ← 唯一进达成判定的质量指标
- l2_bonus     = L2 命中数 / L2 总数          ← 只加分，不扣分
- precision    = 命中任意 GT 的 finding 数 / finding 总数
- fix_actionable = 命中的 finding 里，fix 含"可执行锚点"的比例
- score        = min(1.0, 0.5*recall + 0.3*precision + 0.2*fix + 0.1*l2_bonus)
- achieved     = recall ≥ 0.8 且 precision ≥ 0.6

为什么 recall 只算 L1：smoke 实测发现，把"真实但条件苛刻"的问题也算进必中，
会让 GT 覆盖不足被误读成模型能力不足（详见 SMOKE-20261119.md）。

零依赖：不引 pyyaml，用正则解析 ground-truth.yaml（结构固定）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 修复建议的"可执行锚点"：出现具体函数调用、具体语句、或具体标识
ACTIONABLE_PATTERNS = [
    r"Response\.End", r"\bExit\s+(Function|Sub)", r"白名单", r"allowlist",
    r"[A-Za-z_][A-Za-z0-9_]*\(", r"\.asp\b", r"Server\.", r"RegExp",
    r"参数化", r"parameteriz", r"GetFolder\(", r"Replace\(",
]
VAGUE_ONLY = re.compile(r"^(加强|增强|过滤|校验|验证|注意|严格|完善)+[\s。，,]*$")

ITEM_SPLIT = re.compile(r"^\s*-\s+id:\s*(GT-[A-Za-z0-9]+)\s*$", re.M)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def parse_truth(path: Path) -> dict:
    """从 ground-truth.yaml 抽出 items 与 scoring。

    yaml 结构固定（见文件本身），这里只取判据需要的字段，不追求通用解析。
    """
    text = read(path)
    items = []
    # 只解析 items: 段。rejected_items: 里也有 `- id: GT-xx`，
    # 若全文 split 会把被驳回的条目当必中项算进分母
    # （实测：GT-01 已驳回但 recall 仍是 1/6）。
    m_items = re.search(r"^items:\s*\n(.*?)(?=^[A-Za-z_]+:\s*$|\Z)", text, re.M | re.S)
    scope = m_items.group(1) if m_items else text
    parts = ITEM_SPLIT.split(scope)
    # split 结果：[前言, id1, 块1, id2, 块2, ...]
    for i in range(1, len(parts) - 1, 2):
        gid, block = parts[i], parts[i + 1]

        def grab(key: str) -> str | None:
            m = re.search(rf"^\s+{key}:\s*(.+?)\s*$", block, re.M)
            return m.group(1).strip() if m else None

        line_s = grab("line")
        alt_s = grab("line_alt")
        items.append({
            "id": gid,
            "tier": (grab("tier") or "L1").strip("'\"").upper(),
            "file": grab("file") or "",
            "line": int(line_s) if line_s and line_s.isdigit() else 0,
            # 可选多锚点：同一缺陷在代码里有多个合理落点（如"空壳校验函数"与"调用它的分发块"），
            # 命中任一即可。只在确实歧义时使用，避免整体放宽。
            "line_alt": [int(x) for x in re.findall(r"\d+", alt_s)] if alt_s else [],
            "type": (grab("type") or "").strip("'\""),
            # 可选第二类型：同一缺陷常有两种都正确的叫法
            # （重命名越界 = 任意文件写入 也算 路径穿越）。
            "type_alt": [x.strip().strip("'\"") for x in
                         re.findall(r"[a-z_]+", (grab("type_alt") or ""))],
            "severity": (grab("severity") or "").strip("'\""),
            "exploitable_without_auth": "true" in (grab("exploitable_without_auth") or "").lower(),
        })

    tol_m = re.search(r"line_tolerance:\s*(\d+)", text)
    tolerance = int(tol_m.group(1)) if tol_m else 5

    aliases: dict[str, list[str]] = {}
    alias_block = re.search(r"type_aliases:\s*\n((?:\s+\w+:.*\n|\s+\[.*\n)+)", text)
    if alias_block:
        for m in re.finditer(r"^\s+([a-z_]+):\s*\[([^\]]*)\]", alias_block.group(1), re.M):
            key = m.group(1)
            vals = [v.strip().strip("'\"") for v in m.group(2).split(",") if v.strip()]
            aliases[key] = vals

    return {"items": items, "tolerance": tolerance, "aliases": aliases}


def norm_type(t: str) -> str:
    return (t or "").strip().lower().replace("-", "_").replace(" ", "_")


# 粗粒度分组：真实审计报告对同一个缺陷会用不同词（"写 webshell" vs "任意文件写入"
# vs "RCE"），只靠同义词表会把这些合理叫法判成漏报。
# 实测：J3b 首轮 4 条 L1 里 3 条是因为标签不同被判漏，不是模型没看懂。
# 分组只解决"叫什么"，不解决"是不是"——位置仍受 ±tolerance 约束。
TYPE_GROUPS: dict[str, str] = {}
for _g, _members in {
    "WRITE": ("rce", "command_injection", "code_execution", "remote_code_execution",
              "arbitrary_file_write", "arbitrary_file_upload", "webshell_upload",
              "arbitrary_file_delete", "file_write", "arbitrary_file_edit",
              "arbitrary_file_rename", "arbitrary_file_operation", "file_delete"),
    "READ": ("arbitrary_file_read", "path_traversal", "lfi", "file_read",
             "arbitrary_file_download", "directory_traversal"),
    "CSRF": ("csrf", "xsrf", "cross_site_request_forgery"),
    "AUTHZ": ("auth_bypass", "broken_access_control", "access_control_bypass",
              "missing_authorization", "privilege_escalation"),
    "XSS": ("xss", "cross_site_scripting", "reflected_xss", "stored_xss",
            "script_injection", "js_injection", "client_side_injection"),
    "INFO": ("info_leak", "information_disclosure", "sensitive_data_exposure",
             "info_disclosure"),
}.items():
    for _m in _members:
        TYPE_GROUPS[_m] = _g


def type_match(finding_type: str, gt_type: str, aliases: dict) -> bool:
    ft = norm_type(finding_type)
    gt = norm_type(gt_type)
    if ft == gt:
        return True
    # 显式别名，双向都查（GT 侧写的别名 / 报告侧写的别名）
    if ft in [norm_type(x) for x in aliases.get(gt, [])]:
        return True
    if gt in [norm_type(x) for x in aliases.get(ft, [])]:
        return True
    # 粗粒度分组
    return TYPE_GROUPS.get(ft) is not None and TYPE_GROUPS.get(ft) == TYPE_GROUPS.get(gt)


def file_match(finding_file: str, gt_file: str) -> bool:
    a = (finding_file or "").replace("\\", "/").lstrip("./").lower()
    b = (gt_file or "").replace("\\", "/").lstrip("./").lower()
    return a.endswith(b) or b.endswith(a)


def fix_actionable(fix: str) -> bool:
    if not fix or len(fix.strip()) < 8:
        return False
    if VAGUE_ONLY.match(fix.strip()):
        return False
    return any(re.search(p, fix) for p in ACTIONABLE_PATTERNS)


EMPTY_PRECOND = re.compile(r"^\s*(无|none|null|n/?a|不需要|无需.*即可)?\s*$", re.I)


def has_precondition(pc: str) -> bool:
    """precondition 是否写成了有效内容。

    `无`/`None` 也算"有效填写"——未认证可达的问题本来就该写"无"。
    只有空字符串、纯空白、以及明显占位（"TODO"、"待确认"）算缺失，
    因为那说明作者没想过利用条件。
    """
    s = (pc or "").strip()
    if len(s) < 2:
        return False
    if s.upper() in ("TODO", "TBD", "待确认", "未知", "?"):
        return False
    return True


def grade(findings: list[dict], truth: dict, review: bool = False) -> dict:
    items = truth["items"]
    tol = truth["tolerance"]
    aliases = truth["aliases"]
    l1 = [i for i in items if i.get("tier") == "L1"]
    l2 = [i for i in items if i.get("tier") == "L2"]

    hit_findings: set[int] = set()
    per_item: list[dict] = []

    def match_tier(pool: list[dict], tier_name: str) -> list[str]:
        """一对一匹配：一个 finding 只能对应一个 GT。

        否则同文件相邻行的多个 GT（如 main.asp:63/65/66）会抢同一个 finding，
        导致 precision 被低估（实测：5 条全对时算出 0.8）。
        """
        hit_ids = []
        for gt in pool:
            best = None
            for idx, f in enumerate(findings):
                if idx in hit_findings:
                    continue
                if not file_match(f.get("file", ""), gt["file"]):
                    continue
                try:
                    fl = int(f.get("line") or 0)
                except (TypeError, ValueError):
                    continue
                anchors = [gt["line"]] + list(gt.get("line_alt") or [])
                if not anchors or min(abs(fl - a) for a in anchors) > tol:
                    continue
                gt_types = [gt["type"]] + list(gt.get("type_alt") or [])
                if not any(type_match(f.get("type", ""), t, aliases) for t in gt_types):
                    continue
                best = (idx, f)
                break
            if best:
                hit_ids.append(gt["id"])
                hit_findings.add(best[0])
                per_item.append({
                    "id": gt["id"], "tier": tier_name, "hit": True,
                    "reported_line": best[1].get("line"),
                    "reported_type": best[1].get("type"),
                    "fix_actionable": fix_actionable(best[1].get("fix", "")),
                    "has_precondition": has_precondition(best[1].get("precondition", "")),
                })
            else:
                per_item.append({"id": gt["id"], "tier": tier_name, "hit": False})
        return hit_ids

    l1_hit = match_tier(l1, "L1")
    l2_hit = match_tier(l2, "L2")

    recall = len(l1_hit) / len(l1) if l1 else 0.0
    bonus = len(l2_hit) / len(l2) if l2 else 0.0
    total_f = len(findings)
    precision = (len(hit_findings) / total_f) if total_f else 0.0

    hit_fixes = [p for p in per_item if p.get("hit")]
    fix_rate = (sum(1 for p in hit_fixes if p.get("fix_actionable")) / len(hit_fixes)) if hit_fixes else 0.0

    # 权重和为 1.0：0.45 + 0.25 + 0.20 + 0.10。
    # 早前用 0.5/0.3/0.2/0.1（和 = 1.1）导致 clamp 后掩盖差异——
    # 实测"漏 1 条 L2"和"全对 + 1 条误报"都显示 score=1.0。
    score = min(1.0, 0.45 * recall + 0.25 * precision + 0.20 * fix_rate + 0.10 * bonus)
    # 达成阈值只看 L1 recall + precision：
    # recall 漏报 40%（=0.6）仍判达成过于宽松，实测"只报对 3 条"也过线。
    achieved = recall >= 0.8 and precision >= 0.6

    fp = [f for i, f in enumerate(findings) if i not in hit_findings]

    # precondition 覆盖率：prompt 里要求"每条都写前置条件"，这一项单独度量。
    # 不计入 score（score 只反映审计结果），但它是"是否遵守输出契约"的直接证据。
    pc_ok = sum(1 for f in findings if has_precondition(f.get("precondition", "")))
    pc_cov = (pc_ok / total_f) if total_f else 0.0

    out = {
        "achieved": achieved,
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "fix_actionable": round(fix_rate, 3),
        "l2_bonus": round(bonus, 3),
        "score": round(score, 3),
        "precondition_coverage": round(pc_cov, 3),
        "l1_total": len(l1),
        "l1_hit": len(l1_hit),
        "l2_total": len(l2),
        "l2_hit": len(l2_hit),
        "findings_total": total_f,
        "per_item": per_item,
        "missed": [p["id"] for p in per_item if not p["hit"]],
    }
    if review:
        out["unmatched_findings"] = [
            {"file": f.get("file"), "line": f.get("line"), "type": f.get("type")}
            for f in fp[:30]
        ]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="J3 代码审计判据")
    ap.add_argument("--findings", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--review", action="store_true", help="额外输出未匹配项供人工复核")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    fp = Path(args.findings)
    if not fp.is_file():
        print(f"[error] 找不到 {fp}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(read(fp))
    except json.JSONDecodeError as e:
        print(f"[error] findings.json 解析失败: {e}", file=sys.stderr)
        return 2

    findings = payload.get("findings") if isinstance(payload, dict) else payload
    if not isinstance(findings, list):
        print("[error] findings 必须是数组", file=sys.stderr)
        return 2

    truth = parse_truth(Path(args.truth))
    if not truth["items"]:
        print("[error] ground-truth.yaml 里没解析到 items", file=sys.stderr)
        return 2

    result = grade(findings, truth, review=args.review)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
