---
name: hermes-comfyui-imagegen
description: 把局域网 ComfyUI 上的图像模型（qwen-image / Flux / Z-Image 等）接入 Hermes Agent 与 Hermes One，让 agent 能在对话里直接生图或改图。当任务是「Hermes 接 qwen-image」「Hermes One 生图」「把 ComfyUI 接入 Hermes」「Hermes 图像生成插件」「image_generate 工具不可用」「Hermes 接本地 diffusion 模型」时使用。含 image_gen 插件开发模板、ComfyUI REST 工作流、qwen-image 参数与 Lightning LoRA 加速、显存冲突排查。
agent_created: true
---

# 把 ComfyUI 图像模型接入 Hermes

适用：Hermes Agent CLI 与 Hermes One（GUI）—— 两者共用 `~/.hermes/config.yaml`。
实测环境：Mac mini M4 / macOS 26.6.2；远端 ATOM (NVIDIA GB10, 128GB 统一内存) 上的 ComfyUI 0.36.0 @ `192.168.0.101:8188`。

## 先记住这 5 条硬事实

1. **图像模型和聊天模型是两条完全独立的通路，别混**。

   | 通路 | 数据源 | 载体 | 谁能进 |
   |---|---|---|---|
   | 聊天 LLM | `~/.hermes/models.json` | 聊天页模型选择器 | 只认 LLM |
   | **图像生成** | **`image_gen` provider 插件** | **`image_generate` 工具** | diffusion 模型走这条 |

   qwen-image / Flux 这类 diffusion 模型**永远进不了模型选择器**。想让 agent 生图，只有 `image_gen` 这条路。

2. **provider 必须继承 `ImageGenProvider`**，否则注册被**静默忽略**，只留一行警告：
   `Plugin 'X' tried to register an image_gen provider that does not inherit from ImageGenProvider. Ignoring.`
   实现 `name`（唯一抽象方法）+ `generate()`；`list_models` / `default_model` / `is_available` /
   `capabilities` / `get_setup_schema` 都有基类默认值，按需覆盖。

3. **用户级插件放 `~/.hermes/plugins/<cat>/<name>/`，且必须在 `plugins.enabled` 里显式启用** ——
   bundled 插件是 `kind: backend` 自动加载，**user 插件不会**。漏了这步，插件列表里看得到却永远不生效。

4. **`image_gen.provider` 不配也能跑**（会自动选中唯一可用的 provider），但显式配上更稳 ——
   否则以后谁配了一个云端 key，选择权就被抢走了。

5. **ComfyUI 和 LM Studio 会抢显存**，这是最容易被忽略的副作用，见文末专节。

## 一、最小可用配置

```bash
# 1) 放插件（见下方模板）
mkdir -p ~/.hermes/plugins/image_gen/comfyui

# 2) 启用（--no-allow-tool-override 避免交互卡住）
hermes plugins enable "image_gen/comfyui" --no-allow-tool-override

# 3) 指定 provider 与地址
hermes config set image_gen.provider comfyui
hermes config set image_gen.comfyui.base_url "http://192.168.0.101:8188"
```

`hermes plugins enable` **带交互提示**（"Allow this plugin to replace built-in tools?"），
脚本里必须加 `--no-allow-tool-override`，否则会卡住并被子进程超时杀掉（退出码 137）。
图像插件不需要 tool override —— 它只注册 provider，不覆盖内置工具。

## 二、插件目录结构

```
~/.hermes/plugins/image_gen/comfyui/
├── plugin.yaml      # name / version / description / kind: backend
└── __init__.py      # 供应商实现 + register(ctx)
```

`plugin.yaml`：

```yaml
name: comfyui
version: 1.0.0
description: "ComfyUI (LAN) image generation backend — qwen-image text-to-image and editing."
author: ...
kind: backend
```

**不需要 `requires_env`** —— 本地服务无 key，这也是它比云端 provider 更省事的地方。

`__init__.py` 骨架：

