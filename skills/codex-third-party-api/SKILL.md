---
name: codex-third-party-api
description: 把 Codex（桌面端 / CLI / IDE 扩展）的模型通道接到第三方 OpenAI 兼容 API，绕开 ChatGPT 官方登录。当任务是「Codex 登录不了」「Codex 被墙用不了」「给 Codex 配某某的 API」「Codex 接自定义模型」「改 codex config.toml 的 model_providers」「Codex 桌面端能不能用第三方 API」时使用。含 Atlas Cloud 实战参数、桌面端环境变量注入（launchctl / LaunchAgent）、以及 wire_api 只认 responses 等关键限制。
agent_created: true
---

# Codex 接入第三方 OpenAI 兼容 API

适用场景：官方登录走不通（国内网络），改用第三方中转 / gateway 作为模型通道。
实测环境：Mac mini M4 / macOS 26.6.2 / Codex CLI 0.155.0 / 桌面端 26.915.31029。
（装桌面端本体的流程见 skill `install-macos-dmg-app`。）

## 先记住这 5 条硬事实

1. **桌面端安装包叫 `ChatGPT.app`**，但 `CFBundleIdentifier` 是 `com.openai.codex` —— 它就是 Codex 桌面版本体，别以为装错了。
2. **桌面端 / CLI / IDE 扩展共享同一份 `~/.codex/config.toml`**，配一次三端生效。
3. **`wire_api` 只认 `responses`**。新版 Codex 已移除 chat completions 支持，所以第三方端点**必须实现 `/v1/responses`**。接之前先实测：

   ```zsh
   curl -s https://<endpoint>/v1/responses -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
     -d '{"model":"<model>","input":"Reply with exactly: ROUTE_OK"}'
   ```

4. **project 级 `.codex/config.toml` 里的 provider 配置会被 Codex 忽略**（安全边界，防止仓库偷偷改你的请求出口），必须写 user 级 `~/.codex/config.toml`。
5. **GUI 应用不继承 shell 的环境变量**。桌面端读不到 `env_key` 指向的变量就 401 —— 最容易漏的一步，见下文。

## 配置

`~/.codex/config.toml`：

```toml
model = "<provider-model-id>"
model_provider = "myprovider"

[model_providers.myprovider]
name = "My Provider"
base_url = "https://api.example.com/v1"
env_key = "MYPROVIDER_API_KEY"   # 这里写变量名，不是 key 本身
wire_api = "responses"
```

`base_url` 带不带 `/v1` **以服务商文档为准**，没有通用规则（Atlas Cloud 要带 `/v1`）。

## 环境变量：CLI 和桌面端要分别处理

| 使用方式 | 怎么让变量可见 |
|---|---|
| CLI（终端里跑 `codex`） | 写进 `~/.zshrc`：`export MYPROVIDER_API_KEY="..."` |
| 桌面端（从 Dock / Finder 启动） | **必须** `launchctl setenv MYPROVIDER_API_KEY "..."` |
| 桌面端重启后仍要生效 | 写 LaunchAgent（见下）—— `launchctl setenv` 关机即失效 |

LaunchAgent —— `~/Library/LaunchAgents/com.user.<name>-env.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key><string>com.user.myprovider-env</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/launchctl</string><string>setenv</string>
		<string>MYPROVIDER_API_KEY</string><string>&lt;key&gt;</string>
	</array>
	<key>RunAtLoad</key><true/>
</dict>
</plist>
```

```zsh
plutil -lint ~/Library/LaunchAgents/com.user.myprovider-env.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.myprovider-env.plist
launchctl list | grep myprovider          # 出现在列表里即成功
launchctl getenv MYPROVIDER_API_KEY       # 确认值
```

**改完要彻底退出并重开桌面端**（⌘Q 后重开），已运行的进程不会重新读环境。

## 验证（按顺序，别跳）

```zsh
codex doctor          # 看 model provider / wire API / reachability 三段
codex exec --skip-git-repo-check "Reply with exactly: ROUTE_OK"
```

- `doctor` 期望：`active provider endpoints are reachable over HTTP`，总分 0 fail。
- `exec` 期望：输出里 `provider: <你的 provider>`、`model: <你的 model>`，并正确回显字符串。

验证桌面端是否拿到环境变量（不需要截图）：

```zsh
PID=$(pgrep -f "ChatGPT.app/Contents/Resources/codex" | head -1)
ps eww -p "$PID" | tr ' ' '\n' | grep MYPROVIDER_API_KEY
```

验证桌面端**没有卡在登录页**（看日志里有没有主界面才发的调用）：

```zsh
grep -E "model/list|plugin/installed|mcpServerStatus/list" \
  $(find ~/Library/Logs/com.openai.codex -name "*.log" | head -1)
```

有输出 = 已进入工作界面。

## 已知限制（看到这些别慌，都不影响本地干活）

- 日志里 `Sign in to ChatGPT to check remote control authorization` / `register push notifications` —— 只是**远程控制**和**推送通知**两个附加功能需要官方登录。
- `/wham/tasks/list`、`/wham/usage` 返回 **432 Workspace routing is unavailable** —— Codex Cloud 云端任务列表 + 用量统计不可用（需官方登录），本地会话不受影响。
- `warning: Model metadata for '<id>' not found. Defaulting to fallback metadata` —— 自定义 model id 不在内置 catalog，功能正常，只是 context window 等元数据走默认。想修可加 `model_context_window` / `model_max_output_tokens`，或用 `model_catalog_json` 指一份自建 catalog。
- 桌面端模型选择器可能把自定义模型显示成 "Custom"（已知 issue #19694），但**请求仍会发到正确的模型**。

## Atlas Cloud 实战参数（坚哥这台机器已配好）

| 项 | 值 |
|---|---|
| base_url | `https://api.atlascloud.ai/v1` |
| 协议 | `/v1/responses`（Codex 可用）、`/v1/chat/completions`、`/v1/messages`(Anthropic)、Gemini |
| 认证 | `Authorization: Bearer <key>`，key 以 `apikey-` 开头 |
| 列模型 | `curl https://api.atlascloud.ai/v1/models` —— **无需 key**，国内直连不翻墙，约 119 个模型 |
| 模型 id 格式 | `<厂商>/<模型名>`，如 `openai/gpt-5.3-codex` |
| 本机落地 | `~/.codex/config.toml` 指向 `openai/gpt-5.3-codex`；key 在 `~/.zshrc` + LaunchAgent `com.user.atlascloud-env` |

⚠️ **不是每个模型都支持 responses 协议**。实测 `openai/gpt-5.3-codex`：`/v1/responses` → 200，`/v1/chat/completions` → 400。换模型前先按上面的 curl 探一发。

## 其它要点

- 装 CLI：`npm install -g --prefix ~/.local --registry=https://registry.npmmirror.com @openai/codex`（本机不走 brew）。
- `codex app` 命令可以「启动桌面端，缺安装包则自动下载」；也可以按 `install-macos-dmg-app` 走官方 DMG。
- 卸载时别漏 `~/.codex`（CLI 主目录 + 会话/日志 sqlite）和 `~/Library/Application Support/Codex`（桌面端 Chromium 数据）。
