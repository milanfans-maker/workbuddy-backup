#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台「安全全链重放」—— 把补丁链跑在隔离副本上，**绝不碰真文件**。

为什么需要这个脚本
==================
补丁脚本里 `TARGET = Path.home()/".junqi-sync"/"junqi_sync.py"`，
而 `Path.home()`（= `os.path.expanduser("~")`）有**平台差异**：

    macOS / Linux : 读 `HOME`
    Windows       : 读 `USERPROFILE`  ← **完全不认 `HOME`**

⇒ **只设 `HOME` 在 Windows 上彻底无效**，补丁会径直去改**真文件**。
（2026-09-26 实测踩过：幸而当时真文件已含 `_pid_alive`、幂等跳过了，
  才没被改坏 —— 那是运气，不是设计。）

本脚本把「隔离」做成**可断言**的三步：
  1. 跑前记录真文件 sha256
  2. 在临时目录重建 `.junqi-sync`（起点 = 指定备份 + 9 个补丁），
     子进程里 **同时** 设 `HOME` 与 `USERPROFILE`
  3. 跑后**断言真文件 sha256 未变** —— 变了就说明隔离失效，立即报警

另外每步都核字节数（对不上就停），终态核 sha256。

用法
----
    python3 replay_chain_safe.py
    python3 replay_chain_safe.py --start junqi_sync.py.bak_pre_pidfix_20260926

⚠️ Windows 上跑也**不要**依赖 `$env:HOME`，本脚本已代劳；直接调用即可。
"""
import argparse
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

SRC = pathlib.Path(__file__).resolve().parent
REAL = SRC / "junqi_sync.py"

PATCHES = ["patch_pidfix.py", "patch_metafix.py", "patch_idfix.py",
           "patch_eolfix.py", "patch_racefix.py",
           "patch_writerlock.py", "patch_rofix.py", "patch_collidefix.py",
           "patch_jfirstfix.py"]
# 38205 / d03e5c2f…、39173 / 80fa9978…、41785 / 60105070… 是历史里程碑，
# 保留作中间校验点（末位新增 43496 = J 只读收口）
EXPECT = [34924, 36298, 36592, 36712, 38205, 39173, 40175, 41785, 43496]
FINAL_SHA = "9da0889e54746144e50a5ec4e0b273755a5912b00b03484853936903fec41cdc"
# ⚠️ 原始 sha256 只在「同一天」跑才吻合：补丁脚本把 `%Y%m%d` 追进标记行，
#    跨天重放 ⇒ 字节数一致但哈希必变（2026-09-26→27 实测）。
#    ⇒ **跨机/跨天判分请用归一化哈希**（见 norm_sha.py）。
FINAL_NORM_SHA = "d34d24b76f55adb6143f54bd014d37f351c9b94af9eaeef4b7aba2f029e5eef9"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _norm(p):
    """归一化哈希：抹掉标记行里的 %Y%m%d（**必须与 norm_sha.py 同一算法**）。

    ⚠️ 别用 `splitlines()+join("\\n")` —— 那会吃掉末尾换行，与 norm_sha.py
       算出不同的值（本次首版就踩了：3ab42da0 vs 9094ae2c）。
    """
    txt = pathlib.Path(p).read_text(encoding="utf-8", newline="")
    out = re.sub(r"(?m)^\s*# --- .*$",
                 lambda m: re.sub(r"20\d{6}", "YYYYMMDD", m.group(0)), txt)
    return hashlib.sha256(out.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="junqi_sync.py.bak_pre_pidfix_20260926",
                    help="起点备份文件名（默认 33428 B 那份）")
    a = ap.parse_args()

    start = SRC / a.start
    if not start.exists():
        print("ERROR: 找不到起点 %s" % start)
        return 1
    if not REAL.exists():
        print("ERROR: 找不到真文件 %s" % REAL)
        return 1

    before = sha(REAL)
    print("真文件 sha256（跑前） = %s" % before[:32])
    print("起点   %-38s %6d B" % (start.name, start.stat().st_size))
    print()

    iso = pathlib.Path(tempfile.mkdtemp(prefix="jq-replay-"))
    iso_d = iso / ".junqi-sync"
    iso_d.mkdir(parents=True)
    shutil.copy2(start, iso_d / "junqi_sync.py")
    for p in PATCHES:
        shutil.copy2(SRC / p, iso_d / p)

    # ⚠️ 关键：HOME(POSIX) 与 USERPROFILE(Windows) **都要设**
    env = dict(os.environ, HOME=str(iso), USERPROFILE=str(iso),
               PYTHONDONTWRITEBYTECODE="1")

    target = iso_d / "junqi_sync.py"
    ok = True
    for p, exp in zip(PATCHES, EXPECT):
        r = subprocess.run([sys.executable, str(iso_d / p)],
                           capture_output=True, text=True, env=env)
        got = target.stat().st_size
        flag = "OK " if got == exp else "BAD"
        if got != exp:
            ok = False
        print("  + %-20s → %6d B （期望 %6d）%s" % (p[:-3], got, exp, flag))
        if not ok:
            print("      stdout: %s" % (r.stdout or "").strip()[:300])
            print("      stderr: %s" % (r.stderr or "").strip()[:300])
            break

    final = sha(target)
    size = target.stat().st_size
    crlf = target.read_bytes().count(b"\r\n")
    final_norm = _norm(target)
    print()
    print("终态：%d B  CRLF=%d" % (size, crlf))
    print("      sha256        = %s  %s"
          % (final, "OK" if final == FINAL_SHA else "★ 不同（可能只是跨天日期戳）"))
    print("      归一化 sha256 = %s  %s"
          % (final_norm, "OK" if final_norm == FINAL_NORM_SHA else "★ MISMATCH"))

    after = sha(REAL)
    iso_ok = after == before
    print()
    print("真文件 sha256（跑后） = %s  %s"
          % (after[:32], "未变 ✅ 隔离生效" if iso_ok else "★ 变了 ⇒ 隔离失效！"))

    # 交叉自检：真文件的归一化哈希必须也等于目标值 —— 否则脚本自身算法有偏
    real_norm = _norm(REAL)
    real_norm_ok = real_norm == FINAL_NORM_SHA
    print("真文件 归一化 sha256   = %s  %s"
          % (real_norm, "与重放件一致 ✅" if real_norm_ok else "★ 与重放件不一致"))

    shutil.rmtree(iso, ignore_errors=True)
    good = (ok and final_norm == FINAL_NORM_SHA and crlf == 0 and iso_ok
            and real_norm_ok)
    print()
    print("⇒ %s" % ("✅ 全链可复现（归一化哈希吻合），且真文件零接触"
                    if good else "❌ 未通过，检查上面 BAD/★ 行"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
