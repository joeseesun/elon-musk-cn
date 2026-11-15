"""文稿分段与全文检索索引（纯标准库）。

分段：把逐句字幕（YouTube 自动字幕每段只有几秒）合并成 20–40 秒左右的自然段，去掉 um/uh 口癖。
视频页「英文文稿」与 /search/ 共用同一套分段，搜索结果里的段号就是视频页里的段落锚点 #p{k}。

索引布局（site/data/search/）：
  meta.json         {v, n, eps: [[slug, 段落起始全局号, 日期, 中文标题, 英文标题, 类型, ytId], ...]}
  i/{000-255}.json  倒排分片：{词干: [全局段号的差分序列]}，分片号 = fnv1a(词干) % 256
  p/{k}.json        第 k 个视频的段落 [[秒|null, 文本], ...]，用于结果摘要与校验短语

分词、词干与停用词必须与 site/search.js 完全一致。
"""
import html
import json
import re
import shutil
import unicodedata

SHARDS = 256

STOP = set("""
a an the and or but if so of to in on at by for with from as into about than then that this these those there here
is are was were be been being am do does did done have has had having will would shall should can could may might must
i me my mine we us our ours you your yours he him his she her hers they them their theirs it its itself
what which who whom whose when where why how not no nor yes yeah yep okay ok oh um uh hmm well just like
very really also too only even still all any some such own same other each more most much many few
up down out off over under again further once very s t don isn didn doesn wasn aren weren won wouldn couldn
shouldn haven hasn hadn ll re ve d m o y let get got gonna gotta wanna going thing kind sort lot
""".split())

_TOK = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_FILLER = re.compile(r"(?<![\w'])(?:u+m+|u+h+|e+r+m+|uh-huh|mm-hmm)(?![\w'])[,.]?\s*", re.I)


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace('\u2019', "'")


def stem(w):
    if "'" in w:
        w = w.split("'", 1)[0]
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
        return w[:-1]
    return w


def index_terms(text):
    out = set()
    for raw in _TOK.findall(norm(text)):
        w = stem(raw)
        if w in STOP or raw in STOP:
            continue
        if len(w) < 2 and not w.isdigit():
            continue
        out.add(w)
    return out


def fnv1a(s):
    h = 0x811c9dc5
    for b in s.encode('ascii', 'ignore'):
        h ^= b
        h = (h * 0x01000193) & 0xffffffff
    return h


def clean(t):
    t = html.unescape(html.unescape(t or ''))
    t = _FILLER.sub('', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'\s+([,.?!])', r'\1', t)
    return t


def _split_long(t, limit=700):
    if len(t) <= limit:
        return [t]
    parts, cur = [], ''
    for s in re.split(r'(?<=[.?!])\s+', t):
        if cur and len(cur) + len(s) > limit:
            parts.append(cur)
            cur = s
        else:
            cur = f'{cur} {s}'.strip()
    if cur:
        parts.append(cur)
    return parts


def paragraphs(segs):
    """[[秒, 文本], ...] → [[整秒|None, 段落文本], ...]"""
    out, cur, n, start, last = [], [], 0, None, None

    def flush():
        nonlocal cur, n, start
        if cur:
            out.append([int(start) if start is not None else None, ' '.join(cur)])
        cur, n, start = [], 0, None

    for sec, txt in segs or []:
        t = clean(txt)
        if not t:
            continue
        # YouTube 字幕用 >> 标记换人说话：在这里另起一段
        if '>>' in t and sec is not None:
            head, *turns = [x.strip() for x in t.split('>>')]
            if head:
                if not cur:
                    start = sec
                cur.append(head)
                n += len(head) + 1
            for x in turns:
                flush()
                if x:
                    start, cur, n = sec, [x], len(x) + 1
            last = sec
            continue
        if sec is None:
            flush()
            for part in _split_long(t):
                out.append([None, part])
            continue
        if len(t) > 900:
            flush()
            for part in _split_long(t):
                out.append([int(sec), part])
            last = sec
            continue
        gap = sec - last if last is not None else 0
        if cur and (n >= 650 or (n >= 280 and (cur[-1][-1:] in '.?!' or gap > 4)) or (gap > 12 and n >= 60)):
            flush()
        if not cur:
            start = sec
        cur.append(t)
        n += len(t) + 1
        last = sec
    flush()
    # 换人说话常留下 "Yeah." "Right." 这类碎段，并进上一段，免得文稿被切得太碎
    merged = []
    for p in out:
        if merged and len(p[1]) < 25 and merged[-1][0] is not None and len(merged[-1][1]) < 900:
            merged[-1][1] += ' ' + p[1]
        else:
            merged.append(p)
    return merged


