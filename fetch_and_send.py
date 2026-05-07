#!/usr/bin/env python3
"""
Daily Star Bangladesh News Digest - Top 12 摘要版
每天抓取新闻 → 获取正文 → Extractive Summarization → 发送邮件
"""

import urllib.request
import smtplib
import ssl
import re
import sys
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from collections import Counter
from html import unescape

# ============================================================
# 配置区
# ============================================================
GMAIL_ADDRESS = "shidp304@gmail.com"
GMAIL_APP_PASSWORD = "pvob zeff apte ngdy"
RECIPIENT_EMAIL = "shidp304@gmail.com"
NEWS_URL = "https://www.thedailystar.net/todays-news"
TOP_N = 12  # 每天发 Top 12 条

# 排除词（体育/娱乐）
EXCLUDE_KEYWORDS = [
    "football", "cricket", "match", "player", "score", "goal", "premier league",
    "movie", "film", "actor", "actress", "director", "trailer", "netflix",
    "song", "album", "concert", "fashion week", "beauty", "recipe", "horoscope",
    "real madrid", "barcelona", "liverpool", "manchester", "arsenal",
]
# ============================================================


class ArticleParser(HTMLParser):
    """解析文章链接"""
    def __init__(self):
        super().__init__()
        self.articles = []
        self._capture = False
        self._title = ""
        self._url = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a" and "href" in attrs_dict:
            href = attrs_dict["href"]
            if href and re.match(r'^/\w[\w/-]+-\d{6,}$', href):
                self._url = "https://www.thedailystar.net" + href
                self._capture = True
                self._title = ""

    def handle_endtag(self, tag):
        if tag == "a" and self._capture:
            if self._title.strip():
                self.articles.append({"title": self._title.strip(), "url": self._url})
            self._capture = False
            self._title = ""
            self._url = ""

    def handle_data(self, data):
        if self._capture:
            self._title += data


class ArticleBodyParser(HTMLParser):
    """从文章页面提取正文段落"""
    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self._in_body = False
        self._in_p = False
        self._skip_tags = {"script", "style", "nav", "header", "footer", "aside", "figure"}
        self._current_skip = False
        self._depth = 0

    def _is_copyright(self, text):
        """判断是否为版权/免责声明等无关文字"""
        t = text.lower()
        copyright_keywords = [
            "copyright", "all rights reserved", "reprinted", "without permission",
            "the daily star", "syed mohammed ali", "editorial policy",
            "disclaimer", "terms of use", "privacy policy",
            "follow us on", "subscribe to", "newsletter", "social media",
            "facebook", "twitter", "instagram", "linkedin",
            "republication", "syndication", "fair use",
        ]
        return any(kw in t for kw in copyright_keywords)

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._current_skip = True
        if tag == "p":
            self._in_p = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._current_skip = False
        if tag == "p":
            self._in_p = False

    def handle_data(self, data):
        if self._current_skip:
            return
        text = data.strip()
        if self._in_p and len(text) > 50:
            if self._is_copyright(text):
                return
            self.paragraphs.append(text)


