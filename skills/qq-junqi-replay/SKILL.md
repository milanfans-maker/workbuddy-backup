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
- **行棋起点**：红框 + 箭头自动指向行棋方向（atan2 旋转）；终点框。**两个文件现均为 QQ 军绿棋盘，高亮用 `--highlight-from:#ff4d3d`（红）/`--highlight-to:#ffd54f`（亮金）；旧的深黑 `#1a1a1a` 只在早已废弃的米色棋盘上可见。** 高亮类名是 **`highlight-from` / `highlight-to`**（不是 `hl-*`），加在 `#cell-<row>-<col>` 上，`curMove.from/to` 是 `[行, 列]` 顺序。
- **音效（2026-09-16 起为内嵌 WAV 采样）**：6 条 wav 以 base64 写在 `var SFX_B64` 里，`playSound(type)` 类型名不变。口径：`move`→移动走子 / `eat`+`dig`→吃子 / `killed`+`mine`+`bounce`→撞子被反吃 / `cmdr`→司令阵亡亮旗 / `both`+`bomb`→兑子被炸 / `flag`+事件步 `evKind==='defeat'`→扛旗投降自杀 / `pass`→保留合成双音兜底。**「司令阵亡」靠 `resolveMove()` 打的 `event.cmdr` 结构化标记，事件步靠 `event.evKind`，两者都不许用文案正则判**（详见「音效系统」一节）。
- **棋盘中间**：9 个兵站 = 中央九宫格（行 6/8/10 × 列 6/8/10），用**空心圆角方环**（`.cell.station::after`，`inset:23%` + `2px solid var(--station-ring)`，`border-radius:4px`），有子时 `occupied` 隐藏环；**不再用旧版「方形框 + 五角星」**（那个已随 QQ 棋盘改版删除）。四角大本营 8 格（4 家 × 2）+ `★` 角标（`.cell.hq::after`，淡金色 `--hq-mark`）。行营 20 个用空心圆环（`.cell.camp::after`，`21×21` 圆 + `3px solid var(--camp-ring)`）。三者的环一律走 `::after` + `inset`，**不要用 `border` 直接画在 `.cell` 上**（会撑开格子）。
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

## 棋盘视觉规格 · QQ 军棋客户端风格（2026-09-15）

**✅ 2026-09-15 15:38 起 `index.html` 与 `index_task2.html` 已同为这套风格**（task2 → index 反向迁移完成，见下节「反向迁移记录」）。此前只有 task2 是这套风格。

**⚠️ 两个文件都不再是「旧米色方格 + 方形彩底白字棋子」，改代码时不要按旧印象下手。** 新棋子的关键特征：`30×25` 横牌、浅底深字、四色 `linear-gradient(180deg, …)`、`border-radius:3px`、`font-size:15px`、`border:1.5px solid`；`#boardWrap` 是军绿布料底；铁路走 `.board-svg` 叠加层。

**⚠️ 迁移方向已双向打通**，但**功能块必须逐块甄别**，不能整文件覆盖（两文件 `data-page-node-id` 全不同、功能累积进度不同）。

### 从 QQ 客户端实测反推的比例（复刻依据）

截图上量取（上家阵地 5 列 × 6 行）：格距 **49×43**（宽:高 ≈ 1.14），棋子 **46×40**，即棋子宽/格距 ≈ **94%**、高/格距 ≈ **93%** —— **QQ 棋子几乎填满格子，且是「略横」的长方形，不是明显扁条**（一开始按 1.4 比例做会偏扁）。我们的棋盘是 17×17 **正方形** 32px 格，所以取 `30×25`（同 1.2 宽高比 + 同填充率）。

### 底板

```css
#boardWrap{background:
  radial-gradient(120% 88% at 50% 42%, rgba(255,255,255,.05), transparent 62%),   /* 中心微亮 */
  repeating-linear-gradient(90deg, rgba(0,0,0,.055) 0 1px, rgba(255,255,255,.02) 1px 3px),  /* 纵向织纹 */
  linear-gradient(165deg, var(--board-bg-2), var(--board-bg));}   /* 军绿 #6b7a48 → #5a6839 */
```
`.board-grid` 去掉 `background` 与 `border:2px solid var(--railway)`，改 `background:transparent`（否则棋盘外框会露出旧棕边）。

### 网格线：公路走 CSS 渐变，铁路 + 行营斜线走 SVG 叠加层

**公路细网格线**（保留 CSS 方案）—— 在 `.cell` 上声明两个渐变变量，每格在格心画一个细十字，相邻格自然接成整张网：

```css
.cell{
  --gl-h:linear-gradient(to bottom, transparent 0 calc(50% - .5px), var(--grid-line) calc(50% - .5px) calc(50% + .5px), transparent calc(50% + .5px));
  --gl-v:linear-gradient(to right,  …同上…);   /* 公路：格心 1px 细线 */
  background-image:var(--gl-h), var(--gl-v);
}
```

**铁路网 + 行营斜线改用 SVG 叠加层**（2026-09-15 重做，原按格渐变方案已删除）：

原方案「(r,c) 与 (r,c+1) 都是铁路 → 本格画整格宽横线」有两个治不好的毛病：① 线段只能横平竖直、无法表达端点，铁路段首尾会多画/少画半格；② 拐角与交叉靠格心叠出来，铁路网在中央区直接断成互不相连的碎块。改用 SVG 后线段以**行棋点（格心）**为端点，整网连通。

```css
.board-svg{
  position:absolute; left:20px; top:20px;              /* 跳过 20px 坐标表头 */
  width:calc(17 * var(--cell-size)); height:calc(17 * var(--cell-size));
  pointer-events:none; z-index:1; overflow:visible;
}
.board-svg .diag   {fill:none; stroke:var(--grid-line); stroke-width:1px; vector-effect:non-scaling-stroke}
.board-svg .rail   {fill:none; stroke:var(--railway);   stroke-width:5px; vector-effect:non-scaling-stroke}
.board-svg .rail-hi{fill:none; stroke:var(--railway-hi);stroke-width:1px; vector-effect:non-scaling-stroke}
```

- **⚠️ 最大的坑：SVG 绝对不能当 grid item 排版。** 若写 `grid-area:2/2/19/19` 让它参与网格布局，它会吃掉 17×17 = **289 个格子**，把后面 289 个 `.cell` + 35 个 header 全挤出显式网格，浏览器生成 17 个隐式行、第 1 行被撑到 544px（=SVG 高度），整个棋盘彻底错位。必须 `position:absolute` 脱离网格流，`.board-grid` 补 `position:relative` 做定位上下文。
- 坐标系：`viewBox="0 0 17 17"`，1 单位 = 1 格，格 (r,c) 的格心 = `(c+.5, r+.5)`；SVG 尺寸用 `calc(17 * var(--cell-size))`，所以主窗 32px 与全屏弹窗 46px **同一份 DOM 自动适配**（弹窗克隆卡片即生效，无需另写）。
- 线宽用 `vector-effect:non-scaling-stroke` + **绝对 px**，与改造前行为一致（32px 格与 46px 格里轨道都是 5px）。
- `stroke` 走 CSS 而不是 SVG 表现属性 → 支持 `var()`，主题切换即时生效（图表那条「SVG 不支持 var()」的坑只针对 `fill=`/`stroke=` 属性，CSS 声明不受限）。
- 层级：`.board-svg` `z-index:1`（在 cell 背景之上、棋子之下），`.piece` 保持 `z-index:2`，`.move-arrow` 等留在 cell 内按 tree order 压过 SVG。
- **线段的生成规则**（`buildBoardSvg()`）：每个铁路点只向**右**和**下**各探一次邻居，**但必须过 `railLinked()` 这一关** —— 只有两格心之间真的落在同一条 `RAIL_LINES` 线表线段上，才推一条线段。天然去重，横竖各一条不会重画。

**铁路拓扑口径（2026-09-15 深夜最终版，已按用户三轮纠正收敛）**：

用户第三轮纠正（截图圈出「军长 → 中央铁路」那条多余连线）暴露了上一版口径依旧过宽：**上一版是「逐点布尔判定 + 每家第 1/5 排整排」，于是行 7/9、列 7/9 上虽然点被判成非铁路，但相邻两点之间仍会被连出线段**。根治办法是**从「逐点判定」升级为「线表驱动」**：先列出全部 14 条铁路线段，`isRailway` 判点、`railLinked` 判段，两者同源于一张表，再也不可能各自为政。

- **四家各一个 5×5 铁路环**（不是「第 1/5 排两条横线 + 散布竖线」）：
  - 上家 = 行 1·行 5 × 列 6·列 10；下家 = 行 11·行 15 × 列 6·列 10
  - 左家 = 列 1·列 5 × 行 6·行 10；右家 = 列 11·列 15 × 行 6·行 10
- **中央 3×3 九宫格**（行 6/8/10 × 列 6/8/10）。其中 **行 6/行 10 与 列 6/列 10 本就是四家环的边**（分别贯通列 1-15 / 行 1-15），只有中间那条**「行 8」「列 8」各向两端延伸 1 格**（列 5-11 / 行 5-11），去接四家的第 1 排。
- 合计 **14 条线**，不多不少 —— **行 7/9 与列 7/9 上没有任何铁路线段**，这正是「军长（行 9·列 5）→ 中央铁路」那条多余连线的根源，现已彻底消除。
- 第 6 排（底线）不是铁路（用户第二轮纠正；像素采样亦证实底线为绿色公路色）。

```js
/* 格式 ['h', 行号, 起始列, 终止列] / ['v', 列号, 起始行, 终止行] */
var RAIL_LINES = [
  ['h',1,6,10], ['h',5,6,10], ['h',6,1,15], ['h',8,5,11], ['h',10,1,15], ['h',11,6,10], ['h',15,6,10],
  ['v',1,6,10], ['v',5,6,10], ['v',6,1,15], ['v',8,5,11], ['v',10,1,15], ['v',11,6,10], ['v',15,6,10]
];
function isRailway(r,c){
  if (r<0 || r>16 || c<0 || c>16) return false;   /* 越界保护：c+1 / r+1 探边界会踩 undefined */
  for (var i=0;i<RAIL_LINES.length;i++){
    var L = RAIL_LINES[i];
    if (L[0]==='h'){ if (r===L[1] && c>=L[2] && c<=L[3]) return true; }
    else           { if (c===L[1] && r>=L[2] && r<=L[3]) return true; }
  }
  return false;
}
/* 相邻两格心之间是否真有一段铁路：必须落在同一条 RAIL_LINES 上 */
function railLinked(r,c,r2,c2){
  var lo, hi;
  for (var i=0;i<RAIL_LINES.length;i++){
    var L = RAIL_LINES[i];
    if (L[0]==='h' && r===r2 && r===L[1]){
      lo = Math.min(c,c2); hi = Math.max(c,c2);
      if (lo>=L[2] && hi<=L[3] && hi-lo===1) return true;
    }
    if (L[0]==='v' && c===c2 && c===L[1]){
      lo = Math.min(r,r2); hi = Math.max(r,r2);
      if (lo>=L[2] && hi<=L[3] && hi-lo===1) return true;
    }
  }
  return false;
}
```

`buildBoardSvg()` 里改为：
```js
if (!isRailway(r,c)) continue;
var x = c + .5, y = r + .5;
if (railLinked(r,c,r,c+1)) segs.push([x,y,x+1,y]);   /* 向右半段 */
if (railLinked(r,c,r+1,c)) segs.push([x,y,x,y+1]);   /* 向下半段 */
```

> 历史坑：早期版本靠 `BOARD_LAYOUT[r][c] === 'H' && r,c ∈ [6,10]` 把中央兵站算进铁路（「铁道线缺失、不闭合」的根因）；线表化后该分支彻底消失，顺带绕开「`'H'` 有两类（中央兵站 vs 四角大本营）需靠坐标区分」这个坑。

改后铁路网：**85 个铁路点 / 100 条 SVG 线段 / 64 条行营斜线，整网一块连通**（flood-fill 验证 85/85）。

ASCII 自检图（`node -e` 用 `isRailway` 打印 17×17，`#`=铁路 `o`=行营 `.`=空地 `H`=大本营）：

```
     0 .......H.H.......
     1 ......#####......
     2 ......#o.o#......
     3 ......#.o.#......
     4 ......#o.o#......
     5 ......#####......
     6 .###############.
     7 H#o.o##.#.##o.o#H
     8 .#.o.#######.o.#.
     9 H#o.o##.#.##o.o#H
    10 .###############.
    11 ......#####......
    12 ......#o.o#......
    13 ......#.o.#......
    14 ......#o.o#......
    15 ......#####......
    16 .......H.H.......
```

> 行 7/行 9 上只剩「列 1·5·6·8·10·11·15」7 个铁路点（四家环的两条竖边 + 中央竖轨），**列 7 与列 9 在这两行上完全空白**；列 0/列 16 在所有行上都不是铁路。

**行营「米」字形细线**（用户第三轮需求：每个营 8 个方向都要有线，表示营旁各方向的棋子都能进营）：

- **正交 4 向由 `.cell` 的公路细网格提供**（格心十字天然把相邻行棋点连通），SVG 里只补 **4 条 45° 斜线**。
- 斜线终点**放开到任意行棋点**（不再要求两端都是营）——例如营 (2,7) 的 ↖斜线终点是 (1,6) 的普通行棋点。这正是「米」字比原来「营↔营 X 形」多出来的部分。
- 终点落在 `'.'`（四角空白区）时跳过 —— 角落 4 个营各有一向指进空白区，故总数 = 20 营 × 4 − 16 = **64 条**。
- 用 `min(r,r2),min(c,c2)|max(r,r2),max(c,c2)` 做 key 去重，否则每条会被两侧各推一次。
- 颜色取 `--grid-line`（与公路同色，细线 1px）；画在 `<g class="diag-layer">` 里、铁路层之前，避免交叉处被粗轨道压住。

**中央区除铁道线外不画公路细网格**（用户第三轮需求，对应截图中贯穿格心的淡绿细线）：

```css
.cell.empty{background:transparent}
.cell.plain{background-image:none}   /* 中央区：只有铁道线 */
```
`buildBoardGrid()` 里给 **行 6-10 × 列 6-10 的 25 格**（含中央 3×3 的 9 个兵站 `H`）追加 `plain` 类。注意 `.cell.plain{background-image:none}` 必须写在 `.cell` 的 `var(--gl-h)/var(--gl-v)` 之后才生效；`.cell.empty` 的 `transparent` 简写与 `.cell.hq`/`.cell.camp` 同理，只改 `background-color` 不碰 `background-image`。

