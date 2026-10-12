#!/usr/bin/env python3
"""微云 connector 本地调用封装。

凭证从环境变量 CODEBUDDY_MCP_CONFIG 读取，命令行不留明文 token。
走 WorkBuddy 本地代理端点 http://127.0.0.1:58845/<id>/mcp (JSON-RPC over HTTP)。
"""
import json
import os
import urllib.request

_CFG = json.loads(os.environ["CODEBUDDY_MCP_CONFIG"])
_WY = _CFG["mcpServers"]["tencent-weiyun"]
URL = _WY["url"]
HEADERS = dict(_WY["headers"])
HEADERS["Content-Type"] = "application/json"
HEADERS["Accept"] = "application/json, text/event-stream"

_rid = 0


def _parse(raw):
    """解析响应，兼容 application/json 与 text/event-stream 两种格式。"""
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    # SSE: 逐行取 data:
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise ValueError("无法解析响应: " + raw[:300])


def call(name, arguments, timeout=300):
    """调用一个微云 MCP tool，返回解析后的业务 dict。"""
    global _rid
    _rid += 1
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": _rid,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    res = _parse(raw)
    content = res.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except Exception:
                return {"_raw": item["text"]}
    return res


if __name__ == "__main__":
    print(json.dumps(call("weiyun.list", {"limit": 5, "get_type": 0}),
                     ensure_ascii=False, indent=2))