def fetch_html(url, timeout=20):
    """抓取网页"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] 抓取失败 {url}: {e}")
        return None


def deduplicate(articles):
    seen = set()
    result = []
    for a in articles:
        key = a["url"]
        if key not in seen:
            seen.add(key)
            result.append(a)
    return result


def should_exclude(title):
    title_lower = title.lower()
    return any(kw in title_lower for kw in EXCLUDE_KEYWORDS)


def get_article_body(url):
    """获取文章正文"""
    html = fetch_html(url)
    if not html:
        return ""
    parser = ArticleBodyParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return " ".join(parser.paragraphs[:8])  # 取前8段


def extract_sentences(text):
    """分句（简单的split）"""
    text = re.sub(r'\s+', ' ', text)
    sents = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sents if len(s.strip()) > 30]


def score_sentence(sent, all_words):
    """TF-IDF风格句子打分"""
    words = re.findall(r'\b[a-z]{4,}\b', sent.lower())
    if not words:
        return 0
    score = sum(1 for w in words if w in all_words) / len(words)
    # 偏好包含数字的句子（往往信息量更大）
    if re.search(r'\d+', sent):
        score *= 1.2
    # 惩罚过长句子
    if len(sent) > 250:
        score *= 0.8
    return score


def summarize_text(text, num_sentences=2):
    """Extractive summarization: 从正文提取最重要的句子"""
    sentences = extract_sentences(text)
    if not sentences:
        return None
    if len(sentences) <= num_sentences:
        return " ".join(sentences[:num_sentences])

    # 构建词频
    words = []
    for s in sentences:
        words.extend(re.findall(r'\b[a-z]{4,}\b', s.lower()))
    word_freq = Counter(words)
    max_freq = max(word_freq.values()) if word_freq else 1
    # 归一化
    all_words = set(w for w, c in word_freq.items() if c >= 2)

    # 打分排序
    scored = [(s, score_sentence(s, all_words)) for s in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)

    # 取 top n，保留原文顺序
    top_sents = set(s for s, _ in scored[:num_sentences * 3])
    result = []
    for s in sentences:
        if s in top_sents and len(result) < num_sentences:
            result.append(s)
    return " ".join(result)


def generate_fallback_summary(title, url):
    """无法抓取正文时，从标题生成摘要"""
    title_clean = re.sub(r'\s+', ' ', title).strip()
    title_clean = re.sub(r'^[A-Z][a-z]+\s+\w+\s*:?\s*', '', title_clean)
    
    # 常见模式重写
    patterns = [
        (r'^([A-Z][a-z]+)\s+([A-Z][a-z]+)\s+([A-Z][a-z]+)\s+(.*)$', r'\4'),
        (r'^([A-Z][a-z]+)\s+([A-Z][a-z]+)\s+(.*)$', r'\3'),
    ]
    summary = title_clean
    for pattern, repl in patterns:
        summary = re.sub(pattern, repl, summary)
        if summary != title_clean:
            break
    
    if len(summary) < 10:
        summary = title_clean
    
    # 添加一句话解释
    if any(kw in title.lower() for kw in ["india", "bangladesh", "us", "china", "adb", "imf"]):
        summary = summary.strip()
    else:
        summary = summary.strip()
    
    return summary


def get_article_summary(art):
    """获取文章摘要，优先抓正文，失败则用标题生成"""
    try:
        body = get_article_body(art["url"])
        if len(body) > 200:
            summary = summarize_text(body, num_sentences=2)
            if summary and len(summary) > 50:
                return summary
    except Exception:
        pass
    return generate_fallback_summary(art["title"], art["url"])


def rank_articles(articles):
    """对文章按重要性排序"""
    priority_keywords = [
        "government", "govt", "minister", "cabinet", "parliament", "election",
        "yunus", "hasina", "bnp", "awami league", "political", "reform",
        "war", "conflict", "attack", "military", "sanction",
        "adb", "imf", "world bank", "budget", "economic", "dollar", "taka",
        "india", "china", "us", "trump", "un", "diplomacy",
        "teesta", "rohingya", "treaty", "bilateral",
        # 燃油 & 疫情
        "fuel", "oil", "diesel", "gas", "petrol", "energy", "price", " subsidy",
        "corona", "covid", "virus", "epidemic", "pandemic", "outbreak", "disease",
        "dengue", "cholera", "health", "hospital", "vaccine",
    ]
    
    def score(art):
        t = art["title"].lower()
        s = sum(5 for kw in priority_keywords if kw in t)
        # 包含具体数字的优先（金额、日期等）
        if re.search(r'\$\d+|\d+\s*(billion|million|trillion)', t):
            s += 3
        return s
    
    return sorted(articles, key=score, reverse=True)


def build_email_html(top_articles, fetch_time):
    """构建 Top 10 HTML 邮件"""
    bd_time = fetch_time.strftime("%Y年%m月%d日")
    
    items_html = ""
    for i, art in enumerate(top_articles, 1):
        rank_color = ["#006a4e", "#1a73e8", "#d93025", "#f9ab00", "#5f6368"][(i-1) % 5]
        rank_badge = f'<span style="background:{rank_color}; color:#fff; width:28px; height:28px; border-radius:50%; display:inline-block; text-align:center; line-height:28px; font-size:14px; font-weight:700; margin-right:12px;">{i}</span>'
        
        items_html += f"""
        <div style="margin-bottom:24px; padding:20px; background:#fff; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,0.06); border-left:4px solid {rank_color};">
          <div style="display:flex; align-items:flex-start; margin-bottom:10px;">
            {rank_badge}
            <h3 style="margin:0; color:#1a1a1a; font-size:16px; font-weight:600; line-height:1.5; flex:1;">
              {art['title']}
            </h3>
          </div>
          <p style="margin:0 0 12px; color:#555; font-size:14px; line-height:1.7; padding-left:40px;">
            {art['summary']}
          </p>
          <div style="padding-left:40px;">
            <a href="{art['url']}" style="display:inline-block; padding:6px 14px; background:#f0f4ff; color:#1a73e8; text-decoration:none; border-radius:20px; font-size:12px; font-weight:500;">
              → 阅读原文
            </a>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#eef2f7; font-family: 'Segoe UI', -apple-system, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#eef2f7">
    <tr><td align="center" style="padding:30px 15px;">
      <table width="620" cellpadding="0" cellspacing="0" bgcolor="#ffffff" style="border-radius:12px; box-shadow:0 4px 16px rgba(0,0,0,0.1); overflow:hidden;">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#006a4e,#004d38); padding:32px 36px;">
            <h1 style="margin:0; color:#fff; font-size:26px; font-weight:700;">
              🇧🇩 孟加拉每日 Top 10 新闻
            </h1>
            <p style="margin:10px 0 0; color:rgba(255,255,255,0.85); font-size:15px;">
              {bd_time} · 政府 · 政治 · 国际局势
            </p>
            <p style="margin:6px 0 0; color:rgba(255,255,255,0.6); font-size:12px;">
              来源：The Daily Star · AI 摘要提取
            </p>
          </td>
        </tr>
        <!-- Divider -->
        <tr>
          <td style="background:#f0f4ff; padding:10px 36px; border-bottom:1px solid #e0e0e0;">
            <span style="color:#1a73e8; font-size:13px; font-weight:600;">
              📰 Top {len(top_articles)} 条 · 每条附 AI 摘要 + 原文链接
            </span>
          </td>
        </tr>
        <!-- Articles -->
        <tr>
          <td style="padding:24px 28px;">
            {items_html}
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="padding:20px 28px; background:#f8f9fa; border-top:1px solid #eee;">
            <p style="margin:0; color:#999; font-size:12px; line-height:1.8;">
              由 WorkBuddy 自动生成 · 每日 08:00 BDT · 
              <a href="{NEWS_URL}" style="color:#1a73e8;">查看 The Daily Star 全部新闻 →</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return html


