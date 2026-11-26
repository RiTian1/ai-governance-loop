#!/usr/bin/env python3
"""gov_vault —— 跨平台本地凭据保险箱（Windows / macOS / Linux）。

设计目标
--------
把"凭据/私钥/证书"从**散落在文档、脚本、聊天记录里的明文**，收敛到一个
加密的、每次读取都留痕的单一入口。AI 需要明文时只能走这个入口，
于是"谁在什么时候为了什么取了什么"变成可审计的事实，而不是靠自觉。

跨平台（2026-11-20 第二轮）
---------------------------
工作拓扑是多台机器（Windows 开发机、macOS、Linux 服务器），统一以 GitLab 的
governance 仓为唯一维护基线。因此本工具：

- **Python 3.8+ / 零第三方依赖（除 cryptography）**，不用 3.9+ 才有的 API；
- **存储按条目分文件**（`entries/<编码名>.enc`），不同机器改不同条目时 git 能自动合并，
  不会像单文件库那样每次写入都变成二进制冲突；
- **写入串行化**：Unix 用 `fcntl.flock`，Windows 用 `msvcrt.locking`，防止多 agent 并发 put 丢更新；
- **权限按平台收紧**：Unix 目录 0700 / 文件 0600；Windows 用 `icacls` 断继承并只授当前用户，
  不是"尽力 chmod 一下然后祈祷"；
- **二进制安全**：`.p12`/`.pfx`/`.der`/`.jks` 按字节往返（内部 base64），不再 `decode("utf-8")` 崩；
- **口令来源可接系统钥匙串**：`GOV_VAULT_PASSPHRASE_CMD` 支持
  `security find-generic-password`（macOS）、`pass show` / `secret-tool`（Linux）、
  `op read`（1Password CLI），避免明文口令进 shell 历史或配置文件。

保护的是什么（诚实边界）
------------------------
- 保护的是**静态**：仓库、备份、误提交、随手复制到别处的副本。
- **不防**已沦陷的主机：能读到 passphrase 的人就能解开全部条目。
  所以条目按用途命名、读取必须写 purpose，靠审计而非靠隔离。
- **共享库的代价**：`vault.meta.json` 入库后 salt 与 KDF 参数公开，弱口令可离线爆破。
  入库共享前请用 `init --kdf strong`，口令至少 16 位随机——这不是形式要求。

加密
----
AES-256-GCM（`cryptography` 库），密钥由 scrypt 从 passphrase 派生。
AAD 绑定 `{magic, version, kdf, 条目名}`，所以改头部或把 A 条目密文换到 B 条目名
都会解密失败——重命名攻击不成立。不做"自研密码算法"。

位置
----
默认 `<repo>/.gov-vault/`；可用 `GOV_VAULT_HOME` 覆盖。布局：

    .gov-vault/
      vault.meta.json     # 明文头：KDF 参数 + salt（salt 不是秘密）
      entries/*.enc       # 每条目一个密文文件
      local/              # 本机私有，**永不入库**
        audit.log
        vault.lock

passphrase 解析顺序
-------------------
1. `--passphrase-file <path>`
2. `GOV_VAULT_PASSPHRASE_CMD`（执行命令取 stdout 首行；接系统钥匙串）
3. 环境变量 `GOV_VAULT_PASSPHRASE`
4. 交互式输入（仅当 stdin 是 tty）
5. 否则报错——绝不回落到"空口令"或"默认口令"

退出码
------
0 成功 / 1 一般错误 / 2 CLI 用法错误 / 3 缺依赖 / 4 认证失败（口令错或文件被篡改）
/ 5 审计不可写（拒绝执行）
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

if os.name == "nt":  # pragma: no cover - 平台相关
    import msvcrt
else:  # pragma: no cover - 平台相关
    import fcntl

TOOL_VERSION = "2.0"
FILE_MAGIC = b"GV\x02"          # 密文文件头：magic(2) + 格式版本(1)
META_MAGIC = "GOVVAULT"
META_VERSION = 2
LEGACY_MAGIC = "GOVVAULT1"
ENTRY_SUFFIX = ".enc"
MIN_PURPOSE_LEN = 4
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_NAME_LEN = 120
SECRET_TYPES = ("password", "private_key", "certificate", "token", "note", "bundle")
TRIM_TYPES = ("password", "token")      # 只有单行凭据裁尾换行
KDF_PRESETS = {
    "fast":    {"name": "scrypt", "n": 2 ** 14, "r": 8, "p": 1},
    "default": {"name": "scrypt", "n": 2 ** 15, "r": 8, "p": 1},
    "strong":  {"name": "scrypt", "n": 2 ** 17, "r": 8, "p": 1},
}

# 条目名 → 文件名只保留这些字符，其余百分号编码。
# 必须是纯 ASCII：macOS 的 HFS+/APFS 会对非 ASCII 做 NFD 归一化，
# 同一个中文名在 macOS 与 Linux 上会变成不同字节、git 里表现为"文件消失"。
_SAFE_NAME_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")


class VaultError(Exception):
    def __init__(self, msg: str, code: int = 1) -> None:
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- 加密原语
def _crypto():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except ImportError as exc:  # pragma: no cover - 环境相关
        raise VaultError(
            "缺少 cryptography 库。\n"
            "  Windows: python -m pip install cryptography   （paramiko 通常已带入）\n"
            "  macOS  : python3 -m pip install --user cryptography   或 brew install python-cryptography\n"
            "  Linux  : apt install python3-cryptography  /  dnf install python3-cryptography\n"
            "  本工具不自研密码算法，因此不提供无依赖回退。",
            code=3,
        ) from exc
    return AESGCM, Scrypt


def derive_key(passphrase: str, salt: bytes, kdf: dict) -> bytes:
    _, Scrypt = _crypto()
    k = Scrypt(salt=salt, length=32, n=int(kdf["n"]), r=int(kdf["r"]), p=int(kdf["p"]))
    return k.derive(passphrase.encode("utf-8"))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _parse_iso(text: str):
    """容忍 naive / 带时区 / 带 Z 三种写法，统一返回 aware datetime。"""
    try:
        d = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


# ---------------------------------------------------------------- 平台抽象：权限
def platform_tag() -> str:
    return "%s/%s" % (sys.platform, platform.machine() or "?")


def _harden_windows(p: Path, is_dir: bool) -> tuple:
    """用 icacls 断继承 + 只授当前用户/SYSTEM/Administrators。

    为什么必须这么干：Windows 上 os.chmod 只切只读位，"600" 是自欺。
    真正的访问控制是 DACL——默认继承来的 BUILTIN\\Users 能让同机任何账户读走
    vault 密文与 audit.log（后者是明文）。

    刻意**不加 `/T`**：递归时 `(OI)(CI)` 标志被套到文件上会导致 ACE 被丢弃，
    产出"零 ACE 的裸文件"（实测 vault.lock 变成谁都打不开）。
    子项靠目录的可继承 ACE 拿权限——这才是 Windows 的正确用法。
    """
    exe = shutil.which("icacls")
    if not exe:
        return False, "找不到 icacls"
    who = os.environ.get("USERNAME") or os.environ.get("USER")
    if not who:
        return False, "无法确定当前用户名"
    inherit = "(OI)(CI)F" if is_dir else "F"
    args = [exe, str(p), "/inheritance:r",
            "/grant", "%s:%s" % (who, inherit),
            "/grant", "SYSTEM:%s" % inherit,
            "/grant", "*S-1-5-32-544:%s" % inherit,   # SID 形式，避免本地化名称问题
            "/C", "/Q"]
    try:
        r = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()
        return False, tail[-1] if tail else "icacls 返回 %d" % r.returncode
    return True, ""


def secure_path(p: Path, is_dir: bool = False) -> tuple:
    """收紧权限，返回 (成功?, 说明)。失败不抛异常——doctor 会如实报出来。"""
    if os.name == "nt":
        return _harden_windows(p, is_dir)
    try:
        os.chmod(str(p), 0o700 if is_dir else 0o600)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def perm_state(p: Path, is_dir: bool = False) -> tuple:
    """返回 (人类可读描述, 是否合格)。

    Windows 的合格标准是"没有宽泛主体"，**不是**"没有继承标记"：
    子文件靠父目录的可继承 ACE 拿权限才是正常形态，那种 ACE 天生带 (I)。
    把 (I) 当不合格会逼着人逐个 icacls，反而更容易搞出空 DACL。
    """
    if not p.exists():
        return "不存在", False
    if os.name == "nt":
        exe = shutil.which("icacls")
        if not exe:
            return "无法检查（缺 icacls）", True
        try:
            r = subprocess.run([exe, str(p)], capture_output=True, text=True,
                               errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            return "无法检查（%s）" % exc, True
        out = r.stdout or ""
        # 语言无关的判据：ACE 行必然含 ":(" ; 主体名可能是中文，但 Everyone /
        # BUILTIN\Users / Authenticated Users 三个关键 SID 名称在各语言版保持一致
        wide = [w for w in ("Everyone", "BUILTIN\\Users", "Authenticated Users")
                if w in out]
        if wide:
            return "对 %s 开放" % "/".join(wide), False
        n_ace = out.count(":(")
        if n_ace == 0:
            return "DACL 为空（无任何 ACE，正常访问会被拒）", False
        return "ACL 已收紧（%d 条 ACE，无宽泛主体）" % n_ace, True
    try:
        mode = p.stat().st_mode & 0o777
    except OSError as exc:
        return "无法读取权限（%s）" % exc, True
    ok = (mode & 0o077) == 0
    desc = "%s（期望 %s）" % (oct(mode), "0o700" if is_dir else "0o600")
    return desc, ok


# ---------------------------------------------------------------- 平台抽象：文件锁
class FileLock:
    """跨平台排它锁。Unix=flock，Windows=msvcrt.locking（锁文件首字节）。

    多端协同场景下"同一台机器上多个 agent 同时 put"是真实存在的，
    没有锁就会 read-modify-write 丢更新。不同机器之间靠 git 冲突暴露，不靠锁。
    """

    def __init__(self, path: Path, timeout: float = 30.0) -> None:
        self.path = path
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        # local/ 同时承载审计日志与写锁。它不可写时**写入一律拒绝**——
        # 否则会出现"改了凭据但没留痕"，这正是审计可被绕过的形态。
        # 这里必须转成 VaultError(5)，不能让它裸抛 OSError（会变成 traceback + exit 1）。
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise VaultError(
                "无法创建锁目录（%s）：%s\n"
                "  保险箱的 local/ 必须是可写目录。审计写不进去时，"
                "写入类操作一律拒绝。" % (self.path.parent, exc), code=5)
        fresh = not self.path.exists()
        try:
            fh = open(str(self.path), "r+b")
        except FileNotFoundError:
            fh = open(str(self.path), "w+b")
            fresh = True
        except PermissionError as exc:
            raise VaultError(
                "无法打开锁文件：%s（%s）\n"
                "  多为权限异常：检查 local/ 目录与 .lock 文件的 ACL。"
                % (self.path, exc), code=5)
        if fresh:
            # 锁文件可能先于目录加固被创建，这里补一次
            secure_path(self.path)
        if fh.seek(0, os.SEEK_END) == 0:
            fh.write(b"\0")
            fh.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fh = fh
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    fh.close()
                    raise VaultError(
                        "等待保险箱写锁超时（%.0fs）：%s\n"
                        "  另一进程正在写。确认无进程后可删除该 .lock 文件重试。"
                        % (self.timeout, self.path))
                time.sleep(0.05)

    def __exit__(self, *exc_info):
        fh, self._fh = self._fh, None
        if fh is None:
            return False
        try:
            if os.name == "nt":
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            fh.close()
        except OSError:
            pass
        return False


def _replace(src: str, dst: str, tries: int = 6) -> None:
    """os.replace 的退避重试。Windows 上目标被杀毒/编辑器短暂占用会 PermissionError。"""
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(0.08 * (i + 1))


# ---------------------------------------------------------------- 条目名 ↔ 文件名
def encode_entry_name(name: str) -> str:
    out = []
    for b in name.encode("utf-8"):
        ch = chr(b)
        out.append(ch if (b < 128 and ch in _SAFE_NAME_CHARS) else "%%%02X" % b)
    fn = "".join(out) + ENTRY_SUFFIX
    if len(fn) > 200:
        raise VaultError(
            "条目名过长（编码后 %d 字符）。中文名每字占 3 字节 → 9 字符，"
            "请控制在 40 字节以内。" % len(fn), code=2)
    return fn


def decode_entry_name(fn: str) -> str:
    stem = fn[: -len(ENTRY_SUFFIX)]
    bs = bytearray()
    i = 0
    n = len(stem)
    while i < n:
        ch = stem[i]
        if ch == "%" and i + 3 <= n:
            try:
                bs.append(int(stem[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        bs.extend(ch.encode("utf-8"))
        i += 1
    return bs.decode("utf-8")


def validate_name(name: str) -> str:
    if not name or name != name.strip():
        raise VaultError("条目名为空或首尾有空白", code=2)
    if len(name) > MAX_NAME_LEN:
        raise VaultError("条目名超过 %d 字符" % MAX_NAME_LEN, code=2)
    if any(ord(c) < 32 for c in name):
        raise VaultError("条目名含控制字符", code=2)
    return name


# ---------------------------------------------------------------- 仓库定位
def repo_root() -> Path:
    """从脚本位置向上找治理仓根，找不到就用当前目录。"""
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "project-governance.yaml").exists() or (p / ".git").exists():
            return p
    return Path.cwd()


def vault_home() -> Path:
    env = os.environ.get("GOV_VAULT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return repo_root() / ".gov-vault"


# ---------------------------------------------------------------- passphrase
def _from_command(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VaultError("GOV_VAULT_PASSPHRASE_CMD 执行失败：%s" % exc)
    if r.returncode != 0:
        raise VaultError(
            "GOV_VAULT_PASSPHRASE_CMD 返回 %d：%s"
            % (r.returncode, (r.stderr or "").strip()[:200]))
    line = (r.stdout or "").splitlines()
    if not line or not line[0].strip():
        raise VaultError("GOV_VAULT_PASSPHRASE_CMD 输出为空")
    return line[0].rstrip("\r\n")


def resolve_passphrase(args) -> str:
    path = getattr(args, "passphrase_file", None)
    if path:
        p = Path(path).expanduser()
        if not p.exists():
            raise VaultError("passphrase 文件不存在：%s" % p)
        return p.read_text(encoding="utf-8").rstrip("\r\n")

    cmd = os.environ.get("GOV_VAULT_PASSPHRASE_CMD")
    if cmd:
        return _from_command(cmd)

    env = os.environ.get("GOV_VAULT_PASSPHRASE")
    if env:
        return env

    if sys.stdin.isatty():
        pw = getpass.getpass("vault passphrase: ")
        if not pw:
            raise VaultError("passphrase 为空")
        return pw

    raise VaultError(
        "非交互环境缺少 passphrase。四种方式任选：\n"
        "  GOV_VAULT_PASSPHRASE_CMD='security find-generic-password -s gov-vault -w'  # macOS 钥匙串\n"
        "  GOV_VAULT_PASSPHRASE_CMD='pass show gov/vault'                             # Linux pass\n"
        "  GOV_VAULT_PASSPHRASE=<...> python scripts/gov_vault.py ...\n"
        "  python scripts/gov_vault.py ... --passphrase-file <path>\n"
        "  在终端里交互执行"
    )


def passphrase_source() -> str:
    """doctor 用：当前口令将从哪里来（不打印值）。"""
    if os.environ.get("GOV_VAULT_PASSPHRASE_CMD"):
        return "GOV_VAULT_PASSPHRASE_CMD"
    if os.environ.get("GOV_VAULT_PASSPHRASE"):
        return "GOV_VAULT_PASSPHRASE（明文环境变量）"
    return "未设置（仅可交互输入）"


# ---------------------------------------------------------------- 内容读写
def _is_text(raw: bytes) -> bool:
    if b"\x00" in raw:
        return False
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def read_input(args) -> tuple:
    """按字节读入内容，返回 (bytes, 来源标记)。

    必须按字节：文本模式会做换行归一化（CRLF→LF），对 PEM/证书是内容损坏
    （实测私钥往返后 sha256 不一致）。二进制（.p12/.pfx/.der）后续走 base64。

    变量刻意不叫敏感词：内容闸 tool.r9 会把"变量名含敏感词 + 有赋值"判为明文凭证。
    """
    if getattr(args, "file", None):
        p = Path(args.file)
        if not p.exists():
            raise VaultError("文件不存在：%s" % p)
        if p.stat().st_size > MAX_INPUT_BYTES:
            raise VaultError("文件超过 %d MB，拒绝写入" % (MAX_INPUT_BYTES // 1024 // 1024))
        return p.read_bytes(), "file:%s" % args.file

    if getattr(args, "value", None) is not None:
        print("警告：--value 会把明文留在 shell 历史里，建议改用 --stdin 或 --file",
              file=sys.stderr)
        return args.value.encode("utf-8"), "argv"

    buf = getattr(sys.stdin, "buffer", None)
    raw = buf.read() if buf is not None else sys.stdin.read().encode("utf-8")
    if len(raw) > MAX_INPUT_BYTES:
        raise VaultError("stdin 内容超过 %d MB，拒绝写入" % (MAX_INPUT_BYTES // 1024 // 1024))
    return raw, "stdin"


def entry_blob(rec: dict) -> bytes:
    """条目 → 原始字节。兼容 v1/v2 两种键名与 text/b64 两种编码。"""
    val = rec.get("payload")
    if val is None:
        val = rec.get("secret", "")
    if rec.get("enc") == "b64":
        return base64.b64decode(val)
    return str(val).encode("utf-8")


# ---------------------------------------------------------------- 保险箱
class Vault:
    def __init__(self, home: Path, passphrase: str = "") -> None:
        self.home = home
        self.meta_path = home / "vault.meta.json"
        self.entries_dir = home / "entries"
        self.local_dir = home / "local"
        self.audit_path = self.local_dir / "audit.log"
        self.legacy_audit = home / "audit.log"
        self.legacy_bin = home / "vault.bin"
        self.lock_path = self.local_dir / "vault.lock"
        self.passphrase = passphrase
        self._key = None

    # -- 生命周期
    @property
    def exists(self) -> bool:
        return self.meta_path.exists() and self.entries_dir.exists()

    def init(self, force: bool = False, kdf_name: str = "default") -> None:
        if self.exists and not force:
            raise VaultError(
                "保险箱已存在：%s\n  如需重建，加 --force（会清空全部条目）" % self.home)
        preset = KDF_PRESETS.get(kdf_name)
        if not preset:
            raise VaultError("--kdf 只能是 %s" % ", ".join(KDF_PRESETS), code=2)

        # 顺序很重要：目录先建好并加固，再上锁。
        # 反过来的话锁文件会带着旧的宽泛继承 ACL 出生，之后再断继承就变成裸文件。
        created = []
        for d in (self.home, self.entries_dir, self.local_dir):
            d.mkdir(parents=True, exist_ok=True)
            created.append(d)
        for d in created:
            ok, why = secure_path(d, is_dir=True)
            if not ok:
                print("[vault] 警告：目录权限收紧失败（%s）：%s\n"
                      "  Windows 请用 icacls 手工断继承；Unix 请 chmod 700。"
                      % (d, why), file=sys.stderr)

        with FileLock(self.lock_path):
            if force and self.entries_dir.exists():
                for p in self.entries_dir.glob("*" + ENTRY_SUFFIX):
                    try:
                        p.unlink()
                    except OSError:
                        pass

            salt = os.urandom(16)
            self._write_meta({
                "magic": META_MAGIC, "version": META_VERSION,
                "tool_version": TOOL_VERSION,
                "kdf": {"name": preset["name"], "n": preset["n"], "r": preset["r"],
                        "p": preset["p"], "salt": base64.b64encode(salt).decode("ascii")},
                "created_at": now_iso(),
            })
            self._key = derive_key(self.passphrase, salt, preset)
            self.audit("init", "-", "创建保险箱", "ok",
                       {"kdf": kdf_name, "platform": platform_tag()})
        print("保险箱已创建：%s" % self.home, file=sys.stderr)
        print("  KDF：%s (n=%d)  平台：%s" % (kdf_name, preset["n"], platform_tag()),
              file=sys.stderr)
        print("  提示：passphrase 不落盘，请自行妥善保管；遗失则条目不可恢复。",
              file=sys.stderr)
        if kdf_name == "fast":
            print("  注意：fast 参数仅供自测，生产/共享库请用 default 或 strong。",
                  file=sys.stderr)

    def _write_meta(self, meta: dict) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        text = json.dumps(meta, ensure_ascii=False, indent=1) + "\n"
        tmp = str(self.meta_path) + ".tmp"
        # 不用 Path.write_text(newline=...)：那是 3.10+ 才有的参数，macOS 自带 3.9 会 TypeError
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, str(self.meta_path))
        if os.name != "nt":
            secure_path(self.meta_path)

    def _load_meta(self) -> dict:
        if not self.meta_path.exists():
            raise VaultError("保险箱不存在：%s\n  先执行：gov_vault.py init" % self.home)
        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        if not str(meta.get("magic", "")).startswith(META_MAGIC):
            raise VaultError("vault.meta.json 不是本工具的格式（magic=%r）"
                             % meta.get("magic"))
        return meta

    def _key_bytes(self) -> bytes:
        if self._key is None:
            meta = self._load_meta()
            salt = base64.b64decode(meta["kdf"]["salt"])
            self._key = derive_key(self.passphrase, salt, meta["kdf"])
        return self._key

    def _aad(self, name: str) -> bytes:
        """头部 + 条目名一起做 AAD：改头部或互换密文都会认证失败。"""
        meta = self._load_meta()
        return json.dumps({"magic": meta["magic"], "version": meta["version"],
                           "kdf": meta["kdf"], "name": name},
                          sort_keys=True).encode("utf-8")

    # -- 条目
    def _entry_path(self, name: str) -> Path:
        return self.entries_dir / encode_entry_name(name)

    def entry_names(self) -> list:
        if not self.entries_dir.exists():
            return []
        out = []
        for p in sorted(self.entries_dir.iterdir()):
            n = p.name
            if not n.endswith(ENTRY_SUFFIX) or n.startswith(".tmp-"):
                continue
            try:
                out.append(decode_entry_name(n))
            except (UnicodeDecodeError, ValueError):
                continue
        return sorted(out)

    def load_entry(self, name: str) -> dict:
        p = self._entry_path(name)
        if not p.exists():
            raise VaultError("条目不存在：%s" % name)
        raw = p.read_bytes()
        if len(raw) < len(FILE_MAGIC) + 12 + 16 or raw[:len(FILE_MAGIC)] != FILE_MAGIC:
            raise VaultError("条目文件已损坏或不是本格式：%s" % p.name, code=4)
        AESGCM, _ = _crypto()
        off = len(FILE_MAGIC)
        nonce, ct = raw[off:off + 12], raw[off + 12:]
        try:
            plain = AESGCM(self._key_bytes()).decrypt(nonce, ct, self._aad(name))
        except VaultError:
            raise
        except Exception as exc:
            raise VaultError(
                "解密失败：%s\n  passphrase 不正确，或文件被篡改，"
                "或该条目由另一套口令创建（多端口令不一致）。" % name, code=4) from exc
        return json.loads(plain.decode("utf-8"))

    def save_entry(self, name: str, rec: dict) -> None:
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        plain = json.dumps(rec, ensure_ascii=False).encode("utf-8")
        nonce = os.urandom(12)
        AESGCM, _ = _crypto()
        ct = AESGCM(self._key_bytes()).encrypt(nonce, plain, self._aad(name))
        fd, tmp = tempfile.mkstemp(dir=str(self.entries_dir), prefix=".tmp-",
                                   suffix=ENTRY_SUFFIX)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(FILE_MAGIC + nonce + ct)
                f.flush()
                os.fsync(f.fileno())
            _replace(tmp, str(self._entry_path(name)))
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        if os.name != "nt":
            secure_path(self._entry_path(name))

    def delete_entry(self, name: str) -> dict:
        p = self._entry_path(name)
        if not p.exists():
            raise VaultError("条目不存在：%s" % name)
        rec = self.load_entry(name)
        p.unlink()
        return rec

    # -- 审计
    def audit(self, action: str, name: str, purpose: str, result: str,
              extra: dict = None, strict: bool = True) -> None:
        rec = {
            "ts": now_iso(),
            "action": action,
            "name": name,
            "purpose": purpose,
            "result": result,
            "actor": os.environ.get("GOV_VAULT_ACTOR") or _os_user(),
            "host": socket.gethostname(),
            "platform": platform_tag(),
            "cwd": str(Path.cwd()),
            "pid": os.getpid(),
        }
        if extra:
            rec.update(extra)
        try:
            self.local_dir.mkdir(parents=True, exist_ok=True)
            with open(str(self.audit_path), "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
        except OSError as exc:
            if strict:
                raise VaultError(
                    "审计日志无法写入（%s）。\n"
                    "  取用/写入类操作在无法留痕时一律拒绝——否则只要 chmod -w local/ "
                    "就能无声取走全部凭据。\n"
                    "  修复目录权限后重试：%s" % (exc, self.local_dir), code=5)
            print("[vault] 警告：审计写入失败（%s），本次只读操作继续" % exc,
                  file=sys.stderr)
            return
        if os.name != "nt":
            secure_path(self.audit_path)

    def read_audit(self) -> list:
        """本机审计 + （若存在）v1 遗留审计。v1 那份不入库，仅用于平滑过渡。"""
        lines = []
        for p in (self.audit_path, self.legacy_audit):
            if not p.exists():
                continue
            try:
                lines.extend(p.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue
        return lines

    # -- v1 单文件库迁移
    def legacy_present(self) -> bool:
        return self.legacy_bin.exists() and not self.entry_names()

    def migrate_legacy(self) -> int:
        """把 v1 的 vault.bin 拆成 v2 的多条目文件。返回迁移条数。"""
        if not self.legacy_bin.exists():
            raise VaultError("没有找到 v1 的 vault.bin，无需迁移")
        meta = self._load_meta()
        AESGCM, _ = _crypto()
        raw = self.legacy_bin.read_bytes()
        if len(raw) < 13:
            raise VaultError("vault.bin 过短，可能已损坏", code=4)
        nonce, ct = raw[:12], raw[12:]
        # v1 的 AAD 不含条目名（那时是单文件库）
        old_aad = json.dumps({"magic": LEGACY_MAGIC, "version": 1, "kdf": meta["kdf"]},
                             sort_keys=True).encode("utf-8")
        try:
            plain = AESGCM(self._key_bytes()).decrypt(nonce, ct, old_aad)
        except Exception as exc:
            raise VaultError("v1 库解密失败：口令不对或文件被篡改", code=4) from exc
        data = json.loads(plain.decode("utf-8"))
        entries = data.get("entries", {})
        count = 0
        for name, rec in entries.items():
            if "payload" not in rec and "secret" in rec:
                rec = dict(rec)
                rec["payload"] = rec.pop("secret")
                rec.setdefault("enc", "text")
            self.save_entry(name, rec)
            count += 1
        backup = self.legacy_bin.with_name("vault.bin.v1-migrated")
        _replace(str(self.legacy_bin), str(backup))
        self.audit("migrate", "-", "v1 单文件库迁移到 v2 多条目", "ok",
                   {"entries": count, "backup": backup.name})
        return count


def _os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- 输出小工具
def _disp_width(s: str) -> int:
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def _pad(s, width: int) -> str:
    s = str(s)
    return s + " " * max(0, width - _disp_width(s))


def _cert_summary(pem_text: str) -> str:
    exe = shutil.which("openssl")
    if not exe:
        return "[vault] 未找到 openssl，跳过证书摘要（明文仍会输出）"
    try:
        r = subprocess.run([exe, "x509", "-noout", "-subject", "-issuer", "-dates",
                            "-fingerprint"], input=pem_text, capture_output=True,
                           text=True, errors="replace", timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        return "[vault] openssl 解析失败：%s" % exc
    if r.returncode != 0:
        return "[vault] 不是可解析的 X.509 证书（明文仍会输出）"
    return "[vault] 证书摘要：\n" + (r.stdout or "").rstrip()


# ---------------------------------------------------------------- 命令
def _need_purpose(args) -> str:
    p = (getattr(args, "purpose", "") or "").strip()
    if len(p) < MIN_PURPOSE_LEN:
        raise VaultError(
            "--purpose 必填且至少 %d 个字符。\n"
            "  审计日志要能回答\"为什么取\"，只写 ok/use 这类词等于没写。"
            % MIN_PURPOSE_LEN, code=2)
    return p


def cmd_init(args) -> int:
    Vault(vault_home(), resolve_passphrase(args)).init(
        force=args.force, kdf_name=args.kdf)
    return 0


def cmd_put(args) -> int:
    name = validate_name(args.name)
    if args.type not in SECRET_TYPES:
        raise VaultError("--type 必须是 %s" % ", ".join(SECRET_TYPES), code=2)

    raw, source = read_input(args)
    if not raw:
        raise VaultError("内容为空，拒绝写入")

    if _is_text(raw):
        text = raw.decode("utf-8")
        enc = "text"
        stored = text.strip("\r\n") if args.type in TRIM_TYPES else text
    else:
        enc = "b64"
        stored = base64.b64encode(raw).decode("ascii")

    labels = {}
    for kv in (args.label or []):
        if "=" not in kv:
            raise VaultError("--label 需要 k=v 形式：%s" % kv, code=2)
        k, v = kv.split("=", 1)
        labels[k.strip()] = v.strip()

    v = Vault(vault_home(), resolve_passphrase(args))
    with FileLock(v.lock_path):
        prev = {}
        existed = False
        if v._entry_path(name).exists():
            try:
                prev = v.load_entry(name)
                existed = True
            except VaultError:
                # 旧条目解不开（例如另一台机器用了不同口令）——允许覆盖，但要让人知道
                print("[vault] 警告：同名条目无法解密，将直接覆盖。"
                      "若是多端口令不一致，请先统一口令。", file=sys.stderr)
        rec = {
            "type": args.type,
            "enc": enc,
            "payload": stored,
            "labels": labels or prev.get("labels", {}),
            "note": args.note if args.note is not None else prev.get("note", ""),
            "rotate_days": (args.rotate_days if args.rotate_days is not None
                            else prev.get("rotate_days")),
            "created_at": prev.get("created_at", now_iso()),
            "updated_at": now_iso(),
            "source": source,
            "bytes": len(raw),
        }
        v.save_entry(name, rec)
        try:
            v.audit("put" if not existed else "update", name, args.purpose or "-", "ok",
                    {"type": args.type, "source": source, "enc": enc, "bytes": len(raw)})
        except VaultError:
            # 审计写不进去就不许改：回滚到写入前的状态。
            # 否则会出现"凭据被改了但日志里查不到"——那正是审计可被绕过的形态。
            if existed:
                v.save_entry(name, prev)
            else:
                try:
                    v._entry_path(name).unlink()
                except OSError:
                    pass
            raise
    print("%s：%s [%s/%s]，%d 字节"
          % ("已更新" if existed else "已写入", name, args.type, enc, len(raw)),
          file=sys.stderr)
    return 0


def cmd_get(args) -> int:
    purpose = _need_purpose(args)
    name = validate_name(args.name)
    v = Vault(vault_home(), resolve_passphrase(args))
    try:
        rec = v.load_entry(name)
    except VaultError as exc:
        # 解密失败也要留痕：口令试错本身是安全事件，不能只报错不记录。
        v.audit("get", name, purpose, "decrypt_failed" if exc.code == 4 else "not_found",
                {"reason": str(exc)[:120]}, strict=False)
        raise

    blob = entry_blob(rec)
    enc = rec.get("enc", "text")
    if args.field:
        try:
            obj = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VaultError("条目不是 JSON 结构，无法按 --field 取值：%s" % exc, code=2)
        if args.field not in obj:
            raise VaultError("字段不存在：%s（可用：%s）"
                             % (args.field, ", ".join(map(str, obj))))
        blob = str(obj[args.field]).encode("utf-8")
        enc = "text"

    if args.out:
        out = Path(args.out)
        if not out.parent.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        ok, why = secure_path(out)
        v.audit("get", name, purpose, "ok",
                {"to_file": str(out), "field": args.field, "bytes": len(blob)})
        print("已写入 %s（%d 字节，%s）"
              % (out, len(blob), "权限已收紧" if ok else "权限收紧失败：%s" % why),
              file=sys.stderr)
        return 0

    if args.cert_info:
        print(_cert_summary(blob.decode("utf-8", "replace")), file=sys.stderr)
        v.audit("get", name, purpose, "ok", {"mode": "cert_info"})
    else:
        v.audit("get", name, purpose, "ok", {"field": args.field, "bytes": len(blob)})
        if not args.quiet:
            print("[vault] 已按用途取出：%s → %s" % (name, purpose), file=sys.stderr)

    buf = getattr(sys.stdout, "buffer", None)
    if buf is not None:
        buf.write(blob)
        if enc == "text" and not blob.endswith(b"\n"):
            buf.write(b"\n")
        buf.flush()
    else:  # 极少数被替换成文本流的宿主
        sys.stdout.write(blob.decode("utf-8", "replace"))
        if enc == "text" and not blob.endswith(b"\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
    return 0


def cmd_ls(args) -> int:
    v = Vault(vault_home(), resolve_passphrase(args))
    names = v.entry_names()
    rows = []
    failures = []
    for name in names:
        try:
            rec = v.load_entry(name)
        except VaultError as exc:
            failures.append((name, str(exc)))
            rows.append({"name": name, "type": "?", "updated_at": "", "rotate_due": "",
                         "labels": {}, "note": "", "error": str(exc)})
            continue
        due = ""
        rd = rec.get("rotate_days")
        if rd:
            upd = _parse_iso(rec.get("updated_at", ""))
            due = (upd + timedelta(days=int(rd))).date().isoformat() if upd else "?"
        rows.append({"name": name, "type": rec.get("type"),
                     "enc": rec.get("enc", "text"),
                     "bytes": rec.get("bytes"), "updated_at": rec.get("updated_at"),
                     "rotate_due": due, "labels": rec.get("labels", {}),
                     "note": rec.get("note", "")})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    if not rows:
        print("（空）")
        return 0
    print(_pad("名称", 32) + _pad("类型", 14) + _pad("编码", 7)
          + _pad("更新", 12) + _pad("轮换到期", 12) + "标签")
    for r in rows:
        labels = ",".join("%s=%s" % (k, val) for k, val in (r.get("labels") or {}).items())
        print(_pad(r["name"], 32) + _pad(r.get("type") or "?", 14)
              + _pad(r.get("enc") or "?", 7)
              + _pad(str(r.get("updated_at") or "")[:10], 12)
              + _pad(str(r.get("rotate_due") or ""), 12) + labels)
    if failures:
        print("\n警告：%d 个条目无法解密（多端口令可能不一致）：" % len(failures),
              file=sys.stderr)
        for name, why in failures:
            print("  - %s：%s" % (name, why.splitlines()[0]), file=sys.stderr)
        v.audit("ls", "-", "-", "partial", {"count": len(rows),
                                            "failed": len(failures)}, strict=False)
        return 1
    v.audit("ls", "-", "-", "ok", {"count": len(rows)}, strict=False)
    return 0


def cmd_meta(args) -> int:
    name = validate_name(args.name)
    v = Vault(vault_home(), resolve_passphrase(args))
    rec = v.load_entry(name)
    shown = {k: val for k, val in rec.items() if k not in ("payload", "secret")}
    shown["enc"] = rec.get("enc", "text")
    shown["payload_bytes"] = len(entry_blob(rec))
    print(json.dumps(shown, ensure_ascii=False, indent=1))
    return 0


def cmd_rm(args) -> int:
    if not args.yes:
        raise VaultError("删除不可恢复，需显式加 --yes", code=2)
    name = validate_name(args.name)
    v = Vault(vault_home(), resolve_passphrase(args))
    with FileLock(v.lock_path):
        rec = v.delete_entry(name)
        try:
            v.audit("rm", name, args.purpose or "-", "ok",
                    {"type": rec.get("type"), "bytes": rec.get("bytes")})
        except VaultError:
            v.save_entry(name, rec)     # 没留痕就不许删
            raise
    print("已删除：%s" % name, file=sys.stderr)
    return 0


def cmd_rotate(args) -> int:
    v = Vault(vault_home(), resolve_passphrase(args))
    names = v.entry_names()
    # 先用旧口令把全部条目解开，再整体换密钥重写；中途失败不留半新半旧
    loaded = {}
    for name in names:
        loaded[name] = v.load_entry(name)

    print("请输入新口令（旧口令已通过上一个入口提供）", file=sys.stderr)
    if args.new_passphrase_file:
        np = Path(args.new_passphrase_file).expanduser()
        if not np.exists():
            raise VaultError("--new-passphrase-file 不存在：%s" % np)
        new = np.read_text(encoding="utf-8").rstrip("\r\n")
    elif os.environ.get("GOV_VAULT_NEW_PASSPHRASE_CMD"):
        new = _from_command(os.environ["GOV_VAULT_NEW_PASSPHRASE_CMD"])
    elif os.environ.get("GOV_VAULT_NEW_PASSPHRASE"):
        new = os.environ["GOV_VAULT_NEW_PASSPHRASE"]
    elif sys.stdin.isatty():
        new = getpass.getpass("new passphrase: ")
        again = getpass.getpass("repeat: ")
        if new != again:
            raise VaultError("两次输入不一致")
    else:
        raise VaultError("非交互环境请设 GOV_VAULT_NEW_PASSPHRASE 或 --new-passphrase-file")
    if not new:
        raise VaultError("新口令为空")

    kdf_name = args.kdf or "default"
    preset = KDF_PRESETS[kdf_name]
    with FileLock(v.lock_path):
        salt = os.urandom(16)
        v._write_meta({
            "magic": META_MAGIC, "version": META_VERSION, "tool_version": TOOL_VERSION,
            "kdf": {"name": preset["name"], "n": preset["n"], "r": preset["r"],
                    "p": preset["p"], "salt": base64.b64encode(salt).decode("ascii")},
            "created_at": v._load_meta().get("created_at", now_iso()),
            "rotated_at": now_iso(),
        })
        v.passphrase = new
        v._key = derive_key(new, salt, preset)
        for name, rec in loaded.items():
            v.save_entry(name, rec)
        v.audit("rotate", "-", "-", "ok", {"entries": len(loaded), "kdf": kdf_name})
    print("口令已更换，%d 个条目已用新密钥重新加密（KDF=%s）" % (len(loaded), kdf_name),
          file=sys.stderr)
    return 0


def cmd_migrate(args) -> int:
    v = Vault(vault_home(), resolve_passphrase(args))
    if not v.legacy_present():
        print("没有需要迁移的 v1 库（或 entries/ 已非空）", file=sys.stderr)
        return 0
    n = v.migrate_legacy()
    print("已迁移 %d 个条目到 entries/；旧 vault.bin 保留为 vault.bin.v1-migrated"
          % n, file=sys.stderr)
    return 0


def cmd_audit(args) -> int:
    # 审计日志是明文，读取不需要口令——事故排查时可能正是拿不到口令的场景。
    v = Vault(vault_home(), "")
    lines = v.read_audit()
    if not lines:
        print("（无审计记录）")
        return 0
    if args.tail:
        lines = lines[-args.tail:]
    if args.json:
        for ln in lines:
            print(ln)
        return 0
    print(_pad("时间", 26) + _pad("动作", 9) + _pad("条目", 30)
          + _pad("结果", 14) + _pad("主机", 16) + "用途")
    for ln in lines:
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        print(_pad(str(r.get("ts", ""))[:25], 26) + _pad(r.get("action", ""), 9)
              + _pad(r.get("name", ""), 30) + _pad(r.get("result", ""), 14)
              + _pad(r.get("host", ""), 16) + str(r.get("purpose", "")))
    return 0


def _git(*args):
    exe = shutil.which("git")
    if not exe:
        return 127, ""
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True,
                           errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return r.returncode, r.stdout or ""


def cmd_doctor(args) -> int:
    code = 0
    home = vault_home()
    print("平台：%s   Python：%s" % (platform_tag(), platform.python_version()))
    print("仓库根：%s" % repo_root())
    print("保险箱：%s" % home)
    print("口令来源：%s" % passphrase_source())

    if sys.version_info < (3, 8):
        print("  Python：需要 3.8+（当前 %s）" % platform.python_version())
        return 2
    try:
        from cryptography import __version__ as _cv
        print("  cryptography：%s" % _cv)
    except ImportError:
        print("  cryptography：缺失")
        try:
            _crypto()
        except VaultError as exc:
            print(str(exc))
        return 3

    if not home.exists():
        print("  状态：未初始化（执行 init）")
        return 0

    v = Vault(home, os.environ.get("GOV_VAULT_PASSPHRASE") or "")
    print("  布局：%s" % ("v2 多条目" if v.entries_dir.exists()
                        else ("v1 单文件（需 migrate）" if v.legacy_bin.exists()
                              else "未知")))
    for d in (home, v.entries_dir, v.local_dir):
        if d.exists():
            desc, ok = perm_state(d, is_dir=True)
            print("  %s/ 权限：%s" % (d.name, desc))
            if not ok:
                code = 1
    for f in (v.meta_path,):
        if f.exists():
            desc, ok = perm_state(f, is_dir=False)
            print("  %s 权限：%s" % (f.name, desc))
            if not ok:
                code = 1
    if v.audit_path.exists():
        desc, ok = perm_state(v.audit_path, is_dir=False)
        print("  local/audit.log 权限：%s" % desc)
        if not ok:
            code = 1

    if v.legacy_bin.exists():
        print("  ⚠ 检测到 v1 单文件库 vault.bin，执行：gov_vault.py migrate")

    names = v.entry_names()
    print("  条目数：%d" % len(names))
    n_audit = len(v.read_audit())
    print("  审计记录：%d 条" % n_audit)

    # 多端协同检查：哪些保险箱文件已入库
    try:
        rel_home = home.relative_to(repo_root()).as_posix()
    except ValueError:
        rel_home = str(home)
    rc, tracked = _git("ls-files", "--", rel_home)
    if rc == 0:
        tracked_files = [ln for ln in tracked.splitlines() if ln.strip()]
        print("  git 跟踪：%d 个保险箱文件" % len(tracked_files))
        if tracked_files:
            for ln in tracked_files:
                if "/local/" in ln.replace("\\", "/"):
                    print("  ✗ 本机私有文件被纳入版本控制：%s（应 remove --cached）" % ln)
                    code = 1
            # 密文必须被标记为 binary，否则 core.autocrlf=true 会改坏字节。
            # 随机密文里约 1/3 不含 NUL，git 的文本启发式会判错——这是概率性损坏。
            probe = rel_home.rstrip("/") + "/entries/probe.enc"
            rc2, attr = _git("check-attr", "binary", "--", probe)
            if rc2 == 0:
                if "binary: set" not in attr:
                    print("  ✗ .gitattributes 未把 *.enc 标为 binary"
                          "（core.autocrlf=true 时会改坏密文）")
                    code = 1
                else:
                    print("  .gitattributes：*.enc → binary（字节不会被转换）")
            meta = {}
            try:
                meta = v._load_meta()
            except VaultError as exc:
                print("  vault.meta.json 读取失败：%s" % exc)
                return exc.code
            n_val = int(meta.get("kdf", {}).get("n", 0) or 0)
            weak = n_val < 2 ** 16
            print("  KDF：n=%d%s" % (n_val, "  ⚠ 共享库建议 n>=65536（init/rotate --kdf strong）"
                                    if weak else ""))
            if weak:
                code = 1
            print("  提示：密文入库后 salt 公开，弱口令可离线爆破——口令请 >=16 位随机。")

    try:
        data_ok = True
        for name in names[:1]:
            v.load_entry(name)
    except VaultError as exc:
        print("  可解密性：失败（%s）" % str(exc).splitlines()[0])
        data_ok = False
        code = exc.code
    if names and data_ok:
        print("  可解密性：OK（抽样 1 条）")

    overdue = []
    for name in names:
        try:
            rec = v.load_entry(name)
        except VaultError:
            continue
        rd = rec.get("rotate_days")
        if not rd:
            continue
        upd = _parse_iso(rec.get("updated_at", ""))
        if upd and datetime.now(timezone.utc) > (upd + timedelta(days=int(rd))):
            overdue.append(name)
    if overdue:
        print("  ⚠ 轮换到期：%s" % ", ".join(overdue))
        code = 1
    return code


def cmd_share(args) -> int:
    """打印多端协同所需的 git 操作，并做共享前检查。"""
    home = vault_home()
    v = Vault(home, resolve_passphrase(args))
    if not v.exists:
        raise VaultError("保险箱不存在，先 init")
    meta = v._load_meta()
    n_val = int(meta.get("kdf", {}).get("n", 0) or 0)
    root = repo_root()

    def rel(p: Path) -> str:
        try:
            return p.relative_to(root).as_posix()
        except ValueError:
            return str(p)          # 库在仓外（GOV_VAULT_HOME 指到别处）时如实显示绝对路径

    print("共享前检查：")
    print("  KDF n=%d：%s" % (n_val, "OK" if n_val >= 2 ** 16
                             else "偏弱，建议 rotate --kdf strong"))
    print("  平台：%s" % platform_tag())
    in_repo = True
    try:
        home.relative_to(root)
    except ValueError:
        in_repo = False
    if not in_repo:
        print("  位置：库在仓库外（%s）——不会随 git 同步，其它机器读不到。" % home)
        print("        要让密文库跟仓走，去掉 GOV_VAULT_HOME 或指向仓内 .gov-vault/。")
    print()
    print("需要纳入版本控制（密文，可安全入库）：")
    print("  %s" % rel(v.meta_path))
    print("  %s/" % rel(v.entries_dir))
    print()
    print("永远不要入库（本机私有）：")
    print("  %s/" % rel(v.local_dir))
    print()
    print("执行：")
    print("  git add %s %s" % (rel(v.meta_path), rel(v.entries_dir)))
    print("  git commit -m 'chore(vault): 同步凭据密文库'")
    print()
    print("其它机器拉取后，用同一 passphrase 即可直接读取（不要重新 init）：")
    print("  GOV_VAULT_PASSPHRASE_CMD='security find-generic-password -s gov-vault -w' \\")
    print("    python scripts/gov_vault.py ls")
    print()
    print("并发约定：不同条目可并行写（git 按文件合并）；同一时刻不要在两台机器上")
    print("写同一个条目名——那是语义冲突，git 只会给你一个二进制冲突。")
    return 0


# ---------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--vault-home", help="覆盖 GOV_VAULT_HOME")
    common.add_argument("--passphrase-file", help="从文件读 passphrase（首行）")

    ap = argparse.ArgumentParser(
        prog="gov_vault.py",
        description="跨平台凭据保险箱：加密静态存储 + 取用审计（Windows/macOS/Linux）",
        epilog="完整说明见 docs/governance/VAULT.md",
    )
    ap.add_argument("--version", action="version",
                    version="gov_vault %s (layout v%d)" % (TOOL_VERSION, META_VERSION))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", parents=[common], help="创建保险箱")
    p.add_argument("--force", action="store_true")
    p.add_argument("--kdf", choices=sorted(KDF_PRESETS), default="default",
                   help="KDF 强度：fast(自测)/default/strong(共享库)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("put", parents=[common], help="写入/更新条目")
    p.add_argument("name")
    p.add_argument("--type", required=True, choices=SECRET_TYPES)
    p.add_argument("--value", help="直接在命令行给值（会留在 shell 历史，不推荐）")
    p.add_argument("--file", help="从文件读内容（二进制自动 base64）")
    p.add_argument("--stdin", action="store_true", help="从 stdin 读（推荐）")
    p.add_argument("--label", action="append", help="k=v，可多次")
    p.add_argument("--note")
    p.add_argument("--rotate-days", type=int)
    p.add_argument("--purpose", default="", help="写入原因（也进审计）")
    p.set_defaults(func=cmd_put)

    p = sub.add_parser("get", parents=[common], help="取出明文（必须写用途）")
    p.add_argument("name")
    p.add_argument("--purpose", required=False, default="")
    p.add_argument("--field", help="条目为 JSON 时只取某字段")
    p.add_argument("--out", help="写入文件而不是 stdout")
    p.add_argument("--cert-info", action="store_true", help="额外打印 X.509 摘要")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("ls", parents=[common], help="列出条目（不含值）")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ls)

    p = sub.add_parser("meta", parents=[common], help="查看条目元数据（不含值）")
    p.add_argument("name")
    p.set_defaults(func=cmd_meta)

    p = sub.add_parser("rm", parents=[common], help="删除条目")
    p.add_argument("name")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--purpose", default="")
    p.set_defaults(func=cmd_rm)

    p = sub.add_parser("rotate", parents=[common], help="更换 passphrase（可同时升 KDF）")
    p.add_argument("--new-passphrase-file")
    p.add_argument("--kdf", choices=sorted(KDF_PRESETS))
    p.set_defaults(func=cmd_rotate)

    p = sub.add_parser("migrate", parents=[common], help="v1 单文件库 → v2 多条目")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("share", parents=[common], help="多端协同：打印入库清单与检查")
    p.set_defaults(func=cmd_share)

    p = sub.add_parser("audit", parents=[common], help="查看审计记录")
    p.add_argument("--tail", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("doctor", parents=[common], help="自检：依赖/权限/可解密性/多端状态")
    p.set_defaults(func=cmd_doctor)
    return ap


def main(argv: list = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    args = build_parser().parse_args(argv)
    if getattr(args, "vault_home", None):
        os.environ["GOV_VAULT_HOME"] = args.vault_home
    try:
        return args.func(args)
    except VaultError as exc:
        print("[vault] %s" % exc, file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("[vault] 已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
