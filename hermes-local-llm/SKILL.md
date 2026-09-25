---
name: hermes-local-llm
description: 把本地 / 局域网上的 OpenAI 兼容大模型服务（LM Studio、Ollama、vLLM、llama.cpp）接入 Hermes Agent 或 Hermes One 桌面端。当任务是「Hermes 接本地模型」「Hermes One 用局域网大模型」「hermes config.yaml 配 provider / base_url」「Hermes 报 context window below the minimum 64,000」「Hermes 接 LM Studio / Ollama / vLLM」时使用。含 64K 上下文硬限制、免鉴权诊断接口、各家推理服务的 context 设置方法。
agent_created: true
---

# 把本地 / 局域网 LLM 接入 Hermes Agent

适用：Hermes Agent CLI 与 Hermes One（`fathah/hermes-desktop`）桌面端 —— **两者共用同一份 `~/.hermes/config.yaml`**。
但 **CLI 跑通 ≠ GUI 跑通**：GUI 另有两道与模型配置无关的独立关卡（连接模式必须 `local`、
`.env` 里必须有 `API_SERVER_KEY`），见下文专节。只验 CLI 就交付是最容易踩的坑。
实测环境：Mac mini M4 / macOS 26.6.2 / Hermes Agent v0.21.3 / Hermes One v0.7.7；远端 LM Studio on NVIDIA GB10。

## 先记住这 4 条硬事实

1. **配置只有一份：`~/.hermes/config.yaml`**，GUI 与 CLI 共用。GUI 改设置走的也是写这个文件 ——
   web API `POST /api/model/set` 的 docstring 原文：`Writes ~/.hermes/config.yaml — applies to new sessions only`。
2. **Hermes 硬性要求模型上下文 ≥ 64,000 tokens**，低于直接拒绝启动。这是最大的坑，见下面专节。
3. **LM Studio 能远程加载 / 卸载模型并指定 context** —— 但要用 **v1** 原生 API（`/api/v0` 才是只读的）：
   `POST /api/v1/models/load`、`POST /api/v1/models/unload`（见下面「远程加载模型」专节）。
   注意它对未知路径常返回 **HTTP 200** 加 `{"error":"..."}`，**要看 body 而不是状态码**。
   （早前版本的本文档误记成"LM Studio API 只读、无法远程加载"，已实测推翻。）
4. **GUI 的后端端口每次启动都变**，从 `~/.hermes/dashboard-stderr.log` 的**最后一行**读
   （该文件累积多行）。取错端口会看到 502 `upstream connect failed`，那不是"后端没起"。
   **另外 GUI 还有两道与模型配置无关的独立关卡**（连接模式 `local` + `API_SERVER_KEY`），
   见下面专节 —— **CLI 通了不代表 GUI 能通**。

## 最小可用配置

```yaml
model:
  default: "qwen3.8-27b"                     # 必须填！留空会回落到 gpt-4o-mini 之类根本不存在的模型
  provider: "custom"                         # 任意 OpenAI 兼容端点；ollama / vllm / llamacpp 都是 custom 的别名
  base_url: "http://192.168.0.101:1234/v1"   # LM Studio / Ollama / vLLM 都行
  # api_key: "..."                           # 服务端不校验时可省略
```

`model.default` 留空的典型症状（见 `~/.hermes/logs/agent.log`）：
`Vision auto-detect: using main provider custom (gpt-4o-mini)` —— 它去套一个你压根没有的模型名。

## 一次接入多个模型（Hermes One 模型库）

「把服务器上所有模型都接进来」时，要知道 Hermes 有**两条独立的数据通路**，别只配一条：

| 通路 | 文件 / 接口 | 谁在读 | 作用 |
|---|---|---|---|
| **上游 picker** | `GET /api/model/options`（JSON-RPC `model.options`） | GUI 切换时的**校验** | 从端点实时拉 `/v1/models`，`custom` provider 下**连 embedding 一起列** |
| **Hermes One 模型库** | **`~/.hermes/models.json`** | **聊天页的模型选择器** | 手写 / 同步的模型清单，GUI 文案：*"After adding models here, you can use them in the chat page model selector"* |

