# Changelog

All notable changes to AI News Aggregator are recorded here.

---

## [Unreleased]

### Added
- macOS launchd 定时任务支持，真正的每日 9:00 PST 自动运行
- GitHub star velocity（星标增速）排序：优先展示最近快速增长的新项目
- Reddit JSON API 替换 RSS：获取真实 score/upvote_ratio 数据

### Changed
- GitHub 抓取移除 openai/anthropic/huggingface 大型组织（噪音太多），改为纯 topic 搜索
- GitHub 搜索窗口从 7 天扩展到 30 天，配合增速排序更全面
- GitHub 支持多语言（python/typescript/javascript/go/rust），不再只抓 Python 项目
- Reddit 子版块精简为高信噪比的 AI+Builder 社区，移除通用编程类版块
- Reddit 改为抓取 `/top.json?t=day`（真实今日热榜）而非 `/hot.rss`

### Fixed
- Reddit RSS 分数默认为 10（无真实数据）导致过滤失效
- GitHub 大型知名 repo（如 claude-code 本身）占据榜单的问题

---

## [0.1.0] - 2026-03-01

### Added
- 初始项目架构：asyncio + aiohttp 异步架构
- Twitter/X 内容抓取（Bearer Token）
- GitHub trending repos 抓取（topic 搜索）
- Reddit RSS 内容抓取（无需 API key）
- Hacker News 热帖抓取
- RSS 订阅源抓取（AI 博客、Build in Public 博客）
- Claude API 驱动的内容摘要与分类
- Notion 每日简报自动创建
- APScheduler 定时任务（进程内调度）
- token 使用优化：批量处理、关键词预过滤
- Build in Public 社区焦点配置
