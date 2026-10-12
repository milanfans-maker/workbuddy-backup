---
name: weiyun-cross-machine-sync
description: 用微云做跨机文件自动同步（电脑A改文件 → 自动传微云 → 其他电脑自动拉取）。当任务是「多台电脑同步文件」「改完自动上传云盘」「微云实时同步」「跨设备同步项目」「让另一台电脑自动拿到最新文件」时使用。含微云官方 MCP 直连通道（WyHeader=mcp_token，独立于 WorkBuddy 会话）、OAuth 取 token、三方比对同步算法、A/B+/C/D/F/G/H/I/J 九重修复（竞态垃圾 · 自抖 · 行尾双向污染 · 共享文件并发覆盖静默失配 · 写者锁 · 只读日志收敛 · 撞名 CAS 防静默回滚 · 只读闸门**收口**+兜底 canary）、跨机补丁对齐（原文分发 + 字节/标记/归一化哈希三重校验；落法＝回退干净态→隔离试跑对方原文→落真文件）、「跨天重放哈希必变」识别与归一化哈希（含缩进标记行修正）、**探针契约（断言行为而非数日志行数；文案变更会致假 FAIL）**、隔离重放器（HOME+USERPROFILE 双变量 + 真文件哈希断言）、切版本 SOP、「对齐判据 = 行为契约而非源码哈希」「闸门别挂分支上、要收口」两条方法论，以及微云 API 与 WorkBuddy 环境的实测坑位。
agent_created: true
version: 1.10.0
---

# 微云跨机自动同步

## 何时用

- 用户要在多台电脑间同步同一批文件，且指定用**微云**
- 需要「改完自动上传、另一台自动下载」
- 已有 `~/.junqi-sync/` 环境要维护或排查

## 先讲清楚三条硬约束（必须告知用户，别承诺「真·实时」）

1. **微云没有服务端推送**，只有 `list` / `download` / `upload` —— 纯拉取模型。
   上传端能做到近实时（本地轮询 + 防抖，实测 **4 秒**），**下载端最快也得等一个轮询周期（默认 15s）**。
2. **冲突不自动合并**：两端同时改同一文件，按 mtime 新的赢，本地留 `.conflict-*` 副本。
3. **删除不传播**（默认 `delete_policy: ignore`）。

## 通道：微云官方 MCP（**不要**用 WorkBuddy connector）

| 项 | 值 |
|---|---|
| 端点 | `https://www.weiyun.com/api/v3/mcpserver` |
| 鉴权 | `WyHeader: mcp_token=<token>`（同时兼容 `Authorization: Bearer <token>`） |
| 手动取 token | `https://www.weiyun.com/act/openclaw` |
| 国内直连 | 是，实测 238ms |

**为什么不用 connector**：connector 的 Bearer token 在 `CODEBUDDY_MCP_CONFIG` 环境变量里，是**会话级**的，
launchd 守护进程根本拿不到；connector 的真实凭证又是 `aes-256-gcm` 加密存储的
（`~/.workbuddy/connectors/<uuid>/.credentials.v3.json` + `.master.key`），不该去破解。
官方 MCP 通道拿到的 token **独立、持久**，这才是守护进程该用的。

### OAuth 取 token（自己实现，不需要 mcporter）

```bash
# 1. 生成本地 code（16 hex）
CODE=$(openssl rand -hex 8)
# 2. 让用户开这个链接扫码（QQ / 微信），授权码 5 分钟有效
echo "https://www.weiyun.com/authorize/token?code=$CODE"
# 3. 用户确认后取 token
curl -s -X POST "https://www.weiyun.com/api/v3/mcp/token/code" \
  -H "Content-Type: application/json" -d "{\"code\":\"$CODE\"}"
# 返回 {"token":"..."}
# 错误码：11510 = 未授权或已过期；117402 = token 无效
```

## ⚠️ 微云 API 实测坑（文档与实现不符）

1. **上传不覆盖同名文件** —— 会静默改名 `xxx(1).txt`。
   官方文档第 239 行写「文件已存在时执行覆盖策略」，**实测是加序号**，会直接破坏同步逻辑。
   → 上传前必须先删远端同名文件：
   ```
   weiyun.delete {"file_list":[{"file_id":"...","pdir_key":"..."}]}
   ```
2. **删目录必须带 `dir_name`** —— 文档没写，缺了报 `117404 dir_name is required`：
   ```
   weiyun.delete {"dir_list":[{"dir_key":"...","pdir_key":"...","dir_name":"..."}]}
   ```
3. **`weiyun.download` 返回 `cookie`** —— 后续下载 HTTPS 请求必须带上，否则拿不到内容。
4. `weiyun.list` 关键字段：`file_id` / `file_mtime`（**毫秒**）/ `file_size` / `pdir_key`；
   分页靠 `offset` + `finish_flag`。
5. 响应可能是 `application/json` 也可能是 SSE（`text/event-stream`），解析两种都要兼容。

## ⚠️ 跨机竞态与 `xxx(1).md` 垃圾死循环（**实战踩过，必读**）

**现象**：微云目录里冒出 `xxx(1).md` / `xxx(1).txt`，删了又回来。

**成因链**：
1. 两台机器在**同一时间窗**内都推送**同名文件**（日志类文件最容易，如 `2026-09-26.md`）
2. 微云**不覆盖同名**（见上节坑 1）⇒ 后到的被改名成 `xxx(1)`
3. 即使内容**完全相同**也会生成新条目 —— 「秒传命中」与「新条目诞生」可以同时发生

**关键认知：单端清理在算法上不可能成功。**

```
Mac 竞态上传   → 微云出现 xxx(1).md
Windows 拉取   → 它的本地也有了这份副本
Mac 单方删除   → Windows 见「本地有、远端无」⇒ 重新上传   ← 死循环
```

**判定是不是"对方重传"**：对比删除前后的 `file_id`。
删除生效则 id 必变；若新 id 与基线记录不同、且本地 `sync.log` **无**对应 `↑ 上传` 行 ⇒ 是对方推的。

### 清理顺序铁律（**顺序错了反而制造垃圾**）

| 做法 | 结果 |
|---|---|
| ❌ **先删远端** | 同步器下一轮见「本地有、远端无」⇒ **立刻重传**，白删 |
| ✅ **先立基线，再删远端** | 同步器见「远端无、本地无、基线在」⇒ pop 基线，收敛 |
| ✅ **先删本地，再删远端** | 前提是**基线记录存在**（「远端有、本地无、基线在」⇒ skip 分支） |

推荐脚本骨架（**第 ① 步是关键，别省**）：

