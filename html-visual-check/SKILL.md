---
name: html-visual-check
slug: html-visual-check
version: 1.2.0
agent_created: true
displayName: 单文件 HTML 视觉自查（Chrome headless 截图）
description: 改完本地单文件 HTML 的 CSS / 布局 / 样式后，用本机 Chrome 的 headless 模式批量截图，多断点核对视觉效果，再交付给用户。当任务是「调整某个本地 HTML 的样式/布局/棋盘/UI」并需要在回复前先自查渲染效果时使用。零安装依赖，比装 agent-browser（约 500MB Chromium）快得多。
---

# 单文件 HTML 视觉自查（Chrome headless 截图）

## 何时用

- 用户要求"把 X 改成类似这张图的样子"、"调整样式/布局/配色"，目标是某个**本地单文件 HTML**
- 你需要**在交付前先亲眼确认渲染结果**，而不是靠读 CSS 猜
- 需要按断点核对响应式表现（窄屏单列 / 宽屏多列）

不需要时：纯 JS 逻辑改动（用 `node -e "new Function(...)"` 校验语法即可），或远程 URL 抓内容（用 WebFetch）。

## 为什么不用 agent-browser

`agent-browser` 首次使用要 `npm install -g` + `agent-browser install` 下载约 500MB Chromium。
只是为了截一张图时，直接用系统已装的 Chrome 更划算。**仅当需要点击/输入/登录等多步交互时**才考虑 agent-browser。

## 前置检查

```bash
ls -d "/Applications/Google Chrome.app" 2>/dev/null || echo "无 Chrome，需改用 agent-browser"
ls -d /Users/wangjian/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core 2>/dev/null \
  || echo "缺 puppeteer-core：cd /Users/wangjian/.workbuddy/binaries/node/workspace && npm install puppeteer-core --registry=https://registry.npmmirror.com"
```

## 一条命令搞定：`shoot_report.js`（通用实拍 + 结构自检）⭐首选

**绝大多数场景不需要下面那些手写命令** —— 直接用这个脚本。它把「结构自检 + 关键内容点检 + 逐节实拍 + JSON 摘要 + 失败退出码」打包成一条命令，可直接接进回归流程。

**位置**：`~/.workbuddy/skills/html-visual-check/scripts/shoot_report.js`
（本机约定：项目里用软链 `qq军棋复盘分析/.workbuddy/tests/shoot_report.js` 指向它，**单一源，别复制**）

```bash
NODE=/Users/wangjian/.workbuddy/binaries/node/versions/22.22.2-3/bin/node
S=~/.workbuddy/skills/html-visual-check/scripts/shoot_report.js

# 1) 先看结构，挑要截的节标题
$NODE "$S" 报告.html --list

# 2) 实拍 + 自检
$NODE "$S" 报告.html --prefix shot_depth --heading "h1,h2" \
  --need "关键词1,关键词2,关键数字" \
  --sections "第一节标题,第二节标题,结论" \
  --full --strict --json /tmp/check.json
```

**选项**

| 选项 | 说明 |
|------|------|
| `--prefix NAME` | 截图前缀（默认取文件名主干；`/` 会被清洗，控制目录请用 `--out`） |
| `--out DIR` | 截图输出目录（默认 HTML 同级） |
| `--need "a,b,c"` | **必须出现**的关键词，缺失即 ❌（数字建议用短子串，避免千分位/单位差异误报） |
| `--sections "x,y"` | 按节标题关键词逐节截图（子串匹配，文件名自动带序号+关键词） |
| `--heading "h1,h2"` | 节标题标签（默认自动探测 h1/h2/h3） |
| `--width N` / `--height N` / `--scale N` | 视口与像素比（默认 1100×1200×1；`--scale 2` 出高清图） |
| `--full` | 额外输出一张整页长图 |
| `--list` | 只列标题结构，方便挑 `--sections` |
| `--wait MS` | 加载后额外等待（默认 400） |
| `--json PATH` | 写机器可读摘要 |
| `--strict` | 有任一失败即 **exit 1** |
| `--quiet` | 只留判定行（进度噪声静音，**判定永远可见**） |

**退出码**：`0` 通过（或未开 `--strict`）· `1` 用法错误 / `--strict` 下有失败 · `2` 运行异常（缺 Chrome / 缺 puppeteer-core）。
⚠️ 未开 `--strict` 时即使打了红叉仍返回 0 —— 脚本会显式提示，**接回归流程必须加 `--strict`**。

**它查什么（6 项）**

| 检查 | 判据 | 能抓到的典型问题 |
|------|------|------------------|
| 关键内容缺失 | `innerText` 不含 `--need` 词 | 生成时漏段、数字写错、章节被吞 |
| 横向溢出 | `documentElement.scrollWidth > clientWidth` | `th{white-space:nowrap}`、固定像素宽、长 `pre` |
| Markdown `**` 残留 | 源里仍有 `**` | 生成脚本只对部分块做了 `**`→`<b>` |
| `<b>` 配平 | `<b[ >]` 数 vs `</b>` 数 | 生成时标签错配 |
| 断图 | `img` 未 `complete` / `naturalWidth==0` | 相对路径错、文件没生成 |
| JS 报错 | `pageerror` + `console.error` | 内联脚本写坏、资源 404 |

