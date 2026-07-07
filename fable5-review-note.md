# Fable5 复盘笔记 — ai-news-aggregator

> 复盘日期: 2026-07-07 · Reviewed by Claude (Fable 5)

每日 AI 简报机器人：Python asyncio 从 7 个平台（Twitter/GitHub/Reddit/HN/RSS/官方博客/播客）抓取内容，用 Claude Haiku 批量生成中英双语摘要，写入 Notion 并可发 Gmail 摘要邮件；完全跑在 GitHub Actions cron 上（每天 09:05 PST），去重状态存 Actions Cache，零服务器。src 约 2300 行，共 42 个 commit：2026-04-07/08 两天密集搭建（26 commits），之后进入"事故驱动"维护模式——5 月 Notion 401 事故、6 月 1 日 Twitter tombstone 事故各一轮修复。最后一次 commit 是 6 月 1 日，至今已稳定运行一个多月，属于成熟维护期项目。

## 1. 哪些任务可以做成 Skill

- **`/briefing-doctor`（简报体检/事故分诊）— 最值得做**。你的 prompt 历史就是这个循环的完整样本："pull 最新代码 → 查一下为什么过去几天 twitter 断掉了 → 按长久能 run 的方式修复 → 手动触发看 notion 是否正常 → merge to main"。5 月的 Notion 401（连续 5 天失败）和 6 月的 Twitter tombstone（连续多天 0 条但 job 显示 success）走的是同一套流程。Skill 内容：`gh run list` 拉最近 N 次 run → 下载日志 grep `Raw [source]: N items` 和 fetch_stats → 定位归零/报错的 source → 结合 CLAUDE.md 的"已知问题"表诊断 → 修复后 `gh workflow run` + watch → 验证当天 Notion 页面。`.claude/settings.local.json` 里已经预授权了 `gh run *`，说明这套操作你已重复多次。
- **`/verify-briefing`（触发+验收）**。"手动触发然后看一下notion是否正常"是独立的可复用动作：workflow_dispatch → 等待完成 → 检查当天 Notion 页面存在、抓取状态 callout 里各 source 计数正常、必要时清理失败的残留行（你也提过"之前失败的notion行可以删掉"）。可以先写成脚本，skill 只做编排。
- **`/add-source`（源管理）**。加 Twitter 账号/subreddit/RSS 要同时改 `config/sources.yaml`、README 两个语言版的来源表、CLAUDE.md 的渠道表——PR #3（AI Infrastructure 分类）就伴随了 README/CLAUDE.md 两次 docs commit。Skill 一次改齐三处。
- **文档同步可并入你 skills repo 里已有的 `/document-release` 类能力**：本项目 README 是中英双份 + CLAUDE.md 三处冗余，历史上 docs commit 占比很高（883ad06、c8ed0a7、5e10db8、168b8d1）。

## 2. 哪些流程可以自动化

**已有**：Actions 每日 cron、pip 按 requirements.txt hash 缓存、去重状态用 Actions Cache（fork 隔离，设计得很好）、失败时上传日志 artifact。

**建议补**：
- **静默失败告警（最高优先级）**。6 月事故的教训写在 2149f48 里："The job still exited success, so it went unnoticed in the run list"——Twitter 连续多天 0 条无人发现。在 workflow 加一步 health check：某个平常非零的 source 连续 ≥2 天 count=0 就让 step 失败或自动开 GitHub Issue（email 模块 `src/notifiers/email.py` 现成，也可直接发告警邮件）。fetch_stats 已经有全部数据，只差持久化对比。
- **workflow 失败通知**。现在失败只留 artifact，不推送。加 `if: failure()` 开 issue 或发邮件，否则又要靠"过几天发现 Notion 没更新"来触发排查。
- **最小 CI 测试**。项目零测试。加一个 PR 触发的 pytest：sources.yaml 可解析、summarizer 的 JSON 解析（带 markdown 代码块的 fixture）、state 的 7 天 TTL/同日重跑逻辑。这三块恰好是历史上出过 bug 的地方。
- **博客爬虫月度巡检**。CLAUDE.md 自己写了"OpenAI/Gemini/DeepMind 用 HTML 解析，可能因页面结构变化失效"——这是下一个静默失败源，可用一个 monthly schedule 只跑 blog fetcher 并校验非零。

## 3. 哪些提示词一直在重复

提示词样本只有 4 条，但信息密度很高，且与 commit 历史互相印证：

