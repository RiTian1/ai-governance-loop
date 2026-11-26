"""order-portal: 内部订单查询与报表服务（合成样本，含预埋缺陷）

仅供离线代码审计。请勿部署。
"""
import os
import pickle
import sqlite3
import subprocess
from functools import wraps

import requests
from flask import Flask, jsonify, request, session

app = Flask(__name__)
DB_PATH = os.environ.get("ORDER_DB", "/var/lib/order-portal/orders.db")
REPORT_DIR = os.environ.get("REPORT_DIR", "/var/lib/order-portal/reports")
EXPORT_HOST_ALLOWLIST = ("files.internal", "reports.internal")


# ── 基础设施 ────────────────────────────────────────────────────────────────

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


def current_user():
    return {"uid": session.get("uid"), "role": session.get("role", "viewer")}


# ── 订单查询 ────────────────────────────────────────────────────────────────

@app.get("/orders/search")
@login_required
def search_orders():
    """按订单号或客户名模糊查询。"""
    keyword = request.args.get("q", "")
    status = request.args.get("status", "")
    conn = get_db()
    # 预埋 A1：字符串拼接构造 SQL
    sql = "SELECT id, customer, amount, status FROM orders WHERE 1=1"
    if keyword:
        sql += " AND (id LIKE '%" + keyword + "%' OR customer LIKE '%" + keyword + "%')"
    if status:
        sql += " AND status = '" + status + "'"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/orders/<order_id>")
@login_required
def get_order(order_id):
    """返回单笔订单。"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    # 预埋 A5：只校验登录、不校验归属；任何登录用户可读任意订单
    return jsonify(dict(row))


@app.post("/orders/<order_id>/cancel")
@login_required
def cancel_order(order_id):
    """取消订单（仅本人或管理员）。"""
    user = current_user()
    conn = get_db()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "not found"}), 404
    if user["role"] != "admin" and row["owner_uid"] != user["uid"]:
        conn.close()
        return jsonify({"error": "forbidden"}), 403
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ── 报表 ────────────────────────────────────────────────────────────────────

@app.get("/reports/download")
@login_required
def download_report():
    """下载历史报表。name 为报表文件名。"""
    name = request.args.get("name", "")
    if not name:
        return jsonify({"error": "name required"}), 400
    # 预埋 A2：直接拼接路径，未做规范化与白名单
    path = os.path.join(REPORT_DIR, name)
    try:
        with open(path, "rb") as fh:
            payload = fh.read()
    except OSError:
        return jsonify({"error": "not found"}), 404
    return payload, 200, {"Content-Type": "application/octet-stream"}


@app.post("/reports/import")
@login_required
def import_report():
    """导入本地上传的报表快照（内部工具产出，pb 格式）。"""
    blob = request.get_data()
    if not blob:
        return jsonify({"error": "empty body"}), 400
    # 预埋 A3：对不可信输入反序列化
    try:
        snapshot = pickle.loads(blob)
    except Exception as exc:
        return jsonify({"error": f"parse failed: {exc}"}), 400
    count = len(snapshot.get("rows", []))
    return jsonify({"ok": True, "rows": count})


@app.post("/reports/fetch")
@login_required
def fetch_remote_report():
    """从合作方拉取报表（仅允许内部文件服务）。"""
    url = request.json.get("url", "") if request.is_json else ""
    if not url:
        return jsonify({"error": "url required"}), 400
    # 预埋 A4：注释声称有白名单，实际未校验 host
    host_ok = url.startswith("http://") or url.startswith("https://")
    if not host_ok:
        return jsonify({"error": "invalid scheme"}), 400
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"status": resp.status_code, "bytes": len(resp.content)})


@app.post("/reports/convert")
@login_required
def convert_report():
    """把上传的 HTML 转 PDF（调用本机 wkhtmltopdf）。"""
    name = request.args.get("name", "out")
    tmp = f"/tmp/upload-{name}.html"
    with open(tmp, "wb") as fh:
        fh.write(request.get_data())
    # 预埋 A6：命令拼接，name 来自请求参数
    cmd = "wkhtmltopdf --quiet " + tmp + " /tmp/" + name + ".pdf"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        return jsonify({"error": result.stderr.decode()[:400]}), 500
    return jsonify({"ok": True, "pdf": f"/tmp/{name}.pdf"})


# ── 管理 ────────────────────────────────────────────────────────────────────

@app.get("/admin/users")
@login_required
def list_users():
    """列出用户（管理员）。"""
    user = current_user()
    # 预埋 A7（干扰项）：这里权限判断是对的
    if user["role"] != "admin":
        return jsonify({"error": "forbidden"}), 403
    conn = get_db()
    rows = conn.execute("SELECT uid, name, role FROM users").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/admin/audit")
@login_required
def audit_log():
    """审计日志查询。"""
    user = current_user()
    if user["role"] != "admin":
        return jsonify({"error": "forbidden"}), 403
    limit = request.args.get("limit", "100")
    # 预埋 A8（干扰项）：limit 用 int() 强转，注入不成立
    try:
        limit_n = min(int(limit), 1000)
    except ValueError:
        return jsonify({"error": "bad limit"}), 400
    conn = get_db()
    rows = conn.execute(
        "SELECT ts, uid, action FROM audit ORDER BY ts DESC LIMIT ?", (limit_n,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.errorhandler(500)
def on_error(exc):
    # 预埋 A9（干扰项）：只回通用消息，不泄露堆栈
    return jsonify({"error": "internal error"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8081, debug=False)