def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())
        print(f"[OK] 邮件已发送至 {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        print(f"[ERROR] 发送失败: {e}")
        return False


def main():
    bd_tz = timezone(timedelta(hours=6))
    now = datetime.now(bd_tz)
    today_str = now.strftime("%Y-%m-%d")

    print(f"[INFO] {now.strftime('%Y-%m-%d %H:%M')} BDT - 开始抓取...")

    # 1. 抓取列表页
    html = fetch_html(NEWS_URL)
    if not html:
        print("[ERROR] 列表页抓取失败"); sys.exit(1)

    # 2. 解析文章列表
    parser = ArticleParser()
    parser.feed(html)
    articles = deduplicate(parser.articles)
    print(f"[INFO] 共 {len(articles)} 篇，过滤中...")

    # 3. 过滤 + 排序
    filtered = [a for a in articles if not should_exclude(a["title"])]
    ranked = rank_articles(filtered)
    top_articles = ranked[:TOP_N]
    print(f"[INFO] Top {TOP_N} 已排序，开始获取摘要...")

    # 4. 逐条获取摘要
    for i, art in enumerate(top_articles, 1):
        print(f"  [{i}/{TOP_N}] {art['title'][:60]}...")
        summary = get_article_summary(art)
        art["summary"] = summary

    # 5. 构建并发送
    subject = f"🇧🇩 孟加拉每日 Top 12 新闻 | {today_str}"
    html_body = build_email_html(top_articles, now)
    send_email(subject, html_body)

    # 保存预览
    preview_path = f"/Users/shidp/WorkBuddy/20260424013415/daily_news/preview_top10_{today_str}.html"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html_body)
    print(f"[INFO] 预览已保存: {preview_path}")


if __name__ == "__main__":
    main()
