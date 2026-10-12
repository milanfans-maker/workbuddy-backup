#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日期归一化 sha256 —— 跨机/跨天比对补丁链时的**可信校验值**。

为什么不能直接比 sha256
=======================
每个补丁脚本往目标文件尾部追加一行标记：

    out += "\\n\\n# --- %s (G patch %s) ---\\n" % (MARKER, STAMP)   # STAMP = %Y%m%d

⇒ 文件名/字节数完全一致，但**标记里的日期随「跑的那天」变**。

    2026-09-26 打 D/F/G ⇒ `(D patch 20260926)`
    2026-09-27 重放     ⇒ `(D patch 20260927)`

所以「同一份原文 + 同一串补丁」在**跨天**重放后：

    字节数 ✅ 相同        标记计数 ✅ 相同        sha256 ❌ 必然不同

这不是分叉，是**时间戳进了哈希**。2026-09-26/27 跨零点时实测踩到：
重放件 41785 B 与真实件 41785 B 逐行 diff 只差**三行日期**。

用法
----
    python3 norm_sha.py                       # 算 junqi_sync.py
    python3 norm_sha.py path/to/junqi_sync.py # 算指定文件

归一化规则：只对**标记行**（`# --- ` 开头，**允许前置缩进**）里的 `20\\d{6}` 做替换，
其余内容一律不动 —— 既消除日期噪声，又不会掩盖真实差异。

⚠️ 为什么要允许缩进（2026-09-27 修正，原为 `^# --- `）
    补丁把标记行写进两处：**文件尾追加的**（顶格）+ **函数体内联的**（带缩进），
    两处都嵌了 `%Y%m%d`。只匹配顶格 ⇒ 内联那条的日期不被抹掉 ⇒
    跨天重放时归一化哈希**照样会变**，等于这套机制只对了一半。
    改为 `^\\s*# --- ` 后，缩进/顶格一律覆盖。
"""
import hashlib
import pathlib
import re
import sys

MARKER_LINE = re.compile(r"^\s*# --- .*$", re.M)
DATE_IN_MARKER = re.compile(r"20\d{6}")


def normalize(text):
    def _fix_line(m):
        return DATE_IN_MARKER.sub("YYYYMMDD", m.group(0))
    return MARKER_LINE.sub(_fix_line, text)


def norm_sha256(path):
    raw = pathlib.Path(path).read_text(encoding="utf-8", newline="")
    return hashlib.sha256(normalize(raw).encode("utf-8")).hexdigest()


def main():
    p = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
        pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"
    if not p.exists():
        print("ERROR: 找不到 %s" % p)
        return 1
    raw = p.read_text(encoding="utf-8", newline="")
    print("文件      : %s" % p)
    print("字节      : %d" % len(raw.encode()))
    print("sha256    : %s" % hashlib.sha256(raw.encode()).hexdigest())
    print("归一化    : %s   ← 跨机/跨天比对这个" % norm_sha256(p))
    marks = [l for l in raw.splitlines() if l.startswith("# --- ")]
    print("标记 %2d 行: %s" % (len(marks), " | ".join(
        m.replace("# --- ", "").replace(" ---", "") for m in marks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