**中央九宫格四角的「弧形铁道」**（用户第四轮需求：「师长和司令之间这个角用一条弧行铁道线连接」）：

先定坐标：左家 5×5 环 = 列1·列5 × 行6·行10，其**右下环角 = (10,5)**；下家环角 = (11,6)；中间 (10,6) 是 `行10 × 列6` 的十字交叉 + 兵站。所以「师长和司令之间这个角」= **(10,6) 角的西南象限**。

对 QQ 客户端原图实测（逐像素取弧线中线 + 三种半径叠加比对），结论：

- **四个中心角各有一段**，且都画在**九宫格外侧那一象限**（不是内圈）：
  | 角 | 象限 | 连接的两臂 | 连的格子 | 圆心 |
  |---|---|---|---|---|
  | (6,6) | 西北 | 西 + 北 | (6,5)↔(5,6) | (5,5) |
  | (6,10) | 东北 | 北 + 东 | (5,10)↔(6,11) | (5,11) |
  | (10,6) | 西南 | 西 + 南 | (10,5)↔(11,6) | (11,5) |
  | (10,10) | 东南 | 东 + 南 | (10,11)↔(11,10) | (11,11) |
- 几何：**以该角的「对角格」为圆心、半径 = 1 格的四分之一圆**。于是弧线两端正好落在相邻两条臂的**格心**上（不是半格处），弧中点距交叉口 `√2−1 ≈ 0.414` 格。
  > 半径实测值在 0.88~1.14 格之间抖动（近竖轨处采样被吞），取整为 **1 格** 最自然，且端点恰好落在格心——这个「端点 = 格心」的巧合反过来印证了 R=1 就是原设计。
- **四家自己环的角没有弧线**（如 (5,6) 就是普通的直角/丁字），别画多了。
- 直线臂**不裁短**：QQ 里直轨照旧穿过交叉口，弧线是额外叠上去的（形成「人」字形分叉）。

实现：`RAIL_ARCS` 存 4 条 SVG `d` 字符串，`buildBoardSvg()` 里用**独立的 `<g class="arc-layer">` 追加在 `rail-layer` 之后**（弧压在直轨之上，才能保证弧的白芯连续、不被直轨白芯横切）：

```javascript
var RAIL_ARCS = [
  'M 5.5 6.5  A 1 1 0 0 0 6.5 5.5',
  'M 10.5 5.5 A 1 1 0 0 0 11.5 6.5',
  'M 5.5 10.5 A 1 1 0 0 1 6.5 11.5',
  'M 11.5 10.5 A 1 1 0 0 0 10.5 11.5'
];
```
```css
.board-svg .rail-arc   {fill:none; stroke:var(--railway);    stroke-width:5px; vector-effect:non-scaling-stroke}
.board-svg .rail-arc-hi{fill:none; stroke:var(--railway-hi); stroke-width:1px; vector-effect:non-scaling-stroke}
```

> **⚠️ sweep-flag 是唯一易错点**：端点、弧长、包围盒都对得上，sweep 写反只会让弧朝九宫格**里侧**鼓，肉眼不细看发现不了。用 `path.getPointAtLength(len/2)` 取弧中点、断言它落在预期象限（`圆心 + R·(±√2/2, ±√2/2)`）才是可靠验法；四条弧的 sweep 依次为 **[0,0,1,0]**。
> **⚠️ 解析 `d` 时 A 后面是 7 个参数**：`rx ry x-axis-rotation large-arc sweep x y`。少写一个（例如漏掉 large-arc）正则永远匹配不上，会误报成「4 条弧全都不合格」——本次就是踩了这个坑。
> **⚠️ `getTotalLength()` / `getBBox()` 返回的是 SVG 用户单位**（这里 1 单位 = 1 格），不是屏幕像素。R=1 格 → 弧长 `π/2 ≈ 1.5708`、包围盒 `1×1`。别拿 `cellSize` 去乘。

**相关旧坑仍然有效**：`.cell.camp`/`.cell.hq` 的 `background:xxx !important` 简写会连 `background-image` 一起重置（改用 `background-color`）；`.cell.empty{background:transparent}` 正好清掉背景图，四角空白区无线，与 QQ 一致。

### 棋子（浅色底 + 深色描边 + 深色字）

```css
.piece{width:30px; height:25px; border-radius:3px; font-size:15px; font-weight:700;
       border:1.5px solid; box-shadow:0 1px 2px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.6);
       text-shadow:0 1px 0 rgba(255,255,255,.4);}   /* 文字是深色，所以阴影用白 */
.piece.green {background:linear-gradient(180deg,#dcefa4,#c2db7c); border-color:#5a7a20; color:#3d5710}
.piece.yellow{background:linear-gradient(180deg,#fddc9a,#f5c364); border-color:#c0720f; color:#8a4c05}
.piece.blue  {background:linear-gradient(180deg,#eef6fc,#d3e6f3); border-color:#2a72a4; color:#14517c}
.piece.purple{background:linear-gradient(180deg,#f1e4f7,#dfcbe9); border-color:#7b3f9e; color:#5a2b7d}
```
旧的「白字 + `linear-gradient(135deg,#43a047,#2e7d32)` 彩底」要整组替换掉。

### 行营 / 大本营 / 兵站

- 行营 `.cell.camp::after`：`21×21` 空心圆环 `border:3px solid var(--camp-ring)`，**去掉旧规则的黄底 + 6px 小圆点**（还要去掉 `.cell.camp{background:… !important; border-radius:50%; border:2px solid #F9A825}`）。
- 大本营 `.cell.hq`：淡色块 + `box-shadow:inset 0 0 0 2px rgba(230,206,140,.42)` 内描边；角标 ★ 保留但调淡。
- 兵站 `.cell.station`：**2026-09-15 晚改为「空心圆角方环」**，与行营的空心圆环语言统一（旧版是淡蓝方块 + ★ 字符，已废弃）：

  ```css
  .cell.station{background-color:transparent}
  .cell.station::after{content:""; position:absolute; inset:23%; border-radius:4px;
                       border:2px solid var(--station-ring); box-shadow:0 0 0 1px rgba(0,0,0,.14)}
  .cell.station.occupied::after{display:none}   /* 有子时隐藏，别和棋子叠 */
  ```

  变量 `--station-ring`：浅色 `rgba(212,232,246,.9)`、深色 `rgba(160,196,216,.82)`。深色主题另需 `html.theme-dark .cell.station{background-color:transparent}` 兜底。**不要用 `border` 直接画在 `.cell` 上**（会撑开格子），一律走 `::after` + `inset`。

### 其他必须同步的点

- **坐标表头**（`.col-header/.row-header`）在军绿底上要改浅色：`var(--board-coord)` + 深色 text-shadow。
- **玩家名条 `.corner-label`**：字色是 JS 内联的 `PC_COLORS[c]`（深色），所以**底必须保持浅色**；深色主题下也保持浅底（`rgba(232,240,214,.94)`），改深底会让绿家 `#1e8449` 几乎看不见。
- **`--highlight-to` 从 `#1a1a1a` 改 `#ffd54f`**，否则终点框在军绿底上完全不可见；`--highlight-from` 提到 `#ff4d3d`。
- **阵地区分**：QQ 是统一下盘（靠棋子颜色区分），我们把 `--*-bg` 降成 `rgba(…,.11)` 的极淡色晕，既能分区又不破坏「整片绿」的观感。
- **深色主题**：在 `html.theme-dark{}` 里覆盖 `--board-bg:#28301c / --board-bg-2:#1c2314 / --railway:#8fb0c4 / --grid-line / --camp-ring / --station-ring / --hq-fill / --hq-mark / --board-coord`；棋子单独覆盖成深一档的浅底（绿 `#93ad5a→#78923f` 等），否则深底上过亮发白。同时删掉旧的 `html.theme-dark .cell{border-color:…}` 这类按旧 border 写的规则。
- **全屏弹窗同步放大**：弹窗注入 CSS 里 `:root{--cell-size:46px}`（原 40px）+ `.piece{width:43px;height:36px;font-size:21px;border-radius:4px;border-width:2px}` + `.move-arrow{font-size:26px}` `.corner-label{font-size:15px;line-height:21px}`。**只改 `--cell-size` 不改棋子尺寸，弹窗里棋子会明显偏小。**



## 复盘回放 · 全屏窗口（实现范式，2026-09-10 引入）

**核心思路：不重复实现渲染，只做「克隆 + 代理」。** 用 `window.open('', 'junqiReplay', 'width=1920,height=1080,left=…,top=…,menubar=no,toolbar=no,…')` 开空白子窗（`screen.width/height` 居中，被拦截时 `alert` 提示），然后：

1. **复制主窗全部样式表**：`document.querySelectorAll('style')` 逐个把 `textContent` 拼起来，注入子窗 `<style>`；
2. **克隆「复盘回放」卡片**：`document.querySelector('.card.area-board').outerHTML`，塞进子窗的 `<div id="popupCard">`；
3. **子窗逻辑代理回主窗**：`var op = window.opener`，子窗只做两件事——① 把所有控件事件转成 `op.gotoStep(n)` / `op.toggleSound()` / 改 `op.playSpeed` / 派发 `op.document.getElementById('viewSelect')` 的 `change` 事件；② `sync()` 从 `op.document` 把 `#boardGrid` 的 `innerHTML`、`#stepNo`、`#moveDetail`、`#turnStrip`、`#viewHint`、`.board-legend`、`#viewSelect.value`、`#stepSlider` 拷回子窗。

**必须处理的细节**
- 克隆前先清掉子窗卡片上的内联事件：`card.querySelectorAll('[onclick]')` 全部 `removeAttribute('onclick')`，再自己 `addEventListener`（否则 `onclick="toggleSound()"` 在子窗上下文里找不到主窗变量）。
- 子窗里要 **删掉「↗ 全屏窗口」按钮本身**：`var hb = card.querySelector('h2 button'); if (hb) hb.remove();`。
- 子窗局部覆盖样式（放在主样式表之后）：`:root{--cell-size:40px}`（主窗 32px，全屏要放大）、`#app{max-width:none;width:100%}`、`.piece{width:30px;height:30px;font-size:15px}`、`.move-arrow{font-size:24px}`、`.corner-label{font-size:13px}`。
- **主题继承**：拼 HTML 时按主窗给子窗 `<html>` 加 `class="theme-dark"`；`applyTheme()` 里再顺带 `replayWin.document.documentElement.classList.toggle('theme-dark', dark)` 做实时同步（否则弹窗永远停在打开那一刻的主题）。对应地，主样式表里要有 `html.theme-dark .popup-bar .t` / `.popup-tip` 覆盖（这些规则会被复制进子窗）。
- **快捷键**：`W` 上一步 / `S` 下一步 / `Space` 播放暂停 / `C` 或 `Esc` 关闭，`document.addEventListener('keydown', …)`。
- 子窗 `beforeunload` 里 `op.replayWin = null`，父窗 `beforeunload` 也清一次，避免留下悬空引用。已开子窗时二次点击只 `focus()` 不重写。
- **不要用 `page.waitForEvent('popup')` 做验证**：本机 puppeteer-core **25.7.0 已没有 `Page.waitForEvent`**（报 `page.waitForEvent is not a function`）。改用 `new Promise(res => page.once('popup', res))` 配 `page.click(...)`，并给启动参数加 `--disable-popup-blocking`。
- 子窗 `#boardGrid .cell` 是 **289 格**（17×17），不是 400；断言时拿主窗的 `.cell` 数做对照更稳。


## 复盘回放 · 明棋 / 暗棋（盖牌，2026-09-17 引入）

**需求**：点一次该方（颜色）任意棋子 → 该方**全部**变暗棋（盖牌）；再点该方任意棋子 → 恢复明棋。

### 实现四要点（少一条就会出问题）

```javascript
var hiddenSides = { '绿':false, '黄':false, '蓝':false, '紫':false };   // 状态按「棋子颜色」= 所属方
function applyHiddenState(){                     // 只切 class，不重渲染
  var ps = document.querySelectorAll('#boardGrid .piece');
  for (var i=0;i<ps.length;i++){
    var c = ps[i].getAttribute('data-color');
    if (hiddenSides[c]) ps[i].classList.add('hidden'); else ps[i].classList.remove('hidden');
  }
}
function toggleSideHidden(color){
  if (!color || !COLOR_INFO[color]) return false;
  hiddenSides[color] = !hiddenSides[color]; applyHiddenState(); return hiddenSides[color];
}
```

1. **状态挂在模块变量上**，不能挂在 DOM 上：`gotoStep` 每步重建棋子、视角切换整体重排，
   只有模块变量能跨重渲染存活。`renderBoard` 建棋子时补 `pc.setAttribute('data-color', o.color)`
   （回溯所属方）与 `if (hiddenSides[o.color]) pc.classList.add('hidden')`（恢复盖牌态）。
2. **事件必须委托到 `#boardGrid`**：棋子是每步重建的，直接绑在棋子上的 listener 会随 `innerHTML` 清空一起失效。
   处理函数从 `e.target` 向上回溯到 `.piece`（点到格子空白处时不要有反应）。
3. **切换只改 class、不重渲染**：否则当步的起点/终点高亮与行棋箭头会被冲掉。
4. **全屏回放窗口是克隆 DOM**，监听要在 `popupJs` 里单独绑，并代理回主窗口再 `sync()`：
   ```javascript
   var bgd = document.getElementById('boardGrid');
   if (bgd) bgd.addEventListener('click', function(e){ ... var c = el.getAttribute('data-color');
     if (c && op.toggleSideHidden){ op.toggleSideHidden(c); sync(); } });
   ```

### 盖牌样式：遮字 + 保色 + 纯色牌背

```css
.piece.hidden{color:transparent; text-shadow:none}
/* 四方各一套「压深」纯色底（浅色） + 深色主题再压一档。牌背就是一块素色，无花纹无徽记 */
.piece.hidden.green{background:#84a44a; border-color:#3f5a12}
html.theme-dark .piece.hidden.green{background:#526c30; border-color:#2b3f0a}
```

- **牌背 = 单一实色，不要任何装饰**（2026-09-17 用户明确要求：「牌背纯色，不需要"居中白色菱形"」）。
  初版曾用 `::after` 画居中白菱形徽记，已被要求去掉 —— **不要再加回来**，也不要换成渐变色。
