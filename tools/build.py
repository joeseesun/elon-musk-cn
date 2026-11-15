#!/usr/bin/env python3
"""elon.qiaomu.ai 静态站构建器。

输入：
  tools/elon-master.json     主数据（651 条视频，来自 silicon-valley.tech）
  tools/translations.json    LLM 翻译的中文标题
  data/extra.json            预言追踪 / 精选 / 主题 / 语录（英文）
  data/extra-zh.json         上述内容的中文译文
  data/transcripts/*.json    588 份英文文稿（带时间戳 segs）
  data/quotes-zh.json        金句与语录的中文译文（tools/translate_quotes.py 生成）
  site/zh/{slug}.html        中文精读片段
  tools/site_config.json     站点配置（域名、Umami ID）

输出：
  site/index.html            首页（搜索 + 筛选 + 精选 + 网格）
  site/ep/{slug}/index.html  651 个视频页（视频播放 / 精读 / 文稿 / 金句）
  site/ep/{slug}/index.md    精读 Markdown 版
  site/predictions/          预言与承诺追踪
  site/quotes/               语录
  site/themes/               主题
  site/archive/              按年份目录
  site/data/episodes.json    首页数据
  site/data/search/          文稿全文检索索引（tools/search_index.py）
  site/search/               文稿搜索页
  site/sitemap.xml / feed.xml / llms.txt / 404 / offline / disclaimer

数据来源声明：视频档案与语料来自 silicon-valley.tech（Elon Musk Archive），
转载引用须注明原始出处；本站不托管媒体文件。
"""
import html as H
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import insights  # noqa: E402
import search_index  # noqa: E402
SITE = ROOT.parent / 'site'
TODAY = date.today().isoformat()

CFG = json.load(open(ROOT / 'site_config.json')) if (ROOT / 'site_config.json').exists() else {}
DOMAIN = CFG.get('domain', 'https://elon.qiaomu.ai')
SITE_NAME = '马斯克全访谈'
UMAMI = CFG.get('umami', '')
CSS_V, APP_V, EP_V, SEARCH_V, TRENDS_V, KIT_V = 8, 4, 6, 4, 2, 1

STATUS_ZH = {'kept': '已兑现', 'late': '迟到兑现', 'missed': '未兑现', 'open': '待验证'}

master = json.load(open(ROOT / 'elon-master.json'))
trans = json.load(open(ROOT / 'translations.json'))
extra = json.load(open(ROOT.parent / 'data' / 'extra.json'))
extra_zh = json.load(open(ROOT.parent / 'data' / 'extra-zh.json'))
_qzh = ROOT.parent / 'data' / 'quotes-zh.json'
quotes_zh = json.load(open(_qzh)) if _qzh.exists() else {}
_bili = ROOT / 'bili.json'
BILI = json.loads(_bili.read_text()) if _bili.exists() else {}
EP_QUOTES_ZH = quotes_zh.get('ep') or {}
SAYINGS_ZH = quotes_zh.get('sayings') or {}
PARAS = {}  # slug -> 文稿段落，视频页与全文检索共用
ZTEXTS = {}  # slug -> 精读段落纯文本，与页面里的 data-z 序号一一对应
tr_json = {x['srcId']: x for x in master if x['tr']}

for m in master:
    m['zh'] = (trans.get(m['slug']) or {}).get('zh')

by_slug = {m['slug']: m for m in master}
ZH = {p.stem for p in (SITE / 'zh').glob('*.html')} if (SITE / 'zh').exists() else set()
QUOTES_V, QUOTES_Q = extra['quotes']['v'], extra['quotes']['q']
quotes_by_slug = {}
for i, vid in enumerate(QUOTES_V):
    slug = next((m['slug'] for m in master if m['srcId'] == vid.replace('yt-', '')), None)
    if slug:
        quotes_by_slug[slug] = [q for q in QUOTES_Q if q[0] == i]


def fmt_date(d):
    if not d:
        return ''
    if len(d) == 4:
        return f'{d} 年'
    if len(d) == 7:
        return f'{d[:4]} 年 {int(d[5:7])} 月'
    return f'{d[:4]} 年 {int(d[5:7])} 月 {int(d[8:10])} 日'


def fmt_sec(s):
    if not s:
        return ''
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    if h:
        return f'{h} 小时 {m} 分'
    return f'{m} 分钟'


def esc(s):
    return H.escape(s or '')


def text_for(m):
    """返回 (trm, segs)；文稿按源站 ID 读取。"""
    f = ROOT.parent / 'data' / 'transcripts' / f"{m['srcId']}.json"
    if not m['tr'] or not f.exists():
        return None, None
    try:
        t = json.load(open(f))
        return t, t.get('segs') or []
    except Exception:
        return None, []


TR_NOTE = {
    'exact': '语音识别自动转录（Whisper），含全部发言人，可能有识别错误。',
    'approx': '语音识别自动转录，可能有识别错误，人名与数字请以视频为准。',
    'text': '第三方整理文稿，仅保留马斯克本人发言。',
    'ytauto': 'YouTube 平台字幕（自动或人工），可能有识别错误，人名与数字请以视频为准。',
}


def ts_mmss(sec):
    if sec is None:
        return None
    s = int(sec)
    h, rem = divmod(s, 3600)
    m, ss = divmod(rem, 60)
    return f'{h}:{m:02d}:{ss:02d}' if h else f'{m}:{ss:02d}'


def prune(o):
    if isinstance(o, dict):
        return {k: prune(v) for k, v in o.items() if v not in (None, '', [], {})}
    if isinstance(o, list):
        return [prune(v) for v in o]
    return o


def html_to_md(h):
    h = re.sub(r'\s*<h2[^>]*>(.*?)</h2>\s*', lambda m: f'\n\n## {m.group(1)}\n\n', h, flags=re.S)
    h = re.sub(r'\s*<h3[^>]*>(.*?)</h3>\s*', lambda m: f'\n\n### {m.group(1)}\n\n', h, flags=re.S)
    h = re.sub(r'\s*<blockquote>(.*?)</blockquote>\s*',
               lambda m: '\n\n' + '\n'.join('> ' + ln for ln in re.sub(r'</?p>', '\n', m.group(1)).strip().splitlines() if ln.strip()) + '\n\n',
               h, flags=re.S)
    h = re.sub(r'\s*<li>(.*?)</li>\s*', lambda m: f'\n- {m.group(1).strip()}', h, flags=re.S)
    h = re.sub(r'</?(ul|ol)>', '\n', h)
    h = re.sub(r'<(strong|b)>(.*?)</\1>', r'**\2**', h, flags=re.S)
    h = re.sub(r'<(em|i)>(.*?)</\1>', r'*\2*', h, flags=re.S)
    h = re.sub(r'<br\s*/?>', '  \n', h)
    h = re.sub(r'\s*<p>(.*?)</p>\s*', lambda m: f'\n\n{m.group(1).strip()}\n\n', h, flags=re.S)
    h = H.unescape(re.sub(r'<[^>]+>', '', h))
    return re.sub(r'\n{3,}', '\n\n', h).strip() + '\n'


def thumb_of(m, big=False):
    if m.get('ytId'):
        q = 'maxresdefault' if big else 'mqdefault'
        return f'https://i.ytimg.com/vi/{m["ytId"]}/{q}.jpg'
    if m.get('poster'):
        return m['poster']
    return ''


# ---------------------------------------------------------------- 公共片段
THEME_SCRIPT = """<script>
(function () {
  var d = document.documentElement, g = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var t = g('em-theme'), f = g('em-font'), z = g('em-size'), lh = g('em-lh'), w = g('em-measure');
  var BG = { light: '#ffffff', sepia: '#f5eddc', dark: '#141414' };
  if (!BG[t]) t = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  d.setAttribute('data-theme', t);
  var FONTS = {
    sans: 'https://fonts.googleapis.cn/css2?family=Noto+Sans+SC:wght@400;600&display=swap',
    serif: 'https://fonts.googleapis.cn/css2?family=Noto+Serif+SC:wght@400;600&display=swap',
    kai: 'https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-webfont@1.7.0/lxgwwenkaiscreen.css',
    song: 'https://cdn.jsdelivr.net/npm/@chinese-fonts/jhlst@3.0.0/dist/%E4%BA%AC%E8%8F%AF%E8%80%81%E5%AE%8B%E4%BD%93v2_002/result.css'
  };
  window.__lexFonts = FONTS;
  window.__lexLoadFont = function (k) {
    if (!FONTS[k] || document.getElementById('lexfont-' + k)) return;
    var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = FONTS[k]; l.id = 'lexfont-' + k;
    document.head.appendChild(l);
  };
  if (!f) f = 'serif';
  if (FONTS[f]) { d.setAttribute('data-font', f); window.__lexLoadFont(f); }
  if (z && /^(1[5-9]|2[0-2])$/.test(z)) d.style.setProperty('--read-size', z + 'px');
  if (lh && /^(1\\.\\d+|2(\\.\\d+)?)$/.test(lh)) d.style.setProperty('--read-lh', lh);
  if (w && /^\\d{3}$/.test(w)) d.style.setProperty('--measure', w + 'px');
  var meta = document.querySelector('meta[name="theme-color"]');
  function syncMeta() { if (meta) meta.content = BG[t]; }
  syncMeta();
  window.__lexSetTheme = function (n) {
    if (!BG[n]) return;
    t = n;
    try { localStorage.setItem('em-theme', t); if (t !== 'dark') localStorage.setItem('em-light', t); } catch (e) {}
    d.classList.add('theme-anim');
    d.setAttribute('data-theme', t);
    syncMeta();
    setTimeout(function () { d.classList.remove('theme-anim'); }, 320);
    document.dispatchEvent(new CustomEvent('lex-theme', { detail: t }));
  };
  window.__lexThemeToggle = function () { window.__lexSetTheme(t === 'dark' ? (g('em-light') || 'light') : 'dark'); };
  (function () {
    var vv = window.visualViewport;
    if (!vv) return;
    var queued = false;
    function apply() {
      queued = false;
      var off = Math.round(window.innerHeight - vv.offsetTop - vv.height);
      d.style.setProperty('--vv-off', Math.max(0, off) + 'px');
    }
    function onVV() { if (!queued) { queued = true; requestAnimationFrame(apply); } }
    vv.addEventListener('resize', onVV);
    vv.addEventListener('scroll', onVV);
    window.addEventListener('orientationchange', onVV);
    apply();
  })();
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target : e.target.parentNode;
    if (el.closest('[data-theme-toggle]')) return window.__lexThemeToggle();
    var o = el.closest('[data-open]');
    if (o) { var m = document.getElementById(o.getAttribute('data-open')); if (m) { m.hidden = false; var c = m.querySelector('.modal-close'); if (c) c.focus(); } if (window.umami) window.umami.track('open-' + o.getAttribute('data-open')); return; }
    var mm = el.closest('.modal');
    if (mm && (el === mm || el.closest('.modal-close'))) { mm.hidden = true; return; }
    var sh = el.closest('[data-share]');
    if (sh) {
      var data = { title: document.title, url: location.href.split('#')[0] };
      if (navigator.share) { navigator.share(data).catch(function () {}); }
      else if (navigator.clipboard) navigator.clipboard.writeText(data.title + ' ' + data.url).then(function () { var t = sh.textContent; sh.textContent = '链接已复制'; setTimeout(function () { sh.textContent = t; }, 1600); });
      return;
    }
    var cf = el.closest('[data-copy-feed]');
    if (cf) {
      var url = location.origin + '/feed.xml', label = cf.textContent;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () { cf.textContent = '已复制'; setTimeout(function () { cf.textContent = label; }, 1600); }, function () { location.href = '/feed.xml'; });
      } else location.href = '/feed.xml';
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') Array.prototype.forEach.call(document.querySelectorAll('.modal'), function (m) { m.hidden = true; });
  });
  document.addEventListener('load', function (e) { var t = e.target; if (t.tagName === 'IMG') t.classList.add('ok'); }, true);
  document.addEventListener('error', function (e) { var t = e.target; if (t.tagName === 'IMG' && !t.getAttribute('onerror')) t.classList.add('ok'); }, true);
  var deferred = null;
  function showInstall() { Array.prototype.forEach.call(document.querySelectorAll('[data-install]'), function (b) { b.hidden = false; }); }
  window.addEventListener('beforeinstallprompt', function (e) { e.preventDefault(); deferred = e; showInstall(); });
  var standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone;
  if (/iphone|ipad|ipod/i.test(navigator.userAgent) && !standalone) document.addEventListener('DOMContentLoaded', showInstall);
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-install]');
    if (!b) return;
    if (deferred) { deferred.prompt(); deferred.userChoice.finally(function () { deferred = null; b.hidden = true; }); }
    else { var m = document.getElementById('installModal'); if (m) m.hidden = false; }
  });
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', function () { navigator.serviceWorker.register('/sw.js').catch(function () {}); });
  }
})();
</script>"""

