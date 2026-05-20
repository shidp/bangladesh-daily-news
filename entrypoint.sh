#!/usr/bin/env bash
# entrypoint.sh — GitHub Action 执行入口
set -euo pipefail

# 从 action.yml inputs 传递的环境变量映射到 Python 脚本
export AGENTMAIL_API_KEY="${AGENTMAIL_API_KEY:-}"
export AGENTMAIL_EMAIL="${AGENTMAIL_EMAIL:-shidp@agentmail.to}"
export RECIPIENT_EMAIL="${RECIPIENT_EMAIL:-shidp304@gmail.com}"
export NEWS_COUNT="${NEWS_COUNT:-12}"
export SUBJECT_PREFIX="${SUBJECT_PREFIX:-🇧🇩 孟加拉每日新闻摘要}"
export TOP_SOURCE="${TOP_SOURCE:-government,politics,election,sheikh hasina,bangladesh bank,imf,world bank,adb}"
export EXCLUDE_KEYWORDS="${EXCLUDE_KEYWORDS:-sports,cricket,football,entertainment,movie,celebrity}"

# 检查必要参数
if [[ -z "$AGENTMAIL_API_KEY" ]]; then
  echo "❌ Missing required input: agentmail-api-key is required."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/daily_news.py"