- **只遮字、不换配色**：盖牌后仍要一眼看出「这是哪一方」，所以用该方主色**压深**的纯色实底，
  而不是统一的中性牌背（统一牌背会丢掉归属辨识）。
- 六位 hex 色值 = 原渐变两端的**中点**，这样改纯色后明暗对比与旧版一致：
  浅色 green `#84a44a` / yellow `#cc9833` / blue `#72a0c1` / purple `#9d76b4`；
  深色 green `#526c30` / yellow `#8d681e` / blue `#4c7992` / purple `#6d507f`。
- 用 `background` **简写**写 hex（不要用 `background-image`），这样 `getComputedStyle(el).backgroundImage === 'none'`
  可被直接断言 —— 纯色/渐变一目了然。
- 文字用 `color:transparent` 遮住、**DOM 文本保留** —— 切回明棋时不用重渲染。
- 弹窗（全屏回放）**不要再写 `.piece.hidden` 覆盖规则**：弹窗用 `'<style>' + css + '</style>'` 把主窗口全部
  `<style>` 搬过去，纯色底自动继承；弹窗那段 `<style>` 只保留尺寸覆盖（`.piece{width:43px;height:36px}`）。
  新增任何盖牌样式，**只改主样式表一处**。
- 图例加一条操作提示：`▨ 点棋子＝该方盖牌 / 再点明棋`（`renderLegend()` 会整段重写图例，提示要写进它的输出里，不能只写在静态 HTML）。

### ⚠️ 这块踩过的坑（务必看）

1. **CSS 特异性：深色主题会压过 `.piece.hidden{color:transparent}`**。深色主题的棋子文字色写作
   `html.theme-dark .piece.green{color:#0f1c04}`（特异性 **0,3,1**），而 `.piece.hidden{color:transparent}` 只有 **0,2,0**
   —— 结果浅色下正常、**深色下盖牌仍能透出淡淡的兵种字**。必须补 `html.theme-dark .piece.hidden{color:transparent}`（同 0,3,1，靠源码顺序取胜）。
   **这类「浅色对、深色错」的问题静态断言与浅色截图都看不出来，只有实拍深色主题才会暴露。**
2. **（已废弃，留给后人）伪元素尺寸必须用整数像素**：曾用 `::after` 画菱形徽记，`border-width:2.5px`
   在 1× 屏上被 `getComputedStyle` 吸附成 `2px`，测试期望值对不上。现在盖牌没有伪元素了；
   将来若再加任何 `::after`/`::before` 装饰，仍按整数像素写。
3. **断言不要写死「该方 25 枚」**：行棋过程会吃子，在场棋子数一路在变（第 5 步就已经是 24）。
   正确口径是「该方**在场**棋子是否**全部**盖牌」→ `hid === tot` / `hid === 0`，写成 `'all'|'none'|'partial'` 三态。
4. **弹窗按 `C` 关闭时 puppeteer 可能抛 `TargetCloseError`**：`keydown` 里 `window.close()` 是**同步生效**的，
   CDP 的 `keyUp` 往往来不及派发 → 报 `Protocol error (Input.dispatchKeyEvent): Target closed`。
   这本身就是「窗口确实关掉了」的证据，测试里要 `try{ await popup.keyboard.press('c') }catch(e){}` 再断言 `popup.isClosed()`；
   若快捷键失效则 `press` 不抛错、`isClosed()` 为 false，断言照样失败 —— 判定力度不变。
   （注意：这条只在**脚本里加了额外交互**后才会触发，属纯测试侧竞态，与产品无关。）

## 复盘回放 · 音效系统（合成音 → 内嵌 WAV 采样，2026-09-16 引入）

**两个文件都已落地**：`index.html` 2026-09-16 上午先行实现；`index_task2.html` 同日移植（音效段直接用脚本从 `index.html` **整段提取**，保证字节级一致，顺带把 `event.cmdr`、`evKind`、`gotoStep` 派发、`initSound()` 一起带过去）。**移植时不要手抄 base64** —— 写成 `src_idx[src_idx.index('// ================ 音效系统（采样音效'):…]` 切片再插入，87KB 的数据靠肉眼复制必错。校验方式：base64 解码后与源 wav **逐字节比对**（`base64.b64decode(...) == open(wav,'rb').read()`），6 条全一致才算过。

**6 个 wav 以 base64 直接写在主脚本里**（`var SFX_B64 = {move:'…', eat:'…', …}`），保持单文件零依赖离线可用：**+87KB**（`index.html` 363KB → 449KB；`index_task2.html` 291KB → 377KB）。

**⚠️ 2026-09-16 晚更新：`bounce` 换成独立音频**

用户替换了 `撞子被反吃.wav`（**5770 字节 / 11025Hz / 8bit / 1ch / 0.518s**，MD5 `4cae22cb0a87…`），不再是 `吃子.wav` 的副本。换音频要同步做三件事，缺一不可：

1. `SFX_B64.bounce` 换新（base64 从 8792 → **7696** 字符）。**替换时必须带上 `bounce: ` 前缀做 `rep()`** —— 裸 base64 串在块里出现两次（eat 与 bounce 原本逐字节相同），直接 replace 会连 eat 一起改掉。
2. **`SFX_MAP.mine` 从 `'blast'` 改派到 `'bounce'`** —— 「触雷」与「主动撞子被反吃」同属「自己撞上去被反吃」，本就不该用「兑子被炸」。改前代码与文档口径不一致（文档一直写触雷归 bounce），这次一并对齐。
3. `SFX_VOL.bounce` 0.60 → **0.65**（新音频 RMS 0.239 vs eat 0.263，按等响度对齐）。

**`index.html` 与 `index_task2.html` 都要改**，同一条断言式脚本跑两遍。改完必须双重校验：① 6 段 base64 解码后与源 wav **逐字节一致**；② **`eat` 与 `bounce` 不再是同一段**（这条要钉进测试，否则将来又会退回共用）。

**映射表（用户指定口径，勿改语义）**

| 采样键 | 源文件 | 触发场景（`res.type` / 条件） |
|---|---|---|
| `move` | 移动走子.wav | 普通行棋 `move` |
| `eat` | 吃子.wav | 吃子 / 挖雷 `eat`·`dig` |
| `bounce` | 撞子被反吃.wav | 主动撞击被反吃 `killed` / **触雷 `mine`** / 反弹 `bounce` |
| `cmdr` | 司令阵亡亮旗.wav | **司令阵亡**（`res.event.cmdr === true`） |
| `blast` | 兑子被炸.wav | 炸弹主动炸子 / 被动中炸 / 同级别兑子同尽（`both`·`bomb`） |
| `giveup` | 扛旗投降自杀.wav | 扛旗 `flag`；自杀战败 / 判负 / 退出（事件步 `evKind==='defeat'`） |
| （不占文件） | — | 超时提示 `pass` —— 不在用户清单内，**保留原双音 660/440Hz 兜底**（`playBeep()`，主脚本里唯一残留的 `createOscillator`） |

**⚠️ 源文件事实（2026-09-16 实测）**
- **`吃子.wav` 与 `撞子被反吃.wav` 曾 MD5 完全相同**（`7de6b354bef0a51cc325a985a201e572`，均 6592 字节）→ 「吃子」和「被反吃」曾听起来一模一样。**2026-09-16 晚用户已替换后者**（5770 字节，MD5 `4cae22cb…`），现已能区分。⚠️ 教训：用户反馈「两个音效听不出差别」时，**先对源 wav 做 MD5/长度比对**再怀疑映射 —— 三个字的结论比翻代码快得多。
- 原生格式差异很大：move 11025Hz/16bit/1ch、eat 8000Hz/16bit/2ch、**bounce 11025Hz/8bit/1ch**、cmdr 11025Hz/8bit/1ch、blast 11000Hz/8bit/1ch、giveup 22050Hz/16bit/1ch。**8bit 无符号 PCM 与非 44.1k 采样率都能被 `decodeAudioData` 正常解码，不用预转码。**
- **解码后 `AudioBuffer.sampleRate` 一律被重采样成 AudioContext 的采样率**（本机 48000）。测试里**绝不要断言原生采样率**，用 `duration`（6 条两两不同）+ `numberOfChannels` 做指纹（2026-09-16 起 eat 0.2046s/2ch、bounce 0.518s/1ch，可彻底分辨）。

**实现要点**
- 单一 `sfxCtx` + 一次性 `decodeAudioData` 全部 6 条进 `sfxBuf`；`initSound()` 在 DOMContentLoaded 里调用（避免首次播放延迟）。
- `document.addEventListener('pointerdown' | 'keydown', unlockSound)` —— 浏览器要求用户手势才能 `resume()`。
- 每次播放新建 `createBufferSource()`（**可叠加**，连续点不会互相打断），经 per-key 增益 `SFX_VOL` 接 destination。单条增益按源文件峰值 0.87~1.0 定为 0.55~0.85，`move` 因是 39ms 短点击（RMS 仅 0.11）给到 0.85；`bounce` 自 2026-09-16 换新音频起为 **0.65**（按等响度对齐 eat）。
- 保留原 `playSound(type)` 的**全部类型名**（`move/eat/dig/killed/both/bomb/mine/flag/giveup/pass`），调用点一处未改；只新增 `cmdr` 类型。

**⚠️「司令阵亡」怎么判（本轮最易做错的地方）**
不要在播放派发处用事件文案正则 —— 「司令」既可能是凶手也可能是受害者（`绿方司令斩杀黄方军长` vs `黄方司令被军长反吃`），按 `indexOf('司令')` 判必然误报。正确做法是在 `resolveMove()` 各分支给 `event` 打结构化标记 `cmdr:true`（共 4 处）：
- `eat` 分支末尾 `if (dpiece==='司令') event.cmdr = true;` —— **必须放在那条 `if (va < v) event = {cat:'失着',…}` 覆盖语句之后**，否则标记会被随后的赋值覆盖丢掉。
- `killed` 分支：`if (apiece==='司令') …`（我方司令撞子被反吃）
- `both` 分支末尾：`if (apiece==='司令' || dpiece==='司令') …`（同尽 / 中炸 / 炸杀 都走这里）
- `mine` 分支：`if (apiece==='司令') …`（司令触雷）
- 播放派发用 `if (res.event && res.event.cmdr) playSound('cmdr');` 放**最前**（优先于吃子/同尽音）。
- 注意 `炸杀` 分支实际永不涉及司令：`both` 末尾有一条 `if (dpiece!=='炸弹' && v>va) event = 失着` 覆盖，且炸杀只在「炸掉价值 ≤ 炸弹(35) 的子」时成立。「司令被炸弹炸掉」的 `event.cat` 是 **`失着`**（cmdr 仍正确置位）。

**⚠️ 事件步（超时/战败/退出）必须用结构化字段判，不能用文案**
`res.event` 由 `analyze()` 内联生成（不经 resolve），需在生成 `evStep` 时补 `evKind: (isTimeout&&!isDefeatEvent)?'timeout':'defeat'`。原因：
- 超时未判负的 `desc` 是 **`'超时（累计第 N 次，尚未判负）'` —— 里面含「判负」二字**！按文案 `indexOf('判负')` 判会把超时提示误判成战败音。派发时必须排除「尚未判负」或直接读 `evKind`。
- 旧代码先判「超时」再判「退出/判负」，导致 **`'超时判负'`（累计第 5 次）走了提示音而不是战败音**；本轮已改为**先判战败**（`战败`/`退出`/`判负` → giveup，再 `超时` → beep）。

## index_task2.html 分支（设计画布导出基线，2026-09-15 建立）

`index_task2.html` 是**另一个独立文件**，不是 `index.html` 的副本：它是从设计画布重新导出的版本（**每个标签的 `data-page-node-id` 与 index.html 全不同**），内容基线停在 2026-09-10 上午。两个文件要分别维护。

- **不可逐节点对齐**：node-id 全不同 → 只能**按功能块移植**（CSS 区块、卡片 HTML 区块、JS 函数），不要试图 diff 合并或整文件覆盖。
- **功能分类口径**（用户需求里用 A/B/C/D 指代，沿用）：
  - **A 布局结构重构** = 12 列精确 grid（`.area-info 1/3` `.area-board 3/10` `.area-moves 10/13` `.area-stat 1/8` `.area-eval 8/13`）、胜负手 TOP3 并入统计卡（`.clutch-section`）、子力净值曲线并入统计卡（`.curve-section`）、`#valueCurve svg{width:100%}`。
  - **B 竞技技术积分整套** = `computeTechScore` 引擎 / `renderTechScore` / `techCard` / `techRuleRows` / 称号徽章 `.mvtag.tech` / `.mv-has-title` / 名次奖牌。**独立性最强，可与 A/C/D 分开决定是否移植。**
  - **C 胜负判定重做** = `teamSplit()` + `getWinTeam()` 按行棋结果判定 + 玩家卡胜负/和标签 + 对阵头分队显示。
  - **D UI/UX 增强** = 黑金深色主题 + 月亮/太阳切换、图表 CSS 变量着色、简介折叠、`#btnBack` primary 样式、`moveList` 内边距微调。
  - **E 复盘回放全屏窗口** = `#boardCard h2` 的「↗ 全屏窗口」按钮 + `openReplayWindow/closeReplayWindow` 整块 + 弹窗深色覆盖 CSS。**与 B 完全独立**，弹窗靠克隆 `.card.area-board` + 代理回主窗，不依赖技术积分。（口径见上一节「复盘回放 · 全屏窗口」）
  - **F QQ 军棋风格棋盘** = 军绿底板 + 格心网格线 + 横长方形浅底棋子 + 空心圆环行营 + 亮金终点框 + 深色主题/弹窗尺寸同步。**棋盘渲染 JS（`buildBoardGrid` / `renderBoard`）不动类名与 DOM 结构**，但铁路已从「按格 CSS 渐变」升级为 **SVG 叠加层**（2026-09-15 下午，见「棋盘视觉规格」一节）——移植时除了 `/* 17x17 棋盘 */ … .corner-label{}` 区间与 `:root/html.theme-dark` 变量，还要带上 `.board-svg` 系列 CSS、`RAIL_LINES` 线表 + `isRailway`/`railLinked` 双函数、`buildBoardSvg()`、`buildBoardGrid` 首行注入 SVG、中央区 `plain` 类与其 CSS，以及 `.board-grid{position:relative}`。
  - **F2 铁路网闭合 + 行营米字形斜线**（2026-09-15 深夜）= SVG 叠加层绘制（`buildBoardSvg()`）+ `RAIL_LINES` 线表（14 条线）+ `railLinked()` + 中央 3×3 九宫格 + 四家 5×5 铁路环 + 64 条 45° 米字形斜线 + `.cell.plain` 中央区去细线 + `.board-svg` 绝对定位。当前实测 **100 段铁路 / 85 个铁路点 / 64 条斜线 / 整网连通**。**纯前端绘制，不涉及数据/规则，可与任何分支独立取用。**
