---
name: install-macos-dmg-app
description: 在 macOS 上从 DMG / 官方 CDN 正确安装 .app 到 /Applications，并校验代码签名与 Gatekeeper 公证。This skill should be used when the task is to install a macOS application (desktop app / GUI app) on this machine, especially when the download comes from an official CDN, a DMG, or a side-by-side drag install, and when signature/Gatekeeper ("无法验证开发者"、"a sealed resource is missing or invalid"、quarantine) issues are involved. 含 Homebrew cask 不可用时的绕行方案。
agent_created: true
---

# macOS 从 DMG 安装 .app（含签名校验）

在本机（Mac mini M4 / Apple Silicon / 用户 wangjian）安装 macOS 桌面应用的可靠流程。

## 前置判断

1. **别默认走 Homebrew** —— 本机 brew 仓库陈旧（`brew info/search` 报 cask 定义错误），能拿到官方下载地址就直连。
   - 想查官方地址/校验值但 brew 坏了：直接读 API，不依赖本地仓库
     ```zsh
     curl -s https://formulae.brew.sh/api/cask/<name>.json
     ```
     （注意：cask 里的 `codex` 是 CLI 二进制包，不是桌面应用 —— **cask 名不等于你要的 App**，先看清 `name`/`desc`/`artifacts`。）
2. **优先官方 CDN 直链**，例如 OpenAI 的 `https://persistent.oaistatic.com/codex-app-prod/Codex.dmg`。
   先探活再下载：
   ```zsh
   curl -sIL --max-time 30 "<url>" | grep -iE "^(HTTP/|content-length|content-type|last-modified)"
   ```
2b. **官方只发官网、GitHub Release 里没有任何资产时**（如 Hermes Agent：Release 全是 changelog，`assets count: 0`）：
   别转头去下第三方镜站 / SEO 站点的包，直接从官方落地页 HTML 里抠出 CDN 直链：
   ```zsh
   curl -sL --max-time 30 "<官网下载页>" | python3 -c "
   import sys,re
   h=sys.stdin.read()
   for u in sorted(set(re.findall(r'https?://[^\"\\'<> )]+', h))):
       if any(k in u.lower() for k in ['dmg','download','release','assets','cdn','zip']):
           print(u)
   "
   ```
   典型产物形如 `https://<brand>-assets.<vendor>.com/X-Setup.dmg?build=<hash>`。
   **GitHub 仓库只留 changelog ≠ 项目没发布**，先抓落地页再下结论。
3. **确认权限**：`ls -ld /Applications` 若是 `root admin` 且当前用户在 admin 组，则免 sudo 可写。
   不要用 `sudo`，也不要把应用装进 `~/.local`（那是 CLI 的位置）。

## 安装流程

```zsh
mkdir -p ~/Downloads
curl -L --fail --retry 3 -o ~/Downloads/App.dmg "<直链>"

# 挂载（卷名往往不等于 dmg 名，用输出里的挂载点）
hdiutil attach -nobrowse -readonly ~/Downloads/App.dmg

# 拷贝：优先 rsync -a，绝不要用 ditto（见下方坑）
rsync -a --delete "/Volumes/<卷名>/X.app/" "/Applications/X.app/"
# 或：cp -R "/Volumes/<卷名>/X.app" /Applications/

hdiutil detach "/Volumes/<卷名>"
```

## 必做校验

```zsh
codesign --verify --verbose=2 /Applications/X.app   # 期望：valid on disk + satisfies its Designated Requirement
spctl -a -vvv -t exec /Applications/X.app           # 期望：accepted / Notarized Developer ID
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" /Applications/X.app/Contents/Info.plist
```

**结构比对**（判断拷贝有没有多/少文件，最有效的一招）：

```zsh
diff <(cd "/Volumes/<卷名>/X.app" && find . | sort) <(cd /Applications/X.app && find . | sort)
```

## 坑：ditto 会破坏 .app 的签名封存

`ditto` 把 .app 拷到别的卷时，会在每个文件旁留下自己的临时/克隆文件：

- `.BC.D_<6位>` —— 符号链接
- `.BC.T_<6位>` —— 普通文件（**占真实磁盘空间**）

