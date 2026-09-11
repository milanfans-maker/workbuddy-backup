---
name: qq-junqi-replay
description: 开发和迭代 QQ 四国军棋复盘分析器（单文件 HTML 工具）。This skill should be used when the task involves parsing .jgs 复盘文件（QQ四国军棋二进制复盘）、文本复盘格式（v2.0 复盘文本）、玩家颜色/方位映射、逆时针行棋序、棋子价值表、行棋得失统计、回放渲染、或对 index.html 复盘分析器做任何修改与回归验证。Covers the .jgs binary format (0x20 玩家块/0x19B 指令区/0x5F 棋步), 方位几何推导 (voteDir), 三级回归工作流 (Node 引擎测试 + jsdom 冒烟 + 真实 Chrome 截图 + 6 个真实 .jgs 回归)。
---

# QQ 四国军棋复盘分析器开发

## 概述

本技能用于迭代 `/Volumes/me/ai学习/四国军棋/qq军棋复盘分析/index.html`（单文件 HTML：CSS+JS 全部内联，无外部依赖）。该工具导入 QQ 四国军棋 `.jgs` 二进制复盘文件或 v2.0 文本复盘，做 17×17 棋盘回放、行棋得失统计、胜负手 TOP3、关键事件、战役明细、子力净值曲线、评级。

核心能力：`.jgs` 二进制解析、方位↔颜色动态推导、渲染联动、三级回归验证。

## 关键约定（迭代时不可破坏的基线）