- **移植后必须清掉 B 的联带依赖**：`techScore` 全局变量、`startAnalyze` 里的 `computeTechScore/renderTechScore` 调用、`renderMoveList` 的徽章拼接、`techCard` 显示/隐藏、`.tech-grid` 媒体查询片段。`applyTheme()` 里同步子窗口的那段用了 `replayWin`，若目标文件没有回放弹窗功能，要写成 `typeof replayWin !== 'undefined'` 守卫（放在 `try{}` 里也能吞掉 ReferenceError，但显式守卫更清晰）。
- **署名为分支差异项**：index.html 用「暴暴寒（7z）｜规则赋能/优化：姜朕熙」，task2 保持原文「热心市民小寒（7z）」（页头 badge 与页脚两处）。移植时**不要顺手改署名**，除非用户明确要求。
- **2026-09-15 已完成的移植**：① A + C + D 全量（26 处断言式替换）；② **复盘回放「↗ 全屏窗口」**（3 处：h2 按钮 / 弹窗深色覆盖 CSS / 弹窗 JS 整块照搬）；③ **QQ 风格棋盘**（纯 CSS 换皮）；④ **铁路网闭合 + 行营斜线**（4 处：删三条按格渐变铁路规则并换 `.board-svg` 样式 / 删 `--rw-*`+`--rwh-*` 变量 / `isRailway` 重写 + 新增 `buildBoardSvg()` / `buildBoardGrid` 注入 SVG 并删 `railway-h|v` 类，另加 `.board-grid{position:relative}`）；⑤ **棋盘铁路口径收窄**（用户两轮纠正：中央区 5×5 → **3×3 九宫格**；每家**只保留第 1 排与第 5 排**铁路，**底线第 6 排剔除**）——改动落在 `isRailway()` 早返回分支、`EXTRA_RAILWAY` 重排、`.cell.station` 改空心圆角方环 + `--station-ring` 变量（7 处）；⑥ **铁路拓扑线表化 + 行营米字形 + 中央区去细线**（用户第三轮三项需求：删除「军长 → 中央铁路」多余连线 / 中央区除铁道线外不要细线 / 每营米字形斜线）——`EXTRA_RAILWAY` + `isRailway` **整体替换为 `RAIL_LINES` 线表 + 新增 `railLinked()`**（新增判段层）、`buildBoardSvg` 线段生成改用 `railLinked`、行营斜线终点放开到任意行棋点并补 `.cell.plain` 类与 `.cell.plain{background-image:none}`（5 处断言式替换）；⑦ **中央九宫格四角弧形铁道**（用户第四轮需求：「师长和司令之间这个角用一条弧行铁道线连接」）——新增 `RAIL_ARCS` 路径表 + `.rail-arc`/`.rail-arc-hi` 样式 + `buildBoardSvg` 追加 `<g class="arc-layer">`（3 处断言式替换）。B 未移植。**以上是 index → task2 方向；反向 task2 → index 见下节「反向迁移记录：task2 → index.html」。**
  - 全屏窗口的 3 处落点：`<h2>` 内加 `<button class="btn primary small" onclick="openReplayWindow()" style="margin-left:auto">↗ 全屏窗口</button>`（`.card h2` 本就是 flex，`margin-left:auto` 即可右靠）；主样式表末尾补 `html.theme-dark .popup-bar .t{color:var(--accent2)}` 与 `html.theme-dark .popup-tip{color:var(--muted)}`（这两条会被复制进子窗口）；`openReplayWindow/closeReplayWindow` 整块（131 行）**用脚本从 index.html 原样切片搬过去**，别手抄——位置放在 `function renderValTable(){` 之前，与 index.html 一致。
  - task2 缺 B 时 `applyTheme()` 里同步子窗口那段保持 `typeof replayWin !== 'undefined' && replayWin && …` 的 `typeof` 守卫；现在 task2 已有 `var replayWin = null`（var 提升），守卫照样成立，不必回改成裸引用。
  - task2 的 `#moveDetail / #viewSelect / #viewHint / .board-legend / .speed[data-s] / toggleSound / playSpeed / currentStep / gotoStep` 全部与 index.html 同名同构，弹窗的代理逻辑可直接复用，无需改名适配。

### 双文件同步记录（index.html 与 index_task2.html 必须保持一致）

两个 HTML 的棋盘/回放代码**结构完全同构**，凡涉及棋盘的改动一律**一份断言式脚本跑两遍**，`node --check` 最长 script 块后同时落盘。已同步的项目：棋盘与铁路/弧线（2026-09-15）、采样音效（2026-09-16）、**明棋/暗棋（盖牌，2026-09-17）**、**页脚站点统计（51.la，2026-09-17）**。

校验两文件是否真的一致：`grep -o "hiddenSides = {.*}" index*.html | md5` 之类的片段哈希，几秒就能比完。

**备份命名**：`<file>.bak_pre_<主题>_<YYYYMMDD>`（如 `index_task2.html.bak_pre_hidedark_20260917`）。

### 页脚结构：版权 → 站点统计 → 备案（固定顺序）

两个文件的 `<footer>` 都是 **4 行块级 div、`text-align:center`** 的竖排结构，顺序不可乱：

```
<footer data-page-node-id="...">
  <div>QQ四国军棋复盘分析器 · 本地运行 · 棋谱数据不离开您的浏览器</div>
  <div>© 2026 ...（署名行：两文件不同，index_task2 = 热心市民小寒（7z）；index = 暴暴寒（7z） | 规则赋能/优化：姜朕熙（B站：老姜甄鉴））</div>
  <div><a target="_blank" title="51la网站统计" href="https://v6.51.la/land/3QtlPjL6nKXxNzgV"><img src="https://sdk.51.la/icon/1-1.png"></a></div>
  <script charset="UTF-8" id="LA_COLLECT" src="https://sdk.51.la/js-sdk-pro.min.js"></script>
  <script>if(window.LA&&LA.init)LA.init({id:"3QtlPjL6nKXxNzgV",ck:"3QtlPjL6nKXxNzgV"})</script>
  <div data-page-node-id="wZe44C3uRs2urQOTHriGnK">   <!-- index.html 里是 IMmNB9zHQBub9ZzEBqituu -->
    赣ICP备15001421号 · 赣公网安备36100002000755号（国徽/警徽都是 base64 内嵌 PNG）
  </div>
</footer>
```

- **站点统计（51.la）固定放在「备案信息上方」**（2026-09-17 用户要求），即版权行与备案 div 之间，**独立一行**。
  整段统计 = 图标 `<a>` + `LA_COLLECT` + `LA.init(...)` 三件套，缺任一件则「有图标但无数据」或「有数据但无入口」。
- **51.la 标识（跨全部 4 个页面共用，别写错）**：站点 id / ck 都是 `3QtlPjL6nKXxNzgV`，
  后台入口 `https://v6.51.la/land/3QtlPjL6nKXxNzgV`，图标 `https://sdk.51.la/icon/1-1.png`（**72×15** PNG）。
- **覆盖 4 个页面**：`index_task2.html`、`index.html`（统计在备案上方）；
  `../四国军棋布局转换器.html`（同上）；`../junqi_replay.html`（**该页 footer 无备案信息**，统计放页脚末尾 —— 用户已知悉并接受）。
- 备案图标的国徽/警徽是 **base64 内嵌**（离线可显示）；51.la 图标与 SDK 是**外链**
  —— 离线时会空白/不加载，这是故意的（统计本来只在线上有意义）。
- ⚠️ **署名行两个文件本来就不一样，不要「统一」掉**（用户明确说过页脚署名保持原样）。
- 页脚无需额外 CSS：`footer{text-align:center}` + `footer img{vertical-align:-3px;margin:0 3px}` 已够用
  （`index*.html` 本来就有这条；另两页需要时补 `footer img{vertical-align:middle; margin:0 3px}`）。

**加统计时踩过的三个坑（务必先看）**

1. **协议相对 URL `//sdk.51.la/…` 在 `file://` 下会糊成 `file://sdk.51.la/…`** → 加载失败 → `LA is not defined`
   直接抛 pageerror。`四国军棋布局转换器.html` 原本就是这么写的（本地打开一直报错）。
   **一律写显式 `https://sdk.51.la/js-sdk-pro.min.js`**；`LA.init` 外面套 `if(window.LA&&LA.init)` 兜底。
2. **`junqi_replay.html` 是 `444` 只读文件**：`shutil.copy2` / `open(...,'w')` 都报 `PermissionError`。
   正确姿势 —— 读 → `os.chmod(0o644)` → 备份 + 写入 → **`finally` 里 `os.chmod` 恢复原权限**。
   ⚠️ 注意 `touch` 能成功不代表可写（它只改时间戳，靠的是目录权限）。
   ⚠️ 备份名撞车也会失败：`copy2` 覆盖已存在的 444 备份同样 `EACCES`，备份名带上 `%H%M%S` 更稳。
3. **`LA.init` 要等 `LA_COLLECT` 执行完**：两段 script 必须紧邻且都不带 `async`/`defer`，靠文档顺序保证。
   放在 `<footer>` 内完全没问题（`<script>` 是 `display:none`，不影响页脚排版）。
4. 插入/巡检脚本：`/tmp/ins_stat51la.py` + `/tmp/ins_stat51la_step2.py` + `/tmp/ins_jr_stat.py`（断言式插入）；
   实拍 + 几何断言用 `.workbuddy/tests/shoot_footer_stat.js`（见测试台条目）。


### 反向迁移记录：task2 → index.html「复盘回放」棋盘（2026-09-15 15:38 完成）

**用户需求**：「参照 `index_task2.html`，修改"复盘回放"相关内容。」——即把 task2 里已迭代成熟的 QQ 风格棋盘搬到 `index.html`。

**第一步永远是 `diff -u index.html index_task2.html` 逐块分类**（本次 1546 行）。把差异硬性分成两类，只搬第二类：

| 类别 | 本次实例 | 处置 |
|---|---|---|
| **不属于「复盘回放」** | 删除竞技技术积分整块、`techCard` 相关、主题切换函数位置调整、署名文字、`data-page-node-id` 变化 | **一律不迁移**（index.html 已积累技术积分/奖牌/称号徽章功能，覆盖会回退） |
| **属于「复盘回放」** | 棋盘配色变量、棋盘 CSS（军绿底板/格心公路网/铁路 SVG/行营环/兵站环/大本营/QQ 横牌棋子/角落标签）、`RAIL_LINES`+`RAIL_ARCS`+`isRailway`/`railLinked`+`buildBoardSvg()`、`buildBoardGrid()` 类名产出、全屏弹窗尺寸覆盖 | **全量迁移** |

**实际落点（6 处）**
1. `:root` 配色变量整体替换（`--board-bg/-2`、`--railway`、`--railway-hi`、`--grid-line`、`--camp-ring`、`--station-ring`、`--hq-*`、`--board-coord`、四色 `--*-bg/--*-piece`、`--highlight-from/to`）。
2. 棋盘主样式块整体重写＝`/* 17x17 棋盘 */` … `.corner-label{}` 区间（含 `.board-svg` 系列）。
3. `html.theme-dark` 内棋盘变量覆盖。
4. 深色主题棋盘覆盖段重写（删掉 `.cell.camp/.cell.hq/.cell.station` 的 `border-color` 旧覆盖 —— 新样式改用 `::after` 画环，不再用 border）。
5. `EXTRA_RAILWAY` + `isRailway` **整体替换**为 `RAIL_LINES` 线表 + `railLinked()` + `RAIL_ARCS` + `buildBoardSvg()`。
6. `buildBoardGrid()` 首行注入 `buildBoardSvg()`，并把 `railway-h/railway-v` 判定换成中央 5×5 的 `plain` 类。
   另加全屏弹窗尺寸覆盖：`:root{--cell-size:46px}` + `.piece{width:43px;height:36px;font-size:21px;border-radius:4px;border-width:2px}` + `.move-arrow{font-size:26px}` + `.path-arrow{font-size:17px}` + `.corner-label{font-size:15px;line-height:21px}`。

**⚠️ 语义陷阱：`isRailway` ≠ `railLinked`（最容易写错测试期望）**
- `isRailway(r,c)` 判的是「该**格**是否落在铁路网上」。**交叉格会被纵/横贯通线穿透 → 仍为 `true`**。所以行 7/9 与列 7/9 上的交叉格 `isRailway` 是 `true`，不是 `false`。
- `railLinked(r,c,r2,c2)` 判的是「两相邻格心之间**是否真有一段铁路线段**」（必须落在**同一条** `RAIL_LINES` 上且 `hi-lo===1`）。「行 7/9 与列 7/9 上零线段」这句话是针对**线段**说的，要用 `railLinked` 断言（`railLinked(7,1,7,2)===false`），不是针对格点。
- 实测参考值：`[isRailway(7,c) for c in 4..12] = [f,t,t,f,t,f,t,t,f]`；列 7/列 9 的格点 `[t,t,f,t,t, t,t,f,t,t]`（只有行 7/9 与列 7/9 的**交点**是 `false`）。

**⚠️ 桩 DOM 三大陷阱（本轮全中，导致「棋子数 = 0」的假故障）**
1. `classList.contains` 必须实现（`renderBoard` 里 `cell.classList.contains('station')` 会抛错）。最省事：`{add(){},remove(){},toggle(){},contains(){return false}}`。
2. **`renderBoard()` 第 3 行 `var cells = document.querySelectorAll('#boardGrid .cell'); if (!cells||!cells.length) return;`** —— 桩里 `querySelectorAll` 若恒返回 `[]`，函数直接 early-return，**棋子一枚都不会生成**。必须在桩里给 `#boardGrid .cell` 返回 289 个假格子。
3. **棋子是 `document.createElement` 产物，不进 `boardGrid.innerHTML`** —— 用 innerHTML 正则永远查不到棋子。桩里要捕获 `createElement` 产物到 `created[]`（打 `tag` 标记），据此断言「100 枚 / 四色各 25 / 单字标识 / 类名合法」。

