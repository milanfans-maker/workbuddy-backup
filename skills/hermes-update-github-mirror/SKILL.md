---
name: hermes-update-github-mirror
description: 排查并修复 Hermes One / Hermes Agent 的更新失败——界面红色「更新失败」提示条、hermes update 卡死或报错、git fetch GitHub 超时、Agent 版本落后上游。覆盖两层更新的区分（桌面应用 electron-updater vs Agent 本体 git）、日志与状态文件位置、以及用 gh-proxy 镜像重写 git 通道的修法。当任务是「Hermes 更新失败」「Hermes One 提示更新失败」「hermes update 不动」「Hermes 升级/更新」「检查更新报错」时使用。
agent_created: true
---

# Hermes 更新失败：先分清哪一层，再修 GitHub 通道

**一句话**：Hermes 有两层更新，红了先看清是哪一层；而两层失败的根因通常同一个——本机到 github.com 不通。

先定位层次，别默认某一层就开干。

## 第 0 步：分清两层

| 层 | 是什么 | 谁在触发 | 日志 / 状态 |
|---|---|---|---|
| A | **桌面应用** Hermes One（Electron 外壳） | 启动 5 秒后**自动**检查（硬编码，关不掉）+ 设置页按钮 | `~/Library/Application Support/hermes-desktop/logs/updater.log` |
| B | **Agent 本体** `~/.hermes/hermes-agent`（Python） | 设置页「更新」按钮 / CLI `hermes update` | `~/.hermes/.update_check`（JSON） |

GUI 文案判别：
- 无句点「更新失败」→ 多为 A（`common.updateFailed`）
- 带句点「更新失败。」→ 多为 B 的设置页结果（`settings.updateFailed`）

⚠️ **A 层报错 ≠ 真有新版**。先核对版本再决定要不要当回事。

## 第 1 步：取证

```bash
# A 层
cat "/Applications/Hermes One.app/Contents/Resources/app-update.yml"   # provider/owner/repo
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "/Applications/Hermes One.app/Contents/Info.plist"
tail -30 ~/Library/Application\ Support/hermes-desktop/logs/updater.log
#   成功 → "Update for version X is not available (latest version: X)"  ← info 级，界面不报警
#   失败 → net::ERR_TIMED_OUT / net::ERR_CONNECTION_CLOSED

# B 层
git -C ~/.hermes/hermes-agent log -1 --format="%h %ad" --date=short
cat ~/.hermes/.update_check      # {"ts":…, "behind": N, "ver": "0.21.3", "head": …, "target": …}
```

`behind` = 落后上游提交数，`ver` = 本地 Agent 版本。

## 第 2 步：确认 GitHub 通道状况（本机 2026-09 实测）

```bash
curl -sS -o /dev/null -w "api=%{http_code} %{time_total}s\n" --max-time 12 https://api.github.com/repos/NousResearch/hermes-agent
curl -sS -o /dev/null -w "web=%{http_code} %{time_total}s\n" --max-time 12 https://github.com
```

**典型症状：api.github.com 通（~0.6s），github.com 主站超时。**
- electron-updater 无 token 时走 github.com 通道 → 检查偶发失败
- `git fetch` 走 github.com → **必然失败**

核对上游是否真有新版：
```bash
curl -sS https://api.github.com/repos/fathah/hermes-desktop/releases/latest \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tag_name'], d['published_at'])"
```

## 第 3 步：修 —— 给 git 挂镜像

**实测可用**：`gh-proxy.com`、`ghproxy.net` **支持 git 智能协议**（不只是下载文件）。
`gitclone.com` 已挂（返回 502）。

```bash
# 推荐：只给这一个仓库挂（精准，不动全局）
git -C ~/.hermes/hermes-agent config \
  url."https://gh-proxy.com/https://github.com/".insteadOf "https://github.com/"

# 想全机 GitHub 都走镜像时（可选，影响所有仓库）
git config --global url."https://gh-proxy.com/https://github.com/".insteadOf "https://github.com/"
```

Hermes 官方代码本身就识别这种 url 重写（`hermes_cli/banner.py`），不会误判。

**验证**（`--dry-run` 不下载对象，安全）：
```bash
git -C ~/.hermes/hermes-agent ls-remote origin main
git -C ~/.hermes/hermes-agent fetch --dry-run origin main
# 出现 "老SHA..新SHA  main -> origin/main" 即通道已通
```

`git config --get remote.origin.url` 的原始值不变（insteadOf 只在传输层重写），
所以不会触发 `_is_fork` 误判（`update_cmd.py::_prepare_git_command`）。

## 第 4 步：真要升级时的注意点

`hermes update` 流程：预检 → **自动备份**（`~/.hermes/backups/`）→ 判断 git / zip 路径
（`_prepare_git_command`：有 `~/.hermes/hermes-agent/.git` 走 git，否则走 zip，非 Windows 直接 `sys.exit(1)`）
→ scoped fetch → 代码切换 → 依赖同步 → 可能重建 desktop。

- **跨度大先掂量**：上百上千 commit 的升级可能影响 `~/.hermes/config.yaml`、自建插件
  （如 `~/.hermes/plugins/image_gen/comfyui`）、`~/.hermes/models.json`。升级前留好备份。
- 依赖同步走 **pip / npm**；本机默认官方源且无 `~/.npmrc` → 卡在这一步就配清华/阿里云 pip 源 + npmmirror。
- 升级会重启 gateway。

## 坑

- **macOS 没有 `timeout`**。用 `perl -e 'alarm N; exec @ARGV' git ...`；
  但 git 走 http 时 alarm 杀不干净子进程（会一直挂着），收尾用 `pkill -f "ls-remote ..."`。
- **asar 里的 `checkUpdateFailed` 是 framer-motion 的内部方法**，与更新无关；grep 命中先看上下文。
- GitHub API 的 assets 列表用 `head` 截断，会误判「没有 latest-mac.yml」——**其实存在**，内含 x64/arm64 两个 zip。
- 桌面应用的「自动更新」开关存在
  `~/Library/Application Support/hermes-desktop/update-preferences.json` 的 `autoUpgrade`
  （文件默认不存在 = 启用），**但只关自动下载，关不掉启动时那次检查**（代码里是裸 `setTimeout(…, 5e3)`）。
