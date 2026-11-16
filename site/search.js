/* 马斯克全访谈 · 文稿全文检索：倒排分片按需加载，段落级命中，跳到视频对应秒数
   分词 / 词干 / 停用词 / 分片哈希必须与 tools/search_index.py 一致 */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const BASE = '/data/search/';

  const STOP = new Set(`a an the and or but if so of to in on at by for with from as into about than then that this these those there here
is are was were be been being am do does did done have has had having will would shall should can could may might must
i me my mine we us our ours you your yours he him his she her hers they them their theirs it its itself
what which who whom whose when where why how not no nor yes yeah yep okay ok oh um uh hmm well just like
very really also too only even still all any some such own same other each more most much many few
up down out off over under again further once very s t don isn didn doesn wasn aren weren won wouldn couldn
shouldn haven hasn hadn ll re ve d m o y let get got gonna gotta wanna going thing kind sort lot`.split(/\s+/).filter(Boolean));

  const norm = (s) => (s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\u2019/g, "'");
  function stem(w) {
    const a = w.indexOf("'");
    if (a >= 0) w = w.slice(0, a);
    if (w.length > 4 && w.endsWith('ies')) return w.slice(0, -3) + 'y';
    if (w.length > 3 && w.endsWith('s') && !/(ss|us|is)$/.test(w)) return w.slice(0, -1);
    return w;
  }
  const indexable = (raw, w) => !(STOP.has(w) || STOP.has(raw)) && (w.length >= 2 || /^\d+$/.test(w));
  function fnv1a(s) {
    let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h >>> 0;
  }
  /* 带原文位置的分词：[{s, e, raw, w}] */
  function tokens(text) {
    const out = [];
    const re = /[A-Za-z0-9\u00C0-\u024F]+(?:['\u2019][A-Za-z]+)?/g;
    let m;
    while ((m = re.exec(text))) {
      const raw = norm(m[0]).replace(/[^a-z0-9']/g, '');
      if (!raw) continue;
      out.push({ s: m.index, e: m.index + m[0].length, raw, w: stem(raw) });
    }
    return out;
  }

  /* ---------- 中文常用词 → 英文检索词 ---------- */
  const GLOSS = {
    '第一性原理': ['"first principles"', '"first principle"'], '第一原理': ['"first principles"'],
    '人工智能': ['ai', '"artificial intelligence"'], '超级智能': ['superintelligence', '"digital superintelligence"'],
    '通用人工智能': ['agi'], '机器人': ['robot', 'optimus', 'humanoid'], '人形机器人': ['humanoid'], '擎天柱': ['optimus'],
    '自动驾驶': ['"self-driving"', 'autopilot', 'fsd', 'autonomy', 'autonomous'], '完全自动驾驶': ['fsd', '"full self-driving"'],
    '无人出租车': ['robotaxi', 'cybercab'], '电动车': ['"electric car"', '"electric vehicle"', 'ev'], '电动汽车': ['"electric car"', '"electric vehicle"'],
    '汽车': ['car'], '卡车': ['semi', 'truck'], '皮卡': ['cybertruck'], '跑车': ['roadster'],
    '火星': ['mars'], '月球': ['moon'], '星舰': ['starship'], '猎鹰': ['falcon'], '龙飞船': ['dragon'], '星链': ['starlink'],
    '火箭': ['rocket'], '发动机': ['engine'], '猛禽': ['raptor'], '复用': ['reusable', 'reusability', 'reuse'], '可复用': ['reusable', 'reusability'],
    '回收': ['reusable', 'landing'], '着陆': ['landing', 'land'], '发射': ['launch'], '太空': ['space'], '宇航员': ['astronaut'], '轨道': ['orbit'],
    '多行星': ['multiplanetary', '"multi-planetary"', 'multiplanet'], '殖民': ['colony', 'colonize'], '文明': ['civilization'],
    '特斯拉': ['tesla'], '电池': ['battery'], '储能': ['megapack', 'powerwall', 'storage'], '太阳能': ['solar'], '能源': ['energy'],
    '可持续能源': ['"sustainable energy"'], '气候': ['climate'], '全球变暖': ['"global warming"'], '碳': ['carbon'], '石油': ['oil'], '核能': ['nuclear'],
    '工厂': ['factory', 'gigafactory'], '超级工厂': ['gigafactory'], '制造': ['manufacturing'], '量产': ['production', '"volume production"'],
    '产能': ['production', 'capacity'], '供应链': ['"supply chain"'], '成本': ['cost'], '价格': ['price'], '芯片': ['chip'], '算力': ['compute'],
    '数据中心': ['"data center"'], '神经网络': ['"neural net"', '"neural network"'], '脑机接口': ['neuralink', '"brain-computer"', '"brain computer"'],
    '隧道': ['tunnel', '"boring company"'], '超级高铁': ['hyperloop'], '推特': ['twitter'], '言论自由': ['"free speech"', '"freedom of speech"'],
    '审查': ['censorship', 'censor'], '媒体': ['media'], '记者': ['journalist', 'press'], '广告': ['advertising', 'advertiser'],
    '收购': ['acquisition', 'acquire', 'buy', 'bought'], '出生率': ['"birth rate"', 'birthrate'], '人口': ['population'],
    '人口崩溃': ['"population collapse"'], '孩子': ['kid', 'children'], '家庭': ['family'], '政府': ['government'],
    '监管': ['regulation', 'regulator', 'regulatory'], '政府效率': ['doge', '"government efficiency"'], '税': ['tax'], '补贴': ['subsidy', 'subsidies'],
    '民主': ['democracy'], '民主党': ['democrat'], '共和党': ['republican'], '选举': ['election'], '移民': ['immigration'], '战争': ['war'],
    '中国': ['china', 'chinese'], '美国': ['america', '"united states"'], '欧洲': ['europe'], '俄罗斯': ['russia'],
    '特朗普': ['trump'], '拜登': ['biden'], '奥巴马': ['obama'], '贝索斯': ['bezos'], '奥特曼': ['altman'], '盖茨': ['gates'],
    '乔布斯': ['"steve jobs"'], '佩奇': ['"larry page"'], '扎克伯格': ['zuckerberg'], '罗根': ['rogan'],
    '比特币': ['bitcoin'], '狗狗币': ['dogecoin'], '加密货币': ['crypto', 'cryptocurrency'],
    '创业': ['startup', '"start a company"'], '公司': ['company'], '管理': ['management', 'manager'], '会议': ['meeting'],
    '招聘': ['hire', 'hiring', 'recruit'], '招人': ['hire', 'hiring'], '面试': ['interview'], '人才': ['talent', 'talented'], '工程师': ['engineer'],
    '工程': ['engineering'], '物理': ['physics'], '数学': ['math'], '教育': ['education', 'school'], '大学': ['college', 'university'],
    '学校': ['school'], '读书': ['book', 'read'], '书': ['book'], '建议': ['advice'], '年轻人': ['"young people"', 'young'],
    '失败': ['failure', 'fail'], '风险': ['risk'], '危险': ['danger', 'dangerous'], '生存风险': ['"existential risk"', 'existential'],
    '恐惧': ['fear', 'afraid'], '痛苦': ['pain'], '压力': ['stress', 'pressure'], '工作': ['work'], '加班': ['"hours a week"', '"hours per week"'],
    '睡觉': ['sleep'], '睡眠': ['sleep'], '钱': ['money'], '金钱': ['money'], '财富': ['wealth', 'rich'], '股价': ['stock'], '股票': ['stock', 'share'],
    '估值': ['valuation', '"market cap"'], '利润': ['profit', 'profitable'], '破产': ['bankrupt', 'bankruptcy'], '盈利': ['profitable', 'profit'],
    '幸福': ['happy', 'happiness'], '意义': ['meaning'], '人生': ['life'], '人生意义': ['"meaning of life"'], '意识': ['consciousness'],
    '模拟': ['simulation'], '外星人': ['alien'], '宇宙': ['universe'], '上帝': ['god'], '宗教': ['religion'], '死亡': ['death', 'die'],
    '未来': ['future'], '预测': ['predict', 'prediction'], '明年': ['"next year"'], '年底': ['"end of the year"', '"end of this year"'],
    '游戏': ['game', 'gaming'], '电影': ['movie', 'film'], '音乐': ['music'], '朋友': ['friend'], '爱情': ['love'], '父亲': ['father', 'dad'], '南非': ['"south africa"'],
  };
  const GLOSS_MAX = Math.max(...Object.keys(GLOSS).map((k) => k.length));
  const CJK = /[\u3400-\u9fff]/;

  const PRESETS = [
    ['第一性原理', '"first principles"'],
    ['AI 会威胁人类吗', 'ai|"artificial intelligence" risk|danger|dangerous'],
    ['为什么要去火星', 'mars multiplanetary|"multi-planetary"|civilization'],
    ['怎么招人', 'hire|hiring|recruit'],
    ['给年轻人的建议', 'advice'],
    ['怎么看失败', 'failure|fail'],
    ['每周工作多少小时', '"hours a week"|"hours per week"'],
    ['出生率与人口', '"birth rate"|birthrate|"population collapse"'],
    ['OpenAI', 'openai'],
    ['火箭复用', 'reusable|reusability rocket'],
    ['FSD 何时实现', 'fsd|"self-driving" "next year"|"end of the year"|"end of this year"'],
    ['模拟假说', 'simulation'],
    ['五步工作法', '"the algorithm"|"question the requirements"|"delete the part"'],
    ['人生的意义', '"meaning of life"|consciousness'],
  ];

  /* ---------- 查询解析：空格分隔为「且」，| 分隔为「或」，"..." 为短语 ---------- */
  function rawGroups(q) {
    const groups = [];
    let cur = null, i = 0;
    const n = q.length;
    while (i < n) {
      const c = q[i];
      if (/\s/.test(c)) { if (cur) { groups.push(cur); cur = null; } i++; continue; }
      if (c === '|') { i++; continue; }
      let term;
      if (c === '"' || c === '“' || c === '”') {
        let j = i + 1;
        while (j < n && !/["“”]/.test(q[j])) j++;
        term = { s: q.slice(i + 1, j), quoted: true };
        i = j + 1;
      } else {
        let j = i;
        while (j < n && !/[\s"“”|]/.test(q[j])) j++;
        term = { s: q.slice(i, j), quoted: false };
        i = j;
      }
      if (!term.s.trim()) continue;
      (cur = cur || []).push(term);
    }
    if (cur) groups.push(cur);
    return groups;
  }

  function altFrom(str) {
    const s = str.replace(/^"|"$/g, '');
    const toks = tokens(s);
    const keys = [...new Set(toks.filter((t) => indexable(t.raw, t.w)).map((t) => t.w))];
    if (!keys.length) return null;
    return { label: s, seq: toks.map((t) => t.w), keys, phrase: toks.length > 1 };
  }
  /* 机器翻译出来的英文不当短语，只要求这些词出现在同一段 */
  function altLoose(str) {
    const s = str.toLowerCase().replace(/[.,!?;:"“”]+/g, ' ').trim();
    const toks = tokens(s);
    const keys = [...new Set(toks.filter((t) => indexable(t.raw, t.w)).map((t) => t.w))];
    if (!keys.length) return null;
    return { label: s, seq: toks.map((t) => t.w), keys, phrase: false };
  }

  /* 英文 → 中文：先查 GLOSS 反向表，查不到再翻译 */
  const REV = {};
  Object.entries(GLOSS).forEach(([zh, alts]) => alts.forEach((a) => { const k = a.replace(/"/g, ''); if (!REV[k]) REV[k] = zh; }));
  /* 问句里的虚词：多字的整段去掉，单字的只削两头，免得把「社会」切成「社」 */
  const ZH_STOP_MULTI = ['马斯克', '埃隆', '怎么看', '怎么样', '怎么', '如何', '为什么', '为何', '什么', '是否', '有没有', '关于', '对于',
    '看法', '观点', '认为', '觉得', '谈谈', '说过', '哪些', '多少', '这个', '那个', '一下', '一些', '可以', '能否', '到底'];
  const ZH_STOP_EDGE = '的了吗呢和与及对在是会要有吧啊么呀把被让给从向跟就都也还';
  function stripZh(miss) {
    let s = miss;
    ZH_STOP_MULTI.forEach((w) => { s = s.split(w).join(' '); });
    return s.split(/\s+/).map((x) => {
      let a = 0, b = x.length;
      while (a < b && ZH_STOP_EDGE.includes(x[a])) a++;
      while (b > a && ZH_STOP_EDGE.includes(x[b - 1])) b--;
      return x.slice(a, b);
    }).filter((x) => x.length >= 2);
  }

  function expandCJK(run) {
    const out = [];
    let i = 0, miss = '';
    const flush = () => { if (miss) { stripZh(miss).forEach((m) => out.push({ miss: m })); miss = ''; } };
    while (i < run.length) {
      let hit = null;
      for (let L = Math.min(GLOSS_MAX, run.length - i); L >= 1; L--) {
        const k = run.substr(i, L);
        if (GLOSS[k]) { hit = k; break; }
      }
      if (hit) { flush(); out.push({ hit }); i += hit.length; } else { miss += run[i]; i++; }
    }
    flush();
    return out;
  }

  /* 一个「概念」是一个且条件：en 用来查英文文稿，zh 用来查中文精读，两边各自是「或」 */
  function fragEn(s, quoted) {
    const a = altFrom(quoted ? `"${s}"` : s);
    if (!a) return null;
    const low = s.toLowerCase().trim();
    const f = { src: s, en: [a], zh: [low], needZh: null };
    const rev = REV[low] || REV[stem(low)];
    if (rev) f.zh.push(rev);
    else if (/[a-z]/i.test(s)) f.needZh = s;
    return f;
  }
  function fragZh(part) {
    if (part.hit) {
      const en = GLOSS[part.hit].map(altFrom).filter(Boolean);
      const zh = [part.hit, ...GLOSS[part.hit].filter((a) => /^[a-z0-9]+$/.test(a))];
      return { src: part.hit, en, zh, gloss: true };
    }
    return { src: part.miss, en: [], zh: [part.miss], needEn: part.miss };
  }
  function parse(q) {
    const concepts = [], stopOnly = [];
    const merge = (fs) => ({
      src: fs.map((f) => f.src).join(' | '), en: fs.flatMap((f) => f.en), zh: [...new Set(fs.flatMap((f) => f.zh))],
      needEn: fs.map((f) => f.needEn).filter(Boolean), needZh: fs.map((f) => f.needZh).filter(Boolean),
      cjk: fs.some((f) => CJK.test(f.src)), gloss: fs.some((f) => f.gloss), tr: [],
    });
    for (const g of rawGroups(q)) {
      const frags = [];
      for (const t of g) {
        if (t.quoted || !CJK.test(t.s)) {
          const f = fragEn(t.s, t.quoted);
          if (f) frags.push(f); else stopOnly.push(t.s);
          continue;
        }
        t.s.split(/([\u3400-\u9fff]+)/).forEach((run) => {
          if (!run) return;
          if (CJK.test(run)) expandCJK(run).forEach((p) => frags.push(fragZh(p)));
          else { const f = fragEn(run, false); if (f) frags.push(f); }
        });
      }
      if (!frags.length) continue;
      if (g.length > 1) concepts.push(merge(frags));
      else frags.forEach((f) => concepts.push(merge([f])));
    }
    return { concepts, stopOnly };
  }

  /* ---------- 免费谷歌翻译（与 read-frog 一样直接用网页翻译接口，无需 key）----------
     国内连不上 Google：先走本站 /api/tr（Nginx 反代并缓存），失败再直连 */
  const TR_KEY = 'em-tr-v2';
  const trMem = (() => { try { return JSON.parse(sessionStorage.getItem(TR_KEY) || '{}'); } catch (e) { return {}; } })();
  const trSave = () => { try { sessionStorage.setItem(TR_KEY, JSON.stringify(trMem)); } catch (e) { /* 存不下就不存 */ } };
  const TR_ENDPOINTS = [
    (tl, q) => `/api/tr?tl=${tl}&q=${encodeURIComponent(q)}`,
    (tl, q) => `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${tl}&dt=t&dt=bd&q=${encodeURIComponent(q)}`,
  ];
  let trFirst = 0;
  async function fetchT(u, ms) {
    const c = new AbortController();
    const timer = setTimeout(() => c.abort(), ms);
    try { return await fetch(u, { signal: c.signal }); } finally { clearTimeout(timer); }
  }
  async function gtrans(text, tl) {
    const key = tl + '\u0001' + text;
    if (Object.prototype.hasOwnProperty.call(trMem, key)) return trMem[key];
    const order = [trFirst, ...TR_ENDPOINTS.keys()].filter((v, i, a) => a.indexOf(v) === i);
    for (const i of order) {
      try {
        const r = await fetchT(TR_ENDPOINTS[i](tl, text), 4500);
        if (!r.ok) continue;
        const j = await r.json();
        const main = ((j && j[0]) || []).map((x) => (x && x[0]) || '').join('').trim();
        if (!main) continue;
        // dt=bd 是词典释义：单个词时会给出几个常见译法，一起当「或」来查，召回更全
        const dict = Array.isArray(j[1]) && Array.isArray(j[1][0]) && Array.isArray(j[1][0][1]) ? j[1][0][1] : [];
        const out = [...new Set([main, ...dict].map((x) => String(x).trim()).filter(Boolean))].slice(0, 3);
        trFirst = i;
        trMem[key] = out;
        trSave();
        return out;
      } catch (e) { /* 换下一个地址 */ }
    }
    return null;
  }
  async function translateConcepts(parsed) {
    const jobs = [];
    parsed.concepts.forEach((c) => {
      c.needEn.forEach((s) => jobs.push(gtrans(s, 'en').then((list) => {
        (list || []).forEach((e) => {
          if (CJK.test(e)) return;
          const a = altLoose(e);
          if (a && !c.en.some((x) => x.label === a.label)) { c.en.push(a); c.tr.push(a.label); }
        });
        if (!c.en.length) c.trFail = true;
      })));
      c.needZh.forEach((s) => jobs.push(gtrans(s, 'zh-CN').then((list) => {
        (list || []).forEach((z) => {
          const t = z.replace(/[。．.!！?？,，、\s]+$/g, '').trim();
          if (CJK.test(t) && t.length >= 2 && !c.zh.includes(t)) { c.zh.push(t); c.tr.push(t); }
        });
      })));
    });
    await Promise.all(jobs);
  }

  /* ---------- 数据加载 ---------- */
  const getJSON = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(r.status + ' ' + u); return r.json(); });
  function corpus(prefix, metaFile, paraDir, hash) {
    let meta = null;
    const shardCache = new Map(), postCache = new Map(), paraCache = new Map();
    const C = {
      meta() {
        if (!meta) meta = getJSON(BASE + metaFile).then((m) => { m.off = m.eps.map((e) => e[1]); return m; }, (e) => { meta = null; throw e; });
        return meta;
      },
      async postings(w) {
        if (postCache.has(w)) return postCache.get(w);
        const m = await C.meta();
        const i = hash(w) % m.shards;
        if (!shardCache.has(i)) {
          const p = getJSON(`${BASE}${prefix}/${String(i).padStart(3, '0')}.json`);
          shardCache.set(i, p);
          p.catch(() => shardCache.delete(i));
        }
        const d = (await shardCache.get(i))[w] || [];
        const out = new Array(d.length);
        let g = 0;
        for (let k = 0; k < d.length; k++) { g += d[k]; out[k] = g; }
        postCache.set(w, out);
        return out;
      },
      paras(k) {
        if (!paraCache.has(k)) {
          const p = getJSON(`${BASE}${paraDir}/${k}.json`);
          paraCache.set(k, p);
          p.catch(() => paraCache.delete(k));
        }
        return paraCache.get(k);
      },
    };
    return C;
  }
  const utf8 = new TextEncoder();
  function fnv1aUtf8(s) {
    let h = 0x811c9dc5;
    for (const b of utf8.encode(s)) { h ^= b; h = Math.imul(h, 0x01000193) >>> 0; }
    return h >>> 0;
  }
  const EN = corpus('i', 'meta.json', 'p', fnv1a);
  const ZH = corpus('z', 'zmeta.json', 'zp', fnv1aUtf8);

  const inter = (a, b) => { const o = []; let i = 0, j = 0; while (i < a.length && j < b.length) { if (a[i] === b[j]) { o.push(a[i]); i++; j++; } else if (a[i] < b[j]) i++; else j++; } return o; };
  const union = (a, b) => { const o = []; let i = 0, j = 0; while (i < a.length || j < b.length) { if (j >= b.length || (i < a.length && a[i] < b[j])) o.push(a[i++]); else if (i >= a.length || b[j] < a[i]) o.push(b[j++]); else { o.push(a[i]); i++; j++; } } return o; };
  function epOf(g, off) {
    let lo = 0, hi = off.length - 1;
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (off[mid] <= g) lo = mid; else hi = mid - 1; }
    return lo;
  }

  /* 中文：二字组 + 英文词，与 search_index.zh_terms 一致 */
  function zKeys(s) {
    const t = norm(s);
    const keys = new Set();
    (t.match(/[\u3400-\u9fff\uf900-\ufaff]+/g) || []).forEach((run) => { for (let i = 0; i + 1 < run.length; i++) keys.add(run.slice(i, i + 2)); });
    (t.match(/[a-z0-9]+/g) || []).forEach((w) => { if (w.length > 1 || /^\d+$/.test(w)) keys.add(w); });
    return [...keys];
  }
  const zSearchable = (s) => zKeys(s).length > 0;

  /* 每组「或」内求并集，组与组之间求交集 */
  async function runCorpus(C, groups) {
    const m = await C.meta();
    const keyLists = groups.map((alts) => alts.map((a) => a.keys));
    await Promise.all([...new Set(keyLists.flat(2))].map((w) => C.postings(w)));
    const sets = [];
    for (const lists of keyLists) {
      let gs = [];
      for (const keys of lists) {
        let s = null;
        for (const w of keys) { const p = await C.postings(w); s = s ? inter(s, p) : p; if (!s.length) break; }
        gs = union(gs, s || []);
      }
      sets.push(gs);
    }
    sets.sort((a, b) => a.length - b.length);
    let hits = sets[0] || [];
    for (let i = 1; i < sets.length && hits.length; i++) hits = inter(hits, sets[i]);
    const byEp = new Map();
    for (const g of hits) { const k = epOf(g, m.off); if (!byEp.has(k)) byEp.set(k, []); byEp.get(k).push(g); }
    const years = new Map();
    byEp.forEach((gs, k) => { const y = (m.eps[k][2] || '').slice(0, 4) || '未知'; const v = years.get(y) || [0, 0]; v[0] += gs.length; v[1]++; years.set(y, v); });
    return { meta: m, hits, byEp, years, shown: 0, list: [] };
  }

  /* ---------- 段落校验与摘要高亮 ---------- */
  function verify(text, groups) {
    const toks = tokens(text);
    const ranges = [];
    for (const alts of groups) {
      let ok = false;
      for (const a of alts) {
        if (!a.phrase) {
          const found = a.keys.map((k) => toks.filter((t) => t.w === k));
          if (found.every((f) => f.length)) { ok = true; found.flat().forEach((t) => ranges.push([t.s, t.e])); }
        } else {
          const L = a.seq.length;
          for (let i = 0; i + L <= toks.length; i++) {
            let m = true;
            for (let j = 0; j < L; j++) if (toks[i + j].w !== a.seq[j]) { m = false; break; }
            if (m) { ok = true; ranges.push([toks[i].s, toks[i + L - 1].e]); }
          }
        }
      }
      if (!ok) return null;
    }
    ranges.sort((x, y) => x[0] - y[0]);
    return ranges;
  }
  function verifyZh(text, groups) {
    const low = text.toLowerCase();
    const ranges = [];
    for (const alts of groups) {
      let ok = false;
      for (const a of alts) {
        if (/^[\x00-\x7f]+$/.test(a.s)) {
          // 英文词要整词匹配，免得 ai 命中 OpenAI 里的 ai
          const re = new RegExp('(?<![a-z0-9])' + a.s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![a-z0-9])', 'g');
          let m;
          while ((m = re.exec(low))) { ok = true; ranges.push([m.index, m.index + m[0].length]); }
          continue;
        }
        let i = low.indexOf(a.s);
        while (i >= 0) { ok = true; ranges.push([i, i + a.s.length]); i = low.indexOf(a.s, i + a.s.length); }
      }
      if (!ok) return null;
    }
    ranges.sort((x, y) => x[0] - y[0] || y[1] - x[1]);
    const merged = [];
    ranges.forEach((r) => { const l = merged[merged.length - 1]; if (l && r[0] <= l[1]) l[1] = Math.max(l[1], r[1]); else merged.push(r.slice()); });
    return merged;
  }
  function snippet(text, ranges, width, wordy) {
    let a = 0, b = text.length;
    if (text.length > width) {
      const c = ranges[0][0];
      a = Math.max(0, c - Math.round(width * 0.35));
      b = Math.min(text.length, a + width);
      a = Math.max(0, b - width);
      if (wordy) {
        if (a > 0) { const sp = text.indexOf(' ', a); if (sp > 0 && sp < a + 20) a = sp + 1; }
        if (b < text.length) { const sp = text.lastIndexOf(' ', b); if (sp > b - 20) b = sp; }
      }
    }
    let out = a > 0 ? '…' : '', pos = a;
    for (const [s, e] of ranges) {
      if (e <= pos || s >= b) continue;
      const s2 = Math.max(s, pos);
      out += esc(text.slice(pos, s2)) + '<mark>' + esc(text.slice(s2, Math.min(e, b))) + '</mark>';
      pos = Math.min(e, b);
    }
    out += esc(text.slice(pos, b)) + (b < text.length ? '…' : '');
    return out;
  }
  const mmss = (s) => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };
  const fmtDate = (d) => !d ? '' : d.length === 4 ? d + ' 年' : `${d.slice(0, 4)} 年 ${+d.slice(5, 7)} 月`;

  window.EMSearch = { parse, translateConcepts, runCorpus, EN, ZH };
  if (!$('#srq')) return;

  /* ---------- 状态与渲染 ---------- */
  const input = $('#srq');
  const body = $('#srBody');
  const clearBtn = $('.sr-clear');
  const state = { q: '', sort: 'rel', y: '', src: '' };
  let run = 0;
  let RES = null;
  const PAGE = 8;
  const cur = () => RES && RES[RES.src];

  function readURL() {
    const p = new URLSearchParams(location.search);
    state.q = p.get('q') || '';
    state.sort = ['rel', 'old', 'new'].includes(p.get('sort')) ? p.get('sort') : 'rel';
    state.y = p.get('y') || '';
    state.src = p.get('in') === 'zh' ? 'zh' : p.get('in') === 'en' ? 'en' : '';
    input.value = state.q;
    clearBtn.hidden = !state.q;
  }
  function syncURL() {
    const p = new URLSearchParams();
    if (state.q.trim()) p.set('q', state.q.trim());
    if (state.src) p.set('in', state.src);
    if (state.sort !== 'rel') p.set('sort', state.sort);
    if (state.y) p.set('y', state.y);
    const qs = p.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
    document.title = (state.q.trim() ? `「${state.q.trim()}」· ` : '') + '文稿搜索 · 马斯克全访谈';
  }

  function presetsHTML() {
    return `<div class="sr-presets"><h2>常被问到的</h2><div class="chips">${PRESETS.map(([l, q]) =>
      `<button type="button" class="chip" data-q="${esc(q)}">${esc(l)}</button>`).join('')}</div></div>`;
  }

  async function search() {
    const my = ++run;
    syncURL();
    const q = state.q.trim();
    if (!q) { RES = null; body.innerHTML = presetsHTML(); return; }
    const parsed = parse(q);
    if (!parsed.concepts.length) {
      body.innerHTML = `<div class="sr-empty"><p>这些词太常见，换个更具体的词试试。</p></div>${presetsHTML()}`;
      return;
    }
    const needTr = parsed.concepts.some((c) => c.needEn.length || c.needZh.length);
    body.innerHTML = `<p class="sr-loading">${needTr ? '翻译并搜索中…' : '搜索中…'}</p>`;
    if (needTr) await translateConcepts(parsed);
    if (my !== run) return;
    const enGroups = parsed.concepts.filter((c) => c.en.length).map((c) => c.en);
    const zhGroups = parsed.concepts.map((c) => c.zh.filter(zSearchable).map((s) => ({ s: s.toLowerCase(), keys: zKeys(s) }))).filter((g) => g.length);
    const [en, zh] = await Promise.allSettled([
      enGroups.length ? runCorpus(EN, enGroups) : Promise.resolve(null),
      zhGroups.length ? runCorpus(ZH, zhGroups) : Promise.resolve(null),
    ]);
    if (my !== run) return;
    const pack = (r, groups) => r.status === 'fulfilled' ? (r.value && Object.assign(r.value, { groups })) : { error: true, hits: [] };
    RES = { parsed, en: pack(en, enGroups), zh: pack(zh, zhGroups) };
    RES.en && (RES.en.approx = enGroups.some((alts) => alts.some((a) => a.phrase)));
    RES.zh && (RES.zh.approx = zhGroups.some((alts) => alts.some((a) => a.keys.length > 1)));
    const nEn = RES.en ? RES.en.hits.length : 0, nZh = RES.zh ? RES.zh.hits.length : 0;
    RES.src = state.src && RES[state.src] ? state.src : (nEn || !nZh ? (RES.en ? 'en' : 'zh') : 'zh');
    if (!RES[RES.src]) RES.src = RES.en ? 'en' : 'zh';
    render(my);
  }

  function orderedEps() {
    const C = cur();
    const ks = [...C.byEp.keys()].filter((k) => !state.y || ((C.meta.eps[k][2] || '').slice(0, 4) || '未知') === state.y);
    if (state.sort === 'old') ks.sort((a, b) => a - b);
    else if (state.sort === 'new') ks.sort((a, b) => b - a);
    else ks.sort((a, b) => (C.byEp.get(b).length - C.byEp.get(a).length) || (b - a));
    return ks;
  }

  function interpHTML(parsed) {
    const parts = parsed.concepts.map((c) => {
      const b = (s) => `<b>${esc(s)}</b>`;
      let targets;
      if (c.cjk) targets = c.en.map((a) => a.label);
      else targets = c.zh.filter((z) => CJK.test(z));
      const gt = c.tr.length ? '<small class="sr-gt">谷歌翻译</small>' : '';
      const fail = c.trFail && !c.en.length ? '<small class="sr-unk">没翻译出来，只查精读</small>' : '';
      const arrow = targets.length ? `<span class="sr-zh">${esc(c.src)}</span>${targets.slice(0, 4).map(b).join('<i>或</i>')}` : b(c.src);
      return `<span class="sr-g">${arrow}${gt}${fail}</span>`;
    });
    return `<div class="sr-interp"><span class="sr-k">检索词</span>${parts.join('<span class="sr-and">+</span>')}</div>`;
  }

  function histHTML() {
    const C = cur();
    const ys = [...C.years.keys()].filter((y) => y !== '未知').sort();
    if (ys.length < 2) return '';
    const all = [];
    for (let y = +ys[0]; y <= +ys[ys.length - 1]; y++) all.push(String(y));
    const max = Math.max(...all.map((y) => (C.years.get(y) || [0])[0]));
    const bars = all.map((y) => {
      const v = C.years.get(y) || [0, 0];
      const h = v[0] ? Math.max(6, Math.round((v[0] / max) * 100)) : 0;
      const on = state.y === y ? ' on' : '';
      return `<button type="button" class="sr-bar${on}" data-y="${y}" ${v[0] ? '' : 'disabled'} title="${y} 年：${v[0]} 段，${v[1]} 个视频" aria-label="${y} 年 ${v[0]} 段">
        <span class="sr-bar-n">${v[0] || ''}</span><span class="sr-bar-f" style="height:${h}%"></span><span class="sr-bar-y">${y.slice(2)}</span></button>`;
    }).join('');
    return `<div class="sr-hist"><div class="sr-hist-h"><span>按年份分布</span><small>${state.y ? `只看 ${state.y} 年 · <button type="button" data-y="${state.y}">看全部年份</button>` : '点柱子只看那一年'}</small></div><div class="sr-bars">${bars}</div></div>`;
  }

  function tabsHTML() {
    const t = (src, label) => {
      const C = RES[src];
      const n = C ? (C.error ? '加载失败' : `${C.approx && C.hits.length ? '约 ' : ''}${C.hits.length} 段`) : '无可查词';
      return `<button type="button" role="tab" data-src="${src}" aria-selected="${RES.src === src}" ${C ? '' : 'disabled'}>${label}<small>${n}</small></button>`;
    };
    return `<div class="sr-tabs" role="tablist" aria-label="搜索范围">${t('en', '英文原话')}${t('zh', '中文精读')}</div>`;
  }

  function render(my) {
    const C = cur();
    const { parsed } = RES;
    if (!C) { body.innerHTML = `${interpHTML(parsed)}<div class="sr-empty"><p>这些词没法检索，换个说法试试。</p></div>${presetsHTML()}`; return; }
    if (C.error) {
      body.innerHTML = `${interpHTML(parsed)}${tabsHTML()}<div class="sr-empty"><p>索引加载失败，请检查网络后重试。</p></div>`;
      return;
    }
    C.list = orderedEps();
    C.shown = 0;
    const isZh = RES.src === 'zh';
    const nP = state.y ? C.list.reduce((s, k) => s + C.byEp.get(k).length, 0) : C.hits.length;
    const nE = C.list.length;
    const sorts = [['rel', '命中最多'], ['old', '从早到晚'], ['new', '从晚到早']].map(([v, l]) =>
      `<button type="button" data-sort="${v}" aria-pressed="${state.sort === v}">${l}</button>`).join('');
    const unit = isZh ? '篇精读' : '个视频';
    const other = isZh ? 'en' : 'zh';
    const otherN = RES[other] && !RES[other].error ? RES[other].hits.length : 0;
    const count = C.hits.length
      ? `<h2>${C.approx ? '约 ' : ''}${nP} 段<small>${nE} ${unit}${state.y ? ` · ${state.y} 年` : ''}</small></h2>`
      : `<h2>没有找到<small>${otherN ? `去「${isZh ? '英文原话' : '中文精读'}」看看` : '换个说法，或去掉一些词'}</small></h2>`;
    const note = isZh ? '<p class="sr-evo">精读是 AI 基于文稿写的中文导读，不是逐字翻译；点结果会定位到精读里的那一段。</p>'
      : (state.sort === 'old' && C.hits.length ? '<p class="sr-evo">按时间从早到晚排列，可以看他在这件事上的说法怎么变化。</p>' : '');
    body.innerHTML = `${interpHTML(parsed)}${tabsHTML()}<div class="sr-line">${count}${C.hits.length ? `<div class="sr-sort" role="group" aria-label="排序">${sorts}</div>` : ''}</div>
      ${C.hits.length ? histHTML() : presetsHTML()}
      ${note}
      <div class="sr-list"></div><div class="sr-foot"></div>`;
    if (C.hits.length) more(my);
  }

  async function more(my) {
    const C = cur();
    const list = $('.sr-list', body), foot = $('.sr-foot', body);
    if (!list) return;
    const src = RES.src;
    foot.innerHTML = '<p class="sr-loading">加载中…</p>';
    let added = 0;
    while (added < PAGE && C.shown < C.list.length) {
      const batch = C.list.slice(C.shown, C.shown + PAGE - added);
      C.shown += batch.length;
      // 每个视频的段落文件单独到达：先占位保住顺序，到一个填一个
      const slots = batch.map(() => list.appendChild(document.createElement('div')));
      await Promise.all(batch.map((k, i) => (src === 'zh' ? zhEpHTML(k) : epHTML(k)).catch(() => '').then((h) => {
        if (my !== run || RES.src !== src) return;
        if (h) { slots[i].outerHTML = h; added++; } else slots[i].remove();
      })));
      if (my !== run || RES.src !== src) return;
    }
    const left = C.list.length - C.shown;
    foot.innerHTML = left > 0 ? `<button type="button" class="more-btn" data-more>再看 ${Math.min(PAGE, left)} ${src === 'zh' ? '篇' : '个视频'}</button><span class="more-sub">还有 ${left} 个</span>` : (C.shown > PAGE ? '<span class="end">— 到底了 —</span>' : '');
  }

  function epHeadHTML(meta, k, n, isZh) {
    const [slug, , d, zh, en, kind, yt] = meta.eps[k];
    const local = yt ? `/thumbs/${esc(yt)}.jpg` : '';
    const fb = yt ? `https://i.ytimg.com/vi/${esc(yt)}/mqdefault.jpg` : '';
    const thumb = yt ? `<img loading="lazy" src="${local}" alt="" width="160" height="90" onerror="if(this.src.indexOf('/thumbs/')>=0){this.onerror=null;this.src='${fb}'}">` : '<span class="no-img">EM</span>';
    return `<a class="sr-ep-h" href="/ep/${esc(slug)}/"><span class="sr-thumb">${thumb}</span>
        <span class="sr-ep-t"><span class="sr-kicker">${isZh ? '中文精读 · ' : ''}${esc(kind)}${d ? ' · ' + esc(fmtDate(d)) : ''} · ${n} 处</span>
        <span class="sr-title">${esc(zh || en)}</span>${zh && en !== zh ? `<span class="sr-en" lang="en">${esc(en)}</span>` : ''}</span></a>`;
  }
  function sectionHTML(meta, k, items, isZh) {
    const SHOW = 3;
    const rest = items.length - SHOW;
    return `<section class="sr-ep${isZh ? ' sr-ep-zh' : ''}">${epHeadHTML(meta, k, items.length, isZh)}
      <ol class="sr-hits">${items.slice(0, SHOW).join('')}${rest > 0 ? items.slice(SHOW).map((h) => h.replace('<li>', '<li hidden>')).join('') : ''}</ol>
      ${rest > 0 ? `<button type="button" class="sr-expand">展开另外 ${rest} 处</button>` : ''}
    </section>`;
  }

  async function epHTML(k) {
    const C = RES.en;
    const [slug, off] = C.meta.eps[k];
    const ps = await EN.paras(k);
    const items = [];
    const hlWords = (text, ranges) => [...new Set(ranges.map(([s, e]) => text.slice(s, e).toLowerCase()))].slice(0, 6).join(' ');
    for (const g of C.byEp.get(k)) {
      const local = g - off;
      const p = ps[local];
      if (!p) continue;
      const ranges = verify(p[1], C.groups);
      if (!ranges) continue;
      const qs = new URLSearchParams({ p: local });
      if (p[0] != null) qs.set('t', p[0]);
      qs.set('hl', hlWords(p[1], ranges));
      const ts = p[0] != null ? `<span class="sr-ts">${mmss(p[0])}</span>` : '<span class="sr-ts">¶</span>';
      items.push(`<li><a class="sr-hit" href="/ep/${esc(slug)}/?${qs}">${ts}<span class="sr-snip" lang="en">${snippet(p[1], ranges, 260, true)}</span></a></li>`);
    }
    return items.length ? sectionHTML(C.meta, k, items, false) : '';
  }

  async function zhEpHTML(k) {
    const C = RES.zh;
    const [slug, off] = C.meta.eps[k];
    const ps = await ZH.paras(k);
    const items = [];
    for (const g of C.byEp.get(k)) {
      const local = g - off;
      const text = ps[local];
      if (text == null) continue;
      const ranges = verifyZh(text, C.groups);
      if (!ranges) continue;
      const hl = [...new Set(ranges.map(([s, e]) => text.slice(s, e)))].slice(0, 6).join(' ');
      const qs = new URLSearchParams({ z: local, hl });
      items.push(`<li><a class="sr-hit sr-hit-zh" href="/ep/${esc(slug)}/?${qs}"><span class="sr-ts">精读</span><span class="sr-snip">${snippet(text, ranges, 130, false)}</span></a></li>`);
    }
    return items.length ? sectionHTML(C.meta, k, items, true) : '';
  }

  /* ---------- 事件 ---------- */
  let deb;
  function setQ(q, now) {
    state.q = q;
    state.y = '';
    state.src = '';
    clearBtn.hidden = !q;
    clearTimeout(deb);
    if (now) search(); else deb = setTimeout(search, 320);
  }
  input.addEventListener('input', () => setQ(input.value));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); setQ(input.value, true); input.blur(); }
    else if (e.key === 'Escape') { input.value = ''; setQ('', true); }
  });
  clearBtn.addEventListener('click', () => { input.value = ''; setQ('', true); input.focus(); });
  body.addEventListener('click', (e) => {
    const c = e.target.closest('[data-q]');
    if (c) { input.value = c.dataset.q; setQ(c.dataset.q, true); if (window.umami) window.umami.track('search-preset'); return; }
    const t = e.target.closest('[data-src]');
    if (t && RES && RES[t.dataset.src]) { RES.src = state.src = t.dataset.src; state.y = ''; syncURL(); render(run); return; }
    const s = e.target.closest('[data-sort]');
    if (s && RES) { state.sort = s.dataset.sort; syncURL(); render(run); return; }
    const y = e.target.closest('[data-y]');
    if (y && RES) { state.y = state.y === y.dataset.y ? '' : y.dataset.y; syncURL(); render(run); return; }
    if (e.target.closest('[data-more]') && RES) { more(run); return; }
    const x = e.target.closest('.sr-expand');
    if (x) { $$('li[hidden]', x.parentNode).forEach((li) => { li.hidden = false; }); x.remove(); }
  });
  document.addEventListener('keydown', (e) => {
    const typing = e.target.closest && e.target.closest('input, textarea, [contenteditable]');
    if ((e.key === '/' && !typing) || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) { e.preventDefault(); input.focus(); input.select(); }
  });

  EN.meta().catch(() => {});
  ZH.meta().catch(() => {});
  readURL();
  search();
  if (!state.q) input.focus({ preventScroll: true });
})();