后果：`codesign --verify` 报 `file added: .../.BC.T_xxxx`，`spctl` 报
`a sealed resource is missing or invalid`。实测某 6131 文件的 App 被灌进 6131 个 `.BC.T_*`，
体积从 1.3G 涨到 2.6G。

**修复**（残留文件不属于签名内容，删除无风险；建议先确认没有非符号链接的已签文件被误伤）：

```zsh
find /Applications/X.app -name ".BC.*" -type f -delete
find /Applications/X.app -name ".BC.*" -type l -delete
```

删完再跑一遍上面的校验与 `diff`，应恢复 `valid on disk` + `accepted`。

## 其他要点

- **curl 下载不会写 `com.apple.quarantine`**，所以已公证的应用可直接 `open`，不需要"右键→仍然打开"。
  只有浏览器下载才会加隔离属性；真要处理用 `xattr -d com.apple.quarantine <app>`，但**不要**用它来绕过 Gatekeeper 报错 —— 先修签名。
- **bundle name ≠ 品牌名**：验证时看 `CFBundleIdentifier`（例如 `ChatGPT.app` 的 ID 是 `com.openai.codex`）。
  不要为了"看起来对"去重命名 .app。
- **警惕 6–20 MB 的"安装器型" DMG**：体量远小于正常桌面应用（Electron 系通常 100–250 MB）时，里面多半是
  bootstrapper（如 `com.nousresearch.hermes.setup` / `Hermes-Setup`，单个 arm64 可执行文件 + 一个 icns）。
  这种包拷进 /Applications 后**首次启动才会联网拉真正的运行时**（可能几百 MB，还可能要 Git / uv / Python 3.11+）。
  识别方法：`find <app> -type f | wc -l`（个位数 = 壳）＋ `du -sh`。
  如果用户期待"装完即用"，必须提前讲清这一步，别让他在首次启动时被大下载和网络问题卡住。
  另外要留意同名多版本：搜 "X 桌面版" 常同时出现官方版和第三方 companion（如 Hermes Agent 官方 vs `fathah/hermes-desktop`、
  `dodo-reach/hermes-desktop`），先按 star 数 / 组织归属 / 官网是否挂链 三项判官方，再动手。
  - **但第三方 companion 未必是"另一条路"**：`fathah/hermes-desktop` 发布出来的应用叫 **Hermes One**，
    Bundle ID `com.nousresearch.hermes`（签名方却是 `ZIQX CREATIVE CLIQUE LLP`），它跑的就是**同一份官方 install script、
    共用同一个 `~/.hermes`** —— 本质是给官方 agent 套 GUI。所以换 GUI 前先确认底层 agent 是否已装好，
    已装好的话直接装 GUI 即可，**不用重跑那几个小时的运行时安装**。
  - 判断方法：读它 README 的 Install 段（`curl -sL https://gh-proxy.com/https://raw.githubusercontent.com/<repo>/main/README.md`），
    看是否复用官方 install script。
- 启动验证：`open -a /Applications/X.app` 后 `pgrep -fl <进程名>`，能查到主进程 + 辅助进程即成功。

### 关键坑：WorkBuddy 的 shell 注入了 `ELECTRON_RUN_AS_NODE=1`，Electron 应用会被"启动即退出"

**症状**：`open -a` 返回 0、`codesign`/`spctl` 全过，但 `pgrep` 查不到任何进程。
直接跑 `Contents/MacOS/<exe>` 只吐一行：

```
[ERROR:electron/shell/app/node_main.cc:153] Node.js environment variables are disabled
because this process is invoked by other apps.
```

**根因**：WorkBuddy 的 Bash 工具 shell 里 export 了
`ELECTRON_RUN_AS_NODE=1` 和 `NODE_OPTIONS=--require=.../node-language-shim.cjs`。
Electron 见到 `ELECTRON_RUN_AS_NODE=1` 就**不当 GUI 应用启动，转而以纯 Node 模式跑然后退出**。

先自查（一眼看穿）：

```zsh
echo "ELECTRON_RUN_AS_NODE=[$ELECTRON_RUN_AS_NODE] NODE_OPTIONS=[$NODE_OPTIONS]"
```

**正确做法：起 GUI 应用必须净化环境**（只要 `HOME`/`PATH`/`USER` 就够）：

