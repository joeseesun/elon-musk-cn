# elon-musk-archive

> 你问"马斯克关于 AI 风险到底说过什么"，AI 往往凭印象回答。这个 Skill 让 AI 直接检索 588 份带时间戳的英文逐字文稿和 586 篇中文精读，给出**原话、年份、视频链接和精确秒数**。

[![Stars](https://img.shields.io/github/stars/joeseesun/elon-musk-archive?style=social)](https://github.com/joeseesun/elon-musk-archive/stargazers)
[![Forks](https://img.shields.io/github/forks/joeseesun/elon-musk-archive)](https://github.com/joeseesun/elon-musk-archive/forks)
[![Issues](https://img.shields.io/github/issues/joeseesun/elon-musk-archive)](https://github.com/joeseesun/elon-musk-archive/issues)
[![Last commit](https://img.shields.io/github/last-commit/joeseesun/elon-musk-archive)](https://github.com/joeseesun/elon-musk-archive/commits)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[中文](#中文) | [English](#english)**

---

## 中文

### 装上之后，你能这样问

- "马斯克说'第一性原理'的原话是什么？在哪一期、第几分钟？"
- "他 2023 年以后对 AI 风险的看法有什么变化？"
- "找出'火星殖民'相关的中文精读，给出视频链接。"
- "他说过的预言里，哪些已兑现、哪些迟到兑现？"

AI 会调用公开 MCP 端点，返回**段落级命中 + 时间戳 + 深链**，而不是泛泛而谈。

### 真实输出样例

```text
问题：马斯克怎么看"火星"

命中：Tesla Cybertruck Unveil（2019）
段落 14 · 11:23
"...we're going to be using the same alloy in the **Starship** rocket
and in the Cybertruck..."
出处：https://elon.qiaomu.ai/ep/tesla-cybertruck-unveil/?p=14&t=683
```

### 数据覆盖范围

| 数据 | 数量 | 说明 |
|---|---|---|
| 公开视频 | 651 | 1998 年至今，访谈 / 发布会 / 股东大会 |
| 英文逐字文稿 | 588 | 逐段合并、带时间戳，可跳到视频对应秒数 |
| 中文精读 | 586 | AI 深度改写，不是机器翻译 |
| 双语语录 | 556 | 中英对照 + 出处 |
| 预言追踪 | 22 | 已兑现 / 迟到 / 未兑现 / 待验证 + 核实结果 |
| 主题 | 8 | AI、火星、出生率、言论自由等 |

### 一键安装

```bash
npx skills add joeseesun/elon-musk-archive
```

然后配置 MCP（公开只读，无需密钥）：

```json
{
  "mcpServers": {
    "elon-musk": {
      "type": "http",
      "url": "https://elon.qiaomu.ai/mcp"
    }
  }
}
```

在 WorkBuddy 里保存后到连接器管理点「信任」并启用。只支持 stdio 的客户端可用 `npx -y mcp-remote@latest https://elon.qiaomu.ai/mcp` 桥接。

### 前置条件

- [ ] 已安装 [Node.js](https://nodejs.org/)（含 `npx`），运行 `npx --version` 验证
- [ ] 已登录 GitHub CLI（仅从源码安装时需要），运行 `gh auth status` 验证
- [ ] 客户端支持 MCP Streamable HTTP，或愿意用 `mcp-remote` 桥接
- [ ] 可访问 `https://elon.qiaomu.ai`（国内网络通常可直连；MCP 端点走同一域名）

### 它怎么工作

Skill 本身是一份检索工作流：先调 `site_info` 看数据范围，再用 `search` 做全文中英检索，对需要逐字引用的结论用 `get_transcript` 核对英文原话与时间码，必要时用 `get_deepread` 读中文背景，最后用 `get_quotes` / `get_predictions` / `get_themes` 交叉验证并附上出处。

共 9 个只读工具：`search`、`get_transcript`、`get_deepread`、`list_episodes`、`get_episode`、`get_quotes`、`get_predictions`、`get_themes`、`site_info`。参数详见 `references/tools.md`。

### 风险与限制

- 英文逐字文稿来自 [silicon-valley.tech](https://silicon-valley.tech/) 公开档案，本站保留原始出处链接。
- 中文精读是 AI 改写，**不能当逐字翻译引用**；原话以英文文稿为准。
- MCP 服务为公开只读端点，不接受写入；如服务暂时不可用，Skill 会提示而不是编造答案。

### 常见问题

| 问题 | 解决 |
|---|---|
| 客户端提示"没有工具" | 确认已配置 `https://elon.qiaomu.ai/mcp`，完成 `initialize` 后重启客户端 |
| 中文检索没结果 | 换成英文关键词，或传 `mode="transcript"` 只查英文文稿 |
| 报 404 / 502 | 检查 URL 结尾不要加斜杠；先访问 `https://elon.qiaomu.ai/mcp/health` |
| 想离线用 | clone [elon-musk-cn](https://github.com/joeseesun/elon-musk-cn)，设 `ELON_SITE_DIR=<repo>/site` 用 stdio 模式启动 MCP |

### 致谢

数据来自 [silicon-valley.tech · Elon Musk Archive](https://silicon-valley.tech/)；站点与 Skill 由[向阳乔木](https://qiaomu.ai/)维护。中文精读为 AI 改写，非官方翻译。

---

<!-- qiaomu-profile:start -->
## 关于向阳乔木

向阳乔木（乔向阳 / Joe）是一位实践型 AI 产品与内容创作者，长期把前沿 AI 变化转译成可复用的工作流、产品判断、AI 编程实践、AI 搜索实践和 GEO/AI 营销方法。

- 个人网站: https://qiaomu.ai
- 博客: https://blog.qiaomu.ai
- X: https://x.com/vista8
- GitHub: https://github.com/joeseesun/
- 微信公众号: 向阳乔木推荐看

### 支持与关注

| 打赏支持 | 微信公众号 |
|---|---|
| <img src="assets/qiaomu-profile/qiaomu_reward_qr.png" alt="向阳乔木打赏二维码" width="180" /> | <img src="assets/qiaomu-profile/qiaomu_wechat_public_account_qr.jpg" alt="向阳乔木推荐看公众号二维码" width="180" /> |
| 感谢支持乔木持续分享 AI 实践 | 扫码关注「向阳乔木推荐看」 |

<!-- qiaomu-profile:end -->

## English

> Ask "what exactly did Elon Musk say about AI risk?" and most AIs guess. This Skill makes the AI search 588 timestamped English transcripts plus 586 Chinese deep-reads, returning the **exact quote, year, video link, and second-level timestamp**.

### Try asking

- "What were Musk's exact words on first principles, and in which episode?"
- "How did his view on AI risk change after 2023?"
- "Find Chinese deep-reads about Mars colonization with video links."
- "Which of his predictions came true, and which were late?"

### Install

```bash
npx skills add joeseesun/elon-musk-archive
```

Then add the public read-only MCP endpoint to your client:

```json
{
  "mcpServers": {
    "elon-musk": {
      "type": "http",
      "url": "https://elon.qiaomu.ai/mcp"
    }
  }
}
```

### Contents

651 videos, 588 English transcripts with timestamps, 586 AI-written Chinese deep-reads, 556 bilingual quotes, 22 tracked predictions, 8 themes. Nine read-only MCP tools cover full-text search, per-episode transcripts/deep-reads, episode catalog, quotes, predictions, themes, and site info.

### Caveats

English transcripts come from the public [silicon-valley.tech archive](https://silicon-valley.tech/). Chinese deep-reads are AI paraphrases, **not verbatim translations** — verify original wording against the English transcript. This is an unofficial fan project.

Licensed under [MIT](LICENSE).
