---
name: html-visual-check
slug: html-visual-check
version: 1.0.0
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
```

## 核心命令

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
3. 多断点截图，Read 出来亲眼对比参考图 / 改动目标
4. 有偏差就微调（尺寸百分比、颜色、圆角、纹样透明度）再截一次
5. 最后 `present_files` 呈现给用户，并在回复里说明改了哪些规则、备份在哪
