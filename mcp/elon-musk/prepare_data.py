#!/usr/bin/env python3
"""从已构建的 site/ 刷新随包数据快照（结构化 JSON + 中英概念词表）。

用法：python3 mcp/elon-musk/prepare_data.py [repo_root]
"""

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "data"
SITE = ROOT / "site"
OUT.mkdir(parents=True, exist_ok=True)

for name in ("videos", "quotes", "predictions", "themes"):
    src = SITE / "corpus" / f"{name}.json"
    if src.is_file():
        shutil.copy2(src, OUT / f"{name}.json")
        print("copied", src.name)

for name in ("episodes.json", "zh-index.json"):
    src = SITE / "data" / name
    if src.is_file():
        shutil.copy2(src, OUT / name)
        print("copied", name)

src = ROOT / "site" / "search.js"
if src.is_file():
    block = re.search(r"const GLOSS = \{(.*?)\n  \};", src.read_text(encoding="utf-8"), re.S)
    if block:
        gloss = {}
        for m in re.finditer(r"'([^']+)':\s*\[(.*?)\]", block.group(1), re.S):
            vals = re.findall(r'"([^"]+)"|\'([^\']+)\'', m.group(2))
            gloss[m.group(1)] = [a or b for a, b in vals]
        (OUT / "glossary.json").write_text(json.dumps(gloss, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("glossary", len(gloss), "entries")
print("snapshot ready:", OUT)
