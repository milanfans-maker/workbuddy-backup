---
name: hypit-comfyui-provider
description: 把一个局域网 / 本机的 ComfyUI 实例接入 Hypit —— 写项目级 Provider 包，把 ComfyUI 的「节点图」协议映射到 Hypit 的生成模型语义上。当任务是「Hypit 接 ComfyUI」「Hypit 用本地模型生成视频/图片」「给 Hypit 写 provider」「把 ATOM/局域网 ComfyUI 接到 Hypit」「hypit build 走本地 GPU」时使用。含 MiniMax H3（t2v/fl2v/r2v）的完整可用参数。
agent_created: true
---

# Hypit × ComfyUI：项目级 Provider

Hypit 官方 distribution **没有** ComfyUI provider，必须自己写一个**项目级** Provider 包。
本文是 2026-09-21 在 ATOM（192.168.0.101:8188，ComfyUI 0.37.0 + MiniMax H3）上跑通后的完整记录。

## 0. 先确认三件事（不确认会白干）

```bash
# 1) ComfyUI 活着吗、什么版本、多少节点
curl -s http://<host>:8188/system_stats | head -c 400
# 2) 到底有没有你要的节点（不要靠猜）
curl -s http://<host>:8188/object_info | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d));print([k for k in d if 'MiniMax' in k][:20])"
# 3) 用户是不是已经跑过——history 里有现成的 API 格式节点图，是最可靠的模板
curl -s "http://<host>:8188/history?max_items=5" | python3 -c "import json,sys;d=json.load(sys.stdin);[print(k[:8], json.dumps(v.get('prompt',[None,None,{}])[2], ensure_ascii=False)[:300]) for k,v in d.items()]"
# 4) 用户存的工作流（前端格式，能看参数；但 API 格式要从 history 拿）
curl -s "http://<host>:8188/userdata?dir=workflows&recursive=true"
```

**最省力路径**：从 `/history` 里捞一条**成功**的 `prompt[2]`，那直接就是可提交的 API 节点图。

## 1. ComfyUI 协议 → Hypit 生命周期的映射

| Hypit | ComfyUI |
| --- | --- |
| `start` 上传素材 | `POST /upload/image`（multipart，字段名 **`image`**，附 `overwrite`/`type=input`/`subfolder`）→ 回 `{name, subfolder, type}` |
| `start` 提交 | `POST /prompt`，body `{"prompt": {节点id: {class_type, inputs}}, "client_id": "..."}` → 回 `{prompt_id}` |
| `poll` | `GET /history/{prompt_id}`；**没这个 key = 还在跑**；`status.completed === true` 才算成 |
| `collect` | `GET /view?filename=&subfolder=&type=` → 拿字节 → `context.resources.put` |
| 提前判错 | `POST /prompt` 的响应里若有 `node_errors` 非空，直接抛 |

`sleep` 式轮询不要自己写，用 `wakeAfter(handle, intervalMs, Date.now(), {phase})` 返回 `pending`，Runtime 负责调度。

## 2. Provider 包结构

```
<项目>/
  package.json                     # 要新建！含 "dependencies": {"@your/provider-x": "file:./packages/provider-x"}
  packages/provider-x/
    package.json                   # hypit.activation -> ./dist/activation.js ; exports "." -> ./dist/provider.js
    tsconfig.json                  # 照抄 examples/provider-package/packages/provider-videos/tsconfig.json
    src/provider.ts                # capability + mapping + start/poll/collect
    src/activation.ts              # createRuntimeEndpointAdapterFacet
    dist/                          # npm run build 产物
```

安装（**必须在项目根，且项目根要有 package.json**）：
```bash
cd packages/provider-x && npm install --registry=https://registry.npmmirror.com && npm run build
cd <项目根> && npm install --registry=https://registry.npmmirror.com   # 产出 node_modules/@your/provider-x (symlink)
```

