"""给每个视频找 B 站搬运源：按英文标题、中文标题各搜一次，靠「简介里带 YouTube 链接」或「时长吻合 + 标题相近」认定。

输出 tools/bili.json：{slug: {bv, t, dur, play, up, how}}；请求缓存在 tools/.cache/bili/，可断点续跑。
用法：python3 tools/bili_match.py [--limit N] [--slug SLUG] [--refresh]
      python3 tools/bili_match.py --cands FILE   # 搜索接口被风控时：核对网页搜索引擎找到的候选 {slug: [BV…/av…]}
      python3 tools/bili_match.py --site SESSION # 用 agent-browser 打开站内搜索页（英文标题）找候选，再用详情接口核对
"""
import argparse
import hashlib
import html
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache' / 'bili'
OUT = ROOT / 'bili.json'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
STOP = set('elon musk the a an of and on in at to for with by from his is it its about full interview talk talks '
           'video live new part ep episode official clip vs x'.split())

CACHE_ONLY = False
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [('User-Agent', UA), ('Referer', 'https://search.bilibili.com/')]


MIXIN = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
         37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
WBI = {'key': ''}


def warm():
    """拿 buvid3/buvid4 和 wbi 签名密钥；不带这两样，搜索接口很快会 412 或返回 v_voucher。"""
    jar.clear()
    opener.open('https://www.bilibili.com/', timeout=15).read()
    spi = json.loads(opener.open('https://api.bilibili.com/x/frontend/finger/spi', timeout=15).read())['data']
    for name, val in (('buvid3', spi['b_3']), ('buvid4', spi['b_4'])):
        jar.set_cookie(http.cookiejar.Cookie(0, name, val, None, False, '.bilibili.com', True, True, '/', True, False,
                                             None, False, None, None, {}))
    img = json.loads(opener.open('https://api.bilibili.com/x/web-interface/nav', timeout=15).read())['data']['wbi_img']
    raw = ''.join(u.rsplit('/', 1)[1].split('.')[0] for u in (img['img_url'], img['sub_url']))
    WBI['key'] = ''.join(raw[i] for i in MIXIN)[:32]


def signed(params):
    p = dict(params, wts=int(time.time()))
    p = {k: re.sub(r"[!'()*]", '', str(v)) for k, v in sorted(p.items())}
    q = urllib.parse.urlencode(p, quote_via=urllib.parse.quote)
    return q + '&w_rid=' + hashlib.md5((q + WBI['key']).encode()).hexdigest()


def search(kw):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.md5(kw.encode()).hexdigest() + '.json')
    if f.exists():
        return json.loads(f.read_text())
    if CACHE_ONLY:
        return None
    for attempt in range(5):
        url = 'https://api.bilibili.com/x/web-interface/wbi/search/type?' + signed({'search_type': 'video', 'keyword': kw, 'page': 1})
        try:
            d = json.loads(opener.open(url, timeout=15).read())
        except Exception as e:
            # 412 = 风控，歇一会儿换新 cookie 再试
            print('  net error', e, '- backing off', file=sys.stderr)
            time.sleep(60 * (attempt + 1))
            warm()
            continue
        if d.get('code') == 0 and 'v_voucher' in (d.get('data') or {}):
            print('  v_voucher - backing off', file=sys.stderr)
            time.sleep(15 * (attempt + 1))
            warm()
            continue
        if d.get('code') == 0:
            res = [{'bv': v['bvid'], 't': html.unescape(re.sub(r'<[^>]+>', '', v['title'])), 'desc': html.unescape(v.get('description') or ''),
                    'dur': v.get('duration') or '', 'play': v.get('play') or 0, 'up': v.get('author') or '',
                    'pic': re.sub(r'^(https?:)?//', 'https://', v.get('pic') or '')}
                   for v in (d.get('data') or {}).get('result') or [] if v.get('type') == 'video']
            f.write_text(json.dumps(res, ensure_ascii=False))
            time.sleep(2.2)
            return res
        print('  api code', d.get('code'), d.get('message'), '- backing off', file=sys.stderr)
        time.sleep(60 * (attempt + 1))
        warm()
    return None


def secs(s):
    p = [int(x) for x in re.findall(r'\d+', s)]
    t = 0
    for x in p:
        t = t * 60 + x
    return t


def toks(s):
    return {w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP and len(w) > 1}


def bigrams(s):
    s = re.sub(r'[^\u4e00-\u9fff]', '', s.replace('马斯克', '').replace('埃隆', ''))
    return {s[i:i + 2] for i in range(len(s) - 1)}


_ZH_Q = {'一': '1', '二': '2', '三': '3', '四': '4'}