```python
# ① 先写一条「曾同步过」的基线，避免同步器把远端文件重新下载回来
fs["<root>/<name>"] = {"l_mtime": time.time(), "l_size": it["file_size"],
                       "r_file_id": it["file_id"], "r_mtime": it["file_mtime"],
                       "r_size": it["file_size"], "synced_at": int(time.time())}
save_json(STATE_FILE, st)
# ② 再删远端
c.call("weiyun.delete", {"file_list": [{"file_id": it["file_id"], "pdir_key": D}]})
```

### 九修法（A 场景根治 · B+ 机制兜底 · C 防自抖 · D 行尾 · F 静默失配 · G 写者锁 · H 只读日志收敛 · I 撞名 CAS · J 只读**收口**）—— **实战已全部落地**

只做 A 不够。**A 只防"日志这一种场景"，任何其他同名文件照样会撞名**；B+ 才是机制层兜底。
C 是 A/B+ 都覆盖不到的独立 bug（上传后自己下载自己）。
**D / F 是「两端真并行」才会暴露的两类问题**：D 让文件字节**静默分叉**，F 让基线**静默失效** ——
两者都**没有报错、没有日志**，是最难发现的一类。

| 修法 | 位置 | 作用 |
|---|---|---|
| **A** | 写文件约定 | 各机产出的文件名**带主机名后缀**（`2026-09-26-mac.md` / `-win.md`），从源头消除撞名 |
| **B+** | `WeiyunClient.upload()` | 秒传分支撞名收尾（**漏洞本体**，见下） |
| **C** | `_do_upload()` | 基线写 `r_file_id=None`，消除"上传后自抖" |
| **D** | 全部文本 I/O | 显式 `newline`（读 `""` / 写 `"\n"`），消除跨平台行尾互转 |
| **F** | `sync_once()` 待基线化分支 | 校验远端是否仍是"自己传的那份"，堵住**静默永久失配** |

#### A：命名规约（根治）

| 类型 | 规范 |
|---|---|
| 每日工作日志 | `YYYY-MM-DD-<host>.md`（host = `mac` / `win`），**各机独立写** |
| 跨机通信文件 | `_<Host>_<主题>.md`，发起方写，对侧只读并回新文件 |
| 长期项目记忆 | `MEMORY.md` 共享（无后缀）⇒ 改前确认对方没在改，改完立即推 |

**改名迁移的顺序铁律**（改错就触发死循环）：

1. 先改**本机**文件名（旧 key 走 `lp=None/rp≠None/b≠None` ⇒ `ignore` ⇒ skip，不会被拉回）
2. **等两端本地都不再有旧名**之后，才删微云旧文件
3. ❌ 反例：一端本地还留着旧名就删云端 ⇒ 立刻被重传

#### B+：秒传分支撞名收尾（**漏洞本体**）

`_do_upload()` 本来有「先删后传」，但 `upload()` 命中 `file_exist`（秒传）时**提前 return**，
**绕过了那次删除**；而 `_check_name()` 只打告警、不补救 ⇒ `(1)` 永久留在云端。

```python
# ❌ 原状：只告警
if r.get("file_exist"):
    _check_name(r, p["filename"])
    return r.get("file_id", ""), True
# ✅ 修后：统一走收尾
if r.get("file_exist"):
    return self._finish_named(r, p["filename"], dir_key, path, max_rounds, retry, True)
```

`_finish_named(resp, expect, ...)`：比对返回的 `filename` 与期望值，**被改名则**
① 用返回的 `file_id` 回删撞名产物 ② `delete_by_name(expect, dir_key)` 清目录内同名旧版
③ 重走一次 `upload()`（此时不撞名，可正常落地）。递归深度限 1 层（`retry<1`）。
**正常分片完成分支（`upload_state==2`）也要走同一收尾。**

> ❌ **不要用"size 闸门"替代**（曾讨论过的 B 方案）：在 `l_changed and not r_changed`
> 分支加「同 size 就不传」，会在**内容变了但长度恰好相同**时**静默漏传** —— 比 `(1)` 更危险
> （`(1)` 看得见，漏传看不见）。B+ 的代价只是撞名时多一次删/传往返，且走的是罕见异常路径。

#### C：防「上传后自抖」（**独立 bug，易误判成"网络抖动"**）

**现象**：非秒传上传后，**下一轮必执行一次对同一文件的多余下载**；秒传上传则不会。
实测规律 100% 吻合：

```
22:02:20 ↑ 上传 _Mac验收回报.md (6 KB)      ← 非秒传
22:02:38 ↓ 下载 _Mac验收回报.md (6 KB)      ← 白下载
22:11:06 ↑ 上传 2026-09-26-mac.md [秒传]    ← 秒传
（无下载）✅
```

**根因**：`_do_upload()` 把 `upload()` 返回的 `file_id` 直接写进基线。但**非秒传（分片）
路径返回的 id ≠ 目录内真实 file_id** ⇒ 下一轮 `snapshot_remote` 比对时
`r_changed=True` / `l_changed=False` ⇒ 走 `not l_changed and r_changed` ⇒ 下载自己的文件。
（秒传返回的就是真实 id，故不触发。）

**修法（1 行）**：上传后基线 `r_file_id` 写 `None`（＝「本机刚传，待基线化」）。
`sync_once` **本就有该语义分支**：

```python
elif b.get("r_file_id") is None:
    r_changed = False          # 本机刚传上去的，待基线化
```

且下一轮进 `not l_changed and not r_changed` 分支调 `_refresh_baseline()` 用 list 真实值校准。

**教训**：本节开头"避免回环"那条设计**本来是这么写的，但代码写成了 `fid`** —— 文档与实现脱节
近一年无人察觉，代价是每次非秒传上传都白下载一份文件（大文件尤其肉疼）。**改完要核对代码。**

#### F：堵住「待基线化」被对端覆盖 ⇒ **静默永久失配**（C 的必要补丁）

C 修法让上传后的基线留 `r_file_id=None`，下一轮由 `_refresh_baseline()` 用 list 真实值校准。
**该逻辑默认「下一轮 list 到的远端就是我刚传的那一份」—— 两端并行时这个前提会破。**

**实测事故（文件 `MEMORY.md`，2026-09-26）**：

```
22:40:46  Mac 上传 7763 B  → 基线 l_size=7763, r_file_id=None（待基线化）
22:40:52  对端覆盖云端为 7228 B
下一轮    r_changed=False（待基线化）、l_changed=False
          → _refresh_baseline(rp) 采纳远端 7228 的 file_id
          → 基线变成 l_size=7763 / r_size=7228   ← 自相矛盾
          → 此后两侧恒判「未变」⇒ **永远 skip，永不修复**
```

**为什么最危险**：
- **全程零日志**（静默失败），也不会产生 `.conflict-*` 副本
- 表现为「文件明明两边不一样，同步器却一直是稳态」—— 极易误判成"同步器坏了"或"不报错就是对的"
- **不可自愈**：基线自洽地"错"了，只有人工介入（删远端 + 清基线 key）才能复位

