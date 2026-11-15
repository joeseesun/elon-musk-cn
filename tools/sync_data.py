#!/usr/bin/env python3
"""从 silicon-valley.tech（Elon Musk Archive）同步数据，构建本站主数据。

- 下载 videos / sayings / quotes / promises / picks / themes JSON 与全部带文稿视频的 data/t/*.json
- 生成 tools/elon-master.json：651 条视频元数据（slug、日期、类型、中文标签映射、文稿标记）
- 生成 data/extra.json：预言追踪、精选、主题、语录（带来源，转载须注明 silicon-valley.tech）
- 幂等：可重复执行；文稿已存在则跳过下载

数据来源声明：silicon-valley.tech 公开语料允许研究与 AI 分析使用，须注明原始出处。
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
TR_DIR = DATA / 'transcripts'
MASTER = ROOT / 'tools' / 'elon-master.json'
EXTRA = ROOT / 'data' / 'extra.json'

BASE = 'https://silicon-valley.tech'

# 法语标签 / 类型 → 中文
TAG_ZH = {
    'ia': '人工智能', 'societe': '社会', 'spacex': 'SpaceX', 'tesla': 'Tesla',
    'politique': '政治', 'energie': '能源', 'x': 'X', 'boring': 'Boring Company',
    'neuralink': 'Neuralink', 'crypto': '加密货币',
}
KIND_ZH = {
    'interview': '访谈', 'podcast': '播客', 'conference': '大会演讲',
    'presentation': '发布会', 'gouvernement': '政府活动', 'presse': '媒体',
    'spaces': 'X Spaces', 'tesla-corp': '股东会',
}

# 源数据明显的事实性错误修正（按源站 ID）
DATE_FIX = {
    # Tesla Cybertruck 发布会实际为 2019-11-21（源数据误标 2016）
    'NcROXiN_cdE': '2019-11-21',
}

DP_ZH = {
    'jour': '精确日期', 'mois': '精确到月', 'année': '仅年份',
    '≈ mise en ligne': '约为上传日期',
}


def fetch_json(path, retries=3):
    for i in range(retries):
        try:
            out = subprocess.run(['curl', '-sSL', '--max-time', '60', f'{BASE}/{path}'],
                                 capture_output=True, text=True, check=True, timeout=90)
            return json.loads(out.stdout)
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(3)
    return None


def slugify(t, used):
    s = re.sub(r'[^a-z0-9]+', '-', (t or '').lower()).strip('-')
    s = re.sub(r'-{2,}', '-', s)[:64].strip('-') or 'video'
    base, n = s, 2
    while s in used:
        s = f'{base}-{n}'
        n += 1
    used.add(s)
    return s


def main():
    DATA.mkdir(exist_ok=True)
    TR_DIR.mkdir(parents=True, exist_ok=True)

    videos = fetch_json('data/videos.json')
    sayings = fetch_json('data/sayings.json')
    quotes = fetch_json('data/quotes.json')
    promises = fetch_json('data/promises.json')
    picks = fetch_json('data/picks.json')
    themes = fetch_json('data/themes.json')
    print(f'fetched: videos={len(videos)} sayings={len(sayings)} quotes={len(quotes["q"])} '
          f'promises={len(promises)} picks={len(picks)} themes={len(themes)}')

    used = set()
    master = []
    for v in sorted(videos, key=lambda x: (x.get('d') or '', x['id'])):
        src_id = v['id']
        # ia 平台的 archive.org 镜像内嵌真实 YouTube ID，用于嵌入播放与缩略图
        yt_id = src_id if v.get('p') == 'yt' else (src_id.replace('youtube-', '', 1)
                                                   if src_id.startswith('youtube-') else None)
        d = DATE_FIX.get(src_id, v.get('d') or '')
        master.append({
            'slug': slugify(v.get('t'), used),
            'srcId': src_id,
            'ytId': yt_id,
            'platform': v.get('p'),
            'mp4': (v['mp4'] if str(v.get('mp4', '')).startswith('http')
                    else f"{BASE}/{v['mp4']}") if v.get('mp4') else None,
            'poster': f"{BASE}/{v['poster']}" if v.get('poster') else None,
            'title': v.get('t'),
            'ch': v.get('ch'),
            'd': d,
            'dp': DP_ZH.get(v.get('dp'), v.get('dp')),
            'sec': v.get('sec'),
            'k': v.get('k'),
            'kZh': KIND_ZH.get(v.get('k'), v.get('k')),
            'a': [TAG_ZH.get(t, t) for t in (v.get('a') or [])],
            'tier': v.get('tier'),
            'feat': v.get('feat') or 0,
            'tr': bool(v.get('tr')),
            'trm': v.get('trm'),
        })

    # 下载全部带文稿视频的转录（按源站 ID 命名，幂等）
    need = [m for m in master if m['tr']]
    got = miss = 0
    for m in need:
        dest = TR_DIR / f"{m['srcId']}.json"
        if dest.exists() and dest.stat().st_size > 100:
            got += 1
            continue
        try:
            t = fetch_json(f"data/t/{m['srcId']}.json")
            dest.write_text(json.dumps(t, ensure_ascii=False))
            got += 1
        except Exception as e:
            miss += 1
            m['tr'] = False
            print(f"transcript miss {m['srcId']}: {str(e)[:80]}", file=sys.stderr)
    print(f'transcripts: {got} ok, {miss} miss')

    # 文稿为空的（如源站 2002 Facebook 片段）标记为无文稿
    for m in need:
        f = TR_DIR / f"{m['srcId']}.json"
        if not m['tr'] or not f.exists():
            m['tr'] = False if not f.exists() else m['tr']
            continue
        try:
            t = json.load(open(f))
            if not t.get('segs') or not any(s[1] for s in t['segs']):
                m['tr'] = False
        except Exception:
            m['tr'] = False

    n_tr = sum(1 for m in master if m['tr'])
    MASTER.write_text(json.dumps(master, ensure_ascii=False, indent=1))
    print(f'elon-master.json: {len(master)} videos, {n_tr} with transcripts')

    # 附加内容（预言 / 精选 / 主题 / 语录），原文为英文，中文译文在构建期由 translations 补充
    extra = {
        'source': {'site': 'silicon-valley.tech', 'name': 'Elon Musk Archive',
                   'note': '数据来自 silicon-valley.tech 公开语料，遵循其 CC 条款：研究与引用须注明原始出处。'},
        'promises': promises,
        'picks': picks,
        'themes': themes,
        'sayings': sayings,
        'quotes': {'v': quotes['v'], 'q': quotes['q']},
    }
    EXTRA.write_text(json.dumps(extra, ensure_ascii=False))
    print(f'data/extra.json: promises={len(promises)} picks={len(picks)} themes={len(themes)} sayings={len(sayings)}')


if __name__ == '__main__':
    main()
