#!/usr/bin/env python3
"""马斯克全访谈（elon.qiaomu.ai）MCP Server，纯 Python 标准库。

数据源：
  * ELON_SITE_DIR 指向构建好的 site/ 目录时，优先读本地索引/文稿/精读（离线可用）；
  * 否则走线上 https://elon.qiaomu.ai 的静态索引，结构化专题数据用随包快照；
  * ELON_SITE_URL 可覆盖线上地址，ELON_NO_TRANSLATE=1 可关闭在线翻译。

协议：stdio JSON-RPC 2.0（MCP tools）。
"""

from __future__ import annotations

import bisect
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVER_NAME = "elon-musk-archive"
SERVER_VERSION = "1.0.0"
DATA_DIR = Path(__file__).resolve().parent / "data"
SITE_URL = os.environ.get("ELON_SITE_URL", "https://elon.qiaomu.ai").rstrip("/")
HTTP_TIMEOUT = float(os.environ.get("ELON_HTTP_TIMEOUT", "20"))
NO_TRANSLATE = os.environ.get("ELON_NO_TRANSLATE", "") == "1"
MCP_TOKEN = os.environ.get("ELON_MCP_TOKEN", "").strip()  # 留空则公开可读
_RAW_SITE_DIR = os.environ.get("ELON_SITE_DIR", "").strip()
SITE_DIR = Path(_RAW_SITE_DIR).expanduser() if _RAW_SITE_DIR else None

_CACHE: dict[str, bytes] = {}
_TR_CACHE: dict[tuple[str, str], list[str]] = {}

STOP = set("""
a an the and or but if so of to in on at by for with from as into about than then that this these those there here
is are was were be been being am do does did done have has had having will would shall should can could may might must
i me my mine we us our ours you your yours he him his she her hers they them their theirs it its itself
what which who whom whose when where why how not no nor yes yeah yep okay ok oh um uh hmm well just like
very really also too only even still all any some such own same other each more most much many few
up down out off over under again further once very s t don isn didn doesn wasn aren weren won wouldn couldn
shouldn haven hasn hadn ll re ve d m o y let get got gonna gotta wanna going thing kind sort lot
""".split())

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_ASCII = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]+")
_ZH_STOP_MULTI = [
    "马斯克", "埃隆", "怎么看", "怎么样", "怎么", "如何", "为什么", "为何", "什么", "是否", "有没有",
    "关于", "对于", "看法", "观点", "认为", "觉得", "谈谈", "说过", "哪些", "多少", "这个", "那个",
    "一下", "一些", "可以", "能否", "到底",
]
_ZH_STOP_EDGE = "的了吗呢和与及对在是会要有吧啊么呀把被让给从向跟就都也还"


# ---------------------------------------------------------------- 基础 I/O
def _url(path: str) -> str:
    return path if path.startswith(("http://", "https://")) else f"{SITE_URL}/{path.lstrip('/')}"