**修法**：在 `_refresh_baseline()` 之前加校验 —— 「待基线化」时若
`rp["file_size"] != lstamp["size"]`，说明上传后云端已被改动 ⇒ **不再静默采纳**，
改走**冲突分支**（`conflict_copy()` 留副本 + 按 mtime 判定谁赢），让它**可见**。

```python
# ✅ 修后（F）
if need_fix and b is not None and b.get("r_file_id") is None \
        and rp is not None and lstamp is not None \
        and rp["file_size"] != lstamp["size"]:
    log("⚠ 待基线化时远端已被改动 [%s] 本地 %d / 远端 %d ⇒ 按冲突处理", "WARN")
    stats["conflict"] += 1
    conflict_copy(lp)
    ...  # 按 mtime 决定下载/上传
    continue
if need_fix:
    _refresh_baseline(files_state, sk, lp, rp)
```

**局限（要讲清楚）**：F **不能消除两端争抢本身** —— 微云没有 CAS，谁赢只能靠协议（见下节
§共享文件并发覆盖）。F 的价值是**把静默失败变成可见失败**：至少会留副本、打 WARN、计入
`冲突` 计数，而不是假装一切正常。

**手动复位法**（已陷入失配时）：
```python
c.call("weiyun.delete", {"file_list": [{"file_id": it["file_id"], "pdir_key": D}]})
st["files"].pop(sk, None)          # 清掉这个 key 的基线
js.save_json(js.STATE_FILE, st)    # 下一轮走「本地有 / 远端无 / 无基线」= 新增 ⇒ 重新上传
```
⚠️ 顺序要点：**先删远端、再清基线**。若反过来（先清基线），下一轮会先把远端文件下载回来。

### 九修法补丁链（Mac 侧实测）

```
junqi_sync.py  33428 B (原始)
            → 34924 B  patch_pidfix.py     (_pid_alive 探活)
            → 36298 B  patch_metafix.py    (B+ 秒传收尾)
            → 36592 B  patch_idfix.py      (C 防自抖)
            → 36712 B  patch_eolfix.py     (D 行尾加固：文本 I/O 显式 newline)
            → 38205 B  patch_racefix.py    (F 堵住「待基线化」被覆盖的静默失配)
            → 39173 B  patch_writerlock.py (G 共享文件「只下不上」：readonly_globs)
            → 40175 B  patch_rofix.py      (H 只读文件基线 mtime 收敛 + 日志去重)
            → 41785 B  patch_collidefix.py (I 撞名删除前 CAS，杜绝静默回滚)
            → 43496 B  patch_jfirstfix.py  (J 只读闸门**收口** + _do_upload 兜底 canary)
```

> **当前基线（**两端同源**）**：**`43496 B`**，原始 sha256 `525559793f…`、
> **归一化 sha256 `d34d24b76f55adb6143f54bd014d37f351c9b94af9eaeef4b7aba2f029e5eef9`**，
> `CRLF=0`，MARKER `EOL-HARDENED`·`RACE-HARDENED`·`WRITER-LOCK`·`RO-TIDY`·`COLLIDE-CAS` 各 ×1 · `FIRSTSYNC-GUARD` ×4。
> 历史对齐点：`38205 / d03e5c2f…`（F 期）、`39173 / 80fa9978…`（G 期）、`41785 / 60105070…`（I 期）。
> ✅ **对端落法（可复用）**：**回退干净态 → 隔离试跑对方原文 → 落真文件**（自己的独立实现会和收口块锚点打架）。

> 🎯🎯 **判据变更：跨机对齐比「行为契约」，不再比源码哈希**（2026-09-27 实战结论）
> 起因：J 一开始是两端**独立实现**（对端 42988 = 只补第三条分支；本机 43496 = **收口 + canary**）
> ⇒ 字节必然不同，**再比哈希就是在制造分叉**。
> **正确判据**：双方跑**同一份 `scripts/verify_*.py`**，得到**同一张行为表 = 对齐完成**；
> 只有「**行为表不一致**」才算真分叉。
> **源码哈希只在「双方共享同一份原文」时才有意义** —— 一旦各自实现，哈希就不再是对齐信号。
> ✅ 对端随后**直接采用本机原文** ⇒ 43496 / `d34d24b7…` 逐字节同源，两套判据同时成立。
>
> ⚠️⚠️ **延伸铁律：闸门别挂在分支上。** G 把只读闸门写成 `if l_changed and … is_readonly(…)`，
> **只改 `l_changed` 这个内存判定**；而下游 `if b is None`（首次同步）、
> `if lp is not None and rp is None`（本地有/远端无）两条分支**独立判定、与 `l_changed` 无关**
> ⇒ **绕过守卫照样上传**。同一个洞被看见三次才定位到，就因为每次只挪一格。
> **修法必须收口**：① 在**分支分发之前**统一决定去向并 `continue`；
> ② 在唯一出口（`_do_upload`）放**兜底 canary** —— 新分支会自己喊 ERROR，而不是又静默覆盖一次。

> ⚠️⚠️ **跨天重放哈希必变，不是分叉**：补丁脚本把 `%Y%m%d` 追加进标记行
> ⇒ **隔天重放，字节数相同、标记数相同，sha256 一定不同**。
> 2026-09-26→27 跨零点实测：重放件与真实件**逐行 diff 只差三行日期**，都是 41785 B。
> **⇒ 跨机/跨天判分叉一律用「归一化哈希」**：只把标记行里的 `20\d{6}` 抹成 `YYYYMMDD`
> 再算 sha256，工具 `scripts/norm_sha.py`。
> ⚠️ 两个实现**必须同一算法** —— 我首版用 `splitlines()` + `join("\n")`，
> **吃掉末尾换行** ⇒ 算出 `3ab42da0…`，与 `norm_sha.py` 的 `9094ae2c…` 不符。**先怀疑探针。**
>
> ⚠️⚠️ **第二个坑（2026-09-27 修）：标记行有两处，其中一处带缩进。**
> 补丁把标记写进 ① 文件尾追加的（**顶格**）+ ② 函数体内联的（**12 空格缩进**）。
> 原规则 `^# --- ` 只覆盖 ① ⇒ ② 里的 `%Y%m%d` **不被抹掉** ⇒
> **跨天重放时归一化哈希照样会变**，这套机制等于只对了一半（同天跑看不出来）。
> **修正：`^# --- ` → `^\s*# --- `，`norm_sha.py` 与 `replay_chain_safe.py` 的 `_norm` 两处都要改。**
> 自证：把基线那份的标记日期整体挪一天（字节数不变），归一化哈希不变 ⇒ 成立。
>
> 📌 中间曾出现 **−277 B 残差**，已彻底消解，**拆解值得记住**：
> **+16**（对端 `_pid_alive` docstring 略长）+ **(−293)**（对端 C 只改 1 行 = **+1**；
> Mac 版带 3 行中文注释 = **+294**）⇒ **算术零残差**；
> D/F 两段净增 **+120 / +1493**，两端**逐字节一致** ⇒ 确认**无第三处分叉**。
> **教训：病根不是谁的能力差，是「各写一份」—— 正确做法是发原文、别发描述。**
> 另：**定性对 ≠ 定量对** —— 当时把 Windows 上 CRLF 化后的字节估成
> 「终态 38205 + 终态行数 1018 ≈ **39223**」，实测该步是 **35880**
> （= 该步输出 34924 + 该步 `\n` 数 **956**）。**跨平台字节必须逐步算，别拿终态倒推。**

