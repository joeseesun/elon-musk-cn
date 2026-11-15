#!/usr/bin/env python3
"""批量翻译：651 个视频标题 → 中文；预言/精选/主题导言 → 中文。

输出：
  tools/translations.json  {slug: {zh}}  视频中文标题
  data/extra-zh.json       {promises: [claim_zh], picks: {ytid: why_zh}, themes: {key: [title_zh, intro_zh]}}

断点续跑：已翻译的 slug 直接跳过；可重复执行。
网关：Magpie（钥匙串 qiaomu-llm/magpie），质量路由同 lex 侧。
"""
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TRANS = ROOT / 'tools' / 'translations.json'
EXTRA = ROOT / 'data' / 'extra.json'
EXTRA_ZH = ROOT / 'data' / 'extra-zh.json'

BASE_URL = 'https://magpie.qiaomu.ai/v1'
MODELS_ALL = [
    'opencode-go/deepseek-v4.1-flash',
    'trae-cn/deepseek-v4.1-flash',
    'workbuddy/deepseek-v4.1-flash',
]
WORKERS = 4

_api_key = None


def api_key():
    global _api_key
    if _api_key is None:
        _api_key = os.environ.get('MAGPIE_API_KEY') or subprocess.run(
            ['security', 'find-generic-password', '-s', 'qiaomu-llm', '-a', 'magpie', '-w'],
            capture_output=True, text=True, check=True).stdout.strip()
    return _api_key


def chat(messages, max_tokens=4000, timeout=300):
    last = None
    for attempt in range(6):
        model = MODELS_ALL[attempt % len(MODELS_ALL)]
        try:
            r = requests.post(
                f'{BASE_URL}/chat/completions',
                headers={'Authorization': f'Bearer {api_key()}', 'Content-Type': 'application/json'},
                json={'model': model, 'messages': messages, 'max_tokens': max_tokens,
                      'temperature': 0.3},
                timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                last = f'HTTP {r.status_code}'
                time.sleep(min(120, 8 * 2 ** attempt))
                continue
            r.raise_for_status()
            return r.json()['choices'][0]['message'].get('content') or ''
        except Exception as e:
            last = str(e)[:200]
            time.sleep(min(120, 8 * 2 ** attempt))
    raise RuntimeError(f'chat failed: {last}')


def extract_json(text):
    text = text.strip()
    m = None
    import re
    for m in re.finditer(r'\{[\s\S]*\}|\[[\s\S]*\]', text):
        pass
    if not m:
        raise ValueError('no json in response')
    return json.loads(m.group(0))


def translate_titles():
    master = json.load(open(ROOT / 'tools' / 'elon-master.json'))
    trans = json.load(open(TRANS)) if TRANS.exists() else {}
    todo = [x for x in master if x['slug'] not in trans and x.get('title')]
    print(f'titles todo: {len(todo)}', flush=True)
    if not todo:
        return
    B = 40
    lock = threading.Lock()

    def work(i):
        batch = todo[i:i + B]
        items = {x['slug']: x['title'] for x in batch}
        listing = '\n'.join(f'{k}\t{t}' for k, t in items.items())
        msgs = [
            {'role': 'system', 'content':
             '你是科技媒体编辑。把马斯克相关视频标题翻译成简体中文。要求：'
             '1. 简洁有力，像中文科技媒体的标题；2. 人名音译（Elon Musk=马斯克、Joe Rogan=乔·罗根、'
             'Rishi Sunak=苏纳克、Bill Maher=比尔·马赫、Don Lemon=唐·莱蒙、Jay Leno=杰·雷诺、'
             'Ron Baron=罗恩·巴伦、Chris Anderson=克里斯·安德森、Fareed Zakaria=法里德·扎卡利亚、'
             'Ben Shapiro=本·夏皮罗、Nikhil Kamath=尼基尔·卡马斯、Bret Baier=布雷特·拜尔）；'
             '3. 公司产品名保留英文（Tesla、SpaceX、Model 3、Cybertruck、Falcon、Starship、FSD、Neuralink、'
             'Twitter/X、ChatGPT、Grok、Optimus、Powerwall、Model Y、Roadster、Semi）；'
             '4. Q1/Q2 等财报期保留原样；5. 只输出 JSON：{"slug": "中文标题"}，不要任何解释。'},
            {'role': 'user', 'content': listing},
        ]
        out = extract_json(chat(msgs, max_tokens=8000))
        with lock:
            for k, v in out.items():
                if k in items and isinstance(v, str) and v.strip():
                    trans[k] = {'zh': v.strip()[:80]}
            json.dump(trans, open(TRANS, 'w'), ensure_ascii=False, indent=0)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(work, i) for i in range(0, len(todo), B)]
        done = 0
        for f in as_completed(futs):
            f.result()
            done += 1
            print(f'batch {done}/{len(futs)} done', flush=True)
    print(f'translations.json: {len(trans)} titles')


