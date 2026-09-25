---
name: electron-asar-inspect
description: 逆向排查 Electron 桌面应用（Codex/ChatGPT 桌面端、VS Code 系等）的界面行为问题——例如「语言设置成中文但界面还是英文」「某个设置项开关无效」「功能被隐藏」。通过解析 app.asar 定位实现代码与特性开关（Statsig / feature flag），配合窗口定向截图做实证验证。当任务是「Electron 应用某个 UI 行为不对/设置不生效/想知道为什么」时使用。
agent_created: true
---

# Electron 应用 asar 逆向排查

用于回答「为什么这个 Electron 应用的这个设置不生效」这类问题。核心是**别猜，去读它的代码**。

## 触发场景

- 应用内改了设置（语言、主题、开关），界面没变化
- 某功能明明有 UI 但点了没反应
- 想知道某个行为是本地逻辑还是服务端下发

## 第 0 步：先排除低级原因

按成本从低到高：

1. **应用是否真的重启过** —— macOS 上点红叉只是关窗，进程还在。`pgrep -f "App.app/Contents/MacOS/"` 确认。
   注意：即使完整重启，很多设置类问题也不是重启能解决的，别停在这一步。
2. **系统层设置** —— `defaults read -g AppleLanguages`、`defaults read <bundleid> AppleLanguages`
3. **应用自己的配置** —— 常落在 `~/.<app>/config.toml` 或 `~/Library/Application Support/<App>/` 下
4. **本地化资源是否真的存在** —— `Contents/Resources/*.lproj`（macOS 原生层，只管系统权限提示这类）、asar 内的 webview 语言包（才是 UI 文案）

## 第 1 步：解析 asar

asar 是 Electron 的归档格式，结构：

```
[0..3]   uint32 = 4
[4..7]   uint32 = headerSize（header pickle 大小）
[8..11]  uint32 = ...
[12..15] uint32 = jsonLen
[16..]   header JSON 字符串
数据区起点 = 8 + headerSize
每个文件的真实位置 = 数据区起点 + node['offset']
```

解析脚本（自校准版，最稳）：

```python
import json, struct
P = '/Applications/Xxx.app/Contents/Resources/app.asar'
f = open(P, 'rb')
v1, v2, v3, v4 = struct.unpack('<IIII', f.read(16))
DATA_START = 8 + v2                      # 关键
f.seek(16); j = json.loads(f.read(v4).decode('utf-8'))

def get(path):                            # path 如 '/webview/assets/x.js'
    node = j
    for part in path.strip('/').split('/'):
        node = node['files'][part]
    f.seek(DATA_START + int(node['offset']))
    return f.read(int(node['size']))
```

`DATA_START` 若读出来是空/乱码，用文件自校准：拿一个已知内容开头是 `{` 的文件（如 `/package.json`），试几个候选偏移，哪个解出合法内容就用哪个。

遍历所有文件路径：

```python
files = []
def walk(node, prefix=''):
    if isinstance(node, dict):
        if 'files' in node:
            for k, v in node['files'].items(): walk(v, prefix + '/' + k)
        elif 'offset' in node:
            files.append((prefix, int(node['offset']), int(node['size'])))
walk(j)
```

## 第 2 步：搜关键词并反查文件

在 asar 裸字节上搜，再用 offset 反查是哪个文件：

```python
import re
blob = open(P, 'rb').read()
def which(off):
    rel = off - DATA_START
    for p, o, s in files:
        if o <= rel < o + s: return p

for kw in [b'someFeatureFlag', b'someSettingKey']:
    for m in re.finditer(re.escape(kw), blob):
        print(which(m.start()))
```

有效关键词来源：
- 界面上的**可见文案**（`Language for the app UI`）→ 直接找到设置面板组件
- 设置项的内部键名（从组件里读出来，如 `localeOverride`）
- 推断的机制名（`featureGate`、`overrideAdapter`、`localStorage`）

**高杠杆技巧 —— 从截图上的 UI 文案反查「常量 / i18n 块」，一次挖出整块定义。**
现代 Electron 应用常把界面文案集中成一个扁平常量对象，键名带语义后缀：

```js
const constantsEn = {
  openaiCodexName: "Codex CLI",
  openaiCodexDesc: "Uses your Codex OAuth login",   // ← 描述文案常常一句话讲清机制
  localName: "Local",
  localDesc: "OpenAI-Compatible",
}
```

