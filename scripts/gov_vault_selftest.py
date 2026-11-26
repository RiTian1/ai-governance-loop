#!/usr/bin/env python3
"""gov_vault 跨平台自测（Windows / macOS / Linux 通用）。

不碰真实仓库：全部动作在临时目录里完成，用 fast KDF 保证速度。

覆盖的是"换台机器就会炸"的地方，不是功能清单：
  1. 文本 / 多字节 / 特殊字符往返
  2. PEM 字节级往返（sha256 不变——历史上 read_text 的 CRLF 归一化就炸在这）
  3. 二进制往返（含 \\x00，模拟 .p12/.pfx）
  4. get --out / --field
  5. rotate 后旧口令失效、新口令可读
  6. 并发 put 不丢条目（flock / msvcrt.locking）
  7. 审计不可写时 get 必须失败（否则审计可被 chmod 绕过）
  8. 目录/文件权限（Unix 0700/0600；Windows ACL 无继承）
  9. 条目名编码往返（中文 / 斜杠 / 百分号 / 空格）+ 文件名纯 ASCII
 10. AAD 绑定条目名：密文换名必须解密失败
 11. v1 单文件库迁移
 12. doctor 退出码

退出码：0 全通过 / 1 有失败
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

HERE = Path(__file__).resolve().parent
VAULT = HERE / "gov_vault.py"
FAILED = []
PASSED = 0
PHRASE = "pw-" + os.urandom(8).hex()
NEW_PHRASE = "pw2-" + os.urandom(8).hex()


def say(msg: str) -> None:
    print(msg, flush=True)


def check(cond, label: str, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
        say("  ok   %s" % label)
    else:
        FAILED.append("%s %s" % (label, detail))
        say("  FAIL %s  %s" % (label, detail))


def run(args, *, stdin: bytes = None, phrase: str = None,
        home: Path = None, expect: int = 0, env_extra: dict = None):
    env = dict(os.environ)
    env["GOV_VAULT_PASSPHRASE"] = phrase if phrase is not None else PHRASE
    env["GOV_VAULT_HOME"] = str(home) if home else str(HOME)
    env.pop("GOV_VAULT_PASSPHRASE_CMD", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([sys.executable, str(VAULT), *args], input=stdin,
                       capture_output=True, env=env, timeout=180)
    if expect is not None and r.returncode != expect:
        say("     [cmd] %s" % " ".join(args))
        say("     [rc ] %d (expect %d)" % (r.returncode, expect))
        if r.stderr:
            say("     [err] %s" % r.stderr.decode("utf-8", "replace").strip()[:500])
    return r


def blob_of(r) -> bytes:
    return r.stdout


def test_basic() -> None:
    say("\n[1] init / 文本往返")
    r = run(["init", "--kdf", "fast"])
    check(r.returncode == 0, "init 成功", r.stderr.decode("utf-8", "replace")[:200])
    check((HOME / "vault.meta.json").exists(), "vault.meta.json 存在")
    check((HOME / "entries").is_dir(), "entries/ 目录存在")
    check((HOME / "local").is_dir(), "local/ 目录存在")
    check(not (HOME / "vault.bin").exists(), "不再生成单文件 vault.bin")

    payload = "p@ss w0rd-中文-ümlaut-€\ttab  \"quote\"\n".encode("utf-8")
    r = run(["put", "lab/单行", "--type", "password", "--stdin"], stdin=payload)
    check(r.returncode == 0, "put password")
    r = run(["get", "lab/单行", "--purpose", "自测往返"])
    check(r.returncode == 0, "get password")
    check(blob_of(r).rstrip(b"\r\n") == payload.rstrip(b"\r\n"),
          "单行凭据往返（尾部换行被裁）")

    r = run(["put", "lab/备注", "--type", "note", "--stdin"], stdin="首行\n次行\n".encode())
    r = run(["get", "lab/备注", "--purpose", "自测备注往返"])
    check(r.returncode == 0 and blob_of(r) == "首行\n次行\n".encode(),
          "note 原样保留换行")


def test_pem() -> None:
    say("\n[2] PEM 字节级往返")
    # 假 PEM，只为测换行/字节保真，不是真密钥
    pem = ("-----BEGIN " + "PRIVATE KEY-----\n"  # gov:allow-secret
           "MIIBVQIBADANBgkqhkiG9w0BAQEFAASCAT8wggE7AgEAAkEA0exampleFAKEonly\n"
           "aGVsbG8gd29ybGQgdGhpcyBpcyBub3QgYSByZWFsIGtleSBhdCBhbGwgMTIzNDU2\n"
           "-----END " + "PRIVATE KEY-----\n").encode("utf-8")  # gov:allow-secret
    src = TMP / "fake.key"
    src.write_bytes(pem)
    r = run(["put", "prod/tls-key", "--type", "private_key", "--file", str(src)])
    check(r.returncode == 0, "put private_key", r.stderr.decode("utf-8", "replace")[:200])

    out = TMP / "roundtrip.key"
    r = run(["get", "prod/tls-key", "--purpose", "核对密钥一致性", "--out", str(out)])
    check(r.returncode == 0, "get --out")
    check(out.read_bytes() == pem,
          "PEM 字节完全一致",
          "sha256 %s vs %s" % (hashlib.sha256(out.read_bytes()).hexdigest()[:12],
                               hashlib.sha256(pem).hexdigest()[:12]))

    # CRLF 版本也必须逐字保留
    crlf = pem.replace(b"\n", b"\r\n")
    src2 = TMP / "fake-crlf.key"
    src2.write_bytes(crlf)
    r = run(["put", "prod/tls-key-crlf", "--type", "private_key", "--file", str(src2)])
    out2 = TMP / "crlf.key"
    r = run(["get", "prod/tls-key-crlf", "--purpose", "核对 CRLF 保真", "--out", str(out2)])
    check(out2.read_bytes() == crlf, "CRLF 版 PEM 字节一致（未做换行归一化）")


def test_binary() -> None:
    say("\n[3] 二进制往返（.p12 模拟）")
    raw = bytes(range(256)) * 40 + b"\x00\x01\x02"
    src = TMP / "cert.p12"
    src.write_bytes(raw)
    r = run(["put", "prod/tls-keystore", "--type", "bundle", "--file", str(src)])
    check(r.returncode == 0, "put 二进制", r.stderr.decode("utf-8", "replace")[:200])
    out = TMP / "out.p12"
    r = run(["get", "prod/tls-keystore", "--purpose", "自测二进制往返", "--out", str(out)])
    check(r.returncode == 0 and out.read_bytes() == raw,
          "二进制字节一致（含 \\x00）",
          "len %d vs %d" % (len(out.read_bytes()) if out.exists() else -1, len(raw)))
    r = run(["meta", "prod/tls-keystore"])
    check(r.returncode == 0 and b'"enc": "b64"' in r.stdout, "meta 标出 enc=b64")


def test_json_field() -> None:
    say("\n[4] JSON 条目 --field")
    obj = json.dumps({"client_id": "abc123", "client_secret": "REDACTED"}).encode()
    run(["put", "gitlab/oauth", "--type", "bundle", "--stdin"], stdin=obj)
    r = run(["get", "gitlab/oauth", "--purpose", "CI 取 client_id", "--field", "client_id"])
    check(r.returncode == 0 and blob_of(r).strip() == b"abc123", "--field 取值")
    r = run(["get", "gitlab/oauth", "--purpose", "不存在的字段", "--field", "nope"],
            expect=1)
    check(r.returncode == 1, "缺字段返回 1")


def test_ls_meta_rm() -> None:
    say("\n[5] ls / meta / rm / purpose 强制")
    r = run(["ls"])
    check(r.returncode == 0 and "prod/tls-key".encode() in r.stdout, "ls 列出条目")
    check(PHRASE.encode() not in r.stdout, "ls 不回显任何值")
    r = run(["ls", "--json"])
    rows = json.loads(r.stdout.decode("utf-8"))
    check(any(x["name"] == "lab/单行" for x in rows), "ls --json 可解析")

    r = run(["get", "lab/单行", "--purpose", "ok"], expect=2)
    check(r.returncode == 2, "purpose 太短被拒")
    r = run(["get", "lab/单行"], expect=2)
    check(r.returncode == 2, "缺 purpose 被拒")

    r = run(["meta", "lab/单行"])
    check(r.returncode == 0 and b'"payload":' not in r.stdout, "meta 不含值")

    run(["put", "lab/临时", "--type", "token", "--stdin"], stdin=b"temporary")
    r = run(["rm", "lab/临时"], expect=2)
    check(r.returncode == 2, "rm 缺 --yes 被拒")
    r = run(["rm", "lab/临时", "--yes"])
    check(r.returncode == 0, "rm --yes 成功")
    r = run(["get", "lab/临时", "--purpose", "确认已删"], expect=1)
    check(r.returncode == 1, "删除后取不到")


def test_names() -> None:
    say("\n[6] 条目名编码（跨文件系统）")
    sys.path.insert(0, str(HERE))
    import gov_vault as gv  # noqa: E402

    tricky = ["中文/密钥", "a/b/c", "100%", "with space", "a.b-c_d", "Ünïcode/键"]
    for name in tricky:
        enc = gv.encode_entry_name(name)
        ok_ascii = all(ord(c) < 128 for c in enc)
        back = gv.decode_entry_name(enc)
        check(ok_ascii and back == name, "编码往返 %r" % name, "→ %s → %s" % (enc, back))

    payload = b"name-roundtrip"
    for name in tricky:
        r = run(["put", name, "--type", "token", "--stdin"], stdin=payload)
        if r.returncode != 0:
            check(False, "put %r" % name, r.stderr.decode("utf-8", "replace")[:200])
            continue
        r = run(["get", name, "--purpose", "验证特殊名读取"])
        check(r.returncode == 0 and blob_of(r).strip() == payload, "读取 %r" % name)

    files = list((HOME / "entries").iterdir())
    check(all(all(ord(c) < 128 for c in f.name) for f in files),
          "entries/ 下文件名全 ASCII（macOS NFD 不会打架）")


def test_aad_binding() -> None:
    say("\n[7] AAD 绑定条目名（重命名攻击）")
    sys.path.insert(0, str(HERE))
    import gov_vault as gv  # noqa: E402

    run(["put", "lab/aad-a", "--type", "token", "--stdin"], stdin=b"AAAA")
    run(["put", "lab/aad-b", "--type", "token", "--stdin"], stdin=b"BBBB")
    src = HOME / "entries" / gv.encode_entry_name("lab/aad-a")
    dst = HOME / "entries" / gv.encode_entry_name("lab/aad-b")
    shutil.copyfile(str(src), str(dst))
    r = run(["get", "lab/aad-b", "--purpose", "验证 AAD 绑定"], expect=4)
    check(r.returncode == 4, "密文换名后解密失败（exit 4）",
          r.stderr.decode("utf-8", "replace")[:200])
    # 恢复，供后续用例
    run(["put", "lab/aad-b", "--type", "token", "--stdin"], stdin=b"BBBB")


def test_rotate() -> None:
    global PHRASE
    say("\n[8] rotate：旧口令失效 / 新口令可读")
    r = run(["rotate", "--new-passphrase-file", str(TMP / "newpass.txt")])
    check(r.returncode != 0, "缺 --new-passphrase-file 文件时报错")
    np = TMP / "newpass.txt"
    np.write_text(NEW_PHRASE + "\n", encoding="utf-8")
    r = run(["rotate", "--new-passphrase-file", str(np), "--kdf", "fast"])
    check(r.returncode == 0, "rotate 成功", r.stderr.decode("utf-8", "replace")[:300])

    r = run(["get", "lab/单行", "--purpose", "旧口令应失败"], phrase=PHRASE, expect=4)
    check(r.returncode == 4, "旧口令被拒（exit 4）")
    r = run(["get", "lab/单行", "--purpose", "新口令应成功"], phrase=NEW_PHRASE)
    check(r.returncode == 0, "新口令可读")
    PHRASE = NEW_PHRASE


def test_concurrent() -> None:
    say("\n[9] 并发 put（写锁）")
    names = ["lab/conc-%d" % i for i in range(8)]

    def one(n):
        return run(["put", n, "--type", "token", "--stdin"], stdin=n.encode()).returncode

    with ThreadPoolExecutor(max_workers=8) as ex:
        codes = list(ex.map(one, names))
    check(all(c == 0 for c in codes), "8 个并发 put 全部成功", str(codes))
    r = run(["ls", "--json"])
    present = {x["name"] for x in json.loads(r.stdout.decode("utf-8"))}
    missing = [n for n in names if n not in present]
    check(not missing, "并发写入无丢条目", "missing=%s" % missing)


def test_audit_required() -> None:
    say("\n[10] 审计不可写时 get 必须失败")
    local = HOME / "local"
    backup = TMP / "local-backup"
    shutil.move(str(local), str(backup))
    local.write_bytes(b"blocker")   # 用同名文件占位，mkdir 会失败
    try:
        r = run(["get", "lab/单行", "--purpose", "验证审计强制"], expect=5)
        check(r.returncode == 5, "审计不可写 → exit 5 拒绝取用",
              r.stderr.decode("utf-8", "replace")[:300])
        r = run(["ls"])
        check(r.returncode == 0, "只读类操作（ls）不因审计失败而崩")
    finally:
        local.unlink()
        shutil.move(str(backup), str(local))


def test_permissions() -> None:
    say("\n[11] 权限（平台相关）")
    sys.path.insert(0, str(HERE))
    import gov_vault as gv  # noqa: E402

    if os.name == "nt":
        for d in (HOME, HOME / "entries", HOME / "local"):
            desc, ok = gv.perm_state(d, is_dir=True)
            check(ok, "Windows：%s ACL 已收紧" % d.name, desc)
            say("     (%s)" % desc)
        exe = shutil.which("icacls")
        if exe:
            r = subprocess.run([exe, str(HOME / "local" / "vault.lock")],
                               capture_output=True, text=True, errors="replace")
            out = r.stdout or ""
            check(out.count(":(") > 0, "锁文件 DACL 非空（曾因 /T 变裸文件）")
            check("Everyone" not in out and "BUILTIN\\Users" not in out,
                  "锁文件无宽泛主体")
    else:
        for d in (HOME, HOME / "entries", HOME / "local"):
            mode = stat.S_IMODE(d.stat().st_mode)
            check(mode == 0o700, "%s 权限 0700" % d.name, oct(mode))
        for f in (HOME / "vault.meta.json",):
            mode = stat.S_IMODE(f.stat().st_mode)
            check(mode == 0o600, "%s 权限 0600" % f.name, oct(mode))
        mode = stat.S_IMODE((HOME / "local" / "audit.log").stat().st_mode)
        check(mode == 0o600, "audit.log 权限 0600", oct(mode))


def test_migrate() -> None:
    say("\n[12] v1 单文件库迁移")
    v1home = TMP / "v1vault"
    v1home.mkdir()
    r = run(["init", "--kdf", "fast"], home=v1home)
    check(r.returncode == 0, "v1 容器 init")
    # 造一条 v2 条目，再手工合成 v1 单文件库
    run(["put", "lab/v1src", "--type", "token", "--stdin"], stdin=b"v1-payload", home=v1home)
    sys.path.insert(0, str(HERE))
    import gov_vault as gv  # noqa: E402
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    v = gv.Vault(v1home, PHRASE)
    meta = v._load_meta()
    entries = {}
    for n in v.entry_names():
        rec = v.load_entry(n)
        entries[n] = {"type": rec["type"], "secret": rec["payload"],
                      "created_at": rec.get("created_at"), "updated_at": rec.get("updated_at")}
    plain = json.dumps({"entries": entries}, ensure_ascii=False).encode("utf-8")
    nonce = os.urandom(12)
    old_aad = json.dumps({"magic": "GOVVAULT1", "version": 1, "kdf": meta["kdf"]},
                         sort_keys=True).encode("utf-8")
    ct = AESGCM(v._key_bytes()).encrypt(nonce, plain, old_aad)
    (v1home / "vault.bin").write_bytes(nonce + ct)
    for p in (v1home / "entries").glob("*.enc"):
        p.unlink()

    r = run(["doctor"], home=v1home)
    check(b"migrate" in r.stdout, "doctor 检出 v1 并提示 migrate")
    r = run(["migrate"], home=v1home)
    check(r.returncode == 0, "migrate 成功", r.stderr.decode("utf-8", "replace")[:300])
    r = run(["get", "lab/v1src", "--purpose", "验证迁移结果"], home=v1home)
    check(r.returncode == 0 and blob_of(r).strip() == b"v1-payload", "迁移后条目可读")
    check((v1home / "vault.bin.v1-migrated").exists(), "旧库重命名保留")


def test_doctor_and_audit() -> None:
    say("\n[13] doctor / audit")
    r = run(["doctor"])
    txt = r.stdout.decode("utf-8", "replace")
    check(r.returncode in (0, 1), "doctor 可运行", "rc=%d" % r.returncode)
    check("平台" in txt and "Python" in txt, "doctor 报平台与 Python 版本")
    check("条目数" in txt, "doctor 报条目数")

    r = run(["audit", "--tail", "50"])
    check(r.returncode == 0 and b"get" in r.stdout, "audit 有记录")
    check(PHRASE.encode() not in r.stdout, "审计日志不含口令")
    r = run(["audit", "--json", "--tail", "5"])
    ok = True
    for ln in r.stdout.decode("utf-8").splitlines():
        if ln.strip():
            try:
                json.loads(ln)
            except json.JSONDecodeError:
                ok = False
    check(ok, "audit --json 每行合法 JSON")

    r = run(["--version"])
    check(r.returncode == 0 and b"gov_vault" in r.stdout, "--version 可用")


def main() -> int:
    global TMP, HOME
    if not VAULT.exists():
        say("找不到 %s" % VAULT)
        return 1
    TMP = Path(tempfile.mkdtemp(prefix="govvault-selftest-"))
    HOME = TMP / ".gov-vault"
    say("临时目录：%s" % TMP)
    say("平台：%s  Python：%s" % (sys.platform, sys.version.split()[0]))
    try:
        for fn in (test_basic, test_pem, test_binary, test_json_field, test_ls_meta_rm,
                   test_names, test_aad_binding, test_rotate, test_concurrent,
                   test_audit_required, test_permissions, test_migrate,
                   test_doctor_and_audit):
            try:
                fn()
            except Exception as exc:  # 单个用例崩不影响其余
                FAILED.append("%s 抛异常：%r" % (fn.__name__, exc))
                say("  FAIL %s 抛异常：%r" % (fn.__name__, exc))
    finally:
        if os.environ.get("GOV_VAULT_KEEP_TMP"):
            say("\n保留临时目录：%s" % TMP)
        else:
            shutil.rmtree(str(TMP), ignore_errors=True)

    say("\n" + "=" * 56)
    say("通过 %d 项，失败 %d 项" % (PASSED, len(FAILED)))
    for f in FAILED:
        say("  ✗ %s" % f)
    say("=" * 56)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
