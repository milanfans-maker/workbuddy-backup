#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源程序排版模拟 + 中文字体覆盖诊断。
只做统计，不产 PDF。用于给 junqi_srcdoc.py 选参数。
"""
import io, os, math, functools, collections, sys
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFontFile

ROOT = '/Volumes/me/ai学习/四国军棋/qq军棋复盘分析'
CN_PATH = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
ALT_PATH = '/System/Library/Fonts/STHeiti Light.ttc'
pdfmetrics.registerFont(TTFont('HiraGB', CN_PATH))
pdfmetrics.registerFont(TTFont('STHei', ALT_PATH, subfontIndex=0))

src = io.open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
L = src.split('\n')
print('源文件 index.html：%d 行 / %d 字节' % (len(L), len(src.encode())))

# ---------- 1. 非 ASCII 字符与字体覆盖 ----------
cnt = collections.Counter(ch for ch in src if ord(ch) > 127)
print('\n【字体覆盖】非 ASCII 不同字符 %d 个' % len(cnt))


def cover(fontname):
    face = pdfmetrics.getFont(fontname).face
    for attr in ('charToGlyph', 'charToGlyphMap', 'glyphs'):
        d = getattr(face, attr, None)
        if isinstance(d, dict) and d:
            return set(d.keys())
    return set()


for fn, label in (('HiraGB', 'Arial Unicode MS'), ('STHei', 'STHeiti Light')):
    cov = cover(fn)
    if not cov:
        print('  %s: 取不到字形表' % label); continue
    miss = [(ch, n) for ch, n in cnt.most_common() if ord(ch) not in cov]
    print('  %s: 字形 %d，不覆盖 %d 种 / %d 次' % (label, len(cov), len(miss), sum(n for _, n in miss)))
    for ch, n in miss[:20]:
        print('     U+%04X  %-3s  x%d' % (ord(ch), repr(ch)[1:-1], n))
    # 关键符号探测
    key = '⚠★✓□■●○◆※→←↑↓│─┌【】《》（）、，。：；！？、“”‘’…'
    absent = [ch for ch in key if ord(ch) not in cov]
    print('     常规符号缺失：%s' % (''.join(absent) if absent else '无'))

# ---------- 2. 排版模拟 ----------
@functools.lru_cache(maxsize=100000)
def cw(ch, fs):
    return 0.6 * fs if ord(ch) < 128 else pdfmetrics.stringWidth(ch, 'HiraGB', fs)


def wrap(line, maxw, fs):
    """逐字符按宽度折行，返回显示行列表"""
    if not line:
        return ['']
    out, cur, w = [], [], 0.0
    for ch in line:
        c = cw(ch, fs)
        if cur and w + c > maxw:
            out.append(''.join(cur)); cur = [ch]; w = c
        else:
            cur.append(ch); w += c
    out.append(''.join(cur))
    return out


PAGE_W, PAGE_H = 595.28, 841.89
HEAD_LINE_Y, BOT_Y = 52.0, 40.0
LPP = 50
BODY_W = PAGE_W - 45.0 - 45.0

print('\n【排版模拟】正文宽 %.1fpt，每页 %d 行' % (BODY_W, LPP))
for fs in (7.0, 7.5, 8.0, 8.5, 9.0):
    cpl = int(BODY_W / (0.6 * fs))          # 纯 ASCII 每行字符数
    disp, base_span = [], None
    for i, l in enumerate(L):
        w = wrap(l, BODY_W, fs)
        if base_span is None and len(disp) + len(w) > 1500:
            base_span = i                            # 前 30 页大约切在原始第几行
        disp.extend(w)
    total = len(disp)
    pages = math.ceil(total / LPP)
    # 前 30 页里 base64 那行占多少显示行
    b64_line = 1032                                  # index.html 的 logo base64
    off = sum(len(wrap(L[j], BODY_W, fs)) for j in range(b64_line - 1))
    b64_show = len(wrap(L[b64_line - 1], BODY_W, fs))
    used = max(0, 1500 - off)
    print('  字号 %-4s → 每行 %3d 字符 | 显示行 %6d | 共 %3d 页 | 前30页切在原始第 %d 行 | '
          'base64 行 %d 显示行，前30页里占 %d 行(%.1f%%)'
          % (fs, cpl, total, pages, base_span or 0, b64_show, min(used, b64_show),
             100.0 * min(used, b64_show) / 1500))
