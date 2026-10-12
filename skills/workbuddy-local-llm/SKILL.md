---
name: workbuddy-local-llm
description: 把本机 / 局域网上的 OpenAI 兼容大模型服务（LM Studio、Ollama、vLLM、llama.cpp、Open WebUI）接入 WorkBuddy 桌面端，让 WorkBuddy 的模型下拉里能直接选这些本地模型。当任务是「WorkBuddy 接入本地大模型」「WorkBuddy 用 ATOM/群晖/局域网上的模型」「WorkBuddy 加自定义模型」「models.json 加模型」时使用。含 models.json 结构、id 字段的坑、tool call 前置校验、生效方式与兜底路径。
agent_created: true
---

# 把本地 / 局域网 LLM 接入 WorkBuddy

适用：WorkBuddy 桌面端（macOS / Windows 均同构）。
**接入点是 `~/.workbuddy/models.json`（模型清单），不是 `mcp.json`** —— MCP 是给 agent 加外部工具，
不是换底层模型。走错文件是本任务最常见的翻车点。

实测环境：Mac mini M4 / macOS 26.6.2 / WorkBuddy 5.6.x；远端 LM Studio on NVIDIA GB10（ATOM）。

---

## 0. 一句话判据

要接的是「**一个能当 LLM 用的 OpenAI 兼容端点**」→ 改 `models.json`。
要接的是「一个能当工具用的服务」→ 改 `~/.workbuddy/mcp.json`（另一个话题）。

---

## 1. 探测：先确认服务真的在、模型真的加载了

常用端口对照（局域网扫一遍即可定位）：

| 服务 | 默认端口 | OpenAI 兼容路径 |
|---|---|---|
| LM Studio | 1234 | `/v1/chat/completions` |
| Ollama | 11434 | `/v1/chat/completions` |
| vLLM / SGLang | 8000 | `/v1/chat/completions` |
| llama.cpp server | 8080 | `/v1/chat/completions` |
| Open WebUI | 3000 / 8080 | 需 key，见其 `/api` 文档 |
| ComfyUI | 8188 | ❌ 不是 LLM |

**LM Studio 有专用诊断接口，信息最全，优先用**：

```bash
curl -s http://<HOST>:1234/api/v0/models | python3 -m json.tool
```

关注四个字段：
- `state` —— 必须是 `loaded`。`not-loaded` / `unloaded` 时请求会 400。
- `capabilities` —— 必须含 `tool_use`，否则接进 WorkBuddy 后 **Agent 能力直接废掉**（只会聊天，不会调工具）。
- `type` —— `vlm` 说明支持图片输入，可映射 `supportsImages: true`。
- `loaded_context_length` —— 用它填 `maxInputTokens`。

---

## 2. 三项实测：别只看 capabilities 声明

`capabilities` 是声明，不一定真的好使。三项都跑通再写配置：

```bash
# 2.1 对话
curl -s http://<HOST>:1234/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"<MODEL_ID>","messages":[{"role":"user","content":"只回答两个字：收到"}],"max_tokens":32}'

# 2.2 流式（注意：别用 head 掐管道，会误判成"流式坏了"）
curl -s -N http://<HOST>:1234/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"<MODEL_ID>","messages":[{"role":"user","content":"数到3"}],"max_tokens":32,"stream":true}' \
  -o /tmp/s.txt; wc -c /tmp/s.txt

# 2.3 工具调用（关键）
curl -s http://<HOST>:1234/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model":"<MODEL_ID>","messages":[{"role":"user","content":"北京天气怎么样？用工具查。"}],
  "tools":[{"type":"function","function":{"name":"get_weather","description":"查天气",
    "parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],
  "max_tokens":256}'
```

2.3 合格标准：`finish_reason = "tool_calls"`，且 `tool_calls[0].function.arguments` 是合法 JSON。

---

## 3. 写入 models.json

`~/.workbuddy/models.json` 是**一个数组**，每项一个模型：

```json
{
  "id": "qwen3.8-27b",
  "name": "ATOM 本地 · Qwen3.8-27B",
  "vendor": "Custom",
  "url": "http://192.168.0.101:1234/v1",
  "apiKey": "lm-studio",
  "iconUrl": "",
  "supportsToolCall": true,
  "supportsImages": true,
  "supportsReasoning": true,
  "useCustomProtocol": false,
  "maxInputTokens": 131072,
  "maxOutputTokens": 32768,
  "tags": []
}
```

字段要点：
- **`id` 必须逐字等于服务端的 model id** —— WorkBuddy 直接把它当请求里的 `model` 参数发出去。
  自己起个花名（如 `atom-qwen`）会导致服务端 400 model not found。**显示名想自定义就改 `name`。**
- `url` 结尾带 `/v1`，不带 `/chat/completions`。
- `apiKey`：LM Studio / Ollama / llama.cpp 默认不校验，但字段不能空，随便填个非空串（如 `lm-studio`）。
- `vendor` 统一 `Custom`。
- 现有条目里 `supportsReasoning` 多为 `false`；若模型返回 `reasoning_content`（Qwen3 系、DeepSeek-R1 系），填 `true`。

写入前**必须备份**，改完**必须用 `json.load` 复验**：

```bash
cp ~/.workbuddy/models.json ~/.workbuddy/models.json.bak_pre_<topic>_$(date +%F)
```

写入时用 `newline="\n"` + `ensure_ascii=False` + `indent=2`，保持与程序写出的格式一致。

---

## 4. 生效方式与坑

- **需要重启 WorkBuddy 才读到新清单。**（`Cmd+Q` 完全退出再开，不能只关窗口。）
- ⚠️ **覆盖风险**：`models.json` 由主进程读写。理论上 app 退出时若用内存状态落盘，会冲掉手工条目。
  风险不高（实测该文件只在用户在 UI 里改模型时才写），但**先备份**，并且准备好兜底：
  若重启后下拉里看不到模型，直接走 UI 手动添加（参数照抄上面那张表），UI 加的一定持久。
- ⚠️ **LM Studio 默认只监听本机**。要被别的机器访问，须在 Developer / Local Server 面板里
  勾选 **Serve on Local Network**，否则 `nc` 探测直接失败。
- ⚠️ **ATOM 重启 / LM Studio 重启后模型回到未加载态**，需要重新 Load。模型不在 `loaded` 状态时，
  WorkBuddy 这边表现为请求报错，而不是下拉里消失。

---

## 5. 体检脚本

`atom-llm-check.sh`（本工作区可复用模板）一次性跑完：主机可达 → 端口开放 → 模型清单与状态 →
对话 + 工具调用实测。ATOM 侧任何变动后先跑它，比在 WorkBuddy 里试错快得多。

用法：`bash atom-llm-check.sh`，可用 `ATOM_HOST` / `ATOM_PORT` 环境变量覆盖默认值。
