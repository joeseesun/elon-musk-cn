#!/usr/bin/env python3
"""验证公开 MCP 端点：初始化、列出工具、调用 site_info。纯标准库。"""

import json
import os
import sys
import urllib.request

URL = os.environ.get("ELON_MCP_URL", "https://elon.qiaomu.ai/mcp").rstrip("/")


def rpc(method: str, params: dict, rid: int) -> dict:
    req = urllib.request.Request(
        URL,
        data=json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    try:
        init = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "elon-skill-check", "version": "1.0"}}, 1)
        info = init.get("result", {}).get("serverInfo", {})
        print(f"connected: {info.get('name')} {info.get('version')}")
        tools = rpc("tools/list", {}, 2).get("result", {}).get("tools", [])
        print(f"tools: {len(tools)} -> {', '.join(t['name'] for t in tools)}")
        call = rpc("tools/call", {"name": "site_info", "arguments": {}}, 3)
        text = call.get("result", {}).get("content", [{}])[0].get("text", "")
        data = json.loads(text) if text else {}
        print("data_source:", data.get("data_source"), "| videos:", data.get("counts", {}).get("videos"))
        return 0 if tools else 1
    except Exception as exc:
        print(f"FAILED: {exc!r}\nendpoint: {URL}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
