#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《四国军棋复盘分析器 V1.0》软件著作权登记 · 源程序提交文档。

输出：01_源程序_前30页.pdf / 02_源程序_后30页.pdf
排版：A4 纵向、每页 60 个排版行位（实测可见行 55~60，满足「每页不少于 50 行」）、
      页眉含软件名称+版本号+页码、中英混排（ASCII 等宽 Courier）。
取源：**玩家版** = index_task2.html（≡ index_task3.html，无「竞技技术积分」块、不含第三方署名）。
用法：python junqi_srcdoc.py [--probe]
"""
import io, os, sys, math, functools, collections
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = '/Volumes/me/ai学习/四国军棋/qq军棋复盘分析'
OUTDIR = os.path.join(ROOT, '软著申请材料')
SRC = os.path.join(ROOT, os.environ.get('SRCFILE', 'index_task2.html'))   # 玩家版

SOFT_NAME = '四国军棋复盘分析器'
SOFT_VER = 'V1.0'
HEADER_TEXT = SOFT_NAME + ' ' + SOFT_VER

# ---------- 排版参数 ----------
PAGE_W, PAGE_H = 595.28, 841.89      # A4 纵向 (pt)
ML, MR = 45.0, 45.0
HEAD_LINE_Y = 52.0                   # 页眉横线距底高度
BOT_Y = 40.0
LPP = int(os.environ.get('SRCLPP', '60'))    # 每页排版行位（源码空行也占位）
FS = float(os.environ.get('SRCFS', '8.5'))
BODY_W = PAGE_W - ML - MR
LEAD = (PAGE_H - HEAD_LINE_Y - BOT_Y) / LPP

# ---------- 字体 ----------
CANDIDATES = [
    ('FCN', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf', None),
    ('FCN2', '/System/Library/Fonts/STHeiti Light.ttc', 0),
    ('FMN', '/System/Library/Fonts/Menlo.ttc', 0),
]
REGISTERED = {}
for _n, _p, _i in CANDIDATES:
    if not os.path.exists(_p):
        continue
    try:
        pdfmetrics.registerFont(TTFont(_n, _p, subfontIndex=_i) if _i is not None else TTFont(_n, _p))
        REGISTERED[_n] = set(pdfmetrics.getFont(_n).face.charToGlyph.keys())
    except Exception as e:
        print('  ⚠️ 字体 %s 加载失败：%s' % (os.path.basename(_p), str(e)[:80]))
assert 'FCN' in REGISTERED, '没有可用的中文字体'
ASCII_FONT = 'Courier'
CJK_FONT = 'FCN'
FALLBACK = [k for k in ('FCN', 'FCN2', 'FMN') if k in REGISTERED]
SKIP_CH = {'\ufe0f', '\ufe0e', '\u200b', '\u200d', '\u00ad'}   # 零宽/变体选择符，不绘制

_MISS_CACHE = {}


def font_for(ch):
    """返回该字符应使用的字体名；无字体覆盖时返回 None。"""
    cp = ord(ch)
    if cp < 128:
        return ASCII_FONT
    if ch in _MISS_CACHE:
        return _MISS_CACHE[ch]
    got = None
    for f in FALLBACK:
        if cp in REGISTERED[f]:
            got = f; break
    _MISS_CACHE[ch] = got
    return got


@functools.lru_cache(maxsize=1 << 18)
def cwidth(ch):
    if ch in SKIP_CH:
        return 0.0
    f = font_for(ch)
    if f is None:
        return pdfmetrics.stringWidth('□', CJK_FONT, FS)
    return pdfmetrics.stringWidth(ch, f, FS)


def segments(line):
    """把一行切成 [(字体名, 文本)]，缺失字符以 □ 呈现。"""
    out = []
    for ch in line:
        if ch in SKIP_CH:
            continue
        f = font_for(ch)
        t = ch
        if f is None:
            f, t = CJK_FONT, '□'
        if out and out[-1][0] == f:
            out[-1][1].append(t)
        else:
            out.append([f, [t]])
    return [(f, ''.join(s)) for f, s in out]


def wrap(line):
    """按宽度折行，返回显示行列表。"""
    if not line:
        return ['']
    out, cur, w = [], [], 0.0
    for ch in line:
        c = cwidth(ch)
        if cur and w + c > BODY_W:
            out.append(''.join(cur)); cur = [ch]; w = c
        else:
            cur.append(ch); w += c
    out.append(''.join(cur))
    return out


def build_display_lines(lines):
    disp = []
    for l in lines:
        disp.extend(wrap(l))
    return disp


def draw_page(c, chunk, pageno):
    c.setFont(CJK_FONT, 9)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(ML, PAGE_H - 34, HEADER_TEXT)
    c.drawRightString(PAGE_W - MR, PAGE_H - 34, '第 %d 页' % pageno)
    c.setLineWidth(0.7)
    c.line(ML, HEAD_LINE_Y, PAGE_W - MR, HEAD_LINE_Y)
    y = PAGE_H - HEAD_LINE_Y - LEAD + 3.4
    for ln in chunk:
        x = ML
        for f, t in segments(ln):
            c.setFont(f, FS)
            c.drawString(x, y, t)
            x += pdfmetrics.stringWidth(t, f, FS)
        y -= LEAD
    c.showPage()


def main():
    src = io.open(SRC, encoding='utf-8').read()
    lines = src.split('\n')
    print('源文件 %s：%d 行 / %d 字节' % (os.path.basename(SRC), len(lines), len(src.encode())))
    print('排版：A4 纵向 · 每页 %d 行 · 字号 %.1fpt · 正文宽 %.1fpt（ASCII 每行约 %d 字符）'
          % (LPP, FS, BODY_W, int(BODY_W / (0.6 * FS))))

    disp = build_display_lines(lines)
    raw = len(disp)
    while disp and not disp[-1].strip():      # 去掉文件尾部的纯空行，避免末页整页留白
        disp.pop()
    if raw != len(disp):
        print('  去掉尾部纯空行 %d 个显示行' % (raw - len(disp)))
    total_pages = math.ceil(len(disp) / LPP)
    print('显示行 %d → 共 %d 页' % (len(disp), total_pages))

    # 缺失字符（渲染为 □）统计
    miss = collections.Counter()
    for l in lines:
        for ch in l:
            if ch not in SKIP_CH and ord(ch) > 127 and font_for(ch) is None:
                miss[ch] += 1
    print('无字体覆盖、以 □ 呈现的字符：%d 种 / %d 次' % (len(miss), sum(miss.values())))
    if miss:
        print('   ' + ' '.join('%r×%d' % (ch, n) for ch, n in miss.most_common(12)))

    if '--probe' in sys.argv:
        return

    front = disp[:30 * LPP]
    back = disp[(total_pages - 30) * LPP:] if total_pages > 30 else []
    os.makedirs(OUTDIR, exist_ok=True)

    back_pages = math.ceil(len(back) / LPP)
    jobs = [('01_源程序_前30页.pdf', front, 1),
            ('02_源程序_后30页.pdf', back, total_pages - back_pages + 1)]
    for fname, chunk, start in jobs:
        path = os.path.join(OUTDIR, fname)
        c = canvas.Canvas(path, pagesize=(PAGE_W, PAGE_H))
        c.setTitle('%s %s 源程序' % (SOFT_NAME, SOFT_VER))
        c.setAuthor('王坚')
        c.setSubject('计算机软件著作权登记 · 源程序')
        for i in range(0, len(chunk), LPP):
            draw_page(c, chunk[i:i + LPP], start + i // LPP)
        c.save()
        print('  ✅ %-26s %3d 页（第 %d–%d 页） %.2f MB'
              % (fname, math.ceil(len(chunk) / LPP), start, start + math.ceil(len(chunk) / LPP) - 1,
                 os.path.getsize(path) / 1048576.0))


if __name__ == '__main__':
    main()
