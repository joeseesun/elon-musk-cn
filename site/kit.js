/* 马斯克全访谈 · 共用小工具：英文段落翻译 / 划线复制与海报 / 金句海报。在视频页与语录页加载 */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const CJK = /[\u3400-\u9fff]/;
  const track = (e, d) => { if (window.umami) window.umami.track(e, d); };

  /* ---------- 翻译：先走本站 /api/tr（国内可用），失败再直连谷歌；按句切块，避开反代的 URL 长度上限 ---------- */
  const TR_KEY = 'em-ptr:';
  const hash = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(36); };
  function chunks(text, max) {
    const sents = text.match(/[^.!?。！？]+[.!?。！？]*["”’)]*\s*/g) || [text];
    const out = [];
    let cur = '';
    sents.forEach((s) => {
      if ((cur + s).length > max && cur) { out.push(cur); cur = ''; }
      while (s.length > max) { out.push(s.slice(0, max)); s = s.slice(max); }
      cur += s;
    });
    if (cur.trim()) out.push(cur);
    return out;
  }
  async function trChunk(q, tl) {
    const parse = (d) => (d && d[0] ? d[0].map((x) => x[0] || '').join('') : '');
    const urls = [`/api/tr?tl=${tl}&q=${encodeURIComponent(q)}`,
      `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&dt=t&tl=${tl}&q=${encodeURIComponent(q)}`];
    for (const u of urls) {
      try {
        const ctl = new AbortController();
        const timer = setTimeout(() => ctl.abort(), 7000);
        const r = await fetch(u, { signal: ctl.signal });
        clearTimeout(timer);
        if (!r.ok) continue;
        const t = parse(await r.json());
        if (t) return t;
      } catch (e) { /* 换下一个 */ }
    }
    throw new Error('translate failed');
  }
  async function translate(text, tl) {
    tl = tl || (CJK.test(text) ? 'en' : 'zh-CN');
    const key = TR_KEY + tl + ':' + hash(text);
    try { const c = sessionStorage.getItem(key); if (c) return c; } catch (e) {}
    const parts = await Promise.all(chunks(text.replace(/\s+/g, ' ').trim(), 420).map((c) => trChunk(c, tl)));
    const out = parts.join(tl === 'en' ? ' ' : '');
    try { sessionStorage.setItem(key, out); } catch (e) {}
    return out;
  }

  /* ---------- 页面上下文：标题、日期、深链 ---------- */
  const pageTitle = () => ((($('.ep-title') || {}).textContent) || document.title.split(/[|·]/)[0]).trim();
  const pageDate = () => { const t = $('.ep-byline time, .byline time, time[datetime]'); return t ? t.textContent.replace(/（约）/, '').trim() : ''; };
  const toSec = (t) => { const p = String(t).split(':').map(Number); return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1]; };
  function contextOf(node) {
    const el = node && (node.nodeType === 1 ? node : node.parentElement);
    if (!el) return null;
    const base = location.origin + location.pathname;
    const trP = el.closest('.transcript-text p');
    if (trP) {
      const ts = $('.ts-link', trP);
      const k = (trP.id || '').replace(/^p/, '');
      const sec = ts ? toSec(ts.dataset.t) : null;
      const q = new URLSearchParams();
      if (k) q.set('p', k);
      if (sec != null && isFinite(sec)) q.set('t', sec);
      return { kind: 'tr', lang: 'en', ts: ts ? ts.dataset.t : '', url: base + (q.toString() ? '?' + q : ''), title: pageTitle(), date: pageDate() };
    }
    const zb = el.closest('.zh-article [data-z]');
    if (zb || el.closest('.zh-article')) {
      return { kind: 'zh', lang: 'zh', ts: '', url: base + (zb ? '?z=' + zb.dataset.z : ''), title: pageTitle(), date: pageDate() };
    }
    const qi = el.closest('.quote-item');
    if (qi) {
      const ts = $('.ts-link', qi);
      const sec = ts ? toSec(ts.dataset.t) : null;
      return { kind: 'q', lang: '', ts: ts ? ts.dataset.t : '', url: base + (sec != null && isFinite(sec) ? '?t=' + sec : ''), title: pageTitle(), date: pageDate() };
    }
    const qy = el.closest('.qy-item, li');
    if (qy && el.closest('.qy-year')) {
      const meta = $('.qy-meta', qy);
      const src = meta ? (($('.qy-src-text', meta) || {}).textContent || '') : '';
      const d = meta ? ((meta.querySelector('span') || {}).textContent || '') : '';
      const yr = qy.closest('.qy-year');
      return { kind: 'qy', lang: '', ts: '', url: base + (yr && yr.id ? '#' + yr.id : ''), title: src || '马斯克语录', date: d };
    }
    return null;
  }
  const cite = (ctx) => `—— 马斯克${ctx.kind === 'zh' ? '（中文精读）' : ''}，${ctx.title ? '《' + ctx.title + '》' : ''}${ctx.date ? ' ' + ctx.date : ''}${ctx.ts ? ' ' + ctx.ts : ''}\n${ctx.url}`;

  async function copyText(txt) {
    try { await navigator.clipboard.writeText(txt); return true; } catch (e) {}
    const ta = document.createElement('textarea');
    ta.value = txt;
    ta.style.cssText = 'position:fixed;left:-9999px;top:0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) {}
    ta.remove();
    return ok;
  }
  let toastT;
  function toast(msg) {
    let t = $('.kit-toast');
    if (!t) { t = document.createElement('div'); t.className = 'kit-toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastT);
    toastT = setTimeout(() => t.classList.remove('show'), 1800);
  }

  /* ---------- 英文段落：悬停出现「译」，点击在段落下方展开中文 ---------- */
  const trBox = $('.transcript-text');
  if (trBox) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tr-btn';
    btn.setAttribute('aria-label', '翻译这一段');
    btn.title = '翻译这一段';
    btn.textContent = '译';
    const attach = (p) => {
      if (!p || btn.parentNode === p) return;
      p.appendChild(btn);
      const nx = p.nextElementSibling;
      btn.classList.toggle('on', !!(nx && nx.classList.contains('tr-pop')));
    };
    trBox.addEventListener('pointerover', (e) => { if (e.pointerType === 'mouse') attach(e.target.closest('.transcript-text > p')); });
    trBox.addEventListener('click', (e) => {
      if (e.target.closest('.tr-btn, .ts-link, .tr-pop')) return;
      const sel = window.getSelection();
      if (sel && !sel.isCollapsed) return;
      attach(e.target.closest('.transcript-text > p'));
    });
    trBox.addEventListener('click', async (e) => {
      const b = e.target.closest('.tr-btn');
      if (!b) return;
      e.preventDefault();
      const p = b.parentNode;
      const next = p.nextElementSibling;
      if (next && next.classList.contains('tr-pop')) { next.remove(); b.classList.remove('on'); return; }
      const src = Array.from(p.childNodes).filter((n) => !(n.nodeType === 1 && n.matches('.ts-link, .tr-btn'))).map((n) => n.textContent).join('').trim();
      const pop = document.createElement('div');
      pop.className = 'tr-pop';
      pop.setAttribute('role', 'note');
      pop.innerHTML = '<div class="tr-pop-h"><span>中文翻译 · 谷歌机翻</span><button type="button" class="tr-pop-x" aria-label="收起翻译">×</button></div><p class="tr-pop-t">翻译中…</p>';
      p.after(pop);
      b.classList.add('on');
      track('para-translate');
      try {
        const zh = await translate(src, 'zh-CN');
        $('.tr-pop-t', pop).textContent = zh;
        const h = $('.tr-pop-h', pop);
        const cp = document.createElement('button');
        cp.type = 'button';
        cp.className = 'tr-pop-cp';
        cp.textContent = '复制';
        h.insertBefore(cp, $('.tr-pop-x', h));
        cp.addEventListener('click', async () => {
          const ctx = contextOf(p);
          if (await copyText(`${zh}\n${src}\n${ctx ? cite(ctx) : location.href}`)) toast('已复制译文与原文');
        });
      } catch (err) {
        $('.tr-pop-t', pop).innerHTML = '翻译服务暂时连不上，稍后再试。';
      }
    });
    trBox.addEventListener('click', (e) => {
      const x = e.target.closest('.tr-pop-x');
      if (!x) return;
      const pop = x.closest('.tr-pop');
      const p = pop.previousElementSibling;
      pop.remove();
      if (p) { const b = $('.tr-btn', p); if (b) b.classList.remove('on'); }
    });
  }

  /* ---------- 划线：复制（带出处）/ 生成海报 / 翻译 ---------- */
  const bar = document.createElement('div');
  bar.className = 'sel-bar';
  bar.hidden = true;
  bar.setAttribute('role', 'toolbar');
  bar.setAttribute('aria-label', '选中文字操作');
  bar.innerHTML = '<button type="button" data-a="copy">复制</button><button type="button" data-a="poster">生成海报</button><button type="button" data-a="tr">翻译</button>';
  document.body.appendChild(bar);
  let selCtx = null, selText = '';
  const ZONES = '.zh-article, .transcript-text, .quotes-list, .qy-year';
  function readSel() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const txt = sel.toString().replace(/\s+/g, ' ').trim();
    if (txt.length < 4) return null;
    const r = sel.getRangeAt(0);
    const host = (r.commonAncestorContainer.nodeType === 1 ? r.commonAncestorContainer : r.commonAncestorContainer.parentElement);
    if (!host || !host.closest(ZONES) || host.closest('.tr-pop, .sel-bar')) return null;
    const ctx = contextOf(r.startContainer);
    if (!ctx) return null;
    return { txt, rect: r.getBoundingClientRect(), ctx };
  }
  function showBar() {
    const s = readSel();
    if (!s) { bar.hidden = true; return; }
    selCtx = s.ctx;
    selText = s.txt;
    $('[data-a="tr"]', bar).hidden = CJK.test(selText) && !/[a-z]{3}/i.test(selText);
    bar.hidden = false;
    const touch = matchMedia('(hover: none)').matches;
    const bw = bar.offsetWidth, bh = bar.offsetHeight;
    let x = s.rect.left + s.rect.width / 2 - bw / 2;
    x = Math.max(8, Math.min(x, innerWidth - bw - 8));
    // 触屏上系统菜单在选区上方，工具条放到选区下方
    let y = touch ? s.rect.bottom + 12 : s.rect.top - bh - 10;
    if (y < 8) y = s.rect.bottom + 10;
    if (y + bh > innerHeight - 8) y = Math.max(8, s.rect.top - bh - 10);
    bar.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  }
  let selT;
  document.addEventListener('selectionchange', () => { clearTimeout(selT); selT = setTimeout(showBar, 260); });
  window.addEventListener('scroll', () => { if (!bar.hidden) showBar(); }, { passive: true });
  bar.addEventListener('mousedown', (e) => e.preventDefault());
  bar.addEventListener('click', async (e) => {
    const b = e.target.closest('button');
    if (!b || !selCtx) return;
    const a = b.dataset.a;
    const txt = selText, ctx = selCtx;
    if (a === 'copy') {
      if (await copyText(`“${txt}”\n${cite(ctx)}`)) toast('已复制，带出处链接');
      track('sel-copy', { k: ctx.kind });
    } else if (a === 'poster') {
      const en = !CJK.test(txt);
      openPoster({ main: txt, en: en ? txt : '', needZh: en, ctx });
      track('sel-poster', { k: ctx.kind });
    } else if (a === 'tr') {
      bar.hidden = true;
      showTrPop(txt);
      track('sel-translate');
    }
  });

  function showTrPop(txt) {
    const m = modal('<div class="kit-tr"><p class="kit-tr-src" lang="en"></p><p class="kit-tr-out">翻译中…</p></div>', '翻译');
    $('.kit-tr-src', m).textContent = txt;
    translate(txt).then((t) => { $('.kit-tr-out', m).textContent = t; }, () => { $('.kit-tr-out', m).textContent = '翻译服务暂时连不上，稍后再试。'; });
  }

  /* ---------- 金句卡片上的「海报」按钮 ---------- */
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-poster-q]');
    if (!b) return;
    const item = b.closest('.quote-item, li');
    const zh = (($('.q-zh', item) || {}).textContent || '').trim();
    const enEl = $('.q-en', item) || $('.qy-quote:not(.bi)', item);
    let en = enEl ? enEl.textContent.trim() : '';
    if (!zh && !en) {
      const c = item.cloneNode(true);
      $$('.ts-link, button, .q-foot', c).forEach((n) => n.remove());
      en = c.textContent.replace(/\s+/g, ' ').trim();
    }
    const ctx = contextOf(b) || { kind: 'q', ts: '', url: location.href, title: pageTitle(), date: pageDate() };
    openPoster({ main: zh || en, en, zh, needZh: !zh && !!en, ctx });
    track('quote-poster');
  });

  /* ---------- 弹层 ---------- */
  function modal(inner, label) {
    closeModal();
    const m = document.createElement('div');
    m.className = 'kit-modal';
    m.setAttribute('role', 'dialog');
    m.setAttribute('aria-modal', 'true');
    m.setAttribute('aria-label', label);
    m.innerHTML = `<div class="kit-card">${inner}<button type="button" class="kit-x" aria-label="关闭">×</button></div>`;
    document.body.appendChild(m);
    document.body.classList.add('kit-open');
    m.addEventListener('click', (e) => { if (e.target === m || e.target.closest('.kit-x')) closeModal(); });
    requestAnimationFrame(() => m.classList.add('show'));
    const x = $('.kit-x', m);
    if (x) x.focus({ preventScroll: true });
    return m;
  }
  function closeModal() {
    const m = $('.kit-modal');
    if (!m) return;
    m.remove();
    document.body.classList.remove('kit-open');
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

  /* ---------- 海报：canvas 画成 PNG，含二维码 ---------- */
  let qrLoad;
  const loadQR = () => qrLoad || (qrLoad = new Promise((res, rej) => {
    if (window.qrcode) return res(window.qrcode);
    const s = document.createElement('script');
    s.src = '/vendor/qrcode.js?v=1';
    s.onload = () => res(window.qrcode);
    s.onerror = () => { qrLoad = null; rej(new Error('qr')); };
    document.head.appendChild(s);
  }));

  const SERIF = '"Songti SC", "STSong", "Noto Serif SC", "Source Han Serif SC", "Noto Serif CJK SC", "SimSun", serif';
  const LATIN = '"Libre Caslon Text", Georgia, "Times New Roman", serif';
  const SANS = '-apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
  const NO_START = /^[，。、：；！？）」』》”’,.;:!?)\]…—]/;

  function wrap(ctx, text, maxW, maxLines) {
    const toks = text.match(/[A-Za-z0-9'’\-.,;:!?%$]+\s*|\s+|./gu) || [];
    const lines = [];
    let line = '';
    for (let i = 0; i < toks.length; i++) {
      const t = toks[i];
      if (!line && /^\s+$/.test(t)) continue;
      const test = line + t;
      if (ctx.measureText(test.trimEnd()).width > maxW && line) {
        if (NO_START.test(t) && line.length > 1) { lines.push(line.slice(0, -1).trimEnd()); line = line.slice(-1) + t; }
        else { lines.push(line.trimEnd()); line = /^\s+$/.test(t) ? '' : t; }
        if (lines.length === maxLines) break;
      } else line = test;
    }
    if (lines.length < maxLines && line.trim()) lines.push(line.trimEnd());
    const used = lines.join('').replace(/\s/g, '').length;
    if (used < text.replace(/\s/g, '').length - 1 && lines.length) {
      let last = lines[lines.length - 1];
      while (last.length && ctx.measureText(last + '……').width > maxW) last = last.slice(0, -1);
      lines[lines.length - 1] = last + '……';
    }
    return lines;
  }

  async function drawPoster(o) {
    const W = 1080, P = 92, CW = W - P * 2;
    const c = document.createElement('canvas');
    const g = c.getContext('2d');
    const zh = o.zh || (CJK.test(o.main) ? o.main : '');
    const en = o.en && o.en !== zh ? o.en : '';
    const L = {};
    g.font = `500 ${zh.length > 120 ? 42 : 50}px ${SERIF}`;
    L.zhFont = g.font;
    L.zh = zh ? wrap(g, zh, CW, 13) : [];
    L.zhLH = zh.length > 120 ? 74 : 86;
    g.font = `italic ${zh ? 30 : 46}px ${LATIN}`;
    L.enFont = g.font;
    L.en = en ? wrap(g, en, CW, zh ? 7 : 14) : [];
    L.enLH = zh ? 46 : 70;
    g.font = `400 28px ${SERIF}`;
    L.srcFont = g.font;
    const src = (o.ctx.title || '').trim();
    L.src = src ? wrap(g, src, CW, 2) : [];
    const markY = 324;
    let h = markY - 58;
    h += L.zh.length * L.zhLH + (L.zh.length && L.en.length ? 34 : 0) + L.en.length * L.enLH;
    h += 70 + 44 + L.src.length * 42 + 60;
    h += 290 + P;
    c.width = W;
    c.height = Math.max(h, 1080);
    g.fillStyle = '#faf8f3';
    g.fillRect(0, 0, W, c.height);
    // 报头
    g.fillStyle = '#111';
    g.font = `700 30px ${LATIN}`;
    g.textBaseline = 'alphabetic';
    g.fillText('ELON MUSK', P, 112);
    const ew = g.measureText('ELON MUSK').width;
    g.font = `500 28px ${SERIF}`;
    g.fillText(' 全访谈', P + ew, 112);
    g.font = `400 22px ${SANS}`;
    g.fillStyle = '#6b6b67';
    const kick = o.ctx.kind === 'zh' ? '中文精读摘句' : '马斯克原话';
    g.fillText(kick, W - P - g.measureText(kick).width, 112);
    g.fillStyle = '#111';
    g.fillRect(P, 136, CW, 3);
    g.fillRect(P, 144, CW, 1);
    // 引号
    g.fillStyle = '#b3261e';
    g.font = `700 150px ${LATIN}`;
    g.fillText('“', P - 8, markY);
    let y = markY - 58;
    g.fillStyle = '#111';
    g.font = L.zhFont;
    L.zh.forEach((ln) => { y += L.zhLH; g.fillText(ln, P, y - 18); });
    if (L.zh.length && L.en.length) y += 34;
    g.fillStyle = zh ? '#55554f' : '#111';
    g.font = L.enFont;
    L.en.forEach((ln) => { y += L.enLH; g.fillText(ln, P, y - 14); });
    // 出处
    y += 70;
    g.fillStyle = '#111';
    g.font = `600 30px ${SERIF}`;
    g.fillText(o.ctx.kind === 'zh' ? '—— 摘自中文精读（AI 改写，以原视频为准）' : '—— 埃隆·马斯克', P, y);
    y += 44;
    g.fillStyle = '#55554f';
    g.font = L.srcFont;
    L.src.forEach((ln) => { g.fillText(ln, P, y); y += 42; });
    const meta = [o.ctx.date, o.ctx.ts ? '视频 ' + o.ctx.ts : ''].filter(Boolean).join(' · ');
    if (meta) { g.font = `400 24px ${SANS}`; g.fillStyle = '#8a8a85'; g.fillText(meta, P, y); }
    // 页脚 + 二维码
    const fy = c.height - P - 220;
    g.fillStyle = '#d8d6cf';
    g.fillRect(P, fy - 30, CW, 1);
    g.fillStyle = '#111';
    g.font = `700 38px ${SERIF}`;
    g.fillText('马斯克全访谈', P, fy + 52);
    g.font = `400 26px ${SANS}`;
    g.fillStyle = '#55554f';
    g.fillText('651 个公开视频 · 中文精读 · 原话检索', P, fy + 104);
    g.fillStyle = '#b3261e';
    g.font = `600 26px ${SANS}`;
    g.fillText('elon.qiaomu.ai', P, fy + 152);
    g.fillStyle = '#8a8a85';
    g.font = `400 22px ${SANS}`;
    g.fillText('长按识别二维码，看原视频这一刻', P, fy + 196);
    try {
      const qrcode = await loadQR();
      const qr = qrcode(0, 'M');
      qr.addData(o.ctx.url);
      qr.make();
      const n = qr.getModuleCount(), S = 220, q = 10, cell = (S - q * 2) / n;
      const qx = W - P - S, qy = fy - 4;
      g.fillStyle = '#fff';
      g.fillRect(qx, qy, S, S);
      g.fillStyle = '#111';
      for (let r = 0; r < n; r++) for (let k = 0; k < n; k++) if (qr.isDark(r, k)) g.fillRect(qx + q + k * cell, qy + q + r * cell, Math.ceil(cell), Math.ceil(cell));
    } catch (e) { /* 二维码失败时只留网址 */ }
    return c;
  }

  async function openPoster(o) {
    const m = modal('<div class="kit-poster"><div class="kit-pv"><p class="kit-wait">海报生成中…</p></div>' +
      '<div class="kit-acts"><a class="kit-dl" download="elon-musk-quote.png">保存图片</a><button type="button" class="kit-cp" hidden>复制图片</button></div>' +
      '<p class="kit-hint">手机上长按图片，可保存或直接发给朋友</p></div>', '分享海报');
    bar.hidden = true;
    try {
      if (o.needZh && !o.zh) {
        try { o.zh = await translate(o.en || o.main, 'zh-CN'); } catch (e) { o.zh = ''; }
      }
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
      const c = await drawPoster(o);
      if (!m.isConnected) return;
      const url = c.toDataURL('image/png');
      const img = new Image();
      img.alt = '分享海报';
      img.src = url;
      const pv = $('.kit-pv', m);
      pv.innerHTML = '';
      pv.appendChild(img);
      $('.kit-dl', m).href = url;
      const cp = $('.kit-cp', m);
      if (window.ClipboardItem && navigator.clipboard && navigator.clipboard.write && !matchMedia('(hover: none)').matches) {
        cp.hidden = false;
        cp.addEventListener('click', () => c.toBlob(async (blob) => {
          try { await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]); toast('图片已复制'); } catch (e) { toast('复制失败，请用「保存图片」'); }
        }));
      }
    } catch (err) {
      $('.kit-pv', m).innerHTML = '<p class="kit-wait">海报生成失败，请重试。</p>';
    }
  }

  window.EMKit = { translate, openPoster };
})();
