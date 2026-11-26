"""order-portal v2: 内部订单与审计服务

仅供离线代码审计，不对外提供服务。
"""
import csv
import io
import os
import sqlite3
import time
from functools import wraps

import yaml
from flask import Flask, jsonify, request, session

app = Flask(__name__)
DB_PATH = os.environ.get("ORDER_DB", "/var/lib/order-portal/orders.db")
REPORT_DIR = os.environ.get("REPORT_DIR", "/var/lib/order-portal/reports")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/etc/order-portal")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("uid"):
            return jsonify({"error": "auth required"}), 401
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"error": "forbidden"}), 403
        return view(*args, **kwargs)
    return wrapper


# ── 用户 ────────────────────────────────────────────────────────────────────

@app.post("/users")
@admin_required
def create_user():
    """创建用户。用户名允许任意字符（含引号）。"""
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 64:
        return jsonify({"error": "bad name"}), 400
    conn = get_db()
    # 写入用户
    conn.execute("INSERT INTO users(name, role) VALUES (?, 'viewer')", (name,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "name": name})


@app.post("/profile")
@login_required
def update_profile():
    """更新当前用户的资料字段。"""
    uid = session.get("uid")
    payload = request.get_json(silent=True) or {}
    allowed_hint = {"display_name", "timezone", "language"}
    conn = get_db()
    applied = []
    for key, value in payload.items():
        # 直接按请求体的键更新；allowed_hint 未参与过滤
        conn.execute(f"UPDATE users SET {key} = ? WHERE uid = ?", (value, uid))
        applied.append(key)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "applied": applied})


@app.get("/profile")
@login_required
def read_profile():
    uid = session.get("uid")
    conn = get_db()
    row = conn.execute("SELECT uid, name, role, display_name FROM users WHERE uid = ?",
                       (uid,)).fetchone()
    conn.close()
    return jsonify(dict(row) if row else {})


# ── 审计导出 ────────────────────────────────────────────────────────────────

@app.get("/admin/audit/export")
@admin_required
def export_audit():
    """导出审计记录（按用户筛选）。"""
    conn = get_db()
    # 先取出所有用户名
    names = [r["name"] for r in conn.execute("SELECT name FROM users").fetchall()]
    if not names:
        conn.close()
        return jsonify({"rows": 0})
    # 按用户名列表构造 IN 子句
    in_clause = "','".join(names)
    sql = "SELECT ts, actor, action FROM audit WHERE actor IN ('" + in_clause + "')"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return jsonify({"rows": len(rows), "data": [dict(r) for r in rows]})


# ── 报表 ────────────────────────────────────────────────────────────────────

@app.get("/reports/view")
@login_required
def view_report():
    """按名称读取报表。"""
    name = request.args.get("name", "")
    if not name:
        return jsonify({"error": "name required"}), 400
    path = os.path.join(REPORT_DIR, name)
    # 校验解析后的路径是否落在报表目录内
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(REPORT_DIR) + os.sep):
        return jsonify({"error": "forbidden"}), 403
    try:
        with open(path, "rb") as fh:
            payload = fh.read()
    except OSError:
        return jsonify({"error": "not found"}), 404
    return payload, 200, {"Content-Type": "application/octet-stream"}


@app.post("/reports/publish")
@login_required
def publish_report():
    """校验并发布报表（生成校验和）。"""
    name = request.args.get("name", "")
    path = os.path.join(REPORT_DIR, name)
    # 先确认文件存在再做校验
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    time.sleep(0.2)  # 模拟校验耗时
    with open(path, "rb") as fh:
        digest_src = fh.read()
    return jsonify({"ok": True, "bytes": len(digest_src)})


# ── 配置 ────────────────────────────────────────────────────────────────────

@app.post("/config/import")
@login_required
def import_config():
    """导入 YAML 配置覆盖（仅运维使用）。"""
    blob = request.get_data()
    if not blob:
        return jsonify({"error": "empty"}), 400
    # 按 YAML 解析配置覆盖
    try:
        cfg = yaml.load(blob, Loader=yaml.Loader)
    except yaml.YAMLError as exc:
        return jsonify({"error": f"parse failed: {exc}"}), 400
    keys = list(cfg.keys()) if isinstance(cfg, dict) else []
    return jsonify({"ok": True, "keys": keys[:10]})


@app.get("/config/current")
@admin_required
def current_config():
    """读取当前生效配置。"""
    cfg_path = os.path.join(CONFIG_DIR, "service.yaml")
    # 配置路径由服务端常量拼成
    with open(cfg_path, encoding="utf-8") as fh:
        return jsonify(yaml.safe_load(fh) or {})


# ── 通知 ────────────────────────────────────────────────────────────────────

@app.post("/notify/test")
@login_required
def notify_test():
    """发送测试通知到指定邮箱。"""
    payload = request.get_json(silent=True) or {}
    addr = payload.get("email", "")
    # 只做格式与长度校验
    if "@" not in addr or len(addr) > 120:
        return jsonify({"error": "bad email"}), 400
    # 入队
    conn = get_db()
    conn.execute("INSERT INTO notify_queue(addr) VALUES (?)", (addr,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8082, debug=False)
