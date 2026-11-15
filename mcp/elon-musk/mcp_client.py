#!/usr/bin/env python3
"""stdio MCP 调试客户端：列出工具、调用工具。Skill 也可用它排查连接。

用法：
  python3 mcp_client.py list
  python3 mcp_client.py call search '{"query":"火星","limit":3}'
  python3 mcp_client.py call site_info '{}' 60

可通过 ELON_MCP_SERVER 指定 server 路径（默认同目录的 elon_mcp_server.py）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SERVER = os.environ.get("ELON_MCP_SERVER", str(Path(__file__).resolve().parent / "elon_mcp_server.py"))


class Client:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.n = 0
        self.pending: dict[int, list] = {}
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except Exception:
                continue
            with self.lock:
                ev = self.pending.get(msg.get("id"))
            if ev is not None:
                ev.append(msg)

    def rpc(self, method, params=None, timeout=120):
        self.n += 1
        rid = self.n
        ev = []
        with self.lock:
            self.pending[rid] = ev
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        t0 = time.time()
        while time.time() - t0 < timeout:
            if ev:
                with self.lock:
                    self.pending.pop(rid, None)
                return ev[0]
            time.sleep(0.03)
        with self.lock:
            self.pending.pop(rid, None)
        raise TimeoutError(f"{method} 超时 {timeout}s")

    def initialize(self):
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "elon-mcp-client", "version": "1.0"}}, timeout=60)
        self.rpc("notifications/initialized")
        return r

    def call(self, name, args, timeout=120):
        r = self.rpc("tools/call", {"name": name, "arguments": args}, timeout=timeout)
        result = r.get("result", r)
        if result.get("isError"):
            raise RuntimeError(result["content"][0]["text"])
        return json.loads(result["content"][0]["text"])

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    c = Client()
    try:
        init = c.initialize()
        info = init.get("result", {}).get("serverInfo", {})
        print(f"# connected {info.get('name')} {info.get('version')}", file=sys.stderr)
        if sys.argv[1] == "list":
            r = c.rpc("tools/list", {}, timeout=60)
            for t in r.get("result", {}).get("tools", []):
                print(f"## {t['name']}\n{t.get('description', '')}\n")
        elif sys.argv[1] == "call":
            name = sys.argv[2]
            args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
            timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 120
            out = c.call(name, args, timeout=timeout)
            print(json.dumps(out, ensure_ascii=False, indent=2)[:30000])
        else:
            print(__doc__)
            return 1
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
