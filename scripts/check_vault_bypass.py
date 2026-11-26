#!/usr/bin/env python3
"""凭据保险箱的绕过测试集（cap.exec.vault，M3 证据）。

为什么要有它
------------
`cap.exec.vault` 停在 M2：「破坏性测试证明能抓到真实缺陷」。M2 的证据是
"曾经漏过一次"（第一版把 PEM 读坏了、审计可被 chmod 绕过）。

M3 要回答的是另一个问题：**防线在压力下是否成立**。这不是"再测一遍功能"，
而是按攻击面枚举——攻击者会尝试哪些路径，每一条都断言"必须被拒"，
且拒绝之后**状态没有被破坏、痕迹有留下**。

诚实边界（很重要）
------------------
本测试集只统计「系统承诺防住」的路径。以下三类**不计入 rejected**，
因为威胁模型里已明确写"不防"，把它们算成失败是自欺：

  1. 拿到 passphrase 的人 —— 可以解开全部条目（VAULT.md §7）
  2. 已沦陷主机上的内存取证 —— 明文在进程内存里
  3. 伪造 purpose —— purpose 是记账不是鉴权，给了假的也照样取走

第 3 条尤其要说清：这不是缺陷，是设计边界。把它算作"绕过成功"会让
整份报告失去意义；把它算作"被拒"则是造假。正确做法是**不列入**。

用法：
  python scripts/check_vault_bypass.py            # 跑全部
  python scripts/check_vault_bypass.py --json     # 机器可读
  python scripts/check_vault_bypass.py --list     # 只列攻击面

退出码：0 全部被拒 / 1 有绕过成功 / 2 环境不支持
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VAULT = HERE / "gov_vault.py"
PHRASE = "bypass-" + os.urandom(6).hex()
WRONG = "wrong-" + os.urandom(6).hex()
ENTRY = "prod/target"


# ---------------------------------------------------------------- 基础设施
class Ctx:
    """一条 case 的沙箱：独立 vault + 调用入口 + 断言工具。"""

    def __init__(self, root: Path, case_id: str) -> None:
        self.root = root
        self.home = root / case_id / "vault"
        self.case_dir = root / case_id
        self.case_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args, stdin=None, phrase=None):
        env = dict(os.environ)
        env["GOV_VAULT_HOME"] = str(self.home)
        env["GOV_VAULT_PASSPHRASE"] = phrase if phrase is not None else PHRASE
        env.pop("GOV_VAULT_PASSPHRASE_CMD", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run([sys.executable, str(VAULT), *args],
                              input=stdin, capture_output=True, env=env, timeout=120)

    def init(self):
        r = self.run(["init", "--kdf", "fast"])
        if r.returncode != 0:
            raise RuntimeError("init failed: %s" % r.stderr.decode("utf-8", "replace")[:200])

    def put(self, name=ENTRY, value=b"CANARY-plaintext-value", typ="password"):
        r = self.run(["put", name, "--type", typ, "--stdin"], stdin=value)
        if r.returncode != 0:
            raise RuntimeError("put failed: %s" % r.stderr.decode("utf-8", "replace")[:200])

    def audit_lines(self):
        p = self.home / "local" / "audit.log"
        if not p.exists():
            return []
        out = []
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
        return out

    def has_audit(self, action: str, result: str) -> bool:
        return any(a.get("action") == action and a.get("result") == result
                   for a in self.audit_lines())


def leaks(result) -> bool:
    """响应里是否泄露了明文。"""
    needle = b"CANARY-plaintext-value"
    return needle in (result.stdout or b"") or needle in (result.stderr or b"")


def is_root() -> bool:
    """root 不受文件权限约束——chmod 类攻击面对它根本不存在。

    这不是"系统防不住"，是"这个攻击面在该环境下无意义"。必须标为不适用
    并从 attempts 里排除；算成失败会让 Linux 服务器上的结论无端变差，
    算成通过则是造假。
    """
    try:
        return os.geteuid() == 0
    except AttributeError:      # Windows 无 geteuid
        return False


# ---------------------------------------------------------------- 攻击用例
# 每条返回 (是否被拒, 细节说明)。"被拒"= 退出码符合预期 且 无副作用。

def c_audit_dir_blocked_get(ctx: Ctx):
    """把 local/ 换成同名文件 → 审计写不进去 → get 必须拒绝。"""
    ctx.init(); ctx.put()
    local = ctx.home / "local"
    shutil.move(str(local), str(ctx.case_dir / "local.bak"))
    local.write_bytes(b"blocker")
    try:
        r = ctx.run(["get", ENTRY, "--purpose", "绕过审计取凭据"])
        ok = r.returncode == 5 and not leaks(r)
        return ok, "exit=%d 泄露=%s" % (r.returncode, leaks(r))
    finally:
        local.unlink()
        shutil.move(str(ctx.case_dir / "local.bak"), str(local))


def c_audit_dir_blocked_put(ctx: Ctx):
    """审计不可写时写入也必须拒绝（否则"改了但没记录"）。"""
    ctx.init(); ctx.put()
    local = ctx.home / "local"
    shutil.move(str(local), str(ctx.case_dir / "local.bak"))
    local.write_bytes(b"blocker")
    try:
        r = ctx.run(["put", ENTRY, "--type", "password", "--stdin"], stdin=b"new-value")
        ok = r.returncode == 5
        return ok, "exit=%d" % r.returncode
    finally:
        local.unlink()
        shutil.move(str(ctx.case_dir / "local.bak"), str(local))


def c_audit_file_readonly(ctx: Ctx):
    """audit.log 设只读 → 追加失败 → get 必须拒绝。"""
    if is_root():
        return None, "不适用：root 不受文件权限约束"
    ctx.init(); ctx.put()
    log = ctx.home / "local" / "audit.log"
    old = log.stat().st_mode
    os.chmod(str(log), 0o400 if os.name != "nt" else 0o444)
    try:
        r = ctx.run(["get", ENTRY, "--purpose", "绕过审计取凭据"])
        ok = r.returncode == 5 and not leaks(r)
        return ok, "exit=%d 泄露=%s" % (r.returncode, leaks(r))
    finally:
        os.chmod(str(log), old)


def c_audit_readonly_put_rollback(ctx: Ctx):
    """audit.log 只读时 put 必须拒绝，且**原值不被改动**（回滚）。"""
    if is_root():
        return None, "不适用：root 不受文件权限约束"
    ctx.init(); ctx.put()
    log = ctx.home / "local" / "audit.log"
    old = log.stat().st_mode
    os.chmod(str(log), 0o400 if os.name != "nt" else 0o444)
    try:
        r = ctx.run(["put", ENTRY, "--type", "password", "--stdin"],
                    stdin=b"REPLACED-by-attacker")
    finally:
        os.chmod(str(log), old)
    g = ctx.run(["get", ENTRY, "--purpose", "确认回滚生效"])
    kept = b"CANARY-plaintext-value" in (g.stdout or b"")
    replaced = b"REPLACED-by-attacker" in (g.stdout or b"")
    ok = r.returncode == 5 and kept and not replaced
    return ok, "put_exit=%d 原值保留=%s 被覆盖=%s" % (r.returncode, kept, replaced)


def c_cipher_bitflip(ctx: Ctx):
    """密文改一个字节 → GCM 认证失败。"""
    ctx.init(); ctx.put()
    p = next(iter((ctx.home / "entries").glob("*.enc")))
    raw = bytearray(p.read_bytes())
    raw[-1] ^= 0xFF
    p.write_bytes(bytes(raw))
    r = ctx.run(["get", ENTRY, "--purpose", "篡改后读取"])
    ok = r.returncode == 4 and not leaks(r) and ctx.has_audit("get", "decrypt_failed")
    return ok, "exit=%d 泄露=%s 留痕=%s" % (r.returncode, leaks(r),
                                            ctx.has_audit("get", "decrypt_failed"))


def c_cipher_swap(ctx: Ctx):
    """把 A 的密文复制成 B 的名字 → AAD 绑定条目名，必须失败。"""
    ctx.init()
    ctx.put("prod/a", b"CANARY-plaintext-value")
    ctx.put("prod/b", b"other-value")
    src = next(p for p in (ctx.home / "entries").glob("*.enc")
               if "prod%2Fa" in p.name)
    dst = next(p for p in (ctx.home / "entries").glob("*.enc")
               if "prod%2Fb" in p.name)
    shutil.copyfile(str(src), str(dst))
    r = ctx.run(["get", "prod/b", "--purpose", "重命名攻击"])
    ok = r.returncode == 4 and not leaks(r)
    return ok, "exit=%d 泄露=%s" % (r.returncode, leaks(r))


def c_cipher_truncated(ctx: Ctx):
    """密文截断 → 长度检查或 GCM 失败。"""
    ctx.init(); ctx.put()
    p = next(iter((ctx.home / "entries").glob("*.enc")))
    raw = p.read_bytes()
    p.write_bytes(raw[:len(raw) // 2])
    r = ctx.run(["get", ENTRY, "--purpose", "截断密文读取"])
    ok = r.returncode == 4 and not leaks(r)
    return ok, "exit=%d" % r.returncode


def c_meta_salt_tampered(ctx: Ctx):
    """meta 的 salt 改一字节 → 派生出的密钥不同 → 解密失败。"""
    ctx.init(); ctx.put()
    mp = ctx.home / "vault.meta.json"
    meta = json.loads(mp.read_text(encoding="utf-8"))
    salt = bytearray(base64.b64decode(meta["kdf"]["salt"]))
    salt[0] ^= 0xFF
    meta["kdf"]["salt"] = base64.b64encode(bytes(salt)).decode("ascii")
    # 不用 Path.write_text(newline=...)：那是 3.10+ 参数，macOS 自带 3.9 会 TypeError。
    # （这个坑在 gov_vault.py 里修过一次，本脚本第一版又踩了一次——所以有了
    #   check_gates_portability.py 的 3.9 API 静态扫描。）
    with open(str(mp), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(meta, ensure_ascii=False))
    r = ctx.run(["get", ENTRY, "--purpose", "改 salt 后读取"])
    ok = r.returncode == 4 and not leaks(r)
    return ok, "exit=%d" % r.returncode


def c_wrong_phrase_get(ctx: Ctx):
    """错误口令 → exit 4，且留 decrypt_failed 痕迹。"""
    ctx.init(); ctx.put()
    r = ctx.run(["get", ENTRY, "--purpose", "错误口令尝试"], phrase=WRONG)
    ok = r.returncode == 4 and not leaks(r) and ctx.has_audit("get", "decrypt_failed")
    return ok, "exit=%d 留痕=%s" % (r.returncode, ctx.has_audit("get", "decrypt_failed"))


def c_wrong_phrase_ls(ctx: Ctx):
    """错误口令连 ls 都不行（ls 需要解密条目元数据）。"""
    ctx.init(); ctx.put()
    r = ctx.run(["ls"], phrase=WRONG)
    ok = r.returncode != 0 and not leaks(r)
    return ok, "exit=%d" % r.returncode


def c_get_without_purpose(ctx: Ctx):
    """不带 --purpose → 拒绝，且不输出明文。"""
    ctx.init(); ctx.put()
    r = ctx.run(["get", ENTRY])
    ok = r.returncode == 2 and not leaks(r)
    return ok, "exit=%d 泄露=%s" % (r.returncode, leaks(r))


def c_get_blank_purpose(ctx: Ctx):
    """--purpose 只有空白 → 视为没写。"""
    ctx.init(); ctx.put()
    r = ctx.run(["get", ENTRY, "--purpose", "   "])
    ok = r.returncode == 2 and not leaks(r)
    return ok, "exit=%d" % r.returncode


def c_rm_without_yes(ctx: Ctx):
    """rm 无 --yes → 拒绝，且条目仍在。"""
    ctx.init(); ctx.put()
    r = ctx.run(["rm", ENTRY])
    still = ctx.run(["get", ENTRY, "--purpose", "确认条目仍在"])
    ok = r.returncode == 2 and still.returncode == 0 and leaks(still)
    return ok, "rm_exit=%d 条目仍可读=%s" % (r.returncode, still.returncode == 0)


def c_put_empty_overwrite(ctx: Ctx):
    """空内容 put → 拒绝，且原值未被清空。"""
    ctx.init(); ctx.put()
    r = ctx.run(["put", ENTRY, "--type", "password", "--stdin"], stdin=b"")
    still = ctx.run(["get", ENTRY, "--purpose", "确认原值未被清空"])
    ok = r.returncode != 0 and still.returncode == 0 and leaks(still)
    return ok, "put_exit=%d 原值保留=%s" % (r.returncode, leaks(still))


def c_entry_name_too_long(ctx: Ctx):
    """条目名编码后超过文件名上限 → 拒绝而不是写出畸形文件。"""
    ctx.init()
    r = ctx.run(["put", "x" * 121, "--type", "password", "--stdin"], stdin=b"v")
    ok = r.returncode == 2
    return ok, "exit=%d" % r.returncode


CASES = [
    ("A1", "审计侧", "local/ 不可写时 get 必须拒绝", c_audit_dir_blocked_get),
    ("A2", "审计侧", "local/ 不可写时 put 必须拒绝", c_audit_dir_blocked_put),
    ("A3", "审计侧", "audit.log 只读时 get 必须拒绝", c_audit_file_readonly),
    ("A4", "审计侧", "audit.log 只读时 put 拒绝且回滚", c_audit_readonly_put_rollback),
    ("B1", "密文侧", "密文单字节篡改", c_cipher_bitflip),
    ("B2", "密文侧", "密文换名（AAD 绑定条目名）", c_cipher_swap),
    ("B3", "密文侧", "密文截断", c_cipher_truncated),
    ("B4", "密钥侧", "meta 的 salt 被改", c_meta_salt_tampered),
    ("C1", "口令侧", "错误口令 get", c_wrong_phrase_get),
    ("C2", "口令侧", "错误口令 ls", c_wrong_phrase_ls),
    ("D1", "记账侧", "get 不带 --purpose", c_get_without_purpose),
    ("D2", "记账侧", "--purpose 只有空白", c_get_blank_purpose),
    ("E1", "破坏侧", "rm 无 --yes", c_rm_without_yes),
    ("E2", "破坏侧", "空内容 put 覆盖原值", c_put_empty_overwrite),
    ("F1", "输入侧", "条目名超长", c_entry_name_too_long),
]

NOT_DEFENDED = [
    "持有 passphrase 者可解开全部条目（威胁模型明确不防）",
    "已沦陷主机上的内存取证（明文在进程内存里）",
    "伪造 --purpose 后正常取用（purpose 是记账不是鉴权）",
]


# ---------------------------------------------------------------- 主流程
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="凭据保险箱绕过测试集（cap.exec.vault 的 M3 证据）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--list", action="store_true", help="只列攻击面")
    ap.add_argument("--keep", action="store_true", help="保留临时目录")
    args = ap.parse_args(argv)

    if args.list:
        for cid, surf, name, _ in CASES:
            print("%-4s %-8s %s" % (cid, surf, name))
        print("\n不计入统计（威胁模型已声明不防）：")
        for s in NOT_DEFENDED:
            print("  - %s" % s)
        return 0

    if not VAULT.exists():
        print("找不到 %s" % VAULT, file=sys.stderr)
        return 2

    root = Path(tempfile.mkdtemp(prefix="vault-bypass-"))
    print("保险箱绕过测试集")
    print("平台：%s  Python：%s" % (sys.platform, sys.version.split()[0]))
    print("临时目录：%s\n" % root)

    rows = []
    rejected = 0
    attempts = 0
    skipped = 0
    try:
        for cid, surf, name, fn in CASES:
            ctx = Ctx(root, cid)
            try:
                ok, detail = fn(ctx)
            except Exception as exc:
                ok, detail = False, "用例异常：%r" % (exc,)
            if ok is None:                      # 不适用：不计入 attempts
                skipped += 1
                rows.append({"id": cid, "surface": surf, "case": name,
                             "rejected": None, "detail": detail})
                print("  %-4s %-8s %-30s 不适用  %s" % (cid, surf, name, detail))
                continue
            attempts += 1
            rows.append({"id": cid, "surface": surf, "case": name,
                         "rejected": bool(ok), "detail": detail})
            if ok:
                rejected += 1
            print("  %-4s %-8s %-30s %s  %s"
                  % (cid, surf, name, "被拒" if ok else "!! 通过", detail))
    finally:
        if args.keep:
            print("\n临时目录保留：%s" % root)
        else:
            shutil.rmtree(str(root), ignore_errors=True)

    print("\n" + "=" * 68)
    print("attempts=%d  rejected=%d%s"
          % (attempts, rejected, "  （%d 条在本环境不适用）" % skipped if skipped else ""))
    print("不计入统计（威胁模型已声明不防）：")
    for s in NOT_DEFENDED:
        print("  - %s" % s)
    if args.json:
        print(json.dumps({"attempts": attempts, "rejected": rejected,
                          "skipped": skipped, "cases": rows,
                          "not_defended": NOT_DEFENDED},
                         ensure_ascii=False, indent=1))
    print("=" * 68)
    return 0 if (attempts > 0 and rejected == attempts) else 1


if __name__ == "__main__":
    sys.exit(main())
