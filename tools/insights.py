"""数据洞察：话题热度、口头禅、承诺兑现时间线。只做计算并输出 HTML 片段，页面外壳在 build.py。

查询语法与 /search/ 一致：空格 = 且，| = 或，"..." = 短语。分词与词干复用 search_index。
"""
import html
import re
from datetime import date

from search_index import _TOK, norm, stem

# (中文名, 查询, 分组)
TOPICS = [
    ('火星', 'mars', '太空'),
    ('星舰', 'starship', '太空'),
    ('火箭复用', 'reusable|reusability|reuse|reflight', '太空'),
    ('星链', 'starlink', '太空'),
    ('特斯拉', 'tesla', '汽车与能源'),
    ('自动驾驶', 'fsd|autopilot|"self-driving"|autonomy', '汽车与能源'),
    ('无人出租车', 'robotaxi|cybercab', '汽车与能源'),
    ('电池与储能', 'battery|megapack|powerwall', '汽车与能源'),
    ('太阳能', 'solar', '汽车与能源'),
    ('超级工厂与制造', 'gigafactory|manufacturing', '汽车与能源'),
    ('人工智能', 'ai|"artificial intelligence"', 'AI 与机器人'),
    ('超级智能与 AI 风险', 'superintelligence|"existential risk"|"ai safety"|agi', 'AI 与机器人'),
    ('人形机器人', 'optimus|humanoid', 'AI 与机器人'),
    ('OpenAI', 'openai', 'AI 与机器人'),
    ('xAI 与 Grok', 'xai|grok', 'AI 与机器人'),
    ('脑机接口', 'neuralink', 'AI 与机器人'),
    ('推特 / X', 'twitter', '社会与政治'),
    ('言论自由', '"free speech"|"freedom of speech"|censorship', '社会与政治'),
    ('特朗普', 'trump', '社会与政治'),
    ('政府效率 DOGE', '"government efficiency"|doge', '社会与政治'),
    ('出生率', '"birth rate"|birthrate|"population collapse"', '社会与政治'),
    ('中国', 'china|chinese', '社会与政治'),
    ('隧道与超级高铁', 'tunnel|hyperloop|"boring company"', '其他'),
    ('加密货币', 'bitcoin|dogecoin|crypto|cryptocurrency', '其他'),
    ('气候与可持续能源', 'climate|"sustainable energy"|"global warming"', '其他'),
    ('第一性原理', '"first principles"|"first principle"', '其他'),
]

# 口头禅：(英文, 中文意思, 一句话说明)
PHRASES = [
    ('fundamentally', '从根本上说', '讲物理极限、成本结构时的开场白'),
    ('essentially', '本质上', '把复杂问题压成一句话'),
    ('obviously', '显然', '他觉得不言自明的事，常常别人并不觉得'),
    ('basically', '基本上', '口语里的万能连接词'),
    ('order of magnitude', '一个数量级', '「好一个数量级」= 好十倍，他衡量进步的单位'),
    ('first principles', '第一性原理', '从物理事实出发推理，而不是类比'),
    ('probability', '概率', '谈未来几乎从不说「一定」，而是说概率'),
    ('civilization', '文明', '多行星、出生率、AI，最后都落到文明存续'),
    ('humanity', '人类', '「对人类有益」是他解释动机的常用说法'),
    ('consciousness', '意识', '他说要「扩展意识的范围与规模」'),
    ('sustainable', '可持续的', '特斯拉使命里的关键词'),
    ('exciting', '激动人心的', '描述未来时的高频形容词'),
    ('insane', '疯狂的（褒义）', '「insane mode」就是特斯拉的加速模式名'),
    ('crazy', '疯狂的', '自嘲和夸张时都用'),
    ('massive', '巨大的', '描述规模：产能、算力、火箭'),
    ('tremendous', '极大的', '偏正式的「非常大」'),
    ('dramatically', '大幅地', '「大幅降低成本」的标准搭配'),
    ('hopefully', '但愿', '给时间表留余地的软化词'),
    ('next year', '明年', '「马斯克时间」的源头：很多事都在「明年」'),
    ('to be clear', '说清楚一点', '澄清和纠正前的提示语'),
    ('frankly', '坦白说', '准备说一句不太中听的话'),
    ('in the limit', '在极限情况下', '物理学家式的推演习惯'),
    ('exponential', '指数级的', '谈 AI 与算力增长'),
    ('hardcore', '硬核', '2022 年那封「extremely hardcore」邮件'),
    ('non-trivial', '不简单的', '工程师式的轻描淡写，意思是「很难」'),
    ('epic', '史诗级的', '形容发射和产品发布'),
]

