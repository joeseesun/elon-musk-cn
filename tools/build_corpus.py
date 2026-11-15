#!/usr/bin/env python3
"""生成可下载语料包到 site/corpus/。

本站不重复托管 silicon-valley.tech 的英文原始语料（文稿 / X 帖子 / 回复），
那部分在站内只给链接、注明出处。这里打包的是本站的中文增量：

  llms-full.txt              586 篇中文精读合并的单文件（给 RAG / 长上下文模型 / Agent）
  elon-musk-cn-corpus.zip    完整语料包：逐篇 Markdown + 结构化 JSON + 说明
  index.md                   文件清单（人 + agent 都能读）
  README.md                  来源、版权、用法
  predictions.json           21+ 条预言 / 承诺（中英 + 核实结果）
  quotes.json                556 条双语语录
  themes.json                8 大主题（中英 + 精选视频）
  videos.json                651 条视频目录（中英标题、日期、链接）

全部由本站已有的源数据生成，纯标准库、可重复运行。
"""
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
SITE = ROOT.parent / 'site'
OUT = SITE / 'corpus'
TODAY = date.today().isoformat()

CFG = json.load(open(ROOT / 'site_config.json')) if (ROOT / 'site_config.json').exists() else {}
DOMAIN = CFG.get('domain', 'https://elon.qiaomu.ai')
SITE_NAME = '马斯克全访谈'

master = json.load(open(ROOT / 'elon-master.json'))
trans = json.load(open(ROOT / 'translations.json'))
for m in master:
    m['zh'] = (trans.get(m['slug']) or {}).get('zh')
extra = json.load(open(ROOT.parent / 'data' / 'extra.json'))
extra_zh = json.load(open(ROOT.parent / 'data' / 'extra-zh.json'))
_qzh = ROOT.parent / 'data' / 'quotes-zh.json'
quotes_zh = json.load(open(_qzh)) if _qzh.exists() else {}
SAYINGS_ZH = quotes_zh.get('sayings') or {}

SRC = 'https://silicon-valley.tech/'
STATUS_ZH = {'kept': '已兑现', 'late': '迟到兑现', 'missed': '未兑现', 'open': '待验证'}
TOPIC_ZH = {'tesla': 'Tesla', 'spacex': 'SpaceX', 'ia': '人工智能', 'neuralink': 'Neuralink',
            'politique': '政治', 'societe': '社会'}

by_slug = {m['slug']: m for m in master}