> 🎯🎯 **探针契约：断言「行为」，不要只数「日志行数」**（2026-09-27）
> 收口把只读文件在「**已有基线** + 本地变」时的行为从**只打日志**改成**跟随远端下载**；
> 而旧探针只断言日志行数 ⇒ **两种行为都只产生 1 行日志 ⇒ 根本测不出**
> （对端点名要求补这条断言）。**修法**：
> - `scripts/verify_jfirst.py` 加 **F 组**（A–E 全是「无基线」，结构上覆盖不到）——
>   直接断 `downloads == 1`；并让假客户端 `download()` **真把内容写进目标路径**
>   ⇒ 才能断「**真收敛**（本地被拉回写者版本）」，而不是「调用过 download」。
> - `scripts/verify_hi.py` 加 **H-D** —— 断分辨力：补丁前 `dl=0` / 补丁后 `dl=1`。
> ⇒ **判别力判据：补丁前必须 FAIL、补丁后 PASS。测不出变化 = 探针表达力不够，不是「没问题」。**
>
> ⚠️ **探针会因「日志文案变更」假 FAIL**（本次两端同时踩到）：
> 收口把「只读文件本地有改动」改成「只读文件 [sk] … ⇒ 不传」⇒ 旧 `H_MARK` / `MARK`
> 匹配不到 ⇒ `verify_hi.py` 的 H-B、`verify_writerlock.py` 的用例 A **双双假 FAIL**
> （看似行为回归，实为文案变）。修法：`mark_count()` 支持**多串元组**、
> `MARK` 取**公共前缀**（`只读文件`）。
> **期望过期时改测试更正常 —— 但先跑一遍确认是「文案变」还是「行为回归」。**
>
> ℹ️ **已知限制（记录，不修）**：只读 + 有基线 + 远端 **同 size 改内容**
> ⇒ 收口判为「一致」**不下载** ⇒ 非写者**静默 stale**。
> 根因：收口第二判据是 `本地 size != 远端 size` —— **正是「B size 闸门永不做」那个洞**，
> 只是落在只读路径上（写者机不配 `readonly_globs` ⇒ 不受影响）。
> 危害**低且自愈**（写者下次**长度变化**的编辑就把非写者拉到最新）；一行可修
> （判据换成「远端 vs 基线」的 `r_file_id` / `r_size`）**但需双端重新对齐** ⇒ **不为自愈的低危项再起一轮**。

补丁脚本模板：**幂等**（含 MARKER 则跳过）、**自动备份** `*.bak_pre_<topic>_<date>`、
**锚点预检**（`count != 1` 即报错退出，不硬改）、**语法校验**（`ast.parse`，失败不落盘）、
**原子写入**（临时文件 + `replace`）。
⚠️ `junqi_sync.py` **不随同步分发**（`.py` 不在 globs 内）⇒ 任何补丁都必须**人工双端部署**，
且两端要用**同一份**补丁脚本，避免字节级分叉。
⚠️ **补丁脚本自身也要守行尾铁律**：读写源码一律 `newline=""` / `newline="\n"`，
否则在 Windows 上打一次补丁整份 `.py` 变 CRLF（见下节 §行尾）。

⚠️ **怎么把「同一份补丁」送到对端**（2026-09-26 实战）：`.py` **不随同步分发**
（不在 globs 内）⇒ 唯一通道是**把全文贴进一个 `.md`**，走 `_<Host>_<主题>.md`
单向回报文件（`.md` 在 globs 内，会被同步）。回报里必须同时给出**三重对齐校验**，
让对端能证明「逐字符一致」而不只是「语义一致」：

1. **字节数** —— 打完补丁后的目标大小（如 `43496 B`）
2. **标记计数** —— 每个补丁 MARKER 各 1 次（`grep -c "RACE-HARDENED"`、`EOL-HARDENED` …）
3. **全量 SHA256** —— `shasum -a 256 junqi_sync.py`（**给 64 hex，16 位前缀不够**）
   —— ⚠️ **跨天务必用归一化哈希**（见上节「跨天重放哈希必变」），否则必然误判成「还有分叉」。

⚠️ **别用「字节数相等」单独判分叉**：两端写法不同（docstring 长度、pid 读写拆几项）
会产生**恒定偏移**（本次 Windows 侧每步 +16 B）⇒ 看着像分叉，其实是等价。
顺序是：**先对齐到同一份原文 → 再比哈希**；若原文重放后哈希仍不同 ⇒ 还有第三处
写法分叉，**立即回报，别自行消化**。

⚠️ **全文要「程序化内嵌」，别手抄**（2026-09-26 实战）。回报里贴多份 `.py` 时：

```python
# ✅ 读文件 + 记号替换
report = TEMPLATE.replace("@@PATCH1@@", body("patch_rofix.py"))
# ❌ 别用 report = TEMPLATE % (...)：正文里满是 `%.0f` / `%s` / `%Y%m%d`
#    （日志格式与代码片段）⇒ 会被外层格式化吃掉，报
#    "TypeError: must be real number, not str"
```

手抄必截断，`%` 格式化必炸 —— **两条都踩过**。另：生成后**自检关键锚点**
（`grep -c` 几个字串：目标字节、标记名、`def main` 个数）再上传。

⚠️ **把「原文」发出去之前，先做两件自检**（2026-09-26 实战，踩过才写的）：

1. **自检补丁脚本自身的行尾** —— 一次性修补脚本最容易漏 `newline`。
   本机 `patch_pidfix.py` / `patch_metafix.py` / `patch_idfix.py` 三份老补丁
   就在 `write_text` 上漏了 ⇒ 在 Windows 上重放，**该步输出会被整体 CRLF 化**
   （`该步字节 + 该步 "\n" 数`：如 pidfix → 34924 + 956 = **35880**，对端实测吻合）
   ⇒ **中间步骤字节全错、哈希对不上**（幸而 `eolfix`/`racefix` 写出端强制 LF，终态会自愈回 38205）。
   修法见 `scripts/fix_patch_scripts_eol.py`（就地给读/写补上 `newline`）。