def fetch_bytes(path: str) -> bytes:
    url = _url(path)
    if url not in _CACHE:
        req = urllib.request.Request(url, headers={"User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            _CACHE[url] = resp.read()
    return _CACHE[url]


def fetch_json(path: str):
    return json.loads(fetch_bytes(path).decode("utf-8"))


def local_file(rel: str) -> Path | None:
    if SITE_DIR:
        p = SITE_DIR / rel
        if p.is_file():
            return p
    return None


def source_mode() -> str:
    return "local" if SITE_DIR else "remote+bundled"


def load_json(rel: str, bundled_name: str | None = None):
    p = local_file(rel)
    if p:
        return json.loads(p.read_text(encoding="utf-8"))
    if bundled_name:
        b = DATA_DIR / bundled_name
        if b.is_file():
            return json.loads(b.read_text(encoding="utf-8"))
    try:
        return fetch_json(rel)
    except Exception:
        if bundled_name:
            b = DATA_DIR / bundled_name
            if b.is_file():
                return json.loads(b.read_text(encoding="utf-8"))
        raise


def load_episodes() -> dict:
    return load_json("data/episodes.json", "episodes.json")


def load_corpus(name: str) -> dict:
    return load_json(f"corpus/{name}.json", f"{name}.json")


def load_glossary() -> dict:
    try:
        return json.loads((DATA_DIR / "glossary.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------- 分词与索引
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("\u2019", "'")


def stem(w: str) -> str:
    if "'" in w:
        w = w.split("'", 1)[0]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def indexable(raw: str, w: str) -> bool:
    return not (w in STOP or raw in STOP) and (len(w) >= 2 or w.isdigit())


def tokens(text: str) -> list[dict]:
    out = []
    t = norm(text)
    for m in _TOKEN.finditer(t):
        raw = m.group(0)
        if indexable(raw, stem(raw)):
            out.append({"s": m.start(), "e": m.end(), "raw": raw, "w": stem(raw)})
    return out


def fnv1a_ascii(s: str) -> int:
    h = 0x811C9DC5
    for b in s.encode("ascii", "ignore"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def fnv1a_utf8(s: str) -> int:
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


class SearchIndex:
    """复用站点 tools/search_index.py 生成的倒排索引，本地/远程通吃。"""

    def __init__(self, kind: str):
        self.kind = kind  # 'en' | 'zh'
        if kind == "en":
            self.prefix, self.meta_file, self.para_dir = "i", "meta.json", "p"
            self.hash = fnv1a_ascii
        else:
            self.prefix, self.meta_file, self.para_dir = "z", "zmeta.json", "zp"
            self.hash = fnv1a_utf8
        self._meta = None
        self._shards: dict[int, dict] = {}
        self._paras: dict[int, list] = {}

    @property
    def meta(self) -> dict:
        if self._meta is None:
            self._meta = load_json(f"data/search/{self.meta_file}")
        return self._meta

    def postings(self, term: str) -> list[int]:
        m = self.meta
        shard = self.hash(term) % int(m.get("shards", 256))
        if shard not in self._shards:
            rel = f"data/search/{self.prefix}/{shard:03d}.json"
            p = local_file(rel)
            self._shards[shard] = json.loads(p.read_text(encoding="utf-8")) if p else fetch_json(rel)
        deltas = self._shards[shard].get(term) or []
        out, g = [], 0
        for d in deltas:
            g += d
            out.append(g)
        return out

    def para(self, k: int) -> list:
        if k not in self._paras:
            rel = f"data/search/{self.para_dir}/{k}.json"
            p = local_file(rel)
            self._paras[k] = json.loads(p.read_text(encoding="utf-8")) if p else fetch_json(rel)
        return self._paras[k]

    def ep_of(self, g: int) -> int:
        off = self.meta["off"] if "off" in self.meta else [e[1] for e in self.meta["eps"]]
        return max(0, bisect.bisect_right(off, g) - 1)


_EN_INDEX: SearchIndex | None = None
_ZH_INDEX: SearchIndex | None = None


def en_index() -> SearchIndex:
    global _EN_INDEX
    if _EN_INDEX is None:
        _EN_INDEX = SearchIndex("en")
    return _EN_INDEX


def zh_index() -> SearchIndex:
    global _ZH_INDEX
    if _ZH_INDEX is None:
        _ZH_INDEX = SearchIndex("zh")
    return _ZH_INDEX


# ---------------------------------------------------------------- 查询解析
def translate_text(text: str, tl: str) -> list[str]:
    if NO_TRANSLATE or not text or len(text) > 60:
        return []
    key = (tl, text)
    if key in _TR_CACHE:
        return _TR_CACHE[key]
    try:
        url = f"{SITE_URL}/api/tr?tl={urllib.parse.quote(tl)}&q={urllib.parse.quote(text)}"
        j = json.loads(fetch_bytes(url).decode("utf-8"))
        out = []
        if isinstance(j, list) and j and isinstance(j[0], list):
            out.append("".join(str(x[0]) for x in j[0] if isinstance(x, list) and x and x[0]).strip())
        if isinstance(j, list) and len(j) > 1 and isinstance(j[1], dict):
            for entry in j[1].values():
                if isinstance(entry, list):
                    out.extend(str(x[0]) for x in entry if isinstance(x, list) and x and isinstance(x[0], str))
        result = []
        for x in out:
            x = re.sub(r"[。．.!！?？,，、\s]+$", "", x.strip())
            if x and x not in result:
                result.append(x)
        _TR_CACHE[key] = result[:4]
    except Exception:
        _TR_CACHE[key] = []
    return _TR_CACHE[key]


def _alt_from_gloss(value: str) -> dict | None:
    v = value.strip()
    phrase = v.startswith('"') and v.endswith('"')
    if phrase:
        v = v[1:-1]
    seq = [stem(x) for x in _TOKEN.findall(norm(v)) if indexable(x, stem(x))]
    return {"terms": seq, "phrase": phrase} if seq else None


def split_raw_groups(q: str) -> list[list[str]]:
    """空格分隔为「且」，| 分隔为「或」，引号内不拆。"""
    groups, cur, buf, quoted, i = [], [], "", False, 0
    while i < len(q):
        c = q[i]
        if c in '"“”':
            quoted = not quoted
            buf += '"'
            i += 1
            continue
        if not quoted and (c.isspace() or c == "|"):
            if buf:
                cur.append(buf)
                buf = ""
            if c.isspace():
                if cur:
                    groups.append(cur)
                    cur = []
            i += 1
            continue
        buf += c
        i += 1
    if buf:
        cur.append(buf)
    if cur:
        groups.append(cur)
    return groups


def build_alt(raw: str, glossary: dict, rev: dict, budget: list[int]) -> dict:
    """一个候选：en_groups 为英文检索条件组，zh_terms 为中文精读检索词。"""
    alt = {"src": raw, "en_groups": [], "zh_terms": []}
    quoted = raw.startswith('"') and raw.endswith('"') and len(raw) >= 2
    s = raw[1:-1] if quoted else raw
    if not s.strip():
        return alt
    if not _CJK.search(s):
        w = stem(norm(s))
        if indexable(norm(s), w):
            alt["en_groups"].append({"terms": [w], "phrase": quoted})
        low = norm(s).strip()
        if low and low not in STOP:
            alt["zh_terms"].append(low)
            if low in rev:
                alt["zh_terms"].append(rev[low])
            elif budget[0] > 0 and re.search(r"[a-z]", low):
                budget[0] -= 1
                alt["zh_terms"].extend(x for x in translate_text(low, "zh-CN") if _CJK.search(x))
        return alt

    # 中文：优先命中内置概念词表，未命中部分剥掉问句虚词后走在线翻译
    run = s
    miss = ""
    pos = 0

    def flush_miss():
        nonlocal miss
        if not miss:
            return
        text = miss
        for w in _ZH_STOP_MULTI:
            text = text.replace(w, " ")
        parts = []
        for part in text.split():
            a, b = 0, len(part)
            while a < b and part[a] in _ZH_STOP_EDGE:
                a += 1
            while b > a and part[b - 1] in _ZH_STOP_EDGE:
                b -= 1
            if b - a >= 2:
                parts.append(part[a:b])
        for part in parts:
            alt["zh_terms"].append(part)
            if budget[0] > 0:
                budget[0] -= 1
                for en in translate_text(part, "en"):
                    g = _alt_from_gloss(en)
                    if g:
                        alt["en_groups"].append(g)
        miss = ""

    max_len = max((len(k) for k in glossary), default=1)
    while pos < len(run):
        hit = None
        for L in range(min(max_len, len(run) - pos), 0, -1):
            cand = run[pos:pos + L]
            if cand in glossary:
                hit = cand
                break
        if hit:
            flush_miss()
            alt["zh_terms"].append(hit)
            for en in glossary[hit]:
                g = _alt_from_gloss(en)
                if g:
                    alt["en_groups"].append(g)
                plain = en.strip('"')
                if re.fullmatch(r"[a-z0-9]+", plain, re.I):
                    alt["zh_terms"].append(plain.lower())
            pos += len(hit)
        else:
            miss += run[pos]
            pos += 1
    flush_miss()
    return alt


def parse_query(q: str) -> list[list[dict]]:
    glossary = load_glossary()
    rev = {}
    for zh, alts in glossary.items():
        for a in alts:
            plain = a.strip('"').lower()
            rev.setdefault(plain, zh)
    budget = [8]
    concepts = []
    for group in split_raw_groups(q):
        alts = [build_alt(tok, glossary, rev, budget) for tok in group]
        alts = [a for a in alts if a["en_groups"] or a["zh_terms"]]
        if alts:
            concepts.append(alts)
    return concepts


# ---------------------------------------------------------------- 检索执行
def union_sets(a: set[int], b: set[int]) -> set[int]:
    return a | b


def postings_for_alt(index: SearchIndex, alt: dict) -> set[int]:
    out: set[int] = set()
    for group in alt["en_groups"]:
        cur: set[int] | None = None
        for term in group["terms"]:
            p = set(index.postings(term))
            cur = p if cur is None else cur & p
            if not cur:
                break
        if cur:
            out = union_sets(out, cur)
    return out


def verify_en(text: str, alt: dict) -> list[tuple[int, int]] | None:
    tks = tokens(text)
    ranges = []
    for group in alt["en_groups"]:
        seq = group["terms"]
        if not seq:
            continue
        if group["phrase"]:
            found = False
            for i in range(len(tks) - len(seq) + 1):
                if [t["w"] for t in tks[i:i + len(seq)]] == seq:
                    ranges.append((tks[i]["s"], tks[i + len(seq) - 1]["e"]))
                    found = True
            if not found:
                return None
        else:
            for term in seq:
                matched = [t for t in tks if t["w"] == term]
                if not matched:
                    return None
                ranges.extend((t["s"], t["e"]) for t in matched)
    return ranges or None


def verify_zh(text: str, alt: dict) -> list[tuple[int, int]] | None:
    low = norm(text)
    ranges = []
    for s in alt["zh_terms"]:
        if not s:
            continue
        if re.fullmatch(r"[a-z0-9]+", s):
            found = list(re.finditer(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", low))
        else:
            found = list(re.finditer(re.escape(s), low))
        if not found:
            return None
        ranges.extend((m.start(), m.end()) for m in found)
    return ranges or None


def snippet(text: str, ranges: list[tuple[int, int]], width: int) -> str:
    if not ranges:
        return text[:width] + ("…" if len(text) > width else "")
    first = ranges[0][0]
    a = max(0, first - int(width * 0.3))
    b = min(len(text), a + width)
    a = max(0, b - width)
    out, pos = ("…" if a else ""), a
    for s, e in sorted(ranges):
        if e <= pos or s >= b:
            continue
        s2, e2 = max(s, pos), min(e, b)
        out += text[pos:s2] + "**" + text[s2:e2] + "**"
        pos = e2
    out += text[pos:b] + ("…" if b < len(text) else "")
    return out


def mmss(sec) -> str:
    if sec is None or sec == "":
        return "—"
    n = int(float(sec))
    h, m, s = n // 3600, (n % 3600) // 60, n % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def run_search(index: SearchIndex, concepts: list[list[dict]], kind: str,
               year_from: str, year_to: str, limit: int) -> list[dict]:
    meta = index.meta
    sets = []
    for alts in concepts:
        cur: set[int] = set()
        for alt in alts:
            cur = union_sets(cur, postings_for_alt(index, alt))
        if not cur:
            return []
        sets.append(cur)
    hits: set[int] = set.intersection(*sets) if sets else set()
    gids = sorted(hits)
    if len(gids) > 1500:  # 热门词候选过多，均匀抽样，避免远程模式拉取全站段落
        step = len(gids) / 1500
        gids = [gids[int(i * step)] for i in range(1500)]

    verify = verify_en if kind == "en" else verify_zh
    all_alts = [a for alts in concepts for a in alts]
    results = []
    for g in gids:
        if len(results) >= limit * 4:
            break
        k = index.ep_of(g)
        ep = meta["eps"][k]
        date = str(ep[2] or "")
        if year_from and date[:4] < str(year_from)[:4]:
            continue
        if year_to and date[:4] > str(year_to)[:4]:
            continue
        para = index.para(k)
        local = g - ep[1]
        if not (0 <= local < len(para)):
            continue
        row = para[local]
        if kind == "en":
            sec = row[0] if isinstance(row, list) else None
            text = row[1] if isinstance(row, list) else str(row)
        else:
            sec = None
            text = row if isinstance(row, str) else (row[1] if isinstance(row, list) else str(row))
        ranges = None
        for alt in all_alts:
            ranges = verify(text, alt)
            if ranges:
                break
        if not ranges:
            continue
        score = sum(1 for a in concepts if any(verify(text, alt) for alt in a))
        score = score * 100 + min(len(ranges), 8) * 5 - min(len(text), 1500) / 500
        results.append({
            "slug": ep[0], "title_zh": ep[3], "title_en": ep[4], "date": date,
            "kind": ep[5] or "", "paragraph": local, "timestamp": sec,
            "score": round(score, 2), "snippet": snippet(text, ranges, 320 if kind == "en" else 260),
        })
    results.sort(key=lambda x: (-x["score"], x["date"], x["slug"]))
    return results[:limit]


# ---------------------------------------------------------------- MCP 工具实现
def tool_search(args: dict) -> dict:
    q = (args.get("query") or "").strip()
    if not q:
        raise ValueError("query 不能为空")
    mode = args.get("mode", "all")
    limit = max(1, min(int(args.get("limit", 10)), 30))
    yf = str(args.get("year_from", "") or "")
    yt = str(args.get("year_to", "") or "")
    if mode not in ("all", "transcript", "deepread"):
        raise ValueError("mode 只能是 all / transcript / deepread")
    concepts = parse_query(q)
    if not concepts:
        raise ValueError("没有可用的检索词，试试更具体的中英文关键词")
    out: dict = {"query": q, "parsed_concepts": [a["src"] for alts in concepts for a in alts][:12]}
    if mode in ("all", "transcript"):
        out["transcripts"] = run_search(en_index(), concepts, "en", yf, yt, limit)
    if mode in ("all", "deepread"):
        out["deepreads"] = run_search(zh_index(), concepts, "zh", yf, yt, limit)
    out["note"] = "英文文稿引自 silicon-valley.tech；中文精读为本站 AI 改写，非逐字翻译。"
    return out


def find_episode_index(slug: str) -> tuple[int, list]:
    meta = en_index().meta
    for k, ep in enumerate(meta["eps"]):
        if ep[0] == slug:
            return k, ep
    raise ValueError(f"找不到视频 slug：{slug}（可用 list_episodes 查）")


def tool_get_transcript(args: dict) -> dict:
    slug = (args.get("slug") or "").strip()
    if not slug:
        raise ValueError("slug 不能为空")
    k, ep = find_episode_index(slug)
    paras = en_index().para(k)
    q = (args.get("query") or "").strip()
    if q:
        concepts = parse_query(q)
        paras = [(i, row) for i, row in enumerate(paras)
                 if any(verify_en(row[1] if isinstance(row, list) else str(row), alt) for alt in
                        [a for alts in concepts for a in alts])]
    else:
        paras = list(enumerate(paras))
    offset = max(0, int(args.get("offset", 0)))
    limit = max(1, min(int(args.get("limit", 40)), 500))
    rows = []
    for i, row in paras[offset:offset + limit]:
        sec = row[0] if isinstance(row, list) else None
        text = row[1] if isinstance(row, list) else str(row)
        rows.append({"paragraph": i, "timestamp": sec, "timestamp_text": mmss(sec), "text": text,
                     "url": f"{SITE_URL}/ep/{slug}/?p={i}" + (f"&t={int(float(sec))}" if sec is not None else "")})
    return {"slug": slug, "title_zh": ep[3], "title_en": ep[4], "date": ep[2],
            "total_matched": len(paras), "offset": offset, "count": len(rows),
            "has_more": offset + limit < len(paras), "paragraphs": rows,
            "source": "silicon-valley.tech 公开语料，经本站按语句合并分段"}


def tool_get_deepread(args: dict) -> dict:
    slug = (args.get("slug") or "").strip()
    if not slug:
        raise ValueError("slug 不能为空")
    p = local_file(f"ep/{slug}/index.md")
    if p:
        text = p.read_text(encoding="utf-8")
    else:
        text = fetch_bytes(f"/ep/{slug}/index.md").decode("utf-8")
    offset = max(0, int(args.get("offset_chars", 0)))
    max_chars = max(500, min(int(args.get("max_chars", 24000)), 100000))
    cut = text[offset:offset + max_chars]
    return {"slug": slug, "url": f"{SITE_URL}/ep/{slug}/", "markdown_url": f"{SITE_URL}/ep/{slug}/index.md",
            "offset": offset, "total_chars": len(text), "truncated": offset + max_chars < len(text),
            "text": cut, "note": "AI 深度改写，不是逐字翻译；引用原话请用 get_transcript 核对英文文稿。"}


def tool_list_episodes(args: dict) -> dict:
    items = (load_episodes().get("episodes") or [])
    year = str(args.get("year", "") or "")
    kind = str(args.get("kind", "") or "")
    title = norm(args.get("title_contains", "") or "")
    has_tr = args.get("has_transcript")
    has_zh = args.get("has_deepread")
    if year:
        items = [e for e in items if str(e.get("d", "")).startswith(year)]
    if kind:
        items = [e for e in items if kind in str(e.get("k", "") or e.get("kZh", ""))]
    if title:
        items = [e for e in items if title in norm(e.get("t", "")) or title in norm(e.get("zh", ""))]
    if has_tr is not None:
        items = [e for e in items if bool(e.get("tr")) == bool(has_tr)]
    if has_zh is not None:
        try:
            zh_slugs = set((load_json("data/zh-index.json", "zh-index.json").get("slugs") or []))
        except Exception:
            zh_slugs = set()
        items = [e for e in items if (e.get("s") in zh_slugs) == bool(has_zh)]
    total = len(items)
    offset = max(0, int(args.get("offset", 0)))
    limit = max(1, min(int(args.get("limit", 20)), 100))
    rows = []
    for e in items[offset:offset + limit]:
        rows.append({"slug": e.get("s"), "title_en": e.get("t"), "title_zh": e.get("zh", ""),
                     "date": e.get("d", ""), "kind": e.get("k", ""), "channel": e.get("ch", ""),
                     "seconds": e.get("sec", 0), "has_transcript": bool(e.get("tr")),
                     "url": f"{SITE_URL}/ep/{e.get('s')}/"})
    return {"total": total, "offset": offset, "count": len(rows), "episodes": rows}


def tool_get_episode(args: dict) -> dict:
    slug = (args.get("slug") or "").strip()
    if not slug:
        raise ValueError("slug 不能为空")
    items = (load_corpus("videos").get("items") or [])
    row = next((x for x in items if x.get("slug") == slug), None)
    if row is None:
        raise ValueError(f"找不到视频 slug：{slug}")
    result = dict(row)
    try:
        k, _ = find_episode_index(slug)
        result["transcript_paragraphs"] = len(en_index().para(k))
    except Exception:
        result["transcript_paragraphs"] = 0
    return result


def _filter_text(rows: list[dict], q: str, fields: tuple[str, ...]) -> list[dict]:
    if not q:
        return rows
    low = norm(q)
    return [r for r in rows if any(low in norm(r.get(f, "")) for f in fields)]


def tool_get_quotes(args: dict) -> dict:
    rows = (load_corpus("quotes").get("items") or [])
    q = str(args.get("query", "") or "")
    rows = _filter_text(rows, q, ("text_en", "text_zh", "source"))
    kind = str(args.get("kind", "") or "")
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    total = len(rows)
    offset = max(0, int(args.get("offset", 0)))
    limit = max(1, min(int(args.get("limit", 20)), 100))
    return {"total": total, "count": len(rows[offset:offset + limit]), "items": rows[offset:offset + limit]}


def tool_get_predictions(args: dict) -> dict:
    rows = (load_corpus("predictions").get("items") or [])
    q = str(args.get("query", "") or "")
    rows = _filter_text(rows, q, ("claim_zh", "claim_en", "quote", "outcome_zh", "outcome_en", "source"))
    status = str(args.get("status", "") or "")
    if status:
        rows = [r for r in rows if status in (str(r.get("status", "")), str(r.get("status_zh", "")))]
    topic = str(args.get("topic", "") or "")
    if topic:
        rows = [r for r in rows if topic.lower() in norm(r.get("topic", "") + r.get("topic_zh", ""))]
    total = len(rows)
    offset = max(0, int(args.get("offset", 0)))
    limit = max(1, min(int(args.get("limit", 20)), 100))
    return {"total": total, "count": len(rows[offset:offset + limit]), "items": rows[offset:offset + limit]}


def tool_get_themes(args: dict) -> dict:
    rows = (load_corpus("themes").get("items") or [])
    q = str(args.get("query", "") or "")
    rows = _filter_text(rows, q, ("title_zh", "title_en", "intro_zh", "intro_en", "key"))
    return {"total": len(rows), "items": rows}


def tool_site_info(args: dict) -> dict:
    videos = load_corpus("videos")
    quotes = load_corpus("quotes")
    preds = load_corpus("predictions")
    themes = load_corpus("themes")
    return {
        "site": "马斯克全访谈 · elon.qiaomu.ai", "site_url": SITE_URL,
        "data_source": source_mode(),
        "counts": {"videos": videos.get("count"), "quotes": quotes.get("count"),
                   "predictions": preds.get("count"), "themes": themes.get("count")},
        "snapshot_updated": videos.get("updated"),
        "links": {"search": f"{SITE_URL}/search/", "deepreads": f"{SITE_URL}/archive/",
                  "quotes": f"{SITE_URL}/quotes/", "predictions": f"{SITE_URL}/predictions/",
                  "themes": f"{SITE_URL}/themes/", "trends": f"{SITE_URL}/trends/",
                  "stats": f"{SITE_URL}/stats/", "disclaimer": f"{SITE_URL}/disclaimer/"},
        "notes": ["英文逐字文稿来自 silicon-valley.tech 公开档案，本站保留出处链接。",
                  "中文精读是 AI 改写，非官方翻译；逐字引用请核对英文文稿。",
                  "在线模式下查询索引直接读取站点静态文件，专题数据为随包快照。"],
    }


TOOLS = [
    {
        "name": "search",
        "description": "全文检索：在 588 份英文逐字文稿（段落+时间戳）与 586 篇中文精读中查关键词。支持中文直接提问、英文词、空格=且、|=或、\"短语\"=精确匹配。返回带出处链接的段落。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "检索词或自然语言问题，如 '火星 殖民'、'first principles'、'AI risk'"},
            "mode": {"type": "string", "enum": ["all", "transcript", "deepread"], "description": "all=两类都查（默认）", "default": "all"},
            "year_from": {"type": "string", "description": "起始年份，如 2020"},
            "year_to": {"type": "string", "description": "结束年份，如 2025"},
            "limit": {"type": "integer", "description": "每类最多返回条数，1-30，默认 10", "default": 10},
        }, "required": ["query"]},
    },
    {
        "name": "get_transcript",
        "description": "取某一期视频的英文逐字文稿（已合并成段落，带秒级时间戳与跳播深链）；可用 query 在单期内筛选。",
        "inputSchema": {"type": "object", "properties": {
            "slug": {"type": "string", "description": "视频 slug，如 elon-musk-on-zip2-and-the-internet-1998"},
            "query": {"type": "string", "description": "可选：只返回含该词的段落"},
            "offset": {"type": "integer", "description": "段落偏移，默认 0"},
            "limit": {"type": "integer", "description": "返回段数，1-500，默认 40"},
        }, "required": ["slug"]},
    },
    {
        "name": "get_deepread",
        "description": "取某一期视频的中文精读 Markdown 全文（AI 改写）；大文章可用 offset_chars / max_chars 分段读。",
        "inputSchema": {"type": "object", "properties": {
            "slug": {"type": "string", "description": "视频 slug"},
            "offset_chars": {"type": "integer", "description": "字符偏移，默认 0"},
            "max_chars": {"type": "integer", "description": "最多返回字符数，默认 24000"},
        }, "required": ["slug"]},
    },
    {
        "name": "list_episodes",
        "description": "按年份/类型/标题筛选 651 期视频目录，用于定位 slug 和概览。",
        "inputSchema": {"type": "object", "properties": {
            "year": {"type": "string", "description": "年份前缀，如 2024"},
            "kind": {"type": "string", "description": "类型包含，如 访谈 / 发布会"},
            "title_contains": {"type": "string", "description": "标题包含（中英文均可）"},
            "has_transcript": {"type": "boolean", "description": "是否必须有英文文稿"},
            "has_deepread": {"type": "boolean", "description": "是否必须有中文精读"},
            "offset": {"type": "integer", "description": "默认 0"},
            "limit": {"type": "integer", "description": "默认 20，最多 100"},
        }},
    },
    {
        "name": "get_episode",
        "description": "取单期视频的完整元数据：中英标题、日期、类型、时长、是否有文稿/精读、网页与档案出处链接。",
        "inputSchema": {"type": "object", "properties": {
            "slug": {"type": "string", "description": "视频 slug"}
        }, "required": ["slug"]},
    },
    {
        "name": "get_quotes",
        "description": "检索 556 条中英双语语录（可按关键词、类别筛选）。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "中英文关键词"},
            "kind": {"type": "string", "description": "类别，如 wq"},
            "offset": {"type": "integer", "description": "默认 0"},
            "limit": {"type": "integer", "description": "默认 20，最多 100"},
        }},
    },
    {
        "name": "get_predictions",
        "description": "检索带日期的预言/承诺追踪（中英主张、核实结果、状态、来源）。status 可用 kept/late/missed/open 或中文状态。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "中英文关键词"},
            "status": {"type": "string", "description": "状态筛选"},
            "topic": {"type": "string", "description": "主题筛选，如 tesla / spacex / ia"},
            "offset": {"type": "integer", "description": "默认 0"},
            "limit": {"type": "integer", "description": "默认 20，最多 100"},
        }},
    },
    {
        "name": "get_themes",
        "description": "列出 8 大主题的中英介绍、相关段落数与逐年提及热度。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "可选主题关键词"}
        }},
    },
    {
        "name": "site_info",
        "description": "返回站点数据规模、数据源模式、语料快照日期与各专题入口链接；不确定有哪些数据时先调它。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

TOOL_FUNCS = {
    "search": tool_search,
    "get_transcript": tool_get_transcript,
    "get_deepread": tool_get_deepread,
    "list_episodes": tool_list_episodes,
    "get_episode": tool_get_episode,
    "get_quotes": tool_get_quotes,
    "get_predictions": tool_get_predictions,
    "get_themes": tool_get_themes,
    "site_info": tool_site_info,
}


# ---------------------------------------------------------------- MCP 消息循环
def result_text(obj) -> dict:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": False}


def error_text(msg: str) -> dict:
    return {"content": [{"type": "text", "text": f"错误：{msg}"}], "isError": True}


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}
    if mid is None or str(method).startswith("notifications/"):
        return None  # notification
    if method == "initialize":
        client_ver = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": client_ver or "2025-06-18",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        func = TOOL_FUNCS.get(name)
        if not func:
            return {"jsonrpc": "2.0", "id": mid, "result": error_text(f"未知工具 {name}")}
        try:
            if not isinstance(args, dict):
                raise ValueError("arguments 必须是对象")
            return {"jsonrpc": "2.0", "id": mid, "result": result_text(func(args))}
        except Exception as exc:
            print(f"[elon-mcp] {name} failed: {exc!r}", file=sys.stderr, flush=True)
            return {"jsonrpc": "2.0", "id": mid, "result": error_text(str(exc))}
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