**实机回归探针（`shoot_board_idx.js`）与阈值**
```
railSegs:100  arcs:4  diags:64  svgSize:544x544(=17×32)
centerCellPlain:true  centerCellNoGridLine:true
campRing:"3px rgba(228,216,170,0.88)"  pieceSize:"30pxx25px"
techCards:4  techMedals:4  titleBadges:3   ← 证明技术积分/奖牌/称号徽章未被回退
```
- 线宽 5px + 白芯 1px；铁路线段 **100 直 + 4 弧**、内芯各同数、斜线 **64** 条。
- **回归必查「未迁移能力未被回退」**：`techCards`(4) / `techMedals`(4) / `.mvtag.tech` 徽章（DEMO 落在第 30/68/73 步，文案「🏆 信仰+20」「🏆 天选之人+20」，`animationName` 应为 `techPop, techGlow`）。

### 断言式批量移植范式（推荐）

多区块移植不要手改 20+ 次 Edit（还容易漏），写一个 Python 脚本，把每处改动做成 `(名称, old, new)` 三元组列表：

```python
for name, old, new in EDITS:
    n = src.count(old)
    if n != 1: print("FAIL", name, n); fail += 1; continue   # 命中数必须恰为 1
    src = src.replace(old, new, 1)
```

- **每处 old 必须唯一命中**，命中 0 次（字符串对不上，通常是被 base64 或转义坑到）或 >1 次都算失败 → 整批不落盘，全部回滚为零风险。
- 先备份 `index_task2.html.bak_pre_ACD_<日期>`。
- 注意 Python 里用 `u'''...'''` 包中文；空替换写成 `u''`，别写成 `u'''""")`（会 SyntaxError: '(' was never closed）。
- 移植完成后按顺序验证：① 抽取最长 script 块 `node --check`；② VM 测试台跑 e2e；③ puppeteer 实拍浅/深两版 + 探针读 `getBoundingClientRect()` 核对 12 列布局的真实像素（列宽 = (容器宽 − 11×gap)/12，可反推每块占用列数是否与设计一致）。

### 项目内测试台（`.workbuddy/tests/`，task2 与 index.html 各一套）

**⚠️ `/tmp/junqi_test/` 已被系统清空三次（2026-09-13、09-15 两次），2026-09-15 起整套测试台固化到 `<项目>/.workbuddy/tests/`，不要再放 `/tmp`。** 目录内容：

**A. 针对 `index_task2.html`**（文件名带 `_task2`）

- `extract_engine_task2.py` — 用 `re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)` 取**最长**块写 `engine_task2.js`（页面有 3 个 script：JSON-LD / 主题预置 / 主脚本，取最长即主脚本）。路径全部由 `__file__` 推项目根，不需要改。
- `run_e2e_task2.js` — **172 项** VM 回归（`node run_e2e_task2.js`，需先跑 extract）：
  - 0~5 段：初始化无异常 + DEMO_TEXT/.jgs 两条数据源主面板非空、C 类 `teamSplit/getWinTeam`/对阵头/胜负标签、D 类 `applyTheme/toggleTheme/setSeoCollapsed/toggleSeoIntro`。
  - 6 段：源码级结构断言（12 列 grid、无 `area-clutch/area-curve` 残留、`clutchList/valueCurve` 在统计卡内、主题变量齐备、`var(--chart-` ≥ 9、无遗留硬编码 `#eae4d2/#c9b98a/#e8e4dc`）。
  - 7 段：**反向断言 B 类确实没被引入**（无 `computeTechScore`/`techCard`/`.mvtag.tech`）。
  - 8~9 段：**E 类全屏窗口**（未导入棋谱时 alert 且不抛异常、开窗写出的 HTML 含 `#popupCard`/`popup-bar`/`popup-tip`/W-S 提示/keydown/`op.gotoStep` 代理、浅深主题下子窗 `<html>` 的 `theme-dark` 类、二次调用只 focus 不重写、`closeReplayWindow` 置空、`applyTheme` 同步子窗 + 源码级断言）。
  - 10 段：**F 类 QQ 风格棋盘**（运行时 `buildBoardGrid/renderBoard` 后仍 289 格且四家/行营/大本营/兵站类名齐全；源码级断言军绿变量、织纹、格心十字渐变、SVG 轨道 5px + 白内芯 1px、旧按格渐变铁路已移除、SVG 绝对定位脱离网格流、棋子 30×25 浅底深字、旧白字彩底已移除、空心圆环行营、亮金终点、深色变量、弹窗 46px/43×36）。
  - 10 段尾 **F8/F9/F10 铁路网 + 行营米字形 + 中央区去细线**（2026-09-15 深夜更新为 `RAIL_LINES` 线表口径）：F8 = SVG 已注入、`isRailway` 遍历出 **85 个铁路点**并做 flood-fill 断言**整网一块连通**、越界安全、四家大本营未被误判为铁路、行营布局保持 4 角 + 1 心。**F9 = 四家第 1/5 排专项**：上家行 11/行 15、左家列 5/列 1、右家列 11/列 15 整排铁路，四家第 6 排（底线）都不是铁路。**F10 = 中央九宫格 + 线表拓扑 + 米字形 + plain 共 14 条**：行 6/行 10 贯通列 1-15、行 8 只到列 5-11、列 6/列 10 贯通行 1-15、列 8 只到行 5-11、列 1/5/11/15 只在行 6-10；行 7/行 9 上铁路点仅 列 1·5·6·8·10·11·15；**「多画的行7/行9 连接段已移除」「多画的列7/列9 连接段已移除」**（`railLinked` 反向断言，即用户第三轮那条「军长→中央铁路」）；真连接段保留（行 6/行 8/列 8 接第 1 排）；线段不再连到列 0/列 16；行营共 20 个；**每个营的 4 条斜线齐备（米字形斜向）**；行营格不带 plain、中央区 9 个兵站也带 plain、中央区 25 格全部带 plain、`.cell.plain{background-image:none}` 存在。
  - ⚠️ **VM 桩要补** `screen:{width,height}`（`openReplayWindow` 用 `screen.width` 居中）与 `alert`（否则守卫分支直接 ReferenceError）；`window.open` 要桩成返回 `{closed,focus,close,document:{documentElement:{classList},open,write,close}}` 的假窗口才能断言写出的 HTML。
  - **F10b = 中央九宫格四角弧形铁道专项 8 条**（2026-09-15 深夜加入）：弧 4 段 + 白芯 4 段；图层顺序 `diag → rail → arc`；`d` 全部为 `M + A(1,1,0,largeArc=0,sweep,x,y)`；端点全部是铁路点；每条弧对应九宫格四角之一（两端构成的「对角格」里恰有一个行/列 ∈ {6,10}）；sweep 序列 = `[0,0,1,0]`；端点组合集合 = 预期 4 组；「师长(10,5)↔司令(11,6)」那个角存在；`.rail-arc`/`.rail-arc-hi` 的 CSS 与直轨同色同宽；`RAIL_ARCS` 恰 4 条。**VM 里没有 `getBBox`/`getTotalLength`，几何量只能靠解析 `d` 字符串 + 源码正则；真正的渲染几何交给 `probe_rail.js`。**
  - **F12 = 明棋/暗棋（盖牌）专项 21 条**（2026-09-17 加入，「点某方任意棋子 → 该方整方盖牌 / 再点明棋」）：行为断言 —— `hiddenSides` 四方键初值全 false、`toggleSideHidden` 切换并返回新状态、非法入参（`'黑'`/`undefined`/`null`）返回 false 且不污染状态；源码级断言 —— `renderBoard` 打 `data-color` 与恢复盖牌态、`applyHiddenState` 只切 class 不重渲染、点击用事件委托挂 `#boardGrid`、`onBoardPieceClick` 从 target 回溯 `.piece`、`.piece` 基类 `cursor:pointer`、盖牌 `color:transparent`、**`html.theme-dark .piece.hidden{color:transparent}`（深色主题特异性补丁）**、**牌背纯色：无 `.piece.hidden::after`、无 `background-image`、浅色/深色各四方六位 hex 底色齐备且互不相同（防复制粘贴写重）**、图例提示、弹窗内点击转发 + **弹窗不再下发任何盖牌覆盖规则（靠 `'<style>' + css + '</style>'` 继承主样式表）** + 底部提示。
  - ⚠️ **断言写法坑（本次踩到）**：拼装「键」时务必加括号 —— `Math.min(c,c2) + .5 + ',' + Math.min(r,r2) + .5` 因为 `+` 左结合会算出 `"2.5,20.5"` 这种错键（正确写法 `(Math.min(c,c2)+.5) + ',' + (Math.min(r,r2)+.5)`），导致 64 条斜线**全部**查不到、报「80 条缺失」。这类「看起来像产品 bug 其实是测试 bug」的误报极费时间，写键拼接时一律加括号。
- `shoot_board.js` — puppeteer 实拍：棋盘卡局部（浅/深）、整页浅色、弹窗（浅/深），输出 `out_*.png` 到本目录；并回读探针（棋盘尺寸、`background-image` 层数、棋子宽高与四色计算色、坐标字色）。加载示例后 `gotoStep(30)` 再拍，才有行棋高亮。
- `probe_rail.js` — **24 项**铁路/斜线/弧线对位探针（真实 Chrome）。把 SVG 的 `viewBox` 单位换算回屏幕像素，断言：SVG 区域 = 17×cell 且原点对齐首格；**铁路线段 100 / 白内芯 100 / 斜线 64** 段；铁路线段端点全部落在格心（`.5` 网格）且**横平竖直无斜段**；**斜线端点全部落在行棋点格心**、全部 45°、**每条至少一端是行营**、20 个营、**每个营恰好引出 4 条斜线**；**弧形铁道 4 段 + 白芯 4 段**、图层顺序、`d` 格式、端点落格心且是铁路点、**弧长 = π/2 且包围盒 = 1×1（用户单位）**、**弧中点落在预期象限（验 sweep）**、sweep 序列 `[0,0,1,0]`；旧 `.railway-h/.railway-v` 类已不再生成；零 pageerror。**视觉改造后先跑这个再截图** —— 肉眼很难判断线段端点是否真落在格心（本次就是靠它发现 SVG 当 grid item 导致整个棋盘错位 544px）。
- `zoom_region.js` — **通用区域放大实拍**：`node zoom_region.js r0 c0 r1 c1 [outfile]`，`deviceScaleFactor=5`，逐格报告 `R/L/P/[class]` 图例（`R`=铁路点 `.`=非铁路 `L`=有公路细线 `-`=无线 `P`=有棋子）。**这是验证「中央区去细线」「某格是否铁路」最快的手段** —— 纯文本逐格报告 + 高清截图一次拿到，比截图肉眼数格可靠得多。
- `zoom_center_task2.js` — 中央 7×7 格放大（行 5-11 × 列 5-11），`deviceScaleFactor=4`；含 `cell-r-c` id 选择器修正。
- `verify_sfx_task2.js` — **13 项**采样音效真实浏览器验证（`node verify_sfx_task2.js`）：6 段全部解码成功（打印 duration/sampleRate/channels）；`SFX_MAP` 全部指向已解码的键；**走完整份 demo 棋谱**（`for n=1..replay.moves.length: gotoStep(n)`）同时 hook `window.playSfx` / `window.playBeep` 统计各音效触发次数，断言**每步都有音效**且无越界键；断言 **`bounce` 解码时长 ≠ `eat`** 且 ≈ 0.518s（防止两键又指回同一段采样）；逐条列出「司令阵亡」触发点（demo 棋谱里命中 1 处：第 17 步「同尽（司令vs司令）」）。**这份统计是判断映射有没有接错线的唯一手段** —— 静态断言只能证明表写对了，证明不了「真的走到那个分支」。demo 参考分布：move 47 / eat 14 / bounce 9 / giveup 3 / blast 1 / cmdr 1，共 75 次 = 75 步。
- `sfx_preview.html`（项目根目录，**不是测试脚本**）— 离线试听页：6 张卡片各带源文件名、触发场景、事件标签、原生格式元数据与「▶ 试听」按钮，底部附映射说明。**由 `/tmp/make_sfx_preview.py` 从 `index_task2.html` 提取同一份 base64 生成**（保证试听的就是产品里内嵌的），改音效后重新跑一次即可。⚠️ 生成脚本的 HTML 模板里别用 `%` 格式化 —— CSS 的 `100%` 会被当成格式符报 `unsupported format character`；用 `@@CARDS@@` 之类的显式占位再 `.replace()`。⚠️ 解析 WAV 头取元数据**必须按 RIFF 块表遍历，不能用固定偏移** —— 这 6 个文件里有两种「异形」：`移动走子.wav` 在 data 前多一个 `fact` 块（data@48）；新 `撞子被反吃.wav` 的 `fmt` 块是 **18 字节**（带 cbSize）且前面还有 `fact`（data@50）。固定偏移 `raw[40:44]` 会把 fact 内容当成 data 长度，算出 **0.00s / 26.48s** 这种离谱时长（试听页卡片一度就这么显示）。遍历写法：`fmt` 数据自 `pos+8` 起算 —— `channels=+10`、`sampleRate=+12`、`bitsPerSample=+22`；块长奇数要 `+1` 对齐再跳。**Web Audio 的 `decodeAudioData` 不受影响**，所以「产品里声音正常、只有自写解析器算错」是典型症状。
- **和 QQ 原版做同尺度对照的做法**：QQ 客户端原图格宽 **78.5px**（实测：列6=774、列8=931、列10=1088；行8=675、行10=832，即 `x = 774 + (c-6)*78.5`、`y = 832 + (r-10)*78.5`）；我方实拍先算出 `CELL`，按**同样的格数**裁两块再各自 resize 到同一尺寸，才能真比形状。`cmp_arc_qq_vs_ours.png` 就是 1.5 格见方、以 (10,6) 兵站环为中对齐的成品。
- `shot_replaywin_task2.js` — **36 项**全屏窗口真实浏览器验证：按钮存在/文案/靠右/onclick、点击开子窗（`page.once('popup')`）、子窗标题栏+提示条+`.cell` 数=289+棋子数>0+已删按钮+控制条齐备+`--cell-size:46px`+棋子 43×36+军绿底板三层背景、W/S/▶/播放代理主窗步进、主窗切深色子窗同步、**子窗内点棋子＝该方盖牌（转发回主窗 + `sync()` 双向生效、牌背同样为纯色：`background-image` 空 + 无 `::after`）**、按 C 关闭且 `replayWin` 置空、零 pageerror。
- `verify_hidden_task2.js` — **28 项**「点棋子＝该方盖牌/明棋」真实浏览器交互验证（`node verify_hidden_task2.js`）：四方各 25 枚、初始无盖牌、`data-color` 与 `cursor:pointer`；**真实鼠标点击**（验证棋子没被 SVG 叠加层抢掉命中）→ 该方整方盖牌；盖牌视觉（文字透明、DOM 文本保留、**无 `::after` 徽记、牌背 `background-image` 为空且为单一实色**、底色 ≠ 明棋底色）；再点恢复；多方独立互不干扰；**跨步持久**（`gotoStep(5)` 重建棋子后仍盖牌）、跨视角持久；点空格子无效；**深色主题下文字同样不可见、牌背同样无渐变**；图例提示、`toggleSideHidden` 返回值与非法入参；零 pageerror。
- `shoot_footer_stat.js` — **页脚「51.la 统计」位置实拍 + 加载断言，覆盖 4 页共 51 项**（`node shoot_footer_stat.js`）：
  逐页断言 —— 统计代码在 `footer` 内、全页仅 1 处、`href`/`src` 正确、**图标 `naturalWidth > 0`（真的加载出来了，外链图必须查这个，否则「src 写对但图挂了」查不出来）**、
  **统计图标 `bottom ≤ 备案链接 top`（「在备案信息上方」是位置关系，肉眼看截图不可靠）**、水平居中（中线偏差 < 4px）、
  **采集 JS：`id="LA_COLLECT"` 存在 + `charset=UTF-8` + `src` 为显式 https + `window.LA.init` 是 function**、零 pageerror；
  页面清单：`qq军棋复盘分析/index_task2.html`、`qq军棋复盘分析/index.html`、`四国军棋布局转换器.html`、`junqi_replay.html`
  （后两页路径在上级目录，**脚本里写的是绝对路径**）。产出 `out_footer_task2.png` / `out_footer_index.png` / `out_footer_conv.png` / `out_footer_jr.png`。
  **凡动页脚或统计，跑这一份就够。**
