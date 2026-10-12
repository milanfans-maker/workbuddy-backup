---
name: hypit-deploy
description: 在 macOS（尤其是国内网络、无翻墙、brew 不可用的机器）上部署 Hypit（github.com/hypit-ai/hypit）—— 这套「AI agent 视频创作语言」。当任务是「部署/安装 hypit」「用 hypit 做视频复刻」「hypit 装不上/跑不起来」「给 hypit 接本地模型（ComfyUI/其他）」「hypit doctor 报错」时使用。含三层架构认知、国内镜像适配、只读链路验证法、以及项目级 Provider 接入路径。
agent_created: true
---

# 部署 Hypit（含国内网络适配）

## 先纠正认知：Hypit 不是服务

它**不是一个 web 服务或 Docker 应用**，别去找 `docker run` / `npm start`。它是**给 AI agent 用的视频创作语言 + CLI**。三层生命周期各自独立：

| 层 | 提供什么 | 装法 | 装它不等于 |
| --- | --- | --- | --- |
| **Skill** | 生产判断与导航 | `npx skills add hypit-ai/hypit -g` | 装可执行文件 |
| **`@hypit/hypit`** | CLI / Studio / Runtime / bundled packages | `npm i -g @hypit/hypit` | 连账号、给模型额度、准备浏览器 |
| **视频项目** | .svml/.svs/.svrun 源、Runs、素材、Results | 项目自己的目录 | —— |

**Skill 更新不更新可执行文件；更新任一都不会重写项目的 Sources 或重新生成 Outputs。**

## 一、装 CLI

```bash
npm install -g --prefix ~/.local @hypit/hypit --registry=https://registry.npmmirror.com
```

- 装到 `~/.local` 是本机约定（`~/.local/bin` 已在 PATH）。
- 原生模块 `sharp` / `koffi` 会拉预编译二进制，npmmirror 能正常供给，**不需要**额外 mirror 环境变量（真卡住再加 `--sharp_binary_host=https://npmmirror.com/mirrors/sharp`）。
- 装完立刻验证：

```bash
hypit version      # 报 Distribution 与实际 launcher 路径
hypit paths        # 报项目/.hypit/Profile/宿主位置
```

## 二、装 Skill

官方命令（skill 单一副本在仓库 `skills/hypit`，供各 agent 共享）：

```bash
npx skills add hypit-ai/hypit -g -y --copy -a '*'
```

**坑：这条命令很慢**——它要 clone 整个仓库，实测卡 6 分钟以上、终端无输出。**卡住 ≠ 失败**，别急着重跑；直接查产物：

```bash
find ~/.agents/skills/hypit -type f | wc -l    # 应为 73
```

落点：`~/.agents/skills/hypit`（主副本）+ `~/.claude/skills/hypit`。**WorkBuddy 和 Codex 不在 skills CLI 的识别范围内**，要手动补：

```bash
rsync -a --delete ~/.agents/skills/hypit/ ~/.workbuddy/skills/hypit/
rsync -a --delete ~/.agents/skills/hypit/ ~/.codex/skills/hypit/
```

校验：`SKILL.md` 应为 28604 字节，与 `raw.githubusercontent.com/hypit-ai/hypit/main/skills/hypit/SKILL.md` 一致。

## 三、补齐宿主工具

`hypit doctor` 会逐项报缺。宿主级硬依赖：

| 工具 | 地位 | 本机获取方式 |
| --- | --- | --- |
| **Node.js** | Distribution 运行所需（仓库 `.node-version` = 24.14.1） | 已有 |
| **ffmpeg + ffprobe** | 媒体处理硬依赖，**两个都要在 PATH** | 见下（**别走 brew**） |
| **uv** | 本地 Python Program 建锁定环境（WhisperX 等） | `~/.local/bin/uv` |
| 渲染浏览器 | HyperFrames 渲染 | `hypit runtime up` 自动下到 `~/.cache/hyperframes/` |

### ⚠️ ffmpeg 在本机不能走 brew

Homebrew 的 `brew install` 在这台机器上**固定失败**：

```
Error: Operation not permitted @ apply2files - /opt/homebrew/var/homebrew/locks/<hash>--<pkg>.incomplete.download.lock
```

已排除沙箱、属主权限、残留锁三种原因（清空 locks 后 brew 重建锁时照样失败）。**用静态二进制**：

```bash
BASE="https://gh-proxy.com/https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
mkdir -p /tmp/ffmpeg_dl && cd /tmp/ffmpeg_dl
for n in ffmpeg ffprobe; do
  curl -L --retry 2 -o "$n.gz" "$BASE/$n-darwin-arm64.gz"      # 各 ~18MB
done
gunzip -f ffmpeg.gz ffprobe.gz
install -m 755 ffmpeg ffprobe ~/.local/bin/
xattr -c ~/.local/bin/ffmpeg ~/.local/bin/ffprobe
ffmpeg -version && ffprobe -version     # 应为 6.0
```

