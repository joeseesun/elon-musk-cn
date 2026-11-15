#!/usr/bin/env python3
"""Umami 登记全自动链（在 ego lite 里执行，等用户登录后自动完成）：

1. 轮询 umami.qiaomu.ai 登录态（最长 90 分钟）
2. 检查是否已有 elon.qiaomu.ai 站点（GET /api/websites，处理分页）
3. 没有则创建（POST /api/websites，name=马斯克全访谈）
4. website ID 写入 tools/site_config.json → build → deploy
5. 线上验证 tracker 接线 + 产生 QA 页览 → 从 Umami API 读回验证
"""
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/Users/joe/Documents/ChatGPT/elon-website')
QA_MARK = 'qa=launch-20261115-elon'
TASK = 'umami-register-elon'
PAGE = 'p1'


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_js(code, timeout_ms=60000):
    """在 ego 浏览器的 umami 标签页上下文里执行 JS。

    页面 JS 以 base64 注入节点脚本，避免嵌套反引号/引号转义问题。
    """
    b64 = base64.b64encode(code.encode()).decode()
    script = (
        f'const task = await taskSpace("{TASK}");\n'
        f'const page = task.page("{PAGE}");\n'
        f'const code = Buffer.from("{b64}", "base64").toString();\n'
        'const out = await page.evaluate(code);\n'
        'console.log("RESULT_JSON:" + JSON.stringify(out));\n'
    )
    # 注意：ego-browser nodejs 的位置参数会被当作【代码】而非文件路径
    # （"/tmp/x.mjs" 会被解析成正则字面量），所以必须用 -e 传脚本。
    r = subprocess.run(['ego-browser', 'nodejs', '-e', script],
                       capture_output=True, text=True, timeout=timeout_ms // 1000 + 30)
    text = (r.stdout or '') + (r.stderr or '')
    for line in text.splitlines():
        if line.startswith('RESULT_JSON:'):
            return json.loads(line[len('RESULT_JSON:'):])
    return {'error': 'no result', 'raw': text[-400:]}


BASE = 'https://umami.qiaomu.ai'


def goto(path):
    run_js(f'location.assign("{BASE}{path}")')
    time.sleep(4)


def main():
    # 1. 等登录：以「umami 源内 fetch /api/websites 返回 200」为权威判据
    #    （不能只看有没有密码框：新标签页会误报）
    log('检查 umami 登录态 …')
    logged = False
    goto('/login')
    for i in range(180):
        r = run_js('''
(async () => {
  try {
    const res = await fetch('/api/websites?pageSize=1', {credentials: 'include'});
    return {status: res.status, url: location.href};
  } catch (e) {
    return {status: 0, url: location.href, err: String(e)};
  }
})()
''')
        status = r.get('status')
        if status == 200:
            logged = True
            log(f'已登录（API 200，{r.get("url")}）')
            break
        if i == 0:
            log('未登录，等待用户在 ego 浏览器登录（最长 90 分钟）…')
        if i % 6 == 0:
            log(f'仍未登录（{i * 30}s，status={status}，url={str(r.get("url"))[:60]}）')
        # 用户若把标签页导去别处，拉回登录页
        if '/login' not in str(r.get('url', '')) and not str(r.get('url', '')).startswith('https://umami.qiaomu.ai'):
            goto('/login')
        time.sleep(30)
    if not logged:
        log('超时：用户未登录，退出')
        return

    goto('/websites')

    # 2. 查已有站点
    r = run_js('''
(async () => {
  const out = [];
  for (let page = 1; page <= 10; page++) {
    const res = await fetch(`/api/websites?pageSize=100&page=${page}`);
    if (!res.ok) return {error: 'api ' + res.status};
    const data = await res.json();
    const items = data.data || data.websites || data || [];
    out.push(...items.map(w => ({id: w.id, name: w.name, domain: w.domain})));
    if (data.count != null && out.length >= data.count) break;
    if (items.length < 100) break;
  }
  return out;
})()
''')
    sites = r if isinstance(r, list) else []
    if not sites:
        log(f'站点查询失败：{json.dumps(r, ensure_ascii=False)[:200]}')
        return
    log(f'现有站点数：{len(sites)}')
    exist = next((s for s in sites if s.get('domain') == 'elon.qiaomu.ai'), None)
    if exist:
        wid = exist['id']
        log(f'已有 elon.qiaomu.ai 站点：{wid}')
    else:
        # 3. 创建
        r = run_js('''
(async () => {
  const res = await fetch('/api/websites', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: '马斯克全访谈', domain: 'elon.qiaomu.ai'})
  });
  const data = await res.json().catch(() => ({}));
  return {status: res.status, ok: res.ok, data};
})()
''')
        wid = ((r.get('data') or {}).get('id')) if isinstance(r, dict) else None
        log(f'创建结果：status={r.get("status")} id={wid}')
        if not wid:
            log('创建失败：' + json.dumps(r, ensure_ascii=False)[:300])
            return

    # 4. 写配置 → 构建 → 部署
    cfg_path = ROOT / 'tools' / 'site_config.json'
    cfg = json.load(open(cfg_path))
    if cfg.get('umami') != wid:
        cfg['umami'] = wid
        json.dump(cfg, open(cfg_path, 'w'), ensure_ascii=False, indent=2)
        log(f'site_config.json 已写入 umami={wid}')
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'build.py')], check=True, cwd=ROOT)
        subprocess.run([str(ROOT / 'tools' / 'deploy.sh')], check=True, cwd=ROOT)
        log('已构建并部署')
    else:
        log(f'配置已是 {wid}，跳过构建部署')

    # 5. 线上验证 tracker 接线
    import urllib.request
    html = urllib.request.urlopen('https://elon.qiaomu.ai/', timeout=30).read().decode()
    wired = f'data-website-id="{wid}"' in html
    log(f'线上 tracker 接线: {"OK" if wired else "MISSING"}')

    # QA 页览（真实浏览器访问生产域名）→ 读回事件
    run_js(f'window.open("https://elon.qiaomu.ai/?{QA_MARK}", "_blank")')
    time.sleep(15)
    for attempt in range(8):
        time.sleep(20)
        r = run_js(f'''
(async () => {{
  const start = Date.now() - 3600 * 1000;
  const res = await fetch(`/api/websites/{wid}/events?startAt=${{start}}&pageSize=50`);
  const data = await res.json().catch(() => null);
  return {{status: res.status, data}};
}})()
''')
        raw = json.dumps(r, ensure_ascii=False)
        if 'launch-20261115' in raw:
            log(f'✅ QA 页览已入库（读回成功，标记 {QA_MARK}）')
            log('全部完成：登记 → 部署 → 入库验证')
            return
        log(f'读回尝试 {attempt + 1}/8：未看到标记事件')
    log(f'⚠️ 事件读回未确认，请稍后在 umami.qiaomu.ai/websites/{wid}/realtime 人工复查')


if __name__ == '__main__':
    main()