def _marks(s):
    """标题里能区分「同系列不同期」的数字：期号、年份、第几届、季度。"""
    s = s.lower()
    tagged = set(re.findall(r'(?:#|ep\.?|episode)\s*(\d+)', s))
    yrs = set(re.findall(r'(?<![\d#])((?:19|20)\d\d)(?!\d)', s)) - tagged
    eps = tagged | {n for n in re.findall(r'(?<![\d.])(\d{3,4})(?!\d)', s) if n not in yrs and n not in ('1080', '720', '2160', '480')}
    ords = set(re.findall(r'(\d+)(?:st|nd|rd|th)\b', s)) | set(re.findall(r'第\s*(\d+)\s*届', s))
    qs = set(re.findall(r'\bq([1-4])\b', s)) | {_ZH_Q[x] for x in re.findall(r'第([一二三四])季度', s)}
    return yrs, eps, ords, qs


def conflict(m, title):
    """候选标题和本站视频在期号 / 年份 / 届数 / 季度上对不上（如 JRE #2054 vs #1169），就不是同一场。"""
    ours = (m['title'] or '') + ' ' + (m.get('zh') or '')
    oy, oe, oo, oq = _marks(ours)
    cy, ce, co, cq = _marks(title)
    year = (m.get('d') or '')[:4]
    if year.isdigit():
        oy = oy | {str(int(year) + k) for k in (-1, 0, 1)}
    return bool((ce and oe and not ce & oe) or (cy and oy and not cy & oy)
                or (co and oo and not co & oo) or (cq and oq and not cq & oq))


def score(m, c):
    blob = c['t'] + ' ' + c['desc']
    yt = m.get('ytId')
    id_hit = bool(yt) and yt in blob
    d = secs(c['dur'])
    sec = m.get('sec') or 0
    dd = abs(d - sec) if sec else 0
    dur_ok = bool(sec) and dd <= max(20, sec * 0.03)
    dur_near = bool(sec) and dd <= max(60, sec * 0.10)
    et = toks(m['title'])
    sim_en = len(et & toks(blob)) / len(et) if et else 0
    zb = bigrams(m.get('zh') or '')
    sim_zh = len(zb & bigrams(c['t'])) / len(zb) if zb else 0
    sim = max(sim_en, sim_zh)
    if id_hit and (dur_near or not sec):
        how = 'id'
    elif conflict(m, c['t']):
        return None
    elif dur_ok and sec >= 120 and sim >= 0.35:
        how = 'dur+title'
    elif dur_ok and sim >= 0.6:
        how = 'dur+title'
    else:
        return None
    # 观众是中文读者：同样可信时优先带中文字幕的搬运
    sub = bool(re.search(r'中英|中字|字幕|双语|熟肉|翻译|译制|中文', c['t']))
    cjk = bool(re.search(r'[\u4e00-\u9fff]', c['t']))
    return {'how': how, 'key': (how == 'id', sub, cjk, dur_ok, c['play']), 'bv': c['bv'], 't': c['t'], 'dur': d,
            'play': c['play'], 'up': c['up'], 'sub': sub, 'pic': c.get('pic') or ''}


def clean_title(t):
    t = re.sub(r'[\[\(（【][^\]\)）】]*[\]\)）】]', ' ', t)
    t = re.sub(r'[^\w\s#\'.-]', ' ', t)
    return ' '.join(t.split())[:70]


def fetch_via_browser(session, kws, batch=12, gap=1500):
    """用真实浏览器（agent-browser 会话，已打开 search.bilibili.com）批量请求 wbi 搜索接口，写入缓存。
    直接用 urllib 请求很快会被 412 / v_voucher 风控，浏览器带完整 cookie 稳定得多。"""
    import base64
    import os
    import subprocess
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = [k for k in dict.fromkeys(kws) if k and not (CACHE / (hashlib.md5(k.encode()).hexdigest() + '.json')).exists()]
    print(f'browser fetch: {len(todo)} keywords', flush=True)
    env = {k: v for k, v in os.environ.items() if k != 'AGENT_BROWSER_CDP'}

    def open_page():
        subprocess.run(['agent-browser', '--session', session, 'open', 'https://search.bilibili.com/all?keyword=elon%20musk'],
                       capture_output=True, env=env, timeout=120)
        time.sleep(3)
    open_page()
    fails = 0
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        js = ('(async () => { const out = {}; for (const k of %s) {'
              ' try { const r = await fetch("https://api.bilibili.com/x/web-interface/wbi/search/type?search_type=video&keyword=" + encodeURIComponent(k), {credentials: "include"});'
              ' out[k] = await r.json(); } catch (e) { out[k] = {code: -1}; }'
              ' await new Promise((s) => setTimeout(s, %d)); } return JSON.stringify(out); })()') % (json.dumps(part, ensure_ascii=False), gap)
        b64 = base64.b64encode(js.encode()).decode()
        p = subprocess.run(['agent-browser', '--session', session, 'eval', '-b', b64], capture_output=True, text=True, env=env, timeout=600)
        try:
            raw = json.loads(json.loads(p.stdout.strip()))
        except Exception:
            print('  eval failed', p.stdout[:200], p.stderr[:200], flush=True)
            time.sleep(60)
            open_page()
            continue
        bad = 0
        for k, d in raw.items():
            data = d.get('data') or {}
            if d.get('code') != 0 or 'v_voucher' in data or 'result' not in data:
                bad += 1
                continue
            res = [{'bv': v['bvid'], 't': html.unescape(re.sub(r'<[^>]+>', '', v['title'])), 'desc': html.unescape(v.get('description') or ''),
                    'dur': v.get('duration') or '', 'play': v.get('play') or 0, 'up': v.get('author') or '',
                    'pic': re.sub(r'^(https?:)?//', 'https://', v.get('pic') or '')}
                   for v in data.get('result') or [] if v.get('type') == 'video']
            (CACHE / (hashlib.md5(k.encode()).hexdigest() + '.json')).write_text(json.dumps(res, ensure_ascii=False))
        print(f'  {min(i + batch, len(todo))}/{len(todo)}  bad={bad}', flush=True)
        if bad:
            fails += 1
            time.sleep(min(600, 60 * fails))
            open_page()
        else:
            fails = 0

