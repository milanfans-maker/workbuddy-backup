#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""junqi_sync.py 就地升级补丁（Mac / Windows 通用）。

把 `os.kill(pid,0)` 探活升级为跨平台安全版 `_pid_alive()`，并收紧 `_check_pid()`。
用法：python3 ~/.junqi-sync/patch_pidfix.py
幂等：已打过补丁会直接跳过。改前自动备份 .bak_pre_pidfix_<日期>。
"""
import re
import shutil
import sys
import time
from pathlib import Path

TARGET = Path.home() / ".junqi-sync" / "junqi_sync.py"

NEW_FUNCS = '''def _pid_alive(pid):
    """跨平台判断 pid 是否存活。

    ⚠️ Windows 上 `os.kill(pid, 0)` 会抛 `OSError [WinError 87] 参数错误`
    （即使进程活得好好的），曾导致 status 永远误报「未运行」并**误删 .sync.pid**，
    进而可能重复启动第二个守护进程。故 Windows 走原生 API。
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not h:
                return False
            try:
                code = ctypes.c_ulong()
                if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                    return False
                return code.value == STILL_ACTIVE
            finally:
                k.CloseHandle(h)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # 存在但无权限 → 视为存活
    except Exception:
        return False


def _check_pid():
    if not PID_FILE.exists():
        return None
    try:
        raw = PID_FILE.read_text().strip()
    except OSError:
        return None                     # 读不到不代表进程死了 → 不动文件
    if not raw.isdigit():
        PID_FILE.unlink(missing_ok=True)  # 内容非法（写了一半）→ 清理
        return None
    pid = int(raw)
    if _pid_alive(pid):
        return pid
    PID_FILE.unlink(missing_ok=True)
    return None
'''


def main():
    if not TARGET.exists():
        print(f"❌ 未找到 {TARGET}")
        return 1
    src = TARGET.read_text(encoding="utf-8", newline="")

    if "def _pid_alive" in src:
        print("✅ 已是修复版，无需处理")
        return 0
    if "def _check_pid" not in src:
        print("❌ 未找到 _check_pid，版本不匹配，请勿用本补丁")
        return 1
    if "os.kill(pid, 0)" not in src:
        print("❌ 未找到已知的 os.kill 探活模式，请人工检查")
        return 1

    backup = TARGET.with_name(
        f"junqi_sync.py.bak_pre_pidfix_{time.strftime('%Y%m%d')}")
    shutil.copy2(TARGET, backup)
    print(f"已备份 → {backup.name}")

    pat = re.compile(r"def _check_pid\(\):\n(?:.*?\n)*?(?=\ndef |\nclass |\Z)")
    new_src, n = pat.subn(NEW_FUNCS + "\n", src, count=1)
    if n != 1:
        print(f"❌ 替换失败（命中 {n} 次），原文件未改动")
        shutil.copy2(backup, TARGET)
        return 1

    TARGET.write_text(new_src, encoding="utf-8", newline="\n")

    try:
        import ast
        ast.parse(TARGET.read_text(encoding="utf-8", newline=""))
    except Exception as e:
        print(f"❌ 语法校验失败，已回滚：{e}")
        shutil.copy2(backup, TARGET)
        return 1

    chk = TARGET.read_text(encoding="utf-8", newline="")
    assert "def _pid_alive" in chk and "OpenProcess" in chk
    print("✅ 打补丁成功，语法校验通过")
    print("   验证：python3 ~/.junqi-sync/junqi_sync.py status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
