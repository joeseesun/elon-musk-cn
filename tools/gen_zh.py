#!/usr/bin/env python3
"""批量生成《中文精读》：把带文稿的视频喂给 Magpie，按乔木风格提示词改写成 HTML 片段。

- 断点续跑：site/zh/{slug}.html 已存在即跳过
- 默认只跑 STARTER 精选集；--all 跑全部带文稿视频；--only=slug 单跑
- 校验器检查禁用句式/破折号/Markdown 残留/篇幅，不合格带反馈重试
- 超长文稿（>350KB）走两段笔记 + 成文（同 lex 侧管线）
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
ZH_DIR = SITE / 'zh'
TR_DIR = ROOT / 'data' / 'transcripts'
INDEX_FILE = SITE / 'data' / 'zh-index.json'

BASE_URL = 'https://magpie.qiaomu.ai/v1'
MODELS_ALL = [
    'opencode-go/deepseek-v4.1-flash',
    'trae-cn/deepseek-v4.1-flash',
    'workbuddy/deepseek-v4.1-flash',
    'bigmodel-preview/glm-x-preview-f',
]
MT_OVERRIDES = {
    'opencode-go/deepseek-v4.1-flash': 16384,
    'bigmodel-preview/glm-x-preview-f': 16384,
}
MAX_TOKENS = 8192
CHUNK_BYTES = 350_000
WORKERS = 4
DEPLOY_EVERY = 30  # 每生成 30 篇自动 build + rsync 部署

_stats_lock = threading.Lock()
_last_ok_model = [None]

# 首发精读集：跨年份、跨公司的标志性访谈（slug 见 elon-master.json）
STARTER = [
    'elon-musk-talks-twitter-tesla-and-how-his-brain-works-live-at-te',
    'joe-rogan-experience-1169-elon-musk',
    'joe-rogan-experience-1609-elon-musk',
    'elon-musk-s-full-interview-with-code-conference',
    'elon-full-bbc-interview-12-april-2023',
    'elon-musk-on-racism-bailing-out-trump-hate-speech-and-more-the-d',
    'elon-musk-interviewed-by-ron-baron-4-november-2022',
    'tesla-ai-day-2022',
    'tesla-battery-day',
    'tesla-unveils-model-3',
    'elon-musk-neuralink-and-the-future-of-humanity-lex-fridman-podca',
    'elon-musk-war-ai-aliens-politics-physics-video-games-and-humanit',
    'ai-discussion-with-rishi-sunak',
    'elon-musk-shows-jay-leno-his-spacex-rockets-jay-leno-s-garage-fu',
    'elon-musk-a-future-worth-getting-excited-about-tesla-texas-gigaf',
]

_api_key = None


def api_key():
    global _api_key
    if _api_key is None:
        _api_key = os.environ.get('MAGPIE_API_KEY') or subprocess.run(
            ['security', 'find-generic-password', '-s', 'qiaomu-llm', '-a', 'magpie', '-w'],
            capture_output=True, text=True, check=True).stdout.strip()
    return _api_key


SYSTEM = """你是向阳乔木，一位中文科技内容作者。擅长把信息密度高的英文报告、机器翻译稿或直播文字稿，改写成逻辑清晰、读感流畅的中文文章。
目标读者是有一定技术背景的从业者，时间有限，不喜欢废话，但愿意为真正有价值的内容停下来细读。

---

## 语言风格

- 口语化，对话感强，像和读者面对面聊天
- 短段落，多留白，视觉舒适
- 善用生活化类比解释复杂概念，在专业性和可读性之间自然平衡
- 始终使用第三人称视角叙述
- 真诚、不装，承认困惑，专业但不掉书名
- 数据和案例支撑观点，有洞察力，给读者"原来如此"的感觉
- **直接陈述事实和观点，不给内容贴标签**。不说"这是一个反直觉的数据"，直接说数据是什么。让内容本身说话

---

## 格式规范

- 重要观点用**加粗**突出
- 全程使用中文标点：逗号（，）句号（。）冒号（：）问号（？）顿号（、）书名号（《》）
- 禁止使用中文破折号和英文破折号
- 禁止使用 `---` 水平分隔线，h2/h3 标题本身已做内容分割
- 引用马斯克或访谈者原话用 <blockquote>（翻译成中文，句末括号注明说话人）

---

## 禁用表达

以下词汇和句式有明显的 AI 生成感，一律不用：

**句式禁用：**
不是……而是、想象一下、你有没有想过、值得注意的是、不难理解、毋庸置疑、随着……的发展、对于……来说、在……方面、让我们、关键在于、这是一个、总之、综上所述

**词汇禁用：**
精准打击、赋能、落地、深度融合、全面布局、强势崛起等空洞套话