YEAR_MIN = 2008


def esc(s):
    return html.escape(str(s or ''), quote=True)


def tok_seq(text):
    return [stem(w) for w in _TOK.findall(norm(text))]


_GROUP = re.compile(r'(?:"[^"]*"|[^\s|"]+)(?:\|(?:"[^"]*"|[^\s|"]+))*')


def compile_query(q):
    groups = []
    for g in _GROUP.findall(q):
        alts = []
        for a in re.findall(r'"[^"]*"|[^\s|"]+', g):
            seq = tuple(tok_seq(a.strip('"')))
            if seq:
                alts.append(seq)
        if alts:
            groups.append(alts)
    return groups


def matches(groups, seq, sset):
    for alts in groups:
        ok = False
        for a in alts:
            if len(a) == 1:
                if a[0] in sset:
                    ok = True
                    break
            elif a[0] in sset and all(x in sset for x in a):
                L = len(a)
                if any(tuple(seq[i:i + L]) == a for i in range(len(seq) - L + 1)):
                    ok = True
                    break
        if not ok:
            return False
    return True


def bucket(y):
    return f'≤{str(YEAR_MIN - 1)[2:]}' if y < YEAR_MIN else str(y)


def topic_trends(docs):
    """docs: [(slug, d, zh_title, paras)]，按日期排序。返回 {cols, totals, rows}。"""
    years = sorted({int(d[:4]) for _, d, _, _ in docs if d and d[:4].isdigit()})
    cols = [bucket(YEAR_MIN - 1)] + [str(y) for y in range(YEAR_MIN, max(years) + 1)]
    totals = {c: 0 for c in cols}
    comp = [(zh, q, grp, compile_query(q)) for zh, q, grp in TOPICS]
    counts = [{c: 0 for c in cols} for _ in TOPICS]
    first = [None] * len(TOPICS)
    for slug, d, zh, paras in sorted(docs, key=lambda x: x[1] or '9999'):
        if not d or not d[:4].isdigit():
            continue
        c = bucket(int(d[:4]))
        for k, (sec, text) in enumerate(paras):
            totals[c] += 1
            seq = tok_seq(text)
            sset = set(seq)
            for i, (_, _, _, groups) in enumerate(comp):
                if matches(groups, seq, sset):
                    counts[i][c] += 1
                    if first[i] is None:
                        first[i] = {'slug': slug, 'd': d, 'zh': zh, 'k': k, 'sec': sec}
    rows = []
    for i, (zh, q, grp, _) in enumerate(comp):
        rate = {c: (counts[i][c] * 1000 / totals[c] if totals[c] else 0) for c in cols}
        rows.append({'zh': zh, 'q': q, 'grp': grp, 'n': sum(counts[i].values()), 'counts': counts[i],
                     'rate': rate, 'first': first[i]})
    return {'cols': cols, 'totals': totals, 'rows': rows}


def first_hl(q):
    words = re.findall(r'[a-z0-9]+', q.split('|')[0].lower())
    return ' '.join(words)


