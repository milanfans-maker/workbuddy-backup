---
name: qq-junqi-replay
description: 开发和迭代 QQ 四国军棋复盘分析器（单文件 HTML 工具）。This skill should be used when the task involves parsing .jgs 复盘文件（QQ四国军棋二进制复盘）、文本复盘格式（v2.0 复盘文本）、玩家颜色/方位映射、逆时针行棋序、棋子价值表、行棋得失统计、回放渲染、或对 index.html 复盘分析器做任何修改与回归验证。也覆盖**联众军棋 `.JQH.TXT` 文本复盘**（GBK 编码 / 17×17 字符栅格 / **顺时针**行棋序 / 映射A 坐标 / 非工兵触雷后地雷保留）与**「玩家表现评估」五维公式的数据校准**（v1→v3 方案、AUC 与玩家级 Spearman 验证、共线与维度退化诊断），以及用大师复盘为 AI 机器人打地基。Covers the .jgs binary format (0x20 玩家块/0x19B 指令区/0x5F 棋步), 方位双射择优 (pickOrientByScore + orientSelfCheck 行棋自洽率), 三级回归工作流 (Node 引擎测试 + jsdom 冒烟 + 真实 Chrome 截图 + 6 个真实 .jgs 回归)。
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
python3 live_bridge_server_20260925.py --selftest    # 10 项（①~⑩，含全库合法性与正负样本）
python3 build_live_ui_20260925.py --check            # 切块命中数 + check_symmetry（旋转不变性）
python3 .workbuddy/tests/check_js_blocks.py 四国军棋实战桥.html
node .workbuddy/ld/bridge_e2e_20260925.js --out <项目根>   # 61 项
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
| **⭐ 实战桥（Phase 7 续）** | 见本 skill **§19 / §20**：平台色环/相位 · 视角映射与 `check_symmetry` 前提断言 · `#cell-<vr>-<vc>` 是视角坐标 · `legal_targets_of` 唯一入口且自检须挂 `drive(legal_fn=)` · `overrides` 随新局清零 · e2e `--out` = 项目根。另：坐标跟平台、兵种简写/全名收口、走棋方自动推断、撤销重放式、几何抽取三坑 | 19/20 |
| 绝对强度锚线 | `pimc_mirror.py --anchor`：冻结 `ANCHOR_REF` / `ANCHOR_EVAL` / `ANCHOR_HIST`。⚠️ **常量不得漂移**，新基准**新增** `ANCHOR_REF2`。⚠️ 强制两边同聚合。⚠️ 单次 SE≈125~140 ⇒ **只报 Δ ± 95% CI** | 16.7 |
| **⭐ AI 强度对标人类（Phase 6）** | ⚠️⚠️ **报 AI 强度必须同时报「尺子效度」** —— 效度与 AI 位次**恰好反向**（`−0.16→P98` / `+0.25→P95` / `+0.41→P70`）⇒ **尺子越偏 AI，AI 看起来越强**。⚠️ **上帝视角尺子有同源偏置**且**分辨不出人类水平** ⇒ **不能排位次**。⚠️ **「AI 替一方 + 其余照抄棋谱」打完整局不可行**（100% 失配）。⚠️ 窗口长度扫描有**选择偏差**。⚠️ 净值必须**联盟口径**。⚠️ 必须写明 `greedy` 还是 `pimc`（同口径差 3 倍） | 17 |

---

## 参考文件

- `references/jgs-format.md`：.jgs 二进制格式完整规范、方位双射择优算法（`pickOrientByScore` + 行棋自洽率）、jgsToText 输出格式、已知坑（双偏移、纵坐标翻转、键序陷阱、GBK 编码）。
