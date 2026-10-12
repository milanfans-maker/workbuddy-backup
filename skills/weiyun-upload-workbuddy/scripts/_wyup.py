#!/usr/bin/env python3
"""微云上传引擎：建目录 + 分片上传（走 WorkBuddy connector 本地代理）。

用法：
  python3 _wyup.py mkdir <父目录key> <目录名>
  python3 _wyup.py up <目标目录key> <本地文件路径> [本地文件路径 ...]
"""
import base64
import hashlib
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _wy import call  # noqa: E402

BLOCK_SIZE = 524288  # 512KB


# ---------- 流式 SHA1（可读内部寄存器状态，微云协议要求） ----------

def _left_rotate(n, b):
    return ((n << b) | (n >> (32 - b))) & 0xFFFFFFFF


class SHA1:
    def __init__(self):
        self.h0 = 0x67452301
        self.h1 = 0xEFCDAB89
        self.h2 = 0x98BADCFE
        self.h3 = 0x10325476
        self.h4 = 0xC3D2E1F0
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
                f = (b & c) | ((~b) & d)
                k = 0x5A827999
            elif i <= 39:
                f = b ^ c ^ d
                k = 0x6ED9EBA1
            elif i <= 59:
                f = (b & c) | (b & d) | (c & d)
                k = 0x8F1BBCDC
            else:
                f = b ^ c ^ d
                k = 0xCA62C1D6
            temp = (_left_rotate(a, 5) + f + e + k + w[i]) & 0xFFFFFFFF
            e = d
            d = c
            c = _left_rotate(b, 30)
            b = a
            a = temp
        self.h0 = (self.h0 + a) & 0xFFFFFFFF
        self.h1 = (self.h1 + b) & 0xFFFFFFFF
        self.h2 = (self.h2 + c) & 0xFFFFFFFF
        self.h3 = (self.h3 + d) & 0xFFFFFFFF
        self.h4 = (self.h4 + e) & 0xFFFFFFFF

    def get_state(self):
        assert len(self._unprocessed) == 0
        out = b""
        for h in (self.h0, self.h1, self.h2, self.h3, self.h4):
            out += struct.pack("<I", h)
        return out.hex()

    def hexdigest(self):
        mbl = self._message_byte_length
        unp = self._unprocessed
        tmp = SHA1.__new__(SHA1)
        tmp.h0, tmp.h1, tmp.h2, tmp.h3, tmp.h4 = (
            self.h0, self.h1, self.h2, self.h3, self.h4)
        tmp._unprocessed = b""
        tmp._message_byte_length = mbl
        unp += b"\x80"
        unp += b"\x00" * ((56 - len(unp) % 64) % 64)
        unp += struct.pack(">Q", mbl * 8)
        while len(unp) >= 64:
            tmp._process_chunk(unp[:64])
            unp = unp[64:]
        return "{:08x}{:08x}{:08x}{:08x}{:08x}".format(
            tmp.h0, tmp.h1, tmp.h2, tmp.h3, tmp.h4)


def calc_upload_params(file_path):
    file_size = os.path.getsize(file_path)
    last_block_size = file_size % BLOCK_SIZE or BLOCK_SIZE
    check_block_size = last_block_size % 128 or 128
    before_block_size = file_size - last_block_size
    block_sha_list = []
    sha1 = SHA1()
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for _ in range(0, before_block_size, BLOCK_SIZE):
            data = f.read(BLOCK_SIZE)
            sha1.update(data)
            md5.update(data)
            block_sha_list.append(sha1.get_state())
        between = f.read(last_block_size - check_block_size)
        sha1.update(between)
        md5.update(between)
        check_sha = sha1.get_state()
        check_bytes = f.read(check_block_size)
        sha1.update(check_bytes)
        md5.update(check_bytes)
        file_sha = sha1.hexdigest()
        check_data = base64.b64encode(check_bytes).decode()
        block_sha_list.append(file_sha)
    return {
        "filename": os.path.basename(file_path),
        "file_size": file_size,
        "file_sha": file_sha,
        "file_md5": md5.hexdigest(),
        "block_sha_list": block_sha_list,
        "check_sha": check_sha,
        "check_data": check_data,
    }


