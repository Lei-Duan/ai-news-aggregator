# Changelog

All notable changes to AI News Aggregator are recorded here.

---

## [0.3.0] - 2026-04-07

### Added
- **播客抓取** (`src/fetchers/podcast.py`)：6 个 AI 播客 RSS（Lex Fridman、TWIML、Cognitive Revolution、Latent Space、No Priors、FLI），抓取最近 72 小时内新集，用 RSS description 供 Claude 摘要
- **官方博客爬虫** (`src/fetchers/blog.py`)：抓取 Anthropic + OpenAI 技术博客，优先提取 Next.js `__NEXT_DATA__` JSON，失败降级为 HTML regex，获取文章全文
- **去重机制** (`src/processors/state.py` + `state/seen_items.json`)：记录已处理 item ID，跨日去重，7 天自动过期清理；GitHub Actions 每次运行后自动 commit state 文件回 repo
- **Twitter trending 搜索**：`search_trending()` 用 3 条搜索 query 捞取全平台 AI 高热推文，门槛 ≥2000 likes，不局限于关注账号

### Changed
- **Twitter 重写**：批量解析用户 ID（1 次 API 调用），用 `note_tweet.text` 获取 280 字以上长推文，排除转发/回复，每人最多 3 条，遇 403 只警告不崩溃
- Twitter 每日抓取 = 关注账号推文 + trending 搜索，合并去重后按 likes 排序
- `daily_job.py` 整合所有新 fetcher，run 开始时 load state，发布成功后 save state
- GitHub Actions workflow 加 `permissions: contents: write` + state commit 步骤
- 移除 pod2txt 播客转录依赖（RSS description 已够用）

## [0.2.0] - 2026-04-07

### Added
- macOS launchd 定时任务支持（`scripts/setup_schedule.sh`）
- GitHub star velocity（星标增速）排序：优先展示最近快速增长的新项目
- GitHub 多语言支持（Python/TypeScript/JavaScript/Go/Rust）
- `fetch_recently_starred()`：专门捕获最近 14 天内破 200 星的病毒式新项目
- Reddit JSON API 替换 RSS：获取真实 score/upvote_ratio/num_comments

### Changed
- GitHub 移除 openai/anthropic/huggingface 大型组织，改为纯 topic 搜索
- GitHub 搜索窗口从 7 天扩展到 30 天
- Reddit 子版块从 28 个精简到 14 个高信噪比社区
- Reddit 改为 `/top.json?t=day` 获取真实今日热榜

### Fixed
- Reddit RSS 分数默认 10 导致过滤失效
- GitHub 知名大型 repo 占据榜单问题

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