- `shoot_hidden_task2.js` — 明暗棋效果实拍：`out_hidden_up.png`（明棋）/ `out_hidden_green.png`（一方盖牌）/ `out_hidden_two.png`（两家盖牌）/ `out_hidden_zoom.png`（绿紫交界 4×4，盖牌与明棋同框，DSF 4）/ `out_hidden_dark.png`（深色主题）。**深色主题那张是发现「盖牌仍透出兵种字」的唯一手段，改盖牌样式后务必重拍。** 本复盘方位：绿=右 紫=下 黄=左 蓝=上（视角=紫），取景靠这个定。
- 断言阈值坑：`var(--chart-` 是 **9 处**（不是 10），写 ≥10 会误报失败；弹窗 `#boardGrid .cell` 是 **289 格**（17×17），不是 400；`page.waitForEvent` 在本机 puppeteer-core **25.7.0 已移除**，用 `page.once('popup')`。

**B. 针对 `index.html`**（文件名带 `_index`，2026-09-15 加入）

| 脚本 | 用途 |
|---|---|
| `extract_engine_index.py` | 从 `index.html` 抽最长 `<script>` → `engine_index.js`（与 task2 版逻辑相同，只换输入文件） |
| `run_board_index.js` | **70 项** VM 回归（**棋盘专项**，比 `run_e2e_task2.js` 窄但含 index 独有断言）。覆盖：`RAIL_LINES` 14 条 + 行号不重复 / `isRailway` 与 `railLinked` 双层语义（行 7·9、列 7·9 的交叉格是 `true` 但线段是 `false`）/ `buildBoardSvg()` 段数 100 直 + 100 芯 + 4 弧 + 4 弧芯 + 64 斜线（斜线用独立算法复算）/ 图层顺序 / 端点全是格心 / `buildBoardGrid()` 289 格 + 18 列头 + 17 行头 + 25 plain + 9 station + 8 hq + 20 camp + 无 `railway-h\|v` / 端到端两条数据源 13 个面板非空（**含 index 独有的 `techScoreGrid`**）+ 零 `undefined/NaN` + 棋子 100 枚四色各 25 + `gotoStep` 逐步重绘。用法：`python3 extract_engine_index.py && node run_board_index.js` |
| `shoot_board_index.js` | **17 项** 真实 Chrome 实拍 + 探针（阈值判定）。实拍 `idx_board_light/dark.png`、`idx_full_light.png`、`idx_tech_light.png`、`idx_popup_light/dark.png`；断言铁路 100/100、弧 4/4、斜线 64、SVG `544x544`（=17×32）、中央 plain、行营环 3px、棋子 `30x25`、弹窗 `--cell-size:46px` + 棋子 `43x36` + 289 格、**技术积分 4 卡 4 奖牌 + 称号徽章 ≥1 且 animationName = `techPop, techGlow`**（这三条是「棋盘迁移没把 B 类功能搞回退」的守门断言）、零 pageerror |
| `run_sfx_flags.js` | **14 项** VM 单元：造两子局面直接打 `resolveMove()`，验证「司令阵亡」`event.cmdr` 标记。正向 6 例（军长吃司令 / 司令被反吃 / 司令触雷 / 炸弹炸司令 / 司令中炸 / 司令司令同尽）+ **反向 6 例**（司令吃子、军长撞司令、炸弹炸军长、师长吃营长、工兵挖雷、司令扛旗 —— 均不得置位）+ 覆盖性检查。**演示棋谱只有 1 处司令阵亡（同尽），其余分支必须靠这个脚本覆盖。** |
| `run_sfx_index.js` | **35 项** 真实 Chrome 音效专项：6 条采样解码成功与 duration/声道指纹（**bounce 0.518s/1ch**，2026-09-16 起与 eat 不同）、type→采样键 12 条映射、**逐步走完全场并逐步比对「实际发声键 == 独立 spec 期望键」**、司令阵亡标记与独立统计一致 + 无误报、静音开关、**弹窗点 `#btnNext` 代理后主窗仍发声**、零 pageerror。做法：patch `AudioContext.prototype.createBufferSource/createOscillator`，在 `start()` 里把 `s.buffer` 反查成采样键记进 `window.__log`（用 `pairs.find(p=>p[1]===s.buffer)`，**不要去给 AudioBuffer 挂属性**）。 |

**⚠️ index.html 专有的两个测试坑（本轮踩到）**
1. **`renderMoveList` 里的称号徽章是「数据相关」的**：`DEMO_TEXT` 样本不触发任何称号，只有内置 `.jgs` 样本（`#btnLoadDemo` 载入的是 `DEMO_JGS_B64`，**不是** `DEMO_TEXT`）才触发。**不能硬断言「一定有徽章」**，要与 `sandbox.techScore.titleLog` 对账：渲染出的 `.mvtag.tech` 数 == `titleLog` 中 `stepIdx ∈ [1, replay.moves.length]` 的条数；再汇总断言「两数据源合计 ≥1 枚」。
2. **`__dirname` 层级别照抄 Python 的 `os.path.dirname` 三次**：Python 的 `abspath(__file__)` 含文件名，要 3 次才能到项目根；Node 的 `__dirname` 已是目录，**2 次**即到项目根（写 3 次会去找 `/Volumes/me/ai学习/四国军棋/index.html`，报 `ERR_FILE_NOT_FOUND`）。
3. 顺带一条核对高亮的姿势：高亮类名是 **`highlight-from` / `highlight-to`**（不是 `hl-*`），加在 `#cell-<row>-<col>` 上，且 `from/to` 是 `[行, 列]` 顺序。用 `gotoStep(n)` 后 dump 带这两个类的格子 id，即可 1 秒验证「红框 → 终点」与行棋坐标一致。

## 迭代工作流

修改 index.html 后必须按以下顺序回归，缺一不可：

### 第 1 步：Node 引擎回归

`/tmp/test_color_v2.js`：从 HTML 抽取纯 JS 逻辑（引擎部分）在 Node 中运行，断言解析、统计基线、方位映射、行棋序。当前基线 35 项通过。

```bash
NODE_PATH=/Users/wangjian/.workbuddy/binaries/node/workspace/node_modules /Users/wangjian/.workbuddy/binaries/node/versions/22.22.2-3/bin/node /tmp/test_color_v2.js
```

> ⚠️ **Node 路径会随托管版本升级变化**：`22.22.2` → `22.22.2-2` → `22.22.2-3`（2026-09-15 实测可用的是 **`-3`**）。命令报 `no such file or directory` 时先 `ls /Users/wangjian/.workbuddy/binaries/node/versions/` 确认实际目录名。
> ⚠️ **第 1~4 步的脚本路径（`/tmp/test_color_v2.js` 等）是历史记录**：`/tmp` 会被系统清空，现役测试台一律在 `<项目>/.workbuddy/tests/`（见「项目内测试台」一节）。这些脚本如已丢失，按该节的清单重建。

统计基线（test_color_v2 使用内置固定示例 `DEMO_TEXT`，该文本是用**旧方位**从 6_24_16_22 转换的，205 移动步 + 3 事件步；数组=[步数,吃子,被吃,同尽,炸杀,中炸,挖雷,得分,损失,净值]）：
绿[53,8,5,5,2,1,0,452,285,167]、黄[50,7,8,3,2,1,0,307,368,-61]、蓝[52,6,7,5,1,2,0,450,439,11]、紫[50,7,7,6,1,1,0,257,409,-152]。**改动统计逻辑、战败规则或 DEMO_TEXT 后必须重跑并更新基线**。

> **重要区分（2026-08-18 修正移动颜色编码后）**：`DEMO_TEXT`（旧方位固定文本）统计 ≠ 真实文件 `parseJGS` 的新方位统计。真实 6_24_16_22.jgs（黄=up/绿=down/紫=left/蓝=right，205 移动步 + 3 事件步=蓝/黄/紫自杀战败）**离场串色修复后的移动步基线为 蓝49/黄52/绿52/紫52**（`/tmp/test_view.js` 断言；旧基线 蓝50/黄53/绿50/紫52 是修复前颜色解码错误导致的统计偏差，2026-08-18 已更新）。四家净值总和在有自杀战败清子时不为 0（战败方剩余棋子被清、不给对手计分），这是正常规则。

### 第 2 步：jsdom 全页冒烟

`/tmp/smoke_v2.js`：jsdom 加载完整 HTML，断言 DOM（棋盘 100 子单字、四色 piece class、9 兵站/8 hq/20 camp、行棋条方向、玩家卡、视角下拉与切换、图例、进度条等）。当前 84 项通过。

### 第 3 步：6 个真实 .jgs 回归

`/tmp/all_files_orient_v3.js`：对布局库 6 个 .jgs 逐一验证方位映射（逐键断言，勿用 JSON.stringify 比较对象——键序会导致误判）、orientSrc='geo'、军旗落点、移动步数基线（318/22/67/72/35/205，不含事件步）、布局 100 子、jgsToText 含「方位=」行、二次导入 orientSrc='meta'、事件步输出与识别（文本总步数=移动步+事件步、二次导入事件步数）。当前 66 项通过。

### 第 4 步：真实 Chrome 截图回归

`/tmp/shot_v2.js`（puppeteer-core + 系统 Chrome）：加载文件、点「开始分析」、断言 DOM 状态（turnChips、orientMeta、起点箭头旋转角）+ 截图。**必须零运行时错误（console/pageerror）**。

### 第 5 步：index.html 棋盘专项回归（改棋盘 / 铁路 / 棋子 / 弹窗尺寸时必跑）

```bash
cd "<项目>/.workbuddy/tests"
python3 extract_engine_index.py && node run_board_index.js   # VM 回归，应为 70 通过 / 0 失败
node shoot_board_index.js                                    # 实机探针 + 实拍，应为 17 通过 / 0 失败 + 页面零错误
```

覆盖 `RAIL_LINES` / `isRailway` / `railLinked` / `buildBoardSvg()` / `buildBoardGrid()` / 棋子四色 / 弹窗尺寸，并**守门断言技术积分 4 卡 · 4 奖牌 · 称号徽章动画未被棋盘改动回退**。改棋盘视觉时这两条命令是「改动是否等价」的最快判据。

### 第 6 步：音效专项回归（改音效 / 碰 resolveMove / 碰事件步时必跑）

`index.html`（音效系统在此先行实现）：

```bash
cd "<项目>/.workbuddy/tests"
python3 extract_engine_index.py && node run_sfx_flags.js   # cmdr 标记单元，应为 14 通过 / 0 失败
node run_sfx_index.js                                      # 真实 Chrome 音效专项，应为 35 通过 / 0 失败
```

`index_task2.html`（2026-09-16 起同款实现）：

```bash
cd "<项目>/.workbuddy/tests"
python3 extract_engine_task2.py && node run_e2e_task2.js   # 含 F11 音效 + F12 明暗棋断言，应为 175 通过 / 0 失败
node verify_sfx_task2.js                                   # 走完整份棋谱统计音效触发，应为 13 通过 / 0 失败
node verify_hidden_task2.js                                # 点棋子＝盖牌/明棋 交互，应为 28 通过 / 0 失败
```

**「落盘前预演」技巧**：`run_board_index.js` / `run_sfx_flags.js` 都支持 `ENGINE=<路径>` 环境变量指定引擎，
把改版先写到 `/tmp/...html` → 抽脚本 → `ENGINE=/tmp/engine_new.js node run_*.js`，全绿再 `cp` 覆盖 `index.html`，避免脏改动落盘。

## 竞技技术积分 · 构成（基础得分 + 称号 + 规则 + 技巧）

