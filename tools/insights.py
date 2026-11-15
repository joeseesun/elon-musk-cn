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


# ---------------------------------------------------------------- 提到的公司 / 人物 / 书 / 未来年份
COMPANIES = [
    ('特斯拉', 'tesla', 'k1'),
    ('SpaceX', 'spacex|"space x"', 'k2'),
    ('推特 / X', 'twitter|"x corp"|"x platform"|"x.com"', 'k3'),
    ('xAI / Grok', 'xai|grok', 'k4'),
    ('Neuralink', 'neuralink', 'k6'),
    ('Boring', '"boring company"', 'k7'),
    ('SolarCity', 'solarcity|"solar city"', 'k5'),
]

# (中文名, 英文名, 查询, 一句话身份)
PEOPLE = [
    ('特朗普', 'Donald Trump', 'trump', '美国总统'),
    ('拜登', 'Joe Biden', 'biden', '美国前总统'),
    ('奥巴马', 'Barack Obama', 'obama', '美国前总统'),
    ('普京', 'Vladimir Putin', 'putin', '俄罗斯总统'),
    ('万斯', 'JD Vance', '"jd vance"|"j.d. vance"|"senator vance"|"vice president vance"', '美国副总统'),
    ('哈里斯', 'Kamala Harris', 'kamala', '美国前副总统'),
    ('肯尼迪', 'JFK / RFK Jr.', 'kennedy|rfk', '肯尼迪家族'),
    ('比尔·盖茨', 'Bill Gates', '"bill gates"', '微软创始人'),
    ('贝索斯', 'Jeff Bezos', 'bezos', '亚马逊、蓝色起源创始人'),
    ('乔布斯', 'Steve Jobs', '"steve jobs"', '苹果创始人'),
    ('拉里·佩奇', 'Larry Page', '"larry page"', '谷歌创始人、昔日好友'),
    ('扎克伯格', 'Mark Zuckerberg', 'zuckerberg', 'Meta 创始人'),
    ('奥特曼', 'Sam Altman', 'altman', 'OpenAI CEO'),
    ('哈萨比斯', 'Demis Hassabis', 'hassabis|demis', 'DeepMind 创始人'),
    ('布兰森', 'Richard Branson', 'branson', '维珍集团创始人'),
    ('巴菲特', 'Warren Buffett', 'buffett', '投资家'),
    ('肖特维尔', 'Gwynne Shotwell', 'shotwell|gwynne', 'SpaceX 总裁'),
    ('彼得·蒂尔', 'Peter Thiel', 'thiel', 'PayPal 联合创始人'),
    ('爱迪生', 'Thomas Edison', 'edison', '发明家'),
    ('尼古拉·特斯拉', 'Nikola Tesla', '"nikola tesla"', '发明家，特斯拉公司名字的来源'),
    ('爱因斯坦', 'Albert Einstein', 'einstein', '物理学家'),
    ('习近平', 'Xi Jinping', '"xi jinping"|"president xi"', '中国国家主席'),
]

# (中文书名, 英文书名, 作者, 查询, 一句话)
BOOKS = [
    ('银河系漫游指南', "The Hitchhiker's Guide to the Galaxy", '道格拉斯·亚当斯', 'hitchhiker|"douglas adams"',
     '少年时期帮他走出存在主义危机：问对问题比找到答案更难'),
    ('基地', 'Foundation', '阿西莫夫', '"foundation series"|asimov', '文明衰落后如何缩短黑暗时代，SpaceX 的精神源头之一'),
    ('严厉的月亮', 'The Moon Is a Harsh Mistress', '海因莱因', 'heinlein|"harsh mistress"', '月球殖民地独立的故事，他心目中最好的海因莱因'),
    ('文明系列', 'The Culture series', '伊恩·M·班克斯', '"iain banks"|"culture series"|"player of games"|"iain m banks"',
     '他认为最接近「AI 与人类共处的美好未来」的描写'),
    ('指环王', 'The Lord of the Rings', '托尔金', '"lord of the rings"|tolkien', '小时候读过很多遍：英雄总想拯救世界'),
    ('富兰克林传', 'Benjamin Franklin: An American Life', '艾萨克森', '"benjamin franklin"|"ben franklin"', '他最敬佩的人之一：科学家、创业者、政治家'),
    ('一九八四', 'Nineteen Eighty-Four', '奥威尔', 'orwell|orwellian', '谈言论自由和审查时最常引用'),
    ('2001 太空漫游', '2001: A Space Odyssey', '阿瑟·克拉克', '"space odyssey"|"arthur c. clarke"|"arthur clarke"', 'HAL 9000：AI 被要求说谎的危险'),
    ('文明的故事', 'The Story of Civilization', '威尔·杜兰特', '"will durant"|"lessons of history"|"story of civilization"',
     '十一卷本世界史，他劝人读历史时常提；还有精简版《历史的教训》'),
    ('生命 3.0', 'Life 3.0', '泰格马克', 'tegmark|"life 3.0"', '作者泰格马克创办了他资助的「未来生命研究所」'),
]