HEAD_EXTRA = ('<link rel="preconnect" href="https://fonts.googleapis.cn">'
              '<link rel="preconnect" href="https://fonts.gstatic.cn" crossorigin>'
              '<link rel="preconnect" href="https://i.ytimg.com">'
              '<link rel="stylesheet" href="https://fonts.googleapis.cn/css2?family=Libre+Caslon+Text:ital,wght@0,400;0,700;1,400'
              '&family=Noto+Serif+SC:wght@500;700&display=swap">\n'
              '<link rel="icon" href="/favicon.ico" sizes="32x32">'
              '<link rel="icon" href="/icon.svg" type="image/svg+xml">'
              '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
              '<link rel="manifest" href="/site.webmanifest">\n'
              '<meta name="apple-mobile-web-app-title" content="马斯克全访谈">'
              '<meta name="apple-mobile-web-app-capable" content="yes">'
              '<meta name="mobile-web-app-capable" content="yes">'
              '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
              '<meta name="format-detection" content="telephone=no">'
              '<noscript><style>.thumb img,.cont-thumb img,.hero-media img{opacity:1}</style></noscript>')

THEME_BTN = ('<button class="theme-toggle" type="button" data-theme-toggle aria-label="切换浅色 / 深色模式" title="切换浅色 / 深色模式">'
             '<svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/>'
             '<path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4"/></svg>'
             '<svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7z"/></svg>'
             '</button>')

ICON_SEARCH = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>'

SITE_HEADER = ('<header class="site-header slim">\n  <div class="wrap header-inner">\n'
               '    <a class="hdr-back" href="/">← 全部视频</a>\n'
               '    <a class="wordmark" href="/" aria-label="马斯克全访谈 · 首页">Elon Musk <span>全访谈</span></a>\n'
               f'    <div class="header-actions"><a class="hdr-icon" href="/search/" aria-label="在文稿里搜索马斯克的原话" title="文稿搜索">{ICON_SEARCH}</a>{THEME_BTN}</div>\n'
               '  </div>\n</header>')

ICON_PLAY = '<svg class="i-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.6-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>'

FEED_LINK = (f'<link rel="alternate" type="application/rss+xml" '
             f'title="马斯克全访谈 · 中文精读全文" href="{DOMAIN}/feed.xml">')

SITE_FOOTER = """<footer class="site-footer">
  <div class="wrap">
    <div class="ft-top">
      <a class="ft-mark" href="/">Elon Musk <span>全访谈</span></a>
      <p class="ft-tag">把马斯克 28 年的公开访谈，用中文认真读一遍。</p>
    </div>
    <div class="ft-cols">
      <nav class="ft-col" aria-label="浏览"><h2>浏览</h2>
        <a href="/">全部视频</a><a href="/search/">文稿搜索</a><a href="/?f=zh">中文精读</a><a href="/trends/">话题趋势</a><a href="/stats/">档案数据</a><a href="/archive/">视频目录</a><a href="/predictions/">预言追踪</a>
        <a href="/quotes/">语录</a><a href="/themes/">主题</a><button type="button" data-install hidden>安装为应用</button></nav>
      <nav class="ft-col" aria-label="订阅"><h2>订阅</h2>
        <a href="/feed.xml">RSS 全文订阅</a><button type="button" data-copy-feed>复制 RSS 地址</button>
        <a href="https://silicon-valley.tech/" target="_blank" rel="noopener">数据源 Elon Musk Archive</a></nav>
      <nav class="ft-col" aria-label="关于"><h2>关于</h2>
        <a href="/disclaimer/">免责声明</a><a href="https://github.com/joeseesun/elon-musk-cn" target="_blank" rel="noopener">开源代码</a>
        <a href="/llms.txt">llms.txt</a><a href="https://tuijian.qiaomu.ai/" target="_blank" rel="noopener">乔木推荐</a></nav>
      <div class="ft-col ft-support"><h2>支持这个项目</h2>
        <p>一个人独立制作，没有广告，也不收费。如果这里的某篇精读让你有所收获，欢迎请作者喝杯咖啡，让它一直做下去。</p>
        <div class="ft-actions"><button type="button" class="ft-btn" data-open="rewardModal">打赏支持</button><button type="button" class="ft-btn ghost" data-open="followModal">关注公众号</button></div></div>
    </div>
    <div class="ft-bottom">
      <span>© 2026 向阳乔木 · 非官方粉丝站点，与 Elon Musk 及其公司无隶属关系</span>
      <span>视频与文稿版权归原权利方所有，本站不托管媒体文件 · 中文精读由 AI 改写，仅供学习参考 · 视频档案数据来自 silicon-valley.tech</span>
    </div>
  </div>
</footer>

<div id="rewardModal" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="rewardT">
  <div class="modal-card">
    <button type="button" class="modal-close" aria-label="关闭">×</button>
    <h3 id="rewardT">谢谢你的支持</h3>
    <p class="modal-sub">每一份打赏都会变成更多认真校过的精读</p>
    <img src="/assets/qiaomu_reward_qr.png" alt="打赏二维码" width="220" height="220" loading="lazy">
    <p class="modal-links">微信扫一扫</p>
  </div>
</div>
<div id="installModal" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="installT">
  <div class="modal-card">
    <button type="button" class="modal-close" aria-label="关闭">×</button>
    <h3 id="installT">添加到主屏幕</h3>
    <p class="modal-sub">像应用一样打开，读过的文章离线也能看</p>
    <ol class="install-steps"><li>点 Safari 底部的「分享」按钮 <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7.5 7.5L12 3l4.5 4.5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg></li><li>向下滑，选择「添加到主屏幕」</li><li>点右上角「添加」</li></ol>
  </div>
</div>
<div id="followModal" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="followT">
  <div class="modal-card">
    <button type="button" class="modal-close" aria-label="关闭">×</button>
    <h3 id="followT">关注向阳乔木</h3>
    <p class="modal-sub">微信公众号：向阳乔木推荐看</p>
    <img src="/assets/qiaomu_wechat_public_account_qr.jpg" alt="公众号二维码" width="220" height="220" loading="lazy">
    <p class="modal-links"><a href="https://github.com/joeseesun/" target="_blank" rel="noopener">GitHub</a> · <a href="https://x.com/vista8" target="_blank" rel="noopener">X</a></p>
  </div>
</div>"""

COLOPHON = ('<aside class="colophon" aria-label="致读者">'
            '<div class="colo-k">致读者</div>'
            '<p>这篇精读来自 elon.qiaomu.ai，一个人独立维护的非营利项目：从公开视频与文稿出发，'
            '经 AI 改写与逐篇校验，把几十分钟的访谈压缩成一篇值得静心读完的中文长文。这里没有广告，也不设付费墙。'
            '如果它让你有所收获，欢迎请作者喝杯咖啡。</p>'
            '<div class="colo-actions"><button type="button" class="ft-btn" data-open="rewardModal">打赏支持</button>'
            '<button type="button" class="ft-btn ghost" data-open="followModal">关注公众号</button>'
            '<button type="button" class="colo-link" data-share>分享这篇</button>'
            '<a class="colo-link" href="/feed.xml">RSS 订阅更新</a></div></aside>')


def umami_tag():
    if not UMAMI:
        return ''
    return (f'<script defer src="https://umami.qiaomu.ai/script.js" data-website-id="{esc(UMAMI)}" '
            f'data-domains="elon.qiaomu.ai"></script>')


# ---------------------------------------------------------------- 首页数据
def build_data():
    eps = []
    for m in master:
        qs = quotes_by_slug.get(m['slug'])
        eps.append({
            's': m['slug'], 't': m['title'], 'd': m.get('d') or '',
            'y': m.get('ytId'),
            'po': m.get('poster'),
            'zh': m['zh'], 'ch': m.get('ch'), 'k': m.get('kZh'),
            'a': m.get('a') or [],
            'sec': m.get('sec'),
            'tr': bool(m['tr']), 'r': 1 if m['slug'] in ZH else 0,
            'pick': 1 if m.get('feat') or any(p['v'].endswith(m['srcId']) for p in extra['picks']) else 0,
            'qn': len(qs) if qs else 0,
        })
    n_pick = sum(1 for x in eps if x['pick'])
    out = {'updated': TODAY, 'episodes': eps}
    (SITE / 'data').mkdir(parents=True, exist_ok=True)
    (SITE / 'data' / 'episodes.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    print(f"episodes.json: {len(eps)} videos, tr={sum(1 for x in eps if x['tr'])}, "
          f"zh={len(ZH)}, pick={n_pick}, zh_title={sum(1 for x in eps if x['zh'])}")
    return eps


# ---------------------------------------------------------------- 视频页
EP_SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#ffffff">
<title>{title_tag}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}/">
<meta property="og:image" content="{og_img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{og_img}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
{article_meta}
{md_link}
<script type="application/ld+json">{ldjson}</script>
{theme_script}
{head_extra}
{feed_link}
<link rel="stylesheet" href="/style.css?v={css_v}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{site_header}

<main class="wrap ep-main ep-page{main_cls}" id="main">
  <div class="ep-stage">
    <header class="ep-head">
      <div class="ep-kicker">{kicker}</div>
      <h1 class="ep-title">{h1}</h1>
      {orig_line}
      {dek}
      <div class="ep-byline">{byline}</div>
    </header>
    {media_html}
  </div>
  <article class="ep">
    <section class="content-tabs">
      {tab_buttons}
      {panel_zh}
      {panel_tr}
      {panel_q}
      {no_content_note}
    </section>
    {resources}
    <nav class="ep-prevnext" aria-label="上一个 / 下一个视频">
      {prevnext}
    </nav>
  </article>
  <aside class="ep-toc" aria-label="精读目录"></aside>
