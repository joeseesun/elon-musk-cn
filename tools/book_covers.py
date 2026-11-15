"""把书单用到的封面从本地黑客书架项目拷到 site/assets/books/{OpenLibrary id}.webp。

黑客书架（hackerbooks.qiaomu.ai）的 data/books.json 里每本书有 id（OL…W）和封面 id c，
封面文件在 covers/{c}.webp。用法：python3 tools/book_covers.py [黑客书架 site 目录]
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from insights import BOOKS  # noqa: E402

HB = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent.parent / 'hackerbook' / 'site')
DEST = ROOT.parent / 'site' / 'assets' / 'books'


def main():
    books = {b['id']: b for b in json.load(open(HB / 'data' / 'books.json'))}
    DEST.mkdir(parents=True, exist_ok=True)
    for b in BOOKS:
        hb = b[5]
        if not hb:
            continue
        info = books.get(hb)
        src = HB / 'covers' / f'{info["c"]}.webp' if info and info.get('c') else None
        # 不到 2KB 的多半是纯色布面精装，不如文字封面
        if not src or not src.exists() or src.stat().st_size < 2000:
            (DEST / f'{hb}.webp').unlink(missing_ok=True)
            print(f'  无封面：{b[0]} {hb}')
            continue
        shutil.copyfile(src, DEST / f'{hb}.webp')
        print(f'  {b[0]} ← {info["t"]}')


if __name__ == '__main__':
    main()