def _sent_with(text, groups, lo=40, hi=220):
    best = None
    for s in re.split(r'(?<=[.?!])\s+', text):
        if not (lo <= len(s) <= hi) or '[' in s:
            continue
        seq = tok_seq(s)
        if matches(groups, seq, set(seq)):
            if best is None or abs(len(s) - 120) < abs(len(best) - 120):
                best = s
    return best


def mention_stats(docs, items, quality=None, want_examples=0):
    """items: [(key, query)]。返回 {cols, totals, rows: [{n, counts, rate, docs, ex}]}，统计口径与 topic_trends 相同（按段落）。"""
    years = sorted({int(d[:4]) for _, d, _, _ in docs if d and d[:4].isdigit()})
    cols = [bucket(YEAR_MIN - 1)] + [str(y) for y in range(YEAR_MIN, max(years) + 1)]
    totals = {c: 0 for c in cols}
    comp = [compile_query(q) for _, q in items]
    rows = [{'key': k, 'q': q, 'n': 0, 'counts': {c: 0 for c in cols}, 'docs': set(), 'ex': []} for k, q in items]
    for slug, d, zh, paras in docs:
        if not d or not d[:4].isdigit():
            continue
        c = bucket(int(d[:4]))
        qv = quality(slug) if quality else 0
        for k, (sec, text) in enumerate(paras):
            totals[c] += 1
            seq = tok_seq(text)
            sset = set(seq)
            for i, g in enumerate(comp):
                if matches(g, seq, sset):
                    r = rows[i]
                    r['n'] += 1
                    r['counts'][c] += 1
                    r['docs'].add(slug)
                    if want_examples and len(r['ex']) < 80:
                        s = _sent_with(text, g)
                        if s:
                            r['ex'].append({'q': qv, 'slug': slug, 'zh': zh, 'd': d, 'k': k, 'sec': sec, 's': s})
    for r in rows:
        r['rate'] = {c: (r['counts'][c] * 1000 / totals[c] if totals[c] else 0) for c in cols}
        r['docs'] = len(r['docs'])
        if want_examples:
            r['ex'].sort(key=lambda e: (-e['q'], abs(len(e['s']) - 120)))
            seen, picked = set(), []
            for e in r['ex']:
                if e['slug'] in seen:
                    continue
                seen.add(e['slug'])
                picked.append(e)
                if len(picked) >= want_examples:
                    break
            r['ex'] = picked
    return {'cols': cols, 'totals': totals, 'rows': rows}


def _ep_href(e, hl):
    from urllib.parse import urlencode
    q = {'p': e['k']}
    if e['sec'] is not None:
        q['t'] = e['sec']
    if hl:
        q['hl'] = hl
    return f'/ep/{e["slug"]}/?{urlencode(q)}'


def _hl(s, q):
    words = sorted({w for w in re.findall(r'[a-z0-9.]+', q.lower()) if len(w) > 2}, key=len, reverse=True)
    out = esc(s)
    if words:
        out = re.sub(r'(?i)\b(' + '|'.join(re.escape(w) for w in words) + r')\w*', lambda m: f'<mark>{m.group(0)}</mark>', out)
    return out


