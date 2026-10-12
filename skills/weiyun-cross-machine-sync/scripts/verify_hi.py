#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H（rofix）+ I（collidefix）负样本验证。

原则：**先怀疑探针**。每个用例都要能给「补丁前 / 补丁后」两个相反结论，
否则测不出分辨力。

⚠️ 探针本身的坑（本次首轮就踩了，记下来）：
   ① 模块的 `LOG_FILE` 在**它自己 import 时**按 `JUNQI_SYNC_HOME` 定死 ⇒
      读取必须用**同一个隔离目录**，另建一个目录读是永远 0 行（假 PASS）。
   ② 假客户端的远端 size 若跟着本地文件变，`r_changed` 会被搅成 True ⇒
      把「只读文件」场景带进冲突分支。**远端条目要固定**。

H 组：只读文件日志刷屏（端到端驱动 sync_once）
    A 内容未变、只有 mtime 落后（touch 之后）→ 补丁前：每轮 1 行 INFO
                                            → 补丁后：**0 行**，基线 mtime 收敛
    B 内容真变了（size 变）                  → 补丁后：**仅首次 1 行**，重复轮 0 行
    C 全程断言：只读文件**一次都没上传**
    D 内容真变 ⇒ **跟随远端下载**（判据是「下载行为」，不是日志行数）
      —— 旧版(G)只打日志不下；J 收口版下载 1 次（对端 2026-09-27 点名要求）

I 组：撞名 CAS（直接驱动 WeiyunClient.upload）
    A 并发写（本轮列表无此条目 ⇒ expected_id=None，撞名时已存在）→ 拒绝删远端
    B 自己旧版（expected_id == 远端 id）                          → 照旧先删后传
    C 负样本对照：不撞名                                          → 直接返回、零删除