- **arm64 机器务必取 `-darwin-arm64`**（该 release 同时供 x64）。
- 实测：经 gh-proxy 下载 ffmpeg 约 210KB/s、ffprobe 约 6MB/s，总耗时 ~1.5 分钟。
- 备选源：`evermeet.cx`（可达，但只给单文件）；`pip install static-ffmpeg` 的 wheel 是 `py3-none-any`，二进制仍要运行时下载，**不划算**。

## 四、建 Profile 并起 Runtime

```bash
cd <项目目录>
hypit runtime init default        # 生成并选中 starter Profile（不登录、不下载）
hypit runtime up                  # 准备 Programs（含下 Chrome Headless Shell）并启动 Worker
hypit runtime status              # 期望：Worker running，Programs N/N ready
hypit doctor                      # 看剩余诊断
```

- starter Profile 含三个 endpoint：`hypihub.default`（托管，需登录）、`media.local`（靠 ffmpeg）、`hyperframes.local`（靠 managed Chrome）。
- 注意 `runtime init <name>` 会在**项目根**生成同名文件（如 `default`），这是设计如此。
- Chrome Headless Shell 从 `storage.googleapis.com` 下载，本机直连可成。

## 五、只读链路验证（不花钱、不提交任务）

`hypit check` / `hypit plan` 都是只读的，`plan` 明确"不执行"。用 skill 自带的官方示例源做验收：

```bash
mkdir -p _verify && cp ~/.workbuddy/skills/hypit/references/production/examples/* _verify/
hypit check _verify/production.svml      # 期望：✓ Source is valid，16 个 Output
hypit plan  _verify/production.svrun     # 期望：列出每个请求走哪个 endpoint 及是否收费
```

`check` 会按需报出缺失的机包并给出命令，照做即可：

```bash
npm_config_registry=https://registry.npmmirror.com hypit packages install @fontsource-variable/inter@5.3.0
npm_config_registry=https://registry.npmmirror.com hypit packages install @infolektuell/noto-color-emoji@0.2.0
```

`plan` 的输出是判断"还差什么"的最快入口：标 `local, no Provider charge` 的本地请求全部就绪，就说明宿主工具链没问题了。

## 六、接本地生成模型（ComfyUI 等）

官方 Distribution **不含** ComfyUI provider。可用的内置 provider 只有：
`provider-hypihub` / `beatapi` / `hiapi` / `monid` / `pollo` / `tokendance` / `media-local` / `hyperframes-local` / `whisperx-local` / `image-opencv-local`。

要接自己的服务，照 `examples/provider-package` 写**项目级 Provider**：

1. 复制 `examples/provider-package/packages/provider-videos`（异步任务形态，最贴近视频服务）到项目的 `packages/`
2. 改 `providerModule.name`；把示例的 `POST /tasks` + `GET /tasks/{id}` 协议换成真实服务的协议 —— ComfyUI 是
   `POST /prompt` → 轮询 `GET /history/{prompt_id}` → `GET /view` 取产物，参考图走 `POST /upload/image`
3. **复用现成 Model 语义**（如 `@hypit/seedance@1#seedance-2-mini` / `@hypit/gpt-image@1#gpt-image-2`），
   provider 只负责协议映射；**不要为了迁就某个服务去改 Model**，也不要把服务地址写进 Model
4. 构建安装：`npm install && npm run build` → 回项目 `npm install ./packages/provider-xxx`
5. 把示例的 `hypit.runtime.json` 里的 endpoint / credentials / bindings **合并**进项目 Profile（别覆盖已有服务）
6. 生命周期测试不需要付费请求，先跑测试再联调

**低成本替代**：`@hypit/whisperx#whisperx-alignment` 有现成的本地实现 `@hypit/provider-whisperx-local`，
把 binding 指过去即可免费跑语音对齐（准备好 uv；HF 权重走 `HF_ENDPOINT=https://hf-mirror.com`）。

## 常见坑速查

- `DEP0205 module.register() is deprecated` 警告：node 22 下 tsx/vite 引起，**无害**，输出里 `grep -v DEP0205` 滤掉。
- `hypit` 命令找不到：`~/.local/bin` 不在当前 shell 的 PATH；显式 `export PATH="$HOME/.local/bin:$PATH"`。
- 登录后仍报 `RUNTIME_CREDENTIAL_MISSING`：登录是**按 endpoint**做的，`hypit auth login <endpoint>`，且实例名要与 Profile 里一致。
- 修改运行中服务的模型/设备/批量等设置需**空闲时重启 helper**（`programs down` 再 `programs up`）；只重启 Worker 不会重启它。
- 「服务健康」≠「每种语言/资源都已准备」：`alignmentLanguages` 是准备需求，新增语言必须改 Profile 并重跑 `programs prepare`。
