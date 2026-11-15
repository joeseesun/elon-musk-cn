#!/usr/bin/env python3
"""为没有文稿的视频抓取 YouTube 字幕（自动/人工），补齐 data/transcripts/。

- 目标：master 中 platform=yt 且 tr=false 的视频
- 方式：yt-dlp 拉英文 vtt → 解析去重 → data/transcripts/<ytid>.json（mode=ytauto）
- 成功后更新 tools/elon-master.json 的 tr/trm
- 限速 + 重试，避免触发 YouTube 限流；幂等，可重复执行
"""
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
TR_DIR = DATA / 'transcripts'
MASTER = ROOT / 'tools' / 'elon-master.json'

WORKERS = 4
DELAY = 1.2
MAX_RETRY = 3


def ts_to_sec(ts):
    parts = [float(x) for x in ts.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


TAG_RE = re.compile(r'<[^>]+>')


def parse_vtt(text):
    """VTT → [[sec, text]]；去重滚动字幕的重复行。"""
    segs = []
    last_text = None
    block_start = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE')) or line.isdigit():
            continue
        m = re.match(r'([\d:.]+)\s*-->\s*([\d:.]+)', line)
        if m:
            block_start = ts_to_sec(m.group(1))
            continue
        if block_start is None:
            continue
        clean = TAG_RE.sub('', line).replace('&nbsp;', ' ').strip()
        if not clean:
            continue
        if clean != last_text:
            segs.append([block_start, clean])
            last_text = clean
    return segs


def fetch_one(ytid, tries=MAX_RETRY):
    for attempt in range(tries):
        try:
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / 'sub'
                r = subprocess.run(
                    ['yt-dlp', '--skip-download', '--no-warnings', '--quiet',
                     '--write-auto-subs', '--write-subs',
                     '--sub-langs', 'en.*', '--sub-format', 'vtt',
                     '-o', str(out), f'https://www.youtube.com/watch?v={ytid}'],
                    capture_output=True, text=True, timeout=120)
                vtts = list(Path(td).glob('*.vtt'))
                if not vtts:
                    if 'Sign in to confirm' in (r.stderr or '') or 'bot' in (r.stderr or ''):
                        raise RuntimeError('bot check')
                    return None, 'no-subs'
                best = max(vtts, key=lambda p: p.stat().st_size)
                raw = best.read_text(errors='replace')
                segs = parse_vtt(raw)
                if not segs or sum(len(s[1]) for s in segs) < 200:
                    return None, 'empty-subs'
                return segs, None
        except subprocess.TimeoutExpired:
            err = 'timeout'
        except RuntimeError as e:
            err = str(e)
            if err == 'bot check':
                time.sleep(30 * (attempt + 1))
        except Exception as e:
            err = str(e)[:100]
        time.sleep(2 * (attempt + 1))
    return None, err


def main():
    master = json.load(open(MASTER))
    todo = [m for m in master if m['platform'] == 'yt' and not m['tr']]
    print(f'todo: {len(todo)} videos without transcript', flush=True)

    lock_lock = __import__('threading').Lock()
    stats = {'ok': 0, 'fail': 0, 'nosubs': 0}
    failures = {}

    def work(m):
        time.sleep(DELAY)
        segs, err = fetch_one(m['ytId'])
        with lock_lock:
            if segs:
                (TR_DIR / f"{m['ytId']}.json").write_text(json.dumps({
                    'mode': 'ytauto',
                    'source': 'YouTube captions',
                    'url': f'https://www.youtube.com/watch?v={m["ytId"]}',
                    'publisher': 'YouTube（自动/人工字幕）',
                    'rel': 'auto',
                    'segs': segs,
                }, ensure_ascii=False))
                m['tr'] = True
                m['trm'] = 'ytauto'
                stats['ok'] += 1
                if stats['ok'] % 25 == 0:
                    json.dump(master, open(MASTER, 'w'), ensure_ascii=False, indent=1)
            else:
                stats['fail' if err not in ('no-subs', 'empty-subs') else 'nosubs'] += 1
                failures[m['ytId']] = err
        return m['ytId'], bool(segs), err

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(work, m): m['ytId'] for m in todo}
        for i, f in enumerate(as_completed(futs)):
            ytid, ok, err = f.result()
            tag = 'OK' if ok else f'MISS({err})'
            print(f'[{i + 1}/{len(todo)}] {ytid} {tag}', flush=True)

    json.dump(master, open(MASTER, 'w'), ensure_ascii=False, indent=1)
    n_tr = sum(1 for m in master if m['tr'])
    print(f"DONE ok={stats['ok']} no-subs={stats['nosubs']} fail={stats['fail']} | total tr={n_tr}/{len(master)}", flush=True)
    if failures:
        json.dump(failures, open('/tmp/elon_yt_sub_failures.json', 'w'), ensure_ascii=False, indent=1)
        print('failures saved to /tmp/elon_yt_sub_failures.json')


if __name__ == '__main__':
    main()
