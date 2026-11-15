#!/usr/bin/env bash
# 部署公开 MCP 到乔木 VPS：rsync 代码 + systemd 服务 + Nginx 反代。
# 用法：bash mcp/elon-musk/deploy.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HOST="${ELON_MCP_HOST:-qiaomu-hostinger}"
TARGET="${ELON_MCP_TARGET:-/opt/qiaomu-apps/elon-mcp}"
VHOST="${ELON_MCP_VHOST:-/www/server/panel/vhost/nginx/elon.qiaomu.ai.conf}"

echo "==> rsync $HERE -> $HOST:$TARGET"
rsync -az --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude 'deploy.sh' \
  "$HERE/" "$HOST:$TARGET/"

echo "==> install systemd service + nginx location"
ssh -o BatchMode=yes "$HOST" bash -s -- "$TARGET" "$VHOST" <<'REMOTE'
set -euo pipefail
TARGET="$1"
VHOST="$2"

cat > /etc/systemd/system/elon-mcp.service <<EOF
[Unit]
Description=Elon Musk Archive MCP (streamable HTTP)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$TARGET
Environment=ELON_SITE_URL=https://elon.qiaomu.ai
ExecStart=/usr/bin/python3 $TARGET/elon_mcp_server.py --http --host 127.0.0.1 --port 8791
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now elon-mcp
systemctl restart elon-mcp

python3 - "$VHOST" <<'PY'
import pathlib, re, sys
p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')
begin = '    # BEGIN elon-mcp (managed by mcp/elon-musk/deploy.sh)'
end = '    # END elon-mcp'
snippet = '''    # BEGIN elon-mcp (managed by mcp/elon-musk/deploy.sh)
    # 公开只读 MCP：Streamable HTTP，POST JSON-RPC 到 https://elon.qiaomu.ai/mcp
    location = /mcp {
        proxy_pass http://127.0.0.1:8791/mcp;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
        proxy_buffering off;
        access_log off;
    }
    location = /mcp/health {
        proxy_pass http://127.0.0.1:8791/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Connection "";
        access_log off;
    }
    # END elon-mcp'''
if begin in s:
    s = re.sub(re.escape(begin) + r'.*?' + re.escape(end), lambda _: snippet, s, count=1, flags=re.S)
else:
    idx = s.rfind('    location / {')
    if idx < 0:
        raise SystemExit('vhost 中找不到 location / 锚点')
    s = s[:idx] + snippet + '\n' + s[idx:]
p.write_text(s, encoding='utf-8')
PY

nginx -t
systemctl reload nginx
sleep 1
systemctl is-active elon-mcp
curl -fsS http://127.0.0.1:8791/health
REMOTE

echo "==> public check"
curl -fsS https://elon.qiaomu.ai/mcp/health
echo
echo "deploy ok: https://elon.qiaomu.ai/mcp"