def view(vid):
    """视频详情接口（不走搜索风控）：返回每个分 P 一条候选。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f'view-{vid}.json'
    if f.exists():
        d = json.loads(f.read_text())
    else:
        q = f'aid={vid[2:]}' if vid.startswith('av') else f'bvid={vid}'
        try:
            d = json.loads(opener.open('https://api.bilibili.com/x/web-interface/view?' + q, timeout=15).read())
        except Exception as e:
            print('  view error', vid, e, file=sys.stderr)
            return []
        if d.get('code') not in (0, -404, 62002, 62004):
            print('  view code', vid, d.get('code'), file=sys.stderr)
            return []
        f.write_text(json.dumps(d, ensure_ascii=False))
        time.sleep(0.4)
    v = d.get('data') or {}
    if not v.get('bvid'):
        return []
    pages = v.get('pages') or [{'page': 1, 'duration': v.get('duration') or 0, 'part': ''}]
    base = {'bv': v['bvid'], 'desc': v.get('desc') or '', 'play': (v.get('stat') or {}).get('view') or 0,
            'up': (v.get('owner') or {}).get('name') or '', 'pic': re.sub(r'^http:', 'https:', v.get('pic') or '')}
    return [dict(base, t=v.get('title') or '' if len(pages) == 1 else f"{v.get('title') or ''} {p.get('part') or ''}",
                 dur=str(p.get('duration') or 0), p=p.get('page') or 1) for p in pages[:30]]


def site_search(session, kw):
    """在真实浏览器里打开 B 站站内搜索页读结果卡片；比直接请求接口稳得多。返回 None 表示被拦或出错。"""
    import os
    import subprocess
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / ('site-' + hashlib.md5(kw.encode()).hexdigest() + '.json')
    if f.exists():
        return json.loads(f.read_text())
    env = {k: v for k, v in os.environ.items() if k != 'AGENT_BROWSER_CDP'}
    ab = lambda *a: subprocess.run(['agent-browser', '--session', session, *a], capture_output=True, text=True, env=env, timeout=120)
    ab('open', 'https://search.bilibili.com/video?keyword=' + urllib.parse.quote(kw))
    js = ('JSON.stringify({n: document.querySelectorAll(".bili-video-card").length,'
          ' empty: !!document.querySelector(".search-nodata-container, .no-data"),'
          ' cards: [...document.querySelectorAll(".bili-video-card")].slice(0, 20).map(c => ({'
          ' u: (c.querySelector("a[href*=\'/video/\']") || {}).href || "",'
          ' t: ((c.querySelector(".bili-video-card__info--tit") || {}).textContent || "").trim(),'
          ' d: ((c.querySelector(".bili-video-card__stats__duration") || {}).textContent || "").trim()}))})')
    for _ in range(6):
        time.sleep(1.2)
        p = ab('eval', js)
        try:
            d = json.loads(json.loads(p.stdout.strip()))
        except Exception:
            continue
        if d['n'] or d['empty']:
            res = [{'bv': m.group(1), 't': c['t'], 'dur': c['d']} for c in d['cards']
                   for m in [re.search(r'/video/(BV[0-9A-Za-z]{10})', c['u'])] if m]
            f.write_text(json.dumps(res, ensure_ascii=False))
            return res
    return None


def site_cands(session, limit=0):
    """站内搜索英文标题，按时长粗筛（±10%）出候选，交给 match_cands 用详情接口细核。"""
    master = json.load(open(ROOT / 'elon-master.json'))
    have = json.loads(OUT.read_text()) if OUT.exists() else {}
    cands, n, misses = {}, 0, 0
    for m in master:
        sec = m.get('sec') or 0
        if m['slug'] in have or sec < 240:
            continue
        res = site_search(session, clean_title(m['title']))
        if res is None:
            misses += 1
            print(f"! {m['slug'][:60]} (搜索页没出结果，稍后重跑)", flush=True)
            time.sleep(min(300, 30 * misses))
            continue
        misses = 0
        ok = [c['bv'] for c in res if abs(secs(c['dur']) - sec) <= max(60, sec * 0.10)]
        if ok:
            cands[m['slug']] = ok[:6]
        n += 1
        if n % 20 == 0:
            print(f'  searched {n}, with candidates {len(cands)}', flush=True)
        if limit and n >= limit:
            break
    return cands


def match_cands(path):
    """用网页搜索引擎找到的候选（{slug: [BV.../av...]}）逐个核对时长与简介，合并进 bili.json。"""
    master = {m['slug']: m for m in json.load(open(ROOT / 'elon-master.json'))}
    trans = json.load(open(ROOT / 'translations.json'))
    cands = path if isinstance(path, dict) else json.loads(Path(path).read_text())
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    for slug, ids in cands.items():
        if slug in out or slug not in master or not ids:
            continue
        m = dict(master[slug], zh=(trans.get(slug) or {}).get('zh') or '')
        best = None
        for vid in ids:
            for c in view(vid):
                s = score(m, c)
                if s and (best is None or s['key'] > best['key']):
                    best = dict(s, p=c['p'])
        if best:
            best.pop('key')
            if best.get('p') == 1:
                best.pop('p')
            out[slug] = best
            print(f"+ {slug[:60]:60} {best['how']:9} {best['bv']} p{best.get('p', 1)} {best['t'][:40]}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True))
    print(f'matched {len(out)} / {len(master)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cands', metavar='FILE', help='核对网页搜索得到的候选 BV 号')
    ap.add_argument('--site', metavar='SESSION', help='用 agent-browser 会话打开 B 站站内搜索页（英文标题）找候选')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--slug')
    ap.add_argument('--refresh', action='store_true', help='重新判定已匹配过的视频')
    ap.add_argument('--browser', metavar='SESSION', help='先用 agent-browser 会话批量抓取搜索结果进缓存')
    a = ap.parse_args()
    if a.site:
        cands = site_cands(a.site, a.limit)
        opener.open('https://www.bilibili.com/', timeout=15).read()
        return match_cands(cands)
    if a.cands:
        opener.open('https://www.bilibili.com/', timeout=15).read()
        return match_cands(a.cands)
    master = json.load(open(ROOT / 'elon-master.json'))
    trans = json.load(open(ROOT / 'translations.json'))
    if a.browser:
        kws = []
        for m in master:
            kws += [clean_title(m['title']), (trans.get(m['slug']) or {}).get('zh') or '']
        fetch_via_browser(a.browser, kws)
        a.refresh = True
        global CACHE_ONLY
        CACHE_ONLY = True
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    done = set(json.loads((CACHE / 'done.json').read_text())) if (CACHE / 'done.json').exists() else set()
    if not CACHE_ONLY:
        warm()
    n = 0
    for m in master:
        if a.slug and m['slug'] != a.slug:
            continue
        if m['slug'] in done and not a.refresh and not a.slug:
            continue
        m = dict(m, zh=(trans.get(m['slug']) or {}).get('zh') or '')
        best, failed = None, False
        for kw in (clean_title(m['title']), m['zh']):
            if not kw:
                continue
            res = search(kw)
            if res is None:
                failed = True
                break
            for c in res:
                s = score(m, c)
                if s and (best is None or s['key'] > best['key']):
                    best = s
            if best and best['how'] == 'id':
                break
        if failed:
            print(f"! {m['slug'][:60]} (搜索失败，下次重跑)")
            continue
        if best:
            best.pop('key')
            out[m['slug']] = best
            print(f"+ {m['slug'][:60]:60} {best['how']:9} {best['bv']} {best['t'][:40]}")
        else:
            out.pop(m['slug'], None)
            print(f"- {m['slug'][:60]}")
        done.add(m['slug'])
        n += 1
        if n % 10 == 0:
            OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True))
            (CACHE / 'done.json').write_text(json.dumps(sorted(done)))
        if a.limit and n >= a.limit:
            break
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True))
    (CACHE / 'done.json').write_text(json.dumps(sorted(done)))
    print(f'matched {len(out)} / {len(master)}')


if __name__ == '__main__':
    main()