**已知局限（不是 bug，别误判）**

- `<b>` 配平读的是**解析后的** `innerHTML`，浏览器会自动闭合漏写的 `</b>` ⇒ 它只抓**解析器修不好**的真失衡。查漏写闭合标签请直接 grep 源文件。
- 横向溢出只看**整页**；单个元素的溢出若被祖先 `overflow:hidden` 裁掉则测不到。
- JS 报错不含被 `try/catch` 吞掉的异常。

**反向验证（重要方法论）**：新写/改动任何检查项后，**必须造一个故意坏掉的页面**确认它真的报错，否则就是"假绿"。本项目已多次踩过假绿坑（宽松口径 `illegal=0`、手机模式「溢出量恰好为 0」）。

```bash
# 反例模板：故意溢出 + `**` 残留 + 断图
cat > /tmp/selftest/bad.html <<'HTML'
<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div style="width:2400px">必须被判为横向溢出</div>
<p>**必须被判为 Markdown 残留**</p>
<img src="nope_xyz.png">
</body></html>
HTML
$NODE "$S" /tmp/selftest/bad.html --quiet --out /tmp/selftest   # 期望 4~5 项 ❌
```

## 核心命令（无 Node 环境时的兜底）

不装 puppeteer-core、只需要一张图时，直接用 Chrome 命令行：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1280,2600 \
  --screenshot=/tmp/check.png \
  "file:///绝对路径/页面.html"
```

要点：

- **中文路径 / 含空格路径必须整段加引号**，`file://` URL 同样要引号
- 用**绝对路径**构造 `file://` URL
- `--hide-scrollbars` 避免滚动条影响观感
- `--window-size=W,H` 同时决定**视口宽度（断点）**和**截图高度**；高度给足才能截到长页面
- 输出最后一行 `NNN bytes written to file` 即成功

## 多断点核对

一次任务里按目标断点各截一张，比只截一张信息量大得多：

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL="file:///Volumes/me/ai学习/四国军棋/四国军棋布局转换器.html"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=560,1500  --screenshot=/tmp/narrow.png "$URL"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1280,1000 --screenshot=/tmp/wide.png   "$URL"
```

选断点的方法：先 `grep -n "min-width\|max-width" 页面.html` 找出 CSS 媒体查询的断点值，再在断点两侧各取一个宽度。

## ⚠️ 两个必踩的坑（v1.1 新增，血泪）

### 坑 1：Google Chrome 在 macOS 有**最小窗口宽度**，小于某值的 `--window-size` 会被钳制

实测：`--window-size=375,900` / `420,900` 时，**PNG 宽是 375/420，但页面是按更宽的视口布局后再裁切的**。
表现就是：截图右侧「内容被切掉」，让你误判成"元素横向溢出"，然后去改一堆本来没问题的 CSS。

**判据**（一条命令识别是否被钳制）：截一张，量页面主容器的右边界。

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --force-device-scale-factor=1 --window-size=375,900 \
  --screenshot=/tmp/probe.png "file:///绝对路径/页面.html"
# 若容器是 .wrap{max-width:768px;padding:16px}，则
#   未被钳制 → 容器右边界 = 375-16 = 359
#   已被钳制 → 右边界会明显大于 359（例如落在 374/419）
```

本次实测：**375 和 420 都被钳制，560 正常**。所以：
- **宽屏自查用 560 / 768 / 1280**，这些是可信的
- **需要看 ≤414px 的真实手机效果时，不要靠缩窗口**，用下面的方法

### 坑 2（正确姿势）：用「抬高断点 + 约束 body 宽度」模拟真实手机视口

关键认知：**媒体查询按「视口宽度」计算，不按 `body` 宽度**。
所以 `body{width:360px}` 只能约束**布局宽度**，`@media(max-width:640px)` **不会**因此生效——
直接这么测会让你以为"移动端样式没写对"，其实是压根没触发。

可靠做法：**把断点临时抬到你能渲染的宽度以上**，同时把 body 压到目标宽度。

```bash
# 1) 生成测试副本：断点 640→820，并注入 body 宽度约束
python3 - <<'PY'
p = '/绝对路径/页面.html'
s = open(p, encoding='utf-8').read()
s = s.replace('@media(max-width:640px)', '@media(max-width:820px)', 1)   # 抬高断点
s = s.replace('</style>',
              '</style>\n<style>html{background:#888!important}'
              'body{width:360px!important;background:#f3f4f6}</style>', 1)
open('/tmp/g_mobile.html', 'w', encoding='utf-8').write(s)
PY

# 2) 用 820 宽窗口截（>最小宽度，不会被钳制；此时 820 断点已生效 = 移动端样式生效）
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=820,40000 --screenshot=/tmp/mobile.png "file:///tmp/g_mobile.html"

# 3) 数值化判定「有无横向溢出」：body 右侧的父页面背景色区域里不该有任何内容
python3 - <<'PY'
from PIL import Image
im = Image.open('/tmp/mobile.png').convert('RGB')
bg = (136,136,136)            # 父页面 #888
last = worsty = 0
for y in range(0, im.size[1], 3):
    for x in range(819, 359, -1):     # 只看 360px 之外
        p = im.getpixel((x,y))
        if abs(p[0]-bg[0])+abs(p[1]-bg[1])+abs(p[2]-bg[2]) > 25:
            if x > last: last, worsty = x, y
            break
print('超出 360px 的内容最右 x =', last, '@y=', worsty, '（0 = 无溢出 ✅）')
PY
```