def attention_html(docs):
    """每年提到各家公司的段落，按公司拆成 100% 堆叠柱：看注意力怎么在公司之间转移。"""
    st = mention_stats(docs, [(zh, q) for zh, q, _ in COMPANIES])
    cols = [c for c in st['cols'] if not c.startswith('≤')]
    out = []
    for c in cols:
        tot = sum(r['counts'][c] for r in st['rows'])
        segs = ''.join(f'<i class="{COMPANIES[i][2]}" style="height:{r["counts"][c] * 100 / tot:.2f}%"></i>'
                       for i, r in enumerate(st['rows']) if tot and r['counts'][c])
        tip = f'{c} 年：' + '；'.join(f'{r["key"]} {r["counts"][c] * 100 / tot:.0f}%' for r in st['rows'] if tot and r['counts'][c])
        out.append(f'<div class="yb-col" title="{esc(tip)}" aria-label="{esc(tip)}"><div class="yb-stack at-stack">{segs}</div>'
                   f'<span class="yb-y{" odd" if int(c) % 2 else ""}">{c[2:]}</span></div>')
    legend = ''.join(f'<a href="/search/?q={esc(_q(q))}"><i class="lg {k}"></i>{esc(zh)}</a>' for zh, q, k in COMPANIES)
    return f'<div class="yb-legend at-legend">{legend}</div><div class="yb at" role="img" aria-label="各公司被提及的占比，按年份">{"".join(out)}</div>'


def _spark(vals, w=120, h=26):
    mx = max(vals) or 1
    n = len(vals)
    pts = ' '.join(f'{i * w / (n - 1):.1f},{h - 2 - v / mx * (h - 4):.1f}' for i, v in enumerate(vals))
    return f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="{pts}"/></svg>'


def people_html(docs):
    st = mention_stats(docs, [(p[0], p[2]) for p in PEOPLE])
    cols = [c for c in st['cols'] if not c.startswith('≤')]
    rows = sorted(zip(PEOPLE, st['rows']), key=lambda x: -x[1]['n'])
    mx = rows[0][1]['n'] or 1
    out = []
    for (zh, en, q, who), r in rows:
        if r['n'] < 5:
            continue
        peak = max(cols, key=lambda c: r['rate'][c])
        out.append(f'<li><a href="/search/?q={esc(_q(q))}"><span class="pp-n"><b>{esc(zh)}</b><small lang="en">{esc(en)}</small></span>'
                   f'<span class="pp-who">{esc(who)}</span>'
                   f'<span class="hb-bar"><i style="width:{r["n"] / mx * 100:.1f}%"></i></span><span class="hb-n">{r["n"]:,}</span>'
                   f'{_spark([r["rate"][c] for c in cols])}<span class="pp-peak">{peak} 最多</span></a></li>')
    return f'<ol class="pp">{"".join(out)}</ol><p class="ins-note">数字是提到此人的文稿段落数（含主持人和提问者的话），小折线是 {cols[0]}–{cols[-1]} 每年的热度。点一行去看原话。</p>'


def books_html(docs, quality):
    st = mention_stats(docs, [(b[0], b[3]) for b in BOOKS], quality=quality, want_examples=8)
    out = []
    for b, r in sorted(zip(BOOKS, st['rows']), key=lambda x: -x[1]['n']):
        if not r['n'] or not r['ex']:
            continue
        zh, en, au, q, note = b
        key = q.split('|')[0].strip('"').lower()
        e = next((x for x in r['ex'] if key in x['s'].lower() and not x['s'].endswith('?')), r['ex'][0])
        hl = ' '.join(w for w in re.findall(r'[a-z]+', q.split('|')[0].lower()) if len(w) > 2)
        ts = e['sec'] is not None
        out.append(f'''<li class="bk">
  <div class="bk-cover" aria-hidden="true"><b>{esc(zh)}</b><small>{esc(au)}</small></div>
  <div class="bk-body"><div class="bk-h"><b>《{esc(zh)}》</b><span lang="en">{esc(en)}</span></div>
    <p class="bk-note">{esc(note)}</p>
    <a class="bk-ex" href="{esc(_ep_href(e, hl))}"><span class="ph-s" lang="en">{_hl(e["s"], q)}</span><span class="ph-src">{"▶ " if ts else ""}{esc((e["d"] or "")[:4])} · {esc(e["zh"])}</span></a>
    <a class="bk-more" href="/search/?q={esc(_q(q))}">{r["docs"]} 场视频里提到过 →</a></div>
</li>''')
    return f'<ol class="bk-list">{"".join(out)}</ol>'


_YR = re.compile(r'(?<![\d$,.])(20[1-9]\d|2100)(?![\d,])')