PROMPT_PROMISES = ('把下面每条马斯克公开承诺/预言的 claim 翻译成简体中文，忠实原意，简洁。'
                   '输出 JSON 数组，按原顺序，元素为中文字符串。原文：\n\n')


def translate_extra():
    extra = json.load(open(EXTRA))
    zh = json.load(open(EXTRA_ZH)) if EXTRA_ZH.exists() else {}

    if 'promises' not in zh:
        claims = [p['claim'][0] for p in extra['promises']]
        out = extract_json(chat([{'role': 'user', 'content': PROMPT_PROMISES + '\n'.join(claims)}],
                                max_tokens=6000))
        zh['promises'] = out
        json.dump(zh, open(EXTRA_ZH, 'w'), ensure_ascii=False, indent=1)
        print('promises translated:', len(out))

    if 'picks' not in zh:
        picks = {p['v']: p['why'][0] for p in extra['picks']}
        out = extract_json(chat([{'role': 'user', 'content':
            '把下面每段推荐语翻译成简体中文，保留细节与语气。输出 JSON：{"键": "中文"}。原文：\n\n'
            + '\n'.join(f'{k}\t{v}' for k, v in picks.items())}], max_tokens=6000))
        zh['picks'] = out
        json.dump(zh, open(EXTRA_ZH, 'w'), ensure_ascii=False, indent=1)
        print('picks translated:', len(out))

    if 'themes' not in zh:
        themes = {t['key']: [t['title'][0], t['intro'][0]] for t in extra['themes']}
        out = extract_json(chat([{'role': 'user', 'content':
            '下面是马斯克言论档案的 8 个主题，每个有标题和导言。把标题和导言翻译成简体中文。'
            '输出 JSON：{"键": ["中文标题", "中文导言"]}。原文：\n\n'
            + '\n'.join(f'{k}\t标题: {v[0]}\n导言: {v[1]}' for k, v in themes.items())}], max_tokens=6000))
        zh['themes'] = out
        json.dump(zh, open(EXTRA_ZH, 'w'), ensure_ascii=False, indent=1)
        print('themes translated:', len(out))


    if 'outcomes' not in zh:
        outs = [(i, p.get('outcome', [None, None])[0] or '') for i, p in enumerate(extra['promises'])]
        outs = [(i, o) for i, o in outs if o]
        out = extract_json(chat([{'role': 'user', 'content':
            '把下面每条马斯克承诺/预言的实际结果说明翻译成简体中文，忠实原意。'
            '输出 JSON 数组，元素为 {i, zh}。原文：\n\n'
            + '\n'.join(f'{i}\t{o}' for i, o in outs)}], max_tokens=6000))
        zh['outcomes'] = {str(x['i']): x['zh'] for x in out if isinstance(x, dict) and 'i' in x}
        json.dump(zh, open(EXTRA_ZH, 'w'), ensure_ascii=False, indent=1)
        print('outcomes translated:', len(zh['outcomes']))


def main():
    if '--extra-only' not in sys.argv:
        translate_titles()
    translate_extra()


if __name__ == '__main__':
    main()