</main>

{site_footer}

{umami}
<script src="/ep.js?v={ep_v}"></script>
<script src="/kit.js?v={kit_v}"></script>
</body>
</html>
"""


def build_page(i, eps):
    m = master[i]
    slug, title = m['slug'], m['title']
    d = m.get('d') or ''
    y = m.get('ytId')
    zh_title = m['zh']
    pick = next((p for p in extra['picks'] if p['v'].endswith(m['srcId'])), None)
    lede = (extra_zh.get('picks') or {}).get(pick['v']) if pick else None

    url = f'{DOMAIN}/ep/{slug}'
    title_tag = f'{zh_title} | {SITE_NAME}' if zh_title else f'{title} | {SITE_NAME}'
    desc_bits = []
    if lede:
        desc_bits.append(lede)
    if m.get('kZh'):
        desc_bits.append(f'{m["kZh"]}（{d[:4] if d else "年份未知"}）')
    desc = (zh_title or title) + ('：' + '，'.join(desc_bits) if desc_bits else '') + '。'
    if m['tr']:
        desc += ' 含视频与英文文稿。'
    if slug in ZH:
        desc += ' 附 AI 中文精读。'
    og_title = f'{zh_title}｜{title}' if zh_title else title
    og_img = thumb_of(m, big=True) or f'{DOMAIN}/assets/og-default.jpg'

    zh_html_file = SITE / 'zh' / f'{slug}.html'
    has_zh = slug in ZH and zh_html_file.exists()
    zh_raw = zh_html_file.read_text() if has_zh else ''
    zh_chars = len(re.sub(r'\s+', '', H.unescape(re.sub(r'<[^>]+>', '', zh_raw))))
    read_min = max(1, round(zh_chars / 450)) if zh_chars else 0
    zh_mtime = date.fromtimestamp(zh_html_file.stat().st_mtime).isoformat() if has_zh else None
    zh_sections = [H.unescape(re.sub(r'<[^>]+>', '', x)).strip() for x in re.findall(r'<h2[^>]*>(.*?)</h2>', zh_raw)]
    zh_marked, ztexts = search_index.zh_blocks(zh_raw)
    if ztexts:
        ZTEXTS[slug] = ztexts

    tdata, segs = text_for(m)
    paras = search_index.paragraphs(segs) if segs else []
    if paras:
        PARAS[slug] = paras
    qzh = EP_QUOTES_ZH.get(slug) or []
    qs = quotes_by_slug.get(slug) or []
    qs = [q for q in qs if len(q[2]) >= 60][:40]

    ld_media = []
    if y:
        ld_media.append({"@type": "VideoObject", "embedUrl": f'https://www.youtube.com/embed/{y}',
                         "thumbnailUrl": thumb_of(m, big=True) or None})
    elif m.get('mp4'):
        ld_media.append({"@type": "VideoObject", "contentUrl": m['mp4']})
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "VideoObject", "@id": f'{url}/#video', "url": f'{url}/',
         "name": title, "alternativeHeadline": zh_title or None, "description": lede or desc,
         "datePublished": d or None, "duration": f'PT{int((m.get("sec") or 0) // 60)}M' if m.get('sec') else None,
         "inLanguage": "en", "thumbnailUrl": thumb_of(m, big=True) or None,
         "associatedMedia": ld_media},
        *([{"@type": "Article", "@id": f'{url}/#article', "url": f'{url}/',
             "headline": (zh_title or title)[:110], "alternativeHeadline": title,
             "description": lede or None, "inLanguage": "zh-CN",
             "datePublished": zh_mtime, "dateModified": zh_mtime,
             "wordCount": zh_chars, "timeRequired": f'PT{read_min}M',
             "articleSection": zh_sections[:30] or None,
             "isBasedOn": {"@id": f'{url}/#video'}, "about": {"@id": f'{url}/#video'},
             "author": {"@type": "Person", "name": "向阳乔木", "url": "https://x.com/vista8"},
             "publisher": {"@id": f'{DOMAIN}/#org'},
             "isAccessibleForFree": True,
             "mainEntityOfPage": f'{url}/'}] if has_zh else []),
        {"@type": "Organization", "@id": f'{DOMAIN}/#org', "name": SITE_NAME, "url": f'{DOMAIN}/',
         "sameAs": ["https://github.com/joeseesun/elon-musk-cn", "https://x.com/vista8"]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": f'{DOMAIN}/'},
            {"@type": "ListItem", "position": 2, "name": title_tag.split(' | ')[0], "item": f'{url}/'}]},
    ]}
    ldjson = json.dumps(prune(ld), ensure_ascii=False).replace('<', '\\u003c')

    h1 = esc(zh_title or title)
    orig_line = (f'<p class="ep-title-en" lang="en">{esc(title)}</p>' if zh_title and title != zh_title else '')
    kicker_bits = [esc(m.get('kZh') or '视频')]
    if has_zh:
        kicker_bits.append('<span class="k-zh">中文精读</span>')
    kicker = '<span class="k-sep">·</span>'.join(kicker_bits)
    dek = f'<p class="ep-dek">{esc(lede)}</p>' if lede else ''
    by = []
    if m.get('ch'):
        by.append(f'<span>{esc(m["ch"])}</span>')
    if d:
        when = fmt_date(d)
        note = '（约）' if m.get('dp') == '约为上传日期' else ''
        by.append(f'<time datetime="{d}">{when}{note}</time>')
    if m.get('sec'):
        by.append(f'<span>{fmt_sec(m["sec"])}</span>')
    if has_zh and read_min:
        wan = f'{zh_chars / 10000:.1f} 万字' if zh_chars >= 10000 else f'{zh_chars} 字'
        by.append(f'<span>精读约 {wan} · 阅读 {read_min} 分钟</span>')
    byline = '<span class="k-sep">·</span>'.join(by)

    # 媒体：YouTube 嵌入（有 B 站搬运时加来源切换）/ MP4 直链 / 无视频
    bili = BILI.get(slug)
    if y or (bili and not m.get('mp4')):
        img = thumb_of(m) or (bili or {}).get('pic') or ''
        attrs = (f' data-yt="{esc(y)}"' if y else '') + (f' data-bv="{esc(bili["bv"])}" data-bp="{int(bili.get("p") or 1)}"' if bili else '')
        onerr = f' onerror="this.onerror=null;this.src=\'https://i.ytimg.com/vi/{y}/hqdefault.jpg\'"' if y else ''
        media_html = (f'<div class="media">'
                      f'<button type="button" class="video-facade"{attrs} aria-label="播放视频">'
                      f'<img src="{img}" alt="" width="320" height="180"{onerr}>'
                      f'<span class="vf-play">{ICON_PLAY}<span>看视频</span></span></button></div>')
        if y and bili:
            sub = '<small>中字</small>' if bili.get('sub') else ''
            media_html = (f'<div class="src-tabs" role="tablist" aria-label="视频来源">'
                          f'<button type="button" role="tab" data-src="yt" aria-selected="true">YouTube</button>'
                          f'<button type="button" role="tab" data-src="bili" aria-selected="false">B 站{sub}</button>'
                          f'<span class="src-note">B 站版本为网友搬运，时间点可能差几秒</span></div>') + media_html
    elif m.get('mp4'):
        media_html = f'<div class="media"><video class="mp4-player" controls preload="none" playsinline poster="{esc(m.get("poster") or "")}" src="{esc(m["mp4"])}"></video></div>'
    else:
        media_html = '<div class="ep-notice">该视频暂无可播放源，可通过下方资源访问原始页面。</div>'

    tab_buttons = ['<div class="tabs" role="tablist">']
    if has_zh:
        tab_buttons.append('<button class="tab-btn" type="button" data-tab="zh" role="tab" aria-controls="panel-zh">中文精读</button>')
    if paras:
        tab_buttons.append('<button class="tab-btn" type="button" data-tab="tr" role="tab" aria-controls="panel-tr">英文文稿</button>')
    if qzh or qs:
        tab_buttons.append('<button class="tab-btn" type="button" data-tab="q" role="tab" aria-controls="panel-q">金句</button>')
    tab_buttons.append('</div>')
    tab_buttons = ''.join(tab_buttons) if (has_zh or paras or qzh or qs) else ''

    panel_zh = ''
    if has_zh:
        panel_zh = (f'<div class="tab-panel" id="panel-zh" data-panel="zh">'
                    f'<div class="zh-note">中文精读由 AI 基于原始视频与文稿改写，非官方翻译，可能存在偏差或错误；表述以原视频为准。<a href="/disclaimer/">说明</a></div>'
                    f'<div class="zh-article">{zh_marked}</div>{COLOPHON}</div>')

    panel_tr = ''
    if paras:
        mode = (tdata or {}).get('mode', 'exact')
        lines = []
        for k, (sec, txt) in enumerate(paras):
            ts = ts_mmss(sec)
            ts_html = f'<span class="ts-link" data-t="{ts}">{ts}</span>' if ts else ''
            lines.append(f'<p id="p{k}">{ts_html}{esc(txt)}</p>')
        src_line = ''
        if (tdata or {}).get('url'):
            src_line = f' 文稿来源：<a href="{esc(tdata["url"])}" target="_blank" rel="noopener">{esc(tdata.get("publisher") or tdata["url"])}</a>。'
        panel_tr = (f'<div class="tab-panel" id="panel-tr" data-panel="tr">'
                    f'<div class="tr-note">{TR_NOTE.get(mode, TR_NOTE["exact"])}已按语句合并成段落，并去掉 um、uh 等口头填充词。{src_line}</div>'
                    f'<div class="transcript-text">{"".join(lines)}</div></div>')

    panel_q = ''
    if qzh:
        items = []
        for q in qzh:
            ts = ts_mmss(q['t']) if q.get('t') is not None and q['t'] >= 0 else None
            ts_html = f'<a class="q-ts ts-link" data-t="{ts}" href="javascript:void(0)">▶ {ts}</a>' if ts else ''
            items.append(f'<blockquote class="quote-item bi"><p class="q-zh">{esc(q["zh"])}</p>'
                         f'<p class="q-en" lang="en">{esc(q["en"])}</p>'
                         f'<div class="q-foot">{ts_html}<button type="button" class="q-copy" data-copy-q>复制</button>'
                         f'<button type="button" class="q-copy" data-poster-q>生成海报</button></div></blockquote>')
        panel_q = (f'<div class="tab-panel" id="panel-q" data-panel="q">'
                   f'<div class="tr-note">从现场发言里挑出的 {len(qzh)} 句原话，附中文译文（AI 翻译，以英文原话为准）。点时间戳可跳到视频对应位置。</div>'
                   f'<div class="quotes-list">{"".join(items)}</div></div>')
    elif qs:
        items = []
        for q in qs:
            ts = ts_mmss(q[1])
            ts_html = f'<a class="q-ts ts-link" data-t="{ts}" href="javascript:void(0)">{ts}</a>' if ts else ''
            items.append(f'<blockquote class="quote-item">{esc(q[2])}{ts_html}'
                         f'<button type="button" class="q-copy q-poster" data-poster-q>生成海报</button></blockquote>')
        panel_q = (f'<div class="tab-panel" id="panel-q" data-panel="q">'
                   f'<div class="tr-note">编辑精选的 {len(qs)} 条现场发言，点时间戳可跳到视频对应位置。</div>'
                   f'<div class="quotes-list">{"".join(items)}</div></div>')

    no_content_note = ''
    if not has_zh and not paras and not qzh and not qs:
        no_content_note = '<div class="ep-notice">该视频的文稿与精读暂未收录，可直接观看视频。</div>'

    res = ['<section class="ep-resources"><h2>资源与出处</h2><ul>']
    if y:
        res.append(f'<li><span class="res-k">视频</span><a href="https://www.youtube.com/watch?v={esc(y)}" target="_blank" rel="noopener">在 YouTube 收看</a></li>')
    if bili:
        note = f'UP 主「{esc(bili.get("up") or "")}」搬运' + ('，标题注明带中文字幕' if bili.get('sub') else '')
        res.append(f'<li><span class="res-k">视频</span><a href="https://www.bilibili.com/video/{esc(bili["bv"])}/{"?p=" + str(bili["p"]) if bili.get("p") else ""}" target="_blank" rel="noopener">在 B 站收看</a><span class="res-sub">{note}</span></li>')
    if m.get('mp4'):
        res.append(f'<li><span class="res-k">视频</span><a href="{esc(m["mp4"])}" target="_blank" rel="noopener">原始视频文件</a></li>')
    res.append(f'<li><span class="res-k">档案</span><a href="https://silicon-valley.tech/#v-yt-{esc(m["srcId"])}" target="_blank" rel="noopener">silicon-valley.tech 档案页</a><span class="res-sub">本页视频与文稿数据来自 Elon Musk Archive</span></li>')
    if slug in ZH:
        res.append(f'<li><span class="res-k">精读</span><a href="/ep/{esc(slug)}/index.md">本篇精读 Markdown 版</a></li>')
    res.append('</ul></section>')
    resources = ''.join(res)

    prev_e, next_e = (master[i - 1] if i > 0 else None), (master[i + 1] if i < len(master) - 1 else None)

    def pn_link(ne, label):
        if not ne:
            return '<span></span>'
        t = ne['zh'] or ne['title']
        return (f'<a href="/ep/{ne["slug"]}/" rel="{"prev" if label.startswith("←") else "next"}">'
                f'<span class="pn-k">{label}</span><span class="pn-t">{esc(t)}</span></a>')

    prevnext = f'{pn_link(prev_e, "← 上一个")}{pn_link(next_e, "下一个 →")}'

    page = EP_SHELL.format(
        title_tag=esc(title_tag), desc=esc(desc), url=url,
        og_title=esc(og_title), og_img=esc(og_img),
        ldjson=ldjson, css_v=CSS_V, ep_v=EP_V, kit_v=KIT_V,
        theme_script=THEME_SCRIPT, head_extra=HEAD_EXTRA, feed_link=FEED_LINK,
        site_header=SITE_HEADER, site_footer=SITE_FOOTER, umami=umami_tag(),
        h1=h1, orig_line=orig_line, kicker=kicker, dek=dek, byline=byline,
        main_cls=' has-toc' if has_zh else '',
        article_meta=(f'<meta property="article:published_time" content="{d}">' if d else '') +
                     (f'<meta property="article:modified_time" content="{zh_mtime}">' if zh_mtime else ''),
        md_link=(f'<link rel="alternate" type="text/markdown" title="中文精读 Markdown" href="/ep/{slug}/index.md">' if has_zh else ''),
        media_html=media_html, tab_buttons=tab_buttons,
        panel_zh=panel_zh, panel_tr=panel_tr, panel_q=panel_q, no_content_note=no_content_note,
        resources=resources, prevnext=prevnext,
    )
    dest = SITE / 'ep' / slug / 'index.html'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page)
    if has_zh:
        head = [f'# {zh_title or title}', '',
                f'> {lede or ""}', '',
                f'- 原标题：{title}', f'- 时间：{fmt_date(d)}',
                f'- 频道：{m.get("ch")}' if m.get('ch') else '',
                f'- 网页版：{url}/', f'- 精读字数：约 {zh_chars} 字（阅读约 {read_min} 分钟）', '',
                '> 本文为 elon.qiaomu.ai 基于原始视频与文稿的 AI 改写中文精读，非官方翻译；引用请注明出处并链接网页版。', '']
        (dest.parent / 'index.md').write_text('\n'.join(x for x in head if x) + '\n' + html_to_md(zh_raw))
    else:
        md = dest.parent / 'index.md'
        if md.exists():
            md.unlink()


# ---------------------------------------------------------------- 首页 SSR
def ssr_card(x):
    zh, en = x['zh'] or x['t'], x['t']
    when = (x['d'] or '')[:7].replace('-', '.') or (x['d'] or '')
    thumb = x['y'] and f'https://i.ytimg.com/vi/{x["y"]}/mqdefault.jpg' or x.get('po') or ''
    img = f'<img loading="lazy" decoding="async" src="{H.escape(thumb)}" alt="" width="320" height="180">' if thumb else '<div class="no-img">EM</div>'
    tag = '<span class="zh-tag">中文精读</span>' if x.get('r') else ''
    en_html = f'<div class="card-title-en" lang="en">{esc(en)}</div>' if x['zh'] else ''
    kind = f'<span class="ep-n">{esc(x["k"])}</span>' if x.get('k') else ''
    return (f'<a class="card" href="/ep/{x["s"]}/"><div class="thumb">{img}</div><div class="card-body">'
            f'<div class="card-kicker">{kind}<span>{esc(when)}</span>{tag}</div>'
            f'<div class="card-title">{esc(zh)}</div>{en_html}</div></a>')


def ssr_hero(x):
    zh, en = x['zh'] or x['t'], x['t']
    d = x['d'] or ''
    when = fmt_date(d)
    by = ' · '.join(esc(v) for v in [x.get('ch'), when] if v)
    img = x['y'] and (f'<img src="https://i.ytimg.com/vi/{x["y"]}/maxresdefault.jpg" alt="" '
                      f'onerror="this.onerror=null;this.src=\'https://i.ytimg.com/vi/{x["y"]}/hqdefault.jpg\'">')
    return (f'<a class="hero-media" href="/ep/{x["s"]}/" tabindex="-1" aria-hidden="true">{img}</a>'
            f'<div class="hero-text"><div class="hero-kicker">最新精读</div>'
            f'<h2 class="hero-title"><a href="/ep/{x["s"]}/">{esc(zh)}</a></h2>'
            f'<p class="hero-en" lang="en">{esc(en)}</p><p class="hero-by">{by}</p>'
            f'<a class="hero-cta" href="/ep/{x["s"]}/">阅读全文<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a></div>')


def insight_cards():
    """首页「数据洞察」入口：三张带小图的卡片，数据来自三个洞察页构建时留下的结果。"""
    cards = []
    t = INSIGHT.get('trends')
    if t:
        pick = {'火星': '火星', '特斯拉': '特斯拉', '人工智能': 'AI', '推特 / X': '推特', '政府效率 DOGE': 'DOGE'}
        cols = [c for c in t['cols'] if not c.startswith('≤')]
        rows = ''
        for r in t['rows']:
            if r['zh'] not in pick:
                continue
            mx = max(r['rate'][c] for c in cols) or 1
            cells = ''.join(f'<i style="--v:{r["rate"][c] / mx:.2f}"></i>' for c in cols)
            rows += f'<div class="ic-hm-r"><span>{esc(pick[r["zh"]])}</span><div>{cells}</div></div>'
        cards.append(f'<a class="ic" href="/trends/"><div class="ic-k">话题趋势</div><div class="ic-t">马斯克在关心什么</div>'
                     f'<div class="ic-hm" aria-hidden="true">{rows}<div class="ic-hm-x"><span>{cols[0]}</span><span>{cols[-1]}</span></div></div>'
                     f'<div class="ic-d">26 个话题、{len(PARAS)} 份文稿，逐年看热度</div></a>')
    mt = INSIGHT.get('mt')
    if mt:
        cards.append(f'<a class="ic" href="/predictions/"><div class="ic-k">预言追踪</div><div class="ic-t">马斯克时间</div>'
                     f'<div class="ic-big">× {mt["ratio_med"]:.1f}</div>'
                     f'<div class="ic-d">迟到兑现的承诺，实际用时是他所说的 {mt["ratio_med"]:.1f} 倍</div></a>')
    ph = INSIGHT.get('ph')
    if ph:
        mx = ph[0]['per'] or 1
        bars = ''.join(f'<div class="ic-w"><b lang="en">{esc(r["en"])}</b><span><i style="width:{r["per"] / mx * 100:.0f}%"></i></span><small>{r["per"]:.1f}</small></div>'
                       for r in ph[:4])
        cards.append(f'<a class="ic" href="/stats/#phrases"><div class="ic-k">档案数据</div><div class="ic-t">他最爱用的词</div>'
                     f'<div class="ic-ws">{bars}</div><div class="ic-d">每万词出现次数，附原话例句</div></a>')
    if not cards:
        return ''
    return ('<section class="ins-cards" aria-label="数据洞察"><div class="sec-h"><h2>数据洞察</h2><small>把 28 年的访谈变成图表</small></div>'
            f'<div class="ic-row">{"".join(cards)}</div></section>')

def build_index(eps):
    n_zh = sum(1 for x in eps if x.get('r'))
    since = min((x['d'] for x in eps if x['d']), default='')[:4]
    latest = next((x for x in reversed(eps) if x.get('r')), None)
    picks_sorted = [x for x in eps if x.get('pick')][:10]
    picks_html = ''
    for x in picks_sorted:
        pthumb = (f'https://i.ytimg.com/vi/{x["y"]}/mqdefault.jpg' if x['y'] else (x.get('po') or ''))
        pimg = f'<img loading="lazy" src="{esc(pthumb)}" alt="">' if pthumb else '<div class="no-img">EM</div>'
        picks_html += (f'<a class="pick-card" href="/ep/{x["s"]}/"><div class="pick-thumb">{pimg}</div>'
                       f'<div class="pick-body"><div class="pick-title">{esc(x["zh"] or x["t"])}</div>'
                       f'<div class="pick-en" lang="en">{esc(x["t"])}</div></div></a>')

    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": f'{DOMAIN}/#website', "name": SITE_NAME, "url": f'{DOMAIN}/',
         "description": f'马斯克 {len(eps)} 个公开视频的中文导航：访谈、发布会、股东大会，附 {n_zh} 篇中文精读、预言追踪与语录',
         "inLanguage": "zh-CN", "publisher": {"@id": f'{DOMAIN}/#org'},
         "potentialAction": {"@type": "SearchAction", "target": f'{DOMAIN}/?q={{search_term_string}}',
                             "query-input": "required name=search_term_string"}},
        {"@type": "Organization", "@id": f'{DOMAIN}/#org', "name": SITE_NAME, "url": f'{DOMAIN}/',
         "founder": {"@type": "Person", "name": "向阳乔木", "url": "https://x.com/vista8"},
         "sameAs": ["https://github.com/joeseesun/elon-musk-cn", "https://x.com/vista8"]},
        {"@type": "ItemList", "name": "最新精读", "numberOfItems": min(30, len(eps)),
         "itemListElement": [{"@type": "ListItem", "position": k + 1, "url": f'{DOMAIN}/ep/{x["s"]}/',
                              "name": x['zh'] or x['t']} for k, x in enumerate([y for y in eps if y.get('r')][:30])]},
    ]}

    tags = ['Tesla', 'SpaceX', '人工智能', '政治', '能源', 'Neuralink', 'X', '社会', 'Boring Company', '加密货币']
    tag_chips = ''.join(f'<button type="button" class="chip" data-tag="{esc(t)}">{esc(t)}</button>' for t in tags)

    grid_ssr = ''.join(ssr_card(x) for x in reversed(eps[-30:]))
    hero_ssr = ssr_hero(latest) if latest else ''

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<title>{SITE_NAME} · {len(eps)} 个视频 / 中文精读 / 预言追踪 / 语录</title>
<meta name="description" content="马斯克 1998 年至今 {len(eps)} 个公开视频全收录：每条独立页面附视频播放、英文文稿、AI 中文精读，外加预言追踪、语录与主题档案。">
<link rel="canonical" href="{DOMAIN}/">
<meta property="og:locale" content="zh_CN">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta property="og:title" content="{SITE_NAME}">
<meta property="og:description" content="{len(eps)} 个视频全收录：视频、文稿、中文精读、预言追踪、语录。">
<meta property="og:type" content="website">
<meta property="og:url" content="{DOMAIN}/">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta property="og:site_name" content="{SITE_NAME}">
{FEED_LINK}
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace('<', chr(92) + 'u003c')}</script>
{THEME_SCRIPT}
{HEAD_EXTRA}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>

<header class="masthead">
  <div class="wrap">
    <div class="mast-top">
      <span class="mast-date" id="mastDate"></span>
      <span class="mast-actions"><a class="mast-link" href="/search/">文稿搜索</a><a class="mast-link" href="/trends/">话题趋势</a><a class="mast-link" href="/stats/">数据</a><a class="mast-link" href="/predictions/">预言追踪</a><a class="mast-link" href="/quotes/">语录</a><a class="mast-link" href="/themes/">主题</a><a class="mast-link" href="/archive/">目录</a>{THEME_BTN}</span>
    </div>
    <h1 class="mast-title"><a href="/">Elon Musk <span>全访谈</span></a></h1>
    <p class="mast-sub" id="mastSub">{len(eps)} 个公开视频 · {n_zh} 篇中文精读 · {since} 年至今</p>
  </div>
</header>

<div class="toolbar">
  <div class="wrap toolbar-inner" role="search">
    <div class="search-box">
      <svg class="i-search" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>
      <input id="search" type="search" enterkeyhint="search" placeholder="搜索公司、产品、话题…" autocomplete="off" spellcheck="false" aria-label="搜索全部视频">
      <kbd class="search-kbd" aria-hidden="true">/</kbd>
      <button type="button" class="search-clear" aria-label="清除搜索">清除</button>
    </div>
    <div class="filters" id="filters" role="group" aria-label="筛选">
      <button type="button" data-f="all" class="on" aria-pressed="true">全部</button>
      <button type="button" data-f="zh" aria-pressed="false">中文精读<span class="n" data-n="zh"></span></button>
      <button type="button" data-f="tr" aria-pressed="false" hidden>有文稿<span class="n" data-n="tr"></span></button>
      <button type="button" data-f="hist" aria-pressed="false" hidden>看过<span class="n" data-n="hist"></span></button>
    </div>
    <button type="button" class="sort-btn" id="sort" data-dir="desc" aria-label="切换排序">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4v16M3.5 16.5L7 20l3.5-3.5M13 6h8M13 11h6M13 16h4"/></svg><span>最新</span>
    </button>
  </div>
  <div class="wrap"><div class="tag-row">{tag_chips}</div></div>
</div>

<main class="wrap" id="main">
  <section class="hero" id="hero" hidden aria-label="最新精读">{hero_ssr}</section>

  {insight_cards()}

  <section class="picks">
    <div class="sec-h"><h2>必看精选</h2><small>档案编辑选出的关键现场</small></div>
    <div class="pick-row">{picks_html}</div>
  </section>

  <section class="continue" id="continue" hidden aria-labelledby="cont-h">
    <div class="sec-h"><h2 id="cont-h">继续</h2><button type="button" id="contClear">清除记录</button></div>
    <div class="continue-row" id="contRow"></div>
  </section>

  <div class="result-line" id="resultLine" aria-live="polite"></div>
  <div id="grid" class="grid">{grid_ssr}</div>
  <div id="sentinel" class="sentinel"></div>
</main>

{SITE_FOOTER}

{umami_tag()}
<script src="/app.js?v={APP_V}"></script>
</body>
</html>
"""
    (SITE / 'index.html').write_text(html)
    print(f'index.html: ok (latest zh: {latest["s"] if latest else None})')


