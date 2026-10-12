#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H 补丁（rofix）：修 G 补丁的副作用 —— 只读文件被拦下后基线不刷新 ⇒ 日志刷屏。

背景（对端 2026-09-26 回报）
============================
G 补丁把「非写者机本地改了也不上传」变成机制，但它拦下上传后 **没有刷新基线**：

    if l_changed and lp is not None and is_readonly(key, cfg):
        log("只读文件本地有改动，按规约不上传 [%s]" % sk, "INFO")
        l_changed = False          # ← 只改内存判定，不动 files_state

后果：`b["l_mtime"]` 永远停在旧值。而 `l_changed = (mtime != b.l_mtime)` ⇒
**只要本地 mtime 与基线不同，每轮都重新判为「有改动」⇒ 每轮打一行 INFO**，
即使内容一字未变。对端实测「撤销改动后仍连刷 5 行」，直到 `os.utime` 把
mtime 手动恢复基线才停 —— 这是**靠外部手段掩盖症状**，不是修好。

修法
====
拦下时顺手把基线收敛掉，分两种情况：

  ① **内容未变**（`lstamp.size == b.l_size`，只有 mtime 被 touch）：
     把 mtime 刷进基线 ⇒ 状态收敛，下一轮不再判「有改动」，**零日志**。
     安全：size 相同且我们本来就不上传，刷基线不改变「不上传」这件事。
  ② **内容真变了**（size ≠ 基线）：
     仍然不上传（规约），但**日志只在「状态变化」时打一次** ——
     把当时的 `size|mtime` 记进 `b["ro_stamp"]`，相同就不再重复打。
     不刷 l_mtime/l_size：否则会把「本地与远端不一致」这件事静默吞掉。

⇒ 无论哪种情况都不再刷屏，且**不掩盖真实分歧**。

幂等：已注入则跳过。
"""
import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"
STAMP = time.strftime("%Y%m%d")
MARKER = "RO-TIDY"

OLD_BLOCK = '''            # ⚠️ G 补丁：只读文件（共享文件）—— 本地改了也不上传，只跟随远端。
            if l_changed and lp is not None and is_readonly(key, cfg):
                log("只读文件本地有改动，按规约不上传 [%s]" % sk, "INFO")
                l_changed = False
'''

NEW_BLOCK = '''            # ⚠️ G 补丁：只读文件（共享文件）—— 本地改了也不上传，只跟随远端。
            # --- RO-TIDY (H patch 20260926) ---
            # 修 G 的副作用：拦下上传后基线 l_mtime 不刷新 ⇒ 本地 mtime 一变就每轮刷 INFO。
            # ① 内容未变（size == 基线 l_size）⇒ 把 mtime 刷进基线，静默收敛；
            # ② 内容真变了 ⇒ 仍不上传（规约），但日志只在「状态变化」时打一次（ro_stamp 去重），
            #    且**不**刷 l_mtime/l_size —— 否则等于静默吞掉「本地与远端不一致」。
            if l_changed and lp is not None and is_readonly(key, cfg):
                if (b is not None and b.get("l_mtime") is not None
                        and b.get("l_size") == lstamp["size"]):
                    b["l_mtime"] = lstamp["mtime"]
                    b["l_size"] = lstamp["size"]
                elif b is not None:
                    _stamp = "%s|%s" % (lstamp["size"], lstamp["mtime"])
                    if b.get("ro_stamp") != _stamp:
                        log("只读文件本地有改动，按规约不上传 [%s]" % sk, "INFO")
                        b["ro_stamp"] = _stamp
                l_changed = False
'''


def main():
    if not TARGET.exists():
        print("ERROR: 找不到 %s" % TARGET)
        return 1
    src = TARGET.read_text(encoding="utf-8", newline="")
    if MARKER in src:
        print("已打过 H 补丁（%s 存在），跳过。" % MARKER)
        return 0

    n = src.count(OLD_BLOCK)
    print("锚点 OLD_BLOCK 命中 %d 次" % n)
    if n != 1:
        print("ERROR: 锚点必须恰好 1 次，中止以免误改")
        return 1

    bak = TARGET.with_name(TARGET.name + ".bak_pre_rofix_" + STAMP)
    if not bak.exists():
        shutil.copy2(TARGET, bak)
        print("已备份 → %s" % bak.name)

    out = src.replace(OLD_BLOCK, NEW_BLOCK, 1)
    out += "\n\n# --- %s (H patch %s) ---\n" % (MARKER, STAMP)

    try:
        ast.parse(out)
    except SyntaxError as e:
        print("ERROR: 补丁后语法错误 %s，放弃写入" % e)
        return 1

    tmp = TARGET.with_suffix(".py.tmp")
    tmp.write_text(out, encoding="utf-8", newline="\n")
    tmp.replace(TARGET)
    print("✅ H 补丁完成：%d → %d B" % (len(src.encode()), len(out.encode())))
    print("   语法校验通过；备份 %s" % bak.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
