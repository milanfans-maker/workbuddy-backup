#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mac 侧一键验证：探针到没到 + 补丁打没打 + 守护几个进程。

用法（Mac 单行）：
    python3 ~/.junqi-sync/verify_mac.py
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
SYNC = HOME / ".junqi-sync"
OK, NO, WA = "\033[32m✅\033[0m", "\033[31m❌\033[0m", "\033[33m⚠️\033[0m"

print("=" * 62)
print(" Mac 侧同步验收")
print("=" * 62)

# ---- 1. 探针是否到达 ----
print("\n[1] 跨机探针（Windows 侧 21:34 放入）")
cfg_p = SYNC / "config.json"
probe = None
if cfg_p.exists():
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    base = Path(cfg.get("local_base", "")).expanduser()
    probe = base / ".workbuddy" / "memory" / "_sync_probe_mac.md"
if probe and probe.exists():
    print(f"  {OK} 已收到 → {probe}")
    for line in probe.read_text(encoding="utf-8").splitlines():
        if "生成主机" in line or "生成时间" in line:
            print(f"      {line.strip()}")
    print("      ⇒ **双向同步已实证连通**")
else:
    print(f"  {NO} 未收到 {probe}")
    print("      Mac 上跑一轮：python3 ~/.junqi-sync/junqi_sync.py once")

# ---- 2. 补丁打没打 ----
print("\n[2] 探活 bug 补丁")
sys.path.insert(0, str(SYNC))
patched = False
try:
    import junqi_sync as js
    patched = hasattr(js, "_pid_alive")
    print(f"  {'有修复' if patched else '无修复'} (_pid_alive: {patched})",
          OK if patched else NO)
except Exception as e:
    print(f"  {NO} 导入 junqi_sync 失败: {e}")
if not patched:
    print(f"  {WA} 需打补丁：见 .workbuddy/memory/_Mac升级补丁_pidfix.md")
    print("      复制补丁 → python3 ~/.junqi-sync/patch_pidfix.py")

# ---- 3. 守护进程数 ----
print("\n[3] 守护进程（必须恰好 1 个）")
lines = []


def _count_via_pgrep():
    try:
        out = subprocess.run(["pgrep", "-fl", "junqi_sync.py sync"],
                             capture_output=True, text=True, timeout=5).stdout
        return [l for l in out.splitlines() if l.strip()]
    except Exception:
        return None


def _count_via_wmic():
    """Windows 回退：没有 pgrep，用 WMIC 查 python 进程命令行。"""
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get",
             "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=15).stdout
        hits = []
        for l in out.splitlines():
            if "junqi_sync.py" in l and "sync" in l:
                hits.append(l.strip())
        return hits
    except Exception:
        return None


if os.name != "nt":
    r = _count_via_pgrep()
    if r is None:
        print(f"  {WA} pgrep 不可用")
    lines = r or []
else:
    r = _count_via_wmic()
    if r is None:
        print(f"  {WA} WMIC 不可用，跳过进程计数")
        r = []
    lines = r
    # 兜底：读 .sync.pid + 探活
    if not lines:
        pidf = SYNC / ".sync.pid"
        if pidf.exists():
            try:
                from junqi_sync import _pid_alive
                pid = int(pidf.read_text().strip())
                if _pid_alive(pid):
                    lines = [f"{pid} junqi_sync.py sync (.sync.pid)"]
            except Exception:
                pass

if len(lines) == 1:
    print(f"  {OK} 恰好 1 个 → {lines[0].strip()[:100]}")
elif len(lines) == 0:
    print(f"  {NO} 没有守护在跑 —— 用 start-mac.command 或 launchctl 拉起")
else:
    print(f"  {NO} 有 {len(lines)} 个！孤儿守护，重复上传风险：")
    for l in lines:
        print(f"      {l.strip()[:100]}")
    print("      ⇒ 只留最早那个，其余 kill 掉")

# ---- 4. 本机 status ----
print("\n[4] 本机同步状态")
s = SYNC / "state.json"
if s.exists():
    st = json.loads(s.read_text(encoding="utf-8"))
    lr = st.get("last_run")
    print(f"  已跟踪文件 : {len(st.get('files', {}))}")
    print(f"  last_run   : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(lr)) if lr else '无'}")
    print(f"  last_host  : {st.get('last_host')}  ← 应为本机主机名")

print("\n" + "=" * 62)
allok = (probe and probe.exists()) and patched
print(" 结论：" + ("✅ 探针已通 + 补丁已打" if allok else "⚠️ 见上方红/黄项"))
print("=" * 62)
