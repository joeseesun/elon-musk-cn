#!/usr/bin/env bash
# 部署到乔木 VPS（Nginx 静态）：构建 + rsync 增量同步。
# 前置：本机 ssh 别名 qiaomu-hostinger（= myvps），服务器 /www/wwwroot/elon.qiaomu.ai/ 已建站。
set -euo pipefail
cd "$(dirname "$0")/.."

python3 tools/build.py
rsync -az --delete --exclude '.well-known' site/ qiaomu-hostinger:/www/wwwroot/elon.qiaomu.ai/
curl -sI -L https://elon.qiaomu.ai/ | head -1
echo "deploy ok: https://elon.qiaomu.ai"