做法：把截图里**肉眼可见的那几个词**（卡片名、按钮名、提示语）直接丢进去搜，
命中后从 `const constantsXxx = {` 一直读到配对的 `};`，**把整块 dump 出来**。
比逐个猜关键词快得多，而且 `*Desc` / `*Hint` 这类字段经常直接说明实现方式
（例：某选项写着 "Uses your Xxx OAuth login"，立刻就能判定它需要什么账号、
以及本机能不能满足）。这一步往往能直接回答用户的"我该选哪个"。

⚠️ **判定"某功能存不存在"时，打包进 asar 的 README / 文档不算证据。**
赞助商名、未发布功能、别家版本的说明都可能只存在于 README 里 ——
必须找到**卡片 / 选项 / 分支的定义本身**（常量块或组件代码）才算数。
反例：某项目 README 反复说"选 Atlas Cloud 卡片"，但该版本的常量块里根本没有这张卡片，
出现 atlascloud 字样的全是 README 与 logo 资源文件。

拿到目标文件后提取出来精读：

```python
open('/tmp/x.js','wb').write(get('/webview/assets/xxx.js'))
```

压缩代码阅读技巧：用 Python 切片打印上下文（**不要用 `grep -oE '.{300}'`，GNU grep 的重复次数上限是 255**）：

```python
t = open('/tmp/x.js', encoding='utf-8', errors='ignore').read()
for m in re.finditer('关键词', t):
    i = m.start(); print(t[max(0,i-400): i+400])
```

## 第 2.5 步：i18n 多语言块 —— 既是噪声，也是金矿

现代 Electron 应用把界面文案集中打包成**每种语言一个常量块**：

```js
const chatEn = { setContextFolder: "Set context folder", contextFolderChip: "Choose Folder" };
const chatHe = { setContextFolder: "הגדרת תיקיית הקשר", /* ... */ };
const chatZh = { setContextFolder: "设置上下文文件夹", /* ... */ };
```

**噪声面**：直接搜一个键名（如 `contextFolder`）会命中 20+ 个语言副本，
前十几条全是翻译表，看着像"到处都引用了"，其实只有一条是实现代码。
**按 `": "` 密度过滤**（翻译表的特征就是密集的 `键": "值`）：

```python
for m in re.finditer(kw, s):
    frag = s[max(0, m.start() - 200): m.end() + 200]
    if frag.count('": "') > 4:     # 翻译行 → 跳过
        continue
    print(frag.replace(chr(10), ' '))
```

**金矿面**：中文语言块就是现成的词条表 —— 想知道某功能在界面上叫什么、
有哪些相邻选项，直接读 `const xxxZh = {...}`，比翻截图快。
英文块（`xxxEn`）更要读：**中文翻译会丢语义**，
`workspaceScratch` / `workspaceWorktree` / `*Desc` / `*Hint` 这类键
只有英文原文才讲得清它到底干什么。

## 第 2.6 步：从文案追到实现，三点定位

拿到键名后别急着下结论，追三层：

1. **谁在调用** —— 搜 `t("chat.xxxKey")` 的位置，能直接看到所在组件和回调
   （`onClick: () => setContextFolder(path)`），顺藤摸到真正的逻辑函数。
2. **数据从哪来** —— 区分两类**同名**标识，这一步最容易误判：
   | 形态 | 含义 |
   |---|---|
   | `something.list` / `something.get`（字符串方法名） | **后端 RPC**，有服务端实现 |
   | `.set(` / `.get(` / `.map(`（JS Map/数组 API） | **前端本地计算** |
   实例踩坑：界面里叫 "Projects" 的分组，一度以为读的是后端 projects 表，
   实际是前端把会话按某个字段 `groupBy` 出来的 —— 两种数据源的结论完全相反。
3. **主进程侧** —— 列全部 IPC 通道再挑：
   ```bash
   grep -o 'ipcMain\.handle("[^"]*"' out/main/index.js | sort -u
   ```
   渲染进程里 `window.xxxAPI.foo(...)` 对应主进程的 `ipcMain.handle("foo", ...)`，
   数据落到哪张表、哪个文件都在这里。
   注意：`main.js` 里 `grep` 出的 `xxx.yyy` 形态方法名，可能全是 **SQL/JS 本地操作**
   而非 IPC —— 先看有没有 `ipcMain.handle` 包裹才算数。

## 第 3 步：识别特性开关（高频根因）

Electron 应用常把未全量开放的功能放在服务端开关后面。**Statsig** 是最常见的一家：

```js
o = K_('72216192')                      // gate/experiment 的 id
s = o?.get('enable_i18n', !1)           // 默认 false
c = s
...
if (!c) { messages = undefined }        // 开关关闭 → 功能区不生效
```