2. **隔离全链重放自证落点 —— ⚠️ `HOME` 在 Windows 上无效！**
   补丁里 `TARGET` 用 `Path.home()`（= `os.path.expanduser("~")`），**有平台差异**：
   **macOS/Linux 认 `HOME`；Windows 认 `USERPROFILE`（完全不认 `HOME`）**。
   只设 `HOME` 在 Windows 上 ⇒ **补丁径直去改真文件**
   （对端实测踩过：幸而真文件已含 `_pid_alive`、幂等跳过，属**运气不是设计**）。
   **正解：`HOME` 与 `USERPROFILE` 都设 + 跑后断言真文件 sha256 未变。**
   直接用 `scripts/replay_chain_safe.py` 一键做完（建隔离目录 → 双变量 → 逐步核字节 →
   终态核哈希 → **断言真文件未变**）：
       python3 ~/.junqi-sync/replay_chain_safe.py
   **先自证，再用「权威原文」的口吻发出去** —— 否则对端重放失败时，你分不清是「他弄错了」还是「你发错了」。
3. **切版本先证「旧进程真死」** —— Windows 上 `OpenProcess(0x1000)`
   （`PROCESS_QUERY_LIMITED_INFORMATION`）**不含 `PROCESS_TERMINATE`** ⇒
   `TerminateProcess` **返回 1 但进程照跑** ⇒ 新守护被 pid 检查挡下 ⇒
   **「磁盘是新版、内存跑旧版」**。正解用 `OpenProcess(0x0001)`，且**以 `tasklist` 查不到 pid 为准**
   （**别信 API 返回值**）。Mac 无此坑，但**「切完核磁盘字节 + 内存版本 + pid 三者一致」两端通用**。

## ⚠️ 共享文件并发覆盖 —— 微云**没有 CAS**（实战事故，必读）

**A 命名规约护不住所有文件。** 它只保证「各机自己的产出」名字不相交；
但**共享文件**（`MEMORY.md`、项目对照表这类两端都要写的）**必然同名**，
两端同时改时**没有任何机制能判定谁该赢**。

### 实测事故（2026-09-26，双文件同时被覆盖）

| 文件 | 云端最终 | Mac 的修改 |
|---|---|---|
| `MEMORY.md` | 7228 B（对端版，仍写错误表述） | 7763 B —— **被覆盖** |
| 项目对照表 | 10642 B（对端版） | 9855 B —— **被覆盖** |

证据链（用 `file_id` + mtime 定位，**不要靠推测**）：

```
22:40:46  Mac 日志 ↑ 上传 MEMORY.md (8 KB)      ← 我传的是 7763 B
22:40:52  云端 MEMORY.md mtime                  ← 对端 7228 B 落地
```

**机制**：我传 8 KB → 对端的 B+ 补丁（先删后传）**删掉我的、写入它的** ⇒ 云端只剩它的。
**B+ 解决的是 `(1)` 撞名，不是"谁赢"—— 这是两件不同的事。**

### ⚠️ 检测手法：别信"两边看起来一样"

```python
# 逐字节比对本地 vs 云端（二进制，别用文本模式）
c.download(it["file_id"], D, str(tmp))
same = tmp.read_bytes() == local.read_bytes()
# 再看基线的自洽性
print(b["l_size"], b["r_size"])   # l≠r 且无冲突记录 ⇒ 已被覆盖
```

### 合并流程（**不要用某一端覆盖另一端**）

1. 下载「云端版」到临时目录，本地版原地不动
2. **逐行 diff**（`difflib.unified_diff`），找共同前缀
3. 共同前缀原样保留；两端独有章节**各自完整保留**
4. **冲突的表述**（如本例的"macOS 是否复现行尾问题"）→ 以**有实测数据的一方**为准，
   但要在文中**显式标注原标题作废**（不要悄悄删掉，否则对端会以为被无视）
5. 拼接后用 `newline="\n"` 写回，再核对关键字与行尾
6. 上传 + **发通知文件**要求对端「先下载对齐，别急着上传」

### 根治规约 ①：共享文件改「单一写者 + 建议文件」（**约定**）

| 类型 | 原规约 | 新规约 |
|---|---|---|
| 各机产出（日志 / 回报） | 各机独立写 | 不变（名字不相交，本就不冲突） |
| **共享文件**（`MEMORY.md` 等） | 两端都可写 | **单一写者**；另一端的改动写成 `_<Host>改动建议_<主题>.md`，由写者合并 |

**理由**：微云无 CAS ⇒ 只能靠协议避免。共享文件往往正是**改得最勤**的，
"撞了人工合并"每次都要介入；定成单一写者成本最低。

> 补充：覆盖发生时，**被覆盖端的修改不会丢失在本地**（本地文件还是自己的版本），
> 丢掉的是"已上传"这件事。所以恢复只需：重新上传 / 合并后上传，**不必找回**。

### 根治规约 ②：G 补丁 —— 把「单一写者」从**约定**变成**机制**（**必做**）

⚠️ **实测两次（2026-09-26 22:40 / 23:33）**：**「单一写者」只是文档约定，同步器不认**。
非写者机只要认为「本地变了」（**状态失配、切版本、清基线，甚至只是下载后 mtime 变化**），
就会上传并覆盖写者。

**G 补丁**：非写者机 config 配

    "readonly_globs": ["MEMORY.md", "三任务-文件对照表.md"]

命中文件 ⇒ **参与比对与下载，但本地改了永不上传** ⇒ 无论怎么重传都**不可能**覆盖。
（写者机**不配**，行为零变化。）配置片段 + 补丁见 `scripts/patch_writerlock.py`。

**零代码应急**（G 落地之前先用，立即可做）：非写者机把共享文件名塞进 `exclude`

    "exclude": [..., "MEMORY.md", "三任务-文件对照表.md"]

⇒ 完全**不碰**这两个文件（代价：暂时看不到共享文件更新）。
等 G 配好后再从 `exclude` 里删掉。

### ⚠️ 写者侧的纪律：**改共享文件不要分多阶段编辑**

实测踩过（23:41）：在**同一份共享文件**上连着做多次 `Edit`，同步器会
**在两次编辑之间**把中间态传上云端；下一轮「本地（新）≠ 云端（中间态）」
⇒ **F 补丁按设计判冲突** ⇒ 把**中间态下载回来覆盖本地**。

⇒ **改共享文件的两种正确姿势（二选一）**：

1. **一次性写完整内容**（先定稿，再 `Write` 一次）—— 推荐
2. **改之前先停守护**，改完再启动

> 这不是 F 的 bug：云端确实 ≠ 本地，判定正确。**是写者的操作制造了这个场景。**
> 同理，任何**长文件的多步改写**都该先停守护。

### 根治规约 ③：H 补丁 —— G 的**副作用**（只读文件日志刷屏，**必打**）

**G 拦下上传后没有刷新基线**：

