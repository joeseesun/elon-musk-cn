# 马斯克全访谈 · 中文语料包

本包是 [https://elon.qiaomu.ai](https://elon.qiaomu.ai) 的中文增量语料，与 silicon-valley.tech 的英文原始语料**互补，不重复**：

- **英文原始语料**（逐字文稿、X 帖子与回复、预言英文原文）请直接去
  [silicon-valley.tech/#data](https://silicon-valley.tech/#data) 下载。本站不重新托管，引用请注明
  Elon Musk Archive。
- **本包**只含本站做的中文增量：586 篇 AI 改写的中文精读，以及翻译整理后的结构化数据。

## 文件

| 文件 | 内容 |
|---|---|
| `llms-full.txt` | 586 篇中文精读合并为单个纯文本文件，每篇带标题、日期与网页版链接。给 1M 上下文模型 / RAG / Agent 一次性读入。 |
| `deepreads/` | 586 篇中文精读，每篇一个 Markdown 文件，文件名即视频 slug。给 NotebookLM 作独立来源，或逐篇引用。 |
| `predictions.json` | 带日期的公开承诺 / 预言，含中英双语、状态与核实结果。 |
| `quotes.json` | 双语语录，英文原话 + 中文译文 + 年份 + 出处。 |
| `themes.json` | 8 大主题的中英介绍与逐年提及频率。 |
| `videos.json` | 651 条视频的目录：中英标题、日期、类型、时长、网页版与档案链接。 |

## 给 AI / Agent 用

- **单个大文件**：把 `llms-full.txt` 整个交给支持长上下文的模型，或切块后入库做 RAG。
- **逐篇来源**：用 `deepreads/` 里的 Markdown 作独立来源，回答可cite到具体某篇；每篇顶部有网页版链接可回填出处。
- **结构化查询**：`predictions.json` / `quotes.json` / `themes.json` / `videos.json` 适合程序化检索与交叉验证。
- **在线版**：每篇精读都有网页版 `https://elon.qiaomu.ai/ep/{slug}/`，Markdown 版在网址后加 `index.md`；整站清单见
  [https://elon.qiaomu.ai/llms.txt](https://elon.qiaomu.ai/llms.txt)。

## 版权与引用

- 视频与英文文稿版权归原权利方所有；本站不托管任何媒体文件。
- 中文精读为 AI 二次创作、非官方翻译，未经审阅，仅供学习参考。
- 引用请注明「https://elon.qiaomu.ai 中文精读（AI 改写，非官方翻译）」并链接对应网页版；使用英文原始语料时另请注明
  silicon-valley.tech（Elon Musk Archive）。

生成日期：2026-11-15
