#!/usr/bin/env python3
"""最小 stdio MCP 客户端：连接 lcu --chrome，列出工具或调用工具。

用法：
  python3 lcu_mcp.py list                  # 列出全部工具
  python3 lcu_mcp.py call TOOL '{"arg":1}' # 调用工具
"""
import json
import subprocess
import sys
import threading

LCU = '/Users/joe/.local/share/lcu/current/bin/lcu'


class Mcp:
    def __init__(self):
        self.proc = subprocess.Popen(
            [LCU, '--chrome'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.next_id = 0
        self.pending = {}
        self.lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if isinstance(msg, dict) and 'id' in msg:
                with self.lock:
                    ev = self.pending.pop(msg['id'], None)
                if ev:
                    ev.append(msg)

    def rpc(self, method, params=None, timeout=30):
        self.next_id += 1
        rid = self.next_id
        with self.lock:
            ev = self.pending[rid] = []
        self.proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params or {}}) + '\n')
        self.proc.stdin.flush()
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            if ev:
                return ev[0]
            time.sleep(0.05)
        return {'error': f'timeout after {timeout}s'}

    def initialize(self):
        r = self.rpc('initialize', {
            'protocolVersion': '2025-06-18',
            'capabilities': {},
            'clientInfo': {'name': 'zcode-cli', 'version': '1.0'},
        }, timeout=60)
        self.rpc('notifications/initialized')
        return r

    def list_tools(self):
        r = self.rpc('tools/list', {}, timeout=60)
        return r.get('result', {}).get('tools', [])

    def call(self, name, args, timeout=120):
        r = self.rpc('tools/call', {'name': name, 'arguments': args}, timeout=timeout)
        return r.get('result', r)


if __name__ == '__main__':
    m = Mcp()
    init = m.initialize()
    server = (init.get('result', {}).get('serverInfo') or {})
    print(f"connected: {server.get('name')} {server.get('version')}", file=sys.stderr)
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'list':
        for t in m.list_tools():
            print(f"## {t['name']}\n{t.get('description', '')[:200]}")
    elif cmd == 'call':
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        out = m.call(sys.argv[2], args, timeout=int(sys.argv[4]) if len(sys.argv) > 4 else 120)
        print(json.dumps(out, ensure_ascii=False)[:8000])
