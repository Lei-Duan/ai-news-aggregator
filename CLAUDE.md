# AI News Aggregator - Project Context

## 项目概述
每日 AI 简报机器人。从7个平台抓取内容，用 Claude Haiku 生成中英双语摘要，写入 Notion。运行在 GitHub Actions，每天定时触发，无需服务器。

## 运行命令
```bash
python3 main.py --mode once      # 单次运行
python3 main.py --mode test      # 测试模式（部分数据源）
python3 main.py --mode schedule  # 启动定时任务
```

## 架构
```
main.py
config/settings.py          # 从环境变量读取配置
config/sources.yaml         # 账号、关键词、RSS 地址
src/fetchers/               # 各平台抓取器
src/processors/             # filter, summarizer, state (去重)
src/notion/client.py        # Notion 页面生成
src/notifiers/email.py      # 邮件推送（可选）
src/scheduler/daily_job.py  # 主流程编排
```

## 各渠道逻辑

| 渠道 | 获取方式 | 质量信号 |
|---|---|---|
| Twitter 精选账号 | API v2 search 用 `from:u1 OR from:u2 …`，单次调用拉所有人 | 人工选账号，不过 filter；user ID 缓存 7 天 |
| Twitter 热搜 | **已禁用**（`min_faves:` 需 Pro tier，Basic 拿不到 viral） | n/a |
| GitHub | 爬 github.com/trending?since=weekly | 本周真实新增 stars |
| Reddit | `/r/sub/hot.json`，无需 auth | comments ≥ 50 |
| Hacker News | Algolia API | ≥ 30 points（fetch 时过滤）|
| RSS | feedparser，4个官方 AI 博客 | 来源即保证，无 engagement filter |
| Tech Blogs | 直接爬取 + Anthropic sitemap 取真实日期 | 来源即保证 |
| Podcasts | RSS，72h 内新集 | 来源即保证 |

## 过滤流程
1. **Pre-filter**（AI 摘要前）：日期窗口 + AI 关键词 + 数量上限
   - Twitter 精选账号跳过关键词过滤
   - Blog/Podcast 跳过关键词过滤
2. **Engagement filter**：Reddit 用 comments≥50，其余各平台用平台自身信号
3. **Claude quality_score 不作为 hard filter** — 各平台已有自己的质量保证机制
4. **去重**：title + 内容前100字 fingerprint；跨 run 去重用 GitHub Actions Cache

## AI 摘要
- 模型：`claude-haiku-4-5-20251001`（成本低）
- 批量处理：tweet ≤5/次，github ≤10/次，article ≤6/次
- 输出：title / summary（英）/ summary_zh（中）/ key_points / category / entities
- 费用：约 $0.06/次，$1.8/月

## Notion 输出格式
- 页面顶部：抓取状态 callout + 今日速览表格
- 中文详情 → 英文详情（按分类分组）
- 每条标题格式：`[平台 · 作者/来源] 标题`

## 已知问题 / 注意事项
- Twitter API 需要 Basic 订阅（$100/月）或 pay-per-use；Free tier 返回 402
- Twitter 优化：用 `(from:u1 OR from:u2 …)` 搜索把 25 次 timeline 调用压缩到 1 次 search 调用；user ID 缓存在 `state/twitter_user_ids.json`（7 天 TTL），命中即跳过 `/users/by`。日均 API 调用 ~26 → ~1（成本 ~$0.27/天 → ~$0.01/天）
- Twitter `search_trending` 函数仍保留，但日常流程不调用 — `min_faves:` 操作符需要 Pro tier，否则返回的全是低赞结果。升级 tier 后可在 `daily_job.fetch_twitter_content` 里重新启用
- Haiku 偶发返回带 markdown 代码块的 JSON，batch 解析失败时该批次丢弃（低概率）
- Anthropic blog 用 sitemap 获取日期；OpenAI/Gemini/DeepMind 用 HTML 解析，可能因页面结构变化失效
- Reddit JSON API (`/hot.json`) 对所有非浏览器 IP 返回 403，已切换为 RSS (`/hot.rss`)；RSS 无 score/comments 数据

## 去重机制说明
- 跨日去重：已处理的 item ID 记录在 `state/seen_items.json`，7 天过期
- **同日重跑不去重**：当天 seen 的条目视为 unseen，允许同一天多次运行（如 GitHub Actions 跑完后本地再测试）
- GitHub Actions 每次运行后自动 commit state 文件回 repo

## 依赖
```
aiohttp, httpx, anthropic, notion-client, python-dotenv,
pyyaml, feedparser, apscheduler, beautifulsoup4
```
