#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""软著材料终检。

覆盖：页眉一致性 / 页码连续性 / 每页行数 / 名称版本三处统一 / 日期逻辑自洽 /
      无第三方姓名 / 说明书不出现网址与联系方式 / 占位符残留 / 公司字段已填实。
"""
import os, re, io
import pymupdf

OUT = '/Volumes/me/ai学习/四国军棋/qq军棋复盘分析/软著申请材料'
ROOT = os.path.dirname(OUT)
SOFT, VER = '四国军棋复盘分析器', 'V1.0'
FULL = SOFT + ' ' + VER
BAD_NAMES = ['姜朕熙', '老姜甄鉴', '规则赋能']
ok = True


def chk(label, cond, detail=''):
    global ok
    ok &= bool(cond)
    print('  %s %s%s' % ('✅' if cond else '❌', label, ('　' + detail) if detail else ''))


print('【1】源程序 PDF（取源：玩家版 index_task2.html）')
for f, exp_first, exp_last in [('01_源程序_前30页.pdf', 1, 30), ('02_源程序_后30页.pdf', 100, 129)]:
    d = pymupdf.open(os.path.join(OUT, f))
    chk('%s 页数 30' % f, d.page_count == 30, '实际 %d' % d.page_count)
    hdr_ok, pg_ok, txt_all = True, True, ''
    for i, pg in enumerate(d):
        t = pg.get_text()
        txt_all += t
        if FULL not in t:
            hdr_ok = False
        m = re.search(r'第 (\d+) 页', t)
        if not m or int(m.group(1)) != exp_first + i:
            pg_ok = False
    chk('  每页页眉含「%s」' % FULL, hdr_ok)
    chk('  页码 %d～%d 连续' % (exp_first, exp_last), pg_ok)
    body_min = 99
    for i, pg in enumerate(d):
        n = sum(1 for b in pg.get_text('dict')['blocks'] if b.get('type') == 0
                for ln in b['lines']
                if ln['bbox'][1] >= 50 and ''.join(s['text'] for s in ln['spans']).strip())
        if i < d.page_count - 1:
            body_min = min(body_min, n)
    chk('  每页正文 ≥50 行', body_min >= 50, '最少 %d 行' % body_min)
    hit = [w for w in BAD_NAMES if w in txt_all]
    chk('  源码中无第三方署名', not hit, ('命中 %s' % hit) if hit else '无「姜朕熙/老姜甄鉴/规则赋能」')
    d.close()

print('\n【2】软件说明书 PDF')
mp = os.path.join(OUT, '03_软件说明书.pdf')
d = pymupdf.open(mp)
chk('页数合理（≤60，可全本提交）', d.page_count <= 60, '%d 页' % d.page_count)
hdr_ok, pg_ok, n_pg = True, True, 0
for i, pg in enumerate(d):
    t = pg.get_text()
    if i == 0:
        continue
    if FULL not in t:
        hdr_ok = False
    m = re.search(r'第 (\d+) 页', t)
    n_pg += 1
    if not m or int(m.group(1)) != n_pg:
        pg_ok = False
chk('正文每页页眉含「%s」' % FULL, hdr_ok)
chk('页码自 1 起连续', pg_ok, '正文共 %d 页' % n_pg)
chk('封面不计页码', '第 1 页' not in d[0].get_text().split('二〇二六')[0][-40:])
imgs = sum(len(d[i].get_images()) for i in range(d.page_count))
chk('配图数量', imgs >= 12, '%d 张' % imgs)
txt_all = ''.join(d[i].get_text() for i in range(d.page_count))
for kw in ('运行环境', '界面说明', '功能操作说明', '技术实现说明', '残局研究', '棋子标记'):
    chk('  含章节/内容「%s」' % kw, kw in txt_all)
cover = d[0].get_text()
d.close()

print('\n【2b】说明书封面字段与日期逻辑')
for kw, lab in (('四国军棋复盘分析器', '软件全称'), ('V1.0', '版本号'), ('王坚', '著作权人'),
                ('2026 年 9 月 1 日', '开发完成日期'), ('2026 年 9 月 2 日', '首次发表日期'),
                ('中国', '首次发表地点'), ('独立开发', '开发方式'), ('原始取得', '权利取得方式')):
    chk('  封面含%s「%s」' % (lab, kw), kw in cover)
chk('  开发完成日期 ≤ 首次发表日期', '9 月 1 日' in cover and '9 月 2 日' in cover, '9-1 → 9-2')


def parse_cn_date(s):
    m = re.search(r'(\d{4}) 年 (\d{1,2}) 月 (\d{1,2}) 日', s)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


dev = parse_cn_date(cover[cover.find('开发完成日期'):cover.find('开发完成日期') + 40])
pub = parse_cn_date(cover[cover.find('首次发表日期'):cover.find('首次发表日期') + 40])
chk('  两个日期可解析且 dev < pub', bool(dev and pub) and dev < pub, '%s < %s' % (dev, pub))

print('\n【2c】说明书不得出现网址 / 联系方式（官方补正高频项）')
urls = re.findall(r'(?:https?://|www\.)\S+', txt_all)
mails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', txt_all)
phones = re.findall(r'(?<!\d)1[3-9]\d{9}(?!\d)', txt_all)
chk('  无网址', not urls, str(urls[:3]))
chk('  无邮箱', not mails, str(mails[:3]))
chk('  无手机号', not phones, str(phones[:3]))
hit = [w for w in BAD_NAMES if w in txt_all]
chk('  无第三方署名', not hit, ('命中 %s' % hit) if hit else '无「姜朕熙/老姜甄鉴/规则赋能」')
chk('  含网名一致性说明', '暴暴寒' in txt_all and '热心市民小寒' in txt_all)

print('\n【3】三份材料的名称与版本一致性')
chk('源程序页眉 = 说明书页眉 = %s' % FULL, True, '已在上两项核对')

print('\n【4】占位符残留')
for f in ('01_源程序_前30页.pdf', '02_源程序_后30页.pdf', '03_软件说明书.pdf'):
    d = pymupdf.open(os.path.join(OUT, f))
    t = ''.join(d[i].get_text() for i in range(d.page_count))
    bad = [x for x in ('XXXX', 'xxx', '待填', 'TODO', '【待', '＿＿') if x in t]
    chk('%s 无未替换占位符' % f, not bad, '命中 %s' % bad if bad else '')
    d.close()

print('\n【5】目录文件（md）')
s04 = io.open(os.path.join(OUT, '04_登记申请表_填写信息汇总.md'), encoding='utf-8').read()
s05 = io.open(os.path.join(OUT, '05_材料清单与办理指引.md'), encoding='utf-8').read()
chk('04_登记申请表_填写信息汇总.md（%d 字符）' % len(s04), len(s04) > 3000)
chk('05_材料清单与办理指引.md（%d 字符）' % len(s05), len(s05) > 2000)
for kw, lab in (('362528198202100012', '身份证号'), ('13979461314', '电话'), ('123392@qq.com', '邮箱'),
                ('江西省抚州市临川区广场东路学府中央小区', '联系地址'), ('344000', '邮编'),
                ('王坚', '著作权人'), ('2026 年 9 月 2 日', '首次发表日期'),
                ('tieba.baidu.com/p/10991083683', '发表证明链接'),
                ('玩家版', '登记版本范围说明')):
    chk('  04 含%s' % lab, kw in s04)
chk('  04/05 无「待填」「待你」敷衍标记', '待填' not in s04 + s05 and '待你' not in s04 + s05)
chk('  05 已更新源程序页数口径', '129 页' in s05 or '129页' in s05)

print('\n总体：%s' % ('✅ 全部通过' if ok else '❌ 存在问题'))
