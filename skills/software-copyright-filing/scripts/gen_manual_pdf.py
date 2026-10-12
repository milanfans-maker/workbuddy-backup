#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《四国军棋复盘分析器 V1.0》软件说明书（计算机软件著作权登记用）。
输出：软著申请材料/03_软件说明书.pdf
"""
import os, math, tempfile
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Image, Table, TableStyle, PageBreak, KeepTogether,
                                CondPageBreak, NextPageTemplate)

ROOT = '/Volumes/me/ai学习/四国军棋/qq军棋复盘分析'
OUTDIR = os.path.join(ROOT, '软著申请材料')
SHOTS = os.path.join(OUTDIR, 'screenshots')
OUT = os.path.join(OUTDIR, '03_软件说明书.pdf')

SOFT = '四国军棋复盘分析器'
VER = 'V1.0'
HEADER = SOFT + ' ' + VER
OWNER = '王坚'

CN = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
CNB = '/System/Library/Fonts/STHeiti Medium.ttc'
pdfmetrics.registerFont(TTFont('CN', CN))
pdfmetrics.registerFont(TTFont('CNB', CNB, subfontIndex=0))
registerFontFamily('CN', normal='CN', bold='CNB', italic='CN', boldItalic='CNB')

INK = colors.HexColor('#1a1a1a')
DIM = colors.HexColor('#666666')
ACC = colors.HexColor('#8a5a00')

PW, PH = A4
LM = RM = 22 * mm
TM = 20 * mm
BM = 18 * mm
BODY_W = PW - LM - RM

S_TITLE = ParagraphStyle('t', fontName='CNB', fontSize=20, leading=30, alignment=TA_CENTER, textColor=INK)
S_SUB = ParagraphStyle('s', fontName='CN', fontSize=13, leading=22, alignment=TA_CENTER, textColor=DIM)
S_H1 = ParagraphStyle('h1', fontName='CNB', fontSize=15, leading=24, spaceBefore=16, spaceAfter=9,
                      textColor=INK, keepWithNext=1)
S_H2 = ParagraphStyle('h2', fontName='CNB', fontSize=12.5, leading=21, spaceBefore=11, spaceAfter=6,
                      textColor=ACC, keepWithNext=1)
S_H3 = ParagraphStyle('h3', fontName='CNB', fontSize=11, leading=19, spaceBefore=8, spaceAfter=4, textColor=INK)
S_P = ParagraphStyle('p', fontName='CN', fontSize=10.5, leading=18.5, alignment=TA_JUSTIFY,
                     firstLineIndent=21, textColor=INK, spaceAfter=4)
S_PN = ParagraphStyle('pn', parent=S_P, firstLineIndent=0)
S_LI = ParagraphStyle('li', parent=S_P, firstLineIndent=0, leftIndent=15, bulletIndent=3, spaceAfter=3)
S_CAP = ParagraphStyle('cap', fontName='CN', fontSize=9, leading=15, alignment=TA_CENTER, textColor=DIM,
                       spaceBefore=4, spaceAfter=10)
S_TC = ParagraphStyle('tc', fontName='CN', fontSize=9.5, leading=15, textColor=INK)
S_TCB = ParagraphStyle('tcb', fontName='CNB', fontSize=9.5, leading=15, textColor=INK)
S_TCC = ParagraphStyle('tcc', fontName='CNB', fontSize=9.5, leading=15, alignment=TA_CENTER, textColor=INK)
S_COVK = ParagraphStyle('ck', fontName='CNB', fontSize=11, leading=24, textColor=INK)
S_COVV = ParagraphStyle('cv', fontName='CN', fontSize=11, leading=24, textColor=INK)


def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


FLOW = []
PAGES = {'n': 0}


def h1(t):
    FLOW.append(Paragraph(esc(t), S_H1))


def h2(t):
    FLOW.append(Paragraph(esc(t), S_H2))


def h3(t):
    FLOW.append(Paragraph(esc(t), S_H3))


def p(t):
    FLOW.append(Paragraph(t, S_P))


def pn(t):
    FLOW.append(Paragraph(t, S_PN))


def li(t):
    FLOW.append(Paragraph(t, S_LI, bulletText='●'))


def num(i, t):
    FLOW.append(Paragraph(t, S_LI, bulletText='%d.' % i))


def sp(h=6):
    FLOW.append(Spacer(1, h))


_IMGCACHE = {}


def _prep(path, maxw=1500):
    """截图为 2~3 倍像素密度，缩到 1500px 宽并转 JPEG，控体积、肉眼无损。"""
    if path in _IMGCACHE:
        return _IMGCACHE[path]
    from PIL import Image as PILImage
    im = PILImage.open(path)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = PILImage.new('RGB', im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert('RGB')
    if im.width > maxw:
        im = im.resize((maxw, max(1, round(im.height * maxw / im.width))), PILImage.LANCZOS)
    out = os.path.join(tempfile.gettempdir(),
                       'manj_' + os.path.basename(path).rsplit('.', 1)[0] + '.jpg')
    im.save(out, 'JPEG', quality=90, optimize=True, progressive=True)
    _IMGCACHE[path] = (out, im.size)
    return _IMGCACHE[path]


def figure(name, caption, maxh=560):
    path = os.path.join(SHOTS, name)
    if not os.path.exists(path):
        pn('<font color="#c0392b">［缺图：%s］</font>' % esc(name))
        return
    src, (iw, ih) = _prep(path)
    maxh = min(maxh, 430)
    w = BODY_W
    h = ih * w / iw
    if h > maxh:
        h = maxh
        w = iw * h / ih
    img = Image(src, width=w, height=h)
    img.hAlign = 'CENTER'
    FLOW.append(KeepTogether([img, Paragraph(esc(caption), S_CAP)]))


def table(rows, widths, header=True):
    data = []
    for ri, row in enumerate(rows):
        line = []
        for ci, cell in enumerate(row):
            if ri == 0 and header:
                line.append(Paragraph(esc(cell), S_TCC))
            elif ci == 0 and header:
                line.append(Paragraph(esc(cell), S_TCB))
            else:
                line.append(Paragraph(esc(cell), S_TC))
        data.append(line)
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('TOPPADDING', (0, 0), (-1, -1), 4),
          ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
          ('LEFTPADDING', (0, 0), (-1, -1), 5),
          ('RIGHTPADDING', (0, 0), (-1, -1), 5)]
    if header:
        st += [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0ece0')),
               ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#faf8f3'))]
    else:
        st += [('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#faf8f3'))]
    t.setStyle(TableStyle(st))
    FLOW.append(t)
    FLOW.append(Spacer(1, 8))


# ============================ 封面 ============================
FLOW.append(Spacer(1, 78))
FLOW.append(Paragraph(esc(SOFT), S_TITLE))
FLOW.append(Spacer(1, 10))
FLOW.append(Paragraph('软 件 说 明 书', S_SUB))
FLOW.append(Spacer(1, 14))
FLOW.append(Paragraph('（版本号：%s）' % VER, S_SUB))
FLOW.append(Spacer(1, 62))

cov = [
    ['软件全称', SOFT],
    ['软件简称', '军棋复盘分析器'],
    ['版本号', VER],
    ['著作权人', OWNER],
    ['开发完成日期', '2026 年 9 月 1 日'],
    ['首次发表日期', '2026 年 9 月 2 日'],
    ['首次发表地点', '中国'],
    ['发表载体', '百度贴吧·四国军棋吧'],
    ['开发方式', '独立开发'],
    ['权利取得方式', '原始取得'],
    ['文档类型', '软件说明书（用户操作手册）'],
]
ct = Table([[Paragraph(esc(a), S_COVK), Paragraph(esc(b), S_COVV)] for a, b in cov],
           colWidths=[38 * mm, 74 * mm])
ct.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('LINEBELOW', (0, 0), (-1, -2), 0.4, colors.HexColor('#e0dccf'))]))
ct.hAlign = 'CENTER'
FLOW.append(ct)
FLOW.append(Spacer(1, 56))
FLOW.append(Paragraph('二〇二六年九月', S_SUB))
FLOW.append(NextPageTemplate('body'))
FLOW.append(PageBreak())

# ============================ 目录 ============================
h1('目　录')
toc = [
    ('第一章  软件概述', '1.1 软件名称与版本　1.2 软件简介　1.3 主要功能　1.4 软件特点'),
    ('第二章  运行环境', '2.1 硬件环境　2.2 软件环境　2.3 网络环境　2.4 开发环境与技术选型'),
    ('第三章  部署与启动', '3.1 部署方式　3.2 启动软件　3.3 导入棋谱的三种方式'),
    ('第四章  界面说明', '4.1 总体布局　4.2 顶部栏　4.3 导入区　4.4 对局信息区　4.5 玩家信息区\n'
                      '4.6 棋盘区　4.7 回放控制条　4.8 行棋记录区　4.9 得失统计区　4.10 形势评估区　4.11 图例说明'),
    ('第五章  功能操作说明', '5.1 棋谱导入与解析　5.2 回放控制　5.3 视角切换　5.4 盖牌模式　5.5 棋子标记\n'
                        '5.6 全屏复盘窗口　5.7 残局研究　5.8 主题切换　5.9 音效开关　5.10 移动端自适应'),
    ('第六章  技术实现说明', '6.1 总体架构　6.2 棋谱解析　6.3 行棋结果判定与棋子身份推演　6.4 方位与颜色映射\n'
                        '6.5 得失结算与综合评估　6.6 胜负判定　6.7 棋盘绘制　6.8 兼容性与性能'),
    ('第七章  版本信息与声明', '7.1 版本履历　7.2 版权声明　7.3 使用约定'),
]
for a, b in toc:
    FLOW.append(Paragraph('<b>%s</b>' % esc(a), S_PN))
    FLOW.append(Paragraph(esc(b), ParagraphStyle('toc', parent=S_PN, fontSize=9.5, leading=16,
                                                 textColor=DIM, leftIndent=14, spaceAfter=8)))
FLOW.append(PageBreak())

# ============================ 第一章 ============================
h1('第一章　软件概述')

h2('1.1　软件名称与版本')
pn('软件全称：四国军棋复盘分析器；版本号：V1.0。本软件为面向四国军棋爱好者的玩家版本，'
   '即承载本节所述全部功能、对外发布的版本；本说明书所述内容与登记的软件版本完全对应。')
pn('软件在页面显示标题中沿用社区习惯称法，其中前缀所指为软件所解析的对局格式来源，'
   '软件正式名称以本节为准。')

h2('1.2　软件简介')
p('四国军棋复盘分析器是一款面向四国军棋爱好者的<b>棋谱复盘与对局分析软件</b>。'
  '软件为纯前端单文件 Web 应用，<b>完全运行于用户本地浏览器</b>，无需注册、无需安装、无需上传棋谱，'
  '棋谱数据全程留存在用户本机，不产生任何外发请求。')
p('使用者只需把四国军棋对局结束后导出的复盘文件（或任何符合「玩家 / 布局 / 行棋」三段式格式的棋谱文本）'
  '拖拽或粘贴到页面中，软件即可自动完成棋盘还原、逐步回放、行棋得失结算、胜负手遴选、'
  '关键事件归类、子力净值曲线绘制与综合评级，用于复盘战局、诊断失着、学习高手行棋思路，'
  '也适用于录制解说时快速生成棋谱分析。')

h2('1.3　主要功能')
num(1, '<b>复盘文件直读</b>——可直接导入四国军棋对局保存的二进制复盘文件（.jgs），'
       '软件自动解析四家布局与全部行棋，转换为「复盘 v1.0」文本后再分析，无需手工整理；'
       '同时支持粘贴/拖拽符合三段式格式的复盘文本。')
num(2, '<b>17×17 棋盘还原与逐步回放</b>——四家初始布局自动落子，玩家颜色按复盘文件方位动态确定，'
       '严格按四国军棋逆时针顺序行棋（上家→左家→下家→右家），支持步进、跳转与三档变速播放，'
       '并实时显示每一步的行棋结果。')
num(3, '<b>行棋得失统计</b>——自动结算吃子、同尽、炸杀、中炸、挖雷、扛旗、触雷等事件，'
       '按内置子力价值体系（司令 100 / 军长 80 / 师长 60……）统计各方得分、损失与净值。')
num(4, '<b>胜负手 TOP3 与关键事件归类</b>——按单步子力净值变动自动筛选全场胜负手，'
       '并对扛旗、斩将、中炸、挖雷、触雷、同尽、失着等关键事件分类汇总，点击即可定位回放。')
num(5, '<b>战役明细与子力净值曲线</b>——逐家展示被歼棋子明细与四家净值走势，'
       '直观呈现战局节奏与子力交换过程。')
num(6, '<b>S / A / B / C / D 综合评级</b>——依据子力净值与关键得失，为每位玩家给出复盘评级，'
       '快速定位本局发挥优劣。')
num(7, '<b>残局研究</b>——不依赖棋谱，可直接在空棋盘上自由摆放四方棋子，手动推演残局走法，'
       '软件按四国军棋规则实时判定可落点与行棋合法性。')

h2('1.4　软件特点')
li('<b>零依赖、零安装</b>：软件主体为单个 HTML 文件，内联全部样式、脚本、图形与音效资源，'
   '不引用任何外部框架或网络资源，双击即可运行，可完整离线使用。')
li('<b>数据不出本机</b>：全部解析与计算均在浏览器本地完成，棋谱不上传、不联网、不留存。')
li('<b>跨平台</b>：凡具备现代浏览器的操作系统均可运行，桌面端与移动端自适应。')
li('<b>多视角</b>：支持绝对方位与己方视角两套观察方式，并可在全屏窗口中放大复盘。')
FLOW.append(PageBreak())

# ============================ 第二章 ============================
h1('第二章　运行环境')

h2('2.1　硬件环境')
table([
    ['项目', '最低配置', '推荐配置'],
    ['处理器', 'x86_64 / ARM64 架构，1.0 GHz 及以上', '2.0 GHz 及以上多核处理器'],
    ['内存', '2 GB', '4 GB 及以上'],
    ['可用存储空间', '10 MB（软件本体不足 1 MB）', '50 MB 及以上'],
    ['显示分辨率', '1366 × 768', '1920 × 1080 及以上'],
    ['输入设备', '鼠标或触摸屏', '鼠标 + 键盘'],
], [30 * mm, 62 * mm, 58 * mm])

h2('2.2　软件环境')
table([
    ['项目', '要求'],
    ['操作系统', 'Windows 7 / 8 / 10 / 11；macOS 10.13 及以上；Linux 各发行版；'
                'Android 7.0 及以上；iOS 12 及以上'],
    ['浏览器', 'Google Chrome 90+、Microsoft Edge 90+、Mozilla Firefox 88+、Safari 14+ 及其他同内核浏览器'],
    ['运行支撑', '无需安装任何插件、运行时或服务端组件；不需要数据库；不需要 Web 服务器（亦可托管于静态服务器）'],
    ['驻留软件', '无。软件不向系统写入注册表项、配置文件或缓存目录'],
], [30 * mm, 120 * mm])

h2('2.3　网络环境')
p('软件为纯本地应用，<b>运行全过程不需要网络连接</b>。仅当通过在线地址访问软件页面时，'
  '需要一次网络加载；若将软件文件保存至本机并通过本地路径打开，则可完全离线使用。')
p('软件运行期间不发起任何外部请求，不采集、不上传任何用户数据与棋谱内容。')

h2('2.4　开发环境与技术选型')
table([
    ['项目', '内容'],
    ['开发语言', 'HTML5 + CSS3 + JavaScript（ECMAScript 2015+ 语法，兼容至 ES5）'],
    ['开发工具', '文本编辑器 / 浏览器开发者工具'],
    ['第三方库', '无。软件不依赖任何第三方 UI 框架、图表库或工具库，全部功能原生实现'],
    ['字体与图形', '棋盘与棋子图形由 CSS 与内联可缩放矢量图形原生绘制；音效由内联音频数据内嵌'],
    ['代码规模', '主程序源文件 5,163 行，约 49 万字节；软件全部发行文件合计不足 1 MB'],
    ['开发方式', '独立开发，原始取得全部著作权'],
], [30 * mm, 120 * mm])
FLOW.append(PageBreak())

# ============================ 第三章 ============================
h1('第三章　部署与启动')

h2('3.1　部署方式')
p('软件为单文件应用，部署方式灵活，以下三种任选其一：')
num(1, '<b>本机直接打开</b>：将软件文件保存到本机任意目录，双击文件即可由默认浏览器打开使用；')
num(2, '<b>静态服务器托管</b>：将文件上传至任意静态网站空间即成在线服务，无需服务端程序与数据库；')
num(3, '<b>局域网共享</b>：置于局域网共享目录，供同一网络内多台设备分别打开使用。')
p('由于软件不含服务端组件，部署不涉及环境配置、依赖安装与数据初始化，'
  '亦无并发、运维与安全加固方面的额外要求。')

h2('3.2　启动软件')
p('软件打开后进入首页，页面自上而下由顶部标题栏、软件简介、导入区与功能入口构成，'
  '如图 3-1 所示。首次使用可点击「载入示例复盘」直接体验完整分析流程。')
figure('man_01_landing.png', '图 3-1　软件首页与导入区（含「载入示例复盘」「残局研究」等功能入口）', 430)

h2('3.3　导入棋谱的三种方式')
table([
    ['方式', '操作方法', '适用场景'],
    ['拖拽导入', '将复盘文件从文件管理器拖拽至虚线导入区后松手', '最快捷，支持 .jgs 与 .txt'],
    ['点击选择', '点击导入区，在系统文件对话框中选定文件', '触摸屏设备、文件较多时'],
    ['粘贴文本', '点击「粘贴文本」展开文本框，直接粘贴复盘文本内容', '仅有文本内容、无文件时'],
], [24 * mm, 78 * mm, 48 * mm])
p('导入区支持的文件类型包括：四国军棋二进制复盘文件（.jgs）、复盘文本（.txt / .log）、'
  '以及 QQGame 录像快照（.jqs）与布局文件（.jql）——后两类软件会给出相应的格式提示。')
FLOW.append(PageBreak())

# ============================ 第四章 ============================
h1('第四章　界面说明')

h2('4.1　总体布局')
p('载入棋谱后，主工作区采用「左侧信息栏 + 中部棋盘 + 右侧记录栏」的三栏布局：'
  '左栏为棋子价值表与评级标准，中栏为棋盘回放与控制条，右栏为行棋记录，'
  '下方依次排列行棋得失统计、战役明细、子力净值曲线与形势评估等分析卡片。'
  '整体布局如图 4-1 所示。')
figure('man_02_workspace.png', '图 4-1　主工作区总体布局', 470)

h2('4.2　顶部栏')
p('顶部栏左侧为软件标识与名称，右侧为主题切换按钮组（浅色主题 / 深色主题），'
  '可在米金浅色与黑金深色两套配色间即时切换。')

h2('4.3　导入区')
p('导入区由虚线拖拽框、文件选择按钮与功能按钮行组成。按钮行提供'
  '「载入示例复盘」「粘贴文本」「开始分析」「下载复盘文本」「残局研究」「清空」六项操作；'
  '其中「下载复盘文本」在完成 .jgs 文件解析后出现，用于导出转换所得的复盘文本。')

h2('4.4　对局信息区')
p('分析完成后显示对局基本信息，以网格形式列出来源、结果、总步数、耗时等元数据，'
  '并提供「返回导入」按钮以便重新导入棋谱。')

h2('4.5　玩家信息区')
p('以四张卡片分别展示四方玩家的名称与所在方位，下方为各方用时（步数）占比条，'
  '直观反映行棋节奏与思考时间分布。')

h2('4.6　棋盘区')
p('棋盘区是软件的核心显示区域，按 17×17 网格精确还原四国军棋棋盘，包括行棋点、行营、大本营、'
  '铁路（含弧形铁路）与公路。四方初始布局按复盘文件自动落子，棋子以所属玩家颜色区分，'
  '行棋过程中实时绘制起点标识（红框 + 箭头）、行经格箭头与终点标识（黄框）。')
figure('man_03_board.png', '图 4-2　棋盘初始布局：四方棋子就位，铁路与行营按规格绘制', 400)
figure('man_04_board_mid.png', '图 4-3　行棋过程：起点红框、行经格箭头与终点黄框逐帧呈现', 400)

h2('4.7　回放控制条')
p('控制条依次为「回到初始布局」「上一步」「播放 / 暂停」「下一步」「跳到终局」「音效开关」六个按钮，'
  '其后为当前步号显示、可拖拽的进度条与 1× / 2× / 4× 三档速度按钮，如图 4-4 所示。')
figure('man_05_replaybar.png', '图 4-4　回放控制条', 300)

h2('4.8　行棋记录区')
p('行棋记录区按时间顺序列出全场每一步的行棋，标注序号、玩家颜色与起止坐标；'
  '发生吃子、炸杀、扛旗等事件时同步标注得分子力与分值。顶部提供'
  '「全部 / 仅关键事件 / 仅失着」三个筛选标签，点击任一条目即可把棋盘定位到该步。')
figure('man_06_moves.png', '图 4-5　行棋记录区：逐步记录与关键事件标注', 430)

h2('4.9　得失统计区')
p('统计区汇总各方的吃子、损失与净值，并给出全场胜负手 TOP3。'
  '每一手胜负手标注步号、当事双方、子力交换与净值变动，可直接点击定位。')
figure('man_07_stat.png', '图 4-6　行棋得失统计：得分、损失、净值与胜负手 TOP3', 430)

h2('4.10　形势评估区')
p('评估区按「子力净值、胜负手、关键事件、失着控制、残局表现」等维度给出各玩家的分项得分，'
  '并换算为 S / A / B / C / D 综合评级，用于横向比较四方发挥。')
figure('man_08_eval.png', '图 4-7　形势评估区：分项得分与综合评级', 430)

h2('4.11　图例说明')
p('棋盘下方为图例，说明颜色与方位对应关系、行营与终点的图形标记、行棋顺序方向'
  '以及棋子颜色规则，便于初次使用者快速理解棋盘上的各类符号。')
figure('man_09_legend.png', '图 4-8　棋盘图例说明', 300)
FLOW.append(PageBreak())

# ============================ 第五章 ============================
h1('第五章　功能操作说明')

h2('5.1　棋谱导入与解析')
pn('操作步骤：')
num(1, '在首页导入区拖拽复盘文件，或点击导入区在文件对话框中选择文件；也可点击「粘贴文本」直接粘贴棋谱文本。')
num(2, '点击「开始分析」。软件解析文件、还原棋盘并完成全部结算，进度以浮层提示显示。')
num(3, '解析完成后自动进入主工作区；若导入的是 .jgs 二进制复盘文件，'
       '可点击「下载复盘文本」将转换后的复盘文本导出保存。')
p('软件对输入内容做格式校验：若缺少「玩家 / 布局 / 行棋」任一段落、'
  '或棋谱格式非法，会给出明确提示而不进入分析，避免产生错误结果。')

h2('5.2　回放控制')
table([
    ['操作', '方法', '说明'],
    ['单步前进 / 后退', '点击「▶」/「◀」，或按键盘方向键', '每次移动一步，棋盘与记录同步更新'],
    ['连续播放', '点击「▶ 播放」，再点变为「⏸ 暂停」', '按当前速度自动逐步播放'],
    ['跳转首尾', '点击「⏮」回到初始布局、「⏭」跳到终局', '快速定位两端局势'],
    ['任意定位', '拖拽进度条至目标位置', '拖动过程中实时刷新棋盘'],
    ['变速', '点击 1× / 2× / 4×', '调整自动播放速度'],
], [30 * mm, 62 * mm, 58 * mm])

h2('5.3　视角切换')
p('棋盘下方「视角」下拉框提供两种观察方式：')
li('<b>绝对方位（文件原始）</b>——完全按复盘文件记录的方位呈现棋盘，不作任何旋转。')
li('<b>己方视角（己方在下家）</b>——将指定玩家整体旋转至下方方位，其余玩家方位随之旋转，'
   '四家相对方位关系保持不变，便于从自身视角复盘。')
p('视角切换仅改变呈现方向，不改变任何数据与判定结果。')

h2('5.4　盖牌模式')
p('点击棋盘上的棋子可切换该方棋子的显示状态：盖牌状态下棋子以牌背面显示，'
  '用于在复盘讲解时暂时隐藏某一方的兵力信息。'
  '该操作只影响显示，不改变软件内部的布局与结算结果。')

h2('5.5　棋子标记')
p('复盘回放过程中，可在盖牌棋子上加注级别标记，用于记录自己的推测与判断：')
num(1, '在需要标记的盖牌棋子上<b>点击鼠标右键</b>，棋盘中央浮出半透明的标记面板；')
num(2, '在面板中<b>左键点击</b>对应的棋子级别（司令、军长、师长……工兵、军旗）'
       '或辅助记号，面板随即消失，标记显示在该棋子上；')
num(3, '需要修改或取消标记时，在该棋子上<b>再次点击右键</b>，选择其他级别，或点击「清空标记」。')
p('标记与棋子身份绑定：棋子发生移动后，标记随棋子同步移动；切换视角、明暗切换、'
  '以及发生撞子（吃子、同尽、触雷）等行为时，标记均不会被自动改动——'
  '标记只能由使用者通过右键主动修改或清除。')
figure('man_10_markpanel.png', '图 5-1　棋子标记：右键浮出标记面板，左键选择级别', 450)

h2('5.6　全屏复盘窗口')
p('点击棋盘标题栏右侧的「全屏窗口」按钮，可在独立窗口中打开复盘界面，'
  '棋盘按窗口尺寸等比例放大，便于投屏讲解或大屏复盘；'
  '全屏窗口与主窗口数据双向同步，任一侧的操作都会反映到另一侧。')
figure('man_13_popup.png', '图 5-2　全屏复盘窗口', 430)

h2('5.7　残局研究')
p('残局研究模块用于脱离棋谱、自由摆子推演残局，入口位于首页导入区与棋盘标题栏。'
  '进入后棋盘四角停放四家棋子托盘，可把任意棋子拖放至棋盘的合法落点，'
  '随后按四国军棋规则轮流行棋。软件实时判定可落点与走法合法性，'
  '并支持撤销与清空。')
figure('man_12_study.png', '图 5-3　残局研究：四方棋子托盘与残局推演棋盘', 450)

h2('5.8　主题切换')
p('顶部栏右侧提供浅色（米金）与深色（黑金）两套主题，点击月亮 / 太阳图标即可即时切换，'
  '选择会被记忆，下次打开保持上次主题。深色主题适合夜间复盘与大屏演示。')
figure('man_11_dark.png', '图 5-4　深色主题下的复盘界面', 450)

h2('5.9　音效开关')
p('回放过程中，行棋、吃子、炸子、司令阵亡、扛旗等事件可播放对应音效；'
  '音效数据内嵌于软件内，无需联网加载。点击控制条上的 🔊 按钮可随时开关。')

h2('5.10　移动端自适应')
p('软件内置响应式布局，在手机浏览器中打开时自动适配窄屏：'
  '棋盘按可用宽度等比缩放，各功能卡片改为单列纵向排列，'
  '标记面板与按钮尺寸针对触摸操作适当放大，操作按钮高度满足手指点击要求，'
  '且页面不产生横向滚动。')
figure('man_14_mobile_board.png', '图 5-5　手机端棋盘：按屏宽自适应缩放，各功能区单列纵向排列', 560)
FLOW.append(PageBreak())

# ============================ 第六章 ============================
h1('第六章　技术实现说明')

h2('6.1　总体架构')
p('软件采用单文件前端架构，全部结构（HTML）、样式（CSS）、逻辑（JavaScript）、'
  '图形资源与音效资源内联于同一文件，无外部依赖。运行时由浏览器内核直接解析执行，'
  '整体分为四个层次：')
table([
    ['层次', '职责'],
    ['界面层', '页面结构、响应式样式、主题变量、棋盘与棋子的矢量绘制、交互动效'],
    ['交互层', '文件导入、回放控制、视角切换、盖牌与标记、残局研究等用户操作的事件处理'],
    ['业务层', '棋谱解析、行棋规则判定、棋子身份推演、得失结算、胜负手遴选、评级计算'],
    ['数据层', '内存中的对局模型（玩家、布局、行棋序列、逐步快照），不涉及持久化与服务端'],
], [26 * mm, 124 * mm])

h2('6.2　棋谱解析')
p('软件支持两类棋谱来源：')
li('<b>二进制复盘文件（.jgs）</b>：按四国军棋复盘文件的二进制结构逐字段读取，'
   '解析出对局信息、四方玩家、初始布局与全部行棋记录，再转换为文本形式供业务层使用。')
li('<b>复盘文本</b>：按「玩家 / 布局 / 行棋」三段式结构解析。'
   '布局行格式为「颜色 行,列:棋子」（空格分隔），行棋行格式为「序号. 颜色 起行,起列-止行,止列」。')
p('解析过程包含格式校验与容错：段落缺失、坐标越界、颜色标识异常等情况均会被识别并提示，'
  '避免向业务层传递脏数据。')

h2('6.3　行棋结果判定与棋子身份推演')
p('每步行棋的结果判定由统一的走子裁决函数完成，依据棋盘格属性与双方棋子兵种给出结果类型，'
  '包括：合法行进、吃子、同尽、炸杀、中炸、触雷、挖雷、扛旗、反弹等。')
p('为支持盖牌与标记功能，软件另行维护一套<b>棋子身份模型</b>：以「初始行,初始列 | 颜色」为身份键，'
  '从初始布局出发对行棋序列做正向推演。推演规则与走子裁决同源，因此：')
li('落点归攻方时，攻方身份随之迁移到落点；')
li('被反吃或触雷（落点仍归守方）时，守方身份原地不动、攻方身份消失；')
li('双方同时阵亡时，两个身份一并消失；')
li('行棋非法或反弹时，双方身份均不变化。')
p('由于身份以绝对坐标记录并在推演结束后统一换算至当前视角，'
  '因此切换视角、明暗切换、撞子等操作都不会造成标记错位或丢失。')

h2('6.4　方位与颜色映射')
p('四国军棋四方颜色与方位（上、下、左、右）必须严格一一对应。软件在解析阶段'
  '统计各方行棋与布局的坐标分布，在全部双射组合中择优确定方位映射，'
  '保证「一种颜色对应一个方位」，避免出现两家共用同一方位而导致的布局覆盖、'
  '某一方棋子丢失等异常。方位确定后，棋盘、记录、统计、评估各模块共享同一映射结果。')

h2('6.5　得失结算与综合评估')
p('<b>子力价值体系</b>贯穿全部结算，取值如下表：')
table([
    ['棋子', '司令', '军长', '师长', '旅长', '团长', '营长', '连长', '排长', '工兵', '炸弹', '地雷', '军旗'],
    ['价值', '100', '80', '60', '45', '35', '25', '18', '12', '8', '35', '15', '0'],
], [18 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm, 12 * mm])
p('<b>结算口径</b>：吃子、同尽、炸杀、中炸、挖雷、触雷、扛旗等事件按发生方分别计入得分与损失，'
  '净值为该方得分与损失之差。')
p('<b>胜负手遴选</b>：按单步子力净值变动幅度从大到小排序，取全场前三位作为胜负手；'
  '同一手只作一次排序，不因涉及维度多而重复计入，保证排序结果与净值变动严格一致。')
p('<b>综合评估</b>：从子力净值、胜负手、关键事件、失着控制等维度给出分项得分，'
  '加权换算为总分并映射为 S / A / B / C / D 五级评级。')
table([
    ['评级', '判定区间与含义'],
    ['S', '净值得分 ≥ 100，或扛旗 / 斩将表现极佳，几乎没有失着'],
    ['A', '净值得分 40 ~ 99，攻防有序，偶有小失'],
    ['B', '净值 -40 ~ 39，发挥平稳，得失相当'],
    ['C', '净值 -99 ~ -41，子力交换吃亏或关键失误较多'],
    ['D', '净值 ≤ -100，或多次重大失着 / 被扛旗方'],
], [18 * mm, 132 * mm])

h2('6.6　胜负判定')
p('软件以终局棋子的<b>最终存活情况</b>判定胜负：某一方棋子全部被歼（含军旗被扛）即为战败方，'
  '其余三方按子力净值与关键得失排序确定名次。')
p('判定不以军旗是否被扛作为唯一依据——军旗被扛后若该方仍有棋子存活，'
  '需结合最终存活状态综合判定，避免把「扛旗后反打」的对局误判为终局。')

h2('6.7　棋盘绘制')
p('棋盘完全由 CSS 与内联可缩放矢量图形原生绘制，几何参数全部以棋盘格尺寸为基准换算，'
  '因此棋盘在任意缩放比例下（桌面、全屏窗口、手机）均保持等比例、不错位、不发虚。'
  '绘制内容包括：行棋点（含中间兵站与大本营的不同样式）、行营与行营环、'
  '铁路线（含带枕木细节与弧形铁路线）、公路网，以及棋子、标记与行棋路径指示。')
p('行棋路径指示严格沿实际路线绘制：直线铁路沿铁路线绘制，弧形铁路段沿弧线绘制，'
  '中间格与箭头按真实行经格依次绘制，不使用坐标插值近似，'
  '保证显示路径与规则判定结果一致。')

h2('6.8　兼容性与性能')
li('<b>浏览器兼容</b>：基于标准 HTML5 / CSS3 / ECMAScript 能力实现，'
   '在主流浏览器（Chrome、Edge、Firefox、Safari 及其移动版）中均可正常运行。')
li('<b>大棋谱处理</b>：解析与推演使用线性复杂度的单遍扫描，'
   '百步级棋谱的分析在普通设备上可瞬间完成；回放时仅重绘变化部分，保证拖动进度条时的流畅度。')
li('<b>健壮性</b>：解析、判定、结算各环节均具备边界校验与异常兜底，'
   '非法输入不会导致页面崩溃；软件已就 191 份真实棋谱、35,069 个行棋场景完成回归验证。')
li('<b>安全与隐私</b>：不采集数据、不发起外部请求，不写入系统任何配置，'
   '棋谱内容全程保留在用户本机内存中。')
FLOW.append(PageBreak())

# ============================ 第七章 ============================
h1('第七章　版本信息与声明')

h2('7.1　版本履历')
table([
    ['版本号', '日期', '说明'],
    ['V1.0', '2026 年 9 月', '首个完整版本：实现棋谱导入与解析、棋盘还原与逐步回放、行棋得失统计、'
                            '胜负手与关键事件、战役明细与净值曲线、综合评级、残局研究、'
                            '棋子标记、全屏复盘窗口、主题切换、音效与移动端自适应等全部功能'],
], [22 * mm, 30 * mm, 98 * mm])
pn('本软件 V1.0 于 2026 年 9 月 1 日完成开发并固定于载体，于 2026 年 9 月 2 日'
   '在百度贴吧·四国军棋吧首次向公众发表，发表方式为发布软件介绍并向公众提供在线使用入口，'
   '其后由著作权人持续维护并在其自有站点发布。')

h2('7.2　版权声明')
pn('软件全称：四国军棋复盘分析器')
pn('版本号：%s' % VER)
pn('著作权人：%s' % OWNER)
pn('著作权人网名：暴暴寒（7z）、小寒（7z）、热心市民小寒、☆→小寒')
pn('著作权取得方式：原始取得')
pn('开发方式：独立开发')
pn('本软件由著作权人独立开发完成，软件开发、发布、维护过程中所使用的上述网名'
   '及所使用的发布站点均为著作权人本人所有，不存在合作开发者或第三方权利人。')
pn('本说明书及所述软件的著作权归著作权人所有。未经著作权人许可，任何单位或个人不得以任何方式复制、'
   '传播、修改、汇编或用于商业用途。')
sp(6)
pn('本软件为免费供四国军棋爱好者使用的复盘分析工具，软件中涉及的四国军棋规则、'
   '棋子名称与棋盘样式均属该棋类的通行内容；软件名称仅用于标识本软件，'
   '不涉及也不主张任何第三方的商标权利。')

h2('7.3　使用约定')
li('软件按现状提供，用于棋谱复盘与学习研究；因使用本软件产生的任何对局判断，'
   '仅供参考，不构成对局判定的最终依据。')
li('使用者应确保其导入的棋谱内容来源合法，不得利用本软件从事任何违法或侵犯他人权益的活动。')
li('软件运行于使用者本地浏览器，使用者应自行负责其设备与数据的安全。')
sp(14)
FLOW.append(Paragraph('—— 文档结束 ——', S_CAP))


# ============================ 页眉页脚 ============================
def on_page(c, doc):
    PAGES['n'] += 1
    n = PAGES['n']
    c.saveState()
    c.setFont('CN', 8.5)
    c.setFillColor(DIM)
    c.drawString(LM, PH - TM + 12, HEADER)
    c.drawRightString(PW - RM, PH - TM + 12, '软件说明书')
    c.setStrokeColor(colors.HexColor('#c9c4b4'))
    c.setLineWidth(0.6)
    c.line(LM, PH - TM + 6, PW - RM, PH - TM + 6)
    c.setFont('CN', 9)
    c.drawCentredString(PW / 2, BM - 10, '第 %d 页' % n)
    c.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4,
                      leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
                      title='%s %s 软件说明书' % (SOFT, VER), author=OWNER,
                      subject='计算机软件著作权登记 · 软件说明书')
frame = Frame(LM, BM, BODY_W, PH - TM - BM, id='main',
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)


def cover_page(c, d):
    pass


tpl_cover = PageTemplate(id='cover', frames=[frame], onPage=cover_page)
tpl_body = PageTemplate(id='body', frames=[frame], onPage=on_page)
doc.addPageTemplates([tpl_cover, tpl_body])

doc.build(FLOW)
sz = os.path.getsize(OUT)
import pymupdf
d = pymupdf.open(OUT)
print('✅ %s  共 %d 页  %.2f MB' % (os.path.basename(OUT), d.page_count, sz / 1048576.0))