**预告式渲染禁用：**
"最让我吃惊的是"、"最扎心的是"、"最意外的是"这类预告句式。用具体细节代替情绪预告。

---

## 写作结构

**开头** 必须有钩子：一个反常识的数据、一个尖锐的问题，或一个让人想继续读下去的矛盾。直接陈述事实，让读者自己得出结论。

**正文**
- 每个段落只说一件事
- 因果关系写清楚，尽量把因果关系自然嵌入叙述
- 遇到反直觉的结论，在读者产生疑问之前主动解释
- 小标题要有实际信息量，不用"背景介绍""数据分析"这类标题
- 这是马斯克的访谈，读者想知道他对 AI、火星、电动车、X（推特）、政治、人类未来的真实想法和论据，把这些论点组织清楚

**结尾**
给出一个对读者真正有用的行动结论，不做空泛总结。

---

## 忠实度要求

- 保留原文所有关键数据和核心结论，不遗漏，不夸大
- 可以调整结构和顺序，但不能改变原意
- 文字稿可能来自语音识别，按上下文合理还原专业名词

---

## 本次任务的特殊约定（输出格式）

1. 输入材料是马斯克某次访谈/发布会的英文文字稿。
2. 输出一个完整的 HTML 片段，只允许这些标签：p、h2、ul、ol、li、blockquote、strong、em。
3. 严禁出现任何 Markdown 语法：不加粗星号、不用井号标题、不用 > 引用符、不用代码围栏。加粗一律写 <strong>，小标题一律写 <h2>。
4. 不要 h1，不要 <html>、<body> 等外层标签，不要任何解释或前言，直接从第一个 <p> 开始输出。
5. 全文简体中文，专有名词首次出现时可括注英文原名。正文不少于 5000 个汉字；文字稿特别长的写足 6000 到 7500 字。
6. 结尾的行动结论用一个 ul 列表呈现，给读者可操作的具体建议。
"""

FORBIDDEN = [
    (r'不是[^。\n]{0,15}而是', '句式"不是……而是"'),
    (r'想象一下', '句式"想象一下"'),
    (r'你有没有想过', '句式"你有没有想过"'),
    (r'值得注意的是', '句式"值得注意的是"'),
    (r'不难理解', '句式"不难理解"'),
    (r'毋庸置疑', '词汇"毋庸置疑"'),
    (r'让我们', '句式"让我们"'),
    (r'关键在于', '句式"关键在于"'),
    (r'这是一个', '贴标签开场"这是一个"'),
    (r'最让我吃惊|最扎心|最意外的是', '预告式渲染'),
    (r'总之|综上所述|总而言之', '空泛总结词'),
    (r'精准打击|赋能|深度融合|全面布局|强势崛起', '空洞套话'),
    (r'随着[^。\n]{0,20}的发展', '句式"随着……的发展"'),
    (r'对于[^。\n]{0,10}来说', '句式"对于……来说"'),
    (r'在[^。，\n]{1,6}方面', '句式"在……方面"'),
]
DASH_RE = re.compile(r'——|—|–|--')
ALLOWED_TAGS = {'p', 'h2', 'h3', 'ul', 'ol', 'li', 'blockquote', 'strong', 'em', 'br'}


def chat(messages, max_tokens=MAX_TOKENS, timeout=1200, model=None):
    global _last_ok_model
    order = MODELS_ALL if not model else [model] + [m for m in MODELS_ALL if m != model]
    last = None
    for cur in order:
        for attempt in range(6):
            try:
                r = requests.post(
                    f'{BASE_URL}/chat/completions',
                    headers={'Authorization': f'Bearer {api_key()}', 'Content-Type': 'application/json'},
                    json={'model': cur, 'messages': messages, 'max_tokens': MT_OVERRIDES.get(cur, max_tokens),
                          'temperature': 0.7},
                    timeout=timeout)
                if r.status_code in (400, 401, 402, 403):
                    last = f'HTTP {r.status_code} on {cur}'
                    print(f'model down: {cur} ({r.status_code}), next in ladder', flush=True)
                    break
                if r.status_code == 429 or r.status_code >= 500:
                    last = f'HTTP {r.status_code}: {r.text[:200]}'
                    time.sleep(min(300, 8 * 2 ** attempt))
                    continue
                r.raise_for_status()
                data = r.json()
                msg = data['choices'][0]['message']
                content = msg.get('content') or ''
                if not content.strip() and msg.get('reasoning_content'):
                    last = f'{cur}: reasoning-only response'
                    print(f'model unusable: {cur}, next in ladder', flush=True)
                    break
                _last_ok_model[0] = cur
                return content, data['choices'][0].get('finish_reason', '')
            except requests.RequestException as e:
                last = f'{cur}: {str(e)[:250]}'
                time.sleep(min(300, 8 * 2 ** attempt))
    raise RuntimeError(f'chat failed across ladder: {last}')


def chat_full(messages, model=None):
    out, msgs = '', list(messages)
    for _ in range(5):
        text, reason = chat(msgs, model=model)
        out += text
        if reason != 'length' or not text.strip():
            return out
        msgs = msgs + [{'role': 'assistant', 'content': text},
                       {'role': 'user', 'content': '继续输出剩余部分，从中断处接着写，不要重复已有内容，也不要重新开头。'}]
    return out


def clean(text):
    text = text.strip()
    text = re.sub(r'^```(?:html)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    m = re.search(r'<(?:p|h2|ul|ol|blockquote)[ >]', text)
    if m and m.start() > 0:
        text = text[m.start():]
    return text.strip()


def validate(html, size):
    problems = []
    for tag in set(re.findall(r'</?([a-zA-Z0-9]+)[ >/]', html)):
        if tag.lower() not in ALLOWED_TAGS:
            problems.append(f'出现不允许的标签 <{tag}>')
    for pat, label in FORBIDDEN:
        hits = re.findall(pat, html)
        if hits:
            problems.append(f'{label}（{hits[0][:30]}）')
    if DASH_RE.search(html):
        problems.append('出现破折号')
    if re.search(r'\*\*|^#{1,6}\s|^\s*>|```|^\s*[-*]\s', html, re.M):
        problems.append('残留 Markdown 语法')
    if '<h2' not in html:
        problems.append('缺少 h2 小标题')
    plain = re.sub(r'<[^>]+>', '', html)
    cjk = len(re.findall(r'[\u4e00-\u9fff]', plain))
    if cjk < min_chars(size):
        problems.append(f'篇幅不足：正文汉字 {cjk}，要求 ≥ {min_chars(size)}')
    return problems, cjk


def min_chars(size):
    if size >= 300_000:
        return 5000
    if size >= 100_000:
        return 4200
    if size >= 30_000:
        return 3200
    return 1800


def transcript_text(src_id):
    """从 data/transcripts/<srcId>.json 还原纯文本（segs 去时间戳）。"""
    f = TR_DIR / f'{src_id}.json'
    if not f.exists():
        return None
    t = json.load(open(f))
    return '\n'.join(s[1] for s in t.get('segs', []) if s[1]).strip() or None


def take_notes(chunk, part, model=None):
    msgs = [{'role': 'system', 'content':
             '你是研究助理。从访谈文字稿片段中提取详尽的中文笔记，逐条列出：关键论点、数据、故事、分歧与结论。'
             '保留其中最有力的 8-12 句原话（英文原句照抄，注明说话人）。不要评论，只要事实要点。'}]
    msgs.append({'role': 'user', 'content': f'以下是某次访谈文字稿的{part}：\n\n{chunk}\n\n请输出笔记。'})
    return chat(msgs, max_tokens=3000, timeout=900, model=model)[0]


def gen_one(m, trans, model=None):
    zh = m.get('zh') or ''
    when = f"{m['d'][:4]} 年 {m['d'][5:7]} 月" if len(m.get('d') or '') >= 7 else m.get('d') or '年份未知'
    meta = (f'视频信息：\n- 英文标题：{m["title"]}\n'
            + (f'- 中文标题：{zh}\n' if zh else '')
            + f'- 频道：{m.get("ch") or "见标题"}\n- 时间：{when}\n\n')
    if len(trans) > CHUNK_BYTES:
        half = len(trans) // 2
        for cut in (half, half - 20000, half + 20000):
            if trans[cut:cut + 1] in (' ', '\n'):
                half = cut
                break
        notes_a = take_notes(trans[:half], '前半部分', model=model)
        notes_b = take_notes(trans[half:], '后半部分', model=model)
        user = (meta + '以下是对这期视频两段文字稿的详细笔记（含原话引文），'
                '请基于笔记写一篇覆盖全部内容的《中文精读》，结构、风格、篇幅按系统提示词要求：\n\n'
                '【前半部分笔记】\n' + notes_a + '\n\n【后半部分笔记】\n' + notes_b)
    else:
        user = (meta + '以下是这期视频的完整英文文字稿：\n\n' + trans +
                '\n\n请写一篇《中文精读》文章，按系统提示词的风格、结构与篇幅要求输出 HTML 片段。')
    msgs = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]
    html = clean(chat_full(msgs, model=model))
    problems, cjk = validate(html, len(trans))
    for round_no in range(2):
        if not problems:
            return html, cjk, []
        fb = '；'.join(problems)
        msgs = msgs + [{'role': 'assistant', 'content': html},
                       {'role': 'user', 'content':
                        f'你的文章存在问题：{fb}。请重写并输出修订后的完整 HTML 片段（从头到尾完整输出，不要只给修改处），继续满足系统提示词的全部要求。'}]
        html = clean(chat_full(msgs, model=model))
        problems, cjk = validate(html, len(trans))
    return (html, cjk, problems) if not problems else (None, cjk, problems)


def update_index(slug):
    with _stats_lock:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = json.load(open(INDEX_FILE)) if INDEX_FILE.exists() else {'slugs': []}
        if slug not in data['slugs']:
            data['slugs'].append(slug)
            json.dump(data, open(INDEX_FILE, 'w'), ensure_ascii=False)


def main():
    only = all_mode = None
    for a in sys.argv[1:]:
        if a.startswith('--only='):
            only = a.split('=', 1)[1]
        if a == '--all':
            all_mode = True

    master = json.load(open(ROOT / 'tools' / 'elon-master.json'))
    trans_titles = json.load(open(ROOT / 'tools' / 'translations.json')) if (ROOT / 'tools' / 'translations.json').exists() else {}
    eps = {x['slug']: x for x in master}
    for x in master:
        x['zh'] = (trans_titles.get(x['slug']) or {}).get('zh')

    todo = []
    for slug in (STARTER if not all_mode else sorted(eps)):
        if only and slug != only:
            continue
        m = eps.get(slug)
        if not m or (ZH_DIR / f'{slug}.html').exists():
            continue
        trans = transcript_text(m['srcId'])
        if trans and len(trans) > 800:
            todo.append((slug, m, trans))
    print(f'todo: {len(todo)} videos with transcript but no zh', flush=True)

    done = fail = 0
    since_deploy = 0
    failures = {}
    attempts = {}
    MAX_ATTEMPTS = 4

    def work(item):
        slug, m, trans = item
        with _stats_lock:
            idx = attempts.get(slug, 0)
            attempts[slug] = idx + 1
            model = MODELS_ALL[min(idx, len(MODELS_ALL) - 1)]
        t0 = time.time()
        try:
            html, cjk, problems = gen_one(m, trans, model=model)
        except Exception:
            raise
        if html is None:
            return slug, None, cjk, time.time() - t0, problems, model
        ZH_DIR.mkdir(exist_ok=True)
        (ZH_DIR / f'{slug}.html').write_text(html)
        update_index(slug)
        return slug, cjk, cjk, time.time() - t0, [], _last_ok_model[0] or model

    while todo:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futs = {pool.submit(work, it): it[0] for it in todo}
            for fut in as_completed(futs):
                slug = futs[fut]
                try:
                    slug, cjk, _, dt, problems, model = fut.result()
                    if cjk is None or cjk == 0:
                        fail += 1
                        failures[slug] = '; '.join(problems)
                        print(f'FAIL {slug} [{model}] ({dt:.0f}s): {"; ".join(problems)[:250]}', flush=True)
                    else:
                        done += 1
                        since_deploy += 1
                        print(f'OK {slug} chars={cjk} [{model}] ({dt:.0f}s) [{done + fail}]', flush=True)
                except Exception as e:
                    fail += 1
                    failures[slug] = str(e)[:200]
                    print(f'ERR {slug}: {str(e)[:150]}', flush=True)
        if since_deploy >= DEPLOY_EVERY:
            print(f'--- deploying ({since_deploy} new) ---', flush=True)
            try:
                subprocess.run([sys.executable, 'tools/build.py'], cwd=ROOT, check=True, capture_output=True)
                subprocess.run(['tools/deploy.sh'], cwd=ROOT, check=True, capture_output=True)
                print('deploy ok', flush=True)
            except Exception as e:
                print(f'deploy FAILED: {str(e)[:300]}', flush=True)
            since_deploy = 0
        todo = [it for it in todo if (ZH_DIR / f'{it[0]}.html').exists() is False
                and attempts.get(it[0], 0) < MAX_ATTEMPTS]
        if not all_mode:
            break

    print(f'FINISHED done={done} fail={fail}', flush=True)
    if done and since_deploy:
        try:
            subprocess.run([sys.executable, 'tools/build.py'], cwd=ROOT, check=True, capture_output=True)
            subprocess.run(['tools/deploy.sh'], cwd=ROOT, check=True, capture_output=True)
            print('final deploy ok', flush=True)
        except Exception as e:
            print(f'final deploy FAILED: {str(e)[:300]}', flush=True)
    if failures:
        json.dump(failures, open('/tmp/elon_gen_zh_failures.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