def heatmap_html(t):
    cols = t['cols']
    head = ''.join(f'<th scope="col"><span>{esc(c if c.startswith("≤") else c[2:])}</span></th>' for c in cols)
    body, last_grp = [], None
    for r in t['rows']:
        if r['grp'] != last_grp:
            body.append(f'<tr class="hm-grp"><th scope="rowgroup" colspan="{len(cols) + 1}">{esc(r["grp"])}</th></tr>')
            last_grp = r['grp']
        mx = max(r['rate'].values()) or 1
        cells = []
        for c in cols:
            v = r['rate'][c]
            n = r['counts'][c]
            lvl = v / mx
            y = '' if c.startswith('≤') else c
            href = f'/search/?q={esc(_q(r["q"]))}' + (f'&amp;y={y}' if y else '')
            tip = f'{c.replace("≤", "2007 年及以前") if c.startswith("≤") else c + " 年"}：{n} 段提到「{r["zh"]}」，每千段 {v:.1f}'
            cells.append(f'<td><a href="{href}" style="--v:{lvl:.3f}" title="{esc(tip)}" aria-label="{esc(tip)}">'
                         '</a></td>')
        body.append(f'<tr><th scope="row"><a href="/search/?q={esc(_q(r["q"]))}">{esc(r["zh"])}</a>'
                    f'<small>{r["n"]:,} 段</small></th>{"".join(cells)}</tr>')
    return (f'<div class="hm-wrap"><table class="hm"><thead><tr><th scope="col" class="hm-corner">话题</th>{head}'
            f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def _q(q):
    from urllib.parse import quote
    return quote(q, safe='')


def phrase_stats(docs, quality):
    """docs: [(slug, d, zh, [(sec, text), ...])]；quality(slug, sec) → 越大越优先拿来做例句。"""
    total_words = 0
    counts = {p[0]: 0 for p in PHRASES}
    pats = {p[0]: re.compile(r"(?<![a-z'])" + re.escape(p[0]) + r"(?![a-z'])") for p in PHRASES}
    cands = {p[0]: [] for p in PHRASES}
    for slug, d, zh, paras in docs:
        for k, (sec, text) in enumerate(paras):
            q = quality(slug, sec)
            low = norm(text)
            total_words += len(_TOK.findall(low))
            for ph, pat in pats.items():
                n = len(pat.findall(low))
                if not n:
                    continue
                counts[ph] += n
                if len(cands[ph]) >= 60:
                    continue
                for s in re.split(r'(?<=[.?!])\s+', text):
                    if 50 <= len(s) <= 170 and '[' not in s and pat.search(norm(s)):
                        cands[ph].append({'q': q, 'slug': slug, 'zh': zh, 'd': d, 'k': k, 'sec': sec, 's': s})
                        break
    # 例句尽量分散到不同视频，避免一场访谈包揽所有例句
    used = {}
    examples = {}
    for ph in sorted(cands, key=lambda p: -counts[p]):
        best = min(cands[ph], key=lambda c: (used.get(c['slug'], 0), -c['q'], abs(len(c['s']) - 110)), default=None)
        examples[ph] = best
        if best:
            used[best['slug']] = used.get(best['slug'], 0) + 1
    rows = []
    for ph, zh, note in PHRASES:
        rows.append({'en': ph, 'zh': zh, 'note': note, 'n': counts[ph],
                     'per': counts[ph] * 10000 / total_words if total_words else 0, 'ex': examples[ph]})
    rows.sort(key=lambda r: -r['n'])
    return {'words': total_words, 'rows': rows}


def phrases_html(ps, ts_fmt):
    from urllib.parse import urlencode
    mx = max(r['per'] for r in ps['rows']) or 1
    out = []
    for i, r in enumerate(ps['rows'], 1):
        ex = r['ex']
        ex_html = ''
        if ex:
            q = {'t': ex['sec']} if ex['sec'] is not None else {}
            hi = re.sub(r'(?i)(?<![a-z\'])(' + re.escape(r['en']) + r')(?![a-z\'])', lambda m: f'<mark>{m.group(1)}</mark>', esc(ex['s']))
            ts = ts_fmt(ex['sec']) if ex['sec'] is not None else '¶'
            ex_html = (f'<a class="ph-ex" href="/ep/{esc(ex["slug"])}/{"?" + esc(urlencode(q)) if q else ""}">'
                       f'<span class="ph-ts">▶ {esc(ts)}</span><span class="ph-s" lang="en">{hi}</span>'
                       f'<span class="ph-src">{esc((ex["d"] or "")[:4])} · {esc(ex["zh"])}</span></a>')
        out.append(f'''<li class="ph">
  <div class="ph-h"><span class="ph-rank">{i:02d}</span><b class="ph-en" lang="en">{esc(r["en"])}</b><span class="ph-zh">{esc(r["zh"])}</span>
    <span class="ph-bar"><i style="width:{r["per"] / mx * 100:.1f}%"></i></span><span class="ph-n">{r["per"]:.1f}<small>/万词</small></span></div>
  <p class="ph-note">{esc(r["note"])}</p>{ex_html}
</li>''')
    return f'<ol class="ph-list">{"".join(out)}</ol>'


# ---------------------------------------------------------------- 承诺兑现时间线
_MON = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                    'september', 'october', 'november', 'december'], 1)}
_MON.update({k[:3]: v for k, v in list(_MON.items())})
_MON['sept'] = 9