- **玩家颜色**：绿/黄/蓝/紫 四色，**按复盘文件方位动态确定**，不写死「上=绿、下=黄、左=蓝、右=紫`。`DEFAULT_ORIENT`（无证据时的回退）仍为 `{绿:'up', 黄:'down', 蓝:'left', 紫:'right'}`，但**2026-08-18 修正移动颜色编码后，6 个真实 .jgs 经几何推导（`voteDir`）的实际方位统一为 黄=up / 绿=down / 紫=left / 蓝=right**（对应玩家 大丈夫=黄=上、暴暴寒=绿=下、Ella乐乐=紫=左、习掼叻=蓝=右）；旧基线 绿=up/黄=down 是旧颜色数组导致的 180° 旋转错误结果。非标文件仍按几何推导。
- **方位名称**：上家/左家/下家/右家；**逆时针行棋序 = 上→左→下→右**。
- **棋子标识**：棋子上用单字（司/军/师/旅/团/营/连/排/炸/兵/雷/旗），各玩家棋子统一按玩家色区分，雷/炸不特殊着色。
- **行棋起点**：红框 + 箭头自动指向行棋方向（atan2 旋转）；终点黑框。
- **棋盘中间**：9 个兵站（行 7/9/11 × 列 G/I/K）用方形框 + 五角星；四角大本营 8 格 + 军旗角标。
- **棋子价值表**：司令100 军长80 师长60 旅长45 团长35 营长25 连长18 排长12 工兵8 炸弹35 地雷15 军旗0。
- **`.jgs` 方位映射已实测验证**：玩家块颜色字节 0=黄=下 / 1=蓝=左 / 2=绿=上 / 3=紫=右（`BYTE_COLOR=['黄','蓝','绿','紫']`、`QQ2DIR={0:'down',1:'left',2:'up',3:'right'}`）。**2026-08-18 按用户真实映射修正**：旧映射 `['绿','紫','黄','蓝']`（0=绿=上/1=紫=右/2=黄=下/3=蓝=左）已废弃。6_21 实测：字节0=黄=大丈夫、字节1=蓝=习掼叻、字节2=绿=暴暴寒、字节3=紫=Ella乐乐，己方 0x0F=2=绿=暴暴寒。**棋步颜色编码（b1 位4-3）是「有状态状态机」，不是固定映射，必须由玩家块颜色字节派生且处理玩家离场**：开局 4 家阶段，`bits=(b1>>3)&3` 的取值 = 玩家块颜色字节 QB 的「(QB+1)&3」偏移，即 bit=0→块1、1→块2、2→块3、3→块0，故开局阶段代码等价 `BYTE_COLOR[(bits+1)&3]`（等价 `['蓝','绿','紫','黄'][bits]`）。**但当某玩家「自杀战败/退出」（`0xF5` 事件 code=3/4）离场后，该家的颜色位由颜色环中其「后继者」继承**（环序=初始位升序 `RING=['蓝','绿','紫','黄']`，跳过已离场者，遇全离场则不更新）：
- 蓝离场(QB=1) → 后继者 绿 继承位0（绿原自身位1变空洞）；6_21 实测蓝离场后 bits=0→绿、bits=2→紫、bits=3→黄 全对。
- 黄离场(QB=0) → 后继者 蓝 继承位3。
- 绿离场 → 后继者 紫 继承位1；6_24 多玩家连续离场时，离场者被跳过、取下一个存活后继者（蓝离场→绿得位0，黄离场→绿跳过已离场的蓝得位3）。
实现：`extractMoves` 内维护 `RING/bitOfColor/colorOfBit/active`，`applyExit(ev)` 在 `0xF5` 事件(code=3/4)时更新映射，后续棋步按新状态机解码。**旧固定写法 `BYTE_COLOR[(bits+1)&3]` 玩家离场后会串色**（6_21 蓝离场后 bits=0 被误解为蓝、真值是绿，26 处不一致），此 bug 已于 2026-08-18 修正（6 文件 719 步 0 不一致）。渲染仍必须走动态推导（`voteDir`），不得依赖默认。
- **`.jgs` 布局矩阵按玩家自身视角存储（关键）**：每个玩家块的 30B 矩阵 = 6 行 × 5 列，`i=0` 靠前线、`i=5` 为底线（军旗在底线）、`j=0` 为该玩家左手边；逆时针行棋下四家均「面向棋盘中心」摆棋，故 `mapLayout` 必须统一使用玩家视角：
  - up   → `[5-i, 10-j]`
  - down → `[11+i, 6+j]`
  - left → `[6+j, 5-i]`
  - right → `[10-j, 11+i]`
  - 军旗大本营：`FLAG_H_DIR` 按方位定义双格 `{up:[[0,7],[0,9]], down:[[16,7],[16,9]], left:[[7,0],[9,0]], right:[[7,16],[9,16]]}`，军旗具体落哪格取决于各玩家块布局矩阵（2026-08-18 修正移动颜色编码后，新方位标准下实测示例：黄旗(上)0,9 / 绿旗(下)16,7 或 16,9 / 紫旗(左)7,0 或 9,0 / 蓝旗(右)7,16 或 9,16）。
- **交手净值（同尽）**：双方各记 `消灭对方子力价值 − 自己被消灭子力价值`。例如炸弹35炸司令100 → 炸方 +65、被炸方 −65；司令100吃军长80 → 攻方 +80、守方 −80。**每玩家净值 = 得分 − 损失**；仅在无战败清子时四家净值总和才为 0，存在自杀战败时战败方剩余棋子被清但不给对手计分，净值总和不为 0（正常规则）。`dig` 分支用 `VAL['地雷']=15`，`mine` 分支需双向记分。
- **战败判定与棋子消失**：
  - 被扛军旗：玩家军旗被夺后，该玩家立即战败，其所有棋子从棋盘移除。
  - 无子可动：某玩家轮到行棋时，若其剩余棋子中只有地雷/军旗（无可以移动的棋子），则该玩家战败，所有棋子移除。
  - 连续两次未行棋（自杀）：按逆时针 `TURN_ORDER` 模拟行棋序，玩家连续两次轮到却无行棋记录（被跳过）即战败清子；`trackTurnSkip` 在 analyze/snapshotAt 中调用。
  - 幽灵步保护：已战败玩家残留的行棋记录（resolveMove 会因起点无子返回 error）不参与行棋序跟踪。
  - 实现位置：`resolveMove` 的 `flag` 分支直接移除被扛旗方全部棋子；`analyze()` 与 `snapshotAt()` 在 resolveMove 前调用 `checkDefeatBeforeMove` 检测无子可动，并调用 `trackTurnSkip` 检测连续两次未行棋。`analyze()` 返回的 `alive/defeatedAt` 供渲染层判断胜/负徽章与结果文本。
- **玩家名替换颜色称呼**："本局胜负手""行棋得失统计""本局战役明细"及净值曲线图例中，绿/黄/蓝/紫家统一显示为 `replay.players[c]`（通过 `playerName(c)`），内部逻辑仍用颜色键。
- **对局信息/玩家卡 UI**：对局信息固定五项=对局时间（`parseTimeFromName` 从文件名解析 junqi2026_6_24_16_22 → 2026年6月24日16时22分，优先 meta['时间']）→ 人数 → 步数 → 结果 → 来源文件；不显示己方视角与方位映射。玩家卡顶部名字+胜/负徽章+方位·步数，中间两行统计，底部步数占比条。战果/被俘一览 chips 按子力价值从大到小排序。
- **胜负判定 = 按【行棋结果】，不得再用子力净值（2026-09-10 改）**：`teamSplit()` 按方位对家分队（上/下=UD，左/右=LR）；`getWinTeam()` 优先级：① 出现 `res.type==='flag'`（扛旗）→ 扛旗方所在队胜；② 某队两人皆 `alive=false` 而另一队尚有存活 → 存活队胜；③ 双方全灭 → 比较 `analysis.defeatedAt`，最后离场的一方胜；④ 其余（双方均无人离场，或仅一人离场而队友尚在）→ 返回 `null`，界面回落显示 meta 结果、玩家不贴胜/负标签（含「和局/平局」时贴 `tag draw`「和」）。**旧实现「净值之和大的一队为胜」已删除**（示例谱第162步蓝方扛走绿旗，本应蓝紫胜，却因绿黄净值和更高而误判为绿黄胜）。
- **对局信息对阵头（2026-09-10 改）**：`#infoGameTitle` 不再四人平铺 `vs`，而是**按队分组**——队内用 ` +` 连接、两队间用 ` vs ` 连接，形如 `真实的背后 +↘ゞ钟情 vs 爆炸糖糖 +利物浦＆三拳`。两队先后与队内次序**均按 `COLOR_ORDER=['绿','黄','蓝','紫']` 座位顺序**（按各队第一名在 COLOR_ORDER 的 index 排序），以保持与原先四人顺序视觉一致；`teamSplit()` 返回 null 时回落原四人 ` vs ` 全排。
- **四方阵地左下角外 ID 标签**：四个标签分别在四个阵地左下角外的空白角区/边缘——上 → `cell(5,5)` 右锚点向左延伸、左 → `cell(11,0)` 左锚点向右延伸、右 → `cell(11,11)` 左锚点向右延伸、下 → `cell(16,5)` 右锚点向左延伸（下阵地左下角 (16,6) 左侧空白格，与上方位对称；**不再是棋盘底部外的 `#selfLabel`**）。字号 12px 加粗、颜色 = `PC_COLORS[replay.dirToColor[dir]]`（随视角自动映射）、底色 `rgba(250,247,238,.88)` + 1px 描边 + `white-space:nowrap` + `z-index:3` + `pointer-events:none` 保证不遮挡棋子。`renderBoard` 末尾调用 `renderCornerLabels`（每步重建，因 renderBoard 清空 cell innerHTML）。`spots` 数组定义在 `renderCornerLabels` 内。
- **关键事件步（自杀/战败/退出）——新增于 2026-08-18，必须保留**：`.jgs` 中 `0xF5` 事件指令穿插在 `0x5F` 棋步指令之间，**不占独立移动步**。事件 `b1`=02超时/03自杀战败/04退出/05结束，`a`=玩家颜色字节（`BYTE_COLOR[a]`），`b`=相关参数（`b1=05 && b=4` 为「结束」事件，不输出为玩家步）。为让文本步数与真实对局一致、避免后续步数偏差与颜色串位，必须把玩家事件作为独立步骤纳入：`extractMoves` 用 `seq` 数组保留「指令流顺序」（move/event 交错）；`jgsToText` 遍历 `seq`，事件步输出 `stepNo. 颜色 事件名`（如 `240. 蓝 自杀战败`、`242. 蓝 退出游戏`——新映射下 6_21 的习掼叻=蓝，即用户问题2所指的第240/242步）并从棋盘清除该玩家全部棋子；`parseReplay` 用正则 `^(\d+)[.、]\s*[蓝红绿灰黄紫]\s*(军旗被扛，战败|自杀战败|战败|退出游戏|超时判负|退出|判负)` 识别事件行并纳入 `moves`（`type:'event'`，无 from/to）；`analyze()` 与 `snapshotAt()` 对事件步标记 `alive[evColor]=false; defeatedAt[evColor]=mv.no; removeAllPieces(layout, evColor)`；`renderMoveList`/`gotoStep`/`renderBoard`/`cloneMove`/`rotateView`/`topClutch` 均需对 `type==='event'`（无 from/to）做分支，避免 `mv.from[0]` 崩溃。**事件步清子后，战败玩家后续残留的「幽灵步」（原始文件仍编码为该色）会被 resolveMove 优雅跳过（起点无子→error），不污染统计；`trackTurnSkip` 对已战败玩家直接 return。** 移动步基线（318/22/67/72/35/205）不含事件步；文本/二次导入总步数 = 移动步 + 玩家事件步数（结束事件不计）。
- **军旗被扛战败事件文本修正（2026-08-18 新增）**：QQ 在棋子扛走某家军旗后，会紧接着为该家发一个 `0xF5` code=3 战败事件；此时该事件本质是「军旗被扛，战败」，而不是「自杀战败」。`jgsToText` 用 `justFlagTaken` 记录「上一步是否刚扛了某家军旗」，当紧随其后的 code=3 事件的 `evc===justFlagTaken` 时输出 `军旗被扛，战败`，否则输出 `自杀战败`（每个 move 步重置 `justFlagTaken=null`）。**`parseReplay` 事件正则必须含 `军旗被扛，战败`**（否则该行无法被识别为事件步，会导致步号错位）。实测 6 文件：6_21 的321紫、6_22_14_57 的23黄、6_24_16_22 的200蓝 均为「军旗被扛，战败」；其余自杀（6_21的240蓝、6_22_15_4的67绿/70黄、6_22_16_38的69黄/75绿、6_24_14_24的35绿/38黄、6_24_16_22的206黄/208紫）仍为「自杀战败」。此修正同时改到 `parseReplay` 正则与 `jgsToText` 两处，需同步。
- **Puppeteer 验证陷阱**：`page.setContent` 模式下 localStorage 抛 SecurityError（无 origin），`loadViewPref` 会回退默认 `self`——视角/偏好相关断言需用 `page.goto('file://...')` + `evaluateOnNewDocument(()=>{window.LA={init:()=>{}};})` 桩掉 51.la，否则会有 `LA is not defined` pageerror 且 localStorage 不可用。
- **布局正确性判定方法（强标准）**：对真实 .jgs 文件做**行棋结果位一致性验证**——用引擎推演每步结果类型（移动/吃/被吃/同尽）对比文件 res 位（b1 位1-0：0/1/2/3）。镜像方案错误时一致率通常 70%~95%；正确方案应 ≥99%（6 文件实测 99.5%~100%）。
- **视角旋转（以某玩家为下家）**：QQ 客户端习惯「己方视角」——自己永远在下家。网页默认以「己方」为下家整体旋转（布局+行棋坐标+方位标签），其余三家按复盘相对方位保持。提供「绝对方位（文件原始）」切换。棋盘地形 90° 旋转对称，旋转后军旗仍落对应方位大本营。
- 页面必需要素：SEO 简介（含 JSON-LD WebApplication）、底部备案（赣ICP备15001421号 + 赣公网安备36100002000207号）、51.la 流量统计。**署名为「设计制作：暴暴寒（7z） | 规则赋能/优化：姜朕熙（B站：老姜甄鉴）」，页头 badge 与页脚版权两处需同步**（旧署名「热心市民小寒（7z）」已废弃）。