# ---------------------------------------------------------------- HTTP（Streamable HTTP）
def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key, Mcp-Session-Id, MCP-Protocol-Version",
    }


class MCPHTTPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = f"{SERVER_NAME}/{SERVER_VERSION}"

    def log_message(self, fmt, *args):
        print(f"[elon-mcp/http] {self.address_string()} {fmt % args}", file=sys.stderr, flush=True)

    def _send(self, status: int, body: bytes = b"", content_type: str = "application/json; charset=utf-8",
              extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in {**_cors_headers(), **(extra or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, obj, extra: dict | None = None):
        self._send(status, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                   extra=extra)

    def _authorized(self) -> bool:
        if not MCP_TOKEN:
            return True
        return (self.headers.get("Authorization") == f"Bearer {MCP_TOKEN}"
                or self.headers.get("X-API-Key") == MCP_TOKEN)

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/health", "/healthz", "/mcp/health"):
            self._json(200, {"status": "ok", "server": SERVER_NAME, "version": SERVER_VERSION,
                             "data_source": source_mode()})
        elif path == "/":
            self._json(200, {"name": SERVER_NAME, "endpoint": "/mcp", "transport": "streamable-http",
                             "site": SITE_URL, "docs": f"{SITE_URL}/mcp/"})
        elif path == "/mcp":
            self._json(405, {"error": "Use POST for MCP JSON-RPC messages"}, {"Allow": "POST, OPTIONS"})
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path != "/mcp":
            self._json(404, {"error": "Not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "Unauthorized"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if size <= 0 or size > 2_000_000:
            self._json(413 if size > 2_000_000 else 400, {"error": "Invalid Content-Length"})
            return
        try:
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
        except Exception as exc:
            self._json(400, {"error": f"Invalid JSON: {exc}"})
            return
        responses = []
        try:
            if isinstance(payload, list):
                responses = [r for r in (handle(m) for m in payload if isinstance(m, dict)) if r is not None]
            elif isinstance(payload, dict):
                r = handle(payload)
                if r is not None:
                    responses.append(r)
            else:
                self._json(400, {"error": "Expected JSON-RPC object or array"})
                return
        except Exception as exc:
            print(f"[elon-mcp/http] handler failed: {exc!r}", file=sys.stderr, flush=True)
            self._json(500, {"error": str(exc)})
            return
        if not responses:  # 纯 notification
            self._send(202)
            return
        obj = responses[0] if len(responses) == 1 else responses
        accept = self.headers.get("Accept", "")
        if "text/event-stream" in accept and "application/json" not in accept:
            body = ("event: message\ndata: " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n\n").encode("utf-8")
            self._send(200, body, content_type="text/event-stream; charset=utf-8")
        else:
            self._json(200, obj)


def run_http(host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), MCPHTTPHandler)
    httpd.daemon_threads = True
    print(f"[elon-mcp] HTTP ready on http://{host}:{port}/mcp | mode={source_mode()} | site={SITE_URL}"
          f" | auth={'on' if MCP_TOKEN else 'off'}", file=sys.stderr, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> None:
    argv = sys.argv[1:]
    if "--http" in argv:
        def arg(flag: str, default: str) -> str:
            return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else default
        run_http(arg("--host", os.environ.get("ELON_HOST", "127.0.0.1")),
                 int(arg("--port", os.environ.get("ELON_PORT", "8791"))))
        return
    print(f"[elon-mcp] ready | mode={source_mode()} | site={SITE_URL}", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            resp = handle(msg) if isinstance(msg, dict) else None
        except Exception as exc:
            print(f"[elon-mcp] bad message: {exc!r}", file=sys.stderr, flush=True)
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
