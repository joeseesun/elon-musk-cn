# 安装与连接

## 1) 安装 Skill

已开源到 [GitHub](https://github.com/joeseesun/elon-musk-archive)，一行安装：

```bash
npx skills add joeseesun/elon-musk-archive
```

或下载并解压到用户级 Skill 目录（重启 WorkBuddy 后生效）：

```bash
curl -L -o /tmp/elon-musk-archive.zip https://elon.qiaomu.ai/mcp/elon-musk-archive.zip
mkdir -p ~/.workbuddy/skills
unzip -o /tmp/elon-musk-archive.zip -d ~/.workbuddy/skills/
# 结果：~/.workbuddy/skills/elon-musk-archive/SKILL.md
```

团队协作时改放项目目录 `<repo>/.workbuddy/skills/elon-musk-archive/`。

## 2) 连接 MCP

编辑 `~/.workbuddy/mcp.json`，在 `mcpServers` 下加入：

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

若客户端只支持 stdio 启动，可用通用桥接：

```json
{
  "mcpServers": {
    "elon-musk": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://elon.qiaomu.ai/mcp"]
    }
  }
}
```

保存后，在 WorkBuddy 左下角连接器管理里对新服务器点「信任 / Trust」并启用。端点为公开只读，目前不需要密钥。

## 3) 验证

```bash
python3 ~/.workbuddy/skills/elon-musk-archive/scripts/mcp_http_check.py
```

正常会输出 `connected: elon-musk-archive 1.0.0` 和 9 个工具名。

## 4) 常见问题

- **404 / 502**：确认 URL 末尾没有斜杠，必须是 `/mcp`；可先访问 `https://elon.qiaomu.ai/healthz`。
- **客户端报“无工具”**：确认已完成 `initialize`，再调用 `tools/list`；部分客户端需要重启。
- **中文查不到**：改用英文关键词或 `search(mode="transcript")`；内置词表覆盖常用概念，其余走站点翻译反代。
- **离线使用**：可 clone 仓库，设置 `ELON_SITE_DIR=<repo>/site` 后以 stdio 方式启动 `mcp/elon-musk/elon_mcp_server.py`，全部索引读本地文件。
