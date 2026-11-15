#!/usr/bin/env python3
"""品牌资产：站点图标（favicon / apple-touch / PWA，黑底白 Caslon「M」）与默认 OG 分享卡。

只在设计变更时运行 `python3 tools/brand.py`，产物入库（site/）。
字体（OFL 授权）首次运行时下载到 tools/.cache/fonts/。
"""
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / 'site'
CACHE = ROOT / '.cache'
FONTS = {
    'caslon': ('LibreCaslonText.ttf', 'https://raw.githubusercontent.com/google/fonts/main/ofl/librecaslontext/LibreCaslonText%5Bwght%5D.ttf'),
    'serif_sc': ('NotoSerifSC.ttf', 'https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf'),
}
INK, PAPER, RED = (17, 17, 17), (255, 255, 255), (179, 38, 30)


def font_path(key):
    name, url = FONTS[key]
    p = CACHE / 'fonts' / name
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        print(f'下载字体 {name} …')
        urllib.request.urlretrieve(url, p)
    return p


def font(key, size, weight='Bold'):
    f = ImageFont.truetype(str(font_path(key)), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def draw_icon(size, radius=0):
    img = Image.new('RGB', (size, size), INK)
    d = ImageDraw.Draw(img)
    f = font('caslon', int(size * 0.66), 'Bold')
    bbox = d.textbbox((0, 0), 'M', font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), 'M', font=f, fill=PAPER)
    if radius:
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius, fill=255)
        out = Image.new('RGB', (size, size), INK)
        out.paste(img, (0, 0), mask)
        return out
    return img


def build_icons():
    draw_icon(32).save(SITE / 'favicon-32.png')
    draw_icon(32).save(SITE / 'favicon.ico', sizes=[(32, 32)])
    draw_icon(180).save(SITE / 'apple-touch-icon.png')
    draw_icon(192).save(SITE / 'icon-192.png')
    draw_icon(512).save(SITE / 'icon-512.png')
    draw_icon(512).save(SITE / 'icon-maskable-512.png')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<rect width="64" height="64" fill="#111111"/>'
           '<text x="32" y="46" font-family="Georgia,serif" font-weight="700" font-size="42" '
           'fill="#ffffff" text-anchor="middle">M</text></svg>')
    (SITE / 'icon.svg').write_text(svg)
    print('icons: ok')


def build_og_default():
    W, H = 1200, 630
    img = Image.new('RGB', (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=INK)
    d.text((90, 120), 'ELON MUSK', font=font('caslon', 120, 'Bold'), fill=INK)
    d.text((92, 270), '全访谈', font=font('serif_sc', 120, 'Bold'), fill=INK)
    d.rectangle([90, 440, 210, 448], fill=RED)
    d.text((90, 470), '651 个公开视频 · 中文精读 · 预言追踪 · 语录', font=font('serif_sc', 42, 'Medium'), fill=(107, 107, 103))
    d.text((90, 540), 'elon.qiaomu.ai', font=font('caslon', 40, 'Bold'), fill=(107, 107, 103))
    out = SITE / 'assets'
    out.mkdir(exist_ok=True)
    img.save(out / 'og-default.jpg', quality=88)
    print('og-default: ok')


if __name__ == '__main__':
    build_icons()
    build_og_default()
