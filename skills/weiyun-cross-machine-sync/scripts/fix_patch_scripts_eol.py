#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修订补丁脚本自身的行尾策略（自指风险修复）。

背景
----
`patch_pidfix.py` / `patch_metafix.py` / `patch_idfix.py` 里的
`read_text/write_text` **未声明行尾**：

    src = TARGET.read_text(encoding="utf-8")
    TARGET.write_text(out, encoding="utf-8")

Python 文本模式默认 `newline=None` ⇒ 写时按 `os.linesep` 转换。
在 **Windows** 上跑这三个补丁 ⇒ 整份 `junqi_sync.py` 被转成 CRLF
⇒ 重放结果 ≠ 38205 B，且目标文件被污染。

`patch_eolfix.py` 的读取端也缺 `newline=""`（写出端本来就有）。

⚠️ 这就是「修行尾的补丁自己踩行尾」的活例证。

修法
----
- 读取：`newline=""`  → 保留原始行尾
- 写入：`newline="\n"` → 固定 LF

**对输出无行为变化**（macOS 上 `os.linesep="\n"`，本来就写 LF）；
只修掉 Windows 上的错误。故各机**不必重跑补丁**（幂等会跳过），
但**重放时**必须用本修订版。

幂等：已带参数则跳过。
"""
import ast
import pathlib
import shutil
import sys
import time

D = pathlib.Path.home() / ".junqi-sync"
STAMP = time.strftime("%Y%m%d")

RULES = {
    "patch_pidfix.py": [
        ('    src = TARGET.read_text(encoding="utf-8")\n',
         '    src = TARGET.read_text(encoding="utf-8", newline="")\n'),
        ('        ast.parse(TARGET.read_text(encoding="utf-8"))',
         '        ast.parse(TARGET.read_text(encoding="utf-8", newline=""))'),
        ('    chk = TARGET.read_text(encoding="utf-8")',
         '    chk = TARGET.read_text(encoding="utf-8", newline="")'),
        ('    TARGET.write_text(new_src, encoding="utf-8")\n',
         '    TARGET.write_text(new_src, encoding="utf-8", newline="\\n")\n'),
    ],
    "patch_metafix.py": [
        ('    src = TARGET.read_text(encoding="utf-8")\n',
         '    src = TARGET.read_text(encoding="utf-8", newline="")\n'),
        ('    TARGET.write_text(out, encoding="utf-8")\n',
         '    TARGET.write_text(out, encoding="utf-8", newline="\\n")\n'),
    ],
    "patch_idfix.py": [
        ('    src = TARGET.read_text(encoding="utf-8")\n',
         '    src = TARGET.read_text(encoding="utf-8", newline="")\n'),
        ('    TARGET.write_text(out, encoding="utf-8")\n',
         '    TARGET.write_text(out, encoding="utf-8", newline="\\n")\n'),
    ],
    "patch_eolfix.py": [
        ('    src = TARGET.read_text(encoding="utf-8")\n',
         '    src = TARGET.read_text(encoding="utf-8", newline="")\n'),
    ],
}


def main():
    rc = 0
    for name, rules in RULES.items():
        p = D / name
        if not p.exists():
            print("❌ 找不到 %s" % p)
            rc = 1
            continue

        src = p.read_text(encoding="utf-8", newline="")
        todo = [(o, n) for o, n in rules if o in src]
        if not todo:
            print("ℹ️  %s 已全部带行尾参数，跳过。" % name)
            continue

        bak = p.with_name(p.name + ".bak_pre_selfeol_" + STAMP)
        if not bak.exists():
            shutil.copy2(p, bak)

        before = len(src.encode())
        out = src
        for o, n in todo:
            assert out.count(o) == 1, "%s 锚点 %d 次" % (name, out.count(o))
            out = out.replace(o, n, 1)

        try:
            ast.parse(out)
        except SyntaxError as e:
            print("❌ %s 语法错误 %s，跳过" % (name, e))
            rc = 1
            continue

        tmp = p.with_suffix(".py.tmp")
        tmp.write_text(out, encoding="utf-8", newline="\n")
        tmp.replace(p)
        print("✅ %-20s %d → %d B（改 %d 处）→ 备份 %s"
              % (name, before, len(out.encode()), len(todo), bak.name))

    print()
    print("⚠️ 各机无需重跑补丁（幂等跳过）；但**重放时必须用本修订版**。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