**关键结论：聊天页那个模型下拉框读的是 `~/.hermes/models.json`，不是 `model.options`。**
往端点接一批模型，最直接的做法就是往这个文件里加条目：

```json
{
  "id": "<uuid4>",
  "name": "Gemma 4 26B (ATOM)",
  "provider": "custom",
  "model": "gemma4-26b",
  "baseUrl": "http://192.168.0.101:1234/v1",
  "createdAt": 1789878901000
}
```

- 字段与 `main.js` 里的 `addModel()` 一致；重复判定是 `(model, provider, baseUrl)` 三元组，自己加时按同样规则去重。
- **`provider` 写 `custom`**，切换时前端会 `resolveDashboardProviderForModel()` 按 `baseUrl` 反查回 `custom`，最终发
  `/model <model> --provider custom`，`base_url` 沿用 config 里的，不会丢。
- **contextLength 不要写进这里**（老版本会写在 row 里，现已迁到 `~/.hermes/model-definitions.json`）。
  留空 = 让 Hermes 自动探测，比手填准。
- 该文件只在 `listModels()` 时被读，**加完要重启 Hermes One**（或触发一次模型库刷新）才可见。
- 自动同步只发生在 config 里有 **`providers:` 段**的 custom provider 时（`syncAgentConfigModels`）；
  配在 `model:` 段下的本地端点**不会**被自动带进模型库 —— 这正是"端点上明明有 4 个模型、
  GUI 里只认得 1 个"的原因。
- 种子数据：首次启动会 `seedDefaults()` 灌入 7 条云端预设（`createdAt` 全部相同即可辨认）。

**挑 provider：`custom` 还是 `lmstudio`？**

`probe_lmstudio_models(base_url=...)` 走 LM Studio 原生 `/api/v1/models`，**会自动过滤掉 embedding 模型**，
返回的是"能对话的模型 key"（无对话模型时返回合法空列表）。所以：

- 想要**干净的模型列表**（不含 embedding）→ 用 `provider: "lmstudio"`。
- 但 `lmstudio` 在 `_NO_AUTO_DETECT_PROVIDERS` 里，且默认 base_url 是 `127.0.0.1:1234` ——
  接局域网要额外给 `LM_BASE_URL`（auth.py 里 lmstudio 的 base_url 环境变量名），否则会连本机。
- 图省事、且模型库自己控制清单 → `provider: "custom"` + `baseUrl` 指局域网，最不容易冲突。

## 远程加载模型 / 修正 context（LM Studio 原生管理 API）

**`/api/v0` 只读，`/api/v1` 可写**：

```zsh
H=192.168.0.101
# 卸载（instance_id 就是模型 key）
curl -s -X POST "http://$H:1234/api/v1/models/unload" -H 'Content-Type: application/json' \
  -d '{"instance_id":"gemma4-26b"}'

# 加载并指定 context（echo_load_config 让响应回显最终配置，便于校验）
curl -s -X POST "http://$H:1234/api/v1/models/load" -H 'Content-Type: application/json' \
  -d '{"model":"gemma4-26b","context_length":131072,"echo_load_config":true}'
```

Hermes 自己也是这么干的 —— `hermes_cli/models_local.py::ensure_lmstudio_model_loaded(model, base_url, api_key, target_context_length)`：
**已加载的实例以现有 context 为准**（不会帮你重载），**冷加载时若不显式给 `target_context_length` 就不带 context_length**，
于是落回 LM Studio 的 JIT 默认值。

> ⚠️ **JIT 默认 context 很小（实测 8192）**，远低于 Hermes 的 64K 门槛 ——
> 直接让 LM Studio 自己 JIT 拉起来的模型，在 Hermes 里会直接被拒。
> 所以"接进来的模型"要挨个确认 `loaded_instances[].config.context_length ≥ 64000`，
> 不够的先 `unload` 再用上面的 `load` 指定 131072 重载。
> 一劳永逸的办法是在 LM Studio GUI 里把每个模型的默认加载 context 调大。

