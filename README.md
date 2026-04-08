# 🤖 AI News Aggregator

> **每天早上自动抓取 AI 圈最值得看的内容，用 Claude 总结后推送到 Notion。**  
> Automatically curates the day's most valuable AI content and delivers a structured briefing to Notion — powered by Claude, runs on GitHub Actions, no server needed.

---

[中文](#中文) · [English](#english)

---

## 中文

### 这是什么

一个面向 **AI 从业者 / 独立开发者** 的每日简报机器人，自动完成以下流程：

1. 从 7 个平台抓取过去 24 小时最有价值的 AI 内容
2. 用 Claude 生成中英双语摘要 + 关键点 + 类型标签
3. 把结构化简报写入你的 Notion 数据库

整个流程跑在 GitHub Actions 上，每天 09:05 PST 自动触发，**无需本地服务器，Fork 即用**。

---

### 内容来源

| 来源 | 抓取方式 | 筛选逻辑 |
|---|---|---|
| **Twitter / X** | API v2（需 Basic 订阅） | 25 个精选 AI 账号 + 全平台 ≥2000 likes 热推 |
| **GitHub** | REST API | 按 star 增速（stars/day）排序，优先发现快速崛起新项目 |
| **Reddit** | RSS（免认证） | r/LocalLLaMA、r/MachineLearning 等 14 个高质量社区 |
| **Hacker News** | 官方 Algolia API | AI 相关，≥30 points 过滤 |
| **RSS 订阅** | feedparser | OpenAI、Anthropic、Google、HuggingFace 等官方博客 |
| **技术博客** | 直接爬取 | Anthropic + OpenAI 官网最新文章 |
| **AI 播客** | RSS | Lex Fridman、Latent Space、No Priors 等 6 个，72h 内新集 |

Twitter 跟踪账号（25 个）：@karpathy · @AndrewYNg · @ylecun · @swyx · @ggerganov · @fchollet · @goodside · @levelsio · @marc\_lou\_ · @AnthropicAI · @LangChainAI · @cursor\_ai 等

---

### Notion 输出示例

每天生成一个结构化 Notion 页面：

```
🤖 AI 日报 | AI Daily Briefing — 2026-04-08
生成时间: 2026-04-08 09:12  ·  共 28 条

📡 抓取状态
  ✅ Twitter/X: 12 items    ✅ GitHub: 8 items
  ✅ Reddit: 6 items         ✅ Hacker News: 5 items
  ⚠️ Podcasts: 0 items      ✅ Tech Blogs: 3 items

📊 今日速览（汇总表格）
  类别           │ 标题                        │ 来源        │ 中文摘要
  ──────────────┼─────────────────────────────┼────────────┼──────────
  🚀 基础模型迭代 │ GPT-4o mini gets smarter... │ @OpenAI    │ OpenAI 发布...
  🤖 Agent应用   │ Claude can now use tools... │ @Anthropic │ Anthropic 宣布...

📋 详细内容（按类别，中英双语）
  🚀 基础模型迭代   🕐 2026-04-08   🔗 原文链接
  [中文摘要段落]
  [英文摘要 + 3-5 条关键要点]
  🏷 GPT-4o · OpenAI · multimodal
```

---

### 技术亮点

| 特性 | 实现方式 |
|---|---|
| **零服务器** | 完全运行在 GitHub Actions 免费额度内 |
| **Fork 即用，历史互不干扰** | 去重状态存储在 GitHub Actions Cache 中，每个 Fork 拥有完全独立的 Cache，不会继承原作者的已读历史，也不会相互污染 |
| **跨日去重** | 每次 run 后将已处理 ID 保存到 Actions Cache，下次 run 自动读取，避免重复推送同一内容 |
| **批量 AI 调用** | 多条内容合并为单次 Claude API 请求，大幅降低 token 费用 |
| **防截断分批** | 按类型自动分批（tweet ≤5/次，article ≤6/次），合并结果，避免 JSON 截断 |
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

> Twitter 不是必需的。没有 Bearer Token 时，Twitter 模块自动跳过，其他来源正常运行。

**获取 Notion Database ID：**
1. 在 Notion 新建一个数据库（需包含 `Name`（Title）、`Date`、`Tags`（Multi-select）三个属性）
2. 打开数据库页面，点击右上角 `···` → **Copy link**
3. 链接格式为 `https://notion.so/username/xxxxxxxx...?v=...`，其中 32 位字母数字部分即为 Database ID
4. 在数据库 `···` → **Add connections** → 选择你创建的 Integration

#### 第三步：配置 GitHub Secrets

进入 Fork 的 repo → **Settings → Secrets and variables → Actions → New repository secret**，逐一添加：

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
3. 左侧选择 `Daily AI News Briefing` → 右侧 **Run workflow** 手动触发一次测试

✅ 测试成功后，之后每天 **09:05 PST（北京时间 01:05）** 自动运行。

---

### 本地运行

```bash
# 安装依赖（Python 3.9+）
pip install -r requirements.txt

# 配置密钥
cp .env.example .env
# 编辑 .env，填入你的 API 密钥

# 运行完整简报
python main.py --mode once
```

---

### 自定义配置

所有来源配置在 [`config/sources.yaml`](config/sources.yaml)，直接修改即可：

```yaml
# 添加 / 删除 Twitter 关注账号
twitter:
  ai_accounts:
    - "@karpathy"
    - "@your_account"

# 调整 GitHub 关注 topic
github:
  topics:
    - "llm"
    - "ai-agent"

# 添加任意 RSS 源
rss_feeds:
  - "https://your-blog.com/feed.xml"
```

---

### 常见问题

**Twitter 内容为空？**  
Twitter API Basic 订阅需要 $100/月。没有 token 时所有其他来源正常工作。

**Notion 没有新页面？**  
检查 `NOTION_DATABASE_ID` 是否为 32 位（不含连字符），以及 Integration 是否已在该数据库里 connect。

**修改运行时间？**  
编辑 `.github/workflows/daily_briefing.yml` 中的 `cron: '5 17 * * *'`（UTC 时间）。北京时间 = UTC+8，PST = UTC-8。

**Fork 后会用到原作者的 API 或历史记录吗？**  
不会。GitHub Secrets 不随 Fork 传递；去重历史存在各自的 Actions Cache 里，完全独立。

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
| **Twitter / X** | API v2 (Basic plan required) | 25 curated AI accounts + platform-wide tweets with ≥2000 likes |
| **GitHub** | REST API | Sorted by star velocity (stars/day) to surface fast-rising new projects |
| **Reddit** | RSS (no auth) | 14 high-signal communities: r/LocalLLaMA, r/MachineLearning, etc. |
| **Hacker News** | Official Algolia API | AI-related posts, ≥30 points threshold |
| **RSS Feeds** | feedparser | Official blogs: OpenAI, Anthropic, Google, HuggingFace |
| **Tech Blogs** | Direct scraping | Latest posts from Anthropic + OpenAI websites |
| **AI Podcasts** | RSS | 6 podcasts incl. Lex Fridman, Latent Space, No Priors — episodes within 72h |

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
| `TWITTER_BEARER_TOKEN` | Twitter content | Optional | [developer.twitter.com](https://developer.twitter.com), requires Basic plan $100/mo |

> Twitter is optional. Without a Bearer Token, the Twitter module is silently skipped and all other sources run normally.

**Getting your Notion Database ID:**
1. Create a new database in Notion (needs `Name` (Title), `Date`, and `Tags` (Multi-select) properties)
2. Open the database, click `···` → **Copy link**
3. The URL looks like `https://notion.so/username/xxxxxxxx...?v=...` — the 32-character alphanumeric segment is your Database ID
4. In the database `···` → **Add connections** → select your Integration

#### Step 3: Add GitHub Secrets

Go to your forked repo → **Settings → Secrets and variables → Actions → New repository secret**, and add each one:

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
3. Select `Daily AI News Briefing` on the left → click **Run workflow** to trigger a test run

✅ After a successful test, it will run automatically every day at **09:05 PST**.

---

### Run Locally

```bash
# Install dependencies (Python 3.9+)
pip install -r requirements.txt

# Set up credentials
cp .env.example .env
# Edit .env and fill in your API keys

# Run a full briefing
python main.py --mode once
```

---

### Customization

All source configuration lives in [`config/sources.yaml`](config/sources.yaml):

```yaml
# Add or remove Twitter accounts to follow
twitter:
  ai_accounts:
    - "@karpathy"
    - "@your_account"

# Adjust GitHub topics to watch
github:
  topics:
    - "llm"
    - "ai-agent"

# Add any RSS feed
rss_feeds:
  - "https://your-blog.com/feed.xml"
```

---

### FAQ

**Twitter content is empty?**  
Twitter API Basic plan costs $100/month. Without a token, all other sources still work normally.

**No new Notion page?**  
Check that `NOTION_DATABASE_ID` is 32 characters (no hyphens), and that the Integration has been connected to the database.

**Change the run schedule?**  
Edit `cron: '5 17 * * *'` in `.github/workflows/daily_briefing.yml` (UTC time). Beijing = UTC+8, PST = UTC-8.

**Will a fork use the original author's API keys or reading history?**  
No. GitHub Secrets are not inherited by forks. Deduplication history lives in each repo's own Actions Cache — completely isolated.

---

### Project Structure

```
ai-news-aggregator/
├── main.py                     # Entry point
├── config/
│   ├── settings.py             # Reads config from environment variables
│   └── sources.yaml            # Source configuration (accounts, keywords, feeds)
├── src/
│   ├── fetchers/
│   │   ├── twitter.py          # Twitter API v2
│   │   ├── github.py           # GitHub trending
│   │   ├── reddit_rss.py       # Reddit RSS (no auth)
│   │   ├── hackernews.py       # Hacker News
│   │   ├── rss.py              # Generic RSS parser
│   │   ├── podcast.py          # Podcast RSS
│   │   └── blog.py             # Anthropic / OpenAI blog scraper
│   ├── processors/
│   │   ├── summarizer.py       # Claude batch summarization
│   │   ├── filter.py           # Multi-dimensional filtering
│   │   ├── classifier.py       # Content classification
│   │   └── state.py            # Cross-run deduplication
│   ├── notion/
│   │   └── client.py           # Notion page builder and writer
│   └── scheduler/
│       └── daily_job.py        # Main orchestration logic
└── .github/workflows/
    └── daily_briefing.yml      # GitHub Actions scheduled job
```

---

## License

MIT
