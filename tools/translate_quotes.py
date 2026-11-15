#!/usr/bin/env python3
"""金句中英双语：

1. 视频页「金句」：从 data/extra.json quotes.q 的现场发言里，由 LLM 每个视频挑出至多 10 句
   可独立成立的原话（必须是原文的逐字片段，脚本会校验），并给出中文译文；
2. 语录页：556 条 sayings 逐条翻译。

输出 data/quotes-zh.json：
  {"ep": {slug: [{"g": 全局段号, "t": 秒, "en": 原文片段, "zh": 译文}]},
   "sayings": {id: 译文}}

断点续跑：已完成的 slug / id 跳过。网关与 translate_titles.py 相同（Magpie，钥匙串 qiaomu-llm/magpie）。
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translate_titles import chat, extract_json  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXTRA = ROOT / 'data' / 'extra.json'
OUT = ROOT / 'data' / 'quotes-zh.json'
WORKERS = 3
MAX_PER_EP = 10
MAX_INPUT_CHARS = 60_000

NAMES = ('人名用通行中文译名（Joe Rogan=乔·罗根、Lex Fridman=莱克斯·弗里德曼、Jeff Bezos=贝索斯、'
         'Sam Altman=奥特曼、Donald Trump=特朗普），公司与产品名保留英文（Tesla、SpaceX、Starship、FSD、'
         'Optimus、Neuralink、X、Grok、Model 3、Cybertruck、Falcon 9、Dragon、Starlink、xAI）。')

SYS_EP = ('你是严谨的中文科技编辑。给你一场马斯克现场发言的若干段英文原话（每段有编号），请挑出最值得引用的金句。\n'
          '金句标准：脱离上下文也能读懂；有观点、判断、方法、数字或预言；表达有力。排除寒暄、致谢、主持流程、'
          '指代不明（this/that/it 指向前文）的句子。\n'
          '硬性要求：\n'
          f'1. 至多 {MAX_PER_EP} 句，宁缺毋滥；同一段至多选 1 句。\n'
          '2. en 必须从该段原文中逐字复制连续的 1–3 句，不得改写、拼接、增删任何词或标点，长度不超过 300 个字符。\n'
          '3. zh 是 en 的忠实中文译文，口语自然，不添加原文没有的信息。' + NAMES + '\n'
          '4. 只输出 JSON 数组：[{"i": 段编号, "en": "原文", "zh": "译文"}]，按段编号升序，不要解释。')

SYS_SAY = ('你是严谨的中文科技编辑。把下面每条马斯克的话（访谈原话或 X 帖子）翻译成简体中文。'
           '忠实原意，口语自然，保留语气和幽默，不添加解释；链接、@用户名、表情原样保留。' + NAMES +
           '只输出 JSON：{"编号": "译文"}，不要解释。')

lock = threading.Lock()


def load_out():
    if OUT.exists():
        return json.load(open(OUT))
    return {'ep': {}, 'sayings': {}}


def save(out):
    tmp = OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    tmp.replace(OUT)


def squash(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def episodes():
    extra = json.load(open(EXTRA))
    master = json.load(open(ROOT / 'tools' / 'elon-master.json'))
    by_src = {m['srcId']: m['slug'] for m in master}
    qv, qq = extra['quotes']['v'], extra['quotes']['q']
    eps = {}
    for vi, vid in enumerate(qv):
        slug = by_src.get(vid.replace('yt-', ''))
        if not slug:
            continue
        segs = [(g, q) for g, q in enumerate(qq) if q[0] == vi and len(q[2]) >= 60]
        if segs:
            eps[slug] = segs
    return eps, extra['sayings']


def do_ep(slug, segs, out):
    listing, used = [], 0
    for k, (g, q) in enumerate(segs):
        t = squash(q[2])
        if used + len(t) > MAX_INPUT_CHARS:
            break
        listing.append(f'[{k}] {t}')
        used += len(t)
    picked = []
    for attempt in range(2):
        msgs = [{'role': 'system', 'content': SYS_EP}, {'role': 'user', 'content': '\n\n'.join(listing)}]
        try:
            res = extract_json(chat(msgs, max_tokens=6000))
        except Exception as e:  # noqa: BLE001
            print(f'  {slug}: parse error {str(e)[:80]}', flush=True)
            continue
        picked, bad = [], 0
        seen = set()
        for x in res if isinstance(res, list) else []:
            try:
                k = int(x['i'])
                en, zh = squash(x['en']), squash(x['zh'])
            except (KeyError, TypeError, ValueError):
                bad += 1
                continue
            if not (0 <= k < len(segs)) or k in seen or not en or not zh or len(en) > 400:
                bad += 1
                continue
            g, q = segs[k]
            if en not in squash(q[2]):
                bad += 1
                continue
            seen.add(k)
            picked.append({'g': g, 't': q[1], 'en': en, 'zh': zh})
        if picked and bad <= max(1, len(picked) // 3):
            break
        print(f'  {slug}: attempt {attempt + 1} kept {len(picked)}, rejected {bad}', flush=True)
    picked.sort(key=lambda p: p['g'])
    with lock:
        out['ep'][slug] = picked[:MAX_PER_EP]
        save(out)
    return slug, len(picked)


def do_sayings(batch, out):
    listing = '\n'.join(f'{s["id"]}\t{squash(s["t"])}' for s in batch)
    res = extract_json(chat([{'role': 'system', 'content': SYS_SAY}, {'role': 'user', 'content': listing}],
                            max_tokens=12000))
    ids = {s['id'] for s in batch}
    n = 0
    with lock:
        for k, v in (res.items() if isinstance(res, dict) else []):
            if k in ids and isinstance(v, str) and v.strip():
                out['sayings'][k] = v.strip()
                n += 1
        save(out)
    return n


def main():
    out = load_out()
    eps, sayings = episodes()
    only_say = '--sayings-only' in sys.argv
    ep_todo = [] if only_say else [(s, v) for s, v in eps.items() if s not in out['ep']]
    say_todo = [s for s in sayings if s['id'] not in out['sayings']]
    batches = [say_todo[i:i + 40] for i in range(0, len(say_todo), 40)]
    print(f'episodes todo: {len(ep_todo)} / {len(eps)}; sayings todo: {len(say_todo)} / {len(sayings)}', flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(do_sayings, b, out): f'sayings batch {i}' for i, b in enumerate(batches)}
        futs.update({pool.submit(do_ep, s, v, out): s for s, v in ep_todo})
        for f in as_completed(futs):
            try:
                print(f'OK {futs[f]} -> {f.result()}', flush=True)
            except Exception as e:  # noqa: BLE001
                print(f'ERR {futs[f]}: {str(e)[:160]}', flush=True)
    print(f'done: ep {len(out["ep"])} / {len(eps)}, sayings {len(out["sayings"])} / {len(sayings)}', flush=True)


if __name__ == '__main__':
    main()
