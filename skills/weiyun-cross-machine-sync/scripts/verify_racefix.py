#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F 补丁（racefix）验证：双用例 + 对照组。

隔离方式：JUNQI_SYNC_HOME 指向 /tmp/jq-ftest，config 里 local_base 也指向隔离目录，
且只用 dry 模式（sync_once 在 dry 下 line 694-695 不落盘，_do_* 内部也直接 return）。
**不触碰真实项目文件、不上传、不下载。**

用例：
  A 待基线化 + 远端大小 ≠ 本地  ⇒ 期望：打 WARN 并计冲突（F 生效）
  B 待基线化 + 远端大小 = 本地  ⇒ 期望：无 WARN，走 _refresh_baseline（正常路径）
"""
import json
import os
import pathlib
import subprocess
import sys

TEST_HOME = pathlib.Path("/tmp/jq-ftest")
BASE = TEST_HOME / "base"
PY = "/Users/wangjian/.workbuddy/binaries/python/versions/3.13.12/bin/python3"

# 复用真实 token / 远端目录
sys.path.insert(0, str(pathlib.Path.home() / ".junqi-sync"))
real_cfg = json.loads((pathlib.Path.home() / ".junqi-sync/config.json").read_text(encoding="utf-8"))
MEM_ROOT = next(r for r in real_cfg["roots"] if "memory" in r["name"])
REMOTE_D = MEM_ROOT["remote_dir_key"]
REMOTE_P = MEM_ROOT["remote_parent_key"]

# ---- 隔离环境 ----
import shutil
shutil.rmtree(TEST_HOME, ignore_errors=True)
BASE.mkdir(parents=True)
(TEST_HOME / "logs").mkdir()

cfg = {
    "local_base": str(BASE),
    "token": real_cfg["token"],
    "poll_interval": 15, "debounce": 3,
    "delete_policy": "ignore",
    "exclude": ["*.bak*", "*.tmp", "*~", ".DS_Store", "*.conflict-*"],
    "roots": [{
        "name": "项目配置-memory",
        "remote_dir_key": REMOTE_D,
        "remote_parent_key": REMOTE_P,
        "globs": ["*"],          # 隔离目录下所有文件都当候选，方便构造
    }],
}
(TEST_HOME / "config.json").write_text(
    json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

# 取云端 MEMORY.md 的真实大小（用于构造用例）
sys.path.insert(0, str(pathlib.Path.home() / ".junqi-sync"))
import junqi_sync as js
c = js.WeiyunClient(real_cfg["token"])
rmap = c.list_dir(REMOTE_D, REMOTE_P)
CLOUD = rmap.get("MEMORY.md")
print("云端 MEMORY.md:", CLOUD["file_size"], "B" if CLOUD else "不存在")
assert CLOUD, "云端没有 MEMORY.md，无法构造用例"

LOCAL = BASE / "MEMORY.md"


def setup(local_size, r_size, r_file_id, r_mtime):
    """造本地文件 + 隔离基线。"""
    LOCAL.write_bytes(b"x" * local_size)
    st = js.local_stamp(LOCAL)
    state = {"files": {"项目配置-memory/MEMORY.md": {
        "l_mtime": st["mtime"], "l_size": st["size"],
        "r_file_id": r_file_id, "r_mtime": r_mtime, "r_size": r_size,
        "synced_at": 1790400000,
    }}, "last_run": 1790400000, "last_host": "isolated-test"}
    (TEST_HOME / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return st


def run_dry():
    env = dict(os.environ, JUNQI_SYNC_HOME=str(TEST_HOME), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([PY, str(pathlib.Path.home() / ".junqi-sync/junqi_sync.py"), "dry"],
                       capture_output=True, text=True, env=env, timeout=120)
    return (p.stdout or "") + (p.stderr or "")


print("\n" + "=" * 68)
print("用例 A：待基线化 + 远端大小 ≠ 本地  ⇒ 期望 WARN（F 生效）")
print("=" * 68)
st = setup(local_size=100, r_size=100, r_file_id=None, r_mtime=None)
out = run_dry()
print(out.rstrip())
hitA = "待基线化时远端已被改动" in out

print("\n" + "=" * 68)
print("用例 B（对照）：待基线化 + 远端大小 = 本地  ⇒ 期望无 WARN（正常基线化）")
print("=" * 68)
# 本地大小 = 云端大小，模拟「上传后云端确实是自己那一份」
st = setup(local_size=CLOUD["file_size"], r_size=CLOUD["file_size"],
           r_file_id=None, r_mtime=None)
out = run_dry()
print(out.rstrip())
hitB = "待基线化时远端已被改动" in out

print("\n" + "=" * 68)
print("判定")
print("=" * 68)
print(f"  用例 A 触发 F 告警: {hitA}  期望 True   {'✅' if hitA else '❌'}")
print(f"  用例 B 触发 F 告警: {hitB}  期望 False  {'✅' if not hitB else '❌'}")
ok = hitA and not hitB
print(f"\n  ⇒ {'✅ F 补丁有效且无副作用（有分辨力）' if ok else '❌ 不符合预期'}")

# 清理
shutil.rmtree(TEST_HOME, ignore_errors=True)
print("  隔离环境已清理")