```python
if l_changed and lp is not None and is_readonly(key, cfg):
    log("只读文件本地有改动，按规约不上传 [%s]" % sk, "INFO")
    l_changed = False          # ← 只改内存判定，不动 files_state
```

⇒ `b["l_mtime"]` 永远停在旧值，而 `l_changed = (mtime != b.l_mtime)`
⇒ **内容一字未变也会每轮刷一行 INFO**。对端曾被逼到用 `os.utime` 手动把 mtime
恢复基线才止住 —— **那是掩盖症状，不是修好**。

**H 修法两条（两种思路都做）**：

1. **内容未变**（`lstamp.size == b.l_size`，只有 mtime 被 touch）⇒ 把 mtime**刷进基线**，静默收敛；
2. **内容真变了**（size ≠ 基线）⇒ 仍不上传（规约），但日志**只在状态变化时打一次**
   （`ro_stamp` 记 `size|mtime` 去重），且**不**刷 `l_mtime`/`l_size`
   —— 否则等于**静默吞掉**「本地与远端不一致」。

**验证（端到端 A/B，同一场景分别喂补丁前/后）**：

| 场景 | 补丁前(G) | 补丁后(H) |
|---|---|---|
| 内容没变、只有 mtime 落后 → 轮 1 / 轮 2 | **1 / 1** 行（刷屏） | **0 / 0** ✅ |
| 内容真变了 | 1 行 | **1 行**（不吞掉分歧）✅ |
| 再跑一轮（无变化） | **1 行**（还在刷） | **0 行** ✅ |
| 只读文件上传次数 | — | **0** ✅ |

脚本 `scripts/patch_rofix.py`，验证器 `scripts/verify_hi.py`。

> 🧪 **A/B 对照的选版本陷阱**：备份命名是「打该补丁**之前**的快照」⇒
> 「对端当前版本」是 `bak_pre_<下一个补丁>_*`，不是 `bak_pre_<它自己>_*`。
> 本次首轮拿 `bak_pre_writerlock_*`（38205，**根本没有只读守卫**）当对照，
> 得出「补丁前也不刷屏」的**假 FAIL**。**取错对照 = 测不出分辨力。**

### 根治规约 ④：I 补丁 —— 撞名删除前必须 **CAS**（**必打**）

**B+ 的「先删后传」在并发写下是破坏性的**（2026-09-26 23:33 事故真机理）：

```
23:33:04  Mac  上传 9811               云端 = 9811（真上传，非秒传）
23:33:05  Win  上传 → 返回 MEMORY(1).md  ⇒ 撞名（它那一刻列表里没这个条目）
23:33:06  Win  B+「先删后传」           ⇒ **删掉了 Mac 的 9811**
23:33:08  Win  重传自己的 9038 [秒传]    ⇒ **秒传从对象池把 9038 复活**
23:33:21  Mac  list 到 9038 ⇒ F 判冲突 ✅（判定正确，9811 副本保住）
```

⇒ **B+ 把「可见的 `(1)` 垃圾」升级成「静默回滚」**：内容被换掉、名字却干净。
**秒传是帮凶，不是伪证** —— 它按内容哈希从对象池复活旧内容。

**I 修法**：删之前做 **compare-and-swap** —— 只有远端该名字下**仍是本轮列表看到的
同一个 `file_id`** 才允许删：

```python
cur = list_dir()[expect]["file_id"]
if cur != expected_id:            # expected_id = 本轮列表里的 file_id（可能为 None）
    raise WeiyunError("撞名冲突(并发写) ...")   # 不删、让位
```

- `expected_id is None`（本轮列表里**本来没这个名字**）+ 现在有 ⇒ 判并发写 ⇒ 让位（23:33 就是这个形状）；
- `expected_id == cur` ⇒ 还是我本来要替换的那份旧版 ⇒ 照旧先删后传（行为不变）。

让位后：抛错 ⇒ 不写基线 ⇒ 下一轮 `l_changed and r_changed` ⇒ **走冲突分支**
（存本地副本 + 按 mtime 定赢家）⇒ 与 F 同一套「可见 + 有副本」语义。

**负样本验证（三条，实跑）**：A 并发写 ⇒ 抛「撞名冲突(并发写)」且**不调 `delete_by_name`** ✅；
B 自己旧版 ⇒ 允许先删后传并拿到新 id ✅；C 不撞名 ⇒ 直接返回、**零删除** ✅。
脚本 `scripts/patch_collidefix.py`。

> 🔎 **归因纪律：别让「元数据残留」这类解释蒙混过关。**
> 对端曾把 9038 归因为「秒传返回目录项元数据、内容其实还是 9811」。**判据在日志里**：
> `↑ 上传` 那行的 size 来自**本地** `lp.stat().st_size`（`%.0f /1024`）
> ⇒ 9811 打 `10 KB`、9038 打 `9 KB`（换 `/1000.0` 同样分得开）；
> 而 `↓ 下载` 走 `expect_size` **硬校验**且成功落盘 ⇒ 云端**内容**确实是 9038。
> ⇒ 若「元数据残留」成立，下载会返回 9811、校验失败、文件根本不会被替换。**它没有。**
> ⚠️ 还要防**时间方向错误**：用事后（23:37 恢复之后）的磁盘/基线状态去否证事前（23:33）的事件。

## ⚠️ 行尾（EOL）双向污染 —— **两端方向相反**（实测，别只说"Windows 的坑"）

**通用断言**：Python 文本模式默认 `newline=None` ⇒ **读**时把 `\r\n`/`\r` 统一成 `\n`，
**写**时把 `\n` 按 `os.linesep` 转换。**两个平台都会转换，只是方向相反。**

| 平台 | `os.linesep` | 效果 |
|---|---|---|
| Windows | `"\r\n"` | **LF → CRLF**（曾 34940→37303 B，差 988 = 行数） |
| macOS / Linux | `"\n"` | **CRLF → LF** |

**⇒ 没有哪一侧是安全的。** macOS 这侧更隐蔽：它**静默把对端传来的文件改掉再传回去**，
对端会收到一份"看起来没变、字节全变"的文件。

### 三种写法实测对照（macOS，样本 = 纯 CRLF 的 `.md`，CRLF=4 / 裸LF=0）

| 写法 | 读+写往返后 | 判定 |
|---|---|---|
| `read_text()/write_text()` 默认 | CRLF 4 → **0**，裸 LF 0 → **4** | ⚠️ **CRLF 被吃成 LF** |
| `read_text(newline="")` + `write_text(newline="")` | CRLF 4 → **4**，裸 LF 0 → **0** | ✅ 逐字节相同 |
| `open("rb")` / `open("wb")` | 逐字节相同 | ✅ 保真 |

**铁律**：
1. 凡改写同步范围内文本文件 → **`newline=""`（读+写都加）** 或全程二进制。
   ⚠️ **只加写不加读没用** —— 读的那一步已经把 CRLF 统一掉了。