**两个 API 的口径不一致**：`/api/v0/models` 的 `state` 字段会滞后 / 失真（实测出现过
`v0 说 not-loaded、v1 的 loaded_instances 里明明躺着实例`）。**判断加载状态以 `/api/v1/models` 的
`loaded_instances` 为准**。

**加载失败拿不到原因**：LM Studio 只回 `{"error":{"type":"model_load_failed","message":"Failed to load ... Error: Failed to load model."}}`
（HTTP 500），**不说是 OOM 还是算子不支持**。实测 `arch: glm4moelite` 的 GLM-4.7 Flash 就是这么挂的 ——
模型文件大小正常（19 GB），但当前 LM Studio 运行时不认这个架构。**遇到就升级 LM Studio 的 runtime 或换模型**，
在 Hermes 侧怎么调都没用。



辅助任务是**独立于主模型**的调用（历史压缩、摘要、会话标题、图片理解），配置在 `auxiliary.<task>`，
默认 `provider: "auto"` = 继承主模型。但 auto 链会依次试 `openrouter → nous → local/custom → api-key`，
环境一变就可能落到不该落的地方，**建议和主模型一样显式钉住**：

```yaml
auxiliary:
  compression:
    provider: "custom"
    base_url: "http://192.168.0.101:1234/v1"
    model: "qwen3.8-27b"
    timeout: 600          # ← 关键：默认只有 120s
```

- **本地模型必须调大 `timeout`** —— 官方注释原话（`config_defaults.py`）：`Compression: raise timeout for local models.`
  8 tok/s 的本地模型压缩一段长历史，120s 经常不够，表现为长会话莫名失败。
- `_aux()` 标准形状：`{provider, model, base_url, api_key, timeout, extra_body, reasoning_effort}`；
  `api_key` 缺省会回落到 `OPENAI_API_KEY`。`base_url` 会覆盖 `provider`。
- 其余子键与默认超时：`vision`(120s，另有 `download_timeout`) / `title_generation` / `approval`(30s) /
  `skills_hub`(30s) / `mcp`(30s) / `review`(无 timeout 键，是子 agent) / `transient_retries`(2) / `free_only`(false)。
- **vision 要先确认模型真能看图**：LM Studio 的 `capabilities` 里得有视觉标记；
  只有 `["tool_use"]` 的纯文本模型，配了 vision 也是瞎猜。要图片能力就另接云端 provider。
- 辅助任务上下文另有 `auxiliary.<task>.context_length` 可覆盖（不走主模型的 64K 检查）。

## 最大坑：64K 上下文硬限制

```
Model <name> has a context window of 8,192 tokens, which is below the minimum 64,000
required by Hermes Agent.
```

- 常量：`agent/model_metadata.py` → `MINIMUM_CONTEXT_LENGTH = 64_000`（**硬编码，改不了**）
- 检查点：`agent/agent_init.py`（主模型）、`agent/conversation_loop.py`（运行时），辅助任务各有一份
- **模型的 `max_context_length` ≠ 服务端实际给的窗口**。LM Studio 里 qwen3.8-27b 支持 262144，
  但实际加载只给了 8192 → 照样被拒。
- **正解：在推理服务侧把 context 提到 ≥64K（推荐 131072）**，Hermes 侧绕不过去。

各家怎么设：

| 服务 | 设置方式 |
|---|---|
| LM Studio | GUI：模型加载参数里的 **Context Length**（或聊天窗口右上角）；CLI：`lms load <model> --context-length 131072` |
| Ollama | `OLLAMA_CONTEXT_LENGTH=131072` 环境变量，或 Modelfile 里 `PARAMETER num_ctx 131072` |
| vLLM | 启动参数 `--max-model-len 131072` |
| llama.cpp | 启动参数 `-c 131072` |

**逃生舱（不推荐）**：仅当 `provider: "lmstudio"` **且**显式设置了正整数 `model.context_length` 时，
`agent_init.py` 才允许低于 64K（变量名 `_allow_lmstudio_explicit_below_floor`）。
辅助任务另有 `auxiliary.<task>.context_length` 可覆盖。
但 8K 对 agent 太小 —— 光工具定义就吃掉大半，会频繁爆窗，只适合做"验证通路"，别真用。

