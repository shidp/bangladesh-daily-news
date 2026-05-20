#!/usr/bin/env python3
"""
Daily Star Bangladesh News Digest - GitHub Actions 版本
每天抓取新闻 → 获取正文 → Extractive Summarization → 发送邮件
通过 AgentMail API 发送，环境变量 AGENTMAIL_API_KEY, RECIPIENT_EMAIL
"""

import urllib.request
import re
import sys
import os
import json
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from collections import Counter
from html import unescape

# ============================================================
# 环境变量（由 action.yml / GitHub Action inputs 传入）
# ============================================================
AGENTMAIL_API_KEY = os.environ.get("AGENTMAIL_API_KEY", "")
AGENTMAIL_EMAIL = os.environ.get("AGENTMAIL_EMAIL", "shidp@agentmail.to")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "shidp304@gmail.com")
NEWS_URL = "https://www.thedailystar.net/todays-news"

# 可选配置
NEWS_COUNT = int(os.environ.get("NEWS_COUNT", "12"))
SUBJECT_PREFIX = os.environ.get("SUBJECT_PREFIX", "🇧🇩 孟加拉每日新闻摘要")

# 优先关键词
_TOP_SOURCE = os.environ.get(
    "TOP_SOURCE",
    "government,govt,minister,cabinet,parliament,election,yunus,hasina,bnp,awami league,"
    "political,reform,war,conflict,attack,military,sanction,adb,imf,world bank,budget,"
    "economic,dollar,taka,india,china,us,trump,un,diplomacy,teesta,rohingya,treaty,bilateral,"
    "fuel,oil,diesel,gas,petrol,energy,price,subsidy,corona,covid,virus,epidemic,pandemic,"
    "outbreak,disease,dengue,cholera,health,hospital,vaccine"
)
PRIORITY_KEYWORDS = [kw.strip() for kw in _TOP_SOURCE.split(",") if kw.strip()]

# 排除词（体育/娱乐）
_EXcludeRaw = os.environ.get(
    "EXCLUDE_KEYWORDS",
    "football,cricket,match,player,score,goal,premier league,movie,film,actor,actress,"
    "director,trailer,netflix,song,album,concert,fashion week,beauty,recipe,horoscope"
)
EXCLUDE_KEYWORDS = [kw.strip() for kw in _EXcludeRaw.split(",") if kw.strip()]


class ArticleParser(HTMLParser):
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
    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self._skip_tags = {"script", "style", "nav", "header", "footer", "aside", "figure"}
        self._in_skip = False
        self._in_p = False
        self._current = ""

    def _is_copyright(self, text):
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
            self._in_skip = True
        if tag == "p" and not self._in_skip:
            self._in_p = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._in_skip = False
        if tag == "p" and self._in_p:
            text = self._current.strip()
            if len(text) > 50 and not self._is_copyright(text):
                self.paragraphs.append(text)
            self._current = ""
            self._in_p = False

    def handle_data(self, data):
        if self._in_p and not self._in_skip:
            self._current += data


def fetch_html(url, timeout=20):
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
    html = fetch_html(url)
    if not html:
        return ""
    parser = ArticleBodyParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return unescape(" ".join(parser.paragraphs[:8]))


def extract_sentences(text):
    text = re.sub(r'\s+', ' ', text)
    sents = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sents if len(s.strip()) > 30]


def score_sentence(sent, all_words):
    words = re.findall(r'\b[a-z]{4,}\b', sent.lower())
    if not words:
        return 0
    score = sum(1 for w in words if w in all_words) / max(len(words), 1)
    if re.search(r'\d+', sent):
        score *= 1.2
    if len(sent) > 250:
        score *= 0.8
    return score


def summarize_text(text, num_sentences=2):
    sentences = extract_sentences(text)
    if not sentences:
        return None
    if len(sentences) <= num_sentences:
        return " ".join(sentences[:num_sentences])

    words = []
    for s in sentences:
        words.extend(re.findall(r'\b[a-z]{4,}\b', s.lower()))
    all_words = set(w for w, c in Counter(words).items() if c >= 2)

    scored = [(s, score_sentence(s, all_words)) for s in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)

    top_sents = set(s for s, _ in scored[:num_sentences * 3])
    result = []
    for s in sentences:
        if s in top_sents and len(result) < num_sentences:
            result.append(s)
    return " ".join(result)


def get_article_summary(art):
    try:
        body = get_article_body(art["url"])
        if len(body) > 200:
            summary = summarize_text(body, num_sentences=2)
            if summary and len(summary) > 50:
                return summary
    except Exception:
        pass
    return art["title"]


def rank_articles(articles):
    def score(art):
        t = art["title"].lower()
        s = sum(5 for kw in PRIORITY_KEYWORDS if kw in t)
        if re.search(r'\$\d+|\d+\s*(billion|million|trillion)', t):
            s += 3
        return s
    return sorted(articles, key=score, reverse=True)


