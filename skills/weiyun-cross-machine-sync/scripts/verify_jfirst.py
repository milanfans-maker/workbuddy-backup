#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""J（firstsync-guard）负样本验证 —— 专测「首次同步分支绕过只读守卫」这个洞。

原则（沿用 verify_hi.py）：**先怀疑探针**。每个用例都必须能给「补丁前 / 补丁后」
**相反**的结论，否则测不出分辨力。探针自身的两个老坑已规避：
   ① 模块 LOG_FILE 在 import 时按 JUNQI_SYNC_HOME 定死 ⇒ 读日志必须用同一隔离目录；
   ② 假客户端远端条目**固定**，不跟本地变，否则 r_changed 会被搅乱。

对端 2026-09-27 实测的洞（本组 A/B/C 就是它的三个面）：
    `b is None` 首次同步分支、`本地有/远端无` 分支 —— 都在 G 守卫**之后**独立判定，
    与 `l_changed` 无关 ⇒ G 改了 l_changed 也拦不住，照样 _do_upload。

对端 2026-09-27 第二轮要求补的断言（本组 F —— **判据是"下载行为"不是"日志行数"**）：
    只读 + **已有基线** + 本地内容变（大小≠远端）：
      旧版（H）只打日志、**不下不传**（本地分歧就此搁置）；
      收口版（J）**跟随远端下载**，把本地拉回写者版本。
    旧探针只数日志行 ⇒ 两种行为都只有 1 行日志，**测不出**。故本组直接断言 download 计数。

已知限制（本组 G —— **不计入 FAIL**，仅记录）：
    收口用「本地大小 vs 远端大小」判别，**远端同大小改内容**时判为"一致"⇒ 不下载
    ⇒ 非写者会静默 stale。与「B（size 闸门）永不做」同源，属**已识别未修**。