2. **同步器本体不在风险面内**：上传读 `open(path,"rb")`、下载写 `open(tmp,"wb")`，
   全程二进制 ⇒ **搬运过程零行尾风险**。风险只在「有人编辑文件」这一步。
3. **别用「字节数相等」跨机校验同一性** —— 一方被文本模式改写过就永久失配。
   改用**内容哈希**（`sha1`）或**行尾归一化后比对**。
4. **诊断命令**（一条看清全目录行尾分布）：
   ```python
   for p in sorted(dir.glob("*.md")):
       b = p.read_bytes(); c = b.count(b"\r\n")
       print(p.name, len(b), "CRLF", c, "裸LF", b.count(b"\n")-c)
   ```
   **零混合行尾**的纯 CRLF 文件 ⇒ 自生成后**未被任何一方编辑过**（可作"未被篡改"的证据）。

### 风险入口要分开评估（**编辑工具 ≠ Python 脚本**）

- **编辑工具实测字节级保真**：对 CRLF 文件改一处 → `CRLF=4 → 4`、零裸 LF。
  ⇒ 风险入口**只有 Python 脚本**的 `read_text/write_text`，**不含日常编辑**。
- 对端（Windows）同理但要分开看两个入口：`Path.read_text/write_text` 与
  PowerShell `Set-Content` / `Out-File`（后者默认也按平台行尾转换）。

### 加固补丁（D）覆盖范围

`log()` 追加写（`newline="\n"`）、`load_json()`（`newline=""`）、`save_json()`（`newline="\n"`）、
授权码读/写、pid 写。**对纯 LF 文件完全等价（零行为变化）**，纯属消除隐患。

### 相关事实（别误判成 bug）

- `round(st_mtime, 3)` 是**正确设计**：跨文件系统（APFS 纳秒 / NTFS 100ns）对齐到毫秒，
  且**存与比走同一个函数**，不引入偏差。想自查基线是否匹配，**必须调 `local_stamp()`**；
  直接用裸 `os.stat().st_mtime` 比会被 `round` 的差异骗到（本人踩过，白查一轮）。
- 微云 `list` **不返回内容哈希**，只有 `file_id` / `file_mtime` / `file_size`
  ⇒ 无法做内容级去重，只能靠 `size` 粗判。

## `_pid_alive` 探活补丁（跨平台必打）

`_check_pid()` 若用 `os.kill(pid, 0)` 探活，在 **Windows 上对活着的进程会抛
`OSError [WinError 87] 参数错误`** ⇒ 落进 `except` ⇒ 误判已死 ⇒ **删掉 `.sync.pid`**
⇒ 下次启动不再拦重复 ⇒ **起出第二个守护进程**（重复上传 / 竞争写）。

修法：
- Windows → `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess() == 259`（STILL_ACTIVE）
- POSIX（含 macOS）→ `os.kill(pid, 0)`；**`PermissionError` 视为存活**
- `_check_pid()`：**仅「内容非法」或「确认已死」才删 pid 文件**；读文件 `OSError` 时**不动文件**

自查一行：
```bash
python3 -c "import sys,os;sys.path.insert(0,os.path.expanduser('~/.junqi-sync'));import junqi_sync as js;print('有修复:',hasattr(js,'_pid_alive'))"
```

## ⚠️ WorkBuddy 环境坑

### 1. LaunchAgent 是**可行**的 —— 但只能在 WorkBuddy 之外加载（**重要修正**）

**❌ 在 WorkBuddy 内加载全部失败**（实测穷尽）：

| 尝试 | 结果 |
|---|---|
| `launchctl bootstrap gui/$(id -u) <plist>` | ❌ `Bootstrap failed: 5: Input/output error` |
| `launchctl bootstrap user/$(id -u) <plist>` | ❌ 同上 |
| `launchctl load -w` / `launchctl submit` | ❌ 同上 |
| 提权（`dangerouslyDisableSandbox`）+ **最小 plist** 二分 | ❌ 同上 —— **排除了沙箱与配置问题** |

⇒ 这是 WorkBuddy 进程的 launchd 命名空间受限，**别在这里死磕**。

> ⚠️⚠️ **配套警告：不要在这里 `launchctl bootout`**（2026-09-27 实测教训）
> `bootout` **会成功**卸载 —— 但卸载后本进程就**再也 bootstrap 不回来**（同样 EIO），
> 守护就此挂掉，只能等用户在自己终端重跑。**代价远大于收益。**
> 要「改共享文件前先停守护」时：**用 `kill <守护 pid>`**（或干脆接受一次冲突副本），
> **别用 bootout**。
>
> ⚠️⚠️ **`nohup` / `subprocess.Popen(start_new_session=True)` 也救不了**
> —— WorkBuddy **在本次工具调用结束时会回收其进程组**：实测 3 次，秒起秒死
> （能活到该次调用最后一次输出，之后立刻消失；`disown`、`setsid`、独立会话都无效）。
> ⇒ **agent 上下文根本起不了常驻进程，不要再试第四种姿势。**
> 另：这样起来的实例**还带沙箱** ⇒ 会打 `Brokered host rename overwrite refused`（见坑 2）。
>
> ℹ️ `bootout` **只影响当前登录会话** —— plist 仍在 `~/Library/LaunchAgents/`，
> 所以**重新登录 / 重启**后系统会自动加载回来（`RunAtLoad=true`）。

**✅ 但一旦由用户加载（在自己的终端跑一次，或登录时系统自动加载 `~/Library/LaunchAgents/`），
它工作得完全正常**，而且是**最佳常驻方案**：

- `KeepAlive=true` ⇒ 崩溃自动重启；`RunAtLoad=true` ⇒ 开机自启
- **launchd 实例不受 WorkBuddy 的文件 broker 限制**（见下条坑 2），文件覆盖操作完全正常
- 实测：launchd 实例从 21:52 到 22:12 持续正常工作，上传/下载/覆盖 state.json 全绿

**两个排查陷阱**：

- ⚠️ **`launchctl list | grep <label>` 看不到 ≠ 没加载**。当实例因单例检查退出后
  `active count = 0`，list 就不显示它了。**要用 `launchctl print gui/$(id -u)/<label>`**
  看 `state`（`spawn scheduled` ＝ 已注册）、`runs`（启动次数）、`last exit code`。
- ⚠️ **别把手动实例和 launchd 实例混在一起**：手动实例（单例检查里的 pid 文件）会**挡住**
  launchd 实例，导致 `last exit code = 1` + 每 60s 一次的
  `已有同步进程在跑 (pid=...)，退出` 噪音循环。**正确做法：kill 掉手动实例，让 launchd 接管**，
  必要时 `launchctl kickstart gui/$(id -u)/<label>` 立即拉起。

### 2. 沙箱未真正绕过时，子进程的 `os.replace` 会被拦（**隐蔽陷阱**）