# ---------------------------------------------------------------- 预言页
def build_predictions():
    ps = extra['promises']
    zhc = extra_zh.get('promises') or []
    zho = extra_zh.get('outcomes') or {}
    order = {'kept': 0, 'late': 1, 'open': 2, 'missed': 3}
    items = []
    for idx, p in enumerate(ps):
        st = p.get('status')
        topic_zh = {'tesla': 'Tesla', 'spacex': 'SpaceX', 'ia': '人工智能', 'neuralink': 'Neuralink',
                    'politique': '政治', 'societe': '社会'}.get(p.get('topic'), p.get('topic'))
        video_link = ''
        vid = (p.get('video') or '').replace('yt-', '')
        target = next((m for m in master if m['srcId'] == vid), None)
        if target:
            video_link = f'<a class="pr-video" href="/ep/{target["slug"]}/">相关视频</a>'
        outcome = zho.get(str(idx), '')
        claim_zh = zhc[idx] if idx < len(zhc) else p['claim'][0]
        when = fmt_date(p.get('said') or '')
        dl = p.get('deadline') or ''
        dl_html = f'<span class="pr-dl">期限 {esc(dl)}</span>' if dl and dl != '—' else ''
        items.append(f"""<article class="pr-card st-{esc(st)}">
  <div class="pr-head"><span class="pr-status">{STATUS_ZH.get(st, st)}</span>
    <span class="pr-topic">{esc(topic_zh)}</span>
    <time class="pr-said">{when} 说</time>{dl_html}{video_link}</div>
  <p class="pr-claim">{esc(claim_zh)}</p>
  {f'<blockquote class="pr-quote" lang="en">{esc(p["quote"])}</blockquote>' if p.get('quote') else ''}
  {f'<p class="pr-outcome"><b>结果：</b>{esc(outcome)}</p>' if outcome else ''}
  <p class="pr-src">出处：<a href="{esc(p.get('url') or '#')}" target="_blank" rel="noopener">{esc(p.get('src') or '原始来源')}</a></p>
</article>""")
    counts = {s: sum(1 for p in ps if p['status'] == s) for s in order}
    claims = [zhc[i] if i < len(zhc) else p['claim'][0] for i, p in enumerate(ps)]
    tl_html, tl = insights.promise_timeline(ps, claims, STATUS_ZH)
    INSIGHT['mt'] = tl
    elon_time = f"""<section class="mt">
  <div class="mt-k">马斯克时间</div>
  <div class="mt-big"><b>× {tl['ratio_med']:.1f}</b><p>{tl['late_n']} 条迟到兑现的承诺里，从开口到真正做到，实际用时的中位数是他承诺时间的 {tl['ratio_med']:.1f} 倍；
    最夸张的一条是 {tl['ratio_max']:.1f} 倍。迟到时长的中位数约 {tl['late_med']}。</p></div>
  <p class="mt-tip">下面每一行是一条承诺：圆点是他开口的那天，黑线是他给的期限，琥珀色是迟到的部分，红色虚线是过了期限还没做到。</p>
  {tl_html}
</section>"""
    title = f'预言与承诺追踪 · {SITE_NAME}'
    desc = f'马斯克 {len(ps)} 条带日期的公开承诺与预言，以及经过核实的兑现结果。'
    url = f'{DOMAIN}/predictions'
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title,
          "url": f'{url}/', "inLanguage": "zh-CN", "description": desc,
          "isPartOf": {"@id": f'{DOMAIN}/#website'}}
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}/">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
{THEME_SCRIPT}
{HEAD_EXTRA}
{FEED_LINK}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{SITE_HEADER}
<main class="wrap ep-main" id="main">
  <header class="ep-head"><div class="ep-kicker">档案专题</div><h1 class="ep-title">预言与承诺追踪</h1>
    <p class="ep-dek">{len(ps)} 条带日期的公开承诺与预言：已兑现 {counts['kept']} 条，迟到兑现 {counts['late']} 条，待验证 {counts['open']} 条，未兑现 {counts['missed']} 条。每条附原始出处与核实结果。</p></header>
  {elon_time}
  <h2 class="pr-list-h">逐条核实</h2>
  <div class="pr-list">{''.join(items)}</div>