**内存约束**：加 context 会显著增加 KV cache 占用（8K→128K 常多几十 GB）。
在统一内存机器（如 GB10）上要先腾内存，否则加载直接失败 —— **LM Studio 只报 `Failed to load model`，不给原因**。
ComfyUI 侧可释放：`curl -X POST http://<host>:8188/free -d '{"unload_models":true,"free_memory":true}'`。

## GUI 显示 Offline / 顶部横幅 "API Server Key not set" —— 聊天发不出去

**这是 Hermes One 桌面端的两道独立关卡，和 `model:` 段配得好不好无关。CLI 能跑 ≠ GUI 能跑。**

### ① 连接模式必须是 local（`~/.hermes/desktop.json`）

GUI 自带"连接注册表"，存在 **`~/.hermes/desktop.json`**（注意：不是 `~/Library/Application Support/` 下）：

```json
{"connectionRegistry":{"version":1,"activeConnectionId":"connection-…",
  "connections":[{"connectionId":"connection-…","name":"SSH","config":{"mode":"ssh",
    "ssh":{"host":"","username":"","remotePort":8642,"localPort":18642}}}]},
 "locale":"zh-CN"}
```

前端逻辑（asar 内 `getApiUrl`）：

```js
if (conn.mode === "ssh") {
  const u = getSshTunnelUrl();
  if (u) return normaliseRemoteUrl(u);
  throw new Error("SSH tunnel is not active");      // ← host 空就抛这个
}
return `http://127.0.0.1:${getProfilePort(resolveProfile(profile))}`;   // 只有 local 走这
```

`isRemoteMode = mode === "remote" || mode === "ssh"`。**`mode` 是 ssh 时 GUI 根本不启动本地后端**，
现象是 `~/.hermes/logs/gui.log` 永远不新增、端口无新监听、界面挂横幅且 `offline`。
→ 先退出 GUI，把 `config.mode` 改成 `"local"`（`name` 顺手改 `Local`），再启动。

### ② 必须设 `API_SERVER_KEY` + `API_SERVER_ENABLED`（写在 `~/.hermes/.env`）

这是 hermes 本地 **OpenAI 兼容 API server** 的 Bearer token，桌面端与本地 gateway 共享。
`config_defaults.py` 官方说明：*"Required whenever the API server is enabled;
**server refuses to start without it**."*

```ini
API_SERVER_ENABLED=true
API_SERVER_KEY=<≥16 字符随机串>
```

```zsh
python3 -c "import secrets;print(secrets.token_urlsafe(32))"   # 生成
```

校验规则（前端 `isUsableApiServerKey`）：非空、**≥16 字符**、非占位符
（`changeme|placeholder|your[-_]?key|api[-_]?server[-_]?key`）。
缺它时界面顶部出现横幅 **"API Server Key not set — chat will fail."**。
asar 内打包的开发文档还点明了机制：*"The gateway only loads the api_server platform when
`API_SERVER_ENABLED` is truthy, and the api_server refuses to bind without `API_SERVER_KEY`.
Local mode writes both via `startGateway`"*。

> 界面上的 "Generate key" 按钮干的就是写这两行；自己写效果一样（前后端读同一个 `.env`）。

## GUI 后端端口：每次启动都变，别记死

`~/.hermes/dashboard-stderr.log` **累积**多行，每行是某一次启动：

```
  Hermes Web UI → http://127.0.0.1:49689      ← 上一轮运行
  Hermes Web UI → http://127.0.0.1:52405      ← 本次（必须取最后一行）
