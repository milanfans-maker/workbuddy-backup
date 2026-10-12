#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F 补丁（racefix）：堵住「待基线化」被对端覆盖后静默采纳的洞。

═══════════════════════════════════════════════════════════════════
背景（2026-09-26 实测事故，涉及文件 MEMORY.md）
═══════════════════════════════════════════════════════════════════
C 补丁（idfix）为避免"自抖"，让上传后的基线留 `r_file_id=None`（待基线化），
下一轮由 `_refresh_baseline()` 用 list 的真实值校准：

    elif b.get("r_file_id") is None:
        r_changed = False          # 本机刚传上去的，待基线化
    ...
    if b.get("r_file_id") is None:
        _refresh_baseline(files_state, sk, lp, rp)   # 无条件采纳远端

⚠️ 该逻辑**默认「下一轮 list 到的远端就是我刚传的那一份」**。
但在两端同时改同一文件时，这个前提会破：

  22:40:46  Mac 上传 7763 B  → 基线 l_size=7763, r_file_id=None（待基线化）
  22:40:52  对端覆盖云端为 7228 B
  下一轮    r_changed=False（待基线化）、l_changed=False
            → 走 _refresh_baseline(rp) → 采纳远端 7228 的 file_id
            → 基线变成 l_size=7763 / r_size=7228（自相矛盾）
            → 此后两侧恒判「未变」→ **永远 skip，永不修复**

即「永久失配」，且**全程无任何日志**（静默失败）。

═══════════════════════════════════════════════════════════════════
修法
═══════════════════════════════════════════════════════════════════
在 `_refresh_baseline()` 之前加一道校验：
若「待基线化」且 `rp["file_size"] != lstamp["size"]`，说明上传后云端已被改动
⇒ 不再静默采纳，改走**冲突分支**（留本地副本 + 按 mtime 判定谁赢），
使其**可见**（有 WARN 日志与 conflict 副本）。

注：本补丁**不能**消除两端争抢本身（微云无 CAS，需靠协议避免），
但能消除「静默永久失配」这个最坏结果 —— 让问题暴露出来。

幂等：已注入则跳过。
"""
import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"
STAMP = time.strftime("%Y%m%d")
MARKER = "RACE-HARDENED"

OLD = '''            if not l_changed and not r_changed:
                # 基线待补（首次运行或刚同步过）
                if b is None or b.get("l_mtime") is None \\
                        or b.get("r_file_id") is None:
                    _refresh_baseline(files_state, sk, lp, rp)
                stats["skip"] += 1
                continue
'''

NEW = '''            if not l_changed and not r_changed:
                # 基线待补（首次运行或刚同步过）
                need_fix = (b is None or b.get("l_mtime") is None
                            or b.get("r_file_id") is None)
                # ⚠️ F 补丁：竞态防护。若处于「本机刚上传、待基线化」，
                # 远端此刻应仍是我传的那一份。若大小不符 ⇒ 上传后云端已被对端
                # 覆盖 ⇒ 静默采纳会记下「l=自己 / r=别人」的矛盾基线 ⇒
                # 两侧恒判未变 ⇒ 永久失配且不可自愈、无日志。
                # 故改走冲突分支，使其可见（WARN + 本地副本）。
                if need_fix and b is not None and b.get("r_file_id") is None \\
                        and rp is not None and lstamp is not None \\
                        and rp["file_size"] != lstamp["size"]:
                    log("⚠ 待基线化时远端已被改动 [%s] 本地 %d / 远端 %d"
                        " ⇒ 按冲突处理" % (key, lstamp["size"], rp["file_size"]),
                        "WARN")
                    stats["conflict"] += 1
                    if not dry:
                        conflict_copy(lp)
                    if rp["file_mtime"] >= lstamp["mtime"] * 1000:
                        _do_download(client, cfg, files_state, sk, key, rp,
                                     rkey, base, stats, dry)
                    else:
                        _do_upload(client, cfg, files_state, sk, key, lp,
                                   rkey, stats, dry, existing=rp)
                    continue
                if need_fix:
                    _refresh_baseline(files_state, sk, lp, rp)
                stats["skip"] += 1
                continue
'''


def main():
    if not TARGET.exists():
        print("ERROR: 找不到 %s" % TARGET)
        return 1
    src = TARGET.read_text(encoding="utf-8", newline="")
    if MARKER in src:
        print("已打过 F 补丁（%s 存在），跳过。" % MARKER)
        return 0

    n = src.count(OLD)
    print("锚点命中 %d 次" % n)
    if n != 1:
        print("ERROR: 锚点必须恰好命中 1 次（实际 %d），中止以免误改" % n)
        return 1

    bak = TARGET.with_name(TARGET.name + ".bak_pre_racefix_" + STAMP)
    if not bak.exists():
        shutil.copy2(TARGET, bak)
        print("已备份 → %s" % bak.name)

    out = src.replace(OLD, NEW, 1)
    out += "\n\n# --- %s (F patch %s) ---\n" % (MARKER, STAMP)

    try:
        ast.parse(out)
    except SyntaxError as e:
        print("ERROR: 补丁后语法错误 %s，放弃写入" % e)
        return 1

    tmp = TARGET.with_suffix(".py.tmp")
    tmp.write_text(out, encoding="utf-8", newline="\n")
    tmp.replace(TARGET)
    print("✅ F 补丁完成：%d → %d B" % (len(src.encode()), len(out.encode())))
    print("   语法校验通过；备份 %s" % bak.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
