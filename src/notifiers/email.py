"""
Daily briefing email notifier.
Sends an HTML digest via Gmail SMTP after each successful run.

Required env vars:
  GMAIL_USER         - your Gmail address
  GMAIL_APP_PASSWORD - 16-char App Password (Gmail → Security → App passwords)
  EMAIL_RECIPIENTS   - comma-separated recipient addresses
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_daily_briefing(
    sender: str,
    password: str,
    recipients: List[str],
    date: datetime,
    notion_page_url: str,
    sections: Dict[str, List[Dict]],
    fetch_stats: Dict[str, dict],
) -> bool:
    """Send the daily briefing email. Returns True on success."""
    if not sender or not password or not recipients:
        logger.info("Email: not configured, skipping")
        return False

    try:
        subject = f"🤖 AI 日报 {date.strftime('%Y-%m-%d')} · {sum(len(v) for v in sections.values())} 条"
        html = _build_html(date, notion_page_url, sections, fetch_stats)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender, password)
            smtp.sendmail(sender, recipients, msg.as_string())

        logger.info(f"Email sent to {recipients}")
        return True

    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


# ── HTML builder ─────────────────────────────────────────────────────────────

CATEGORY_ZH = {
    "agent-project": "🤖 Agent应用",
    "model-release": "🚀 基础模型迭代",
    "research-paper": "📄 学术研究",
    "industry-news": "🏢 行业动态",
    "tutorial": "🛠 教程资源",
    "agent-framework": "🤖 Agent框架",
    "llm-tool": "⚙️ LLM工具",
    "model-implementation": "🔬 模型实现",
    "research-breakthrough": "🔬 研究突破",
    "product-launch": "🆕 产品发布",
    "technical-tutorial": "🛠 技术教程",
    "industry-analysis": "📊 行业分析",
    "policy-update": "📋 政策动态",
    "podcast": "🎙 播客",
    "blog": "📝 官方博客",
    "other": "📰 其他",
}

SOURCE_ICON = {"ok": "✅", "empty": "⚠️", "error": "❌"}


def _build_html(date, notion_url, sections, fetch_stats) -> str:
    total = sum(len(v) for v in sections.values())
    date_str = date.strftime("%Y-%m-%d")

    # ── fetch status rows
    status_rows = ""
    for source, stat in fetch_stats.items():
        icon = SOURCE_ICON.get(stat["status"], "❓")
        err = f" — {stat['error'][:60]}" if stat.get("error") else ""
        status_rows += f"<tr><td>{icon} {source}</td><td>{stat['count']} items{err}</td></tr>"

    # ── content rows (top 15 items across all sections)
    all_items = []
    for section, items in sections.items():
        for item in items:
            all_items.append((section, item))
    all_items = all_items[:15]

    content_rows = ""
    for section, item in all_items:
        cat = item.get("category", "other")
        cat_label = CATEGORY_ZH.get(cat, cat)
        title = item.get("title", "")
        url = item.get("url", "")
        summary_zh = item.get("summary_zh", item.get("summary", ""))
        source = item.get("source", "")
        title_html = f'<a href="{url}" style="color:#1a73e8;text-decoration:none;">{title}</a>' if url else title
        content_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#555;white-space:nowrap;">{cat_label}</td>
          <td style="padding:8px 12px;">{title_html}<br>
              <span style="color:#888;font-size:12px;">{source}</span></td>
          <td style="padding:8px 12px;color:#333;font-size:13px;">{summary_zh[:80]}</td>
        </tr>"""

    notion_btn = ""
    if notion_url:
        notion_btn = f"""
        <p style="text-align:center;margin:28px 0;">
          <a href="{notion_url}" style="background:#1a73e8;color:#fff;padding:12px 28px;
             border-radius:6px;text-decoration:none;font-weight:bold;">
            📖 在 Notion 查看完整日报
          </a>
        </p>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f5f5f5;margin:0;padding:20px;">
  <div style="max-width:720px;margin:0 auto;background:#fff;
              border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">

    <!-- header -->
    <div style="background:#1a1a2e;padding:28px 32px;">
      <h1 style="color:#fff;margin:0;font-size:22px;">🤖 AI 日报 | {date_str}</h1>
      <p style="color:#aaa;margin:6px 0 0;font-size:14px;">共 {total} 条内容</p>
    </div>

    <div style="padding:24px 32px;">

      <!-- fetch status -->
      <h2 style="font-size:15px;color:#333;margin:0 0 10px;">📡 抓取状态</h2>
      <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px;">
        {status_rows}
      </table>

      <!-- content summary -->
      <h2 style="font-size:15px;color:#333;margin:0 0 10px;">📋 今日精选（前 {len(all_items)} 条）</h2>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tr style="background:#f8f8f8;font-weight:bold;">
          <th style="padding:8px 12px;text-align:left;">类型</th>
          <th style="padding:8px 12px;text-align:left;">标题</th>
          <th style="padding:8px 12px;text-align:left;">摘要</th>
        </tr>
        {content_rows}
      </table>

      {notion_btn}

    </div>

    <!-- footer -->
    <div style="background:#f8f8f8;padding:16px 32px;font-size:12px;color:#999;text-align:center;">
      AI News Aggregator · 自动生成，每天 09:05 PST
    </div>
  </div>
</body>
</html>"""
