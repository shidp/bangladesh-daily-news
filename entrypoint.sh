#!/usr/bin/env bash
# entrypoint.sh — GitHub Action 入口脚本
set -euo pipefail

# 解析 action.yml 中定义的环境变量，注入到 Python 脚本
# GitHub Action inputs 通过 INPUT_* 环境变量传入
export GMAIL_USER="${GMAIL_USER:-}"
export GMAIL_APP_PASSWORD="${GMAIL_APP_PASSWORD:-}"
export RECIPIENT_EMAIL="${RECIPIENT_EMAIL:-${GMAIL_USER}}"
export NEWS_COUNT="${NEWS_COUNT:-12}"
export SUBJECT_PREFIX="${SUBJECT_PREFIX:-🇧🇩 孟加拉今日新闻}"
export TOP_SOURCE="${TOP_SOURCE:-government,politics,election,sheikh hasina,bangladesh bank,imf,world bank,adb}"
export EXCLUDE_KEYWORDS="${EXCLUDE_KEYWORDS:-sports,cricket,football,entertainment,movie,celebrity}"

# 验证必填参数
if [[ -z "$GMAIL_USER" || -z "$GMAIL_APP_PASSWORD" ]]; then
  echo "❌ Missing required inputs: gmail-user and gmail-app-password are required."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/daily_news.py"
