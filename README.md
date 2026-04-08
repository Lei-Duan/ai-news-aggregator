# 🤖 AI News Aggregator

> **每天早上自动抓取 AI 圈最值得看的内容，用 Claude 总结后推送到 Notion。**  
> Runs daily on GitHub Actions — no server required, no manual work.

---

## 这是什么

一个面向 **AI 从业者 / 独立开发者** 的每日简报机器人，自动完成以下流程：

1. 从 7 个平台抓取过去 24 小时最有价值的 AI 内容
2. 用 Claude 生成中英双语摘要 + 关键点 + 类型标签
3. 把结构化简报写入你的 Notion 数据库

整个流程跑在 GitHub Actions 上，每天 09:05 PST 自动触发，**无需本地服务器，Fork 即用**。

---

## 内容来源

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

## Notion 输出示例

每天生成一个结构化 Notion 页面：

```
🤖 AI 日报 | AI Daily Briefing — 2026-04-08
生成时间: 2026-04-08 09:12  ·  共 28 条

📡 抓取状态
  ✅ Twitter/X: 12 items    ✅ GitHub: 8 items
  ✅ Reddit: 6 items         ✅ Hacker News: 5 items
  ⚠️ Podcasts: 0 items      ✅ Tech Blogs: 3 items

📊 今日速览（汇总表格）
  类别          │ 标题                        │ 来源        │ 中文摘要
  ─────────────┼─────────────────────────────┼────────────┼──────────
  🚀 基础模型迭代 │ GPT-4o mini gets smarter... │ @OpenAI    │ OpenAI 发布...
  🤖 Agent应用   │ Claude can now use tools... │ @Anthropic │ Anthropic 宣布...

📋 详细内容（按类别，中英双语）
  每条内容包含：
  🚀 基础模型迭代   🕐 2026-04-08   🔗 原文链接
  [中文摘要段落]
  [英文摘要 + 3-5 条关键要点]
  🏷 GPT-4o · OpenAI · multimodal
```

---

## 快速开始（Fork 使用）

### 第一步：Fork 本项目

点击右上角 **Fork**，在自己账号下创建副本。

### 第二步：准备 API 密钥

| 密钥 | 用途 | 是否必需 | 获取方式 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude 摘要 | **必需** | [console.anthropic.com](https://console.anthropic.com) |
| `NOTION_TOKEN` | 写入 Notion | **必需** | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | 目标数据库 ID | **必需** | 见下方说明 |
| `GH_TOKEN` | 抓取 GitHub trending | 推荐 | GitHub → Settings → Developer settings → PAT（`public_repo` 权限） |
| `TWITTER_BEARER_TOKEN` | Twitter 内容 | 可选 | [developer.twitter.com](https://developer.twitter.com)，需 Basic $100/mo |

> Twitter 不是必需的。没有 Bearer Token 时，Twitter 模块自动跳过，其他来源正常运行。

**获取 Notion Database ID：**
1. 在 Notion 新建一个数据库（需包含 `Name`（Title）、`Date`、`Tags`（Multi-select）三个属性）
2. 打开数据库页面，点击右上角 `···` → **Copy link**
3. 链接格式为 `https://notion.so/username/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=...`，其中 32 位字母数字部分即为 Database ID
4. 在数据库页面 `···` → **Add connections** → 选择你创建的 Integration

### 第三步：配置 GitHub Secrets

进入 Fork 的 repo → **Settings → Secrets and variables → Actions → New repository secret**，逐一添加：

```
ANTHROPIC_API_KEY     sk-ant-...
NOTION_TOKEN          secret_...
NOTION_DATABASE_ID    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GH_TOKEN              ghp_...
TWITTER_BEARER_TOKEN  AAAA...（可选）
```

### 第四步：启用 GitHub Actions

1. 进入 Fork 的 repo → **Actions** 标签
2. 点击 **"I understand my workflows, go ahead and enable them"**
3. 左侧选择 `Daily AI News Briefing` → 右侧 **Run workflow** 手动触发一次测试

✅ 测试成功后，之后每天 **09:05 PST（北京时间 01:05）** 自动运行。

---

## 本地运行

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

## 自定义配置

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

## 项目结构

```
ai-news-aggregator/
├── main.py                     # 入口
├── config/
│   ├── settings.py             # 从环境变量读取配置
│   └── sources.yaml            # 内容来源配置
├── src/
│   ├── fetchers/
│   │   ├── twitter.py          # Twitter API v2
│   │   ├── github.py           # GitHub trending
│   │   ├── reddit_rss.py       # Reddit RSS（免认证）
│   │   ├── hackernews.py       # Hacker News
│   │   ├── rss.py              # 通用 RSS
│   │   ├── podcast.py          # 播客 RSS
│   │   └── blog.py             # Anthropic / OpenAI 博客爬取
│   ├── processors/
│   │   ├── summarizer.py       # Claude 批量摘要
│   │   ├── filter.py           # 多维过滤
│   │   ├── classifier.py       # 内容分类
│   │   └── state.py            # 跨日去重
│   ├── notion/
│   │   └── client.py           # Notion 页面构建与写入
│   └── scheduler/
│       └── daily_job.py        # 主调度逻辑
├── state/
│   └── seen_items.json         # 去重状态（CI 自动提交）
└── .github/workflows/
    └── daily_briefing.yml      # GitHub Actions 定时任务
```

---

## 技术亮点

| 特性 | 实现方式 |
|---|---|
| **零服务器** | 完全运行在 GitHub Actions 免费额度内 |
| **跨日去重** | `state/seen_items.json` 记录已处理 ID，CI 每次运行后自动 commit 回 repo |
| **批量 AI 调用** | 多条内容合并为单次 Claude API 请求，降低 token 费用 |
| **防截断分批** | 按类型自动分批（tweet ≤5/次，article ≤6/次），合并结果，避免 JSON 截断 |
| **星速排序** | GitHub 按 stars/day 而非总 stars 排序，优先发现新兴项目 |
| **容错隔离** | 每个数据源独立 try/except，单个来源失败不影响其他来源 |

---

## 常见问题

**Twitter 内容为空？**  
Twitter API Basic 订阅需要 $100/月。没有 token 时所有其他来源正常工作。

**Notion 没有新页面？**  
检查 `NOTION_DATABASE_ID` 是否为 32 位（不含连字符），以及 Integration 是否已在该数据库里 connect。

**修改运行时间？**  
编辑 `.github/workflows/daily_briefing.yml` 中的 `cron: '5 17 * * *'`（UTC 时间）。时间转换：北京时间 = UTC+8，PST = UTC-8。

**Fork 后会用到原作者的 API 吗？**  
不会。GitHub Secrets 不随 Fork 传递，定时任务在 Fork 中默认也是禁用状态。

---

## License

MIT