Profile（`hypit paths` 看 Runtime Profile 在哪）加两段：
```json
"endpoints": {
  "comfyui.atom": {
    "use": "@your/provider-x",
    "config": { "baseUrl": "http://192.168.0.101:8188", "concurrency": 1, "pollIntervalMs": 5000 }
  }
},
"bindings": { "@hypit/minimax-h3@1#minimax-h3": "comfyui.atom" }
```

## 3. 无鉴权服务：不要造凭证

官方文档明确：**"An API works without a credential → Configure the Endpoint as its Provider declares; no auth command is needed"**。
局域网服务直接**省掉** `credentials` / `credentialInputs` / `apiKey`，`pricing` 写 `{ kind: "local" }`（plan 里会显示 `local, no Provider charge`）。

`defineEndpointPackage` 的 `credentials` 是**可选**字段，`activation.ts` 里用 `runtimeConfigExact(config, ["baseUrl","concurrency","pollIntervalMs"], ...)` 把允许的键写死。

## 4. 选哪个 capability

**不要自造 Model**。先看 Hypit 内置了哪些（`<distribution>/packages/` 下有一堆 model 包）：
`gpt-image` / `nano-banana` / `seedream` / `seedance` / `pixverse` / `wan` / `minimax-h3` / `grok-imagine` / `elevenlabs-speech` / `fishaudio-speech` / `mimo-speech` / `whisperx` …

拿**最权威的 mapping 参考**：`packages/provider-hypihub/src/mapping.ts`（它把每个内置 Model 的字段都映射了一遍）。

capability 的写法（注意 `name` 不是 endpoint key）：
```ts
// minimax-h3 的 endpoint key 是 "video"，但 capability name 是 "minimax-h3"
export const capability = { module: { name: "@hypit/minimax-h3", version: "1" }, name: "minimax-h3" } as const;
// binding key = `<module>@<version>#<capability name>`
```

## 5. 诚实声明支持范围（框架哲学，别妥协）

- 服务范围窄于模型 → `supports` 返回 `{status:"unsupported", reason:"..."}`，**不要**静默 clamp（`Do not silently clamp the author's number`）
- **不要**为了迁就某个服务去改 Model
- 端口没实现的（比如某参考类型）→ 明确拒绝并给出 reason
- `whenAbsent` 声明作者省略某端口时服务应收到什么

## 6. MiniMax H3 on ComfyUI（ATOM 实测可用参数）

**一个 `MiniMaxH3Director` 节点覆盖全部模式**，靠 `task_type` 切换。字符串必须**原样**（含 em dash）：

| 模式 | task_type | UNET | 4步 turbo LoRA |
| --- | --- | --- | --- |
| 文生视频 | `t2v — 文生视频(Text to Video)` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors` |
| 首尾帧 | `fl2v — 首尾帧生视频(First-Last Frame)` | 同上 | 同上 |
| 参考主体 | `r2v — 参考主体生视频(Reference to Video)` | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` |

共用：CLIP `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（type=`minimax`）、
video VAE `minimax_h3_video_vae_fp16.safetensors`、audio VAE `minimax_h3_audio_vae_fp32.safetensors`（**两个都要**）。
权重名**不要带 `vae/` `loras/` 等子目录前缀**（`/models/<cat>` 会重复列出，直接用扁平名）。

节点图骨架：
```
UNETLoader ─┐
            └→ LoraLoaderModelOnly ─┐