```
[ERROR] 本轮异常: Brokered host rename overwrite refused by file policy: prompt
```

**成因**：WorkBuddy 的 Bash 在**未真正 bypass 沙箱**时启动的子进程，会继承它的文件 broker；
`os.replace(tmp, dst)` 这类**覆盖式 rename** 被策略拒绝（策略是 `prompt`，非交互下等于拒）。
命中的是 `save_json()`（原子写 state.json）和 `download()`（落盘覆盖）。

**判据**：同一条命令，**沙箱 bypassed 会打印 `⚠️ Sandbox bypassed` 提示**。
有提示 ⇒ 子进程正常；无提示 ⇒ 子进程的文件覆盖会被拦。
（`dangerouslyDisableSandbox: true` 也只是**请求**提权，用户拒绝时不生效。）

**回避**：常驻一律走 **launchd**（不在 WorkBuddy 进程树内，根本不吃这个限制）。
手动调试时如必须 `nohup`，确保那条命令确实 bypass 了沙箱。

### 3. Bash 工具调用结束会清理进程树

`nohup ... &` / `disown` 起的进程默认活不过下一次工具调用。
**但实测：真正 bypass 沙箱启动的实例可以跨调用存活**（16047 / 16178 均存活多轮）。
→ 无论如何，**常驻请用 launchd**，别依赖 nohup。

### 4. 其他

- `python -m py_compile` 会因写 `__pycache__` 被安全中心拦
  → 改用 `python -c "import ast; ast.parse(open(f).read())"`，并设 `PYTHONDONTWRITEBYTECODE=1`。
- 诊断进程时用 **`pgrep -f "[j]unqi_sync.py"`**（方括号技巧）—— 否则脚本里的字面字符串
  会让 `pgrep` 匹配到**执行该命令的 bash 自身**，得出错误结论。
- `ps -p <pid>` / `ps aux` 在沙箱内常被拒（`operation not permitted`），提权才可用。
- `timeout` 命令 macOS 不自带（属 GNU coreutils）。

## 同步算法：三方比对

必须持久化**上次同步基线**（同时记本地侧与远端侧状态），否则无法区分「新增」和「删除」：

| 本地 vs 基线 | 远端 vs 基线 | 动作 |
|---|---|---|
| 变了 | 没变 | 上传 |
| 没变 | 变了 | 下载 |
| 都没变 | 都没变 | 跳过 |
| 变了 | 变了 | 冲突（mtime 裁决 + 留副本） |

- **避免回环**：上传成功后把基线里 `r_file_id` **置 `None`**（标记「待基线化」），
  下一轮 list 到该文件时直接采纳为基线、**不触发下载**。否则自己传上去的会被自己拉回来。
  ⚠️ **务必核对代码**：本设计早已写进文档，但实现里误写成 `"r_file_id": fid`（用了上传返回值），
  导致"自抖"bug 潜伏至今（详见上文 C 修法）。**文档与实现脱节是常态，改完要跑起来看日志验证。**
  ⚠️⚠️ **该机制有隐含前提**：默认"下一轮 list 到的远端就是我刚传的那份"。
  **两端并行时前提会破** ⇒ 会把对端的版本当自己的采纳 ⇒ 静默永久失配（详见上文 F 修法）。
  **C 与 F 必须同时上，缺 F 的 C 比不加还危险**（自抖看得见，失配看不见）。
- **首轮特判**：基线为空时，若本地与远端**大小一致**则视为已同步（只补基线，不动文件）；
  不一致则以本地为准上传。不特判的话首轮会把全部文件误判成冲突。
- **远端也要过 glob 筛子**：只处理落在产物清单里的文件名，否则远端目录里别的文件会被误下载。
- 本地变更检测用 `(mtime, size)` 快速判断即可；加 **debounce**（文件写入未完成时跳过）。

## 部署结构

```
~/.junqi-sync/
├── junqi_sync.py     主程序（单文件 Python，跨平台）
├── config.json       token + 目录映射（local_base 每台机器不同）
├── state.json        同步基线（删掉会触发重新基线化）
└── logs/sync.log     自动轮转，上限 2MB
```

命令：`junqi-sync auth | fetch | set-token | status | dry | once | sync`

启动常驻（**在你自己的终端**执行 —— WorkBuddy 内做不到，见环境坑 1）：
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.junqi.weiyun-sync.plist
# 或：直接重启 Mac / 重新登录 —— 系统会自动加载 ~/Library/LaunchAgents/ 下的 plist
# 核对（list 看不到时用 print）
launchctl print gui/$(id -u)/com.junqi.weiyun-sync | grep -E "state|runs|last exit"
```
⚠️ **不要再补一条 `nohup` 兜底** —— 手动实例会挡住 launchd 实例，制造每 60s 一次的
`已有同步进程在跑，退出` 噪音（`last exit code = 1`）。**只留 launchd 一个。**

跨平台：Windows 用 `start-windows.bat` + 任务计划程序（触发器「登录时」）；
macOS/Linux 用 LaunchAgent / systemd user unit。

## 验证清单（改完代码必跑）

1. `junqi-sync dry` —— 预演，基线已建立时应 0 上传 0 下载
2. 逐文件比对本地 vs 远端大小
3. 端到端：A 建文件 → A 同步 → B 同步（内容应一致）→ B 改 → B 同步 → A 同步（内容应更新）
4. 冲突：两边同时改 → 应出现 `.conflict-主机名-时间戳` 副本
5. `touch` 一个产物文件，等 ≤20s，看日志是否自动上传

**打过补丁 / 改过 `junqi_sync.py` 之后，另跑三条**（都是隔离 + 自断言，不碰真文件）：

```bash
python3 ~/.junqi-sync/verify_hi.py            # H/I 负样本（A/B 分辨力 + CAS 三用例）
python3 ~/.junqi-sync/replay_chain_safe.py    # 八步全链重放 + 真文件未变断言
python3 ~/.junqi-sync/norm_sha.py             # 归一化哈希（跨机/跨天比对这个）
```

⚠️ 自检三个「探针陷阱」（本轮全踩过，**先怀疑探针**）：
① **日志路径**要读模块自己的 `LOG_FILE`（在 `JUNQI_SYNC_HOME` 下），另建目录读恒为 0 行 ⇒ **假 PASS**；
② **假客户端的远端条目要固定**，跟着本地变会把 `r_changed` 搅成 True、把场景带进冲突分支；
③ **A/B 对照版本别取错**（`bak_pre_<自己>` 是**打它之前**的快照）。

## 打包 zip 的坑

中文条目名在 zip 里会乱码（Windows 解压更明显，实测显示成 `跨�?��??`）。
→ **zip 内条目名一律用纯 ASCII**（目录 `junqi-sync/`、文件 `README.md`）；
文件**内容**用中文没问题。