def build(out_dir, docs):
    """docs: [(slug, date, zh, en, kind, ytId, paras)]，paras 为 paragraphs() 的结果。返回统计信息。"""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / 'i').mkdir(parents=True)
    (out_dir / 'p').mkdir()
    postings = {}
    eps = []
    gid = 0
    for k, (slug, d, zh, en, kind, yt, paras) in enumerate(docs):
        eps.append([slug, gid, d or '', zh or '', en or '', kind or '', yt or ''])
        (out_dir / 'p' / f'{k}.json').write_text(json.dumps(paras, ensure_ascii=False, separators=(',', ':')))
        for _, text in paras:
            for w in index_terms(text):
                postings.setdefault(w, []).append(gid)
            gid += 1
    shards = [dict() for _ in range(SHARDS)]
    for w, gids in postings.items():
        prev, deltas = 0, []
        for g in gids:
            deltas.append(g - prev)
            prev = g
        shards[fnv1a(w) % SHARDS][w] = deltas
    sizes = []
    for i, sh in enumerate(shards):
        body = json.dumps(sh, separators=(',', ':'))
        (out_dir / 'i' / f'{i:03d}.json').write_text(body)
        sizes.append(len(body))
    from datetime import date
    (out_dir / 'meta.json').write_text(json.dumps({'v': date.today().isoformat(), 'n': gid, 'shards': SHARDS, 'eps': eps},
                                                  ensure_ascii=False, separators=(',', ':')))
    return {'docs': len(docs), 'paras': gid, 'terms': len(postings), 'shard_max': max(sizes), 'shard_total': sum(sizes)}


# ---------------------------------------------------------------- 中文精读检索
# 中文没有空格分词：按「相邻两字」建索引，英文词（产品名、人名）原样小写入索引；
# 查询时取词的全部二字组求交集，再在段落原文里做子串校验。
ZSHARDS = 256
_ZBLK = re.compile(r'<(p|h[2-4]|li|blockquote)\b([^>]*)>(.*?)</\1>', re.S)
_CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]+')
_ASC = re.compile(r'[a-z0-9]+')


def fnv1a_utf8(s):
    h = 0x811c9dc5
    for b in s.encode('utf-8'):
        h ^= b
        h = (h * 0x01000193) & 0xffffffff
    return h


def zh_blocks(html_src):
    """精读 HTML → (每个段落块加上 data-z 序号的 HTML, [段落纯文本])。两者按同一次遍历编号，保证搜索结果能定位回页面。"""
    texts = []

    def mark(m):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        if tag == 'blockquote' and re.search(r'<(p|li)\b', inner):
            inner = _ZBLK.sub(mark, inner)
            return f'<{tag}{attrs}>{inner}</{tag}>'
        t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', inner))).strip()
        if not t:
            return m.group(0)
        texts.append(t)
        return f'<{tag}{attrs} data-z="{len(texts) - 1}">{inner}</{tag}>'

    return _ZBLK.sub(mark, html_src or ''), texts


def zh_terms(text):
    t = norm(text)
    out = set()
    for run in _CJK.findall(t):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    for w in _ASC.findall(t):
        if len(w) > 1 or w.isdigit():
            out.add(w)
    return out


def build_zh(out_dir, docs):
    """docs: [(slug, date, zh, en, kind, ytId, texts)]，texts 为 zh_blocks() 的段落文本。写到 out_dir/z、zp、zmeta.json。"""
    for sub in ('z', 'zp'):
        if (out_dir / sub).exists():
            shutil.rmtree(out_dir / sub)
        (out_dir / sub).mkdir(parents=True)
    postings, eps, gid = {}, [], 0
    for k, (slug, d, zh, en, kind, yt, texts) in enumerate(docs):
        eps.append([slug, gid, d or '', zh or '', en or '', kind or '', yt or ''])
        (out_dir / 'zp' / f'{k}.json').write_text(json.dumps(texts, ensure_ascii=False, separators=(',', ':')))
        for t in texts:
            for w in zh_terms(t):
                postings.setdefault(w, []).append(gid)
            gid += 1
    shards = [dict() for _ in range(ZSHARDS)]
    for w, gids in postings.items():
        prev, deltas = 0, []
        for g in gids:
            deltas.append(g - prev)
            prev = g
        shards[fnv1a_utf8(w) % ZSHARDS][w] = deltas
    sizes = []
    for i, sh in enumerate(shards):
        body = json.dumps(sh, ensure_ascii=False, separators=(',', ':'))
        (out_dir / 'z' / f'{i:03d}.json').write_text(body)
        sizes.append(len(body.encode()))
    (out_dir / 'zmeta.json').write_text(json.dumps({'n': gid, 'shards': ZSHARDS, 'eps': eps},
                                                   ensure_ascii=False, separators=(',', ':')))
    return {'docs': len(docs), 'paras': gid, 'terms': len(postings), 'shard_max': max(sizes), 'shard_total': sum(sizes)}