</main>
{SITE_FOOTER}
{umami_tag()}
</body>
</html>
"""
    out = SITE / 'predictions' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f'predictions page: {len(ps)} items')


# ---------------------------------------------------------------- 语录页
def build_quotes():
    sayings = extra['sayings']
    by_year = {}
    for s in sayings:
        by_year.setdefault((s.get('d') or '0000')[:4], []).append(s)
    nav = ''.join(f'<a href="#y{y}">{y}</a>' for y in sorted(by_year, reverse=True) if y != '0000')
    sec = []
    for y in sorted(by_year, reverse=True):
        rows = []
        for s in by_year[y]:
            u = f'<a class="qy-src" href="{esc(s.get("u") or "#")}" target="_blank" rel="noopener">来源</a>' if s.get('u') else ''
            kind = '<span class="qy-kind">X</span>' if s.get('k') == 'x' else ''
            zh = SAYINGS_ZH.get(s.get('id'))
            body = (f'<blockquote class="qy-quote bi"><p class="q-zh">{esc(zh)}</p><p class="q-en" lang="en">{esc(s["t"])}</p></blockquote>'
                    if zh else f'<blockquote class="qy-quote" lang="en">{esc(s["t"])}</blockquote>')
            rows.append(f'<li>{body}'
                        f'<p class="qy-meta"><span>{esc(s.get("d") or "")}</span>{kind}<span class="qy-src-text">{esc((s.get("src") or "")[:120])}</span>{u}'
                        f'<button type="button" class="q-copy" data-poster-q>生成海报</button></p></li>')
        sec.append(f'<section class="qy-year" id="y{y}"><h2>{y}<small>{len(by_year[y])} 条</small></h2><ol>{"".join(rows)}</ol></section>')
    title = f'语录 · {SITE_NAME}'
    desc = f'马斯克 {len(sayings)} 条公开语录：从 1998 年的互联网到 AI 与火星，每条注明年份与出处。'
    url = f'{DOMAIN}/quotes'
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}/">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
{THEME_SCRIPT}
{HEAD_EXTRA}
{FEED_LINK}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{SITE_HEADER}
<main class="wrap ep-main" id="main">
  <header class="ep-head"><div class="ep-kicker">档案专题</div><h1 class="ep-title">语录</h1>
    <p class="ep-dek">{len(sayings)} 条公开语录，按年份排列，每条注明出处{'，附中文译文（AI 翻译，以英文原话为准）' if SAYINGS_ZH else ''}；带 X 标记的来自他本人的帖子。</p></header>
  <nav class="ar-nav" aria-label="按年份跳转">{nav}</nav>
  {''.join(sec)}
</main>
{SITE_FOOTER}
{umami_tag()}
<script src="/kit.js?v={KIT_V}"></script>
</body>
</html>
"""
    out = SITE / 'quotes' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f'quotes page: {len(sayings)} sayings')


