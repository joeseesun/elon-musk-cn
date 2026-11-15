# 马斯克全访谈 MCP Server

把 `elon.qiaomu.ai` 的 651 期视频、588 份英文逐字文稿、586 篇中文精读、语录、预言与主题，暴露给任意 MCP 客户端。纯 Python 标准库，无第三方依赖。

## 公开服务（推荐）

- MCP 端点：`https://elon.qiaomu.ai/mcp`（Streamable HTTP，POST JSON-RPC 2.0）
- 健康检查：`https://elon.qiaomu.ai/mcp/health`
- Skill 下载：`https://elon.qiaomu.ai/mcp/elon-musk-archive.zip`
- 安装说明：`https://elon.qiaomu.ai/mcp/`

客户端配置（`~/.workbuddy/mcp.json`）：

```json
{
  "mcpServers": {
    "elon-musk": { "type": "http", "url": "https://elon.qiaomu.ai/mcp" }
  }
}
```

只支持 stdio 的客户端可用 `npx -y mcp-remote@latest https://elon.qiaomu.ai/mcp` 桥接。配置后需在连接器管理里点「信任」。

## 本地 / 离线模式

```bash
python3 mcp/elon-musk/elon_mcp_server.py                  # stdio
ELON_SITE_DIR=/abs/path/elon-website/site python3 mcp/elon-musk/elon_mcp_server.py
python3 mcp/elon-musk/mcp_client.py list
python3 mcp/elon-musk/mcp_client.py call search '{"query":"火星","limit":3}'
```

- `ELON_SITE_DIR`：指向构建好的 `site/`，索引、文稿、精读全读本地文件。
- 不设置时走线上静态索引，专题 JSON 用 `data/` 内随包快照。
- `ELON_SITE_URL`：覆盖站点地址；`ELON_NO_TRANSLATE=1`：关闭在线翻译。
- `ELON_MCP_TOKEN`：可选 Bearer token；留空即公开只读。

## 工具

`search`（全文，中英文/短语/年份）、`get_transcript`（段落+时间戳）、`get_deepread`（中文精读 Markdown）、`list_episodes`、`get_episode`、`get_quotes`、`get_predictions`、`get_themes`、`site_info`。详细参数见 `skills/elon-musk-archive/references/tools.md`。

## 部署到乔木 VPS

```bash
python3 mcp/elon-musk/prepare_data.py     # 刷新 data/ 快照
bash mcp/elon-musk/deploy.sh              # rsync + systemd(elon-mcp) + Nginx /mcp
```

默认 SSH 别名 `qiaomu-hostinger`、目标 `/opt/qiaomu-apps/elon-mcp`、端口 `8791`，可用 `ELON_MCP_HOST` / `ELON_MCP_TARGET` 覆盖。Nginx vhost 为 `/www/server/panel/vhost/nginx/elon.qiaomu.ai.conf`，脚本幂等插入 `# BEGIN elon-mcp` 标记块。

Skill 包更新后执行：

```bash
python3 .../skill-creator/scripts/package_skill.py skills/elon-musk-archive dist
rsync -az site/mcp/ qiaomu-hostinger:/www/wwwroot/elon.qiaomu.ai/mcp/
```
