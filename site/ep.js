/* 马斯克全访谈 · 视频页：tab 切换 / 阅读设置 / 目录 / 视频懒加载 / 时间戳跳播 */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => (s || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ls = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { localStorage.removeItem(k); } catch (e) {} },
  };
  const html = document.documentElement;
  const slug = (location.pathname.match(/\/ep\/([^/]+)/) || [])[1];

  document.body.classList.add('epjs');

  /* ---------- 阅读历史（首页「继续」用）：em-hist = {slug: {rp, at}} ---------- */
  function histUpdate(patch) {
    if (!slug) return;
    let h = {};
    try { h = JSON.parse(ls.get('em-hist') || '{}') || {}; } catch (e) {}
    h[slug] = Object.assign(h[slug] || {}, patch, { at: Date.now() });
    const keys = Object.keys(h).sort((a, b) => h[b].at - h[a].at);
    keys.slice(40).forEach((k) => delete h[k]);
    ls.set('em-hist', JSON.stringify(h));
  }
  const histGet = () => { try { return (JSON.parse(ls.get('em-hist') || '{}') || {})[slug] || {}; } catch (e) { return {}; } };

  /* ---------- 返回顶部 ---------- */
  const toTop = document.createElement('button');
  toTop.id = 'toTop';
  toTop.type = 'button';
  toTop.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5.5 11.5L12 5l6.5 6.5"/></svg>';
  toTop.setAttribute('aria-label', '回到顶部');
  toTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  document.body.appendChild(toTop);

  /* ---------- 内容 tab：中文精读 / 英文文稿 / 金句 ---------- */
  const tabsRow = $('.tabs');
  const tabBtns = $$('.tab-btn');
  const panels = $$('.tab-panel');
  const article = $('.zh-article');
  let current = null;
  function activate(name) {
    current = name;
    tabBtns.forEach((b) => {
      const on = b.dataset.tab === name;
      b.classList.toggle('on', on);
      b.setAttribute('aria-selected', on);
    });
    panels.forEach((p) => p.classList.toggle('active', p.dataset.panel === name));
    syncTools();
  }

  /* ---------- 正文细节：首字下沉 / 摘句署名与悬挂引号 / 西文 em / 文末终止符 ---------- */
  if (article) {
    const CJK = /[㐀-鿿]/;
    const firstP = $(':scope > p', article);
    if (firstP && CJK.test(firstP.textContent.trim().charAt(0))) firstP.classList.add('dropcap');
    $$('blockquote', article).forEach((q) => {
      const tail = q.lastChild && q.lastChild.nodeType === 3 ? q.lastChild : null;
      const m = tail && tail.nodeValue.match(/^([\s\S]*?)[（(]([^（）()]{1,40})[）)]\s*$/);
      if (m) {
        tail.nodeValue = m[1].replace(/\s+$/, '');
        const c = document.createElement('cite');
        c.textContent = m[2];
        q.appendChild(c);
      }
      if (/^[「“『‘"]/.test(q.textContent.trim())) q.classList.add('hang');
    });
    $$('em', article).forEach((em) => { if (!CJK.test(em.textContent)) em.classList.add('latin'); });
    let last = article.lastElementChild;
    while (last && (last.tagName === 'UL' || last.tagName === 'OL')) last = last.lastElementChild;
    if (last && /^(P|LI|BLOCKQUOTE)$/.test(last.tagName)) last.classList.add('end-mark');
  }

  /* ---------- 阅读工具（tabs 右端）：目录 + 阅读设置 Aa ---------- */
  let tools, tocBtn, aaBtn, aaPop, tocPop, progress, aside;
  const heads = article ? $$('h2', article) : [];
  const css = (k) => getComputedStyle(html).getPropertyValue(k).trim();
  const SIZE = { min: 15, max: 22, def: 18 };
  const LH = [['1.75', '紧凑'], ['2', '适中'], ['2.25', '宽松']];
  const MEASURE = [['600', '窄'], ['680', '标准'], ['760', '宽']];
  const FONTS = [
    ['sys', '系统默认', '苹方 / 雅黑', ''],
    ['sans', '思源黑体', 'Noto Sans SC', '"Noto Sans SC"'],
    ['serif', '思源宋体', 'Noto Serif SC', '"Noto Serif SC"'],
    ['song', '京華老宋', 'KingHwa OldSong', '"KingHwa_OldSong"'],
    ['kai', '霞鹜文楷', 'LXGW WenKai', '"LXGW WenKai Screen"'],
  ];
  const THEMES = [['light', '浅色', '#ffffff', '#111111'], ['sepia', '护眼', '#f5eddc', '#2f2618'], ['dark', '深色', '#141414', '#ebebe8']];
  const st = {
    size: parseInt(css('--read-size'), 10) || SIZE.def,
    lh: css('--read-lh') || '2',
    measure: String(parseInt(css('--measure'), 10) || 680),
    font: html.getAttribute('data-font') || 'sys',
  };

  if (tabsRow && article) {
    tools = document.createElement('div');
    tools.className = 'tab-tools';
    tools.innerHTML =
      (heads.length > 2 ? `<button type="button" class="tool-btn" data-tool="toc" aria-expanded="false" aria-haspopup="true" title="目录">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h11M4 18h14"/></svg><span class="lbl">目录</span></button>` : '') +
      `<button type="button" class="tool-btn" data-tool="aa" aria-expanded="false" aria-haspopup="true" title="阅读设置">
        <span class="aa">A<small>a</small></span><span class="lbl">阅读设置</span></button>`;
    tabsRow.appendChild(tools);
    tocBtn = $('[data-tool="toc"]', tools);
    aaBtn = $('[data-tool="aa"]', tools);

    aaPop = document.createElement('div');
    aaPop.className = 'pop';
    aaPop.hidden = true;
    aaPop.setAttribute('role', 'dialog');
    aaPop.setAttribute('aria-label', '阅读设置');
    aaPop.innerHTML = `
      <div class="pop-head"><span>阅读设置</span><button type="button" data-reset>恢复默认</button></div>
      <div class="swatches" data-k="theme" role="group" aria-label="背景">${THEMES.map(([v, n, bg, fg]) =>
        `<button type="button" data-v="${v}" style="background:${bg};color:${fg}">${n}</button>`).join('')}</div>
      <div class="font-list" data-k="font" role="group" aria-label="字体">${FONTS.map(([v, n, en, fam]) =>
        `<button type="button" data-v="${v}" title="${en}"${fam ? ` style='font-family:${fam},serif'` : ''}>${n}</button>`).join('')}</div>
      <div class="pop-pair">
        <div class="seg" data-k="size" role="group" aria-label="字号"><button type="button" data-v="-1" aria-label="缩小字号">A−</button><span class="sz"></span><button type="button" data-v="1" aria-label="放大字号">A+</button></div>
        <div class="seg seg-lh" data-k="lh" role="group" aria-label="行距">${LH.map(([v, n], i) =>
          `<button type="button" data-v="${v}" title="行距：${n}" aria-label="行距${n}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${['M5 8h14M5 12h14M5 16h14', 'M5 7h14M5 12h14M5 17h14', 'M5 5.5h14M5 12h14M5 18.5h14'][i]}"/></svg></button>`).join('')}</div>
      </div>
      <div class="seg seg-measure" data-k="measure" role="group" aria-label="版心宽度">${MEASURE.map(([v, n]) => `<button type="button" data-v="${v}">${n}栏</button>`).join('')}</div>`;
    tabsRow.appendChild(aaPop);
    if (window.matchMedia('(max-width: 760px)').matches) $('[data-k="measure"]', aaPop).hidden = true;

    progress = document.createElement('div');
    progress.className = 'read-progress';
    tabsRow.appendChild(progress);

    const press = (k, v) => $$(`[data-k="${k}"] button[data-v]`, aaPop).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === String(v))));
    const syncAa = () => {
      press('theme', html.getAttribute('data-theme'));
      press('font', st.font);
      press('lh', st.lh);
      press('measure', st.measure);
      $('.sz', aaPop).textContent = st.size;
      const [dn, up] = $$('[data-k="size"] button', aaPop);
      dn.disabled = st.size <= SIZE.min;
      up.disabled = st.size >= SIZE.max;
    };
    const apply = () => {
      html.style.setProperty('--read-size', st.size + 'px');
      html.style.setProperty('--read-lh', st.lh);
      html.style.setProperty('--measure', st.measure + 'px');
      html.classList.remove('indent');
      if (st.font === 'sys') html.removeAttribute('data-font');
      else { html.setAttribute('data-font', st.font); if (window.__lexLoadFont) window.__lexLoadFont(st.font); }
      ls.set('em-size', String(st.size));
      ls.set('em-lh', st.lh);
      ls.set('em-measure', st.measure);
      ls.set('em-font', st.font);
    };
    syncAa();
    document.addEventListener('lex-theme', syncAa);
    aaPop.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      const stuck = tabsRow.getBoundingClientRect().top <= 1;
      const anchor = stuck && heads.concat($$('p', article)).find((el) => el.getBoundingClientRect().top > 60);
      const before = anchor ? anchor.getBoundingClientRect().top : 0;
      if (b.hasAttribute('data-reset')) {
        Object.assign(st, { size: SIZE.def, lh: '2', measure: '680', font: 'serif' });
      } else {
        const k = b.parentNode.dataset.k;
        const v = b.dataset.v;
        if (k === 'theme') { if (window.__lexSetTheme) window.__lexSetTheme(v); }
        else if (k === 'font') st.font = v;
        else if (k === 'size') st.size = Math.min(SIZE.max, Math.max(SIZE.min, st.size + Number(v)));
        else if (k === 'lh') st.lh = v;
        else if (k === 'measure') st.measure = v;
        if (window.umami && k) window.umami.track('reading-setting', { k, v });
      }
      apply();
      if (anchor) window.scrollBy(0, anchor.getBoundingClientRect().top - before);
      syncAa();
    });

    /* 目录：宽屏是与正文一起居中的侧栏，窄屏为弹出层 */
    const main = $('.ep-main');
    aside = $('.ep-toc');
    if (heads.length > 2) {
      heads.forEach((h, i) => { if (!h.id) h.id = 's' + (i + 1); });
      const listHTML = '<ol class="toc-list">' + heads.map((h) => `<li><a href="#${h.id}">${esc(h.textContent)}</a></li>`).join('') + '</ol>';
      tocPop = document.createElement('div');
      tocPop.className = 'pop pop-toc';
      tocPop.hidden = true;
      tocPop.setAttribute('role', 'dialog');
      tocPop.setAttribute('aria-label', '目录');
      tocPop.innerHTML = listHTML;
      tabsRow.appendChild(tocPop);
      if (aside) aside.innerHTML = '<div class="toc-h">目录</div>' + listHTML;
      document.addEventListener('click', (e) => {
        const a = e.target.closest('.toc-list a');
        if (!a) return;
        e.preventDefault();
        const t = document.getElementById(a.getAttribute('href').slice(1));
        if (t) {
          t.scrollIntoView({ behavior: 'smooth', block: 'start' });
          history.replaceState(null, '', '#' + t.id);
        }
        closePops();
      });
    } else {
      if (main) main.classList.remove('has-toc');
      aside = null;
    }

    const pops = [[aaBtn, aaPop], [tocBtn, tocPop]].filter((x) => x[0] && x[1]);
    function closePops(except) {
      pops.forEach(([b, p]) => { if (p !== except) { p.hidden = true; b.setAttribute('aria-expanded', 'false'); } });
    }
    pops.forEach(([b, p]) => b.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = p.hidden;
      closePops(p);
      p.hidden = !open;
      b.setAttribute('aria-expanded', String(open));
      if (open && p === aaPop) FONTS.forEach(([k]) => window.__lexLoadFont && window.__lexLoadFont(k));
      if (open && p === tocPop) { const on = $('a.on', p); if (on) p.scrollTop = on.offsetTop - p.clientHeight / 3; }
    }));
    document.addEventListener('click', (e) => { if (!e.target.closest('.pop')) closePops(); });
    let ty = 0;
    document.addEventListener('touchstart', (e) => { ty = e.touches[0].clientY; }, { passive: true });
    document.addEventListener('touchmove', (e) => {
      const open = pops.find(([, p]) => !p.hidden);
      if (!open) return;
      const box = e.target.closest('.pop');
      if (!box) { e.preventDefault(); return; }
      const dy = e.touches[0].clientY - ty;
      const atTop = box.scrollTop <= 0, atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 1;
      if (box.scrollHeight <= box.clientHeight || (dy > 0 && atTop) || (dy < 0 && atEnd)) e.preventDefault();
    }, { passive: false });
    window.addEventListener('wheel', (e) => {
      const open = pops.find(([, p]) => !p.hidden);
      if (!open) return;
      const box = e.target.closest && e.target.closest('.pop');
      if (box && box.scrollHeight > box.clientHeight) return;
      if (box) e.preventDefault();
    }, { passive: false });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePops(); });
  }

  function syncTools() {
    const zhOn = current === 'zh';
    if (tools) tools.style.visibility = zhOn ? '' : 'hidden';
    if (progress) progress.style.display = zhOn ? '' : 'none';
    if (aside) aside.classList.toggle('is-off', !zhOn);
  }

  if (tabBtns.length) {
    tabBtns.forEach((b) => b.addEventListener('click', () => {
      const y = tabsRow.getBoundingClientRect().top <= 1 ? window.scrollY : null;
      activate(b.dataset.tab);
      if (y !== null) window.scrollTo({ top: tabsRow.parentNode.offsetTop - 1 });
    }));
    activate(tabBtns[0].dataset.tab);
  }

  /* ---------- 滚动：返回顶部 / 阅读进度 / 目录高亮 / 记录读到哪 ---------- */
  let tick = false, lastSaved = 0;
  function onScroll() {
    tick = false;
    toTop.classList.toggle('show', window.scrollY > 600);
    if (!article || current !== 'zh') return;
    const r = article.getBoundingClientRect();
    const total = r.height - window.innerHeight * 0.6;
    const p = Math.min(1, Math.max(0, -r.top / (total > 0 ? total : 1)));
    if (progress) progress.style.transform = `scaleX(${p})`;
    if (heads.length > 2) {
      let idx = -1;
      for (let i = 0; i < heads.length; i++) { if (heads[i].getBoundingClientRect().top < 110) idx = i; else break; }
      $$('.toc-list a').forEach((a) => a.classList.toggle('on', idx >= 0 && a.getAttribute('href') === '#' + heads[idx].id));
    }
    if (Math.abs(p - lastSaved) > 0.02 && p > 0.03) { lastSaved = p; histUpdate({ rp: Math.round(p * 1000) / 1000 }); }
  }
  window.addEventListener('scroll', () => { if (!tick) { tick = true; requestAnimationFrame(onScroll); } }, { passive: true });
  onScroll();

  /* 继续阅读：上次读到中段时，给一个可点的提示，不自动跳 */
  if (article && !location.hash && !/[?&](p|t|z)=/.test(location.search)) {
    const rp = histGet().rp || 0;
    if (rp > 0.06 && rp < 0.95) {
      const toast = document.createElement('div');
      toast.className = 'mini-player resume-toast';
      toast.innerHTML = `<div class="mp-body"><div class="mp-title">上次读到 ${Math.round(rp * 100)}%</div></div>
        <button type="button" class="chip" data-go>继续阅读</button><button type="button" class="mp-close" aria-label="关闭">×</button>`;
      document.body.appendChild(toast);
      requestAnimationFrame(() => toast.classList.add('show'));
      const hide = () => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); };
      $('[data-go]', toast).addEventListener('click', () => {
        if (current !== 'zh' && tabBtns.length) activate('zh');
        const r = article.getBoundingClientRect();
        window.scrollTo({ top: window.scrollY + r.top + rp * (r.height - window.innerHeight * 0.6), behavior: 'smooth' });
        hide();
      });
      $('.mp-close', toast).addEventListener('click', hide);
      setTimeout(hide, 9000);
    }
  }

  /* ---------- 视频：YouTube 懒加载（YT IFrame API）/ MP4 直链 ---------- */
  const facade = $('.video-facade');
  const mp4 = $('.mp4-player');
  const srcTabs = $('.src-tabs');
  let ytPlayer = null, pendingSeek = null, ytApiReady = false, biliFrame = null;
  // 有 B 站搬运时可切换来源；没手动选过的话，国内时区默认 B 站（YouTube 在国内打不开）
  let vsrc = facade && !facade.dataset.yt && facade.dataset.bv ? 'bili' : 'yt';
  function markSrc() {
    if (srcTabs) $$('[data-src]', srcTabs).forEach((b) => b.setAttribute('aria-selected', String(b.dataset.src === vsrc)));
    const lab = facade && $('.vf-play span', facade);
    if (lab) lab.textContent = vsrc === 'bili' ? '看视频 · B 站' : '看视频';
  }
  if (srcTabs && facade) {
    let saved = null;
    try { saved = localStorage.getItem('em-vsrc'); } catch (e) {}
    let tz = '';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) {}
    vsrc = saved === 'bili' || saved === 'yt' ? saved : (/^Asia\/(Shanghai|Chongqing|Chungking|Harbin|Urumqi)$/.test(tz) ? 'bili' : 'yt');
    srcTabs.addEventListener('click', (e) => {
      const b = e.target.closest('[data-src]');
      if (!b || b.dataset.src === vsrc) return;
      const live = media.classList.contains('video-open');
      vsrc = b.dataset.src;
      try { localStorage.setItem('em-vsrc', vsrc); } catch (err) {}
      markSrc();
      if (live) { resetMedia(); openVideo(); }
      if (window.umami) window.umami.track('video-src', { src: vsrc, slug });
    });
  }
  markSrc();

  const biliUrl = (sec) => `https://player.bilibili.com/player.html?isOutside=true&bvid=${encodeURIComponent(facade.dataset.bv)}&p=${Number(facade.dataset.bp) || 1}&autoplay=1&danmaku=0&high_quality=1${sec ? '&t=' + Math.floor(sec) : ''}`;
  function openBili(sec) {
    media.classList.add('video-open', 'is-live');
    if (!biliFrame) {
      biliFrame = document.createElement('iframe');
      biliFrame.className = 'bili-frame';
      biliFrame.title = (($('.ep-title') || {}).textContent || 'Elon Musk') + '（B 站）';
      biliFrame.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture';
      biliFrame.allowFullscreen = true;
      biliFrame.setAttribute('scrolling', 'no');
      biliFrame.src = biliUrl(sec);
      if (facade.isConnected) facade.replaceWith(biliFrame);
      else media.prepend(biliFrame);
    } else {
      biliFrame.src = biliUrl(sec);
    }
  }
  // 换来源：拆掉当前播放器，放回封面
  function resetMedia() {
    if (ytPlayer && ytPlayer.destroy) { try { ytPlayer.destroy(); } catch (e) {} }
    ytPlayer = null;
    biliFrame = null;
    unpin();
    Array.from(media.children).forEach((c) => { if (!c.classList.contains('pin-close')) c.remove(); });
    media.prepend(facade);
    media.classList.remove('video-open', 'is-live');
  }

  function loadYtApi() {
    if (ytApiReady) return;
    ytApiReady = true;
    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(tag);
  }

  function openVideo() {
    if (!facade) return Promise.resolve(null);
    if (vsrc === 'bili' && facade.dataset.bv) {
      openBili(pendingSeek || 0);
      pendingSeek = null;
      return Promise.resolve(null);
    }
    if (ytPlayer) return Promise.resolve(ytPlayer);
    if (!facade.isConnected) return Promise.resolve(null);
    const box = facade.closest('.media') || facade.parentNode;
    box.classList.add('video-open', 'is-live');
    const holder = document.createElement('div');
    holder.className = 'yt-holder';
    facade.replaceWith(holder);
    loadYtApi();
    return new Promise((resolve) => {
      let tries = 0;
      (function make() {
        if (window.YT && window.YT.Player) {
          ytPlayer = new window.YT.Player(holder, {
            videoId: facade.dataset.yt,
            playerVars: { autoplay: 1, rel: 0, origin: location.origin },
            events: {
              onReady: (e) => {
                resolve(e.target);
                if (pendingSeek != null) {
                  e.target.seekTo(pendingSeek, true);
                  e.target.playVideo();
                  pendingSeek = null;
                }
              },
            },
          });
        } else if (++tries < 100) {
          setTimeout(make, 100);
        } else if (facade.dataset.bv) {
          // YouTube 接口 10 秒没加载出来（多半是网络打不开），有 B 站源就直接换过去
          holder.remove();
          vsrc = 'bili';
          markSrc();
          openBili(pendingSeek || 0);
          pendingSeek = null;
          resolve(null);
        } else {
          // API 加载失败兜底：直接 iframe 自动播放
          const f = document.createElement('iframe');
          f.src = `https://www.youtube.com/embed/${facade.dataset.yt}?autoplay=1&rel=0`;
          f.title = ($('.ep-title') || {}).textContent || 'Elon Musk';
          f.allow = 'accelerometer; autoplay; encrypted-media; picture-in-picture';
          f.allowFullscreen = true;
          holder.replaceWith(f);
          resolve(null);
        }
      })();
    });
  }
  if (facade) facade.addEventListener('click', () => openVideo());

  function seekTo(sec) {
    if (vsrc === 'bili' && facade && facade.dataset.bv) {
      openBili(sec);
      pinOff = false;
      checkPin();
      return;
    }
    if (ytPlayer && ytPlayer.seekTo) {
      ytPlayer.seekTo(sec, true);
      if (ytPlayer.playVideo) ytPlayer.playVideo();
      pinOff = false;
      checkPin();
      return;
    }
    if (mp4) {
      mp4.currentTime = sec;
      mp4.play().catch(() => {});
      return;
    }
    pendingSeek = sec;
    if (facade) openVideo().then(() => { pinOff = false; checkPin(); });
  }
  const tsLabel = (s) => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };

  /* ---------- 文稿与金句：时间戳可点击跳播 + 文稿内搜索高亮 ---------- */
  const trText = $('.transcript-text');
  const toSec = (t) => {
    const p = t.split(':').map(Number);
    return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1];
  };
  const hasVideo = !!(facade || mp4);
  if (trText) {
    const tools2 = document.createElement('div');
    tools2.className = 'tr-tools';
    tools2.innerHTML = `<input class="tr-search" type="search" placeholder="在本篇文稿中搜索…" autocomplete="off" aria-label="在本篇文稿中搜索">
      <span class="tr-count" aria-live="polite"></span>${hasVideo ? '<span class="tr-hint">点击时间戳可跳到视频对应位置</span>' : ''}<a class="tr-all" href="/search/">搜全部文稿 →</a>`;
    trText.parentNode.insertBefore(tools2, trText);
    const inp = $('.tr-search', tools2);
    const cnt = $('.tr-count', tools2);
    const baseHTML = trText.innerHTML;
    let marks = [], cur = -1;
    const highlight = (q) => {
      const lq = q.toLowerCase();
      const walker = document.createTreeWalker(trText, NodeFilter.SHOW_TEXT);
      const targets = [];
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (node.nodeValue.toLowerCase().includes(lq)) targets.push(node);
      }
      targets.forEach((node) => {
        const frag = document.createDocumentFragment();
        const text = node.nodeValue;
        let i = 0, idx;
        const lower = text.toLowerCase();
        while ((idx = lower.indexOf(lq, i)) !== -1) {
          if (idx > i) frag.appendChild(document.createTextNode(text.slice(i, idx)));
          const mark = document.createElement('mark');
          mark.textContent = text.slice(idx, idx + q.length);
          frag.appendChild(mark);
          i = idx + q.length;
        }
        if (i < text.length) frag.appendChild(document.createTextNode(text.slice(i)));
        node.parentNode.replaceChild(frag, node);
      });
      return $$('mark', trText);
    };
    const go = (d) => {
      if (!marks.length) return;
      if (cur >= 0) marks[cur].classList.remove('cur');
      cur = (cur + d + marks.length) % marks.length;
      const m = marks[cur];
      m.classList.add('cur');
      trText.scrollTop += m.getBoundingClientRect().top - trText.getBoundingClientRect().top - trText.clientHeight / 3;
      $('.tr-pos', cnt).textContent = `${cur + 1} / ${marks.length}`;
    };
    let deb;
    inp.addEventListener('input', () => {
      clearTimeout(deb);
      deb = setTimeout(() => {
        const q = inp.value.trim();
        trText.innerHTML = baseHTML;
        marks = []; cur = -1;
        if (!q) { cnt.textContent = ''; return; }
        marks = highlight(q);
        if (!marks.length) { cnt.textContent = '无匹配'; return; }
        cnt.innerHTML = `<span class="tr-pos"></span><button type="button" data-d="-1" aria-label="上一处">↑</button><button type="button" data-d="1" aria-label="下一处">↓</button>`;
        go(1);
      }, 180);
    });
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); go(e.shiftKey ? -1 : 1); }
    });
    cnt.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) go(Number(b.dataset.d)); });
  }

  /* 时间戳点击 → 跳播（文稿与金句共用） */
  document.addEventListener('click', (e) => {
    const el = e.target.closest('.ts-link');
    if (!el) return;
    const s = toSec(el.dataset.t);
    if (!isFinite(s)) return;
    seekTo(s);
    if (window.umami) window.umami.track('ts-seek', { slug });
  });

  /* ---------- 小窗：视频滚出视口后固定在右下角，继续边看边读 ---------- */
  const media = $('.media');
  let pinOff = false;
  const pinClose = document.createElement('button');
  pinClose.type = 'button';
  pinClose.className = 'pin-close';
  pinClose.setAttribute('aria-label', '关闭小窗');
  pinClose.textContent = '×';
  if (media) media.appendChild(pinClose);
  function unpin() {
    if (!media || !media.classList.contains('pinned')) return;
    media.classList.remove('pinned');
    media.style.height = '';
    document.body.classList.remove('has-pin');
  }
  function checkPin() {
    if (!media || !media.classList.contains('is-live')) return;
    const r = media.getBoundingClientRect();
    if (r.bottom > 0) { pinOff = false; unpin(); return; }
    if (pinOff || media.classList.contains('pinned')) return;
    media.style.height = r.height + 'px';
    media.classList.add('pinned');
    document.body.classList.add('has-pin');
  }
  if (media && 'IntersectionObserver' in window) new IntersectionObserver(() => checkPin()).observe(media);
  pinClose.addEventListener('click', () => {
    pinOff = true;
    unpin();
    if (ytPlayer && ytPlayer.pauseVideo) ytPlayer.pauseVideo();
    if (mp4) mp4.pause();
    // B 站播放器跨域无法暂停，关小窗就直接停掉
    if (biliFrame) resetMedia();
  });
  if (mp4) mp4.addEventListener('play', () => { media.classList.add('is-live'); checkPin(); });

  /* ---------- 深链：?p=段落&t=秒&hl=高亮词（来自文稿搜索）/ ?z=精读段落&hl= / ?t=秒 ---------- */
  const params = new URLSearchParams(location.search);
  const pParam = params.get('p'), tParam = params.get('t'), zParam = params.get('z');
  const tSec = tParam != null && /^\d+(\.\d+)?$/.test(tParam) ? Number(tParam) : null;
  const deepPara = pParam != null && /^\d+$/.test(pParam) ? document.getElementById('p' + pParam) : null;
  const hlWords = (params.get('hl') || '').split(/\s+/).filter(Boolean).slice(0, 8);
  function highlightIn(el, words) {
    if (!words.length) return;
    const re = new RegExp('(' + words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi');
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) if (!walker.currentNode.parentNode.classList.contains('ts-link')) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const parts = node.nodeValue.split(re);
      if (parts.length < 2) return;
      const frag = document.createDocumentFragment();
      parts.forEach((s, i) => {
        if (!s) return;
        if (i % 2) { const m = document.createElement('mark'); m.textContent = s; frag.appendChild(m); }
        else frag.appendChild(document.createTextNode(s));
      });
      node.parentNode.replaceChild(frag, node);
    });
  }
  const deepZh = zParam != null && /^\d+$/.test(zParam) && article ? $(`[data-z="${zParam}"]`, article) : null;
  if (deepZh) {
    if (tabBtns.length) activate('zh');
    deepZh.classList.add('z-hit');
    highlightIn(deepZh, hlWords);
    requestAnimationFrame(() => {
      const offset = (tabsRow ? tabsRow.offsetHeight : 0) + 28;
      window.scrollTo({ top: deepZh.getBoundingClientRect().top + window.scrollY - offset });
    });
  }
  if (deepPara && trText && tabBtns.some((b) => b.dataset.tab === 'tr')) {
    activate('tr');
    deepPara.classList.add('hit');
    highlightIn(deepPara, hlWords);
    requestAnimationFrame(() => {
      const top = tabsRow.parentNode.getBoundingClientRect().top + window.scrollY - 1;
      window.scrollTo({ top });
      trText.scrollTop += deepPara.getBoundingClientRect().top - trText.getBoundingClientRect().top - 24;
    });
  }
  if (tSec != null && hasVideo) {
    const toast = document.createElement('div');
    toast.className = 'mini-player resume-toast';
    toast.innerHTML = `<div class="mp-body"><div class="mp-title">从 ${esc(tsLabel(tSec))} 开始播放</div></div>
      <button type="button" class="chip" data-go>▶ 播放</button><button type="button" class="mp-close" aria-label="关闭">×</button>`;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    const hide = () => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); };
    $('[data-go]', toast).addEventListener('click', () => { seekTo(tSec); hide(); if (window.umami) window.umami.track('deeplink-play', { slug }); });
    $('.mp-close', toast).addEventListener('click', hide);
  }

  /* ---------- 金句：复制（带出处与时间戳链接） ---------- */
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-copy-q]');
    if (!b) return;
    const item = b.closest('.quote-item');
    const zh = ($('.q-zh', item) || {}).textContent || '';
    const en = ($('.q-en', item) || {}).textContent || '';
    const tsEl = $('.ts-link', item);
    const sec = tsEl ? toSec(tsEl.dataset.t) : null;
    const title = (($('.ep-title') || {}).textContent || '').trim();
    const url = location.origin + location.pathname + (sec != null && isFinite(sec) ? '?t=' + sec : '');
    const txt = `“${zh}”\n${en}\n—— 马斯克，${title}${tsEl ? ' ' + tsEl.dataset.t : ''}\n${url}`;
    const done = () => { b.textContent = '已复制'; setTimeout(() => { b.textContent = '复制'; }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, () => {});
  });
})();
