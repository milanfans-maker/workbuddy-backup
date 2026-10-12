#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四国军棋任务 · 微云双向同步器
=========================================================
把本地项目产物与微云网盘做双向同步：
  - 本机文件一改  -> 自动上传   （延迟 ~ debounce 秒）
  - 远端被别人改了 -> 自动下载   （延迟 ~ poll_interval 秒）

凭证走微云官方 MCP（https://www.weiyun.com/api/v3/mcpserver），
用 WyHeader: mcp_token=<token> 鉴权，**不依赖 WorkBuddy 是否在运行**。

子命令
------
  init            生成配置模板
  auth            生成授权链接（首次授权第 1 步）
  fetch           用户授权完成后取 token 并落盘（第 2 步）
  set-token <t>   直接写入 token（跳过 OAuth）
  once            只跑一轮同步，便于调试
  sync            常驻同步循环（默认）
  status          查看当前同步状态

设计要点
--------
三方比对：本地当前(L) / 远端当前(R) / 上次同步基线(B)
  L==B 且 R==B  -> 无变化
  L!=B 且 R==B  -> 上传
  L==B 且 R!=B  -> 下载
  L!=B 且 R!=B  -> 冲突（按 mtime 新的赢，输的存 .conflict 副本）

上传成功后把基线里的 r_* 置为 None，表示"远端状态待下轮基线化"，
下一轮 list 到该文件时直接采纳为基线、不触发下载，避免回环。
"""

import base64
import fnmatch
import hashlib
import json
import os
import signal
import socket
import struct
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- 常量

HOME = Path.home()
# 支持 JUNQI_SYNC_HOME 覆盖，便于隔离测试
CFG_DIR = Path(os.environ.get("JUNQI_SYNC_HOME") or (HOME / ".junqi-sync"))
CFG_FILE = CFG_DIR / "config.json"
STATE_FILE = CFG_DIR / "state.json"
LOG_FILE = CFG_DIR / "logs" / "sync.log"
AUTH_CODE_FILE = CFG_DIR / ".auth_code"
PID_FILE = CFG_DIR / ".sync.pid"

API_URL = "https://www.weiyun.com/api/v3/mcpserver"
TOKEN_API = "https://www.weiyun.com/api/v3/mcp/token/code"
AUTH_URL_TPL = "https://www.weiyun.com/authorize/token?code="

BLOCK_SIZE = 524288          # 微云分片 512KB
UA = "junqi-sync/1.0"
LOG_MAX_BYTES = 2 * 1024 * 1024

HOST = socket.gethostname().split(".")[0]
_running = True


# ---------------------------------------------------------------- 日志

def _rotate_log():
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            bak = LOG_FILE.with_suffix(".log.1")
            if bak.exists():
                bak.unlink()
            LOG_FILE.rename(bak)
    except Exception:
        pass


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[%s] [%-5s] %s" % (ts, level, msg)
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _rotate_log()
        with open(LOG_FILE, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- SHA1（可读寄存器状态）

def _left_rotate(n, b):
    return ((n << b) | (n >> (32 - b))) & 0xFFFFFFFF


class SHA1:
    """微云上传协议要求能读取分块后的内部寄存器状态，故自实现。"""

    def __init__(self):
        self.h0, self.h1, self.h2, self.h3, self.h4 = (
            0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0)
        self._message_byte_length = 0
        self._unprocessed = b""

    def update(self, data):
        self._unprocessed += data
        self._message_byte_length += len(data)
        while len(self._unprocessed) >= 64:
            self._process_chunk(self._unprocessed[:64])
            self._unprocessed = self._unprocessed[64:]

    def _process_chunk(self, chunk):
        w = [0] * 80
        for i in range(16):
            w[i] = struct.unpack(">I", chunk[i * 4:(i + 1) * 4])[0]
        for i in range(16, 80):
            w[i] = _left_rotate(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1)
        a, b, c, d, e = self.h0, self.h1, self.h2, self.h3, self.h4
        for i in range(80):
            if i <= 19:
                f, k = (b & c) | ((~b) & d), 0x5A827999
            elif i <= 39:
                f, k = b ^ c ^ d, 0x6ED9EBA1
            elif i <= 59:
                f, k = (b & c) | (b & d) | (c & d), 0x8F1BBCDC
            else:
                f, k = b ^ c ^ d, 0xCA62C1D6
            temp = (_left_rotate(a, 5) + f + e + k + w[i]) & 0xFFFFFFFF
            e, d, c, b, a = d, c, _left_rotate(b, 30), a, temp
        self.h0 = (self.h0 + a) & 0xFFFFFFFF
        self.h1 = (self.h1 + b) & 0xFFFFFFFF
        self.h2 = (self.h2 + c) & 0xFFFFFFFF
        self.h3 = (self.h3 + d) & 0xFFFFFFFF
        self.h4 = (self.h4 + e) & 0xFFFFFFFF

    def get_state(self):
        assert len(self._unprocessed) == 0
        return b"".join(struct.pack("<I", h)
                        for h in (self.h0, self.h1, self.h2, self.h3, self.h4)).hex()

    def hexdigest(self):
        mbl, unp = self._message_byte_length, self._unprocessed
        tmp = SHA1.__new__(SHA1)
        tmp.h0, tmp.h1, tmp.h2, tmp.h3, tmp.h4 = (
            self.h0, self.h1, self.h2, self.h3, self.h4)
        tmp._unprocessed, tmp._message_byte_length = b"", mbl
        unp += b"\x80"
        unp += b"\x00" * ((56 - len(unp) % 64) % 64)
        unp += struct.pack(">Q", mbl * 8)
        while len(unp) >= 64:
            tmp._process_chunk(unp[:64])
            unp = unp[64:]
        return "{:08x}{:08x}{:08x}{:08x}{:08x}".format(
            tmp.h0, tmp.h1, tmp.h2, tmp.h3, tmp.h4)


# ---------------------------------------------------------------- 微云客户端

class WeiyunError(Exception):
    pass


def _check_name(resp, expect):
    """微云遇同名文件会自动改名（xxx -> xxx(1)），此处给出告警。"""
    got = resp.get("filename")
    if got and got != expect:
        log("⚠ 微云把文件名改成了 %s（期望 %s）" % (got, expect), "WARN")


class WeiyunClient:
    """直连微云官方 MCP 端点。"""

    def __init__(self, token):
        self.token = token
        self._rid = 0

    def _post(self, body, timeout=300):
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": UA,
            # 官方端点两种鉴权头都认，双发以兼容
            "Authorization": "Bearer " + self.token,
            "WyHeader": "mcp_token=" + self.token,
        }
        req = urllib.request.Request(API_URL, data=data,
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")

    @staticmethod
    def _parse(raw):
        raw = raw.strip()
        if not raw:
            raise WeiyunError("空响应")
        if raw.startswith("{"):
            return json.loads(raw)
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise WeiyunError("无法解析响应: " + raw[:300])

    def call(self, tool, args, timeout=300, retries=3):
        """调用一个 MCP tool，返回业务 dict。服务繁忙(50000)自动重试。"""
        last = None
        for attempt in range(1, retries + 1):
            self._rid += 1
            body = {"jsonrpc": "2.0", "id": self._rid, "method": "tools/call",
                    "params": {"name": tool, "arguments": args}}
            try:
                res = self._parse(self._post(body, timeout))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                raise WeiyunError("HTTP %s: %s" % (e.code, detail))
            except urllib.error.URLError as e:
                last = "网络错误: %s" % e
                if attempt < retries:
                    time.sleep(3)
                    continue
                raise WeiyunError(last)

            content = res.get("result", {}).get("content", [])
            for item in content:
                if item.get("type") == "text":
                    try:
                        out = json.loads(item["text"])
                    except Exception:
                        out = {"_raw": item["text"]}
                    break
            else:
                if "error" in res:
                    raise WeiyunError(str(res["error"]))
                out = res

            if isinstance(out, dict) and out.get("retcode") == 50000 \
                    and attempt < retries:
                log("服务繁忙(50000)，3s 后重试 %d/%d" % (attempt, retries), "WARN")
                time.sleep(3)
                continue
            return out
        raise WeiyunError(last or "调用失败")

    # ---------------- 业务封装 ----------------

    def list_dir(self, dir_key, parent_key=None, limit=50):
        """列出目录全部文件（自动分页），返回 {filename: item}。"""
        out = {}
        offset = 0
        while True:
            args = {"dir_key": dir_key, "limit": limit,
                    "offset": offset, "get_type": 2, "order_by": 0}
            if parent_key:
                args["pdir_key"] = parent_key
            r = self.call("weiyun.list", args)
            if r.get("error"):
                raise WeiyunError("list 失败: %s" % r["error"])
            files = r.get("file_list") or []
            for it in files:
                out[it["filename"]] = it
            if r.get("finish_flag") or len(files) < limit:
                break
            offset += len(files)
        return out

    # ---------------- 上传 ----------------

    @staticmethod
    def _calc_params(path):
        size = os.path.getsize(path)
        last_block = size % BLOCK_SIZE or BLOCK_SIZE
        check_block = last_block % 128 or 128
        before = size - last_block
        block_sha = []
        sha1, md5 = SHA1(), hashlib.md5()
        with open(path, "rb") as f:
            for _ in range(0, before, BLOCK_SIZE):
                d = f.read(BLOCK_SIZE)
                sha1.update(d)
                md5.update(d)
                block_sha.append(sha1.get_state())
            between = f.read(last_block - check_block)
            sha1.update(between)
            md5.update(between)
            check_sha = sha1.get_state()
            check_bytes = f.read(check_block)
            sha1.update(check_bytes)
            md5.update(check_bytes)
            file_sha = sha1.hexdigest()
            block_sha.append(file_sha)
        return {
            "filename": os.path.basename(path),
            "file_size": size,
            "file_sha": file_sha,
            "file_md5": md5.hexdigest(),
            "block_sha_list": block_sha,
            "check_sha": check_sha,
            "check_data": base64.b64encode(check_bytes).decode(),
        }

    def upload(self, path, dir_key, max_rounds=400, retry=0,
               expected_id=None):
        """分片上传，返回 (file_id, 是否秒传)。"""
        p = self._calc_params(path)
        size = p["file_size"]
        pre = {
            "filename": p["filename"], "file_size": p["file_size"],
            "file_sha": p["file_sha"], "file_md5": p["file_md5"],
            "block_sha_list": p["block_sha_list"],
            "check_sha": p["check_sha"], "check_data": p["check_data"],
            "pdir_key": dir_key,
        }
        with open(path, "rb") as f:
            blob = f.read()

        for _ in range(max_rounds):
            r = self.call("weiyun.upload", pre)
            if r.get("error"):
                raise WeiyunError("预上传失败: %s" % r["error"])
            if r.get("file_exist"):
                return self._finish_named(r, p["filename"], dir_key,
                                          path, max_rounds, retry, True,
                                          expected_id=expected_id)
            ch_list = r.get("channel_list") or []
            ch = next((c for c in ch_list if int(c.get("len", 0)) > 0), None)
            if ch is None:
                if int(r.get("upload_state", 0)) == 2:
                    return r.get("file_id", ""), False
                raise WeiyunError("无可上传通道 state=%s" % r.get("upload_state"))
            offset, length = int(ch["offset"]), int(ch["len"])
            actual = min(length, len(blob) - offset)
            up = self.call("weiyun.upload", {
                "filename": p["filename"], "file_size": size,
                "file_sha": p["file_sha"], "block_sha_list": [],
                "check_sha": p["check_sha"],
                "upload_key": r.get("upload_key", ""),
                "channel_list": [{"id": int(c["id"]), "offset": int(c["offset"]),
                                  "len": int(c["len"])} for c in ch_list],
                "channel_id": int(ch["id"]), "ex": r.get("ex", ""),
                "file_data": base64.b64encode(blob[offset:offset + actual]).decode(),
            })
            if up.get("error"):
                raise WeiyunError("分片失败: %s" % up["error"])
            if int(up.get("upload_state", 0)) == 2:
                return self._finish_named(up, p["filename"], dir_key,
                                          path, max_rounds, retry, False,
                                          expected_id=expected_id)
        raise WeiyunError("超过最大分片轮数")

    # ---------------- 下载 ----------------

    def download(self, file_id, dir_key, dest, expect_size=None):
        """取下载链接并落盘，返回实际字节数。"""
        r = self.call("weiyun.download",
                      {"items": [{"file_id": file_id, "pdir_key": dir_key}]})
        if r.get("error"):
            raise WeiyunError("取下载链接失败: %s" % r["error"])
        items = r.get("items") or []
        if not items:
            raise WeiyunError("下载结果为空")
        it = items[0]
        url = it.get("https_download_url")
        if not url:
            raise WeiyunError("无下载链接")
        headers = {"User-Agent": UA}
        if it.get("cookie"):
            headers["Cookie"] = it["cookie"]

        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=600) as rsp, open(tmp, "wb") as f:
            while True:
                chunk = rsp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        got = tmp.stat().st_size
        if expect_size is not None and got != expect_size:
            tmp.unlink(missing_ok=True)
            raise WeiyunError("大小不符 期望%s 实际%s" % (expect_size, got))
        os.replace(str(tmp), str(dest))
        return got

    def _finish_named(self, resp, expect, dir_key, path,
                      max_rounds, retry, fast, expected_id=None):
        """上传返回后校验文件名。微云撞名会静默改名为 xxx(1)。

        被改名 ⇒ 回删撞名产物 + **CAS 校验** + 清目录内同名旧版 + 重传一次。

        --- COLLIDE-CAS (I patch 20260926) ---
        「先删后传」必须过 CAS：只有远端该名字下仍是本轮列表看到的同一个
        file_id 时才删。否则说明**对端期间写过这个名字**，盲删会删掉它的新版，
        而本机若命中秒传会从对象池把旧内容复活 ⇒ **静默回滚**（见 patch 文档）。
        """
        got, fid = resp.get("filename"), resp.get("file_id", "")
        if not got or got == expect:
            return fid, fast
        log("⚠ 微云把文件名改成了 %s（期望 %s）→ 回删并重试"
            % (got, expect), "WARN")
        try:
            if fid:
                self.delete_file(fid, dir_key)
        except WeiyunError as e:
            log("回删撞名条目失败: %s" % e, "WARN")
        if retry < 1:
            # --- COLLIDE-CAS (I patch 20260926) ---
            # 删之前先确认「远端该名字下还是我本轮看到的那一份」。
            # expected_id is None ⇒ 本轮列表里本来没这个名字，现在却撞名 ⇒ 并发写。
            try:
                ex = self.list_dir(dir_key).get(expect)
            except WeiyunError as e:
                log("撞名 CAS 校验时 list 失败: %s" % e, "WARN")
                ex = None
            if ex is not None:
                cur = ex.get("file_id")
                if cur != expected_id:
                    raise WeiyunError(
                        "撞名冲突(并发写)：远端 %s 已被对端改写"
                        "（本轮已知 id=%s，现在 id=%s，远端 %s B）"
                        " ⇒ 不删远端，让位给对端"
                        % (expect, expected_id, cur, ex.get("file_size")))
            self.delete_by_name(expect, dir_key)
            return self.upload(path, dir_key, max_rounds,
                               retry=retry + 1, expected_id=expected_id)
        raise WeiyunError("撞名重试后仍失败: %s" % got)

    def delete_by_name(self, filename, dir_key):
        """按名删除远端同名文件（清同名旧版用）。返回删除个数。"""
        rmap = self.list_dir(dir_key)
        it = rmap.get(filename)
        if not it:
            return 0
        self.delete_file(it["file_id"], dir_key)
        return 1

    def delete_file(self, file_id, dir_key):
        """删除远端文件（进回收站）。微云上传不覆盖同名文件，须先删旧版。"""
        r = self.call("weiyun.delete",
                      {"file_list": [{"file_id": file_id, "pdir_key": dir_key}]})
        if r.get("error"):
            raise WeiyunError("删除失败: %s" % r["error"])
        return r


# ---------------------------------------------------------------- 配置 / 状态

DEFAULT_GLOBS = {
    "复盘分析器": ["index.html", "index_task*.html",
                   "*报告_2026*.html", "sfx_preview.html"],
    "实战桥": ["四国军棋实战桥.html", "四国军棋实战桥_使用说明_*.html",
              "实战桥Windows迁移说明_*.html", "实战桥Windows版.zip",
              ".workbuddy/bridge_e2e_result.json"],
    "项目配置-memory": [".workbuddy/memory/*.md"],
}


def load_json(path, default):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, str(path))


def load_cfg():
    cfg = load_json(CFG_FILE, None)
    if not cfg:
        log("找不到配置 %s，请先执行 init" % CFG_FILE, "ERROR")
        sys.exit(2)
    return cfg


# ---------------------------------------------------------------- 同步核心

def is_excluded(name, cfg):
    for pat in cfg.get("exclude", []):
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def is_readonly(name, cfg):
    """G 补丁：共享文件「只读」判定 —— 参与比对/下载，但本地改了**永不上传**。

    共享文件（MEMORY.md / 对照表）的「单一写者」只是文档约定，
    同步器不认 ⇒ 非写者机只要认为「本地变了」就会上传并覆盖写者
    （2026-09-26 23:33 实测发生过一次）。
    本机 config 里 `readonly_globs` 命中的文件，本地改动一律不上传。
    """
    for pat in cfg.get("readonly_globs", []):
        if fnmatch.fnmatch(name, _glob_basename(pat)):
            return True
    return False


def _glob_basename(g):
    """取 glob 的文件名部分，兼容 Windows 分隔符。"""
    return g.replace("\\", "/").rsplit("/", 1)[-1]


# --- FIRSTSYNC-GUARD (J patch 20260927) ---
_RO_LAST = {}


def _ro_log(sk, st, msg):
    """只读文件状态日志：同一状态（size|mtime|msg）不重复打，防每轮刷屏。

    与 H 的 `b["ro_stamp"]` 等价，但**不依赖基线存在** —— 首次同步时 `b is None`，
    正是 H 那套去重覆盖不到的场景。
    """
    _stamp = "%s|%s|%s" % (st["size"], st["mtime"], msg)
    if _RO_LAST.get(sk) == _stamp:
        return
    _RO_LAST[sk] = _stamp
    log("只读文件 [%s] %s ⇒ 不传" % (sk, msg), "INFO")


def matches_globs(filename, globs):
    """远端文件名是否落在同步范围内（仅产物，避免把无关文件拉下来）。"""
    return any(fnmatch.fnmatch(filename, _glob_basename(g)) for g in globs)


def scan_local(cfg):
    """扫描本地，返回 {root_name: {filename: {path, mtime, size}}}。"""
    base = Path(cfg["local_base"]).expanduser()
    result = {}
    for root in cfg["roots"]:
        found = {}
        for pat in root["globs"]:
            for p in base.glob(pat):
                if not p.is_file():
                    continue
                if is_excluded(p.name, cfg):
                    continue
                if p.name.endswith(".part"):
                    continue
                found[p.name] = p
        result[root["name"]] = found
    return result


def snapshot_remote(client, cfg):
    """拉取远端各目录清单，返回 {root_name: {filename: item}}。"""
    out = {}
    for root in cfg["roots"]:
        try:
            out[root["name"]] = client.list_dir(
                root["remote_dir_key"], root.get("remote_parent_key"))
        except Exception as e:
            log("拉取远端目录 [%s] 失败: %s" % (root["name"], e), "ERROR")
            out[root["name"]] = None      # None 表示本轮该目录不可用
    return out


def local_stamp(path):
    st = path.stat()
    return {"mtime": round(st.st_mtime, 3), "size": st.st_size}


def conflict_copy(path):
    p = Path(path)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = p.with_name("%s.conflict-%s-%s%s" % (p.stem, HOST, ts, p.suffix))
    try:
        dst.write_bytes(p.read_bytes())
        log("冲突副本已保存: %s" % dst.name, "WARN")
    except Exception as e:
        log("保存冲突副本失败: %s" % e, "ERROR")
    return dst


def sync_once(client, cfg, state, dry=False):
    """跑一轮同步。返回本轮动作统计。"""
    base = Path(cfg["local_base"]).expanduser()
    files_state = state.setdefault("files", {})
    local = scan_local(cfg)
    remote = snapshot_remote(client, cfg)

    stats = {"up": 0, "down": 0, "conflict": 0, "skip": 0, "err": 0}
    debounce = cfg.get("debounce", 3)
    now = time.time()

    for root in cfg["roots"]:
        rname = root["name"]
        rkey = root["remote_dir_key"]
        lmap = local.get(rname, {})
        rmap = remote.get(rname)
        if rmap is None:
            continue                      # 该目录本轮远端不可用，整体跳过
        # 远端文件也要过 glob 筛子：测试文件、别的机器放的无关文件不参与同步
        rmap = {k: v for k, v in rmap.items() if matches_globs(k, root["globs"])}

        names = set(lmap) | set(rmap)
        for key in sorted(names):
            sk = "%s/%s" % (rname, key)
            b = files_state.get(sk)
            lp = lmap.get(key)
            rp = rmap.get(key)

            # ---- 远端状态是否变化
            if rp is None:
                r_changed = bool(b)
            elif b is None:
                r_changed = True
            elif b.get("r_file_id") is None:
                r_changed = False          # 本机刚传上去的，待基线化
            else:
                r_changed = (rp["file_id"] != b.get("r_file_id")
                             or rp["file_size"] != b.get("r_size"))

            # ---- 本地状态是否变化
            if lp is None:
                l_changed = bool(b)
                lstamp = None
            else:
                lstamp = local_stamp(lp)
                if b is None:
                    l_changed = True
                elif b.get("l_mtime") is None:
                    l_changed = False      # 刚从远端拉下来的，待基线化
                else:
                    l_changed = (lstamp["mtime"] != b.get("l_mtime")
                                 or lstamp["size"] != b.get("l_size"))

            # ⚠️ G+H+J：只读文件（共享文件）—— **永不上传**，只跟随写者。
            # --- RO-TIDY (H patch 20260926) ---
            # ① 内容未变 ⇒ 静默把 mtime 刷进基线（否则每轮刷 INFO）；
            # ② 内容真变 ⇒ 不上传，日志按状态去重（不刷 l_mtime/l_size，不掩盖分歧）。
            # --- FIRSTSYNC-GUARD (J patch 20260927) ---
            # 洞：G 挂在 `l_changed` 上，而下游「首次同步 (b is None)」「本地有/远端无」
            #     两条分支**独立判定**（与 l_changed 无关）⇒ 绕过守卫照样上传。
            # 修法：改成**单一收口** —— 只读且有本地文件者，一律在本块内决定去向并
            #     continue；后续任何分支都不再有机会把它推上去。
            #       远端无   ⇒ 不复活（不上传）
            #       大小不符 ⇒ 跟随写者下载（只下不上）
            #       大小一致 ⇒ 只补基线
            if lp is not None and is_readonly(key, cfg):
                if rp is None:
                    _ro_log(sk, lstamp, "远端已无 ⇒ 不复活")
                    stats["skip"] += 1
                    continue
                if lstamp["size"] != rp["file_size"]:
                    _ro_log(sk, lstamp, "本地 %d / 远端 %d ⇒ 跟随远端下载"
                            % (lstamp["size"], rp["file_size"]))
                    _do_download(client, cfg, files_state, sk, key, rp, rkey,
                                 base, stats, dry)
                    continue
                if b is not None and b.get("l_mtime") is not None:
                    b["l_mtime"] = lstamp["mtime"]
                    b["l_size"] = lstamp["size"]
                else:
                    _refresh_baseline(files_state, sk, lp, rp)
                stats["skip"] += 1
                continue

            # ---- 判定
            if lp is None and rp is None:
                files_state.pop(sk, None)
                continue

            if lp is None and rp is not None:
                # 远端有、本地无
                if b is None:
                    _do_download(client, cfg, files_state, sk, key, rp, rkey,
                                 base, stats, dry)
                else:
                    # 本地被删了 -> 删除不传播，按需拉回
                    if cfg.get("delete_policy") == "mirror":
                        _do_download(client, cfg, files_state, sk, key, rp, rkey,
                                     base, stats, dry)
                    else:
                        stats["skip"] += 1
                continue

            if lp is not None and rp is None:
                # 本地有、远端无
                if b is None or cfg.get("delete_policy") != "mirror":
                    if now - lstamp["mtime"] < debounce:
                        stats["skip"] += 1
                        continue
                    _do_upload(client, cfg, files_state, sk, key, lp, rkey,
                               stats, dry)
                continue

            # ---- 两边都在
            if b is None:
                # 首次遇到该文件：基线尚未建立。
                # 大小一致 => 视为已同步，只补基线，不动文件。
                if lstamp["size"] == rp["file_size"]:
                    _refresh_baseline(files_state, sk, lp, rp)
                    stats["skip"] += 1
                    continue
                # 大小不一致 => 本地是"活的工作副本"，以本地为准推上去
                log("首次同步 [%s] 大小不一致 本地 %d / 远端 %d，以本地为准"
                    % (key, lstamp["size"], rp["file_size"]), "WARN")
                _do_upload(client, cfg, files_state, sk, key, lp, rkey,
                           stats, dry, existing=rp)
                continue

            if not l_changed and not r_changed:
                # 基线待补（首次运行或刚同步过）
                need_fix = (b is None or b.get("l_mtime") is None
                            or b.get("r_file_id") is None)
                # ⚠️ F 补丁：竞态防护。若处于「本机刚上传、待基线化」，
                # 远端此刻应仍是我传的那一份。若大小不符 ⇒ 上传后云端已被对端
                # 覆盖 ⇒ 静默采纳会记下「l=自己 / r=别人」的矛盾基线 ⇒
                # 两侧恒判未变 ⇒ 永久失配且不可自愈、无日志。
                # 故改走冲突分支，使其可见（WARN + 本地副本）。
                if need_fix and b is not None and b.get("r_file_id") is None \
                        and rp is not None and lstamp is not None \
                        and rp["file_size"] != lstamp["size"]:
                    log("⚠ 待基线化时远端已被改动 [%s] 本地 %d / 远端 %d"
                        " ⇒ 按冲突处理" % (key, lstamp["size"], rp["file_size"]),
                        "WARN")
                    stats["conflict"] += 1
                    if not dry:
                        conflict_copy(lp)
                    if rp["file_mtime"] >= lstamp["mtime"] * 1000:
                        _do_download(client, cfg, files_state, sk, key, rp,
                                     rkey, base, stats, dry)
                    else:
                        _do_upload(client, cfg, files_state, sk, key, lp,
                                   rkey, stats, dry, existing=rp)
                    continue
                if need_fix:
                    _refresh_baseline(files_state, sk, lp, rp)
                stats["skip"] += 1
                continue

            if l_changed and not r_changed:
                if now - lstamp["mtime"] < debounce:
                    stats["skip"] += 1
                    continue
                _do_upload(client, cfg, files_state, sk, key, lp, rkey,
                           stats, dry, existing=rp)
                continue

            if not l_changed and r_changed:
                _do_download(client, cfg, files_state, sk, key, rp, rkey,
                             base, stats, dry)
                continue

            # ---- 双向都变了：冲突。无论谁赢，先给本地版本留一份快照
            stats["conflict"] += 1
            if not dry:
                conflict_copy(lp)
            l_ts = lstamp["mtime"] * 1000
            r_ts = rp["file_mtime"]
            if r_ts >= l_ts:
                _do_download(client, cfg, files_state, sk, key, rp, rkey,
                             base, stats, dry)
                log("冲突 [%s] 远端较新 → 已下载，本地旧版存为副本" % key, "WARN")
            else:
                _do_upload(client, cfg, files_state, sk, key, lp, rkey,
                           stats, dry, existing=rp)
                log("冲突 [%s] 本地较新 → 已上传，本地版本存为副本" % key, "WARN")

    state["last_run"] = int(time.time())
    state["last_host"] = HOST
    if not dry:
        save_json(STATE_FILE, state)
    return stats


def _refresh_baseline(files_state, sk, lp, rp):
    st = local_stamp(lp)
    files_state[sk] = {
        "l_mtime": st["mtime"], "l_size": st["size"],
        "r_file_id": rp["file_id"], "r_mtime": rp["file_mtime"],
        "r_size": rp["file_size"],
        "synced_at": int(time.time()),
    }


def _do_upload(client, cfg, files_state, sk, key, lp, rkey, stats, dry,
               existing=None):
    # --- FIRSTSYNC-GUARD (J patch 20260927) ---
    # 兜底闸门（canary）：只读闸门应收口在 sync_once 里。若真走到这里，说明又有人
    # 加了一条绕过收口的上传分支 —— 宁可拒传 + 响亮报错，也不覆盖写者。
    if is_readonly(key, cfg):
        log("⛔ 只读兜底闸门拒绝上传 [%s] —— 有分支绕过了收口，请检查" % key,
            "ERROR")
        stats["skip"] += 1
        return
    size = lp.stat().st_size
    if dry:
        log("[dry] 将上传 %s (%d B)" % (key, size))
        stats["up"] += 1
        return
    try:
        # 微云上传不覆盖同名文件（会生成 xxx(1).txt），先删掉远端旧版再传
        if existing and existing.get("file_id"):
            client.delete_file(existing["file_id"], rkey)
        fid, fast = client.upload(
            str(lp), rkey, expected_id=(existing or {}).get("file_id"))
        st = local_stamp(lp)
        files_state[sk] = {
            "l_mtime": st["mtime"], "l_size": st["size"],
            # r_file_id 故意留 None：非秒传路径返回的 id 未必等于目录内真实
            # file_id（实测下一轮 list 会不一致 ⇒ 自判「远端变了」⇒ 白下载一份）。
            # 置 None 让下一轮 _refresh_baseline() 用 list 真实值校准。
            "r_file_id": None, "r_mtime": None, "r_size": size,
            "synced_at": int(time.time()),
        }
        log("↑ 上传 %s (%.0f KB)%s" % (key, size / 1024.0,
                                       " [秒传]" if fast else ""))
        stats["up"] += 1
    except Exception as e:
        log("上传失败 %s: %s" % (key, e), "ERROR")
        stats["err"] += 1


def _do_download(client, cfg, files_state, sk, key, rp, rkey, base,
                 stats, dry):
    dst = Path(base)
    # 依据 glob 归属还原相对路径
    rel = _relpath_for(cfg, key)
    dst = base / rel if rel else base / key
    if dry:
        log("[dry] 将下载 %s (%d B)" % (key, rp["file_size"]))
        stats["down"] += 1
        return
    try:
        got = client.download(rp["file_id"], rkey, dst, rp["file_size"])
        st = local_stamp(dst)
        files_state[sk] = {
            "l_mtime": st["mtime"], "l_size": st["size"],
            "r_file_id": rp["file_id"], "r_mtime": rp["file_mtime"],
            "r_size": rp["file_size"],
            "synced_at": int(time.time()),
        }
        log("↓ 下载 %s (%.0f KB)" % (key, got / 1024.0))
        stats["down"] += 1
    except Exception as e:
        log("下载失败 %s: %s" % (key, e), "ERROR")
        stats["err"] += 1


def _relpath_for(cfg, filename):
    """按 glob 反查该文件名对应的本地相对路径（memory 类文件带目录）。"""
    for root in cfg["roots"]:
        for pat in root["globs"]:
            if "/" in pat and fnmatch.fnmatch(filename, _glob_basename(pat)):
                sub = pat.replace("\\", "/").rsplit("/", 1)[0]
                return str(Path(sub) / filename)
    return None


# ---------------------------------------------------------------- 命令

def cmd_init():
    if CFG_FILE.exists():
        print("配置已存在: %s" % CFG_FILE)
        return
    cfg = {
        "local_base": str(Path.home() / "ai学习/四国军棋/qq军棋复盘分析"),
        "token": "",
        "poll_interval": 15,
        "debounce": 3,
        "delete_policy": "ignore",
        "exclude": ["*.bak*", "*.tmp", "*~", ".DS_Store", "*.conflict-*"],
        "roots": [
            {"name": "复盘分析器",
             "remote_dir_key": "5e5b090bd03ab119b22e150037c3f0b9",
             "remote_parent_key": "5e5b090bcda8f65256842498df740fec",
             "globs": DEFAULT_GLOBS["复盘分析器"]},
            {"name": "项目配置-memory",
             "remote_dir_key": "5e5b090b8c2147209f551050b6967ec9",
             "remote_parent_key": "5e5b090bd03ab119b22e150037c3f0b9",
             "globs": DEFAULT_GLOBS["项目配置-memory"]},
            {"name": "实战桥",
             "remote_dir_key": "5e5b090b245a37fde5c2eec99135a221",
             "remote_parent_key": "5e5b090bcda8f65256842498df740fec",
             "globs": DEFAULT_GLOBS["实战桥"]},
        ],
    }
    save_json(CFG_FILE, cfg)
    print("已生成配置: %s" % CFG_FILE)


def cmd_auth():
    import secrets
    code = secrets.token_hex(8)
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_CODE_FILE.write_text(code, encoding="utf-8", newline="")
    print(AUTH_URL_TPL + code)


def cmd_fetch():
    if not AUTH_CODE_FILE.exists():
        print("ERROR: 找不到授权码，请先执行 auth")
        sys.exit(1)
    code = AUTH_CODE_FILE.read_text(encoding="utf-8", newline="").strip()
    data = json.dumps({"code": code}).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_API, data=data, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("ERROR: 网络请求失败 %s" % e)
        sys.exit(1)
    token = res.get("token")
    if token:
        cfg = load_cfg()
        cfg["token"] = token
        save_json(CFG_FILE, cfg)
        AUTH_CODE_FILE.unlink(missing_ok=True)
        print("TOKEN_READY")
        return
    print("ERROR code=%s message=%s" % (res.get("code"), res.get("message")))
    sys.exit(1)


def cmd_set_token(token):
    cfg = load_cfg()
    cfg["token"] = token
    save_json(CFG_FILE, cfg)
    print("TOKEN_READY")


def _pid_alive(pid):
    """跨平台判断 pid 是否存活。

    ⚠️ Windows 上 `os.kill(pid, 0)` 会抛 `OSError [WinError 87] 参数错误`
    （即使进程活得好好的），曾导致 status 永远误报「未运行」并**误删 .sync.pid**，
    进而可能重复启动第二个守护进程。故 Windows 走原生 API。
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not h:
                return False
            try:
                code = ctypes.c_ulong()
                if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                    return False
                return code.value == STILL_ACTIVE
            finally:
                k.CloseHandle(h)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # 存在但无权限 → 视为存活
    except Exception:
        return False


