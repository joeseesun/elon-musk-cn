# MCP 工具参考

端点：`https://elon.qiaomu.ai/mcp`（Streamable HTTP，POST JSON-RPC 2.0）。所有工具只读。

## search

全文检索英文逐字文稿与中文精读，段落级命中。

| 参数 | 类型 | 说明 |
|---|---|---|
| `query` | string（必填） | 中文问句或英文关键词；空格=且，`\|`=或，`"短语"`=精确匹配 |
| `mode` | string | `all`（默认）/ `transcript` / `deepread` |
| `year_from`, `year_to` | string | 年份前缀，如 `2020` |
| `limit` | integer | 每类条数，1–30，默认 10 |

返回 `{query, parsed_concepts, transcripts[], deepreads[], note}`。每条命中含 `slug, title_zh, title_en, date, kind, paragraph, timestamp, snippet`。

示例：`{"query":"火星 殖民","mode":"all","limit":5}`、`{"query":"\"first principles\"","mode":"transcript","year_from":"2010"}`。

## get_transcript

取单期英文逐字文稿（已按语句合并为段落），带秒级时间戳。

参数：`slug`（必填）、`query`（可选，单期内筛选）、`offset`（默认 0）、`limit`（默认 40，最多 500）。

返回 `paragraphs[]`：`paragraph, timestamp, timestamp_text, text, url`。`has_more` 表示是否要继续翻页。

示例：`{"slug":"elon-musk-on-zip2-and-the-internet-1998","limit":20}`。

## get_deepread

取单期中文精读 Markdown。

参数：`slug`（必填）、`offset_chars`（默认 0）、`max_chars`（默认 24000，最多 100000）。

返回 `text, total_chars, truncated, markdown_url, note`。长文用 `offset_chars` 续读。

## list_episodes

按条件浏览 651 期视频目录。

参数：`year`, `kind`, `title_contains`, `has_transcript`, `has_deepread`, `offset`, `limit`（默认 20，最多 100）。

返回 `total, episodes[]`；`episodes[].slug` 可传给 `get_episode` / `get_transcript` / `get_deepread`。

## get_episode

取单期元数据：`title_zh, title_en, date, kind, channel, seconds, has_transcript, has_deepread, url, archive_url, transcript_paragraphs`。

参数：`slug`（必填）。

## get_quotes

检索 556 条中英双语语录。

参数：`query`, `kind`, `offset`, `limit`（默认 20，最多 100）。返回 `total, items[]`；每条含 `text_en, text_zh, date, kind, source, source_url`。

## get_predictions

检索 22 条预言/承诺追踪。

参数：`query`, `status`（`kept` / `late` / `missed` / `open` 或中文状态）, `topic`（`tesla` / `spacex` / `ia` 等）, `offset`, `limit`。

返回 `total, items[]`；每条含 `claim_zh, claim_en, said, deadline, status_zh, outcome_zh, outcome_en, source_url`。

## get_themes

列出 8 大主题的中英介绍与逐年提及热度（`freq_by_year`）。参数：`query`（可选）。

## site_info

返回数据规模、数据源模式、快照日期与各专题入口链接。不知道有哪些数据或不确定工具能力时先调它。无参数。