判断要点：
- `?.get('xxx', !1)` 里的 `!1` 就是**默认 false**，`!0` 是 true
- gate 是**服务端下发**的，本地配置改不了
- 拉取端点常在 asar 里能找到（如 `api.oaistatsig.com`、`ab.chatgpt.com`）
- 检查状态文件（如 `statsig-state.json`）里**有没有配置缓存** —— 只有 stable-id、没有缓存，说明从来没成功拉取过配置
- 用 `re.finditer(rb'client-[A-Za-z0-9]{20,}', blob)` 能挖到 SDK key

**重要**：如果 gate 是服务端的，结论就是「本地无解」。不要为了"解决"去改 asar —— 见下面的约束。

## 第 4 步：实证验证（能做就做）

**Windows 定向截图**（比整屏截图干净，只需窗口 id）：

```swift
// /tmp/wid.swift —— 列出窗口 id/标题/尺寸
import Cocoa
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
for w in list {
    let owner = (w[kCGWindowOwnerName as String] as? String) ?? ""
    let layer = (w[kCGWindowLayer as String] as? Int) ?? -1
    let num   = (w[kCGWindowNumber as String] as? Int) ?? 0
    if owner.contains("App"), layer == 0 { print(num) }
}
```

```bash
WID=$(swift /tmp/wid.swift | head -1)
screencapture -x -o -l "$WID" /tmp/shot.png     # -l 指定窗口
```

然后用 Read 工具直接看图。**这是唯一能确认界面实际渲染结果的手段** —— 日志、配置文件、AX 树都可能骗人（Electron 的 web 内容在 AX 树里通常只暴露很浅一层）。

获取窗口标题（不需要屏幕录制权限）：

```swift
import Cocoa
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
for w in list {
    let owner = (w[kCGWindowOwnerName as String] as? String) ?? ""
    if owner.contains("App") { print(w[kCGWindowName as String] ?? "") }
}
```

**Electron 界面内容区的文案拿不到**：AX 树只到 `AXGroup`/`AXButton` 就断了（Electron 的 accessibility 默认不展开 web 内容）。别在这上面浪费时间，直接截图。

## 硬约束：不要改 asar

改 asar 会遇到两道锁：

1. **ElectronAsarIntegrity 校验**

   ```bash
   /usr/libexec/PlistBuddy -c "Print :ElectronAsarIntegrity" /Applications/X.app/Contents/Info.plist
   ```

   有 hash 就必须同步更新，否则应用启动直接崩。

2. **代码签名** —— 改完 Info.plist 签名失效，需要重签名。Electron 应用有多层 helper + entitlements（JIT 等），`--deep` 已废弃且不可靠，逐层重签很容易把应用搞坏。

再加上应用自动更新（Sparkle）会覆盖修改。**结论：除非用户明确要求并接受风险，否则不要走这条路。**

## 常见坑

| 坑 | 说明 |
|---|---|
| `grep -r` 跑在应用目录 | 会扫进 `node_modules`（几万文件），命令被 SIGTERM 杀掉（exit 137）。改用 Grep 工具、加 `--exclude-dir=node_modules`，或先把目标 bundle 提取成单文件再用 Python 搜 |
| 搜关键词只得到翻译表 | 见「第 2.5 步」——按 `": "` 密度过滤掉 i18n 行，否则会误判成"到处都引用了" |
| `grep -oE '.{300}'` | GNU grep 重复次数上限 255，改用 Python 切片 |
| `UID` 变量 | zsh 里是只读保留变量，赋值报 `bad math expression`，换个名字 |
| `ps -o command=` / `lsof` | 沙箱下输出常为空，别据此判断进程/端口不存在 |
| `trash` 退出码 | 成功移入废纸篓仍返回非零，**按「路径是否还存在」判断成败** |
| `open --args --remote-debugging-port=` | Chromium switch 常不生效；且沙箱内连不上 localhost 端口，CDP 这条路基本走不通 |
| 配置值被应用改写 | 应用启动时会用自己的内部状态重写配置文件（如 `localeOverride = "zh-CN"`），你手改的值可能被覆盖 —— 改完要复查 |
| `curl` 走沙箱代理 | 访问 localhost 或特殊端口要加 `--noproxy '*'` 并 `env -u http_proxy -u https_proxy` |

## 交付结论的写法

把「代码证据 + 本地状态 + 网络条件」三条线摆出来，明确区分：

- **已验证**（有代码片段/截图/文件内容支撑）
- **推断**（逻辑上成立但没直接观测到）
- **本地能否修复**（能 / 不能，不能就说清为什么）

不要为了让结论好看而含糊，也不要把「服务端灰度开关」包装成「配置问题」。
