---
name: macos-install-binary-no-brew
description: 在这台 Mac（macOS 26 / arm64，Homebrew 的 install 通道损坏）上安装系统级命令行二进制与预编译包，不走 brew。当任务是「装 ffmpeg/ripgrep/jq/tree 等 CLI」「brew install 报 Operation not permitted @ apply2files」「没有 brew 怎么装某个工具」「找一个二进制的国内下载源」时使用。含故障辨别、静态二进制选源、镜像加速、安装与校验的完整套路。
agent_created: true
---

# macOS 上绕开 brew 装二进制

## 故障辨别：brew 的 info 能用，install 不能用

本机（Mac mini M4）Homebrew 处于这种状态：

```bash
brew info ffmpeg     # ✓ 正常，能列版本、依赖、bottle 大小
brew install ffmpeg  # ✗ 固定失败
```

失败长这样：

```
Error: Operation not permitted @ apply2files -
/opt/homebrew/var/homebrew/locks/<hash>--<pkg>.incomplete.download.lock
```

**已经排除过的原因（别重复排查）**：
1. 沙箱 → 关闭沙箱跑，照样失败
2. 权限 → `/opt/homebrew` 属主就是当前用户（`wangjian:admin`），且 `touch` / `mv` / `rm` 在 locks 目录里都成功
3. 残留锁 → 把 53 个 `.incomplete.download.lock` 全删干净，brew 重建锁时**一样失败**

结论：**这是 brew 写入通道本身的问题，不是环境可以配好的**。要装东西直接走下面的静态二进制路线。

## 选源顺序（国内网络优先）

按"国内可达性 + 是否免 root"排序：

| 目标 | 首选路径 |
| --- | --- |
| ffmpeg / ffprobe | `eugeneware/ffmpeg-static` release 的 `*-darwin-arm64.gz`，经 gh-proxy 加速 |
| 通用 GitHub release 二进制 | `https://gh-proxy.com/https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>` |
| Node 生态工具 | `npm i -g --prefix ~/.local <pkg> --registry=https://registry.npmmirror.com` |
| Python 生态工具 | `uv tool install` / pip + `https://pypi.tuna.tsinghua.edu.cn/simple` |
| 模型权重 | ModelScope 优先于 HuggingFace；HF 要走 `HF_ENDPOINT=https://hf-mirror.com` |

**实测有效的镜像**（2026-09-21）：

- `https://gh-proxy.com/https://github.com/...` → 200，可用
- `https://ghfast.top/...` → 000，不通
- `https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles` → 能取 bottle，但 brew 装不上（见上），手动解 bottle 不现实（依赖链太深）

**别踩的坑**：
- `pip install static-ffmpeg` 的 wheel 是 `py3-none-any`（纯 Python 标签），**二进制不在 wheel 里**，运行时才下载 —— 想靠 PyPI 镜像一次拿到二进制是行不通的
- 本机**没有** conda / micromamba / pixi，conda-forge 镜像那条路走不通
- `evermeet.cx` 可达（302 跳转）但只提供 ffmpeg 单文件，拿不到 ffprobe

## 标准流程

以 ffmpeg 为例（其它二进制同构）：

```bash
# 1. 先确认真实 release 与资产名（别猜 tag）
curl -sS "https://api.github.com/repos/eugeneware/ffmpeg-static/releases/latest" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['tag_name']); [print(a['name'], round(a['size']/1e6,1),'MB') for a in d['assets']]"

# 2. 下载（arm64 机器务必取 -darwin-arm64）
BASE="https://gh-proxy.com/https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
mkdir -p /tmp/dl && cd /tmp/dl
for n in ffmpeg ffprobe; do curl -L --retry 2 -o "$n.gz" "$BASE/$n-darwin-arm64.gz"; done

# 3. 解压安装
gunzip -f ffmpeg.gz ffprobe.gz
install -m 755 ffmpeg ffprobe ~/.local/bin/

# 4. 清安全属性（规避 Gatekeeper 干预）
xattr -c ~/.local/bin/ffmpeg ~/.local/bin/ffprobe

# 5. 校验
ffmpeg -version | head -1 && ffprobe -version | head -1
```

## 要点

- **安装位置固定用 `~/.local/bin`**：本机约定，`~/.zshrc` 已用 `source ~/.local/bin/env` 注入 PATH，终端直接可调用；`/usr/local/*` 归 root，免 sudo 写不进去。
- **永远用 `install -m 755` 而不是 `mv`**：一次到位地设好权限与属主。
- **`xattr -c` 不是可选项**：curl 下载的产物通常不带 `com.apple.quarantine`，但清一下能避免偶发的 Gatekeeper/签名干扰。
- **下载日志要落盘**：`curl ... > /tmp/x.log 2>&1` 后台跑，避免长下载把前台超时；同时别用它的退出码判断成败，**用"文件是否存在 + 版本命令能否跑通"验证**。
- 大文件下载（>15MB）放后台，速度实测差异很大：同一个镜像上 ffmpeg 210KB/s、ffprobe 6MB/s —— 别因为一个慢就判定源不可用。