**技术积分 = 基础得分（玩家表现评估） + 称号成就 + 规则结算 + 操作技巧**。
- `card.basePts` = **「玩家表现评估」综合得分**（`evaluateAll()` → `computePlayerEval().total`，五维加权百分制 0~100，子力交换25%+信息判断20%+配合贡献20%+关键节点20%+心理节奏15%），与 S/A/B/C/D 评级**同源**。`card.baseGrade/baseStars` 供 UI 展示；`card.baseNet`（子力净值）只作对照、**不计分**。`total = basePts + titlePts + rulePts + skillPts`。
- **调用顺序有依赖**：`startAnalyze()` 必须 `var evals = evaluateAll(replay, analysis)` → `computeTechScore(replay, analysis, evals)` → `renderTechScore()` → … → `renderPlayerEval(evals)`。`computeTechScore(replay, analysis, evals)` 第三参可省：未传时若 `analysis.stats` 存在则内部补算 `evaluateAll`，否则 `basePts=0`（保证合成测试台不崩）。
- 页头副标题写「基础得分取玩家表现评估 · 与 S/A/B/C/D 评级同源」。
- `newCard()` 必须带 `basePts/titlePts/rulePts/skillPts`，`total` 在终局统一结算。

**信息栏名次奖牌（2026-09-14 新增，同日加绶带 + 动画）**：`renderTechScore()` 内按 `cd.total` 排名，玩家信息栏 `.tech-head` 整条着色并带一枚「绶带 + 金属圆牌」奖牌（形似 🏅）。
- **名次算法**：先取有卡的玩家 → `rankList.sort((a,b)=>b.t-a.t)` → 逐个回溯「前面是否有同分」定名次，即**标准竞赛排名**（同分并列，后续名次顺延：1,1,3,4）。四人同分则四个都是第 1 名（全金）。
- **奖牌映射**：`MEDALS = {1:{k:'g',n:'金牌'}, 2:{k:'s',n:'银牌'}, 3:{k:'b',n:'铜牌'}, 4:{k:'i',n:'铁牌'}}`。
- **HTML 三段结构**（`class`/`title` 的写法不能动，`run_medal.js` 靠它解析名次）：
  `<div class="tech-head medal-{k}"><span class="tech-medal" title="技术积分第 N 名 · 金牌"><i class="tm-ribbon"></i><span class="tm-disc"><span class="tm-shine"></span>N</span></span>…`
  - `.tech-medal` = 22×26 的定位盒（`align-items:flex-end`，让圆牌贴底、绶带在上）；
  - `.tm-ribbon` = 绶带容器，`::before`/`::after` 两条 7×15 的斜带各 `rotate(-17deg)/rotate(17deg)`（`transform-origin:50% 100%`）向外张开成 V 形，压在圆牌下方（`z-index:0`）；
  - `.tm-disc` = 20×20 金属圆牌（`z-index:1`、`overflow:hidden`、`border-radius:50%`），名次数字直接写在里面；`.tm-shine` 是牌面上的循环扫光（`::after` 不行——伪元素会盖在数字上，所以用独立子元素）。
- **四段动画**（都在 `.tech-medal` 这一簇上，`prefers-reduced-motion` 里统一 `animation:none` + 扫光 `display:none`）：
  - `medalSwing 3.4s` — `.tech-medal` 整体悬挂摆动 `rotate(-5deg ↔ 5deg)`，`transform-origin:50% 1px`（绕绶带顶端摆，像挂在绶带上的真奖牌）；
  - `medalGlow 2.8s` — `.tm-disc` 的金色外发光呼吸；
  - `medalShine 2.9s` — `.tm-shine` 斜切白光在牌面上扫过；
  - `ribbonFlow 2.8s` — 绶带 `background-size:100% 220%` + 竖向滚动 `background-position`，做出缎带流光。
- **绶带配色按名次分色**（用 CSS 变量 `--rb1/--rb2/--rb3` 声明在**伪元素自身**的规则里，主规则用 `var(--rb1,#f0604a)` 带兜底；变量在计算值阶段解析，因此同元素的两条规则可以分开放）：金=红 `#f0604a→#c0392b→#93261a`、银=蓝 `#8db6d4→#3a6f96→#27506d`、铜=橙 `#e8ab68→#a55d21→#7a4013`、铁=灰 `#9fabb6→#5a646d→#3f474e`。配色规则写成 `.medal-g .tm-ribbon::before,.medal-g .tm-ribbon::after{--rb1:…}`。
- **样式要点**：`.tech-head` 用负外边距 `margin:-10px -12px 0` 撑满卡片顶部做成「奖牌带」，`.tech-card` 必须同时加 `overflow:hidden`（否则圆角处溢出），并配 `border-radius:7px 7px 0 0`。四种底色用 `linear-gradient(90deg,rgba(...,.3x),…,transparent)`；圆牌 `.tm-disc` 仍用 `radial-gradient(circle at 32% 26%,…)` 做金属球面 + `inset` 高光。奖牌高度由 20px 变 26px，奖牌带整体高 6px，四张卡一致、grid 会让卡片等高，不会错位；绶带顶端距卡顶还有 7px（`tech-head` 的 `padding-top`），不会被 `overflow:hidden` 切掉。
- **深色主题**：`html.theme-dark .tech-head.medal-*` 单独把透明度调低（.20~.24），否则金/银底色在深底上过亮、浅色文字对比度下降；奖牌本体再单独覆盖 `html.theme-dark .tech-medal .tm-disc{box-shadow:…rgba(0,0,0,.55)}`（降外阴影）与 `… .tm-ribbon::before/::after{box-shadow:…}`（提亮绶带描边），铁牌圆牌另给一档更弱的高光。
- **玩家名要包 `<span class="tech-pname">`**（`min-width:0` + ellipsis），否则长昵称（如「江湖人称小武哥」）在 4 列窄卡里会把总分挤出卡片。
- 奖牌只按**技术积分总分**排名，与「四位玩家」里的胜负关系/子力净值无关。

**行棋记录内的称号徽章（高亮 + 动画，2026-09-14 新增）**：某一步触发了「称号成就」时，`renderMoveList()` 在该条记录末尾追加 `<span class="mvtag tech">🏆 称号名+N</span>`，并给行加 `mv-has-title` 类。
- **数据源**：`computeTechScore` 内的 `titleLog`（`grant(c,'titles',...)` 时 push `{color,name,pts,stepIdx,desc}`）。**只有 `titles` 类入 log**，`rules`/`skills` 不进去 —— 想给「规则结算/操作技巧」也加徽章时，改 `grant()` 里那行 `if (cat==='titles' && stepIdx)` 即可。
- **匹配口径**：`tl.stepIdx === i+1`（`i` 是 `analysis.steps` 的下标），故 `titleLog` 的顺序是**授予顺序**（终局结算类称号是倒序的，如第73步→第68步→第30步），而徽章渲染出来必然是**步号升序**。写断言时不要拿两个数组直接 `JSON.stringify` 比对，要先按 `stepIdx` 排序。
- **事件行也要挂徽章（已修）**：`.act` 是三元表达式渲染的，原先 `tag` 只拼在「非事件」分支里，落在 `type==='event'`（自杀战败/退出游戏）那一步的称号会被静默漏掉（`以和为贵`/`绝地老六`/`天选之人`/`复活圣手` 这类在 `pStep`/`lastAct` 结算的称号最容易踩到）。两个分支都必须 `+tag`。
- **高亮动画（3 段）**：`.mvtag.tech` 用金色渐变 `linear-gradient(120deg,#ffeaa6,#ffcb3d 48%,#f5a623)` + 深金字色；`animation:techPop .42s both, techGlow 2.4s ease-in-out .42s infinite`（入场弹出 + 呼吸光晕）；`::after` 伪元素做循环扫光 `techShine 2.6s`。行标记 `.mv.mv-has-title{box-shadow:inset 3px 0 0 rgba(240,166,0,.85)}`（用 `box-shadow` 而不是 `border-left`，避免 flex 行发生 1px 布局位移）。
- **实现细节**：`::after` 扫光要求徽章自身 `position:relative; overflow:hidden`（`.mvtag` 本来就是 `inline-block`，可放心加）；`.mvtag.tech` 记得给 `margin-right:3px`，否则贴到右边的 `+得分`。
- **深色主题**：`html.theme-dark .mvtag.tech` 必须单独覆盖（金调亮到 `#8a6512→#cfa01f→#96700f`、字色 `#fff4c8`），否则原来那段「暗棕底 + 浅金字」在深色下几乎没有高亮感；`html.theme-dark .mv.mv-has-title` 的金条也要单独给。
- **必须带 `@media (prefers-reduced-motion:reduce)` 兜底**：`.mvtag.tech{animation:none}` + `::after{display:none}`（`techPop` 用了 `both`，关掉动画后元素才能回到默认 `opacity:1`）。

**规则结算（`TECH_RULES`）两项**：
- `逃跑瓜分` — **每局最多执行一次**：本局**首次**有玩家投降/逃跑时，其**剩余子力净值**的 **50%**，由**仍在局中的玩家平分**（队友与敌对方一视同仁）。实现要点：
  - **一次性锁定**：`var escapeDone = false` 置于 `escapeSplit` 外层作用域，`escapeSplit` 首行 `if (escapeDone) return;`，在所有门槛通过、即将分账前 `escapeDone = true;`。**门槛拦下的那次不算「执行」，不消耗机会**（下次符合条件者仍可触发）。
  - **触发门槛**：离场时**剩余子力净值 ≥ 开局总净值的 50%**（`est * 2 >= initEst[ecolor]`，整数比较、无浮点误差；`initEst[color] = Σ VAL[棋子]` 在 `computeTechScore` 开头按初始 `layout` 统计，一副完整子的开局净值 = 739）。不到半净值视为「已被打光、非主动放弃」，不瓜分。⚠️ 净值必须在 `markDefeat()` **之前**取（`markDefeat` 会 `removeAll` 清空该家棋子，之后净值恒为 0），所以调用点先算 `eEst` 再传第 2 参 `escapeSplit(ecol, eEst, si)`。
  - 分账：`var others = COLOR_ORDER.filter(c => c!==ecolor && alive[c])`；每人 `Math.round(est * 50 / (100 * others.length))`。逃跑方本人已在 `markDefeat()` 中置 `alive=false`，故天然被排除。
  - 触发事件 = 「主动投降 / 强行退出 / 5 次超时判负」；`isDef = (mv.timeouts>=5) || !isTimeout` 覆盖超时判负（解析器把 `超时判负` 事件写成 `timeouts:5`）。**被扛旗**（`/军旗被扛/`）与**子力被歼**不算。
  - 触发条件**不是**看事件文本是否含「退出」，而是「事件为 defeat 事件 且 `alive[ecolor]` 仍为 true」。因为 `.jgs` 把投降编码成 `战败`(+`退出游戏`) 两条事件，而**真正被歼的玩家在失去最后一枚可动子力的那一步就被 `hasMovablePiece` 检查提前判负**（`alive=false`），根本走不到事件分支。所以能走到这里的 defeat 事件必然子力尚存 = 主动离场。
  - **例外**：`/军旗被扛/` 的事件不瓜分（军旗判负已由「扛旗勇士」结算）。
  - 分账写入 `escapeAcc[color]` 累加、`escapeNote[color]` 记说明（含「离场时剩余净值 N/M，≥开局50%」的门槛凭据），循环结束后**一次性 `grant(c,'rules','逃跑瓜分',escapeAcc[c])`**。**不能**在 split 时就 grant——`grant()` 对同名只认一次，一局内两家先后逃跑时第二笔会被静默丢弃。
  - **百分比一律写成「整数分子 / 100」**：`Math.round(est * 50 / (100 * others.length))`。写 `0.5` 之外的浮点小数会踩坑——历史上 `180*0.35 = 62.99999999999999`、再 `/2` 得 `31.499999999999996`，`Math.round` 会舍成 **31**（真值应为 32）；同理不要用 `Math.floor`。
  - 历史沿革：30%/70%（每家 30 分底 + 均分）→ 30%/70%（按估值）→ 15%/35% + 半数门槛（2026-09-12）→ 50% 由在局玩家平分（2026-09-13）→ **每局最多一次、首次符合条件者独占（2026-09-13）**。当前已无队友/敌方之分，`hasAlly`/`foes` 两个局部变量已随之移除。
- `扛旗勇士` — 扛走敌方军旗：扛一家 +20、扛两家 +50。用 `flagVictims[扛旗方][被扛方] = step` 收集（`dc !== ALLY[ac]` 才计），终局按 `Object.keys(...).length` 给 20 或 50；原「被拿旗估值（按剩余子力估值计分）」已废弃。

**操作技巧（`TECH_SKILLS`）四项**：`令子言杀`+40 / `骗炸`+子力价值 / `无损`+5 / `磨棋`+10。（`骗令` 已于 2026-09-13 应要求删除。）
- `令子言杀`（2026-09-13 新增，替代 `骗令`；同日按用户口径加「另一侧」约束）— 敌方某家**绝对令子身份已明**后，我方用其**次令子**（仅次于该令子一级的子力）**避开这枚令子所在一侧**，攻击该家**另一侧**的子力。实现要点：
  - **「已明」追踪**：`originRevealed[origin] = step` —— ①`t==='killed'`（被撞击存活）时记 `preDefOri`；②`t==='eat'`（吃过子力）时记 `aOri`。注意在 `eat` 分支里**先做判定、再记 `originRevealed[aOri]`**，否则当步自身就会污染判定。
  - **判定六条件**（在 `t==='eat'` 分支内）：`dc && dc!==ac && dc!==ALLY[ac]`（目标是敌方）＋ `originRevealed[preTopInfoDc.origin]`（该家令子已明）＋ `preDefOri !== preTopInfoDc.origin`（打的不是令子本人）＋ `ap === nextRankDown(preTopInfoDc.piece)`（我方用的是次令子）＋ 两侧位均可判定（`preTopSide`/`preTgtSide` 都非 `'C'`）＋ `preTgtSide !== preTopSide`（打的是另一侧）。
  - **侧位判定**：`sideOfJ(j)` 把该家自身视角的「路」`j`（`localOf(color,r,c)[1]`，恒为 0~4）映射为 `j<=1 → 'L' 左翼`、`j===2 → 'C' 中线'`、`j>=3 → 'R' 右翼`。**令子与落点都在中线时不算触发**（无「所在一侧」可言），中线也不被视为「另一侧」。
  - **令子当前格**：`origin` 记的是棋子**初始格**（`origin[key]=key`，移动时 `origin[to]=aOri`），所以必须用 `cellOfOrigin(layout, ori)` 反查它的当前格再算侧位；`preTopSide`/`preTgtSide` 都在 `resolveMove()` 之前取（落点格此时仍有目标子）。
  - **三个辅助件**（都定义在 `computeTechScore` 追踪变量区）：`RANK_ORDER = ['司令','军长','师长','旅长','团长','营长','连长','排长','工兵']` + `nextRankDown(p)`（军阶降序取下一级，越界返回 `null`）；`topOriginOf(color, layout)`（返回该家绝对令子的 `{piece, origin}`，**必须在 `resolveMove()` 之前**调用，结果存 `preTopInfoDc`）+ `cellOfOrigin(layout, ori)`；`sideOfJ(j)`。
  - 与「绝对令子」口径一致：用 `VAL` 最大值选令子（同 `topPieceOf`），故令子是 炸弹/地雷/军旗 时 `indexOf` 为 -1、`nextRankDown` 返回 `null`，条件自然不成立。
  - 测试维度：正例（撞明后打另一侧 / 吃过子后打另一侧 / 左右对称）、反例（同侧、落点中线、令子中线、非次令子、令子未明、打令子本人、打的是另一家）—— 见 `run_rules.js`。

