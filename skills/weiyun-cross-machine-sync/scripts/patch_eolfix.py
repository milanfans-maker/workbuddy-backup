#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D 补丁：行尾（EOL）跨平台加固。

背景
----
Python 文本模式默认 `newline=None`：
  读: 把 \r\n 与 \r 统一成 \n
  写: 把 \n 按 os.linesep 转换（macOS/Linux → \n，Windows → \r\n）

⇒ 同一个脚本在 Windows 上把 LF 变 CRLF，在 macOS 上把 CRLF 变 LF。
   两端都会「静默篡改」对方传来的文件，造成字节级分叉。

本补丁把所有文本模式 open/read_text/write_text 显式声明行尾策略：
  - 读取：`newline=""`   → 保留原始行尾，不做统一
  - 写入：`newline="\n"` → 固定 LF，跨平台一致

对纯 LF 文件完全等价（零行为变化），对 CRLF 文件是修正。

幂等：已注入则跳过。
"""
import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"
STAMP = time.strftime("%Y%m%d")

MARKER = "EOL-HARDENED"

# (旧片段, 新片段, 说明)
RULES = [
    ('with open(LOG_FILE, "a", encoding="utf-8") as f:',
     'with open(LOG_FILE, "a", encoding="utf-8", newline="\\n") as f:',
     "log 追加写 → 固定 LF"),

    ('with open(path, encoding="utf-8") as f:\n            return json.load(f)',
     'with open(path, encoding="utf-8", newline="") as f:\n            return json.load(f)',
     "load_json → 保留原始行尾"),

    ('with open(tmp, "w", encoding="utf-8") as f:\n        json.dump(',
     'with open(tmp, "w", encoding="utf-8", newline="\\n") as f:\n        json.dump(',
     "save_json → 固定 LF"),

    ('AUTH_CODE_FILE.write_text(code, encoding="utf-8")',
     'AUTH_CODE_FILE.write_text(code, encoding="utf-8", newline="")',
     "授权码写 → 保留"),

    ('code = AUTH_CODE_FILE.read_text(encoding="utf-8").strip()',
     'code = AUTH_CODE_FILE.read_text(encoding="utf-8", newline="").strip()',
     "授权码读 → 保留"),

    ('PID_FILE.write_text(str(os.getpid()))',
     'PID_FILE.write_text(str(os.getpid()), newline="")',
     "pid 写 → 保留"),
]


def main():
    if not TARGET.exists():
        print("ERROR: 找不到 %s" % TARGET)
        return 1

    src = TARGET.read_text(encoding="utf-8", newline="")

    if MARKER in src:
        print("已打过 D 补丁（%s 存在），跳过。" % MARKER)
        return 0

    # 逐条替换，先验证锚点唯一
    plan = []
    for old, new, desc in RULES:
        n = src.count(old)
        if n == 0:
            print("  [跳过] 锚点未找到: %s" % desc)
            continue
        if n > 1:
            print("  [警告] 锚点出现 %d 次，仅替换首个: %s" % (n, desc))
        plan.append((old, new, desc, n))

    if not plan:
        print("ERROR: 没有任何锚点命中，中止（避免误改）")
        return 1

    # 备份
    bak = TARGET.with_name(TARGET.name + ".bak_pre_eolfix_" + STAMP)
    if not bak.exists():
        shutil.copy2(TARGET, bak)
        print("已备份 → %s" % bak.name)

    out = src
    for old, new, desc, n in plan:
        out = out.replace(old, new, 1 if n > 1 else -1)
        print("  ✅ %s" % desc)

    # 打标记（放在 docstring 之后的第一行注释位；用行尾注释块更安全）
    out += "\n\n# --- EOL-HARDENED (D patch %s) ---\n" % STAMP

    # 语法校验（纯内存，不写 __pycache__）
    try:
        ast.parse(out)
    except SyntaxError as e:
        print("ERROR: 补丁后语法错误 %s，已放弃写入" % e)
        return 1

    # 原子写入
    tmp = TARGET.with_suffix(".py.tmp")
    tmp.write_text(out, encoding="utf-8", newline="\n")
    tmp.replace(TARGET)

    print()
    print("✅ D 补丁完成：%d → %d B" % (len(src.encode()), len(out.encode())))
    print("   语法校验通过；备份 %s" % bak.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
