---
name: qq-junqi-replay
description: 开发和迭代 QQ 四国军棋复盘分析器（单文件 HTML 工具）。This skill should be used when the task involves parsing .jgs 复盘文件（QQ四国军棋二进制复盘）、文本复盘格式（v2.0 复盘文本）、玩家颜色/方位映射、逆时针行棋序、棋子价值表、行棋得失统计、回放渲染、或对 index.html 复盘分析器做任何修改与回归验证。也覆盖**联众军棋 `.JQH.TXT` 文本复盘**（GBK 编码 / 17×17 字符栅格 / **顺时针**行棋序 / 映射A 坐标 / 非工兵触雷后地雷保留）与**「玩家表现评估」五维公式的数据校准**（v1→v3 方案、AUC 与玩家级 Spearman 验证、共线与维度退化诊断），以及用大师复盘为 AI 机器人打地基。Covers the .jgs binary format (0x20 玩家块/0x19B 指令区/0x5F 棋步), 方位双射择优 (pickOrientByScore + orientSelfCheck 行棋自洽率), 三级回归工作流 (Node 引擎测试 + jsdom 冒烟 + 真实 Chrome 截图 + 6 个真实 .jgs 回归)。亦覆盖实战桥的**人机对战**（1 人类 + 3 AI 下四暗军棋、AI 走 PIMC 深核）与 **AI 布阵风格四档**（稳/攻/龟/闪电，按联众真实布局库分档采样、默认轮换）及**监督模仿网络 + PIMC 先验**。
---

# QQ 四国军棋复盘分析器开发

## 概述

本技能用于迭代 `/Volumes/me/ai学习/四国军棋/qq军棋复盘分析/` 下的单文件 HTML（CSS+JS 全部内联，无外部依赖）：`index.html`（主文件，含竞技技术积分）、`index_task2.html`（同构副本，无技术积分）、`index_task3.html`（自 task2 拷贝的任务起点）。**2026-09-21 晚起「残局研究」已整体回灌到三页** —— `index_task2.html` 与 `index_task3.html` 现在完全同构（diff 0 hunk），`index.html` 只比它们多技术积分模块。该工具导入 QQ 四国军棋 `.jgs` 二进制复盘文件或 v2.0 文本复盘，做 17×17 棋盘回放、行棋得失统计、胜负手 TOP3、关键事件、战役明细、子力净值曲线、评级，并可**手动摆残局推演**（见「残局研究」一节）。

核心能力：`.jgs` 二进制解析、方位↔颜色动态推导、渲染联动、三级回归验证。

## 关键约定（迭代时不可破坏的基线）

- **玩家颜色**：绿/黄/蓝/紫 四色，**按复盘文件方位动态确定**，不写死「上=绿、下=黄、左=蓝、右=紫`。`DEFAULT_ORIENT`（无证据时的回退）仍为 `{绿:'up', 黄:'down', 蓝:'left', 紫:'right'}`，但**2026-08-18 修正移动颜色编码后，6 个真实 .jgs 经几何推导（现由 `pickOrientByScore` 做双射择优）的实际方位统一为 黄=up / 绿=down / 紫=left / 蓝=right**（对应玩家 大丈夫=黄=上、暴暴寒=绿=下、Ella乐乐=紫=左、习掼叻=蓝=右）；旧基线 绿=up/黄=down 是旧颜色数组导致的 180° 旋转错误结果。非标文件仍按几何推导。
- **方位名称**：上家/左家/下家/右家；**逆时针行棋序 = 上→左→下→右**。
- **棋子标识**：棋子上用单字（司/军/师/旅/团/营/连/排/炸/兵/雷/旗），各玩家棋子统一按玩家色区分，雷/炸不特殊着色。
- **棋子标记（右键盖牌棋子，2026-09-22 新增 · 三页共有）**：右键一枚**已盖牌**的棋子 → 棋盘中央浮出半透明标记面板（19 个瓦片：`司军师炸/旅团营雷/连排兵旗/! ? 大 小/一 二 三`）→ 左键点一个 → 面板消失、该子上显示该标记；再右键该子即进入「改标记 / 清空标记」。⚠️ **标记按「棋子身份」存（`pieceMarks['初始行,初始列|颜色']`），不能按格子存** —— 复盘里棋子会走，按格子存会留在原地不跟着子走；只在盖牌态显示（明棋时叠在真兵种上会误导）。详见「复盘回放 · 棋子标记」一节。
- **行棋起点**：红框 + 箭头自动指向行棋方向（atan2 旋转）；终点框。**两个文件现均为 QQ 军绿棋盘，高亮用 `--highlight-from:#ff4d3d`（红）/`--highlight-to:#ffd54f`（亮金）；旧的深黑 `#1a1a1a` 只在早已废弃的米色棋盘上可见。** 高亮类名是 **`highlight-from` / `highlight-to`**（不是 `hl-*`），加在 `#cell-<row>-<col>` 上，`curMove.from/to` 是 `[行, 列]` 顺序。
- ⚠️ **中间格箭头（红色轨迹）必须走真实行棋路线**（2026-09-20 修）：唯一入口是 `movePathCells(from, to, blocked)`，**绝不能用「曼哈顿步数 + 线性插值」猜中间格** —— 那样斜走一格会凭空多出一个落点，铁路拐弯步会画成一条斜穿棋盘的阶梯，箭头大量落在非铁路格、甚至四角空白区（视觉上「轨迹跑出了棋盘」）。全库 34461 步实测四类：
  - ① 直走 1 格（11178 步）→ **无中间格**；② **斜走 1 格（8080 步）→ 无中间格**（行营「米」字斜线、九宫四角弧形铁道都是**一步**，棋盘上就是从营心到斜角格心的直线，中途没有落点）
    - ⚠️ 这 8080 是按**起终点几何斜跨**统计的，**不等于**棋盘上真有斜线：其中 **2 步是工兵**的铁路 L 形（黄工兵 `J6→K6→K7`、绿工兵 `J12→K12→K11`，K6/K12 为共同铁路邻居）—— 严格说这 2 步的中间格是 K6/K12。目前 `movePathCells` 会把它们当「斜走 1 格」处理（轨迹画成一条斜箭头），占 2/34461 步，视觉上无影响，**未做特殊处理**；若日后要修，判据是「工兵 + 终点 ∈ `railReachSet(from,{},true)` + 起终点不正交」时改走铁路 BFS。
  - ③ 直行多格（10902 步，同行/同列）→ 整段在铁路上就取该线上的逐格；**整段不在铁路上、但两端都在铁路上时必须沿铁路绕行**（如 `(7,11)→(7,1)` 要绕 v11→h6→v1 —— **行 7 根本没有铁路**，直接横穿会落在 8 个非铁路格上）
  - ④ 斜向多格（4301 步）→ **100% 两端都在铁路上**，即「沿铁路拐弯」→ 铁路网 BFS 最短路。邻接 = 四方向 `railLinked` + `RAIL_ARC_LINKS` 四条弧形铁道；⚠️ `railArcLinked` 判的是**斜向相邻**，**不在 `railNeighbors` 的四个正交候选里，必须单独补一段**，否则弧线永远走不到。
  - ⚠️ **轨迹还必须「畅通」——不得穿过任何棋子**（同日再修）：工兵飞棋与非工兵在铁路上的长距离行驶都要求整条轨道无子，所以第三个参数 `blocked`（`{'r,c':1}` 占用表）**必须传**。新增 `railPathThrough(r1,c1,r2,c2,blocked)` 在 BFS 里把被占的**中间格**判为不通，**终点格例外**（那是落点或被吃目标）。全库 15203 步多格移动里有 **597 步**的几何最短路会被棋子挡住而必须改道。
  - **障碍表在 `renderBoard` 里就地构造**：入参 `layout` 是「**该步之后**」的布局，反推该步之前 = `全盘棋子 − 终点 + 起点`。⚠️ 这条反推与「该步之前」的真实 `snapshotAt(n-1)` 在路径判定上**完全等价**（全库 15203 步实测零差异），**不要**为此再跑一遍 `snapshotAt`（那是 O(n) 的重复模拟）。
  - 降级链：畅通 BFS → 无解则 `railShortestPath`（几何最短路）→ 再无解则退回直线（宁可画出来也不留空）。⚠️ `railPathThrough` 不可达返回 **`null`** 而非 `[]` —— `[]` 是 truthy，`if (via)` 会把「空路径」误当成功。
  - ⚠️ `railShortestPath` 回溯出的 `full` **本就不含起点**（`while` 在 `k2===startKey` 时停），只需 `full.pop()` 去终点；多写一个 `full.shift()` 会吞掉第一个中间格（路径凭空少一格）。起点大箭头 `move-arrow` 的旋转角取 `pathCells[0]`，**不是** `from→to` 的直线角（拐弯时两者方向完全不同）。
- ⚠️ **「某局显示 205 步 / 未分胜负 / 走棋棋子混乱」= 输入是旧版导出的 `.txt`，不是解析器 bug**（详见「复盘数据自洽性自查」一节）。`.jgs` 路径实测完全正常，**别去改解析器**；三页已加 `auditReplaySelfCheck()` 自动识别并给出常驻警告。
- ⚠️ **扛旗不需要「军旗亮出」，也不需要该方司令先阵亡**（2026-09-24 坚哥指出 + 全库铁证定案）：**任何一方只要走到对方军旗格即扛旗、该方立即出局**。「司令阵亡 → 军旗亮出」只是**显示层**规则（见「明棋/暗棋」节），**不是可攻击的前置条件**。铁证：全库 2379 局 / 1850 次扛旗事件中 **134 次（7.2%）发生在被扛方司令尚存时**（例：`right司令 扛 down 方军旗`、`up排长 扛 left 方军旗`）。⚠️ 本页 `resolveMove()` 的 `flag` 分支从来就没有这个前置检查 ⇒ **页面口径一直是对的**；但 **Python 侧（`.workbuddy/ld/`）曾按误解加了 `legal_moves(flag_locked=)`**，把「司令未亡方的军旗」设成不可攻击 —— 会让 AI 平白少掉 7.2% 的取胜路径、并误判搜索终局，**已删除**。写合法走法枚举 / AI / 搜索时**不得**再加这个条件。
- **音效（2026-09-16 起为内嵌 WAV 采样）**：6 条 wav 以 base64 写在 `var SFX_B64` 里，`playSound(type)` 类型名不变。口径：`move`→移动走子 / `eat`+`dig`→吃子 / `killed`+`mine`+`bounce`→撞子被反吃 / `cmdr`→司令阵亡亮旗 / `both`+`bomb`→兑子被炸 / `flag`+事件步 `evKind==='defeat'`→扛旗投降自杀 / `pass`→保留合成双音兜底。**「司令阵亡」靠 `resolveMove()` 打的 `event.cmdr` 结构化标记，事件步靠 `event.evKind`，两者都不许用文案正则判**（详见「音效系统」一节）。
- **棋盘中间**：9 个兵站 = 中央九宫格交叉处（行 6/8/10 × 列 6/8/10），用**与普通行棋点同款的「回」字方块**（`.cell.station::before`，只是把蓝紫带换成 `--station-ring`）。⚠️ **中央 5×5 里除这 9 格以外的 16 格是 `BOARD_LAYOUT` 的 `R`（铁路通过点，不可停留）**，加 `.cell.rail-only` **不画方块也不画公路线**（详见「棋盘视觉规格」章的 `R` 一节）。四角大本营 8 格（4 家 × 2）用**单圈粉环** `.cell.hq::before`（外径 41.6%、环宽 7.6% `--hq-ring`）；行营 20 个用**单圈橙环** `.cell.camp::before`（同尺寸 `--camp-ring`）。⚠️ **三者一律走 `::before` + `inset`/`box-shadow` 环，不再用 `::after`、不要用 `border` 直接画在 `.cell` 上**（会撑开格子）；有子时由 `.cell.occupied::before{display:none}` 统一压掉。
- **棋子价值表**：司令100 军长80 师长60 旅长45 团长35 营长25 连长18 排长12 工兵8 炸弹35 地雷15 军旗0。
- **`.jgs` 玩家块颜色字节 ↔ 颜色**：`BYTE_COLOR=['黄','蓝','绿','紫']`（0=黄 / 1=蓝 / 2=绿 / 3=紫），四块固定按 (0,1,2,3) 顺序排列（全库 191 份无一例外）。6_21 实测：字节0=大丈夫、1=习掼叻、2=暴暴寒、3=Ella乐乐，己方 `0x0F`=2=绿=暴暴寒。
  - ⚠️ **2026-09-20 更正（此前写法已过时，勿沿用）**：本文件曾称「颜色字节 0=黄=**下** / 2=绿=**上** 已实测验证」——那是 `QQ2DIR` 这个**仅用于平票兜底的先验常量**的值，并非文件实际方位。**方位一律由几何推导决定**（`pickOrientByScore` 在 24 个「颜色→方位」双射里取行棋自洽率最高者）。实测全库 191 份 `.jgs`，推导结果**恒为 绿=下、黄=上、蓝=右、紫=左**（0 份为 绿=上），即文件只存在**一个固定绝对坐标系** `{0:'up', 1:'right', 2:'down', 3:'left'}`。`QQ2DIR={0:'down',1:'left',2:'up',3:'right'}` 与真实坐标系恰好相差 180°，因权重仅 1e-6，正常谱永远轮不到它起作用。
  - **唯一例外（1/191）**：`junqi2025_3_6_21_14.jgs` —— 全局只走 1 步就 `0xF5` code=5 b=6（有玩家逃跑）的废谱；只有黄有行棋证据，蓝/绿/紫 的 `orientSrc` 均为 `byte`，方位由 `QQ2DIR` 先验裁定，导致 蓝/紫 互换（= 真实坐标系的镜像）。**若要一并修正：把 `QQ2DIR` 改为 `{0:'up',1:'right',2:'down',3:'left'}`（1 行），必跑 `run_orient.js`（65 项）+ 用 `cross_tab` 复扫全库，预期偏离数 1 → 0。当前有意不改：正常谱零影响，收益/风险不成比例。****棋步颜色编码（b1 位4-3）是「有状态状态机」，不是固定映射，必须由玩家块颜色字节派生且处理玩家离场**：开局 4 家阶段，`bits=(b1>>3)&3` 的取值 = 玩家块颜色字节 QB 的「(QB+1)&3」偏移，即 bit=0→块1、1→块2、2→块3、3→块0，故开局阶段代码等价 `BYTE_COLOR[(bits+1)&3]`（等价 `['蓝','绿','紫','黄'][bits]`）。**但当某玩家「自杀战败/退出」（`0xF5` 事件 code=3/4）离场后，该家的颜色位由颜色环中其「后继者」继承**（环序=初始位升序 `RING=['蓝','绿','紫','黄']`，跳过已离场者，遇全离场则不更新）：
- 蓝离场(QB=1) → 后继者 绿 继承位0（绿原自身位1变空洞）；6_21 实测蓝离场后 bits=0→绿、bits=2→紫、bits=3→黄 全对。
- 黄离场(QB=0) → 后继者 蓝 继承位3。
- 绿离场 → 后继者 紫 继承位1；6_24 多玩家连续离场时，离场者被跳过、取下一个存活后继者（蓝离场→绿得位0，黄离场→绿跳过已离场的蓝得位3）。
实现：`extractMoves` 内维护 `RING/bitOfColor/colorOfBit/active`，`applyExit(ev)` 在 `0xF5` 事件(code=3/4)时更新映射，后续棋步按新状态机解码。**旧固定写法 `BYTE_COLOR[(bits+1)&3]` 玩家离场后会串色**（6_21 蓝离场后 bits=0 被误解为蓝、真值是绿，26 处不一致），此 bug 已于 2026-08-18 修正（6 文件 719 步 0 不一致）。渲染仍必须走动态推导（`pickOrientByScore`），不得依赖默认。
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
- **对局信息/玩家卡 UI**：对局信息固定五项=对局时间（`parseTimeFromName` 从文件名解析 junqi2026_6_24_16_22 → 2026年6月24日16时22分，优先 meta['时间']）→ 人数 → 步数 → 结果 → 来源文件；不显示己方视角与方位映射。玩家卡顶部名字+**「己方」徽章**+胜/负徽章+方位·步数，中间两行统计，底部步数占比条。**「己方」徽章（`.tag.own`）标出复盘录制者所在颜色，与胜负徽章并列、与当前视角偏好无关**（浅色主题 `background:var(--accent2)` `#8b4513` 配白字；深色主题须补 `html.theme-dark .player .tag.own{color:#231d10}`，否则白字落在 `#e6c667` 浅金底上不可读）。战果/被俘一览 chips 按子力价值从大到小排序。
- **胜负判定 = 按【最终存活】，不得再用子力净值（2026-09-10 改；2026-09-19 修掉「扛旗优先」）**：`teamSplit()` 按方位对家分队（上/下=UD，左/右=LR），且**要求恰好 2:2，否则返回 `null`**（2026-09-20 加，防止方位解析异常时给出 3:1 的荒谬分队）；`getWinTeam()` 只剩三条 —— ① 某队两人皆 `alive=false` 而另一队尚有存活 → 存活队胜；② 两队全灭 → 比较 `analysis.defeatedAt`，**最后离场的一方胜**；③ 其余 → `null`（未分胜负）。判不出胜负时 `getResultText()` 返回 `'未分胜负'`（只有 meta 明确写「和局/平局」才沿用），玩家卡不贴胜/负标签（和局贴 `tag draw`「和」）。
  - **⚠️ 扛旗不是终局判据（2026-09-19 修掉的真 bug，最容易再犯）**：旧实现曾有一条「① 出现 `res.type==='flag'`（扛旗）→ 扛旗方所在队**立即获胜**」，**是错的** —— 四国军棋里扛走敌方军旗只让【被扛家】出局（`resolveMove` 的 `flag` 分支已 `alive[defender]=false` 并清子），**其队友仍可继续作战、对局并不结束**。190 个真实 `.jgs` 里 **23 个**存在「扛旗之后仍在行棋」，其中 **13 个**是扛旗方随后自己两人全灭、对方仍有存活，却因那条规则被判胜。用户上报的 `junqi2025_3_28_20_4.jgs` 就是典型：蓝扛走黄旗（第160步）后紫、蓝相继自杀战败（167/168 步），绿存活 → 正确结果是 **绿黄队胜**，旧代码却判蓝紫队胜（净值 +349 的绿被判负、−95 的蓝被判胜）。
  - 另 8 个是「扛旗后被扛家的队友仍在、对局又打了 100+ 步却再没人出局」—— 这些文件的 QQ 结束事件 `b=2`（和局），旧代码判「扛旗方胜」、新代码显示「和局」，与 QQ 一致。
  - **权威判据在结束事件里**：`.jgs` 的 `0xF5` code=5（结束）的 `b` 字段就是 QQ 的官方结论，`jgsToText` 里映射为 `{2:'和局', 4:'一方战败', 6:'有玩家逃跑'}`。注意 `'一方战败'` 只是占位描述（说不出是谁赢），**不能当结论直接显示**；`getResultText()` 会过滤掉它改用判定的胜队。
  - **`renderSummary()` 的「本局结论」也必须用 `getResultText()`**，不能直接拼 `meta['结果']`（否则页面会显示「一方战败」这种没信息量的词）。
  - **旧实现「净值之和大的一队为胜」已删除**（2026-09-10）。
  - **改这条规则必须跑 `run_winrule.js`**（41 项，覆盖两个引擎）—— 它把「扛旗方随后全灭」这个 case 和 3 个真实文件钉死在断言里。
- **对局信息对阵头（2026-09-10 改）**：`#infoGameTitle` 不再四人平铺 `vs`，而是**按队分组**——队内用 ` +` 连接、两队间用 ` vs ` 连接，形如 `真实的背后 +↘ゞ钟情 vs 爆炸糖糖 +利物浦＆三拳`。两队先后与队内次序**均按 `COLOR_ORDER=['绿','黄','蓝','紫']` 座位顺序**（按各队第一名在 COLOR_ORDER 的 index 排序），以保持与原先四人顺序视觉一致；`teamSplit()` 返回 null 时回落原四人 ` vs ` 全排。
- **四方阵地左下角外 ID 标签**：四个标签分别在四个阵地左下角外的空白角区/边缘——上 → `cell(5,5)` 右锚点向左延伸、左 → `cell(11,0)` 左锚点向右延伸、右 → `cell(11,11)` 左锚点向右延伸、下 → `cell(16,5)` 右锚点向左延伸（下阵地左下角 (16,6) 左侧空白格，与上方位对称；**不再是棋盘底部外的 `#selfLabel`**）。字号 12px 加粗、颜色 = `PC_COLORS[replay.dirToColor[dir]]`（随视角自动映射）、底色 `rgba(250,247,238,.88)` + 1px 描边 + `white-space:nowrap` + `z-index:3` + `pointer-events:none` 保证不遮挡棋子。`renderBoard` 末尾调用 `renderCornerLabels`（每步重建，因 renderBoard 清空 cell innerHTML）。`spots` 数组定义在 `renderCornerLabels` 内。
- **关键事件步（自杀/战败/退出）——新增于 2026-08-18，必须保留**：`.jgs` 中 `0xF5` 事件指令穿插在 `0x5F` 棋步指令之间，**不占独立移动步**。事件 `b1`=02超时/03自杀战败/04退出/05结束，`a`=玩家颜色字节（`BYTE_COLOR[a]`），`b`=相关参数（`b1=05 && b=4` 为「结束」事件，不输出为玩家步）。为让文本步数与真实对局一致、避免后续步数偏差与颜色串位，必须把玩家事件作为独立步骤纳入：`extractMoves` 用 `seq` 数组保留「指令流顺序」（move/event 交错）；`jgsToText` 遍历 `seq`，事件步输出 `stepNo. 颜色 事件名`（如 `240. 蓝 自杀战败`、`242. 蓝 退出游戏`——新映射下 6_21 的习掼叻=蓝，即用户问题2所指的第240/242步）并从棋盘清除该玩家全部棋子；`parseReplay` 用正则 `^(\d+)[.、]\s*[蓝红绿灰黄紫]\s*(军旗被扛，战败|自杀战败|战败|退出游戏|超时判负|退出|判负)` 识别事件行并纳入 `moves`（`type:'event'`，无 from/to）；`analyze()` 与 `snapshotAt()` 对事件步标记 `alive[evColor]=false; defeatedAt[evColor]=mv.no; removeAllPieces(layout, evColor)`；`renderMoveList`/`gotoStep`/`renderBoard`/`cloneMove`/`rotateView`/`topClutch` 均需对 `type==='event'`（无 from/to）做分支，避免 `mv.from[0]` 崩溃。**事件步清子后，战败玩家后续残留的「幽灵步」（原始文件仍编码为该色）会被 resolveMove 优雅跳过（起点无子→error），不污染统计；`trackTurnSkip` 对已战败玩家直接 return。** 移动步基线（318/22/67/72/35/205）不含事件步；文本/二次导入总步数 = 移动步 + 玩家事件步数（结束事件不计）。
- **军旗被扛战败事件文本修正（2026-08-18 新增）**：QQ 在棋子扛走某家军旗后，会紧接着为该家发一个 `0xF5` code=3 战败事件；此时该事件本质是「军旗被扛，战败」，而不是「自杀战败」。`jgsToText` 用 `justFlagTaken` 记录「上一步是否刚扛了某家军旗」，当紧随其后的 code=3 事件的 `evc===justFlagTaken` 时输出 `军旗被扛，战败`，否则输出 `自杀战败`（每个 move 步重置 `justFlagTaken=null`）。**`parseReplay` 事件正则必须含 `军旗被扛，战败`**（否则该行无法被识别为事件步，会导致步号错位）。实测 6 文件：6_21 的321紫、6_22_14_57 的23黄、6_24_16_22 的200蓝 均为「军旗被扛，战败」；其余自杀（6_21的240蓝、6_22_15_4的67绿/70黄、6_22_16_38的69黄/75绿、6_24_14_24的35绿/38黄、6_24_16_22的206黄/208紫）仍为「自杀战败」。此修正同时改到 `parseReplay` 正则与 `jgsToText` 两处，需同步。
- **Puppeteer 验证陷阱**：`page.setContent` 模式下 localStorage 抛 SecurityError（无 origin），`loadViewPref` 会回退默认 `self`——视角/偏好相关断言需用 `page.goto('file://...')` + `evaluateOnNewDocument(()=>{window.LA={init:()=>{}};})` 桩掉 51.la，否则会有 `LA is not defined` pageerror 且 localStorage 不可用。
- **布局正确性判定方法（强标准）**：对真实 .jgs 文件做**行棋结果位一致性验证**——用引擎推演每步结果类型（移动/吃/被吃/同尽）对比文件 res 位（b1 位1-0：0/1/2/3）。镜像方案错误时一致率通常 70%~95%；正确方案应 ≥99%（6 文件实测 99.5%~100%）。
- **视角旋转（以某玩家为下家）**：QQ 客户端习惯「己方视角」——自己永远在下家。网页默认以「己方」为下家整体旋转（布局+行棋坐标+方位标签），其余三家按复盘相对方位保持。提供「绝对方位（文件原始）」切换。棋盘地形 90° 旋转对称，旋转后军旗仍落对应方位大本营。
  - **「己方」颜色的唯一来源 = `ownColorOf(replay)`**（2026-09-20 抽出，勿再各处重写）：`.jgs` 取文件头 `0x0F` 颜色字节 → `BYTE_COLOR[mc]`；文本复盘取 `meta['己方']`。`viewColorOf` 的 `self` 分支直接 `return ownColorOf(replay)`。
  - ⚠️ **`replay.viewColor` 语义 = 「当前主视角颜色」，不等于「发生过旋转」**。旧实现在 `rotateView` 里 `if (!base || base === 'down') return false;` 提前返回，**己方本就位于棋盘下方时（如己方=绿，全库占比 54/191）`viewColor` 留在 `null`**，于是 `syncViewSelect` 走 else 分支，出现「下拉选着『己方视角』、提示却说『当前为文件原始方位』」的自相矛盾（toast 同错）。**修法：在 `rotateView` 里先判 `if (!base) return false;`，紧接着 `replay.viewColor = viewColor;`，再判 `base === 'down'` 时提前返回**——旋转与否交给 `rotK` 表达（0=无需旋转）。
  - 视角提示与 toast 必须**分三态**：`viewColor && rotK` → 「…为下家，棋盘已整体旋转」；`viewColor && !rotK` → 「…为下家（文件原始方位即是，无需旋转）」；`pref.mode==='abs'` → 「当前为文件原始方位（绝对方位）」；其余 → 「当前为文件原始方位」。
  - ⚠️ **视角偏好的解析必须唯一 = `resolveView(replay, pref)`**（2026-09-20 修）。它返回 `{mode:'abs'|'self'|'player', color}`，`viewColorOf` 只是取 `.color` 的薄包装。**下拉选中值（`syncViewSelect`）与实际旋转（`startAnalyze` / `applyViewAndRerender`）都必须走它**——旧实现两处各写一套判断，于是出现：偏好记着「以某某为下家」，换了一盘棋、该玩家不在本局时 `viewColorOf` 返回 `null` → 渲染走绝对方位（**己方跑到棋盘上方**），而 `syncViewSelect` 的兜底把下拉显示成「己方视角（己方在下家）」→ **显示与实际自相矛盾**（用户截图即此）。偏好存在 localStorage、四国又是随机匹配对手，**换棋谱必踩**，属高频路径，不是边缘场景。
  - `resolveView` 的两条回退：① `player` 匹配不到本局玩家 → **退回己方视角**（不是 `null`）；② 连 `ownColorOf` 都返回 `null`（复盘缺「己方=」信息）→ **老实走绝对方位**，且 `syncViewSelect` 要显示 `abs` 并提示「未识别到己方（复盘缺少「己方=」信息），当前为文件原始方位」，不要谎称己方视角。
  - 改动后自查口径：`resolveView(null, {mode:'self'})` 必须返回 `{mode:'self', color:null}` 且不抛（页面尚未导入棋谱时 `syncViewSelect` 会被调用）。
  - **术语约定（勿"顺手改正"）**：本项目里「上家/下家/左家/右家」= **屏幕方位**（`COLOR_INFO[c].dir = DIR_CN[orient[c]] + '家'`，`DIR_CN={up:'上',down:'下',left:'左',right:'右'}`），**不是**军棋口语的"下一个出牌者"。所以「以 XX 为下家」= 把 XX 转到棋盘下方，文案正确，不要改成「下方」。
- 页面必需要素：SEO 简介（含 JSON-LD WebApplication）、底部备案（赣ICP备15001421号 + 赣公网安备36100002000207号）、51.la 流量统计。
- ⚠️ **署名是「分支差异项」，三页现在各说各话（2026-09-22 现状，别顺手统一）**：
  - `index.html`：页头 badge = `设计制作：暴暴寒（7z） | 规则赋能/优化：姜朕熙（B站：老姜甄鉴）`；页脚 © = `© 2026 暴暴寒（7z） | 规则赋能/优化：姜朕熙（B站：老姜甄鉴）`。
  - `index_task2.html` / `index_task3.html`：页头 badge = `以此致敬永远的尖刀师！设计制作：☆→小寒（7z）`（2026-09-22 坚哥指定改稿）；页脚 © 仍是原文 `© 2026 热心市民小寒（7z） · 仅供学习交流使用`（**本次没动**）。
  - ⇒ **改署名只改被点名的那一处**：锚点必须带「设计制作：」前缀，否则会连页脚 © 行一起改掉（两者同含「热心市民小寒（7z）」）。

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

## 手机模式（响应式 ≤720px，2026-09-23 新增 · 三页共有）

> 坚哥需求：「给网页增加手机模式，手机浏览器打开会自动适应。」
> 全部改动集中在**一个** `@media (max-width:720px)` 块（+ 全屏复盘窗注入串里的一份同款），
> **桌面端（>720px）零影响**：所有既有测试都在 1500×1050 跑，天然当回归守卫。

### ⚠️ 判断「有没有适应」的唯一硬指标：布局视口有没有被撑开

改前手机打开时 `window.innerWidth = 635`（视口 390）。原因：内容最小宽 635px（由棋盘卡撑出
564 棋盘 + 边距），**Chrome 会把布局视口撑到内容宽、再把整页按 390/635 ≈ 61% 缩着给你看**。
于是「页面无横向溢出」是**假绿**（`scrollWidth - innerWidth = 0`），正文 14px 屏幕上只剩 8.6px。
⇒ 判据必须写成 **`innerWidth === 视口宽`**，不能只看溢出量。Puppeteer 侧要
`setViewport({..., isMobile:true, hasTouch:true})` 才复现这条行为。

### 做法：一个 `--cell-size` 旋钮 + 一批「写死 px 改等比」

1. **`--cell-size: min(32px, calc((100vw - 74px) / 17))`**。74px = 页面/卡片/棋盘容器全部水平
   内边距与描边（16+2+16+20）——`20px 坐标槽 + 17 格` 必须 ≤ `100vw - 74px`。
   棋盘上所有走 `calc(var(--cell-size) * 比例)` 的图形（行棋点/行营/大本营/铁路/白枕木/
   弧形铁道/SVG 叠加层）随之同比缩小，**结构上不可能错位**。390px → 格子 18.58px；720px → 32px（封顶）。
2. ⚠️ **棋盘上有一批写死 px 的元素必须一起改成等比**，否则格子一缩它们就溢出格子：
   `.piece` 30×25/字号 15 → `.9375/.78125/.46875 × --cell-size`、`.piece-mark` 字号 15 →
   `.46875`、`.mk-bars i` 13×2 → `.40625 × --cell-size` / 1px、`.corner-label` 11px/行高17 →
   `.34/.53`、`.move-arrow` 20 → `.625`、`.path-arrow` 13 → `.40625`。
   **比例一律取「桌面值 ÷ 32」** ⇒ 手机棋盘 = 桌面棋盘的**等比缩小版**（测试就是这么比的）。
3. ⚠️ **`#boardWrap` 的 `padding:10px` 绝对不能动** —— `.board-svg{position:absolute;left:20px;top:20px}`
   是硬编码、与棋盘容器内边距耦合；改内边距铁路叠加层就会和格子错位。省那 12px 不值得。
4. 卡片/表格/页头/间距降一档（`.card{padding:10px 8px}`、`.stat-table` 11px + 单元格 4px/3px、
   `.eval-grid` 单列、`#moveList{height:min(56vh,300px)}`）；`#viewSelect{font-size:16px}` 是因为
   **iOS 对 font-size < 16px 的表单控件获得焦点会强制放大整页**。
5. 棋子上的长按 = 右键打开标记面板：`.piece,.cell{-webkit-touch-callout:none}` 压掉系统菜单。
6. **标记面板**：手机分支把 `.mark-panel{--mk-scale}` 由 `.5` 提到 **1.25** ⇒ 瓦片 34.8px
   （桌面缩到 19px 格子时瓦片只剩 24px，手指点不准）。面板 173.7×254.1 仍完全落在 336px 棋盘内。
7. **残局研究**：原布局是「60px 托盘 + 17格 + 60px 托盘」三列，手机上必然横向溢出，且
   `#studyOverlay.on{justify-content:center}` + `overflow:auto` 会把左侧滚不到。手机分支改为
   `.study-stage{display:flex;flex-direction:column}`、托盘 `flex-direction:row`（上/左/右/下各占整行）。
8. **用时（步数）占比条**：窄段（7% = 24px）原来把「文明用语 7%」折行、下半行被 `overflow:hidden`
   切掉。改法 = 生成时把名称/百分比各包一层 `<span class="tn|tp">` + 手机分支
   `.timer-bar>div{container-type:inline-size}` + `@container (max-width:64px){.timer-bar .tn{display:none}}`
   （纯 CSS 没法只隐藏文本节点的一半；不支持容器查询的浏览器退化为「裁切」= 改前行为）。
   ⚠️ flex 容器**不渲染纯空白文本节点** ⇒ 名字与百分比之间原来的字面空格换成
   `.timer-bar>div>span.tp{margin-left:.25em}`（这条写在**基础 CSS**里，桌面端视觉不变）。
9. **全屏复盘窗**：`openReplayWindow()` 注入的 `<head>` 原本**没有 viewport meta** ⇒ 手机上按
   默认 980px 布局视口渲染、整页缩着显示。必须补
   `<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">`（注意在源码里这串
   位于 JS 字符串内，引号写作 `\"`）；它的 `:root{--cell-size:46px}` 与写死的
   `.piece{43×36}` 也要在注入串里补一份同款 `@media` 覆盖（媒体查询与 `:root` 同特异性，
   靠**源码顺序**取胜 ⇒ 覆盖规则必须排在 `:root{--cell-size:46px}` 之后）。

### 测试
`verify_mobile_20260923.js`（**55 项**，默认 `index_task2.html`）：源码层 4 项（viewport meta /
未禁用缩放 / `@media (max-width:720px)` 恰 2 处 / `--mk-scale:1.25`）+ 桌面 1500×1050 基线 9 项
（媒体查询不命中、格子 32、棋子 30×25、棋盘 564、`--mk-scale .5`、`#moveList 558`）+ iPhone 390 与
安卓 360 各 17 项 + 全屏窗 7 项。**对照改前备份跑报 15 失败** ⇒ 有分辨力。
⚠️ 对它 `setViewport` 时**不能带 `isMobile`**（Chrome 切换移动仿真会把该 target 的文档打回空白：
实测 `#boardGrid .cell` 289 → 0）。真机路径是「弹窗按本机宽度开新标签」= 把窗口宽度设成 390 再量。
实拍：`shoot_mobile_20260923.js`（整页 + 布局视口/溢出量表格）、`shoot_mobile_sections_20260923.js`
（页头/信息/棋盘/记录/统计/评估/价值/页脚/标记面板/残局研究分区）、`compose_mobile_20260923.py`
→ `shot_mobile_compare.png`（四点改前/改后并排长图；两张图同为 1170 物理 px 宽，**可直接并排**）。

## 棋盘视觉规格 · QQ 军棋客户端风格（**v2 终稿 2026-09-21**）

> ⚠️ **本节 2026-09-21 整节重写过**：旧版（09-15）的「军绿迷彩多层渐变 / 42.5% 方块 / 周期 75% 枕木 /
> `.cell.camp::after` 21×21 环 / `--board-bg-2/-3`」**全部作废**，不要按旧印象下手。
> 现行规格 = **按附件原图（452×542，格距 79.3px）逐像素实测复刻**，全部以**格距百分比**表达，
> 一律走 `calc(var(--cell-size) * 比例)`（弹窗把 `--cell-size` 调到 46px 时自动同比放大）。

**✅ 三页同源**：`index.html` / `index_task2.html` / `index_task3.html` 的棋盘 CSS+JS 高度同构，
一次改动必须三页同落（用断言式脚本）。**`junqi_replay.html` 是另一套旧版视觉实现，不改**（坚哥 09-21 确认）。

### 变量总表（`:root` 浅色；`html.theme-dark` 覆盖 `--board-bg/#node-*/#railway*/#road/#camp-ring/#hq-ring/#station-ring`）

```css
--board-bg:#435743;        /* 底板：纯色（迷彩 21 层渐变已全删，勿加回） */
--node-frame:#101046;      /* 行棋点方块：外框 + 内环（深蓝） */
--node-fill:#8687ff;       /* 行棋点方块：亮蓝紫带 */
--node-core:#435743;       /* 行棋点方块：中心镂空 = 底板色（遮住穿心公路线，**不是 transparent**） */
--railway:#000000;  --railway-hi:#ffffff;
--rail-w:0.14;             /* 铁路带宽 14% 格距 */
--rail-tie-w:0.076;        /* 白枕木长 = 宽 = 7.6% 格距（小方块） */
--rail-tie-gap:0.344;      /* 枕木间隙 1 */
--rail-tie-gap2:0.504;     /* 枕木间隙 2（0.076+0.344+0.076+0.504 = 1.000 = 一周期） */
--rail-tie-lag:-0.252;     /* dash 相位：首条枕木落后路径起点 0.252 格 */
--road:#785206;  --grid-line:var(--road);
--road-w:1.4px;            /* 公路线半宽（全宽 2.8px ≈ 8.8% 格距） */
--camp-ring:#ffb900;  --camp-ring-dk:#6b4700;
--station-ring:#8687ff;
--hq-ring:#ff8b89;  --hq-ring-dk:#7d3f3d;  --hq-fill:transparent;  --hq-mark:#ff8b89;
```

### 原图实测规格（复刻依据，格距 79.3px）

| 元素 | 规格 | 实现 |
|---|---|---|
| 底板 | 纯色 `#435743` | `#boardWrap{background:var(--board-bg)}` + `inset` 阴影做边缘感 |
| 行棋点方块 | 外径 **47.9%**：中心镂空 17.7% / 内深环 5% / 亮蓝紫带 7.6% / 外深框 2.4% | `.cell::before` 四层 `box-shadow` 环 |
| 行营橙环 | 外径 **41.6%**、环宽 **7.6%**、纯色 `#ffb900`（环心镂空，无内暗边） | `.cell.camp::before` `inset` 环 |
| 大本营粉环 | 外径 **41.6%**、环宽 **7.6%**、`#ff8b89`（**与行营同尺寸**） | `.cell.hq::before` |
| 兵站 | 与普通行棋点**同款**回字方块，蓝紫带换 `--station-ring` | `.cell.station::before` |
| 铁路 | 黑带 **14%** 格距 | `.board-svg .rail` |
| 白枕木 | **7.6%×7.6% 小方块**（长=宽），每格 **2 条**，位于节点 **±0.29 格** | `.rail-hi` 的 4 段 `stroke-dasharray` + `stroke-dashoffset` |
| 公路 | 棕色 `#785206`，全宽 **8.8%** 格距 | `.cell` 的 `--gl-h`/`--gl-v` 格心十字 |
| 公路分布 | 正交网覆盖**所有行棋点**；对角米字**只从行营引出** | `.cell` 渐变 + `.board-svg .diag` |

**⚠️ `::before` 标记体系**（旧版是 `::after`）：全部改用 `::before`（`.cell::before` / `.cell.camp::before` /
`.cell.hq::before` / `.cell.station::before`），图层栈：`.board-svg` z-index:1 → `.cell::before` z-index:2 →
`.piece` z-index:3 → `.path-arrow` z-index:4 → `.move-arrow` z-index:5。**方块必须 `z-index:2`**，否则被 SVG 铁路盖住。

**⚠️ 三个必须保留的「压掉标记」规则**（都踩过）：
```css
.cell.empty::before{display:none}      /* 四角 6×6=144 格不是行棋点 */
.cell.rail-only::before{display:none}  /* R 铁路通过点（见下节） */
.cell.rail-only{background-image:none} /* R 格也不画公路十字 */
```

```css
.cell::before{
  content:""; position:absolute; left:50%; top:50%;
  width:calc(var(--cell-size) * .177); height:calc(var(--cell-size) * .177);
  transform:translate(-50%,-50%);
  border-radius:calc(var(--cell-size) * .03); background:var(--node-core);
  box-shadow:
    0 0 0 calc(var(--cell-size) * .050) var(--node-frame),
    0 0 0 calc(var(--cell-size) * .126) var(--node-fill),
    0 0 0 calc(var(--cell-size) * .151) var(--node-frame),
    0 1px 2px rgba(0,0,0,.30);
  pointer-events:none; z-index:2;
}
.cell.camp::before{ width:calc(var(--cell-size) * .416); height:calc(var(--cell-size) * .416);
  border-radius:50%; background:transparent;
  box-shadow:inset 0 0 0 calc(var(--cell-size) * .076) var(--camp-ring), 0 0 0 1px rgba(0,0,0,.32); }
.cell.hq::before{ /* 同 camp，环色换 --hq-ring */ }
```

### ⚠️ `BOARD_LAYOUT` 五种字符与「R 铁路通过点」（2026-09-21 第三轮）

`P` 普通行棋点 / `C` 行营 / `H` 大本营 **+** 中央兵站 / **`R` 铁路通过点（不可停留）** / `.` 空白角。
计数恒为 **`.`144 / `P`92 / `H`17 / `C`20 / `R`16 = 289**。

⚠️ **`R` 不是行棋点**：中央 5×5（行 6-10 × 列 6-10）只有 **9 个交叉点是 `H` 兵站**，其余 **16 格全是 `R`**。
旧代码只处理 `.`/`C`/`H`，`R` 落进 `else` → 被当成普通行棋点画了方块 → 中央读起来是 25 个方块的 5×5。
**全库 191 份棋谱 / 34461 步实测（`scan_cells_task3.js`）**：这 16 格作为起点/落点**次数恒为 0**
→ **真行棋点 129 = 四家各 30 + 中央 9 兵站，不是 145**。

必须改的 5 处（脚本 `restrict_railonly.py`）：
1. CSS：`.cell.rail-only{background-image:none}` + `.cell.rail-only::before{display:none}`
2. 主棋盘 `buildBoardGrid`：`if (ch==='R') cls.push('rail-only');`
3. 残局棋盘 `buildStudyBoardOnce`：同上（用 `c2`）
4. `studyIsPlay`：`... && BOARD_LAYOUT[r][c] !== 'R'`（不能在上面摆子）
5. `studyLegalTargets` 铁路分支：`var reach = railReachSet(...)` 后 `if (BOARD_LAYOUT[rr][cc]==='R') continue;`
   —— **铁路可穿过、不可停留**（BFS 仍要能路过 R 格）

**⚠️ 三处测试期望值是「预期后果」不是回归**：`verify_study_rail_task3` 的参考实现要加 `STOPPABLE()` 守卫
（否则 293 个位置全差分）；`verify_study_dom_task3` 紫师长 (6,15) 高亮 **48 → 42**；
`verify_study_task3` 里 (6,6) 工兵被封堵只能吃**上/左**两邻（下/右是 R 格）。

### 网格线：公路走 CSS 渐变，铁路 + 行营斜线走 SVG 叠加层

**公路细网格线**（格心十字，宽度由 `--road-w` 控）：
```css
.cell{
  --gl-h:linear-gradient(to bottom, transparent 0 calc(50% - var(--road-w)), var(--grid-line) calc(50% - var(--road-w)) calc(50% + var(--road-w)), transparent calc(50% + var(--road-w)));
  --gl-v:linear-gradient(to right,  /* 同上 */);
  background-image:var(--gl-h), var(--gl-v);
}
.cell.plain{background-image:none}   /* 中央 5×5 不画公路线 */
```
> ⚠️ 写测试正则时注意：`to right,` 后面源码里是**两个空格**，别写成一个。

**铁路 / 斜线走 SVG 叠加层**：
```css
.board-svg{ position:absolute; left:20px; top:20px;   /* 跳过 20px 坐标表头 */
  width:calc(17 * var(--cell-size)); height:calc(17 * var(--cell-size));
  pointer-events:none; z-index:1; overflow:visible; }
.board-svg .diag   {fill:none; stroke:var(--road); stroke-width:0.088; stroke-linecap:round}
.board-svg .rail   {fill:none; stroke:var(--railway); stroke-width:var(--rail-w); stroke-linecap:butt}
.board-svg .rail-arc{fill:none; stroke:var(--railway); stroke-width:var(--rail-w); stroke-linecap:butt}
.board-svg .rail-hi{  /* 白枕木：宽=长，4 段 dasharray，固定相位 */
  fill:none; stroke:var(--railway-hi); stroke-width:var(--rail-tie-w);
  stroke-dasharray:var(--rail-tie-w) var(--rail-tie-gap) var(--rail-tie-w) var(--rail-tie-gap2);
  stroke-dashoffset:var(--rail-tie-lag); }
/* .rail-arc-hi 同 .rail-hi */
```
- **⚠️ 最大的坑：SVG 绝对不能当 grid item 排版**。写 `grid-area:2/2/19/19` 会让它吃掉 17×17 = **289 个格子**，把 289 个 `.cell` + 35 个 header 全挤出显式网格，第 1 行被撑到 544px，整个棋盘错位。必须 `position:absolute` 脱离网格流，`.board-grid` 补 `position:relative`。
- 坐标系 `viewBox="0 0 17 17"`，1 单位 = 1 格，格 (r,c) 格心 = `(c+.5, r+.5)`；尺寸 `calc(17 * var(--cell-size))` → 主窗 32px 与弹窗 46px 同一份 DOM 自适应。
- 线宽**必须走格距比例**（旧版用 `vector-effect:non-scaling-stroke` + 绝对 px，已废弃）→ 弹窗放大时铁路/枕木同比放大。**`vector-effect` 现应为 `"none"`**。
- `stroke` 走 CSS 而非 SVG 表现属性 → 支持 `var()`，主题切换即时生效。

### ⚠️ 白枕木的 `stroke-dasharray` 相位陷阱（本轮最大坑）

dash 相位是**从每条 path 的起点重新起算**的。若铁路按「一格一段」推 100 条路径，
枕木就会在每格两端各错开一次，肉眼看是「枕木左右乱跳」。**唯一解 = 按行/列把连续铁路格合并成长线**：

- 生成规则：行方向扫 `isRailway(r,c) && (railLinked(r,c,r,c+1) || railLinked(r,c,r,c-1))`，
  连续段合成一条 `M x0 y0 L x1 y1`。100 段 → **14 段**（四家各 1 个环 + 中央网 10 条），
  **总长必须守恒 = 100 格**（务必加断言）。
- dash 数学：周期 = 1 格，序列 `0.076 / 0.344 / 0.076 / 0.504`（和 = 1.000），
  offset `-0.252` ⇒ 枕木落在 +0.252→0.328 与 +0.672→0.748，正好节点各侧 0.086 格。
- 弧线（`.rail-arc`）是独立 path，单独给一份同样的 dasharray/offset 即可。

### ⚠️ 米字斜线「只从行营引出」+ 去重 key 的方向陷阱

用户 09-21 明确纠正：`行营路线是米字形` —— 斜线**不是铺满阵地**，而是**只从行营（`C`）的 8 个方向引出**。
原图 452×542 逐条采样铁证：**32 条候选对角线里，端点含行营的 16 条全部有棕线、端点不含行营的 16 条全部没有**
（合起来才是「米」字；正交 4 向由 `.cell` 的格心十字提供）。总数 = **64 条**（20 营 × 4 − 16 条指进空白角）。

```js
var DIRS = [[1,1],[1,-1],[-1,1],[-1,-1]];
for (r=0;r<17;r++) for (c=0;c<17;c++){
  if (BOARD_LAYOUT[r][c] !== 'C') continue;                 /* ⚠️ 只从行营引出 */
  for (var k=0;k<4;k++){
    var r2 = r + DIRS[k][0], c2 = c + DIRS[k][1];
    if (r2<0||r2>16||c2<0||c2>16) continue;
    if (BOARD_LAYOUT[r2][c2] === '.') continue;              /* 指进空白角则跳过 */
    var pa = r + ',' + c, pb = r2 + ',' + c2;
    var key = pa < pb ? pa + '|' + pb : pb + '|' + pa;       /* ⚠️ 端点对，不能 min/max 各自取 */
    if (seen[key]) continue; seen[key] = 1;
    diags.push([c+.5, r+.5, c2+.5, r2+.5]);
  }
}
```
**⚠️ 去重 key 的方向陷阱**：`Math.min(r,r2)+','+Math.min(c,c2)+'|'+Math.max(r,r2)+','+Math.max(c,c2)`
按坐标**分别**取 min/max 会丢方向 —— `(r,c)-(r+1,c+1)` 与 `(r,c+1)-(r+1,c)` 会算成同一个 key。
本布局下行营之间不存在正交相邻，两种写法**恰好都得 64**（`diag_keycheck_task3.js` 实测），
但语义脆弱，**必须用端点对**。

### 铁路拓扑口径（09-15 深夜定稿，仍然有效）

- **四家各一个 5×5 铁路环**：上家 = 行 1·行 5 × 列 6·列 10；下家 = 行 11·行 15 × 列 6·列 10；左家 = 列 1·列 5 × 行 6·行 10；右家 = 列 11·列 15 × 行 6·行 10。
- **中央 3×3 九宫格**（行 6/8/10 × 列 6/8/10）；行 6/10 与列 6/10 本就是四家环的边，只有「行 8」「列 8」各向两端延伸 1 格（列 5-11 / 行 5-11）去接四家第 1 排。
- 合计 **14 条线**；**行 7/9 与列 7/9 上没有任何铁路线段**（这正是「军长 → 中央铁路」多余连线的根源）。第 6 排（底线）不是铁路。

```js
/* 格式 ['h', 行号, 起始列, 终止列] / ['v', 列号, 起始行, 终止行] */
var RAIL_LINES = [
  ['h',1,6,10], ['h',5,6,10], ['h',6,1,15], ['h',8,5,11], ['h',10,1,15], ['h',11,6,10], ['h',15,6,10],
  ['v',1,6,10], ['v',5,6,10], ['v',6,1,15], ['v',8,5,11], ['v',10,1,15], ['v',11,6,10], ['v',15,6,10]
];
```
`isRailway(r,c)` = 点是否落在线表上；`railLinked(r,c,r2,c2)` = **相邻两格心之间**是否真有一段（同一条线上 + 距离恰 1）。
> 历史坑：早期靠 `BOARD_LAYOUT[r][c]==='H' && r,c∈[6,10]` 把中央兵站算进铁路（「铁道线不闭合」的根因）；线表化后该分支消失。

改后铁路网：**85 个铁路点 / 14 条合并直轨（总长 100 格）/ 64 条行营斜线**，整网一块连通（flood-fill 85/85）。

ASCII 自检图（`#`=铁路 `o`=行营 `.`=空地 `H`=大本营）：
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

### 中央九宫格四角的「弧形铁道」

坐标：左家 5×5 环 = 列1·列5 × 行6·行10，其**右下环角 = (10,5)**；下家环角 = (11,6)；中间 (10,6) 是 `行10 × 列6` 十字交叉 + 兵站。

- **四个中心角各有一段**，都画在**九宫格外侧那一象限**（不是内圈）：
  | 角 | 象限 | 连接两臂 | 连的格子 | 圆心 |
  |---|---|---|---|---|
  | (6,6) | 西北 | 西 + 北 | (6,5)↔(5,6) | (5,5) |
  | (6,10) | 东北 | 北 + 东 | (5,10)↔(6,11) | (5,11) |
  | (10,6) | 西南 | 西 + 南 | (10,5)↔(11,6) | (11,5) |
  | (10,10) | 东南 | 东 + 南 | (10,11)↔(11,10) | (11,11) |
- 几何：**以该角的「对角格」为圆心、半径 = 1 格的四分之一圆** → 弧两端正好落在相邻两臂的**格心**上，弧中点距交叉口 `√2−1 ≈ 0.414` 格。
- **四家自己环的角没有弧线**（如 (5,6) 就是普通直角/丁字）。直线臂**不裁短**（弧线额外叠上去，形成「人」字形分叉）。

```javascript
var RAIL_ARCS = [
  'M 5.5 6.5  A 1 1 0 0 0 6.5 5.5',
  'M 10.5 5.5 A 1 1 0 0 0 11.5 6.5',
  'M 5.5 10.5 A 1 1 0 0 1 6.5 11.5',
  'M 11.5 10.5 A 1 1 0 0 0 10.5 11.5'
];
```
弧层用**独立的 `<g class="arc-layer">` 追加在 `rail-layer` 之后**（弧压在直轨之上，保证弧白芯连续、不被直轨白芯横切）。

> **⚠️ sweep-flag 是唯一易错点**：端点、弧长、包围盒都对得上，sweep 写反只会让弧朝九宫格**里侧**鼓，肉眼不细看发现不了。可靠验法 = `path.getPointAtLength(len/2)` 取弧中点、断言落在预期象限（`圆心 + R·(±√2/2, ±√2/2)`）。四条弧的 sweep 依次为 **[0,0,1,0]**。
> **⚠️ 解析 `d` 时 A 后面是 7 个参数**：`rx ry x-axis-rotation large-arc sweep x y`。少写一个正则永远匹配不上，会误报「4 条弧全不合格」。
> **⚠️ `getTotalLength()` / `getBBox()` 返回 SVG 用户单位**（1 单位 = 1 格），不是屏幕像素。R=1 → 弧长 `π/2 ≈ 1.5708`、包围盒 `1×1`，**别拿 `cellSize` 去乘**。

### 棋子（浅色底 + 深色描边 + 深色字）

尺寸反推：QQ 截图上（上家阵地 5 列 × 6 行）格距 **49×43**，棋子 **46×40** → 宽/格距 ≈ **94%**、高/格距 ≈ **93%**
（QQ 棋子几乎填满格子，且是**「略横」长方形**，不是明显扁条；按 1.4 比例做会偏扁）。
我们棋盘是 17×17 正方形 32px 格 → 取 `30×25`（同 1.2 宽高比 + 同填充率）。

```css
.piece{width:30px; height:25px; border-radius:3px; font-size:15px; font-weight:700;
       border:1.5px solid; box-shadow:0 1px 2px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.6);
       text-shadow:0 1px 0 rgba(255,255,255,.4);}   /* 文字是深色，所以阴影用白 */
.piece.green {background:linear-gradient(180deg,#dcefa4,#c2db7c); border-color:#5a7a20; color:#3d5710}
.piece.yellow{background:linear-gradient(180deg,#fddc9a,#f5c364); border-color:#c0720f; color:#8a4c05}
.piece.blue  {background:linear-gradient(180deg,#eef6fc,#d3e6f3); border-color:#2a72a4; color:#14517c}
.piece.purple{background:linear-gradient(180deg,#f1e4f7,#dfcbe9); border-color:#7b3f9e; color:#5a2b7d}
```
> ⚠️ 棋子尺寸**不走 `calc(var(--cell-size)*…)`**（是写死的 30×25），弹窗里必须**单独放大**，见下节「全屏弹窗同步放大」。

### 其他必须同步的点

- **坐标表头**（`.col-header/.row-header`）在绿底上改浅色：`var(--board-coord)` + 深色 text-shadow。
- **玩家名条 `.corner-label`**：字色是 JS 内联的 `PC_COLORS[c]`（深色）→ **底必须保持浅色**；深色主题下也保持浅底（`rgba(232,240,214,.94)`），改深底会让绿家 `#1e8449` 几乎看不见。
- **`--highlight-to` 从 `#1a1a1a` 改 `#ffd54f`**，否则终点框在绿底上完全不可见；`--highlight-from` 提到 `#ff4d3d`。
- **阵地区分**：QQ 是统一下盘（靠棋子颜色区分），我们把 `--*-bg` 降成 `rgba(…,.17)` 极淡色晕。**中央 5×5 不带任何 `-area` 类**（四家分区条件已排除 r/c ∈ [6,10]）。
- **深色主题**：`html.theme-dark{}` 覆盖 `--board-bg:#2b3529 / --node-frame:#0d0d38 / --node-fill:#8a8bff / --node-core:#2b3529 / --railway:#0a0a0a / --railway-hi:#dcdcdc / --road:#6b4a06 / --camp-ring:#e8a800 / --camp-ring-dk:#4e3400 / --hq-ring:#e88b89 / --hq-ring-dk:#5a2e2c / --station-ring:#8a8bff / --board-coord`；棋子单独覆盖成深一档的浅底（绿 `#93ad5a→#78923f` 等）。同时删掉旧的 `html.theme-dark .cell{border-color:…}` 这类按旧 border 写的规则。
- **全屏弹窗同步放大**：弹窗注入 CSS 里 `:root{--cell-size:46px}` + `.piece{width:43px;height:36px;font-size:21px;border-radius:4px;border-width:2px}` + `.move-arrow{font-size:26px}` `.corner-label{font-size:15px;line-height:21px}`。**只改 `--cell-size` 不改棋子尺寸，弹窗里棋子会明显偏小**（棋盘标记会同比放大，棋子不会）。

### 改棋盘时必跑的测试（三页同源）

- `run_e2e_task2.js`（201）—— 源码级：纯色底板 / 0 层迷彩 / 公路色宽 / 铁路比例变量 / 4 段 dasharray / camp-only 斜线 / 端点对 key / 回字方块三层 / `.cell.rail-only` 两条 + `cls.push('rail-only')`。
- `run_board_index.js`（71）—— 14 段合并禁 + **总长守恒 = 100 格** + 64 斜线 + 289 格。
- `verify_study_dom_task3.js`（65）—— DOM：289 格 / 14+4+64 / 总长守恒 / 纯色底板 `rgb(67,87,67)` / `rail-only` 恰 16 且 `::before`+`background-image` 皆 none / 中央 5×5 恰 9 个标记格。
- 实拍 `shoot_boardstyle_task3.js`（`HTML=` 换页、`TAG=` 换产物名）—— 三页规格必须一致：`普通点 92 / 行营 20 / 大本营 8 / 兵站 9 / R 16 → 真行棋点 129`、`14` 合并直轨 / `4` 弧 / `64` 斜线、零 pageerror。

**⚠️ 探针口径两个坑（都踩过）**：
1. **Chrome 对 `display:none` 的伪元素仍返回计算宽度**（行棋点方块是 `5.664px`）。判「有没有标记」**必须先看 `getComputedStyle(el,'::before').display === 'none'`**，只判 `width==='auto'/'0px'` 会把 `.cell.empty` / `.cell.rail-only` 误算成标记格（曾误报「普通点 108」= 92 P + 16 R）。
2. **`.cell.occupied::before{display:none}` 是既有规则**（有子的格标记被棋子盖住）→ 按「伪元素可见」计数会随当前步浮动（曾误报「兵站 8」，因为 (6,8) 恰好落了子）。标记计数**改成按类名**，另单独输出 R 格可见性不变量（带标记 0 / 带公路线 0）。

**⚠️ 找不到附件原图时先扫 `~/.workbuddy/blobs/`**：本轮 3 张附件没落盘，但早前缓存过的原图仍在 `blobs/18/…png`，用 `find … -name '*.png' -mmin -40` + 尺寸比对即可捞回（原图已备份 `/tmp/ref_board.png`，另可用 `tests/board_full.png`）。

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


## 复盘回放 · 行棋记录（`#moveList`）滚动跟随（2026-09-22 新增）

**需求原话**：「复盘回放时……行棋记录中会自动对应步数往下走，并强制屏幕停留在底部实时走棋记录处，将屏幕拉到别的项目时会自动跳回行棋记录底部。**修改复盘回放时主屏幕不强制跳回行棋记录底部位置。**」

**根因**：`markActiveStep()` 原写 `target.scrollIntoView({block:'nearest'})` —— 该 API 会滚动**目标元素的所有可滚动祖先**，**包含整页 `window`**。于是自动播放（每 `1200/playSpeed` ms 一步）时，用户翻看页面其它区块（本局结论 / 表现评估 / 玩家统计 / 净值曲线 / 页脚）会被每一步强行拉回行棋记录处。

**定稿口径（三页同构，`index.html` / `index_task2.html` / `index_task3.html`）**：
- 新增 `scrollListNearest(list, target)`：用 `getBoundingClientRect` 差值（扣 `list.clientTop` 的边框）算 delta，**只改 `list.scrollTop`**；`|delta| < 1` 不动（避免取整反复微调）。语义 = `block:'nearest'` 的**容器内**效果。
- `markActiveStep()` 改调它。**行棋记录内部照旧跟随当前步**（即用户认可的「自动往下走」保留），变的只是「不再拖走整页」。
- ⚠️ **禁止再用 `element.scrollIntoView()` 做「把某行带进可视区」** —— 它必然连带整页。要给容器内某元素定位，一律走 `scrollListNearest`（或直接 `list.scrollTop = …`）。同一机制在「测试脚本维护」节的截图坑里也踩过一次（截 `#moveList` 前对行 `scrollIntoView` 会把整页滚走）。

**验收（`verify_scrollfollow_task3.js`；第 3 个参数传 `pre` 即拿改动前备份做对照）**：

| 项 | 现行 | 改动前（对照） |
|---|---|---|
| 跳步（0 → 150 步）窗口位移 | **2px**（页高 +2px 触发的滚动锚定噪声） | **734px**（被拉回） |
| 播放 ~4.2s、窗口 40ms 采样 | 105 样本 / **1 个值**、最大偏移 **0px** | 2 个值、最大偏移 **736px** |
| 行棋记录内部跟随 | `list.scrollTop` 4044 → 4116、`.mv.active` 恒可见 | 同（未变） |
| `shoot_scrollhold_task3.js` 实拍 | 播放 3 步前后同位置截图 **0 / 1008000 像素差异** | **71.3%** 差异（视口整个被换掉） |

- ⚠️ 断言判据用 **40px 容差**：`gotoStep` 会让个别元素出现/消失 → 页高变 1~2px → Chrome 的**滚动锚定**顺带挪同量级。被拉回的量级是几百 px ⇒ 40px 既能滤噪又有充分分辨力。**不要写严格相等**，会误报「失败」。
- ⚠️ 实拍前要**等 toast（「分析完成：共 N 步…」）淡出再截 before**，否则它只出现在 before、after 已消失，会被像素比对当成「内容变了」（实测那 2.5% 差异全来自它）。
- ⚠️ 拿备份文件当对照页时**要先拷成 `.html`**：`file://` 下 Chrome 按扩展名判类型，`.bak_pre_noscroll_20260922` 会被当作纯文本渲染。

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
- ⚠️ **图例文案有两份，改一处必须两处都改**（2026-09-22 踩过）：`renderLegend()` 里的拼接串 **+** 静态 HTML 里那份
  `<div class="board-legend">`。没载入棋谱时看到的是静态那份（`renderLegend` 有 `if (!el || !replay || !replay.dirToColor) return;`
  的前置返回），只改动态串的话「空页面图例是旧的、载入棋谱后图例是新的」。
  当前口径（09-22）：**已删除「□★中间兵站」「★大本营」两项**，终点项写作 **`■终点（黄框）`**（起点项保持 `■起点(红框+箭头)`）。删除项时要**连同它前面的全角分隔符 `　` 一起删**，否则会留双空格。

### 司令阵亡 → 军旗必须亮出（不受盖牌影响，2026-09-22）

四国军棋正式规则：**一方司令阵亡后，该方的军旗必须翻开显示**。本页把它实现为「盖牌豁免」：

> ⚠️ **这是「显示层」规则，不是「扛旗的前置条件」（2026-09-24 坚哥指出 + 全库铁证定案）**
> 「军旗亮出」只决定**盖不盖牌**；**扛旗与它无关** —— 任何一方只要走到对方军旗格即扛旗、
> 该方立即出局，**不需要该方司令先阵亡，也不需要军旗先亮出**。
> 铁证：全库 2379 局、1850 次扛旗事件中 **134 次（7.2%）发生在被扛方司令尚存时**
> （实例：`right司令 扛 down 方军旗`、`up排长 扛 left 方军旗`、`down工兵 扛 left 方军旗`）。
> 本页 `resolveMove()` 的 `flag` 分支从来就没有这个前置检查 ⇒ **页面口径一直是对的**。
> ⚠️ 但 Python 侧（`.workbuddy/ld/`）曾按误解加了 `legal_moves(flag_locked=)`，把「司令未亡方的
> 军旗」设成不可攻击 —— 那会让 AI 平白少掉 7.2% 的取胜路径、并误判搜索终局，**已删除**。
> 写合法走法枚举 / AI / 搜索时**不得**再加这个条件。

- **判据（页面口径）**：`refreshCmdrDead(layout)` 每次在 `renderBoard()` 开头重算 `cmdrDead{绿黄蓝紫}` ——
  初始布局里每家必有且仅有一枚司令，所以「当前布局里找不到该方司令」即该方司令已阵亡。
  ⚠️ **必须再加一条「该方场上仍有棋子」**：军旗被扛 / 战败 / 超时判负会把该方棋子**全部移除**，
  那时司令也不在场，但那是「整方出局」而不是「司令阵亡」。少了这条，全库 191 份里会有 **7 份**误判
  （实测 `41junqi…jgs`：第 40 步蓝方扛旗夺黄旗 → 第 41 步黄方清盘）。加上后与解析器的
  `analysis.steps[i].res.event.cmdr` 事件口径在全库 **191 份上零差异**。
- **`isFlagRevealed(pieceName, color) = pieceName === '军旗' && cmdrDead[color]`**，
  **两处贴 hidden 类的地方都要加这个例外**：`renderBoard()` 内联那句 + `applyHiddenState()`。
  只改一处的话「跳步正确、点一下棋子切换明暗就丢」。
- ⚠️ `.piece` 上加 **`data-piece`（真实兵种）**供 `applyHiddenState()` 判定 —— 它只拿得到 DOM，
  而 **`textContent` 会被 `.piece-mark` 子元素拼脏**，不能用它判兵种。
  （注意：残局研究的 `renderStudyBoard` **早就在用 `data-piece`**，那套棋子走 `studyLayout`、不吃盖牌逻辑。）
- ⚠️ **不加任何视觉区分**（坚哥 2026-09-22 明确答复）：军旗因司令阵亡而亮出后，外观与明棋**完全一致**即可，
  **不要自作主张加淡金边 / 角标 / 底色**。`isFlagRevealed()` 只决定「盖不盖」，不引入新样式。
- 弹窗无需额外代码：hidden 类随 `sync()` 的 innerHTML 一起过去；但要用 `verify_flagreveal_popup` 实测守住。

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

## 复盘回放 · 棋子标记（右键盖牌棋子 → 选兵种标记，2026-09-22 新增 · 三页共有）

**需求原话**：「复盘回放中，鼠标右键点击已经盖牌的某个棋子，棋盘显示（参考图 edf9f967…png 的）半透明背景图片，左键点击图片上的相应的棋子级别，图片消失，该盖牌棋子上显示刚选择的棋子级别标记（修改或取消该棋子的标识显示，需要重新鼠标右键点击该棋子，再点击其他标识或者选择清除标识）。」

### 面板（`#markPanel`，插在 `#boardWrap` 内、默认 `hidden`）

- 定位 `position:absolute; left/top:50%; translate(-50%,-50%)` ⇒ **居中于棋盘**；`z-index:30`（棋子 3、箭头 4/5）。底 `rgba(70,69,41,.93)` —— **半透明**，棋盘仍隐约可见。
- 19 个瓦片（`.mk-tile[data-mark]`）：`司军师炸 / 旅团营雷 / 连排兵旗 / ! ? 大 小 / 一 二 三`；底部 `清空标记`（绿 `#2eb84d`）+ `✕`（橙红 `#ff4500`），高度都 = `--mk-tile`。
- **视觉按参考图用 CSS 重绘、不贴位图**：瓦片 = `--mk-tile: calc(var(--cell-size) * 1.5 * var(--mk-scale))` 的正方形（底 `#59583f` + 1px 暗内描边、圆角 `8px × scale`）；网格底 `#3f3e25`；金字的做法是 **渐变 `#fffefa→#fffce4→#ffe270→#ffc31f→#f0a51e` + `-webkit-background-clip:text` + 四向 `drop-shadow(1.25px × scale) #8a3a00` 当描边**（`font-weight:900`、字号 `0.6 × --mk-tile`）。**所有尺寸由 `--cell-size` 换算** ⇒ 主棋盘（32px）与全屏窗口（46px）比例一致、不发虚。
- ⭐ **`--mk-scale` = 面板的整体缩放系数**（2026-09-22 坚哥要求「面板长、宽都缩小到 1/2」⇒ 定为 `.5`）。定义在 `.mark-panel` 上，面板内**每一处**由 `--cell-size` / `--mk-tile` 换算的长度都必须乘它 —— 共 7 类：① `--mk-tile` 本体 ② 面板 `padding`/圆角 ③ 栅格 `gap`/`padding`/圆角 ④ 瓦片圆角 ⑤ 选中框 `3px` ⑥ 金字描边 `1.25px`×4 ⑦ 横杠白描边 `1.5px` ⑧ 按钮区 `gap`/`margin-top`。**漏一处就不是等比缩放**。
  - ⚠️ **描边类必须跟着缩**：字号随 `--mk-tile` 自动变小，若 `drop-shadow`/`box-shadow` 的 px 留在原值，半尺寸下会显得发胖发糊。
  - ⚠️ **棋子上的 `.piece-mark` 不能缩**：它在 `.mark-panel` **之外**（挂在 `.piece` 里），天然不受影响 —— 这是设计意图（24px 的格子里再缩就看不清了）。迁移脚本末检就是「`.piece-mark` 段不得出现 `var(--mk-scale)`」。
  - 实测（`--cell-size`=32px）：面板 **239.3×350.0 → 119.6×175.0**（宽高都 ×0.500）、瓦片 48 → 24、面板内边距 16 → 8、栅格间距 3.84 → 1.92 / 内边距 1.92 → 0.96、按钮区间距 3.84 → 1.92 / 上距 10.88 → 5.44。想再调只动这一个数（`.33` = 1/3 …）。
  - 面板高 = **5 行**瓦片（19 瓦片 ÷ 4 列）；量整体尺寸时的公式：`W = 2×面板padding + 2×栅格padding + 4×瓦片 + 3×gap`，`H = 2×面板padding + 2×栅格padding + 5×瓦片 + 4×gap + margin-top + 瓦片`。
- **一/二/三 = 三条白杠、第 1/2/3 条亮橙**（`.mk-bars-icon i.h`）——**三者都是三根杠，区别只在亮橙那条的位置**（不是「几根杠」，别照「一二三=1/2/3 条杠」实现）。
- 瓦片由 `MARK_TILES`（JS 常量表）在 `buildMarkPanel()` 里生成，**HTML 只留空的 `.mk-grid`** —— 单一数据源，也保证全屏弹窗克隆到的就是同一份。
- 对参考图做同尺度比对的方法：`document.documentElement.style.setProperty('--cell-size','40px')` **+ `--mk-scale` 改回 `1`**（否则只拍到现在的 1/2 大）⇒ `--mk-tile=60px`，与参考图瓦片 60px 同尺度，再 `elementHandle.screenshot()` 面板本体，PIL 并排拼图。实测（scale=1）我方 299×438 vs 参考 296×416。

### 标记 = 棋子身份，不是格子！（这块最关键）

- **状态**：`var pieceMarks = {}`，key = `'初始行,初始列|颜色'`，value = 标记 id（= 瓦片上的那个字，一/二/三 也直接用 `'一'|'二'|'三'`）。
- **身份怎么算**：`pieceIdentityMap()` —— 从**绝对方位**的 `baseLayout` 起，按 `baseMoves` 正向推进 `id`，得到「当前格 → 身份」；若 `replay.rotK ≠ 0`，再用 `rotCoord(行, 列, rotK)` 把格换算回当前视角。
  ⚠️ **推进必须与引擎布局推演（`resolveMove` / `snapshotAt`）逐位同源**（2026-09-22 修的 bug，全库 13591 个战斗场景里 13131 个错位）：**撞子时绝不能无脑 `id[落点] = id[起点]`**。正确规则四条 ——
  ① 落点归**攻方色**（移动 / 吃子 / 挖雷 / 扛旗）→ 身份随子搬到落点，落点原身份（被吃的守方）消失；
  ② 落点仍是**守方色**（攻方被反吃 / 触雷，守方原地不动）→ **守方身份原地不动**，攻方身份消失；
  ③ 落点为空（**同归于尽**）→ 双方身份一并消失；
  ④ `res.error`（反弹 / 非法行棋）→ 棋子原地不动，两边都不动。
  每步收尾再以真实布局裁剪 id（`if (!L[k]) delete id[k]`），整方出局 / 判负清子就自动兜住了。
- **为什么这样设计**：用**绝对坐标**做身份 ⇒ **切视角后标记不丢**；用**初始格**（一子一格、唯一）而不是当前格 ⇒ **棋子走动后标记跟着走**。
- **为什么复用引擎的推演而不自己写简化版**：撞子有 7 种结果分支、去向各不相同（谁留谁走谁全灭），简化版必错；现在就是「与 `snapshotAt` 同循环 + 同一个 `resolveMove` + 按落点归属搬 id」，于是 `id` 的键集**恒等于**该步真实布局的键集（可断言的不变量）。
- `markKeyOfPieceEl(el)`：只读 `el.parentNode.id`（`cell-r-c`）与 `data-color` ⇒ **全屏弹窗里的克隆 DOM 也能直接用**（不需要把身份传过去）。
- **贴回时机**：`renderBoard()` 末尾调 `applyPieceMarks()`（每步重建棋子后统一贴）。无任何标记时直接返回，零开销。
- **只在盖牌态显示**：CSS `.piece.hidden .piece-mark{display:flex}`（默认 `display:none`）。明棋时叠在真兵种上反而误导；因为只切 class，明/暗切换（`applyHiddenState`）**不必重算标记**。
- **换棋谱必须清空**：`startAnalyze()` 里加 `pieceMarks = {}; closeMarkPanel();` —— 两局的同一初始格会撞 key，不清就会把上一局的标记错误地贴到新棋谱上。

### 交互三条

1. **右键**用事件委托挂 `#boardGrid`（棋子每步重建，直接绑会失效）；非盖牌棋子**不弹面板**，改用 `toast('请先点击该方棋子盖牌（变暗棋），再右键标记')`；右键空白处先 `preventDefault()` 再关面板。
2. **打开时高亮当前标记**（`.mk-tile.active`）—— 这就是「改标记」的入口；点别的瓦片即覆盖，点「清空标记」即 `delete`。
3. **关面板**：`✕` / `Esc` / 点面板以外的任何地方（document 级 click 监听，用 `pn.contains(e.target)` 排除面板内部）。
4. ⚠️ **标记只能由鼠标右键修改**（用户 2026-09-22 明确要求）：`pieceMarks` 的**写点只有 3 处** —— ① `startAnalyze()` 里 `pieceMarks = {}`（换棋谱清空）② 主窗口右键面板 `pieceMarks[markTargetKey] = mk` ③ 弹窗右键面板 `op.pieceMarks[mkey] = mk`。**绝不允许加"按步 / 按事件自动改标记"的逻辑**；`verify_markident_20260922.js` 第 6 项就是这条的源码计数守卫（赋值写点合计恒 = 4，含 `var` 声明）。

### 全屏回放窗口

弹窗的 `#boardGrid` 每步由 `sync()` 从主窗口复制 innerHTML ⇒ **标记子元素自动带过来**，无需额外代码；但**右键逻辑必须在弹窗脚本里单独绑**（用 `op.markKeyOfPieceEl(el)` / `op.pieceMarks` / `op.applyPieceMarks()` 后 `sync()`）。弹窗的 `Esc` 已改为「面板开着先关面板，否则关窗口」。

### 测试

| 脚本 | 项数 | 覆盖 |
|---|---|---|
| `verify_piecemark_20260922.js` | **45** | 面板结构/瓦片顺序/三横杠；明棋右键不弹 + 提示；盖牌右键弹面板（半透明底、居中 ±2px、层高、完整落在 `#boardWrap` 内）；选标记 → 面板消失 + 标记落到该子；再右键高亮 + 改标记；**连续 40 步标记跟着棋子走**（且该子确实走动过）；同方两枚不串子；**真 rotK≠0 的视角切换后不丢**；明/暗切换；关面板（点外/Esc）；清空标记；**面板几何（4 列、`--mk-scale=.5`、瓦片 0.75×cell 正方形、整体宽高按公式 ±1.5px）**；换棋谱清空；零 pageerror |
| `measure_markscale_20260922.js` | **12** | ⭐**跨页「恰好 1/2」对照**：同进程开「改前备份页 + 当前页」，同一棋谱同一视口，逐项量面板宽/高、瓦片、面板 padding、栅格 gap/padding、按钮区 gap/margin-top 并算比值，断言全 ≈0.500。**这是唯一能真正证明「1/2」的做法**（单页内自证只是复述公式）。改前跑必报 9 失败 ⇒ 有分辨力 |
| `verify_piecemark_popup_20260922.js` | **21** | 全屏窗口：克隆到面板与 19 个瓦片、**克隆面板同样 ×`--mk-scale`（scale=.5 / 瓦片 0.75×cell / 宽按公式）**、右键弹面板且落在弹窗自己的 `#boardWrap` 内、选标记写回主窗口 + **两侧棋盘都出现**、清空两侧同步、明棋右键不弹、**Esc 先关面板不关窗口**、两窗口零 pageerror |
| `verify_markident_20260922.js` | **23** | ⭐**身份健壮性 / 「标记只能右键改」**（撞子后标记被自动顶掉那个 bug 的守卫）。样本固定在 275 步的 `41junqi2026_2_7_3_16…jgs`（一份就含反吃/同尽/扛旗三种撞子）。核心是**打满标记 + 逐步逐位比对**：给初始布局**每一枚**棋子打上标记，抽样 93 步，每步断言 ① `pieceIdentityMap()` 键集 ≡ `snapshotAt(n)` 键集（不多不少）② 标记所在棋子 `data-color` ≡ 身份 key 里的颜色 ③ **标记所在棋子 `data-piece` ≡ 身份 key 在 `baseLayout` 里的兵种**（③ 是最强判据：只看颜色抓不到「紫司令身上挂着绿营长身份」这种张冠李戴）。外加点名场景：反吃（守方标记不丢、攻方身份不残留）、同尽（两枚一起消失）、扛旗（被扛方整方清零）、回退复原、5 个视角 × 7 个关键步、源码写点计数守卫。**对照过修复前备份**：修复前 17/6 失败（含 `10,10 身份=绿营长 但棋子上是紫司令`），修复后三页 23/23。 |
| `shoot_piecemark_20260922.js` | 实拍 | `shot_piecemark_panel.png`（同尺度面板本体）、`shot_piecemark_board_light/dark.png`、`shot_piecemark_mark_zoom.png`（4× 特写：盖牌子上的 司/炸/?/一） |
| `shoot_markscale_20260922.js` + `compose_markscale_20260922.py` | 实拍 | 缩到 1/2 的证据图 `shot_markscale_compare.png`（1:1 大小对比 + 2× 像素查描边 + 棋盘遮挡面积 20%→5%）。配套 `shoot_markscale_dpr1.js` 拍 dpr=1 的 `ms_cur_dpr1.png`（查非视网膜下 24px 瓦片的字可读性）。⚠️ PIL 不会自动折行，标题/注释得自己按 `font.getlength` 折行，否则互相压字 |
| `shoot_markident_20260922.js` | 实拍 | 撞子标记对照：绿营长打「营」+ 紫司令打「司」→ 步18/步19 各拍棋盘 + 两格特写；`node … [页面] [post\|pre]`，修复前那版会拍出「紫司令被打成『营』」 |
| `verify_mobile_20260923.js` | **55** | ⭐**手机模式**（`node verify_mobile_20260923.js [页面]`，默认 task2；三页均可）。源码层 4 项 + **桌面 1500×1050 基线 9 项**（媒体查询不命中 / 格子 32 / 棋子 30×25 / 棋盘 564 / `--mk-scale .5` / `#moveList 558 ⇒ 手机模式不得污染桌面）+ iPhone 390×844 与安卓 360×780 各 17 项 + 全屏窗 7 项。手机层核心判据是 **`innerWidth === 视口宽`**（改前 635/634 —— 只看「无横向溢出」会假绿），其余：棋盘铺满一行、格子正方形且 ∈[15,32]、**棋子不超出格子 + 文字宽/棋子宽与字号/格子宽 ≡ 桌面端**、标记面板瓦片 ≥28px 且完全落在 `#boardWrap` 内、`#moveList` ≤60vh、页头无溢出、残局研究 stage 已转纵向 flex 且覆盖层无溢出。**对照改前备份 `pre_mobile_task2.html` 跑报 15 失败** ⇒ 有分辨力。⚠️ 对弹窗 `setViewport` **不能带 `isMobile`**（会把该 target 文档打回空白，`cell` 数 289→0） |
| `verify_datawarn_20260924.js` | **130** | ⭐**复盘数据自洽性自查**（`node verify_datawarn_20260924.js [页面]`，默认三页）。源码层 8 项 × 3 页（两个函数定义、自查调用 `startAnalyze`+`applyViewAndRerender` 各 1、开头清空、两条判据齐备、`.data-warn` 浅/深各 1）+ VM 判据（正常 .jgs `problems=0` / 旧 txt `errCount=19`+`resultConflict` ⇒ `problems=20` / `.txt.bak` 仅命中判据② ⇒ `problems=1`）+ **全库 110 份 .jgs 零误报**（`problems=0`、`resultConflict=0`）+ 页面 3 页（警告出现、文案含「19」「第 44 步」「旧版本页面导出」「.jgs」、浅色配色 `rgb(253,241,238)/rgb(192,57,43)`、深色 `rgb(42,23,18)/rgb(240,182,164)`、**换棋谱后警告清空**、零 pageerror）+ **改动前备份对照**（无该函数、无警告 ⇒ 有分辨力）。实拍 `shoot_datawarn_20260924.js` + `compose_datawarn_20260924.py` → `shot_datawarn_compare.png` |
| `shoot_mobile_20260923.js` | 实拍 | 整页 + 分区：打印每档视口的 `--cell-size` / **布局视口是否被撑开** / 页面与 `#boardWrap` 溢出量 / 格子·棋子盒 / `#moveList` 高 / 页头溢出；产出 `mb_{before,after}_{iphone,android}_{board,full}.png` |
| `shoot_mobile_sections_20260923.js` | 实拍 | 分区视口照（页头/对局信息/棋盘/行棋记录/得失统计/评估/棋子价值/页脚/标记面板/残局研究），并打印标记面板几何与残局研究覆盖层溢出量。`W=390 H=844 node …` 可换档 |
| `compose_mobile_20260923.py` | 实拍 | `shot_mobile_compare.png`（**四点改前/改后并排长图**：棋盘 / 得失统计表 / 标记面板 / 残局研究）。关键：两张源图都是 1170 物理 px 宽（= 390 CSS @dsf3 的**可视视口**）⇒ **可直接并排**，左图那 635px 内容就是被 Chrome 压进 390 的同一画面 |

⚠️ **六个测试脚手架坑（都是「测试写错、功能没错」，别去改产品）**：
1. **身份 key 是 `'行,列'`，格子 id 是 `'cell-行-列'`** —— 测试里必须 `CID(k)`（`'cell-' + k.replace(',', '-')`）转换。直接拼 `'cell-' + key` 会查不到元素，表象是「面板打不开 / 标记没出现」，其实全是测试自己在找错节点。
2. **`index.html` 的棋盘比 task2/task3 低约 380px**（多一张「竞技技术积分」卡）⇒ 不先 `#boardWrap.scrollIntoView({block:'center'})` 的话，真鼠标点击的 y 会落在视口外（`elementFromPoint` 返回 `null`）→ 「右键点不到棋子」。而 `el.click()` 是 JS 直调、不走命中测试，所以**只有「真鼠标右键」这一类断言会暴露它**。
3. `.mk-bars` 是加在 `.piece-mark` **自身**上的类 ⇒ 判定必须用 `classList.contains('mk-bars')`；`querySelector('.mk-bars')` 只查后代、**恒为 null**（会把「三横杠」误判成空文本）。
4. ⚠️ **`snapshotAt(n)` 返回的键已经是「屏幕坐标」，别再 `rotCoord` 一次**（双旋转会把整盘错位，一次踩坑：`abs` 视角下报 36 处假违规）。原因：`rotateView()` 是**就地改写** `replay.layout` / `replay.moves`（不是渲染时旋转），而 `snapshotAt` 直接吃这两者；`pieceIdentityMap()` 才是「`baseLayout/baseMoves` 推演 + 末尾 `rotCoord(rotK)`」那条路（`baseLayout` 永远保持未旋转的原始坐标）。两条路最终都落在屏幕坐标，**只有前者需要旋转**。
5. ⚠️ **不载入棋谱时，`#boardWrap` 在 `.main-grid` 里整块 `display:none`** ⇒ 面板 `getBoundingClientRect()` 全 0、`gridTemplateColumns` 返回 2 段乱值、`elementHandle.screenshot()` 直接抛 `Node is either not visible or not an HTMLElement`。**量几何 / 拍面板前必须先 `startAnalyze(jgsToText(bytes, name))` 载一份棋谱**（`#btnLoadDemo` 也行），再 `pn.hidden=false`。
6. ⚠️ **对 `window.open` 出来的弹窗 target 调 `setViewport` 时不能带 `isMobile:true`** —— Chrome 切移动仿真会把该 target 的文档打回空白（实测 `#boardGrid .cell` 289 → 0、`innerWidth` 变 980）。要量「窄视口下的弹窗」就**只改窗口宽高、不带 isMobile**（`setViewport({width:390,height:844,deviceScaleFactor:2})`），媒体查询照常命中。同理：想复现「手机布局视口被撑开」这个**主页面**行为，则**必须**带 `isMobile:true, hasTouch:true`。

## 环境与工具坑（本机 macOS，2026-09-23 汇总）

- **`/Volumes/me/ai学习/四国军棋/junqi_replay.html` 权限是 444 只读**：要改必须先 `chmod u+w`，并在 `finally` 里恢复原权限。（三页 `qq军棋复盘分析/` 不受影响。）
- **Chrome / puppeteer**：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`；`puppeteer-core` 用**绝对路径** `require('/Users/wangjian/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core')`；本版本**没有 `page.waitForEvent`**，抓弹窗用 `page.once('popup')`。
- ⚠️ **`page.screenshot({clip})` 的 `clip` 是「文档坐标」，而 `getBoundingClientRect()` 是「视口坐标」** ⇒ 必须自己加 `window.scrollX/scrollY`（曾把「标记特写」截成另一家阵地）。
- ⚠️ **`index.html` 的棋盘比 task2/task3 低约 380px**（多一张「竞技技术积分」卡）⇒ 任何**真鼠标**操作前先 `#boardWrap.scrollIntoView({block:'center'})`，否则 y 落在视口外、`elementFromPoint` 返回 `null`。`el.click()` 是 JS 直调、不走命中测试，**只有真鼠标事件会暴露这个问题**。
- ⚠️ **Node 沙箱里没有 `new TextDecoder('gbk')`** ⇒ 同一份 .jgs，Node 里玩家名是乱码、浏览器里正常。**Node 侧断言一律用颜色 / 方位，不要断言玩家名文本**。
- ✅ **要搜 `.jgs` 里的中文网名，改用 Python**：`open(f,'rb').read().decode('gbk', errors='ignore')` 就能读出玩家块里的昵称（`.jgs` 玩家名是 GBK 编码）。⚠️ 但**搜到名字 ≠ 该名字是「己方」** —— 全库 191 份有 189 份含同一网名（都是录制者本人参与的对局），而「己方」只有一位，必须走 `ownColorOf(replay)`（文件头 `0x0F`）判定。批量挑「己方 = 某人」的棋谱用页面同源链路扫，见 `.workbuddy/tests/probe_ownname_20260923.js`。
- **库内现状（2026-09-23 实测）**：191 份 `.jgs` 中 110 份 ≥2KB 可解析，其中 **108 份「己方 = 暴暴寒」**（46 份己方获胜 / 58 份落败）。挑演示/软著样本优先「己方取胜 + 步数多 + 四家网名干净」，当前最优候选 `junqi2026_6_19_16_47.jgs`（591 步，己方=绿=暴暴寒，四家 暴暴寒 / 亦有亭 / 明 教 / 辉哥，rotK=0 无需旋转）。
- **软件内置示例复盘 = `DEMO_JGS_B64`**（即 `junqi2026_6_22_16_38.jgs`，1180 B / base64 1576 字符，75 步，己方=紫=暴暴寒，三页字节一致），与 `DEMO_TEXT` 是**两份不同数据**。⚠️ 替换它会改变源码行数 ⇒ 若材料取自源码（如软著源程序 PDF），前/后 30 页的页码分配会整体位移，**要在冻结源程序文档之前定死**。
- ⚠️ **BSD grep 不支持 `\|` 交替**（**会静默返空**，多次被误判成「不存在」）⇒ 用 `grep -E` 或直接上 Grep/ripgrep 工具。zsh 下无匹配的 glob 会**中止整条命令** ⇒ 包一层 `sh -c`。
- ⚠️ **Chrome 对 `display:none` 元素的伪元素仍返回计算宽度** ⇒ 判「这格有没有标记」要先看 `getComputedStyle(el,'::before').display`；且 `.cell.occupied::before{display:none}` 是既有规则 ⇒ 统计一律**按类名**计数，别按伪元素。
- ⚠️ **跑测试批次的「退出码」不可信**：Chrome 退出时会删自己的 `code_sign_clone` 临时 bundle 与 `RLZ/GoogleUpdater` 小文件，**沙箱会拦截这些 `file-delete`** ⇒ 外壳退出码非零（`zsh _regress_aieval_20260926.sh` 会报 failed）。判成败**只看输出行**（`通过 N / 失败 M`、`=== 全部通过 N/N ===`），别只看退出码。
- ⚠️ **localStorage 偏好（`junqi_view` / `junqi_theme`）**：改完必须 `reload()` 再导入才生效；**headless 新 profile 的 localStorage 是空的** ⇒ 只测「默认路径」会漏掉全部偏好相关 bug。
- **PIL 拼图**：本机**没有** `/System/Library/Fonts/PingFang.ttc`，必须用 `/System/Library/Fonts/Hiragino Sans GB.ttc`；✅/❌ 在该字体下渲染成方块 ⇒ 用【正确】【错误】。`ImageDraw.text` **不会自动折行** ⇒ 标题/注释要自己按 `font.getlength` 折行，否则互相压字。
- **找不到用户给的附件图**时先扫 `~/.workbuddy/blobs/`：`find ~/.workbuddy/blobs -name '*.png' -mmin -40` 再按尺寸比对。

## 复盘数据自洽性自查（2026-09-24 新增 · 三页共有）

**需求背景**：用户上报 `junqi2026_6_24_16_22` 回放「**实际 208 步显示 205 步 / 分了胜负却显示未分胜负 / 走棋棋子混乱**」。

**诊断结论（先看这段再动手）**：
- **`.jgs` 路径完全正常**（三页均实测）：该局 208 步、结果「八方、孤独一生 胜」、逐步自洽 205/205、零 pageerror。**不要去改解析器！**
- `junqi_replay.html`（另一套旧实现）**不接收 `.jgs`**（报「未解析到行棋记录」）。
- 真正来源 = **同目录 08-18 12:18 导出的 `junqi2026_6_24_16_22.txt`**：三个症状**精确复现**
  （205 步 / 未分胜负 / 19 步行棋报错 / 方位 180° 错）。该文本的 `[方位]`/`[布局]`/`[行棋]` 三者不自洽 ——
  **旧颜色编码 + 旧方位推导规则的产物，信息不可还原**。
- ⚠️ 用户说「导入的是 .jgs」也**不能全信**：txt 头部与页面「来源文件」都写着 `文件=xxx.jgs`。
- ⚠️ 全库普查：`/Users/wangjian/Documents/布局库` 的 8 份 `.txt`/`.txt.bak` 中 **7 份会报警**，
  而**同名 `.jgs` 全部正常** ⇒ 结论：这类文件一律改用 `.jgs`。

### 两条判据（`auditReplaySelfCheck()`，`problems = errCount + (resultConflict?1:0)`）

| 判据 | 定义 | 金标准实测 |
|---|---|---|
| `errCount` | `analysis.steps` 里 `res.error === true` 的步数（`错误：起点无子` / `错误：目标为友军棋子` / `非法行棋（反弹，未生效）`） | **全库 110 份 .jgs 恒为 0**；旧 txt **19 / 205** |
| `resultConflict` | `meta['结果']` 含「战败」/「逃跑」（且不含「和局/平局」）但 `getWinTeam()` 返回 `null` ⇒ 战败方的清子事件缺失 | **全库 .jgs 恒为 false**（「一方战败」95 份全部判出胜队；「和局」14 份判不出属正常，已被 `/和局|平局/` 排除） |

⚠️ **两条判据缺一不可**：`junqi2026_6_24_16_22.txt.bak` 的行棋恰好**自洽**（`errCount = 0`）但缺 3 个事件步
⇒ 只靠判据 1 会**漏掉它**（步数 205、结果「未分胜负」）。该样本已钉进测试。

命中时：① `#conclusion` 内常驻 `.data-warn` 警告条（浅色红调 / 深色暗红调各一套 CSS）② 红色 toast。

### 落点（脚本 `add_datawarn_20260924.py`，11 处锚点 × 3 页，`--dry` 可预演、可幂等重建）

CSS 浅/深各 1；全局 `dataAudit`；`auditReplaySelfCheck()` + `dataWarnHtml()`（插在 `getResultText()` 之后）；
`startAnalyze` 三处（开头 `dataAudit = null` / `analyze` 后自查 / toast 分流）；`applyViewAndRerender` 一处（**切视角必须重算**）；
`renderClutch` 结论区一处（含「连 meta 结果都没有但数据坏」的 `else if` 分支）。
⚠️ 三页锚点有 **2 处不同**：`index.html` 的全局变量多一个 `techScore`、`startAnalyze` 里 `analyze()` 后面跟的是评估注释而非 `importPanel`
⇒ 脚本按页分流（`EDITS` 支持第 4 个元素 = 适用页列表）。备份 `.bak_pre_datawarn_20260924`。

### 排查同类问题的工具箱（本轮新建，通用）
`diag_624bug_20260924.js`（单局逐层诊断：原始指令流 / 步数 / 事件步 / alive / 胜负 / 逐步自洽）、
`diag_import_20260924.js`（**任意文件 → 真实浏览器导入 → 打印页面实际显示**，页面参数支持绝对路径，最常用）、
`diag_selfcheck_20260924.js`（.jgs vs 旧 txt vs 全库的 error 分布）、
`scan_txt_audit_20260924.js`（全库 `.txt` 普查，列出所有会报警的文件）。

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
- **署名为分支差异项**：index.html 用「暴暴寒（7z）｜规则赋能/优化：姜朕熙」；**task2/task3 的页头 badge 自 2026-09-22 起为「以此致敬永远的尖刀师！设计制作：☆→小寒（7z）」**（页脚 © 行仍是「© 2026 热心市民小寒（7z）」）。移植时**不要顺手改署名**，除非用户明确要求。
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
  <div>© 2026 ...（署名行：三页各不相同，见「关键约定 · 署名是分支差异项」；task2/task3 页脚为「© 2026 热心市民小寒（7z） · 仅供学习交流使用」，index 为「© 2026 暴暴寒（7z） | 规则赋能/优化：姜朕熙（B站：老姜甄鉴）」）</div>
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
- ⚠️ **署名行三页本来就不一样，不要「统一」掉**（用户明确说过页脚署名保持原样）。改稿要**逐页点名**：
  2026-09-22 坚哥只要求改 task2/task3 的**页头 badge**（→「以此致敬永远的尖刀师！设计制作：☆→小寒（7z）」），
  **同一页的页脚 © 行与 index.html 的 badge/© 都没动** —— 「只改被点名的那一处」是本项目的常规口径。
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

### 项目内测试台（`.workbuddy/tests/`，task2 / task3 与 index.html 各一套）

**⚠️ `/tmp/junqi_test/` 已被系统清空三次（2026-09-13、09-15 两次），2026-09-15 起整套测试台固化到 `<项目>/.workbuddy/tests/`，不要再放 `/tmp`。**

> 📌 **`_task3` 后缀的脚本（残局研究 / 铁路行驶规则 / 悔棋）集中在后面「残局研究」一节的「测试台」表里**（`verify_study_task3` / `verify_study_dom_task3` / `verify_study_rail_task3` / `verify_railturn_task3` / `diag_arcs_task3` / `verify_moverule_task3`），本节只列 `_task2` 与无后缀的两套。

> ⚠️⚠️ **2026-09-21 棋盘重绘 v2 —— 下表里所有「棋盘视觉」相关数字都已作废，以「棋盘视觉规格」章为准。**
> 具体来说：**铁路线段 100 → 14**（按行/列合并长线，**总长守恒 100 格**必须断言）；**`stroke-width:5px`+`non-scaling-stroke` → 比例变量 `--rail-w:0.14`/`--rail-tie-w:0.076`，`vector-effect` 应为 `"none"`**；
> **白内芯 = 4 段 `dasharray` 的 7.6% 小方块（每格 2 条）**，不再是 1px 实线；**底板 = 纯色 `#435743`（0 层渐变）**，不再有军绿织纹/多层背景；
> **公路线宽 = 半宽 1.4px / 全宽 8.8% 格距**，色 `#785206`；**行营/大本营 = `::before` 单圈环 41.6%/7.6%**（不再是 `::after` 21×21 环）；**行棋点 = `::before` 四层「回」字方块**；
> **米字斜线只从行营引出（64 条）**；**新增 `.cell.rail-only`（R 铁路通过点 16 格，不画方块也不画公路线）**；**真行棋点 129 而非 145**。
> 现行断言口径见 `run_e2e_task2.js`（**201**）/ `run_board_index.js`（71，含 14 段 + 总长守恒）/ `verify_study_dom_task3.js`（**65**）与「棋盘视觉规格」章末尾的「改棋盘时必跑的测试」小节。

目录内容：

**A. 针对 `index_task2.html`**（文件名带 `_task2`）

- `extract_engine_task2.py` — ⚠️ **2026-09-22 起已被 `extract_engine_task3.py` 取代**（后者支持任意页面），本脚本头部已加废弃标注、仅为兼容历史命令保留。原文：用 `re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)` 取**最长**块写 `engine_task2.js`（页面有 3 个 script：JSON-LD / 主题预置 / 主脚本，取最长即主脚本）。路径全部由 `__file__` 推项目根，不需要改。
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
- `verify_piecemark_20260922.js` — **45 项**「棋子标记」真实浏览器验证（`node verify_piecemark_20260922.js [页面名]`，默认 `index_task2.html`；三页均 45/45）。右键盖牌棋子 → 半透明面板 → 选标记 → 标记贴在该子上并**跟着棋子走 / 不随视角漂移 / 明暗切换不丢** / 改标记 / 清空 / 换棋谱清空；几何项断言 `--mk-scale=.5`、瓦片 `0.75×cell`、面板整体宽高按公式。详见「复盘回放 · 棋子标记」一节的测试坑 5 条。
- `measure_markscale_20260922.js` — **12 项**⭐面板缩放**跨页对照**（`node measure_markscale_20260922.js`；需先 `cp index_task2.html.bak_pre_markscale_20260922 pre_markscale_task2.html`，备份当页面加载必须先改成 `.html` 后缀）。同进程开「改前 + 改后」两页、同棋谱同视口，逐项算比值断言全 ≈0.500。**证明「恰好 1/2」只能这么做**。
- `verify_piecemark_popup_20260922.js` — **21 项**同功能的**全屏窗口**验证：面板随卡片克隆（含**克隆面板同样缩放**）、右键逻辑在弹窗里单独绑并能写回主窗口、`Esc` 先关面板不关窗口。
- `verify_markident_20260922.js` — **23 项**「标记只能由右键改 / 撞子后身份不漂移」守卫（打满标记 + 逐步逐位比对兵种 + 源码写点计数）；其**全库版**是 `probe_identdrift_20260922.js`（Node 直跑引擎：`node probe_identdrift_20260922.js` 查全部战斗步±1 共 13591 场景，`ALL=1 node …` 逐步全量 35069 场景，两者都必须 0 错位）。
- `shoot_piecemark_20260922.js` — 面板/棋盘/标记特写实拍，并与坚哥给的参考图做**同尺度并排比对图**（`--cell-size:40px` **+ `--mk-scale:1`** ⇒ 瓦片 60px，注意别漏后者）。
- `shoot_markscale_20260922.js` + `compose_markscale_20260922.py` — 缩到 1/2 的实拍证据 `shot_markscale_compare.png`；`shoot_markscale_dpr1.js` 另拍 dpr=1 的 `ms_cur_dpr1.png` 查 24px 瓦片的字可读性。⚠️ 不载棋谱时面板在 `display:none` 的 `.main-grid` 里，元素截图会抛 `Node is either not visible…`，必须先 `startAnalyze(jgsToText(...))`。
- `verify_legendcredit_20260922.js` — **16~17 项**「棋盘图例 + 页脚署名」文案守卫（`node verify_legendcredit_20260922.js [页面]`，默认 `index_task2.html`；index 16、task2/task3 各 17）。**两种图例状态都查**：未载入棋谱时的静态 `.board-legend`、载入棋谱后 `renderLegend()` 重建的那份 —— 都不得含「中间兵站」「大本营」、终点项必须是 `■终点（黄框）`，且起点/行营/行棋方向/两条操作提示**未被误伤**；再加一条 `s0 !== s1` 证明「两种状态确实走了不同代码路径」（防「其实没跑 renderLegend」的假阳性）。署名按页分流：task2/task3 断言页头 badge = 致敬文案 **且页脚 © 行仍为原文**；index.html 断言 badge 仍是「暴暴寒…」。
- `shoot_legendcredit_20260922.js` — 实拍图例 + 页脚（页头 badge 特写 / 整幅 footer），并拼成带标题的对比长图 `shot_legendcredit_compare.png`。⚠️ **PIL 拼图的中文字体要用 `/System/Library/Fonts/Hiragino Sans GB.ttc` 或 `STHeiti Light.ttc`** —— 本机**没有** `/System/Library/Fonts/PingFang.ttc`（`ImageFont.truetype` 抛错后若 fallback 到 `load_default()`，中文会渲染成一串豆腐块）。
- `verify_flagreveal_20260922.js` — **40 项**「司令阵亡 → 军旗亮出」真实浏览器验证（`node verify_flagreveal_20260922.js [页面名]`，三页均 38/38）。样本 `junqi2026_9_6_21_44.jgs`（第 2 步黄方司令阵亡）。含：阵亡前军旗跟着盖 / 阵亡后**只有军旗亮、其余仍盖**（`hid == tot-1`）/ 未阵亡方不享受豁免 / 回退后重新盖上 / 2↔1 跳 6 次 / 真旋转视角不丢 / 明棋态 / `isFlagRevealed` 与边界（`refreshCmdrDead({})`、`refreshCmdrDead(null)`）/ 右键亮出的军旗不弹标记面板。
- `verify_flagreveal_popup_20260922.js` — **17 项**同功能的**全屏窗口**验证：克隆态军旗同样亮、弹窗内「上一手/下一手」步进后军旗跟着变、弹窗内切明暗、两窗口盖牌数与军旗状态一致。
- `verify_flagreveal_scope_20260922.js` — **全库交叉验证（纯 Node VM，不启浏览器）**：191 份 `.jgs` 上对比两条独立口径的**首次阵亡步号** —— 解析器事件流 `analysis.steps[i].res.event.cmdr` vs 布局对比 `refreshCmdrDead(snapshotAt(n))`。断言「布局口径**不得晚于**事件口径」（晚于 = 军旗该亮没亮）；同时统计覆盖面：186/191 份有司令阵亡、17 份在 5 步内、**75978 个「必须自动亮旗」的 (步,颜色) 场景**。⚠️ 初版曾报 7 份不一致，根因是「整方出局」误判（见正文），修完 **0 份**。
- `probe_flagreveal_20260922.js` — 探针：扫全库列出每份棋谱「首次司令阵亡」的步号与颜色，用来挑测试样本（`node probe_flagreveal_20260922.js`）。
- `verify_duptitle_20260922.js` — **15 项**「棋子 title 提示」不重复/不丢失守卫（默认三页，可传页名）：① **源码层**每页 `pc.title = '点击：该方盖牌 / 恢复明棋';` **恰好 1 处** —— 2026-09-22 加 `data-piece` 时在 `index.html` 里手滑连写了两遍（无功能影响，属脏代码，已删）；② **运行层**载入棋谱后每枚棋子都带且仅带这句 title（防「删多了」静默）。**拿改前备份跑 ① 报 2 处** ⇒ 有分辨力。修法脚本 `fix_duptitle_20260922.py`（只动 index.html，并顺带断言 task2/task3 恒 1 处）。
- `shoot_flagreveal_20260922.js` — 实拍第 1 步（军旗跟着盖）vs 第 2 步（军旗亮出）+ 军旗格 3.4 倍特写 + 深色主题，拼成 `shot_flagreveal_compare.png`。
- `verify_eval_task2.js` — **6 项**「表现评估评分不变量」校验（`node verify_eval_task2.js`，纯 Node VM 不启浏览器；`ENGINE=engine_index.js` 跑另一引擎，也支持绝对值路径做落盘前预演）。扫 `/Users/wangjian/Documents/布局库` 全部 191 份 `.jgs` / 764 条玩家评估，断言：① 净值 > 0 者**评语**不得含「子力交换亏损」；② 净值 < 0 者评语不得含「占优」；③ **标签（tags）**同 ①②；④ `s.失着 > 0 ⇔ s.失着损 > 0`；⑤ D 级占比 < 30%。**已用「改动前」引擎实测会 4 项失败**，故它是有效的回归保护，不是假绿。
- `port_evalv3_20260924.py` — **评估公式 v1→v3 断言式迁移**（`python3 port_evalv3_20260924.py [--dry]`）。锚点 `count==1` + 迁移后自检；`--dry` 只校验不写盘；一次处理 `index_task2.html` 与 `index_task3.html` 并做**同构校验**（两者必须逐字节相等）。⚠️ 替换锚点若包含前一函数的结尾（如 `return ev;\n}`），**替换文本必须把它带回去**，否则函数缺右括号、`check_js_blocks.py` 报 `Unexpected end of input`。
- `port_evalv3b_20260924.py` — **v1→v3.1 迁移（含第二轮 insight 校准 + 三页推广）**。⚠️ 与上一条的关键差别：① **以 `.bak_pre_evalv3_20260924` 为输入源重建目标文件**（幂等，重跑结果一致、不累积改动）；② 目标含 **`index.html`**（竞技积分版）。前提是已实测 `analyze()`/`computePlayerEval()`/`evaluateAll()`/`killRatio()`/`renderPlayerEval()`/`DIM_WEIGHTS` 在 index 与 task2 中**逐字一致**（用「抓函数块 + 比长度/内容」脚本核实，别只凭肉眼）。新增 stats 字段 `主动手`。
- `align_evalv3_20260924.js` — **评估公式 JS↔Python 数值对齐**（`node align_evalv3_20260924.js engine_task2.js /tmp/eval_align_in.json`）。配合 `.workbuddy/ld/dump_for_js.py`（先 `python dump_for_js.py 300 > /tmp/eval_align_in.json`）。把 Python 的 `stats/curve/steps/alive` 注入 Node，逐条比对**特征层 + v1 五维与总分 + v3 五维与总分** —— 期望 **300 局 / 1200 样本全 0 差异**。这是「页面实现 = 校准口径」的唯一硬证据（两页只吃 `.jgs`、校准数据是联众 `.JQH`，无法同局比）。
- `probe_evalv3_task2.js` — **页面级 v1/v3 对照探针**（`node probe_evalv3_task2.js [engine.js]`）。191 份 `.jgs` 上分别跑两版：确认默认 `EVAL_ENGINE`、总分 AUC / 前 2 命中 / 评级分布 / 各维均值·标准差·**触界率** / 两版相关性。⚠️ 有效对局仅 44 局（其余是和局或非 2v2），**AUC 与前 2 命中噪声大**，权威结论以联众 2332 局为准；它的价值在**跨数据集互证退化**（v1 的 `insight` 触 0 界 30.7%）。
- `shoot_evalv3_20260924.js` — **评估面板实拍 v3/v1 对照**（`node shoot_evalv3_20260924.js <输出目录> [棋谱.jgs]`）。同一局分别以 v3、v1 渲染并各截 `#evalPanel` 一张，同时打印四方分数便于核对。截图内联进校准报告用（base64，保持单文件离线可看）。
- `verify_path_task2.js` — **24 项**「行棋路线压铁道」不变量（`node verify_path_task2.js`，纯 Node VM 不启浏览器；`ENGINE=engine_index.js` 跑另一引擎，也支持绝对值路径做落盘前预演）。单元行为：同格 / 直走 1 格 / 斜走 1 格（行营米字 + 弧形铁道正反两向）→ **均无中间格**；直行多格 `(6,12)→(6,2)` 中间格 9 个且首格 `(6,11)`；铁路拐弯 `(6,12)→(3,10)` 全在铁路上、末格 `(4,10)`；同行长距离 `(7,11)→(7,1)` 沿铁路绕行且**不横穿行 7**。全库 191 份 / 34461 步断言：**中间格离开铁路 = 0**、斜向多格不可解 = 0、路径跳格断点 = 0。**已用「改动前」引擎实测 2 项失败（退出码 1）**，是有效的回归保护。
- `verify_pathdom_task2.js` — **8 项**页面级红色轨迹验证（`node verify_pathdom_task2.js [页面路径]`，默认 `index_task2.html`；第二参传任意路径可**做改动前对照**）：用 `41junqi2026_2_7_3_16-…jgs` 抽检斜走 1 格 20 步 / 直行多格 20 步 / 斜向多格 24 步 —— DOM 上 `.path-arrow` 所在格集合与 `movePathCells(from,to,blocked)` **完全一致**（⚠️ 期望值必须传「该步之前」的真实棋盘 `snapshotAt(i)` 作障碍表，否则会与 DOM 不一致；⚠️ `querySelectorAll` 返回的是 DOM 行优先顺序，与路径顺序无关，比较前必须排序）、`.move-arrow` 恒在起点格、**离轨数 0**、**轨迹不再穿过任何棋子**（先挑出「不带障碍表会穿子」的步，再断言那些步的箭头格内没有 `.piece`）、斜走一格不再产生中间箭头、零 pageerror，并实拍 `out_pathclear_<页面>_board.png`（优先拍「老画法会穿子」那一步，便于新旧对照）。改动前的页面跑它会报 **离轨**（如第 11 步斜走落在 `cell-13-8`）与 **穿子 3 例**。
- `verify_pathclear_task2.js` — **34 项**「轨迹必须畅通」不变量（`node verify_pathclear_task2.js`；`ENGINE=engine_index.js` 跑另一引擎）。单元：`pathFree` 占用识别（值非 1 也算占）；`railPathThrough` 无障碍时与 `railShortestPath` **逐格相同**（保证只改被挡的步）、堵死终点全部铁路邻居返回 `null`、不可达契约 `railShortestPath→[]` vs `railPathThrough→null`；`movePathCells` 直线被挡后改道（不再经过被占格、仍全在铁路、长度不短于直线）、**终点格被占（吃子目标）不算障碍**、斜走/直走一格与障碍无关、改道路径逐格相邻。全库 191 份 / 15203 步多格移动：中间格**真有棋子 = 0**、离轨 = 0、无解 = 0、跳格断点 = 0；**因挡道改道 = 597 步**（精确断言）；**反向对照**：不带障碍表的几何最短路会穿子 **597 步 / 1658 个落点**（证明该参数确有必要）；「之后布局反推的障碍表」与「之前真实棋盘」求得路径**零差异**。⚠️ 全库扫描必须走页面同源链路 `jgsToText → parseReplay → applyOrient → snapshotAt`（`parseJGS` 的 moves **不含事件步**，直喂会让布局模拟错位）。
- `verify_scrollfollow_task3.js` — **12 项**「复盘回放不强制跳回行棋记录底部」页面级验证（`node verify_scrollfollow_task3.js [页面] [pre]`，默认 `index_task3.html`；第 3 参 `pre` = 自动取 `<页面>.bak_pre_noscroll_20260922` 拷成临时 `.html` 做**改动前对照**，此时 ②③ 期望「被拉回」）：断言 ① 场景有效（页高 > 视口+200、`#moveList` 内容高于容器）② 跳步 0→150 后窗口位移 ≤ **40px 容差** ③ 自动播放 ~4.2s、窗口 40ms 采样 105 个样本、最大偏移 ≤ 40px ④ 行棋记录内部仍跟随（`list.scrollTop > 0`、`.mv.active` 恒在容器可视区内）⑤ 点已可见行不改 `list.scrollTop` ⑥ 零 pageerror。对照页 ② 报 **734px**、③ 报 **736px**。
- `shoot_scrollhold_task3.js` — 实拍证据（同样支持 `[页面] [pre]`）：跳到第 150 步 → 滚到页面最底部（`#moveList` 已在视口之上）→ 截图 before → 播放 3 步 → 截图 after。现行三页 before/after **0 像素差异**；改动前 **71.3%**。产出 `shot_scrollhold_<页面>[_pre]_before/after.png`。⚠️ 必须先 `sleep 3600` 等「分析完成」toast 淡出再截 before，否则 toast 会污染比对。
- `verify_ownview_task2.js` — **21 项**「己方视角」链路真实浏览器验证（`node verify_ownview_task2.js [index.html]`，省略参数默认测 `index_task2.html`）：用 `41junqi2026_2_7_3_16-…jgs`（己方=绿，**绿在文件原始方位就已位于下方**，是最容易踩「`viewColor` 留 null」坑的样本）——`ownColorOf`=绿、下拉选中 `self`、`viewColor`=绿、`rotK`=0、提示文案含「为下家（文件原始方位即是，无需旋转）」；绿在行 11~16（底行 16=大本营）、黄在行 0~5；玩家卡「己方」徽章恰好 1 个且紧邻绿方名；首步方=`TURN_ORDER[0]`（逆时针锚点未破）；切「绝对方位」→ `viewColor=null` 且提示含「绝对方位」；切「以 XX 为下家」→ `rotK≠0`、目标方落到行 16、提示含「已整体旋转」、己方徽章不随视角漂移；零 pageerror。
- `shoot_footer_stat.js` — **页脚「51.la 统计」位置实拍 + 加载断言，覆盖 4 页共 51 项**（`node shoot_footer_stat.js`）：
  逐页断言 —— 统计代码在 `footer` 内、全页仅 1 处、`href`/`src` 正确、**图标 `naturalWidth > 0`（真的加载出来了，外链图必须查这个，否则「src 写对但图挂了」查不出来）**、
  **统计图标 `bottom ≤ 备案链接 top`（「在备案信息上方」是位置关系，肉眼看截图不可靠）**、水平居中（中线偏差 < 4px）、
  **采集 JS：`id="LA_COLLECT"` 存在 + `charset=UTF-8` + `src` 为显式 https + `window.LA.init` 是 function**、零 pageerror；
  页面清单：`qq军棋复盘分析/index_task2.html`、`qq军棋复盘分析/index.html`、`四国军棋布局转换器.html`、`junqi_replay.html`
  （后两页路径在上级目录，**脚本里写的是绝对路径**）。产出 `out_footer_task2.png` / `out_footer_index.png` / `out_footer_conv.png` / `out_footer_jr.png`。
  **凡动页脚或统计，跑这一份就够。**
- `run_orient.js` — **方位推导专项 65 项**（`python3 extract_engine_task2.py && node run_orient.js`）：
  源码级（两个文件各 11 条）：无旧 `voteDir`、含 `pickOrientByScore`/`orientSelfCheck`、注释点名两个撞车样本、`MAX` 按文件长度、`teamSplit` 2:2 守卫、`applyOrient` 补位、`renderTurnStrip` 跳过缺失方位、铺盘跨家撞格守卫；
  行为级：`dirOfCoord` 七分区、`orientSelfCheck` 对错方位 1 vs 0、离场事件后撤子、`pickOrientByScore` 平票回退/四色互异；
  真实文件：上报文件（方位四项、各 25 子、269 步、275 步分析、存活=绿紫、黄 40 步/蓝 73 步被扛旗、分队 2:2、判不出胜队 → **和局**）、`7_6_16_38`（黄/蓝撞 up → 各 25 子）、`6_19_21_14`（**252 步**，旧实现只读 4 步）、`3_6_21_14`（单步谱定黄=up）；
  构造级：撞方位输入经 `applyOrient` 自动补成 4 项且不抛异常、3:1 → `teamSplit` 返回 null、重名但恰好 2:2 不误伤。
  **凡动 `parseJGS` 的方位推导 / `teamSplit` / 布局铺盘 / `applyOrient`，跑这一份就够。**
- `run_winrule.js` — **胜负判定专项 41 项**（`python3 extract_engine_task2.py && node run_winrule.js`）：**两个引擎都跑**（自己从 `index.html` 抽最长 script 块建第二个沙箱，所以 index 侧不会偷偷回退）。
  覆盖 —— 源码级：两文件均无 `captureColor`、注释含「一出现扛旗…是错的」「扛旗之后仍在行棋」警示、「未分胜负」文案、`renderSummary` 结论已改用 `getResultText()`；
  行为级（构造 `{replay, analysis}` 直接调 `getWinTeam`/`getResultText`/`renderPlayers`）：**扛旗方随后全灭 → 对方胜**（本次修的那个 case）、扛旗后被扛家队友仍在 → `null`、meta=和局时保留「和局」、无扛旗一队全灭 → 对方胜、两队全灭 → 最后离场方胜（含同时刻）、无人出局 → `null`、玩家卡恰好 2 胜 2 负；
  真实文件：`junqi2025_3_28_20_4.jgs`→绿黄 / `10_29_20_9`→绿黄 / `3_8_22_36`→蓝紫 / `6_24_16_22`→绿黄（判定不变），两个引擎各跑一遍。
  **凡动 `getWinTeam` / `getResultText` / `teamSplit` / `分析.alive` 口径，跑这一份就够。**
- `shoot_hidden_task2.js` — 明暗棋效果实拍：`out_hidden_up.png`（明棋）/ `out_hidden_green.png`（一方盖牌）/ `out_hidden_two.png`（两家盖牌）/ `out_hidden_zoom.png`（绿紫交界 4×4，盖牌与明棋同框，DSF 4）/ `out_hidden_dark.png`（深色主题）。**深色主题那张是发现「盖牌仍透出兵种字」的唯一手段，改盖牌样式后务必重拍。** 本复盘方位：绿=右 紫=下 黄=左 蓝=上（视角=紫），取景靠这个定。
- 断言阈值坑：`var(--chart-` 是 **9 处**（不是 10），写 ≥10 会误报失败；弹窗 `#boardGrid .cell` 是 **289 格**（17×17），不是 400；`page.waitForEvent` 在本机 puppeteer-core **25.7.0 已移除**，用 `page.once('popup')`。

**B. 针对 `index.html`**（文件名带 `_index`，2026-09-15 加入）

| 脚本 | 用途 |
|---|---|
| `extract_engine_index.py` | ⚠️ **2026-09-22 起已被 `extract_engine_task3.py` 取代**（`python3 extract_engine_task3.py index.html` 等价），头部已加废弃标注、仅为兼容保留。从 `index.html` 抽最长 `<script>` → `engine_index.js` |
| `run_board_index.js` | **71 项** VM 回归（**棋盘专项**，比 `run_e2e_task2.js` 窄但含 index 独有断言）。覆盖：`RAIL_LINES` 14 条 + 行号不重复 / `isRailway` 与 `railLinked` 双层语义（行 7·9、列 7·9 的交叉格是 `true` 但线段是 `false`）/ `buildBoardSvg()` 段数 100 直 + 100 芯 + 4 弧 + 4 弧芯 + 64 斜线（斜线用独立算法复算）/ 图层顺序 / 端点全是格心 / `buildBoardGrid()` 289 格 + 18 列头 + 17 行头 + 25 plain + 9 station + 8 hq + 20 camp + 无 `railway-h\|v` / 端到端两条数据源 13 个面板非空（**含 index 独有的 `techScoreGrid`**）+ 零 `undefined/NaN` + 棋子 100 枚四色各 25 + `gotoStep` 逐步重绘。用法：`python3 extract_engine_index.py && node run_board_index.js` |
| `shoot_board_index.js` | **17 项** 真实 Chrome 实拍 + 探针（阈值判定）。实拍 `idx_board_light/dark.png`、`idx_full_light.png`、`idx_tech_light.png`、`idx_popup_light/dark.png`；断言铁路 100/100、弧 4/4、斜线 64、SVG `544x544`（=17×32）、中央 plain、行营环 3px、棋子 `30x25`、弹窗 `--cell-size:46px` + 棋子 `43x36` + 289 格、**技术积分 4 卡 4 奖牌 + 称号徽章 ≥1 且 animationName = `techPop, techGlow`**（这三条是「棋盘迁移没把 B 类功能搞回退」的守门断言）、零 pageerror |
| `run_sfx_flags.js` | **14 项** VM 单元：造两子局面直接打 `resolveMove()`，验证「司令阵亡」`event.cmdr` 标记。正向 6 例（军长吃司令 / 司令被反吃 / 司令触雷 / 炸弹炸司令 / 司令中炸 / 司令司令同尽）+ **反向 6 例**（司令吃子、军长撞司令、炸弹炸军长、师长吃营长、工兵挖雷、司令扛旗 —— 均不得置位）+ 覆盖性检查。**演示棋谱只有 1 处司令阵亡（同尽），其余分支必须靠这个脚本覆盖。** |
| `run_sfx_index.js` | **35 项** 真实 Chrome 音效专项：6 条采样解码成功与 duration/声道指纹（**bounce 0.518s/1ch**，2026-09-16 起与 eat 不同）、type→采样键 12 条映射、**逐步走完全场并逐步比对「实际发声键 == 独立 spec 期望键」**、司令阵亡标记与独立统计一致 + 无误报、静音开关、**弹窗点 `#btnNext` 代理后主窗仍发声**、零 pageerror。做法：patch `AudioContext.prototype.createBufferSource/createOscillator`，在 `start()` 里把 `s.buffer` 反查成采样键记进 `window.__log`（用 `pairs.find(p=>p[1]===s.buffer)`，**不要去给 AudioBuffer 挂属性**）。 |
| `run_zhabait.js` | **30 项** VM 单元：「骗炸」触发条件专项（2026-09-20 收紧口径）。造「我方两子 + 目标格敌方一子」局面直接喂 `computeTechScore(replay, null, null)`（**`analysis` 可传 null**，只有 `baseLayout/baseMoves/baseOrient` 必需），读 `out.tech[色].skills['骗炸']`。正例 8（团长 35 / 营长 25 / 连长 18 / 排长 12 / 工兵 8 各档 + 令子已降级 + 蓝方炸弹亦算敌方）+ 反例 12（旅长/师长/军长/司令 超等级、自身即令子、`ap` 是炸弹、**队友炸弹**、地雷、被反吃、吃子、普通移动、同色目标）+ **判定时点专项 2**（令子＝团长时用团长撞炸不计 vs 同一局面用营长撞炸计 —— 若把判定挪到 `resolveMove()` 之后，此例会红）+ 计分去重 3 + 源码级口径 5。用法：`node run_zhabait.js`，支持 `ENGINE=<路径>` 落盘前预演。**⚠️ 造局面时「我方」必须另外放一枚更大的子**，否则被测子本身就是我方绝对令子、恒被条件 ② 拦住。 |
| `shoot_zhabait_index.js` | **8 项** 真实 Chrome：「骗炸」口径实机验证。断言页面 `TECH_SKILLS['骗炸'].d` 已含「限「团长及以下」子力…不得为我方当前绝对令子」、计分规则弹窗「操作技巧分项」表内该行文案已同步、**载入真实 `.jgs`（默认 `junqi2026_6_20_12_3.jgs` → 黄方 骗炸 +25）后结算卡出现「骗炸」分项且分值 ≤35**、零 pageerror。实拍 `idx_techrule_light.png`（计分规则弹窗）、`idx_zhabait_card_light.png`（4 张结算卡）。可用 `JGS=<路径>` 换样本。 |
| `run_lingyan.js` | **34 项** VM 单元：「令子言杀」触发几何 + **终局口径**专项（2026-09-20）。同样直接喂 `computeTechScore(replay, null, null)`。正例 6（撞明后打另一侧 / 吃过子力后已明 / 左右对称 / 和局 20 / 令子降为军长时次令子降为师长）+ **分值口径 7**（胜 40 / 和局 20 / 战败不出现 / 无 meta 未分胜负不出现 / meta 写「一方战败」「有玩家逃跑」不出现 / 仅一方出局判不出胜队不出现 / 队友先亡而敌两家全灭仍 +40）+ 反例 9（目标非敌方、令子未明、打令子本人、非次令子、改用炸弹、落点中线、令子中线、同侧×2）+ 一局只记一次 3 + 源码级口径 9。**反例一律给「和局」终局**，这样若误触发会以 +20 现形，不会被「0 分不出现」掩盖成假绿。另注：`run_lingyan.js` 的 `scenario()` 造局时**四家各留一枚可动子**，否则无子的一方会在第 1 步被自动判负、污染终局判据。 |
| `shoot_lingyan_index.js` | **11 项** 真实 Chrome：「令子言杀」终局口径实机验证。断言规则弹窗该行文案与 `+40`、**三个真实样本**结算卡分别出现 `令子言杀 +40`（胜）/ `+20`（和局）/ **完全不出现**（战败）。样本可用 `WIN_JGS` / `DRAW_JGS` / `LOSE_JGS` 覆盖；默认 胜 `junqi2025_10_25_16_40.jgs`[黄] / 和 `junqi2025_10_27_19_59.jgs`[黄] / 败 `junqi2025_10_26_14_9.jgs`[绿]。实拍 `idx_lingyan_rule_light.png`、`idx_lingyan_win_card_light.png`、`idx_lingyan_draw_card_light.png`。⚠️ 读结算卡时 `#techCard > div` 会把「装着四张卡的外层容器」也选进来 → 每项被统计两遍，**断言前必须用 `Set` 去重**。 |
| `scan_lingyan_index.js` | **口径影响面扫描（页面同源链路）**：`node scan_lingyan_index.js <engine.js>`。走 `.jgs → jgsToText → parseReplay → applyOrient → analyze → computeTechScore(r, analysis, null)`，输出触发次数 / 分值分布 / 终局归属分布 / 三档样本文件名，并对比「本地兜底 vs 页面 analysis」两条终局判据链路的不一致条数（应为 0）。**换任何「按终局判据」的分项口径，改用它量化后再汇报。** |
| `shoot_moqi_index.js` | **10 项** 真实 Chrome：验证「操作技巧分项 · 磨棋」已删除。断言页面 `TECH_SKILLS` 恰 3 项（`令子言杀/骗炸/无损`）且无 `磨棋`、计分规则弹窗「操作技巧分项」表恰 3 行且全文不含磨棋、真实样本 `junqi2025_10_25_16_40.jgs`（四家原本各触发磨棋）结算卡无任何 `磨棋` chip 且技术积分 **118/118/67/48 → 108/108/57/38**（每家 -10；蓝方的「操作技巧」由 +10 归为 **+0**）、零 pageerror。实拍 `idx_moqi_rule_light.png`（完整弹窗）、`idx_moqi_card_light.png`。⚠️ `.tech-chip` 同时用于「基础得分/称号/技巧」各类项，断言只应按「是否含磨棋」过滤，别限定类别。 |
| `scan_moqi_index.js` | **删除项影响面扫描（页面同源链路）**：`node scan_moqi_index.js <旧引擎.js> <新引擎.js>`。对全库 191 份统计磨棋触发条数 / 分值合计 / 全部玩家技术积分合计，并**核对「技术积分总降幅 ≡ 被删项分值合计」**。实测 581→0 条、5810→0 分、78225→72415，差值核对一致。同表还会打印两版引擎的 `TECH_SKILLS` 键名与是否含被删项。 |
| `diag_ownview_index.js` | **「己方视角」全库普查**：`node diag_ownview_index.js <engine.js> [file.jgs ...]`。走页面同源链路，打印每份的 `myColor` / `ownColorOf` / `baseOrient` / `rotK`，并**实测旋转后该色棋子的行区间**判定它究竟落在 up/down/left/right 哪半场（标签区位：上下家需 `cMin>=6 && cMax<=10`，左右家需 `rMin>=6 && rMax<=10`）。不给文件名即扫全库。实测 191/191 全部落在下方、0 例外；分布 `紫(left,rotK3):52 / 紫(right,rotK1):1 / 绿(down,rotK0):54 / 蓝(right,rotK1):41 / 黄(up,rotK2):43`。**改任何方位/视角逻辑后先跑它，10 秒出全库结论。** |
| `shoot_ownview_index.js` | **9 项** 真实 Chrome：默认（`localStorage` 空 → `{mode:'self'}`）己方视角链路。断言 `ownColorOf` 已知、默认视角=self、下拉选中 `self`、`viewColor`=己方、**己方 25 枚全部 `rMin>=11` 且 `cMin=6,cMax=10`**、四家各 25 枚、只有己方在 `down`、零 pageerror。产出 `idx_ownview_board_light.png` / `idx_ownview_meta_light.png`。`HTML=<路径>` 可换页面，`node shoot_ownview_index.js <file.jgs>` 可换棋谱。 |
| `repro_ownview_index.js` | **视角偏好归因**：`node repro_ownview_index.js [file.jgs]`。四个场景各跑一次并打印（下拉值 / 提示文案 / `ownColorOf` / `viewColor` / `rotK` / 己方落位）：① `{mode:self}` 对照 ② **`{mode:player,name:不在本局}`（失配，历史的 bug 现场）** ③ `{mode:player,name:本局玩家}`（用户主动选，应保留不覆盖） ④ 剔掉「己方=」行的文本（识别不出己方）。判定标准：**只要 `selVal==='self'` 而 `viewColor==null` 就是脱节**。⚠️ 必须 `reload()` 后再导入——`loadViewPref` 只在载入/切换时读，改 localStorage 后不刷新不生效。 |
| `shoot_viewfix_index.js` | **9 项** 真实 Chrome：复刻用户场景（偏好失配）后的实拍 + 断言。断言解析退回 `self`、解析出的颜色=己方颜色、下拉与解析一致、`viewColor` 有色值、己方 25 枚在下半场、**提示不再出现「文件原始方位」**且含「为下家」、`resolveView(null,self)` 不崩、零 pageerror。产出 `idx_viewfix_board_light.png`（己方在下方）、`idx_viewfix_row_light.png`（视角行：下拉与提示同步）。 |

**⚠️ index.html 专有的测试坑（逐轮累积）**
1. **`renderMoveList` 里的称号徽章是「数据相关」的**：`DEMO_TEXT` 样本不触发任何称号，只有内置 `.jgs` 样本（`#btnLoadDemo` 载入的是 `DEMO_JGS_B64`，**不是** `DEMO_TEXT`）才触发。**不能硬断言「一定有徽章」**，要与 `sandbox.techScore.titleLog` 对账：渲染出的 `.mvtag.tech` 数 == `titleLog` 中 `stepIdx ∈ [1, replay.moves.length]` 的条数；再汇总断言「两数据源合计 ≥1 枚」。
2. **`__dirname` 层级别照抄 Python 的 `os.path.dirname` 三次**：Python 的 `abspath(__file__)` 含文件名，要 3 次才能到项目根；Node 的 `__dirname` 已是目录，**2 次**即到项目根（写 3 次会去找 `/Volumes/me/ai学习/四国军棋/index.html`，报 `ERR_FILE_NOT_FOUND`）。
3. 顺带一条核对高亮的姿势：高亮类名是 **`highlight-from` / `highlight-to`**（不是 `hl-*`），加在 `#cell-<row>-<col>` 上，且 `from/to` 是 `[行, 列]` 顺序。用 `gotoStep(n)` 后 dump 带这两个类的格子 id，即可 1 秒验证「红框 → 终点」与行棋坐标一致。
4. **⚠️ 截图前清理提示条只能「隐藏」不能 `remove()`**：页面 `toast()` 直接 `document.getElementById('toast').textContent = msg`（**无空值保护**），`#toast` 节点一旦被删，之后任何一次 `toast()` 都抛 `TypeError: Cannot set properties of null`；更阴的是 `.jgs` 导入路径那次 `toast()` 位于 `try` 内，异常会被 `catch` 吞成「JGS 解析失败」并再抛一次，把真实原因彻底掩盖。统一写 `forEach(e => { e.style.display = 'none'; })`（见 `shoot_zhabait_index.js` 的 `hidetoasts()`）。排查姿势：逐段 `page.on('pageerror')` 计数 + 打印 `e.stack`，能直接看到 `at toast (…index.html:4064)` 与调用点行号。
5. **⚠️ 截「长弹窗」元素图前不要对目标行 `scrollIntoView`**：puppeteer 的 `elementHandle.screenshot()` 只截「元素 ∩ 视口」，把深处的行居中会把弹窗**顶部的行滚出视口**，截出一张「缺一截」的图 —— 2026-09-20 据此误判「称号表少了一行」，回头查 `grep -c 横扫千军` 三个版本（含上轮备份）都是 7 处，才确认是截图裁切而非数据问题。正确姿势：把 `setViewport` 高度调到能装下整个弹窗（如 `height: 1700`），截图前只把内部 `scrollTop` 归零。**判据是「三处（当前版 + 两个历史备份）计数一致」即可排除文件被第三方改动，先查这个再怀疑数据。**

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
python3 extract_engine_task3.py index.html && node run_board_index.js   # VM 回归，应为 71 通过 / 0 失败
node shoot_board_index.js                                    # 实机探针 + 实拍，应为 17 通过 / 0 失败 + 页面零错误
```

覆盖 `RAIL_LINES` / `isRailway` / `railLinked` / `buildBoardSvg()` / `buildBoardGrid()` / 棋子四色 / 弹窗尺寸，并**守门断言技术积分 4 卡 · 4 奖牌 · 称号徽章动画未被棋盘改动回退**。改棋盘视觉时这两条命令是「改动是否等价」的最快判据。

### 第 5.4 步：方位推导专项（改 parseJGS 方位 / 碰布局铺盘 / 碰 teamSplit 时必跑）

```bash
cd "<项目>/.workbuddy/tests"
python3 extract_engine_task3.py index_task2.html && node run_orient.js   # 65 项，应为 65 通过 / 0 失败
```

**必须跑**：方位一错就是连环塌方（0 棋子 + 3:1 分队 + 三个名字的「胜队」+ 行棋序条空白 + 棋盘被转 180°）。
另建议顺手跑一次全库自洽率扫描（`/tmp/scan_orient.js` 那套：191 个 .jgs 逐个比对「引擎方位 vs 48 假设最优」），
正确实现应当是 **191/191 全部 100% 自洽**。

### 第 5.5 步：胜负判定专项（改胜负 / 改 alive 口径 / 碰扛旗分支时必跑）

```bash
cd "<项目>/.workbuddy/tests"
python3 extract_engine_task3.py index_task2.html && node run_winrule.js   # 两个引擎 × 41 项，应为 41 通过 / 0 失败
```

**必须跑**：这条规则一错，画面就会把「净值 +349 的一方」标成负、「−95 的一方」标成胜，用户一眼就能看出来。

### 第 6 步：音效专项回归（改音效 / 碰 resolveMove / 碰事件步时必跑）

`index.html`（音效系统在此先行实现）：

```bash
cd "<项目>/.workbuddy/tests"
python3 extract_engine_task3.py index.html && node run_sfx_flags.js   # cmdr 标记单元，应为 14 通过 / 0 失败
node run_sfx_index.js                                      # 真实 Chrome 音效专项，应为 35 通过 / 0 失败
```

`index_task2.html`（2026-09-16 起同款实现）：

```bash
cd "<项目>/.workbuddy/tests"
python3 extract_engine_task3.py index_task2.html && node run_e2e_task2.js   # 含 F11 音效 + F12 明暗棋断言，应为 201 通过 / 0 失败
node verify_sfx_task2.js                                   # 走完整份棋谱统计音效触发，应为 13 通过 / 0 失败
node verify_hidden_task2.js                                # 点棋子＝盖牌/明棋 交互，应为 28 通过 / 0 失败
node verify_ownview_task2.js                               # 己方视角链路，应为 21 通过 / 0 失败（加 index.html 参数可测另一页面）
node diag_ownview_index.js engine_index.js                 # 全库 191 份「己方视角下己方是否落下方」普查，应为 0 份例外
node shoot_ownview_index.js                                # 真实 Chrome 默认己方视角链路，应为 9 通过 / 0 失败
node shoot_viewfix_index.js                                # 复刻「换棋谱后偏好失配」场景 + 实拍，应为 9 通过 / 0 失败
node repro_ownview_index.js                                # 视角偏好四场景归因（改视角/偏好逻辑时用它定位）
node verify_eval_task2.js                                  # 全库 764 条评分不变量，应为 6 通过 / 0 失败
ENGINE=engine_index.js node verify_eval_task2.js           # 同一套断言跑 index.html 的引擎（两引擎结果必须一致）
ENGINE=/tmp/engine_new.js node verify_eval_task2.js        # 落盘前预演：拿改版引擎先验，全绿再覆盖源文件
node verify_path_task2.js                                  # 行棋路线压铁道（VM + 全库 34461 步），应为 24 通过 / 0 失败
node verify_pathdom_task2.js                               # 页面红色轨迹压铁道 + 实拍，应为 7 通过 / 0 失败（加 index.html 参数可测另一页面）
node verify_scrollfollow_task3.js                          # 回放不强制跳回行棋记录底部，应为 12 通过 / 0 失败（加 pre 拿改动前备份做对照）
node verify_scrollfollow_task3.js index.html               # 同一套断言跑 index.html
```

**「落盘前预演」技巧**：`run_board_index.js` / `run_sfx_flags.js` / `run_zhabait.js` 都支持 `ENGINE=<路径>` 环境变量指定引擎，
把改版先写到 `/tmp/...html` → 抽脚本 → `ENGINE=/tmp/engine_new.js node run_*.js`，全绿再 `cp` 覆盖 `index.html`，避免脏改动落盘。

### 第 7 步：计分口径专项（改 `TECH_TITLES/RULES/SKILLS` 任一触发条件时必跑）

```bash
cd "<项目>/.workbuddy/tests"
node run_zhabait.js                                        # 骗炸门槛单元，应为 30 通过 / 0 失败
node shoot_zhabait_index.js                                # 真实 Chrome 口径 + 结算卡实拍，应为 8 通过 / 0 失败
node run_lingyan.js                                        # 令子言杀触发几何 + 终局口径单元，应为 34 通过 / 0 失败
node shoot_lingyan_index.js                                # 真实 Chrome：规则弹窗文案 + 胜40/和20/败不出现，应为 11 通过 / 0 失败
node shoot_moqi_index.js                                   # 真实 Chrome：技巧表仅 3 项 + 结算卡无磨棋，应为 10 通过 / 0 失败
node scan_moqi_index.js <旧引擎.js> engine_index.js         # 删除类改动的影响面（旧 vs 新），差值须恒等于被删项分值合计
ENGINE=engine_index.js node verify_eval_task2.js           # 全库 764 条不变量（口径改动不得影响五维评估）
```

**口径改动的影响面必须量化后再交付**：用「造局面单测」只能证明分支对，证不了「真实棋库变了多少」。
姿势是拿「改前备份」与「改后文件」各抽一次引擎，对全库 191 份 `.jgs` 统计该分项的触发次数与分值分布
（骗炸：304→185 次 / 11510→3090 分；令子言杀终局口径：103→49 次 / 4120→1740 分；
**删除磨棋：581→0 条 / 5810→0 分，技术积分合计 78225→72415**），把数据一并汇报给用户。
改前引擎从备份抽：`cp index.html.bak_xxx /tmp/old_index.html`（**必须是 `.html` 后缀**，否则 Chrome 不按页面加载；
纯 Node VM 抽脚本则无此限制）。

⚠️ **「删除某一计分项」是特殊的口径改动，必须多核对一条不变量**：`Σ全部玩家技术积分` 的降幅
**必须恒等于**被删项的分值合计（见 `scan_moqi_index.js` 的「差值核对」）。两者不等就说明删除动作
泄漏到了别的分项（例如误删了与它共用计数器的其它 grant，或 `per` 字段被别处读取）。
磨棋的触发率极高（**764 张结算卡里 581 张 = 76%**，几乎等于人手白送 10 分），删掉后技术积分的区分度明显提升。

⚠️ **全库扫描必须走页面同源链路**，见 `scan_lingyan_index.js`：
`parseJGS()` → `jgsToText()` → `parseReplay()` → 手动补 `baseLayout/baseMoves` → `applyOrient()` → `analyze()` → `computeTechScore(r, analysis, null)`。
**直接拿 `parseJGS().moves` 喂 `computeTechScore` 是错的** —— `parseJGS` 的 `moves` **不含事件步**（样本 263 vs 页面 268 步）、
且返回值**没有 `meta` 键**，`analysis.alive` 会全判存活、`meta['结果']` 恒为空 → 凡是「按终局判据」的分项统计会整体走偏
（2026-09-20 据此误报「102 → 17」，走对链路实际是 103 → 49）。扫描脚本同时比较
「本地推演兜底（analysis=null）vs 页面 analysis」两条链路，不一致条数应为 0。

## 表现评估（五维评分）三条铁律（2026-09-20 修正，最容易再犯）

> 触发场景：用户报「某玩家子力净值是正数，表现评估却给出『子力交换亏损』的结论」。

- **失着惩罚必须按「金额」而非「次数」，且不能每个维度都扣一遍**。
  旧实现把 `- mistakes * N` 同时塞进五个维度（exchange 10 / insight 5 / teamwork 4 / clutch 6 / mental 3 = **28 倍/次**），
  5 次失着即 **-140**，把所有维度一并压穿 → 净值 +61 也判「交换亏损」。
  现改为新增 `s.失着损`（每次失着累加净亏价值：撞子被吃＝`VAL[阵亡子]`；被小子吃大子／同尽亏＝`VAL[防守子]−VAL[进攻子]`），
  再折算 `mistakePenalty = clamp(失着损 * 0.08, 0, 25)`，只在 insight / teamwork / clutch / mental 里按 `0.6 / 0.5 / 0.6 / 0.4` 分摊。
  **不要改回按次数扣分，也不要加到 exchange 维度里。**
- **exchange 维度的主锚是「交换比」`得分/(得分+损失)`，不是「相对同局均值」**。
  全场 `Σ得分 ≡ Σ损失`，故 0.5 天然是中位且不受同局极端玩家拉偏；旧的「相对同局均值」会被净值 -113 这种玩家带偏，
  出现过**相对 +81.3 仍判亏损**。现公式：`clamp(50 + (ratio-0.5)*300 + netSign + clamp((攻击效率-4)*3, -12, 12) + highOps*2, 0, 100)`，
  其中 `netSign` 只在**净值与交换比同号**时给 ±6（防止「净值 +1」被抬成占优）；**公式内不含失着项**。
- **「子力交换占优 / 亏损」的文案与标签必须与净值同号**：`ev.exchange >= 65 && s.净值 > 0` 才说占优，
  `ev.exchange < 45 && s.净值 < 0` 才说亏损。两处都要改：`computePlayerEval` 里的 tags、`buildSummary` 里的 parts。
- **改完必跑全库校验**：191 份 `.jgs` / 764 条评估，「净值正 ↔ 亏损」+「净值负 ↔ 占优」矛盾条数必须为 **0**
  （`.workbuddy/tests/verify_eval_task2.js`，两个引擎各跑一遍）。修正后评级分布 S:0 / A:14 / B:346 / C:291 / D:113
  （修正前 D 有 300 条 —— 过度惩罚所致）。
- ⚠️ **2026-09-24 数据校准的推翻性结论**：上面第 1 条的「失着」**本身几乎无判别力** ——
  2332 局实测 AUC 仅 **0.376**（次数）/ **0.338**（金额）；再按「信息是否已知」把撞子拆成「探路成本 vs 真失误」
  也只有 0.391 / 0.450（`split_blunder.py`）。根因：**撞子被吃是四国军棋必需的信息获取手段，不是水平差异**。
  ⇒ **失着是待移除项，不要再给它加码**。下面新节的 v3 方案已不含量级失着惩罚。

## 联众复盘数据校准与表现评估 v3（2026-09-24 新增）

> 触发场景：任务是「用大师复盘校准/提升玩家表现评估」「为 AI 机器人打地基」，或任何涉及
> `/Users/wangjian/Downloads/联众复盘/联众复盘` 下 `.JQH.TXT` 文件、`.workbuddy/ld/` 工作区的场合。
> **交付报告**：`qq军棋复盘分析/评估公式数据校准报告_20260924.html`。
> **结论一句话**：现有五维公式是「净值复读机」（`total↔净值` 0.910），v3 在玩家级准确度上首次超过 v1。

### 1. 联众 `.JQH.TXT` 格式要点（与 QQ `.jgs` 完全不同的体系）

- **编码 GBK**（2491/2491 严格解码成功）；行分隔 **CRLF**；头 `Junqi Output Text File by www.ourgame.com` +
  `Version 1.31.0.2.1998.710`（全库统一）。**Node 侧无 GBK 解码 ⇒ 断言只能看颜色/方位/坐标，不能比玩家名**。
- **棋盘 = 17×17 ASCII 字符栅格**（恒 24 行），与 QQ 的「每玩家 6×5 矩阵」完全不同。
- **坐标映射 = 「映射 A」**：行标签全角 `Ａ Ｂ Ｃ Ｄ Ｅ Ｆ Ｇ Ｈ Ｋ Ｍ Ｎ Ｐ Ｑ Ｒ Ｓ Ｔ Ｗ`（17 个，跳过 I/J/L/O/V/X/Y/Z）→ `row = ROW_MAP[字母]`；
  列用数字 1..17 → `col = num - 1`。8 种候选映射横向评测：A 首步命中率 **64.3%**（次优仅 43.6%）。
- **行棋序 = 顺时针**，即 `[up, right, down, left]`（**QQ 是逆时针，这是两者唯一规则差异**）。
  决定性实验：顺时针零误差 **2314** / 逆时针 23 / 双向 0。
- **颜色名不固定**：实测 4 种配色（上蓝/下红/左绿/右灰 1887 次；上红/下蓝/左灰/右绿 431；上绿/下灰/左红/右蓝 88；上灰/下绿/左蓝/右红 85）。
  **颜色只标识玩家、与方位无关** ⇒ 玩家行正则必须是 `^(上|下|左|右)(蓝|红|绿|灰)(\*?)\s*[:：]\s*(.*)$`，**不要写死配色**。
- 玩家行标记：`*` = 本方（录制者）；`(first move)` = 先手；`win` = 胜利；`break` = 断线。
- 字符含义：`P` 普通格 / `C` 行营 / `H` 大本营 / `R` 铁路通过点 / `.` 空白。
  ⚠️ **中央 5×5（行/列 6-10）里 9 个 `H` 是「兵站」（可停留、初始空），16 个 `R` 不可停留**。
  `cells_of_row()` 必须排除中央 5×5，否则 2491/2491 全解析失败（曾报 `piece_count 12 vs 15`、`orphan_piece`）。
- ⚠️ **只解析「4 人局」**：2491 份里 112 份不可用（111 份是 2 人对局、1 份无棋子），且这 112 份**全是「G 行无棋子」**（隐藏棋子渲染模式）。

### 2. ⚠️ 地雷规则定案（本次最重要的规则发现，最容易搞错）

**非工兵棋子碰地雷 → 攻方阵亡、地雷原地保留**（**不是**同归于尽）。

判定过程（两步，都可复现）：
1. `test_mine_rule.py` 全库对照 —— 假设 B（雷存活）零误差 **2332 (98.02%)**，假设 A（同归）2314 (97.27%)；
   B 在 4 项指标里 3 项更优：`from_empty` 319→295、`friendly` 62→23、`turn_mismatch` 6127→6093。
2. `prove_mine.py` 铁证 —— 全库 **40 个格位出现「同一格 ≥2 次非工兵触雷」**，单格最高 `(6,1)` **触雷 154 次**。
   **若同归于尽，第二次触雷在物理上不可能发生** ⇒ 假设 A 必然错误。

⚠️ **`index_task2.html` 的 `autoResult`/`resolveMove` 的 `mine` 分支（攻方消失、`layout[to]` 保留地雷）是正确的，别改**。
统计：非工兵触雷 2128 次 / 工兵挖雷 3874 次 / 炸弹碰雷 70 次。

### 3. 数据管道（`qq军棋复盘分析/.workbuddy/ld/`）

```
jqh_parse.py  → dataset.jsonl (2379 局：{file, mates, players, pieces, moves})
replay_drive.py drive()  → 逐步事件流（供验证/诊断/统计共用）
junqi_engine.py          → 走法生成 + 战斗结算 + 顺时针 next_alive
extract_features.py → features.jsonl (2332 局 × 4 方 × 20+ 维)
dump_features.py    → v2feat.jsonl (8524 样本：v1 分维分 + v2 原始特征)
```
- **质量闸门 = 只保留零误差局**（`turn_mismatch`/`from_empty`/`friendly`/`illegal` 全为 0）：2332 局。
- 有明确胜负 2091 局（win 标记恰 2 家）；不同玩家 1183 人，**≥20 局者 84 人**（可做玩家级统计的最低样本量）。
- ⚠️ **`turnState` 陷阱（改引擎必看）**：`turn` 初值必须取「第一个**起点确实有棋子**的走子」的所属方位
  （置 `None` 会让后续每步都判 mismatch）；**事件行（Pass/GiveUp）必须推进 turn**（否则其后全局错位）；
  `apply_move` 的 `killed` 是「被消灭棋子所属方位列表」，用它递减 `cnt` 判出局。

### 4. 现有五维公式的诊断（5 项硬伤，改公式前必读）

| # | 问题 | 量化证据 |
|---|---|---|
| 1 | **五维高度共线** | `exchange↔净值` Pearson **0.961**、`total↔净值` **0.910**、`exchange↔mental` 0.814 ⇒ 五维实际只有 2~3 个独立信号 |
| 2 | **insight 退化** | 均值 13.11、**28.8% 样本压在下界 0**。病因 = `counterKills*6` 用「被反吃**绝对次数**」且无上限 |
| 3 | **clutch 压扁** | 均值 77.15、**11.2% 触顶 100**、标准差仅 13.27 |
| 4 | **失着判定无效** | AUC 0.376 / 0.338；按「已知 vs 未知」拆也只有 0.450 / 0.391 |
| 5 | **「战败即扣分」冤枉牺牲者** | **20.53%（426/2075）的胜局里赢家联盟折了一家**，其对家仍单独赢下；落败方联盟则 100% 两家全被清盘 |

⚠️ **第 5 条的规则背景**：`win` 标记的 2 家 **100% 是对家（同一联盟）**；因为「扛旗只让被扛家出局、队友仍可继续作战」，
所以**「某玩家出局」≠「他表现差」**。现有 `mental` 的 `isDefeated ? -10 : 0` 应移除。

### 5. v3 重构方案（已验证 · **已落地三页：`index_task2.html` ≡ `index_task3.html` ＋ `index.html`**）

**候选特征先按 (AUC, 与净值共线度) 双筛**（`feature_lab.py`），入选与实测：

| 维度 | 权重 | 主锚 | AUC / 与净值相关 |
|---|---|---|---|
| 子力交换 | 0.22 | 交换比 `ratio` | 0.857 / 0.966 |
| 信息判断 | 0.16 | 攻防成功率 `hit = 吃子/(吃子+被吃)` | 0.729 / 0.689 |
| 配合贡献 | 0.24 | 团队净值 + `countIntercepts` 策应 | — |
| 关键节点 | 0.24 | **残局净值变化 `late`** | **0.773** / 0.607 |
| 心理节奏 | 0.14 | 开局净值变化 `early` | 0.640 / 0.514 |

v3 公式（`eval_v3.py` 变体 E）：
```js
exchange = clamp(50 + (ratio-0.5)*300 + clamp((atkEff-13)*2,-10,10)
                 + (净值>0&&ratio>0.5 ? 6 : (净值<0&&ratio<0.5 ? -6 : 0)), 0, 100)
insight  = clamp(50 + (hit-0.5)*150 - (counterRate-0.0833)*40 + (atkShare-0.5)*20, 0, 100)  // ★★第二轮重标定，见 5.1
teamwork = clamp(50 + clamp(itc*7,0,21) + clamp(teamNet/12, -25, 25), 0, 100)
clutch   = clamp(50 + clamp(late*0.30,-20,20) + flag*18 + clamp(dig*7,0,21)
                 + clamp(bombNet*0.15,-12,12), 0, 100)                    // ★炸弹改按净收益
mental   = clamp(50 + clamp(early*0.25,-18,18) - clamp(mine*12,0,24)
                 + (净值>0 ? 14 : (净值<-60 ? -16 : 0)), 0, 100)          // ★无战败惩罚
total    = 0.22*exchange + 0.16*insight + 0.24*teamwork + 0.24*clutch + 0.14*mental
```
其中 `counterRate = 反吃 / 交手`（**分子必须用新增字段 `反吃`，绝不能用 `被吃`** —— 见第 7 节的字段陷阱）、
`atkShare = 主动手 / 交手`、`atkEff = 得分/步数`、`bombNet` = 炸弹净收益累计。

**验证结果**：

| 指标 | v1 | v3（含第二轮校准） | |
|---|---|---|---|
| **玩家级 Spearman（n≥20，78 人）** | +0.909 | +0.909 | 持平（insight 单维 +0.774→**+0.841**）|
| 可靠度 split-half（50 次平均） | +0.695 | +0.688 | 持平 |
| insight 维度 AUC | 0.694 | **0.751** | v3 优 |
| clutch 维度 AUC | 0.712 | **0.815** | v3 优 |
| insight 触 0 界 | 28.8% | **1.7%**（QQ 独立数据集 30.7%→**0.0%**）| v3 修复 |
| 单局 AUC / 局内前 2 命中 | 0.896 / 63.9% | 0.885 / 60.1% | v1 略优 |

#### 5.1 insight 二次校准（2026-09-24 第二轮）

诉求：让 `insight` 更偏「主动出手的判断力」。**数据结论：不要换 hit 口径，要重标定系数。**

| 候选 hit 口径 | 定义 | AUC | rho(净值) | rho(counterRate) |
|---|---|---|---|---|
| `hit_total`（现行） | 吃子 ÷（吃子+被吃） | **0.770** | +0.807 | −0.383 |
| `hit_atk` | (吃+挖雷) ÷ (吃+挖雷+被反吃+触雷) | 0.689 | +0.552 | **−0.857** |
| `hit_atk2` | 吃 ÷（吃+被反吃） | 0.668 | +0.511 | **−0.889** |

⚠️ **主动口径「双重受损」**：判别力掉 8 个点，且与 `counterRate` 相关 0.86 —— 因为「主动出手被反吃」
本来就是 `counterRate` 的分子，两者是同一件事的两种表达；换过去等于把维度变成单一信号的复读。

⚠️ **真收益在系数**：现状 90/160 本是拍脑袋定的；**5 折 CV（按局分折）每一折都独立选出 150/40**
（CV AUC **0.7504→0.7716**，insight 单维玩家级 rho **+0.774→+0.841**）—— 非过拟合。

**新增 `atkShare`（主动出手 ÷ 交手）作诊断项**：AUC 仅 0.581，但分档胜率**严格单调 40.4%→60.3%**、
与净值仅 **+0.260** 相关，是唯一独立「主动向」信号。代价：CV AUC −0.0014 / rho −0.0011（σ=0.0096 内）。
**要纯统计最优，删掉 `+(atkShare-0.5)*20` 即可。**

最终：`insight = clamp(50 + 150*(hit−0.5) − 40*(counterRate−0.0833) + 20*(atkShare−0.5), 0, 100)`
（基准 = 实测中位数，故 50 分 = 完全中性）。

⚠️ **必须理解的取舍**：v3 单局 AUC 低约 1 个百分点，是因为它**主动降低了「结果类信号」的重复计权**。
对「表现评估」而言，**玩家级准确度（+0.911）与维度诊断价值才是产品目标**；事后预测单局胜负没有产品价值。

### 6. ⚠️ 三个必须避开的分析陷阱

1. **别把「12 原始特征最优判别」的 CV AUC 0.9835 当目标**。它含 `team_net`（AUC 0.975）与终局附近的 `late`，
   是**标签泄漏**；照它改会把评分退化成纯结果复读。**表现评估的正指标是玩家级 Spearman，不是单局 AUC。**
2. **别用「胜/负组均值差」单独下结论**：结果类特征（`survive_val` 0.948、`net` 0.873）天然高 AUC 却无诊断价值。
   必须同时看**与净值共线度**（双筛）。
3. **别拿 4 人局内的顺序做「配合」判据**：`countSupport` 原实现按「对家走完己方紧接着走」计数，
   **顺时针行棋序下对家之间恒定隔着两家，只有出现玩家出局后才可能相邻**（实测仅 18.6% 样本非零）。
   真正有效的团队信号是 `countIntercepts`（对家净值 < -30 时本方吃子）。

### 7. v3 落地实现与字段陷阱（2026-09-24 完成，同日第二轮推广至三页）

**范围**：`index_task2.html` ≡ `index_task3.html`（同构铁律）**＋ `index.html`（竞技积分版，第二轮一并推广）**。
第一轮脚本 `port_evalv3_20260924.py`；第二轮改用 **`port_evalv3b_20260924.py`**（**以备份为输入源重建** ⇒ 幂等；
三页一次处理；新增 `主动手` 字段 + insight 新系数）。备份统一 `.bak_pre_evalv3_20260924`。
第一轮 499,727 → 505,253 B；第二轮 505,537 → 506,656 B（index：550,777 → 557,706 B）。

**`analyze()` 新增四项统计**（写进 `stats[c]`）：
```js
交手:0        // 己方作为攻方或守方参与结算的次数（eat/killed/both/dig/mine/flag）→ counterRate/atkShare 的分母
反吃:0        // 己方**作为攻方被反吃**（t==='killed'）→ counterRate 的分子
主动手:0      // 己方**作为攻方发起交手**（s 恒为攻方）→ atkShare 的分子
炸弹净收益:0   // 仅 both 分支、攻方视角：己方炸弹撞非炸弹 += 对方价值-35；己方非炸弹撞对方炸弹 += 35-己方价值
```
⚠️ `交手` 与 `主动手` 必须在**同一处**同时自增（`s.交手++; s.主动手++;`），分母才严格对齐。
另需 `curveAtIndex(color, idx, curve)` —— Python 校准脚本的 `late`/`early` 是**按 curve 数组索引**取的
（`i1=nc//4`、`i2=nc*2//3`），与页面既有的 `netAtStep`（按**步号**查找）**语义不同**，不要混用。

#### ⚠️⚠️ 三个「同名不同义」字段陷阱（混用则页面分 ≠ 报告分）

| 字段 | 直觉含义 | **真实含义** | 后果 |
|---|---|---|---|
| `stats["被吃"]` | 被反吃次数 | **总被吃**（`eat` 分支给守方 +1、`killed` 分支给攻方 +1） | 当作 counterRate 分子 → **高估 3~7 倍**（实测 7 vs 2） |
| `killRatio()` | 攻防成功率 | 仅**主动攻击**胜率 `eat/(eat+killed)` | ≠ 校准用的 `hit` |
| `hit`（校准口径） | — | **交手总胜率** `吃子/(吃子+总被吃)`，含防守被动交手 | 用 `killRatio` 顶替 → insight 整体偏高 |

⇒ **正解**：分子一律用新增字段 **`s.反吃`**；`hit` 直接算
`var hitAll = s.吃子 + s.被吃; var hitRatio = hitAll > 0 ? s.吃子/hitAll : 0.5;`，**不要调 `killRatio`**。

#### 保留 v1 做对照（推荐做法）
v1 实现**整体保留**，只改名 `computePlayerEvalV1`；`evaluateAll` 按全局开关分发：
```js
var EVAL_ENGINE = 'v3';   // 控制台 window.EVAL_ENGINE='v1' 可随时切回对照，便于同屏比较
var engine = (EVAL_ENGINE === 'v1') ? computePlayerEvalV1 : computePlayerEvalV3;
```

#### JS↔Python 数值对齐法（本次关键闸门，值得复用）
两页 HTML 只解析 `.jgs`（QQ，逆时针），而公式校准数据是联众 `.JQH`（顺时针）—— **两者无法同局对比**。
做法：`dump_for_js.py` 把 Python `analyze_py` 的 `stats / curve / steps / alive` 序列化注入 Node，
再用 `align_evalv3_20260924.js` 逐条比对 —— **300 局 / 1200 样本，特征层 + v1/v3 五维与总分 全 0 差异**。
桥接三条注意事项（少一条就出伪差异）：
1. 颜色键映射：Python `up/right/down/left` ↔ JS `绿/黄/蓝/紫`，映射须满足 `ALLY`（up↔down、left↔right）配对；
2. `captured` / `lost` 由元组 `(step, piece, kind)` 转对象 `{step, piece, kind}`；
3. `steps` 每条都要有 `move:{color}` —— **事件行也要给**，否则 `countSupport` 的 `prev` 更新行为与 JS 不一致。

#### 顺带修正的 Python 复现偏差
`count_support` 原实现写 `not s.get("event")` 排除事件行，但 JS 侧事件行的 `s.move.color` 是存在的
⇒ 事件方 == 己方时 JS **会**进入判断分支。已按 JS 语义改正（764 条里 3 条差异；v1/v3 指标几乎不变）。

#### 三层验证（全绿）
1. **公式数值对齐**：300 局 / 1200 样本 0 差异（方法见上）。第二轮起 **`engine_task2.js` 与 `engine_index.js` 各跑一遍**，
   确认 index.html 的引擎也同源。
2. **全量回归 26 套**：E2E 202、评估专项 6、hidden 28、path 24/34/8、orient 65、winrule 41、ownview 21、
   legend 17、board 71、scroll 12、duptitle 15、sfx 13、mobile 55、piecemark 45/21、markident 23、
   flagreveal 40/17/5、study 125/77/12、railstrict（页面 ≡ 严格模型）。
   ⚠️ **`run_sfx_index.js` 会报「33 通过 / 1 失败」**（「弹窗可打开」）—— 这是 **headless 弹窗被拦的环境性预存失败**，
   已用**改动前备份跑同一测试对照**证实（同样失败）。**别误判成回归**；`measure_markscale.js` 报 `MODULE_NOT_FOUND` 同理（缺依赖）。
3. **页面探针** `probe_evalv3_task2.js`（191 份 `.jgs` / 176 样本）：确认默认走 v3；
   **v1 的 `insight` 在独立数据集上同样 30.7% 触下界 0**，v3 → 1.1%（第二轮重标定后 → **0.0%**，维度 AUC 0.612→0.764）
   ⇒ **跨数据集互证：这是实现缺陷，不是联众数据特性**。

**实拍**（`shoot_evalv3_20260924.js`，同一局）：
v1 信息判断 `0 / 10 / 0 / 0`（三家雷达角塌陷）vs v3 `54 / 41 / 31 / 17`。

### 8. 下一步

- **观察本页实际效果**（落地与三层验证已完成）；确认无误后推广到含「竞技技术积分」的 `index.html`。
- **AI 机器人地基**：推演引擎已达 98.02% 零误差；**Phase 1（走法枚举 + 信息集 + 期望估值 + 决策质量指标）已于
  09-24 第四轮完成**，见下面第 9 节。**下一步 = 接搜索**（把 `eval_move()` 当现成局面评估函数上 minimax / MCTS）。
- **维度语义再打磨**：`hit` 现取「交手总胜率」（含防守被动交手）；可试验「仅主动攻击胜率」变体是否判别力更强。
- 玩家级长期胜率（算法见 `player_rating.py`）可作为机器人强度评估的**基准线**。

### 9. 替代走法评估（what-if）与 AI 机器人地基（2026-09-24 第四轮）

> 触发：任务是「AI 机器人地基接 what-if / 替代走法评估」「给失着一个站得住的定义」「做决策质量评分」，
> 或涉及 `.workbuddy/ld/whatif.py`、`run_whatif.py`、`final_whatif.py`、`ai_playout.py` 时。
> **交付报告**：`qq军棋复盘分析/替代走法评估报告_20260924.html`。

#### 9.1 ⚠️ 先修引擎漏洞：铁路走法不检查路径障碍（本轮最意外的收获）

`junqi_engine.gen_moves` 的 `rail_walk()` / `gen_rail_moves()` **完全不检查路径障碍**，会生成大量
「穿过棋子」的非法走法（what-if 候选池均值膨胀到 **141 个/步**）。页面侧 `railReachSet(r,c,blocked,isEng)`
本来就是对的（传了 `blocked`），**Python 侧漏了**。

修复后全库复验（2379 局 / 443,179 步）：**零误差局仍 2332（一个没少）**、`illegal` 0 → **22**（全在被淘汰的 47 局内）。

- ⚠️ **宽松口径的 `illegal = 0` 是假绿**：`want_moves=True` 用 `gen_moves` 做子集检查，超集**永不误报**。
  今后凡报「走法生成器 100% 覆盖」，必须确认用的是**严格口径**（路径障碍检查已开）。
- 修改仅涉及 `rail_walk` / `gen_rail_moves` / `gen_moves` 三个函数，均新增可选参数 `board`；
  修改前快照 `junqi_engine.py.bak_pre_mine_20260924`（更早）与 `junqi_engine.py.bak_pre_railblock_20260924`（本轮）。

#### 9.2 信息集模型（最关键的设计约束，别搞错）

暗棋 = **遮兵种、保位置与颜色**（skill「明棋 / 暗棋」节：遮字 + 保色 + 纯色牌背）⇒
**位置与归属全知，只有兵种未知**。由「位置全知」可做两条**纯可观测**的演绎推理：

1. **某格有子，且该格从未作为任何一步的起点或终点出现过 ⇒ 它就是初始那枚棋子。**
   （棋子要离开该格必须「作为起点」出现在某一步；要被换掉必须「作为终点」出现。）
   ⇒ 于是「初始位置 → 兵种」先验是**合法信息**，不是数据泄漏。
2. **地雷与军旗不能移动 ⇒ 它们只可能出现在「原封不动」的初始格上；已动过的格上出现它们的概率严格为 0。**
   （唯一例外是地雷原地被非工兵撞存活，但那种情况该格已进 `known`，分支不会执行。）

⚠️ **推理 ② 少不得**：不加时整池均匀分布里那枚军旗（1/25）会给每个未知格白送 `500 × 4% ≈ 20` 分，
表现为「**每步的最优得分都恒在 30 附近**」——这是第一版最典型的病征。

`init_prior.py` → `prior_init.json`：2379 局统计，每格 n 恒 2379。示例（up 方视角）：
`(0,8)` 地雷 0.68、`(0,7)` 排长 0.41 + **军旗 0.39**、`(8,0)` 地雷 0.60、`(6,11)` 师长 0.20 + 司令 0.19。

#### 9.3 估值与决策质量

```python
payoff(atk, dfd, waste=0)      # 攻方视角净子力收益；waste>0 时扣「大材小用」机会成本（仅供 AI 选步）
eval_move(...) = 期望交手收益 + W_ADV×推进格数 + W_CAMP×(进/出行营)
  # 目标已知 → payoff 直算；目标未知 → Σ p(兵种|信息集) × payoff(攻方子, 兵种)
evaluate_step(...) -> {actual, best, worst, loss=best−actual, rank, n, pct, c_actual, c_best}
```

- `legal_moves(board, side, ally)`：`gen_moves` 之上再排除己方/队友棋子、行营内的棋子。
  ⚠️ **2026-09-24 规则修正：曾有一个 `flag_locked` 参数用于排除「司令尚存活方位的军旗」，
  那是错的，已整段删除** —— 扛旗**不需要**任何前置条件（不需要军旗亮出、不需要对方司令先阵亡）。
  铁证：2379 局 / 1850 次扛旗中 **134 次（7.2%）发生在被扛方司令尚存时**。
  「司令阵亡 → 军旗亮出」只是**显示层**规则（决定盖不盖牌），与合法性无关。
- ⚠️ **`payoff` 有两套用途，别混**：玩家评分（`c_gain`）用 `waste=0`；AI 选步用 `waste>0`。
- 性能：**0.2 ms/步**（全库 43 万步约 80 s）。

#### 9.4 验证结果（全量 2332 局 / 433,455 步 / 9,314 玩家-局）

> ⚠️ **2026-09-24 修正（数字已重跑）**：本节原先的「子力净值」与「失着率」两个基线数字**是错的** ——
> `eval_whatif.py` / `final_whatif.py` 判 res 时混用了**短名**（`eat`/`killed`/`both`），
> 而引擎原生名是 `attacker_wins`/`defender_wins`/`both_die`/`dig`/`mine`/`flag` ⇒ 分支静默失效：
> 「失着率」实际只统计了触雷、「净值」实际只统计了挖雷−触雷。修正后**结论反转**。
> 详见「AI 机器人搜索层」一节第 2/4 小节。

| 指标 | 单局 AUC（修正后） | 玩家级 Spearman（84 人 ≥20 局） |
|---|---|---|
| **`c_gain` 平均交手期望收益** | **0.6918** | **+0.6107** |
| `gain`（含位置项） | 0.6911 | +0.5820 |
| **`net` 子力净值** | **0.6933** | **+0.7490** |
| `fail_rate` 失着率（修正后口径） | 0.3615（反向 ⇒ 0.6385） | −0.4991 |
| `fail_val` 失着损失 | 0.6655 | +0.4735 |
| `neg_rate` 负期望步占比 | 0.3829 | −0.2371 |

- **五档分档胜率均严格单调**：`c_gain` **24.4 → 33.9 → 42.6 → 53.0 → 70.7%**（跨度 46.3 点）；
  净值 **19.0 → 35.9 → 48.3 → 54.5 → 67.0%**（跨度 48.0 点）。
- ⚠️ **修正后 `c_gain` 不再优于净值**：单局 AUC 二者打平（0.6918 vs 0.6933），
  玩家级净值更强（+0.7490 vs +0.6107）；两者 Pearson 从 +0.116 升到 **+0.473**。
  ⇒ 「c_gain 是完全独立的信号」这个说法**要弱化**。
- **`c_gain` 仍然有用的地方**：它**不含任何结果信息、可在线计算**，而净值是事后诸葛
  （净值 = 全对局累计交手收益，天然带结果）。
- ⚠️ **对 v3 的增量有限**：v3_total 玩家级 **+0.9055** → 加 `0.25·z(c_gain)` 得 **+0.9142**（仅 +0.0086）
  ⇒ **不为它改动三页已落地的评分公式**。

#### 9.5 ⚠️ 单步贪心不是完整机器人（诚实的负面结论）

- 能走棋：**卡死 0 次**（7897 次决策全部枚举出候选）。
- 但与大师实际走法**平均排名 31.7**（候选中位 55–60，近随机）、top-1 重合率 7.6%。
- 四方对局（`ai_playout.py`）**全部 1200 步触顶打不出胜负**，场上仍余 21–55 枚棋子。
  根因：扛旗**虽无前置条件**，但军旗守得要死（周围有子与地雷），**必须多步规划**才能先打穿防线、
  再把棋子送到军旗格 —— 单步贪心看不到这条链条，于是双方互相僵持到步数上限。
  （⚠️ 别写成「因为必须先灭司令才能扛旗」—— 那是**错误规则**。）
- 参数实验（400 局）：**位置项对判别力零贡献**（去掉后 `c_gain` 完全相同）；**信息项 `W_INFO`（5/10/20）
  与战略价值表均使主指标单调变差** ⇒ 采用**最简模型**。
- ⚠️ `ai_playout.py` 的 `end` 标签要区分 `timeout`（步数触顶）与 `stuck`（全场无人可动）——两者曾混标。

#### 9.6 下一步

见「AI 机器人搜索层（Phase 2）」一节 —— 已把 `eval_move()` 的估值接上 **negamax + alpha-beta**
与 **PIMC 暗棋版**，并对局验证。风险口径 `payoff(..., waste)` 仍未在搜索框架下调参。

## AI 机器人搜索层（Phase 2：negamax + PIMC，2026-09-24 新增）

工作目录 `.workbuddy/ld/`。Python `/Users/wangjian/.workbuddy/binaries/python/envs/default/bin/python`。
交付报告 `AI机器人搜索报告_20260924.html`。

### ⚠️ 10.0 先读：四国军棋是**四暗**（2026-09-24 坚哥指出，**推翻上一轮 PIMC 全部成绩**）

**除了自己的棋子，另外三家都是暗棋 —— 包括队友和敌人。**
⇒ 每个方位各有**自己的信息集**：`up` 只知道 up 的 25 枚；`down` 只知道 down 的 25 枚；
**队友之间不共享棋子信息**（真实对局要靠「配合」去猜对家的意图）。

写任何 PIMC / 不完全信息代码前先逐条对一遍：

- `PIMCPolicy` **必须按单方构造**：`up` / `down` **各一个实例、各持自己的 `InfoSet`**。
- **严格区分两个集合，绝不混用**（混用 = 把队友当明棋，这就是旧 bug）：
  · `known_sides = {me}` —— 给**采样**（只有自己全知）；
  · `team = A_SET / B_SET` —— 给**搜索**里「我方 − 对方」的评估符号。
- `sample_world(board, info, known_sides, rng)` 的 `known_sides` **绝不能传整个联盟**。
- 「每方独立实例」的副作用是**好的**：AI 替队友走棋时，队友的牌在自己视角里已知
  ⇒ 不会输出非法着法。**单实例同时管 up / down 才会出问题** ——
  `apply_move` **不做兵种合法性校验**（「地雷 / 军旗 / 大本营棋子不能移动」只在**走法生成**里排除），
  采样一旦把队友的真地雷猜成可动子，就会**静默推进出非法局面**。
- 兜底断言：`drive_match(validate=True)` 记 `illegal[方位]`，**必须为 0**。
- `SW_PIMC_LEAK=1` 复现旧行为（连队友一起当全知），**只用于量化泄漏收益**，正式对局必须 0。

军旗的额外信息约束（同一轮一起修）：

- 军旗**只能落在该方大本营格**（`is_hq()`，全盘 8 格 = 每方 2 格，属公开信息）
  ⇒ 采样分**三层、约束紧的先分**：
  `moved`（动过的格，地雷 + 军旗**都**排除）→ `fresh`（未动过的非大本营格，可接地雷、排除军旗）
  → `hq`（未动过的大本营格，收尾，什么都能接）。
- **亮旗（司令阵亡）后军旗位置已公开 ⇒ 采样时钉死真值**，不参与采样。
  这与 `Searcher` 一致：`SW_THREAT` 用 `flag_pos` 但**仅在该方 `cmdr_dead` 为真时生效**
  （亮旗是全场可见的显示层规则）⇒ 不构成泄漏。
- ⚠️ 旧版把军旗采到任意未动过的初始格 ⇒ 而搜索的扛旗判定走的是**棋盘上的军旗格** ⇒ 会朝错格扛旗。

### 10.1 文件清单

| 文件 | 作用 |
|---|---|
| `search.py` | **搜索层核心**：`Searcher`（negamax + alpha-beta + 迭代加深 + 走法截断 + 战略项） |
| `match.py` | **对局驱动器**：`drive_match()` + 30 秒时限规则 + `on_move` 钩子 |
| `ai_search_check.py` | 完全信息自检（给 AI 上帝视角，逻辑正确性上界） |
| `ai_search_dark.py` | **PIMC 暗棋版**：`sample_world()` + `PIMCPolicy` + `--verify` 采样自检 |
| `measure_think.py` | 实测「思考时间 → 搜索深度/节点数」曲线 |
| `verify_search_20260924.py` | **断言式自检（17 项）**，改 `search.py` 后必跑 |

⚠️ **后台跑对局脚本重定向到日志时必须加 `-u`**（或 `PYTHONUNBUFFERED=1`）：
Python 的 stdout 在非 tty 下是**块缓冲**，不加 `-u` 时日志会一直空白、直到进程结束才一次性刷出，
看起来像「卡住了」。而 `ai_search_check.py` 的对照实验单局最长可跑 15 分钟，很容易误判。

### 10.2 ⚠️ 关键发现：标准 negamax 在这里直接成立（别去写四博弈）

```python
DIRS4 = ["up", "right", "down", "left"]     # 联众顺时针行棋序
联盟： {up, down} = 甲      {right, left} = 乙
轮转：  up(甲) → right(乙) → down(甲) → left(乙) → up(甲) ...
        max        min        max         min
```
**轮转序与联盟归属严格交替** ⇒ 树上 max/min 层天然交替 ⇒ **标准 negamax + alpha-beta 零改动可用**，
不需要 max<sup>n</sup> / 四博弈特殊处理。（某家出局后 `next_alive` 跳过，连环同阵营节点仍是正确的零和求解，
只是深度消耗变快。）

### 10.3 关键参数（全部可用环境变量覆盖，便于做变体实验）

| 参数 | 默认 | 作用 |
|---|---|---|
| `SW_K` | 8 | 每节点保留走法数（走法截断） |
| `SW_DEPTH` | 4 | 最大深度（**半步**；迭代加深步长 2） |
| `SW_TIME` | 0.4 s | 每决策时间预算 |
| `SW_NODES` | 0 | **>0 时优先于时间预算**（确定性、可复现） |
| `SW_UNLOCK` | 80 | 对方司令阵亡 ⇒ 其军旗可被扛（己方对称扣分） |
| `SW_THREAT` | 30 | 军旗逼近奖励（反比、双向；设 0 做消融） |

⚠️ **为什么必须同时有节点预算**：时间预算的截断点取决于机器负载 ⇒
**同一局面两次搜索可能到达不同深度、给出不同走法**（实测同一初局一次 timeout、一次 119 步胜）。
A/B 对照实验必须可复现 ⇒ 用确定性的节点计数。

### 10.4 战略项 —— 「能走棋」→「能赢棋」的关键

```python
SW_UNLOCK = 80                    # 司令只值 100 分，但「解锁命门」远超它，必须显式建模
SW_THREAT: term = SW_THREAT * 4.0 / (1.0 + dmin)     # 反比、双向
```
- **反比形式 `4/(1+d)`**：距离 1 步的权重是距离 6 步的 **3.5 倍** ⇒ 近处「下一步就能扛」被强烈偏好
  （可压过吃子，正确 —— 赢棋优先）；远处仍留一个**持续梯度**。
- **必须双向**：只写「我方逼近对方军旗得正分」会让 AI 只顾进攻不顾门户，
  对方逼近我方军旗必须记负分。
- ⚠️ **这个梯度项同时解决了 Phase 1 遗留的「原地振荡」**：alpha-beta + 静态评估在视野内无人可吃时
  **所有走法同分** ⇒ 任意选择 ⇒ 循环（实测三家原地来回）。双向军旗逼近项提供持续梯度打破平局。
  **别为了「简化」把它删掉。**

### 10.5 实验结论（全部用 `SW_NODES=30000` 的确定性预算）

**① 深度是胜负的决定变量**（完全信息自检，搜索=甲 vs 单步贪心=乙）：

| 配置 | ≈深度 | 结果 |
|---|---|---|
| 8000 节点/决策 | 4 | **0 / 2 胜** |
| 30000 节点/决策 | 6~8 | **2 / 2 胜**（459 步 / 129 步） |

**② 四组对照**：

| 组 | 配置 | 局数 | 结果 | 终局类型 |
|---|---|---|---|---|
| 组1 基线 | 双方均贪心 | 3 | 0 胜 | **timeout 3/3** |
| 组2 主实验 | 搜索 = 甲 | 5 | **4 胜 1 平** | win-A 4 / timeout 1 |
| 组3 交换 | 搜索 = 乙 | 3 | **0 胜 1 负 2 平** | timeout 2 / win-A 1 |
| 组4 消融 | 搜索 = 甲，`SW_THREAT=0` | 3 | **1 胜 2 平** | win-A 1 / timeout 2 |

- **基线局局拖到 1500 步上限**，而搜索方胜局仅 91~459 步 ⇒ 这个对比本身就是「多步规划生效」的证据。
- 搜索方 4 个胜局的存活态全是 `up,down`（**一人未损**）。
- ⚠️ 组2 局5 仍是 timeout（场上余 39 枚）⇒ **强度不是压倒性的**，贪心方偶尔能靠对耗守住。
- ⚠️⚠️ **组3 交换后优势完全消失（最重要的一条）**：搜索方（乙）**0 胜 1 负 2 平**，
  其中局2 是**搜索方输给贪心方**（贪心的甲 121 步拿下）。
  同一批布局下「**甲是搜索方 3/3 胜、甲是贪心方 0/3 胜**」⇒
  **「4 胜 1 平」被方位 / 先手（`up` 先走）的固有优势严重调制，不能直接当强度成绩。**
  ⚠️ **今后报强度必须用镜像对局（每局换边各打一次）并扣除方位基线**；5 局 / 3 局都**不足以下统计结论**。
- 组3 峰值思考 2.85~3.03s（组2 1.80~2.54s）⇒ 乙方局面更复杂，但**仍远低于 30 秒、超时 0 次**。
- ✅ **组4 消融证实「军旗逼近项是必需项」**：组4 与组2 用**完全相同的 3 个布局 / 种子 / 侧 / 节点预算**，
  只把 `SW_THREAT` 30 → 0 ⇒ **同批布局胜率 3/3 → 1/3**（rec0 183 步胜、rec1/rec2 双双 timeout）。
  ⇒ 别为了「简化」删掉 `SW_THREAT`。
- ✅ **「联盟折一家仍能赢」在搜索对局里反复复现**：组4 局1 存活「仅 down」、PIMC 局1 存活「仅 up」，
  组2 的 4 个胜局均一人未损 ⇒ 与联众「20.53% 胜局赢家联盟也折一家」一致。
- ⚠️ **对局耗时是「局面宽度」的代理指标**：组4 局2（场上 13 枚）1500 步只花 113.4s
  （走法少 ⇒ 预算没花完就搜完深度 8）；局3（场上 43 枚）1500 步花 1082.9s（每步撞满预算）。

### 10.6 思考时间 → 深度（部署参数，实测）

| 时间预算 | 到达深度（中位） | 节点数（中位） | 相对 0.5s 倍数 |
|---|---|---|---|
| 0.5 s | 4 | 12,544 | 1.0× |
| 2.0 s | 4 | 41,984 | 3.3× |
| 5.0 s | **6** | 100,352 | 8.0× |
| 10.0 s | 6 | 192,000 | 15.3× |
| 15.0 s | 6 | 281,088 | 22.4× |
| 24.0 s（= 30×0.8） | **6** | 463,360 | 36.9× |

- **边际收益急剧递减**：0.5→2.0s 节点翻 3.3 倍深度**没变**；5→24s 节点再翻 4.6 倍深度**还是没变**。
- **24 秒整的预算打不满**：现有宽度因子（`K=8`）下深度 8 几乎到不了。
  **要更深必须投入走法截断/置换表/杀手走法，而不是加时间。**
- **部署取值 2~5 秒即可**（深度 4~6）。实测对局峰值思考 **2.24~2.54 秒**，
  30 秒限时下**超时 0 次** ⇒ 完全合规且余量巨大。

### 10.7 30 秒时限规则（坚哥给定，已落地 `match.py`）

```python
STEP_TIME_LIMIT = 30      # 每步限时（秒）
STEP_TIME_SAFE  = 0.8     # 安全垫 ⇒ 实际预算 24 秒
TIMEOUT_LIMIT   = 5       # 累计超时 5 次 ⇒ 该方判战败（清场出局，队友仍可战）
MATCH_MAX_STEPS = 1500    # 步数上限，终局类型记 timeout
def step_budget(tb): return min(float(tb), STEP_TIME_LIMIT * STEP_TIME_SAFE)
```
⚠️ **必须「事前设预算」而不是「到点掐断」** —— 同步搜索无法在 30 秒整处被打断。
安全垫 0.8 固定实际预算 24 秒，留 6 秒给走法生成、结算、日志。

### 10.8 PIMC 暗棋版（只用可观测信息）

```python
1. 从当前信息集「采样」若干完整世界（把未知兵种按后验分布填上）
2. 每个世界当完全信息局面，各跑一次 alpha-beta
3. 聚合选步（默认最优走法投票 vote，平票看平均分；可切 mean）
```
**采样约束（四暗修正后共 5 条，详见 10.0）**：
① **只有自己一方全知**（`known_sides = {me}`，队友与敌人一律采样）；
② 兵种计数守恒（逐个扣减剩余池）；
③ 地雷 / 军旗不能移动 ⇒ 只落在**该方自己的**未动过初始格；
④ **军旗只可能在大本营**（`is_hq()`，每方 2 格）；
⑤ **亮旗后军旗位置已公开 ⇒ 钉死真值**，不参与采样。
（另：位置先验 `prior_init.json` 仅作权重，且只对未动过的初始格生效。）

⚠️ **采样顺序决定成败**：**三层、约束最紧的先分** ——
`moved`（动过的格，雷 + 旗**都**排除）→ `fresh`（未动过的**非大本营**格，可接雷、排除旗）
→ `hq`（未动过的**大本营**格，收尾，什么都能接）。后分的一组任何情况都有解。
若随机打乱一起分，会出现「非 fresh 格只剩雷棋可挑」的死结，兜底分支会把军旗扔到动过的格上。

**采样自检五项不变量（`--verify`，720 次采样全 0 违规）**：
① 兵种计数与真实一致 ② 雷/旗不落非法格 ③ 池大小 == 未知格数 ④ 采样前后棋子总数不变
⑤ **军旗不落非大本营格**。
⚠️ 校验方位是 **`down` / `right` / `left` 三方** —— 旧版只查两个敌人、且把 `down` 当已知，**根本查不出来**。
⚠️ 发现「池大小 ≠ 未知格数」时脚本**只计数、不兜底** —— 静默「保持原值」等于把真实兵种泄漏给 AI。

**另有「着法合法性」断言**：`drive_match(validate=True)` 逐步核对策略输出是否在**真局面**的合法集合里，
`illegal[方位]` **必须为 0**。这是四暗修正的配套兜底 —— 单实例同时管 up / down 时会踩（见 10.10 #6）。

⚠️ **已知理论缺陷（必须记录）**：**策略融合（strategy fusion）** —— PIMC 通病。
多个世界共享同一条搜索路径 ⇒ 隐含假设「对手必须用同一策略应对所有可能世界」⇒ **高估自己**。
军棋里主要影响**试探性撞子**的估值。根治需要信息集搜索（ISMCTS / 反事实遗憾）。

### 10.9 断言式自检（`verify_search_20260924.py`，17 项全过）

| 断言组 | 内容 |
|---|---|
| ① 增量推进还原 | 60 步 × 3 局 × 2 种子，`make` 后 `unmake` 并逐项比对 board/alive/cmdr_dead（**360 次异常 0**） |
| ② 搜索无副作用 | `negamax` 跑完 board 必须逐格一致 |
| ③ 终局判定 | 开局 eval 对称=0；任一联盟全灭 ⇒ 另一方视角 `+W_WIN` |
| ④ 扛旗清场与回滚 | 清场、`alive=False`、board 恰好少 25 枚、回滚后完整还原 |

⚠️ **写这个脚本时踩的两个「测试侧」坑**（引擎是对的，别误判成 bug）：
① `Searcher.__init__` 会 `dict(alive)` **拷贝**传入字典 ⇒ 构造后改外层字典不起作用，必须改 `sr.alive`；
② 构造「对方军旗格」**不能直接赋值** `board[flag_cell]=(...)`（会把军旗覆盖掉 ⇒ `flag` 事件永不触发），
正确做法 = **把军旗与相邻格上的棋子交换位置**（保持总数不变）。

### 10.10 顺带修掉的 6 个真实 bug（全部是静默失效）

| # | 位置 | 症状 |
|---|---|---|
| 1 | `ai_playout.py` / 原 `search.py` | 司令碰炸弹（`both_die`）未标记阵亡 ⇒ 该方军旗永远不能被扛 ⇒ 打不出胜负。修复：抽公共件 `junqi_engine.casualties()` |
| 2 | `whatif.InfoSet.observe()` | 用短名 `eat`/`killed`/`both` 判**引擎原生 res** ⇒ 池无限超扣枯竭（采样自检 480 次里 **448 次**计数不符） |
| 3 | `whatif.dist` / `sample_world` | `fresh` 判据用「全体初始格」而非「该方自己的初始格」⇒ 雷/旗落非法格 14~35 次 |
| 4 | `ai_search_dark.sample_world` | 采样顺序导致军旗被扔到动过的格上（死结 + 兜底） |
| 5 | **`eval_whatif.py` / `final_whatif.py`** | 同样混用短名 ⇒ **前序报告的「净值」「失着率」基线被污染**（净值实为「挖雷−触雷」）。**已修正并重跑，结论反转**（见 9.4） |
| 6 | **`ai_search_dark.py`（PIMCPolicy）** | ⚠️ **把「联盟」当「已知方位」** —— `known_sides=A_SET` ⇒ 队友 `down` 的兵种被 AI 全知。① 信息泄漏（强度虚高，违反四暗）；② AI 替队友走棋时可能输出**非法着法**（`apply_move` 不校验兵种合法性）⇒ 静默推进出非法局面。修复：每方独立 `InfoSet` + `validate=True`（见 10.0） |

⚠️ **两套 res 命名并存是重大陷阱**：引擎原生 `attacker_wins` / `defender_wins` / `both_die` / `dig` / `mine` / `flag`；
页面口径短名 `eat` / `killed` / `both`。**写新脚本一律用原生名**。
`eval_baseline.py` 内部做了映射所以自洽（这也是「JS↔Python 对齐 300 局 0 差异」能通过的原因）。

### 10.11 下一步（按优先级）

1. **赛制修正（✅ 2026-09-24 已完成）**：已实现 **镜像对局** `mirror_match.py`
   （同一布局每局换边各打一次，方位优势在配对内完全抵消）
   —— 完全信息组的强度数字**此前全部受方位污染**（组2 4胜1平 vs 组3 0胜1负2平，同一批布局）。
   **今后任何强度数字一律走镜像配对**，见 §11.6。
2. **对手口径二选一**：现在乙方的单步贪心是**上帝视角**（知道甲方的全部棋子）⇒ 是过强的对手、
   AI 成绩被系统性低估。要么给乙方也建 `InfoSet` + depth-1 采样搜索（真实，但 AI 成绩会变好看），
   要么保留上帝视角并明确标注「AI 成绩是下界」。**建议两者都跑，取区间。**
3. **加强搜索效率**：置换表 / 杀手走法 / 历史启发 / 走法排序 —— 目标 5 秒内到深度 8
   （**瓶颈是宽度不是时间**）。⚠️ **四暗下每方各一个实例 ⇒ 成本翻倍，效率优化更紧迫。**
4. **继续强化 PIMC**（当前最短板）：`vote` vs `mean`、世界数与每世界预算的分配、提高总预算
   （实测预算常常没花完）；缓解策略融合（ISMCTS / 反事实遗憾搜索）。
5. **自对弈**（四暗版 vs 四暗版）分真实强弱梯度。
6. 把「30 秒 / 5 次」做成**可配置的对局仲裁**，为在线对弈留接口。

---

## 四暗配合与判断挖掘（Phase 3，2026-09-24 新增）

> ⚠️ **前提铁律**：全库联众复盘是 **四暗** —— 除自己外**三家都是暗棋，含队友**。
> 明棋（上帝视角）下「判断」与「配合」根本不存在，所以这是**唯一**能学到这两件事的途径。
> 见 §10.0 与「关键约定」。

### 11.1 文件清单

| 文件 | 职责 |
|---|---|
| `mine_coord.py` | 行为挖掘主脚本。17 个特征（判断层 7 + 配合层 10），**全事件化**、四窗口、双向对称性检验 |
| `analyze_coord.py` | 增量分析（相对 `net`）+ 玩家画像 + 全库真实走棋用时统计 |
| `mirror_match.py` | **镜像赛制**（同布局换边各一局）—— 修掉「方位优势污染强度数字」的硬伤 |

用法：
```bash
python mine_coord.py 300                    # 前 300 局快速验证
python mine_coord.py 0 --dump rows.jsonl    # 全量（2332 局 ≈ 4 分钟）
python analyze_coord.py rows.jsonl          # 增量 + 画像 + 用时
python mirror_match.py --mode greedy --n 3 --nodes 20000   # 诚实强度
python mirror_match.py --mode link   --n 2 --nodes 10000 --link 12   # 隔离协同项
```

### 11.2 ⚠️ 三条方法纪律（缺一条结论就会错）

1. **全事件化**：特征必须由「(步号, 值)」事件流聚合，**不能**直接用 `Counter` 累计
   —— 否则窗口切不开、一半特征拿不到早窗值。（第一版就栽在这，重写为事件流。）
2. **双向对称性检验**：每个特征**分别算甲联盟 AUC 与乙联盟 AUC**，
   方向不一致（✗）一律判噪声、不入结论。理由见 §10.11 第 1 条
   （同一批布局：甲搜索 3/3 胜、乙搜索 0 胜 —— 方位优势能吃掉整个结论）。
3. **分窗口**：全程口径含**结果倒推**（赢了之后自然就集中、就没人打进来）。
   必须切 **早窗 ≤60 / 中盘 31~150 / 残局 >150** 分别看，
   **只有换窗口还站得住的才算「赢的原因」**。

### 11.3 ⚠️⚠️ 最重要的一条：分窗口能识别「原因 / 结果」

同一指标的四个窗口 AUC 排一起就能定性。**不做这一步会得出至少三个错误结论**：

| 指标 | 全程 | 早窗 | 中盘 | 残局 | 判定 |
|---|---|---|---|---|---|
| `net` 子力净值 | 0.7149 | 0.6145 | 0.6757 | 0.6046 | ✅ 真信号（全程稳） |
| `focus` 协同围剿 | 0.6519 | 0.5093 | **0.6111** | 0.6325 | ✅ 真信号（早窗受「未接触」限制） |
| `info_eff` 信息-子力效率 | 0.6203 | 0.5765 | 0.5983 | 0.5695 | ✅ 真信号 |
| `self_press` 我被施压 | 0.2872 | **0.4860** | 0.3459 | 0.3760 | ❌ **同义反复**（「没被打输」） |
| `opp_share` 集中度 | 0.3940 | **0.5001** | 0.4180 | 0.5049 | ❌ 方向漂移，不可用 |
| `support_in` 回防 | 0.5076 | 0.5016 | 0.5133 | 0.5121 | ❌ 全程贴 0.5，无判别力 |
| `relay_out` 接力让路 | 0.5691 | 0.5075 | 0.5478 | 0.5410 | △ 幅度不足 |

- ⚠️ **「早窗没信号」≠「特征没用」**：开局 60 步两家往往**还没接触**，施压计数全 0、
  没有方差 ⇒ 测不出东西。这正是 `focus` 从 0.5093 升到 0.6111 的原因。
  **中盘（31~150 步）才是协同类指标的决定性窗口。**
- ⚠️ **「增量大」≠「能用」**：`self_press` 增量最大（Δ+0.0488）但它是同义反复。

### 11.4 核心结论（全量 2332 局 / 8364 玩家-局 / 99 名 ≥15 局玩家）

**① 唯一有实质增量的配合指标 = `focus` 协同围剿**
- 中盘 AUC **0.6111**（双向一致）、玩家级 ρ **+0.532**
- 与 `net` 的 Pearson **仅 +0.101**（几乎独立）
- `net + 0.75·focus` ⇒ AUC 0.6757 → **0.7055（Δ+0.0298）**
  —— 是前序 `c_gain` 对 v3 增量（+0.0086）的 **3.5 倍**
- 定义：两个对手里，我方与队友**都**达到施压阈值（占各自走法 8%）的占比

**② 判断力可量化，且强弱棋手分得很开**

| 特征 | 中盘 AUC | 玩家级 ρ（全程/中盘） | 方向 |
|---|---|---|---|
| `probe_loss` 试探损失 | 0.3847 | **−0.477 / −0.494** | 低更好 |
| `probe_sel` 试探选择性 | 0.4317 | **−0.471 / −0.325** | 低更好 |
| `info_eff` 信息-子力效率 | 0.5983 | +0.246 / +0.315 | 高更好 |

玩家画像对比（中盘口径）：
- 顶尖（胜率 73.7~85.7%）：`probe_loss` **8.61~14.86**、`probe_sel` 33.5~36.6、`info_eff` 4.7~10.7
- 最弱（13.3~21.1%）：`probe_loss` **13.83~22.00**、`probe_sel` 34.8~39.6、`info_eff` 1.0~5.9
⇒ **可教给 AI 的一句话：「用便宜的子、挑看着弱的格去试探」。**
- ⚠️ **两组是「重叠」不是「分离」**（强手最高 14.86 / 弱手最低 13.83）⇒ 单局数值区分不出棋力，
  玩家级 ρ 能到 −0.494 靠的是**跨几十局取均值**。别误以为「一眼看得出谁强」。
- ⚠️ 反例：`1zfo`（胜率 13.3%）的 `focus` 0.667 与顶级持平 ⇒ 单指标推不出棋力。

**③ 未通过的项（诚实记录）**：`support_in` 增量 +0.0001 ≈ 零；
`opp_share` 各窗口方向漂移；`relay` 幅度不足；`think_*`（用时）甲乙两盟方向不一致
⇒ **想得久不代表想得好**。

### 11.5 落地：`SW_LINK` / `SW_SUPPORT`（`search.py`）

```python
SW_LINK    = 12   # 协同围剿：Σ_敌象限 min(我方两家在该象限的棋子数)  ← 用 min 只奖励「都到」
SW_SUPPORT = 12   # 回防协防：Σ_我各象限 min(队友兵力, 敌情规模)，仅当有敌情
```
- ⚠️ **两项只用「队友棋子的位置」** —— 四暗下队友的棋**在哪**是公开可见的，
  未知的只是「那是什么」⇒ **不构成信息泄漏**。
- ⚠️ 权重必须做成**实例参数**（`Searcher(..., link=, support=)`），不能只读模块全局
  —— 对照实验要让甲乙用不同权重。
- ⚠️ `SW_SUPPORT` 是**对照组**：复盘数据已判定它无判别力，实现它是为了证伪。

### 11.6 镜像赛制（`mirror_match.py`）—— 强度测量必须走这条路

```
每个开局布局打两局：实验方先坐甲(up+down)、再坐乙(right+left)（同布局同 seed）
⇒ 两局覆盖甲乙两个位置 ⇒ 方位优势在配对内被完全抵消
输出：坐甲战绩 / 坐乙战绩 / 配对净得分 / 配对一致性
```
- `--mode greedy`：实验方=搜索、对照方=贪心 ⇒ **诚实的强度数字**
- `--mode coord|link|support`：**双方都是搜索**、同深度同预算，
  唯一差别是实验方多一个协同项 ⇒ **可直接隔离协同的净效果**（不受量级差异干扰）

### 11.7 附带验证：30 秒时限在真实对局里的分布

全库 443,179 步真实用时（联众每步带两个时间字段，`t1` 均值 1.82s 是用时）：
- `t1` > 30 秒的步数：**81 步（0.0183%）**；`t2` 只有 4 步（0.0009%）
- **单局累计超时 ≥5 次（应判战败）：0 / 2379 局**
- ⇒ 这条规则是**兜底**不是常态约束；我们的 AI 峰值思考 1.4~3.0 秒，**离 30 秒有 10 倍余量**。

### 11.8 下一步（按优先级）

1. ✅ **已完成（09-24 第二轮，见 §12）**：镜像实验加大局数 ⇒ **结论反转**，
   `SW_LINK` / `SW_SUPPORT` 在 20 局上**都不显著**（第一轮 n=2 的「正向」是小样本假象）。
2. ✅ **已完成（09-24 第二轮，见 §12）**：配合指标升级为**时序对 / 序列模型** ⇒ **基本失败**，
   独立增量仅 **+0.006**（`focus` 的 1/5），两个序列模型（互信息 / 可预测性）无效。
3. **把「便宜子试探」落进 PIMC 的分支选择**：暗棋下试探是主要信息来源，
   当前评估里没有显式建模「试探的成本-信息收益」。
4. PIMC 仍是最大短板（§10.8）；它不变强，协同项的收益会被采样噪声淹没。

---

## 12. 默契量化与镜像验证（Phase 3 第二轮，2026-09-24）

> 交付报告：`默契量化与镜像验证报告_20260924.html`（10 节 / 17 表）
> 本轮做的是 §11.8 的第 1、2 条。**结论以负面为主** —— 但两处都是「**有价值的负面**」：
> 拦住了我们把两个实际打不出优势的协同项当成有效项继续投入。

### 12.1 文件清单

| 文件 | 作用 |
|---|---|
| `mirror_match.py`（**已改造**） | 镜像对局 + **三个统计口径**（胜负符号检验 / **终局净子力差 Δ** / 终局类型分解）+ `--json` 输出 |
| `mine_pair_seq.py`（新） | **6 个时序对指标**的挖掘（全量 2332 局；`PAIR_K` / `BUCKET` 可用环境变量覆盖） |
| `analyze_pair.py`（新） | 时序指标的增量分析（相关矩阵 + **固定子集**逐层加项组合 AUC） |
| `perm_pair.py`（新） | **置换检验**（`global` / `within` 局内两种模式，默认 within） |
| `mirror_{greedy,link,support}_n10.{log,json}` | 三组各 20 局实验的原始结果 |
| `rows_pair_20260924.jsonl` | 8,364 玩家-局 × 时序指标（四窗口） |

备份：`mirror_match.py.bak_pre_stats_20260924`

### 12.2 ⚠️ 镜像赛制必须补的三个口径（**本轮最大的方法论收获**）

第一轮镜像实验的两个硬伤：① **平局率 50~75%**（link 4局2平、support 4局3平），
且平局**全是** `timeout`/`stuck`（场上还剩 20+ 子）；② 只有 4~6 局。

⚠️ **最容易犯的错**：把 `timeout` 当「真平局」记 0 分。实际那时**一方往往已明显占优**。

⇒ 必须补上：
- **② 终局净子力差 Δ** = 实验方联盟存活子价值和 − 对照方联盟，用 **`VAL_STRAT` 战略口径**
  （司令 220 / 炸弹 60 / 工兵 24 —— 体现不可替代性）。**连续量 ⇒ 平局也计入**。
  用**配对和**做 t 检验 + Wilcoxon 符号秩。
- **① 符号检验**（非平局里胜率是否 ≠ 0.5）
- **③ 按终局类型分解**（把 timeout / stuck 的 Δ 均值单列）

⚠️ **Δ 均值与胜负净得分方向不一致时，取更保守的结论**：
support 组 Δ 均值 +33.8 但配对净得分 −4/20、配对和中位 −32.0 ⇒ 判**无效果**。

### 12.3 ⚠️ 确定性由「约束类型」决定 —— 决定实验能否并行

`search.py` 判预算的写法是 `if self.node_budget: ... elif time.time() > self.deadline:`
⇒ **只要设了 `--nodes`，时间就完全不参与** ⇒ 搜索是**纯节点数约束** ⇒
**结果确定性、可复现**，多组实验可并行（CPU 争抢只影响快慢）。
**跑对照实验前先确认这一点**（否则并行会互相污染结果）。

### 12.4 结果：三组 20 局（`--n 10 --nodes 10000 --steps 600`）

| 组 | 实验方 | 战绩 | 配对净得分 | 符号检验 p | 配对 Δ 均值 | t p | Wilcoxon p |
|---|---|---|---|---|---|---|---|
| A | 搜索 vs 单步贪心 | 14-2-4 | **+12/20** | **0.0042 ★** | +1516.2 | **<0.0001 ★** | **0.0098 ★** |
| B | 搜索 + `SW_LINK=12` vs 搜索 | 5-4-11 | +1/20 | 1.0000 | +117.8 | 0.6133 | 0.6953 |
| C | 搜索 + `SW_SUPPORT=12` vs 搜索 | 2-6-12 | **−4/20** | 0.2891 | +33.8 | 0.8672 | 1.0000 |

- ✅ **A 组**：「**搜索 > 单步贪心**」由方向性证据升为**统计结论**（三口径 p<0.01）。
  终局分解还显示 **4 局 timeout 的 Δ 均值 +382**（搜索方占优）⇒ **Δ 口径确实救回了信息**。
- ❌ **B / C 组都无效果**。而第一轮 n=2 时 B 是 +2/4、C 是 +1/4（看起来方向一致）
  ⇒ **那是小样本假象**（这正是本轮加大局数的意义）。

⚠️⚠️ **本轮最该记住的一条**：**「行为指标与胜利相关」≠「把它做成搜索项能提升棋力」**。
`focus` 在复盘数据分析上有 **+0.0304** 的真增量（§11.4），但做成 `SW_LINK` 加进搜索后
**打不出优势**。原因推测：① 评估函数已有一堆项（子力/位置/司令/威胁），协同的增量被淹没；
② 搜索太浅（K=6 / depth≤8 / 1e4 节点），协同需要**多步**才能兑现；
③ 平局率高（10~12 / 20），优势来不及转成胜利；④ 权重 `12` 是拍的，没扫参。

### 12.5 任务 2：时序对 / 序列模型（`mine_pair_seq.py`）

动机：第一轮的配合指标是**单方计数**，丢了「**时机对不对**」。
6 个新指标（都在**步号**维度刻画同一联盟两家）：

| 指标 | 定义 | 中盘 AUC | 甲/乙 | 玩家级 ρ | 结论 |
|---|---|---|---|---|---|
| `pair_sync` | 我方每次施压，队友 ±K 步内也压同一对手的比例 | 0.5913 | ✓ | +0.337 | 成立但**弱** |
| `pair_lift` | P(我压｜队友压) / P(我压) | 0.5923 | ✓ | +0.380 | 成立但**弱** |
| `pair_pred` | 队友上一桶区域 → 我方本桶区域的准确率 − 基线 | 0.5591 | ✓ | +0.217 | 弱 |
| `pair_help` | 敌入我象限 K 步内队友也进我象限 | 0.5238 | ✓ | +0.379 | 很弱 |
| `pair_mitgt` | 区域序列**归一化互信息** | 0.5218 | **✗** | −0.002 | **失败** |
| `pair_lag` | 首次协同的中位时滞 | 0.5136 | **✗** | +0.139 | **失败** |
| （对照）`focus` | 第一轮计数版 | 0.6208 | ✓ | +0.426 | 仍是最强配合项 |
| （对照）`press_n` | 施压总步数 | 0.6401 | ✓ | +0.417 | **比所有时序项都强** |

⚠️ `pair_sync` 与 `pair_lift` 的 Pearson **0.511** ⇒ 它俩是**同一件事**，不是两个独立维度。
⚠️ 失败的两个（互信息 / 时滞）**甲乙方向不一致** ⇒ 按 §11.2 纪律直接判噪声。

### 12.6 ★ 增量分析（`analyze_pair.py`）—— 关键裁决

⚠️ **必须先固定同一子集**：`combo()` 会剔除任一指标缺失的行 ⇒ 不同组合的样本集不同
（8364 vs 7866），直接比 AUC 会把「**样本差异**」误当「增量」。固定 **7,349 行**再逐层加项。

| 组合（中盘 · n=7349） | AUC | Δ |
|---|---|---|
| `net` | 0.6705 | — |
| `net` + `focus`（w=0.75） | 0.7009 | **+0.0304** |
| `net` + `press_n`（w=0.75） | 0.6981 | +0.0276 |
| `net` + `focus` + `pair_sync` | 0.7065 | +0.0056 |
| `net` + `focus` + `pair_lift` | 0.7072 | +0.0063 |
| `net` + `focus` + `pair_pred` | 0.7005 | **−0.0004** |

⇒ **时序项独立增量只有 +0.006（`focus` 的 1/5）**，**不足以再落一个搜索项**
（落地门槛 ≈ **+0.03 级别**）。`pair_pred` 直接是**负增量**。

旁证：`pair_sync` 与 `press_n` 的 Pearson 只有 **0.063** ⇒ 它**确实**抓到了施压量之外的东西
（我原以为「同步率只是施压多的副产品」，被这个数字推翻），但**那点独立信息太少**。

### 12.7 置换检验（`perm_pair.py`）

⚠️ **8,364 行来自 1,980 局（每局 4 行、胜负强相关）⇒ 行不独立**，
按行打乱（`global`）p 值**偏乐观**。正确做法是**局内置换**（`within`：只在每局内打乱 4 人特征值，
保留局效应）。两种模式都实现了，**默认 within**。

| 特征 | 观测 AUC | 局内置换均值 | 经验 p |
|---|---|---|---|
| `net` | 0.6705 | 0.5061 | <0.0025 ★ |
| `focus` | 0.6113 | 0.5036 | <0.0025 ★ |
| `press_n` | 0.6232 | 0.5068 | <0.0025 ★ |
| `pair_sync` | 0.5872 | 0.5086 | <0.0025 ★ |
| `pair_lift` | 0.5918 | 0.5119 | <0.0025 ★ |
| `pair_pred` | 0.5507 | 0.5039 | <0.0025 ★ |
| `pair_help` | 0.5222 | 0.4973 | <0.0025 ★ |

⇒ **时序指标与胜负的关联是真的**（400 次置换无一达到观测值）。
置换均值升到 0.50~0.51 **正是局效应存在的证据**（说明控制对了）。

### 12.8 K 稳健性

`pair_sync` 中盘 AUC：K=2 → 0.5914、K=3 → 0.5913、K=5 → **0.6049**、K=8 → 0.5911
⇒ 稳定在 **0.591~0.605**，**对 K 不敏感**（K 由环境变量 `PAIR_K` 控制）。
⚠️ 所以问题**不是**「指标是噪声」，而是「**它携带的独立信息本来就少**」。

### 12.9 玩家画像的强反例

- 全库 `pair_sync` **最高**的 `266201`（0.432）胜率只有 **25%**；
  `1zfo`（sync 0.361）胜率 **13.3%**（与第一轮 `focus` 的反例同源）
  ⇒ **单看同步率推不出棋力**。
- 玩家级 ρ：`pair_sync` **+0.337** / `pair_lift` **+0.380**，
  **弱于** `focus` **+0.426** / `press_n` **+0.417**。

### 12.10 方法论沉淀（可复用）

1. **平局要测「差值」不测「胜负」**：自对弈大量 `timeout` 时，必须加终局净子力差口径。
2. **组合对比必须固定子集**：否则 AUC 变化里混着样本差异。
3. **置换检验要按聚类做**：同一局的行不独立 ⇒ 用**局内置换**。
4. **正交 ≠ 有用**：先看互相关（本处 0.063 很低），再看**组合增量**，两者都过才落地。
5. **确定性由约束类型决定**：设了 `node_budget` 时间就不参与 ⇒ 可并行、可复现。
6. ⚠️ **`sorted(..., reverse=True)` 的元组键要写对**：`(0, -1)` 若写成 `(-1, 0)` 会**静默漏统计**
   该类配对（本轮踩过，已修 `mirror_match.py`；**从 JSON 重算即可，不必重跑对局**）。

### 12.11 结论与下一步

- ✅ **搜索 > 单步贪心**：统计显著（p=0.0042）。
- ❌ **`SW_LINK` / `SW_SUPPORT` 打不出优势** ⇒ **`SW_SUPPORT` 建议撤掉或大幅降权**；
  `SW_LINK` 可保留（微弱正向、有理论依据）但**别指望它**。
- ❌ **时序 / 序列路线未走通**：独立增量 +0.006、序列模型无效。
  ⇒ 在四暗条件下，**队友行为能提供的信息本来就有限**，计数版几乎已把信号榨干。
- **下一步优先级**：① **PIMC 变强**（§10.8）比再加评估项更值；
  ② 若真要提升配合项收益，应**先把搜索加深**（协同需多步兑现）；
  ③ 把「便宜子试探」落进 PIMC 分支选择。

---

## 13. PIMC 聚合改进与确定性修复（Phase 4，2026-09-24）

**交付报告**：`PIMC聚合改进与确定性修复报告_20260924.html`（5 节 / 5 表）。
本轮三件事：撤除 `SW_SUPPORT` → 修确定性缺陷 → 攻 PIMC。**最有价值的产出是中间那个意外发现的真 bug。**

### 13.1 文件清单

| 文件 | 作用 |
|---|---|
| `equiv_dropsupport_20260924.py` | 撤 support 的**逐位等价性验证**（⚠ 前提 = 每个版本用**独立 board 拷贝**，见 13.3） |
| `verify_det_keyorder_20260924.py` | 键顺序无关性验证（20 局面 × 3 种打乱） |
| `cmp_keyorder_20260924.py` | **修复前 / 后对照** —— 有分辨力的关键（遵循「改前备份是测试有分辨力的唯一对照物」） |
| `pimc_sweep_20260924.py` | 固定**总预算**扫世界数（5 档并行，用 `Δ` 主指标） |
| `pimc_mirror.py` | **PIMC 镜像赛制** —— 评估 PIMC 改进的标准框架（同布局换边 + 双方同预算）；支持 `--exp-depth/--ctl-depth/--exp-npw/--ctl-npw` |
| `pimc_agg_exp_20260924.py` | 聚合对照的并行驱动（`[n] [steps] [npw] [worlds] [arms]`） |
| 证据留档 | `pimc_exp1_{borda,mean,min}.{json,log}` · `pimc_exp2_{mean_n10,max_n6}.{json,log}` · `pimc_sweep_{n1_vote,n2_vote,n3_vote,n4_vote,n3_mean}.{json,log}` |
| 备份 | `search.py.bak_pre_dropsupport_20260924` · `search.py.bak_pre_tiebreak_20260924` · `ai_search_dark.py.bak_pre_pimc20260924` · `mirror_match.py.bak_pre_dropsupport_20260924` |

### 13.2 ⚠️⚠️⚠️ `order()` 必须带**确定性次级键**（最容易再犯的静默失效）

```python
def order(self, moves, waste=0.0):
    return sorted(moves, key=lambda m: (-self.move_value(m, waste), m))
                                                              ↑ 必须有
```

**根因链**（一环都不能少）：
```
unmake() 用「del + 重新插入」还原格子
   ↓ dict 的**插入顺序**改变（内容完全不变）
legal_moves() 遍历 board.items()
   ↓ 走法生成顺序随对局推进**持续漂移**
order() 只按 -move_value 排序（sorted 稳定 ⇒ 平局保留输入顺序）
   ↓ move_value 平局极多（开局同兵种的平行推进分数完全相同）
gen(turn)[:K] 取到的 top-K **集合不同**
   ↓
搜索树不同 ⇒ 同一局面给出不同走法
```

**量化**（同内容、不同键顺序的 board，`cmp_keyorder_20260924.py`）：

| 版本 | 受影响的局面 | 比例 |
|---|---|---|
| 修复前 | 6 / 20 | **30.0%** |
| 修复后 | 0 / 20 | **0%** |

⚠⚠ **一个必须说清的辨析（否则会误判上一轮结论失效）**：
修复前「**同一开局 + 同一策略跑两次**」**仍然可复现**（实测 3/3 局一致）——
键顺序漂移是**路径确定**的，同一历史 ⇒ 同一顺序。所以这个 bug **不会**让
镜像实验的结论作废。真正的危害是**语义契约破裂**：
`best_move(A) ≠ best_move(B)` 即使 A 与 B **内容完全相同**。
这会污染「**不同历史路径到达同一局面**」的场景 —— 恰好包括
**PIMC（每个采样世界都是重新构造的棋盘）**、多进程、跨版本对比。

### 13.3 ⚠️ 对照实验必须给每一方**独立的 board 拷贝**

第一次跑等价性验证时报了 **7 处「假差异」**：`a = NEW.Searcher(board)` 与
`b = OLD.Searcher(board)` **共享同一个 board 引用**，`a.best_move()` 内部的
make/unmake 已经把**键顺序**改了，`b` 于是读到不同的走法生成顺序。
⇒ 每个版本 `dict(board)` 一份独立拷贝，差异才归因于被考察的改动。
（这条与 13.2 是同一个机制的两面。）

### 13.4 PIMC 的跨世界聚合：五种方式 + 实测结论

`PIMCPolicy.__call__` 累积三种统计后按 `SW_AGG` / `agg` 选路：

| 聚合 | 语义 | 实测（镜像 vs `vote`） |
|---|---|---|
| `vote` | 每世界投一票给自己的最优（**默认**） | 基线 |
| `mean` | 跨世界**归一化**平均分 | Δ −924（20 局）/ 未达显著 |
| `borda` | **世界内排名**聚合（第 k 名得 n−k 分） | Δ −498（12 局）/ 未达显著 |
| `min` | 最坏世界（αμ 简化版） | **配对 6/6 全负**，Δ −4130，p=0.000 ⇒ **★ 显著有害** |
| `max` | 最好世界（与 `min` 对称） | **配对 6/6 全负**，Δ −4312，p=0.002 ⇒ **★ 显著有害** |

⚠ **修掉一个真 bug**：`agg="mean"` 原本是
`max(score_sum, key=score_sum[m])` —— **没有归一化**。
`root_scores` 在节点预算耗尽时会提前 `break`，某些世界只覆盖**部分**走法
⇒ 出现次数少的走法被系统性低估。现已统一用
`mavg(m) = score_sum[m] / score_cnt[m]`（`vote` 的平票打破也一并归一化）。

### 13.5 ⚠️ 四暗 PIMC 必须用**跨世界汇总统计**，不能取**单世界极值**

`min` 与 `max` 是**相反方向**的两个极端，却**都是配对 6/6 全负**、
Δ 幅度比其它组大**一个数量级** ⇒ 这不是「保守还是激进」的问题，
而是 **「用单个世界的极值做决策」这个做法本身错**：

> 每个世界都是一次**确定化猜测**。`vote`/`mean`/`borda` 把所有世界的信息汇总
> ⇒ 决策反映「平均而言怎样」；`min`/`max` 只看**一个世界**的第 k 名
> ⇒ 决策被**单个采样噪声**主导，**不再是期望值决策**。

机制上还解释得通 `min` 为什么特别糟：它假设「凡是我要撞的格都是大子」⇒ AI 不敢试探
⇒ 四暗下**主动放弃唯一的信息来源**（与 §11 挖出的「**失着（撞子被吃）几乎无判别力**」
正好互为反面 —— 撞子不是主要失分点，所以为躲撞子而过度保守是净亏）。

### 13.6 又一个小样本假象的实例（本轮第二个）

`mean` 在 **12 局**时是 **+846**（4 正 2 负），扩到 **20 局**后变成 **−924**（6 胜 8 负 6 平）。
⚠ 两组**不可直接比** —— 期间修了 `vote` 分支的归一化 bug，对照方行为已变
（这也正是前 6 个配对数值完全不同的原因），但它们都是「mean vs vote」的对照。

**可复用判据**：**|Δ| 小于 ~1000 的效应，在 10 个配对以内测不出来**；
只有 |Δ| > 4000 级别的效应（如 min/max）才能在 6 个配对里稳定复现。

### 13.7 本轮结论与下一步

- ✅ 撤 `SW_SUPPORT` 安全（32 项等价性 0 差异 + 回归 17 项 + 采样 5 项全过）；
  `SW_LINK` 保留（默认 0），两者**默认都关闭**。
- ✅ **两个真 bug 修掉**：`order()` 缺次级键 · PIMC `mean` 未归一化。
- ✅ **两个方向干净排除**：`min` / `max`（以后不必再试）。
- ❌ **「预算被多世界分摊」不成立**：固定总预算下世界数 1/2/3/4 的 Δ
  = −1132 / −1648 / −1228 / −1462，**无单调趋势**。
- ❌ **「换聚合方式能让 PIMC 变强」也不成立**：`vote`/`mean`/`borda` 三者打平（p 全 > 0.6）。
  ⇒ **PIMC 的瓶颈不在聚合层**。
- **下一步优先级**：① **先验质量** —— `sample_world` 目前只用初始位置先验，
  「动过的格」完全退回**均匀分布**（`mode == "moved"` 时 `pr = 1.0`），
  **完全不用走棋行为**；② **队友的行为线索**（做成采样/推断，**不要**做成评估项 ——
  §12 已证明 `SW_LINK` 无效）；③ **搜索深度** —— ✅ **已执行，见 §14**：
  `max_depth` 虚设、**K 才是杠杆**；④ **补一条「绝对强度」锚线** —— 镜像赛制只能回答
  「A 比 B 好吗」，回答不了「PIMC 到底多强」。

---

## 14. 搜索深度的真相：`max_depth` **虚设** + **K 才是杠杆**（Phase 4 第二轮，2026-09-24）

### 14.1 ⚠️⚠️⚠️ `max_depth` 参数**完全虚设**（本轮最重要的架构级发现）

`search.py` 的 `best_move` 是**迭代加深**，而 `node_budget` 在**整个调用内共享**：

```python
self.nodes = 0                            # ← 只在这里重置一次
for depth in range(2, md + 1, 2):         # 2, 4, 6, 8, ...
    sc = self.root_scores(t, depth, ordered)
    if self.aborted or len(sc) < len(ordered):
        break                             # ← 丢弃该层，保留上一层
    best = sc
    self.depth_reached = depth
```

⇒ 预算不足以走完第 `d` 层时 `break` 并**保留第 `d-2` 层的结果** ⇒ **`md` 只在预算够走完时才起作用**。

**实测**（`probe_depth_20260924.py`，3 局面 × md∈{8,16,32} × 预算∈{5K,20K,80K,320K}）：

| 局面 | md | 预算 | depth达 | nodes | 落子 |
|---|---|---|---|---|---|
| 步25 | **8 / 16 / 32** | 5000 | 4 | 5120 | (5,9,6,14) |
| 步25 | **8 / 16 / 32** | 80000 | 6 | 80128 | (5,9,8,11) |
| 步25 | **8 / 16 / 32** | 320000 | 6 | 320000 | (5,9,8,11) |

**12/12 组「md=8/16/32 落子全同」** ⇒ 提高 depth 上限是**空转**。
实际 `depth_reached` **只由预算决定**：5000→2~4 · 20000→4 · 80000→6 · 320000→**6**（×4 预算无进展）。

### 14.2 depth=8 的门槛预算 ≈ **523K 节点**（`probe_depth_cost_20260924.py`）

| 预算 | depth达 | 实际用节点 | 落子 |
|---|---|---|---|
| 80000 | 6 | 80128（耗尽）| (5,9,8,11) |
| 200000 | 6 | 200192（耗尽）| (5,9,8,11) |
| 500000 | 6 | 500224（耗尽）| (5,9,8,11) |
| 1200000 | **8** | **522743** | **(5,6,10,5)** |
| 2500000 | 8 | 522743 | (5,6,10,5) |

- **depth=6 → 8 的落子完全不同** ⇒ 加深确实改变决策（不是空转）。
- 500K 只差 **4.5%** 就能到 depth=8，但 `aborted` 是**全或无** ⇒ 差一点 = 等于没搜。
- **换算**：PIMC 默认 `npw=8000` 时实际 depth≈4；要到 depth=8 需预算 **×65**，
  且**每个世界都要**（×3 世界）⇒ 每步 ≈160 秒，**远超 30 秒规则** ⇒ **加算力不可行**。

### 14.3 ✅ 可行路径：**降 K**（宽度换深度）

**关键性质**：`best_move` 的 **root 层全宽**（`ordered = self.order(lm)`，不截断），
`K` 只截断**非根层**（`gen()` 里的 `[:self.K]`）
⇒ **降 K 不会漏掉任何「第一步」候选**，只牺牲对手回应的覆盖度。

**实测**（`probe_k_vs_depth_20260924.py`，3 棋谱 × 3 局面 = 9 局面，`max_depth=64` 让预算成唯一约束）：

| 预算 | K=2 | K=3 | K=4 | K=6 |
|---|---|---|---|---|
| 8000 | **+3.3** | +2.0 | +0.0 | 基准 |
| 20000 | **+4.7** | +2.7 | +2.0 | 基准 |

（Δ = 相对 K=6 的 `depth_reached` 增益均值；实测最深：r3/步50 在 20000 预算下 K=2 → depth=**10**）

⇒ **K=2 在同预算下比 K=6 深 3~5 层，零额外算力。**

### 14.4 ⚠️ 对照实验的混淆变量：**双方 agg 必须统一**

`pimc_mirror.py` 的 `--exp-agg` 默认 `borda`、`--ctl-agg` 默认 `vote`
⇒ 若只传 `--exp-K/--ctl-K` 而不管 agg，**agg 会变成混淆变量**。
测 K 必须显式写 `--exp-agg vote --ctl-agg vote`。同理测 agg 要固定 K。

### 14.5 脚本

- `probe_depth_20260924.py` —— md × 预算 → 可达深度（证明 md 虚设）
- `probe_depth_cost_20260924.py` —— depth=8 的门槛预算
- `probe_k_vs_depth_20260924.py` —— K × 预算 → 可达深度（证明 K 杠杆）
- `add_expk_pimc_mirror_20260924.py` —— 给 `pimc_mirror.py` 加 `--exp-K/--ctl-K`（7 处断言式迁移）
- `pimc_k_exp_20260924.py` —— K 对照实验并行驱动（用法 `n steps npw worlds 实验方K列表 对照K [seed]`）

---

## 15. ⚠️⚠️⚠️ 跨进程确定性的**第二个**漂移源：字符串 `frozenset` 的迭代顺序（2026-09-24）

### 15.1 现象：同 seed + 同棋谱，两次运行结果不同

K 对照实验里 n=4（seed=7）与 n=8（seed=7）的**前 4 个配对本应完全相同**
（`load_clean` 按 jsonl 行序取前 n 份 ⇒ 前 4 份必然一致；seed 派生式
`a.seed + i*10 + …` 也只看棋谱索引 `i`）。实测：

| | 布局1 坐甲 | 布局2 坐甲 |
|---|---|---|
| n=4 | **+308**（场上 28 枚）| +222（23 枚）|
| n=8 | **+172**（场上 31 枚）| −52（33 枚）|

⇒ **连「场上棋子数」都不同** ⇒ 对局本身走出了不同路径 ⇒ 存在**进程级**隐藏随机源。

### 15.2 根因：Python 3 对 **str 的 hash 加盐随机化**

`PYTHONHASHSEED` 未固定时，**每次进程启动** str 的 hash 都不同
⇒ `ALL_SET = frozenset(DIRS4)`、`A_SET`、`B_SET`、`known_sides`、`self.my`
这类**字符串集合的迭代顺序每次启动都变**。凡是「遍历它 + 顺序敏感」处都会漂移：

1. **主因** `ai_search_dark.py` 的 `sample_world`：`for side in ALL_SET:`
   循环体内 `rng.shuffle(moved_cells)` 等**消耗 rng**
   ⇒ 四个方位的采样顺序变 ⇒ **rng 消耗顺序变** ⇒ 采出的世界完全不同。
2. **次因** `search.py` 的 `eval_raw`：`for ds in ALL_SET:` 循环体内**浮点累加**
   `s += -term if mine_flag else term` ⇒ 累加顺序变 ⇒ 浮点末位差
   ⇒ 本项目 `move_value` 平局极多 ⇒ `order()` 的排序可能翻转 ⇒ 走法变。

### 15.3 实测证据（`--n 1 --steps 16 --npw 3000 --exp-K 2 --ctl-K 6`）

| 运行 | PYTHONHASHSEED | 坐甲 | 坐乙 |
|---|---|---|---|
| run1 | 12345 | −44（81 枚）| +6（82 枚）|
| run2 | **12345** | **−44（81 枚）** | **+6（82 枚）** ← 完全一致 |
| run3 | **999** | −50（87 枚）| −94（84 枚）← 不同 |

⇒ **同 hash seed 完全可复现；换 hash seed 结果就变。**

### 15.4 修复：一律按 `DIRS4`（有序 tuple）遍历

`fix_hashorder_20260924.py`（5 处断言式迁移）：

| 文件 | 原 | 改 |
|---|---|---|
| `ai_search_dark.py` | `for side in ALL_SET:` | `for side in DIRS4:` ★主因 |
| `search.py` | `for ds in ALL_SET:` | `for ds in DIRS4:` ★次因 |
| `search.py` | `any(self.alive[d] for d in ALL_SET - self.my)` | `… for d in DIRS4 if d not in self.my` |
| `search.py` | `mine = tuple(self.my)` | `tuple(d for d in DIRS4 if d in self.my)` |
| `search.py` | `foes = tuple(ALL_SET - self.my)` | `tuple(d for d in DIRS4 if d not in self.my)` |

**语义完全不变**（元素集合相同），只把「顺序」固定。
**验证**：修复后 `PYTHONHASHSEED ∈ {12345, 999, 7}` 三者结果**完全一致**
（坐甲 +78.0 / 坐乙 +44.0，场上均 87 枚）。

⚠️ **另加一道保险**：实验驱动脚本里 `os.environ["PYTHONHASHSEED"] = "0"`，
保证「同 seed + 同棋谱 ⇒ 同结果」可复现。

### 15.5 ⚠️ 影响评估（这个 bug 改变了什么、没改变什么）

- ❌ **「精确复现」被破坏**：不能假设「同 seed + 同棋谱 ⇒ 同结果」。
  这也解释了 §14 里 **K=3 从样本 A 的 +2146 翻到样本 C 的 −1920**（部分原因）。
- ✅ **配对设计的统计结论仍然有效**：每局的实验方与对照方在**同一进程、同一 hash seed**
  下对弈 ⇒ **配对内的比较是干净的**；hash 随机化是**独立同分布的噪声**
  （增方差、不引入系统性偏向）⇒ 镜像赛制的方向性结论不受影响。
- ⚠️ **与 §13.3 的关系**：上一轮修的 `order()` 次级键解决的是「**dict 插入顺序**」
  （由 `unmake` 的 `del`+重新插入引起）。而上一轮的验证脚本**在同一个进程里跑**，
  hash seed 相同 ⇒ **没有暴露**这第二个漂移源。两者**互相独立**，都必须修。
- ⚠️ **这是「同一进程内测不出来」的教训**：要测「跨进程确定性」，
  必须**跨进程**跑（换 `PYTHONHASHSEED`），同进程内重复调用永远测不出来。

---

## 16. 先验质量改进（Phase 5，2026-09-25）

### 16.1 一句话：先验**确实更准**，但**决策质量与强度都测不出收益**

| 证据 | 结果 |
|---|---|
| 留出 80 局，对「动过的格」的兵种预测 | 对数概率 **-1.7674 → -1.6326**（**+0.115~0.135 nat**，+6.3~7.6%）；top1 **24.8% → 37.5%（+12~13 pp）** |
| 同源上限 vs 留出 | 几乎重合 ⇒ **几乎没有过拟合** |
| 决策质量探针（648 检查点，三臂） | god-view 评分配对差 **-0.11**，95% CI `[-3.0, +2.8]` ⇒ 排除 ≥3 分收益 |
| 镜像对局 40 配对 | Δ 均值 **+108**，95% CI `[-87, +304]`，配对符号 **20 正 20 负** |

⇒ **两个开关默认关闭，不进入生产。** 生产/回归路径完全不变。

### 16.2 两个默认关闭的开关（`InfoSet(origin_prior=, infer_engineer=)`）

- **`origin_prior` —— 原点回溯先验**。旧实现 `sample_world` 对「动过的格」
  **完全退回均匀分布**（`mode=="moved"` 时 `pr = 1.0`），等于把「这枚子从哪里出发」整条丢掉。
  ⚠️ **可观测性论证**：任何碰撞都会让参与者公开（赢家翻开 / 双方离场 / 触雷 / 挖雷 / 扛旗）
  ⇒ **未知棋子只可能做出纯 `move`** ⇒ 沿走子链复制「原点标记」即可把未知子**回溯到初始格**
  ⇒ 「初始位置→兵种」先验适用于**全部未知格**（不再只是从未动过的格）。
  实测 12 局 898 格 **100% 可回溯且与真值一致**，三条独立不变量全 0 违例。
- **`infer_engineer` —— 工兵几何硬推理**。把该格换成「连长」后用**真棋盘**枚举可达集，
  目标不在其中 ⇒ 必为工兵。实测 2319 步：判定 63 次（**2.72%**），**假阳性 0**，覆盖真实工兵走法的 25.4%。
  ⚠️ 朴素判据「两坐标都变 ⇒ 工兵」是**错的**（忽略行营「米」字斜线 + 非工兵的「直行+恰一段弧线+直行」）。
  ⚠️ 起点在大本营时 `gen_moves` 恒空 ⇒ 会产生**假阳性**，必须显式排除。
  ⚠️ **覆盖面太小、改了 0 个决策** ⇒ 不值得单独保留（作为「纯可观测硬推理」样例留着）。

### 16.3 ⚠️⚠️ 等价性验证必须**双向**（本项目新增铁律）

`equiv_originprior_20260925.py` 的两种模式：

```bash
$P equiv_originprior_20260925.py 8 off   # 期望：known/pool/touched/dist/sample 五项全 0
$P equiv_originprior_20260925.py 8 on    # 期望：⑥dist 改变 >0 · ⑦采样改变 >0 ⇒ 不是死代码
```

- **只证「关着一样」是假绿** —— 可能只是功能没接上。
- 第一版 `off` 跑出 **④ 654/9884、⑤ 45/117 不一致**，挖出**两处真实的语义漂移**：
  1. `whatif.py` 的 `dist()`：旧版是「`not fresh` ⇒ 直接均匀、**根本不查先验**」两段式；
     我重写成「统一先查先验、再按 fresh 过滤」后，**「动过、且恰好停在初始格」**的格从均匀变成先验分布。
     **修**：`not fresh and not origin_prior ⇒ pc = None`。
  2. `ai_search_dark.py` 的 `sample_world`：旧守卫 `if mode != "moved" and pc and pc.get("p")`
     被简化成 `if pc and pc.get("p")` ⇒ 关着时 `moved` 格也查本格先验。
     **修**：`use_prior = (mode != "moved") or origin_prior`，不满足时 `pc = None`。
- **方法学要点**：用 `SourceFileLoader` 加载**改前备份**（旧文件无 `.py` 后缀 ⇒ `spec_from_file_location`
  推不出 loader，必须显式 `SourceFileLoader`）。**采样比对用独立 rng（同种子）、且不共享 board 引用**。

### 16.4 决策质量探针（`probe_prior_decision_20260925.py`）—— 比镜像信噪比高得多

镜像的因变量（整局净子力差 Δ）方差极大；先验改进本质是**信息质量**问题，直接问
「换了更准的先验后，选的走法是不是更接近上帝视角最优」更有效。

**设计**：沿真实复盘推进，为 4 方位各维护一套只喂可观测事件的 `InfoSet`；检查点处取**该步行棋方**，
分别用三臂跑 PIMC —— **三臂共用同一 rng 种子**（世界结构相同、只有兵种指派不同 ⇒ 干净配对）；
再用**完全信息**在同一真实棋盘上跑更强预算的搜索当参照系。

**结论**：648 检查点 / 24 局 / 10 进程 505s。决策变了 **60%**，但 **166 变好 / 152 变差 / 71 持平**；
命中上帝视角最优 21.5%→22.8%（McNemar p=0.47）；与棋手一致率 7.7%→7.9%。
**功率**：配对差 SD 37.2、SE 1.46 ⇒ 80% 功率可检出 **≥4.09 分**（基线 regret 29.2 分的 14%）。

**`--check-ref` 参照系信度检查（必须做，否则零结果无法解释）**：同一局面用两种预算
（A: K99/npw20000/d10 · B: K99/npw80000/d14）各算一次 ⇒ 最优走法一致 **36/36**、
同走法评分 **r=1.000**、重测差 SD 2.9 ⇒ **单次评分噪声 SD ≈ 2.1**。
⚠️ 但实测**实际搜索深度只有 2.0~2.2 层**（K=99 展开所有根走法 ⇒ 预算吃光，加 4 倍预算深度不变）
⇒ 参照系是「**低深度全信息评估**」，信度高但视野浅，
**只能说明「短期内无收益」，测不出更长远的收益**。报告结论时必须带上这句。

### 16.5 ⚠️⚠️⚠️ 假阳性实录：首样本 p=0.011，独立样本没复现

| 样本 | 配对 | Δ 均值 | SE | t / p | 胜负平 | 配对符号 |
|---|---|---|---|---|---|---|
| A（布局 1~20） | 20 | **+320.0** | 122.8 | **2.54 / 0.0111 ★** | 18/10/12 | — |
| B（布局 21~40） | 20 | **-103.6** | 142.2 | -0.71 / 0.478 | 16/18/6 | — |
| 合并 | 40 | +108.2 | 99.7 | 不显著 | 34/28/18 | **正 20 / 负 20** |

**教训（与本项目既有判据完全一致）**：SE=122.8 时 80% 功率检出下限 ≈ **344**，
而观测的 +320 **恰好卡在检出线下方** ⇒ 这种位置的「显著」最容易是假阳性。
**新纪律**：任何「显著」结果在写进结论前，**必须**再用**不同布局段的独立样本**复核一次。
`--offset` 就是为此加的。汇总用 `summarize_mirror_20260925.py`（自动合并 + 报功率 + 符号统计）。

### 16.6 `--jobs` 并行（已验与串行逐位一致）

`pimc_mirror.py --jobs N` 按布局用 `multiprocessing`（macOS 必须 `spawn`）并行。
⚠️ 用 `pool.map` + 模块级 `_job()`（参数必须可 pickle；`prior` 不能靠继承，必须在子进程各自 `new`）。
⚠️ **并行模式下所有 `print` 都在最后一次性返回** ⇒ 跑长任务时看不到中途进度。
**验证**：`--jobs 1` 与 `--jobs 2` 的 `d_strat/d_page/out/end/n/illegal` **逐位一致**（4 局全等）。

### 16.7 绝对强度锚线（`--anchor`）

镜像只能回答「A 比 B 好吗」；要回答「这一轮有没有变强」需要**冻结基准**。

```
ANCHOR_REF  = K=2, depth=8, npw=4000, worlds=3, agg=vote, origin=0, engineer=0
ANCHOR_EVAL = offset=0, n=20, steps=300, seed=7
ANCHOR_HIST = anchor_history.jsonl          # 逐次追加
python pimc_mirror.py --anchor --tag "…" --jobs 10
```

⚠️ **冻结纪律**：这两组常量**不得**随项目改进漂移；需要新基准就**新增** `ANCHOR_REF2`。
⚠️ 单次锚线 SE ≈ 125~140 ⇒ **只报「Δ ± 95% CI」，不拿单个数当结论**；
判「这一轮 vs 上一轮」用**镜像**，锚线只回答「相对冻结基准的绝对位置」。
⚠️ `--anchor` 会**强制两边同聚合**（否则测的是聚合不是改进）—— argparse 的 `--exp-agg`
默认 `borda` 会污染锚线 ⇒ 已把默认值改成 `None` 再按模式解析。

**零刻度标定（已跑，必做）**：让「我方 = 参考方」（同配置）跑同一评测集 ⇒ 真实差值 0，
测出来的就是刻度零点。实测 **Δ 均值 +2.1**（合计 +42）、SE 133.8、**t=0.02 p=0.9878**、
Wilcoxon p=0.9854、胜负平 11/15/14、`illegal` 0 ⇒ **零点正确，锚线无系统偏差**。
⚠️ 这条标定同时是**假阳性判据的校准物**：样本 A 的 +320 只比零点大 **2.4 个 SE**（SE≈134），
本来就落在噪声带内。

### 16.8 ⚠️ 一处**标注修正**（最容易骗过自己的那类错）

`probe_prior_holdout_20260925.py` 原把 `pr=None` 那行标成「均匀（无先验）」，
但它打出来的其实是 `B_p`（**池计数加权**）—— 而**那正是旧实现**对「动过的格」的预测分布；
同时 Δ 行拿 `B_u`（**完全均匀**，只是探针内部的百分比参照）当基准。
⇒ **数字被系统性高估**：相对「完全均匀」是 +0.200 nat，相对**旧实现**只有 +0.135 nat。

**新纪律**：基线名字里**必须写清「它到底是哪一版实现」**。
「什么都不用」与「旧实现」混为一谈，是最容易骗过自己的那种错。
（已修正标注，并把 Δ 改成报「**新 − 旧**」。）

### 16.9 「信息更准 ≠ 决策更准」的四个可能解释（②③ **已实测排除**）

1. PIMC 落子只由 3~8 个采样世界的「投票」决定，把分布调准多数时候只是**重排世界结构**
   —— **唯一仍站得住的解释**；
2. ~~参照系视野只有 2 层~~ ⇒ **已排除，见 §16.10**；
3. ~~`n_worlds=3` 太少~~ ⇒ **已排除，见 §16.11**；
4. 工兵几何推理信息量太小（0 决策影响）。

**排除两条后的判断升级**：剩下的①与④都**不是「还没试够」，而是「机制上就不该指望」**
⇒ **先验质量的改进在 PIMC 这条路径上不产生可测收益**。

**唯一还值得走的一条**：换到**分析侧**用这份先验 —— `dist()` 直接进 `eval_move` 的期望收益
（「替代走法评估」）。那是先验的**一阶用途**（分布准一分、期望收益准一分），
不像 PIMC 要过「采样 → 3 票投票 → 聚合」三层稀释。

### 16.10 参照系加深（②，2026-09-25 第二轮）：**视野从 2 层加到 6 层，结论不变**

<b>根因</b>：`Searcher` 的 `K` 截断**深层**分支（`gen()` = `order(all_moves())[:K]`），
而 `root_scores` **根层不截断**（全窗口枚举所有走法 ⇒ **任何 K 下每个走法都有分数**，
口径②始终良定义）。原参照系用 `K=99` ⇒ 深层每层也展开 99 个走法 ⇒ 节点预算在 2 层见底。

<b>加深办法 = 降 K + 加大预算</b>。节点数 ≈ `R × K^(d-1)`（R=根走法数 ≈ 54~99）。
⚠️ **成本 ≈ 节点预算** —— `gen()` 每节点都要重新枚举+排序**全部**合法走法
⇒ 每节点恒定开销。**这是深参照系的真正代价上限**（200k 预算 ≈ 15s/局面 ⇒ 648 检查点要 2.7 小时）。

`--ref-sweep N` 扫描结果（2 份复盘 × 2 检查点）：

| 配置 | 实际深度 | 秒/局面 | 与现用走法不同 | 自洽（2 倍预算） |
|---|---|---|---|---|
| `K99/20k`（原用） | **2.0** | 0.58 | — | 100% |
| `K6/30k` | 4.5 | 2.36 | 25% | 75% |
| **`K6/80k`（选定）** | **6.0** | 6.13 | **50%** | **100%** |
| `K4/80k` | 7.0 | 7.10 | 75% | 75% |
| `K6/200k` | 6.5 | 15.14 | 50% | 未做 |

⚠️ 注意「K6/200k 深度 6.5 < K4/80k 的 7.0」：**预算够也不能无限加深**，
K=6 的 `R×6^5` 已逼近 200k ⇒ 再加预算性价比骤降。**K=6/80k 是深度/成本的最优点**。

<b>结论（`--compare-ref` 同批决策换尺子）</b>：
- **三臂决策逐位一致**（不一致 0 次）⇒ 参照系确实只换尺子、不动决策，是**干净对照**；
- 两参照系选出的「最优走法」**62.5% 不同** ⇒ 浅尺子确实看不见东西，「视野浅」前提成立；
- 但先验的相对优势只从 **−0.11 → +1.44**（配对变化量 mean(c) = **+1.55, t=1.08 p=0.28**；
  Wilcoxon p=0.90；**符号检验 179 正 / 186 负 p=0.75**）⇒ **三者一致不显著**。
- ⇒ **解释②「参照系视野浅」被削弱**：加深 3 倍视野后收益仍测不出，且幅度仅
  deep 尺子 regret 基线（−28.6）的 **5%**。

⚠️⚠️ **新增方法论铁律（本轮的教训）**：**「翻转计数」这类只看符号、不看幅度的统计量，
在「零差样本占比高」时会虚高**。本例浅尺子下 **51% 检查点是平局** ⇒ 翻转检验报
**p=0.011「显著」**，而 t / Wilcoxon / 符号检验三者一致不显著 ⇒ **是假阳性**。
**判据：结论一律以「配对差 mean + 符号检验」为准；任何自定义统计量若与标准检验冲突，
先怀疑自定义的那个。**

### 16.11 世界数扫描（①，2026-09-25 第二轮）：**假设不成立，且镜像本就没分辨力**

假设「`n_worlds=3` 抽样方差淹掉了分布精度的改进 ⇒ 收益应随世界数上升而显现」。
在**冻结评测集**（offset 0 / n=20 / steps=300 / seed 7 / 双方同 agg=vote）上跑三点：

| 世界数 | 配对 | Δ 均值 | 95% CI | t / p | 胜负平 | 耗时 |
|---|---|---|---|---|---|---|
| 3 | 20 | **+320.0** | [+79, +561] | 2.54 / 0.011 ★ | 18/10/12 | 13.6 min |
| 8 | 20 | **−46.5** | [−296, +203] | −0.36 / 0.72 | 9/18/13 | 37.2 min |
| 12 | 20 | **+127.7** | [−115, +370] | 1.01 / 0.31 | — | 52.9 min |

- **OLS 斜率 −23.5/世界，SE 20.3，t=−1.15** ⇒ **不显著** ⇒ 假设不成立。
- ⚠️ 别把「从 +320 降到 −47」读成「收益随世界数衰减」——**+320 早已被独立样本
  （offset 20 → −104）证伪**，这一步只是**假阳性归位**。三点合起来是围绕 0 的噪声。
- **决策探针同口径**（深参照系）：worlds=3 `+1.44`(p=0.44)、worlds=8 `+2.28`(p=0.24)
  ⇒ 方向为正但极小且不显著。

⚠️⚠️ **最该记住的一条：这个实验本来就没有分辨力。**
每档**配对差 SD ≈ 577** ⇒ n=20 时 **SE ≈ 129、80% 功率检出下限 ≈ 361**。
⇒ **三档都只否定了 ≥360 的效应**；要检出 ±150 需 **~116 配对/档（约 5 倍算力）**。
**想在镜架上再谈「效应消失」，先解决检验力，而不是加世界数。**

⚠️ **顺带否掉一个直觉**：以为「世界数上去 ⇒ 对局更果决」——
实测超时/僵持率 **30.0% / 32.5% / 30.0%**、平均步数 **177 / 188 / 178**、
场上余子 **15.5 / 13.9 / 15.9** ⇒ **三档几乎完全一样**。
世界数只影响每步决策精度，不改变对局宏观走向。（⚠️ 别用 1~2 局的冒烟下这个结论。）

⚠️ `summarize_mirror_20260925.py` 的 `by_worlds()` **跨不同 worlds 的样本不可直接合并**
（不是同一套对局）—— 已加拦截，只出趋势表 + OLS + 果决度 + 功率提醒。

---

## 17. AI 强度对标：它在人类棋手里排第几（Phase 6，2026-09-25）

**问题**：AI 机器人在联众复盘库的棋手里排第几？
**答**：点估计 **P80 附近**（100 人榜约第 20 名），区间 **P50 ~ P95**。
交付 `AI水平位次评估报告_20260925.html`（10 节 10 表，`shoot_report --strict` 六项全过）。

### 17.1 库内规模与榜单口径
- 有名字玩家 **1103** 人；`n≥15` 的 **100** 人（≈常说的「99 位棋手」）；`n≥20` 的 **78** 人。
- 榜 = v3.1 五维总分（`player_rank_v31.json` / `player_rank_v31_n15.json`；分数 39.7~67.5，中位 54.0）。

### 17.2 五个口径（全部同局面配对）

| 口径 | 人类 | AI | 位次 | **尺子效度 ↔ 长期胜率** |
|---|---|---|---|---|
| 上帝视角命中率 | 6.6% | 22.6% | **P98** | **−0.156**（负！） |
| 8 步窗口净值 · `greedy` | +52.5 | +68.4 | P95 | +0.255 |
| **8 步窗口净值 · `pimc`** | +53.8 | +58.9 | **P70** | **+0.410** ← 最可信 |
| 单步即时收益 · `greedy` | +5.92 | +8.99 | —（4.07:1） | — |
| 完整对局胜负 | — | — | **测不了** | — |

### 17.3 ⚠️ 铁律一：报 AI 强度**必须同时报「尺子效度」**
三个口径的「尺子效度」与「AI 位次」**恰好反向**：
`上帝视角 −0.16 → P98` / `贪心 +0.25 → P95` / `PIMC +0.41 → P70`。
⇒ **尺子越偏 AI，AI 看起来越强**。只报「AI 赢了 X 分」而不报尺子能不能分辨人类水平，结论无效。
**今后任何 AI 强度结论都要附一列「该尺子 ↔ 玩家长期胜率」。**

### 17.4 ⚠️ 铁律二：上帝视角尺子有**同源偏置**，不能用来排位次
`god_view` 用 `Searcher` 的评估函数，而 AI（PIMC 的世界内搜索、贪心 `eval_move`）**用同一套**
⇒ AI 天然更贴合尺子。实测该尺子与玩家长期胜率 `−0.156`、与 v3.1 总分 `−0.288`（n=24）
⇒ **它分辨不出人类玩家之间的水平**。（`probe_ai_vs_human_20260925.py`）

### 17.5 ⚠️ 铁律三：「AI 替一方 + 其余照抄棋谱」打完整局 = **不可行**
实测 **100% 失配、平均只走 14 步**。根因：AI 一旦吃子，棋谱后续走法**起点已无棋子**。
四国军棋没有「局部换人」这回事（不像棋类有稳定的局面续接）。
⇒ 要完整对局胜负，必须让对手**能应对**（真人或全 AI）。

### 17.6 正确做法：**同起点、同步数的窗口配对**（`ai_window_match_20260925.py`）
从同一真实局面出发，两臂各走 K 个全局步：一臂全按棋谱（人类），一臂在轮到该方位时由 AI 决策、
其余方仍按棋谱。因变量 = 窗口内**该方位所在联盟**的净子力变化（`whatif.VAL`）。

- 两臂同起点 / 同步数 / 同对手走法 ⇒ 唯一差别是「这几步由谁走」，**配对干净**；
- **净值是真实交手结果**，不含评估函数偏好；
- `--engine greedy|pimc`：**必须写明用哪个** —— 同口径差 3 倍（+15.9 vs +5.0）；
- 窗口 **8 步 / 步长 12** 最稳（零差 27%，300 局 9847 窗口 / 10.8s）；
- `--window 1 --stride 1` = 单步口径，样本最大（7 万+）但最偏 AI（4.07:1）。

### 17.7 ⚠️ 窗口长度扫描的**选择偏差**（别再踩）

| 窗口 | 有效数 | AI−人类 | `t` | 零差占比 | 可解读 |
|---|---|---|---|---|---|
| 4 | 26397 | +10.40 | +55 | 36.5% | ✓ |
| 8 | 7490 | +15.30 | +29 | 27.3% | ✓ |
| 16 | 1235 | +18.72 | +11 | 33.8% | 勉强 |
| 32 | 180 | +6.48 | +1.8 | **67.8%** | ✗ |
| 64 | 37 | −7.38 | −0.9 | **94.6%** | ✗ |

长窗口下「有交手的窗口」因棋谱失配被**选择性剔除**，残余样本只剩「双方都没交手」的平静窗口
⇒ 配对差被压向 0。**不能读成「AI 的长期优势消失」。**

### 17.8 净值口径必须是**联盟口径**（自造 bug 实录）
第一版写成「对方阵亡 = 收益」，把**队友阵亡也算成收益** ⇒ 人类净值均值虚高到 **1096**
（合理量级 ±300）。正确：`ALLY[sd] == ALLY[d]` 记负，否则记正。

### 17.9 阶段结构与辅助证据
- 上帝视角下 AI 优势**随步数增大**（100+ 步 `+14.57, t=5.4`）；窗口净值下开局最大、残局最小
  ⇒ **两把尺子方向相反**，再一次说明它们测的不是同一件事。
- **唯一一致结论：开局（前 20 步）AI 不占优**（`−2.85`，不显著）
  ⇒ 人类的开局布阵 / 流派经验 AI 没超越。
- PIMC 不是碾压：37 位有样本玩家中 **13 人（35%）对 AI 是正分**（AI 吃亏），
  负值止于 −13.4，正值长尾到 +38.2（均值被正尾拉起）。
- AI 自对弈平均 **177~188 步** vs 人类 **186 步**（中位 180）⇒ 对局节奏一致。

### 17.10 下一步最该攻的指标
把**尺子效度从 +0.41 提到 0.6+**（到 0.6 才能把位次说到 ±5 名以内）。三条路按硬度排序：
① 上真实平台与真人下（最硬）；② 人机混合对局（失配后 AI 接管，只在失配前计分）；
③ **用真实胜负训练「局面 → 终局胜负」模型当独立尺子**（与 AI 评估函数解耦，
可复用 `eval_v3`/`v2feat` 特征栈，性价比最高）。

### 17.11 文件
`probe_ai_vs_human_20260925.py` · `analyze_avh_20260925.py` · `ai_window_match_20260925.py` ·
`analyze_win_20260925.py` · `ai_human_replace_20260925.py` · `player_rank_v31_n15.json` ·
数据 `avh_60.json` / `win_greedy_300.json` / `win_step_greedy.json` / `win_pimc_100.json`

---

## 18. 实战接入桥：让 AI 上真实平台对战（Phase 7，2026-09-25）

工作区 `live_bridge_20260925.py` · 交付报告 `AI实战接入方案_20260925.html`

### 18.1 结论先行：只缺 I/O 层

AI 侧早就齐备（`InfoSet.eval_move` 毫秒级 / `PIMCPolicy` 秒级且支持 `think_seconds` 时间预算 /
`match.py` 已建模「每步 30 秒 + 一局累计 5 次超时即出局」）。**唯一没有的是**
「客户端局面 → 内部表示 → AI 决策 → 客户端可点的走法」这条链 —— 即 I/O 层。

**三层架构（第③层可整体替换，①②不动）**：
① AI 核心（已有）｜② 会话桥（本轮交付）｜③ I/O（A 人工代操作 / B UI 自动化 / C 协议层）

⚠ **平台形态是硬约束**：联众与 QQ 的四国军棋主战场都是 **Windows 客户端**
（联众「单机复盘研究」正是 `.JQH` 的来源），macOS 跑不了 ⇒ 客户端必须在 Windows；
但桥做成「本地服务 + 浏览器」就天然跨机器，**这个约束在选择「人工代操作」后自动消失**。

### 18.2 坐标（三套，禁止混用）

| 体系 | 格式 | up 方军旗 |
|---|---|---|
| 内部 | `(row,col)` 0-based | `(0,9)` |
| **联众** | 行字母 + 列号(1-based) | `A10` |
| QQ | 行列 1-based 数字 | `(1,10)` |

```python
ROW_LETTERS = "ABCDEFGHKMNPQRSTW"   # 17 个；跳过易混的 I J L O U V
```
实测：`up=A10 right=H17 down=W8 left=H1`（四方军旗落在四边中线）。row0=up 一线 / row16=down / col0=left / col16=right。

### 18.3 ⚠️⚠️ 实战桥的**两个特有坑**（复盘管线永远踩不到）

**坑①：`info.known` 里的格必须回填 board，否则 PIMC 必崩。**
`observe()` 把摊牌的兵种记进 `info.known`；`sample_world()` 又把 `known` 里的格
**从待采样集合排除**（「已知 ⇒ 无需采样」）。而桥的 board 是「他方一律 `('?',side)` 占位」
⇒ 那些格**永远填不上** ⇒ 搜索层 `Searcher.move_value → W.payoff(atk,'?')` 直接 `KeyError`。
实测**第 2 步起必崩**。修法：`feed()` 末尾同步
`for k,piece in self.info.known.items(): if board[k][0]==UNKNOWN: board[k]=(piece, board[k][1])`。
⚠ **复盘管线踩不到**，因为那边 board 一开始就是 `board_from_rec()` 全真值。
→ 已加为验收断言「**已知格未回填** 必须 = 0」。

**坑②：搜索层不像评分层那样信息集感知。**
`eval_move`（评分）经 `target_piece()` 走信息集 ✓；但 `Searcher.move_value`（搜索）
**直接读 board 兵种算 `payoff`** ⇒ 搜索前 board 必须已被采样填满（桥的职责）。
失败模式是**响亮**的（`KeyError`），不是静默错建议 —— 这个失败模式是对的，别去「容错」掉它。

### 18.4 ✅ 无泄漏保证（可断言，务必保留）

`InfoSet.target_piece()` 对非己方棋子一律查 `self.known`，查不到**直接返回 `None`**
⇒ **board 里他方兵种即使填真值，也不改变 AI 的任何建议**。
→ 做成自检第④项：用「真值 board」与「占位 board」各算一遍建议，**必须逐位相同**。

⚠ 合成 `rec` 的正确构造（脱复盘实时局面）：`InfoSet.__init__` 只吃 `rec["pieces"]` 的
`(r,c,兵种**简写**,side)`（内部走 `FULL[p]`，传全名会 `KeyError: '连长'`）。
他方位置按**标准构成**回填即可 —— `pool[side]` 只是 `Counter`，丢掉位置↔兵种对应 ⇒ 不泄漏。
标准构成（25）：司1 军1 师2 旅2 团2 营2 连3 排3 兵3 弹2 雷3 旗1。
**军旗位置：只喂己方给 `Searcher`**（他方军旗未知；喂真值会让 `SW_THREAT` 泄漏）。

### 18.5 录入协议（为人录设计，约 6 字符/步）

```
<方> <起点> <终点> [结果]
  方：U/D/L/R    坐标：联众格式（A10）
  结果：省略=move | atk=攻方吃掉 | lose=攻方被吃 | both=同归于尽
        | dig=挖雷 | mine=碰雷阵亡 | flag=扛旗
```
**为什么这么少**：位置与颜色**本来就是公开信息**（暗棋只遮兵种）⇒ 不需要录盘面，
只需录「变化的那一格」+ 交手结果。己方 25 枚开局录一次（可固化成模板）。
未看清公开兵种可留空（`_guess()` 按剩余池权重猜，计入 `approx`）。

### 18.6 验证方法（这是「桥是对的」的唯一硬证据）

**把一整局真实复盘当成「人工录入流」**逐步喂进桥，**每步断言「桥内盘面 == 引擎重放盘面」**。
可信的理由：复盘同时给出走法与真实交手结果，**等价于一位录入零失误的操作者**。
实测 **60 局 / 12,000+ 步 / 盘面差异 0 格次**，覆盖 `move/attacker_wins/defender_wins/
both_die/dig/mine/flag` **全部 7 分支**。

```bash
python3 live_bridge_20260925.py --selftest              # 自检 5 项（含无泄漏断言）
python3 live_bridge_20260925.py --verify 60             # 验收：盘面零差异 + 已知格未回填=0
python3 live_bridge_20260925.py --replay 0 --side up --engine pimc --think 3
python3 live_bridge_20260925.py --interactive 0 --side up --engine greedy   # 实战录入
```
⚠ `greedy` 引擎在「人未采纳建议」时会**反复给出同一步**——这是**自洽行为不是 bug**
（局面未变 ⇒ argmax 不变）；`PIMC` 因采样随机且响应局面，会给出变化的建议。

### 18.7 胜率 → 位次的换算（比裸胜率强得多）

裸胜率缺「对手强度」，无法定位次。做法：
① 每局记录 **对手 ID + 胜负** → ② 用 `player_rank_v31.json`（1103 人榜）查对手强度
→ ③ 用 **Bradley-Terry / Elo** 反解 AI 强度分（赢强手加分多）→ ④ 插回 1103 人榜读位次**与标准差**。
⚠ 样本量：要在 1103 人榜上把位次说到 ±5 名，约需 **80–150 局**。
⚠ 这条路「与 99 人榜同坐标系 ⇒ 效度定义上 = 1.0」，远高于 Phase 6 那套决策质量尺子（最高 +0.41）。

### 18.8 合规红线（必须提示用户）

使用 AI 代打**不符合多数平台用户协议**，可能封号。仅限**自建房间/练习房 + 非主力小号**，
**不进排位/竞技/比赛房**。**不建议做协议层（路径 C）** —— 最明确的对抗性行为且投产比最差。

---

## 19. 实战桥 · 可视化录入（Phase 7 续，2026-09-25）

把桥从「命令行文字录入」升级成**复盘回放式可视化**：己方导入布局 → 其他三方盖棋 →
在棋盘上点各方棋子实时走棋 → 碰撞时右键选该步后果。

### 产物
| 文件 | 作用 |
|---|---|
| `四国军棋实战桥.html`（项目根） | 前端单文件，**生成物，勿手改** |
| `.workbuddy/ld/build_live_ui_20260925.py` | 前端生成器：从 `index_task2.html` 逐字抽取棋盘几何 + CSS 注入模板（`--check` 只校验） |
| `.workbuddy/ld/live_bridge_server_20260925.py` | 后端 HTTP（`--selftest` 7 项） |
| `.workbuddy/ld/bridge_e2e_20260925.js` | 端到端交互验收 30 项（真点击 / 真右键 / 真网络） |
| `.workbuddy/ld/build_bridge_doc_20260925.py` | 生成《使用说明》HTML（截图内嵌 base64） |

> ⚠️ 上表的「7 项 / 30 项」是**当时**的状态；**当前**为 后端自检 **11 项** / e2e **92 项**
> （§20.8 / §23 / **§24** 是现行的交付必跑清单；§24.12 是最新那张）。

启动：`python3 live_bridge_server_20260925.py --port 8765`，浏览器开 `http://127.0.0.1:8765/`。
⚠️ **必须走 HTTP**（服务 `GET /` 直接把页面送出来）；双击 HTML 只会显示「未连接」。

### ⚠️⚠️ 坐标口径：桥跟**平台**走，与三页**故意不同**
- 平台（联众 / QQ）= **行字母 + 列数字**；行字母表 `ABCDEFGHKMNPQRSTW`（跳过 I/J/L/O/U/V）。
  锚点（`live_bridge.to_lz` 与后端 `--selftest ②` 打印）：up 军旗 `(0,9)` = `A10` · right = `H17`
  · down = `W8` · left = `H1`。
- 三页棋盘标头 = **列字母 + 行数字**（象棋式，见 `studyCellName = String.fromCharCode(65+c)+(r+1)`），
  **与平台互为转置**。
- ⇒ 桥标头改成「上方数字 1–17 / 左侧行字母」，并加悬停坐标条显示
  `坐标 A10（行 A · 列 10）· 大本营`。**写反了坚哥在平台上就找不到格。**
  e2e 步骤 2 用四个军旗锚点做逐字对照（已设断言）。

### ⚠️ 兵种命名：内部简写、对外全名（混用会「棋盘对、托盘错」）
- `whatif.InfoSet.__init__` 是 `piece = FULL[p]` ⇒ **只吃简写**（`司`）；传全名 `KeyError: '连长'`。
- 前端 UI 全用全名（`司令`）—— `SHORT[全名]` 才是单字。
- 收口在服务端 `to_short()` / `to_full()`：**进库转简写、出 API 转全名**。
- 真实症状（本轮踩到）：随机布局返回简写、手动放置给全名 ⇒ 前端按全名算「已用/剩余」时简写全落空
  ⇒ **棋盘上明明放了 25 枚、托盘仍显示 25 枚**（`已放 25/25` 却不消失）。
- ⚠️ 自检写法坑：`FULL` 是「简写→全名」⇒ `SHORT_OF` 是「全名→简写」，
  **判「是不是全名」要用 `n in SHORT_OF`（键）**；写成 `.values()` 会把 25 个合法全名全判成非法。

### ⚠️ 走棋方必须从起点棋子**自动推断**
录的是「平台上实际发生的每一步」，**四家走法都要能录**。恒定填 `self.side` 会在轮到别家第一笔就炸：
`AssertionError: 走棋方 up 与起点棋子归属 left 不符`（`feed` 内断言）。
⇒ `Table.move(..., side=None)` 默认 `side or board[(fr,fc)][1]`。

### ⚠️ 撤销用「重放式」，不做 deepcopy
后端只存「己方布阵 + 走法流水」，任何变更后从零 `rebuild()` 重放。
- 结构上不可能出现「撤了但信息集残留」；也无需 deepcopy 大 `InfoSet`（prior/pool 大且易漂）
- 一局 ~200 步，单次重放 < 0.2 s
- 前提：`_guess()` 随机数可复现（`LiveSession` 内 rng 固定种子）
- 自检：撤到 0 笔后盘面必须与 `_initial_board` **逐格一致**

### 几何抽取的三个真坑（`build_live_ui_20260925.py`）
1. **`cut_braces` 的锚点常常不含 `{`**（如 `function foo(`）⇒ 从 depth=1 起算会多算一层、一路配平到文件末尾
   （`IndexError: string index out of range`）。应先 `src.index("{", i)` 再 depth=0 起算，
   切完断言「`{` 数 == `}` 数」。
2. **锚点必须唯一**：`:root{` 全页 5 次、`#boardWrap{` 2 次 ⇒ 用「锚点 + 紧随的特征串」锁定。
3. **块注释必须配平**：起始注释漏写 `*/` 会一路吞到下一个 `*/`，把 `BOARD_LAYOUT … function movePathCells(...){`
   整段注释掉，表现为 node 报 `Unexpected token '}'`（错误位置离真因很远）。
   生成后断言「`/*` 数 == `*/` 数」且 10 个函数头都在。

### 交付前必跑
```
python3 live_bridge_server_20260925.py --selftest        # 7 项（含 API录入 vs 引擎重放：位置差/归属差 = 0）
python3 build_live_ui_20260925.py --check                # 切块命中数
python3 .workbuddy/tests/check_js_blocks.py 四国军棋实战桥.html
node bridge_e2e_20260925.js --out <项目根>                # 30 项
```
⚠️ **e2e 开头必须先 `POST /api/new` 重置**：服务是常驻进程，上一次运行可能已把它推进到「对局」阶段，
页面加载后就没有布阵托盘 / 可放格（本轮实测栽在这里，症状是「本方阵地可放格 0 个」）。

---

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

**操作技巧（`TECH_SKILLS`）三项**：`令子言杀`+40 / `骗炸`+子力价值 / `无损`+5。（`骗令` 已于 2026-09-13 应要求删除；**`磨棋`+10 已于 2026-09-20 应要求删除**。删除「磨棋」时须同步清掉四处：`per[c]` 初始化里的 `moveOnly:0`、`t==='move'` 处的 `per[ac].moveOnly++`、`computeTechScore` 里的 `grant(c,'skills','磨棋',…)` 整行、以及 `TECH_SKILLS['磨棋']` 常量项 —— **`lastActionStep` 不能跟着删**，它被「复活圣手」「逃跑瓜分」等共用。）
`骗炸` 自 **2026-09-20** 起另带两项门槛（「团长及以下」＋「非我方当前绝对令子」）；`令子言杀` 自 **2026-09-20** 起改为**终局结算**（分值与去留取决于本局胜负）。两者详见下方。
- `令子言杀`（2026-09-13 新增替代 `骗令`；同日加「另一侧」约束；**2026-09-20 加终局口径**）— 敌方某家**绝对令子身份已明**后，我方用其**次令子**（仅次于该令子一级的子力）**避开这枚令子所在一侧**，攻击该家**另一侧**的子力。实现要点：
  - **「已明」追踪**：`originRevealed[origin] = step` —— ①`t==='killed'`（被撞击存活）时记 `preDefOri`；②`t==='eat'`（吃过子力）时记 `aOri`。注意在 `eat` 分支里**先做判定、再记 `originRevealed[aOri]`**，否则当步自身就会污染判定。
  - **判定六条件**（在 `t==='eat'` 分支内）：`dc && dc!==ac && dc!==ALLY[ac]`（目标是敌方）＋ `originRevealed[preTopInfoDc.origin]`（该家令子已明）＋ `preDefOri !== preTopInfoDc.origin`（打的不是令子本人）＋ `ap === nextRankDown(preTopInfoDc.piece)`（我方用的是次令子）＋ 两侧位均可判定（`preTopSide`/`preTgtSide` 都非 `'C'`）＋ `preTgtSide !== preTopSide`（打的是另一侧）。
  - **侧位判定**：`sideOfJ(j)` 把该家自身视角的「路」`j`（`localOf(color,r,c)[1]`，恒为 0~4）映射为 `j<=1 → 'L' 左翼`、`j===2 → 'C' 中线'`、`j>=3 → 'R' 右翼`。**令子与落点都在中线时不算触发**（无「所在一侧」可言），中线也不被视为「另一侧」。
  - **令子当前格**：`origin` 记的是棋子**初始格**（`origin[key]=key`，移动时 `origin[to]=aOri`），所以必须用 `cellOfOrigin(layout, ori)` 反查它的当前格再算侧位；`preTopSide`/`preTgtSide` 都在 `resolveMove()` 之前取（落点格此时仍有目标子）。
  - **三个辅助件**（都定义在 `computeTechScore` 追踪变量区）：`RANK_ORDER = ['司令','军长','师长','旅长','团长','营长','连长','排长','工兵']` + `nextRankDown(p)`（军阶降序取下一级，越界返回 `null`）；`topOriginOf(color, layout)`（返回该家绝对令子的 `{piece, origin}`，**必须在 `resolveMove()` 之前**调用，结果存 `preTopInfoDc`）+ `cellOfOrigin(layout, ori)`；`sideOfJ(j)`。
  - 与「绝对令子」口径一致：用 `VAL` 最大值选令子（同 `topPieceOf`），故令子是 炸弹/地雷/军旗 时 `indexOf` 为 -1、`nextRankDown` 返回 `null`，条件自然不成立。
  - 测试维度（触发几何）：正例（撞明后打另一侧 / 吃过子后打另一侧 / 左右对称 / 令子降级为军长时次令子降为师长）、反例（目标非敌方、令子未明、打令子本人、非次令子、改用炸弹、落点中线、令子中线、同侧）—— 见 `run_lingyan.js`。
  - **终局口径（2026-09-20 新增，用户口径）**：本项**当步只登记、不 grant**，分值在**终局结算**时按本局胜负入账：

    | 本局结果 | 得分 | 结算卡 |
    |---|---|---|
    | 胜利 | **+40** | 出现「令子言杀 +40」 |
    | **明确和局** | **+20**（40 的 50%） | 出现「令子言杀 +20」 |
    | 战败 | 0 | **完全不出现** |
    | 未分胜负（判不出胜队） | 0 | **完全不出现** |

    - **实现**：`t==='eat'` 分支里改为 `if (!lingYan[ac]) lingYan[ac] = {step, dc, top, ap, dp, topSide, tgtSide};`（一局只登记**首个**符合条件者，等价于 `grant` 的「同名去重」，`ly.step` 保留首次触发步号）；推演结束后新增「令子言杀终局结算」块，`COLOR_ORDER.forEach` 里 `var oc = finalOutcomeFor(c); var pts = (oc==='win')?40:((oc==='draw')?20:0); if (!pts) return;` 再 `grant(c,'skills','令子言杀',pts,ly.step, ...)`。
    - **`finalOutcomeFor(c)` 的判据必须与页面「结果」同源**：`var A = (analysis && analysis.alive) ? analysis.alive : alive;`（`D` 同理取 `analysis.defeatedAt`，否则本地 `diedAt`）。判据与 `getWinTeam()` 一致：一队全员出局、另一队尚有存活 → 存活队胜；两队全灭 → **最后离场方**胜；否则无胜队。
      - 为此 `markDefeat(col, stepNo)` 加了第二个参数（写本地 `diedAt[col]`），**三处调用点**（事件离场 / 扛旗 / 每步无活动子力）都要把 `si` 传进去。
      - **优先 `analysis` 不是可选项**：页面 `getWinTeam()`/`getResultText()` 读的就是 `analysis.alive`。只信本地推演会出现「页面显示我方战败、结算卡却给 +40」的自相矛盾。
    - ⚠️ **「和局」只认 `replay.meta['结果']` 命中 `/和局\|平局/`**。`.jgs` 结束事件的 `{2:'和局',4:'一方战败',6:'有玩家逃跑'}` 里「一方战败」**说不出是谁**，不能当结论；「未分胜负」一律 0 分（用户口径：和局与未分胜负**区别对待**）。
    - ⚠️ **`replay.meta` 只在文本链路存在**：`parseJGS()` 的返回值**没有 `meta` 键**，只有 `jgsToText()` 写出的 `结果=` 行经 `parseReplay()` 才进 `meta`。所以任何「按终局判据」的统计/扫描**必须走「.jgs → jgsToText → parseReplay → applyOrient」**（与页面 `startAnalyze` 同源）。用 `parseJGS().moves` 直算会**丢掉全部事件步**（样本 263 vs 页面 268 步），`analysis.alive` 全判存活 → 终局判据整体走偏（曾据此误报「102 → 17」，走对链路实际是 **103 → 49**）。
    - **影响面**（2026-09-20 全库 191 份，页面同源链路）：触发 **103 → 49 次**、累计分值 **4120 → 1740**；分布 `{40:103}` → `{40:38, 20:11}` —— 即 **54 条（52%）的完成者本局战败被剔除**；`未分胜负` 0 条。两条终局判据链路（本地兜底 vs 页面 `analysis`）**不一致 0 条**。
    - 测试：`run_lingyan.js`（**34 项**：正例 6 / 分值口径 7 / 反例 9 / 一局一次 3 / 源码级 9）+ `shoot_lingyan_index.js`（**11 项**实机：规则弹窗文案、胜方 +40、和局 +20、战败不出现、零页面错误）；`scan_lingyan_index.js` 扫全库影响面与两链路一致性。三个样本可复用：胜 `junqi2025_10_25_16_40.jgs`[黄]、和 `junqi2025_10_27_19_59.jgs`[黄]、败 `junqi2025_10_26_14_9.jgs`[绿]。
- `骗炸`（**2026-09-20 收紧口径**）— **非炸弹棋子主动撞敌方炸弹被炸**，骗出炸弹。落点 = `t==='both'` 分支里的 `dp==='炸弹' && ap!=='炸弹'`。计分 = `VAL[ap]`（该子力价值），**一局只记一次**（`grant()` 同名去重 → 记首个符合条件者）。两项门槛须**同时**满足：
  - ① **子力为「团长及以下」（含团长）**：`RANK_ORDER.indexOf(ap) >= 4`（`RANK_ORDER` 军阶降序，下标 4 = 团长；越界返回 -1 自然排除 炸弹/地雷/军旗）。**语义是「军阶」不是「价值」**，别改写成 `VAL[ap]<=35`（炸弹也是 35）。
  - ② **该子不得为我方当前绝对令子**：`ap !== preTopAc`，其中 `preTopAc = topPieceOf(ac, layout)` 是在 `resolveMove()` **之前**取的快照。① ②**不冗余**：当我方令子已降到团长级（司令/军长/师长/旅长皆阵亡）时，条件 ① 仍放行团长，靠 ② 拦住「拿自己最后的令子去送炸」。
    ⚠️ **判定时点必须是「撞击发生前」**：若挪到 `resolveMove()` 之后按「我方剩余最大子力」判，撞炸的令子已从 `layout` 中消失、我方令子会易主成更小的子力，于是 `ap !== top` 成立 → **误计分**。`run_zhabait.js` 有两条专项用例锁死这一点。
  - ③ 另补 **`dc !== ALLY[ac]`（只认敌方炸弹）**：`resolveMove` 只在 `dcolor === acolor`（同色）时早退，**队友的炸弹不会被拦**，所以这条不是死代码。同日把结算说明文案 `TECH_SKILLS['骗炸'].d` 改为「…（限「团长及以下」子力，且该子不得为我方当前绝对令子）」。
  - ⚠️ `grant()` 给 `skills`/`rules` 的 `desc` **只是形参、不会被存储**（只有 `titles` 会 push 进 `titleLog`），所以技巧项的说明文字**只**以 `TECH_SKILLS[名].d` 出现在「计分规则」弹窗里 —— 改口径时**代码与常量表两处都要动**。
  - **影响面**（2026-09-20 全库 191 份实测）：**304 → 185 次触发**（-39%），累计分值 **11510 → 3090**（-73%）；分值分布由 `{8:66,12:24,18:28,25:27,35:27,45:46,60:40,80:25,100:21}` 收窄为 `{8:72,12:28,18:31,25:27,35:27}`。注意 8/12/18 档**反而变多**：一局只记一次，原先被高等级诱饵「占位」的玩家，现在会改记其后一次的低等级诱饵 —— 这是去重规则叠加门槛后的正常现象，不是 bug。

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
- 合成场景测试台：`run_lingyan.js` / `run_zhabait.js` / `run_sfx_flags.js`（均已固化到项目内 `.workbuddy/tests/`）；`/tmp/junqi_test/run_titles.js`（**26 条**称号正反用例，含天使下凡新口径：己方握有全场令子时炸掉敌方令子仍触发）、`/tmp/junqi_test/run_rules.js`（**41 条**用例：逃跑瓜分 50% 由在局玩家平分（3 人各30 / 2 人各45）、**每局仅一次**（首次触发后第二次退出不再瓜分）、**门槛被拦不消耗机会**（首次 49% 被拦、第二次仍触发）、净值门槛正反例、5 次超时判负触发 vs 2 次超时不触发、扛旗勇士 20/50、基础得分=表现评估、称号 16 项全量减半核对、人屠已删除、技巧表已无「骗令」）—— 这两个 `/tmp` 脚本**随时可能已被系统清掉**，丢了就照 `run_lingyan.js` 的骨架重建。都构造 `{layout, baseLayout, moves, baseMoves, orient, baseOrient}` 直接调 `computeTechScore`；事件步写成 `{color, type:'event', event:'...', no, timeouts?}`。改分值后**必须同步更新其中写死的期望值**（例如「万人之上 = 50（减半）」「在局3人各30」），否则会误报失败。
- **渲染类断言**：`run_medal.js`（**28 条**：真实局名次与奖牌一一对应、两人/三人/四人并列的顺延规则、负分排名、圆章数量与提示文案、**奖牌三段结构 `tm-ribbon`/`tm-disc`/`tm-shine` 齐备且数字在圆牌内**、四段动画关键帧与绑定、绶带/圆牌四色分色、深色覆盖、reduced-motion 兜底）、`run_titlebadge.js`（**28 条**：两局 titleLog↔徽章条数/步号/名称/分值一一对应且按步号升序、徽章所在行带 `mv-has-title`、事件行也挂徽章、CSS 含 3 段动画 + 深色覆盖 + reduced-motion 兜底）与 `run_e2e.js`（**14 条**：初始化无异常 + 两条数据源各自的 13 个面板非空 + 无 `undefined/NaN/[object Object]` + 奖牌数 = 卡数）。改 `renderTechScore()` / `renderMoveList()` 的 HTML 结构时都要跑。
- **不要对同一个文件并行发多个 Edit**：两条 Edit 落盘会互相覆盖，后写的那条基于旧快照，前一条改动被静默丢弃。两种症状都真实踩过：
  ① 代码里引用了一个刚被删掉的 `var`，报 `ReferenceError: xxx is not defined`；
  ② **更阴的一种：两条 Edit 都回「Successfully edited」，但只有后一条真的落了盘**（2026-09-20 改 `run_lingyan.js` 时踩到 —— 一次并行发了两处不同用例的修改，前一处被无声吞掉，于是测试持续报红而代码「看起来已经改过」，白查了半小时）。
  **改多处时一律逐条串行发**；若刚做了并行 Edit，落盘后 `grep` 回读一次确认。
- **`techRuleRows()` 的 `+` 前缀**：只对纯数字（或数字开头且不含 `%` 的 `pts`）自动加 `+`；`表现评估` / `50% 平分` / `+20 / +50` 原样输出。

## 测试脚本维护

- **测试脚本一律放 `<项目>/.workbuddy/tests/`，绝不放 `/tmp`**（`/tmp/junqi_test/` 已被系统清空三次：2026-09-13、09-14、09-15）。2026-09-15 起整套测试台固化到项目内。修改引擎/渲染后先更新测试断言（新基线、新用例），再跑回归。
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
- **e2e 基线**（`DEMO_TEXT` = `junqi2026_6_24_16_22.jgs`，**2026-09-20 实测**·表现评估改「交换比」主锚后）：拆分 = 基础得分(表现评估) + 称号 + 规则 + 技巧 → 绿 = 76+80+20+15 = **191**（A 级）；黄 = 46+40+0+75 = **161**（C）；蓝 = 36+0+0+15 = **51**（C）；紫 = 54+20+0+40 = **114**（C）。**注意这组数字只在「表现评估公式 + 称号表 + 规则表 + 技巧表」四者都不动时才成立**——`骗炸` 分值 = 被炸掉的己方棋子价值（`VAL[ap]`）、`逃跑瓜分` 按剩余净值与在局人数浮动，改任意一项都要重新实测。所以别把它们当固定断言，只做「页面零错误 + 各项加总等于总分」的校验（原先的 `/tmp/junqi_test/run_check_base.js` **已被系统清理，需重建**；重建时构造 `{layout, baseLayout, moves, baseMoves, orient, baseOrient}` 直接调 `computeTechScore`，事件步写成 `{color, type:'event', event:'...', no, timeouts?}`）。本局门槛实况（可在 `escapeSplit` 插桩打印）：蓝 剩300/739=41%、紫 剩295/739=40% 均被门槛拦截；黄 剩371/739=50.2% 通过，但队友绿已被扛旗出局，在局者唯余紫 → 紫独得 `round(371*50/100)` = **186**。（本局只有黄一次合格离场，故「每局最多一次」不改变分数。）
- **`.jgs` 演示局（`#btnLoadDemo` = `junqi2026_6_22_16_38.jgs`，75 步，方位 绿down/黄up/蓝right/紫left）**：黄(69 步，剩净值426/739=58%)先主动离场且过门槛 → **本局唯一一次**逃跑瓜分，在局 3 人（绿/蓝/紫）各 +`round(426*50/300)`=71；绿(75 步)随后离场时 `escapeDone` 已锁定 → **不再瓜分**（这正是「每局最多一次」生效的直观样本）。终局技术积分：绿 99 / 黄 45 / 蓝 173 / 紫 151。（两局示例均未触发「令子言杀」。）
- **注意页面里有两个不同的示例**：`#btnLoadDemo` 载入的是 `.jgs` 演示（`junqi2026_6_22_16_38.jgs`，玩家 木木/江湖人称小武哥/%无声仿有声%/暴暴寒），与 `DEMO_TEXT` 不是同一局。用浏览器截图核对分数时不要拿 `DEMO_TEXT` 的基线去比。
- 新增视角/旋转类需求：加用例覆盖目标玩家=下家、军旗落新大本营、行棋序、玩家卡、坐标旋转、可切回绝对方位。
- 断言对象相等用**逐键断言**（`obj['绿']==='up'`），勿用 `JSON.stringify` 比较——JS 对象键插入顺序会造成误判。

## 方位推导机制（详见 references/jgs-format.md）

- ⚠️ **方位映射必须是【一一对应】（2026-09-20 改，最容易再犯的一条）**：旧实现让每个颜色**各自独立投票**（旧 `voteDir`，已删除），互不知道对方投了什么，会出现**两家撞同一方位**。撞车方的布局矩阵在铺盘时被整片覆盖，后果是连环的：
  ① 该方棋盘上一片空白（**0 棋子**，用户报的就是「绿方不显示棋子」）；② 方位行缺一项；③ `teamSplit()` 退化成 **3:1** → `getWinTeam()` 给出**三个玩家名当胜队**；④ `TURN_ORDER` 里出现 `undefined` → `renderTurnStrip` 读 `COLOR_INFO[undefined].dir` **抛 TypeError**（被 `gotoStep` 内部 catch 住，只见行棋序条整条空白 + toast）；⑤ 页面还会误触发「以己方为下家」的视角旋转（撞车方拿不到 down 位），把棋盘整体转 180°，更难看出问题。
  现改为 `pickOrientByScore(scoreOf)`：**在 24 个「颜色→方位」双射里取打分最高者**，结构上不可能撞车。
  - `.jgs` 的打分 = **行棋自洽率**（`orientSelfCheck`）。铺盘后按 `seq` 逐条模拟（离场事件 code=3/4 按 `resolveMove` 语义撤走该家棋子；res 0/1 走子、2 攻方死、3 同尽），统计「**起点格上站着的正是行棋方棋子**」的步数占比 —— 正确方位应接近 100%。
    **为什么不用「落点分区投票」**：棋会深入敌境（本例紫方一路打到下行），按 from 坐标的半场投票会把这类棋算成对方半场的票。实测该文件 紫 down 61 票 > left 47 票 → 投错；而自洽率对正确方位是 **269/269 = 100%**、对错方位只有 22%。
  - 文本复盘的打分 = 逐子落点票数（`deriveOrientFromLayout`，布局行即初始落子，均在各自阵营半场）。
  - 平票时自动回退默认方位：`ORIENT_PERMS[0]` 配 `COLOR_ORDER=['绿','黄','蓝','紫']` 恰好 = `DEFAULT_ORIENT`（上绿/下黄/左蓝/右紫），而 `pickOrientByScore` 打分相同时**保留先出现者**。
  - `.jgs` 额外给「等于玩家块字节默认方位 `QQ2DIR`」的假设加 `1e-6` 权重作次级判据（盖不过任何真实差异）。`orientSrc` 现为「该颜色有行棋 → `'geo'`，无 → `'byte'`」。
  - 配套守卫（三层，缺一不可）：`teamSplit()` 要求 **恰好 2:2** 否则返回 `null`（宁可交给 meta 兜底，也不给出三个名字的「胜队」）；`applyOrient` 里撞车颜色**顺位补空方位**；布局铺盘**跨家撞格先到先得**（绝不整片覆盖）；`renderTurnStrip` 跳过缺失方位。
- 文本复盘：`[对局信息]` 的「方位=上:绿 右:紫 下:黄 左:蓝」行最优先（`'meta'`）→ 布局落点推导（`'layout'`）回退。
- `applyOrient(replay)` 把 orient 应用到渲染层：重排 TURN_ORDER、更新 TURN_POS/COLOR_INFO[c].dir、写回 replay.orient/dirToColor/orientSrc。**startAnalyze 必须在 parseReplay 之后调用 applyOrient**。
- **视角旋转在 applyOrient 之后由 `setView(replay, viewColor)` 完成**：先保存 baseLayout/baseMoves/baseOrient，再整体旋转坐标与方位，再调用 applyOrient 更新渲染全局。`loadViewPref/saveViewPref/viewColorOf` 负责读取 localStorage 视角偏好并解析为颜色。
- `inBase` 必须读 `replay.orient`（或 DEFAULT_ORIENT），不得写死颜色→区域；旋转后 orient 与坐标同步更新，故仍正确。
- 渲染层「方位映射」元信息项需带来源标注（行棋坐标推导/文件方位/布局位置推导），并在视角旋转后追加视角说明。
- 板底图例需随当前视角动态更新（`renderLegend`），不能写死 上绿/下黄/左蓝/右紫。

## 领域格式速查

- `.jgs` 二进制：偏移 0x20 起 4 个 88B 玩家块（p+0x00 颜色字节、p+0x08 名字 GBK 20B、p+0x1C 布局 30B）；指令区 0x19B/0x19C 起（双偏移容错），每 10B 一条，0x5F=棋步、0xF5=事件；**⚠️ `0x19~0x1A` 那个「指令总数」小端 uint16 字段实测不可靠，绝不能当扫描硬上限** —— `junqi2025_6_19_21_14.jgs` 里它是 `4`，而文件实含 256 条记录（252 步 + 4 事件），拿它当上限会把整局截成前 4 步（四家各一步）→ 四色各只 1 票 → 回退默认方位 → 0% 自洽、胜负全错。现按文件长度折算：`MAX = Math.floor((bytes.length - start) / 10) + 1`；棋步 b1 位4-3=玩家颜色位 `bits=(b1>>3)&3`，**为有状态状态机**：开局阶段取值=玩家块颜色字节 QB 的「(QB+1)&3」偏移（bit=0→块1/1→块2/2→块3/3→块0），等价 `BYTE_COLOR[(bits+1)&3]`（即 `['蓝','绿','紫','黄'][bits]`）；玩家离场（0xF5 code=3/4）后，该颜色位由颜色环后继者继承（RING=蓝→绿→紫→黄→蓝，跳过已离场者）。b2b3=起点(纵,横)、b4b5=终点，纵坐标自下而上需 16-y 翻转。事件字节：b1=02超时/03战败/04退出/05结束、`a`=玩家颜色字节（`BYTE_COLOR[a]`）、`b`=参数；**code=3 战败若紧随「刚被扛军旗的同一家」，文本应为 `军旗被扛，战败`（QQ 在扛旗后发 code=3），否则为 `自杀战败`**；事件穿插于棋步间，`extractMoves` 用 `seq` 保留指令流顺序。
- 完整字段说明见 `references/jgs-format.md`。
- **联众 `.JQH.TXT` 文本**（2026-09-24 新增）：**GBK + CRLF**；头 `Junqi Output Text File by www.ourgame.com` / `Version 1.31.0.2.1998.710`；
  **17×17 ASCII 字符栅格**恒 24 行（`P` 普通格 / `C` 行营 / `H` 大本营 / `R` 铁路通过点 / `.` 空白；
  ⚠️ 中央 5×5（行/列 6-10）内 9 个 `H` 是**兵站**（可停留、初始空），16 个 `R` **不可停留**）；
  坐标 = 全角字母行 `Ａ Ｂ Ｃ Ｄ Ｅ Ｆ Ｇ Ｈ Ｋ Ｍ Ｎ Ｐ Ｑ Ｒ Ｓ Ｔ Ｗ`（跳过 I/J/L/O/V/X/Y/Z）
  + 数字列 `col = num - 1`（**「映射 A」**，8 种候选映射里首步命中率 64.3%，次优仅 43.6%）；
  **顺时针**行棋序（QQ 为逆时针，**这是两者唯一规则差异**）；玩家行配色有 **4 种变体**（上蓝/下红/左绿/右灰 等），
  **颜色只标识玩家、与方位无关，正则勿写死**（应为 `^(上|下|左|右)(蓝|红|绿|灰)(\*?)\s*[:：]\s*(.*)$`）。
  ⚠️ **非工兵碰地雷 → 攻方阵亡、地雷原地保留**（不是同归于尽；见下文专节）。
  解析器 `jqh_parse.py` / 引擎 `junqi_engine.py` / 驱动 `replay_drive.py`，全在 `qq军棋复盘分析/.workbuddy/ld/`。

## 残局研究（2026-09-21 新增 · **三页共有**：`index.html` / `index_task2.html` / `index_task3.html`）

**需求口径（用户原话）**：在「复盘回放」旁加「残局研究」按钮 → 点开出现空白棋盘，**四方不同颜色的棋子放在棋盘外四个托盘**；点托盘棋子 → 点棋盘任意位置落子（**本方军棋必须在本方大本营，地雷必须在本方第 5、6 线**）；点「开始研究」后用鼠标控制各家行棋，**一家一步，顺序按原有规定（逆时针）**。

### 落点与结构

- **覆盖层实现（`#studyOverlay`，`position:fixed` 全屏）**，不复用 `#boardGrid`：残局棋盘是**独立 DOM**（`#studyGrid` + `scell-r-c`，class 仍用 `.board-grid`/`.cell` 以继承全部棋盘样式），布局状态 `studyLayout` 与 `#boardGrid` 的 `layout` 完全分离 —— 两边互不干扰，主棋盘「点棋子＝盖牌」的委托挂在 `#boardGrid` 上，碰不到残局棋盘。
- **棋盘几何直接复用**：`buildBoardSvg()`（返回字符串）+ `BOARD_LAYOUT` + `RAIL_LINES` + `isRailway`/`railLinked`/`railArcLinked`/`railNeighbors`，`buildStudyBoardOnce()` 是 `buildBoardGrid()` 的副本（只换 id 前缀 + 只建一次）。
- **吃子结果判定复用 `resolveMove(move, layout)`** —— 落子合法性由自己校验，结果类型 / 分值变动 / 扛旗清子全部走既有引擎，保证与复盘口径一致。
- ⚠️ **入口必须在导入面板也放一个**：`#mainGrid` 初始 `display:none`（未导入棋谱不可见），只放 h2 里的按钮会导致「不导入棋谱就进不去」。现在两个入口：`#btnStudyEntry`（导入面板按钮行，`id="btnClear"` 之前）+ `.area-board h2` 里 `button[onclick="studyOpenPanel()"]`（在「↗ 全屏窗口」之前，同样 `margin-left:auto`）。

### 三页同构移植（2026-09-21 晚 · `index_task3.html` → `index.html` / `index_task2.html`）

**结论**：残局研究已整体搬到三页。`index_task2.html` 与 `index_task3.html` **完全一致（diff 0 hunk）**；`index.html` 只比它们多出「竞技技术积分」模块（+ `data-page-node-id` 设计画布 ID 值不同，属噪音）。

残局研究 = **6 个可移植块**，由断言式脚本 `add_study_module.py` 一次性插入，**纯插入、0 删除**（合计 721 行）：

| 块 | 源行 | 行数 | 插入锚点（A~D **插在其后**，E/F **插在其前**） |
|---|---|---|---|
| A CSS | 692-733 | 42 | `html.theme-dark .popup-tip{color:var(--muted)}` |
| B 入口按钮1 | 783 | 1 | 行含 `<button` + `id="btnDownloadTxt"` |
| C 入口按钮2 | 824 | 1 | 行以 `<h2` 开头且含 `🕹 复盘回放` |
| D 覆盖层 HTML | 918-946 | 29 | 行含 `class="toast" id="toast"` |
| E 铁路可达集 JS | 1156-1279 | 124 | `/* 生成铁路网 + 行营斜线的 SVG 叠加层` **之前** |
| F 残局研究主体 JS | 3541-4064 | 524 | `/* ================= 复盘回放弹窗（1024×768）` **之前** |

⚠️ **六块都不含 `data-page-node-id`** —— index.html 那套设计画布 ID 与 task 系不同，但新增内容一律不带该属性，所以锚点只需匹配「文本行」，不必匹配随机 ID（B/D 的锚点行本身含 ID，用「含某子串」的谓词找即可）。

⚠️ **F 块的外部依赖全部是两页已有的公共函数/常量**：`buildBoardSvg` `isRailway` `movePathCells` `playSound` `stopPlay` `resolveMove` `railLinked` `railNeighbors` + `BOARD_LAYOUT` `COLOR_INFO` `COLOR_ORDER` `DEFAULT_ORIENT` `DIR_CN` `PC_COLORS` `TURN_ORDER` `RAIL_ARC_LINKS` `RAIL_LINES` `VAL` `FLAG_H_DIR`（`STUDY_FULL` 由 F 块自带）。**顶层标识符与两个目标页零重名**（曾逐一比对 158 / 148 个原有顶层声明）。改残局研究时若新增顶层名，仍需复查一次。

⚠️ **残局棋盘会用到分区底色**：`buildStudyBoardOnce` 给四家阵地加 `green-area/yellow-area/blue-area/purple-area`，所以 `--*-bg` 的深浅**直接决定残局观感**——移植残局研究时**必须一并确认分区底色一致**，否则同一残局在两页看着不一样（实测整片底色差异达 22.5% 像素）。

**同批同步的 3 处「非残局研究但影响观感」差异**（脚本 `sync_visual_task3.py`）：浅色分区底色 4 个变量、深色分区底色 4 个变量（均 `.11 → .17`）、`.board-svg{}` 之后 6 行「铁路重绘说明」注释。

**验收口径**：三页实拍 `arrow/nohint` 截图差异 ≤ 115 px（0.033%，仅棋子文字抗锯齿），**选中态 0 差异**；三页 `verify_study_task3` 125/0、`verify_study_rail_task3` 292 位置零差分 + 12/12、`verify_study_dom_task3` 77/0。

### 摆子约束（`studyPlaceCheck`）

| 子 | 规则 | 实现 |
|---|---|---|
| 军旗 | 只能在本方大本营两格 | `FLAG_H_DIR[studyDirOf(color)]` 命中才放行 |
| 地雷 | 只能在本方第 5、6 线 | `studyLocalOf(color,r,c)[0] >= 4`（i=0 最前线 … i=5 底线） |
| 其余 | **任意位置**（含敌境、中央兵站） | 只校验「是行棋点」+「该格为空」 |

`studyLocalOf` = `mapLayout` 的逆映射：`up→[5-r,10-c]` / `down→[r-11,c-6]` / `left→[5-c,r-6]` / `right→[c-11,10-r]`。**task3 没有 `ALLY`/`localOf`（那是 index.html 技术积分模块里的）**，队友关系由方位对家现算：`studyAlly()` 取 `{up:down,down:up,left:right,right:left}` 反查。
摆子阶段的交互：点托盘棋子 → 选中（同时高亮全盘合法落点 `study-hint`）；点棋盘落子；**点棋盘上已有的棋子 → 取回托盘**（按军阶序插回）。
⚠️ **行棋阶段的可落点不做任何视觉标记**（2026-09-21 晚起，见「视觉标记口径」节）：`.study-target` 只剩 class 影子，用户靠状态条「可走 N 处」+ 点错时的「该格不是合法落点」反馈。

### 走法生成（`studyLegalTargets`，四国军棋规则）

1. **公路一步**：正交相邻且两格之间有公路 —— `studyInCenter()`（行6-10×列6-10）内的格之间**没有公路**（那里只有铁道），任一端在中央区即正交不通；**行营「米」字斜线**可斜走一步（`dr=dc=1` 时要求至少一端 `studyIsCamp`）。
2. **铁路**（`isRailway(r,c)` 的子才有此分支）：**统一入口 `railReachSet(r,c,blocked,isEng)`** —— 详见下面「铁路行驶规则」节。**不要再写「沿 4 方向直线 + 直接 `railArcLinked(r,c,…)` 判弧线」的老实现**，那样棋子走到环角后拐不上弧线。
3. **不能移动**：地雷 / 军旗；**大本营内（`studyIsHQCell`）的棋子也不能移动**（含刚走进去的）。
4. **不能攻击**：己方、**队友**（方位对家）、**行营内的棋子**（安全区）；行营有子也不能再进（一营一子）。

### 铁路行驶规则（2026-09-21 定稿 · 官方原文 + 四条独立证据链）

> **一句话**：非工兵在铁路上 = **直行** 或 **直行 + 一段弧形线 + 沿「到达朝向」继续直行**（一手棋至多转一次弯，且**弧线是有向的**：反向进弧 / 出弧后反向直行都等于「掉头」，一律禁止）；工兵在铁路上**可以走到任何有铁路的地方**（任意拐弯）。
> **官方原文（坚哥 2026-09-21 提供，最高依据）**：
> 「在公路上，棋子每次只能走一步；在铁路上，只要路途没有棋子阻隔，步数就不受限制。**但遇到铁路直角拐弯时，除了『工兵』允许通过外，其他棋子是不能通过的。**」
> 「另外，**大本营中的棋子以及『地雷』，不能移动。**」
> 同口径旁证：百度百科/网易/边锋「其它棋子在铁路线上只能直走或经过弧形线，不能转直角弯」；CYC 平台「鐵路上，可以走直線和轉一次彎的路線」。

⚠️ **旧实现的两个致命错**（坚哥实拍报的 4 个 bug 全是它引起的）：
- 弧形铁道判定写成 `railArcLinked(r, c, ar, ac)` —— **用棋子的「原始起点格」坐标**。棋子沿铁路走到环角后起点已不是弧线端点，于是拐不上弧线 → 表现成「**蓝军走别人家铁道只能前进一步**」「**紫师不能走别人家铁道**」。
- 老口径「非工兵只能直走」本身也不对：全库 2351 步违规。

**正确实现（三个原语，紧接 `railShortestPath` 之后）**：

| 函数 / 常量 | 作用 |
|---|---|
| `ARC_DIRS` | **弧线两端的有向朝向表**（本轮核心）。`{'6,5':[3,2], '5,6':[1,0], '5,10':[1,0], '6,11':[2,3], '10,5':[3,2], '11,6':[0,1], '10,11':[2,3], '11,10':[0,1]}`，索引同 `RAIL_DIRS`（0上 1下 2左 3右）。`[depart, arrive]`：**depart** = 能以之「上弧」的行进方向；**arrive** = 出弧后**唯一**允许继续直行的方向（= 反向 depart）。几何含义：以「朝被绕过的兵站（交叉口）走」的方向到达本端才能上弧，出弧后只能背离那个交叉口继续 |
| `railArcPartner(r,c)` | 弧形铁道另一端（不是弧线端点则 `null`）。`RAIL_ARC_LINKS = [[6,5,5,6],[5,10,6,11],[10,5,11,6],[10,11,11,10]]`，圆心 = 对角格 `[[5,5],[5,11],[11,5],[11,11]]` |
| `railReachSet(r,c,blocked,isEng)` | **唯一**可达集入口，返回 `{'r,c':1}`（不含起点）。`blocked` = 占用表 |
| ~~`railThroughDirs(r,c)`~~ | ⚠️ **历史遗留 · 已无调用方**（2026-09-21 晚起）。它只给「穿过型轴向」，用它做转向校验会放过两种掉头。保留仅为可追溯，**勿再接线** |

`railReachSet` 非工兵分支是**射线递归 `_ray(r0,c0,d,usedArc)`**（不再是状态机 BFS，也不再用 `railThroughDirs`）：
- 从起点沿 4 条射线的各方向 `_ray`；每走一格 `out[kk]=1`，遇 `blocked[kk]` 立即 `return`（**可吃不可穿**）。
- 走完一格后若 `!usedArc` 且 `ARC_DIRS[kk]` 存在且 **`ARC_DIRS[kk][0] === d`（depart 对齐）** → 可上弧：登记 `out[对方端点]`，未被堵则 `_ray(对方, ARC_DIRS[对方][1], true)` —— **出弧方向被锁死为 arrive**。
- `usedArc` 为真后**只能继续直行** ⇒ 结构上实现「一手棋只拐一次弯」。
- **起点恰在弧线端点时**可直接上弧（不需要 depart 对齐），与「从相邻格走来」对称。
- **工兵分支**：`railNeighbors` BFS 全网任意拐弯；中间格有子 → `out[kk]=1`（**可吃**）但不入队（**不可穿**）。

⚠️ **不要改回「只校验切线轴向」**（旧 `railThroughDirs` 版）：那会把 ① 反向进弧 ② 出弧后反向直行 两种**掉头**当成合法 —— 全库各 0 例，纯属过宽。当前页面 = `ARC_DIRS` 有向模型。

⚠️ **改口径后必有「测试变红」，先分清是回归还是过期期望**（本轮踩过）：`verify_study_task3.js` / `verify_study_rail_task3.js` / `verify_study_dom_task3.js` 里都写死了旧宽松模型下的期望（(6,15) 可经弧线到列 6 下端、(10,1) 可达、紫师 42 格…）。判定基准只能是**官方原文 + 全库拟合**，不是测试里的老数字。正确动作 = 把**参考实现一起**改成有向模型 → 用 `probe_study_targetcount_task3.js` **重测**基准数 → 再改期望；**绝不能为了让测试变绿把页面改回去**。

**落点基准数**（`probe_userboard_task3.js` 原样复刻坚哥截图局面）：
- 紫旅长 (8,15)：**8 个落点** = v15 竖向铁路上下 4 格（(7,15)(6,15)(9,15)(10,15)）+ 第 8 线公路左右 2 格（(8,14)(8,16)）+ 两条行营斜线 2 格（(7,14)(9,14)，因这两个是行营）。线路很少，正合坚哥「只有 5 条线路可以走」的直觉 —— **收紧前后都是 8 格**（此处本来就对，真正过宽的是别的位置）。
- 蓝连长 (10,1) **34 → 20**、蓝司令 (15,6) **24 → 17**（砍掉的全是掉头越权格）。

**拟合证据（四条独立链，全部跑绿才算定稿）**：

| 脚本 | 关键数字 |
|---|---|
| `verify_railturn_task3.js` | 候选规则 R0（只走直线）**2351 步违规** ❌；**R1~R6 全 0** ✅（R6 = 页面现行有向模型） |
| `verify_arc_strict_task3.js` | 非工兵多格 **13618** = 纯直线 10366 + 弧线·严格 3252；**弧线·仅宽松 0 例、★其它 0 例** ⇒ 全库从不掉头（判决性证据） |
| `verify_railstrict_task3.js` | 页面 `ARC_DIRS` vs 独立几何复算 **8 端点全一致**；页面 `railReachSet` vs 严格模型 **73 个铁路起点零差异**；旧宽松模型**多给 1140 格** |
| `probe_study_boardstate_task3.js` | 全库 **34461 步（多格 15203）在真实棋盘状态下 100% 被残局研究认可，认不出 = 0** |

- 非工兵 4315 步拐弯的**转向格 100% 落在 8 个弧线端点上**；工兵则 L 形(602)/S 形(325)/十字口(18) 都能拐（拐弯点分布由 `verify_railturn_task3.js` 直接打印）。
- 非工兵拐弯中**只用 1 段弧线的 100%，2 段及以上 0 步** ⇒ 「一次行棋至多一段弧线」。
- ⚠️ **不可放宽**（多段弧线 / 只校验轴向 / 允许掉头）：都会凭空多出绕行落点，全库零例支持。
  (6,15) 紫师这一位的基准值变迁：**48**（早期，R 格未禁停）→ **42**（2026-09-21 第三轮 R 格不可停）→ **23**（本轮有向收紧）= v15 南下 4 + h6 西行 12 + 弧线转列 10 共 5 + 公路 2。
- ⚠️ **`.jgs` 之外还有一条规则**「大本营中的棋子不能移动」：已由 `studyIsHQCell` + `studyLegalTargets` 首行 `if (studyIsHQCell(r,c)) return [];` + `studySelectFrom` 的提示语覆盖（只认四角 8 座大本营，中央 9 兵站不算）。

### 中央区九宫格与 `R` 铁路通过点（2026-09-21 第三轮）

用户指正：`@中央区 修改为三横三竖9宫格，横竖交叉才有兵站`。

`BOARD_LAYOUT` 里 `R` = **铁路通过点（不可停留）**。中央 5×5（行 6-10 × 列 6-10）里只有 **9 个交叉点是 `H` 兵站**，
其余 **16 格全是 `R`**。旧渲染只处理 `.`/`C`/`H`，`R` 落进 `else` → 被当成普通行棋点画了「回」字方块
→ 中央区读起来是 25 个方块的 5×5，而不是九宫格。

**铁证**（`scan_cells_task3.js`）：全库 191 份棋谱 / 34461 步中，这 16 格作为起点/落点**次数恒为 0**
→ **真行棋点 129 = 四家各 30 + 中央 9 兵站，不是 145**。

落点 5 处（`restrict_railonly.py`，断言式 × 3 页）：
1. CSS `.cell.rail-only{background-image:none}` + `.cell.rail-only::before{display:none}`
2. 主棋盘 `buildBoardGrid`：`if (ch==='R') cls.push('rail-only');`
3. 残局棋盘 `buildStudyBoardOnce`：同上（用 `c2`）
4. `studyIsPlay`：`... && BOARD_LAYOUT[r][c] !== 'R'`（不能摆子）
5. `studyLegalTargets` 铁路分支：`if (BOARD_LAYOUT[rr][cc] === 'R') continue;` —— **可穿过、不可停留**

⚠️ **测试期望会「因这个规则而变」，那是预期后果不是回归**：
- `verify_study_rail_task3.js`：参考实现 `refRail` 要加 `STOPPABLE()` 守卫 + `run()` 的受检格改走 `STOPPABLE`。
- `verify_study_dom_task3.js`：紫师 (6,15) 落点 **48 → 42**（R 格禁停）；有向收紧后进一步 **42 → 23**（见「铁路行驶规则」节）。
  ⚠️ 2026-09-21 晚起 `verify_study_dom_task3.js` 里这些数字断的是 **`.study-target` class 计数**（不再有红框），别再以为是「高亮格数」。
- `verify_study_task3.js`：(6,6) 工兵被四面堵住时只能吃**上/左**两邻（下/右是 R 格），已拆成两条断言。
- ⚠️ 被堵场景里往 R 格摆子是**刻意的合成场景**（`blocked` 表直接由 `studyLayout` 构造，不校验合法性），
  只为验证「被封堵时能否吃子」，不要误以为引擎允许在 R 格停子。

### 悔棋（`studyHistory` 栈）

- `studySnapshot()` 返回 `{layout(深拷贝), turn, step, last, phase}`。
- ⚠️ **`studyDoMove` 里必须在 `resolveMove(mv, studyLayout)` 之前取快照** —— `resolveMove` 会就地结算吃子/改布局，之后取就存的是「走完」的局面，悔棋退不回去。
- `studyUndo()` 弹栈恢复五个字段后 `studyBtnText(); renderStudyBoard(); studyRenderChip();`，状态栏提示「↶ 已悔棋 —— 回到第 N 步后的局面（还可悔 M 步 / 已回到最初局面）」。
- 按钮 `#btnStudyUndo` 放在 `.study-status` 行内、`.study-status .undo-btn{margin-left:auto}` 顶到最右；禁用态由 `studySyncUndoBtn()` 统一管（`(studyPhase==='play'||studyPhase==='over') && studyHistory.length > 0`）。
- ⚠️ **`studyRenderChip()` 末尾必须调 `studySyncUndoBtn()`** —— 原来该函数开头是 `if (!el) return;`，放在后面会被短路掉，按钮永远不同步。
- `studyResetPool()` / `studyStartPlay()` 都要 `studyHistory = []`（换残局/重开研究时清栈）。

### 回合推进

- 顺序 = 全局 `TURN_ORDER`（`applyOrient` 后为「上→左→下→右」逆时针）。未导入棋谱时它仍是初始值 `['绿','蓝','黄','紫']`，与 `DEFAULT_ORIENT` 一致。
- `studyStartPlay()`：要求**至少 2 枚棋子且至少 2 家有子**，起始手 = `TURN_ORDER` 里第一个有子的方。
- `studyAdvanceTurn()`：**无子的方直接跳过**；**整方无子可动（`studyHasAnyMove`，如只剩地雷/军旗）也自动让过**并在状态栏点名（不卡死）；`alive <= 1` → `studyPhase='over'`，提示「XX 方胜出，其余各家已出局」。
- ⚠️ **方位签名守卫**：`studyOrientSignature()` = 四色→方位的字符串。**换棋谱 / 换视角后 `orient` 会变**，已摆的残局里「绿子在 (2,8)」的绝对坐标就站到别人阵地上了 —— `studyOpenPanel()` 比对签名，变化则 `studyResetPool()` 清空并在状态栏说明。不做这一步会得到「子站错阵地」的诡异画面。

### 界面

- 托盘方位**跟随当前 orient**（`renderStudyTrays()` 按 `studyOrient()` 把四色分到 `.st-up/.st-left/.st-right/.st-down`），托盘标题写「上家 · 绿」，棋子按军阶降序、25 枚。
- 状态栏两个元素：`#studyTurnChip`（`.turn-chip` 样式，`摆子阶段` / `● 上家 · 绿方行棋` / `🏁 已结束`）+ `#studyMsg`（操作与拒绝提示，同时也是测试的观测点）。
- 按钮：`▶ 开始研究` ↔ `↺ 摆子`（`studyTogglePhase()`，行棋/结束态都回到摆子并保留布局）、`🗑 清空`（`studyClearAll()`）。
- ⚠️ **托盘换行必须给固定 `width` 而不是 `max-width`**：`.st-left .tray-body{width:60px}` —— 用 `max-width` 时 flex-wrap 的行内宽度会被 `.tray`（宽度 = `tray-title` 宽 + padding）压到 40px 出头，25 枚只会排成 **1 列**超长条；固定 60px 才能排成 2 列 × 13 行。
- 上/下托盘 `.tray-body{max-width:564px}`（= 棋盘宽 20+17×32），25 枚自动换行成两行。

### 视觉标记口径（2026-09-21 晚 · 坚哥两点要求）

> **需求原话**：①「棋子走棋可到位置不要额外用红框显示，去除红框」（附满屏红框的截图）；②「增加复盘回放中棋子行棋起点到终点的箭头显示」。
> **澄清后落点**（已用选项问过坚哥）：① 可落点**完全不提示**（不是改淡、不是换虚线）；② 箭头加在**残局研究**棋盘 —— 复盘回放页本来就有箭头（`renderBoard` 的 `.move-arrow` / `.path-arrow`），不用动。

| 标记 | 旧 | 现 |
|---|---|---|
| 可落点 | `.cell.study-target{box-shadow:inset 0 0 0 3px var(--highlight-from); background-color:rgba(255,77,61,.16)}`（深色主题 `#ff6b52` + 淡红底纹 → 满屏红框压住铁路） | **`.cell.study-target{}`（空规则 = 零样式）**。class 照旧打在格子上，作 `studyTargets` 的 **DOM 影子**供 `verify_study_dom_task3` / `diag_domtargets_task3` 断言引擎落点；信息改由状态条给：「可走 N 处，点击目标格落子（可落点不做视觉标记）」 |
| 上一手起点/终点 | `.cell.study-last`（蓝 2px 双框） | **停用**。改用与 `renderBoard` 同款：起点 `.highlight-from`（红框）+ `.move-arrow`（20px ➤，角度 = 真实路线**第一步**）、路径中间格 `.path-arrow`（13px / 50% 透明）、终点 `.highlight-to`（黄框） |
| 摆子阶段合法落点 | `.cell.study-hint`（琥珀 2px，129 格全亮） | **保留未动** —— 坚哥只点了「走棋可到位置」的红框；要一起去掉时改这里 |
| 选中了哪枚子 | `.cell.study-sel`（琥珀框） | 保留（标的不是可落点） |

- 箭头实现照抄 `renderBoard`：`blocked` 表由「该步**之后**的 `studyLayout`」反推 = 全盘棋子 − 终点（落点/被吃目标） + 起点，再 `movePathCells(from,to,blocked)`。⚠️ **终点格必须从 blocked 里排除**，否则「走到被吃目标所在的格」会被自己吃掉的子挡住而绕远（`probe_studypath_task3.js` 第 4 例专门验这条）。
- ⚠️ `renderStudyBoard` 的清类列表必须补 `'highlight-from','highlight-to'`，否则换步后残留上一手标记；箭头 div 随 `cells[i].innerHTML=''` 自动清掉。
- 实测（`shoot_studymarks_task3.js`）：选中紫师长 (6,15) → 引擎 23 落点 / DOM `.study-target` 23 格，样格 `box-shadow = none`；走 (6,15)→(1,10) 后 → 起点红框 + 20px ➤ `rotate(180deg)`、**8 个路径箭头**（含 `scell-6-11` / `scell-5-10` 弧线两端）、终点黄框、旧蓝框 0 个。悔棋后标记跟着回退，退回最初局面时清空。
- ⚠️ **像素分析老脚本 `analyze_shots.js` 的「红框 = 可落点」语义已过期**（新截图上红 = 上一手**起点**、琥珀 = 选中格或上一手终点、蓝恒为 0），文件头已标注；查落点请改用 `probe_studypath_task3.js`（引擎）+ `verify_study_dom_task3.js`（DOM）。

### 测试台

| 脚本 | 内容 | 期望 |
|---|---|---|
| `verify_study_task3.js` | VM 纯逻辑：摆子约束（军旗/地雷/任意位置/占位/空白区）、走法生成（公路 4 点、行营 8 点、铁路直线到 (1,10)/(15,6) 且不拐弯、**有向弧线（(6,1) 可达而 (6,15) 不可达 = 反向出弧被拒）**、工兵拐弯到 (1,7)/(1,10)、被封堵时只能吃上/左两邻（下/右是 R 格）、弧线斜向一步）、吃子口径（队友/己方/行营/挡道/跨越）、回合推进（跳过无子方、让过无子可动方、只剩一家 over、前置校验）、**悔棋（7 个场景）**、源码级结构断言（含 `studyIsPlay` 排除 `R`、`studyLegalTargets` 滤 `R`、`.cell.rail-only` 两处渲染、**`ARC_DIRS` 常量存在且 `railReachSet` 内无旧「轴线校验」**） | **125 项全过**（三页可跑，见下表后「换页跑」口径） |
| `verify_study_dom_task3.js` | 真实 Chrome：两个入口、覆盖层、**289 格 + 14 条合并直轨（总长守恒 100 格）/4 弧/64 斜线**、纯色底板 `rgb(67,87,67)`（0 层渐变）、**`rail-only` 恰 16 格且 `::before`+`background-image` 皆 none、中央 5×5 恰 9 个标记格**、四托盘各 25 枚且方位正确、点选后的落点 class 计数（**2026-09-21 晚起不做视觉标记，只留 `.study-target` 影子**）、落子/取回、军旗与地雷越界被拒（提示点名「大本营」「第 5、6 线」）、开始研究、4 个落点、走子后步数与轮次、「上一手起点→终点」标记（**起点红/终点黄框 + `.move-arrow` 角度 −90°/180° + 8 个 `.path-arrow` 压在弧线两端；悔棋后跟着回退、退回最初局面清空**）、非当前方被拒、**铁路行驶（有向弧线转向：紫师 (6,15) 恰 23 格；(1,10) 在、(15,10) 不在）与悔棋**、深色主题、关闭、导入棋谱后托盘方位跟随 orient 且布局被清空、零 pageerror | **77 项全过**（产出 `out_study_setup/play/dark/oriented/railturn/undo_task3.png`） |
| `verify_study_rail_task3.js` | **逐格全枚举差分**：对全盘每个**可停留**铁路格，用页面 `studyLegalTargets` 与参考实现（**有向严格模型**）各算一遍可达集，逐格比对；开头先做「页面 `ARC_DIRS` vs 独立几何复算」核对并打印 8 个端点的 depart/arrive；外加 12 条专项断言（直行 / 恰一段弧线 / 弧线有向、工兵对照）。⚠️ 参考实现必须带 `STOPPABLE()` 守卫（R 格可穿过、不可停留） | **292 个受检位置零差分 + 12/12 专项** |
| `verify_railturn_task3.js` | 全库语料拟合 R0~**R6** 七个候选规则（只评「至少一个方向跨 ≥2 格」的 15203 步），含铁路格路口类型表、工兵/非工兵分桶的拐弯点统计、`ARC_DIRS` 复算打印。**R6 = 页面现行有向模型** | **R0 报 2351 违规；R1~R6 零违规** |
| `verify_arc_strict_task3.js` | 判决性证据：用「严格有向模型」vs「旧宽松模型（只看轴线）」给全库 15203 步多格走法分类 | 非工兵 13618 = 直线 10366 + 弧线·严格 3252；**弧线·仅宽松 0 / ★其它 0** ⇒ 从不掉头 |
| `verify_railstrict_task3.js` | 等价性交叉验证：页面 `ARC_DIRS` vs 独立几何复算；页面 `railReachSet` vs 严格模型（空盘 73 个铁路起点）；旧宽松模型多给多少格 | **8 端点全一致 / 73 起点零差异 / 宽松多给 1140 格** |
| `probe_userboard_task3.js` | 原样复刻坚哥截图局面（绿师长(6,1)/绿工兵(6,6)/黄军长(8,1)/紫旅长(8,15)/蓝连长(10,1)/蓝司令(15,6)），逐子打印落点表 ASCII | 紫旅长 (8,15) **8 格 = 5 条线路** ✓；蓝连长 34→**20**、蓝司令 24→**17** |
| `probe_study_targetcount_task3.js` | 改口径后**重测**写死在 DOM 测试里的「落点 N 格」期望值（列清单 + 个数 + ASCII 图） | 紫师 (6,15) → **23**（含 (1,10)、不含 (15,10)） |
| `probe_studypath_task3.js` | 残局研究「上一手」标记三要素：`movePathCells(from,to,blocked)` 中间格序列 + 起点箭头角度 + 每格轨迹箭头角度。4 个用例：相邻北/东行（0 中间格、角度 −90°/0）、跨家弧线（**8 中间格、起点 180°、弧线段 −135°**）、终点格占位（吃子场景，结果必须与上一条完全一致） | 与 `verify_study_dom_task3.js` 的箭头断言互为对拍 |
| `shoot_studymarks_task3.js` | 实拍 + 计算样式核对：① 选中紫师 (6,15) → 落点 23 但 `box-shadow = none`（无红框）② 走 (6,15)→(1,10) → 起点红框 + 20px ➤ / 8 个 `.path-arrow` / 终点黄框 / 蓝框 0 ③ 摆子阶段 `study-hint` 仍 129 格 | `shot_studymarks_nohint/arrow/setup.png`，零 pageerror。支持 `HTML=` 换页 + `SHOT_SUFFIX=_portindex` 加文件名后缀（跑移植页时避免覆盖 task3 实拍） |
| `probe_study_boardstate_task3.js` | **全库 191 份 / 34461 步在真实棋盘状态下的走法认可率**（每条真实走法都用残局研究的 `studyLegalTargets` 复算一遍） | **认不出 = 0**（多格 0）；支持 `ENGINE=` 换引擎 |
| `diag_arcs_task3.js` | 统计非工兵拐弯走法用了几段弧线 | **1 段 3252 / ≥2 段 0** |
| `scan_cells_task3.js` | 全库 191 份 / 34461 步统计**每个格**作为起点/落点的出现次数 | **中央 5×5 里除 9 个交叉点外的 16 格出现次数恒为 0**（R 格不是行棋点的铁证） |
| `diag_rcells_task3.js` | 导出 `BOARD_LAYOUT` 全图 + R 格清单 + 各字符计数 | `.{144 / P92 / H17 / C20 / R16}`；旧 `studyIsPlay` 145 → 新 129 |
| `diag_keycheck_task3.js` | 对比「min/max 各自取坐标」与「端点对」两种去重 key 的计数 | 本布局下**都是 64**，但前者语义脆弱（丢方向） |
| `probe_rcell_effect_task3.js` | R 格规则的影响探针：(6,6) 各邻的 `isRailway`/`railLinked`/`studyIsPlay`、被堵时的落点集、(6,15) 紫师落点数 | 被封堵只吃 (5,6)/(6,5)；紫师 **42**（⚠️ 有向收紧后为 23，期望数请用 `probe_study_targetcount_task3.js` 重测） |
| `diag_domtargets_task3.js` | DOM 侧对拍：选中每枚子后把 `.study-target` 的格子 id 全列出来，与引擎落点清单比 | 与引擎**逐格一致**（2026-09-21 晚起这些格子已无任何样式，纯 class） |
| `analyze_shots.js` | ⚠️ **已过期**：像素分析从截图里提取「红=可落点 / 琥珀=选中 / 蓝=上一手」的坐标 —— 2026-09-21 晚口径变了（红 = 上一手**起点**、蓝恒 0），文件头有警示；查落点请用 `probe_studypath_task3.js` + `verify_study_dom_task3.js` | 只对旧截图有效 |
| `add_study_module.py` | **残局研究三页移植**：从 `index_task3.html` 抽 6 个块，按「整行锚点」插入 `index_task2.html` / `index.html`（A~D 插在其后、E/F 插在其前；锚点 `count==1` 断言 + 花括号守恒 + 7 项关键要素抽查） | 两页各 +721 行、**纯插入 0 删除**；task2 与 task3 diff **0 hunk** |
| `sync_visual_task3.py` | 同步 3 处非残局研究的视觉差异：浅色/深色分区底色 8 个变量 `.11→.17` + `.board-svg{}` 后 6 行铁路重绘注释 | 三页分区底色一致，`index_task2.html` 与 task3 diff 归零 |
| `extract_engine_task3.py` | 从**任意页面**抽最长 `<script>` 块 → `engine_*.js`。命名：`index.html → engine_index.js`、`index_taskN.html → engine_taskN.js`；**无参数 = `index_task3.html → engine_task3.js`**（向后兼容）；`OUT=` 可覆盖 | `engine_task2.js` 与 `engine_task3.js` **md5 完全相同**（残局研究部分同源） |
| `restrict_railonly.py` | 断言式迁移：R 格 5 处改动 × 3 页（`count==1` 才落盘） | 备份 `*.bak_pre_railonly_20260921` |
| `restyle_board_v2.py` | 棋盘 v2 改版：8 组替换 × 3 页（支持 `ONLY=` 限定单页 / `--apply`） | 备份 `*.bak_pre_boardstyle_20260921` / `*.bak_pre_boardsolid_20260921` |
| `revert_diag_camponly.py` | 把斜线从「铺满阵地」回退成「只从行营引出」+ 修去重 key 方向 bug | `diag = 64` |
| `fix_board_comment.py` | 修正 `:root` 里「棋盘配色」注释块（旧值写着迷彩 / 42.5% / 周期 75%） | 三页各命中 1 |
| `check_js_blocks.py` | 抽取三页全部 `<script>` 块（**跳过 `ld+json`/`application/json`**）逐个 `node --check` | 三页均「JS 块 3 个 / 语法错误 0」 |
| `measure_board_task3.js` | 抓「残局研究」空棋盘（无棋子干扰）并做像素剖面，与原图实测值对表。`CLIP="c0,r0,cw,rh"`（单位=格）、`ZOOM=`（= `deviceScaleFactor`）、`HTML=` 换页 | 与原图逐项吻合 |
| `shoot_boardstyle_task3.js` | 三页棋盘实拍 + 探针（`HTML=`/`TAG=` 共用一套）。**标记计数按类名**（不是「伪元素可见」），另报 R 格可见性不变量 | `普通点 92 / 行营 20 / 大本营 8 / 兵站 9 / R 16 → 真行棋点 129`、`14` 合并直轨 / `4` 弧 / `64` 斜线、R 格带标记 0 / 带公路线 0、零 pageerror |

**「换页跑」通用口径**（残局研究三页共用同一套测试，2026-09-21 晚起）：

- 抽引擎：`python3 extract_engine_task3.py index.html` → `engine_index.js`；`index_task2.html` → `engine_task2.js`。
- VM / 差分：`ENGINE=engine_index.js node verify_study_task3.js`；`ENGINE=engine_task2.js node verify_study_rail_task3.js`。
- DOM / 实拍：`HTML=../../index.html node verify_study_dom_task3.js`；`HTML=../../index.html SHOT_SUFFIX=_portindex node shoot_studymarks_task3.js`。
- 全库状态：`ENGINE=engine_index.js node probe_study_boardstate_task3.js`。
- ⚠️ 脚本里的**页面源码级断言已参数化**（`verify_study_task3.js` 用 `PAGE_FILE`、`verify_study_dom_task3.js` 用 `PAGE`），缺省仍指 `index_task3.html`，所以老命令行为不变。

⚠️ **`verify_moverule_task3.js` 的「斜 1 格」分类口径**：该分类按**起终点几何斜跨**归类，**不等于**棋盘上真有斜线。工兵在铁路上可任意拐弯，会有「几何斜跨、实际路径是两正交格」的走法（全库 2 例：黄工兵 `J6→K6→K7`、绿工兵 `J12→K12→K11`，K6/K12 是两格的共同铁路邻居）。
排除逻辑**必须放在兜底分支**（先判行营米字 → 再判九宫弧线 → 最后才查工兵铁路可达）：前置会把工兵走弧线的 13 步也吞进来，破坏「米字/弧线」两个类目的原有口径。修正后 `斜 1 格 8080 = 米字 7307 + 弧线 771 + 工兵 L 形 2`，`⚠️ 两者都不是 = 0`。

⚠️ **写测试时踩到的三个「以为是 bug 其实是测试错」**：
1. **铁路成环 ⇒ 「必经格被堵就过不去」不成立**：工兵在 (6,6) 放一枚敌子堵 (6,5)，仍然可以 `列6↑→行1→列10↓→行10→列1↑` 绕到 (6,1)。断言要么测「绕行可达」，要么把四正邻居全堵死再断言不可达。
2. **棋盘字符集**：`BOARD_LAYOUT` 只有 `.{P,C,H,R}`（`#` 是文档 ASCII 图里的铁路符号，**不在** LAYOUT 里）。上家阵地 `(2,8)='P'`、`(2,7)/(2,9)/(3,8)='C'`（行营）；`(0,7)/(0,9)='H'` 才是大本营，`(0,8)` 是 `'P'`（不是大本营）。
3. **走完一步后「当前方」可能已经换人**：绿走完 → 蓝无子 → 轮到黄，此时点黄子是正确的来源选择；要测「点非当前方被拒」得点**绿**子。
4. **别把「孤例」当规则漏洞**：`verify_moverule_task3.js` 报「斜 1 格·既非行营米字也非弧线」2 例（都是工兵）时，第一反应不是去补一条「工兵可斜走一步」的规则，而是**用 `railReachSet(...,true)` 验证终点在可达集内** —— 在，就说明是分类器口径问题（工兵 L 形），不是规则缺失。**先做可达性探针，再决定改不改引擎。**
5. **别在注释里写会被源码断言误命中的代码串**：`ok(!/railArcLinked\(r,c,ar,ac\)/.test(src))` 这类「确认旧实现已删干净」的断言，若注释里也写了该字符串就会失败 —— 改用 `bodyOf('studyLegalTargets')` 只对函数体断言。

## 20. 实战桥三功能升级（平台 / 视角 / 导入 / 走法合法化，2026-09-25）

坚哥原文三条：① 桥支持 **联众 / QQ** 两平台（两平台棋子颜色不同；联众**顺时针**行棋、QQ**逆时针**），
**己方固定在棋盘下方**、己方可选颜色、其余三家按平台配色对应；② 增加**己方导入布局**，格式对齐
`junqiwang.cn/bj.html`（联众 JQS 6×5）；③ **棋子走棋路径需合法化**。

### 20.1 平台 = 色环 + 相位（本轮的关键抽象）

平台**只固定「绕桌一圈的颜色顺序」**；**谁坐哪（相位）由「我选哪个颜色」决定** —— 选颜色就是选相位。

| 平台 | 色环（读向） | `seats`（颜色 → 方位） | 行棋序 |
|---|---|---|---|
| 联众 | `蓝→灰→红→绿`（**顺时针**读） | `{蓝:up, 红:down, 绿:left, 灰:right}` | **顺时针** |
| QQ | `绿→蓝→黄→紫`（**逆时针**读） | `{绿:up, 黄:down, 蓝:left, 紫:right}` | **逆时针** |

⚠️ 别把 `seats` 当平台常量硬编 —— 它是「色环相位 + 我选的色」的函数，**换色即换座位**。
配色表由后端 `/api/new` 返回（`platforms`），前端 `selColor` 选项由它驱动，避免两处色表漂移。

### 20.2 视角旋转 = 坐标映射，**不转底板**（本轮核心决定）

**动手前先测量几何是否旋转不变** —— 结论是 **是**：`BOARD_LAYOUT` 的 17×17 子阵（第 18 列恒 `.`）、
`RAIL_LINES` 14 段端点集合、`RAIL_ARCS` 4 段，在 90°/180°/270° 下**逐位不变** ⇒ **转底板等于白转**。

⇒ 方案：**底板与铁路坐标一律不动，只映射「棋子 → 屏幕格」与「标头轴」**。

```javascript
var VIEW = {
  down : {f:(r,c)=>[r,c],      rowLab:'letter', colLab:'num',    rowRev:false, colRev:false},
  up   : {f:(r,c)=>[16-r,16-c],rowLab:'letter', colLab:'num',    rowRev:true,  colRev:true},
  left : {f:(r,c)=>[16-c,r],   rowLab:'num',    colLab:'letter', rowRev:true,  colRev:false},
  right: {f:(r,c)=>[c,16-r],   rowLab:'num',    colLab:'letter', rowRev:false, colRev:true}
};
```
`down:(r,c)` · `up:(16-r,16-c)` · `left:(16-c,r)` · `right:(c,16-r)`（与后端 `view_of` 逐位一致）。
`rowRev/colRev` 决定标头是否倒序，`rowLab/colLab` 决定该轴取**字母**还是**数字**。

**为什么不能用 CSS `transform: rotate()`**：① 几何旋转不变 ⇒ 没收益；② **90°/270° 时标头轴线必须互换**
（屏幕行 ↔ 绝对列），纯 CSS 旋转表达不了（文字会躺倒、轴线也换不了）。

⚠️⚠️ **成立前提必须写成构建期断言**：既然「不转底板」**完全依赖几何旋转不变性**，一旦有人改了
`BOARD_LAYOUT` / `RAIL_*` 破坏对称性，旋转视角会**静默错位**（不报错、只是格子错）。
⇒ `build_live_ui_20260925.py` 加 `check_symmetry(js_layout, js_rail, js_arcs)`：旋转 90/180/270 逐位比对，
`RAIL_LINES` 端点集合旋转后不变，`RAIL_ARCS` 恰 4 条，任一不满足 **构建立即失败（return 1）**。
- ⚠️ 踩坑：`BOARD_LAYOUT` 行是**字符串**，旋转后是**字符列表** ⇒ `list != str` 恒真、断言**恒失败**。
  必须先 `M = [[row[c] for c in range(N)] for row in L]`；行 0–5 / 11–16 有 **18 个字符**（第 18 列恒 `.`）也要处理。
- ⚠️ 踩坑：`RAIL_LINES` / `RAIL_ARCS` 是**单引号 JS 字面量**（非 JSON）⇒ 解析前 `replace("'", '"')` 并去 `//` 行内注释。

### 20.3 ⚠️ 单元格 id 口径变更（最容易写出「静默指错格」的 bug）

| 属性 | 含义 |
|---|---|
| `id="cell-<vr>-<vc>"` | **屏幕 / 视角坐标**（随视角变） |
| `data-r` / `data-c` | **绝对坐标**（永不随视角变） |

`S.cells` / `BOARD_LAYOUT` / `toLZ` / `FLAG_H_DIR` **全是绝对坐标**。
⇒ 「点某个**绝对坐标**的格」**必须**走页面自带的 `cellEl(r,c)`（内部做 `VIEW[S.side].f`），
**绝对不能**拼 `'#cell-'+r+'-'+c` —— 那在 `down` 视角下恰好对，其余三个视角**静默指错格**。
`buildGridOnce()` 的跳过条件从「有 `data-built`」改为「有 `data-built` **且 `data-side` 相同**」（侧别变更 = 整块重建）；
`markMove()` 的箭头方向用**视角坐标差分**算（路径本身仍在绝对坐标里算）。

### 20.4 JQS 布局导入 / 导出

- 格式 = 联众 `junqiwang.cn/bj.html` 同款：**6 行 × 5 列 = 30 格**（**行 1 = 锋线、行 6 = 端线**）。
- 行营填 `0`；`00` = 炸弹 · `30` = 军旗 · `31` = 地雷 · `32` = 工兵 · `40` = 司令（**行话码优先于两位十六进制**）。
- 兼容宽松输入：**25 格**（自动补 5 个行营）· **连写文本**（无分隔）。
- 6×5 局部 ↔ 17×17 绝对：`abs_of(side,i,j)` / `local_of(side,r,c)`，**与三页 `mapLayout` / `studyLocalOf` 逐字相同**
  （`CAMP_IDX=[6,8,12,16,18]` · `FORT_IDX=[26,28]`）。
- 校验：编制不符 ⇒ **返回可读理由**（「团长：0 枚（应 2）；排长：4 枚（应 3）…」）且**不破坏已有布阵**；军旗必须落本方大本营。
- 导出 = 从当前布阵反推 JQS，**导入 → 导出必须逐 token 相同（幂等）**。
- ⚠️ 换方位后导入：`sideColor` 变了，`abs_of` 的方位也变 ⇒ 军旗必须落在**新方位**的大本营，且在**屏幕最底行**。

### 20.5 走法合法化（需求 ③）

- **唯一算法入口 = 模块级纯函数 `legal_targets_of(board, fr, fc)`**，返回 `(side, note, [[r,c],...])`；
  `Table.legal_targets()` 只是薄壳（`return legal_targets_of(self.sess.board, fr, fc)`）。
  ⚠️ 把算法体留在 `Table` 方法里、自检再抄一份 ⇒ **两份口径 = 自检失去分辨力**。
- 新接口 `GET /api/legal?fr&fc`（合法落点集合，驱动前端高亮）；`/api/move` 默认**校验**，`force:true` 强行录入
  并计入 `overrides`。
- 前端：合法落点 `.cell.legal`（青点底纹）、`.cell.nolegal`；非法时**给出理由**、**保持高亮**（可原地改点），
  并点亮 **「仍然录入（忽略校验）」** 兜底 —— **不能把坚哥卡死**（走法模型有盲区，平台上真实发生的走法必须能录）。
- ⚠️ **`overrides` 必须随新局清零**（`new_game()` 里 `self.overrides = 0`）—— 它是「**本局**被迫绕过校验几次」的信号。
  **e2e 唯一暴露的真实缺陷**就是这个：跨局累计会让界面显示「强行 4」这种无从解释的数。

### 20.6 ⚠️⚠️ 自检 ⑩ 的假阳性：**未复刻权威重放的清盘语义**

第一版 ⑩ 在 `Table` 上「自己重实现一遍移动 + 落点过滤」，报出 **67 个「不在落点集」+ 24 个「落点不合法」**。
根因：**`replay_drive.drive()` 会处理 ① 扛旗清盘（`res=='flag'` 清掉 dside 全部棋子）② 认输（GiveUp 移除该方全部棋子）
③ 事件行与回合推进** —— 自己重实现必漏 ①②，于是从第一次扛旗/认输起**盘面与权威实现发散**，之后每步都「不合法」。

**修法（本项目通用范式）**：
1. 把算法抽成**模块级纯函数** `legal_targets_of`；
2. 给权威重放加参数 `drive(rec, want_moves=True, legal_fn=...)`，**把同一口径挂上去**：
   ```python
   legal = gen_moves(board, fr, fc)
   if (tr, tc) not in legal:      err["illegal"] += 1
   elif legal_fn is not None:     # 更严口径（排除己方 / 队友 / 行营内的子）
       _sd,_note,_tg = legal_fn(board, side, fr, fc)
       if _sd is not None and (tr,tc) not in set(map(tuple,_tg)): err["illegal_strict"] += 1
   ```
   `illegal_strict` 与 `illegal` **不重叠**（后者是「连生成器超集都没覆盖」的那类）。
3. **⑩ 必须在未经 `load_clean` 过滤的全库上统计**（`load_clean` 已滤掉 `illegal≠0` 的局，在它上面测 = **自证**），
   且**只对「零误差局」断言**。
4. 加 ⑩b 正向（把 `drive()` 的 `steps` 喂进 `Table.move()`，断言零误拒）+ ⑩c 负样本（起点=终点 / 随机非合法落点 /
   锁定子必须被拒，并断言 `locked` 非空）—— **一个恒返回 True 的校验器也能过「真实走法全过」**。

**修后结果**：全库 **2379 局 / 443179 步**，生成器口径 `illegal = 22`（0.0050%，**全落在被淘汰的 47 局内**）；
**零误差局 2332 局桥口径违规 0**；⑩b 4 局 815 笔 0 误拒；⑩c 正样本 42 笔全过 / 负样本 125 笔全拒。
⇒ 与「上一轮全库 illegal=0」**不再矛盾**（那次是宽松口径 / 已过滤集）。

### 20.7 e2e 扩展到 61 项（`bridge_e2e_20260925.js`）

新增三组（旧四条保留）：
- **A 平台 / 视角**：8 组「平台 × 颜色」断言（配色 / 行棋序 / 视角角度 / **标头换轴** / 己方在屏幕下半部）；
  四侧实拍 `bridge_view_{down,left,up,right}_{平台}{色}.png`；四侧映射自洽 + 己方棋子底色（`red`/`green`/`purple`）。
- **B 导入导出**：25 枚落位 / 兵种构成 / 军旗在大本营 / 幂等 / **换方位后军旗仍在屏幕最底行** / 非法布局被拒且不破坏现有布阵。
- **C 合法性**：高亮集合与 `/api/legal` **逐格相同** / 非法落点不被录入（round 不变）/ 给出理由 / 「仍然录入」可用 /
  被拒后高亮保持 / `force` 走 API 时 `overrides` 计数 / **正负样本各 12 笔**。

⚠️ **测试侧三个真坑**（本轮实测踩全）：
1. 期望表 **join 分隔符必须与采集一致**（标头逐格 join 用 `,`；写成 `join('')` 会拿 `WTS…` 比 `W,T,S…`）；
2. 「**再点同一格 = 取消选择**」会让复用上次选中态的用例失效 ⇒ 该用例开头先 `Escape` 清场；
3. 用例**故意**打的 400 会在浏览器控制台记 `Failed to load resource` ⇒ 必须单列 `softErrs`，
   否则「测试制造的错误把测试自己判失败」。

⚠️ e2e 的 `--out` 默认必须是**项目根**（`path.resolve(__dirname,'..','..')`），写错一层 ⇒ 文档生成器找不到配图并**静默跳过**。

### 20.8 交付前必跑（桥，更新版）

```
python3 live_bridge_server_20260925.py --selftest    # 11 项（①~⑪，含全库合法性 + 正负样本 + 暗棋口径/军旗亮出）
python3 build_live_ui_20260925.py --check            # 切块命中数 + check_symmetry（旋转不变性）
python3 .workbuddy/tests/check_js_blocks.py 四国军棋实战桥.html
node .workbuddy/ld/bridge_e2e_20260925.js --out <项目根>   # 92 项（见 §24.12）
python3 probe_darklabel_20260925.py                  # 改暗棋标识/军旗链路时必跑（6 项计数全 0）
python3 build_bridge_doc_20260925.py                 # 使用说明（截图内嵌 base64）
node .workbuddy/tests/shoot_report.js 四国军棋实战桥_使用说明_20260925.html --strict --need "a,b,c" --sections "x,y"
```
⚠️ `shoot_report.js` 的 `--need` / `--sections` 是**逗号分隔**（写成 `a|b|c` 会被当成**一个字面关键词**，
报「关键内容缺失」+「未找到节标题」—— 本轮实测踩到）。

### 20.9 ⚠️⚠️ 真 bug：CSS **被注入两遍** ⇒ 暗棋的平台配色被明牌渐变压掉

**症状**：三家盖棋在屏幕上全是**浅色**、看起来和明牌一样，**平台配色几乎看不出来**
（只有 red 因明牌色恰好是半透明斜纹而侥幸可见）。而 e2e 第一轮 **61 项全过** ——
因为它只断言了棋子的 **class 名**（`piece back blue`），class 完全正确。

**排查路径（可复用）**：
1. 读**计算样式**：`getComputedStyle(el).backgroundColor` + `.backgroundImage`。
   实测：暗棋 `bgc=rgb(43,74,99)`（**正确的深色**！）但 `bgi=linear-gradient(#eef6fc,#d3e6f3)`
   （**明牌的浅色渐变**）⇒ 深色被不透明渐变**盖住**。
2. 定位「谁在压它」⇒ 在**生成物**里 grep `^\.piece`：`.piece.green/.yellow/.blue/.purple`
   出现了**两次**，第二份在 `.piece.back*` **之后**。同特异度（都是 0,2,0）⇒ **源序决胜**，后者胜。
3. 追到生成器：**一条 CSS 注释里写了占位符的完整名字**，而替换是无界的 `tpl.replace(k, v)`
   ⇒ 整块棋盘 CSS **被注入了两遍**。第二份落在注释里，但注入内容自带 `/*…*/`，
   第一个 `*/` 把外层注释**提前闭合** ⇒ 后半段变成**活样式**。

**修法（三处，缺一不可）**：
1. 注释里**不要写出占位符全名**（写「棋盘 CSS 占位符」即可）。
2. 把 `assert k in tpl` 升级为 **`assert tpl.count(k) == 1`** —— **存在性 ≠ 唯一性**，
   这是唯一能自动抓到它的断言。顺带加 `assert "@@" not in tpl` 与替换后 `/*` 数 == `*/` 数。
3. 加**源序断言**防回归：`assert tpl.rindex(".piece.back{") > max(tpl.rindex(s) for s in 六条明牌规则)`。
   并且真的把 `.piece.back*` 块**挪到**所有 `.piece.<色>` 之后 ——
   否则修好重复注入后，red/gray 的明牌渐变会**反过来**压掉暗棋斜纹。
   ⚠️ 教训：写这条断言时我**又在注释里写了一次占位符名**，当场被 `count == 1` 抓到 —— 性价比就是这么来的。

**e2e 必须补的断言（把「假绿」堵死）—— 读计算样式，不读 class 名**：
- 暗棋：`background-color` **非透明**、**三家两两不同**（证明平台配色真的生效）、
  `background-image` 含 `repeating-linear-gradient`（斜纹）、每色恰 25 枚
- 明牌：`background-image` 含 `linear-gradient` 且**不含** `repeating`
- **反向验证**：`page.addStyleTag()` 追加明牌渐变复现旧行为 ⇒ 断言必须**立刻判失败**
  （实测抓到「暗棋缺少斜纹层」✓）

**可推广结论**：`X in s` 形式的断言只能证明「有」，证明不了「只有一份」——
**任何注入 / 模板替换都必须断言次数**。而「class 名对」也不等于「渲染对」，
**视觉需求必须断言计算样式**。两条都是本项目「不做反向验证的检查都是假绿」的延伸。

---

## 23. 实战桥 · 六项实战调整（2026-09-25 第二轮）

坚哥用了一轮实战后的六条反馈（逐字见下），全部落地。**e2e 61 → 75 项 · 后端自检 10 → 11 项**。

> 1. 盖牌棋子碰撞盖牌棋子后，剩下的盖牌棋子不要显示兵种标识，因为都是乱显示。
> 2. 盖牌棋子碰我方棋子后，如盖牌棋子存活，则显示该盖牌棋子的标识为比我方阵亡棋子高一级的兵种。
> 3. 棋子碰撞后果除攻方吃子再加两个选项分别是（司令同归于尽）（司令被炸身亡）。
> 4. 所有玩家司令阵亡后要自动显示军旗。
> 5. 棋子碰撞同行棋一样用左键，显示「这一步的结果」选项。
> 6. 轮到己方走棋，AI 直接在棋盘上给出行棋建议，不需要点击「求AI建议」。采纳就自动按建议行棋，不点采纳就玩家自己走棋。

### 23.1 ⚠️⚠️⚠️ 暗棋信息**三分**：唯一解进情报集、**下界只能上屏**

这是需求 ①② 的**唯一正确口径**，也是最容易做错的地方。改的是 `live_bridge_20260925.py`：

| 类别 | 判据 | 落点 | 举例 |
|---|---|---|---|
| **确切兵种** | 已摊牌 / 我方棋子 / 碰撞后公开 | 进 `info.known`（**AI 可用**） | 吃子后守方兵种公开 |
| **唯一解** | 规则上**只剩一种可能** | **进 `info.known`** | `dig` ⇒ 攻方**必**工兵、被挖的雷**必**地雷；`mine` ⇒ 守方（留在原地）**必**地雷 |
| **下界** | 「**至少**为 X」，真值可能更高 | **只上屏**（`infer_label`），**绝不进 `known`** | 盖棋撞掉我方子却存活 ⇒ 「≥ 比我方阵亡子高一级」（`rank_above`） |

- 下界进 `known` 的两个后果（都会**静默**变坏）：① `Searcher` 拿「至少为 X」当确定兵种去撞，**比不知道更糟**；
  ② 破坏 `sample_world` 的硬不变量 **`sum(pool[side]) == len(未知格数)`**（违反只累加 `info.inconsistent`）。
- 需求 ① 的「乱显示」根因 = 旧 `_guess()` 会给幸存者**随机填一个兵种**。现在**幸存者不带任何兵种字**。
- 前端：下界格加 `.piece.infer` + `.inferlab`（**橙色虚线框** + 「≥某兵种」，与摊牌实心字视觉区分）。

### 23.2 ⚠️⚠️ 池构成漂移（本轮最深的坑，`probe_darklabel` 挖出来的）

**现象**：`probe_darklabel_20260925.py` 报「池↔未知格不一致 **347**」。

**根因链**：`_guess()` 的职责只是「把池减 1」，但它**选谁扣**会污染池的**构成**。若把
**会被唯一解点名**的兵种（工兵 / 地雷 / 军旗）随机扣掉，等真需要按它们扣时池里已经空了
⇒ `_unpool` **静默失败** ⇒ 池大小 ≠ 未知格数。

**排查顺序（很反直觉，值得记）**：
1. 先只加 `feed()` 的 ⓪ 唯一解块（`dig`/`mine` 时把真值塞进 `known`）—— 不一致数**反而从 347 升到 391**
   （因为唯一解定了、但 `_guess` 照样随机扣那三类）。
2. 再加 **`GUESS_EXCLUDE = ("工兵", "地雷", "军旗")`**（军旗另有一层兜底：池里只剩军旗时也尽量不扣）—— **归零 ✅**。

**结论**：任何「池 / 计数」类不变量的修复，**不能只看大小对不对，还要看构成对不对**；
`_guess` 这类「随机扣一个」的函数必须有**禁猜集合**，且禁猜集必须覆盖**所有会被确定性规则点名的兵种**。

### 23.3 需求 ③⑤：8 项后果菜单 + **左键触发**（附带修掉一个真 bug）

- `RES_OPTS` 6 → 8：新增 `cmdr_both`（司令同归于尽）与 `cmdr_bombed`（司令被炸身亡）；
  引擎层面都映射到原生 `both_die`，**额外价值是顺手把「该方司令已亡」记下来**（触发需求 ④）。
  自动判定「哪一侧是司令」的顺序：**先看盘面**（我方全知 / 他方已摊牌的才带兵种名）→ 再看下拉值 → 默认攻方。
- **⚠️ 需求 ⑤ 引出的真 bug**：`document` 上有一条「点别处就关菜单」的 `click` 监听，
  **无差别地在冒泡阶段**调 `closeMenu()`。左键点棋盘格时 `#boardGrid` 先开菜单，
  事件继续冒泡到 `document` 又被关掉 ⇒ **菜单一闪即没**，新功能完全不可用。
  - **旧实现走 `contextmenu`，不在 `click` 路径上 ⇒ 一直没暴露**；这也解释了为什么以前只测右键。
  - **同族受害者**：侧栏**「采纳」按钮**（`btnApply`）—— 采纳后若终点有子要弹后果菜单，同样被吃掉。
  - 修法：① `document` 的 click 监听**放过 `#ctxMenu` 与 `#boardGrid` 两个来源**；
    ② `applySuggest` 里用 `setTimeout(() => openMenu(...), 0)` 推到下一 tick。
  - **验收教训**：必须加「**真左键**」断言（并保留「右键仍等价」防回退）—— 用右键代替 = 测不到这条路径。

### 23.4 需求 ④：司令阵亡 ⇒ 军旗亮出（后端 `set_flag` / `rebuild` 逐步学旗）

- 前端把该方 2 个大本营格高亮成 **「旗?」候选**（`.flagcand` + `.flagpick` 徽章），
  **点徽章**确认（点整格是「选这枚棋当起点」，两者不冲突）。
- 后端 `Table.flags`（`side -> (r,c)`）+ `set_flag(side,r,c)` 双重校验：
  **只在本方大本营格**（`is_hq`）**且该方司令已阵亡**，否则拒绝。
- `rebuild()`（撤销/重放）里**逐步**补学旗：每 feed 一笔后，对每个「已知旗位但尚未学进 `InfoSet`」的方
  调 `learn_flag(d, *self.flags[d])`。**旗位不动**（棋子不能挪旗），所以只需补一次。
- ⚠️ **这是纯信息增益、不是泄漏**：喂进 `flag_of` 只在 `cmdr_dead[side]` 为真时生效
  （搜索的递旗逼近项与采样器的亮旗钉死都带这个前置）。
- ⚠️ **司令阵亡判定必须用解析后的兵种**（`a_true` / `d_true`），不能用入参（入参可能是 `None`）。

### 23.5 需求 ⑥：轮到己方**自动**给建议

- `askSuggest(auto)` 加参数 + `U.sugBusy` 闩；`maybeAutoSuggest()` 在 `absorb()` 末尾调用，
  **去重键 `(round, next)`** ⇒ 同一手不反复打后端。
- 「采纳」= `applySuggest()`；不点就自己走（玩家走法直接覆盖建议）。

### 23.6 ⚠️⚠️ 测试层两条「假绿」教训（本轮）

1. **判据本身没有分辨力**：验证「自动建议」时第一版判「棋盘上出现 `highlight-to` / `move-arrow` 元素」
   ⇒ **假绿**，因为**上一手标记用的正是同一组 class**，不点按钮也一直存在。
   改成只认页面自己的状态位 **`U.sug.auto === true` 且建议框可见**。
2. **绕过页面状态机**：直接用裸 `fetch` 推进回合 ⇒ **不经过页面的 `absorb`** ⇒ 页面状态陈旧
   （`maybeAutoSuggest` 不触发、`S.round` 串位连带后续「撤销」断言失败）。
   修法：推进后**显式** `const stNow = await fetch('/api/state'); absorb(stNow);`。
3. 另一条老坑复现：e2e 用例录一步会改 `S.cells` ⇒ **开局抓的 `opp`/`mine` 到第二步就失效**，
   必须**每小节重新 `snap()` 取盘面**。

### 23.7 交付前必跑（本轮）

```
python3 live_bridge_server_20260925.py --selftest   # 11 项（新增 ⑪ 暗棋口径 + 军旗亮出，含负样本）
python3 probe_darklabel_20260925.py                 # 6 项计数必须全 0（尤其「池↔未知格不一致」）
node .workbuddy/ld/bridge_e2e_20260925.js --out <项目根>   # 92 项（读屏段见 §24）
```

---

## 24. 实战桥 · 屏幕自动实读（Phase 7 第三轮，2026-09-25）

**需求原文（坚哥）**：
> 实战桥点击开战后，自动读取电脑屏幕上玩家在平台上的棋盘信息，包括棋子颜色及棋子行棋，碰撞等信息，
> 并实时在实战桥棋盘页面体现，己方玩家走棋时自动给出建议，由玩家确定是不是采纳。

四个已确认的决策：运行机器 = **Windows 便携包** · 平台 = **联众 + QQ 两个都要** ·
棋盘标定 = **自动检测棋盘底板** · 兵种身份 = **只推唯一解，其余留空**。

### 24.1 文件清单（4 个新模块 + 2 处改造）

| 文件 | 作用 | 自测 |
|---|---|---|
| `screen_capture_20260925.py`（新） | 跨平台取图，**零第三方依赖**。`Frame`/`encode_png`/`downscale`/`grab()` | **8/8** |
| `board_detect_20260925.py`（新） | 棋盘自动定位 + 四色自学。`Calib`/`find_backdrop`/`find_blobs`/`fit_grid`/`learn_palette`/`read_cells`/`auto_detect` | **13/13** |
| `move_infer_20260925.py`（新） | 帧间差异 → 走棋 / 碰撞推断。`assign_sides`/`diff_grids`/`infer` | **13/13** |
| `live_read_20260925.py`（新） | 会话：`calibrate`/`adjust`/`preview`/`read`/`poll`/`take_pending`/`reset_baseline` | 真机 **6/6** |
| `live_bridge_server_20260925.py`（改） | 软引用 `live_read` + `POST /api/vision/<act>` + `GET /api/vision/state` | — |
| `build_live_ui_20260925.py`（改） | 前端新增「③ 屏幕自动实读」面板（CSS + HTML + JS + 挂接） | — |

辅助：`verify_liveread_20260925.py`（真机链路 6/6）· `diag_liveread_20260925.py`（抓一屏存盘后离线反复分析，
`--use-cached` 跳过抓屏）。**API 动作表**（POST）：`calib` / `adjust` / `preview` / `start` / `stop` /
`realign` / `poll` / `apply` / `ignore` / `clear`。

### 24.2 ⚠️ 零第三方依赖是硬约束（决定了整个取图方案）

便携包里是 **embed 版 Python（无 pip）** ⇒ 装不了 PIL / mss / pyautogui。取图只能走系统自带能力：
macOS `/usr/sbin/screencapture`、Windows `user32/gdi32` 的 `BitBlt`+`GetDIBits`（ctypes）。
这同时解决了性能问题 —— 起 PowerShell 子进程每帧 200~400 ms 且**闪黑框**，ctypes BitBlt 只要几毫秒。

**稀疏读 BMP（关键优化）**：棋盘只需 17×17 个采样点 × 3×3 像素 < 1 KB，而 BMP 行在文件里连续 ⇒
**seek 到目标行只读几十字节**。实测 1600×1600（10.2 MB）整图 vs 稀疏读 ≈12 KB（约 850×）。

### 24.3 ⚠️⚠️ 两套坐标口径（混了就全错）

| 口径 | 用在哪 |
|---|---|
| **逻辑点** | `screencapture -R` 入参、浏览器 `clientX/Y`、CSS 像素 |
| **物理像素** | BMP 真实行列 |

Retina = 逻辑 ×2。实测：主屏 3840×2560 物理 / 1920×1280 逻辑，`-R 100,100,200,100` → 得到 **400×200 物理**、
**top-down 32bpp BMP**（高度为负）。`grab(x,y,w,h)` 统一收**物理**坐标，macOS 侧内部再换算成逻辑点。

**Windows DPI 感知必须开**：`SetProcessDpiAwareness(2)`，否则 125%/150% 缩放的屏上 `GetDC` 给逻辑坐标，
抓的区域系统性偏移（症状：**标定时对得上、跑起来越走越偏**）。

### 24.4 ⚠️⚠️⚠️ 最深的坑：`round()` 银行家舍入把**正确结果**判成失败

`_fit_axis` 的残差度量最初写成 `d = abs((v-org)/cw - round((v-org)/cw)) * cw`。
而格心恰在 `origin + (k+0.5)·cw` ⇒ `(v-org)/cw` 落在**半整数**上，Python 的 `round()` 对 `.5` 走银行家舍入：
`round(0.5)=0`、`round(1.5)=2`、`round(2.5)=2` ⇒ **每一个完全对齐的格心都被算成 0.5 格误差**，
残差恒等于 `0.49·cw`。实测代价：`cw`/`origin` 全对（52.03/209.3 vs 真值 52/210），
却因「残差 25.6 px 过大」把正确网格判成失败。修法：

```python
u = (v - org) / cw - 0.5      # ⚠️ 必须先减 0.5 再取整
d = abs(u - round(u)) * cw
```

### 24.5 棋盘定位：三步法（试错过的两条死路也记下来）

① 找底板（棋盘底板是一整块纯色，量化直方图按**占比 + 方形度 + 填充率**打分）；
② `find_blobs`（非底板掩码 → 8 邻接连通域）；③ `fit_grid`（用棋子质心做一维周期相位估计）。

**两条死路（别再走）**：
- ❌ **直接优化网格参数**：试过两个自监督目标都无分辨力 —— `vividness` 峰值**不在真值**（把 cell=52 推到 61.7）、
  `contrast` 在真值处取**最小值**（有退化解）。根因：都在**直接猜参数**，参数空间存在大量伪最优。
- ❌ **一维行/列投影找底板**：假定同色像素只集中一处。真机全屏里底板色散布在 **3504×2412（屏面 87%）**，
  投影法给出的 bbox 完全没意义。也试过「投影里最长连续区间」——棋盘的列投影在棋子密集处会掉到阈值以下
  （**一枚子吃掉该列约 1/8 底板采样点**），把 884 px 棋盘截成 150 px。
  ✅ 最终：**二维连通域**（`_dilate_sep` 4 邻域膨胀 + `_largest_comp` 最大 8 邻接连通域）+ 取**最外侧**跨度 `_outer_span`。

**周期估计也必须换口径**：「到最近格心的均方残差」天然偏好**更小周期**（实测把真值 38 拉到 30.5、52 拉到 41.8）。
✅ 正确做法：**先用相邻簇心差锁定周期 `cw`**，再用**圆均值**定 `origin`。

其它两条判据：
- **`step` 自适应**：`step = int(round(min(10.0, max(4.0, cell_guess/8.0))))`。真机 cell≈96 时若自适应到 23，
  团块面积只有理论值一半 ⇒ `pick_piece_blobs` 的面积判据必须用**相对中位数**，不能用理论圆盘面积
  （`px_area = 采样点数 × step²`）。
- **方形性检查**：`abs(cw-ch) > 0.07*max` 直接拒绝。棋盘必然方形，这条能拦掉「底板被遮挡/杂色干扰导致 bbox 拉长」。

### 24.6 ⚠️ 颜色 → 方位必须**枚举 24 种双射**

不能逐轴比较 `|dx|>|dy|`。实录：四个质心 `(1,2.5)(15,2.5)(1,15)(15,15)` 被逐轴判成
`left/right/left/right`（两方位空着、两方位撞车）。
✅ `assign_sides` 用 `itertools.permutations` 取总代价最小，返回 `(映射, 诊断)`，诊断含 `reliable`。
⚠️ 合成器里布阵区必须是**真实形状**：up = 行0-5列6-10 / down = 行11-16列6-10 / left = 行6-10列0-5 /
right = 行6-10列11-16（**四条边的中段，不是四角**）；`SIDE_ANCHOR`（centroid 用，(x=列,y=行)）=
up(8.0,2.5) / down(8.0,13.5) / left(2.5,8.0) / right(13.5,8.0)。

### 24.7 推断：屏幕上**天然区分不了**的那些情形

- `mine` / `dig` 的一般情形与「攻方被吃」「工兵挖雷」**视觉完全同形**（攻方消失、守方不动）⇒ **只能留空**，
  给一个默认结果由玩家在卡片里改。**这不是算法不够好，是信息不在屏幕上。**
- **唯一解可判**（进 `pending` 一步的 `atk`/`dfd`）：己方地雷被撞（己方兵种已知）、己方工兵存活进占
  （工兵碰非雷子必亡）。判据直接看**这一格在不在 `own_pieces` 里**（`_maybe_unique_kind`）。
- ⚠️ **「攻方阵亡」的目标格在 diff 里根本不出现**（守方原地没动）⇒ 必须靠**走法合法性**反推碰撞点，
  且必须复用 `legal_targets_of` **同一算法入口**（另写一份 = 两套口径，合法步会被自己判非法）。
  反推出多个候选时 `conf='low'` + `ambiguous=True` + `tr=None`，前端卡片显示「目标格没定下来」并禁用「确认录入」。
- **四情形**：普通移动 / 吃子 · 攻方阵亡 · 同归于尽 · 扛旗清盘（某色 ≥8 子 → 0 子）· 漏帧。

### 24.8 前后端契约（前端只做「展示 + 人在回路」）

```
标定  POST /api/vision/calib    → {ok, calib, diag, sides, preview}
微调  POST /api/vision/adjust   {dl, dt, ds}     位移按**格**、缩放按**比例**
监控  POST /api/vision/start    → 后端自己从 TABLE.side / TABLE.my_pieces 取己方方位与布阵，不让玩家再填
轮询  POST /api/vision/poll     → {ok, changed, steps[], note, ambiguous, settling, ms, reader}
确认  POST /api/vision/apply    {fr,fc,tr,tc,res,atk,dfd}   ⚠️ 前端送**改过的**坐标，服务端不直接吃 pending
忽略  POST /api/vision/ignore · 重对齐 POST /api/vision/realign · 清零 POST /api/vision/clear
读    GET  /api/vision/state   → {available, error, calibrated, calib, watching, n_poll, n_change, n_apply, last_ms, own_side}
```

前端 JS（`build_live_ui_20260925.py` 模板内）：`apiV` / `vInfo` / `vBar` / `vSwatches` / `vShowPreview` /
`vDrawGrid` / `visionCalib` / `visionAdjust` / `visionPreview` / `visionStart` / `visionStop` / `visionRealign` /
`visionPoll` / `vRenderPend` / `vApply` / `vIgnore`。状态位 `U.{vcal,vrun,vqueue,vbusy,vtimer,vpick,vgrid,vown,vavail}`。

### 24.9 ⚠️⚠️ 本轮两个真 bug（e2e 抓出来的）

1. **`apiV('/api/vision/state', {})` 被当成 POST** —— `apiV` 用 `body ? 'POST' : 'GET'` 判方法，
   而**空对象 `{}` 在 JS 里是真值** ⇒ 打到只认 GET 的路由上，后端回
   `404 未知的读屏操作: state` ⇒ 前端「以为本机不支持读屏」把标定按钮**永久禁用**。
   **凡是「读」接口都不要传第二个参数。**
2. **`vBar()` 里的自引用可用性判断** —— 曾写成 `var av = (el('btnVCalib').disabled === false) || U.vcal`：
   一旦某次 `renderPanel()` 先把它置成 disabled，后续再也回不到可用 ⇒
   「对局阶段标定按钮永远灰着」而且看不出原因。修法：可用性只认 `U.vavail`（boot 里那次探测的唯一落点）。

### 24.10 ⚠️ 三条使用须知（不满足就会「标定失败」或「读不到」）

1. **平台棋盘窗口必须完整可见、不被任何窗口遮挡** —— 被盖住的部分读出来是那块窗口的颜色，
   会被当成「棋盘没了」。这是**真实使用中最常见的失败原因**（`verify_liveread` 里必须用
   `osascript` 把 Preview 摆到左上并 activate，否则检测失败）。
2. **尽量窗口化运行平台客户端，不要全屏独占** —— Windows 全屏独占画面无法用 BitBlt 抓取，会抓到黑屏。
3. **实战桥这页要保持在前台可见** —— Chrome 对**后台标签**会把 `setInterval` 节流到 1 次/分钟，
   那时识别会明显变慢甚至停住。所以「标定→监控→待确认→确认」的轮询间隔定 **1200 ms**，
   并在面板上把这条写清楚，否则玩家会以为识别坏了。

### 24.11 测试台

```
python3 screen_capture_20260925.py       # 8/8
python3 board_detect_20260925.py         # 16/16（3 种格子尺寸 × 4 种「平台配色×底板」+ QQ 色块路 2 例 + 2 个负样本）
python3 move_infer_20260925.py           # 13/13
python3 verify_liveread_20260925.py      # 6/6 真机链路（真 screencapture → BMP → 连通域 → 周期拟合 → 读格 → 方位）
node .workbuddy/ld/bridge_e2e_20260925.js --out <项目根>   # 92 项（D5 段 = 读屏 20 项）
```

⚠️ `verify_liveread` **不断言绝对格宽**（窗口会按自己的规则缩放），只断言本质：方、格子数、逐格正确率。
实测：格宽 75.86×76.09（预期 38×2=76，误差 0.2%）、棋子数 100 = 真值、**逐格正确率 100%**、四色→四方位 `max_offset=0.1`。

⚠️ **e2e 的 D5 段「人在回路闭环」故意不依赖真实屏幕**：把 `U.vqueue` 注入成「poll 刚推过来的样子」，
再用**真点击**走「改起点 / 改终点 / 确认录入 / 忽略」。理由是「本机桌面有没有平台棋盘」是**环境变量**，
拿它当断言会把测试变成看运气。真正要守的是**契约**：标定成功 ⇒ 必须给预览 + 网格 + 可微调 + 可开始监控；
标定失败 ⇒ 必须给**可读原因**（绝不能静默成功 / 静默失败）；未监控时 poll 必须明说「未在监控」；未知动作必须 404。
⚠️ D5 开头必须 `POST /api/vision/stop` + `clearInterval(U.vtimer)` ——
否则万一 `watching` 留成 true，后台轮询会在**注入队列的同时**往里塞新步，断言随机失败（最典型的 flaky 来源）。

### 24.12 交付前必跑（读屏）

```
python3 live_bridge_server_20260925.py --selftest
python3 probe_darklabel_20260925.py
python3 board_detect_20260925.py && python3 move_infer_20260925.py && python3 screen_capture_20260925.py
python3 verify_liveread_20260925.py
python3 build_live_ui_20260925.py --check && python3 build_live_ui_20260925.py
python3 .workbuddy/tests/check_js_blocks.py 四国军棋实战桥.html
node .workbuddy/ld/bridge_e2e_20260925.js --out <项目根>
# 改了桥的代码 ⇒ 必须重出便携包（白名单要带上 4 个读屏模块）
python3 make_bridge_portable_20260925.py --with-python python-3.11.9-embed-amd64.zip
python3 smoke_portable_20260925.py
```

### 24.13 ⚠️⚠️⚠️ 直方图桶的**代表色**必须取桶心，不能取桶下沿（2026-09-26 修）

**症状**：`verify_liveread` 从 6/6 掉到 **3 过 / 3 败** —— 读到的棋子数 75（真值 100）、
逐格正确率 91.3%，且**失败格子全部是同一家**（右家）、**其它三家 100% 正确**。
学到的主色里那一家漂成 `(187,43,43)`（真值 `(206,62,62)`），覆盖率全 0 ⇒ 整片读成空。

**根因**（`learn_tile_colors` 的直方图代表色）：

```python
q = quant(p, 4)        # ← 取**桶下沿**（206 → 192、62 → 48）
mode, cnt = top[0]
c1 = [p for p in pts if dist(p, mode) <= tol * 1.5]   # 半径 24
```

`quant` 是**向下**量化到 4 bit ⇒ 桶内任意点到桶下沿最远 `sqrt(3)×15.99 ≈ 27.7`，**大于 24**。
真色一旦落在桶的远端，精修第一轮就**够不到它**：
`dist((206,62,62),(192,48,48)) = 24.25` —— **只差 0.25 就翻车**。四家主色里恰好只有它中招，
所以症状表现得像「右家坏了」而不是「代码有 bug」，极易被误判成「这张图有问题 / 测试 flaky」。

**修法**：新增 `quant_rep(c, bits=4)` = 桶下沿 + 半格（**桶心**），`learn_tile_colors` 改用它。
桶心到桶内任意点 ≤ `sqrt(3)×8 ≈ 13.9 < 24` —— **硬保证**，该类 bug 被证明性消灭。
`probe_tilecolor_20260925.py` 同一处也要改（它就是当年发现这个现象的地方）。

⚠️ 别顺手把 `quant()` 本身改成取整（四舍五入）：`learn_palette` 的底盘色、`read_cells_qq` 的
主色学习都用 `quant()` 当**桶键**、再**取桶内均值** —— 那是正确写法，桶键必须保持一致。

**排查这类「只有一家不对」问题的通用手法**：
① 先看 `learn_tile_colors` 的 `info`（`mode` / `share` / `color` / `d_backdrop` / `top3`）；
② 再把该家的**原始采样点色**打出来，算它们到学到色的距离 —— 一眼看出是「学错了色」还是「判据错了」；
③ 距离恰好卡在阈值边缘（差 < 1）⇒ 基本可以断定是**量化/舍入**类缺陷，去找口径不一致的地方。

**顺带记录的一条观察（未修，非阻塞）**：`find_blobs` 在 `step=5` 时会把间距 9.3 px 的相邻棋子
连成一片（`px_area` 出现 61250 的巨型连通域），`pick_piece_blobs` 随后按形状/填充率把它丢掉
⇒ 100 枚子只留 68 个团块，**恰好整行整行地缺**（17 行里缺 6 行，行号 ≡2,3 mod 5）。
对**定标**无影响（残差仍 0.65 px，因为剩余行足以锁住周期与相位），但换更小的 cell 时要留意。
`verify_liveread` 的 `method=backdrop` 分支走的就是这条路。

---

## 22. 跨机迁移：实战桥 Windows 便携化（2026-09-25）

**任务**：把 Mac 上的实战桥搬到 Windows 用。结论：**运行时 17 个文件 / 约 370 KB，零第三方库**
（原 13 个；2026-09-25 「屏幕自动实读」又加了 4 个 .py —— 见 §24.1，白名单要跟着加），
连 Python 都可以用官方 embeddable 包（解压即用、免安装）。三个产物：

| 文件 | 作用 |
|---|---|
| `live_bridge_server_20260925.py`（改） | `BOARD_LAYOUT` 改为三级来源 + **fail fast** |
| `board_layout.json` + `make_board_layout_json_20260925.py`（新） | 359 B 棋盘几何，让代码**自带**，不再依赖 500 KB 的 `index_task2.html` |
| `bridge_launch_20260925.py`（新） | 便携启动器：完整性自检 → 端口预检 → 起后端 → 轮询就绪 → 开浏览器 |
| `make_bridge_portable_20260925.py`（新） | 打包器：按白名单复制 + 生成 ASCII `.bat` + 中文说明 + zip |

### 22.1 ⚠️ 后端原先「不自带」棋盘几何 —— 换个目录就静默错几何

改前的三级来源，**只有第三级实际存在**：
```python
BOARD_LAYOUT = getattr(search, "BOARD_LAYOUT", None)      # ① 实测 search 里没有
if not BOARD_LAYOUT:
    _p = os.path.join(PROJ, "index_task2.html")           # ② 唯一生效
```
而 `PROJ = dirname(dirname(HERE))` ⇒ **代码必须待在 `<项目根>/.workbuddy/ld/`**。
一挪走 ⇒ `BOARD_LAYOUT = None` ⇒ `CAMP_CELLS` 变空集、启动断言被 `if BOARD_LAYOUT:` **跳过**
⇒ 带着错的几何继续跑，直到某次 `hq_cells()` 才炸成
`'NoneType' object is not subscriptable`（**错误信息指不出原因**）。

**修法**：① 首选 359 B 的 `board_layout.json`（自带）→ ② `search.BOARD_LAYOUT` → ③ HTML 兜底 →
**三级全落空 `raise SystemExit(2)` 并打印修复命令**。⚠️ 绝不可退回「静默 None」。
启动时打印 `棋盘几何：<来源>（N 行）`，一眼看出用的是哪一级。

`make_board_layout_json_20260925.py` 的断言（**抽完必须验**）：
- 与后端抽取逻辑**逐字同源**（否则便携包会用错几何）；只取前 17 行（尾部有一个空串杂质）
- 字符计数恒 `.144 / P92 / H17 / C20 / R16`（与 §「BOARD_LAYOUT 五种字符」硬约束交叉验证 ✅）
- 90° 旋转不变；回读逐位一致

### 22.2 pimc 引擎的隐藏 import：`run_whatif`

现象：便携包里点「AI 建议（pimc）」返回 `HTTP 400`，体为 `{"error": "No module named 'run_whatif'"}`。
根因：`ai_search_dark.py` **顶层**就 `from run_whatif import load_clean`。
⇒ 白名单**不能只按「谁被调用」列**，要按 **import 闭包**列。
⚠️ 但 `load_clean` 只被 `__main__` 调用 ⇒ 补 5.9 KB 的 `run_whatif.py` 即可，
**不必**拖进 19.6 MB 的 `dataset.jsonl`（实测：在线功能一项都不读它）。

### 22.3 ⚠️ 迁移测试必须用「同构隔离环境」——否则是假绿

便携包第一次试跑放在**项目根的子目录**里，一切正常 —— 假绿：`PROJ` 恰好又落回项目根，
那里正好有 `index_task2.html`，于是退化到第三级照样能跑，**把问题完全盖住**。
拷到**外层没有那个 HTML** 的隔离目录（`/tmp/wp`）才暴露。

**可推广结论**：凡「换机器 / 换目录」类迁移，**必须构造与目标环境同构的隔离环境**再测；
在自家目录里测，测的是自家那条捷径。

### 22.4 Windows 侧三条硬约束

1. **`.bat` 必须纯 ASCII**（`cmd.exe` 按当前 OEM 代码页解析 .bat，中文会乱码甚至解析失败）
   ⇒ 所有中文提示交给 Python 打印。打包器里加断言：`open(bat,'rb')` 不得出现 `>127` 的字节。
   用 `newline="\r\n"` 写，`使用说明.txt` 用 `utf-8-sig`（BOM，记事本友好）。
2. **控制台必须转 UTF-8**：`chcp 65001` + `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`，
   否则 Python 在 GBK 控制台打印中文直接 `UnicodeEncodeError` 崩掉。
3. **⚠️ 代理会拦截 localhost**：本机 `HTTP_PROXY=http://127.0.0.1:54526` 让
   `curl http://127.0.0.1:8899/api/state` 返回 **502 Bad Gateway**（服务明明活着）。
   Windows 上 Clash / v2ray / 公司代理极常见 ⇒ 启动器的就绪轮询与所有自检脚本
   **一律 `ProxyHandler({})` 直连**，并把「把 127.0.0.1 加进代理 bypass」写成说明书第一条排查项。

### 22.5 Python embeddable 够不够用（可复用的核查法）

官方 `python-X.Y.Z-embed-amd64.zip`（本机实测 3.11.9 = 11.2 MB，华为云镜像国内直连）。
⚠️ 它的标准库是 `python311.zip` 里的 **`.pyc` 字节码**（不是 `.py`）——
所以核查清单要写 `http/server.pyc` 这种名字，否则会误判成「全部缺失」。
- 实测：桥所需 **50 个模块 50/50 覆盖**（`itertools` 是内建 C 模块，不需要 .pyc）
- `python311._pth` 内容为 `python311.zip` + `.`，**未启用 `site`**（无 site-packages = 无所谓，我们零第三方）
- ⚠️ **WindowsApps 的 python.exe 是「存根」**（运行它只会打开微软商店）⇒
  `.bat` 里必须**排除** `%LOCALAPPDATA%\Microsoft\WindowsApps\` 这个前缀；
  优先顺序：`python-embed\python.exe` → `py -3` → PATH 上的 python。
- 首次运行自动解压：`powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force ..."`

### 22.6 命令速查

```bash
# 抽取/校验几何
python3 make_board_layout_json_20260925.py [--check]
# 打便携包（--with-python 带上免安装解释器；⚠️ zip 必须原名 python-3.11.9-embed-amd64.zip）
python3 make_bridge_portable_20260925.py --with-python /path/python-3.11.9-embed-amd64.zip
# 便携包自检（不启动）
python bridge_launch_20260925.py --check
# 便携包启动（--no-browser 供自动化测试）
python bridge_launch_20260925.py --port 8899 --no-browser
# 便携包 API 烟测（31 项；改完桥的代码重出包后必跑）
python3 smoke_portable_20260925.py [--pkg /tmp/wpb/实战桥Windows版] [--port 8899]
```

Windows 侧两步：① 拷**整个文件夹** ② 双击 `启动实战桥.bat`。
逃生通道（`.bat` 万一失效）：`cd app` → `..\python-embed\python.exe bridge_launch_20260925.py`。

### 22.7 验收（改动后必跑）

| 项目 | 结果 |
|---|---|
| 后端 `--selftest` | **11 / 11 全过**（几何来源已切换为 `board_layout.json`；⑪ = 暗棋口径 + 军旗亮出） |
| `bridge_e2e_20260925.js` | **92 / 0 全过**（§24 读屏段 20 项为纯增量） |
| 便携包 API 烟测（隔离目录、真 HTTP） | **31 / 31 全过**（`smoke_portable_20260925.py`） |
| 读屏四模块自测 | `screen_capture` 8/8 · `board_detect` 13/13 · `move_infer` 13/13 · `verify_liveread` 6/6 |
| 成品一致性 | 17 文件 sha256 与源逐项一致；`MANIFEST.json` 自校验 |
| 缺数据行为 | 藏起 `board_layout.json` ⇒ 明确报错 + 退出码 2（**不再是静默错几何**） |
| 免安装 Python | stdlib 覆盖 50/50；`.bat` 无非 ASCII 字节 |

> ⚠️ **端口约定**：Mac 常驻 8765；跑便携包烟测/隔离验证时用 **8899**，别覆盖 8765。
> ⚠️ 重启 8765 服务后**必须重跑 e2e** —— 旧进程可能是改前的代码（本轮就差点在旧代码上验收）。

### 22.8 ⚠️ 改了桥的代码后「重出包」的标准动作（2026-09-25 第二轮补）

**背景**：`make_bridge_portable_20260925.py` 只按 `APP_FILES` 白名单**拷贝当时的源文件**，
所以**任何**改了 `live_bridge*.py` / `build_live_ui*` 产物（`四国军棋实战桥.html`）的改动，
**必须重跑一次打包**，否则 Windows 那份永远是旧代码（本轮实测包里 HTML 还停在 16:37 的 74 KB 版）。

```bash
cd .workbuddy/ld
# ① 先备份旧包（坚哥规矩：改前备份留着当对照物）
cp -R ../实战桥Windows版 ../实战桥Windows版.bak_pre_<主题>_<日期>
cp ../实战桥Windows版.zip ../实战桥Windows版.zip.bak_pre_<主题>_<日期>
# ② 重打包（⚠️ zip 文件名必须原样叫 python-3.11.9-embed-amd64.zip）
python3 make_bridge_portable_20260925.py --with-python /tmp/pyembed/python-3.11.9-embed-amd64.zip
# ③ 隔离目录烟测（把包拷出去，外层不能有 index_task2.html）
rm -rf /tmp/wpb && mkdir -p /tmp/wpb && cp -R ../实战桥Windows版 /tmp/wpb/
python3 smoke_portable_20260925.py --pkg /tmp/wpb/实战桥Windows版 --port 8899   # 必须 31/31
```

**⚠️⚠️ 本轮踩到的坑（很容易复现）**：`--with-python` 传的**路径决定包里 zip 的文件名**，
而 `启动实战桥.bat` 是**写死**去找 `python-3.11.9-embed-amd64.zip` 的。
我第一次传了 `/tmp/pyembed/py.zip`（同内容的别名）⇒ 包里出现 `py.zip` ⇒ 首次双击**不会解压**、
直接掉到「找不到 Python」。**必须传原名**（打包脚本不做这个校验，值得补一条断言）。

**重出包后的核对清单**（每一条都能脚本化，别靠眼睛）：
1. 包内 `app/*` 与 **MANIFEST** 逐项 sha8 一致；
2. 包内每个文件与**源**逐项 sha8 一致（HTML 与 `<项目根>/四国军棋实战桥.html` 比）；
3. 包内 `app/四国军棋实战桥.html` 与项目根那份**字节相同**（确认前端是新的，不是旧的）；
4. `app/` 里**不该有** `index_task2.html` / `dataset.jsonl`；
5. `.bat` 无非 ASCII 字节；`使用说明.txt` 是 UTF-8 **BOM**；
6. zip 解到别处后 `bridge_launch.py --check` ⇒ 「运行文件 **16** 项：齐全」（`app/` 共 **17** 个文件 = 16 + 前端）；
   ⚠️ 读屏那 4 个 .py 是**软依赖**（`try: import`）—— 缺了主流程照跑，
   所以清单里必须显式列出，否则「少了读屏模块」会被静默放过；
7. `smoke_portable_20260925.py` **31 / 31**（其中「首页含 `cmdr_both`/`cmdr_bombed`/`maybeAutoSuggest`/`inferlab`/`flagpick`」
   就是「包里是最新前端」的**分辨力断言** —— 没有它，旧包也能全绿）。

**同时要同步的文档**（本轮漏查过一次）：
- `使用说明.txt` ← 打包器里的 `README` 常量（**功能速查**那节最容易过期：碰撞后果数量、AI 建议是否自动、暗棋标识口径）；
- `实战桥Windows迁移说明_20260925.html`（**无生成器，直接改 HTML**）：包体积、文件数、`--selftest` / e2e / 烟测三组数字、功能速查表；
- skill §22.7 本表 + §24 · `MEMORY.md` §1.4。

---

## 21. 禁止事项总表（自 `MEMORY.md §5` 迁入；MEMORY 只留指针）

> 这张表的用途：**动手前查「这件事是不是已经证伪过」**。数字与证据全在本 skill 对应章节。

| 要动的东西 | 禁止事项 | 章节 |
|---|---|---|
| 复盘解析 / 自洽警告 | ⚠️ 报「步数不对」先分辨 `.jgs` 还是旧 `.txt`：`.jgs` 正常**别改解析器**；`Documents/布局库` 的 `.txt` 是过期导出**一律改用 `.jgs`**。两条**独立**判据（`errCount` + `resultConflict`）都不能省 | 复盘自洽性自查 |
| 评分公式 / 字段口径 | ⚠️ **「战败/出局」不能当扣分项**。⚠️ **别拿 12 特征判别 CV AUC 0.9835 当目标**（标签泄漏），**正指标 = 玩家级 Spearman**。⚠️ 三处同名不同义：`stats["被吃"]` = 总被吃（counter_rate 要用 **`反吃`**）· `killRatio()` = 仅主动攻击 · `hit` = **交手总胜率** | 联众校准 / v3 |
| 碰撞规则 | **非工兵碰地雷 → 攻方阵亡、地雷原地保留**（不是同归于尽）；`index_task2.html` 的 `mine` 分支是对的**别改**。**联众 = 顺时针行棋序**（QQ 逆时针） | 同上 |
| what-if / 表现指标 | ⚠️ 判 `res` **必须用引擎原生名**。⚠️ 修正后**净值是最强单一指标** ⇒ **不改已落地的评分公式**。⚠️ **「失着」已四次被证伪**（AUC 0.3615 反向）⇒ **待移除/降权** | 搜索层 / v3 |
| AI 机器人设计 | ⚠️ **单步贪心不是完整机器人**。⚠️ 根因**别写成「必须先灭司令才能扛旗」**（错规则）—— 正确是**军旗守得要死，必须多步规划打穿防线** | 同上 |
| 配合 / 协同项 | ⚠️ **`focus` 是唯一有实质增量的配合指标**（已落成 `SW_LINK`）；⚠️ **别再试**：`support_in`(0) · `opp_share`（「集中兵力打一家」**不成立**）· `relay` · `think_*` · 6 个时序对。⚠️ 协同项**只用队友位置**、不涉兵种 ⇒ 不泄漏。⚠️ 强弱两组 `probe_loss` **重叠** ⇒ **单局数值不能区分棋力** | 四暗配合 / 12 |
| 强度测量 | ⚠️ **必须镜像赛制** + 足够局数。⚠️ **自对弈平局率极高** ⇒ **必须加「终局净子力差 Δ」连续口径**；Δ 与胜负方向不一致时取更保守结论。⚠️ `sorted(...,reverse=True)` 元组键别写错 | 12 |
| PIMC | ⚠️ **必须用「跨世界汇总统计」**（取单世界 `min`/`max` 两端配对 6/6 全负 ⇒ 做法错）。⚠️ **瓶颈不在聚合层、也不在预算分摊** ⇒ **三者不必再互测**。⚠️ **`max_depth` 虚设，用 K**；**K=3 无效**，**K=2 是唯一站住的**。⚠️ **`SW_SUPPORT` 已撤除别加回** | 13/14/15 |
| 先验质量（**已结案**） | ⚠️ **`origin_prior` / `infer_engineer` 默认关闭、不进生产** —— 先验更准（+0.115~0.135 nat）但**决策侧与分析侧都测不出收益**（分析侧 `hit` 反 **−1.61pp**，根因**条件选择偏差**）⇒ 「机制上就不该指望」。⚠️ **工兵几何推理改了 0 个决策** ⇒ **建议删除** | 16 |
| ⚠️ 结论纪律（**通用铁律**） | **任何「显著」写进结论前必须用「不同布局段的独立样本」复核**（实录：A 段 Δ+320/p=0.0111★ ⇒ 独立样本 −104/p=0.478）。⚠️ **等价性验证必须双向**。⚠️ 基线名必须写清是**哪一版实现**。⚠️⚠️ **自定义统计量与标准检验冲突时先怀疑自定义的** | 16.3~16.10 |
| **⭐ 实战桥（Phase 7 续）** | 见本 skill **§19 / §20 / §22**：平台色环/相位 · 视角映射与 `check_symmetry` 前提断言 · `#cell-<vr>-<vc>` 是视角坐标 · `legal_targets_of` 唯一入口且自检须挂 `drive(legal_fn=)` · `overrides` 随新局清零 · e2e `--out` = 项目根。另：坐标跟平台、兵种简写/全名收口、走棋方自动推断、撤销重放式、几何抽取三坑。⚠️ **跨机迁移**：几何必须**自带**（`board_layout.json` + fail fast，别依赖 `PROJ` 上两级的 HTML）· 白名单按 **import 闭包**列 · `.bat` 纯 ASCII · **代理拦 localhost** · **迁移测试须在隔离目录**（放项目根内 = 假绿） | 19/20/22 |
| **⭐ 实战桥 · 人机对战（§28）** | `human_vs_ai.py` 步进式状态机 + `/api/vs/*` 10 条路由 + `vsSect` 侧栏。⚠️ 必记：**四暗口径 `reveal_winner=False`，别改默认 True**（深核 113 项对照依赖它）· **铁路走法 = 有向弧线**（非工兵只能「直行」或「直行→恰一段弧线→沿 arrive 直行」）· **步时 20s 权威在后端**（`step_deadline` 绝对时刻 + 三道防重放闸门）· **判负闸门 `_settle_human()` 要收口**（别挂分支）· **回看 = 终局后四方全明**（快照存全明、`replay()` 按 `self.over` 决定是否过滤；未终局仍严格四暗，别在 `_snap()`/`state()` 里摊牌）· **AI 思考档 = 区间 3–5 / 2–3 / 1–2 / 0.5–1 秒**（`THINK_TIERS` + **每步抽样**；`MAX_THINK_SEC=5.0` **只夹上限、不抬小值**（自检/e2e 用 0.4~1s）；接口字段 `think_seconds`，`think` 已被占为调用次数；`/api/vs/new` 收 `level=0..3` 并回 `think_level/think_lo/think_hi`）· **开场大本营不留标记**（`flag_known` **只列「司令阵亡」的方位**，自己那方也不上榜）· **司令阵亡 ⇒ 该方军旗亮出**（口径收口在 `_open_flags()`；只亮旗 1 枚，别整方摊开）· **AI 布阵经验规则**（§28.20）：大本营非旗格 **≤连长 且不放炸弹/工兵**、地雷正后方 **≤旅长**（324 份真实布局实测合规 97.2%/97.9%）；`rationality_violations()` 单一实现 + **生成即自证**；⚠️ 改规则必须递增 `LAYOUT_RULE` 指纹（rl1→rl2→**rl3**；`restart_8765.py` 靠它判「代码是否已重启生效」）· **rl3 起布阵改为从真实布局库 `layout_book.json` 采样**（§28.21，273 份·竞技军棋v4.2；⚠️ 库缺席会**静默退回**旧生成器 ⇒ 打包 `APP_FILES` 必须带上它，自检 ㉓ 断言采样率 100%）· **布阵默认随机**（`b.get("seed")`，写成 `default 0` ⇒ 局局同阵型）· `S.vsBusy` 是双重语义（`vsNew()` 必须显式复位）· `vsDrive()` 必须判 `S.vsSetup` 防空转 · ⚠️⚠️ **8765 是坚哥的常驻口：测试一律用 8771/8772/8897-8899，禁止 `pkill -f live_bridge_server`**（误杀 ⇒ 他页面立刻 `Failed to fetch`）· ⚠️⚠️ **「进程活着」≠「代码是对的」**：本机跑着微云 + UGREEN 同步，会**整体搬走 `实战桥Windows版/`**（旧目录重命名带时间戳丢进废纸篓），旧进程攥着旧 inode 继续跑 ⇒ **半新半旧混搭**（实录：`TypeError: Searcher.__init__() got an unexpected keyword argument 'grab_r'`，新 `ai_search_dark` 传给旧 `search`）。**诊断/修复一律用 `.workbuddy/tests/restart_8765.py`**（查 cwd + 行为指纹，`--fix` 按端口精确重启）· 断言别硬编码「25 明 / 75 盖 / 100 枚」（开战后可能已吃子）· 投降 e2e 必须接 `confirm` dialog · **`ld/` 是打包源、工作树是产出，改完要回灌**（`.py` 手拷 + 前端 `sync_bridge_frontend.py --apply`）· **打包前把 `.bak_pre_*` 挪出工作树**（`make_bridge_portable` 会 rmtree 它）| 28 |
| 绝对强度锚线 | `pimc_mirror.py --anchor`：冻结 `ANCHOR_REF` / `ANCHOR_EVAL` / `ANCHOR_HIST`。⚠️ **常量不得漂移**，新基准**新增** `ANCHOR_REF2`。⚠️ 强制两边同聚合。⚠️ 单次 SE≈125~140 ⇒ **只报 Δ ± 95% CI** | 16.7 |
| **⭐ AI 强度对标人类（Phase 6）** | ⚠️⚠️ **报 AI 强度必须同时报「尺子效度」** —— 效度与 AI 位次**恰好反向**（`−0.16→P98` / `+0.25→P95` / `+0.41→P70`）⇒ **尺子越偏 AI，AI 看起来越强**。⚠️ **上帝视角尺子有同源偏置**且**分辨不出人类水平** ⇒ **不能排位次**。⚠️ **「AI 替一方 + 其余照抄棋谱」打完整局不可行**（100% 失配）。⚠️ 窗口长度扫描有**选择偏差**。⚠️ 净值必须**联盟口径**。⚠️ 必须写明 `greedy` 还是 `pimc`（同口径差 3 倍） | 17 |

---

## 参考文件

- `references/jgs-format.md`：.jgs 二进制格式完整规范、方位双射择优算法（`pickOrientByScore` + 行棋自洽率）、jgsToText 输出格式、已知坑（双偏移、纵坐标翻转、键序陷阱、GBK 编码）。

---

## 25. 项目硬约束速查表（自 `.workbuddy/memory/MEMORY.md` 迁入，2026-09-26）

> 这是「详尽版」。`MEMORY.md` 只保留路由指针，避免超限被截断。
> 任何一条与正文其他章节冲突时，以本节 + 对应专项章节的**最新日期**为准。

> **不做资料库。** 细节全在 skill `qq-junqi-replay`（§21 禁止事项总表 · §24 读屏 · §24.13 血案）· `html-visual-check` · `software-copyright-filing`。写新条目前先自问：能不能只写进 skill？

## 0 改法纪律
1. 三页同构：`index.html`（多「竞技技术积分」）｜ **`index_task2.html` ≡ `index_task3.html`，`diff` 必须 0 hunk**。只改 `qq军棋复盘分析/` 下三页；`../junqi_replay.html` 旧视觉不动。
2. 改一处 = 备份 `.bak_pre_<主题>_<日期>` → **断言式 Python 迁移**（锚点 `count==1` + 迁移后自检，三页共用一份脚本）→ `check_js_blocks.py` → 专项+全量回归 → Chrome 实拍 → 更新 skill/日志 → `present_files`。
3. ⚠️ **顺序：先跑探针重测 → 再改期望 → 最后动代码**。期望过期时**改测试更正常**，绝不为了让测试变绿改回页面。**改前备份必须留着**（「测试有分辨力」的唯一对照物）。
4. ⚠️ **生成物勿手改**（实战桥 HTML ← `build_live_ui_20260925.py`；Windows 包 ← `make_bridge_portable_20260925.py`）。**不做负样本验证的检查都是假绿。**

## 1 页面 / 引擎硬约束
- ⚠️ **颜色→方位一一对应**（`pickOrientByScore` 在 24 双射取最高分）；旧「半场投票」⇒ 两家撞方位、该方 0 子。
- ⚠️ **视角偏好唯一入口 `resolveView(replay,pref)`**；`replay.viewColor` ≠ 发生过旋转（看 `rotK`）。
- ⚠️ **胜负按最终存活判，不按净值**；**扛旗不是终局判据**；**扛旗无前置条件**（「司令阵亡→军旗亮出」只是**显示层**规则）。Python `legal_moves(flag_locked=)` **已删，不得加回**。
- ⚠️ **`isRailway`（在不在网里）≠ `railLinked`（两格心间有无真线段）**；中间格箭头走真实路线（唯一入口 `movePathCells`，禁曼哈顿插值；`railPathThrough` **无解返 `null` 而非 `[]`**）。
- ⚠️ **自动滚动禁 `scrollIntoView`**，唯一入口 `scrollListNearest`。⚠️ **手机模式判据 = `innerWidth === 视口宽`**；「无横向溢出」= **假绿**。
- `BOARD_LAYOUT` 恒 `.144/P92/H17/C20/R16=289`；`R` 可穿不可停 ⇒ **真行棋点 129 = 四家各 30 + 中央 9**。
- 棋盘 v2：底板**纯色** `#435743`（迷彩已删）；尺寸全走 `calc(var(--cell-size)*比例)`。⚠️ **`#boardWrap` 的 `padding:10px` 不能动**（与 `.board-svg{left:20px;top:20px}` 耦合）。
- 棋子标记按**身份**存（`pieceMarks['初始行,初始列|颜色']`）**不按格子**；`pieceIdentityMap()` 与 `resolveMove` 同源；**只能右键改**；单旋钮 `.mark-panel` 的 `--mk-scale`（桌面 `.5`/手机 `1.25`），面板内每处连描边都乘它，**棋子上的 `.piece-mark` 不缩**。
- 司令阵亡→亮旗：`refreshCmdrDead()` 须加「该方场上仍有子 > 0」；`isFlagRevealed()` **两处贴盖牌都要加**；⚠️ 亮出后**不加任何视觉区分**。
- 残局研究：**官方原文为最高依据**（**铁路直角拐弯只有工兵能过**；**大本营子与地雷不能动**）；非工兵 = 直行 或 直行+恰一段弧线+沿到达朝向直行，**掉头必须挡掉**；⚠️ 可落点**不做视觉提示**；⚠️ 手机端 `.study-stage` 纵向 flex、托盘 `row`。
- 署名**三页不同，只改被点名那处**：index =「暴暴寒（7z）｜规则赋能：姜朕熙」；task2/3 badge =「以此致敬永远的尖刀师！设计制作：☆→小寒（7z）」（锚点须带「设计制作：」否则 `count==2`）；**页脚 © 仍**「© 2026 热心市民小寒（7z）」。页脚序 = 产品说明→署名→站点统计→备案；51.la URL 须显式 `https://`。
- ⚠️ 不载棋谱时 `#boardWrap` 的 `.main-grid` 是 `display:none` ⇒ 量几何/截图前先 `startAnalyze(jgsToText(...))`。⚠️ Node 无 GBK ⇒ 断言用颜色/方位，别断玩家名；⚠️ `window.open` 弹窗 target 调 `setViewport` **不能带 `isMobile`**。

## 2 四暗前提（AI 地基）
- ⚠️ **除自己外三家全暗（含队友）**，各自独立信息集；`PIMCPolicy` 按**单方**构造；`known_sides={me}`（采样）≠ `team=A_SET/B_SET`（搜索符号），**混用 = 把队友当明棋**。
- ⚠️ `apply_move` **不校验兵种合法性** ⇒ AI 替队友走可能**静默推进非法局面**；兜底 `drive_match(validate=True)`，`illegal` 必须 0。军旗只落大本营格（`is_hq()`）；**亮旗后位置公开 ⇒ 采样钉死真值**。
- ⚠️ 暗棋 = 遮兵种、保位置与颜色 ⇒ 位置归属全知。① 某格有子且从未作任何一步起/终点 ⇒ 就是初始那枚；② **地雷/军旗不能移动** ⇒ 动过的格出现它们概率**严格 0**。
- ⚠️ 信息三分：`信息.known` = 已公开兵种；**唯一解可进 known**；**下界只能上屏**（`infer_label`=「≥某兵种」）——下界进 known 会 ① 让 `Searcher` 拿错情报 ② 破坏 **`sum(pool[side]) == 未知格数`**。⚠️ 扛旗清盘须连带清 `known`/`infer_label`。

## 3 AI 搜索层（`.workbuddy/ld/`；skill §10~§17）
⚠️ **AI 复盘层落地（三页接入 + QQ 桥 + 逐位对齐 + PIMC 深核）见 skill §26**。
⚠️⚠️ **Python 侧浮点一律走 `fnaive.fsum/fmean/pstdev`**（`sum()` 是补偿求和 ≠ JS `+=` ⇒ 下游阈值计数翻边）；**跨家聚合用 `PAGE_DIR_ORDER = ("up","down","left","right")`**（≠ `DIRS4`）。
⚠️⚠️ **QQ `.jgs` 记录集四坑**：①颜色→方位名必须映射 ②`{"order":"ccw"}`（QQ 逆时针）不声明 ⇒ 整批被闸门静默滤掉 ③事件五类，**`超时` 只丢一手绝不清盘** ④判据用**文件声明的方位** `[no,fr,fc,tr,tc,side]`，但只在有声明时改写 `turn`（否则联众 `illegal` 22→50）。
- ⚠️⚠️⚠️ **`order()` 必须带确定性次级键** `key=lambda m:(-value, m)`；`unmake()` 用 del+重插 ⇒ dict 顺序变 ⇒ top-K **集合不同**（真危害是**语义契约破裂**，含 PIMC）。
- ⚠️⚠️ **禁遍历字符串 `frozenset` 做顺序敏感操作**（`PYTHONHASHSEED` 每进程不同）；耗 `rng`/浮点累加处按有序 `DIRS4`。⚠️ 对照实验必须每方独立 `dict(board)` 拷贝（曾报 7 处假差异）。
- ⚠️ **`max_depth` 虚设，`K` 才是杠杆**；root 层全宽 ⇒ 降 K 不漏第一步。⚠️ 别动：标准 negamax（`DIRS4` 与联盟 `{up,down}/{right,left}` **严格交替**，别写四博弈）；战略项必需（`SW_UNLOCK=80`+`SW_THREAT=30`）；必须有 `SW_NODES` 预算。
- ⭐ **配合意识四项（`SW_GRAB` 双抢 / `SW_SUPP` 协同防守 / `SW_COMBO` 组合进攻 / `SW_TWIN` 双急）见 §26.18**。四暗红线：只读 `side`（归属）与坐标、不读兵种；`need_reg` 必须含 combo；经验权重未定权（待 Windows 侧 `mirror_match.py` 跑 20 局显著性）。
- ⚠️ **镜像赛制 = 强度测量唯一合法方式**；分窗口识别因果（早 ≤60 / 中 31~150 / 残局 >150）：「早窗没信号」≠「特征没用」、「增量大」≠「能用」、「与胜利相关」≠「作搜索项能提棋力」（门槛 ≈+0.03）；**|Δ|<1000 的效应 10 配对以内测不出** ⇒ **n≤4 不当结论**。
- ⚠️ 自检两坑：`Searcher.__init__` 会 `dict(alive)` 拷贝 ⇒ 改 `sr.alive`；造「对方军旗格」**不能直接赋值**（覆盖军旗 ⇒ `flag` 永不触发），要与邻格交换。⚠️ **res 用引擎原生名**（`attacker_wins`/`defender_wins`/`both_die`/`dig`/`mine`/`flag`）。

## 4 实战桥（skill §19/§20/§22/§23/**§24**）
产物：`四国军棋实战桥.html`（⚠️ **人改的源是 `实战桥Windows版/app/` 那份**，别用已停用的 `build_live_ui` 重生成 —— 见 §28.24）· 后端 `live_bridge_server_20260925.py`（`--selftest` **11**）· e2e `bridge_e2e_20260925.js`（**92**）· 文档 `build_bridge_doc_20260925.py` · 探针 `probe_darklabel_20260925.py` / `diag_pool_20260925.py`。`--port 8765`，**必须走 HTTP**。
- ⚠️ 池构成漂移：`_guess` 只做「池 −1」，但**选谁**污染**构成** ⇒ `_unpool` 静默失败；修法 `GUESS_EXCLUDE`。⇒ **不变量修复不能只看大小，还要看构成**。改这块必跑 `probe_darklabel_20260925.py`（6 项计数全 0）。
- 六项调整：②撞我方存活 ⇒ 标 **≥高一级**；③后果菜单 6→**8**；④司令阵亡 ⇒ 2 大本营格成「旗?」候选 → 点徽章确认（判定用**解析后**兵种）；⑤碰撞改**左键**；⑥轮到己方**自动给建议**（去重键 `(round,next)`）。「≥某兵种」只上屏、不进 `known`。
- ⚠️⚠️ `document` 的 `click` 监听无条件冒泡关菜单 ⇒ 左键点碰撞格「菜单一闪即没」（**侧栏「采纳」同族**）；修法 = 放过 `#ctxMenu`/`#boardGrid` + `setTimeout(openMenu,0)`。旧测试只用右键 ⇒ 没暴露 ⇒ **「真左键」断言必须有**。
- ⚠️ 假绿：用 `highlight-to`/`move-arrow` 存在性判「自动建议」= 假绿（上一手标记同 class）⇒ 认状态位 `U.sug.auto`。⚠️ **裸 `fetch` 推进回合绕过页面 `absorb`** ⇒ 状态陈旧串位 ⇒ 推进后显式拉 `/api/state` 再 `absorb`。
- ⚠️⚠️ **坐标跟「平台」不跟三页**：平台 = 行字母+列数字（`ROW_LETTERS`，锚点 `up=A10·right=H17·down=W8·left=H1`）；三页 = 列字母+行数字 ⇒ **互为转置**。⚠️ 视角旋转 = 坐标映射、**不转底板**。⚠️ id：`#cell-<vr>-<vc>` 视角 / `data-r,data-c` 绝对 ⇒ 点绝对格走 `cellEl(r,c)`。
- ⚠️ 合法性唯一入口 = 纯函数 `legal_targets_of(board,fr,fc)`；自检须**同口径**挂 `replay_drive.drive(legal_fn=…)`，在**未过滤全库**统计 + **带负样本**。⚠️ `overrides` 随新局清零；e2e `--out` 默认项目根；测试故意的 400 单列 `softErrs`。
- ⚠️ **「有」≠「只有一份」**：注入/替换必须断言**次数**（`tpl.count(k)==1`）。⚠️ **class 名对 ≠ 渲染对** ⇒ 视觉需求必须断言**计算样式 + 反向验证**。
- ⚠️⚠️ **两份 = 前端两份 + 运行时两份**（`app/` 是**人改的源**，根版 HTML 与 `.workbuddy/ld/*.py` 是另存）：改完必跑 `python3 .workbuddy/ld/sync_bridge_frontend.py`（不带参数只检查，`--apply` 才对齐；打包闸门 `pick_html`/`check_drift` 也靠它）⇒ **A 段 47 项烟测**（`PORT=8771 vs_v6_smoke_20260930.py`）。细节 §28.24。
- ⭐ **AI 布阵风格四档（rl4）**：`_vs_new` 的 `style` ∈ {稳,攻,龟,闪电} / `random` / 缺省**轮换**；⚠️ **显式 seed ⇒ 风格由 `seed % 4` 定**（无条件轮换会破「同 seed 可复现」，烟测抓过）。细节 §28.24 · 强度验证 §28.25。

### 4.1 屏幕自动实读（09-25 第三轮）
⚠️ 细节/四条死路/测试台/平台双路/跨机迁移坑全在 skill §24 / §24.13 / §22.8。
模块（**零第三方依赖**）：`screen_capture`(8/8) · `board_detect`(**16/16**) · `move_infer`(13/13) · `live_read`+`verify_liveread`(6/6)。接口 `POST /api/vision/<act>` + `GET /api/vision/state`。
- ⚠️⚠️⚠️ **`round()` 银行家舍入**：格心在 `origin+(k+0.5)·cw` ⇒ 归一化落在**半整数**而 `round(0.5)=0` ⇒ 每个对齐格心都算成 0.5 格误差。修法：先 `u=(v-org)/cw-0.5` 再 `abs(u-round(u))*cw`。QQ 相位判据同坑 ⇒ 用**相对相位** `v%p`。
- ⚠️⚠️⚠️ **直方图桶的「代表色」取桶心 `quant_rep`，不能取桶下沿 `quant`** —— 否则精修半径 24 够不到桶远端真色（实测 `dist((206,62,62),(192,48,48))=24.25`）⇒ **整片棋子读成空**，且只出现在**一家**上，极易误判成「图有问题 / flaky」。血案 skill §24.13。
- ⚠️ 定标只认棋规判据：绝对偏移用**色块落在 LAYOUT 129 可行格的比例**；节距用**格心内点率**（真 0.90~0.93 / 1.5× 0.15）；原点**全局枚举**。⚠️ QQ 色块尺子会被桌面图标带偏（面积中位数被压 ⇒ 尺寸闸砍掉真色块）⇒ 多把尺子 `QQ_SCALE_PCTS`；⚠️ 团块筛选**面积下限 `amin=0.30*a85` 不能丢**。
- ⚠️ 平台双路：`Calib.style` 分派（`lj`/`qq`），**判据不得互借**；三路顺序固定 **①纯色底板 → ②色块法 → ③瓷砖法**；⚠️ 风格仲裁 `_qq_tile_vote`（≥3 家主色命中 `_qq_block_hit`）是**唯一入口**，但**学到 <3 家主色时必须弃权**（否则把 `qq` 误降 `lj` ⇒ 整片读空）。
- ⚠️ 前端契约：`apiV()`/`api()` 分开、**永不抛**；⚠️⚠️ 读接口**别传第二参数**（`{}` 也真值 ⇒ 被当 POST ⇒ 404 ⇒ 标定按钮永久禁用）。⚠️ 画面**必须完整不被遮挡**；桥页面**保持前台**（后台标签 `setInterval` 被节流到 1 次/分）⇒ 轮询 1200 ms。

## 5 测试入口
⚠️ 完整清单与期望值查 skill「项目内测试台」表。三条通用：
- 任何改动都跑**全量回归**；**引擎改动**另加 `extract_engine_task3.py` 重抽 + `md5 engine_task2.js engine_task3.js` **必须相同**。
- 实战桥/读屏：后端 `--selftest`(11) · `build_live_ui_20260925.py --check` · `check_js_blocks.py 四国军棋实战桥.html` · `bridge_e2e_20260925.js --out <项目根>`(92) · 读屏四模块 8/**16**/13/6。
- 人机对战（**测试口 8771/8772，绝不用 8765**）：`vs_v6_smoke_20260930.py`(**47**) · `probe_coord_passthrough_20260930.py`(**10**) · `probe_style_e2e_20261002.py`(四档 6/6) · `shot_vs_style_20261002.js`(前端 DOM + 轮换负样本) · `human_vs_ai.py --selftest`（⚠️ **需 numpy ⇒ 用 `~/.workbuddy/binaries/python/envs/default/bin/python`**）· `restart_8765.py --fix`（`JUNQI_8765_PORT=8771` 可指向测试口）。
- ⚠️⚠️ **要跑普通模式 `bridge_e2e` 必须用「干净」实例**：`launch_bridge_20261002.py --port 8771 --restart`（起服务 + 自验 `active is False`）。**用过诊断/烟测/风格 e2e 的端口会被残留 VS 会话劫持**（页面自动切回对战视图 ⇒ `dropzone=0`）—— 详见 §28.24。
- AI 网络/风格：（详见 §28.23 / §28.24 / §28.25）`sl_data` 训练≡部署口径探针 · `probe_np_notorch_20261002.py`（免 torch）· 镜像强度 `sl_mirror_20261002.py`。
- ⚠️ **前端一致性**：`python3 .workbuddy/ld/sync_bridge_frontend.py`（不带参只检查）—— 改完前端/后端**必跑**，打包前也靠它。
- 报告型 HTML 交付前：`node .workbuddy/tests/shoot_report.js 报告.html --strict --need "…" --sections "…"`（`--need/--sections` 逗号分隔）。
- AI 复盘层：`verify_aieval_task2_20260926.js`(27×3) · `verify_aideep_task2_20260926.js`(10×3) · `align_ai_eval_20260926.js`(逐位 0 差异) · `ai_deep_review_20260926.py --selftest` · `diag_recs_gate_20260926.py <recs.jsonl>`。⚠️ 页面脚本参数走 `path.resolve` ⇒ **传绝对路径**。

## 6 环境
macOS arm64；Chrome 与 puppeteer-core **必须绝对路径** require（`~/.workbuddy/binaries/node/workspace/node_modules`）；python 用 `~/.workbuddy/binaries/python/envs/default/bin/python`（有 PIL）；全局 CLI 装 `~/.local`、npm 走 npmmirror；PIL 用 `Hiragino Sans GB.ttc`；`junqi_replay.html` 是 **444 只读**。
⚠️ **reportlab 装不了 CFF 轮廓 `.ttc`** ⇒ 嵌中文字体用 `Supplemental/Arial Unicode.ttf` 或 `STHeiti Light/Medium.ttc`。⚠️ 便携包烟测端口 **8899**，别覆盖 Mac 常驻 **8765**；**重启 8765 后必须重跑 e2e**。

## 7 软著（已结案；skill `software-copyright-filing`）
名称「四国军棋复盘分析器 V1.0」（去「QQ」）· 著作权人 **王坚**（个人/独立开发/原始取得）· 开发完成 **2026-09-01** · 首次发表 **2026-09-02**。⚠️ **登记范围 = 只报玩家版** = `index_task2.html` ≡ `index_task3.html`（MD5 `d818a1db…`）；含积分块的 `index.html` **不在范围**；**截图必须同源取玩家版**。⚠️ **说明书 PDF 绝不能出现网址/联系方式**。署名归属：**暴暴寒（7z）· 小寒（7z）· 热心市民小寒 · ☆→小寒 均为王坚本人网名**；**www.junqiwang.cn 为本人所有** ⇒ 可「独立开发」申报。产物在 `软著申请材料/`。

## 8 历轮「别再做」索引
**整表已迁入 skill §21**（复盘解析·评分字段口径·碰撞规则·what-if·AI 机器人·配合协同·强度测量·PIMC·绝对强度锚线·先验质量·读屏取图）—— **动手前先查那一节**。三条铁律：
- ⚠️ **结论纪律**：「显著」写进结论前须用**不同布局段的独立样本**复核；等价性验证**双向**；基线写清哪一版；⚠️⚠️ 自定义统计量与标准检验冲突时**先怀疑自定义的**（skill 16.3~16.10）。
- ⭐ **AI 强度对标人类**：⚠️⚠️ 必须同时报**「尺子效度」**（二者**恰好反向** ⇒ 尺子越偏 AI，AI 看起来越强）；上帝视角尺子有**同源偏置** ⇒ 不能排位次；写明 `greedy`/`pimc`（skill 17）。
- **先验质量（已结案）**：⚠️ `origin_prior`/`infer_engineer` **默认关闭、不进生产**（skill 16）。
- **AI 复盘层（09-26）**：⚠️ 别用 `sum()`/容差判据（见 §3 与 §26.3）；⚠️ 别把 AI 分做成**替换** v3（无增量：0.8852 ≈ 0.8861，见 §26.7）；⚠️ 事件行**别把 `超时` 当认输**（§26.4-3）。

## 26. AI 复盘层落地三页（四暗单步 + PIMC 深核，2026-09-26）

目标：把**已训练好的 AI** 接进三页，按**四暗信息集**口径给出 ① 行棋得失 ② 胜负手（AI 榜）③ 玩家表现（AI 决策质量分）。
⚠️ **本节只写页面接入 + QQ 桥 + 逐位对齐这三个新面**；单步估值层看 §9，搜索层看 §10，采样看 §10.8。

### 26.1 文件清单（`.workbuddy/ld/`，全部**零第三方依赖**）

| 文件 | 作用 |
|---|---|
| `fnaive.py` | ⭐ **朴素左折叠** `fsum/fmean/pstdev`。与 JS `+=` 逐位等价的唯一保障，见 26.3 |
| `ai_features_20260926.py` | 逐步特征提取（四暗信息集）→ `ai_features_strict.jsonl` |
| `ai_train_20260926.py` | 训练 + 5 折 CV 验证 → `ai_eval_model.json`（5.2 KB） |
| `prior_pack.json` | 压缩先验（21802 → **4879 字符**，解码最大误差 **0.000000**） |
| `ai_eval_core.js` | 单步期望评估层 JS 移植（`aiAnalyze`，26 KB） |
| `ai_review.css` / `ai_review_ui.js` | 三页接入层（样式 + UI，见 26.5） |
| `migrate_aieval_20260926.py` | ⭐ 三页**断言式迁移**脚本（幂等 + task2≡task3 自检） |
| `dump_ai_for_js_20260926.py` | 把 Python 的 `stats/curve/steps/alive` 注入 Node，做逐位对齐 |
| `align_ai_eval_20260926.js` | JS↔Python 逐位对齐（**精确相等**判据） |
| `ai_deep_review_20260926.py` | PIMC 离线深度复核（`--selftest` / `--recs`） |
| `export_recs_for_deep_20260926.js` | ⭐ `.jgs` → Python 记录集 JSONL（**QQ 侧唯一入口**） |
| `diag_recs_gate_20260926.py` | 记录集**闸门诊断**（被 `load_clean` 丢掉时，它是唯一能说清原因的工具） |
| `pack_deep_20260926.py` | ⭐ 把 `ai_deep_*.json` 精简成**页面内嵌包**（27.2 → 11.5 KB，2.36×）；`--merge` 合并多份 |
| `dump_qq_steps_20260926.js` | 页面侧逐步评估 dump（多局），供 QQ 对齐用 |
| `align_qq_20260926.py` | ⭐ **QQ 桥 JS↔Python 逐位对齐**（8 局 1448 步 0 差异，见 26.9） |

### 26.2 ⚠️ 三页接入的落点（不许凭记忆改，锚点以 `migrate_aieval_20260926.py` 为准）
- AI 源码块插在 `/* ===== 全量分析 ===== */` **之前**；CSS 块插在 `html.theme-dark{` **之前**。
- `startAnalyze` 内插 `aiRun();` 与 `renderAI(evals);`；行棋记录条目串换成 `PANEL_MV`（带 `+aiBadgeHtml(i)`）。
- ⚠️ 迁移脚本必须**幂等**：`strip_blocks` 的正则要带 `\n*` 吃掉插入补的换行；`PANEL_MV` 的装配与还原**共用同一常量**（手抄漏一个 `+` 就会幂等失效 —— 本轮踩过）。
- ⚠️ 复用同一批锚点时，**必须先逐函数比对** `analyze()` / `computePlayerEval()` / `evaluateAll()` / `killRatio()` / `renderPlayerEval()` / `DIM_WEIGHTS` 在 `index` 与 `task2` 中**逐字一致**，再共用锚点。

### 26.3 ⚠️⚠️ 浮点累加口径：`sum()` ≠ JS `+=`（本轮最隐蔽的坑）
- **Python 3.12+ 的 `sum()` / `statistics.fmean` 对浮点做 Neumaier 补偿求和，JS 的 `+=` 是朴素左折叠** ⇒ 末位不同。
- 血案：`sum([0.1,0.2,0.3,20,-1e16,1e16,19.999999999999996])` = `40.599999999999994`，朴素循环 = `40.0`。
- 危害只在**下游阈值计数**上显形：`loss >= 20`（blunder_rate）、`c_actual < -0.5`（c_neg_rate）翻边 ⇒ 300 局里若干局分数差 ~0.5。
- **修法：Python 侧一律走 `fnaive.fsum/fmean/pstdev`**（`whatif.InfoSet.dist/eval_move`、`ai_features`、`ai_train`、`dump_ai_for_js`）。
- ⚠️ **对齐判据必须是精确相等**，不能用容差：曾用 `near(...,1e-9)` ⇒ 末位差被吞掉、每步都报「对齐」，但阈值计数照旧翻边。**容差判据会掩盖阈值判据的翻边。**
- ⚠️ **第二条：跨家遍历序**。页面 `COLOR_ORDER=['绿','黄','蓝','紫']` 经 `DEFAULT_ORIENT` 映射 = 方位序 **[up,down,left,right]**；而 `junqi_engine.DIRS4=["up","right","down","left"]`。跨家聚合（局内 z 分）求和次序不同 ⇒ `g_*`/`score` 差 ~1e-15。**Python 侧统一 `PAGE_DIR_ORDER = ("up","down","left","right")`。**
- 对齐成绩：**40 局 + 300 局（58159 步）在精确相等判据下全 0 差异**（新旧模型各验一次）。

### 26.4 ⚠️⚠️⚠️ QQ `.jgs` → Python 记录集：**四个并列的坑**（缺一个就整批 0 局）
`export_recs_for_deep_20260926.js` 是新脚本，四条都在它/`replay_drive` 里踩过：

1. **颜色 → 方位名必须映射**。Python `junqi_engine.DIRS4` 只认 `up/right/down/left`；页面内部用中文颜色 ⇒ 不映射直接 `DIRS4.index('黄')` ValueError。用页面自己的 `DEFAULT_ORIENT`（绿=up/黄=down/蓝=left/紫=right）映射，且因为只调 `parseReplay`（**未**调 `startAnalyze`）⇒ `rep.layout` 未被 `rotateView` 旋转，坐标确在绝对框架内。
2. **行棋序：QQ = 逆时针**。记录集写 `{"order":"ccw"}`，`junqi_engine.TURN_ORDER` / `set_turn_order` / `turn_order_of` 三个入口切序。
   ⚠️ 不声明 ⇒ 用顺时针推进 ⇒ `turn_mismatch` 全量误报 ⇒ 闸门 `load_clean` 把**整批 QQ 局静默滤掉（表现为「0 局」）**。
   实测确认（`_diag_turnorder_20260926.py` 统计「上一手方位→下一手方位」转移矩阵）：QQ 真序 = **`up → left → down → right`**，8 局里 6 局完美成 4 环。
3. **事件行是五类，不是一类**。`.jgs` 实测：`超时` / `自杀战败` / `退出游戏` / `认输` / `军旗被扛，战败`。
   - ⚠️ **`超时` 只丢一手，绝不清盘**。旧版把所有 event 一律写 `'giveup'` ⇒ 超时被当认输清盘 ⇒ **后续几十步「起点无子」**（实测 104/268 步）。
   - `军旗被扛，战败` 是**确认**事件（扛旗那一步引擎已清过盘），不再清。
   - **未知事件按 `timeout`（不清盘）处理** —— 宁可少清一家，不可错清一家（错清会级联）。
   - 统一入口：`junqi_engine.event_info(mv, turn) -> (kind, actor)`，兼容旧格式 `[no,'giveup']` ⇒ `('out', None)`。
4. **判据优先级：文件声明的方位 > 推导出的 `turn`**。`.jgs` 每步自带 `color` ⇒ 导出成 6 元组 `[no,fr,fc,tr,tc,side]`，`drive` 用它当判据（`declared`）。
   ⚠️ 实测部分 `.jgs` **本身就有跳步记录**（转移矩阵出现 `right→right`）⇒ 用推导 `turn` 会把**本来能用的局**判成 `turn_mismatch` 而误杀。
   ⚠️⚠️ **但只许在「有声明」时改写 `turn`**：无声明的（联众）路径必须逐位保持原样，否则推进基准从「期望方」变「实际方」，一旦出现 mismatch 就与旧结果发散 —— 实测联众 `illegal` 22 → **50**（纯自伤）。
- 其它：`p.evaluate` 的回调跑在**页面上下文**，Node 侧常量（`PY_SHORT`/`EVENT_KIND`/`KIND_DEFAULT`）必须**显式传参**（否则 `ReferenceError`）；全角逗号不能做对象字面量的键（`'军旗被扛，战败'` 要加引号）；`console.log` 不支持 `%.1f`（只认 `%d/%i/%f/%s`）。

### 26.5 UI 口径（`ai_review.css` + `ai_review_ui.js`）
- **绝对方位框架**：一律跑 `replay.baseLayout / baseMoves / baseOrient`。`AI_PRIOR` 按**绝对棋盘坐标**统计，在旋转后的视角框架里评估 ⇒ 分数随切视角漂移。⇒ **切换视角只重渲染、不重算**，`aiRes.steps[i]` 与 `analysis.steps[i]` 恒一一对应。
- 徽标分档：`loss` ≥40 `ai-bad2` / ≥20 `ai-bad` / ≥8 `ai-mid` / 否则 `ai-ok`；深核另加 `ai-deep`（🔍）。
- **两套 `payoff` 不可混**：玩家评分用 `waste=0`（纯子力盈亏），AI 选步用 `waste>0`。页面侧统一 `AI_W_WASTE = 0`。
- 深核导入的**唯一入口**是 `aiApplyDeep(obj, label)` —— 导入控件与测试**共用**它（曾因测试直接赋值 `aiDeep={...}` 绕过状态刷新而导致验收失败）。
- AI 卡**必须并列展示**并写明诚实口径（见 26.7），**不替换** v3。

### 26.6 测试（新增）
- `verify_aieval_task2_20260926.js`：**27 项**页面验收（跑起来 / 并列表 / 徽标数 / 失误榜降序 / **视角无关性** / 深核导入 / 点击定位 / 深色 + 手机 / 零 pageerror）。三页各 27/27。
- `verify_aideep_task2_20260926.js`：**10 项真产物端到端**（`.jgs` → 记录集 → PIMC → 页面导入 → 徽标/数值一致）。三页各 10/10。
- `diag_recs_gate_20260926.py <recs.jsonl>`：闸门诊断。**「复核 0 局」时先跑它**，它会逐局打出 `from_empty/turn_mismatch/friendly/illegal`。
- `ai_deep_review_20260926.py --selftest`：复核不改状态（棋盘点 + 池计数断言）、`loss>=0`、同种子逐位一致、采样守恒。
- ⚠️ `verify_mobile_20260923.js` 的判据已由「恰 2 处 `@media (max-width:720px)`」改为「恰 3 处 **+ 第 3 处身份必须是 AI 块**」——只数个数会失去分辨力。
- ⚠️ 该脚本参数走 `path.resolve` ⇒ **必须传绝对路径**（传裸文件名会读 `tests/index_task2.html` 而 ENOENT）。

### 26.7 ⚠️ 诚实口径（写进 UI，也是本轮的结论）
- AI 决策质量分**打不过 v3**：严格口径 CV AUC **0.8150** / 玩家级 ρ **+0.8354** / 前 2 命中 **48.6%**；
  对照 v1 `0.8967/+0.9080/64.6%`、v3 `0.8861/+0.9055/60.5%`、净值 `0.8530/+0.8649/54.0%`。
- AI↔v3 Pearson 仅 **+0.679**；`0.5·z(AI)+0.5·z(v3)` = **0.8852** ≈ v3 单独 0.8861 ⇒ **无增量**。
- ⇒ **落地选择（坚哥拍板）= v3 保留为默认，AI 分并列展示**；胜负手 = **双榜并列（净值榜 + AI 失误榜）**。
  ⚠️ 别把 AI 分做成替换项，也别在 UI 里暗示它更准。
- 深核确实能给出**有价值的分歧**（单步 176 → 搜索 45、157 → 搜索 0.0 这种量级差，页面上会标「搜索复核后翻案」），
  但**一致率并不高**（方位修正后重跑 8 局：单步/搜索对「大失着」的判定一致 **3~12/12，合计 72/96**）⇒ 深核是**旁证**，不是权威。
  ⚠️ 早前那句「8 局里 1 局 0/12 一致」是**方位修正前**的旧产物，别再用它下结论。

### 26.8 ⭐ 深度复核的**自动加载**（三层，2026-09-26 第二轮）

> 旧形态是「生成 `ai_deep_*.json` → 手动点『导入』」——对使用者是负担，而且**生成了却忘了导入**
> 会让 🔍 一列**静默消失**。现在三层并存，**载入棋谱即自动出现**，零操作。

| 层 | 来源 | 何时生效 | 怎么更新 |
|---|---|---|---|
| `导入` | 页面选文件 | 本次会话立即 | 导入时顺带写入本地记忆 |
| `本地记忆` | `localStorage` 键 `qj_ai_deep_pack_v1` | 打开页面即恢复（**跨会话**） | 导入时自动写；「忘记已存的包」清掉 |
| `内嵌包` | `var AI_DEEP_PACK = …`（页面资产） | **零操作自动生效** | 两步：`pack_deep_*` → `migrate_aieval_*` |

优先级 `导入 > 本地记忆 > 内嵌包`，但**不是覆盖关系**：`aiDeepFind()` 按优先级依次找
「**含当前这一局**」的包 ⇒ 内嵌包只覆盖某几局时，导入的包仍能用上。全部落空时**诚实说明**
「已加载 N 份数据，但其中没有本局」——**绝不许随便挑一份假装命中**（那是最危险的退化解）。

**内嵌包怎么生成（两步，缺一不可）**
```bash
python pack_deep_20260926.py ai_deep_qq_20260926.json   # 精简：27.2 KB → 11.5 KB（2.36×）
python migrate_aieval_20260926.py                        # 注入三页（含幂等 + task2≡task3 自检）
```
- 多份产物合并：`--merge a.json b.json -o ai_deep_pack.json`（同名局后者覆盖）。
- 精简只保留页面真正用到的 `loss / rank / cand / loss_single / rank_single / agree`
  + 包级 `version/worlds/depth/root/k/top/seed`（用于在 UI 里说明「3 世界 × 定深 4」的近似性），
  数值**不做任何舍入**（显示时才 `aiFmt` 取整）⇒ **无损**。
- ⚠️ 迁移脚本会自检「**页内那份逐字等于 `ai_deep_pack.json`**」⇒ 防「改了包忘了重跑迁移」。
- ⚠️ 包内字面量绝不能含 `</script` 或 `<!--`（`pack_deep` 有断言，内嵌进 `<script>` 会炸）。
- ⚠️ **换一批深核产物后必须重跑这两步**；否则页面还挂着旧包（状态行照样显示「内嵌包」，数值却是旧的）。
- ⚠️ `localStorage` 全程 `try/catch`：file:// 或隐私模式下不可用时**静默降级**（内嵌包仍是主路径，
  状态行会写「未写入本地记忆」）。单份包 > 1.2 MB 不记（免得挤爆配额）。

**UI 落点**
- 状态行 `#aiDeepStatus` **必须写明来源**：`已加载深度复核（内嵌包/本地记忆/导入）：本局复核 N 步`。
- 「忘记已存的包」= 清掉 `导入` + `本地记忆`，**保留内嵌包**（页面资产）。
  ⚠️ `filter` 里保的必须是 `p.src === '内嵌包'`。写成 `!==` 会**反着清**（内嵌包被删、导入包留下，
  状态行还理直气壮显示「导入」）—— 本轮踩过，而且**测试差点没抓住**（见 26.10 的断言）。
- 失误榜与徽标必须把**两个口径分开写**：`🔍 单步 176 → 搜索 45`，并给翻案/加重加标记
  （`sgl>=8 && loss<8` ⇒ 「搜索复核后翻案」；反向 ⇒ 「搜索复核后加重」）。
  ⚠️ 两套 loss 数值**巧合相同**时最易误读（实测有「单步 157 → 搜索 0.0」与
  「单步口径：实际得分 0.0」并列）⇒ 文案必须带**口径前缀**，别只写数字。
- 行棋记录的 🔍 徽标 `title` 也要带 `单步 X → 搜索 Y`，悬停即可看到两口径。

### 26.9 ⚠️⚠️ QQ 桥的两个「口径陷阱」（会让对齐看起来失败）

⓵ **方位必须用 `.jgs` 自带的 `rep.orient`**，**不是** `DEFAULT_ORIENT`。
   实测 `junqi2025_10_25_16_40.jgs` 的 meta =「上:黄 右:蓝 下:绿 左:紫」⇒ `rep.orient`
   = 绿=down / 黄=up / 蓝=right / 紫=left；而 `DEFAULT_ORIENT` = 绿=up / 黄=down / 蓝=left / 紫=right
   —— **恰好差 180°**！后果：Python 算出的「前进方向」实为**后退** ⇒ 位置项反号 ⇒
   与页面 `aiRes.steps[i].loss` 差恒 **1.2 = 2 × W_ADV(0.6)**，且**只在纵向走法上显形**
   （横向走法不吃位置项，看着「一致」⇒ 极易误判成「只有个别步有问题」）。
   ⚠️ 方位名是**几何座位**（up = 上方），环 up→left→down→right 与「哪个颜色坐哪」无关
      ⇒ 换映射**不会**破坏行棋序与闸门判定（实测：闸门仍 8/8，联众 2379 局误差**逐位不变**）。

⓶ **走法生成器必须注入 `moves_strict`**（页面同款严格铁路模型）。
   `whatif.GEN_MOVES` 的默认值是引擎原生**宽松**版（`junqi_engine.gen_moves`）⇒
   候选集大小 `n` 差 1、`loss` 跟着差。实测：不注入 **105/263 步**不一致，注入后 **0**。
   （`ai_deep_review` 内部有 `inject_strict()`；**自己写探针时最容易漏这一步**。）

⇒ 由此新增正式验收 **`align_qq_20260926.py`**（对应联众侧的 `align_ai_eval_20260926.js`）：
   页面 dump（`dump_qq_steps_20260926.js`）+ Python 重放 + 逐字段比较 ⇒ **8 局 1448 步 0 差异**。
   判据必须**精确相等**（容差会同时掩盖末位差与「差 1.2」这种系统性偏移）。
   ⚠️ Python 侧 `simulate` 的 step 是 `{no, side, …, ev:{loss,n,rank,actual,best}}`，比较前
      **必须扁平化**。忘了扁平 ⇒ 全 None ⇒ 报 7240 处不一致（纯属探针自己的错，白查半天）。

**QQ 事件行的 turn 推进**：事件行自带方位（`[no,'event',kind,side]`，`event_info` 的 `actor`）
⇒ 三处重放（`replay_drive` / `run_whatif` / `ai_deep_review`）统一写成
`cur = actor or turn; turn = next_alive(cur, alive)` —— 有声明就**不靠方向表推导**，
取不到（旧联众 `[no,'giveup']`）才退回，保持既有行为逐位不变。

### 26.10 测试更新（第二轮）

- `verify_aideep_task2_20260926.js` 重写为 **19 项**（三页各 19/19）：自动加载（**零操作**）/
  🔍 徽标数 == 「本局被复核且存在于行棋记录」的步数 / 内嵌包 vs 源产物逐位一致（精简无损）/
  **JS 单步 `loss` == 包内 `loss_single`**（把逐位对齐搬到**页面里**复验）/
  清空包栈后无 🔍 且状态「未加载」/ 重新装配可复现 / 导入覆盖内嵌 / **重载页面后本地记忆自动生效**
  （跨会话路径）/ 忘记后回落内嵌包。
- `verify_aieval_task2_20260926.js` **27 → 29 项**（三页各 29/29）：新增
  「**内嵌包不含本局时诚实说明**」（改掉原「默认未加载」——有包无本局不再是「未加载」）、
  「导入写入本地记忆」、「忘记清掉本地记忆」。⚠️ 该脚本刻意挑**不在内嵌包里**的棋谱（排序最后一个）
  ⇒ 两条测试分工互补，**别合并**。
- ⚠️ 每个测试**起点都要清本地记忆**（`aiDeepDropLS(); aiDeepPacks=[]; aiDeepBooted=false`），
  否则上一个测试导入的包会在下一个测试里被自动加载，断言就成了「测别人的残留」。
- ⚠️ 该脚本参数改走 `path.resolve`（与 `verify_mobile` 同口径）：**绝对路径与裸页名都能传**。
  曾用 `path.join(BASE, argv)` ⇒ 传绝对路径会被拼坏。

### 26.11 实拍（`shoot_aideep_20260926.js`）
产出 `crop_aideep_addon_20260926.png`（AI 卡 + 自动加载状态行 + 忘记按钮）、
`crop_aideep_addon_dark_20260926.png`、`crop_aideep_mistake_20260926.png`（失误榜，含「单步 → 搜索」与翻案标记）、
`crop_aideep_movelist_20260926.png`（行棋记录，**第 59 步能同时看到 `AI −171` 与 `🔍 32` 两个徽标**）、
`shot_aideep_mobile_20260926.png`（390px，`scrollWidth == clientWidth == 390` 无溢出）。
⚠️ 两个截图坑：① `#moveList` 是**滚动容器**，`page.screenshot({clip})` 会拍到空白 ⇒
用**元素截图** + 临时 `maxHeight`；② 深核只复核 loss 最高的 12 步（都在中后盘）⇒
**必须先滚到第一个 🔍 徽标**，否则前 15 步一个 🔍 都没有、看不出「两列徽标」。

### 26.12 ⭐⭐ 「页面内现算」：PIMC 深核移植成纯前端 JS（第三轮，2026-09-26）

**动因（坚哥实测反馈）**：内嵌包只覆盖**预生成过的 8 局**，加载别的棋谱时状态行只能诚实说
「已加载 1 份深度复核数据，但其中没有本局（按来源文件名匹配：xxx.jgs）」。这是**覆盖面缺口**，
不是匹配 bug。解法（坚哥选定）：把整个 PIMC 深核**移植成纯前端 JS**，页面加按钮，任意棋谱现算。

- 新文件 `.workbuddy/ld/ai_deep_core.js`（≈800 行，**零第三方依赖**，`file://` 可跑）。
  内容 = `junqi_engine` 的 `resolve_move`/`apply_move`/`casualties` + `whatif.InfoSet` 的采样口径
  + `search.Searcher` 的 `evalRaw`/`order`/`root_scores` + `ai_deep_review.pimc_step`/`review_replay`
  的逐行移植，外加**分片执行**（每步 `setTimeout(0)` 让出主线程，否则长棋谱会把页面冻住、连进度都刷不出来）。
- UI（`ai_review_ui.js`）：`⚡ 本局现算` 按钮 + 三档 `快/标准/深` + `中止` + 进度文案
  （`aiLiveOpts()`：fast `{2,2,6,6,8}` / std `{3,4,8,8,12}` / deep `{4,6,12,10,16}`）。
  算完走 `aiApplyDeep(res, '现算 · '+file, '现算')`，`src='现算'` ⇒ 排进包栈首位、覆盖同局内嵌包、
  并写入 localStorage（下次打开自动带上）。中止是约定值 `null`，UI 显示「已中止现算」而**不是**「失败」。
- **std 档参数与内嵌包生成参数逐字相同**（worlds 3 / depth 4 / root 8 / K 8 / top 12 / seed 11）
  ⇒ 这正是下面那条黄金对照能成立的前提。
- ⚠️ 现算结果必须与离线报告**逐值相等**；这是本项目的硬纪律（「同一局面两个分」是最贵的 bug）。
  实测：`verify_aideep_golden_task2_20260926.js` 三页各 **113/0（8 局）**。

### 26.13 ⚠️⚠️⚠️ 页面里跑 PIMC，必须补一层「端到端黄金对照」（本轮共 6 个**静默** bug，本节 3 个）

> 另 3 个同类静默坑：**RNG 不是 MT19937**（26.14）· **快照取在走子之后=混合态**（26.15）·
> **内嵌包 `seed + i`**（26.16）。**六个都不报错**，只有「键集合 + 逐位数值」的端到端对照能一次性逼出来
> ⇒ 教训可泛化：**凡把 Python 算法搬进页面，验收终点必须是「页面输出 ≡ 离线报告」，而不是「单元测试都绿」。**

**教训**：此前已有三层验证，但**全部绕过页面的输入管线**：
`align_ai_eval`（单步层 60 局 11776 步）、`align_deep`（喂**同一个世界**比分数）、
`align_rng`（rng 序列）——它们证明的是「**单元**是对的」，证不了
「页面喂进深核的东西、以及把结果挂回**哪一步**，都是对的」。

**补法**：内嵌包 `ai_deep_pack.json` 是 **Python 引擎**在**同一批 `.jgs`** 上用
**与 std 档完全相同的参数**算出来的 ⇒ 「⚡ 本局现算 · 标准」的输出**必须逐值等于内嵌包**。
新脚本 `verify_aideep_golden_task2_20260926.js`（三页各 113 项；比 **键（步号）集合** + 数值）。
⚠️ **比「键集合」是关键**——bug ③ 的表现是「loss 多重集完全正确、但每条挂到了别的步上」，
只有键级比对能抓到。

三个 bug 的**共同点：全都不报错**（`loss ≥ 0` / `rank ≥ 1` / `cand ≥ 1` / 零 pageerror 全过）：

| # | bug | 症状指纹 | 修法 |
|---|---|---|---|
| ① | capture 钩子把 `alive/cmdr/fp/info` 的**引用**交给深核 | 深核永远拿**终局状态** ⇒ `evalRaw` 首行 `if (!oppLive()) return AD_WIN` 恒真 ⇒ 所有候选同分 ⇒ **`loss ≡ 0.0`** | 按值快照（见 26.15） |
| ② | `info` 是**颜色**键、深核要**方位**键 | `pool[方位]` = undefined ⇒ `remaining={}` ⇒ 世界原封不动（采样退化成恒等映射） | 新增 `adInfoToDirs(info, orient)` 翻键 |
| ③ | 挑步用 `steps` 的下标去索引 `captures` | **loss 多重集全对，但每条结果挂到别的步**（🔍 标注的评估与那一手不是同一手） | 建 `capByI[c.i] = c` 显式映射 |

- ③ 的机理：`steps` 每一行 `replay.moves` 都占一位（事件行 / 起点无子行各 `push(null)`），
  而 `captures` 只有**真正走了一步**的行才有快照 ⇒ 错位量 = 该步之前所有占位行的数量，
  **随棋局推进单调增长**（实测某局 +2 → +3 → +6）。
- 给这类「不报错的错误」加了**自检字段**：`adLiveReview` 返回 `degenerate`
  （= 所有步 loss 都是 0 且确实有步被评过）。验收脚本据此断言
  「多数步 loss > 0」+「`degenerate === false`」——**范围断言在退化实现下也全过**，
  必须直接断言「loss 不是全 0」这个方差指纹。

### 26.14 ⚠️⚠️⚠️ `adRng` 必须**逐位复刻 CPython `random.Random`**（MT19937），不能用 mulberry32

- 初版用 mulberry32（「统计上等价」的思路）。**深核采样层对 rng 顺序敏感**
  ⇒ 页面现算与离线报告**从第一个世界起就不同**（实测同一步 loss 23.3 vs 50.2、`agree` 也翻）。
- 必须逐位复刻的**五个环节**（差一个，流就从某处整体错开，且**不报错**）：
  ① seed 展开 = `init_by_array` + `key` = 绝对值的**小端** 32 位字表（`bits==0 ⇒ 1 个字`）；
  ② `random()` = `(gen()>>5)*2**26 + (gen()>>6)` 再除 `2**53`（27 位 + 26 位拼装）；
  ③ `getrandbits(k) = gen() >> (32-k)`；
  ④ `_randbelow(n)` = **拒绝采样** `r = getrandbits(n.bit_length())`，`r >= n` 重抽；
  ⑤ `shuffle` = **倒序** Fisher-Yates + `_randbelow(i+1)`（`j = floor(random()*(i+1))` **不是**同一件事）；
  ⑥ `choice(seq) = seq[_randbelow(len(seq))]`。
- 验证脚本：`align_rng_20260926.py`（dump CPython 权威序列）+ `align_rng_20260926.js`
  （页面里按**同样的用例顺序**重算）⇒ 43 用例 / 688 数值**逐位一致**。
- ⚠️ 迁移副作用：页面现算数值**会变**（变成与离线一致的那一组）——这是**修好**，老 mulberry32 数值无基准意义。
- `adScriptedRng`（按 dump 的调用序列回放）**保留**：它是「消费错位」（JS 分支 ≠ Python）
  的**更早**报警器，比数值比对更早定位。

### 26.15 ⚠️⚠️ capture 钩子：**「走子前的状态」必须一次性取全**

`ai_eval_core.js` 里 `aiAnalyze(replay, analysis, opts)` 的 `opts.capture` 钩子
（**只增不改**：不传时返回值与历史版本逐位相同——60 局 11776 步 0 差异仍成立）。

- ⚠️⚠️⚠️ **整组快照必须在走子之前取**。初版只把 `layout` 放在走子前，
  而 `info`/`alive`/`cmdr`/`fp` 的快照写在了 `observe()` 与状态维护**之后**
  ⇒ 深核拿到「**走子前的棋盘 + 走子后的信息集与存活状态**」这种**混合态**。
  后果同样是静默数值漂移：采样层用「比自己多推了一步」的 `touched` 判 `fresh`
  ⇒ 先验权重错 ⇒ 世界不同；`alive/cmdr` 提前一步 ⇒ `evalRaw` 的胜负短路与亮旗威胁项错。
  **实测某局第 1 手就现形**：Python `touched` 为空、JS 已有 `{4,8;4,9}`。
  ⇒ 纪律：凡「走子前的状态」，**一律在同一个位置一次性取全**，别分散到函数两端。
- ⚠️ `alive/cmdr/fp/infos[side]` 都是**全程共享的可变对象** ⇒ 必须**按值快照**
  （`info` 需拷 `pool`/`known`/`touched`/`origin`；`init_by_side`/`prior_cells` 构造后不变可共享引用）。
  **只快照行棋方那一个 InfoSet**（复核也只需它），四个全拷是 4 倍无用功。

### 26.16 ⚠️⚠️ 内嵌包必须**统一 seed**（`seed + i` 是个隐形不一致）

`ai_deep_review_20260926.main()` 里写的是 `seed=seed + i`（i = 局在批次里的序号）
⇒ 内嵌包第 i 局实际用 **seed = 11 + i**，而页面现算固定 `seed: 11`
⇒ **只有批次第 0 局对得上**（黄金对照实测：8 局里恰好只有 `41junqi…` 全绿）。

- 为什么不是「让页面也用 seed+i」：页面无法可靠知道「这一局在生成批次里的序号」，
  手动导入的包也不该依赖这个隐形契约。**统一 seed 才是可复现的契约。**
- 修法：新脚本 `.workbuddy/ld/regen_deep_pack_20260926.py`
  → 读 recs jsonl → `review_replay(..., seed=11)`（**不加 i**）→ 直接复用
  `pack_deep_20260926.slim` 写出 `ai_deep_pack.json`（旧文件自动备份 `.bak_pre_fixedseed_20260926`）。
  ⇒ 之后**必须**重跑 `migrate_aieval_20260926.py` 重嵌三页，再跑黄金对照。
- ⚠️ `export_recs_for_deep_20260926.js <out.jsonl> <src> [limit]` 的 `<src>` 可以是**单个 `.jgs`**
  （目录则按 `readdir` 排序取前 limit 个）。批次顺序 = 内嵌包的局顺序。

### 26.17 第三轮测试与命令（`index_task2/3.html` + 新 `index.html` 三页同跑）

```
# 单元级（都必须绿）
node align_ai_eval_20260926.js          # 60 局 / 11776 步 / 事件步 98 ⇒ 0 差异（capture 零影响）
node align_deep_20260926.js             # 12 样例 / 36 世界 / 322 分数 ⇒ 逐位一致
node align_rng_20260926.js <页面> /tmp/py_rng.json     # 43 用例 / 688 数值 ⇒ 逐位一致
# 端到端（三页各跑）
node verify_aieval_task2_20260926.js <页面>            # 29 项（AI 复盘层总验收）
node verify_aideep_task2_20260926.js <页面>            # 19 项（预生成包自动加载三层）
node verify_aideep_live_task2_20260926.js <页面>       # 33 项（⚡ 本局现算端到端）
node verify_aideep_golden_task2_20260926.js <页面>     # 113 项（8 局，现算 ≡ 离线包 逐值）
# 全量回归（16 脚本；含 verify_mobile 56 / run_e2e 202 / run_board_index 71 …）
zsh .workbuddy/tests/_regress_aieval_20260926.sh
# 装配与语法
python migrate_aieval_20260926.py && python check_js_blocks.py
```
- ⚠️ **黄金对照与现算验收必须三页同跑**（`index.html` / `index_task2.html` / `index_task3.html`）：
  AI 层三页同构（`index.html` 多「竞技技术积分」块）；`migrate_aieval_20260926.py` 也是一次嵌三页
  ⇒ 只跑 task2 会漏掉竞技版的回归。
- ⚠️ **`verify_aideep_live` 的时序纪律**：运行态相关断言**不得**用「点完 sleep 固定毫秒再取快照」。
  「快」档实测 40~70 ms 就跑完，固定 sleep 会**恰好错过整个窗口**，把 4 条断言一起误报失败
  （那是**测试侧时序**问题，不是产品缺陷）。正确做法：
  ① 同步读的（按钮禁用 / 中止显隐）在 click 的**同一个 evaluate 里**读；
  ② 异步发生的（曾进入运行态、曾出现进度文案）用**页内 `setInterval(2~4ms)` 记 `everXxx`**；
  ③ 需要外部介入的（中止）用**页内紧轮询**，一见到条件就动作，不赌固定延迟。
- ⚠️ 诊断三件套（定位本轮三个 bug 的正是它们，**留着复用**）：
  `_diag_steps_js_20260926.js`（页面全部步的 `no/i/loss` 序列）+ `_diag_steps_20260926.py`（对比挑步口径）；
  `_diag_world_20260926.js` + `_diag_world_py_20260926.py` + `_diag_world_cmp_20260926.py`
  （逐字段比**棋盘 / 输入状态 / 世界 / 候选序 / 分数**，含**全步 series** 用于定位 `touched`/`known` 首个分歧点）；
  `_diag_rngoff_20260926.js`（把「①真实共享 rng / ②每步重建 rng / ③自己控制循环」三种调用并列打印，
  **一眼看出问题在单步采样还是在 rng 消费位置**）。

### 26.18 ⭐ 配合意识四项（Phase 4 · 2026-09-28 · 来自《四国军棋必胜秘籍》第八章）

> 承接 Phase 3 的 `SW_LINK`（§11.5 / §12），把「配合篇」四条理论落成 `search.py` 的四个协同项。
> 与 Phase 3 的关键差异：Phase 3 是「从复盘数据挖出 `focus` 再落成 `SW_LINK`」；
> Phase 4 是「从**理论书**直接提炼四条战术，逐条落成评估项」。

#### 四条理论 → 四项代码（`实战桥Windows版/app/search.py`）

| 书第八章理论 | 代码权重 | 默认值 | 口径 | 判定逻辑 |
|---|---|---|---|---|
| **双抢** | `SW_GRAB` | 6 | **精确几何** | 两家各一子逼近**同一**敌方军旗，且该旗已亮（司令已亡），两家曼哈顿距离都 ≤6 才给分 `grab·6/(1+max(d_self,d_ally))` |
| **协同防守** | `SW_SUPP` | 4 | **精确几何** | 队友的棋（归属方=队友）几何落在我方象限 ⇒ 渡子协防，双向对称 |
| **组合进攻** | `SW_COMBO` | 3 | **静态近似** | 两家各 ≥2 子压**同一**敌象限才给 `combo·min(n_self,n_ally)`（与 `SW_LINK` 同构，但阈值 ≥2 区分「组合」） |
| **双急** | `SW_TWIN` | 2 | **静态近似** | 两家各一子逼近同一敌旗要点（≤4）给固定分（时序无法在单步还原，弱化降权） |

#### 三条铁律（动手前必读）

1. **四暗红线**：四项**全部只读 `board[(r,c)]` 的 `side`（归属方位）与坐标，绝不读兵种**。队友的棋「在哪」可见、「是什么」不可见。`eval_raw` 里靠 `cells_by_side`（每方位坐标列表）喂给四项，`need_coord` 判断是否收集。
2. **`side`（归属）≠ `region_of(r,c)`（几何）**：这是「协同防守」精确判定的关键——`side` 移动不变、`region_of` 移动后变。队友棋 `side=队友` 但 `region_of=我方象限` ⇒ 渡子协防。
3. **`regv` 依赖 trap**：`regv[(方位,象限)]=棋子数` 原只在 `need_reg = link>0` 时填充，而 `SW_COMBO` 也按象限计数 ⇒ **`need_reg` 必须写成 `link>0 or combo>0`**（已修），否则 combo 走脆弱的 fallback 计数。凡新增「按象限计数」的项，都要同步检查 `need_reg`。

#### 两类口径的边界（诚实标注）

- **精确判定**（`SW_GRAB` / `SW_SUPP`）：纯几何，单步 `eval_raw` 即可精确还原。
- **静态近似**（`SW_COMBO` / `SW_TWIN`）：书的「双急」是**跨回合时序**（A 手筋→C 再手筋→D 应接不暇），「组合进攻」含意图/时序，单步 `eval_raw` 无「上一手」信息 ⇒ 只能静态代理，**权重刻意压低**。这不是 bug，是信息集约束下的诚实近似。

#### 经验权重 vs 定权（当前状态，2026-09-28）

- **权重现状**：`SW_GRAB=6 / SUPP=4 / COMBO=3 / TWIN=2` 是**经验值**，让 AI 立刻表现出配合行为（坚哥定「先跑通」）。
- ⚠️ **尚未经 20 局镜像赛制显著性检验**。正式定权须走 §11.6 的 `mirror_match.py --mode grab|supp|combo|twin`，但该脚本与复盘数据（`replay_drive` / `mirror_*.log`）**都在 Windows 侧真机，Mac 侧未部署** ⇒ 本机无法跑定权，**待 Windows 侧有数据时补**。结论写回本表 + `search.py` 权重注释。
- ⚠️ 历史教训（§12）：Phase 3 的 `SW_LINK` 第一轮 n=2 显示正向，第二轮 20 局**反转不显著**。四项经验权重**不能**当已定权，同理要警惕小样本假象。

#### 自检与回归（本机已全绿）

- `test_coord_20260928.py`：11 项（每项正/负/边界 + **不泄漏兵种净贡献差分法** + **方位对称镜像换边**）全绿。
  - ⚠️ 「不泄漏兵种」**不能**直接比总分——`eval_raw` 里另有 `VAL` 子力项随兵种变；必须用**净贡献差分**（开权重−关权重的增量，两次换兵种增量相等）。
- 回归：构造四方开局棋盘，`Searcher.best_move` 在「四项开 vs 关」下均正常出着、节点数一致、无异常（开局无配合机会 ⇒ 四项贡献 0，符合预期）。
- ⚠️ `ai_search_dark.py` 的 `main()` 依赖 `replay_drive`（数据加载），本机缺该模块跑不起来——**与本次改动无关**，是数据链路本机未部署。

#### 命令速查

```bash
cd 实战桥Windows版/app
python search.py            # 打印权重：GRAB=6 SUPP=4 COMBO=3 TWIN=2
python test_coord_20260928.py   # 11/11 全绿
# 定权（Windows 侧有数据时）：python mirror_match.py --mode grab --n 20 --nodes 10000 --grab 6
```

## 27. 风行手册规则注入（Phase 5/6 · 2026-09-29 · 来自《四国军棋风行手册》）

> 承接 Phase 4（§26.18，来自《必胜秘籍》第八章），把《风行手册》里**必胜秘籍没有的增量规则**落进评估层。
> 分两批：**落点 A**（先验类，默认关 `WI_FENGXING`，零风险软 lift 修正）；**落点 B**（搜索类，默认关 `SW_SNIPE/SW_HUNT/SW_PIN`，镜像赛制定权）。
> 坚哥口径：先验增量「从复盘数据统计」，验证「两者都要」（先验类留出局 + 搜索类镜像赛制）。

### 27.1 落点 A：三条布阵/进营先验（`whatif.py`）

| 编号 | 规则 | lift 系数 | 触发条件 | 作用对象 |
|---|---|---|---|---|
| **A1** 双炸集路→雷少 | 两炸弹已公开且初始布局同路 ⇒ 该侧地雷降权 | `×0.6` | `len(public_bombs[side])>=2` 且两炸弹 origin 同 `_lane_of` | 该侧同路格 `地雷` |
| **A2** 进下营→邻位有雷 | 该下营 8 邻位地雷升权 | `×2.0` | `fresh`（初始格仍原位）且是下营 8 邻位 | `地雷` |
| **A3** 进营子→工兵/炸弹/司令 | 进过营的这枚棋本身 lift | 炸弹`×1.6` 工兵`×1.5` 司令`×0.85` | `origin[(r,c)] ∈ camp_enter_orig` | 未知格三兵种 |

**三个关键数据结构**（`whatif.py` `InfoSet`）：
- `self.public_bombs = {d: [] for d in DIRS4}`（L146）：已公开炸弹的**碰撞格**（`observe` 里记录）。
- `self.camp_enter_orig = set()`（L147）：**进过行营的子的初始格**（origin 标识）。
- `self.origin`（L125）：格 → 该格棋子的初始格，`_advance_public` 里 `origin[t]=origin[f]` 沿走子链更新，全程可观测（不读未公开兵种，四暗红线守住）。

**接入点**：`dist()` 在 `_apply_layout_rules` 之后、归一化之前 `if self.WI_FENGXING > 0 and p: p = self._apply_fengxing(...)`（L488-489）。

**开关**：`WI_FENGXING = float(os.environ.get("WI_FENGXING", "0"))`（L339，模块级，默认 0=关）。

### 27.2 ⚠️⚠️ 落点 A 两个真实 bug（本轮血案）

1. **A3 语义 bug（`fresh` 自相矛盾）**：旧实现 `if fresh and (r,c) in self.camp_enter_orig` —— 子动过才能进营，其初始格必已 `touched` ⇒ `fresh` 恒 False ⇒ **A3 从不触发**；且语义错位（应 lift「进营子这枚棋本身」的当前位置，不是「初始格」，初始格此刻已是空格/别子）。修法：`og = self.origin.get((r,c)); if og is not None and og in self.camp_enter_orig`（不要求 fresh，靠 origin 回溯定位进营子当前位置）。
2. **进营跟踪位置 bug（move 提前 return）**：风行跟踪 `camp_enter_orig.add(og)` 原写在 `observe` 里 `if res=="move": return` **之后**，而进营绝大多数是纯 `move` ⇒ 被提前 return 跳过 ⇒ `camp_enter_orig` 几乎恒空（实测 39 次进营全漏）。修法：把「进营跟踪」上移到 `_advance_public` 之后、`if res=="move":return` 之前。

**教训**：凡「走子后状态跟踪」代码，务必核对它是否落在 `return` 早退之后；凡「初始格 vs 当前位置」语义，务必想清楚 lift 对象是**谁**。

### 27.3 落点 B：三个搜索 SW 开关（`search.py`）

| 开关 | 规则 | 默认 | 判定逻辑 |
|---|---|---|---|
| `SW_SNIPE` 配合炸令 | 敌司令公开 + 我方炸弹可及 → 炸令 | 0（关） | 敌司令（采样世界）公开，我方炸弹曼哈顿距离 ≤6 反比加分 `snipe·6/(1+dmin)`；**对称扣分**：敌方炸弹贴我方司令 ⇒ 减分 |
| `SW_HUNT` 抓子定式 | 残局圈住敌弱子 | 0（关） | 敌子气数 `_empty_mobility` ≤3 且我方子邻位 ⇒ `hunt·(4-br)·adj` |
| `SW_PIN` 残局控制 | 己方强子牵制敌弱子 | 0（关） | 己方强子（司令/军长/师长）相邻敌弱子且 `VAL[己] > VAL[敌]·1.5` ⇒ `+pin` |

**实例级透传**：`Searcher.__init__` 新增 `snipe=None, hunt=None, pin=None`（None 时取模块级开关），`eval_raw` 用 `self.snipe/hunt/pin`。`ai_search_dark.py` 的 `PIMCPolicy` 透传三权重。

**四暗红线**：三项都只读「位置 + 归属方位 + 采样世界已确定兵种」，绝不读未公开兵种。`need_fengxing = (self.snipe>0 or self.hunt>0 or self.pin>0)` 才收集坐标。

**开关语义**：`snipe/hunt/pin` 是**权重**（>0 开），`float(os.environ.get(...))` 默认 0=关，环境变量可覆盖。

### 27.4 验证结论（留出 + 镜像赛制）

- **等价性**：`whatif.py` 5 局 228 未知格 0 差异（默认关零漂移）；`search.py` 8 局 `eval_raw` 逐位一致 0 差异。
- **落点 A 留出局**：整体 top1 +0.30pp、对数概率 +0.66%；触发级分解 A2 99.6%（245 次）强先验、A1 62.5%（16 次）、A3 32.4%（1157 次）弱先验（方向正确）。
- **落点 A 单元**：`probe_fengxing_A_clean.py` 15+ 项全 ✓；**落点 B 单元**：`probe_fengxing_B_clean.py` 9 项全 ✓（含 SW_SNIPE 对称扣分 Δ=-2.0）。
- **落点 B 镜像赛制 20 局**（`mirror_fengxing_B.json`，K=2/npw=4000/steps=300/jobs=8）：
  - 胜负 W14/L10/D16，符号检验 **p=0.5413 未达显著**。
  - 配对净子力差 Δ：合计 +3430、均值 +171.5，t=1.32 **p=0.1868**、Wilcoxon **p=0.4248**，均未达显著。
  - 稳健性：正/负 = 11/9（55%），方向二项 p=0.412；**中位数仅 +38**（均值 +171.5 被两个极端正值 +1192/+1200 拉高）。
  - **结论：三个 SW 开关方向偏正但效应微弱、未达统计显著 ⇒ 默认保持关闭（诚实负结果）**。
  - 历史先验类参照 `mirror_prior.json`：W18/L10/D12，p_t=0.011、p_w=0.027（连续口径显著）——先验类在 Δ 上显著，搜索类三开关不显著，两者差异符合「先验软修正比搜索启发式更稳」的预期。
  - ⚠️ 教训：snipe/hunt/pin 让 eval_raw 每步三重遍历，镜像赛制从历史 13.5 分钟涨到 27.5 分钟；**定权前先想清楚权重是否值得这么重的评估**。

### 27.5 命令速查

```bash
cd 实战桥Windows版/app
# 落点 A 单元（新语义）
python /tmp/probe_fengxing_A_clean.py
# 落点 B 单元
python /tmp/probe_fengxing_B_clean.py
# 等价性
python /tmp/probe_fengxing_equivalence.py      # whatif 5 局
python /tmp/probe_fengxing_B_equivalence.py    # search 8 局
# 镜像赛制（轻量口径，与 mirror_prior.json 对齐）
cd .workbuddy/ld && python pimc_mirror.py --n 20 --steps 300 --npw 4000 --worlds 3 --K 2 --depth 8 --exp-snipe 1.0 --exp-hunt 1.0 --exp-pin 1.0 --seed 7 --json mirror_fengxing_B.json
```

---

## 28. 人机对战（1 人类 down + 3 AI 四暗 · 2026-09-29）

> 需求（坚哥原话）：「实战桥增加人机对战功能，即一个人类玩家与 3 个 ai 一起下四暗军棋，ai 用最高难度。」
> 四条已确认口径：**人类固定 down** · **全自动推进** · **严格四暗** · **PIMC 深核 think=24s**。

### 28.1 文件与三条新增 API

| 文件 | 作用 |
|---|---|
| `app/human_vs_ai.py`（**新**，~700 行） | 对局引擎：`HumanVsAI` 步进式状态机 + `random_layout()` 四方合法布阵 + `_selftest()` |
| `app/live_bridge_server_20260925.py` | `_hva()` 懒加载 + `VS`/`VS_LOCK`/`VS_ERR` 容器 + **4 条路由** + `_vs_call()` 统一兜底 |
| `app/四国军棋实战桥.html` | `vsSect` 侧栏 + `vsClick()` / `vsDrive()` / `vsNew()` / `loadVsLegal()` / `submitVsMove()` |

| 路由 | 语义 |
|---|---|
| `POST /api/vs/new` | 生成四方布阵 → 建会话，**停在布局阶段**（`started=False`）。可选 `step` / `max_delays` |
| `POST /api/vs/swap` | 布局阶段互换**本方**两枚棋子（试换→校验→不合法回滚） |
| `POST /api/vs/start` | 布局完成 → 正式开战（第一手 `up`）；开战后不能再换子 |
| `POST /api/vs/legal` | 人类某格合法落点 |
| `POST /api/vs/move` | **只走人类一步**（`auto=False`） |
| `POST /api/vs/step` | **只推进一家 AI**（`advance_ai(max_steps=1)`） |
| `POST /api/vs/timeout` | 步时到点回调：记一次延时（用满 ⇒ 判负）。入参 `{n: 步号}` |
| `POST /api/vs/resign` | 人类主动投降 ⇒ 判负 |
| `GET  /api/vs/state` | 全量状态（会话不存在时带 `active:false` + `reason`） |
| `GET  /api/vs/replay?n=k` | 终局回看第 k 帧（0 = 开局；缺省 = 末帧）。**必须是 GET** |

⚠️ **必须走 `/api/vs/step` 逐步驱动，不能让 `/api/vs/move` 一次跑完 3 家**：
3 家深核各最长 24s ⇒ 单请求阻塞 **70s+**，浏览器黑屏干等、且中途没有任何可观察状态。
逐步驱动下**每落一子立刻上屏**。实测：`auto=0` + `stepped=1` 逐家（43 项 e2e 有断言）。

⚠️ **`/api/vs/*` 用独立的 `VS_LOCK`，绝不持有 `TABLE.lock`** —— 深核最长 24s，
蹭到 `TABLE.lock` 会卡死普通录入模式的并发请求。

### 28.2 ⚠️⚠️ 四暗口径：**`reveal_winner` 开关（默认 True 保深核；人机对战用 False）**

> **2026-09-29 口径更新（坚哥需求 2：四暗碰撞后胜方不显示兵种）** —— 本节早期版本写的是
> 「赢家翻开是有意为之，别当 bug 修」，那句话**只对深核/复盘分析成立，对人机对战已不成立**。
> 现在用 `whatif.InfoSet(reveal_winner=...)` 显式分开，**两套口径并存且互不干扰**：

| 场景 | `reveal_winner` | 理由 |
|---|---|---|
| 深核分析 / 复盘分析 / 三页 AI 层 / 113 项黄金对照 | **True**（默认） | 历史口径：碰撞后参与者公开（赢家翻开）。**改它会让 113 项全漂** |
| 人机对战（`HumanVsAI`） | **False** | 真实四暗：**胜方也不显示兵种**，双方信息对称 |

⚠️ `InfoSet.__init__` 默认值**必须保持 `True`**；只有 `human_vs_ai.HumanVsAI.__init__`
（默认 `reveal_winner=False`）会传 False。**别把默认值改掉**。

`False` 的实现要点（`observe()` 的碰撞分支）：
```python
keep_atk = (not self.reveal_winner) and survivor == aside
keep_dfd = (not self.reveal_winner) and survivor == dside
if atk_new and not keep_atk: self._unpool(aside, atk)
if dfd_new and not keep_dfd: self._unpool(dside, dfd)
```
⇒ 幸存方**既不写 `known` 也不出 `pool`**，`sum(pool[side]) == len(unknown)` 恒成立，
**不会**触发 `inconsistent`。若只改成「不写 known」而不保留 pool，就会自相矛盾。

⚠️⚠️ **显示层与信息集解耦**：`HumanVsAI.human_view()` **恒不读** `info.known` ——
自己的 25 枚明棋、其余一律盖棋。这样任何开关都不会让前端漏出对方兵种。
（因此「用 HTTP 层断 `reveal=True` 时人类视角会出现敌方明棋」**永远不成立**；
   该开关的分辨力由引擎自检第 ⑫ 条**逐值**证明：True→`known` 有值 / False→None。）

**渲染保真判据不变**：测「严格四暗」时以「后端 `cells` vs DOM 逐格一致」为准。

### 28.3 后端 `state()` 必须与 `Table.state()` **同构**（前端零改动复用的前提）

`HumanVsAI.state()` 补齐：`side` / `seats` / `colors` / `platform` / `platform_name` /
`dir_cn` / `view_rot` / `base_cells` / `order` / `next` / `round` / `msg` / `engine`。
四暗无平台配色表 ⇒ 用固定映射 `{"蓝":"up","红":"down","绿":"left","灰":"right"}`。
⚠️ `"last"` 必须是 **`[fr,fc,tr,tc]`**（与 `Table.state()` 一致）；
曾写成 `list(self.history[-1])` —— 那是 **dict 的键名列表**，
前端 `markMove('fr','fc',…)` 会把字符串当坐标算 ⇒ 路径箭头全乱。

### 28.4 ⚠️⚠️⚠️ 血案一：**前端有两份，服务端原先优先服「项目根下的旧构建产物」**

`live_bridge_server.HTML_CANDIDATES` 原顺序是 `[PROJ/…, HERE/…]`，而 `PROJ` 跨**两级**（`ld` 的遗留口径）：

- 本机从 `实战桥Windows版/app/` 起服务 ⇒ `PROJ` = **项目根** `<…>/qq军棋复盘分析/`；
- 那里躺着一份 `build_live_ui_20260925.py` 生成的**旧产物**（`四国军棋实战桥.html`，110749B）。
- ⇒ 浏览器拿到旧页面（**改完刷新看不到变化、新按钮不存在**），而 `make_bridge_portable`
  的 `HTML_SRC` **也从根版取源** ⇒ 新功能**静默不进 zip**。
- 实测铁证：那份旧 zip 内 HTML `sha256=b59ecfe3…`/110749B，`grep -c 人机对战` = **0**。

**修法三件套（缺一不可）**：
1. `HTML_CANDIDATES` 改成 **同目录优先**（`[HERE/…, PROJ/…]`）——「跟服务端同目录的那份」才是配套前端。
2. `make_bridge_portable.HTML_SRC` 取**工作树**，并新增 `pick_html()`：
   两份**不一致就拒绝打包**（报出双路径 + sha8 + 对齐办法），**不静默挑一个**。
3. 打包源 `ld/` 与工作树 `app/` 也要逐个 `sha8` 比对（新增 `check_drift()`）——
   实测 `live_bridge_server` 在两边差 5439 B（app 有新的人机对战 API，ld 还停在旧版）。

⚠️⚠️ **`rmtree` 顺序铁律**：`--out` 默认就是 `<PROJ>/实战桥Windows版`（= 工作树本身）。
   所以 `check_drift()` / `pick_html()` / **前端字节读进内存** 三者都必须**早于 `rmtree(out)`**，
   否则工作树被删空 ⇒ `os.path.exists()` 全假 ⇒ 断言**恒通过（假绿）**，
   而且会在「拷到一半」崩、把工作树留在「有 app/*.py、没 HTML」的残废状态（本轮真踩）。
   回归守卫：`verify_portable_guards_20260925.py` 断源码里三者的 `index()` 都 `< rmtree` 的 `index()`。

### 28.5 ⚠️⚠️⚠️ 血案二：**烟测会静默打到上一轮的旧服务上**

`bridge_launch_20260925.py` 用 `subprocess.call` 把真正的 server 起成**子进程**再等它；
旧烟测 `proc.terminate()` **只杀启动器** ⇒ 服务子进程存活、端口一直被占
⇒ 下一轮烟测新服务 `bind` 失败退出，请求**全打上一轮的旧服务**
⇒ 表现为莫名其妙的 `RemoteDisconnected`（跑到第 N 节才炸），极难归因。

**修法**：① `Popen(..., start_new_session=True)` + `_kill_tree()` 杀**整个进程组**；
② 开测前 `_port_busy(PORT)` 前置闸门，端口被占**直接 FAIL** 并给清理命令。
负样本实测：抽掉包内 `human_vs_ai.py` ⇒ 6 项 FAIL、**不崩**、无残留进程。

### 28.6 ⚠️ 懒加载模块缺失 ⇒ 必须回可读 JSON，不能掐断连接

`_hva()` 在首次 `/api/vs/*` 时才 `import human_vs_ai`。包里漏了它（或它依赖的
`prior_init.json` / `ai_search_dark` 缺失）时，异常在 handler 里抛出
⇒ `BaseHTTPRequestHandler` **直接断连** ⇒ 浏览器只报 `Failed to fetch`
（用户看到「按钮点了没反应」——正是本项目历史症状）。
**修法**：`_vs_call(fn, b)` 统一兜底，`ImportError` 单独说清**缺哪个文件** +
`hint` 指向「重新生成便携包」；`/api/vs/state` 也回报 `reason`。
前端 `api()` 把 `j.hint` 挂到 `Error.hint` 上，`vsNew()` 的 catch 一并显示。

### 28.7 测试与命令

```bash
P=/Users/wangjian/.workbuddy/binaries/python/versions/3.13.12/bin/python3
N=/Users/wangjian/.workbuddy/binaries/node/versions/22.22.2-3/bin/node
APP=实战桥Windows版/app

# ⚠️⚠️ 铁律（2026-09-29 事故）：**8765 是坚哥的常驻口**。
#    测试一律用 8771 / 8772（vs 与普通模式各一个）· 便携烟测 8897~8899。
#    **不要 kill 8765**（他浏览器开着页面，杀了立刻 `Failed to fetch`）。

# 引擎自检（22 组：布阵 100 子 / 布局互换 / 严格四暗 / 自动落子 / 非法拒斥 / 回看帧一致 /
#           投降判负 / 无棋可走判负 / 步时延时判负 / 终局回看四方全明 / 未终局回看防守 /
#           思考档区间与夹上限 / 布阵随机 / 司令阵亡⇒军旗亮出 / 开场无标记 / 每步抽样落到 PIMCPolicy /
#           ㉒ 布阵合理性（大本营≤连长且禁炸弹/工兵 · 雷后≤旅长 · 含 4 个手工负样本））
$P $APP/human_vs_ai.py --selftest          # ⚠️ 必须带 --selftest；不带是「跑一局演示局」，要几分钟

# 铁路规则「页面侧原码对拍」（516 组逐格 0 差异；负样本 100/516 组不一致）
$N .workbuddy/tests/verify_rail_parity_20260929.js
$P .workbuddy/tests/probe_rail_parity_20260929.py

# ── 起测试服务 + 跑测试 + 收服务，**必须写在同一条命令里** ──
#    （`( nohup … & )` 起完就返回的写法会被回收，下一个命令打过去时它已经死了 —— 实测）
cd $APP && $P live_bridge_server_20260925.py --port 8771 > /tmp/b8771.log 2>&1 & SVC=$!; sleep 4; \
  cd .workbuddy/tests && PORT=8771 $N verify_vs_v4_20260929.js; kill $SVC

# 后端冒烟（⚠️ **规范版在 .workbuddy/tests/，别用 /tmp 的旧副本**）
PORT=8771 $P .workbuddy/tests/vs_v6_smoke_20260930.py  # 第六轮 47 项：档位区间/开场无标记/回看摊牌/旗显现
PORT=8771 $P .workbuddy/tests/vs_v7_smoke_20261001.py  # 第七轮 18 项：布阵合理性（含**真数据注入负样本**、无炸弹/无工兵）
$P /tmp/vs_v4_smoke_20260929.py            # v4 回归 27 项
$P /tmp/vs_v3_smoke_20260929.py            # v3 回归 45 项（步时/延时/投降/闸门）
$P /tmp/vs_v2_smoke_20260929.py 8766       # v2 回归 42 项

# 前端 e2e（真实 DOM 点击；跑完看 .workbuddy/tests/vs4_*.png）
PORT=8771 $N verify_vs_v4_20260929.js      # 第四轮 28 项：档位区间 · 换阵 · 回看全明
PORT=8771 $N verify_vs_flagshow_20260930.js # 第六轮 22 项：开场无标记 · 司令阵亡⇒旗亮（金描边）
PORT=8771 $N verify_vs_20260929.js         # 第一轮 76 项
PORT=8771 $N verify_vs_timer_20260929.js   # 第二轮 45 项：倒计时 / 延时 / 投降

# 全量回归（92 项，普通录入模式）
mkdir -p /tmp/e2e92 && cd .workbuddy/ld && $N bridge_e2e_20260925.js \
    --url http://127.0.0.1:8772/ --out /tmp/e2e92
#   ⚠️ `--out` 目录**必须先建**：否则第一张截图 ENOENT ⇒ 脚本中途退出（只跑 19/92 就没了）

# 便携包烟测（第六轮 74 项，含 vs 组；端口 8897~8899）
cd .workbuddy/ld && $P smoke_portable_20260925.py --pkg <目录> --port 8899
# 打包闸门负样本（正/负样本均有分辨力）
$P .workbuddy/ld/verify_portable_guards_20260925.py

# 打包前必跑：先对齐，再打包
$P .workbuddy/ld/sync_bridge_frontend.py            # 前端三处检查（drift ⇒ 退出码 1）
$P .workbuddy/ld/sync_bridge_frontend.py --apply    # 备份后对齐
#   ⚠️ 同步器**只管前端**；`.py` 要自己回灌（改了哪个拷哪个，二进制 cp，零行尾转换）：
for f in human_vs_ai.py live_bridge_server_20260925.py junqi_engine.py whatif.py; do
    cp -p $APP/$f .workbuddy/ld/$f; done
$P .workbuddy/ld/make_bridge_portable_20260925.py   # 打包（内部也会断言一致）
# 终极证据：unzip 到隔离目录，对**包内**再跑一遍烟测

```

⚠️ **`kill` 在 zsh 下不做词分割** ⇒ `kill $PIDS` / `kill $(lsof -ti :8766)` 会把整串当**一个** pid，
报 `illegal pid: 930\n86562`。正解：`xargs`（按空白分割）或 `while read`。

⚠️⚠️ **清端口禁止一刀切 `pkill -f live_bridge_server_20260925.py`** ——
**8765 是坚哥的常驻服务**（他浏览器里开着页面），一刀切会连它一起杀掉，
页面立刻报 `连不上后端 /api/state：Failed to fetch`
（**2026-09-29 23:09 真实事故**：收尾清理端口时误杀 8765，坚哥当场来问）。
**按端口精确清，只清测试口**：

```bash
for p in 8766 8770 8897 8898 8899; do lsof -ti :$p 2>/dev/null | xargs -n1 kill -9 2>/dev/null; done
lsof -nP -iTCP:8765 -sTCP:LISTEN   # 8765 必须仍在；若空，按下面拉起来
```

**Mac 侧拉起 / 自检 / 修复（首选一键脚本，2026-09-30 新增）**：

```bash
cd .workbuddy/tests
$P restart_8765.py          # 只诊断：①端口 ②**进程 cwd == 工作树** ③前端本轮标记 ④后端行为指纹
$P restart_8765.py --fix    # 诊断 + 有问题时按端口精确重启 + 自动复验
# 端口可覆盖：JUNQI_8765_PORT=8771 …（**只为构造负样本自测**，生产别带）
```

> 为什么四项都要查：**「进程活着」≠「代码是对的」**。
> ① 端口通不代表代码新；② `cwd` 是抓「跑在废纸篓旧副本」的唯一手段（实录见 §28.19）；
> ③ 前端每次请求读盘 ⇒ 只能证明 HTML 新；④ **后端 `.py` 走 import 缓存、只有重启才换逻辑**
> ⇒ `think_level` 这类**行为指纹**才是后端版本的可信判据。
> 负样本已验证：把 `app` 复制到 `/tmp` 再从那儿起 ⇒ ①③④ 仍绿、**② 单独报红**（检查有分辨力）。

手工拉起（脚本不可用时）：

```bash
P=/Users/wangjian/.workbuddy/binaries/python/versions/3.13.12/bin/python3
$P -c "import subprocess;subprocess.Popen(['$P','live_bridge_server_20260925.py','--port','8765'],cwd='实战桥Windows版/app',stdout=open('/tmp/bridge8765.log','wb'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,close_fds=True)"
sleep 4 && curl -s http://127.0.0.1:8765/api/state | head -c 80   # 期望 platform=lz / phase=setup
```

> ⚠️⚠️ **不要用 `( nohup … & )`**：本沙箱里它**起完就返回、下一条命令打过去时已经死了**
> （8771/8765 各实测一次）——「同命令 curl 通」是假象。正解 = `subprocess.Popen(start_new_session=True)`。
> ⚠️ 启动后必看 `platform`：若返回 `platform=vs` 说明**端口上还是旧的人机对战会话**。

⚠️ **服务陈旧会伪装成大面积回归**：第一轮 e2e 出现过 `方位 down≠up`／`本方阵地可放格 25 个→0`
这类「像代码坏了」的失败，根因只是 8765 上还跑着上一版进程（返回的是**人机对战** state）。
**看到「整个平台都错」先查进程与端口**。

### 28.8 ⚠️ 本轮两条「探针」教训（期望过期时改测试更正常）

1. **别硬编码「100 枚 / 75 盖棋 / 25 明棋」**：`/api/vs/new` 现在停在**布局阶段**（0 步、
   100 枚），但一旦开战 AI 先手、之后会有阵亡与扛旗清场 ⇒ 数字天然对不上。
   正确判据 = **后端 `cells` 与 DOM 逐格一致**（渲染保真）+ 盖棋必须**无兵字**。
2. **「点完立刻判 `myTurn`」是假绿**：点击是**同步**进 `submitVsMove`（先置 `vsBusy`、再发请求），
   此刻 `S.myTurn` 还是上一轮的 `true` ⇒ `waitForFunction("myTurn")` **当场满足**。
   正解：**两段等待** —— 先等 `myTurn` 变 **false**（请求已受理），再等它回 **true**（AI 走完）。
3. 人类那一步在流水里是**最后一条**（前面已有 AI 先手的两步），不是第一条。
4. ⚠️⚠️ **`S.vsBusy` 是双重语义**：「正在处理」**且**「禁止一切操作」
   （`vsSwapClick` / `vsStart` / `vsClick` 开头都 `if (S.vsBusy) return;`）。
   旧版靠末尾的 `vsDrive()` 顺带清掉；改成「只建局不开战」后没那一步 ⇒
   **`vsNew()` 的 `.then` 里必须显式 `S.vsBusy = false`**，否则布局阶段**点击全部失效**
   （点棋子没反应、点「开始对战」也没反应；e2e 实测 `sel=null / hl=0`，随后 180s 超时）。
5. **`vsDrive()` 必须一起判 `S.vsSetup`**：布局阶段后端 `advance_ai()` 直接返回 0（不推进），
   只看 `myTurn` 会让它**无限自调**（每轮 step 都不落子）⇒ 前端空转打满 CPU。

### 28.9 打包后的「三处 sha 一致」判据

**工作树 / 发布版 / 包内解包** 三处 HTML 的 sha256 必须相同。
⚠️ **别把指纹记死**（每次改动都变）—— 现算法：
```bash
shasum -a 256 实战桥Windows版/app/四国军棋实战桥.html 四国军棋实战桥.html
unzip -p 实战桥Windows版.zip 实战桥Windows版/app/四国军棋实战桥.html | shasum -a 256
```
⚠️ 打包**前**的备份（`*.bak_pre_*`）里是更早的快照，**本来就该不同**，别当成分叉。
最终证据链：**解包 zip → 隔离目录跑烟测 66/66**。
参考值（2026-09-29 第三轮收口，仅供比对进度）：HTML 143769 B / `be909839`、
zip 257314 B、`grep -c 人机对战 使用说明.txt` = 5。

### 28.10 工具：一键对齐（`sync_bridge_frontend.py`）

```bash
python3 .workbuddy/ld/sync_bridge_frontend.py           # 只检查；drift ⇒ 退出码 1
python3 .workbuddy/ld/sync_bridge_frontend.py --apply   # 备份后以工作树为准覆盖两边
```
它同时管两件事：**前端**（工作树 → `<PROJ>/四国军棋实战桥.html`）与**运行时**
（工作树 → `.workbuddy/ld/`，清单从 `make_bridge_portable.APP_FILES` 读，不手抄第二份）。
备份名带**序号**（`*.bak_pre_sync_YYYYMMDD[_NN]`），同日多次对齐不互相覆盖 ——
第一次留下的那份往往正是「分叉前」的证据。
实测：检查 → drift(1) → `--apply`(0) → 复检全绿；负样本（改坏发布版）确实报 drift。
⚠️ 只用 `rb`/`wb` 二进制读写（`newline=None` 会跨平台改行尾）。

⚠️⚠️ **`ld/` 是打包的「源」，工作树 `app/` 是「产出」** —— 但历史上多轮只在工作树改、
`ld/` 没回灌（本轮实测 4 个文件分叉：`junqi_engine` / `whatif` / `human_vs_ai` /
`live_bridge_server`，ld 侧缺的是**前两轮**的改动）。
**回灌前必须先做 AST 级「ld 无独有符号」验证**（`ast.parse` 取顶层 def/class/赋值名做差集），
确认工作树是**严格超集**才敢覆盖 —— 否则可能把只存在于 ld 的增强反向抹掉。
`check_drift()` 只比 sha，**不告诉你谁更全**。

⚠️⚠️ **打包前必须把 `.bak_pre_*` 备份挪出工作树**：`make_bridge_portable --out` 默认就是
`<PROJ>/实战桥Windows版`，它会 **`rmtree` 整个目录**。
备份是「测试有分辨力」的唯一对照物 ⇒ 先 `cp` 到 `.workbuddy/tests/bak_<日期>/` 再打包。

### 28.11 铁路走法：**有向弧线**模型（坚哥需求 1）

> 原话：「工兵在铁路上可任意行走，其它棋子在铁路线上只能直走或经过弧形线，不能转直角弯。」

`junqi_engine.gen_rail_moves` 原来**缺弧线约束**，按页面的 `railReachSet` 重写：

```python
RAIL_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]        # 上 下 左 右（索引与 ARC_DIRS 一致）
ARC_DIRS  = {(6,5):(3,2), (5,6):(1,0), (5,10):(1,0), (6,11):(2,3),
             (10,5):(3,2), (11,6):(0,1), (10,11):(2,3), (11,10):(0,1)}
```
- **工兵**：BFS 任意拐弯（`rail_neighbors` 连弧线两端）。
- **非工兵**：`ray()` = 「直行」；遇到 `ARC_DIRS[(r,c)][0] == 当前方向` 时可**拐一次**：
  跳到弧线对端 `rail_arc_partner`，然后**沿 arrive 方向继续直行**（`used_arc=True` 后不再拐）。
- 弧线**有向**：反向进弧 / 出弧后反向直行 = 掉头 ⇒ 全库零例，不实现。
- `seen_ray` 用 `(r,c,d,used_arc)` 去重防环。

**验证法 = 页面侧 JS 原码对拍**（不重写规则）：
`verify_rail_parity_20260929.js` 从 `index_task2.html` 用**非贪婪**正则切出 8 段 JS
（`RAIL_LINES`/`RAIL_ARC_LINKS`/`RAIL_DIRS`/`ARC_DIRS`/`railLinked`/`railArcPartner`/
`railNeighbors`/`railReachSet`）在 `node:vm` 里跑，扫 129 可停留格 × {工兵,非工兵} ×
{空盘,有阻挡} = **516 组**输出 `/tmp/rail_page.json`；`probe_rail_parity_20260929.py`
用完全相同场景跑 Python 侧逐格比对 ⇒ **0 差异**；喂**修正前引擎**（备份
`*.bak_pre_railfix_20260929`）⇒ **100/516 组不一致**（证明对拍有分辨力）。
⚠️ 切 JS 正则别用 `\n\];`（单行定义会一路切进页面主逻辑 ⇒ `document is not defined`），
用非贪婪 `\];` / `\};`。
⚠️ 加载 `*.py.bak_*` 备份要 `importlib.machinery.SourceFileLoader`（扩展名不是 `.py`，
`spec_from_file_location` 返回 None）。
⚠️ **改了 `gen_moves` 必须回归普通模式 92 项**（普通录入与 AI 建议同走这条链）。

### 28.12 布局互换 / 无棋可走判负 / 投降（坚哥需求 3、6、7）

| 能力 | 落点 |
|---|---|
| 布局互换 | 引擎 `swap(a,b)` + `/api/vs/swap` + 前端 `vsSwapClick()`；`/api/vs/new` **只建局**，`/api/vs/start` 才开战 |
| 无棋可走判负 | `human_has_move()` + `_settle_human()` ⇒ `END_NO_MOVE="no-move"` |
| 投降 | `resign()` + `/api/vs/resign` + `btnVsResign` ⇒ `END_RESIGN="resign"` |

**`swap()` 是「试换 → 校验 → 不合法回滚」**：换完立刻 `layout_violation()`，
不合法就把两格换回去并返回可读原因（`不能这样换：军旗只能放在大本营`）。
军旗换位还要同步 `flag_pos` 与**每个 AI 的 `policies[*].flag_pos`**。
合法的自身判据：军旗在本方大本营（`_hq_cells`）、地雷 `_local_line ≥ 4`、
炸弹 `_local_line ≥ 1`、且都在本方阵地内。

⚠️ **判负闸门必须收口**（同 §16 的 J 补丁教训）：
```python
def _settle_human(self):        # 在 advance_ai() / human_move() / begin() 末尾统一调用
    if self.over or self.turn != self.human: self.step_deadline = None; return False
    if not self.human_has_move():
        self._lose_human(END_NO_MOVE); self.snapshots.append(self._snap()); return True
    self._arm_clock(); return False
```
**别把「无棋可走」写进 `advance_ai` 的某个分支里** —— 以后新增「转回人类」的路径就会漏判。

⚠️ **判负语义**：人类 `down ∈ A_SET` ⇒ `_lose_human()` 置 `win="B"`，
并让 `state()["human_won"]` 报 False（**前端别自己按 `win==='A'` 推**，读 `human_won`）。

### 28.13 步时 20s / 延时 5 次判负（坚哥需求 5）

> 原话：「每步棋时间最多 20 秒，超过 20 秒未走动就延时一次，玩家一局棋延时 5 次自动判负。」

**计时的权威在后端**：`HumanVsAI.step_deadline` = **绝对截止时刻**（epoch 秒）。
`state()` 给 `deadline_left`（剩余秒数，前端换算成本地毫秒戳只做显示）；
前端 `vsClockSync/Tick` 每 200ms 刷新，到点回调 `POST /api/vs/timeout {n: 步号}`。
⚠️ **不能让前端计时器参与判负** —— 否则刷新页面 / 关标签页就能白嫖时间。

`human_timeout()` 三道防重放闸门（缺一不可）：
1. 未开战 / 已终局 / 不是人类回合 ⇒ 拒；
2. 传了步号且 `int(n) != self.n` ⇒ **上一回合的迟到回调**，拒；
3. `left > tol` ⇒ 早触发抖动，拒。`tol = max(0.15, min(0.75, step_limit*0.25))`
   （20s ⇒ 0.75s；短步长时按比例缩，否则拦不住「早触发」）。

延时语义：`delays += 1`；`delays >= max_delays` ⇒ `_lose_human(END_TIMEOUT)`；
否则 `_arm_clock()` **重置**再给一个完整步时。默认 `STEP_LIMIT_SEC=20` / `MAX_DELAYS=5`。
`/api/vs/new` 可选传 `step` / `max_delays`（生产 UI 不暴露；**测试靠它把 5 次延时压进几秒**）。

前端去重：`U.vsTmoTok = 步号 + ':' + 已用延时数`，同一档位只申请一次
（200ms 定时器会连着触发好几轮；后端也有闸门兜底，本地先挡避免打一串 400）。

### 28.14 终局回看 ⇒ **四方全明（摊牌）**（坚哥需求 4 + 第四轮需求 1）

引擎每推进一步 `snapshots.append(self._snap())`，第 0 帧 = 开局（`start()` 时存）。

**一份数据两种口径**（第四轮改法，别退回旧写法）：

| 状态 | `replay(n)` 返回 | 用途 |
|---|---|---|
| **已终局** | `_all_view()` 原样 ⇒ **四方棋子全明** + `reveal=True` | 复盘看全局（坚哥要的） |
| 未终局 | 把非己方压成 `"?"`（等价 `human_view()`）+ `reveal=False` | **防守**：防中途调接口偷看 |

- `_snap()` **一律存全明**（`_all_view()`：四方兵种写真名，`sorted(board.items())` 保证帧间稳定）。
- ⚠️ 摊牌**只发生在 `replay()` 且 `self.over`**：不要写进 `_snap()`（那样对局中就被偷看），
  也不要在 `state()` 里摊牌 —— **实时视角必须永远严格四暗**（e2e 有专门断言）。
- 前端在回看态标注「四方棋子全明（已摊牌）」（`vsReplayInfo` + `setHint`）。
- ⚠️ **投降 / 无棋可走 / 延时判负都会补最后一帧**（判负那一刻的盘面）⇒
  「投降后 frames 不缩水」的正确断言是 **`>= 之前 + 1`**，不是 `==`（第一版写错，改测试）。
- 前端 `render()` / `absorb()` **零改动**复用（cells 结构没变，只是兵种不再是 `"?"`）。
- 一局最多 1500 步 × 100 格 ≈ 20 MB，桌面端可接受。

### 28.15 ⭐ 第四轮三条（2026-09-29 晚 · 坚哥）

**① 回看四方全明** → 见 §28.14。

**② AI 思考预算：最高 10 秒**（原 24）。**难度 = 每步思考预算**，档位 **10 / 6 / 3 / 1 秒**：

- `human_vs_ai.py`：`MAX_THINK_SEC = 10.0` · `THINK_LEVELS = (10, 6, 3, 1)` ·
  `AI_KW["think_seconds"] = 10.0`。
- `HumanVsAI.__init__`：`self.think = min(max(t, 0.05), MAX_THINK_SEC)`
  —— **只夹上限、不抬小值**（自检 / e2e 用 0.4~1.0 秒，必须原样生效）。
- `state()` 新增 `think_seconds`。⚠️ **别叫 `think`** —— 那个字段已被占用为
  「AI 调用次数」统计（`{side: calls}`）；前端按 `think` 显示秒数会显示成 `0`。
- 前端 `#vsThink` 档位改 `10/6/3/1`、默认 10，开战/落子提示同步。
  ⚠️ 旧 e2e 里写死的 `s.value = '2'` 会失效（options 里没 2 了 ⇒ 落回默认）—— 已改 `'1'`。

**③ 每局布阵都要变**（原 bug：**局局一模一样**）。

- 根因：`/api/vs/new` 写成 `seed = b.get("seed", 0)`，而前端 `vsNew()` **根本不传 seed**
  ⇒ 恒取 0 ⇒ `random_layout(seed=0)` 每次生成同一套布阵。
- 修法：`seed = b.get("seed")`（`None` ⇒ `random.SystemRandom().randint(0, 2**31-1)`）；
  **显式传 seed 仍可复现**（测试与「重看某局」需要）。`state()` 回传 `seed` 与 `layout_seed`。

### 28.16 ⚠️ 第四轮四个坑（会重犯）

1. ⚠️⚠️ **别硬编码「25 明 / 75 盖 / 100 枚」**：只要 AI 已先手走过一步，途中**可能有碰撞吃子**
   ⇒ 场上少子（实测 74 ≠ 75，我的断言先 FAIL）。判据要写成
   ①「己方 0 盖 + 他方 0 明」②「DOM 与后端 `cells` **逐格**一致」（渲染保真）。
   §28.8 已记过一次，这轮又踩 —— 数字越小越诱人写死。
2. ⚠️⚠️ **点「🏳 投降」的 e2e 必须挂 dialog handler**：`vsResign()` 里有原生
   `confirm('确定投降？…')` ⇒ 不接 dialog 时渲染进程被阻塞，
   报 `Input.dispatchMouseEvent timed out`（症状：前几节全绿，到投降这节崩）。
   正解 `page.on('dialog', d => d.accept())`；launch 时加 `protocolTimeout` 更稳。
3. ⚠️ **`bridge_e2e --out DIR` 的 DIR 必须先 `mkdir -p`**：否则第一张截图 `ENOENT`
   ⇒ 脚本中途退出（exit=2、只跑了 19/92 就没声了，看着像「大面积回归」）。
4. ⚠️⚠️ **起后台服务的姿势（本轮踩两次：8771 与 8765 各栽一次）**：

   - **跑测试**（用完就收）⇒ 写进**同一条命令**：
     `… --port 8771 > log 2>&1 & SVC=$!; sleep 4; <跑测试>; kill $SVC`。
   - **要常驻**（如 8765 给坚哥用）⇒ `( nohup … & )` **不可靠** —— 实测起来后
     下一条命令打过去时它已经被回收了（命令里跑过长任务也一样）。正解 = **Python 起 + 新会话**：

     ```python
     subprocess.Popen([sys.executable, "live_bridge_server_20260925.py", "--port", "8765"],
         cwd=APP, stdout=open("/tmp/bridge8765.log", "wb"), stderr=subprocess.STDOUT,
         stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
     ```

     `start_new_session=True` 让它脱离工具清理时用的进程组（实测跨命令存活）。
   - ⚠️ **起完必须「跨命令」再查一次** `lsof -nP -iTCP:8765 -sTCP:LISTEN` ——
     别把「刚起好」当成「还活着」（本轮就是这么被骗的：同命令内 curl 200，下一条命令就没进程了）。
   - 且**永远不要用 8765 跑测试/烟测**（见 §28.7 铁律）。
5. ⚠️⚠️ **改了后端 `.py` 后，正在跑的服务不会自动换新代码**：`live_bridge_server` 是单进程，
   模块一旦 `import` 就进了 `sys.modules`（`_hva()` 还额外用 `_HVA` 缓存）⇒
   **必须重启服务**才生效。反过来，**前端 HTML 是每次请求读磁盘**（`do_GET` 里
   `open(p,'rb').read()`）⇒ 刷新浏览器就能拿到新前端。两件事别混：
   「刷新看不到变化」优先怀疑**服务是不是旧进程**，「前端变了但行为没变」多半是 **py 没重启**。

### 28.17 ⭐ 第六轮四条（2026-09-30 · 坚哥）

> 需求原话：①「开场大本营不要有标记」②「某方司令阵亡后，该方军旗翻现为明棋」③「最高难度 AI 行棋速度加快到 3 秒-5 秒」④「继续研究军棋复盘，强化配合能力，提升走棋合理性」。

#### ① 开场大本营不要有标记

- **病根**：`state()` 里 `flag_known` 写成 `d == self.human or d in self._open_flags()` ⇒ 己方旗位**恒上榜**
  ⇒ 前端 `render()` 给该格加 `.flagopen`（金色内嵌描边）⇒ **开局大本营那枚旗上就有一道金框**。
  实测（`probe_vs_open_20260930.js`）：开局唯一一个 `.flagopen` 坐标 = `flag_pos["down"]` = `(16,9)`。
- **修法**：`state()` 与 `replay()` 两处的 `flag_known` 一律
  `{d: [...] for d in DIRS4 if d in self._open_flags() or cm.get(d)}`（= **只列司令阵亡的方位**）。
  己方那枚旗本来就是**明棋**（明棋来自「己方全知」，与 `flag_known` 无关）⇒ 位置自明，不需要标记。
- **判据（正/负样本都要）**：
  - 负样本：开局 `flag_known == {}` **且 DOM `.flagopen` 数 == 0**；己方旗仍是明棋（`txt === '旗'`）但 `gold === false`。
  - 正样本：某方司令阵亡 ⇒ 该方位上榜、DOM 有且只有 1 个 `.flagopen`，坐标 == 后端 `flag_known[side]`。
  - 不变：**孤儿描边**（带 `.flagopen` 但不在 `flagKnown` 里）必须为 0。
- ⚠️ `verify_vs_flagshow_20260930.js` 里两条旧期望（「新局 flag_known 只剩自己」「flagopenCount == 1」）
  **本轮需求改了** ⇒ 改测试（改成「恒为 0」），**别动代码**。

#### ② 某方司令阵亡 ⇒ 该方军旗翻现为明棋（第五轮已落地，本轮复核）

- 口径收口在 `HumanVsAI._open_flags()`（`{d for d in DIRS4 if self.cmdr[d]}`）；
  `human_view()` / `replay()` / `state()["flag_known"]` **三处同源**（§28.2 的「闸门要收口」同理）。
- ⚠️⚠️ **坚哥这轮又把它列成需求 ⇒ 因为 8765 上跑的还是旧进程**（第五轮改完 `.py` 后没重启）。
  **改 `.py` 必须重启服务**（§28.16 第 5 条）——「代码对了但用户看不到」八成是这个原因。
- 实测（seed=41 / 21~22 步）：`up`、`right` 两方司令阵亡 ⇒ 各自**只亮「军旗」1 枚**、其余 23 枚仍盖；
  未亡方位 0 枚明棋；己方 25 枚（中盘 20 枚）全明不受影响。

#### ③ 思考档位 = **区间**（最高 3–5 秒）

- `MAX_THINK_SEC = 5.0`；`THINK_TIERS = ((3.0,5.0),(2.0,3.0),(1.0,2.0),(0.5,1.0))`；
  `THINK_LEVELS`（兼容旧名）= 各档**上沿** = `(5,3,2,1)`。
- `HumanVsAI(seed, level=None, think_seconds=None, ...)` **三选一**：
  - 显式 `think_seconds` ⇒ **固定预算、不抽样**（自检 / e2e / 复现用；`level` 置 `None`）
  - `level`（0 = 最高）⇒ 该档区间；**每步**在区间内抽样
  - 都不给 ⇒ 默认档 0
- 抽样实现：`_draw_think()`（RNG = `random.Random(seed*7919+13)` ⇒ **同 seed 同局逐值可复现**）
  \+ `advance_ai()` 里 `pol.think = self._draw_think()`
  （`PIMCPolicy.think` 在 `__call__` 内被读 ⇒ 改写即生效）。
- 后端 `/api/vs/new` 新增 `level` 参数（`think` 保留作**固定预算覆盖**，两者互斥、`think` 优先）；
  `state()` / `replay()` 增 `think_level` / `think_lo` / `think_hi`（`think_seconds` = 该档上沿）。
- ⚠️⚠️ **前端 `#vsThink` 的 `value` 改成「档位索引 0–3」**（❌ **不是秒数**）——
  凡「拿 value 当秒数显示」的地方必须改走 `vsThinkText()`；漏一处就会显示成「思考 **0** 秒」。
- 判据：四档 `(level, lo, hi)` == `(0,3,5)/(1,2,3)/(2,1,2)/(3,0.5,1)`；越界 level 夹住；
  `think=24` 与 `think=10`（旧值）都夹到 **5**；`_draw_think` 40 次抽样都在区间内**且非常数**；
  **同 seed 两次抽样序列逐值相等**；`advance_ai` 每推一家**恰好**调一次 `_draw_think`。

#### ④ 配合能力「实际影响」实测 + 镜像定权

- **工具扩展**：`pimc_mirror.py` 新增 `--exp-grab/--ctl-grab/…`（配合四项 + `link`，共 5 个权重可分别设；
  **不给 = 用 `search.py` 模块默认** `GRAB=6/SUPP=4/COMBO=3/TWIN=2/LINK=0`，**显式 `0` 才是关**）。
  `PIMCPolicy` 新增 `link/grab/supp/combo/twin` 实例级透传（打包成 `self.coord` 一次展开，
  免得两处 `Searcher(...)` 构造各写 5 个参数、漏一处）。
- ⚠️⚠️ **`pimc_mirror` 在本机曾经跑不起来**：数据集 `dataset.jsonl`（20 MB）只在 `ld/`，
  而 `sys.path` 把 `APP` 排在最前 ⇒ `replay_drive.DATASET` 解析成 `<app>/dataset.jsonl`（不存在）
  ⇒ `FileNotFoundError`。修法：`DATASET = os.path.join(HERE, "dataset.jsonl")` 并 `load_clean(..., path=DATASET)`。
- **探针**（`probe_coord_impact_20260930.py` · 10 局 / 76 决策点）：

  | 项 | 机会率 | 触发时均值 |
  |---|---|---|
  | `SW_SUPP` 协同防守 | **15.8%** | +4.67 |
  | `SW_GRAB` 双抢 | 6.6% | +10.51 |
  | `SW_TWIN` 双急 | 6.6% | +2.00 |
  | **`SW_COMBO` 组合进攻** | **0.0%** | — |

  - 任一项触发 **22.4%**；**决策分歧率仅 1.3%（1/76）** ⇒ 四项把走法改掉的机会极小。
  - ⚠️ **COMBO 是死代码**：门槛「两家各 ≥2 子压同一敌象限」在 76 个局面里 **0 次可达**
    （`max min(我压, 队友压)` 分布 = `{0: 71, 1: 5}`）；放宽到「两家都压（`min ≥ 1`）」可得 **6.6%**。
  - `GRAB/TWIN` 门槛偏严：两家到敌旗的 `max` 距离**中位数 11**，「两家都 ≤6」只 **6/84**。
  - ⚠️ 四项**只读归属方位 + 坐标**（四暗下的**公开信息**）⇒ 真实盘面的贡献与任何**采样世界逐值相同**，
    所以「真实盘面机会率」**不是近似**，也不需要采样。
- **镜像赛制**（`mirror_coord_20260930.json` · n=12 布局 / 24 局 · steps=220 · npw=2500 · worlds=3 ·
  K=3 · depth=8 · jobs=8 · offset=100 · **双方 `agg=borda`**；实验方 = 四项开 6/4/3/2 · 对照方 = 全关 0/0/0/0）：
  - 胜负 **胜 2 / 负 4 / 平 18** ⇒ 符号检验 **p=0.6875 未达显著**。
  - 配对净子力差 Δ：合计 **+742.0**、均值 **+61.8**（t 检验 p=0.6273、Wilcoxon p=0.6221，**均未达显著**）；
    页面口径 +362.0 / +15.1。非法着法 **0**。
  - **结论（诚实负结果）**：方向偏正但**效应微弱、未达显著** ⇒ 与「决策分歧率仅 1.3%」**互相印证**
    （改不动走法，自然也测不出强度差）。**默认权重不动**。
- **下一步（已量化、待验证）**：① COMBO 门槛放宽到 `min ≥ 1`（触发率 0% → 6.6%）；
  ② `GRAB` 距离上限 6 → 8。两项都**必须再跑一轮镜像**才算数（§26.18 纪律：经验权重 ≠ 已定权）。

#### 第六轮新增测试 / 工具

```bash
P=/Users/wangjian/.workbuddy/binaries/python/versions/3.13.12/bin/python3
N=/Users/wangjian/.workbuddy/binaries/node/versions/22.22.2-3/bin/node
$P .workbuddy/tests/vs_v6_smoke_20260930.py             # 后端 47 项（需求1/3 + 前几轮全部回归）
PORT=8771 $N .workbuddy/tests/verify_vs_v4_20260929.js       # 前端 26 项（档位改索引 + 区间文案）
PORT=8771 $N .workbuddy/tests/verify_vs_flagshow_20260930.js # 前端 24 项（旗显现 + 开场无标记）
$P .workbuddy/tests/probe_coord_passthrough_20260930.py # 6 项：四项是否**真的**透传到 Searcher
$P .workbuddy/tests/probe_coord_impact_20260930.py      # 机会率 + 门槛诊断 + 决策分歧率
cd .workbuddy/ld && $P pimc_mirror.py --n 12 --steps 220 --npw 2500 --worlds 3 --K 3 --depth 8 \
    --exp-agg borda --ctl-agg borda --exp-grab 6 --exp-supp 4 --exp-combo 3 --exp-twin 2 \
    --ctl-grab 0 --ctl-supp 0 --ctl-combo 0 --ctl-twin 0 --offset 100 --jobs 8 --json mirror_coord.json
```

#### ⚠️ 第六轮三个坑

1. ⚠️ **`whatif.ALLY[side]` 是「单个队友方位」（字符串），不是联盟集合** ——
   `Searcher(my_set=...)` 要的是**两家集合** ⇒ 必须用 `search.A_SET / B_SET`。
   误用 `frozenset('down')` = `{'d','o','w','n'}` ⇒ `KeyError: 't'`（`my_live()` 里炸）。
2. ⚠️ **「四项在开局贡献为 0」不是 bug** —— 开局没有配合机会（§26.18 已记）。
   别把它写成「权重没生效」的判别力断言；要造**正样本**（例：把队友一子挪进我方象限 ⇒
   `supp` 开/关的 `eval_raw` 差**恰好等于权重值**）。
3. ⚠️ **便携烟测 `--pkg` 要给「包含 `app/` 的那一级」**：`unzip` 后是
   `<tmp>/实战桥Windows版/app/…` ⇒ 传 `<tmp>/实战桥Windows版`；传 `<tmp>` 会
   `FileNotFoundError: <tmp>/app`。

### 28.18 ⭐ 配合门槛参数化 + 第二轮镜像（2026-09-30 午后 · 需求 4 跟进）

> 起因：§28.17 的「下一步」（COMBO 门槛 `min≥1`、GRAB 距离 6→8）本轮**做掉了**，并给了终判。

#### 工程：把「门槛」也变成自变量（否则没法做这个实验）
- `search.py`：模块全局 `SW_GRAB_R=6 / SW_TWIN_R=4 / SW_COMBO_MIN=2`（可被同名环境变量覆盖）；
  `Searcher.__init__` 加 `grab_r/twin_r/combo_min`（**None ⇒ 回落全局**）；`eval_raw` 三处字面量
  `<=6` / `>=2` / `<=4` 换成 `self.*`。
- `ai_search_dark.PIMCPolicy`：加同名三参并塞进 `self.coord`（`**self.coord` 一次展开 ⇒ **两处
  Searcher 构造自动同步**，这正是当初把它打包成 dict 的原因）。
- `pimc_mirror.py`：`--exp-grab-r / --ctl-grab-r / --exp-twin-r / --ctl-twin-r / --exp-combo-min /
  --ctl-combo-min`；banner 与 `--json`（`exp_coord/ctl_coord`）都记门槛。
- ⚠️ **改完必须回灌 ld**（`ld/search.py`、`ld/ai_search_dark.py`），否则打包器 `check_drift` 报错。
- ✅ **零行为变化怎么证（模板）**：`importlib` 把**备份版**与**新版**各加载成独立模块
  （`spec_from_file_location` + 手动塞 `sys.modules`），对同一批 (布局×联盟×权重) 逐值对拍
  `eval_raw()`。本轮 18/18 完全相等 + 默认门槛 == 旧字面量 `(6,4,2)`。
  **比“读代码确认”强**：它直接排除「某个分支忘了换」。

#### 探针：⚠️ **采样窗口会系统性扭曲机会率**（本轮最大的方法论收获）
- 旧 `probe_coord_impact` 只取**开局前几手** ⇒ 而「两家协同抢同一面旗」要等 `cmdr_dead`（司令阵亡）
  ⇒ 是**中后盘**现象 ⇒ **开局窗会把机会率低估到 0%**。
- 新增 `--window early|even|late`（**默认 `even` = 全程均匀**）。对比（72 决策点）：
  | 窗口 | grab | supp | combo | twin | 任一 |
  |---|---|---|---|---|---|
  | early（旧） | 0.0% | 6.0% | 0.0% | 0.0% | 6.0% |
  | even（新默认） | 4.2% | 9.7% | 0.0% | 5.6% | 15.3% |
  | even + 放宽门槛 8/6/1 | **13.9%** | 9.7% | **5.6%** | 5.6% | **25.0%** |
- **门槛诊断**（`min(我压,队友压)` 分布 = `{0:68, 1:4}`）⇒ 现行 `min≥2` **0/72 可达**（真死代码）；
  `min≥1` 才 4/72。GRAB/TWIN：两家到敌旗的 max 距离**中位数 11**，≤6 仅 4/77。
- ⚠️ **Q2 决策分歧率 0/72**（npw=400）：**即使触发也不改选步** ⇒ 量级相对主项太小。
  ⚠️ 低预算下的这个口径**不能外推生产预算**，终判只能交给镜像。

#### 镜像终判：放宽门槛 **仍然无显著增益**
- `--n 20 --offset 100 --steps 220 --npw 2500 --worlds 3 --K 3 --depth 8`（borda/borda，jobs=8，19 分钟）：
  实验方 = 四项开(6/4/3/2) **+ 门槛 8/6/1**；对照方 = **全关(0/0/0/0)**。
- **胜 5 / 负 4 / 平 31**，符号检验 **p=1.0000**；配对 Δ战略 合计 **−96**、均值 **−4.8**、
  t=−0.05 **p=0.9616**、Wilcoxon p=0.6215（首轮 +742 / +61.8 ⇒ 放宽后**方向归零**）。
- **功率**：SE 97.3 ⇒ 80% 功率最小可检出 **+272**；95% CI [−195, +186]。
  两轮合并（32 配对）均值 **+20.2**、CI [−129, +170]、最小可检出 **+214**。
  ⇒ 只能排除 **>+214 的大效应**；**小正效应测不出**。措辞必须是
  「**无证据表明配合项提升强度**」，**不是**「证明有害」。

#### 结论与下一步（**别再来回调权重/门槛**）
1. 四项照现定义（两家**同时**逼近同一敌旗/压同一敌象限）在真实局面**结构性罕见**，且**触发也不改选步**。
2. 放宽门槛让机会率翻倍（15.3%→25.0%）但强度不动 ⇒ 病根是**项语义**，不是阈值。
3. ⇒ **默认权重与门槛一律不动**（§26.18 纪律）。下一轮要继续攻配合，应**换语义**：
   候选 =「一家到位 + 另一家**威胁呼应**」的**时序/互补**判据（`eval_raw` 无「上一手」信息，
   需要把判据挪到带历史的层），或用复盘数据**学**一个「配合价值」监督目标。

#### 新增/改动测试与命令
```bash
P=/Users/wangjian/.workbuddy/binaries/python/versions/3.13.12/bin/python3
$P .workbuddy/tests/probe_coord_passthrough_20260930.py                # 10 项（含门槛透传 + 两个几何重算正样本）
$P .workbuddy/tests/probe_coord_impact_20260930.py --window even \
     --grab-r 8 --twin-r 6 --combo-min 1                               # 机会率/门槛诊断/分歧率
cd .workbuddy/ld && $P pimc_mirror.py --n 20 --offset 100 --steps 220 --npw 2500 --worlds 3 \
     --K 3 --depth 8 --exp-agg borda --ctl-agg borda \
     --exp-grab 6 --exp-supp 4 --exp-combo 3 --exp-twin 2 --exp-grab-r 8 --exp-twin-r 6 --exp-combo-min 1 \
     --ctl-grab 0 --ctl-supp 0 --ctl-combo 0 --ctl-twin 0 --jobs 8 --json mirror_coord_loose_20260930.json
$P summarize_mirror_20260925.py mirror_coord_20260930.json mirror_coord_loose_20260930.json   # 功率 + 合并
```

#### ⚠️ 本轮两个新坑
1. ⚠️ **探针的采样窗口是隐藏自变量**：只采开局 ⇒ 中后盘现象（司令阵亡后的协同）**必然测成 0%**，
   而你会误以为「这项是死代码」。**报机会率前先问：窗口覆盖了它可能出现的那一段吗？**
2. ⚠️ **「机会率提上去了」≠「强度提升了」**：机会率 15%→25% 的同时强度均值 −4.8。
   **两个口径必须分开报**，否则容易把「能让项触发」当成「项有用」。

### 28.19 ⚠️⚠️ 血案三：**8765 跑在废纸篓里的旧副本上**（「进程活着」≠「代码是对的」）

> 2026-09-30 16:30 坚哥报：`AI 落子失败：人机对战内部错误：
> TypeError: Searcher.__init__() got an unexpected keyword argument 'grab_r'`

#### 症状 vs 真相
- **症状**：只有**人机对战**报错，普通模式一切正常；`/api/state`、`GET /` 都回 200。
- **真相**：8765 那个 python 进程的 `cwd` =
  `/Volumes/me/.Trashes/501/实战桥Windows版 10-41-38-226/app`
  —— **一个已经被清掉、不存在的废纸篓目录**。进程攥着旧 inode 继续跑：那里的 `search.py` 是
  **旧版**（不认识 `grab_r`），同目录 `ai_search_dark.py` 却是**新版**（传 `grab_r`）
  ⇒ **半新半旧混搭** ⇒ `TypeError`。
  （这也解释了「为什么只有人机对战坏」：普通模式不走 `PIMCPolicy`。）

#### 为什么会这样（⚠️ **会复发**）
- 本机常驻两个同步客户端：**微云 `WeiyunResona`** + **UGREEN NAS `syncspace`**。
- `stat` 铁证：`实战桥Windows版/app` 的 mtime = `09-30 10:41:38`，
  而废纸篓目录名里的时间戳 = `10-41-38-226` —— **完全对应**。
  ⇒ 某次同步在 10:41:38 **把整个 `实战桥Windows版/` 重命名（带时间戳）丢进废纸篓、再落地一份新目录**；
  8765 是 10:26 起的，`cwd` 跟着旧 inode 走。
- **推论：「目录被替换」≠「进程换了代码」** —— 进程只在启动那一刻解析路径。

#### 诊断四项（缺一不可）——工具 `.workbuddy/tests/restart_8765.py`
| 项 | 查什么 | 为什么不能省 |
|---|---|---|
| ① | 端口有进程监听 | 只是底线 |
| ② | **进程 cwd == 本工作树** | 唯一能抓「跑在废纸篓/副本」的手段（`lsof -a -p <pid> -d cwd`） |
| ③ | `GET /` 含本轮标记文案 | ⚠️ 前端**每次请求读盘** ⇒ 它只能证明 HTML 新，**证明不了后端** |
| ④ | `/api/vs/new` 的**行为指纹**（`think_level` / `think_lo`） | ⚠️⚠️ **后端 `.py` 走 import 缓存、只有重启才换逻辑** ⇒ 这才是后端版本的**唯一可信判据** |

```bash
cd .workbuddy/tests
$P restart_8765.py            # 只诊断（退出码 0 = 全通过）
$P restart_8765.py --fix      # 按端口精确重启 + 自动复验
```

#### ⚠️ 三条通用教训
1. ⚠️⚠️ **别拿「进程活着 / 端口回 200」当验收** —— 要查**行为指纹**（新字段、新档位、新接口）。
   本轮若只看 `lsof`，会得出「服务正常」的**错结论**。
2. ⚠️⚠️ **同步工具会搬走工作目录**：`/Volumes/me/.Trashes/501/` 里出现
   `实战桥Windows版 <MM-DD-HH-mm-ss-mmm>` 就是迹象。改完 `.py` **必须重启**（刷新页面只够换前端）。
3. ⚠️ **清端口仍按端口**（`lsof -ti :8765 | xargs -n1 kill -9`）—— §28.7 铁律不变；
   本轮正是靠它精确换掉旧进程，没碰任何测试口。**不要**因这次事故改用 `pkill -f`。

#### 负样本验证（不做负样本的检查都是假绿）
把 `app` 复制到 `/tmp/appcopy` 并从那儿起 8771，再跑
`JUNQI_8765_PORT=8771 restart_8765.py` ⇒ **①③④ 仍绿、② 单独报红**
（`/private/tmp/appcopy` ≠ 工作树），退出码 1 ⇒ 检查**有分辨力**，不是只会打勾。

### 28.20 ⭐ 第七轮：**布阵合理性**（2026-10-01 · 坚哥）

> 原话：「AI 机器人的布阵存在问题，不能将大于连长以上的兵种放到大本营，
> 一般不将师长以上兵种放子地雷下方。」
> → 追加「大本营不能放炸弹」→ 再追加「工兵一般也不放大本营」。
> ⚠️ 三次追加 ⇒ 规则最终为 `HQ_BAN = ("弹", "兵")`，版本指纹据此从 `rl1` 递增到 **`rl2`**。

#### 为什么该有这条（不是拍脑袋，是引擎规则推出来的）
- `junqi_engine.is_hq(r,c)` 的格子 **永远不能移动**（`gen_moves` 直接返 `[]`）
  ⇒ 大本营里放大子 = **白废一个大子**；炸弹/工兵是**能走动**的子（工兵还能挖雷、铁路任意行），
  关进大本营同样是废 —— 故 `HQ_BAN = ("弹", "兵")` 一律禁
  （地雷无所谓 —— 它本来就不动，放底线/大本营都是标准做法，**故不禁**）。
- 地雷不可动 ⇒ 它**正后方**（更靠本方底线那格）放师长及以上 = 把大子**堵死在底线**。
- 而此前 `random_layout` 的 19 枚子是**纯随机**塞进剩余格（只受平台硬规则约束）。

#### 规则与实现（**收口点：只有一处实现**）
| 项 | 规则 | 常量 |
|---|---|---|
| 大本营（非旗格）| 军衔 ≤ 连长 **且禁炸弹 / 工兵** | `HQ_RANK_MAX` / `HQ_BAN` |
| 地雷正后方 | 军衔 ≤ 旅长（师及以上不放）| `MINE_BACK_RANK_MAX` |

全在 `human_vs_ai.py`：常量 `_RANK_S`（**简写**口径）/`HQ_RANK_MAX`/`HQ_BAN`/`MINE_BACK_RANK_MAX`；
几何 `_below_cell(side, rc, cellset)`；检查 `rationality_violations(side, lay)`
—— **自检 / 后端冒烟 / 生成自证共用同一函数**，避免「生成」与「检查」各写一份、各自漂移。

- `random_layout()`：先标「受限格」→ **拒绝采样**（500 次上限，仍失败就 `raise`，
  **不许静默退化成随便放**）→ 末尾 `assert not rationality_violations(...)`（**生成即自证**）。
- ⚠️⚠️ **炸弹必须单独处理**：它在「剩下 19 格」分配**之前**就落位了，`cap/ban` 根本管不到
  ⇒ 要在 `bomb_slots` 候选里就排除大本营格。**实测被自检第 ㉒ 组当场抓住**（这才叫有效断言）。
- ⚠️ **「后方」按己方视角**（up→r-1 / down→r+1 / left→c-1 / right→c+1），**不是屏幕坐标**。
- ⚠️ **仅约束 AI 的随机布阵**：`layout_violation()`（人类互换闸门）**不动** ——
  坚哥摆好后要换随他，只受平台硬规则约束。

#### 为什么只改人机对战、不改普通模式
`live_bridge_server.Table.random_layout()` 是**普通录入**用的「平台硬规则」口径
（注释：与平台/前端 `studyPlaceCheck` 一致），坚哥在那儿是手动摆 / 导入棋谱。
两条经验规则属**实战经验**，只约束 AI。若哪天要统一，**两处都要改 + 重跑 92 项 e2e**。

#### 版本指纹 `LAYOUT_RULE`（把 §28.19 的教训落地）
- `human_vs_ai.LAYOUT_RULE = "rl1"` 随 `state()` 下发；**改布阵规则必须递增**（rl1→rl2…），
  否则「改了代码没重启」会静默通过自检。本轮追加「禁工兵」时实际递增到 **`rl2`**
  （指纹机制第一次真正投入使用）。
- `.workbuddy/tests/restart_8765.py` 的 ④ 现在**同时核对 `think_level` 与 `layout_rule`**，
  且 `layout_rule` 期望值**直接从工作树 `human_vs_ai.py` 正则读**（改规则自动跟随，永不过期）。

#### 验证矩阵（本轮）
| 项 | 结果 |
|---|---|
| 引擎自检（新增 ㉒ 组）| 绿（10 seed × 四方正样本 + **4 个手工负样本** + 几何 + 边界）|
| 1000 seed × 四方 = 4000 份 | **违规 0**；大本营格落子只剩 **连 / 排 / 雷**（**炸弹、工兵归零**）|
| 后端 v7（新）| **18/18**（多 seed + 走终局回看验四方 + **真数据注入负样本** + 「无炸弹」「无工兵」）|
| 后端 v6 回归 | 47/47 |
| 前端 e2e | v4 28 项 ✅ · flagshow 22 项 ✅ |
| 普通模式 92 项 | 92 / 0（任务标 failed 只因 Chrome 清临时文件被沙箱拦）|
| 便携包烟测（解包 zip）| 74 / 74（包内 `human_vs_ai.py` sha 与工作树一致）|
| 8765 实拍 | 布局阶段文案渲染 ✅ · 自检 4/4（含 `layout_rule=rl2`，pid 随重启变）|

#### 三个新坑
1. ⚠️ **`cap/ban` 只作用于「剩下 N 格」** ⇒ 先落位的雷/弹要在**各自的候选集**里就排除受限格
   （否则「大本营禁放炸弹」形同虚设 —— 炸弹压根不走那条分配路径）。
2. ⚠️ **macOS 的 `grep` 不支持 `\|`**（要 `-E`）：本轮连吃两次空结果，白绕一圈。
   BSD grep 把 `\|` 当字面量 ⇒ 什么都匹配不到，**看起来像「字段不存在」**，极易误判。
3. ⚠️⚠️ **血案三重演（收尾时）**：改完 `rl2` 准备重启 8765 时，旧进程 `cwd` 又落在
   `/Volumes/me/.Trashes/501/实战桥Windows版 21-45-42-997/app` —— **微云 `WeiyunResona`
   又在收尾瞬间把整个 `实战桥Windows版/` 搬走了**。⇒ **收尾前一定先跑 `restart_8765.py` 诊断四项**，
   别假设「刚改完的代码就在跑」（本次 ②cwd + ④指纹 双双报 ❌，正好验中）。

#### 新工具
```bash
$P .workbuddy/tests/vs_v7_smoke_20261001.py       # 布阵合理性后端冒烟 18 项
$N .workbuddy/tests/shot_vs_layout_20261001.js    # 布局阶段实拍（puppeteer-core 绝对路径）
```


### 28.21 ⭐ 第八轮：**吸收「竞技军棋v4.2」的训练数据**（2026-10-01 · 坚哥）

> 坚哥原话：「读取 `/Users/wangjian/Downloads/竞技军棋v4.2` 中 AI 训练相关数据，
> 吸取训练内容，充实到我方训机器人经验，增强 AI 机器人能力。」

#### 这个包里到底有什么（先盘点再动手）
| 位置 | 内容 | 规模 | 处理 |
|---|---|---|---|
| `res/Bu/{Jin,Xin}/*.jql｜.JQL` | **QQ 布局文件（二进制）** | 324 | **✅ 全量吸收** |
| `Fu/*.jgs` | 对局录像（实为 `QQGame JQS` 头） | 14 局（56 布局块） | ⚠️ 解密未并入（见下） |
| `junqi_v7.pth` / `_internal/junqi_v4.pth` | PyTorch 权重 | 108 MB ×2 | ⚠️ 架构已解，权重不可用 |
| `res/output.txt` / `output2.txt` | 模型输出样本 | 192+221 行 | ⚠️ 无输入特征，零信息 |
| `_internal/res/` | 与根目录 `res/` 逐字节重复 | — | 忽略 |

`说明文档.txt` 原文：「队友对手皆为 AI。**以上万局复盘训练所得 AI** … 复盘文件在根目录的
『Fu』文件夹中。作者：Shrimp」⇒ 布局库定位 = **上万局复盘沉淀的棋手经验**。

#### ⚠️⚠️ `.jql` 格式（本包无任何文档，**必须逐字节破译**）
```
偏移 0x00  16 B  "QQGame JQL File\0"
偏移 0x10   4 B  固定 57 04 00 00（324/324 份一致）
偏移 0x14  30 B  布局矩阵（6×5 行主序，0 = 行营空位）
```
- 坐标 = **玩家自身视角**（`i=0` 前线 … `i=5` 底线；`j=0` 己方左手）——
  与三页 `mapLayout()` / `human_vs_ai._local_line()` **同口径**（实测大本营恒在局部 `(5,1)/(5,3)`）。
- 编码 = **与 `.jgs` 同一张 `QQ_PIECE` 表**（`index.html:2009`）：
  `0x02军旗 0x03地雷 0x04炸弹 0x05司令 0x06军长 0x07师长 0x08旅长 0x09团长 0x0A营长 0x0B连长 0x0C排长 0x0D工兵`。
  **自证三连**：`0x02` 100% 在底线、`0x03` 100% 只在后两排、`0x04` 前线 0 次。
- ⚠️ `find -name "*.jql"` 与 `glob("*.jql")` 在 **macOS 大小写不敏感**盘上会**重复计数**
  （`.JQL` 后缀 74 份）⇒ 正确总数 = 250 `.jql` + 74 `.JQL` = **324**。

#### 真实布局教义（273 份清洗样本，行 0=前线 … 行 5=底线）
| 兵种 | r0 | r1 | r2 | r3 | r4 | r5 |
|---|---|---|---|---|---|---|
| 司令 | **48%** | 8 | 11 | 11 | 20 | 3 |
| 师长 | 30 | 26 | 18 | 8 | 15 | 3 |
| 工兵 | 30 | 13 | 17 | 12 | 22 | 7 |
| 排长 | 18 | 9 | 13 | 17 | 7 | **36** |
| 炸弹 | **0** | 25 | **38** | 14 | 18 | 5 |
| 地雷 | 0 | 0 | 0 | 0 | 47 | **53** |
| 军旗 | 0 | 0 | 0 | 0 | 0 | **100** |

- **司令压前线 48%**（主流是司令当先锋强攻，不是龟缩）。
- **工兵上铁路前线**：热门格 `(0,1)/(0,3)/(1,2)` 各 ≈120 次 = 铁路入口 ⇒ 为「抢挖雷」铺路。
- **排长守大本营**（热门格就是 `(5,1)/(5,3)`）；**炸弹走中盘**（r2 38%，前线 0）；
  **地雷守旗**（热门 `(5,2)`=180，即军旗正上方那颗护卫雷）。
- 军旗落点：`(5,1)` 188 / `(5,3)` 136，**324/324 全在大本营**。

#### ★ 反向验证：坚哥第七轮的经验规则站得住
| 规则 | 真实布局里的实际内容 | 违规 | 合规率 |
|---|---|---|---|
| 大本营 ≤ 连长 · 禁炸弹/工兵 | 排207 · 雷90 · 连18 · 营7 · 团2 · **弹0 · 兵0** | 9/315 | **97.2%** |
| 地雷正后方 ≤ 旅长 | 旗135 · 排131 · 雷112 · 连36 · 营18 · 弹10 · 旅7 · 团7 · **师6 · 司3 · 军1** | 10/466 | **97.9%** |

⇒ 规则是**真实棋手的主流做法**，只保留我们的严格口径；**建库时先把那 3% 例外过滤掉**
（290 唯一 → **273 合规**），否则采样会撞上「生成即自证」断言。

#### 落地方案（`LAYOUT_RULE: rl2 → rl3`）
- 新增资产 **`app/layout_book.json`**（22 873 B：`{source,raw:324,unique:290,clean:273,layouts:[30 字串…]}`）。
  ⚠️ **必须加进 `make_bridge_portable` 的 `APP_FILES`** —— 缺它功能不崩，但 AI 会
  **静默退回旧生成器**（「负样本思维」：最容易漏的就是这种「不报错的降级」）。
- `human_vs_ai.py` 新增：`_load_layout_book()`（惰性 + 失败返 `[]` 兜底）、
  `_local_to_abs(side,i,j)`（与 `mapLayout()` 逐字一致）、`_book_layout(rng,side)`。
- ⚠️ **只做左右镜像**（`j→4-j`）：这是该 6×5 阵地**唯一**合法对称；
  **上下翻转会把行营 `(1,1)` 搬到 `(4,1)`（那格不是行营）⇒ 非法**。
- `random_layout()` 每方优先走库，采样后**仍断言** `rationality_violations` 为空。
- 自检新增 **㉓ 组**：库非空 + 抽检每份×四方合规 + **采样率 100%**
  （断言「**比例**」而不是「存在性」——防「只有一个 seed 走库」的假绿）。

#### 验证矩阵
| 项 | 结果 |
|---|---|
| 引擎自检（22 组 · 含 ㉓） | ✅ 「真实布局库采样(273 份·100% 命中)」 |
| 抽样 500 局 × 四方 = 2000 份 | ✅ 违规 0 · **100% 来自库** |
| 分布一致性 | ✅ 大本营 排67.0/雷27.6/连5.5%（真实 65.7/28.6/5.7）· 司令前线 47.5%（真实 47%） |
| 后端 v7 / v6 | ✅ 18/0 · ✅ 47/0（**新旧代码各跑一遍都 47/0**） |
| 普通模式 e2e | ✅ 92 / 0 |
| 便携包 + 解包烟测 | ✅ 281 383 B / 23 文件 · 74 / 74 |
| 8765 自检 | ✅ 4/4 · pid 52399 · `layout_rule=rl3` |
| **负样本**：`BOOK_FILE` 指向不存在 | ✅ ㉓ 立即抛 `AssertionError: 真实布局库为空…` |

#### 新坑（会重犯）
1. ⚠️⚠️ **「不报错的降级」最难查**：库文件缺失时 `random_layout` 悄悄退回旧生成器，
   功能全对、测试全绿 —— 只有「采样率 100%」和「库非空」两条断言能抓住。
   **凡是 `try/except` 兜底，就必须配一条「兜底没被触发」的断言。**
2. ⚠️ **场景巧合型断言**：v6 的「只亮军旗这 1 枚」写成数「可见枚数 ==1」，
   依赖「人类没撞过该方」；换成 rl3 后 seed=41 轨迹变了就假红。
   正解 = 换 **轨迹无关口径**：比较**司令阵亡那一步前后该方的可见枚数增量**（对手方恒 = +1）；
   **己方不适用**（自己 25 枚本就全明 ⇒ 增量为 0），改为断言「旗位公开 ⇒ 自己那方上榜」。
   另一半「flag_known」断言同理 ⇒ 改成 **`flag_known` 的键 == 恰好「司令阵亡」的方位集合**。
   ⚠️ **旧代码必须先跑一遍对照**，否则分不清「真回归」还是「期望过期」。
3. ⚠️ **`.jgs` 里的布局块**：偏移 **60/148/236/324（步长 88）**，每局 4 块。
   14 局 → 56 块 → 37 唯一 → 合规但**只有 13 份是新面孔**，且是 **AI 自战**布局
   （玩家名 `AI_orange/blue/green/purple`）⇒ **不并入**（会污染「真实棋手布局」口径）。
4. ⚠️ **多集校验别把占位符算进去**：建库时 `Counter(sh)` 忘了排除行营 `'0'`
   ⇒ 每份都判「编制不符」⇒ **290 份全被丢弃**（自检当时只报「过滤后 0」，一眼看不出）。

#### `junqi_v7.pth` 架构（本机无 torch，用自定义 Unpickler 解 `model_v5/data.pkl`）
- `model_type = tactical_v5_fixed` · epoch **86** · `best_val_combined=0.3038`
- 骨干：`input_conv`（**28 输入通道** × 3×3，96 filters）+ **16 个 `res_blocks`**（ResNet 风格）
- 多头：`from_pos`(289=17²) · `from_type` · `action` · `to_pos`(289) · `target_type`(13) ·
  `target_owner`(2) · `region`(14)
- 借鉴点：**28 通道棋盘编码**；把「走到哪 + 吃到谁(类型/归属) + 落在哪个区域」当**辅助监督头**；
  `to_pos_fc.bias`(289) / `from_pos_head` 偏置本身就是一份**「哪些格常被走」的先验**（可蒸馏）。
- ⚠️ 解 pth 的姿势：`pickle.Unpickler` 自定义 `find_class` 把 `torch._utils._rebuild_tensor*`
  换成 `lambda *a: a[2]`（= size），`persistent_load` 兜住 storage ⇒ 无需 torch 即可拿到**层名与形状**。

#### 新工具
```bash
$P .workbuddy/tests/build_layout_book_20261001.py "实战桥Windows版/app/layout_book.json"  # 建库（可重跑）
$P .workbuddy/tests/analyze_jql_20261001.py     # 解码 + 位置分布统计
$P .workbuddy/tests/analyze_jql2_20261001.py    # 针对经验规则的正负统计（大本营/雷后）
```


### 28.22 ⭐ 第九轮：**读取联众《布局库》4053 份 `.jqs`**（2026-10-01 · 坚哥）

坚哥一句话：「读取 `/Users/wangjian/Documents/联众布局`」。**只读不接**（接入需他选方案）。

#### 目录盘点
**4 大流派 / 69 个阵型组 / 4053 份 `.jqs`**（16 MB）。组名**自带语义**，是这批数据独有的价值。

| 一级流派 | 组数 | 文件 | 唯一 | 代表组 |
|---|---|---|---|---|
| 【Z】全能乱步 | 28 | 2131 | 2023 | 奇九百阵 900 · 全能布阵 299 · 自创棋谱 121 |
| 【Z】可攻可盘 | 22 | 1342 | 1167 | 二级阵型 319 · 慢棋两百 200 · 联众高手 177 |
| 【Z】能盘能龟 | 8 | 375 | 371 | 经典龟阵 148 · 乌龟楚少 101 |
| 【Z】大闪大攻 | 11 | 205 | 200 | 经典闪电 39 · 闪电阴阳 27 |

目录内**没有任何说明文件**（只有 `.jqs` + `.DS_Store`）。

#### ⚠️⚠️ `.jqs` 格式（**GL 魔数**，恒 1264 B）
```
0x00   8B   魔数 47 4C E9 03 CE 07 C4 02   （前两字节 = ASCII「GL」）
0x08  26B   时间戳 C 串 "Fri Aug 14 15:15:38 2026\n\0"
0x22   ~    署名区（含 ASCII "by "）+ 若干指针字段
0x64  i32   棋盘宽 17
0x68  i32   棋盘高 17
0x6C  17*17*4B  int32 棋盘（小端）：0=空，1..12=兵种
```
**自洽校验**：`0x6C + 17*17*4 = 108 + 1156 = 1264` —— 与文件长度**分毫不差**。
布局恒落在**下家区**：`abs_of("down", i, j) = (11+i, 6+j)`（行 11–16 / 列 6–10），
即 17 宽棋盘第 11 行第 6 列起 —— 等价于 `0x370 + r*0x44 + c*4`（坚哥转换器的写法）。
旁证：5 个行营格 `(12,7)(12,9)(13,8)(14,7)(14,9)` 在 **4053/4053 全为 0**；
2 个大本营格 `(16,7)(16,9)` **全部有子**；与三页 `BOARD_LAYOUT` 的 `C`/`H` 逐格吻合。

#### ⭐ 编码表：**先 grep，别硬破译**（血的教训）
> **`GL_PIECE` 表早就在坚哥自己的 `/Volumes/me/ai学习/四国军棋/四国军棋布局转换器.html` 里**
> （那里还实现了 `parseGLJQS` / `buildGLJQSBytes` / `GL_TEMPLATE_B64` 全链路读写）。
> 我的独立推导虽然全对，但**先去 grep 一遍能省一半时间**。

```
1司 10军  2师  3旅  4团  5营  6连  7排  8兵  9旗  11雷  12弹
```
推导路径（可复现）：频次分布（`1×3, 2×5, 3×4`）定「谁有几枚」→ 位置约束定身份：
- `9` → 大本营 100% ⇒ **军旗**；`11` → 后两线 100%、锋线 0% ⇒ **地雷**；`12` → 锋线 0% ⇒ **炸弹**
- 大本营（非旗格）占比 **排 54.6% > 雷 34.6% > 连 9.9%** ⇒ `7=排 11=雷 6=连`（`8=兵` 大本营 0.1%）
- 锋线率 `1` 44.6% vs `10` 25.0% ⇒ `1=司令 10=军长`

#### 全量校验（4053 / 4053，零异常）
长度恒 1264 · 魔数唯一 · 枚数恒 25 · 编制多重集恒为标准金字塔 · **行营非空 0 次** · **越界格 0** ·
军旗 100% 在大本营 · 地雷 100% 在后两线 · 炸弹锋线 0%。
**去重**：4053 → 唯一 **3602**（左右镜像合并 **3458**），最高重复仅 7 次（3 个局面）。

#### ★ 跨库交叉验证（两套解码器互证）
与第八轮「竞技军棋 v4.2」273 份库 **逐字重合 133 份**（镜像 132）。
两套**完全不同的解码器**（`.jql` 20B 矩阵 vs `.jqs` 17×17 int32 棋盘）产出**同一批简写串**
⇒ 互相验证通过。

#### ★ 坚哥两条经验规则：**第二语料再次验证**
| 规则 | 样本 | 违规 | 合规率 |
|---|---|---|---|
| 大本营（非旗格）≤ 连长，且禁炸弹/工兵 | 3602 | 31 | **99.14%** |
| 地雷正后方 ≤ 旅长 | 5002 | 166 | **96.68%** |

违规局面 184/3602（5.11%），两类都违规仅 7 个。违规构成：大本营 → 营19/司5/兵4/团2/弹1；
雷后 → 师83/司47/军36。对照第八轮 QQ 库 97.2% / 97.9% ⇒ **两平台同一棋理**。

#### ★ 四大流派「风格指纹」（**新维度**，QQ 库没有）
| 指标 | 全能乱步 | 可攻可盘 | 能盘能龟 | 大闪大攻 |
|---|---|---|---|---|
| 司令在锋线 r0 | 39.0 | **55.2** | 34.5 | **55.0** |
| 司令在后两线 | 18.0 | 4.4 | **25.9** | 5.0 |
| **工兵在锋线 r0** | 22.5 | 27.2 | 23.4 | **41.3** ← 闪电独门指纹 |
| 军长在后两线 | 22.1 | 14.6 | **50.7** | 23.5 |
| 排长在端线 r5 | 26.2 | **36.8** | 26.6 | **40.0** |
| 大本营 排/雷/连 % | 45.0/39.7/14.5 | 69.8/25.7/3.8 | 48.0/44.7/5.4 | 79.0/14.5/5.0 |

全库（3602）：司令锋线 **44.6%** · 军长 25.0% · 师长 30.0% · 工兵 24.7% · 炸弹 r2 峰 36.5% ·
地雷 r4 46.3 / r5 53.7 · 大本营 排54.6 / 雷34.6 / 连9.9。
**与 QQ 库一致**：司令锋线 44.6% vs 47%；大本营构成形状一致 ⇒ 同一套棋理。

#### 落地方案（**尚未接入**，等坚哥选）
候选库 `.workbuddy/tests/lz_layout_book_20261001.json`（3602 条 + `tags` 流派标签 / 1.0 MB，
**与 `human_vs_ai.py` 现有库同 schema**）。四选项：
**A** 合并扩池（`rl3→rl4`，273→约 3800，风格大杂烩）·
**B** 用 `tags` 分「稳/攻/龟/闪电」四档采样（**推荐**，AI 开局有可感知的风格变化）·
**C** 只替换 · **D** 先不动。

#### 新坑（会重犯）
1. ⚠️⚠️ **`~/Documents` 是 macOS 受保护目录**：全量遍历到约 **2000 份时进程被沙箱 SIGTERM 掐断**
   （无任何输出、无 traceback，exit 137）。`ls` 单个文件没事，**大批量读就死**。
   ⇒ **先 `rsync` 复制进工作区再分析**。
2. ⚠️ **外置卷上每份文件 open ≈ 17 ms**，4053 份一趟 ≈ **210 s > 120 s 默认超时** ⇒ **必须
   `run_in_background`**。且**别用 `| tail` 管道看进度** —— 被掐时缓冲全丢；**写进度到文件**才留得下。
3. ⚠️ **先找既有实现**：`GL_PIECE` 表就在坚哥自己的转换器里（见上）。**硬破译前先 grep 一轮。**

#### 新工具
```bash
$P .workbuddy/tests/decode_lz_jqs_20261001.py     # .jqs 破译 + 全量统计（列 code→落点）
$P .workbuddy/tests/analyze_lz_library_20261001.py # 去重 + 规则验证 + 建库（产 layout_book_lz.json）
$P .workbuddy/tests/style_lz_20261001.py           # 按流派算风格指纹
$P .workbuddy/tests/group_lz_jqs_20261001.py       # 按阵型组统计落点（钉编码用）
#   环境变量：LZ_BASE=<复制进来的目录>  OUTDIR=<输出目录>
```
报告：`联众布局库读取报告_20261001.html`（9 节，`shoot_report.js --strict` 6 项全过）。

---

### 28.23 ⭐ 第九轮 B：**监督模仿网络 + PIMC**（2026-10-01 · 坚哥）

**坚哥原话**：「AI 两种模式结合：监督模仿网络用来快速评估局面 / 剪枝，PIMC 做搜索规划
（类似 AlphaZero 里的网络 + MCTS 架构），监督模仿网络训练数据来源
`~/Documents/军棋棋谱/联众军棋复盘/复盘`」。

#### 语料：**先核实，结论是「不需要扩充」**
新目录 2555 `.TXT` = **2443 四人局 + 112 份两人局**（`人数:2`、左/右名字空 ⇒ `validate` 全失败）。
与旧库逐位比对 `pieces/moves/players` **零差异** ⇒ `dataset.jsonl` 就是这批数据的全部可用局。
全量闸门：2443 局 / **454657 步** / `illegal` 24（0.005%）· `from_empty` 306 · `turn_mismatch` 6508。

#### 口径：**训练必须与部署逐字一致**
部署（人机对战）= `InfoSet(rec, d, prior, reveal_winner=False)`（`human_vs_ai.py:181`），
`origin_prior` / `infer_engineer` **全关**。训练集用同一口径。
⚠️ **别照抄深核的默认 `reveal_winner=True`**（那是三页 113 项黄金对照的依赖）。

#### 训练集 `sl_data_20261001.py`
- **20 通道 × 17 × 17 uint8**：己方棋子 id / 三方占位 / 已公开兵种 / 铁路 / 行营 / 大本营 /
  未动过的初始格 / 己方可动格 / 6 条全局量。
- `encode` **只读** `known` / `init_cells` / `init_by_side` / `touched`；**不读 `pool`**（未公开分布）。
- ⭐ **反泄漏负样本自检**（`leak_check`）：非己方三家兵种在方位内随机重排（位置/计数不变）
  ⇒ 重新编码**逐字节相同**（40/40 通过）。**这是四暗红线唯一的硬证据，改编码后必跑。**
- 全量 **454327 样本** / 15.1 s（3 万样本/s）⇒ **在线生成即可**，不必落地 GB 级缓存。

#### ⚠️⚠️ 三条新坑（都会重犯）
1. **`nohup ... &` 在沙箱里活不下来** —— Bash 工具调用一结束进程即被清（`kill` 报 no such process，
   输出停在启动那几行）。**长任务必须用 `run_in_background=true`**。
2. **固定节点预算下 `nodes` 测不出剪枝收益** —— 三组 `nodes` 恒等于预算（实测都是 129024）。
   剪枝的真实度量 = **同预算下的到达深度**（`Searcher.depth_reached`）。
3. **预算太小 ⇒ 搜索被截断 ⇒ 三组退化成「排序第一名」**（`nodes=800` 时节点数完全相同、命中率全 0）。
   对照实验**必须打印「预算利用率」当闸门**。

#### 改动（都备份 + 对照）
| 文件 | 改动 | 对照证据 |
|---|---|---|
| `replay_drive.py` | `drive(..., want_trace=True)` 增**步前快照** `board/alive/cnt`（默认 False） | 六项错误计数与改前**完全一致** |
| `search.py` | `Searcher(move_ranker=, root_limit=)`（默认 None） | **黄金对照 22 局面**：`mv` / 逐走法分数 / `nodes` / `depth_reached` 全一致 |
| `ai_search_dark.py` | `PIMCPolicy` 透传两参数（放进 `self.coord`）+ `self.depths` | `--verify` 采样 6 项全 0 违例 |

⚠️ **为什么快照必须由 `drive` 给**：认输事件行整体清盘、被丢弃的 `from_empty` 行、扛旗清盘
这三处，调用方自维护并行棋盘**必然发散**（实测 `iter_game` 自维护棋盘在局末比对失败）。
**「局末断言」挡不住** —— 只有当发散恰好改变终局时才会响。

#### 网络 `sl_train_20261001.py`
CNN 骨干（w=64 / 5 残差块 / **428K 参数**）+ from 头(289) + **条件 to 头**（骨干 ‖ from one-hot 平面）
+ value 头。设备 MPS，**311 s/epoch**，2077 训练局 / 366 验证局（按局划分，非按步）。

**ep8 结果**：from@1 **0.516** / from@3 0.832 / from@5 0.941 / from@10 **0.998**；
to@1 **0.495** / to@5 0.901；联合@1 0.221；value acc 0.785，AUC **0.872**。

⭐⭐ **value 必须做分层 AUC 对照**：全局 AUC 被残局巨大子力差主导 ⇒ 朴素子力差基线轻松 0.86，
只看全局会得出「网络 0.9」的**假绿**（冒烟实测 0.810 **<** 基线 0.861）。分层才有分辨力：

| 阶段 | 网络 | 基线 | Δ |
|---|---|---|---|
| **早局 <80 步** | **0.8002** | 0.7624 | **+0.0378** |
| 中局 80–180 | 0.9298 | 0.9227 | +0.0071 |
| 残局 ≥180 | 0.8764 | 0.8747 | +0.0017 |

⇒ 早局子力差未拉开时网络明显更强（**确实学到了位置/形态层面的东西**）；残局胜负本由子力决定，只持平。

#### ⭐ 先验排序质量对照（`sl_prior_vs_movevalue_20261001.py`）
判据：**真实走法落在排序 top-K 的比例** —— PIMC 的宽度瓶颈就是 `Searcher.gen()` 的 `[:K]`
（默认 K=6）；真实最优走法被挤出前 K 名，搜索再深也找不回来。

**704 局面**（验证集，候选走法均值 55.8/局面，ep8 权重）：

| K | `move_value`（手工启发式） | 网络先验 | Δ |
|---|---|---|---|
| 1 | 0.112 | 0.178 | +0.065 |
| 3 | 0.223 | 0.392 | +0.169 |
| 5 | 0.293 | 0.504 | +0.212 |
| **6**（PIMC 实际宽度） | **0.312** | **0.538** | **+0.226（相对 +72%）** |
| 8 | 0.355 | 0.626 | +0.271 |
| 10 | 0.399 | 0.693 | +0.294 |

开销：`move_value` **0.03 ms**/局面 · 网络 **25 ms**/局面（≈800×）⇒ **只在根节点调用才划算**。

#### 端到端四组对照（61 局面 · n_worlds=3 · 每世界 6000 节点）
| 策略 | 命中率 | 秒/步 | **到达深度** | 节点/步 |
|---|---|---|---|---|
| A 基线（不剪枝） | 0.115 | 1.94 | 3.57 | 18432 |
| B 只改排序（网络，不截断） | 0.115 | 2.03 | 3.57 | 18432 |
| C 手工排序 + 截断 6 | **0.066** | 1.93 | **5.36** | 18432 |
| D 网络排序 + 截断 6 | **0.148** | 2.00 | **5.30** | 18432 |

- ⭐ **A ≡ B 逐位相同** ⇒ **「只改排序」零效果**（`root_scores` 全窗口，分数与顺序无关）。
  **排序只有配合截断才兑现** —— 所以对照必须带 C 组，否则是**归因错误**。
- C vs D（同宽度）：**0.066 → 0.148（2.2×）**，且 D 不低于不剪枝的 A。
- ⚠️ **61 局面的 D−A = +0.033 在噪声内，不足以判显著**；稳健的是「A≡B」与「C≪D」与深度 +48%（183 次搜索均值）。

⚠️ **root 排序对 `root_scores` 的分数无影响**（每个走法都从 `(-INF, INF)` 全窗口开始）
⇒「排序更准」**只有在配合截断时才兑现**。所以对照必须带**同宽度的 `move_value` 组**，
否则是**归因错误**（把「截断的代价」算到网络头上）。

#### 接入点：**只接根节点**
`best_move` 里 `ordered` 排序 + `root_limit` 截断。**不接 `gen()`**：内部节点每层都调用，
网络前向（5~44 ms）会让节点预算名存实亡；且要为 4 方各维护一套 InfoSet 跟着搜索树走。

#### 本轮未做（下一轮的入口）
- 内部节点 `gen()` 的网络排序（先解决「搜索树里四套 InfoSet」）；
- value 头做**叶节点估值**（先解决「搜索节点 ≠ 四暗自视角」的分布错位）；
- **强度**：镜像对局（做法见 §28.18）。离线命中率**不等于**强度 —— 人类的败着也被学到了。

---

### 28.24 ⭐ 第十轮：**AI 布阵风格四档**（稳 / 攻 / 龟 / 闪电 · 2026-10-02 · 坚哥）

> 坚哥原话：「**用 tags 分四档采样**（我推荐）：AI 开局会有可感知的「稳/攻/龟/闪电」风格变化，
> 也能当训练课程。」

#### 四档映射（联众 `.jqs` 自带 `cats` → 档名）
| 源库 `cats` | 档名 | 面板文案 | 规模 |
|---|---|---|---|
| `【Z】全能乱步` | **稳** | 🛡 稳（全能） | **2026** |
| `【Z】可攻可盘` | **攻** | ⚔ 攻（可攻可盘） | **1152** |
| `【Z】能盘能龟` | **龟** | 🐢 龟（能盘能龟） | **336** |
| `【Z】大闪大攻` | **闪电** | ⚡ 闪电（大闪大攻） | **197** |

**并集 3558**（≠ 相加和：多标签重复计入；多标签仅 145/3602 = 4.0%）。
生成物 `.workbuddy/tests/layout_book_style_20261002.json`（**604078 B**）⇒ 覆盖 `app/layout_book.json`。

#### 生成链（三步，脚本可重跑）
1. `tests/lz_style_book_eval_20261002.py` —— **先评估再动手**：两种归属方案规模 / 合规率 / 过滤后规模。
   实测 **全合规 3418/3602 = 94.89%**；违规集中在「地雷正后方放师/司/军」+ 少量「大本营放营/司」。
2. `tests/lz_style_book_build_20261002.py` —— 合规过滤（**4 方位 × 2 镜像**任一违规即剔）+ 按 `cats` 分档
   + 并入旧库（逐字重合跳过，新增归「稳」）。
3. 覆盖 `app/layout_book.json` ⇒ `sync_bridge_frontend.py --apply`。
   顶层键 `['source','raw','unique','clean','encoding','frame','styles','layouts','meta']`。
   ⚠️ 库缺席会**静默退回旧生成器** ⇒ `APP_FILES` 必须带它；自检 ㉓ 断言采样率 100%。

#### 后端语义（`_vs_new`；**唯一风格状态在 `HVA.next_style()`**）
| 入参 | 结果 |
|---|---|
| `style="稳"/"攻"/"龟"/"闪电"` | 用该档（跑课程 / 复现某一风格） |
| `style="random"/"随机"/"all"/"全量"` | 全量池（不分档） |
| **不传** style · **不传** seed | **轮换**「稳→攻→龟→闪电」（前端常态 ⇒ 可感知） |
| **不传** style · **传了** seed | `STYLE_ORDER[seed % 4]` —— 由 seed **确定性**推出 |

⚠️⚠️ **本轮被烟测抓到的真回归**：最初「不传 style ⇒ **无条件**轮换」⇒ 显式同 seed 两次调用拿到
**不同风格** ⇒ 布阵不同 ⇒ 破「同 seed 可复现」契约（`vs_v6_smoke` A 段 1 项失败）；
更糟的是风格随**调用次序**漂移（同 seed 在第 3 次与第 5 次调用结果不同）—— 隐性的不可复现。
**修法**：轮换只在「不传 seed」时发生；显式 seed 的语义是「整局都由 seed 决定」，风格也必须由 seed 定。
修后 **47/47 全绿**，且 E 段覆盖反而更好（24 步、两家司令阵亡）。

⚠️ `random_layout(seed=, style=)` **必须保持纯函数**（自检断言「同 seed 必可复现」）⇒
轮换状态**不能放它内部**，放模块级 `next_style()`，由 `_vs_new` 持有。

#### 指纹与前端
- `LAYOUT_RULE` **rl3 → rl4**（服务自检据此判「进程是否已重启到最新布阵规则」）。
- `state()` 增下发 `style` / `style_name`；前端 `VS_STYLE_TXT` + `vsStyleText()` 渲染
  （「🤖 AI 布阵按经验…开局阵型取自 **3558** 份真实棋手布局」+「🎲 本局 AI 布阵风格 🐢 龟（能盘能龟）」）。
- HVA 自检新增 **㉕**：四档非空 / 按档采样 100% / 负样本（同 seed 不同风格必须分叉）/ 轮换有序（9 次 = 两轮 + 首）。

#### ⚠️ 前端与运行时文件流水线（本轮查清，极易踩）
| 类别 | **人改这份（源）** | 另存一份 | 谁在读 | 对齐工具 |
|---|---|---|---|---|
| 前端 | `实战桥Windows版/app/四国军棋实战桥.html` | `<PROJ>/四国军棋实战桥.html`（发布版） | 本机服务候选表 / 打包 | `sync_bridge_frontend.py --apply` |
| 运行时 | `实战桥Windows版/app/*.py` | `.workbuddy/ld/*.py` | `make_bridge_portable` 打包 | 同上（**方向都是 工作树 → 另存**） |

⚠️⚠️ **`build_live_ui_20260925.py` 已停用** —— 它的 `TEMPLATE`（脚本内 322~1937 行）**没有人机对战面板**，
且 `OUT_HTML` 指向**项目根**那份。**别拿它重新生成**，否则会把根版打回旧页面（本轮改动就会「看起来丢了」）。
只保留作「几何抽取的历史参照」。诊断一个命令就够：`sync_bridge_frontend.py`（不带参数只检查）。

#### 「先怀疑探针」—— 本轮同一天连续 **5 次**探针自己错
1. `probe_train_deploy_parity`：`board.items()` 应为 `board.values()`（解包 `(_p,sd)` 得 `sd=(p,sd)`）⇒ 全 0 假红；
2. 同探针漏同步 `iter_game` 的「出局 ⇒ cmdr=False」⇒ 1/2319 分叉（补上后 2319/2319 全同）；
3. `probe_style_e2e`：`"司令"[-1]` = 「令」≠「司」/ `"工兵"[0]` = 「工」≠「兵」取简写 ⇒ 全 0/6 假红
   （**唯一正解是查 `human_vs_ai.FULL_TO_SHORT`**）；
4. `shot_vs_style` 一版统计「四档名出现几个」—— 轮换提示 `（稳 → 攻 → 龟 → 闪电）` 自带全部四个名字 ⇒ 恒 ❌；
5. 同脚本二版正则 `[^\s（(]*` 取档名 —— 文案是 `🛡 稳（全能）`，**emoji 与档名之间有空格** ⇒ 断在空格上 ⇒ 抓到 `[]`。

⇒ **正解**：抓「紧跟 `本局 AI 布阵风格` 的档名」要**截到第一个括号/换行**，再在片段里找档名。
> 探针一旦「全红 / 全绿」，**第一嫌疑是探针自己**；不查就信会白白否定一小时的工作。

#### 测试入口
```bash
PORT=8771 python3 .workbuddy/tests/vs_v6_smoke_20260930.py              # 47 项（A~F）
python3 .workbuddy/tests/probe_coord_passthrough_20260930.py            # 10 项（配合四项透传）
python3 .workbuddy/tests/probe_style_e2e_20261002.py --port 8771 --n 6  # 四档 6/6 + random 6/6
python3 .workbuddy/tests/shot_vs_style_20261002.js                      # 前端 DOM 文案（含轮换负样本）
# ⚠️ human_vs_ai.py --selftest **需要 numpy**（㉔ 网络先验）⇒ 用 venv 的 python：
#    ~/.workbuddy/binaries/python/envs/default/bin/python human_vs_ai.py --selftest
```

#### 别再做
- 别把「轮换」无条件挂在 `style` 缺省上（破 seed 复现，烟测会抓）；
- 别用 `build_live_ui_20260925.py` 重新生成前端；
- 别只改 `app/` 或只改 `ld/` 一边 —— 打包/服务会读到另一边（`sync_bridge_frontend.py` 是唯一通道）；
- 别用 `pkill -f live_bridge_server` 清端口（8765 是坚哥常驻口）；
- **别在「跑过诊断/烟测/风格 e2e 的服务」上跑普通模式 e2e**（残留 VS 会话会劫持页面，见下）。

#### ⚠️⚠️ 第十一轮：**`/api/vs/*` 残留会话会劫持普通模式页面**（血案级）
现象：`bridge_e2e_20260925.js` 报「本方阵地可放格 **25 → 实测 0**」+ 8 组「平台×颜色」全挂
+ A2 段 `Error: Node is either not clickable or not an Element`。**看起来像前端被我改坏了。**

**真因两条**（缺一条都不会出问题）：
1. 前端 `四国军棋实战桥.html` 约 **2725 行**有**「人机对战会话接回」**：页面加载时若后端 VS 还活着
   （刷新页面 / 中途路过）就 `absorb(vs_state)` ⇒ **`S.phase='vs'` / `S.platform='vs'`**
   ⇒ 本方 `.cell.dropzone` 不再生成（`1212-1216` 只在 `S.phase==='setup'` 时加 dropzone）、
   平台/颜色下拉与 `cellEl` 点击都被 VS 面板接管。
   ⚠️ UI 的「退出」按钮**有意不销毁后端会话**（`2570-2581` 注释）。
2. 服务端 `GET /api/vs/state` 的 **`active` 字段只在「无会话」时才出现**（`live_bridge_server` 728 行）；
   有会话时返回**全量 state**（无 `active`）⇒ 于是「`active` 缺失」本身就是会话存在的信号。

**会话从哪来（三个你可能不觉得在造会话的动作）**：
- `restart_8765.py` 的**诊断第 ④ 条**会 `POST /api/vs/new {"seed":41,"level":0}`（拿 `layout_rule` 指纹）
  ⇒ **它一跑就在服务器上留一个会话**；`--fix` 之后**会再诊断一次**（又造一个）；
- `vs_v6_smoke_20260930.py`、`probe_style_e2e_20261002.py` 同样建 VS 会话。

**正解 = `.workbuddy/tests/launch_bridge_20261002.py`**：只起服务、**不跑任何诊断**，且**自验干净**：
```bash
python3 .workbuddy/tests/launch_bridge_20261002.py --port 8771 --restart
# → 按端口精确清杀 → 起服务 → 断言 GET /api/vs/state 的 active is False（否则不叫干净）
```
⚠️ **判据**：`active is False` 才是干净；`active` **缺失** = 有会话在。

**归因方法论（值得复用）**：出现「看起来是自己改坏的」失败时，三步杀嫌疑 ——
① 与**改动前**的 HTML 做 diff（本轮证明是**纯增量**，无结构损伤）；② **加 `dangerouslyDisableSandbox=true` 重跑**
（本轮两次输出逐条相同 ⇒ 证明沙箱拦截 `code_sign_clone … (file-delete)` **与失败无关**）；
③ 写**只读探针** dump `window.S` 与 DOM（`diag_dropzone_20261002.js` ⇒ 一击锁定 `phase='vs'`）。

---

### 28.25 ⭐ 强度验证：**镜像对局三组**（2026-10-02；承接 §28.23「本轮未做：强度」）

> 离线命中率 ≠ 强度（**人类的败着也被学到了**）。赛制四口径见 §28.18：
> ① 胜负 + 符号检验 ② 配对净子力差 Δ（平局也计入）→ t + Wilcoxon + 95% CI ③ 按终局类型分解
> ④ **空对照（噪声地板）**。脚本 `.workbuddy/ld/sl_mirror_20261002.py`，产物 `mirror_*_20261002.json`。

| 组 | 配置 | 胜负(W-L-D) | p(符号) | Δ 均值 | t | p(t) | p(W) | 95% CI |
|---|---|---|---|---|---|---|---|---|
| **[1] 空对照** | none vs none（仅 seed 不同） | 5-8-27 | 0.5811 | **−3.1** | −0.02 | 0.9828 | 0.9056 | [−278,+272] |
| **[2] M1** | **net+截6** vs 纯 PIMC | 3-5-32 | 0.7266 | **−178.9** | −1.24 | 0.2132 | 0.2611 | [−453,+96] |
| **[3] M2** | **net+截6** vs **mv+截6** | **6-0-34** | **0.0312 ★** | **+217.2** | 1.45 | 0.1484 | 0.1769 | [−70,+504] |

- **噪声地板**：Δ 均值 −3.1、t=−0.02、p=0.98 ⇒ 真零效应测得极准、**无系统性偏置**；**SE 140.3** ⇒
  **MDE = 2.80×SE ≈ ±392.8**（80% 功率、双侧 α=0.05）。三组 SE 几乎相同（140.3 / 140.1 / 146.5）
  ⇒ **同一 MDE 可作三组共同标尺**（Δ 的方差由「同局两臂对撞 + 子力口径」主导，与差异大小无关）。
- **M1**：点估计**为负**（不如纯 PIMC），CI 跨 0，**未达显著** ⇒ 此配置下网络臂无优势。
- **M2**：胜负 **6:0**、p=0.0312 **显著**；但 Δ 口径 CI [−70,+504] 跨 0、**未达显著**。
- ⚠️ **口径冲突取更保守结论**（§12.2）：M2 只能报「**信号有利（胜负 6:0）但连续口径未达显著**」。
- **分解**：M1 的 timeout Δ −152.7 / mixed −218.2（一致偏负）；M2 的 timeout +59.7 / mixed **+689.6**
  （**分胜负的局里网络显著更好**）。
- **非法着法合计 0**（三组）⇒ 信息集无错配。耗时 1338 / 1247 / 1401 s。
- **下一步若要判定 M2 的 +217**：需约 **3–4 倍**样本（当前 MDE ≈ ±392）。

#### 第十一轮：**扩大到 n=80 —— M2 结论翻转**（2026-10-02 同日 · 坚哥「扩大镜像样本」）
`zsh .workbuddy/tests/run_mirror_n80_20261002.sh` ⇒ 三组顺序、**n=80**（布局 100..179 / 160 局 / `--jobs 8`），
耗时 **3 h 42 m**。编排脚本同口径（`--offset 100 --steps 220 --npw 2500 --worlds 3 --K 6 --depth 8 --agg borda`），
唯一差别：**空对照改用 `net` 配置**（与实验臂匹配；第十轮是 `none`）。收尾分析
`tests/analyze_mirror_n80_20261002.py`（配置断言 + 确定性对拍 + 三组并列 + 终局分解 + 合法性 + §12.2 结论）。

| 组 | 配置 | 胜负 W-L-D | p(符号) | Δ 均值 | t | p(t) | p(W) | 95% CI | MDE |
|---|---|---|---|---|---|---|---|---|---|
| [1] 空对照 | net vs net | 24-18-118 | 0.4408 | +50.4 | 0.85 | 0.3993 | 0.3880 | [−66,+167] | ±166.5 |
| [2] M1 | net+截6 vs 纯 PIMC | 24-24-112 | 1.0000 | −36.6 | −0.53 | 0.5936 | 0.8366 | [−170.1,+96.9] | ±190.7 |
| [3] **M2** | **net+截6 vs mv+截6** | **25-0-135** | **&lt;0.0001** | **+218.1** | **3.13** | **0.0017** | **0.0030** | **[+82.6,+353.6]** | ±193.6 |

- ⭐ **M2 从「未达显著」翻为「两口径一致显著」**：胜负 25:0（p<0.0001）+ Δ 三条口径全显著（t / W / CI 不跨 0）
  + 点估计 **218.1 > MDE 193.6** ⇒ 按 §12.2 **可以下「显著」结论**（第十轮是功效不足，不是效应不存在）。
- ⭐ **点估计极稳**：n=20 Δ=**+217.2** → n=80 Δ=**+218.1**，多打 120 局只动 **+0.9** ⇒ 效应量真实。
- **M1 仍无差异**（Δ −36.6，p=0.5936）；n=20 的 −178.9 向 0 收缩 ⇒ 印证「截断到网络 top-6 ≈ 不损失强度」。
- **口径③（n=80）**：M2 效应**集中在能分胜负的局** —— `mixed` 22 配对 Δ**+811.2**，
  而 `timeout` 58 配对 Δ**−6.9**（打满 220 步的僵局两边一样）⇒ 优势不来自拖延。
  M1 各类型贴 0（mixed +13.0 / timeout −77.2）⇒ 真无效应。
- **非法着法三组合计 0**。
- ⚠️ **噪声地板要怎么看**：空对照点估计 **+50.4**（非 0），但 p=0.3993、CI 跨 0 ⇒ **检不出系统性偏置**，
  按标准做法**不做扣除**（扣噪声点估计 = 双重计数）。报告里如实标注了这个敏感性但不采纳。
- 📄 报告 `镜像强度验证_n80扩样_20261002.html`；第十轮报告的同名章节已加「被取代」指针。

⚠️⚠️ **口径更正：「n=20 含于 n=80 ⇒ 合并成 n=100 池化」是错的**。
`sl_mirror_20261002.py:189` 的 seed 是 `a.seed + i*10 + (0|1)`（**i = offset 之后的序号**），
两次跑都是 `--seed 7 --offset 100` ⇒ 布局 100..119 在两次跑中**拿到相同 seed**（M1/M2 配置也相同）
⇒ **是同一批游戏**，相加即**重复计数**，会把 SE 人为压低 `√(100/80)=1.12×`、MDE 从 205 谎报成 183
—— 足以把**不显著说成显著**，且输出上完全看不出来。
**正解：报 n=80 独立超集**（已含 n=20 全部证据）；n=20 转作**确定性校验** ——
M1/M2 的**前 20 个配对 Δ 必须与第十轮逐位相同**。
✅ **本轮实证：net6 20/20、m2 20/20 逐位相同** ⇒ 同时证明①多进程 `spawn` 池无竞态
②网络 CPU 前向无随机性 ③两次跑在同一份代码上（不是「进程活≠代码对」的受害者）。
⚠️ **空对照不参与对拍**（配置 none→net 变了，前 20 Δ 本就该不同）。
第十轮对拍基线：M1 `diffs[:6]=[-486,-548,+404,-1562,-146,+492]` · M2 `[-774,+1036,+426,-94,+728,+138]`。

#### 附：#114 免 torch 推理（独立硬隔离复验 · `tests/probe_np_notorch_20261002.py`）
`sys.modules["torch"] = None` ⇒ 任何 `import torch` 立即 ImportError。结果：构造 0.18 s /
trunk 3.2 ms / 三头前向 OK / `state_from` (1,20,17,17) / `eval_moves` 40 条合法走法全有分 9.1 ms
⇒ **Windows 端（无 torch）可独立推理**。
⚠️ **但便携包不内置 numpy**（`make_bridge_portable` 既不带 wheel 也不 pip）
⇒ `JUNQI_NET_PRIOR=1` 在 Windows 上需先有 numpy（**默认关，不影响开箱即用**）。

### 28.26 ⭐ 第十二轮：**内层网络钩子（#112）· 读屏真机三段收口 · 联众真机路收口**（2026-10-02）

> 坚哥指令：「**执行：下一步 1、4、5、6**」= #112 内层剪枝/叶节点估值 · 读屏真机三段 · 联众真机路回归 · n=160 镜像扩样。

#### ⚠️⚠️ A. `node_budget` 的**检查粒度是 256**（本轮最重要的口径发现，直接改写 A/B 设计）

`app/search.py` 的 `Searcher.negamax` **只在 `if (self.nodes & 255) == 0` 时查预算** ⇒
**任何 `npw ∈ (0, 256]` 完全等价**（都在 nodes=256 处中止），之后按 256 台阶。
实证（n=1 · offset=100 · 两臂同为 `net+root6` · 同一份代码）：

| `--npw` | 配对和 | 耗时 |
|---|---|---|
| 40 | `+106` | 66.2 s |
| 200 | `+106` | 66.9 s |
| 2500 | `-486` | **547.9 s**（8.2× ≈ 2560/256） |

⇒ **40 与 200 逐位相同**。独立印证：成本探针的 `节点/决策` 恒为「3 世界 × npw 的下整 256 台阶」
（768 = 3×256 · 7680 = 3×2560）。
⚠️ **推论（会再犯）**：任何「把实验臂预算调大/调小以**等墙钟**」的 A/B 设计，
只要两端都落在 (0,256] 就**完全无效**（两臂等价，测出来的是 0）。
**A/B 一律显式写 `--npw 256`**，要归因就**同预算**归因；要「等墙钟」得跨台阶（如 2560）并接受成本。

#### ⚠️⚠️ B. 判「后台进程真活」：**看日志句柄，不要看进程列表**

`nohup <cmd> &` 再套一层「后台包装」时，包装一退 **子进程会被连带回收**
（本轮踩：日志停在标题行、`pgrep` 无结果、脚本已不在任务列表，但**看着像在跑**）。
**硬证据 = 有没有人持着日志 fd**：`lsof <logfile>` 有持有者 ⇒ 真活。
⚠️ 沙箱内 `ps` / `pgrep` 常报 `operation not permitted`，**不可信**。

#### ⚠️⚠️ C. `bridge_e2e` 的**三条硬前置条件**（本轮把前两条都踩了）

1. **必须全新实例**：残留 VS 会话会让页面**自动切回对战视图** ⇒ `dropzone=0` 假失败
   （`/api/vs/state` 的 `active` **只在无会话时出现**）。正解用 `tests/launch_bridge_20261002.py`
   （起服务 + 自验 `active is False`）。⚠️ `restart_8765.py --fix` 之后**别在同一端口跑 e2e**。
2. **不能与重负载并发**：n=160（8 job）+ 快照冒烟 + Chrome 同时跑时，页面渲染/定时器被饿死，
   `ocS` 读到 `null` ⇒ 崩在 `line 401 TypeError`。重负载下的 2 败 + 1 崩溃均判**假失败**；
   换干净实例 + 降并发 ⇒ **92/0 两次通过**。
3. ⚠️ **同一实例不能跑第二遍**：D5 读屏段会故意标定一次，而 `ScreenReader.calib` **跨会话保留**、
   动作表里**没有「取消标定」** ⇒ 第二遍必挂「尚未标定」。**每遍换新实例。**

#### D. 读屏真机三段 `calib → start → poll` ⇒ **已收口**（`tests/probe_vision_3stage_20261002.py`，**21/0 连跑两遍**）

- 标定两次独立运行**逐位一致**：`Calib(left=88.56682341386313, top=282.0452055654349, cw=75.864, ch=76.094, n=17, note=质心拟合, style=lj)`
  ⇒ **定位是确定性的**（与上一轮 `verify_liveread` 的 75.86×76.09 互证）。
- `start` ⇒ `watching=True own_side=down`；`poll×2` ⇒ `n_poll +2 / n_change 0 / reader.pending` 空。
- ⚠️ 探针四处修正（**都是探针自己的坑**）：
  ① 读状态是 **GET `/api/vision/state`**，不是 POST（`state` **不在** `_vision` 动作表里 ⇒ POST 落 404，
     而**前端一见 404 会永久禁用标定按钮** —— 正是 §24.9 那个真 bug 的形态）。
  ② `Calib.to_dict()` 只有 `{left, top, cw, ch, n, note, style}`，**没有 `cols`/`rows`**（断言别照抄猜测）。
  ③ `pending` 在 `_reader_state()`（`READER.pending`）里 ⇒ **顶层断言 `pending` 恒真 = 假绿**。
  ④ **不可重跑**：`stop` 只置 `watching=False`、**不清计数器** ⇒ 开场要 `stop + clear` 并改**增量断言**。

#### D2. ⚠️ 跑三段前的**前置自检** `tests/check_screen_capture_20261003.py`（2026-10-03 新增）

`probe_vision_3stage` 第一段 `calib` 报 `抓屏失败：screencapture 失败（退出码 256）` ——
**看着像产品缺陷，实际是宿主 App 的「屏幕录制」TCC 授权失效**。判据混进契约检查里 ⇒ 白查很久。

自检顺序：**先 `caffeinate -u -d` 唤醒 → 全屏试拍（判有无内容）→ 区域 `-R`（读屏真正走的路，同 `screen_capture.grab_mac`）**。
退出码 **0 = 可跑三段 · 2 = 环境不满足**。

⚠️ **两个病因形态几乎一样、处置完全不同**：

| 病因 | 全屏截图 | 区域 `-R` | 处置 |
|---|---|---|---|
| **A 显示器休眠**（Mac mini 默认 30 s） | 纯黑/极小 | 失败 | `caffeinate -u` 唤醒即可，**不是故障** |
| **B 缺屏幕录制权限** | **有内容但只有壁纸** | **必失败** | 只能**人工授权 + 重启 App** |

**2026-10-03 实测 = exit 2 / 病因 B**。证据：全屏 3840×2560 有内容 · `-R` rc=1 `could not create image from rect` ·
`grab_mac` rc 256；`~/Library/Caches/com.tencent.workbuddy.mac.BundleMigration/backups/` 下有
`WorkBuddy-5.7.3.40038958-….backup.app`(09-21) + `install-mac-bundle-update.sh`(**10-01 22:26**)
⇒ **10-01 bundle 迁移** ⇒ TCC 授权（**绑定代码签名**）静默失效、**不再弹窗**。

**处置（人工、一次性）**：系统设置 → 隐私与安全性 → **屏幕录制** → 找到 **WorkBuddy**
（已列 ⇒ **关掉再打开**；未列 ⇒ `+` 添加 `/Applications/WorkBuddy.app`）→ **完全退出并重启 WorkBuddy** → 重跑自检见 ✅ 再跑三段。
可选 `tccutil reset ScreenCapture com.tencent.workbuddy.mac` 先清失效条目。
⚠️ TCC 按**责任 App** 判：python 由 WorkBuddy 派生 ⇒ 授权**必须给 WorkBuddy**（给终端无效）。
⚠️ 重启 WorkBuddy 会**终结当前 agent 会话** ⇒ 这一步只能**坚哥手动做**。

#### E. 联众真机路 ⇒ **已收口**（`ld/align_ai_eval_20260926.js`；起手就是真回归）

- 症状：`ReferenceError: adIsCamp is not defined`。
- 根因：抽取清单 `FNS` 漏了 `ai_eval_core.js` 引用的 **`adCampCoords` / `adIsCamp` / `adLaneOf`**（页面 ad* 家族）。
- 修法：补名字 **+（关键）加「①b 预检」** —— 先点名「core 引用了但没抽取」的自由标识符，
  漏了就 `process.exit(2)`，**别再等运行到那一步才炸**。
- ⚠️ **预检自己也要防假阳性**：`\bNAME\s*\(` 会把 `Math.abs(` / `Object.keys(` / `xs.map(` 也收进来
  ⇒ 必须用**负向后顾** `(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(` + `BUILTIN` 集合。
- 结果：`①b 预检 ✅（FNS 17 · VARS 10）` / 60 局 / 11776 步 / 事件步 98 /
  **逐步 ev、聚合特征、局内 z 分、最终 AI 分 —— 全部 0 差异**。

#### F. #112：内层钩子（`gen()` 网络排序 + 叶节点 value 估值）

**架构**（`app/search.py`，42354 → 48354 B）：`Searcher` 新增 4 参，**全部默认 None/0 ⇒ 与改前逐位一致**：
`inner_ranker(moves, turn, board, step_no, alive, cmdr_dead) -> {mv: score}` ·
`inner_limit`（None ⇒ 沿用 `K`）·
`leaf_value(board, turn, step_no, alive, cmdr_dead) -> float`（**我方联盟视角**，正 = 我好，符号同 `eval_raw`）·
`step0` / `self.step_no`（`CH_STEP` 是**全局**通道）。
`gen()` 只在 `inner_ranker is not None` 时走新分支，**但仍返回 `[:K]`** ⇒ 钩子只改**走法序**、不删走法
⇒ 期望值高、风险低（与 `leaf` 相反）。

⚠️⚠️ **本轮两个真 bug（离线指标完全看不出，必须记住）**：

1. **未给分走法一律压 `-INF`**：v1 写 `sorted(lm, key=lambda m: (-pr.get(m, -INF), m))`，
   而 `inner_ranker` 只给**部分**走法打分（最典型：只给自己方位、对手方位返回 `{}`）⇒
   其余走法**全被压末尾再 `[:lim]` 截断** ⇒ 对手节点被降级成「按坐标字典序取 K 个」
   ⇒ A/B 退化成「网络排序 vs 对手乱序」，**结论不可信**。
   **正解**：`给了分的按网络序在前` + `没给分的回落 order()` 在后；**全弃权 ⇒ 等价 order()（无操作）**。
2. **存活态用根快照**：`Searcher.make()/unmake()` 会更新 `self.alive` / `self.cmdr_dead`
   ⇒ **内层节点的存活态 ≠ 根快照**。钩子签名必须扩成 `(..., step_no, alive, cmdr_dead)`，
   由 `Searcher` 传**活引用**；否则深层节点喂错 `CH_ALIVE`(15) / `CH_CMDR`(16)。
   ⚠️ 这类错**在离线指标上完全看不出来** ⇒ 验证器必须用 **`is` 身份判据**
   （纯值判据在根节点会偶然相等 ⇒ **假绿**）。

⚠️ **内层网络前向必须逐节点重算**：`gen()` 里的 `board` 是**该内部节点**的（采样世界沿分支推下去的**假设**局面），
不是根棋盘。根节点能「用真棋盘算一次、所有世界共享」，是因为 `probe_encode_leak_20261002` 证明编码在**采样空间内恒定**；
**内层节点不满足**。
⚠️ **内层排序只对自己方位生效**（`turn != d ⇒ return {}`）：`net.eval_moves` 的打分头是在「`me` 的走法」上训练的，
给队友/对手走法打分属**分布外**输入。

**验证器**（`tests/verify_search_innerprune_20261002.py`，**10/10**）：默认 0 不一致 · 局部给分 ·
**全弃权 = 无操作** · 计数契约 · **反假绿**（临时把 `gen()` 换回 v1 写法必须报警）· **活引用**（`is` 判据）。

**成本**（CPU 设备，每前向 ≈ 7.2 ms 内插）：base ≈ **0.30 s/决策** · `inner` **1.83** · `leaf` **3.99** · `inner+leaf` **5.83**
⇒ **`inner` 便宜且低风险、`leaf` 贵且量纲靠人为常数（`LEAF_SCALE=2000.0`）⇒ 高风险，必须单独 A/B**。
⚠️ **接 `human_vs_ai` 前必读**：CPU 上 5.83 s/决策 ≈ 现有 PIMC 的 **20×**，实战桥上限 30 s/步 ⇒ **很可能超时**。

**A/B**（`tests/run_mirror_inner_20261002.sh`，跑在**冻结快照** `.workbuddy/snap_inner_20261002/`）：
四组全部**显式 `--npw 256`**、`--jobs 4`（与 n=160 并行；镜像按**节点预算**驱动 ⇒ 争用只影响墙钟、结果逐位确定），
按**便宜优先**排：① `A2a` 内层排序 vs 无钩子 @n=40 ② `N-inner` 空对照 @n=40 ③ `A2b` 叶节点估值 vs 无钩子 @n=40 ④ `N-leaf` 空对照 @n=24。
⚠️ **冻结快照是必须的**：微云 `WeiyunResona` 会**整体重命名搬走** `实战桥Windows版/` ⇒ `mp.spawn` 的 worker
启动时 import 会失败。快照 = `app/` 全量 + 全部 `sl_*.py` + `mirror_match.py` + `dataset.jsonl` 符号链接，
`APP = os.path.join(HERE, "app")`。
⚠️ **对拍锚点**（证明「新增参数不动默认路径」）：改动前（`.bak_pre_inner_20261002`）`配对和 ['+106']`（77.4 s）
→ 改动后**同参数逐位相同 `['+106']`**（65.3 s）。
⚠️ **真网络钩子冒烟**：`['+106']` → `['-336']`、**非法着法 0**、645 s（vs 65 s @npw200）；快照上重跑**逐位相同**。

#### G. #112 A/B **结果**（2026-10-02 晚 · 四组全部收口 · @npw256 · 冻结快照）

| 组 | 臂 | n | 胜-负-平 | 符号 p | Δ 均值 | SE | t p | W p | 95% CI | MDE(80%) | 耗时 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A2a | 内层排序 vs 无钩子 | 40 | 18-16-46 | 0.8642 | −101.3 | 104.1 | 0.3363 | 0.3252 | [−305.4, +102.7] | ±291.4 | 1112.6 s |
| N-inner | **空对照**（同臂·仅 seed） | 40 | 19-14-47 | 0.4869 | **−102.9** | 101.8 | 0.3181 | 0.2766 | [−302.4, +96.6] | ±285.0 | 1491.1 s |
| A2b | 叶节点估值 vs 无钩子 | 40 | **3-21-56** | **0.0003 ★** | **−395.4** | 91.1 | **0.0000 ★** | **0.0001 ★** | **[−573.9, −217.0]** | ±255.0 | 5180.1 s |
| N-leaf | **空对照**（同臂·仅 seed） | 24 | 1-2-45 | 1.0000 | **+50.8** | 130.5 | 0.7030 | 0.7102 | [−205.0, +306.7] | ±365.5 | 6723.8 s |

非法着法四组合计 **0** ✓。

**正式判据（实验臂 Δ − 自己的空对照 Δ）**：

| 钩子 | 效应 | SE_diff | z | p | 判定 |
|---|---|---|---|---|---|
| `inner` 内层排序 | **+1.6** | 145.6 | 0.01 | **0.9915** | **零效应** |
| `leaf` 叶节点估值 | **−446.3** | 159.2 | −2.80 | **0.0050 ★** | **显著有害** |

- ⭐ **`inner` 的关键读法**：实验臂 −101.3 与自己的空对照 −102.9 **几乎逐位重合（差 1.6）**
  ⇒ 观测到的 −103 **是镜像框架偏置**（实验方/对照方 seed 结构），**不是钩子效应**。
  没有空地板的 A/B 会把 −101.3 误读成「略有代价」，甚至误读成效应。**这就是必须有空对照的理由。**
- ⚠️ **`leaf` 的稳健性**：截到与 N-leaf 同一批 **24** 个布局（样本对齐）后 Δ **−422.6**（SE 129.2, p=0.0011 ★），
  子集效应 **−473.4**（SE 183.6, z=−2.58, **p=0.0099 ★**）⇒ 与 n=40 结论一致，**与样本量无关**。
- **处置**：`inner` 与 `leaf` **都不接** `human_vs_ai` / 实战桥。代码保留（默认 `None` ⇒ 零影响），作为「已排除」的证据。
- **为什么 `leaf` 会显著有害**（三条线索）：
  ① 效应集中在能分胜负的局 —— 口径③ `mixed` 22 配对 Δ **−630.1**、`timeout` 17 配对 Δ −139.2
     ⇒ 不是拖延，是**真在关键决策上走坏**；
  ② `LEAF_SCALE=2000.0` 是**人为常数**（「胜率 → 子力差」量纲对齐是猜的）；
  ③ 用**有噪**估计（value 头，分层 AUC 0.872）替换**精确**启发式（`eval_raw` 子力差），
     在 `npw=256` 这种**极浅**预算下叶节点评估就是搜索的主要信息来源 ⇒ 必然退化。
  ⇒ **要救 `leaf` 必须先做量纲标定**（在 `eval_raw` 口径上回归，而不是拍 2000），并**跨 256 台阶**（如 2560）重测。
  ⚠️ **成本也独立否决**：CPU 上 `inner+leaf` ≈ **5.83 s/决策** ≈ 现有 PIMC 的 **20×**，实战桥上限 30 s/步 ⇒ 很可能超时。
- **确定性对拍（并发污染检测）**：在 n=160（`--jobs 8`）正跑时重跑 `A2a --n 1 --offset 100`
  ⇒ `配对和 ['-50']`、布局1 坐甲 `+250.0` / 坐乙 `−300.0`，与 n=40 跑的布局1 **逐位相同**
  ⇒ ① 镜像按**节点预算**驱动（CPU 争用只影响墙钟）② 多进程无竞态 ③ 并发未污染。
- 📄 报告 `内层网络钩子AB报告_20261002.html`（`shoot_report.js --strict` 全绿）。
- 📊 分析脚本 `tests/analyze_inner_ab_20261002.py`（四口径 + 地板差异检验 + 子集复算）。

#### H. n=160 镜像扩样：**污染检测 80/80 逐位相同**（本轮已出两组）

`sl_mirror` 的 seed = `a.seed + i*10 + (0|1)`（`i` = offset 之后的序号），两轮都是 `--seed 7 --offset 100`
⇒ **n=160 的前 80 个配对必然与 n=80 逐位相同**。这不是巧合，是**免费的污染检测**：

| 组 | n=80（Δ / SE / MDE） | n=160（Δ / SE / MDE） | 污染检测 | 非法着法 |
|---|---|---|---|---|
| 空对照 | +50.4 / 59.5 / ±166.5 | **+17.6** / 41.6 / ±116.4 | ✅ 80/80 | 0 |
| M1 · net+截6 vs 纯PIMC | −36.6 / 68.1 / ±190.7 | **+29.8** / 55.0 / ±153.9 | ✅ 80/80 | 0 |
| M2 · net+截6 vs mv+截6 | **+218.1** / 69.1 / ±193.6 ★ | （第 3 组运行中） | — | — |

- ⭐ **对拍通过的三重含义**：① 多进程 `spawn` 池**无竞态**；② 网络 CPU 前向**无确定性缺口**；
  ③ 本轮与上一轮跑在**同一份代码/权重**上 —— 不是「进程活 ≠ 代码对」的受害者。
- ⚠️⚠️ **因此 n=160 是 n=80 的独立超集，两轮绝不可相加池化**（相加 = 重复计数，SE 假降 √(240/160)=1.22×）。
  报告口径一律写「**n=160 独立超集**」。
- ⭐ **M1 的读法**：n=80 −36.6 → n=160 +29.8 ⇒ 两档都远在 MDE 内且**符号翻转**
  ⇒ 正是「无效应 + 布局间方差大」的表现 ⇒ **「截断到网络 top-6 不损失强度」的结论更稳**。
- ⚠️ **空对照不得与第十轮对拍**（第十轮空对照是 `none→net` 配置变更，前 20 Δ 本就该不同）——§28.25 已记。
- 📊 分析脚本 `tests/analyze_mirror_n160_20261002.py`（配置断言 + 污染检测 + 三档并列 + 口径③ + 结论纪律）。

#### I. 另一条工程教训：判「后台进程真活」要看**日志句柄**

首次启动 A/B 时写成 `nohup <脚本> &` **再套一层「后台包装」** ⇒ 包装一退，**子进程被连带回收**。
症状：日志停在标题行、`pgrep` 无结果、脚本已不在任务列表，但表面**看着像在跑**。

**硬证据 = 有没有人持着日志 fd**：`lsof <logfile>` 有持有者才算真活。
⚠️ 沙箱内 `ps` / `pgrep` 常报 `operation not permitted`，**不可信**。
正解：`zsh <脚本>` 直接进后台（不套 `nohup`、不写 `&`）。

---

## §28.27 第三方站点侦察与可借鉴性评估（junqionline.com / Junqi Arena）

> 触发词：**junqionline · 外部站点 · 能不能借鉴别人的 AI · 提取训练数据 · 第三方口径核对 · 公开模型**
> 结论一句话：**它的训练数据拿不到（服务端持有 + 无公开接口 + robots 明禁内部路由 + All rights reserved）；可借鉴的是它的「信念特征工程」，不是它的数据或权重。**

### A. 结论（先背下来）

| 问题 | 答案 |
|---|---|
| 有训练数据吗 | **没有**。全站零对局数据面；`/replay/:matchId` = **486 B 空壳**（只设 SEO meta，零 fetch） |
| 能拿到 AI 东西吗 | **能拿到一个成品模型**：`/models/bot/latest.onnx`（+ `.data`），前端 **onnxruntime-web** 拉取推理 |
| 能用它吗 | **不能也不该**：成品权重 + `All rights reserved` + **其编码器在对方 JS 里，拿到权重也喂不进去**（抄编码器 = 抄代码） |
| 真可借鉴的 | ① **信念特征显式入网** ② **信念辅助监督** ③ **把推理结论做成特征**（如 `route_is_observer_proved_engineer`）+ ④ 布局闸门补**行营显式断言** |
| 附带收益 | 规则页 = **第三方口径交叉验证**：26 项核对 **全一致**，仅 **2 处参数差异**（步数上限 / 每步时限） |

### B. 只读侦察姿势（三条纪律）

1. **只读公开静态资源 + 规则页 + 打包路由**；**不碰** `robots.txt` 的 `Disallow` 路径（`/internal/`）。
2. ⚠️ **不下载别人的模型权重**，即使 URL 无鉴权。理由：成品权重 / 版权 / **编码器不可得 ⇒ 无用**。
3. **结论必须能由静态证据自证**，不依赖在线探测 —— 本轮 `curl /api/rooms` 全部超时或代理 502（本机出口在侦察时段不可用），**结论照旧成立**。

### C. 它的公开面（穷举，全在客户端 chunk 里）

* 技术栈：**Remix / React Router v7 + Vite SSR**；`/assets/manifest-*.js` 列**全部 34 条路由 id**。
* **REST 只有 3 条业务端点**：`GET /api/rooms` · `POST /api/rooms` · `GET /api/rooms/{id}`（+ `/api/auth/{me,sign-in,sign-up,sign-out,refresh,forgot-password,reset-password}`、`/api/me/cosmetics`）。
* **WS 唯一对局通道**：`/ws/room/{roomId}`。客户端命令：`join/leave/changeSeat/readyChange/start/moveSubmit/replayRequest/setupSave/settingsChange/ping/trail/kick/skip/surrender/pieceMarkChange`（+ 重连 `reconnect:true` 的 `join`）；服务端消息：`room:ping` / `room:trail` / `room:closed` / `ack`。
* 房间对象字段：`players/seats/seatPlayerIds/playerCount/ready/settings/setupSaved/seatCount/privateGame`。
  ⇒ **全是控制面**（谁坐哪、准备、观战、私人房），**不含对局历史** —— 这就是「没有可提取数据」的技术根因。
* ⚠️ **误报坑**：早期疑似「开局库」的 `Book`/`opening` 实为 **SVG 图标名** `U('outline','book','Book',[[…path…]])`。
* ⛔ 内部路由：`routes/bot-lab*`（机器人实验室）、`routes/internal-skins*`、`routes/chrome-devtools` —— **robots 禁止 → 不碰**。

### D. 它的模型规格（逆自 `protocol-*.js`，带硬断言 ⇒ 几乎不会误读）

```
dl(e=256)                                              // hiddenSize = 256，按座位各一份
stateFeatures         float32 [1, S]
moveEventFeatures     float32 [1, 8, F]                // ⚠️ >8 事件直接抛错
moveEventMask         bool    [1, 8]
previousHiddenState   float32 [1, 256]
possibleKindMask      float32 [1, 129, 12]             // ⚠️ 断言 length === 1548
candidateFeatures     float32 [1, N_cand, C]
candidateSpaceIndices int64   [1, N_cand, 2]           // (from,to) 空间 id
输出 scores           float32 [N_cand]                 // 每候选一分
     nextHiddenState  float32 [256]
决策 = softmax(scores / temperature) 采样（policy:'sample'），**不做搜索**
```

**关键对照**：`candidateSpaceIndices (from,to)` ≡ 我们的 **from/to 双头**；他们**多**「按座位循环隐状态 + ≤8 事件序列 + 信念 mask」，我们**多** `value` 头 + **PIMC（3 世界 × depth 8）+ 根节点截断**。⇒ **我们搜索更强，它表征更细**。
`revealMode` 三档：`fog_of_war`（默认，= 我们的严格四暗）/ `open_board` / `team_intel`；房间默认 `turnTimerSeconds:60`。

### E. ⭐ 它的事件特征表 `pl`（55 条，名字未混淆）—— 本轮最有价值单块证据

```
event_is_start / move / combat / no_legal_move_elimination / flag_capture_elimination
actor_is_self / ally / enemy / actor_is_{north,east,south,west}
source_space_index_normalized / destination_space_index_normalized
route_is_ordinary / route_is_railroad / route_is_observer_proved_engineer   ← ★
combat_attacker_survived / combat_defender_survived / combat_both_removed
mover_is_known / target_is_known
mover_known_kind_is_{12类} / target_known_kind_is_{12类}
mover_memory_has_entry / suspected_bomb / suspected_mine / confirmed_not_bomb / confirmed_not_engineer / confirmed_not_mine
target_memory_has_entry / suspected_bomb / suspected_mine / confirmed_not_bomb / confirmed_not_engineer / confirmed_not_mine
source_is_station/camp/headquarters/public/has_railroad
destination_is_station/camp/headquarters/public/has_railroad
move_index_normalized
```
另有两个**监督目标**：`beliefSupervisionMask` / `beliefTargets`（用真实布局监督「可能兵种」预测）。

**三条读法**：
1. `route_is_observer_proved_engineer` = **把我们那条规则（非工兵铁路只能直行）直接变成输入特征**：观察到铁路多段转弯 ⇒ **证明**是工兵。这是「推理结论显式化」的范式。
2. `*_memory_suspected_* / confirmed_not_*` = 每枚未知敌子挂一份**信念记录**。**这是我们目前缺的那一块。**
3. 组合受控：12 类 × 2（mover/target）× 6 记忆位 + 5 格子类型，**全 0/1 或 one-hot**，成本可忽略。

### F. 规则核对（26 项全一致）与真差异

**全一致清单**（详见报告表）：南北/东西同盟 · 夺两旗胜 · 四方位 · **回合顺序北→东→南→西 = 我们 `DIRS4=['up','right','down','left']`（同一件事！原「差异候选②」撤销）** · 淘汰跳回合 · 25 子名册 · 军衔序（它 10…2，我们 9…1，同序异基准）· 炸弹同归于尽 · **地雷只被工兵排除 / 击败非工兵（攻方亡、雷保留）** · 军旗须在大本营 · 炸弹禁最前排 · 地雷后两排（我们更严）· 大本营进不出 · 行营不可攻 · 公路一步 · **非工兵铁路直立 / 工兵可转** · 铁路不穿子可攻击结束 · **侧边走廊直连** · **不混用首排横向铁路与弯道铁路** · 不占盟友格 · 不穿子 · 司令亡 ⇒ 旗揭示 · 不揭示军衔（盟友也隐藏）· 夺旗 ⇒ 淘汰 + **剩余棋子移出棋盘** + 盟友继续 · 终局回看全明。

**真差异只有 2 处，都不影响 AI 强度**：

| # | 项 | 它 | 我们 | 处置 |
|---|---|---|---|---|
| 1 | 步数上限 | **300**（正式规则 ⇒ 平局） | `MATCH_MAX_STEPS=1500`（防死循环兜底）/ 人机对战 `n>=1500` / 镜像 `220` | **不动**。我们是安全阀、它是规则；镜像 220 更早截断更保守。<br>⚠️ 但注意：**`CH_STEP` 早已按 `/300` 量化** ⇒ 编码层默认就是它的尺度 |
| 2 | 每步时限 | `turnTimerSeconds:60` | 人机对战 `STEP_LIMIT_SEC=20`（预算 24 s） | 可选做成可调项，**不动引擎常数** |

### G. 可借鉴清单（方法层面，不涉其代码/权重）

| # | 项 | 价值 | 成本 | 风险 | 建议 |
|---|---|---|---|---|---|
| 1 | **信念特征显式入网**：`possibleKindMask [129,12]` + 12 条 `memory_suspected/confirmed_not` | 高 | 中 | 低 | ⭐ 做 |
| 2 | **信念辅助监督**：`beliefSupervisionMask` / `beliefTargets` | 中高 | 中 | 低 | ⭐ 做（**必须配反泄漏负样本**） |
| 3 | **推理结论做成特征**：`route_is_observer_proved_engineer` | 中 | 低 | 低 | ✅ 做（零推理成本） |
| 4 | 按座位循环隐状态 + ≤8 事件编码 | 中 | 高 | 中 | ⏸ 暂缓（与我们「静态编码 + PIMC」冲突；它**无搜索** ⇒ 单点模仿是降级） |
| 5 | **布局闸门补显式行营断言** | 低 | 极低 | 无 | ✅ 做（≈10 行，防将来换实现路径时静默失效） |
| 6 | `turnTimerSeconds` / `revealMode` 三档 | 低 | 低 | 无 | 🔵 仅记录 |

**我们的现状（做 #1 时的起点，别写成「从零」）**：20 通道里**已有两个准信念通道** —— `CH_KNOWN`(5, 已公开兵种 id) + `CH_INIT_FRESH`(9, 未动过的初始格 = 雷/旗唯一可能位)，其余靠 PIMC **采样世界隐式**。⇒ #1 = **扩通道**（20 → 20+k），不动搜索层，重训后用**既有镜像三组**量强度。

**#1 路线（两步）**：① 先扩通道（每枚未知敌子：suspected_bomb / suspected_mine / confirmed_not_bomb / confirmed_not_engineer / confirmed_not_mine + 12 类 one-hot）→ 重训 → 镜像三组；② 再加 belief 头 + 辅助监督 + 反泄漏负样本。
⚠️ 属「改输入编码 ⇒ 必须重训」，与 **#112（内层/叶钩子，已判定两钩都不接）无耦合**；改前照旧「先跑探针重测 → 再改期望 → 最后动代码」。

### H. ⛔ 合规红线（写死）

* **不下载、不使用** `/models/bot/latest.onnx`（+ `.data`）；
* **不访问** `/internal/bot-lab`、`/internal/skins`、`/chrome-devtools`（robots `Disallow: /internal/`）；
* **不逆向服务端**、不绕鉴权、不批量抓取（公开面本来就是空的，抓也无所得）。

### I. 产物与证据

* 报告：`junqionline站点分析与可借鉴性评估_20261002.html`（`shoot_report.js --strict` 全绿：页高 10164px / 11 表 / 4 pre / 16 标题节点 / 零溢出零残留）。
* 抓站产物（**未入项目树**）：`/tmp/jq_site/` 19 个文件。关键指纹：
  `rules.html` 62819 B md5 `4c3e84018027682fd1820f19586edeb6` ·
  `robots.txt` 90 B `8069bcd14169e93cbcb42dd2e8870b09` ·
  `sitemap.xml` 6351 B `9ef02da9cc5473b2aef11023b365ca85` ·
  `js/manifest-67da0409.js` 31474 B `195e7d3a3652852ad72951ce7dbf9560` ·
  `js/protocol-DMCZebhD.js` 139192 B `1899a2136ec99184dc6be4e176f00e4f`（D/E 节唯一来源）·
  `js/GameBoard-wdfw3sSE.js` 333222 B `25b79d8651e8f6e2056fa622ceeff9bd` ·
  `js/client-XogFNDLS.js` 3996 B `671b37fbf4b6abdd95ba625672da24d9` ·
  `js/replay-4GV8ecHx.js` 486 B `623223b5a091460dc91aa06d28702b69`（空壳证据）。
* 我们侧被核对的实现（**本轮未修改**）：`junqi_engine.py` 18426 B `adabe6f0…` · `match.py` 8275 B `a28bdf91…` · `search.py` 48354 B `1b88bd7c…` · `human_vs_ai.py` 92554 B `12638897…` · `sl_data_20261001.py` 16863 B `0500ea0b…` · `sl_net_np_20261002.py` 18459 B `7d6e9b2b…`。

### J. 坑（可复用）

1. ⚠️ **「能下载」≠「能用」**：模型权重可拿，但**编码器在对方的 JS 里**，抄编码器就是抄代码 ⇒ 拿到权重也喂不进去。评估外部模型时先问「编码器可得吗」。
2. ⚠️ **在线探测不可用不影响结论**：本轮 `curl` 全超时/502，但结论只由**静态资源 + 打包路由**自证 —— 别因为「探不到」就降低结论强度，也别因为「探不到」就放弃已拿到的静态证据。
3. ⚠️ **minified 变量名仍可读**：`manifest-*.js` 的 route id、`protocol-*.js` 的 `pl` 特征名、硬断言字符串（`expected 1548`）都**未混淆** ⇒ 逆规格比想象中容易，先找**断言与字符串常量**再找逻辑。
4. ⚠️ **误报要主动排除**：`Book`/`opening` 来自 SVG 图标名 ⇒ 任何「疑似开局库/训练数据」的线索都要**回到定义处**确认，别凭出现频率下结论（同「先怀疑探针」纪律）。

## §28.28 信念特征入网 + 信念辅助监督 + 布局行营断言（「执行1、2、3、4」）

> 来源：§28.27 的可借鉴清单 #1/#2/#3/#4。顺序：**#4（独立低风险）→ #1+#3（同在编码层）→ #2（在其上加头）→ 重训 → 量强度**。
> 涉及文件：`sl_data_20261001.py`（app+ld，唯一权威源）· `sl_train_20261001.py`（**仅 ld**）· `sl_net_np_20261002.py`（app+ld）· `sl_net_20261001.py`（**仅 ld**）· `human_vs_ai.py`（app+ld）。

### A. 结论表

| # | 项 | 状态 | 关键事实 |
|---|---|---|---|
| #4 | 布局闸门补**行营显式断言** | ✅ | `layout_violation()` 越界检查收紧为**本方全集**；行营断言加在「越界之后、线号之前」；配**负样本** |
| #1 | 信念特征入网（`possibleKindMask` 类） | ✅ | `N_CH` **20 → 26**，6 个信念通道（只读**五项严格公开量**） |
| #3 | 推理结论入特征（`route_is_observer_proved_engineer`） | ✅ | `INFER_ENGINEER` 默认**开**（env `JUNQI_INFER_ENG`）＝ 开启 `InfoSet._engineer_only()` |
| #2 | 信念辅助监督（`beliefSupervisionMask/Targets`） | ✅ | belief 头 `Conv2d(w,13,1)`，λ_b 加权 CE；**三条免费对照**（置换 / 全局众数 / **逐格众数**） |
| — | 离线指标 | ⚠️ | 与旧 20 通道网**逐项同档**（增量 ≈ 0，见 G） |
| — | 强度 | ✅ 见 **I** | 新网 M2 Δ**+341.4**（p=0.0000 · **33:0**）· M1 未检出差异 · **本轮四项对强度无可测增益**（新 vs 旧 M2 差异 p=0.19）|

### B. #4 布局闸门（`human_vs_ai.layout_violation`）

```python
own_all = [rc for rc, (p, s) in self.board.items() if s == sd]
if any(not in_base(rc) for rc in own_all):
    return "棋子不能摆到本方阵地之外"
if any(rc in _CAMP_CELLS for rc in own_all):
    return "棋子不能摆在行营"
```

* **越界检查收紧为全集**：旧版只查 `mines + bombs + flag` ⇒ 普通子越界**不会被发现**。旧版「恰好安全」只是当前调用链的巧合，**不是被断言的不变量**。
* ⚠️ **断言顺序会耦合报错文案**：行营格**包含在** `_BASE_SPAN` 矩形内 ⇒ 越界检查抓不到它，所以行营那条必须**单独写**；而把它放在「地雷/炸弹线号」之后，报错会被后者抢先 ⇒ 顺序不能随便调。
* ⚠️ **负样本是必须的**：只断言「合法布局返回 None」是**假绿**（那条隐式路径本来就恒真）。正解 = 人为把一枚**非军旗/非地雷/非炸弹**的普通子搬进行营 ⇒ 必须**精确**报「棋子不能摆在行营」；再还原 ⇒ 必须合法（正对照，证明不误报）。选普通子是为了不先撞上大本营/后两排/最前线那几条检查。
* 数据事实：`board_layout.json` 是 **`list[17][17]`（不是 dict）**；`C` 行营 **20** 格 · `H` 大本营 **17** 格（含中央 `(6,8)(8,8)(10,8)`）；**行营全部落在各方 `_BASE_SPAN` 之内**。

### C. #1 信念通道（20 → 26）

| 通道 | 名 | 含义 | 判据 |
|---|---|---|---|
| 20 | `CH_UNK_ANY` | 非己方占位 ∧ 兵种未公开 | 掩码 |
| 21 | `CH_UNK_MOVED` | 该子**动过** ⇒ 硬排除地雷/军旗 | 纯几何 + 公开位置 |
| 22 | `CH_UNK_FRESH` | 仍在**未动过的本方初始格** ⇒ 仍可能是雷/旗 | 纯几何 |
| 23 | `CH_SIDE_UNK` | 该方未公开兵种数 / 25 | 公开计数 |
| 24 | `CH_SIDE_KNOW` | 该方已公开兵种数 / 25（摊牌 + 几何推理命中） | 公开计数 |
| 25 | `CH_SIDE_FRESH` | 该方仍未被碰过的初始格数 / 25 | 公开几何 |

* ⚠️⚠️ **`info.pool` 是真值、不是公开可推量**：`_unpool` 在「死子未翻牌」时照样被调用（严格四暗 `keep_atk/keep_dfd` 为 False）⇒ 池里含真值。**而反泄漏的「重排兵种」探针按方位重排、多重集不变 ⇒ 抓不到它**。故信念通道只用**五项**：`board`（位置+归属）/ `info.touched` / `info.init_by_side` / `info.known` / 名册计数。
* ⚠️ **`fresh` 判据必须与 `whatif.InfoSet.dist()` 逐字一致**：`(r,c) not in touched and (r,c) in init_by_side[side]`。不一致 = 网络的信念与采样的信念各说各话。
* **`mk_infos(rec, prior, sides=None, reveal_winner=False, **kw)` = 四暗口径的唯一入口**。训练 / 自检 / PIMC 对拍 / 人机对战**全调它** ⇒ 杜绝「训练侧开着、部署侧关着」（那种错位**离线指标看不出来**）。
* `INFER_ENGINEER`（默认 **开**）等价于 junqionline 的 `route_is_observer_proved_engineer`；结论写进 `info.known` ⇒ 自动被 `CH_KNOWN` 承载，**同时从采样池扣除**（PIMC 世界更准）。`_engineer_only()` 实测**假阳性 0**，覆盖全库真实工兵走法 **25.4%**。只用 `reveal_winner=False` 那条四暗管线，**三页深核 113 项黄金对照不受影响**。
* **`origin_prior` 保持 False**（一次只改一个变量）。

### D. ⚠️⚠️ 本轮自查抓到的口径 bug：`CH_SCALE` 必须是**单一权威来源**

`CH_SIDE_{UNK,KNOW,FRESH}` 在 `encode` 里写的是 **0..255**（`min(255, round(255*n/25))`），但 `CH_SCALE` 给的是 **1.0** ⇒ 这三片输入被放大 **256×**，第一个卷积直接被它们主导。

**根因不是「漏改一处」，而是同一张表被抄了两份**（`sl_train` 与 `sl_net_np` 各写一遍 `CH_SCALE_LIST`，注释还写着「改一处必须改两处」）。修法：

* 在 `sl_data_20261001.py` 立 **`CH_VMAX` / `CH_SCALE` / `QUANT_CH`**，判据只有一条 —— **`encode` 写的是 0/1、1..12 还是 0..255**（⇒ 分母 1 / 12 / 255）。两个消费者一律 `from sl_data_20261001 import CH_SCALE`。
* 权威表（实测）：`0:12 1..4:1 5:12 6..13:1 14..18:255 19:1 20..22:1 23..25:255`。
* `--check` 新增**「通道值域」探针**（**必须先于训练**）：① 实测 max ≤ 声明上界；② **量化型通道必须真出现过 >1**。
  ⚠️ **只查 ① 是假绿** —— 把量化通道错写成 0/1 它照样通过。两条互为负样本。实测 `ch23=255/255 ch25=255/255 ch18=255/255 ch24=10/255`。

### E. 反泄漏：**双防线**（单靠一条必漏）

1. **`leak_check`（数据面）** —— 把非己方三家的兵种**重贴标签**后重编码，要求逐字节相同。
   * ⚠️⚠️ **必须「在同一局面的棋盘对象上重贴标签」，不能「重排后重新 drive」**：兵种一变碰撞胜负就变、存活子不同、后续位置发散 ⇒ 在 `frac=0.5` 处比对等于拿两个**不同局面**相比（实测 40 局报 **289 格全不同**的伪差异）。正解 `_relabel_board(board, me, rng)`。
   * ⚠️⚠️ **必须多步**：第 0 步 `touched` 为空 ⇒ `CH_UNK_FRESH` 恒 1 / `CH_UNK_MOVED` 恒 0 / `CH_SIDE_*` 退化成常数 ⇒ 6 个新通道里一半**没被检验**。用 `fracs=(0.0,0.25,0.5,0.75)`。
2. **`source_guard()`（源码面）** —— **AST** 查 `encode` / `_belief_targets` 里的 `.pool` 属性访问。因为重排探针**按设计抓不到**多重集型泄漏（M2 臂就是把这个盲区**显式量出来**，而不是假装它不存在）。
   * ⚠️ **不能用「源码字符串包含 pool」**：`encode` 的 docstring 里就写了「绝不读 `info.pool`」⇒ 假阳性。必须 `ast.walk` 找 `ast.Attribute.attr == "pool"`。
3. **负样本对照 `leak_mutation_check`**：`M0 不注入`（期望 0 不同）· `M1 真值兵种入通道`（**必报**）· `M2 多重集型模拟 pool`（期望 0 ⇒ 盲区已量出，由 `source_guard` 兜底）。

实测输出（`--check 40`，必须在 `.workbuddy/ld/` 跑）：`160 / 失败 0` · `M0 0/48` · `M1 48/48` · `M2 0/48` · `source_guard ✓`。

### F. #2 belief 头（信念辅助监督）

* **网络**：`self.belief = nn.Conv2d(w, N_BEL, 1)`，`N_BEL = 1 + max(PID.values()) = 13`（0 = 「无」，mask 保证该格有子 ⇒ 永不命中，留 0 只为**对齐 PID**，省掉 ±1 换算）。**与 from/to/value 共享骨干** —— 这才是「辅助」的意义（挂在骨干外对 policy 毫无作用）。
* **标签**：`_belief_targets(info, board, me)` → `mask[289]`（站着**非己方**子 ∧ 兵种对我**未公开**；**队友也计入**，四暗下盟友军衔同样隐藏）+ `target[289]`（**真值** PID）。真值来自重放棋盘 —— ⚠️ 那是**标签**不是输入，红线约束的是 `encode`。
* **损失**：`F.cross_entropy(blf[mask], tgt[mask])`，只在 mask 格上算（已公开/己方的格白送损失）。`--lambda-b`（默认 1.0）/ `--no-belief`。
* **`evaluate` 的三条免费对照**（不训练、不额外前向）：
  * `belief_base_global` 永远猜**训练集全局众数**；
  * ⭐ `belief_base_cell` 永远猜**该格在训练集里最常见的兵种**（= **布局先验**，最强的那条）；
  * ⭐ `belief_perm` **局面内置换真值**后重算 —— 破坏「状态→兵种」对应，任何虚高都说明命中有状态以外的来源。
  * 另加**分阶段**（`early<80` / `mid80-180` / `late>=180`，与 value 分层 AUC 共用 `_PHASES`）。
* **`--belief-selftest` 接线自检（带负样本对照）**：① mask 计数区间 + 真值必 ∈ 1..12；② **λ_b=1 ⇒ `belief.weight` 梯度非零**；③ **λ_b=0 ⇒ 同一份数据上梯度恒 0**（这一对才是分辨力所在，只测 ② 会被「随便什么路径给了梯度」骗过）；④ `has_belief=False` ⇒ `belief_logits()` 返回 None。
* ⚠️ **`SLNet` 必须按 ckpt 里的键自适应建网**（`has_belief = any(k.startswith("belief.") ...)`）：否则用旧 ckpt 建新模型会因缺 `belief.*` strict 加载**直接 RuntimeError**，连带打断 `--verify/--mutate` 与 PIMC 全链路。

**实测数字**（短冒烟 200 局 / 260 batch）：`top1 0.319` ≫ `置换 0.123`，`全局众数 0.175`，`逐格众数 0.346`；分阶段 `0.290 → 0.351 → 0.456`（残局候选少 ⇒ 更好猜）。

### G. 离线结果与下游验证

**8 epoch / 2443 局（2077 训练 / 366 验证）· MPS · 每 epoch ~470-480 s（比旧的 311-325 s 慢：信念头 + 与镜像并发争 CPU）**

| 指标 | 新网（26 ch + belief） | 旧网（20 ch，上一轮 ep8） |
|---|---|---|
| from@1 / @3 / @5 / @10 | 0.518 / 0.832 / 0.941 / 0.998 | 0.516 / — / 0.941 / 0.998 |
| to@1 / @5 | 0.495 / 0.900 | 0.495 / — |
| joint@1 | **0.222** | 0.221 |
| value acc / auc（朴素基线） | 0.783 / **0.871**（0.855） | — / 0.872（0.855） |
| 分层 AUC `early<80` Δ | **+0.0377** | +0.0378 |
| 分层 AUC `mid80-180` / `late>=180` Δ | +0.0070 / −0.0008 | +0.0071 / +0.0017 |
| 信念头 top1（置换/全局众数/**逐格众数**） | **0.369**（0.130 / 0.178 / **0.339**） | — |
| 信念分阶段 | 0.332 / 0.412 / **0.494** | — |

⚠️ **诚实结论**：`#1+#2+#3` 对**离线指标**的增量 ≈ **0**（逐项同档）。原因不是改动错，而是**指标已饱和**（from@10 0.998 / from@5 0.941 / 分层 AUC early 逐位持平 +0.0378）。信念头**确实学到了新东西**（+0.030 超「布局先验」这条最强基线，且残局更好），但那是**一项新能力**，不是 policy/value 的提升。⇒ 强度只能由镜像对照回答（见 I）。

**下游预验证（省掉 43 分钟白跑）** —— 用**短训临时 ckpt** 提前把下游跑通，跑完**逐字节还原**并比对 sha256：
`--export`（**89 键 / n_ch=26**；信念头权重导出但 `NPNNet` 不读 ⇒ 不可能借它泄漏）→ `--verify --n 60`（`max|Δ| 7.6e-06`，**排序全同 60/60**）→ `--mutate --n 20`（**5 类注入 bug 全检出、M0 不报**）。

⚠️ **重训前的「必然红」要认得**：`encode` 已 26 通道而线上 npz 仍 20 通道时，任何走 net 先验的路径都会报
`ValueError: matmul ... (size 180 is different from 234)`（`human_vs_ai.py --selftest` 会红、`JUNQI_NET_PRIOR=1` 会红）。
**线上 8765 不受影响**（`NET_PRIOR` 默认关 + 进程攥旧 inode 跑旧码）⇒ **重训 + 重导出 npz 即闭环**（实测重训后 `--selftest` 18 组全过）。

**并发决策（反直觉但正确）**：`PIMCPolicy` 在镜像里 `think_seconds=None` ⇒ 走 **`node_budget=npw`（节点驱动，结果确定、可复现）**，**不是墙钟** ⇒ **并发训练不会污染镜像结论**，只拖长墙钟。据此不必等镜像收口就能起训练。
（先决条件：确认 `think_seconds` 没被设 —— 若哪天改成按时间驱动，这条推理立即失效。）

### H. 坑（可复用）

1. ⚠️⚠️ **同一张表被抄两份 = 迟早分叉**（本轮 `CH_SCALE` 256× 血案）。判据必须能**从数据自身推出**（「encode 写入 0/1 还是 0..255」），并且**只留一个定义处**。
2. ⚠️⚠️ **正反两条才算探针**：只查「上界不越界」会把「量化通道错写成 0/1」放过去 ⇒ 必须同时要求「量化通道真的出现过 >1」。
3. ⚠️⚠️ **「重排 → 重新 drive → 中途比对」全是伪差异**：状态发散 ⇒ 必须在**同一局面对象**上重贴标签。
4. ⚠️⚠️ **探针的盲区要主动量出来**：重排探针**按设计**抓不到多重集型泄漏 ⇒ 用 M2 臂把盲区显式量化，再补 `source_guard` 兜底。**两条防线缺一不可。**
5. ⚠️ **推理框架要被「训练侧结构变化」驱动**：`SLNet` 自适应 `has_belief` 否则旧 ckpt 直接崩。
6. ⚠️ **训练前先跑一遍下游**（用短训临时 ckpt）：否则 43 分钟跑完才发现 `--export/--verify` 不通。**跑完必须逐字节还原并比对 sha256**。
7. ⚠️ **`sl_mirror_20261002.py` / `mirror_match.py` 里的 `APP` 是写死的实时路径**，且 `mirror_match` 会在 `HERE` **之后**再 `insert(0, APP)` ⇒ **核心模块实际从实时工作树加载**。所以：① 冻结快照必须**同时**改 `mirror_match.py` 的 `APP`；② **镜像跑完前绝不能碰 `实战桥Windows版/`**（打包脚本 `--out` 默认就是它，会 `rmtree`）。事后靠 `frozen_hashes.json`（逐文件 sha256）证明「跑的是同一份」。
8. ⚠️ **背景任务会被延迟启动**（本轮实测：`run_in_background` 的命令 ~5 h 后才真正执行）⇒ **起长跑任务后必须「回读日志头 + 时间戳」确认它真的在跑**，不能只看「已启动」。另外**别把每组输出 `| tail -25`**：那样整组跑完才落盘，中途完全看不到进度。
9. ⚠️ **符号链接要验证能否解析**：`ln -s ../../ld/dataset.jsonl` 层级写错时**不报错**，要到运行时才 `FileNotFoundError`（三臂瞬间全灭）。⇒ 建完立刻 `os.path.realpath` + `os.path.exists` 验证。

### I. 强度结论（镜像三臂 + ⚠️ 本批空对照异常）

**命令**：`--n 80 --offset 260 --jobs 8 --npw 2500 --exp-ranker net --exp-root-limit 6`（三臂）。
**05:41:44 → 09:22:55**，三组 4495.5 / 4367.5 / 4401.9 s（**3 h 41 m**），**非法着法 0**。
产物 `.workbuddy/snap_belief_20261003/mirror_*_n80_new_20261003.json`。

| 臂 | 实验方 vs 对照方 | W/L/D | 符号 p | Δ 均值 | SE | t | p(t) | 95% CI |
|---|---|---|---|---|---|---|---|---|
| [1] 空对照 | net+截6 vs net+截6 | 18-29-113 | 0.1439 | **−130.2** | 55.2 | −2.36 | **0.0208** | [−238.4, −22.0] |
| [2] M1 | net+截6 vs **纯 PIMC** | 23-16-121 | 0.3368 | +106.0 | 67.4 | 1.57 | 0.1196 | [−26.0, +238.0] |
| [3] **M2** | net+截6 vs **mv+截6** | **33-0-127** | **0.0000** | **+341.4** | 62.8 | **5.44** | **0.0000** | **[+218.3, +464.4]** |

口径③ 终局分解：M2 `mixed` 30 配对 **Δ+725.7** / `timeout` 50 配对 +110.8；
M1 `timeout`/`mixed` = +45.4 / +263.8；空对照 = −46.8 / −299.2。
（页面口径 VAL_PAGE 均值：空对照 −44.1 · M1 +34.7 · M2 +113.9。）

#### ⚠️⚠️ 一等公民警报：本批空对照**没有落回 0**

`net vs net`（两臂**同配置**、只差 RNG seed）本该只回答「0 效应能测出多大」，
但本批给出 **Δ −130.2（t=−2.36 · p=0.0208 · CI 不跨 0）**，**配对符号检验 p=0.0049（53/80 为负）**。

**不是离群点驱动**：截尾 10%（去最大最小各 8 个）后仍 **−129.6**，中位数 **−142**
⇒ 这批布局的噪声地板**整体偏负**。

**查清它 = 三份独立空对照**（每份 80 配对；**配置完全相同** `net/net · npw 2500 · root_limit 6 · K 6 · depth 8 · null=True · reveal_winner=False` ⇒ **可池化**）：

| 批次 | 来源 | Δ 均值 ± SE | t |
|---|---|---|---|
| offset 100 | 旧网 n=80 空对照 | +50.4 ± 59.5 | +0.85 |
| offset 180 | ⭐**免费样本**：n=160 空对照的**后 80 个配对** | −15.2 ± 57.9 | −0.26 |
| offset 260 | **本轮**新网空对照 | −130.2 ± 55.2 | −2.36 |
| — | **三批等权池化** | **−31.7 ± 33.2** | **−0.95** ⇒ 未达显著 |

⚠️ **但批间 SD ≈ 91.4 > 批内 SE ≈ 57** ⇒ **布局批次间异质性可能被批内 SE 低估**，单批的 ± 区间偏乐观。

#### 关键：这个异常**折不倒** M2（三读法都算）

| 读法 | M2 的 τ̂ | SE | t | p |
|---|---|---|---|---|
| 不校正（主口径） | +341.4 | 62.8 | 5.44 | 0.0000 |
| 按本批地板 −130.2 校正 | +471.6 | 83.6 | 5.64 | 0.0000 |
| 按三批池化地板 −31.7 校正 | +373.1 | 71.0 | 5.25 | 0.0000 |

**为什么一定成立**：本批地板是**负**的（对实验方**不利**），而 M2 与空对照**同布局、同 seed 派生结构、
同实验方配置**，**唯一差别是对照方从 `net+截6` 换成 `mv+截6`** ⇒ 地板偏负只能让 M2 的观测值**偏小**，
**不可能凭空造出 +341**。⇒ **+341.4 是保守估计**。

**M1 则不稳健**（如实标注）：+106.0（p=0.1196） / **+236.2（p=0.0082）** / +137.7（p=0.0705）
⇒ 按 §12.2 **取更保守 = 报「未检出差异」**。

#### 新网 vs 旧网（M2）：**本轮不能说新网更强**

两个 M2 用**不同布局区间**（100..179 vs 260..339）⇒ 只能**两样本**比较、**不可配对**：

| 读法 | 新网 | 旧网 | 差 | t | p |
|---|---|---|---|---|---|
| 原始（主口径） | +341.4 (62.8) | +218.1 (69.1) | +123.3 | 1.32 | 0.1886 |
| 各自按本批地板校正 | +471.6 (83.6) | +167.7 (91.2) | +303.9 | 2.46 | 0.0151 |

**两种读法冲突 ⇒ 按 §12.2 取更保守 ⇒ 本轮不能说新网更强**（与离线「增量 ≈ 0」的预期一致）。

#### 结论与纪律

* **故事与旧网同构**：M1 未检出差异（**截断到网络 top-6 免费**）+ M2 显著（**同宽度下网络排序带来可测增益**）。
  ⇒ **#1/#2/#3 对强度无可测增益**。旧网 n=160 M2（独立超集）Δ**+276.9**（p=0.0000 · 54:0）作为旁证。
* ⭐ **要干净判定新旧网孰强，唯一办法 = 同批次直接对打**（实验方新 ckpt vs 对照方旧 ckpt，**同一批布局**
  ⇒ 地板项完全抵消）。当前镜像脚本只有**一个全局网络实例**（`sl_mirror_20261002.py` 的 `_NET[0]` 单例），
  要做得先加「**双网络**」支持。
* ⭐⭐ **纪律：「空对照没落回 0」必须当成一等公民查**。三步：
  ① 判是否**离群点驱动**（截尾 / 中位数 / 配对**符号**检验，别只看 t）；
  ② 取**多份独立空对照池化**定偏置（新批次跑不动就去找**已有数据的尾部**当免费样本）；
  ③ 对主结论做**多读法稳健性**（不校正 / 本批校正 / 池化校正）。
  ⚠️ **只有当地板偏负（不利于实验方）时，「不校正」才是保守读法**；地板偏正时相反。
  别因为「探针一向没红过」就跳过这一步。

#### ⭐⭐ ⇒ 已完成（2026-10-03）：**同批次直接对打**（本节上一版写的「唯一办法」，现已落地）

`zsh .workbuddy/tests/run_h2h_n80_20261003.sh`（快照 `snap_h2h_20261003`，含 `sl_mirror` 的**双网络**支持：
单例从 `_NET[0]` 改成**按 ckpt 路径索引的表**）。三臂**同批布局**（`--n 80 --offset 260 --jobs 8 --npw 2500 --root-limit 6`），
**3 h 44 m**，**非法着法 0**：

| 臂 | 实验方 vs 对照方 | W/L/D | 符号 p | Δ 均值 | SE | t | p(t) | 中位 | 负:正 |
|---|---|---|---|---|---|---|---|---|---|
| [1] **H2H** | **新网 vs 旧网** | 21-30-109 | 0.2624 | **−25.6** | 59.4 | −0.43 | **0.6664** | **+3.0** | **40:40** |
| [2] 空对照·新网 | 新网 vs 新网 | 18-29-113 | 0.1439 | **−130.2** | 55.6 | −2.34 | **0.0191** | −142.0 | 53:27 |
| [3] 空对照·旧网 | 旧网 vs 旧网 | 29-20-111 | 0.2529 | **+18.3** | 61.4 | +0.30 | 0.7658 | +24.0 | 39:41 |

⭐ **⇒ 新网 vs 旧网：无差异。** H2H 的 Δ **中位 +3.0、负:正 = 40:40**（教科书级纯噪声形态），胜负 21:30（p=0.262）也不显著
⇒ 与本节「不能说新网更强」一致，但现在是**直接对打的干净证据**（同批布局 ⇒ 地板项抵消）。
⚠️ 两点如实标注：① **MDE（80% 功率）≈ ±155~171** ⇒ 本设计**只能**发现极大差异，观测到的 −25.6 远小于此；
② 第 [2][3] 臂**只差「挂哪份 ckpt」**，地板就从 −130.2 变到 +18.3（逐布局配对差 **−148.5 ± 88.0, t=−1.69, p≈0.095**，未达显著）
⇒ **地板波动 ~±150，量级与待测效应相当**。
**逐布局配对拆两臂权重效应**：**ctl 臂 旧→新 = −104.6（p≈0.20）** vs **exp 臂 新→旧 = +43.9（p≈0.62）** ⇒ **符号相反**
⇒ **不存在一致的权重效应**（与「无差异」互相独立的第二条佐证）。

⭐ **确定性交叉验证**：本轮的**空对照·新网**与 §28.28 I 上一版的**空对照**（`snap_belief_20261003`，**默认 ckpt**）
**80 个配对值逐位相同**（`diffs` 全等，`d_mean = −130.225`）⇒ **跨快照/跨「默认 vs 显式 ckpt」两次独立运行完全复现**。
⚠️ **含意**：这个「地板异常」是**确定性事实**，**重跑多少次都一样** ⇒ §28.28 I 里那些「符号检验 p=0.0049 / t p=0.0208」
描述的是**跨布局**的变异，**不是重复实验的抽样分布** ⇒ **不能靠复跑来确认/推翻它**，只能**换布局批次**或**改 seed 结构**去扰动。

#### ⚠️⚠️ 读源抓到的**结构性硬伤**：`sl_mirror` 的 seed 奇偶与臂号**完全共线**

`sl_mirror_20261002.py` L336 `seed = a.seed + i*10 + (0 if exp_is_A else 1)`，再 L235 `seed*31 + DIRS4.index(d)`。
而 **`DIRS4=['up','right','down','left']`、`A_SET={up,down}` = 下标 `{0,2}`（全偶）**、补集 = 下标 `{1,3}`（全奇）：

| 局 | base | 实验方 | 对照方 |
|---|---|---|---|
| `exp_is_A=True` | 7 | `{217,219}`（**奇**） | `{218,220}`（偶） |
| `exp_is_A=False` | 8 | `{249,251}`（**奇**） | `{248,250}`（偶） |

**解析证明（与 `i`、`--seed` 取值无关）**：`parity(seed) = parity(base) XOR parity(idx)`，其中
`parity(base) = p(S) XOR (¬A)`、`parity(exp_idx) = (¬A)` ⇒ **两次相消** ⇒
**实验方的 4 个 seed 恒同奇偶、对照方恒为相反奇偶**（实测 `S=0,1,7,8,13,100` × 两种角色全部成立）。

⇒ **空对照测到的 Δ 就是「奇 seed 实现 vs 偶 seed 实现」之差**，并被**整段带进 H2H**。
`PIMCPolicy.rng = random.Random(seed)`（`ai_search_dark.py:245`），`sample_world` 用 `rng.shuffle/random` 消耗它
⇒ seed 直接决定抽出的世界。
⚠️ **尚未证明因果**（MT19937 对奇偶无预先偏向）—— 这是**头号机制候选**，不是结论。
**便宜的决定性测试**：同布局跑空对照 `--seed 7`（奇）vs `--seed 8`（偶）⇒ 会**整体对调**两臂的 seed 奇偶；
若地板显著移位 ⇒ 奇偶共线是主因。

#### 附：两网「行为上到底差多少」（离线，秒级）

同批局面（14 局 × 6 frac，n=84 个决策点）比两 ckpt：

| 指标 | 值 | 读法 |
|---|---|---|
| `value` 头相关 | **0.9917** | 信念头**几乎没改变**价值估计（new 均值 .532 / old .517） |
| 根排序 **top-1** 一致率 | **0.655** | 走法策略**确实不同** |
| top-6 集合重叠 | 0.768 | 同上（未排除「近似并列」造成） |

⇒ **改动确实进了 policy（≈35% 决策换首选），但没转成强度** ⇒ H2H 的「无差异」是**测过一个真差异**的结果，
**不是**「两网本来就一样」。

#### ⇒ 修正 + 修复（2026-10-03 ·「执行下一步 便宜→贵」①②③）

⚠️ **先纠正上面那块的一个读源错误**：`sl_mirror.make_arm` 里 `seed*31+idx` 被**应用了两次**
（调用点一次 + `make_arm` 内一次）⇒ 实际喂给 `random.Random` 的是

```
pimc_seed = (s*31 + idx)*31 + idx = 961*s + 32*idx     （idx = DIRS4.index(d)）
```

⇒ **同一局四家奇偶 / 低 5 位完全相同**（`parity(E) = parity(s)`），**不存在**上面写的
「实验方恒同奇偶、对照方恒相反」（那是按**单次**应用算出来的）。
旁证：独立入口 `ai_search_dark.py:508` 用的是**单次** `seed*31 + i*7 + idx`
⇒ sl_mirror 的双次是**独立入口的复制粘贴残留**（不改，无害）。

⭐ **真正稳的缺陷不是奇偶，而是「座席项破坏了精确镜像」**：
旧式 job seed = `a.seed + i*10 + (0 if exp_is_A else 1)` ⇒ 同一布局的**两局用不同 RNG**
⇒ 两局**不是**「同 seed 的座席互换」⇒ 座席效应**不能严格抵消** ⇒ 空对照出现**非零地板**
（offset 260 = **−130.225**, p=0.019，且**随 ckpt 变**：旧网 +18.3）。

🔧 **修复**（`ld/sl_mirror_20261002.py` · 去掉座席项）：

```diff
-  a.seed + i * 10 + (0 if exp_is_A else 1)
+  a.seed + i * 10
```

⇒ 两局**共享 base seed** ⇒ `--null` 两局策略**逐位相同** ⇒ 座席严格抵消 ⇒ **地板恒为 0**
（实测 n=2：坐甲 `+626` / 坐乙 `−626` ⇒ 配对和 `+0`；`t`/Wilcoxon 退化为 `n/a`，
`t_test_one` 已守 `var<=0`）。
⇒ H2H 升级为**精确配对设计**（座席效应抵消、方差更低）；噪声改由 H2H **自身配对 SE** 估计。
⚠ 备份 `tests/bak_20261003/sl_mirror_20261002.py.bak_pre_seedsym_20261003`（sha256 `16f23e91…`）；
改后 **23813 B** / sha256 `e201c570…`。
⚠⚠ **旧号作废**：任何历史镜像 Δ 均在**旧（非对称）seed** 下取得，不可与新码混用。

📊 **①② 结果（2026-10-03 20:59 → 23:15 · 非法着法 0 · 快照 `snap_h2h_20261003`）**：

| 臂 | offset | seed | W/L/D | Δ | SE | p(t) |
|---|---|---|---|---|---|---|
| 基线（∈#1） | 260 | 7 | 18-29-113 | **−130.2** | 55.2 | **0.0191 ★** |
| ① 诊断 | 260 | **8** | 22-26-112 | **−92.5** | 64.2 | 0.1523 |
| ② 新批 | **340** | 7 | 22-24-114 | **+70.3** | 67.0 | 0.2974 |

- **① `--seed 7→8` 不翻转地板**（两臂都**负**；逐布局配对差 −37.8 ± 103.7 · t=−0.36 · **n.s.**）
  ⇒ **「seed 奇偶因果」不成立**（与上面「同局四家同奇偶」的解析一致）。
  ⚠ 附带观察：逐布局 `corr(Δ7, Δ8) = **−0.506**`（n=80 时约 4.5σ，**显著负相关**）—— 机制未明，记着别丢。
- **② 地板随批次乱走且变号**：−130.2（off260，★）→ **+70.3**（off340，n.s.）
  ⇒ 那个「显著地板」是**本批次的偶然**，**不是固定偏置**。
- **合起来**：地板 = **确定性噪声**（均值≈0 · 散布 ~±130 · 随 **ckpt / 批次 / seed** 三者变），
  **量级与待测效应 / MDE（±155~188）相当** ⇒ **不能当常数「校正」**
  （§28.28 I 早先那种「减地板」读法要打折 —— 减掉的那个地板自己就是一次噪声抽样）。
  ⇒ **结构性修复（上）才是正解**：它把「同一布局两局 base seed 不一致」这一项**彻底消掉**。
  ⇒ 旧号（#1 H2H Δ −25.6 · #142 leaf Δ −327.1）**多带一项乱走地板**；但**远大于 ±130 的效应结论仍成立**
  （尤其 #142 的 −327，地板挪 ±130 翻不动它）。

**⇒ #148 重跑（2026-10-04 · 精确配对口径）**：新快照 = 前身**逐字节复制** + **只替 `sl_mirror`**
（`snap_seedsym_20261003` ← `snap_h2h_20261003`；`snap_leaf_seedsym_20261003` ← `snap_leafguard_20261003`；
生成器 `tests/make_snap_seedsym_20261003.py`，5 条断言）⇒ **前后只差「seed 口径」一处**。

| 臂 | 旧号（非对称 seed） | 新号（精确配对） |
|---|---|---|
| 空对照 n=8 | （同批 −130.2 系） | **Δ = +0.00 · 非零 diffs 0/8**（**硬断言**） |
| H2H 新网 vs 旧网 n=80 off260 | −25.6（p=0.67） | **−50.1（p=0.40 · SE 58.7 · MDE ±164）** |
| #142 leaf vs none n=40 off400 | −327.1（p=0.0007） | **−323.8（p=0.0016）** · 逐布局配对差 **+3.4** |

⇒ 两轮结论**都稳**（H2H **无差异** / leaf **仍有害**），且 **Δ 不再需要减地板**。
⚠⚠ **修的是「偏置」不是「噪声」**：SE **没降**（59.1→58.7 / 94.9→101.4）⇒ 逐布局**世界采样方差照旧**
⇒ **MDE 仍 ±164（n=80）/ ±284（n=40）** ⇒ **要判更小的效应仍只能加 n**（口径修复替代不了样本量，只让读数干净）。
⚠ **建快照断言坑**：判「座席项已消失」别拿**裸片段** `0 if exp_is_A else 1`（会被**修复注释里引用的旧写法**顶成
`count==1` 假红）⇒ 必须查**可执行行** `a.seed + i * 10 + (0 if exp_is_A else 1)`。
⚠ 快照 `app/search.py` 有两版（h2h 系 `48354`/`7823cbd7` 旧守卫前；leaf 系 `49731`/`3c3255c7` 守卫版）——
**用哪版取决于该臂要不要走 leaf 钩子**（`leaf=none` 时两版逐位等价）。

### J. 收尾（便携包 + 8765 重启 + 全量回归）与 ⚠️⚠️ 新坑：**测试口被外部驱动**

**一致性检查**：`sync_bridge_frontend.py` **默认就是「只检查」**（加 `--apply` 才写）⇒ 本次输出
「前端一致（`fd33463e`）+ 运行时 22 个文件与 `ld/` 一致 ⇒ **无需对齐**」。

**便携包重出**：app/ **23** 文件 / **2998 KB** / `实战桥Windows版.zip` **2.1 MB**。关键 sha8：

| 文件 | 字节 | sha256_8 |
|---|---|---|
| `sl_data_20261001.py` | 34279 | `acb7a2c1` |
| `sl_net_np_20261002.py` | 18473 | `db3c57a9` |
| `sl_net_20261001.npz` | 1631468 | `1880ecf5` |
| `human_vs_ai.py` | 95468 | `a4186476` |
| `四国军棋实战桥.html` | 148544 | `fd33463e` |

⚠️ **打包会 `shutil.rmtree(out)`，而 `--out` 默认就是工作树** ⇒ 先把 `app/*.bak_pre_*` 挪到 `tests/bak_20261002/`。
⚠️ **打包源全在 `.workbuddy/ld/`**（`APP_FILES` 逐个从 `HERE` 读），`--out` 只是**重建目标**。

**8765 重启 = 「进程活 ≠ 代码对」第五次重演**：诊断显示 cwd = `10-25-18-425/app`（时间戳正是刚打包重建工作树的那一刻）
—— 进程攥着**被搬走的旧 inode**。`restart_8765.py --fix`（**按端口精杀**）⇒ 四项全绿；
服务端返回前端 `148544 B / fd33463e` ≡ 工作树**逐字节一致**。

⚠️⚠️ **但 `--fix` 会留下一个「残留 VS 会话」，必须最后清掉**：它的**诊断第 ④ 条**会 `POST /api/vs/new`
去读 `layout_rule` 指纹 —— **这个 POST 本身就在服务端造了一个对战会话**；前端的「会话接回」逻辑
⇒ **坚哥一刷新就被切到对战视图**。判据：`GET /api/vs/state` **不含 `active` 键** = 会话存在。

⭐ **正解**：`--fix` 之后再跑一次 **`launch_bridge_20261002.py --port 8765 --restart`** ——
它与 `restart_8765.py` 的**启动实现逐字相同**（同 `SERVER` / 同 `cwd=APPDIR` / 同 `start_new_session` / 同日志路径
`/tmp/bridge_8765.log`），区别只在**用 GET 自验、绝不碰 `/api/vs/new`**。
**最终三面验收**：`active == False` · 前端 `fd33463e` ≡ 工作树 · 读屏 `calibrated=false n_apply=0 watching=false`（本轮最终 **PID 98380**）。

**回归（跑在干净端口上）**：`bridge_e2e` **92/0** · 坐标透传 **10/0** · 风格 e2e 四档各 **6/6** + random 6/6 ·
烟测 `vs_v6` **47/0** · 便携包烟测 **74/74** · 打包闸门**正样本 + 5 负样本全过**。

#### ⚠️⚠️ 新坑（与 §28.24 的「VS 残留会话劫持」**同一个「干净实例」概念的第二面**）

**现象**：`:8771` / `:8772` 上 `bridge_e2e` 各报 **90 / 2**，两项失败都在读屏段
（`未标定时「开始监控/停止/刷新预览」全部禁用` 与 `/api/vision/state：尚未标定`），
后端却回 `calibrated:true, n_apply:1`。**看起来完全像读屏被我改坏了。**

**排查三步**：① 全新实例刚起时**确实干净**（`calibrated=false, n_apply=0`）；
② 在 `:8772` 上**只发过只读 curl**，两次查询之间 `n_apply` 却从 **1 涨到 2**；
③ **决定性实验**：换一个**从未用过**的端口 `:8901`，静置 45 s + 90 s 状态**纹丝不动**，
同一份 e2e 跑出 **92 / 0**。⇒ **污染是「端口特定」的**（上轮遗留页面占用并驱动了 8771/8772），与代码无关。

**正解（三条）**：
1. 跑 e2e **用全新未用过的端口**；
2. 起服务后**不只验** `/api/vs/state` 的 `active is False`，**还要验读屏三件套**
   `calibrated=false · n_apply=0 · watching=false`；
3. 清测试口**按端口精杀**（`lsof -ti :$p | xargs -n1 kill -9`），**绝不动 8765**。

⭐ **判据升级**：`active is False` **不等于**「干净」。**「干净」= VS 会话 ∧ 读屏状态 两面都归零。**

⚠️ 另一个小坑：`bridge_e2e_20260925.js` 的 `--out` 目录**必须预先存在**，否则第一次截图就
`ENOENT` 崩在 **[A2]**，**把后面全部检查都掩盖掉**（看起来像「跑到一半挂了」）。

**速记命令**：
```
python .workbuddy/tests/launch_bridge_20261002.py --port <新端口> --restart
curl -s http://127.0.0.1:<P>/api/vision/state      # 必须 calibrated=false / n_apply=0
node .workbuddy/ld/bridge_e2e_20260925.js --url http://127.0.0.1:<P>/ --out <先建好的目录>
python .workbuddy/tests/restart_8765.py --fix      # 8765 专用（别用 pkill -f）
```

---

## §28.29 ⭐ #112 叶节点估值：**量纲标定 + 离线 AUC 对照**（2026-10-03 · 第十五轮 #2）

> 坚哥指令：「**执行#1、#2、#3**」。本节 = **#2**。
> 一句话：**「网络 value 是有噪估计」这个解释被推翻**；量纲确实错但只错 **2.3×**；
> 叶钩子另有**终局接管**缺陷（压缩决定性信号 **52×**，但只占 0.29% 的叶调用）⇒ **第十二轮「leaf 有害」的机理仍未知**。
> 报告：<code>叶节点估值_量纲标定与离线对照_20261003.html</code>（项目根）

### A. 结论表（⚠️ 先看这张，别照抄旧结论）

| 问题 | 结论 | 判据强度 |
|---|---|---|
| `LEAF_SCALE=2000` 对不对 | **错，偏大 2.31×**（`k*=866.4`；剔开局段后 `905.8`）。现值 **R²=−0.347**（比用均值还差） | n=640，负样本 R²=0.015 |
| 网络 `value` 是不是噪声 | **不是**。预测真实终局 AUC **0.8701 vs eval_raw 0.7783**，Δ=**+0.0918** CI**[+0.0855,+0.0982] 不含 0**，早/中/晚全为正 | n=12780，负样本 0.5007 |
| 还有别的缺陷吗 | **有：叶钩子吃掉 `±W_WIN`**（`search.py:671` 的条件含 `not my_live()/opp_live()`）⇒ 终局叶返回 ±1927 而非 ±100000，**压缩 52×** | 双侧终局计数 **267/267 相符** |
| 那第十二轮为何有害 | **仍未被解释**。①2.3× 与 ③0.29% 都**不足以**单独解释显著负面 Δ | **开放问题** |
| **受控重测（G2）后呢** | ⚠️ **仍然显著有害**：净效应 **−314.6 ~ −331.4**（p≈0.019~0.027），**两个空对照都干净落回 0**（−12.6 / +4.2）⇒ **三机理全排除、伤害仍在** ⇒ 最可信的剩余解释 = **`npw=256` 太浅**（未跨台阶） | n=40 · **3-20-57** · 原始 Δ −327.1 |

⚠️ **纪律**：这是「**由错前提得出对结论**」的典型（§12.2）。旧结论「网络有噪 ⇒ 别接」**撤回**；
新状态是「**机理未知 ⇒ 受控实验再判一次**」。**不许**再拿「量纲」或「终局」当已解释的理由。

### B. 量纲标定（`tests/calib_leaf_scale_20261003.py`）

因变量 = **真实的** `Searcher.eval_raw()`（**不复刻** —— 复刻=造第二个真值源，即 §28.28 D 血案形态）。
自变量 `s = (value(x) − 0.5) × 2`。

| 量 | 值 |
|---|---|
| 无截距最优 `k*` | **866.4**（现值差 **2.31×**） |
| 量纲匹配 `k_sd = sd(eval_raw)/sd(s)` | 1242.5 |
| lstsq 带截距 | k=868.0 `b=−19.3`（截距可忽略） |
| R²（k* / k_sd / **2000**） | 0.4873 / 0.3955 / **−0.3468** |
| MAE（k* / **2000** / 常数） | 423.5 / **697.1** / 548.8（校准降 **39%**） |
| 符号一致率（k* / 2000 / 常数） | 0.666 / 0.666 / 0.500 ← **与尺度无关**（k>0 同号单调）⇒ 这是「方向质量」，不是量纲 |
| 剔 `frac≤0.02` 后 | n=560，**k*=905.8**（2.21×），R²+0.512，符号一致 **0.761**，MAE 438.3 |
| 分层 k* | early 831.6 / mid 952.4 / late 661.0 ⇒ **同量级，k*≈870 稳** |

`eval_raw` 全程极值 **±2197**（\|值\| 中位 464.2 / p90 1180.3）；
现值 2000 映射后 \|leaf\| 中位已 **944.9**、p90 **1829.5** ⇒ **网络项在叶节点上压过真实子力差**。

### C. ⚠️⚠️ 口径自检必须两道（**只用相关系数会漏**）

1. **联盟内恒等（确定性不变量，最锐利）**：同 `my_set` 的两个方位 `eval_raw` 必须**逐位相等** ——
   `eval_raw(up)==eval_raw(down)` 且 `(left)==(right)`。实测 **320/320 ✅**。
   若把 `d` 直接当 `my` 传，这里**立刻响**，而相关系数**不会**。
2. `corr(eval_raw, 纯子力差)`：实测 **0.7658** —— **预期就是 0.8~1.0 而非 1**
   （`eval_raw` 还含 `SW_GRAB=6 / SW_THREAT=30 / SW_UNLOCK=80 / SW_MOM=1.5 …`）。
   **只有 ≈0 或为负才是视角错** ⇒ ⚠️ **别把「不到 1」当成 bug 去调**。

### D. 离线 AUC 对照（`tests/eval_value_vs_evalraw_20261003.py`）

**为什么用 AUC 不用相关系数**：搜索在叶节点做**比较**（negamax 取 max/min）⇒ 重要的是**排序**；
AUC 对 `k>0` 单调变换**不变** ⇒ 能把「量纲错」（A/B 节）与「信息错」**干净分开**。

设置：400 局 × 9 frac × ≤4 方位；标签取**真实终局**（`sl_data._final_labels`：文件 `win` 标记，或终局存活推导）。

| 分组 | n | AUC value | AUC eval_raw | AUC 混合 |
|---|---|---|---|---|
| 全样本 | 12780 | **0.8701** | 0.7783 | 0.8422 |
| early <80 | 6256 | 0.8361 | 0.7188 | 0.7932 |
| mid 80–180 | 5312 | 0.9109 | 0.8373 | 0.8891 |
| late ≥180 | 1212 | 0.8440 | 0.7860 | 0.8353 |

配对差 Δ=AUC(value)−AUC(eval_raw)：全样本 **+0.0918 [+0.0855,+0.0982]**；
early +0.1173 / mid +0.0736 / late +0.0582 —— **全部不含 0**。
负样本（跨局面置换标签 ×20）：AUC **0.5007 ± 0.0052** ✅。

⚠️ **标签覆盖率 ≈40%**：其余是「文件无 `win` 标记 **且** 双方联盟都有存活」= **真判不出**（不是 bug）。
⚠️ **`|eval_raw| ≥ 1e4` 的终局满量程不计入**（两法都会「猜对」，无分辨力）。

⚠️⚠️ **必须说的局限（否则又是在用错原因下结论）**：`value` 头**就是被训练来预测终局的**
（标签= `win`）⇒ 它在「预测终局」上赢 `eval_raw` **有一半是循环论证**；
`eval_raw` 是**手写行棋启发式**，从没被优化去预测终局。
**严格表述**：本节**排除**「网络 value 是差估计量」这个解释，**不等于**「替换一定更好」。
**唯一能判定的是镜像对局。**

⚠️ **附带**：混合（`eval_raw + k*·网络项`）AUC **0.8422 < 0.8701** ⇒
**「小权重修正 eval_raw」这条路数据不支持**；要做混合必须让网络项**主导**。

### E. ⚠️⚠️ 终局接管（**读源确认的代码事实**，非统计推断）

`app/search.py:671`（`Searcher.negamax`）：
```python
if depth <= 0 or not self.my_live() or not self.opp_live():
    if self.leaf_value is not None:      # ← 装了钩子，**终局也走这里**
        v = self.leaf_value(self.board, turn, self.step_no, self.alive, self.cmdr_dead)
    else:
        v = self.eval_raw()              # ← 终局时返回 ±W_WIN = ±100000
```
而 `sl_mirror._mk_net_hooks` 的叶钩子**没有任何终局守卫**：
`return (net.value(x) − 0.5) × 2.0 × scale` ⇒ **「一方联盟被打光」被降级成一条普通估分**。

实测（8 局 × 4 frac × up，`node_budget=4000` / `K=6` / `depth=8`）：

| 项 | 带钩子 | 不带钩子 |
|---|---|---|
| 叶调用 | 90 672 | 92 673 |
| **其中终局叶** | **267** | **267**（**完全相符** ⇒ 归因确定） |
| 占比 | 0.29% | 0.29%（**只出现于 frac ≥ 0.99**；≤0.95 时为 0） |
| 该处 \|v\| 中位 | **1 926.9** | **100 000**（⇒ 压缩 **52×**） |

**为什么不足以解释第十二轮**：0.29% 的叶、且只在真残局（一局**只有最后约 1 步**落在 frac≈1.0）
⇒ 影响面「每局约 1 个决策点」。**值得修**（正确性问题），但**不可能**单独造成显著负面 Δ。

**⇒ 已修复 + 双向验证（2026-10-03 #1）**：`app/search.py` 叶分支加终局守卫，**钩子只在非终局叶生效**：
```python
terminal = (not self.my_live()) or (not self.opp_live())
if depth <= 0 or terminal:
    if self.leaf_value is not None and not terminal:      # ← 钩子让位终局
        self.n_leaf_net += 1
        v = self.leaf_value(self.board, turn, self.step_no, self.alive, self.cmdr_dead)
    else:
        v = self.eval_raw()                              # ← 终局仍拿 ±W_WIN
    return v if turn in self.my else -v
```
48354 → **49731 B**（md5 `2346bd913ef3df56`）；`sync_bridge_frontend.py --apply` 已对齐 `ld/search.py`（sha8 `3c3255c7`）。

**验证**（`tests/verify_leafguard_20261003.py`）**15 通过 / 0 失败**。手法 = **拿旧文件当对照模块**同进程对拍
（`.bak_pre_*` 后缀 `spec_from_file_location` 推不出 loader ⇒ 必须显式 `SourceFileLoader`）：

| 判据 | 结果 |
|---|---|
| 负样本 S1（终局叶 + 钩子恒返 `12345`） | 旧 **+12345（错）** → 新 **+100000**（= 无钩子真值） |
| 负样本 S2a / S2b | 旧 −12345 / +12345（错）→ 新 +100000 / −100000 |
| 正样本 S3（**非**终局 + `depth=0`） | 钩子**仍生效** ⇒ 守卫没把钩子整体关掉 |
| 黄金对照 `leaf_value=None` | old ≡ new（3 项） |
| 深搜逐位回归（4 局） | `best_move` / nodes=3072 / 深度 **逐位相同** |
| 计数 | 旧终局叶调钩子 **7**、新 **0**；`n_leaf_net ==` 钩子调用数；`new ≤ old` |
| `probe_leaf_terminal` 复跑 | 带钩子终局叶 **267 → 0**、不带钩子 **267 不变** |

⚠️ **我两次踩同一个坑**：拿「节点数不变」当负样本判据 ⇒ 钩子改估值 ⇒ alpha-beta 剪枝**必变**（1491 ≠ 1538−7）。
正解 = 断言「旧代码**确实**在终局叶调过钩子（>0）· 新代码**一次都不调**（==0）」。
⚠️ **期望值不许写魔法常数**：S2 里 `turn` 属于**获胜**联盟 ⇒ 从 turn 视角是 **+W_WIN**（negamax 按 `turn in my` 翻符号）；
应直接取**同模块无钩子运行**当真值（我首版写 −W = 探针错）。

### F. ⚠️ 本轮**探针自己的**三个坑（不查就信 = 白干一小时）

1. **`frac=0.0` 的「假斜率」**：开局对称 ⇒ `eval_raw` 均值/中位**恰为 0**、`sd(e)=35.7`，
   而 `value` 标准差 0.32 ⇒ 回归把**近常量目标**拟到变化的自变量上，**k*=−110.5、R²=1.000**。
   2 局冒烟时它把总体 `k*` 从 **866 拖到 116**（差 7 倍）。**必剔或单列**。
2. **「同树」作负样本判据是错的**：钩子改变估值 ⇒ alpha-beta 剪枝必变（实测 2512 vs 2508）。
   有意义的比法是**两侧的终局计数**（267 vs 267）。
3. **中盘搜不到终局叶**：`frac≤0.95` + `depth=8` 时终局叶恒为 **0** ⇒
   首版只采中点，得出「终局叶=0 ⇒ 缺陷不存在」的**假否定**。**必须残局采样**。

### G. 下一步（受控重测，把未知机理逼出来）

同一批布局（地板抵消）+ 必带空对照，三臂：

| 臂 | 配置 | 目的 |
|---|---|---|
| **A** | `leaf=none` | 参照 |
| **B** | `leaf=net` + **终局守卫** + `leaf_scale=1200` | 一并排除「量纲」与「终局」两个解释 |
| **C** | 空对照（B 配置只换 seed） | **噪声地板**（没有它不能说「无害」） |

成本用 `--npw 256`（⚠️ §28.26 A：(0,256] 等价）+ 同预算归因。
若 B vs A 仍显著有害 ⇒ 查**第三个候选机理**：`eval_raw` 独有的
`SW_UNLOCK=80`（敌司令阵亡 ⇒ 可扛旗）/ `SW_THREAT=30`（旗逼近）这两项**决胜知识**在 value 头里是否缺失。
先做**便宜的离线判据**：在「某方司令已阵亡」子集上单独比 AUC。

### G2. ⇒ 第三候选机理**已排除** + 三臂**已起跑**（2026-10-03 #3 / #4）

**离线分层 AUC**（`eval_value_vs_evalraw_20261003.py` 的 `unlock` 层）：

| 子集 | n | Δ = AUC(value) − AUC(eval_raw) | 95% CI |
|---|---|---|---|
| `unlock=0`（无「可扛旗」） | 2442 | +0.0725 | [+0.0515,+0.0923] |
| **`unlock=1`（敌联盟有司令阵亡 ⇒ 可扛旗）** | 10338 | **+0.0920** | [+0.0853,+0.0986] |

⇒ value 优势在「可扛旗」子集上**没消失，反而略大** ⇒ **「决胜知识在 value 头里缺失」不成立**。
`unlock` 定义 = **对方联盟任一方司令阵亡**（`any(cmdr_dead[k] for k not in my_all)`）。

⭐ **⇒ 三个候选机理（量纲错 · 差估计量 · 终局接管 / 决胜知识缺失）全部排除**
⇒ 问题**不在「叶估值质量」本身**。**唯一出路 = 受控镜像重测**。

**三臂已起跑**：`tests/run_leafguard_3arm_20261003.sh 40 400 256 5` —— 冻结快照 `snap_leafguard_20261003/`
（**含守卫版 `search.py`**；前置硬断言：守卫在快照里 · `import numpy` · 记 `search.py sha256` · 收尾**产物可解析**）。
三臂共用 `offset=400` ⇒ **地板抵消、不可相加**；实验路径 `node_budget` **优先于墙钟** ⇒ **与并发无关、完全确定性**。
臂：**A** `leaf=none` / **B** `leaf=net` + 守卫 + `k=1200` / **C** 空对照（= B 配置只换 seed）。

**⇒ 结果（2026-10-03 15:54 收口 · 三臂 4466.8 / 6470.9 / 255.1 s · 非法着法 0）**：

| 臂 | 配置 | W/L/D | 符号 p | Δ 均值 | SE | t p | W p | 95% CI | MDE |
|---|---|---|---|---|---|---|---|---|---|
| **B** | `leaf=net`(守卫,`k=1200`) vs `leaf=none` | **3-20-57** | **0.0005 ★** | **−327.1** | 94.9 | **0.0007 ★** | **0.0015 ★** | **[−513.2, −141.1]** | ±265.8 |
| C1 | 空对照·钩子侧（leaf=net vs leaf=net） | 7-5-68 | 0.7744 | **−12.6** | 94.9 | 0.8961 | 0.8290 | [−198.6, +173.5] | ±265.8 |
| C2 | 空对照·基线侧（leaf=none vs leaf=none） | 22-16-42 | 0.4177 | **+4.2** | 115.7 | 0.9711 | 0.8820 | [−222.6, +231.1] | ±324.0 |

⭐ **两个空对照都干净落回 0**（比 #1 那批干净得多）⇒ 本批**地板可信**。
**正式判据（实验臂 Δ − 空对照 Δ）**：

| 地板取法 | 净效应 | SE_diff | z | p |
|---|---|---|---|---|
| 钩子侧（−12.6） | **−314.6** | 134.2 | −2.34 | **0.0191 ★** |
| 基线侧（+4.2） | **−331.4** | 149.7 | −2.21 | **0.0268 ★** |
| 池化（−4.2） | **−323.0** | 120.9 | −2.67 | **0.0075 ★** |

⭐⭐ **⇒ 裁决：修掉终局接管 + 量纲 2000→1200 之后，`leaf` 仍然显著有害。**

**与第十二轮（§28.26 G · A2b）对拍**：

| | 第十二轮 | 本轮 |
|---|---|---|
| 配置 | `leaf=net`，**无守卫**，`k=2000` | **有守卫**，`k=1200` |
| 原始 Δ | −395.4 (SE 91.1) | **−327.1** (SE 94.9) |
| W/L/D | 3-21-56 | **3-20-57** |
| 净效应 | **−446.3**（p=0.0050 ★） | **−314.6 ~ −331.4**（p≈0.019~0.027 ★） |
| 口径③ `mixed` | −630.1 | **−706.0** |
| 口径③ `timeout` | −139.2 | **+20.9** |

⇒ **独立复现**（不同 offset/布局批次、不同 jobs、修了守卫、改了量纲）：原始 Δ **只缩小 17.3%**、胜负形态几乎不变
⇒ **「终局接管」与「量纲 2000」都不是主因**。
⭐ 口径③ 形态**完全一致**：`mixed`（能分胜负的局）巨负（−630 → **−706**）、`timeout` 近零
⇒ **不是拖延，是真在关键决策上走坏**（第十二轮原话，现已二次确认）。

⚠️ **仍然活着的解释（唯一没被排除、也最可信）**：**`npw=256` 太浅**。
§28.26 G 的处置原话就是「……并**跨 256 台阶**（如 2560）重测」—— **本轮没做**（三臂仍 `--npw 256`）。
在 768 节点/决策的极浅搜索下，**叶评估就是搜索的主要信息来源** ⇒ 用「排序更好但有噪」的 `value` 替换「精确但粗」的 `eval_raw` 必然退化
（§28.29 D 的 AUC **0.8701** 是**终局标签**口径、且**循环论证**，不能保证搜索内更好）。
**⇒ 下一步必须跨台阶**：`npw` 256 / 512 / 1024（n=20）⇒ 若伤害随预算上升而消失 ⇒ 是**浅预算问题**，不是叶估值本身。
⚠️ 成本：本轮臂 B 已 **4466.8 s**（n=40 @ npw256）；2560 是 ~10× ⇒ **先做 512 / 1024 两档**。

### G3. ⚠️ 本轮编排 / 回归**三坑**（每一个都会造成**假绿**）

1. **zsh 不对未加引号的 `$VAR` 分词**（≠ bash）⇒ `python x.py $COMMON` 把整串当**一个** argv
   ⇒ argparse 报「unrecognized arguments」（**像程序拒绝合法参数，实为 shell**）。**必须用数组 + `"${ARR[@]}"`**。
2. **编排脚本绝不无条件打印「完成」**：`{ ... } | tee` 块**不吃失败** ⇒ 三臂全崩仍打印「全部结束」。
   **以「产物存在 + 可解析」判成败**（`json.load` + `exit "$FAIL"`），**不看退出码、不看日志末尾**。
3. **裸 `python` 在本沙箱解析到 `versions/3.13.12`（无 numpy）** ⇒ 必须写死 `envs/default/bin/python`；
   并在前置**断言** `-c 'import numpy'`（否则 `ModuleNotFoundError` 同样被 `tee` 吞掉）。

### H. 触发词路由

| 碰到的事 | 查 |
|---|---|
| `LEAF_SCALE` 该取多少 · `k*` / `k_sd` / 现值 2000 的 R² | §28.29 B |
| 「网络 value 是不是噪声」· `eval_raw` 当基准可不可信 · AUC 对照 | §28.29 D |
| 叶钩子 `±W_WIN` 被吃掉 · 终局守卫 | §28.29 E |
| **`frac=0` 假斜率 · 「同树」判据错 · 中盘搜不到终局叶** | **§28.29 F** |
| 叶钩子修好后怎么验（负样本 + 黄金对照）· **「节点数不变」为何不能当判据** | §28.29 E |
| 第三机理（`SW_UNLOCK` 决胜知识）排除了吗 · 三臂臂配置 | §28.29 G2 |
| 编排脚本**假绿**（zsh 分词 / `tee` 不吃失败 / 裸 python 无 numpy） | §28.29 G3 |
| 三个脚本 | `calib_leaf_scale_20261003.py` · `eval_value_vs_evalraw_20261003.py` · `probe_leaf_terminal_20261003.py` + `verify_leafguard_20261003.py` · `run_leafguard_3arm_20261003.sh` |


## §28.30 ⭐ 第十四轮：**把最新 AI 训练成果接入实战桥 —— 网络先验默认启用**（2026-10-04 · 坚哥）

> 坚哥指令：「**将最新的 ai 训练成果运用到实战桥**」

### A. 摸查结论：**接线早就好了，卡在「便携包不带 numpy」**

| 项 | 事实 |
|---|---|
| 「最新成果」 | 监督模仿网络 **26ch + belief**（`sl_net_20261001.pt/.npz`：434 064 参数 · `stem.0.weight=(64,26,3,3)` · 含 `belief.weight/bias`） |
| 制品同步 | `实战桥Windows版/app/` = `.workbuddy/ld/` = 发布版 HTML（22 文件，`sync_bridge_frontend.py` 全绿）；npz `1880ecf5` |
| 接线 | `human_vs_ai._inject_net_prior()` 已实现：每步一次（~19 ms）根重排 + `NET_ROOT_LIMIT=6` 截断 |
| **卡点** | `NET_PRIOR` **默认关** —— 因为 **`make_bridge_portable` 既不带 numpy 也不 pip**（§28.26 附注），开了就 ImportError |
| 值不值得开 | **M2「net+截6 vs mv+截6」Δ+341.4 · 33:0 · p=0.0000 显著**（§28.28 I）⇒ 同宽度下网络排序**优于**手工启发式；M1 未检出差异 ⇒ 截断**免费** |

⇒ 「运用」= **① 解决 numpy 供给 + ② 打开开关 + ③ 重打包**。

### B. 四处改动（人改源 = `实战桥Windows版/app/`；改完必须 `sync_bridge_frontend.py --apply` 回灌 `ld/`）

1. **`human_vs_ai.py`：`NET_PRIOR` 默认 关 → 开**
   ```python
   _NET_OFF = os.environ.get("JUNQI_NET_PRIOR", "").strip().lower()
   NET_PRIOR = _NET_OFF not in ("0", "false", "no", "off")
   ```
   ⚠️ 只认**显式**关闭值；空白/未设 ⇒ 开。（旧写法 `not in ("", "0", "false", "False")` 是「默认关」。）
2. **`human_vs_ai.py`：`_net_prior_net()` 加 ImportError 优雅降级** —— 缺 numpy ⇒ `NET_PRIOR=False` +
   `sys.stderr` **打印一次** + `return None`；`_inject_net_prior` 见 None 即 return。
   ⚠️ **禁止静默降级**（会让人以为「网络在跑」）。
3. **`human_vs_ai.py` 自检 ㉔：正/负样本对调** —— 默认**必须开且注入**；显式关**必须零注入、零改 `coord`**。
   ⚠️ 旧断言「默认关时不得注入」在新默认下**必然红** ⇒ 按纪律**改测试**（不是回退默认）。
4. **`bridge_launch_20260925.py`：`net_prior_status()` + 启动横幅** ——
   打印「监督模仿网络先验：**默认启用**（numpy x.y.z）」或「不可用（原因）⇒ 自动回退手工启发式」。
5. **`make_bridge_portable_20260925.py`**：① bat 加 **1b 分支**；② README 加 AI 说明；③ 打包对 `.zip` 用 **ZIP_STORED**
   （25 MB 已压缩数据别重复 deflate，白耗十几秒 CPU）。

### C. ⚠️⚠️ 定制 Python zip（本轮的真正工程）

**做法**：把 numpy **预先塞进那个 `python-3.11.9-embed-amd64.zip` 本身**，**文件名不变**
⇒ `.bat` 主体**零改动**（复用既有「首次运行解压到 `python-embed\`」逻辑）。
生成器：`tests/build_python_embed_numpy_20261004.py`（官方 embed 34 条目 + numpy wheel ⇒ 25.4 MB / sha256 `758ea082…`）。

**⚠️ 必须做的一件事**：在 `python311._pth` 里加 `Lib\site-packages`：

```
python311.zip
.
Lib\site-packages        ← 不加就**静默** import 不到 numpy

# Uncomment to run site.main() automatically
#import site
```

**为什么**：embeddable 发行版**只要存在 `*. _pth`** ⇒ Python 进 **isolated 模式**
（`sys.path` **只**由 `_pth` 决定，且默认**不执行** `site`）⇒ 光把 numpy 拷进
`Lib\site-packages\` 是**没用**的，而且失败信息指向 `import numpy`，看着像包坏了。

**其余要点**：
- numpy 落位：`Lib/site-packages/{numpy, numpy.libs, numpy-1.26.4.dist-info}`（三者同级；`numpy.libs` 里是 38 MB openblas，体积主因）。
- **剥离 `numpy/**/tests/`**（未压缩 6.2 MB，推理用不到）。
- ⚠️ **跳过 wheel 里 pip 留的 0 字节 `*.whl` 标记文件**（`numpy-1.26.4-cp311-cp311-win_amd64.whl`）——
  照抄会污染 `site-packages`（无害但脏）。判据：**只收**顶层 ∈ {`numpy` / `numpy.libs` / `*.dist-info`}。
- 版本：**numpy 1.26.4**（最后 1.x，官方支持 3.9–3.12）+ **cp311 win_amd64** ⇒ 与 embed 的 `python311.dll` 同 ABI。
- 下载源：阿里云 PyPI 镜像（`pip download ... --platform win_amd64 --python-version 311`）+ 华为云 python 镜像。

### D. bat 的 **1b 分支**（升级路径，最易漏）

```
rem ---- 1b) python-embed exists but is an OLD one WITHOUT numpy ----
if defined PYEXE if not exist "%ROOT%python-embed\Lib\site-packages\numpy\__init__.py" (
  if exist "%ROOT%python-3.11.9-embed-amd64.zip" (
    echo [setup] Adding numpy to the existing bundled Python ...
    powershell ... "Expand-Archive -Force ... -DestinationPath '%ROOT%python-embed'"
  )
)
```
⚠️ **不做这一步**：用户跑过旧包（`python-embed\` 已存在但无 numpy）⇒ 分支 1) 命中 ⇒ `PYEXE` 已定 ⇒
分支 2)（首次解压）**永不执行** ⇒ **永远拿不到 numpy**，且**完全静默**。

### E. 验证矩阵（Mac 侧全绿；⚠️ **Windows 二进制跑不了，须坚哥双击实测**）

| 项 | 结果 |
|---|---|
| `human_vs_ai.py --selftest` | ✅ 通过（含改后的 ㉔） |
| `tests/probe_netprior_numpy_absent_20261004.py` | ✅ ①~④ 缺 numpy ⇒ None / 置 False / 零注入 / 不崩；⑤ 恢复后能构造（**反证降级分支有分辨力**） |
| `live_bridge_server --selftest` | ✅ 全部通过（暗棋口径 / 分辨力负样本 / 亮旗） |
| `bridge_e2e_20260925.js`（8771 干净实例） | ✅ **92 / 0** |
| `bridge_launch --check` | ✅ 横幅「默认启用（numpy 2.5.2）」 |
| 三处 sha256 | ✅ 构建产物 = 包内 = zip 内提取（`758ea082…`） |
| 解压后 `site-packages/` | ✅ 仅 3 项（干净） |

**产物**：`实战桥Windows版.zip` **2.0 → 27.4 MB**。
**关键指纹**：`human_vs_ai.py` **98691 B** / `9ee13047` · `bridge_launch_20260925.py` **8784 B** / `6b5f3442` ·
`search.py` **49731 B** / `3c3255c7`（守卫版）· `sl_net_20261001.npz` 1631468 / `1880ecf5`。

### F. 速查

| 碰到的事 | 查 |
|---|---|
| 网络先验开关的默认值 / 怎么强制关 | §28.30 B1（`JUNQI_NET_PRIOR=0/false/no/off`） |
| 缺 numpy 会怎样 / 为什么不静默降级 | §28.30 B2 |
| 定制 Python zip 怎么来的 / `_pth` 为什么必须改 | §28.30 C |
| 升级老包为什么还是没 numpy | §28.30 D（bat 1b 分支） |
| 包多大 / 各文件指纹 / Windows 侧怎么验 | §28.30 E |
| 两个新脚本 | `tests/build_python_embed_numpy_20261004.py` · `tests/probe_netprior_numpy_absent_20261004.py` |

---

## §28.31 Mac 侧 8765 真常驻（launchd 自启 + 掉线自动拉起）

**触发**：Mac 上 8765 要「开机自启 / 掉线自动拉起 / 重启后自动回来」。

### A. 落地产物（2026-10-04）

| 文件 | 作用 |
|---|---|
| `~/Library/LaunchAgents/com.junqi.bridge-8765.plist` | `RunAtLoad` + `KeepAlive` + `ThrottleInterval=60`；日志 → `~/.junqi-bridge/logs/bridge-8765.{out,err}`；`ProgramArguments = [/usr/bin/python3, <wrapper>]` |
| `.workbuddy/ld/launchd_bridge_wrapper_20261004.py` | 等 `/Volumes/me` 就绪（≤120s）→ 按候选挑**带 numpy** 的 Python → 端口预检 → **`os.execv` 替换自身**（launchd 直接盯服务进程，无中间进程） |
| `~/.junqi-bridge/venv/` | **自持 venv**：`/usr/bin/python3` 3.9.6 + **numpy 1.26.4**（清华源）⇒ 网络先验可用、且**不依赖 WorkBuddy 托管目录** |
| `.workbuddy/ld/安装实战桥开机自启_20261004.command` | 双击：清 8765 旧实例 → bootout → bootstrap → 20s 就绪探测（输出落 `~/.junqi-bridge/logs/install_trace.log`） |
| `.workbuddy/ld/打开实战桥_20261004.command` | 双击：先探活再 `open` |

**Python 候选顺序**（wrapper 内 `PY_CANDIDATES`）：
`~/.junqi-bridge/venv/bin/python`（首选：自持 + 有 numpy）
→ `~/.workbuddy/binaries/python/envs/default/bin/python`（有 numpy，属外部管理）
→ `/usr/bin/python3`（稳但**无 numpy ⇒ 自动降级**，界面照常）。

### B. ⚠️⚠️ `launchctl` 写操作在本执行环境**一律 EIO**（必须桌面会话）

`bootstrap gui/$U` / `bootstrap user/$U` / `load -w` / `submit` **全部** `Bootstrap failed: 5: Input/output error`。

**不是 plist 的问题** —— 三次对照坐实：
1. 最小纯 ASCII plist（放 `/tmp`）⇒ 同 EIO；
2. **把已成功加载过的 `com.junqi.weiyun-sync.plist` 复制一份、只改 Label** ⇒ 同 EIO；
3. 关沙箱重跑 ⇒ 仍 EIO。

**根因**：进程**不在 Aqua 会话**（`TERM_SESSION_ID` 为空）；且环境带强制 `http_proxy`（`curl` 见 **502**）、`sudo` = `operation not permitted`。
**旁证**：`open -a Terminal <脚本>` 返回 0，但**脚本未被执行**（trace 文件未生成）。

⇒ **加载只能由坚哥在真实终端 / 双击 `.command` 完成，且只需一次**；之后重启机器由 launchd 自动加载。

### C. Mac 侧 Python 现状（实测 2026-10-04）

| 解释器 | 版本 | numpy |
|---|---|---|
| `/usr/bin/python3` | 3.9.6 | ❌（**能跑通服务**：`http=200` / 148544 B） |
| `…/envs/default/bin/python` | 3.13.12 | ✅ 2.5.2 |
| `~/.junqi-bridge/venv/bin/python` | **3.9.6** | ✅ **1.26.4** |

⚠️ `sl_net_np_20261002.py --verify` 需要 **torch**（仅测试对照用）；**运行时** `NPNNet` 只用 numpy。

### D. 验证矩阵（Mac 侧，全绿）

| 项 | 结果 |
|---|---|
| 系统 python3.9 起服务 | ✅ `GET /`=200 / 148544 B · `/api/vs/state` 正常 |
| venv 起服务 / wrapper 日志 | ✅ `Python = ~/.junqi-bridge/venv/bin/python（numpy 有 ⇒ 网络先验可用）` |
| `human_vs_ai.py --selftest`（venv） | ✅ 全绿（含「网络先验 默认开·每步注入·显式关则零注入」） |
| `_net_prior_net()` | ✅ `NPNNet` **434064** 参数 / 26ch / 5 blocks |
| `plutil -lint` / `py_compile` / `bash -n` | ✅ 全 OK |

### E. 速查

| 碰到的事 | 查 |
|---|---|
| 8765 重启后不在了 / 连接被拒 | §28.31 A（装一次 launchd）；**先查端口有无进程，别先怀疑代码**（§⑨） |
| `launchctl bootstrap` 报 EIO | §28.31 B —— **在这个环境里是正常的**，换桌面会话 / 双击 `.command` |
| 看日志 / 状态 / 强制重启 | `tail -n 30 ~/.junqi-bridge/logs/bridge-8765.out` · `launchctl print gui/$(id -u)/com.junqi.bridge-8765` · `launchctl kickstart -k gui/$(id -u)/com.junqi.bridge-8765` |
| 卸载常驻 | `launchctl bootout gui/$(id -u)/com.junqi.bridge-8765` |
| Mac 上没有带 numpy 的 Python | §28.31 A —— wrapper 会退到 `/usr/bin/python3`，网络先验自动关，**界面照常** |
