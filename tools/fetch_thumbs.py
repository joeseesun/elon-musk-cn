#!/usr/bin/env python3
"""把 episodes.json 里所有封面图抓到本地 site/thumbs/。
- 小图: {yid}.jpg          <- mqdefault (320x180)
- 大图: {yid}@big.jpg      <- maxresdefault, 失败降级 hqdefault
- 第三方封面(po): 直接下载并按 slug 命名 {slug}.jpg / {slug}@big.jpg
纯标准库, 并发 + 重试。"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SITE = Path('/Users/joe/Documents/ChatGPT/elon-website/site')
DATA = SITE / 'data' / 'episodes.json'
THUMBS = SITE / 'thumbs'
THUMBS.mkdir(parents=True, exist_ok=True)

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36'

def fetch(url, dest, tries=3, timeout=20):
    if dest.exists() and dest.stat().st_size > 1000:
        return 'cached'
    last = ''
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 1000:
                last = f'too small ({len(data)}B)'
                time.sleep(0.5)
                continue
            dest.write_bytes(data)
            return f'ok {len(data)}B'
        except Exception as e:
            last = str(e)[:60]
            time.sleep(0.6 * (i + 1))
    return 'FAIL ' + last

def jpg_size(path):
    """纯标准库读取 JPEG 宽高, 用于识别 maxresdefault 是否真的存在。"""
    try:
        b = path.read_bytes()
    except Exception:
        return (0, 0)
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3):
            h = int.from_bytes(b[i+5:i+7], 'big'); w = int.from_bytes(b[i+7:i+9], 'big')
            return (w, h)
        if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        seg = int.from_bytes(b[i+2:i+4], 'big')
        i += 2 + seg
    return (0, 0)

def big_for_yid(yid):
    out = THUMBS / f'{yid}@big.jpg'
    # maxresdefault 缺失时 YouTube 返回 120x90 占位图, 检测到就降级 hqdefault
    r = fetch(f'https://i.ytimg.com/vi/{yid}/maxresdefault.jpg', out)
    if not r.startswith('FAIL'):
        w, h = jpg_size(out)
        if w >= 600:
            return 'big-maxres'
        out.unlink(missing_ok=True)
    return 'big-hq:' + fetch(f'https://i.ytimg.com/vi/{yid}/hqdefault.jpg', out)

def job(ep):
    res = []
    yid = ep.get('y')
    slug = ep['s']
    if yid:
        res.append('small:' + fetch(f'https://i.ytimg.com/vi/{yid}/mqdefault.jpg', THUMBS / f'{yid}.jpg'))
        res.append(big_for_yid(yid))
    po = ep.get('po')
    if po:
        res.append('po:' + fetch(po, THUMBS / f'{slug}.jpg'))
    return slug, res

def main():
    eps = json.load(open(DATA))['episodes']
    ok = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(job, ep): ep for ep in eps}
        for n, f in enumerate(as_completed(futs), 1):
            slug, res = f.result()
            if any(x.startswith('FAIL') for x in res):
                fail += 1
                print(f'[FAIL] {slug}: {res}', flush=True)
            else:
                ok += 1
            if n % 100 == 0:
                print(f'...{n}/{len(eps)}  {time.time()-t0:.0f}s', flush=True)
    print(f'DONE ok={ok} fail={fail} time={time.time()-t0:.0f}s', flush=True)
    # 统计
    files = list(THUMBS.glob('*.jpg'))
    total = sum(p.stat().st_size for p in files)
    print(f'FILES={len(files)} TOTAL={total/1024/1024:.1f}MB', flush=True)

if __name__ == '__main__':
    main()