```python
from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO, ImageGenProvider, error_response, resolve_aspect_ratio,
    save_b64_image, success_response)          # ← 继承必须，漏了就被静默忽略

class ComfyUIImageGenProvider(ImageGenProvider):
    provider_id = name = "comfyui"             # name 是唯一抽象方法，类属性实现即可
    label = display_name = "ComfyUI（局域网）"

    def is_available(self) -> bool:            # 探 /system_stats 判断可达性
        ...
    def list_models(self):
        return [{"id": ..., "display": ..., "speed": ..., "strengths": ..., "price": ...}]
    def capabilities(self):
        return {"modalities": ["text", "image"], "max_reference_images": 3}

    def generate(self, prompt, aspect_ratio=DEFAULT_ASPECT_RATIO, *,
                 image_url=None, reference_image_urls=None, **kwargs):
        # 有源图 → edit 工作流；否则 → 文生图
        return success_response(image=path, model=..., prompt=..., aspect_ratio=...,
                                provider="comfyui", modality="text", extra={...})

def register(ctx) -> None:
    ctx.register_image_gen_provider(ComfyUIImageGenProvider())
```

**写插件时别 import `plugins.image_gen._common`** —— 那是 repo 内的路径，用户级插件目录下解析不到。
只依赖 `agent.image_gen_provider` 的公共 API，HTTP 用 stdlib `urllib`，插件就能跨 Hermes 升级存活。

## 三、ComfyUI 侧要用的端点

| 端点 | 用途 |
|---|---|
| `GET /system_stats` | 存活探测 + 看显存（`devices[0].vram_free`） |
| `POST /prompt` | 提交工作流，返回 `prompt_id`；body `{"prompt": {...}, "client_id": "..."}` |
| `GET /history/<prompt_id>` | 轮询结果；完成后 `status.completed` / `status_str` |
| `GET /view?filename=&subfolder=&type=` | 下载输出图 |
| `POST /upload/image` | **multipart** 上传参考图（edit 用），返回服务端 filename |
| `GET /models/<folder>` | 列模型：`diffusion_models` / `text_encoders` / `vae` / `loras` |
| `GET /object_info` | 全节点参数定义（约 2MB），构造工作流前查参数名用这个 |
| `GET /queue` | 队列状态；`POST /free {"unload_models":true}` 可释放显存 |

轮询节奏：`POLL_INTERVAL = 2s`，作业超时给 600s（冷加载一个 20GB 模型就要 60s+）。
`/history` 的完成判定要同时看 `status.completed is True` **和** `status.status_str == "success"`。

## 四、qwen-image 工作流（实测参数）

ATOM 上可用的 qwen-image 权重（`diffusion_models/`）：

| 文件 | 用途 |
|---|---|
| `qwen_image_2512_fp8_e4m3fn.safetensors` | 文生图主力（2025-12 版） |
| `qwen_image_fp8_e4m3fn.safetensors` | 文生图初版 |
| `qwen_image_edit_2511_bf16.safetensors` | 指令改图（多参考图） |
| `qwen_image_edit_2509_fp8_e4m3fn.safetensors` | 上一代编辑版 |

配套固定件：
- text encoder：`qwen_2.5_vl_7b_fp8_scaled.safetensors`，`CLIPLoader` 的 **`type` 必须写 `qwen_image`**
- VAE：`qwen_image_vae.safetensors`

**文生图节点图**（API format）：

```
UNETLoader(qwen_image_2512) ─┐
                             ├→ ModelSamplingAuraFlow(shift=3.1) ─→ [LoraLoaderModelOnly] ─→ KSampler
CLIPLoader(qwen_2.5_vl_7b, qwen_image) ─→ CLIPTextEncode(+/-) ────────────────────────────────┘
VAELoader(qwen_image_vae) ─→ VAEDecode ←──────────────────────────────────────────────────────┘
EmptySD3LatentImage(1664x928) ─→ KSampler.latent_image
VAEDecode ─→ SaveImage
```

**关键参数**：

| 参数 | 值 | 说明 |
|---|---|---|
| `ModelSamplingAuraFlow.shift` | **3.1** | qwen-image 官方设定，不加画面会发灰 |
| 全精度（无 LoRA） | `steps=20, cfg=2.5, euler, simple` | 冷启约 **87s**（1024²） |
| **Lightning 4 步 LoRA** | `steps=4, cfg=1.0` | 同上约 **16s**，快 5 倍 |
| 尺寸 | landscape `1664x928` / square `1024x1024` / portrait `928x1664` | 原生分辨率桶，都是 16 的倍数 |

加速用 `LoraLoaderModelOnly`（只接 model，不接 clip），LoRA 文件：
`Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors`、
`Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors`。
**cfg 必须跟着降到 1.0** —— 沿用 2.5 配 4 步会糊。

