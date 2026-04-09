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
| Twitter 精选账号 | API v2 timeline | 人工选账号，不过 filter |
| Twitter 热搜 | API v2 search，query 内含 `min_faves:5000` | ≥5000 likes 服务端过滤 |
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
- Twitter trending search 的 `min_faves:` operator 需要 Basic 以上权限，pay-per-use 待验证
- Haiku 偶发返回带 markdown 代码块的 JSON，batch 解析失败时该批次丢弃（低概率）
- Podcast fetcher 有 `transcript` 属性缺失的 bug，待修（无新集时不影响运行）
- Anthropic blog 用 sitemap 获取日期；OpenAI/Gemini/DeepMind 用 HTML 解析，可能因页面结构变化失效

## 依赖
```
aiohttp, httpx, anthropic, notion-client, python-dotenv,
pyyaml, feedparser, apscheduler, beautifulsoup4
```
