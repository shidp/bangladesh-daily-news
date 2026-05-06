# Bangladesh Daily News Digest Action

> 每天自动抓取 The Daily Star 孟加拉新闻，生成摘要邮件，支持 Gmail SMTP 发送。

[![GitHub Actions](https://github.com/shidp/bangladesh-daily-news-action/workflows/Daily%20News/badge.svg)](https://github.com/shidp/bangladesh-daily-news-action/actions)

---

## 一句话引用

```yaml
# 在任意 GitHub 仓库的 .github/workflows/news.yml 中：
- uses: shidp/bangladesh-daily-news-action@v1
  with:
    gmail-user: ${{ secrets.GMAIL_USER }}
    gmail-app-password: ${{ secrets.GMAIL_APP_PASSWORD }}
    recipient-email: ${{ secrets.RECIPIENT_EMAIL }}
```

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 新闻来源 | The Daily Star (thedailystar.net) |
| 摘要生成 | TF-IDF 风格 Extractive Summarization（每篇2句） |
| 智能排序 | 优先级：政府政治 > 国际冲突 > 金融援助 > 印孟关系 > 能源疫情 |
| 过滤机制 | 自动排除体育、娱乐内容 |
| 邮件格式 | 美化 HTML，多端适配 |
| 云端运行 | GitHub Actions，每日 BDT 08:00 自动执行 |

---

## 配置说明

### Inputs（必填）

| 参数 | 说明 | 示例 |
|------|------|------|
| `gmail-user` | Gmail 发件地址 | `user@gmail.com` |
| `gmail-app-password` | Gmail App Password（16位，非登录密码） | `abcd efgh ijkl mnop` |

### Inputs（可选）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `recipient-email` | 同 `gmail-user` | 收件邮箱 |
| `news-count` | `12` | 选取新闻条数 |
| `subject-prefix` | `🇧🇩 孟加拉今日新闻` | 邮件主题前缀 |
| `top-source` | 政府/政治/选举/亚投行… | 优先关键词（逗号分隔） |
| `exclude-keywords` | 体育/娱乐/电影… | 排除关键词（逗号分隔） |

---

## 快速上手

### 第一步：创建 GitHub Secrets

在你的仓库 → **Settings → Secrets and variables → Actions** 中添加：

```
GMAIL_USER = your@gmail.com
GMAIL_APP_PASSWORD = xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL = target@example.com
```

> Gmail App Password 在 [Google 账户安全](https://myaccount.google.com/security) → **两步验证** → **应用密码** 中生成。

### 第二步：创建 workflow 文件

`.github/workflows/news.yml`:

```yaml
name: Bangladesh Daily News

on:
  schedule:
    # 每天 UTC 02:00 = BDT 08:00
    - cron: '0 2 * * *'
  workflow_dispatch:  # 手动触发

jobs:
  news:
    runs-on: ubuntu-latest
    steps:
      - uses: shidp/bangladesh-daily-news-action@v1
        with:
          gmail-user: ${{ secrets.GMAIL_USER }}
          gmail-app-password: ${{ secrets.GMAIL_APP_PASSWORD }}
          recipient-email: ${{ secrets.RECIPIENT_EMAIL }}
          news-count: 12
          subject-prefix: "🇧🇩 孟加拉今日新闻"
```

### 第三步：发布 Action（可选）

如果想让别人也能用，发布一个 Release：

```bash
# 在你自己的仓库中
git tag v1.0.0
git push origin v1.0.0
```

之后别人就可以用 `@v1` 或 `@v1.0.0` 引用你的 Action。

---

## 自定义关键词

```yaml
- uses: shidp/bangladesh-daily-news-action@v1
  with:
    # 更关注金融和援助新闻
    top-source: "imf,world bank,adb,loan,funding,budget,export,remittance"
    # 排除更多类别
    exclude-keywords: "sports,cricket,movie,festival,obituary"
```

---

## 本地测试

```bash
# 克隆后
cd daily_news
pip install requests beautifulsoup4 lxml

export GMAIL_USER="your@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export RECIPIENT_EMAIL="target@example.com"

python daily_news.py
```

---

## 依赖

- Python 3.12+
- `requests`
- `beautifulsoup4`
- `lxml`

---

## License

MIT — 自由使用、修改、分发。