def _check_pid():
    if not PID_FILE.exists():
        return None
    try:
        raw = PID_FILE.read_text().strip()
    except OSError:
        return None                     # 读不到不代表进程死了 → 不动文件
    if not raw.isdigit():
        PID_FILE.unlink(missing_ok=True)  # 内容非法（写了一半）→ 清理
        return None
    pid = int(raw)
    if _pid_alive(pid):
        return pid
    PID_FILE.unlink(missing_ok=True)
    return None


def _on_signal(signum, frame):
    global _running
    log("收到信号 %s，准备退出" % signum)
    _running = False


def cmd_sync(once=False, dry=False):
    cfg = load_cfg()
    if not cfg.get("token"):
        log("未配置 token，请先执行 auth + fetch", "ERROR")
        sys.exit(2)
    base = Path(cfg["local_base"]).expanduser()
    if not base.exists():
        log("本地目录不存在: %s" % base, "ERROR")
        sys.exit(2)

    client = WeiyunClient(cfg["token"])
    state = load_json(STATE_FILE, {})

    if once:
        stats = sync_once(client, cfg, state, dry=dry)
        log("%s本轮: 上传 %d / 下载 %d / 冲突 %d / 跳过 %d / 失败 %d"
            % ("[预演] " if dry else "", stats["up"], stats["down"],
               stats["conflict"], stats["skip"], stats["err"]))
        return

    other = _check_pid()
    if other:
        log("已有同步进程在跑 (pid=%s)，退出" % other, "ERROR")
        sys.exit(1)
    PID_FILE.write_text(str(os.getpid()), newline="")

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    interval = cfg.get("poll_interval", 15)
    log("=== 同步守护启动 pid=%d host=%s ===" % (os.getpid(), HOST))
    log("本地: %s" % base)
    log("轮询间隔: %ds  防抖: %ds" % (interval, cfg.get("debounce", 3)))
    try:
        while _running:
            try:
                stats = sync_once(client, cfg, state)
                if stats["up"] or stats["down"] or stats["err"] or stats["conflict"]:
                    log("本轮: 上传 %d / 下载 %d / 冲突 %d / 失败 %d"
                        % (stats["up"], stats["down"], stats["conflict"], stats["err"]))
            except Exception as e:
                log("本轮异常: %s" % e, "ERROR")
            for _ in range(interval):
                if not _running:
                    break
                time.sleep(1)
    finally:
        PID_FILE.unlink(missing_ok=True)
        log("=== 同步守护退出 ===")