# ---------------------------------------------------------------- 主题页
THEME_META = {
    'ai': ('人工智能', '🤖', '人工智能'), 'mars': ('火星', '🔴', 'SpaceX'),
    'birth': ('出生率', '👶', '社会'), 'speech': ('言论自由', '🗣', 'X'),
    'energy': ('能源', '⚡', '能源'), 'autonomy': ('自动驾驶', '🚗', 'Tesla'),
    'gov': ('政府与监管', '🏛', '政治'), 'meaning': ('人生意义', '🌌', '社会'),
}


def build_themes():
    themes = extra['themes']
    zht = extra_zh.get('themes') or {}
    cards = []
    for t in themes:
        zh_title, zh_intro = (zht.get(t['key']) or [t['title'][0], t['intro'][0]])
        meta = THEME_META.get(t['key'], ('', '📎', ''))
        tag_link = f'<a class="th-tag" href="/?q={esc(meta[2])}">看相关视频 →</a>' if meta[2] else ''
        cards.append(f"""<article class="th-card" id="{esc(t['key'])}">
  <div class="th-emoji" aria-hidden="true">{meta[1]}</div>
  <h2>{esc(zh_title)} <span lang="en">{esc(t['title'][0])}</span></h2>
  <p>{esc(zh_intro)}</p>
  <p class="th-meta">他谈过 {t['n']} 次这个主题 · 高峰在 {max(t['freq'], key=lambda k: t['freq'][k])} 年{tag_link}</p>
</article>""")
    title = f'主题 · {SITE_NAME}'
    desc = f'马斯克反复谈论的 {len(themes)} 个主题：AI、火星、出生率、言论自由、能源、自动驾驶、政府监管与人生意义。'
    url = f'{DOMAIN}/themes'
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}/">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
{THEME_SCRIPT}
{HEAD_EXTRA}
{FEED_LINK}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{SITE_HEADER}
<main class="wrap ep-main" id="main">
  <header class="ep-head"><div class="ep-kicker">档案专题</div><h1 class="ep-title">主题</h1>
    <p class="ep-dek">把 651 个视频按他反复谈论的主题归纳成 {len(themes)} 条线索，每条附谈话次数与高峰年份。</p></header>
  <div class="th-grid">{''.join(cards)}</div>
</main>
{SITE_FOOTER}
{umami_tag()}
</body>
</html>
"""
    out = SITE / 'themes' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f'themes page: {len(themes)} themes')


# ---------------------------------------------------------------- 目录页
def build_archive(eps):
    years = {}
    for x in eps:
        years.setdefault((x['d'] or '0000')[:4], []).append(x)
    nav = ''.join(f'<a href="#y{y}">{y}</a>' for y in sorted(years, reverse=True) if y != '0000')
    sec = []
    for y in sorted(years, reverse=True):
        rows = []
        for x in years[y]:
            zh = x['zh'] or x['t']
            md = (x['d'] or '')[5:10].replace('-', '.')
            tag = '<span class="ar-zh">精读</span>' if x.get('r') else ''
            rows.append(f'<li><a href="/ep/{x["s"]}/"><span class="ar-n">{esc(x["k"] or "")}</span>'
                        f'<span class="ar-t"><b>{esc(zh)}</b><i lang="en">{esc(x["t"])}</i></span>'
                        f'<span class="ar-d">{esc(md or (x["d"] or "")[:4])}{tag}</span></a></li>')
        label = '年份未知' if y == '0000' else f'{y}'
        sec.append(f'<section class="ar-year" id="y{y}"><h2>{label}<small>{len(years[y])} 个</small></h2><ol>{"".join(rows)}</ol></section>')
    title = f'视频目录 · 全部 {len(eps)} 个 · {SITE_NAME}'
    desc = f'马斯克全部 {len(eps)} 个公开视频按年份排列的目录，含 {sum(1 for x in eps if x.get("r"))} 篇中文精读、视频与英文文稿。'
    url = f'{DOMAIN}/archive'
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}/">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
{THEME_SCRIPT}
{HEAD_EXTRA}
{FEED_LINK}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{SITE_HEADER}
<main class="wrap ar-main" id="main">
  <header class="ep-head"><div class="ep-kicker">视频目录</div><h1 class="ep-title">全部 {len(eps)} 个视频</h1>
    <p class="ep-dek">从 1998 年到最新一期，按年份排列；标有「精读」的视频附中文长文。</p></header>
  <nav class="ar-nav" aria-label="按年份跳转">{nav}</nav>
  {''.join(sec)}
</main>
{SITE_FOOTER}
{umami_tag()}
</body>
</html>
"""
    out = SITE / 'archive' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f'archive page: {len(eps)} videos')


# ---------------------------------------------------------------- 免责声明
DISCLAIMER_BODY = """
    <article class="ep">
      <header class="ep-head"><div class="ep-kicker">关于本站</div><h1 class="ep-title">免责声明与内容说明</h1></header>
      <div class="zh-article disclaimer-body">
        <p>本站（elon.qiaomu.ai）是一个非官方的中文导读与检索项目，帮助中文读者发现并理解马斯克 1998 年至今的公开访谈、发布会与股东大会视频。本站与 Elon Musk、Tesla、SpaceX、X 及其任何关联公司均无隶属或合作关系，站点内容不代表其观点或立场。</p>

        <h2>数据来源</h2>
        <p>本站的视频档案、语录、预言追踪与文稿数据来自 <a href="https://silicon-valley.tech/" target="_blank" rel="noopener">silicon-valley.tech（Elon Musk Archive）</a>公开语料，该语料明确允许研究与 AI 分析使用，但要求注明原始出处。本站每条视频页均保留指向原始来源的链接。</p>

        <h2>内容版权</h2>
        <p>所涉全部原始内容——包括视频、音频、文字稿、标题与节目名称——版权归 Elon Musk、各媒体及相应权利方所有。本站不托管、不存储、不分发任何媒体文件：YouTube 视频通过官方嵌入播放，X 与其他平台视频直链原始地址；文稿以引用与出处标注为限。</p>

        <h2>中文精读</h2>
        <p>「中文精读」由 AI 基于原始视频与文稿辅助生成的中文解读，属于二次创作，并非官方翻译，也未经任何人审阅。受语言理解与信息压缩所限，可能存在理解偏差、遗漏或错误，不构成对原意的权威解释。请以原始视频与文稿为准；如本站表述与原始内容存在出入，以原始内容为准。</p>

        <h2>预言追踪与语录</h2>
        <p>「预言与承诺追踪」与「语录」页的判定与整理来自 silicon-valley.tech 档案，本站仅做中文转述与导航。状态标注（已兑现 / 迟到兑现 / 待验证 / 未兑现）为该档案编辑的核实结论，仅供参考。</p>

        <h2>使用目的</h2>
        <p>本站为非商业性质，无广告、无收费，仅用于学习、检索与导读。如权利方认为本站任何内容不适合展示，请联系站点维护者，经确认后将移除或更正。</p>

        <h2>反馈与联系</h2>
        <p>纠错、建议或版权事宜，可通过 <a href="https://x.com/vista8" target="_blank" rel="noopener">X（@vista8）</a> 或 <a href="https://github.com/joeseesun/" target="_blank" rel="noopener">GitHub</a> 联系站点维护者。</p>
      </div>
    </article>
"""


def build_disclaimer():
    title = f'免责声明与内容说明 · {SITE_NAME}'
    desc = '本站性质、数据来源、内容版权归属、中文精读与文稿来源说明，以及反馈与移除流程。'
    url = f'{DOMAIN}/disclaimer'
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#ffffff">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}/">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
{THEME_SCRIPT}
{HEAD_EXTRA}
{FEED_LINK}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{SITE_HEADER}

<main class="wrap ep-main" id="main">{DISCLAIMER_BODY}
  <nav class="ep-prevnext">
    <span></span><a href="/">← 返回全部视频</a>
  </nav>
</main>

{SITE_FOOTER}
{umami_tag()}
</body>
</html>
"""
    out = SITE / 'disclaimer' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print('disclaimer page: ok')


# ---------------------------------------------------------------- 文稿全文检索
def build_search():
    docs = []
    for m in master:
        paras = PARAS.get(m['slug'])
        if paras:
            docs.append((m['slug'], m.get('d'), m['zh'], m['title'], m.get('kZh'), m.get('ytId'), paras))
    st = search_index.build(SITE / 'data' / 'search', docs)
    print(f"search index: {st['docs']} videos, {st['paras']} paragraphs, {st['terms']} terms, "
          f"shards {st['shard_total'] // 1024} KB (max {st['shard_max'] // 1024} KB)")
    zdocs = [(m['slug'], m.get('d'), m['zh'], m['title'], m.get('kZh'), m.get('ytId'), ZTEXTS[m['slug']])
             for m in master if m['slug'] in ZTEXTS]
    zs = search_index.build_zh(SITE / 'data' / 'search', zdocs)
    print(f"zh search index: {zs['docs']} articles, {zs['paras']} paragraphs, {zs['terms']} terms, "
          f"shards {zs['shard_total'] // 1024} KB (max {zs['shard_max'] // 1024} KB)")
    return st


def build_search_page():
    n_docs = len(PARAS)
    hours = round(sum((by_slug[s].get('sec') or 0) for s in PARAS) / 3600)
    title = f'文稿搜索 · 马斯克的原话 · {SITE_NAME}'
    n_zh = len(ZTEXTS)
    desc = (f'在 {n_docs} 份马斯克英文文稿（约 {hours} 小时）和 {n_zh} 篇中文精读里搜索，结果精确到段落，'
            '点时间戳直接跳到视频那一秒。中文、英文都能搜。')
    url = f'{DOMAIN}/search'
    ld = {"@context": "https://schema.org", "@type": "SearchResultsPage", "name": title, "url": f'{url}/',
          "inLanguage": "zh-CN", "description": desc, "isPartOf": {"@id": f'{DOMAIN}/#website'}}
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}/">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
{THEME_SCRIPT}
{HEAD_EXTRA}
{FEED_LINK}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{SITE_HEADER}
<main class="wrap sr-main" id="main">
  <header class="ep-head sr-head"><div class="ep-kicker">文稿搜索</div><h1 class="ep-title">马斯克说过什么</h1>
    <p class="ep-dek">在 {n_docs} 份英文文稿（约 {hours} 小时）和 {n_zh} 篇中文精读里找他说过的话。英文原话的结果能跳到视频里的那一秒。</p></header>
  <form class="sr-form" role="search" action="/search/" onsubmit="return false">
    <svg class="i-search" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>
    <input id="srq" name="q" type="search" enterkeyhint="search" autocomplete="off" spellcheck="false"
      placeholder="试试：第一性原理、火星时间表、first principles" aria-label="搜索文稿">
    <button type="button" class="sr-clear" aria-label="清除" hidden>清除</button>
  </form>
  <p class="sr-tip">中文、英文都能搜：中文词会翻成英文去查原话，英文词也会翻成中文去查精读。<code>"短语"</code> 精确匹配，<code>a|b</code> 表示任一。</p>
  <div id="srBody" aria-live="polite"><noscript><p class="sr-empty">文稿搜索需要启用 JavaScript。</p></noscript></div>
</main>
{SITE_FOOTER}
{umami_tag()}
<script src="/search.js?v={SEARCH_V}"></script>
</body>
</html>
"""
    out = SITE / 'search' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print('search page: ok')

