#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_idfix.py —— C 修法：防「上传后自抖」

现象（实测规律，100% 吻合）：
    非秒传上传 → 下一轮必执行一次多余下载；秒传上传 → 不抖。
    Mac 侧 sync.log 证据：
        22:02:20 ↑ 上传 _Mac验收回报.md (6 KB)      ← 非秒传
        22:02:38 ↓ 下载 _Mac验收回报.md (6 KB)      ← 白下载
        22:11:06 ↑ 上传 2026-09-26-mac.md [秒传]    ← 秒传
        （无下载）

根因：
    _do_upload() 把 client.upload() 返回的 file_id 直接写进基线。
    但非秒传（分片）路径返回的 id 与目录内真实文件的 file_id 不一致
    ⇒ 下一轮 snapshot_remote 比对时 r_changed=True、l_changed=False
    ⇒ 走 `not l_changed and r_changed` 分支 ⇒ 下载一份自己刚传的文件。

    秒传路径返回的就是已存在文件的真实 id，故不触发。

修法：
    上传后把基线 r_file_id 置 None（语义＝「本机刚传，待基线化」）。
    sync_once 已有该语义：`elif b.get("r_file_id") is None: r_changed = False`，
    且下一轮会进 `not l_changed and not r_changed` 分支调 _refresh_baseline()
    用 list 的真实值校准。⇒ 不再自抖，基线自动收敛。

特性：幂等（已打则跳过）、自动备份、语法校验、失败回滚。
"""

import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"

OLD = '''        fid, fast = client.upload(str(lp), rkey)
        st = local_stamp(lp)
        files_state[sk] = {
            "l_mtime": st["mtime"], "l_size": st["size"],
            "r_file_id": fid, "r_mtime": None, "r_size": size,
            "synced_at": int(time.time()),
        }'''

NEW = '''        fid, fast = client.upload(str(lp), rkey)
        st = local_stamp(lp)
        files_state[sk] = {
            "l_mtime": st["mtime"], "l_size": st["size"],
            # r_file_id 故意留 None：非秒传路径返回的 id 未必等于目录内真实
            # file_id（实测下一轮 list 会不一致 ⇒ 自判「远端变了」⇒ 白下载一份）。
            # 置 None 让下一轮 _refresh_baseline() 用 list 真实值校准。
            "r_file_id": None, "r_mtime": None, "r_size": size,
            "synced_at": int(time.time()),
        }'''

MARKER = '"r_file_id": None, "r_mtime": None, "r_size": size,'


def main():
    if not TARGET.exists():
        print("❌ 找不到 %s" % TARGET)
        return 1

    src = TARGET.read_text(encoding="utf-8", newline="")

    if MARKER in src:
        print("ℹ️  补丁已存在，跳过。")
        return 0

    if OLD not in src:
        print("❌ 锚点缺失，_do_upload 可能已被改动。")
        return 1

    bak = TARGET.with_name(
        TARGET.name + ".bak_pre_idfix_" + time.strftime("%Y%m%d"))
    shutil.copy2(str(TARGET), str(bak))
    print("已备份 → %s" % bak.name)

    out = src.replace(OLD, NEW, 1)

    try:
        ast.parse(out)
    except SyntaxError as e:
        print("❌ 替换后语法错误，已回滚：%s" % e)
        return 1

    TARGET.write_text(out, encoding="utf-8", newline="\n")
    print("✅ 打补丁成功，语法校验通过。")
    print("   文件：%d B → %d B" % (len(src.encode("utf-8")),
                                   len(out.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