```

curl 旧端口会得到 **502 `upstream connect failed`**，极易误判成"后端没启动"。
可靠确认端口：`netstat -an -p tcp | grep LISTEN`（本机 `lsof` 在沙箱下读不到）。
前端连对后端后，`gui.log` 会出现 `tui_gateway.ws: ws accepted`（WebSocket 已建立）。

## 诊断入口

```zsh
hermes doctor                                   # 配置 / 依赖 / 鉴权全量体检
hermes model --help                             # 交互式选择器（无可用的非交互参数，别指望脚本化）
```

只读 API（**免鉴权**，最适合脚本排查）：
```zsh
PORT=$(sed -n 's/.*127\.0\.0\.1:\([0-9]*\).*/\1/p' ~/.hermes/dashboard-stderr.log | head -1)
curl -s "http://127.0.0.1:$PORT/api/model/info"     # → {"model":..,"provider":..,"effective_context_length":..}
curl -s "http://127.0.0.1:$PORT/api/status"         # → version / config_version / active_sessions
```
`/api/model/options`、`/api/model/set` 等**需要 token**（401 Unauthorized）；
只有 `PUBLIC_API_PATHS`（`hermes_cli/dashboard_auth/public_paths.py`）里的路径免鉴权。

日志：`~/.hermes/logs/{gui,agent,errors}.log`（GUI 走 `hermes_cli.web_server` + `tui_gateway.ws` WebSocket）。

## 接线前先验三件事（curl 直打推理服务）

```zsh
H=192.168.0.101
curl -s "http://$H:1234/v1/models" | head          # ① 端点活着吗、有哪些模型

curl -s -X POST "http://$H:1234/v1/chat/completions" -H "Content-Type: application/json" \
  -d '{"model":"<m>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'   # ② 能出话吗、多快

# ③ agent 的硬需求：tool calling 必须可用
curl -s -X POST "http://$H:1234/v1/chat/completions" -H "Content-Type: application/json" \
  -d '{"model":"<m>","messages":[{"role":"user","content":"北京天气?"}],"max_tokens":300,
       "tools":[{"type":"function","function":{"name":"get_weather","description":"查天气",
       "parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}]}'
# 看 finish_reason 是否为 "tool_calls"
```

LM Studio 的原生接口能给出更成套的元数据：
```zsh
curl -s "http://$H:1234/api/v0/models"   # state / max_context_length / loaded_context_length / capabilities / arch / quant
```

## 坑位备忘

- **`streaming:` 段可能被写坏**：实测遇到过值是字符串 `true false`（非法）。正确结构是 dict ——
  `{enabled: false, transport: "auto", edit_interval: 0.8, buffer_threshold: 24, cursor: " ▉"}`（见 `hermes_cli/config_defaults.py`）。
  顶层 `streaming` 只管**消息网关**（Telegram/Discord 等）的流式，与 `display.streaming` 无关。
- **config 版本过旧**：`hermes doctor` 会报 `Config version outdated (v0 → v45)`；迁移用 `hermes migrate`（改前先备份）。
- **改配置前必备份**：`cp -p ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-$(date +%Y%m%d-%H%M%S)`。
- **配置改完要重启 GUI 或开新会话**：`/api/model/set` 注明只对 **new** sessions 生效。
- **`provider: "custom"` vs `"lmstudio"`**：GUI 自己写的是 `custom`，保持一致最不容易冲突；
  `lmstudio` 是内置一等公民（还带上面那个 context 逃生舱），但 GUI 设置页可能显示不一致。
- **reasoning 模型的 token 账**：qwen3.8-27b / deepseek-r1 这类会把 max_tokens 先烧在 thinking 上，
  小 max_tokens 下 `content` 会是空字符串 —— 不是坏了，是还没轮到输出正文。
  **探测能力时别用小 max_tokens**（12 都不够），否则会误判成"模型没输出"。正文在 `message.content`，
  思考过程在 `message.reasoning_content`。
- **v0 与 v1 的 capabilities 口径也不同**：同一个 qwen3.8-27b，`/api/v0/models` 报 `capabilities:["tool_use"]`，
  `/api/v1/models` 报 `{vision:True, trained_for_tool_use:True}`。**别拿 v0 的 capabilities 断定"这模型不能看图"**，
  要交叉核对 v1。判断加载状态同理，以 v1 的 `loaded_instances` 为准。
- **别用 `timeout` 命令**：macOS 默认没有，脚本里会 `command not found`。