同时把关键区域裁出来 Read 一眼，确认视觉可读（数值只证明"没溢出"，不证明"好看"）。

## 响应式表格：手机端横向溢出的标准解法

**根因（最常见）**：`th{white-space:nowrap}`。一个 nowrap 的表头就能把整张表撑到视口之外。
→ 去掉 th 的 nowrap，并给 `th,td` 加 `overflow-wrap:anywhere;word-break:break-word`。

**若还嫌挤**（4–5 列表格在 360px 下每列只有 ~70px，单元格会被拉得极高），按下面顺序升级：

| 方案 | 做法 | 评价 |
|------|------|------|
| A. 收紧 | 去 th nowrap + `overflow-wrap:anywhere` | 最省事，能消溢出，但窄屏仍显高 |
| B. 固定列宽 | `@media(max-width:640px){table{table-layout:fixed}}` | 保证不溢出，但**列宽被均分**，长文本列会炸高 → 不推荐单独用 |
| C. **整行堆叠卡片** ✅ | 见下 | **零横向滚动 + 手机端最好读**，首选 |

C 方案的 CSS（放在 `@media(max-width:640px)` 里）：

```css
.tw{overflow:visible}
table,thead,tbody{display:block;width:100%;background:transparent;border:none}
tr{display:block;border:1px solid var(--line);border-radius:10px;background:#fff;
   margin-bottom:10px;padding:7px 0;overflow:hidden}
tbody tr:first-child{display:none}        /* 隐藏表头行（浏览器会自动插 tbody） */
th,td{display:block;border:none;padding:3px 12px;text-align:left;font-size:13.5px}
td:first-child{font-weight:700;color:var(--brand);font-size:14px;
   border-bottom:1px dashed var(--line);padding:2px 12px 7px;margin-bottom:5px}
td[colspan]{color:var(--muted);font-size:12.5px}
```

要点：
- **前提是「第一列本身是有效标题」**（路段/服务区/目的地/店名/档位/分类…）。绝大多数攻略/说明类表格都满足，堆叠后自带小标题，不必额外加 `data-label`。
- 若某表第一列无意义（如纯序号），再考虑给 td 手写 `data-label` + `td::before{content:attr(data-label)}`。
- **列多的表更好的做法是直接放弃表格**：本次把「美食 5 列表」和「预算三档 7 列表」分别改成 `.shop` / `.tier` 卡片（名称 + meta 一行 + 若干 `b` 标签行），效果远好于任何表格方案。

**验证顺序**：改完必须重跑上面的「抬高断点 + body 约束」脚本，确认 `超出 x = 0`，再 Read 裁图看观感。

## 查看截图

截图落盘后**用 Read 工具读取 PNG**（多模态可直观看图），不要用 shell 看图。
若只需看某个区块，截窄屏（`--window-size=560,...`）可以让单栏布局铺满宽度、细节更清楚。

## 已知无害噪声

- `CVDisplayLinkCreateWithCGDisplay failed. CVReturn: -6670` — 无头环境的显示链接报错，忽略
- `task_policy_set TASK_SUPPRESSION_POLICY: (os/kern) invalid argument (4)` — 忽略
- 只要最后一行是 `bytes written to file`，截图就是成功的

## 配合的其它自查手段

| 目的 | 手段 |
|------|------|
| 脚本语法是否被改坏 | `node -e` 提取所有 `<script>` 用 `new Function` 逐块编译 |
| 关键函数是否还在 | `grep -c "function 函数名"` 逐个点检 |
| 映射表是否全覆盖 | 写个小 `node -e` 断言脚本核对编码/键的完备性 |
| 改动前留退路 | `cp 页面.html "页面.html.bak_pre_改动名_$(date +%Y%m%d_%H%M%S)"` |

## 交付前清单

1. 备份原文件（命名带 `bak_pre_<改动语义>_<时间戳>`）
2. 改完后跑语法检查 + 关键函数点检
3. **`shoot_report.js --strict`** 一把过结构自检 + 关键内容点检 + 多断点截图（省掉手写命令）
4. Read 出截图亲眼对比参考图 / 改动目标
5. 有偏差就微调（尺寸百分比、颜色、圆角、纹样透明度）再截一次
6. 最后 `present_files` 呈现给用户，并在回复里说明改了哪些规则、备份在哪
