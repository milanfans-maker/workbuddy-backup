#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G 补丁（writerlock）负样本验证：只读文件本地改了 ⇒ **不上传**；对照组 ⇒ 走正常上传。

隔离：JUNQI_SYNC_HOME 指向 /tmp/jq-lock，config.local_base 也指向该目录；
只用 **dry** 模式（不落盘、不上传）。**不触碰真实项目文件。**
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

home = pathlib.Path.home()
TEST = pathlib.Path("/tmp/jq-lock")
PY = "/Users/wangjian/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
NAME = "三任务-文件对照表.md"
KEY = "项目配置-memory/" + NAME

sys.path.insert(0, str(home / ".junqi-sync"))
real = json.loads((home / ".junqi-sync/config.json").read_text(encoding="utf-8"))
MEM = next(r for r in real["roots"] if "memory" in r["name"])

import junqi_sync as js  # noqa: E402

c = js.WeiyunClient(real["token"])
rmap = c.list_dir(MEM["remote_dir_key"], MEM["remote_parent_key"])
rp = rmap.get(NAME)
assert rp, "云端没有 %s" % NAME
print("云端 %s: size=%s id=%s" % (NAME, rp["file_size"], rp["file_id"][:12]))


def setup(readonly):
    shutil.rmtree(TEST, ignore_errors=True)
    (TEST / "base").mkdir(parents=True)
    (TEST / "logs").mkdir()
    cfg = {
        "local_base": str(TEST / "base"),
        "token": real["token"],
        "poll_interval": 15, "debounce": 3,
        "delete_policy": "ignore",
        "exclude": ["*.bak*", "*.tmp", "*~", ".DS_Store", "*.conflict-*"],
        "roots": [{
            "name": MEM["name"],
            "remote_dir_key": MEM["remote_dir_key"],
            "remote_parent_key": MEM["remote_parent_key"],
            "globs": ["*.md"],
        }],
    }
    if readonly:
        cfg["readonly_globs"] = [NAME]
    (TEST / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    # 本地文件：size/mtime 与基线**故意不符** ⇒ l_changed = True
    f = TEST / "base" / NAME
    f.write_bytes(b"x" * 1234)
    state = {
        "files": {KEY: {
            "l_mtime": 1.0, "l_size": 1,          # 故意旧 ⇒ l_changed=True
            "r_file_id": rp["file_id"], "r_size": rp["file_size"],
            "r_mtime": rp["file_mtime"], "synced_at": 1790400000}},
        "last_run": 1790400000, "last_host": "isolated-test",
    }
    (TEST / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def run_dry():
    env = dict(os.environ, JUNQI_SYNC_HOME=str(TEST), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([PY, str(home / ".junqi-sync/junqi_sync.py"), "dry"],
                       capture_output=True, text=True, env=env, timeout=120)
    return (p.stdout or "") + (p.stderr or "")


# ⚠️ J 收口改了日志文案（旧「只读文件本地有改动」→ 新「只读文件 [sk] … ⇒ 不传」）
#    取公共前缀「只读文件」⇒ 新旧文案都能命中，避免把「文案变」误报成「行为回归」。
MARK = "只读文件"

print("\n" + "=" * 62)
print("用例 A：config 配了 readonly_globs ⇒ 期望出现「%s」" % MARK)
print("=" * 62)
setup(True)
outA = run_dry()
print(outA.rstrip()[:900])
hitA = MARK in outA

print("\n" + "=" * 62)
print("用例 B（对照）：config 未配 ⇒ 期望【不】出现该提示（走正常上传）")
print("=" * 62)
setup(False)
outB = run_dry()
print(outB.rstrip()[:900])
hitB = MARK in outB

print("\n" + "=" * 62)
print("判定")
print("=" * 62)
print("  用例 A 命中只读拦截: %s  期望 True   %s" % (hitA, "✅" if hitA else "❌"))
print("  用例 B 命中只读拦截: %s  期望 False  %s" % (hitB, "✅" if not hitB else "❌"))
ok = hitA and not hitB
print("\n  ⇒ %s" % ("✅ G 补丁有效且无副作用（有分辨力）" if ok else "❌ 不符合预期"))
shutil.rmtree(TEST, ignore_errors=True)
print("  隔离环境已清理")