# ---------------------------------------------------------------- 数据洞察页（话题趋势 / 档案数据）
INSIGHT = {}  # 洞察页构建时留下的结果，首页入口卡片要用，所以 main() 里首页最后构建

def page_html(path, title, desc, kicker, h1, dek, body, scripts='', main_cls='ins-main'):
    url = f'{DOMAIN}{path}'
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": url,
          "inLanguage": "zh-CN", "description": desc, "isPartOf": {"@id": f'{DOMAIN}/#website'}}
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{DOMAIN}/assets/og-default.jpg">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
{THEME_SCRIPT}
{HEAD_EXTRA}
{FEED_LINK}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
{SITE_HEADER}
<main class="wrap {main_cls}" id="main">
  <header class="ep-head"><div class="ep-kicker">{kicker}</div><h1 class="ep-title">{h1}</h1>
    <p class="ep-dek">{dek}</p></header>
{body}
</main>
{SITE_FOOTER}
{umami_tag()}
{scripts}
</body>
</html>
"""


def _en_docs():
    return [(m['slug'], m.get('d') or '', m['zh'], PARAS[m['slug']]) for m in master if m['slug'] in PARAS]


def build_trends_page():
    docs = _en_docs()
    qual = lambda slug: (2 if slug in ZTEXTS else 0) + (1 if (by_slug[slug].get('d') or '') >= '2015' else 0)
    t = insights.topic_trends(docs)
    INSIGHT['trends'] = t
    n_docs = len(PARAS)
    n_para = sum(t['totals'].values())
    presets = [('火星 vs AI', '火星, 人工智能'), ('三家公司', '特斯拉, SpaceX, 推特'), ('自动驾驶 vs 机器人', 'FSD, Optimus'),
               ('中国 vs 美国', '中国, 美国'), ('他说过多少次「明年」', '"next year"'), ('比特币 vs 狗狗币', '比特币, 狗狗币'),
               ('出生率', '出生率'), ('特朗普', '特朗普')]
    chips = ''.join(f'<button type="button" class="chip" data-ng="{esc(q)}">{esc(l)}</button>' for l, q in presets)
    body = f"""
  <section class="ins-sec">
    <div class="ins-h"><h2>话题热力图</h2><p>每一格是那一年的文稿里，提到这个话题的段落占比。颜色按每一行自己的最高点来深浅，看的是这个话题在他嘴里什么时候最热。点格子能直接搜那一年的原话。</p></div>
    {insights.heatmap_html(t)}
    <p class="ins-note">统计范围：{n_docs} 份英文文稿、{n_para:,} 个段落（含主持人与提问者的话）。2007 年及以前的视频较少，合并成一列。视频日期来自档案数据，个别视频日期可能不准。</p>
  </section>
  <section class="ins-sec" id="ngram">
    <div class="ins-h"><h2>自己比一比</h2><p>输入几个词，看它们在马斯克 {n_docs} 份文稿里逐年出现的频率。中文、英文都行，中文会自动翻成英文；用逗号隔开，最多 4 个。</p></div>
    <form class="ng-form" onsubmit="return false"><input id="ngq" type="search" enterkeyhint="search" autocomplete="off" placeholder="例如：火星, 人工智能, 特斯拉" aria-label="要比较的词"><button type="submit" class="ng-go">比较</button></form>
    <div class="chips ng-presets">{chips}</div>
    <div id="ngOut" class="ng-out" aria-live="polite"><noscript><p class="ins-note">这个图需要启用 JavaScript。</p></noscript></div>
  </section>
  <section class="ins-sec" id="attention">
    <div class="ins-h"><h2>注意力分配：他在聊哪家公司</h2><p>每一年提到各家公司的段落，按占比堆成 100%。2023 年推特（X）一下子占了一大半，2025 年以后 xAI 明显变宽。点图例去搜原话。</p></div>
    {insights.attention_html(docs)}
  </section>
  <section class="ins-sec" id="people">
    <div class="ins-h"><h2>他嘴里的人</h2><p>马斯克和采访者最常提到的人物，从总统、对手到他敬佩的科学家。</p></div>
    {insights.people_html(docs)}
  </section>
  <section class="ins-sec" id="future">
    <div class="ins-h"><h2>他嘴里的未来</h2><p>文稿里每一次提到「比说话时更晚的年份」都算一次：他最常把哪一年当成目标？</p></div>
    {insights.future_html(docs, qual)}
  </section>"""
    html = page_html('/trends/', f'马斯克在关心什么 · 话题趋势 · {SITE_NAME}',
                     f'从 {n_docs} 份马斯克英文文稿里统计 26 个话题 1998 年至今的热度变化：火星、AI、特斯拉、推特、DOGE、出生率……也可以输入任意词自己比较。',
                     '数据洞察', '马斯克在关心什么', f'把 {n_docs} 份文稿按年份摊开，看火星、AI、推特、政治这些话题在他嘴里什么时候升温、什么时候冷下来。',
                     body, f'<script src="/search.js?v={SEARCH_V}"></script>\n<script src="/trends.js?v={TRENDS_V}"></script>')
    out = SITE / 'trends' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f'trends page: {len(t["rows"])} topics × {len(t["cols"])} years')


KIND_GROUP = {'访谈': ('对话', 'k1'), '播客': ('对话', 'k1'), 'X Spaces': ('对话', 'k1'), '发布会': ('发布会', 'k2'),
              '大会演讲': ('演讲', 'k3'), '股东会': ('股东会', 'k4'), '政府活动': ('其他', 'k5'), '媒体': ('其他', 'k5')}


def build_stats_page():
    from collections import Counter, defaultdict
    by_year = defaultdict(Counter)
    hours = Counter()
    for m in master:
        y = (m.get('d') or '')[:4]
        if not y.isdigit():
            continue
        by_year[y][KIND_GROUP.get(m.get('kZh'), ('其他', 'k5'))] += 1
        hours[y] += (m.get('sec') or 0) / 3600
    ys = [str(y) for y in range(int(min(by_year)), int(max(by_year)) + 1)]
    mx = max(sum(c.values()) for c in by_year.values())
    groups = [('对话', 'k1'), ('发布会', 'k2'), ('演讲', 'k3'), ('股东会', 'k4'), ('其他', 'k5')]
    cols = []
    for y in ys:
        c = by_year.get(y, Counter())
        n = sum(c.values())
        segs = ''.join(f'<i class="{k}" style="height:{c[(g, k)] / mx * 100:.2f}%"></i>' for g, k in groups if c[(g, k)])
        tip = f'{y} 年：{n} 个视频，约 {hours[y]:.0f} 小时' + (''.join(f'；{g} {c[(g, k)]}' for g, k in groups if c[(g, k)]))
        cols.append(f'<div class="yb-col" title="{esc(tip)}" aria-label="{esc(tip)}"><span class="yb-n">{n or ""}</span>'
                    f'<div class="yb-stack">{segs}</div><span class="yb-y{" odd" if int(y) % 2 else ""}">{y[2:]}</span></div>')
    legend = ''.join(f'<span><i class="lg {k}"></i>{g}</span>' for g, k in groups)
    tr_sec = sum((by_slug[s].get('sec') or 0) for s in PARAS)
    words = sum(len(search_index._TOK.findall(search_index.norm(t))) for ps in PARAS.values() for _, t in ps)
    n_zh = len(ZTEXTS)
    n_tr = len(PARAS)
    kinds = Counter(m.get('kZh') or '其他' for m in master)
    kmax = max(kinds.values())
    kind_rows = ''.join(f'<li><span class="hb-l">{esc(k)}</span><span class="hb-bar"><i style="width:{v / kmax * 100:.1f}%"></i></span><span class="hb-n">{v}</span></li>'
                        for k, v in kinds.most_common())
    longest = sorted((m for m in master if m.get('sec')), key=lambda m: -m['sec'])[:10]
    lmax = longest[0]['sec']
    long_rows = ''.join(
        f'<li><a href="/ep/{esc(m["slug"])}/"><span class="hb-l">{esc(m["zh"] or m["title"])}<small>{esc((m.get("d") or "")[:4])} · {esc(m.get("kZh") or "")}</small></span>'
        f'<span class="hb-bar"><i style="width:{m["sec"] / lmax * 100:.1f}%"></i></span><span class="hb-n">{fmt_sec(m["sec"])}</span></a></li>'
        for m in longest)
    # 口头禅：只统计马斯克本人的回答（档案里分好说话人的 69 场）
    ans = defaultdict(list)
    vids = extra['quotes']['v']
    for vi, sec, text in extra['quotes']['q']:
        vid = vids[vi].split('-', 1)[1] if '-' in vids[vi] else vids[vi]
        m = next((x for x in master if x['srcId'] == vid), None)
        if m:
            ans[m['slug']].append((sec if sec is not None and sec >= 0 else None, text))
    adocs = [(s, by_slug[s].get('d') or '', by_slug[s]['zh'], segs) for s, segs in ans.items()]
    ps = insights.phrase_stats(adocs, lambda slug, sec: (2 if slug in ZTEXTS else 0) + (1 if sec is not None else 0))
    INSIGHT['ph'] = ps['rows']
    big = [(f'{len(master)}', '个公开视频', f'{ys[0]}–{ys[-1]}'), (f'{n_tr}', '份英文文稿', f'约 {tr_sec / 3600:.0f} 小时'),
           (f'{words / 10000:.0f} 万', '个英文词', '文稿总字数'), (f'{n_zh}', '篇中文精读', f'覆盖 {n_zh * 100 / max(1, n_tr):.0f}% 的文稿')]
    big_html = ''.join(f'<div class="bn"><b>{a}</b><span>{b}</span><small>{c}</small></div>' for a, b, c in big)
    body = f"""
  <div class="bn-row">{big_html}</div>
  <section class="ins-sec">
    <div class="ins-h"><h2>每年留下了多少公开视频</h2><p>档案里每一年的视频数，按场合分色。2022 年收购推特、2024–2025 年投身政治之后，他出现在镜头前的次数明显变多。</p></div>
    <div class="yb-legend">{legend}</div>
    <div class="yb" role="img" aria-label="每年公开视频数量柱状图">{''.join(cols)}</div>
  </section>
  <div class="ins-two">
    <section class="ins-sec"><div class="ins-h"><h2>在什么场合说话</h2></div><ol class="hb">{kind_rows}</ol></section>
    <section class="ins-sec"><div class="ins-h"><h2>最长的十场</h2></div><ol class="hb hb-long">{long_rows}</ol></section>
  </div>
  <section class="ins-sec" id="phrases">
    <div class="ins-h"><h2>跟马斯克学英语：他最爱用的词</h2><p>只统计马斯克本人说的话：档案里 {len(adocs)} 场已经分好说话人的对话，共约 {ps['words'] / 10000:.0f} 万词，按每万词出现几次排序。每个词配一句他的原话，点一下跳到视频里那一秒。</p></div>
    {insights.phrases_html(ps, ts_mmss)}
  </section>
  <section class="ins-sec" id="books">
    <div class="ins-h"><h2>马斯克书单：他在访谈里亲口提到的书</h2><p>不是网上流传的「推荐书单」，而是从 {n_tr} 份文稿里找出的、他在镜头前真正说起过的书。每本配一句原话，点一下跳到视频那一刻。</p></div>
    {insights.books_html(_en_docs(), lambda slug: (2 if slug in ZTEXTS else 0) + (1 if (by_slug[slug].get('d') or '') >= '2015' else 0))}
  </section>
  <section class="ins-sec">
    <div class="ins-h"><h2>中文精读进度</h2><p>AI 基于完整文稿改写的中文长文，正在一篇篇补齐。</p></div>
    <div class="zp"><div class="zp-bar"><i style="width:{n_zh * 100 / max(1, n_tr):.1f}%"></i></div><p><b>{n_zh}</b> / {n_tr} 篇 · <a href="/?f=zh">去读精读 →</a></p></div>
  </section>"""
    html = page_html('/stats/', f'档案数据 · 用数字看马斯克 · {SITE_NAME}',
                     f'{len(master)} 个马斯克公开视频、{n_tr} 份文稿的统计：每年出镜次数、场合分布、最长的对话，以及他最爱用的英文词和原话例句。',
                     '数据洞察', '用数字看马斯克', f'{len(master)} 个视频、{words / 10000:.0f} 万个英文词摊开来看：他哪年说得最多、在什么场合说、最爱用哪些词。',
                     body)
    out = SITE / 'stats' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f'stats page: {len(ys)} years, {len(ps["rows"])} phrases from {ps["words"]:,} words')

# ---------------------------------------------------------------- sitemap / llms / feed / 404
def build_sitemap(eps):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             f'<url><loc>{DOMAIN}/</loc><lastmod>{TODAY}</lastmod><priority>1.0</priority></url>',
             f'<url><loc>{DOMAIN}/search/</loc><lastmod>{TODAY}</lastmod><priority>0.8</priority></url>',
             f'<url><loc>{DOMAIN}/trends/</loc><lastmod>{TODAY}</lastmod><priority>0.8</priority></url>',
             f'<url><loc>{DOMAIN}/stats/</loc><lastmod>{TODAY}</lastmod><priority>0.7</priority></url>',
             f'<url><loc>{DOMAIN}/predictions/</loc><lastmod>{TODAY}</lastmod><priority>0.8</priority></url>',
             f'<url><loc>{DOMAIN}/quotes/</loc><lastmod>{TODAY}</lastmod><priority>0.8</priority></url>',
             f'<url><loc>{DOMAIN}/themes/</loc><lastmod>{TODAY}</lastmod><priority>0.8</priority></url>',
             f'<url><loc>{DOMAIN}/archive/</loc><lastmod>{TODAY}</lastmod><priority>0.7</priority></url>',
             f'<url><loc>{DOMAIN}/disclaimer/</loc><lastmod>{TODAY}</lastmod><priority>0.3</priority></url>']
    for x in eps:
        lines.append(f'<url><loc>{DOMAIN}/ep/{x["s"]}/</loc><lastmod>{x["d"] or TODAY}</lastmod><priority>0.7</priority></url>')
    lines.append('</urlset>')
    (SITE / 'sitemap.xml').write_text('\n'.join(lines))
    print(f'sitemap.xml: {len(eps) + 9} urls')


def build_llms(eps):
    lines = [f'# {SITE_NAME}（elon.qiaomu.ai）', '',
             f'> 马斯克 {len(eps)} 个公开视频的中文导航站（非官方粉丝站点）：1998 年至今的访谈、发布会、股东大会，'
             f'每条一个独立页面，含视频嵌入、英文文稿与 AI 改写的中文精读，另附预言追踪、语录与主题档案。'
             f'视频档案数据来自 silicon-valley.tech，内容版权归原权利方所有。', '',
             '## 使用说明', '',
             '- 每篇中文精读都有纯 Markdown 版本：在视频页网址后加 `index.md`',
             f'- 全部视频按年份的目录：{DOMAIN}/archive/',
             f'- 英文文稿全文搜索（结果带时间戳，可跳到视频对应位置）：{DOMAIN}/search/?q=first+principles',
             f'- 预言与承诺追踪：{DOMAIN}/predictions/ · 语录：{DOMAIN}/quotes/ · 主题：{DOMAIN}/themes/',
             f'- 话题趋势（26 个话题逐年热度）：{DOMAIN}/trends/ · 档案数据与马斯克高频英文词：{DOMAIN}/stats/',
             f'- RSS 全文订阅（最新 20 篇精读）：{DOMAIN}/feed.xml',
             '- 引用时请注明「elon.qiaomu.ai 中文精读（AI 改写，非官方翻译）」并链接对应网页。', '',
             '## 中文精读（AI 深度改写）', '']
    for x in eps:
        if x['s'] in ZH:
            lines.append(f'- [{x["zh"] or x["t"]}]({DOMAIN}/ep/{x["s"]}/index.md)：{x["k"]}，{fmt_date(x["d"])}')
    lines += ['', '## 全部视频索引', '']
    for x in eps:
        t = x['zh'] or x['t']
        orig = '' if not x['zh'] else f'（原标题：{x["t"]}）'
        lines.append(f'- [{t}]({DOMAIN}/ep/{x["s"]}/)：{x["k"] or ""}，{fmt_date(x["d"])}{orig}')
    (SITE / 'llms.txt').write_text('\n'.join(lines))
    print(f'llms.txt: {len(lines)} lines')


def cdata(s):
    return '<![CDATA[' + s.replace(']]>', ']]]]><![CDATA[>') + ']]>'


def rfc822(d):
    import datetime
    import email.utils
    try:
        dt = datetime.datetime.fromisoformat(d).replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        dt = datetime.datetime.now(datetime.timezone.utc)
    return email.utils.format_datetime(dt)


def build_feed(eps, limit=20):
    """RSS 2.0 全文订阅：最新 limit 篇中文精读。"""
    import datetime
    import email.utils
    items = []
    for x in [e for e in eps if e.get('r')][:limit]:
        slug = x['s']
        url = f'{DOMAIN}/ep/{slug}/'
        zh_file = SITE / 'zh' / f'{slug}.html'
        body = ''
        if zh_file.exists():
            body = (zh_file.read_text() +
                    f'<hr><p>本文为中文精读（AI 基于原始视频与文稿改写，仅供参考）。'
                    f'观看原视频与英文文稿请访问 <a href="{url}">原文页面</a>。</p>')
        desc = f'{x["k"] or "视频"} · {fmt_date(x["d"])}'
        items.append(
            f'<item><title>{esc(x["zh"] or x["t"])}</title>'
            f'<link>{url}</link>'
            f'<guid isPermaLink="true">{url}</guid>'
            f'<pubDate>{rfc822(x["d"])}</pubDate>'
            f'<description>{cdata(esc(desc))}</description>'
            f'<content:encoded>{cdata(body)}</content:encoded></item>')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f'<title>{SITE_NAME} · 中文精读</title>\n'
        f'<link>{DOMAIN}/</link>\n'
        f'<atom:link href="{DOMAIN}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        f'<description>马斯克 {len(eps)} 个公开视频的中文精读全文与导航（非官方粉丝站点）</description>\n'
        '<language>zh-CN</language>\n'
        f'<lastBuildDate>{email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc))}</lastBuildDate>\n'
        '<generator>elon.qiaomu.ai static build</generator>\n'
        + '\n'.join(items) + '\n</channel>\n</rss>\n')
    (SITE / 'feed.xml').write_text(xml)
    print(f'feed.xml: {len(items)} items, {len(xml) // 1024} KB')


def build_special_pages(eps):
    picks = [x for x in eps if x.get('r')][:4]
    links = ''.join(f'<li><a href="/ep/{x["s"]}/"><b>{esc(x["zh"] or x["t"])}</b>'
                    f'<i>{esc(x["k"] or "")} · {fmt_date(x["d"])}</i></a></li>' for x in picks)
    pages = {
        '404.html': ('页面不存在', '这一页没有找到', '链接可能写错了，或者那个视频换了地址。试试搜索，或者从最新的几篇精读读起。', True),
        'offline.html': ('离线', '现在没有网络', '读过的文章已为你离线保存，可以返回上一页继续阅读；联网后会自动恢复。', False),
    }
    for fn, (t, h1, dek, show) in pages.items():
        body = f"""<main class="wrap ep-main special" id="main">
  <header class="ep-head"><div class="ep-kicker">{t}</div><h1 class="ep-title">{h1}</h1><p class="ep-dek">{dek}</p>
  <p class="special-actions"><a class="more-btn" href="/">回到首页</a><a class="more-btn ghost" href="/#search">搜索视频</a></p></header>
  {f'<section class="special-list"><h2>最新精读</h2><ol>{links}</ol></section>' if show else ''}