def _dump(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n')
    return p


def build_predictions():
    zhc = extra_zh.get('promises') or []
    zho = extra_zh.get('outcomes') or {}
    rows = []
    for i, p in enumerate(extra['promises']):
        vid = (p.get('video') or '').replace('yt-', '')
        target = next((m for m in master if m['srcId'] == vid), None)
        rows.append({
            'said': p.get('said') or '',
            'deadline': p.get('deadline') or '',
            'status': p.get('status') or '',
            'status_zh': STATUS_ZH.get(p.get('status'), p.get('status')),
            'topic': p.get('topic') or '',
            'topic_zh': TOPIC_ZH.get(p.get('topic'), p.get('topic')),
            'claim_zh': zhc[i] if i < len(zhc) else (p['claim'][0] if p.get('claim') else ''),
            'claim_en': (p.get('claim') or [''])[0],
            'quote': p.get('quote') or '',
            'outcome_zh': zho.get(str(i), ''),
            'outcome_en': (p.get('outcome') or [''])[0],
            'source': p.get('src') or '',
            'source_url': p.get('url') or '',
            'video_slug': target['slug'] if target else '',
        })
    return _dump('predictions.json', {
        'source': SRC, 'note': '数据来自 silicon-valley.tech（Elon Musk Archive），中文为本站 AI 翻译/整理',
        'updated': TODAY, 'count': len(rows), 'items': rows})


def build_quotes():
    rows = []
    for s in extra['sayings']:
        sid = s.get('id') or ''
        rows.append({
            'id': sid,
            'text_en': s.get('t') or '',
            'text_zh': SAYINGS_ZH.get(sid, ''),
            'date': s.get('d') or '',
            'kind': s.get('k') or '',
            'source': s.get('src') or '',
            'source_url': s.get('u') or '',
        })
    return _dump('quotes.json', {
        'source': SRC, 'note': '英文原话来自 silicon-valley.tech，中文为本站 AI 翻译（以英文为准）',
        'updated': TODAY, 'count': len(rows), 'items': rows})


def build_themes():
    rows = []
    for th in extra['themes']:
        key = th.get('key') or ''
        zh = extra_zh.get('themes', {}).get(key) or ['', '']
        rows.append({
            'key': key,
            'title_en': (th.get('title') or [''])[0],
            'title_zh': zh[0] if zh else '',
            'intro_en': (th.get('intro') or [''])[0],
            'intro_zh': zh[1] if len(zh) > 1 else '',
            'paragraphs': th.get('n') or 0,
            'freq_by_year': th.get('freq') or {},
        })
    return _dump('themes.json', {
        'source': SRC, 'updated': TODAY, 'count': len(rows), 'items': rows})


def build_videos():
    epdir = SITE / 'ep'
    rows = []
    for m in master:
        slug = m['slug']
        has_zh = (epdir / slug / 'index.md').exists()
        rows.append({
            'slug': slug,
            'title_zh': m.get('zh') or '',
            'title_en': m.get('title') or '',
            'date': m.get('d') or '',
            'date_precision': m.get('dp') or '',
            'kind': m.get('kZh') or '',
            'channel': m.get('ch') or '',
            'seconds': m.get('sec') or 0,
            'has_transcript': bool(m.get('tr')),
            'has_deepread': has_zh,
            'url': f'{DOMAIN}/ep/{slug}/',
            'deepread_md': f'{DOMAIN}/ep/{slug}/index.md' if has_zh else '',
            'archive_url': f'{SRC}#v-yt-{m["srcId"]}' if m.get('srcId') else '',
        })
    return _dump('videos.json', {
        'source': SRC, 'updated': TODAY, 'count': len(rows), 'items': rows})


def build_full_text(files):
    """把所有中文精读合并成一个纯文本文件，每篇保留标题、日期、来源链接。"""
    out = [f'# {SITE_NAME} · 中文精读全文（AI 改写）\n',
           f'> 本站 {len(files)} 篇中文精读的完整原文，按年份排序。\n'
           f'> 数据来自 silicon-valley.tech（Elon Musk Archive）；中文精读由本站 AI 改写，非官方翻译。\n'
           f'> 引用请注明「{DOMAIN} 中文精读（AI 改写）」并链接对应网页。\n'
           f'> 生成日期：{TODAY}\n']
    ordered = sorted(files, key=lambda p: (by_slug.get(p.parent.name, {}).get('d') or ''))
    for i, p in enumerate(ordered, 1):
        slug = p.parent.name
        m = by_slug.get(slug, {})
        out.append('\n\n' + '=' * 72 + '\n')
        out.append(f'[{i}/{len(ordered)}] {m.get("zh") or m.get("title") or slug}\n')
        out.append(f'日期：{m.get("d") or "未知"} · 类型：{m.get("kZh") or ""}\n')
        out.append(f'网页版：{DOMAIN}/ep/{slug}/\n')
        out.append(f'档案出处：{SRC}#v-yt-{m.get("srcId", "")}\n')
        out.append('-' * 72 + '\n\n')
        out.append(p.read_text().strip())
    path = OUT / 'llms-full.txt'
    path.write_text(''.join(out))
    return path


def build_readme():
    n_zh = len(list((SITE / 'ep').glob('*/index.md')))
    text = f"""# {SITE_NAME} · 中文语料包

本包是 [{DOMAIN}]({DOMAIN}) 的中文增量语料，与 silicon-valley.tech 的英文原始语料**互补，不重复**：

- **英文原始语料**（逐字文稿、X 帖子与回复、预言英文原文）请直接去
  [silicon-valley.tech/#data](https://silicon-valley.tech/#data) 下载。本站不重新托管，引用请注明
  Elon Musk Archive。
- **本包**只含本站做的中文增量：{n_zh} 篇 AI 改写的中文精读，以及翻译整理后的结构化数据。

## 文件

| 文件 | 内容 |
|---|---|
| `llms-full.txt` | {n_zh} 篇中文精读合并为单个纯文本文件，每篇带标题、日期与网页版链接。给 1M 上下文模型 / RAG / Agent 一次性读入。 |
| `deepreads/` | {n_zh} 篇中文精读，每篇一个 Markdown 文件，文件名即视频 slug。给 NotebookLM 作独立来源，或逐篇引用。 |
| `predictions.json` | 带日期的公开承诺 / 预言，含中英双语、状态与核实结果。 |
| `quotes.json` | 双语语录，英文原话 + 中文译文 + 年份 + 出处。 |
| `themes.json` | 8 大主题的中英介绍与逐年提及频率。 |
| `videos.json` | {len(master)} 条视频的目录：中英标题、日期、类型、时长、网页版与档案链接。 |

## 给 AI / Agent 用

- **单个大文件**：把 `llms-full.txt` 整个交给支持长上下文的模型，或切块后入库做 RAG。
- **逐篇来源**：用 `deepreads/` 里的 Markdown 作独立来源，回答可cite到具体某篇；每篇顶部有网页版链接可回填出处。
- **结构化查询**：`predictions.json` / `quotes.json` / `themes.json` / `videos.json` 适合程序化检索与交叉验证。
- **在线版**：每篇精读都有网页版 `{DOMAIN}/ep/{{slug}}/`，Markdown 版在网址后加 `index.md`；整站清单见
  [{DOMAIN}/llms.txt]({DOMAIN}/llms.txt)。

## 版权与引用

- 视频与英文文稿版权归原权利方所有；本站不托管任何媒体文件。
- 中文精读为 AI 二次创作、非官方翻译，未经审阅，仅供学习参考。
- 引用请注明「{DOMAIN} 中文精读（AI 改写，非官方翻译）」并链接对应网页版；使用英文原始语料时另请注明
  silicon-valley.tech（Elon Musk Archive）。

生成日期：{TODAY}
"""
    p = OUT / 'README.md'
    p.write_text(text)
    return p


def build_index(files, extra_files):
    lines = [f'# {SITE_NAME} · 语料文件清单\n',
             f'> 生成日期 {TODAY} · 全部文件在 `{DOMAIN}/corpus/`\n',
             '| 文件 | 说明 | 大小 |', '|---|---|---|']
    for path, desc in extra_files:
        lines.append(f'| [{path.name}]({DOMAIN}/corpus/{path.name}) | {desc} | {path.stat().st_size / 1048576:.1f} MB |')
    total = sum(p.stat().st_size for p in files)
    lines.append(f'| [elon-musk-cn-corpus.zip]({DOMAIN}/corpus/elon-musk-cn-corpus.zip) | 上列全部文件 + 逐篇 Markdown，一次下载 | — |')
    lines.append('')
    lines.append(f'共 {len(files)} 篇中文精读，合计 {total / 1048576:.1f} MB。')
    lines.append('英文原始语料（文稿 / X 帖子 / 回复）请去 [silicon-valley.tech/#data](https://silicon-valley.tech/#data)，本站不重复托管。')
    p = OUT / 'index.md'
    p.write_text('\n'.join(lines) + '\n')
    return p


def build_zip(parts, deep_files):
    """把所有可下载文件 + 逐篇 Markdown 打成一个 zip。"""
    zpath = OUT / 'elon-musk-cn-corpus.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p, arc in parts:
            z.write(p, arc)
        for p in deep_files:
            z.write(p, f'deepreads/{p.parent.name}.md')
    return zpath


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    deep_files = sorted((SITE / 'ep').glob('*/index.md'))
    structured = [build_predictions(), build_quotes(), build_themes(), build_videos()]
    full = build_full_text(deep_files)
    readme = build_readme()

    desc = {
        'llms-full.txt': '全部中文精读合并的单个纯文本文件（给 RAG / 长上下文 / Agent）',
        'predictions.json': '预言与承诺追踪（中英双语 + 核实结果）',
        'quotes.json': '双语语录',
        'themes.json': '8 大主题（中英 + 逐年频率）',
        'videos.json': '视频目录（中英标题、日期、链接）',
        'README.md': '来源、版权与使用说明',
        'index.md': '本文件清单',
    }
    loose = [full] + structured + [readme]
    build_index(deep_files, [(p, desc[p.name]) for p in loose])

    parts = [(p, p.name) for p in loose] + [(OUT / 'index.md', 'index.md')]
    zp = build_zip(parts, deep_files)

    print(f'corpus: {len(deep_files)} deep-reads, llms-full {full.stat().st_size / 1048576:.1f} MB, '
          f'zip {zp.stat().st_size / 1048576:.1f} MB')


if __name__ == '__main__':
    main()
