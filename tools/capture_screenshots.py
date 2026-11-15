#!/usr/bin/env python3
"""刷新 README 截图。默认截线上站点，可用 SCREENSHOT_URL 指向本地预览。

依赖：python3 -m pip install playwright
用法：python3 tools/capture_screenshots.py
"""

import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
BASE = os.environ.get("SCREENSHOT_URL", "https://elon.qiaomu.ai").rstrip("/")
CHROME = os.environ.get(
    "CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)

EP = "/ep/elon-musk-the-end-of-work-the-death-of-money-and-a-world-run-by/"

# 名称、路径、可选滚动锚点、等待选择器、宽度、高度
SHOTS = [
    ("home", "/", "", "", 1440, 1000),
    ("episode", EP, "", "", 1440, 1000),
    ("search", "/search/?q=%E7%81%AB%E6%98%9F", "", ".sr-list > *", 1440, 1000),
    ("predictions", "/predictions/", "", "", 1440, 1000),
    ("quotes", "/quotes/", "", "", 1440, 1000),
    ("themes", "/themes/", "", "", 1440, 1000),
    ("trends", "/trends/", "", "", 1440, 1000),
    ("stats", "/stats/", "", "", 1440, 1000),
    ("corpus", "/stats/", "corpus", "", 1440, 1000),
    ("books", "/stats/", "books", "", 1440, 1000),
    ("movies", "/stats/", "movies", "", 1440, 1000),
    ("mcp", "/mcp/", "", "", 1440, 1000),
    ("i18n", "/stats/?lang=en", "", "", 1440, 1000),
    ("mobile", "/", "", "", 500, 900),
]


def main():
    if not Path(CHROME).exists():
        sys.exit(f"找不到 Chrome：{CHROME}（可用 CHROME_BIN 指定）")
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
        for name, path, anchor, wait_for, width, height in SHOTS:
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                service_workers="block",
                locale="zh-CN",
            )
            page = context.new_page()
            print(f"→ {name}  {path}" + (f"#{anchor}" if anchor else ""), flush=True)
            page.goto(BASE + path, wait_until="domcontentloaded", timeout=60000)
            if wait_for:
                try:
                    page.locator(wait_for).first.wait_for(state="visible", timeout=15000)
                except Exception:
                    print(f"  警告：未等到 {wait_for}，仍继续截图", file=sys.stderr)
            page.wait_for_timeout(1200)
            page.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
            page.wait_for_timeout(900)
            page.add_style_tag(content=".kit-toast{display:none !important}")
            if anchor:
                y = page.evaluate(
                    """id => {
                        const el = document.getElementById(id);
                        return el ? el.getBoundingClientRect().top + window.scrollY - 70 : 0;
                    }""",
                    anchor,
                )
                page.evaluate("y => window.scrollTo(0, y)", y)
                page.wait_for_timeout(1800)
            page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=82)
            context.close()
        browser.close()

    print(f"完成：{len(SHOTS)} 张截图 → {OUT}")
    subprocess.run(["du", "-sh", str(OUT)], check=False)


if __name__ == "__main__":
    main()