```zsh
env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin USER="$USER" open -a "/Applications/X.app"
sleep 8
ps -eo pid,comm | grep -i "<关键词>"     # 应见主进程 + Helper(GPU/Network/Renderer)
```

验证时**用 `ps -eo pid,comm` 而不是只靠 `pgrep -fl`** —— 前者能列出全部 helper 子进程，
一眼分辨"起来了"和"闪退"。想确认窗口真的画出来了：

```zsh
osascript -e 'tell application "System Events" to tell process "X" to get name of windows'
```

**这是本机环境问题，不是应用/签名问题** —— 坚哥从 Finder / Launchpad 双击不受影响，
**别为此去改 fuses 或重签应用**。
- 装完问一句要不要删 `~/Downloads` 里的 dmg（几百 MB），**不要自动删用户目录里的文件**。

## 反操作：完整卸载一个 macOS 应用

用户要"卸载掉"通常意味着**清干净**，别只删 /Applications 里的 .app。完整清单：

| 类别 | 路径 |
|---|---|
| 应用本体 | `/Applications/X.app` |
| 偏好 | `~/Library/Preferences/<bundleid>.plist` |
| 数据 | `~/Library/Application Support/<App 名>`、`~/Library/Application Support/<厂商>/<App>` |
| 缓存 / 网络存储 / 日志 | `~/Library/Caches/<bundleid>`、`~/Library/HTTPStorages/<bundleid>`(+`.binarycookies`)、`~/Library/Logs/<bundleid>` |
| CLI 包的独立主目录 | 如 `~/.codex`、`~/.config/<tool>` |

盘点用：`find ~/Library -maxdepth 3 -iname "*<关键词>*"`，别只按应用显示名找 ——
**bundle name 可能和品牌名不同**（`ChatGPT.app` 的 ID 是 `com.openai.codex`，两种名字都要搜）。

### 卸载前先分清「共享资产」——别把别人的凭据一起清掉

同一个凭据可能被多个工具复用。典型：给 Codex 配的 `ATLASCLOUD_API_KEY`
（`~/.zshrc` 导出 + LaunchAgent `com.user.atlascloud-env` 注入 GUI 会话）
**Hermes / Hermes One 也在用**。卸载 Codex 时如果顺手把这些清了，Hermes 立刻就废。

所以动手前先过一遍：
1. `grep -n "<变量名>" ~/.zshrc`、`ls ~/Library/LaunchAgents/`、`launchctl list | grep -i <关键词>` —— 找出环境变量 / 开机注入项
2. `pgrep -fl "<其它可能依赖它的应用>"` —— 看谁是活的消费者
3. 判据：**凭据文件里如果只有 key、没有该应用专属的型号选择/界面设置，就倾向于保留**，并在报告里明确告知"这项我留着了，因为 X 在用"。
4. 应用自己的配置目录（如 `~/.codex`，内含指向第三方 API 的 `config.toml`）可以整个删 —— 前提是重建所需内容已沉淀在别处（本机有 skill `codex-third-party-api` 记录完整模板）。

卸载方式：
- npm 全局包：`npm uninstall -g --prefix ~/.local @scope/pkg`（它删掉 bin 软链和包体，可能残留一个空的 scope 目录，用 `rmdir` 收尾）
- **先 `defaults delete <bundleid>` 再 `trash` plist** —— 否则 `cfprefsd` 可能把内存里的偏好回写，plist "删了又回来"
- 其余路径一律 `trash`，**不要 `rm -rf`**

### 关键坑：应用会劫持共享命令，卸载后留下悬空软链

有些应用安装时会往 `~/.local/bin`（或 `/usr/local/bin`）**塞软链指向自己的私有运行时**，覆盖同名命令。
删掉它的运行时目录后，这些软链就悬空了 —— 命令直接失效。

**实例**：Hermes（`com.nousresearch.hermes`）安装时把 `~/.local/bin/node|npm|npx` 指向
`~/.hermes/node/bin/*`（自带 node 26.9.0）。卸载 `~/.hermes` 后三个命令全悬空。
（本机运气好：真正的 node 在 `/usr/local/bin/node` v24.14.0 且 PATH 优先，所以没出事 —— **但不能赌，必须显式检查**。）

**卸载前必查**：

```zsh
ls -la ~/.local/bin/ /usr/local/bin/ 2>/dev/null | grep '\->'
# 找出目标落在「即将删除的目录」里的软链
```