def cmd_status():
    cfg = load_json(CFG_FILE, {})
    state = load_json(STATE_FILE, {})
    print("配置文件   : %s" % CFG_FILE)
    print("token      : %s" % ("已配置 (%d 字符)" % len(cfg["token"])
                               if cfg.get("token") else "未配置"))
    print("本地目录   : %s" % cfg.get("local_base", "-"))
    pid = _check_pid()
    print("守护进程   : %s" % ("运行中 pid=%s" % pid if pid else "未运行"))
    print("同步根     : %s" % ", ".join(r["name"] for r in cfg.get("roots", [])))
    files = state.get("files", {})
    print("已同步文件 : %d" % len(files))
    if state.get("last_run"):
        print("上次同步   : %s (%s)" % (
            datetime.fromtimestamp(state["last_run"]).strftime("%Y-%m-%d %H:%M:%S"),
            state.get("last_host", "-")))
    pend = [k for k, v in files.items() if v.get("r_mtime") is None]
    if pend:
        print("待基线化   : %d 个（本机刚上传）" % len(pend))


def main():
    args = sys.argv[1:]
    if not args:
        cmd_sync(once=False)
        return
    cmd = args[0]
    if cmd == "init":
        cmd_init()
    elif cmd == "auth":
        cmd_auth()
    elif cmd == "fetch":
        cmd_fetch()
    elif cmd == "set-token":
        if len(args) < 2:
            print("用法: junqi_sync.py set-token <token>")
            sys.exit(1)
        cmd_set_token(args[1])
    elif cmd == "once":
        cmd_sync(once=True)
    elif cmd == "dry":
        cmd_sync(once=True, dry=True)
    elif cmd == "sync":
        cmd_sync(once=False)
    elif cmd == "status":
        cmd_status()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()


# --- EOL-HARDENED (D patch 20260926) ---


# --- RACE-HARDENED (F patch 20260926) ---


# --- WRITER-LOCK (G patch 20260926) ---


# --- RO-TIDY (H patch 20260927) ---


# --- COLLIDE-CAS (I patch 20260927) ---


# --- FIRSTSYNC-GUARD (J patch 20260927) ---