def _call_retry(name, args, max_retries=3):
    """遇到 retcode=50000（服务繁忙）自动重试。"""
    for attempt in range(1, max_retries + 1):
        r = call(name, args)
        if r.get("retcode") == 50000 and attempt < max_retries:
            print(f"    ! 服务繁忙 50000，3s 后重试 ({attempt}/{max_retries})",
                  flush=True)
            time.sleep(3)
            continue
        return r
    return r


def upload_file(file_path, pdir_key=None, max_rounds=300):
    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)
    params = calc_upload_params(file_path)
    blocks = len(params["block_sha_list"])
    print(f"  -> {filename}  {file_size/1024:.0f} KB, {blocks} block(s)",
          flush=True)

    pre_args = {
        "filename": params["filename"],
        "file_size": params["file_size"],
        "file_sha": params["file_sha"],
        "file_md5": params["file_md5"],
        "block_sha_list": params["block_sha_list"],
        "check_sha": params["check_sha"],
        "check_data": params["check_data"],
    }
    if pdir_key:
        pre_args["pdir_key"] = pdir_key

    with open(file_path, "rb") as f:
        blob = f.read()

    for rnd in range(1, max_rounds + 1):
        pre = _call_retry("weiyun.upload", pre_args)
        if pre.get("error"):
            raise RuntimeError(f"预上传失败: {pre['error']}")
        if pre.get("file_exist"):
            print(f"     [秒传] file_id={pre.get('file_id','')}", flush=True)
            return pre
        ch_list = pre.get("channel_list", [])
        uk = pre.get("upload_key", "")
        ex = pre.get("ex", "")
        ch = next((c for c in ch_list if int(c.get("len", 0)) > 0), None)
        if ch is None:
            state = int(pre.get("upload_state", 0))
            if state == 2:
                print(f"     [完成] file_id={pre.get('file_id','')}", flush=True)
                return pre
            raise RuntimeError(f"无可上传通道, upload_state={state}")
        offset = int(ch["offset"])
        length = int(ch["len"])
        channel_id = int(ch["id"])
        actual = min(length, len(blob) - offset)
        pct = min(100, int(offset / file_size * 100))
        chunk_b64 = base64.b64encode(blob[offset:offset + actual]).decode()
        cl = [{"id": int(c["id"]), "offset": int(c["offset"]),
               "len": int(c["len"])} for c in ch_list]
        up = _call_retry("weiyun.upload", {
            "filename": filename,
            "file_size": file_size,
            "file_sha": params["file_sha"],
            "block_sha_list": [],
            "check_sha": params["check_sha"],
            "upload_key": uk,
            "channel_list": cl,
            "channel_id": channel_id,
            "ex": ex,
            "file_data": chunk_b64,
        })
        if up.get("error"):
            raise RuntimeError(f"分片失败: {up['error']}")
        if int(up.get("upload_state", 0)) == 2:
            print(f"     [{pct}%] 完成 file_id={up.get('file_id','')}",
                  flush=True)
            return up
        print(f"     [{pct}%] 分片 offset={offset} len={actual} ch={channel_id}",
              flush=True)
    raise RuntimeError(f"超过最大轮数 {max_rounds}")


def main():
    cmd = sys.argv[1]
    if cmd == "mkdir":
        parent, name = sys.argv[2], sys.argv[3]
        r = call("weiyun.create_dir", {"pdir_key": parent, "dir_name": name})
        print(json.dumps(r, ensure_ascii=False))
    elif cmd == "up":
        dst = sys.argv[2]
        files = sys.argv[3:]
        ok, fail = 0, 0
        for fp in files:
            print(f"\n[{ok+fail+1}/{len(files)}] {fp}", flush=True)
            try:
                upload_file(fp, dst)
                ok += 1
            except Exception as e:
                print(f"     !! 失败: {e}", flush=True)
                fail += 1
        print(f"\n=== 上传结束: 成功 {ok}, 失败 {fail} ===", flush=True)
    else:
        print("未知命令", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