def future_years(docs, quality):
    """他说话时提到的「未来年份」：只算比视频年份晚的年份。"""
    from collections import defaultdict
    cnt = defaultdict(int)
    gaps = defaultdict(list)
    ex = defaultdict(list)
    for slug, d, zh, paras in docs:
        if not d or not d[:4].isdigit():
            continue
        y0 = int(d[:4])
        qv = quality(slug)
        for k, (sec, text) in enumerate(paras):
            for s in re.split(r'(?<=[.?!])\s+', text):
                for m in set(_YR.findall(s)):
                    t = int(m)
                    if t <= y0:
                        continue
                    cnt[t] += 1
                    gaps[t].append(t - y0)
                    if 40 <= len(s) <= 200 and not s.rstrip().endswith('?') and len(ex[t]) < 40:
                        ex[t].append({'q': qv, 'slug': slug, 'zh': zh, 'd': d, 'k': k, 'sec': sec, 's': s, 'g': t - y0,
                                      'fw': bool(_FWD.search(s)), 'nar': bool(_NARR.search(s))})
    return cnt, gaps, ex


# 例句要像他本人在展望：第一人称 + 将来时；旁白、转述（he said / in a 2015 discussion）往后排
_FWD = re.compile(r"\b(I think|I'd|I'll|we'll|we will|we're going to|going to|gonna|expect|hope|probably|maybe|by (?:the end of )?(?:19|20)\d\d)\b", re.I)
_NARR = re.compile(r"\b(he|his|him|she|says|said|musk|elon|discussion|described|according|do you think|you think)\b|\bin an? (?:19|20)\d\d\b"
                   r"|AIDS related", re.I)  # 最后一条：转述援助报告的数字，不是他的预测


def future_html(docs, quality):
    cnt, gaps, ex = future_years(docs, quality)
    if not cnt:
        return ''
    total = sum(cnt.values())
    lo, hi = 2010, 2100
    decades = list(range(lo, hi + 1, 10))
    mx = max(cnt.values())
    bars = []
    for y in range(lo, hi + 1):
        n = cnt.get(y, 0)
        lab = f'<span class="fy-y">{y}</span>' if y % 10 == 0 else ''
        tip = f'{y} 年：被提到 {n} 次'
        bars.append(f'<a class="fy-b{" on" if n >= mx * .25 else ""}" href="/search/?q={y}" title="{tip}" aria-label="{tip}">'
                    f'<i style="height:{max(n / mx * 100, 1 if n else 0):.1f}%"></i>{lab}</a>')
    # 卡片只挑「远期目标」：说的时候离那一年至少还有 3 年
    med = {y: sorted(g)[len(g) // 2] for y, g in gaps.items()}
    def best(y):
        es = sorted(ex[y], key=lambda e: (e['nar'], -e['fw'], e['g'] < 2, -e['q'], abs(len(e['s']) - 110)))
        return es[0] if es and not es[0]['nar'] else None
    top = [y for y in sorted(cnt, key=lambda y: -cnt[y]) if med[y] >= 3 and cnt[y] >= 10 and best(y)][:6]
    cards = []
    for y in sorted(top):
        e = best(y)
        if e:
            s = re.sub(r'^(?:(?:and|then|so|um|uh)[,\s]+)+', '', e['s'], flags=re.I)
            e = dict(e, s=s[:1].upper() + s[1:])
        g = med[y]
        ex_html = (f'<a class="bk-ex" href="{esc(_ep_href(e, str(y)))}"><span class="ph-s" lang="en">{_hl(e["s"], str(y))}</span>'
                   f'<span class="ph-src">{esc(e["d"][:4])} · {esc(e["zh"])}</span></a>') if e else ''
        cards.append(f'<li class="fy-c"><div class="fy-h"><b>{y}</b><span>提到 {cnt[y]} 次 · 说的时候距那年中位数 {g} 年</span></div>{ex_html}</li>')
    first = max(cnt, key=lambda y: cnt[y])
    return (f'<div class="fy" role="img" aria-label="被提到的未来年份分布">{"".join(bars)}</div>'
            f'<p class="ins-note">共 {total:,} 次提到「比当时更晚的年份」。被提得最多的是 <b>{first}</b> 年。点柱子搜这一年的原话。下面是被提到最多的远期年份（说的时候离那一年至少还有 3 年）。</p>'
            f'<ol class="fy-list">{"".join(cards)}</ol>')