用例
====
A（洞 · 正样本） 只读 + 无基线 + 本地≠远端   → 前：**上传**(覆盖写者) / 后：不上传，跟随远端下载
B（收敛）        只读 + 无基线 + 本地=远端   → 前后都不上传；后：只补基线
C（不复活）      只读 + 无基线 + 远端已删   → 前：上传复活 / 后：不上传
D（负样本）    非只读 + 无基线 + 本地≠远端 → 前后**都**上传（证明没误伤普通文件）
E（兜底闸门）    直接调 _do_upload(只读)     → 后：拒传 + 打「只读兜底闸门」ERROR
F（有基线 · 对端点名）只读 + **有基线** + 本地变(大小≠远端) → 前：只打日志、不上不下 / 后：**下载**
G（已知限制 · 记录）只读 + 有基线 + 远端同大小改内容 → 后：不下载（静默 stale，未修）
"""
import importlib.util
import os
import pathlib
import shutil
import sys
import tempfile

REAL_HOME = pathlib.Path.home() / ".junqi-sync"
SANDBOX = pathlib.Path("/tmp/jq-verify-j")
FAIL = []

P_SMALL = b"hello world\n" * 200      # 2400 B
P_BIG = b"hello world\n" * 400        # 4800 B
P_ALT = b"goodbye wrld\n" * 200       # 2400 B —— 与 P_SMALL 同大小、内容不同


def check(name, cond, detail=""):
    print("   %-50s %s %s" % (name, "✅ PASS" if cond else "❌ FAIL", detail))
    if not cond:
        FAIL.append(name)


def note(name, detail=""):
    """仅记录、不计分（已知限制/观察）。"""
    print("   %-50s ℹ️  NOTE %s" % (name, detail))


def load_module(name, path, isolate_dir):
    tmp = pathlib.Path(tempfile.mkdtemp()) / (name + ".py")
    shutil.copy2(path, tmp)
    os.environ["JUNQI_SYNC_HOME"] = str(isolate_dir)
    spec = importlib.util.spec_from_file_location(name, tmp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def log_text(isolate_dir):
    p = pathlib.Path(isolate_dir) / "logs" / "sync.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


class FakeClient:
    """远端条目**固定**（传进来的字典），本地怎么变都不动它。

    `dl_content` 给定后，download() 会**真的把内容写进目标路径** —— 这样才能断言
    「收敛」（本地被拉回写者版本），而不只是「调用过 download」。
    """

    def __init__(self, remote, dl_content=None):
        self.remote = dict(remote)
        self.dl_content = dl_content
        self.uploads = 0
        self.downloads = 0
        self.deletes = 0

    def list_dir(self, dk, pk=None):
        return dict(self.remote)

    def upload(self, *a, **k):
        self.uploads += 1
        return ("NEWID", False)

    def download(self, file_id, dir_key, dest, expect_size=None):
        self.downloads += 1
        if self.dl_content is not None:
            pathlib.Path(dest).write_bytes(self.dl_content)
            return len(self.dl_content)
        return -1

    def delete_file(self, *a, **k):
        self.deletes += 1

    def delete_by_name(self, *a, **k):
        return 0


def build(mod, tag, readonly, remote, payload, use_baseline=False,
          base_l_size=None, base_r_size=None, base_r_id="REMOTE1"):
    work = SANDBOX / ("j_" + tag)
    if work.exists():
        shutil.rmtree(work)
    local = work / "local"
    local.mkdir(parents=True)
    (local / "MEMORY.md").write_bytes(payload)
    cfg = {
        "local_base": str(local),
        "readonly_globs": ["MEMORY.md"] if readonly else [],
        "exclude": ["*.bak*", "*.tmp", "*~", ".DS_Store", "*.conflict-*"],
        "delete_policy": "ignore",
        "debounce": 0,
        "roots": [{"name": "R", "remote_dir_key": "K",
                   "remote_parent_key": "P", "globs": ["*.md"]}],
    }
    state = {"files": {}}
    if use_baseline:
        st = (local / "MEMORY.md").stat()
        state["files"]["R/MEMORY.md"] = {
            "l_mtime": st.st_mtime,
            "l_size": st.st_size if base_l_size is None else base_l_size,
            "r_file_id": base_r_id,
            "r_mtime": 1758900000000,
            "r_size": len(payload) if base_r_size is None else base_r_size,
            "synced_at": 0}
    return cfg, state


def run_case(mod, tag, readonly, remote, payload, iso_dir, use_baseline=False,
             base_l_size=None, base_r_size=None, base_r_id="REMOTE1",
             dl_content=None):
    cfg, state = build(mod, tag, readonly, remote, payload, use_baseline,
                       base_l_size, base_r_size, base_r_id)
    client = FakeClient(remote, dl_content)
    before = len(log_text(iso_dir))
    mod.sync_once(client, cfg, state, dry=False)
    delta = log_text(iso_dir)[before:]
    lp = pathlib.Path(cfg["local_base"]) / "MEMORY.md"
    return {"up": client.uploads, "down": client.downloads,
            "del": client.deletes, "state": state,
            "base": state["files"].get("R/MEMORY.md"),
            "log": delta, "l_size": lp.stat().st_size}


def main():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)

    old_bak = sorted(REAL_HOME.glob("junqi_sync.py.bak_pre_jfirstfix_*"))[-1]
    new_py = REAL_HOME / "junqi_sync.py"
    print("补丁前 = %s（%d B，H+I 版 = 对端收口前的版本）"
          % (old_bak.name, old_bak.stat().st_size))
    print("补丁后 = junqi_sync.py（%d B，+J 收口）" % new_py.stat().st_size)
    print()

    iso_old, iso_new = SANDBOX / "iso_old", SANDBOX / "iso_new"
    OLD = load_module("js_old_j", old_bak, iso_old)
    NEW = load_module("js_new_j", new_py, iso_new)

    REMOTE_DIFF = {"MEMORY.md": {"filename": "MEMORY.md", "file_id": "REMOTE1",
                                 "file_size": len(P_BIG), "file_mtime": 1758900000000}}
    REMOTE_SAME = {"MEMORY.md": {"filename": "MEMORY.md", "file_id": "REMOTE1",
                                 "file_size": len(P_SMALL), "file_mtime": 1758900000000}}
    REMOTE_NONE = {}

    print("=== A 组：只读 + 无基线 + 本地(%d)≠远端(%d) —— 这是那个洞 ==="
          % (len(P_SMALL), len(P_BIG)))
    oA = run_case(OLD, "a_old", True, REMOTE_DIFF, P_SMALL, iso_old)
    nA = run_case(NEW, "a_new", True, REMOTE_DIFF, P_SMALL, iso_new)
    print("  补丁前: 上传=%d 下载=%d   补丁后: 上传=%d 下载=%d"
          % (oA["up"], oA["down"], nA["up"], nA["down"]))
    check("A-1 补丁前**确实**会上传（洞成立 · 分辨力前提）", oA["up"] == 1)
    check("A-2 补丁后零上传（写者不再被覆盖）", nA["up"] == 0)
    check("A-3 补丁后改为跟随远端下载（能收敛，不是干等）", nA["down"] == 1)

    print()
    print("=== B 组：只读 + 无基线 + 大小一致 ===")
    oB = run_case(OLD, "b_old", True, REMOTE_SAME, P_SMALL, iso_old)
    nB = run_case(NEW, "b_new", True, REMOTE_SAME, P_SMALL, iso_new)
    print("  补丁前: 上传=%d   补丁后: 上传=%d 基线=%s"
          % (oB["up"], nB["up"], "已补" if nB["base"] else "无"))
    check("B-1 前后都零上传", oB["up"] == 0 and nB["up"] == 0)
    check("B-2 补丁后基线已补上（下轮不再重复判定）", nB["base"] is not None)

    print()
    print("=== C 组：只读 + 无基线 + 远端已删（本地有/远端无）===")
    oC = run_case(OLD, "c_old", True, REMOTE_NONE, P_SMALL, iso_old)
    nC = run_case(NEW, "c_new", True, REMOTE_NONE, P_SMALL, iso_new)
    print("  补丁前: 上传=%d   补丁后: 上传=%d" % (oC["up"], nC["up"]))
    check("C-1 补丁前会上传（把写者删掉的文件复活）", oC["up"] == 1)
    check("C-2 补丁后不上传（不复活）", nC["up"] == 0)

    print()
    print("=== D 组（负样本）：非只读 + 无基线 + 本地≠远端 ===")
    oD = run_case(OLD, "d_old", False, REMOTE_DIFF, P_SMALL, iso_old)
    nD = run_case(NEW, "d_new", False, REMOTE_DIFF, P_SMALL, iso_new)
    print("  补丁前: 上传=%d   补丁后: 上传=%d" % (oD["up"], nD["up"]))
    check("D-1 普通文件照旧上传（补丁没误伤）", oD["up"] == 1 and nD["up"] == 1)

    print()
    print("=== E 组：兜底闸门（canary）—— 直接调 _do_upload ===")
    cfg, state = build(NEW, "e_new", True, REMOTE_DIFF, P_SMALL)
    lp = pathlib.Path(cfg["local_base"]) / "MEMORY.md"
    c = FakeClient(REMOTE_DIFF)
    stats = {"up": 0, "down": 0, "conflict": 0, "skip": 0, "err": 0}
    before = len(log_text(iso_new))
    NEW._do_upload(c, cfg, state["files"], "R/MEMORY.md", "MEMORY.md",
                   lp, "K", stats, False)
    tail = log_text(iso_new)[before:]
    print("  上传=%d  skip=%d  日志: %s"
          % (c.uploads, stats["skip"], tail.strip().splitlines()[-1:]))
    check("E-1 绕过收口的上传被拒（canary 生效）", c.uploads == 0)
    check("E-2 留下响亮 ERROR（可发现新分支）", "只读兜底闸门" in tail)

    print()
    print("=== F 组（对端点名的断言）：只读 + **已有基线** + 本地内容变（大小≠远端）===")
    print("    判据是**下载行为**，不是日志行数 —— 旧版与新版都只打 1 行日志。")
    oF = run_case(OLD, "f_old", True, REMOTE_DIFF, P_SMALL, iso_old,
                  use_baseline=True, base_l_size=len(P_SMALL) - 100,
                  base_r_size=len(P_BIG), dl_content=P_BIG)
    nF = run_case(NEW, "f_new", True, REMOTE_DIFF, P_SMALL, iso_new,
                  use_baseline=True, base_l_size=len(P_SMALL) - 100,
                  base_r_size=len(P_BIG), dl_content=P_BIG)
    print("  补丁前: 上传=%d 下载=%d 本地=%d   补丁后: 上传=%d 下载=%d 本地=%d"
          % (oF["up"], oF["down"], oF["l_size"],
             nF["up"], nF["down"], nF["l_size"]))
    check("F-1 补丁前只打日志、**不上不下**（本地分歧被搁置）",
          oF["down"] == 0 and oF["up"] == 0 and "只读文件本地有改动" in oF["log"])
    check("F-2 补丁后**跟随远端下载**（对端点名的行为，方向正确）",
          nF["down"] == 1)
    check("F-3 补丁后本地被拉回写者版本（真收敛，非只调用）",
          nF["l_size"] == len(P_BIG) and nF["base"] is not None
          and nF["base"]["l_size"] == len(P_BIG))

    print()
    print("=== G 组（已知限制 · 仅记录，不计分）：只读 + 有基线 + 远端**同大小**改内容 ===")
    nG = run_case(NEW, "g_new", True, REMOTE_SAME, P_SMALL, iso_new,
                  use_baseline=True, base_l_size=len(P_SMALL),
                  base_r_size=len(P_SMALL), base_r_id="OLDID",
                  dl_content=P_ALT)
    print("  收口版: 下载=%d（远端 file_id 由 REMOTE1→OLDID、内容已变）" % nG["down"])
    note("G-1 远端同大小改内容 ⇒ 判为「一致」不下载",
         "⇒ 非写者静默 stale（与「B size 闸门」同源，已识别未修）")

    print()
    if FAIL:
        print("❌ 共 %d 项未通过: %s" % (len(FAIL), FAIL))
        return 1
    print("✅ 全部通过（A/C/F 组补丁前 FAIL 是预期，证明有分辨力）")
    print("   ℹ️  G 组为已知限制，仅记录；未通过项不含它。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