</main>"""
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#ffffff">
<meta name="robots" content="noindex">
<title>{t} · {SITE_NAME}</title>
{THEME_SCRIPT}
{HEAD_EXTRA}
<link rel="stylesheet" href="/style.css?v={CSS_V}">
</head>
<body>
{SITE_HEADER}
{body}
{SITE_FOOTER}
{umami_tag()}
</body>
</html>
"""
        (SITE / fn).write_text(html)
    print('404 / offline pages: ok')


def clean_stale(eps):
    import shutil
    live = {x['s'] for x in eps}
    epdir = SITE / 'ep'
    if epdir.exists():
        for d in epdir.iterdir():
            if d.is_dir() and d.name not in live:
                shutil.rmtree(d)
                print('removed stale', d.name)


def main():
    eps = build_data()
    build_archive(eps)
    build_predictions()
    build_quotes()
    build_themes()
    build_disclaimer()
    for i, x in enumerate(eps):
        build_page(i, eps)
    print(f'ep pages: {len(list((SITE / "ep").glob("*/index.html")))}')
    build_search()
    build_search_page()
    build_trends_page()
    build_stats_page()
    build_index(eps)
    build_sitemap(eps)
    build_llms(eps)
    build_feed(eps)
    build_special_pages(eps)
    clean_stale(eps)


if __name__ == '__main__':
    main()