def build_email_html(top_articles, fetch_time):
    bd_time = fetch_time.strftime("%Y年%m月%d日")
    colors = ["#006a4e", "#1a73e8", "#d93025", "#f9ab00", "#5f6368",
              "#006a4e", "#1a73e8", "#d93025", "#f9ab00", "#5f6368",
              "#006a4e", "#1a73e8"]

    items_html = ""
    for i, art in enumerate(top_articles, 1):
        c = colors[i % len(colors)]
        badge = f'<span style="background:{c};color:#fff;width:28px;height:28px;border-radius:50%;display:inline-block;text-align:center;line-height:28px;font-size:13px;font-weight:700;margin-right:12px;">{i}</span>'
        items_html += f"""
        <div style="margin-bottom:24px;padding:20px;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.06);border-left:4px solid {c};">
          <div style="display:flex;align-items:flex-start;margin-bottom:10px;">
            {badge}
            <h3 style="margin:0;color:#1a1a1a;font-size:16px;font-weight:600;line-height:1.5;flex:1;">{art['title']}</h3>
          </div>
          <p style="margin:0 0 12px;color:#555;font-size:14px;line-height:1.7;padding-left:40px;">{art['summary']}</p>
          <div style="padding-left:40px;">
            <a href="{art['url']}" style="display:inline-block;padding:6px 14px;background:#f0f4ff;color:#1a73e8;text-decoration:none;border-radius:20px;font-size:12px;font-weight:500;">→ 阅读原文</a>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:'Segoe UI',-apple-system,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#eef2f7">
    <tr><td align="center" style="padding:30px 15px;">
      <table width="620" cellpadding="0" cellspacing="0" bgcolor="#ffffff" style="border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,0.1);overflow:hidden;">
        <tr>
          <td style="background:linear-gradient(135deg,#006a4e,#004d38);padding:32px 36px;">
            <h1 style="margin:0;color:#fff;font-size:26px;font-weight:700;">🇧🇩 孟加拉每日新闻摘要 Top 12 条</h1>
            <p style="margin:10px 0 0;color:rgba(255,255,255,0.85);font-size:15px;">{bd_time} · 政府 · 政治 · 国际局势</p>
          </td>
        </tr>
        <tr>
          <td style="background:#f0f4ff;padding:10px 36px;border-bottom:1px solid #e0e0e0;">
            <span style="color:#1a73e8;font-size:13px;font-weight:600;">📰 Top {len(top_articles)} 条 · 每条附 AI 摘要 + 原文链接</span>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 28px;">{items_html}</td>
        </tr>
        <tr>
          <td style="padding:20px 28px;background:#f8f9fa;border-top:1px solid #eee;">
            <p style="margin:0;color:#999;font-size:12px;line-height:1.8;">
              由 GitHub Actions 自动发送 · 每日 08:00 BDT · 发件：{AGENTMAIL_EMAIL} · <a href="{NEWS_URL}" style="color:#1a73e8;">查看全部新闻 →</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def send_email(subject, html_body):
    """通过 AgentMail API 发送邮件"""
    if not AGENTMAIL_API_KEY:
        print("[ERROR] AGENTMAIL_API_KEY 未设置")
        return False

    text_body = re.sub(r'<[^>]+>', ' ', html_body)
    text_body = re.sub(r'\s+', ' ', text_body).strip()

    payload = {
        "to": RECIPIENT_EMAIL,
        "subject": subject,
        "html": html_body,
        "text": text_body[:2000],
    }

    url = f"https://api.agentmail.to/v0/inboxes/{AGENTMAIL_EMAIL}/messages/send"
    headers = {
        "Authorization": f"Bearer {AGENTMAIL_API_KEY}",
        "Content-Type": "application/json",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"[OK] 邮件已发送至 {RECIPIENT_EMAIL} (AgentMail)")
            return True
    except urllib.error.HTTPError as e:
        print(f"[ERROR] AgentMail 发送失败: HTTP {e.code}")
        try:
            err_body = e.read().decode("utf-8")
            print(f"[ERROR] 详情: {err_body}")
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"[ERROR] 发送失败: {e}")
        return False


def main():
    if not AGENTMAIL_API_KEY:
        print("[ERROR] 请设置 AGENTMAIL_API_KEY 环境变量")
        sys.exit(1)

    bd_tz = timezone(timedelta(hours=6))
    now = datetime.now(bd_tz)
    today_str = now.strftime("%Y-%m-%d")

    print(f"[{now.strftime('%Y-%m-%d %H:%M')} BDT] 开始抓取...")

    html = fetch_html(NEWS_URL)
    if not html:
        print("[ERROR] 列表页抓取失败"); sys.exit(1)

    parser = ArticleParser()
    parser.feed(html)
    articles = deduplicate(parser.articles)
    print(f"[INFO] 共 {len(articles)} 篇，过滤中...")

    filtered = [a for a in articles if not should_exclude(a["title"])]
    ranked = rank_articles(filtered)
    top_articles = ranked[:NEWS_COUNT]
    print(f"[INFO] Top {NEWS_COUNT} 已排序，开始获取摘要...")

    for i, art in enumerate(top_articles, 1):
        print(f"  [{i}/{NEWS_COUNT}] {art['title'][:60]}...")
        art["summary"] = get_article_summary(art)

    subject = f"{SUBJECT_PREFIX} | {today_str}"
    html_body = build_email_html(top_articles, now)
    send_email(subject, html_body)


if __name__ == "__main__":
    main()
