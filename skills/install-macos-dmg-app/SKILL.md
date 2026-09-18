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
- 启动验证：`open -a /Applications/X.app` 后 `pgrep -fl <进程名>`，能查到主进程 + 辅助进程即成功。
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

卸载方式：
- npm 全局包：`npm uninstall -g --prefix ~/.local @scope/pkg`（它删掉 bin 软链和包体，可能残留一个空的 scope 目录，用 `rmdir` 收尾）
- 其余路径一律 `trash`，**不要 `rm -rf`**

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
