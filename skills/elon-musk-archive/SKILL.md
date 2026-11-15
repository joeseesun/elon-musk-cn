---
name: elon-musk-archive
description: This skill should be used when a user asks about Elon Musk's public interviews, speeches, product launches, transcripts, exact quotes, views over time, predictions, books, or any content from elon.qiaomu.ai. It routes questions through the site's public MCP endpoint and returns sourced answers from 588 English transcripts, 586 Chinese deep-reads, 556 bilingual quotes, and the predictions/themes datasets.
agent_created: true
---

# 马斯克全访谈档案检索

## 用途

通过公开 MCP 端点 `https://elon.qiaomu.ai/mcp` 查询「马斯克全访谈」站点的全部文稿与结构化数据。覆盖 651 期视频、588 份带时间戳的英文逐字文稿、586 篇中文精读、556 条双语语录、22 条预言追踪和 8 大主题。MCP 不可用时，先按 `references/setup.md` 排查；不要直接凭记忆回答具体问题。

## 何时使用

- 用户问马斯克"说过什么""怎么看 X""什么时候说的"、要原话/出处/时间戳。
- 用户要找某一期访谈的英文文稿、中文精读，或按年份/主题找视频。
- 用户问预言是否兑现、语录原文、主题观点演变、提到的书/电影等站内数据。
- 用户用中文提出自然语言问题，或给出英文关键词要求全文检索。

## 标准工作流

1. **确认数据范围**：先调 `site_info` 了解当前数据规模；若用户没给具体期数，用 `list_episodes` 按年份/标题/类型定位 slug。
2. **全文检索**：调 `search`。中文问题可直接传（内置中英概念词表 + 在线翻译）；英文查询支持空格=且、`|`=或、`"短语"`=精确匹配。返回结果是段落级命中，带 slug、日期、时间戳和深链。
3. **核对原话**：对需要逐字引用、时间戳或上下文的结论，调 `get_transcript(slug, query=...)` 读取英文文稿；必要时增大 `limit` 或翻页 `offset`。中文精读只作背景理解，调 `get_deepread(slug)`，不要把它当成逐字翻译。
4. **交叉验证专题数据**：涉及语录、承诺兑现、主题热度时分别调 `get_quotes`、`get_predictions`、`get_themes`；这些工具返回中英双语与核实结果。
5. **给出带出处的答案**：每个事实后附视频页深链；英文原话附 `?t=秒` 或 `?p=段号`，中文精读附 `?z=段号`。说明数据来自「elon.qiaomu.ai / silicon-valley.tech 公开档案」。

## 查询构造

- `"first principles"` 精确短语；`mars colony` 两个词都要出现；`robot|humanoid` 任一出现。
- 中文如"他怎么看人工智能风险"可直接传入；若有多个概念，拆成 `search(query="人工智能 风险")` 这类空格分隔的"且"查询。
- 需要限定年代时传 `year_from` / `year_to`；一次 `limit` 不要超过 10，先看命中再决定是否深挖。
- 找不到结果时：换同义词、去掉虚词、改用英文关键词、放宽年份，或只查 `transcript` / `deepread` 单侧。

## 引用与边界

- 英文逐字文稿来自 silicon-valley.tech 公开档案，是原话依据；中文精读为 AI 改写，**不得当作原文逐字引用**。
- 不得编造时间戳、出处或原文；如果检索无命中，明确说明"站内未检索到"。
- 预言的"已兑现/迟到/未兑现/待验证"仅按站点核实结果陈述，不自行改写结论。
- 用户只要概览时优先用 `site_info` / `get_themes`，避免拉全文；用户要长文时用 `get_deepread` 分段读取。

## 资源

- `references/tools.md`：9 个 MCP 工具的完整参数、返回字段与调用示例。
- `references/setup.md`：朋友安装 MCP 与 Skill 的操作步骤（含 WorkBuddy / 通用客户端配置）。
- `scripts/mcp_http_check.py`：一条命令验证 HTTP 端点、列出工具。