**卸载后验证**（这一步别省）：

```zsh
for f in node npm npx; do p="$HOME/.local/bin/$f"; [ -L "$p" ] && echo "悬空候选: $p -> $(readlink "$p")"; done
```

⚠️ **`-e` 检测悬空软链返回 false**（它跟随软链）。判断「软链本身还在不在」必须用 **`-L`**（或 `-h`）。
所以上面用 `[ -L ]`，写成 `[ -e ]` 会全部漏检。

**修复**：确认系统里有替代实现后，`trash` 掉悬空软链（或重指向系统版本），再验证 `node -v` / `npm -v` 可用。

**附带**：用 uv 装的工具可能在 `~/.local/share/uv/tools/<name>`（独立于 `~/.<app>`），卸载盘点时容易漏掉。

### 两个输出判读陷阱

- **命令带 `Sandbox bypassed` 提示时可能被执行两遍** —— 第二遍会报部分路径「不存在」，
  很容易误判成"卸载失败"。**别急结论**，用只读命令（`ls -ld` / `find`）复核现状再判断。
- **zsh 下 `ls <glob>` 无匹配是硬错误**（`no matches found`，退出码非零），`2>/dev/null` **挡不住**。
  检查路径存在性一律用 `[ -e ]` / `[ -L ]`，别用 `ls` + glob（要用就 `find`）。

### 关键坑：`trash` 的退出码不可信

`/usr/bin/trash` 在本机**成功移入废纸篓后仍会返回非零退出码（实测 5）**。
若写 `if trash "$p"; then ... elif mv ...; fi` 这种逻辑，会把已成功的项误报为失败，并触发多余的回退。

**正确做法**：逐个 `trash`，然后用**存在性检查**汇报结果，例如

```zsh
for p in "$@"; do
  trash "$p" 2>/dev/null
  [ -e "$p" ] && echo "✗ 仍在: $p" || echo "✓ 已删: $p"
done
```

- 收尾清空目录用 `rmdir`（只删空目录，非空自动报错），比 `rm -rf` 安全。
- `ls ~/.Trash` 可能报 `Operation not permitted`（TCC 限制），属正常，别当成失败。
- 卸载完可用 `command -v <cmd>`、`npm ls -g`、`ls /Applications | grep -i`、`pgrep -fl`、
  `find ~/Library -iname "*<关键词>*"` 做五项终检。
- 移入废纸篓**不会立即释放磁盘**。想真正回收空间得清空废纸篓，但那会连带清掉里面其它东西 ——
  **先问用户，不要自己动手**。

### ⚠️ 清空废纸篓：WorkBuddy 环境下**做不到**，直接交给用户

即使用户明确说"清理废纸篓"，**也不要**尝试用 `rm -rf ~/.Trash/*` 绕过 —— 那是规则明令禁止的
（递归删 Home + `rm -rf` + 宽泛通配符，三重违规），而且废纸篓的意义就是"还能反悔"。

本机实测，三条路全被 macOS TCC 挡死：

| 尝试 | 结果 |
|---|---|
| `ls ~/.Trash` / `du -sh ~/.Trash` | 命令被**安全策略拦截**（连清单都读不到） |
| `osascript -e 'tell application "Finder" to empty trash'` | `execution error: 发生权限违例 (-10004)`，**沙箱外重试同样失败** |
| `open ~/.Trash` | `_LSOpenURLsWithCompletionArgs() failed with error -54` |

**根因**：WorkBuddy 进程没拿到「隐私与安全性 → 自动化 → 访达」授权，TCC 静默拒绝（连授权弹窗都不出）。

**正确话术**：查完磁盘占用后告诉用户 ——
> 废纸篓我这层权限动不了，你点 Dock 上的废纸篓 → 右键「清倒废纸篓」（或 `⌘⇧⌫`），会释放约 X GB。

可选的根治方案（用户愿意的话）：系统设置 → 隐私与安全性 → 自动化 → 找到 WorkBuddy → 勾选「访达」。

**注意 `trash` 命令仍然可用**（只是"移入"不是"清空"）—— 删除单个文件照常走 `trash`，
验证照旧用「原路径是否还存在」。清空这一步单独留给用户。
