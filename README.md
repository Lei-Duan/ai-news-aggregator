# 🤖 AI News Aggregator

> Automatically curates the day's most valuable AI content and delivers a structured bilingual briefing to Notion — powered by Claude, runs on GitHub Actions, no server needed.

**Want to receive the daily briefing without setting this up yourself?** Leave a comment on [Issue #2 — Add Recipient](https://github.com/Lei-Duan/ai-news-aggregator/issues/2) and I'll add you directly.

---

[English](#english) · [中文](#中文)

---

## English

### What is this

A daily briefing bot for **AI practitioners and indie developers** that automatically:

1. Fetches the most valuable AI content from 7 platforms in the past 24 hours
2. Uses Claude to generate bilingual (Chinese + English) summaries, key points, and category labels
3. Writes a structured briefing into your Notion database

Runs entirely on GitHub Actions, triggered daily at 09:05 PST — **no server required, just fork and go**.

---

### Content Sources

| Source | Method | Filter Logic |
|---|---|---|
| **Twitter / X** | API v2 (Basic plan, $100/mo) | 25 curated AI/builder accounts (24h, no keyword filter) + platform-wide search ≥5000 likes across 4 AI keyword/hashtag queries |
| **GitHub** | Scrape github.com/trending | Weekly trending page across 6 languages; ranked by stars gained this week; excludes big-org repos; AI keyword filter |
| **Reddit** | RSS (no auth) | 14 subreddits incl. r/LocalLLaMA, r/MachineLearning, r/buildinpublic; comments ≥ 50 |
| **Hacker News** | Algolia API | AI-related posts; ≥ 30 points at fetch time |
| **RSS Feeds** | feedparser | 8 official AI blogs (OpenAI, Anthropic, Google, HuggingFace, Distill) + 8 indie-builder blogs; no engagement filter |
| **Tech Blogs** | Direct scraping | Anthropic, OpenAI, Google Gemini, Google DeepMind; 72h window; real publication date extracted (undated posts flagged) |
| **AI Podcasts** | RSS | Lex Fridman, TWIML, Cognitive Revolution, Latent Space, No Priors, FLI; episodes within 72h |

Tracked Twitter accounts (25): @karpathy · @AndrewYNg · @ylecun · @swyx · @ggerganov · @fchollet · @goodside · @levelsio · @marc\_lou\_ · @AnthropicAI · @LangChainAI · @cursor\_ai and more

---

### Key Features

| Feature | How it works |
|---|---|
| **Zero infrastructure** | Runs entirely within GitHub Actions free tier |
| **Fork-isolated dedup history** | Seen-item state is stored in GitHub Actions Cache — each fork gets its own independent cache, with no inherited history from the original repo and no cross-fork contamination |
| **Cross-run deduplication** | Processed item IDs are saved to Actions Cache after each run and restored on the next, preventing the same content from being pushed twice |
| **Batched AI calls** | Multiple items combined into a single Claude API request, significantly reducing token cost |
| **Truncation-safe batching** | Auto-splits by type (tweet ≤5/call, article ≤6/call) and merges results to prevent JSON truncation |
| **Star velocity ranking** | GitHub sorts by stars/day rather than total stars, surfacing emerging projects early |
| **Per-source fault isolation** | Each data source has its own try/except — one failure doesn't block the others |

---

### Notion Output

Every day a structured Notion page is generated:

```
🤖 AI Daily Briefing — 2026-04-08  ·  28 items

📡 Fetch Status
  ✅ Twitter/X: 12    ✅ GitHub: 8    ✅ Reddit: 6
  ✅ Hacker News: 5   ✅ Tech Blogs: 3   ⚠️ Podcasts: 0

📊 Today at a Glance  (summary table: category · title · source · summary)

📋 Detailed Content (Chinese)
  [all items in Chinese, grouped by category]

📋 Detailed Content (English)
  [all items in English, grouped by category]
```

Each item shows: `🚀 Model Release   🕐 2026-04-08   🔗 Source link`

---

### Quick Start (Fork & Use)

#### Step 1: Fork this repo

Click **Fork** in the top right to create your own copy.

#### Step 2: Get your API keys

| Secret | Purpose | Required | How to get |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude summarization | **Required** | [console.anthropic.com](https://console.anthropic.com) |
| `NOTION_TOKEN` | Write to Notion | **Required** | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | Target database | **Required** | See below |
| `GH_TOKEN` | Fetch GitHub trending | Recommended | GitHub Settings → Developer settings → PAT (`public_repo` scope) |
| `TWITTER_BEARER_TOKEN` | Twitter content | Optional | [developer.twitter.com](https://developer.twitter.com), Basic plan $100/mo |

> Twitter is optional. Without a token, all other sources still run normally.

**Getting your Notion Database ID:**
1. Create a new database in Notion with `Name` (Title), `Date`, and `Tags` (Multi-select) properties
2. Open the database → `···` → **Copy link**
3. The URL looks like `https://notion.so/username/xxxxxxxx...?v=...` — the 32-character segment is your Database ID
4. In the database `···` → **Add connections** → select your Integration

#### Step 3: Add GitHub Secrets

Go to your forked repo → **Settings → Secrets and variables → Actions → New repository secret**:

```
ANTHROPIC_API_KEY     sk-ant-...
NOTION_TOKEN          secret_...
NOTION_DATABASE_ID    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GH_TOKEN              ghp_...
TWITTER_BEARER_TOKEN  AAAA...  (optional)
```

#### Step 4: Enable GitHub Actions

1. Go to your forked repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. Select `Daily AI News Briefing` → click **Run workflow** to test

✅ After a successful test, it runs automatically every day at **09:05 PST**.

---

### Email Notifications (Optional)

After each briefing, an HTML digest email is sent with fetch status, top 15 items, and a Notion link.

1. Enable 2FA on Gmail → [Google Account Security](https://myaccount.google.com/security) → App passwords → generate 16-char password
2. Add to GitHub Secrets:

```
GMAIL_USER          your_gmail@gmail.com
GMAIL_APP_PASSWORD  xxxx xxxx xxxx xxxx
EMAIL_RECIPIENTS    you@example.com,other@example.com
```

No-op if not configured. Supports multiple recipients (comma-separated).

---

### Run Locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python main.py --mode once
```

---

### Customization

Edit [`config/sources.yaml`](config/sources.yaml) to add accounts, topics, or feeds:

```yaml
twitter:
  ai_accounts:
    - "@karpathy"
    - "@your_account"

github:
  topics:
    - "llm"
    - "ai-agent"

rss_feeds:
  - "https://your-blog.com/feed.xml"
```

---

### FAQ

**Twitter content is empty?**
Twitter API Basic plan costs $100/month. All other sources work without it.

**No new Notion page?**
Check that `NOTION_DATABASE_ID` is 32 characters (no hyphens) and the Integration is connected to the database.

**Change the run schedule?**
Edit `cron: '5 17 * * *'` in `.github/workflows/daily_briefing.yml` (UTC). Beijing = UTC+8, PST = UTC-8.

**Will a fork use the original author's API keys or reading history?**
No. Secrets are not inherited. Dedup history lives in each repo's own Actions Cache — completely isolated.

---

### Project Structure

```
ai-news-aggregator/
├── main.py
├── config/
│   ├── settings.py             # Reads config from environment variables
│   └── sources.yaml            # Accounts, keywords, RSS feeds
├── src/
│   ├── fetchers/               # twitter, github, reddit_rss, hackernews, rss, podcast, blog
│   ├── processors/             # summarizer (Claude), filter, classifier, state (dedup)
│   ├── notion/                 # Page builder and Notion API client
│   ├── notifiers/              # Email digest
│   └── scheduler/              # Main orchestration (daily_job.py)
└── .github/workflows/
    └── daily_briefing.yml
```

---

## 中文

### 这是什么

一个面向 **AI 从业者 / 独立开发者** 的每日简报机器人，自动完成以下流程：

1. 从 7 个平台抓取过去 24 小时最有价值的 AI 内容
2. 用 Claude 生成中英双语摘要 + 关键点 + 类型标签
3. 把结构化简报写入你的 Notion 数据库

整个流程跑在 GitHub Actions 上，每天 09:05 PST 自动触发，**无需本地服务器，Fork 即用**。

**觉得配置麻烦？** 在 [Issue #2 — Add Recipient](https://github.com/Lei-Duan/ai-news-aggregator/issues/2) 留言，我直接把你加为收件人。

---

### 内容来源

| 来源 | 抓取方式 | 筛选逻辑 |
|---|---|---|
| **Twitter / X** | API v2（需 Basic 订阅，$100/月） | 25 个精选 AI/builder 账号（24h，不过关键词）+ 全平台 ≥5000 likes，4 组 AI 关键词/hashtag query |
| **GitHub** | 爬取 github.com/trending | 按周 trending 页面，覆盖 6 种语言；按本周新增 star 数排序；排除大厂 org；AI 关键词过滤 |
| **Reddit** | RSS（免认证） | r/LocalLLaMA、r/MachineLearning、r/buildinpublic 等 14 个社区；评论数 ≥ 50 |
| **Hacker News** | 官方 Algolia API | AI 相关帖子；抓取时已过滤 ≥ 30 points |
| **RSS 订阅** | feedparser | 8 个官方 AI 博客（OpenAI / Anthropic / Google / HuggingFace / Distill）+ 8 个 indie builder 博客；不过 engagement |
| **技术博客** | 直接爬取 | Anthropic、OpenAI、Google Gemini、Google DeepMind；72h 内；提取真实发布日期（无法确定时标注） |
| **AI 播客** | RSS | Lex Fridman、TWIML、Cognitive Revolution、Latent Space、No Priors、FLI；72h 内新集 |

---

### 技术亮点

| 特性 | 实现方式 |
|---|---|
| **零服务器** | 完全运行在 GitHub Actions 免费额度内 |
| **Fork 即用，历史互不干扰** | 去重状态存储在 GitHub Actions Cache 中，每个 Fork 拥有完全独立的 Cache |
| **跨日去重** | 每次 run 后将已处理 ID 保存到 Actions Cache，下次 run 自动读取 |
| **批量 AI 调用** | 多条内容合并为单次 Claude API 请求，大幅降低 token 费用 |
| **防截断分批** | 按类型自动分批（tweet ≤5/次，article ≤6/次），合并结果 |
| **星速排序** | GitHub 按 stars/day 而非总 stars 排序，优先发现快速崛起的新项目 |
| **容错隔离** | 每个数据源独立 try/except，单个来源失败不影响其他来源 |

---

### 快速开始（Fork 使用）

#### 第一步：Fork 本项目

点击右上角 **Fork**，在自己账号下创建副本。

#### 第二步：准备 API 密钥

| 密钥 | 用途 | 是否必需 | 获取方式 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude 摘要 | **必需** | [console.anthropic.com](https://console.anthropic.com) |
| `NOTION_TOKEN` | 写入 Notion | **必需** | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | 目标数据库 ID | **必需** | 见下方说明 |
| `GH_TOKEN` | 抓取 GitHub trending | 推荐 | GitHub Settings → Developer settings → PAT（`public_repo` 权限） |
| `TWITTER_BEARER_TOKEN` | Twitter 内容 | 可选 | [developer.twitter.com](https://developer.twitter.com)，需 Basic $100/mo |

**获取 Notion Database ID：**
1. 在 Notion 新建数据库（需包含 `Name`、`Date`、`Tags` 三个属性）
2. 打开数据库 → `···` → **Copy link**
3. 链接中 32 位字母数字部分即为 Database ID
4. 数据库 `···` → **Add connections** → 选择你创建的 Integration

#### 第三步：配置 GitHub Secrets

进入 Fork 的 repo → **Settings → Secrets and variables → Actions → New repository secret**：

```
ANTHROPIC_API_KEY     sk-ant-...
NOTION_TOKEN          secret_...
NOTION_DATABASE_ID    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GH_TOKEN              ghp_...
TWITTER_BEARER_TOKEN  AAAA...（可选）
```

#### 第四步：启用 GitHub Actions

1. 进入 Fork 的 repo → **Actions** 标签
2. 点击 **"I understand my workflows, go ahead and enable them"**
3. 选择 `Daily AI News Briefing` → **Run workflow** 手动触发测试

✅ 测试成功后，之后每天 **09:05 PST（北京时间 01:05）** 自动运行。

---

### 邮件推送（可选）

每次简报生成后自动发送 HTML 邮件，包含抓取状态、今日精选和 Notion 链接。

1. Gmail 开启两步验证 → [Google 账号安全设置](https://myaccount.google.com/security) → 应用专用密码 → 生成 16 位密码
2. 在 GitHub Secrets 添加：

```
GMAIL_USER          your_gmail@gmail.com
GMAIL_APP_PASSWORD  xxxx xxxx xxxx xxxx
EMAIL_RECIPIENTS    you@example.com,other@example.com
```

不配置时静默跳过，支持多个收件人（逗号分隔）。

---

### 本地运行

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入你的 API 密钥
python main.py --mode once
```

---

### 常见问题

**Twitter 内容为空？**
Twitter API Basic 订阅需要 $100/月，没有 token 时其他来源正常工作。

**Notion 没有新页面？**
检查 `NOTION_DATABASE_ID` 是否为 32 位（不含连字符），以及 Integration 是否已在该数据库里 connect。

**修改运行时间？**
编辑 `.github/workflows/daily_briefing.yml` 中的 `cron: '5 17 * * *'`（UTC 时间）。

**Fork 后会用到原作者的 API 或历史记录吗？**
不会。Secrets 不随 Fork 传递，去重历史在各自的 Actions Cache 里完全独立。

---

## License

MIT