CLIPLoader ─────────────────────────┼→ MiniMaxH3Director ─→ CreateVideo ─→ SaveVideo
VAELoader(video) ───────────────────┤        (images→[0], audio→[1])
VAELoader(audio) ───────────────────┘
```

`MiniMaxH3Director` 的关键 inputs：
- `bd_grp_sample`:`"采样设置"`、`bd_grp_advanced`:`"高级采样 Advanced"`、`bd_grp_perf`:`"性能 Performance"` ← **分组标记字符串，值必须写成这样**
- `cfg`:1.0、`steps`:4（配 turbo LoRA）、`sampler`:`"res_multistep"`、`scheduler`:`"simple"`
- `shift_video`:12.0、`shift_audio`:3.0、`frame_rate`:24.0
- `width`/`height`：**32 对齐**；`total_frames` = 秒数 × 24
- **`timeline_data`：一个 JSON 字符串**（导演台的前端状态），含
  `{version:4, editMode:"global", timelineMode:"gen_blank", totalFrames, frameRate, width, height, refMaxSize,
    output:{...}, videoClips:[], video:{...},
    global:{taskType, prompt, refs:[], referenceVideo:{}, continuousReference:false, genImage:{imageFile:""}},
    segments:[{id:"s0",start:0,length,frameCount,durationSec,prompt:"",taskType:"",refs:[],...}],
    gen:{defaultFrameCount:124}, runSelectEnabled:false, runSelection:[]}`
- **r2v 的参考图**放 `global.refs = [{"index":0,"imageFile":"<上传后的文件名>","subfolder":""}]`，prompt 里用 **`<Picture 1>`** 引用

**性能**：864x480 / 96 帧（4 秒）/ 4 步 turbo → **约 80 秒**，输出 `h264 + aac`（H3 原生同时出音频）。
首次提交含模型加载，时间相近（权重会被 ComfyUI 缓存）。

**取输出**：`SaveVideo` 的结果在 history 里挂在 **`outputs.<node>.images`** 键下（**不是** `video`），元素是 `{filename, subfolder, type}`。

## 7. 常见坑

| 症状 | 原因 / 解法 |
| --- | --- |
| `node_errors` 非空 | 看响应体，通常是权重名带错子目录前缀，或分组标记字符串不匹配 |
| 提交成功但一直 pending | 检查 `GET /queue`；`/history` 里没 key 就是真在跑（大模型加载慢） |
| `resolution` 之类的标量不想直接下发 | mapping 里仍要声明（`assertMappingCoversPorts` 会校验端口覆盖），但 `start` 里可以**自己算** width/height 而不是用 wire 值 |
| `tsc` 报 `'x' is possibly 'null'` / `Property 'status' does not exist` | `noUncheckedIndexedAccess` 导致索引访问是 `unknown`；先 `const raw = obj[key]; if (raw === undefined) ...; const rec = object(raw);` |
| `exactOptionalPropertyTypes` 报错 | 可选属性不能赋 `undefined`，用条件展开 `...(v === undefined ? {} : { v })` |
| 每次运行输出文件混在一起 | `SaveVideo.filename_prefix` 里带 `context.operation`，poll 时再按 history 实际返回的文件名取，不靠猜 |

## 8. 验证顺序（每步都能单独确认，别跳）

```bash
# 1) 裸 ComfyUI 直提一次（绕开 Hypit，确认节点图本身对）
python3 verify.py            # POST /prompt + 轮询 /history + GET /view
# 2) Hypit 解析
hypit check <run>.svml
# 3) Hypit 就绪度（应显示 bound in the Profile + local, no Provider charge）
hypit plan <run>.svrun
# 4) 真跑
hypit build <run>.svrun --follow
```

最小 .svml（文生视频）：
```xml
<?svml using="@hypit/markup@1"?>
<svml>
  <import as="text" from="@hypit/text@1"/>
  <import as="h3" from="@hypit/minimax-h3@1"/>
  <text:Value id="shot">A red paper lantern swings in the rain at night. Audio: soft rain.</text:Value>
  <h3:TextVideo id="scene" prompt={shot} duration="4" resolution="768P" aspect-ratio="16:9"/>
</svml>
```
对应 .svrun：
```xml
<?svml using="@hypit/run-markup@1"?>
<svrun version="1">
  <author source="./x.svml"/>
  <target output="scene.video"/>
</svrun>
```