def _end_of_month(y, m):
    return date(y + (m == 12), m % 12 + 1, 1).toordinal() - 1


def parse_deadline(s):
    """'end of 2017' / 'December 2017' / 'Oct–Nov 2020' / '2022 / 2024' → 该期限的最后一天（ordinal）。"""
    if not s or s.strip() in ('—', '-'):
        return None
    m = re.search(r'(19|20)\d\d', s)
    if not m:
        return None
    y = int(m.group(0))
    before = s[:m.start()].lower()
    mons = [(_MON[w]) for w in re.findall(r'[a-z]+', before) if w in _MON]
    if mons:
        return _end_of_month(y, mons[-1])
    return date(y, 12, 31).toordinal()


_DATE = re.compile(r'(?:(?P<mon>[A-Z][a-z]+)\s+(?:(?P<day>\d{1,2}),\s+)?)?(?P<y>(?:19|20)\d\d)')


def parse_outcome(text, said_ord):
    """从英文结果描述里找「兑现日期」：优先含 first / reached / deliveries 的句子里的第一个日期。"""
    if isinstance(text, list):
        text = text[0] if text else ''
    if not text:
        return None
    sents = re.split(r'(?<=[.;])\s+', text)
    pref = [s for s in sents if re.search(r'\b(first|reached|deliveries|built|launched|landing)\b', s, re.I)]
    for group in (pref, sents):
        for s in group:
            for m in _DATE.finditer(s):
                y = int(m.group('y'))
                mon = _MON.get((m.group('mon') or '').lower())
                if mon and m.group('day'):
                    o = date(y, mon, int(m.group('day'))).toordinal()
                elif mon:
                    o = date(y, mon, 15).toordinal()
                else:
                    o = date(y, 7, 1).toordinal()
                if o > said_ord:
                    return o
    return None


def parse_said(s):
    if not s:
        return None
    p = s.split('-')
    y = int(p[0])
    mth = int(p[1]) if len(p) > 1 else 7
    d = int(p[2]) if len(p) > 2 else 1
    return date(y, mth, d).toordinal()


def _dur(days):
    if days >= 330:
        return f'{days / 365.25:.1f} 年'
    return f'{max(1, round(days / 30.44))} 个月'