- **"按照长久能够run的方式修复吧，注意节约token"**——两个约束反复出现：修复要 durable（区分瞬时故障 vs 永久失效，2149f48 整个 commit body 都在讲这个）、任何改动要省成本（0c9e8a4 砍 96% Twitter 费用、切 Haiku、批量摘要）。建议把这两条写进 CLAUDE.md 的"修复原则"节：*"所有 fix 必须考虑瞬时错误重试与永久失效的区分；任何新增 API 调用先估算日成本"*。写进去之后就不用每次口头强调。
- **"手动触发然后看一下notion是否正常"**——验收循环，见上文 skill 建议。
- **"直接merge to main"**——合并策略。可在 CLAUDE.md 写明：*"验证通过后直接 merge PR 到 main，不需再确认"*，省一轮往返。
- **从 commit 推断的隐性重复**：每次行为变更后都要单独提一次"更新 CLAUDE.md/README"（至少 4 次 docs commit）；5 月 18-19 日连续 3 个 `chore(ci): temp debug` commit 说明"在 CI 里靠提交调试代码排错"也是一个重复过的低效模式（见第 5 节）。

## 4. 一次性代码 / 清理建议

- **`src/processors/classifier.py`（175 行，死代码）**：`ContentClassifier` 只在 `daily_job.py:59` 被实例化，从未被调用——分类实际来自 summarizer 的输出。→ **本 PR 已删除**（文件 + daily_job.py 两行引用）。
- **`AGENTS.md`（untracked，6 月 23 日生成）**：是 CLAUDE.md 的 sed 复制品，把 "Claude" 全局替换成了 "Codex"，产生了 `Codex Haiku`、`Codex-haiku-4-5-20251001` 这种错误模型名，会误导任何读它的 agent。要么删掉，要么正确重生成（AGENTS.md 应与 CLAUDE.md 内容一致，模型名不该被替换）。（未跟踪文件，无法进本 PR，需你本地处理。）
- **`config/settings.py` 的 `twitter_api_key/api_secret/access_token/access_token_secret`**：四个配置项全项目无人使用，workflow 里对应的 4 行 secrets 注入也可一并删。→ **本 PR 已删除（含 workflow 4 行，dry-run 实例化验证通过）**
- **`main.py` 的 `--config` 参数**：解析后从未读取；`--mode schedule`（APScheduler 常驻模式）自从上了 Actions cron 后也没有存在必要，删掉可顺带去掉 `apscheduler` 依赖——需要你决定是否保留本地常驻的可能性。
- **`state/twitter_user_ids.json` 被 track 进 git**：它是运行时缓存，条目带 7 天 TTL（`cached_at` 停在 5 月 7 日），任何人拿到时都已过期，且 CI 里会被 Actions Cache 覆盖——作为 fork 种子毫无作用。建议 `git rm --cached` 并像 `seen_items.json` 一样进 .gitignore。
- **`src/notion/client.py` 尾部 4 个方法**（`update_page_properties`/`get_existing_pages`/`append_to_page`/`create_database_if_not_exists`，约 100 行）：全项目无调用，属初版遗留。→ **本 PR 已删除**
- **小问题**：`.gitignore` 里 `.DS_Store` 重复两次，且有一行 `.idea/.env.api` 疑似两行粘连（导致 `.idea/` 实际没被忽略）→ **本 PR 已修复**；`CHANGELOG.md` 停更在 0.3.1（4 月 7 日），之后的邮件推送、Actions Cache 去重、AI 基建分类、Twitter 成本优化都没记录。
- **保留勿删**：`twitter.py` 的 `search_trending()` 是有意保留的（CLAUDE.md 明确写了升级 Pro tier 后重新启用）。

## 5. 常规使用方法 & 经验总结

- **你的模式**：短周期密集搭建（4 月 7-8 日两天 26 commits 从 0.1 干到 0.3.1）→ 长期靠"发现产出异常 → 开一个 Claude Code session 分诊修复"维护。对这种无人值守项目，这个模式成立，但前提是失败要能主动找到你——目前它不能（见第 2 节告警建议），这是全项目最大的单点风险。
- **做得好、要保持的**：① CLAUDE.md 质量很高（渠道逻辑表、已知问题、成本数字、去重语义），且每次事故后都回写（c8ed0a7）——这是你 session 效率高的直接原因；② commit message 是小型 postmortem（1dbb8f2、2149f48 把 root cause 写得清清楚楚），三个月后复盘全靠它们；③ 独立开发也走 PR + merge（#3、#4），可追溯性好；④ 成本意识贯穿始终。
- **踩过的坑**：① "job success ≠ 系统健康"——Twitter 断供多天无感知；② 5 月 14-20 日的 Notion 401 拖了 6 天，期间靠 3 个 temp debug commit 在 CI 里排错，而最终修复（notion-client 3.1.0 吞掉 auth kwarg）恰恰是本地就能复现的——教训：先在本地复现 CI 环境，别用每日 cron 当调试循环；③ 文档三处冗余（README 中英 + CLAUDE.md）已开始漂移，CHANGELOG 已弃更——要么用 skill 强制同步，要么砍掉一处。
- **下次开工建议**：先做静默失败告警（半小时的活，回报最高），再顺手清第 4 节的死代码，最后把"修复原则/merge 策略"两条写进 CLAUDE.md（**本 PR 已写入**，见 CLAUDE.md 新增的"修复原则 & 工作约定"节）。
