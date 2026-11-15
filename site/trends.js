/* 马斯克全访谈 · 话题趋势：输入几个词，画出它们在文稿里逐年出现的频率（每千段）。检索核心来自 search.js 的 window.EMSearch */
(function () {
  'use strict';
  const S = window.EMSearch;
  const $ = (s, r) => (r || document).querySelector(s);
  const input = $('#ngq'), out = $('#ngOut');
  if (!S || !input || !out) return;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const COLORS = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)'];
  const Y0 = 2008;
  let run = 0;

  function splitTerms(q) {
    return q.split(/[,，、;；]|\s+vs\.?\s+/i).map((s) => s.trim()).filter(Boolean).slice(0, 4);
  }

  async function series(term, meta) {
    const parsed = S.parse(term);
    if (!parsed.concepts.length) return { term, err: '太常见' };
    await S.translateConcepts(parsed);
    const groups = parsed.concepts.filter((c) => c.en.length).map((c) => c.en);
    if (!groups.length) return { term, err: '没翻译出来' };
    const r = await S.runCorpus(S.EN, groups);
    const per = new Map();
    r.byEp.forEach((gs, k) => { const y = +(meta.eps[k][2] || '').slice(0, 4); if (y) per.set(y, (per.get(y) || 0) + gs.length); });
    const label = parsed.concepts.map((c) => (/[\u3400-\u9fff]/.test(c.src) ? `${c.src}（${c.en.slice(0, 2).map((a) => a.label).join(' / ')}）` : c.src)).join(' + ');
    const approx = groups.some((alts) => alts.some((a) => a.phrase || a.keys.length > 1));
    return { term, label, per, total: r.hits.length, approx };
  }

  function totals(meta) {
    const t = new Map();
    meta.eps.forEach((e, k) => {
      const y = +(e[2] || '').slice(0, 4);
      if (!y) return;
      const n = (k + 1 < meta.eps.length ? meta.eps[k + 1][1] : meta.n) - e[1];
      t.set(y, (t.get(y) || 0) + n);
    });
    return t;
  }

  function chart(list, tot) {
    const years = [...tot.keys()].filter((y) => y >= Y0).sort((a, b) => a - b);
    const W = 720, H = 300, L = 40, R = 14, T = 16, B = 30;
    const x = (i) => L + (i / (years.length - 1)) * (W - L - R);
    const vals = list.map((s) => years.map((y) => (tot.get(y) ? ((s.per.get(y) || 0) * 1000) / tot.get(y) : 0)));
    const max = Math.max(1, ...vals.flat());
    const nice = (m) => { const p = Math.pow(10, Math.floor(Math.log10(m))); const f = m / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; };
    const step = nice(max / 4);
    const nStep = Math.max(1, Math.ceil(max / step - 1e-9));
    const top = step * nStep;
    const y = (v) => T + (1 - v / top) * (H - T - B);
    const grid = Array.from({ length: nStep + 1 }, (_, i) => step * i).map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="ng-grid"/><text x="${L - 6}" y="${y(v) + 4}" class="ng-yl">${+v.toFixed(2)}</text>`).join('');
    const xl = years.map((yr, i) => (yr % 2 === 0 || i === years.length - 1) ? `<text x="${x(i)}" y="${H - 10}" class="ng-xl">${yr % 100 === 0 || i === 0 ? yr : String(yr).slice(2)}</text>` : '').join('');
    const lines = vals.map((vs, si) => {
      const d = vs.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
      const dots = vs.map((v, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="2.6"/>`).join('');
      return `<g class="ng-line" style="--lc:${COLORS[si]}"><path d="${d}"/>${dots}</g>`;
    }).join('');
    return { svg: `<svg class="ng-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="逐年出现频率折线图">${grid}${xl}${lines}<line class="ng-cursor" x1="0" x2="0" y1="${T}" y2="${H - B}" visibility="hidden"/></svg>`, years, vals, x, W };
  }

  async function draw(q, sync) {
    const my = ++run;
    const terms = splitTerms(q);
    if (sync) {
      const url = new URL(location.href);
      if (terms.length) url.searchParams.set('q', terms.join(', ')); else url.searchParams.delete('q');
      history.replaceState(null, '', url.pathname + url.search + '#ngram');
    }
    if (!terms.length) { out.innerHTML = ''; return; }
    out.innerHTML = '<p class="ins-note">翻译并统计中…</p>';
    let meta;
    try { meta = await S.EN.meta(); } catch (e) { out.innerHTML = '<p class="ins-note">索引加载失败，请检查网络后重试。</p>'; return; }
    const list = await Promise.all(terms.map((t) => series(t, meta).catch(() => ({ term: t, err: '加载失败' }))));
    if (my !== run) return;
    const ok = list.filter((s) => !s.err);
    const bad = list.filter((s) => s.err).map((s) => `「${esc(s.term)}」${s.err}`).join('，');
    if (!ok.length) { out.innerHTML = `<p class="ins-note">${bad || '没有结果'}</p>`; return; }
    const tot = totals(meta);
    const c = chart(ok, tot);
    const legend = ok.map((s, i) => `<a class="ng-lg" style="--lc:${COLORS[i]}" href="/search/?q=${encodeURIComponent(s.term)}"><i></i><b>${esc(s.label)}</b><small>${s.approx ? '约 ' : ''}${s.total.toLocaleString()} 段</small></a>`).join('');
    out.innerHTML = `<div class="ng-legend">${legend}</div><div class="ng-chart">${c.svg}<div class="ng-tip" hidden></div></div>
      <p class="ins-note">纵轴：那一年每 1000 个文稿段落里有几段提到这个词。${ok.some((s) => s.approx) ? '多词与短语按「同一段里都出现」近似计算。' : ''}${bad ? ' 未统计：' + bad + '。' : ''}点图例去看原话。</p>`;
    const svg = $('.ng-svg', out), tip = $('.ng-tip', out), cur = $('.ng-cursor', out);
    const move = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * c.W;
      let best = 0, bd = Infinity;
      c.years.forEach((yr, i) => { const d = Math.abs(c.x(i) - px); if (d < bd) { bd = d; best = i; } });
      cur.setAttribute('x1', c.x(best)); cur.setAttribute('x2', c.x(best)); cur.setAttribute('visibility', 'visible');
      tip.hidden = false;
      tip.innerHTML = `<b>${c.years[best]}</b>` + ok.map((s, si) => `<span style="--lc:${COLORS[si]}"><i></i>${esc(s.term)} ${c.vals[si][best].toFixed(1)}</span>`).join('');
      const left = (c.x(best) / c.W) * r.width;
      tip.style.left = Math.min(Math.max(left, 60), r.width - 60) + 'px';
    };
    svg.addEventListener('pointermove', move);
    svg.addEventListener('pointerdown', move);
    svg.addEventListener('pointerleave', () => { tip.hidden = true; cur.setAttribute('visibility', 'hidden'); });
  }

  $('.ng-form').addEventListener('submit', () => { draw(input.value, true); input.blur(); });
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-ng]');
    if (!b) return;
    input.value = b.dataset.ng;
    draw(b.dataset.ng, true);
  });
  const q0 = new URLSearchParams(location.search).get('q');
  input.value = q0 || '火星, 人工智能';
  draw(input.value);
})();