def promise_timeline(ps, claims_zh, status_zh, today=None):
    """ps：extra['promises']；claims_zh：同序中文。返回 (html, 统计)。"""
    today = (today or date.today()).toordinal()
    rows = []
    for i, p in enumerate(ps):
        s = parse_said(p.get('said'))
        d = parse_deadline(p.get('deadline'))
        st = p.get('status')
        o = parse_outcome(p.get('outcome'), s) if st in ('kept', 'late') else None
        rows.append({'i': i, 's': s, 'd': d, 'o': o, 'st': st, 'zh': claims_zh[i] if i < len(claims_zh) else p['claim'][0],
                     'dl': p.get('deadline') or ''})
    lo = date(date.fromordinal(min(r['s'] for r in rows)).year, 1, 1).toordinal()
    hi_y = max(date.fromordinal(max([r['d'] or 0 for r in rows] + [r['o'] or 0 for r in rows] + [today])).year + 1, 2027)
    hi = date(hi_y, 1, 1).toordinal()
    pos = lambda o: (o - lo) / (hi - lo) * 100
    ticks = ''.join(f'<span class="pt-tick" style="left:{pos(date(y, 1, 1).toordinal()):.2f}%">{str(y)[2:] if y % 2 else y}</span>'
                    for y in range(date.fromordinal(lo).year, hi_y + 1) if y % 2 == 0 and 3 < pos(date(y, 1, 1).toordinal()) < 95)
    now = f'<span class="pt-now" style="left:{pos(today):.2f}%"><b>今天</b></span>'
    late_days, ratios = [], []
    out = []
    tag_pos = lambda p: f'left:{p:.2f}%' if p < 60 else f'right:{100 - p:.2f}%;margin-right:-2px'
    for r in sorted(rows, key=lambda r: r['s']):
        s, d, o, st = r['s'], r['d'], r['o'], r['st']
        segs, tag = [], ''
        seg = lambda a, b, cls: f'<i class="pt-seg {cls}" style="left:{pos(a):.2f}%;width:{max(.6, pos(b) - pos(a)):.2f}%"></i>'
        if d:
            segs.append(seg(s, d, 'seg-p'))
        if st == 'late' and d and o:
            segs.append(seg(d, o, 'seg-late'))
            late_days.append(o - d)
            ratios.append((o - s) / max(1, d - s))
            tag = f'迟到 {_dur(o - d)}'
            end = o
        elif st == 'kept':
            if not d and o:
                segs.append(seg(s, o, 'seg-kept'))
            tag = f'用时 {_dur(o - s)}' if o else '已兑现'
            end = o or s
        elif st == 'missed':
            if d:
                segs.append(seg(d, today, 'seg-miss'))
                tag = f'过期 {_dur(today - d)} 仍未兑现'
            else:
                tag = '未兑现'
            end = today if d else s
        else:
            if d:
                dd = date.fromordinal(d)
                tag = f'期限 {dd.year} 年' + ('底' if dd.month == 12 else f' {dd.month} 月')
            else:
                tag = '待验证'
            end = d or s
        mark = f'<i class="pt-end st-{st}" style="left:{pos(end):.2f}%"></i>' if st in ('kept', 'late') else ''
        label = r['zh']
        tip = f'{date.fromordinal(s).isoformat()[:7]} 说：{label}'
        out.append(f'''<li class="pt-row st-{esc(st)}">
  <div class="pt-label" title="{esc(tip)}"><span class="pt-st">{esc(status_zh.get(st, st))}</span><span class="pt-claim">{esc(label)}</span></div>
  <div class="pt-track"><i class="pt-said" style="left:{pos(s):.2f}%"></i>{"".join(segs)}{mark}<span class="pt-tag" style="{tag_pos(pos(end))}">{esc(tag)}</span></div>
</li>''')
    ratios.sort()
    late_days.sort()
    med = lambda xs: (xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2) if xs else 0
    stats = {'late_n': len(late_days), 'late_med': _dur(med(late_days)) if late_days else '',
             'ratio_med': med(ratios), 'ratio_max': max(ratios) if ratios else 0}
    legend = ('<div class="pt-legend"><span><i class="lg seg-p"></i>承诺的时间</span><span><i class="lg seg-late"></i>迟到的部分</span>'
              '<span><i class="lg seg-miss"></i>过期未兑现</span><span><i class="lg seg-kept"></i>无期限，实际用时</span></div>')
    html_out = (f'<div class="pt" style="--now:{pos(today):.2f}%">{legend}<div class="pt-axis"><div class="pt-axis-in">{ticks}{now}</div></div>'
                f'<ol class="pt-rows">{"".join(out)}</ol></div>')
    return html_out, stats