"""
import importlib.util
import os
import pathlib
import shutil
import sys
import tempfile

REAL_HOME = pathlib.Path.home() / ".junqi-sync"
SANDBOX = pathlib.Path("/tmp/jq-verify-hi")

FAIL = []


def check(name, cond, detail=""):
    print("   %-44s %s %s" % (name, "✅ PASS" if cond else "❌ FAIL", detail))
    if not cond:
        FAIL.append(name)


def load_module(name, path, isolate_dir):
    """把 .py / .bak 加载成独立模块，并让它把日志写到指定隔离目录。"""
    tmp = pathlib.Path(tempfile.mkdtemp()) / (name + ".py")
    shutil.copy2(path, tmp)
    os.environ["JUNQI_SYNC_HOME"] = str(isolate_dir)
    spec = importlib.util.spec_from_file_location(name, tmp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def mark_count(isolate_dir, mark):
    p = pathlib.Path(isolate_dir) / "logs" / "sync.log"
    txt = p.read_text(encoding="utf-8") if p.exists() else ""
    if isinstance(mark, (tuple, list)):
        return sum(txt.count(m) for m in mark)
    return txt.count(mark)


# ⚠️ J 收口改了日志文案：旧「只读文件本地有改动，按规约不上传」
#    → 新「只读文件 [sk] … ⇒ 不传」。**多串兼容新旧**，否则「文案变了」会被
#    误报成「行为回归」（对端 + 本机 2026-09-27 双双实测踩到 ⇒ 假 FAIL）。
H_MARK = ("只读文件本地有改动", "只读文件 [")
PAYLOAD0 = b"hello world\n" * 200          # 2400 B
PAYLOAD1 = b"hello world\n" * 400          # 4800 B


def h_scenario(mod, iso_dir):
    work = SANDBOX / ("h_" + pathlib.Path(iso_dir).name)
    if work.exists():
        shutil.rmtree(work)
    local = work / "local"
    local.mkdir(parents=True)
    target = local / "MEMORY.md"
    target.write_bytes(PAYLOAD0)

    cfg = {
        "local_base": str(local),
        "readonly_globs": ["MEMORY.md"],
        "exclude": ["*.bak*", "*.tmp", "*~", ".DS_Store", "*.conflict-*"],
        "delete_policy": "ignore",
        "roots": [{"name": "R", "remote_dir_key": "K",
                   "remote_parent_key": "P", "globs": ["*.md"]}],
    }

    class FakeClient:
        def __init__(self):
            self.uploads = self.downloads = 0

        def list_dir(self, dk, pk=None):
            # 远端条目**固定**（不跟本地变），否则 r_changed 会被搅成 True
            return {"MEMORY.md": {"filename": "MEMORY.md", "file_id": "REMOTE1",
                                  "file_size": len(PAYLOAD0),
                                  "file_mtime": 1758900000000}}

        def upload(self, *a, **k):
            self.uploads += 1
            return ("x", True)

        def download(self, *a, **k):
            self.downloads += 1
            return len(PAYLOAD0)

        def delete_file(self, *a, **k):
            pass

        def delete_by_name(self, *a, **k):
            return 0

    st = target.stat()
    state = {"files": {"R/MEMORY.md": {
        "l_mtime": st.st_mtime - 100,     # 基线 mtime 落后 ⇒ 判「本地变了」
        "l_size": st.st_size,             # 但 size 一致 ⇒ 内容其实没变
        "r_file_id": "REMOTE1", "r_mtime": 1758900000000,
        "r_size": len(PAYLOAD0), "synced_at": 0}}}
    client = FakeClient()

    r1 = mark_count(iso_dir, H_MARK)
    mod.sync_once(client, cfg, state, dry=False)
    n1 = mark_count(iso_dir, H_MARK) - r1

    r2 = mark_count(iso_dir, H_MARK)
    mod.sync_once(client, cfg, state, dry=False)
    n2 = mark_count(iso_dir, H_MARK) - r2

    mtime_fixed = (state["files"]["R/MEMORY.md"]["l_mtime"]
                   == round(target.stat().st_mtime, 3))

    dl_before = client.downloads
    target.write_bytes(PAYLOAD1)          # 内容真变了（size 2400 → 4800）
    r3 = mark_count(iso_dir, H_MARK)
    mod.sync_once(client, cfg, state, dry=False)
    n3 = mark_count(iso_dir, H_MARK) - r3
    dl_on_change = client.downloads - dl_before

    r4 = mark_count(iso_dir, H_MARK)
    mod.sync_once(client, cfg, state, dry=False)
    n4 = mark_count(iso_dir, H_MARK) - r4

    return {"r1": n1, "r2": n2, "mtime_fixed": mtime_fixed,
            "on_change": n3, "on_repeat": n4, "dl_on_change": dl_on_change,
            "uploads": client.uploads, "downloads": client.downloads}


def i_scenario(mod):
    tmp = pathlib.Path(tempfile.mkdtemp())
    f = tmp / "X.txt"
    f.write_bytes(b"payload\n" * 50)

    class C(mod.WeiyunClient):
        def __init__(self, remote, replies):
            self.remote = remote
            self.replies = list(replies)
            self.log = []

        def call(self, method, args):
            self.log.append(("call", method))
            return self.replies.pop(0)

        def list_dir(self, dk, pk=None):
            self.log.append(("list_dir", None))
            return dict(self.remote)

        def delete_file(self, fid, dk):
            self.log.append(("delete_file", fid))

        def delete_by_name(self, name, dk):
            self.log.append(("delete_by_name", name))
            return 1

    def has(c, kind, arg=None):
        return any(e[0] == kind and (arg is None or e[1] == arg) for e in c.log)

    # A 并发写：本轮列表里没有这个条目（expected_id=None），传到一半它已存在
    cA = C({"X.txt": {"filename": "X.txt", "file_id": "PEER1", "file_size": 999}},
           [{"file_exist": 1, "filename": "X.txt(1).md", "file_id": "MINE1"}])
    errA = ""
    try:
        cA.upload(str(f), "K", expected_id=None)
    except mod.WeiyunError as e:
        errA = str(e)
    A_ok = ("撞名冲突(并发写)" in errA) and not has(cA, "delete_by_name")

    # B 自己旧版：远端 id 与本轮已知一致 ⇒ 允许先删后传
    cB = C({"X.txt": {"filename": "X.txt", "file_id": "MINE0", "file_size": 1}},
           [{"file_exist": 1, "filename": "X.txt(1).md", "file_id": "MINE1"},
            {"file_exist": 1, "filename": "X.txt", "file_id": "MINE2"}])
    fidB, errB = "", ""
    try:
        fidB, _ = cB.upload(str(f), "K", expected_id="MINE0")
    except mod.WeiyunError as e:
        errB = str(e)
    B_ok = (errB == "") and has(cB, "delete_by_name", "X.txt") and fidB == "MINE2"

    # C 负样本：不撞名 ⇒ 什么都不该删
    cC = C({}, [{"file_exist": 1, "filename": "X.txt", "file_id": "MINE9"}])
    fidC, errC = "", ""
    try:
        fidC, _ = cC.upload(str(f), "K", expected_id=None)
    except mod.WeiyunError as e:
        errC = str(e)
    C_ok = (errC == "" and fidC == "MINE9"
            and not has(cC, "delete_by_name") and not has(cC, "delete_file"))

    return {"A": A_ok, "B": B_ok, "C": C_ok, "A_err": errA[:78],
            "A_deleted": [e for e in cA.log if e[0].startswith("delete")]}


def main():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)

    # ⚠️ 备份命名是「打该补丁**之前**的快照」⇒ 对端当前的 G 版 = bak_pre_rofix_*
    #    （bak_pre_writerlock_* 是 38205 的 F 版，无只读守卫 —— 拿它当对照会假 FAIL）
    old_bak = sorted(REAL_HOME.glob("junqi_sync.py.bak_pre_rofix_*"))[-1]
    old_size = old_bak.stat().st_size
    print("补丁前 = %s（%d B，G 版 = 对端当前版本）" % (old_bak.name, old_size))
    print("补丁后 = junqi_sync.py（%d B，H+I）"
          % (REAL_HOME / "junqi_sync.py").stat().st_size)
    print()

    iso_old, iso_new = SANDBOX / "iso_old", SANDBOX / "iso_new"
    OLD = load_module("js_old", old_bak, iso_old)
    NEW = load_module("js_new", REAL_HOME / "junqi_sync.py", iso_new)

    if old_size != 39173:
        print("⚠️ 对照版本字节不是 39173，疑似取错备份：%d" % old_size)
    print("=== H 组：只读文件日志刷屏（端到端 sync_once） ===")
    print("  （对照版本含 WRITER-LOCK 守卫: %s）"
          % ("WRITER-LOCK" in old_bak.read_text(encoding="utf-8", newline="")))
    o = h_scenario(OLD, iso_old)
    n = h_scenario(NEW, iso_new)
    print("  补丁前(G) 轮1=%d 轮2=%d | 内容变化时=%d 重复轮=%d" %
          (o["r1"], o["r2"], o["on_change"], o["on_repeat"]))
    print("  补丁后(H) 轮1=%d 轮2=%d | 内容变化时=%d 重复轮=%d" %
          (n["r1"], n["r2"], n["on_change"], n["on_repeat"]))
    print()
    check("H-A 补丁前确实刷屏（分辨力前提）", o["r1"] >= 1 and o["r2"] >= 1,
          "轮1=%d 轮2=%d" % (o["r1"], o["r2"]))
    check("H-A 补丁后：内容没变 ⇒ 零日志", n["r1"] == 0 and n["r2"] == 0,
          "轮1=%d 轮2=%d" % (n["r1"], n["r2"]))
    check("H-A 补丁后：基线 l_mtime 已收敛", n["mtime_fixed"])
    check("H-B 内容真变 ⇒ 恰好 1 行（不静默吞掉分歧）", n["on_change"] == 1,
          "实得 %d" % n["on_change"])
    check("H-B 重复轮不重复打（去重生效）", n["on_repeat"] == 0,
          "实得 %d" % n["on_repeat"])
    check("H-C 只读文件全程零上传", n["uploads"] == 0, "实得 %d" % n["uploads"])
    check("H-D 补丁前只打日志不下 / 补丁后**跟随远端下载**（分辨力 · 对端点名）",
          o["dl_on_change"] == 0 and n["dl_on_change"] == 1,
          "补丁前=%d 补丁后=%d" % (o["dl_on_change"], n["dl_on_change"]))

    print()
    print("=== I 组：撞名 CAS ===")
    r = i_scenario(NEW)
    print("  A 抛错: %s" % r["A_err"])
    print("  A 期间的删除动作: %s" % r["A_deleted"])
    check("I-A 并发写 ⇒ 拒绝并抛「撞名冲突(并发写)」", r["A"])
    check("I-A 并发写 ⇒ 不调 delete_by_name（不删对端）",
          not any(e[0] == "delete_by_name" for e in r["A_deleted"]))
    check("I-B 自己旧版 ⇒ 允许先删后传，拿到新 id", r["B"])
    check("I-C 负样本：不撞名 ⇒ 零删除", r["C"])

    print()
    if FAIL:
        print("❌ 共 %d 项未通过: %s" % (len(FAIL), FAIL))
        return 1
    print("✅ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
