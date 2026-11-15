#!/usr/bin/env python3
"""lcu cua_repl 驱动：单个 lcu 进程内执行一段 js，打印结果。

用法：python3 tools/lcu_js.py < js代码文件
"""
import json
import subprocess
import sys
import threading
import time

p = subprocess.Popen(['/Users/joe/.local/share/lcu/current/bin/lcu', '--chrome'],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, text=False)
out = []
done = threading.Event()


def rd():
    while True:
        b = p.stdout.read(1)
        if not b:
            break
        out.append(b)


threading.Thread(target=rd, daemon=True).start()
rid = 0


def rpc(method, params=None, wait=60):
    global rid
    rid += 1
    my = rid
    p.stdin.write((json.dumps({'jsonrpc': '2.0', 'id': my, 'method': method,
                               'params': params or {}}) + '\n').encode())
    p.stdin.flush()
    t0 = time.time()
    while time.time() - t0 < wait:
        data = b''.join(out)
        for line in data.split(b'\n'):
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get('id') == my:
                return msg
        time.sleep(0.1)
    return {'error': 'timeout'}


if __name__ == '__main__':
    r = rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                           'clientInfo': {'name': 'zc', 'version': '1'}}, wait=60)
    if 'result' not in r:
        print('INIT FAIL:', json.dumps(r)[:300])
        p.kill()
        sys.exit(1)
    rpc('notifications/initialized')
    code = sys.stdin.read()
    timeout = int(json.loads(sys.argv[1])) if len(sys.argv) > 1 else 120000
    r = rpc('tools/call', {'name': 'js', 'arguments': {'code': code, 'timeout_ms': timeout}},
            wait=timeout // 1000 + 30)
    result = r.get('result', r)
    # MCP tools/call 返回 content 数组
    if isinstance(result, dict) and 'content' in result:
        for c in result['content']:
            if c.get('type') == 'text':
                print(c['text'])
            else:
                print(json.dumps(c, ensure_ascii=False)[:2000])
        if result.get('isError'):
            print('[isError]', file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False)[:8000])
    p.kill()