## 主题化（浅色米金 ↔ 黑金奢华深色，2026-09-10 新增）

单文件 HTML 加主题的可靠范式，本项目的具体落点：

- **挂载点选 `<html class="theme-dark">` 而非 body**：这样能在 `<head>` 末尾放一小段内联脚本 `try{if(localStorage.getItem('junqi_theme')==='dark')document.documentElement.classList.add('theme-dark')}catch(e){}`，**提前于 body 渲染加类，避免深色下首屏闪白**。所有深色规则统一写 `html.theme-dark ...`。
- **优先覆盖 CSS 变量**：`html.theme-dark{--bg/--panel/--ink/--line/--accent/...}` 整体覆盖 `:root`。`html.theme-dark`（0,1,1）特异性高于 `:root`（0,1,0），无需 `!important`。
- **硬编码浅色只能逐条覆盖**：原样式里写死的浅底（`#faf7ee`/`#f9f8f5`/`#fcfbf6`/`#e3f2fd`/`#eee`/`#f5efdc` 等约 128 处）用 `html.theme-dark .xxx{...}` 覆盖，**只改配色、绝不动布局尺寸**。
- **棋盘变量**：`--board-bg`/`--railway`/`--green-bg`…`--purple-bg`/`--camp-bg`/`--hq-bg` 换深色版本即可；`--highlight-to` 浅色下是 `#1a1a1a`（黑框），深色下必须改成亮色（如 `#f0c940`）否则终点框在深色棋盘上不可见。
- **图表换色（关键坑）**：曲线/雷达 SVG 原写死 `stroke="#eae4d2" / fill="#999"`。**SVG 表现属性不支持 `var()`**，`stroke="var(--x)"` 无效，必须改成**内联样式** `style="stroke:var(--chart-grid)"`。已抽出 6 个变量：`--chart-grid / --chart-axis / --chart-label / --chart-label-strong / --chart-grid-soft / --chart-label-soft`，两套主题各一组 → **切主题时图表无需重渲染即自动换色**。
- **切换控件**：页头 `#themeSwitch` 双段药丸（`.ts-btn[data-theme=light|dark]`，☀️/🌙），选中态金色渐变+发光环，未选中 `opacity:.45; filter:grayscale(.55)` 拉开对比（两个 emoji 都是黄色，靠灰度/透明度区分否则看不出选中）。
- **宿主窗口同步**：`applyTheme()` 内顺带 `replayWin.document.documentElement.classList.toggle('theme-dark', dark)`；`openReplayWindow()` 拼 HTML 时按主窗主题给子窗 `<html>` 加 `class="theme-dark"`，否则弹窗永远是浅色。
- **持久化**：`localStorage['junqi_theme'] = 'dark'|'light'`；全局函数 `currentTheme()` / `applyTheme(mode, persist)` / `toggleTheme()`，常量 `THEME_KEY`。DOMContentLoaded 里 `applyTheme(saved, false)` 恢复（`persist=false` 避免无谓写回）。
- **验证**：`puppeteer-core`（在 `/Users/wangjian/.workbuddy/binaries/node/workspace/node_modules`）+ 本机 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` 做无头截图，逐块比对深色下的页头/棋盘/技术积分/统计卡(含曲线)/评估卡(雷达图)/弹窗，确认无白底残留；并断言弹窗 `documentElement.className==='theme-dark'`、主窗切回浅色后弹窗 `body` 背景同步回 `rgb(242,239,232)`。

## 迭代工作流

修改 index.html 后必须按以下顺序回归，缺一不可：

### 第 1 步：Node 引擎回归

`/tmp/test_color_v2.js`：从 HTML 抽取纯 JS 逻辑（引擎部分）在 Node 中运行，断言解析、统计基线、方位映射、行棋序。当前基线 35 项通过。

```bash
NODE_PATH=/Users/wangjian/.workbuddy/binaries/node/workspace/node_modules /Users/wangjian/.workbuddy/binaries/node/versions/22.22.2/bin/node /tmp/test_color_v2.js
```

统计基线（test_color_v2 使用内置固定示例 `DEMO_TEXT`，该文本是用**旧方位**从 6_24_16_22 转换的，205 移动步 + 3 事件步；数组=[步数,吃子,被吃,同尽,炸杀,中炸,挖雷,得分,损失,净值]）：
绿[53,8,5,5,2,1,0,452,285,167]、黄[50,7,8,3,2,1,0,307,368,-61]、蓝[52,6,7,5,1,2,0,450,439,11]、紫[50,7,7,6,1,1,0,257,409,-152]。**改动统计逻辑、战败规则或 DEMO_TEXT 后必须重跑并更新基线**。

> **重要区分（2026-08-18 修正移动颜色编码后）**：`DEMO_TEXT`（旧方位固定文本）统计 ≠ 真实文件 `parseJGS` 的新方位统计。真实 6_24_16_22.jgs（黄=up/绿=down/紫=left/蓝=right，205 移动步 + 3 事件步=蓝/黄/紫自杀战败）**离场串色修复后的移动步基线为 蓝49/黄52/绿52/紫52**（`/tmp/test_view.js` 断言；旧基线 蓝50/黄53/绿50/紫52 是修复前颜色解码错误导致的统计偏差，2026-08-18 已更新）。四家净值总和在有自杀战败清子时不为 0（战败方剩余棋子被清、不给对手计分），这是正常规则。

### 第 2 步：jsdom 全页冒烟

`/tmp/smoke_v2.js`：jsdom 加载完整 HTML，断言 DOM（棋盘 100 子单字、四色 piece class、9 兵站/8 hq/20 camp、行棋条方向、玩家卡、视角下拉与切换、图例、进度条等）。当前 84 项通过。

### 第 3 步：6 个真实 .jgs 回归

`/tmp/all_files_orient_v3.js`：对布局库 6 个 .jgs 逐一验证方位映射（逐键断言，勿用 JSON.stringify 比较对象——键序会导致误判）、orientSrc='geo'、军旗落点、移动步数基线（318/22/67/72/35/205，不含事件步）、布局 100 子、jgsToText 含「方位=」行、二次导入 orientSrc='meta'、事件步输出与识别（文本总步数=移动步+事件步、二次导入事件步数）。当前 66 项通过。

### 第 4 步：真实 Chrome 截图回归

`/tmp/shot_v2.js`（puppeteer-core + 系统 Chrome）：加载文件、点「开始分析」、断言 DOM 状态（turnChips、orientMeta、起点箭头旋转角）+ 截图。**必须零运行时错误（console/pageerror）**。

## 测试脚本维护

- 测试脚本放 `/tmp/`（不入库）。修改引擎/渲染后先更新测试断言（新基线、新用例），再跑回归。
- **注意 `/tmp` 会被系统清理**：上面第 1~4 步提到的 `/tmp/test_color_v2.js`、`/tmp/smoke_v2.js`、`/tmp/all_files_orient_v3.js`、`/tmp/shot_v2.js` 常已不存在。重建最省事的办法是照 `/tmp/junqi_test/` 的现成套路：`extract_engine.py`（用 `re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)` 取**最长**的 script 块写 `engine_raw.js`，比脆弱的 `/<script>(...)<\/script>\s*<\/body>/` 正则稳——页面后来新增了 `<head>` 内联脚本，老正则会误配）、`run_e2e.js`（Node+vm 桩 DOM 跑 startAnalyze）、`run_ui.js`、`run_badge.js`、`run_timeout5.js`、`run_tech.js`、`shot.js/shot2.js`（puppeteer-core 无头截图）。有条件时把这套 harness 固化到项目目录里，避免每次重建。
- **e2e 基线**（示例棋谱 `DEMO_TEXT`，75 步）：技术积分 绿27 / 黄125 / 蓝576 / 紫65。**注意 `骗令` 分值 = 被吃掉的己方棋子价值（`VAL[ap]`），非固定值**，所以别把它当作固定基线断言。
- 新增视角/旋转类需求：加用例覆盖目标玩家=下家、军旗落新大本营、行棋序、玩家卡、坐标旋转、可切回绝对方位。
- 断言对象相等用**逐键断言**（`obj['绿']==='up'`），勿用 `JSON.stringify` 比较——JS 对象键插入顺序会造成误判。

## 方位推导机制（详见 references/jgs-format.md）

- `.jgs`：`voteDir`（行棋 from 坐标半场多数派，≥2 票）→ `orientSrc='geo'`；不足 2 票回退玩家块颜色字节默认方位 `'byte'`。
- 文本复盘：`[对局信息]` 的「方位=上:绿 右:紫 下:黄 左:蓝」行最优先（`'meta'`）→ 布局落点推导（`'layout'`）回退。
- `applyOrient(replay)` 把 orient 应用到渲染层：重排 TURN_ORDER、更新 TURN_POS/COLOR_INFO[c].dir、写回 replay.orient/dirToColor/orientSrc。**startAnalyze 必须在 parseReplay 之后调用 applyOrient**。
- **视角旋转在 applyOrient 之后由 `setView(replay, viewColor)` 完成**：先保存 baseLayout/baseMoves/baseOrient，再整体旋转坐标与方位，再调用 applyOrient 更新渲染全局。`loadViewPref/saveViewPref/viewColorOf` 负责读取 localStorage 视角偏好并解析为颜色。
- `inBase` 必须读 `replay.orient`（或 DEFAULT_ORIENT），不得写死颜色→区域；旋转后 orient 与坐标同步更新，故仍正确。
- 渲染层「方位映射」元信息项需带来源标注（行棋坐标推导/文件方位/布局位置推导），并在视角旋转后追加视角说明。
- 板底图例需随当前视角动态更新（`renderLegend`），不能写死 上绿/下黄/左蓝/右紫。

## 领域格式速查

- `.jgs` 二进制：偏移 0x20 起 4 个 88B 玩家块（p+0x00 颜色字节、p+0x08 名字 GBK 20B、p+0x1C 布局 30B）；指令区 0x19B/0x19C 起（双偏移容错），每 10B 一条，0x5F=棋步、0xF5=事件；棋步 b1 位4-3=玩家颜色位 `bits=(b1>>3)&3`，**为有状态状态机**：开局阶段取值=玩家块颜色字节 QB 的「(QB+1)&3」偏移（bit=0→块1/1→块2/2→块3/3→块0），等价 `BYTE_COLOR[(bits+1)&3]`（即 `['蓝','绿','紫','黄'][bits]`）；玩家离场（0xF5 code=3/4）后，该颜色位由颜色环后继者继承（RING=蓝→绿→紫→黄→蓝，跳过已离场者）。b2b3=起点(纵,横)、b4b5=终点，纵坐标自下而上需 16-y 翻转。事件字节：b1=02超时/03战败/04退出/05结束、`a`=玩家颜色字节（`BYTE_COLOR[a]`）、`b`=参数；**code=3 战败若紧随「刚被扛军旗的同一家」，文本应为 `军旗被扛，战败`（QQ 在扛旗后发 code=3），否则为 `自杀战败`**；事件穿插于棋步间，`extractMoves` 用 `seq` 保留指令流顺序。
- 完整字段说明见 `references/jgs-format.md`。

## 参考文件

- `references/jgs-format.md`：.jgs 二进制格式完整规范、方位几何推导算法、jgsToText 输出格式、已知坑（双偏移、纵坐标翻转、键序陷阱、GBK 编码）。
