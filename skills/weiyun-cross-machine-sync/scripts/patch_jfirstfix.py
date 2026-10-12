#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""J 补丁（firstsync-guard）：只读闸门**下沉为单一收口**，堵住 G/H 漏掉的首次同步路径。

洞在哪（对端 2026-09-27 实测）
==============================
`sync_once` 里能调到 `_do_upload` 的路径不止一条，而 G/H 只守住了其中一条：

    if l_changed and lp is not None and is_readonly(key, cfg):   # ← G：只在 l_changed 为真时进
        ...
        l_changed = False

问题在于 **G 改的是 `l_changed` 这个内存判定，而下游分支不是全都依赖它**：

    676 行  if b is None:            # ← 首次同步：只看 b 是不是 None，与 l_changed 无关
    684-687  ... 大小不一致 ⇒ _do_upload(...)         ← ★ 绕过守卫

同理 665 行「本地有 / 远端无」分支也是独立判定（`b is None or delete_policy != mirror`）
⇒ 也会上传。对端实测 `00:09:06 ↑ 上传 三任务-文件对照表.md [秒传]` 正是第一条。

⇒ 病根不是「漏了某一行」，而是**闸门挂在分支上** —— 分支会变形、会增加，
每补一次只挪一格。所以本补丁不再给分支打补丁，改成**收口**。

修法
====
只读文件（`readonly_globs` 命中）且有本地文件的，在**分支分发之前**统一决定去向，
然后 `continue` —— 后面的任何分支都不再有机会把它推上去：

    远端无     ⇒ 不复活（不上传）
    大小不符   ⇒ 跟随写者下载（只下不上）
    大小一致   ⇒ 只补基线（H 的静默收敛）

另在 `_do_upload` 入口加**兜底闸门（canary）**：万一将来又有人加了一条绕过收口的
分支，宁可拒传 + 打 ERROR，也不覆盖写者。

⚠️ 本机（Mac）**不配 `readonly_globs`** ⇒ 补丁后**行为零变化**（我是写者）。
   价值在于：① 对端配置后机制真正闭合；② skill 里的机制描述不再有洞。

幂等：已注入则跳过。行尾：读 `newline=""`、写 `newline="\\n"`（自指风险，见 skill）。
"""
import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"
STAMP = time.strftime("%Y%m%d")
MARKER = "FIRSTSYNC-GUARD"

# ---------------------------------------------------------------- 锚点 1：收口块
OLD_GUARD = '''            # ⚠️ G 补丁：只读文件（共享文件）—— 本地改了也不上传，只跟随远端。
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

NEW_GUARD = '''            # ⚠️ G+H+J：只读文件（共享文件）—— **永不上传**，只跟随写者。
            # --- RO-TIDY (H patch 20260926) ---
            # ① 内容未变 ⇒ 静默把 mtime 刷进基线（否则每轮刷 INFO）；
            # ② 内容真变 ⇒ 不上传，日志按状态去重（不刷 l_mtime/l_size，不掩盖分歧）。
            # --- FIRSTSYNC-GUARD (J patch %STAMP%) ---
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
'''.replace("%STAMP%", STAMP)

# ---------------------------------------------------------------- 锚点 2：日志去重助手
OLD_HELPER = '''def _glob_basename(g):
    """取 glob 的文件名部分，兼容 Windows 分隔符。"""
    return g.replace("\\\\", "/").rsplit("/", 1)[-1]
'''

NEW_HELPER = OLD_HELPER + '''

# --- FIRSTSYNC-GUARD (J patch %STAMP%) ---
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
'''.replace("%STAMP%", STAMP)

# ---------------------------------------------------------------- 锚点 3：_do_upload 兜底
OLD_UP = '''def _do_upload(client, cfg, files_state, sk, key, lp, rkey, stats, dry,
               existing=None):
    size = lp.stat().st_size
'''

NEW_UP = '''def _do_upload(client, cfg, files_state, sk, key, lp, rkey, stats, dry,
               existing=None):
    # --- FIRSTSYNC-GUARD (J patch %STAMP%) ---
    # 兜底闸门（canary）：只读闸门应收口在 sync_once 里。若真走到这里，说明又有人
    # 加了一条绕过收口的上传分支 —— 宁可拒传 + 响亮报错，也不覆盖写者。
    if is_readonly(key, cfg):
        log("⛔ 只读兜底闸门拒绝上传 [%s] —— 有分支绕过了收口，请检查" % key,
            "ERROR")
        stats["skip"] += 1
        return
    size = lp.stat().st_size
'''.replace("%STAMP%", STAMP)


def main():
    if not TARGET.exists():
        print("ERROR: 找不到 %s" % TARGET)
        return 1
    src = TARGET.read_text(encoding="utf-8", newline="")
    if MARKER in src:
        print("已打过 J 补丁（%s 存在），跳过。" % MARKER)
        return 0

    for name, anchor in (("收口块", OLD_GUARD), ("helper", OLD_HELPER),
                         ("_do_upload", OLD_UP)):
        n = src.count(anchor)
        print("锚点 %-12s 命中 %d 次" % (name, n))
        if n != 1:
            print("ERROR: 锚点 %s 必须恰好 1 次，中止以免误改" % name)
            return 1

    bak = TARGET.with_name(TARGET.name + ".bak_pre_jfirstfix_" + STAMP)
    if not bak.exists():
        shutil.copy2(TARGET, bak)
        print("已备份 → %s" % bak.name)

    out = src.replace(OLD_GUARD, NEW_GUARD, 1)
    out = out.replace(OLD_HELPER, NEW_HELPER, 1)
    out = out.replace(OLD_UP, NEW_UP, 1)
    out += "\n\n# --- %s (J patch %s) ---\n" % (MARKER, STAMP)

    try:
        ast.parse(out)
    except SyntaxError as e:
        print("ERROR: 补丁后语法错误 %s，放弃写入" % e)
        return 1

    tmp = TARGET.with_suffix(".py.tmp")
    tmp.write_text(out, encoding="utf-8", newline="\n")
    tmp.replace(TARGET)
    print("✅ J 补丁完成：%d → %d B" % (len(src.encode()), len(out.encode())))
    print("   语法校验通过；备份 %s" % bak.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