**编辑（图生图）节点图**：与文生图的差别在于
- 用 `TextEncodeQwenImageEditPlus`（参数名是 **`prompt`** 不是 `text`，可带 `image1/2/3` 三个参考）
- latent 从 `VAEEncode(参考图)` 来，不是 `EmptySD3LatentImage`
- 参考图先 `LoadImage` → `ImageScaleToTotalPixels(megapixels=1.0, resolution_steps=64, lanczos)`

实测：换镜片颜色这类指令改图，4 步约 **50s**（含 bf16 模型冷加载）。

## 五、显存冲突（本方案最大的坑）

**GB10 是统一内存**：ComfyUI 和 LM Studio 共用同一池 128GB。

实测症状链：
1. 在 Hermes 里生图 → ComfyUI 加载 qwen-image（20–40GB，且**缓存不释放**）
2. LM Studio 的聊天模型被挤掉
3. 下次聊天触发 JIT 重载 → **用的是模型自带默认 context（8192）**，不是上次的 131072
4. Hermes 报 `context window of 8,192 tokens, which is below the minimum 64,000`
5. 表现为「昨天还能聊，今天 Hermes 就废了」—— 很容易误判成 Hermes 配置坏了

**排查**：

```bash
curl -s http://192.168.0.101:1234/api/v1/models | python3 -c "
import json,sys
for m in json.load(sys.stdin)['models']:
    if m.get('type')=='embedding': continue
    li=m.get('loaded_instances') or []
    print(m['key'], [i['config']['context_length'] for i in li] or '未加载')"
```

**即时修复**（与 `hermes-local-llm` skill 同一套办法）：

```python
# 先卸载低上下文实例，再用 Hermes 自己的加载通道重载
# POST /api/v1/models/unload {"instance_id": "<模型名>"}
from hermes_cli.models_local import ensure_lmstudio_model_loaded
ensure_lmstudio_model_loaded("qwen3.8-27b", "http://192.168.0.101:1234/v1",
                             None, 131072, timeout=900, return_load_result=True)
```

**治本**（按推荐顺序）：
- 在 LM Studio 的 Model Settings 里给每个模型设**默认加载 context ≥ 64K**（JIT 重载才会沿用）
- 或减少 ComfyUI 常驻缓存：生图后 `POST /free {"unload_models": true}`（代价是每次冷加载）
- 或把 Hermes 的 `model.provider` 从 `custom` 改成 `lmstudio`，由 Hermes 自己管加载上下文

## 六、验证顺序（别跳步）

```bash
# 1) 插件被识别（应看到 not enabled → enabled）
hermes plugins list --user --plain

# 2) 注册没被忽略（关键！只看 plugins list 看不出继承问题）
cd ~/.hermes/hermes-agent && ./venv/bin/python -c "
import sys,os; sys.path.insert(0,os.getcwd())
from hermes_cli.plugins import get_plugin_manager
get_plugin_manager().discover_and_load()
from agent.image_gen_registry import get_active_provider
p=get_active_provider(); print(type(p).__name__, p.name, p.is_available())"

# 3) 端到端（agent 真去调工具）
cd /tmp && hermes -z "用 image_generate 画一只橘猫坐在月亮上" -t image_gen
```

第 2 步是**不可省的**：插件没继承 `ImageGenProvider` 时，`hermes plugins list` 照样显示 enabled，
只有走到 registry 才会暴露 `Ignoring` 警告。

## 七、零碎坑

- **macOS 没有 `timeout` 命令** —— 脚本里别用，会 `command not found`。
- **`hermes -z` 可能被超长会话历史拖死**：报 `This conversation has grown too long for <model> to read`。
  加 `-t image_gen` 限定工具集、并换到 `/tmp` 之类干净目录再跑。
- **中文 prompt** 提交时用 `json.dumps(..., ensure_ascii=False).encode("utf-8")`，别用默认 ASCII 转义。
- **`LoadImage` 的 `image` 枚举只有 8 个**（ComfyUI 只列部分），但传自己上传的 filename 仍可用。
- 云端 provider 目录（`tools/image_generation_catalog.py`）里已有 `fal-ai/qwen-image`、`alibaba/qwen-image-3`
  等**付费云版本** —— 别和本地 ComfyUI 搞混，它们要 FAL key 且按张计费。
