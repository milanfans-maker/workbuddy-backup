#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G 补丁（writerlock）：共享文件「只下不上」—— 把单一写者从**约定**变成**机制**。

背景（2026-09-26 23:33 第二次实测事故）
=====================================
共享文件约定「单一写者 = Mac」，但 **同步器不认这个约定**：
非写者机只要认为「本地变了」，就会上传并覆盖写者。

证据链
------
    23:33:04  Mac 上传 MEMORY.md 9811          ⇒ 云端变 9811
    （其间）  对端重传其本地旧版 9038            ⇒ 云端被改回 9038
    23:33:21  Mac list 到 9038 ⇒ F 补丁判冲突（**判定正确**）⇒ 下载覆盖本地

    ※ 已排除「微云 list 延迟」：探针实测上传后 **2.3s** list 即见新文件、id 稳定。
    ※ 23:37:22 恢复上传命中【秒传】= 内容已在服务器（全局 SHA1 去重），
      与「目录条目被改成 9038」并不矛盾。

⇒ F 补丁做到了「**可见**」（WARN + 冲突副本，数据没静默丢），但**阻止不了覆盖**。
  本补丁补上「**阻止**」。

修法
====
config 增加 `readonly_globs`（按文件名匹配，风格同 `globs` / `exclude`）：

    "readonly_globs": ["MEMORY.md", "三任务-文件对照表.md"]

命中的文件 ⇒ **参与比对与下载（远端变了照常取），但本地改了永不上传**。

⇒ 非写者机无论状态怎么失配、怎么重传，都**不可能**覆盖共享文件。

用法
----
**只在非写者机（Windows）的 config 里配**；写者机（Mac）不配，保持可写。
幂等：已注入则跳过。
"""
import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"
STAMP = time.strftime("%Y%m%d")
MARKER = "WRITER-LOCK"

OLD_FUNC = '''def _glob_basename(g):'''

NEW_FUNC = '''def is_readonly(name, cfg):
    """G 补丁：共享文件「只读」判定 —— 参与比对/下载，但本地改了**永不上传**。

    共享文件（MEMORY.md / 对照表）的「单一写者」只是文档约定，
    同步器不认 ⇒ 非写者机只要认为「本地变了」就会上传并覆盖写者
    （2026-09-26 23:33 实测发生过一次）。
    本机 config 里 `readonly_globs` 命中的文件，本地改动一律不上传。
    """
    for pat in cfg.get("readonly_globs", []):
        if fnmatch.fnmatch(name, _glob_basename(pat)):
            return True
    return False


def _glob_basename(g):'''

OLD_GUARD = '''            # ---- 判定
            if lp is None and rp is None:'''

NEW_GUARD = '''            # ⚠️ G 补丁：只读文件（共享文件）—— 本地改了也不上传，只跟随远端。
            if l_changed and lp is not None and is_readonly(key, cfg):
                log("只读文件本地有改动，按规约不上传 [%s]" % sk, "INFO")
                l_changed = False

            # ---- 判定
            if lp is None and rp is None:'''


def main():
    if not TARGET.exists():
        print("ERROR: 找不到 %s" % TARGET)
        return 1
    src = TARGET.read_text(encoding="utf-8", newline="")
    if MARKER in src:
        print("已打过 G 补丁（%s 存在），跳过。" % MARKER)
        return 0

    for name, frag in (("OLD_FUNC", OLD_FUNC), ("OLD_GUARD", OLD_GUARD)):
        n = src.count(frag)
        print("锚点 %s 命中 %d 次" % (name, n))
        if n != 1:
            print("ERROR: 锚点必须恰好 1 次，中止以免误改")
            return 1

    bak = TARGET.with_name(TARGET.name + ".bak_pre_writerlock_" + STAMP)
    if not bak.exists():
        shutil.copy2(TARGET, bak)
        print("已备份 → %s" % bak.name)

    out = src.replace(OLD_FUNC, NEW_FUNC, 1).replace(OLD_GUARD, NEW_GUARD, 1)
    out += "\n\n# --- %s (G patch %s) ---\n" % (MARKER, STAMP)

    try:
        ast.parse(out)
    except SyntaxError as e:
        print("ERROR: 补丁后语法错误 %s，放弃写入" % e)
        return 1

    tmp = TARGET.with_suffix(".py.tmp")
    tmp.write_text(out, encoding="utf-8", newline="\n")
    tmp.replace(TARGET)
    print("✅ G 补丁完成：%d → %d B" % (len(src.encode()), len(out.encode())))
    print("   语法校验通过；备份 %s" % bak.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