## 竞技技术积分 · 称号成就（权威口径见《竞技军棋称号说明.docx》）

`TECH_TITLES`（弹窗展示）与 `computeTechScore()` 内的 `grant(...)` 判定**必须一一对应**，改一处要同步另一处。当前 **16 项**（文档顺序，**2026-09-12 起全部按文档原值减半**）：横扫千军+40 / 天降神炸+20 / 宏宇之光+40 / 以和为贵+15 / 藏旗家+15 / 万人之上+50 / 过关斩将+40 / 扫雷能手+15 / 天使下凡+20 / 万人敌+25 / 绝地老六+40 / 天选之人+20 / 复活圣手+20 / 颠倒众生+25 / 似兵非兵+25 / 信仰+20。（原「持久战神」「爆破能手」「和为贵」已随文档调整移除/改名；**「人屠」已于 2026-09-12 应要求删除**，连带清掉了只为它服务的 `killBy`/`addKill` 记账代码。`initEst`（开局总估值）保留，供逃跑瓜分门槛使用。）

**「全体减半」类需求怎么改**：改 2 处，缺一处就会表里不一致 —— ①`TECH_TITLES[].pts`；②引擎里 16 条 `grant(...,'titles','X',<字面量>,'...')` 的数字。可用脚本 `/tmp/junqi_test/half_titles.py` 做带断言的批量替换（校验命中条数为 16、字面量全为偶数）。**改称号「触发条件/口径」时同样要同步 2 处**：`TECH_TITLES[].d`（弹窗表格说明）与引擎 `grant(...)` 的判定表达式 + 消息文案（如 2026-09-13 天使下凡由「全场绝对令子 `preTopAll`」改为「敌方绝对令子 `preTopDc`」，两处都改了）。**删称号**时要同时删 `TECH_TITLES` 条目与引擎 `grant` 块，并检查该块独占的局部变量是否变成死代码（`allyOf`/`foes`/`killBy` 就是这么清掉的）。

**令子口径**（文档只对部分称号锁死司令，其余为动态令子）：
- `topPieceOf(color, layout)` = 该家当前最大级子力（绝对令子）；`globalTopPiece(layout)` = 全场最大级子力。
- 锁死「司令」的：宏宇之光、天选之人；锁死「军长」的：横扫千军、过关斩将。
- 动态令子的：天降神炸（该敌家令子 `preTopDc` 或全场令子 `preTopAll`）、天使下凡（**该敌家令子 `preTopDc`**，2026-09-13 由「全场令子」改为此口径）、复活圣手（闯入方自家的令子）。
- **快照时机**：令子必须在 `resolveMove()` **之前**取（`preTopDc/preTopAll/preTopAc`），否则炸弹/同尽已经把目标从盘上删掉了。

**origin 级追踪**（同一枚棋子的跨步状态）：
- `origin[key]`（当前位置→origin id）、`originOwner`、`originPiece`（origin→棋子名）。
- `markKill(o,si)` / `markDeath(o,si)` / `originKillSteps` / `originLastKill` / `originDeath`。
- `preDefOri = origin[to]` 必须在 `resolveMove()` 前记录——resolveMove 会把 `layout[to]` 改成攻方，之后再读 `origin[to]` 就是攻方自己了。

**线/路口径**（`localOf(color,r,c)`，逆映射自 `mapLayout()`）：i=0 最前线 … i=5 底线；j=0 该玩家左手边 … j=4 右手边。`似兵非兵` 用它判定：深入 = i≤3；挂角 = i===4 且 j∈{0,4}；六线一路 = i===5 且 j===0。

**易踩的坑**：
- 队友关系由绝对方位决定（`ALLY`：上↔下、左↔右）。构造测试布局时别把队友当成敌人（例如 orient 为 绿up/黄down/蓝left/紫right 时，**黄是绿的队友**，绿的敌人是蓝、紫）。
- `#btnLoadDemo` 的 `.jgs` 演示与 `DEMO_TEXT` 是**两局不同的棋**。
- 合成场景测试台：`/tmp/junqi_test/run_titles.js`（**26 条**称号正反用例，含天使下凡新口径：己方握有全场令子时炸掉敌方令子仍触发）、`/tmp/junqi_test/run_rules.js`（**41 条**用例：逃跑瓜分 50% 由在局玩家平分（3 人各30 / 2 人各45）、**每局仅一次**（首次触发后第二次退出不再瓜分）、**门槛被拦不消耗机会**（首次 49% 被拦、第二次仍触发）、净值门槛正反例、5 次超时判负触发 vs 2 次超时不触发、扛旗勇士 20/50、基础得分=表现评估、称号 16 项全量减半核对、人屠已删除、**令子言杀 10 条**（3 正例：撞明后打另一侧 / 左右对称 / 吃过子力后打另一侧；7 反例：同侧、落点中线、令子中线、非次令子、令子未明、打令子本人、打的是另一家）+ 技巧表已无「骗令」）。两者都构造 `{layout, baseLayout, moves, baseMoves, orient, baseOrient}` 直接调 `computeTechScore`；事件步写成 `{color, type:'event', event:'...', no, timeouts?}`。改分值后**必须同步更新其中写死的期望值**（例如「万人之上 = 50（减半）」「在局3人各30」），否则会误报失败。
- **渲染类断言**：`run_medal.js`（**28 条**：真实局名次与奖牌一一对应、两人/三人/四人并列的顺延规则、负分排名、圆章数量与提示文案、**奖牌三段结构 `tm-ribbon`/`tm-disc`/`tm-shine` 齐备且数字在圆牌内**、四段动画关键帧与绑定、绶带/圆牌四色分色、深色覆盖、reduced-motion 兜底）、`run_titlebadge.js`（**28 条**：两局 titleLog↔徽章条数/步号/名称/分值一一对应且按步号升序、徽章所在行带 `mv-has-title`、事件行也挂徽章、CSS 含 3 段动画 + 深色覆盖 + reduced-motion 兜底）与 `run_e2e.js`（**14 条**：初始化无异常 + 两条数据源各自的 13 个面板非空 + 无 `undefined/NaN/[object Object]` + 奖牌数 = 卡数）。改 `renderTechScore()` / `renderMoveList()` 的 HTML 结构时都要跑。
- **不要对同一个文件并行发多个 Edit**：两条 Edit 落盘会互相覆盖，后写的那条基于旧快照，前一条改动被静默丢弃（症状：代码里引用了一个刚被删掉的 `var`，报 `ReferenceError: xxx is not defined`）。改多处时逐条串行发。
- **`techRuleRows()` 的 `+` 前缀**：只对纯数字（或数字开头且不含 `%` 的 `pts`）自动加 `+`；`表现评估` / `50% 平分` / `+20 / +50` 原样输出。

## 测试脚本维护

- 测试脚本放 `/tmp/`（不入库）。修改引擎/渲染后先更新测试断言（新基线、新用例），再跑回归。
- **注意 `/tmp` 会被系统清理**：第 1~4 步提到的 `/tmp/test_color_v2.js`、`/tmp/smoke_v2.js`、`/tmp/all_files_orient_v3.js`、`/tmp/shot_v2.js` 常已不存在；`/tmp/junqi_test/` 也**反复整批被清**（2026-09-13 早上丢过一次 `extract_engine.py`/`harness.js`/`run_timeout5.js`；2026-09-14 凌晨又丢光了 `run_ui.js`/`run_e2e.js`/`run_badge.js`/`run_tech.js`/`run_tech2.js`/`run_full.js`，只剩 `run_rules.js`/`run_titles.js`/`run_check_base.js`/`run_jgsdemo.js`/`shot_*.js`/`extract_engine.py`/`harness.js`）。**每次开工前先 `ls /tmp/junqi_test/` 确认存活**，不要假设脚本还在。**2026-09-15 实测整个 `/tmp/junqi_test/` 又一次被清空**（`run_titles.js`/`run_rules.js`/`run_medal.js`/`extract_engine.py`/`harness.js` 全丢）。task2 侧已固化到项目内 `.workbuddy/tests/`；index.html 侧的 `run_rules.js`/`run_titles.js`/`run_medal.js` 等下次用到时**建议一并固化**，别再重建第三次。

**重建配方**（照 `/tmp/junqi_test/` 的现成套路）：
- `extract_engine.py` — 用 `re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)` 取**最长**的 script 块写 `engine_raw.js`；比脆弱的 `/<script>(...)<\/script>\s*<\/body>/` 正则稳（页面后来新增了 `<head>` 内联脚本，老正则会误配）。
- `harness.js` — **共用 vm 桩 DOM 的模块**，`module.exports` 直接导出 vm 上下文对象，于是测试脚本既能调引擎函数又能覆写 `sb.document.getElementById`。
- `run_e2e.js` — 桩 DOM + 跑 `startAnalyze`。⚠️ **必须手动派发 `DOMContentLoaded`**：桩 `addEventListener` 是个空函数，`buildBoardGrid()` / 值表等**初始化期**渲染永远不会跑，`boardGrid`/`valTable` 会莫名其妙是空的（曾据此误判为回归）。做法：让 `document.addEventListener`/`window.addEventListener` 把 `DOMContentLoaded|load` 的回调收集起来，`vm.runInContext` 之后再依次调用。
- `run_medal.js` — 复用 `run_check_base.js` 的桩（`getElementById` **记忆化**，故可直接读 `elements.techScoreGrid.innerHTML`），前 14 条校验名次奖牌的类名/名次/并列规则，后 14 条校验奖牌三段结构 + 四段动画的 CSS 声明（用 `fs` 读源文件正则断言，比开浏览器快）。
- `shot_medal_ribbon.js` — 无头截图 `#techScoreGrid` 与逐枚 `.tech-head.medal-{g,s,b,i}`（浅/深两套），并回读 `.tech-medal`/`.tm-disc`/`.tm-ribbon::before`/`.tm-shine` 的计算样式确认动画名与配色真的生效。⚠️ 截图前先 `document.querySelectorAll('.toast,#toast,.tip').forEach(e=>e.remove())` 去掉「已载入示例复盘」提示条，否则会盖住卡片。
- `run_titlebadge.js` — 同上桩，直接读 `elements.moveList.innerHTML` 抓 `<span class="mvtag tech">` 徽章，与 `techScore.titleLog` 对账；并用 `fs` 读源文件正则断言 CSS 动画声明（比开浏览器快，能进回归流水线）。事件行用例：临时把 `techScore.titleLog` 改指向首个 `type==='event'` 的步 → `renderMoveList()` → 断言徽章出现 → 还原。
- `shot_tech.js`/`shot_skills.js`/`shot_full.js`/`shot_badge.js` — puppeteer-core 无头截图（`page.on('pageerror')` 用于确认浏览器零错误）。⚠️ 截图 `#moveList` 这类**内部可滚容器**时：不要用 `row.scrollIntoView()`（它会连带滚动整个文档，之后按 `getBoundingClientRect()` 算出的 clip 就跑到视口外、只截到页头），正确做法是 `list.scrollIntoView({block:'center'})` 把容器滚进视野后**只设 `list.scrollTop`**，再直接用 `(await page.$('#moveList')).screenshot()` 走元素截图。想放大看细节就把 `deviceScaleFactor` 提到 4~6，并对**整行**（`.mv-has-title`）而非徽章本体截图（徽章在 `align-items:baseline` 的 flex 行里会溢出容器盒，元素截图会被裁掉一半）。
- 有条件时把这套 harness 固化到项目目录里，避免每次重建。
- **e2e 基线**（`DEMO_TEXT` = `junqi2026_6_24_16_22.jgs`，2026-09-13 实测·删「骗令」+每局一次逃跑瓜分后）：拆分 = 基础得分(表现评估) + 称号 + 规则 + 技巧 → 绿 = 46+0+0+15 = **61**；黄 = 18+0+0+15 = **33**；蓝 = 33+0+20+22 = **75**；紫 = 1+0+186+10 = **197**。**注意基础得分来自表现评估（五维评分，会随评估公式变动）、`骗炸` 分值 = 被炸掉的己方棋子价值（`VAL[ap]`）、`逃跑瓜分` 按剩余净值与在局人数浮动**，所以别把这些当固定基线断言，只做「能跑通 + 各项加总等于总分」的校验（`/tmp/junqi_test/run_check_base.js`）。本局门槛实况（可在 `escapeSplit` 插桩打印）：蓝 剩300/739=41%、紫 剩295/739=40% 均被门槛拦截；黄 剩371/739=50.2% 通过，但队友绿已被扛旗出局，在局者唯余紫 → 紫独得 `round(371*50/100)` = **186**。（本局只有黄一次合格离场，故「每局最多一次」不改变分数。）
- **`.jgs` 演示局（`#btnLoadDemo` = `junqi2026_6_22_16_38.jgs`，75 步，方位 绿down/黄up/蓝right/紫left）**：黄(69 步，剩净值426/739=58%)先主动离场且过门槛 → **本局唯一一次**逃跑瓜分，在局 3 人（绿/蓝/紫）各 +`round(426*50/300)`=71；绿(75 步)随后离场时 `escapeDone` 已锁定 → **不再瓜分**（这正是「每局最多一次」生效的直观样本）。终局技术积分：绿 99 / 黄 45 / 蓝 173 / 紫 151。（两局示例均未触发「令子言杀」。）
- **注意页面里有两个不同的示例**：`#btnLoadDemo` 载入的是 `.jgs` 演示（`junqi2026_6_22_16_38.jgs`，玩家 木木/江湖人称小武哥/%无声仿有声%/暴暴寒），与 `DEMO_TEXT` 不是同一局。用浏览器截图核对分数时不要拿 `DEMO_TEXT` 的基线去比。
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
