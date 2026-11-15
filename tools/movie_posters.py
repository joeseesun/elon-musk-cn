"""用 OMDb 下载片单海报到 site/assets/movies/{IMDb id}.webp。

需要 OMDb API key：OMDB_API_KEY=... python3 tools/movie_posters.py [--force]
已有的海报默认跳过；OMDb 没有海报的片子，页面会退回文字封面。
"""
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from insights import MOVIES  # noqa: E402

DEST = ROOT.parent / 'site' / 'assets' / 'movies'
WIDTH = 240


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'elon-archive/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    key = os.environ.get('OMDB_API_KEY')
    if not key:
        sys.exit('缺少 OMDB_API_KEY 环境变量')
    force = '--force' in sys.argv
    DEST.mkdir(parents=True, exist_ok=True)
    for zh, en, yr, kind, q, note, imdb in MOVIES:
        out = DEST / f'{imdb}.webp'
        if out.exists() and not force:
            continue
        info = json.loads(get('https://www.omdbapi.com/?' + urllib.parse.urlencode({'apikey': key, 'i': imdb})))
        poster = info.get('Poster')
        if info.get('Response') != 'True' or not poster or poster == 'N/A':
            print(f'  无海报：{zh} {imdb} {info.get("Error", "")}')
            continue
        if info.get('Title', '').lower().lstrip('the ') != en.lower().lstrip('the ') or not info.get('Year', '').startswith(yr):
            print(f'  注意：{zh} 对应 OMDb「{info.get("Title")}」({info.get("Year")})')
        im = Image.open(io.BytesIO(get(poster))).convert('RGB')
        if im.width > WIDTH:
            im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        im.save(out, 'WEBP', quality=80, method=6)
        print(f'  {zh} ← {info["Title"]} ({info["Year"]}) {im.width}×{im.height} {out.stat().st_size // 1024}KB')


if __name__ == '__main__':
    main()
