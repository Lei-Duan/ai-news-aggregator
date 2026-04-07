# AI News Aggregator - Project Context

## 项目概述
这是一个AI新闻聚合器，专注于收集Twitter(X)、GitHub、Reddit等平台上的AI相关信息，特别是"build in public"社区的内容。系统每天自动生成简报并添加到Notion页面。

## 核心功能
- 多平台内容抓取（Twitter API v2、GitHub、Reddit RSS、Hacker News、RSS订阅）
- AI驱动的内容摘要和分类（使用Claude API）
- 自动创建Notion页面格式的每日简报
- 支持定时任务（每天上午9点PST执行）
- 专注于AI工具构建者和独立开发者社区

## 设计原则 - 成本优化
**token使用优化是最高优先级：**
- ✅ **批量处理优于逐个处理** - 将多条内容聚合到单个API调用，减少system prompt overhead
- ✅ **严格过滤无关内容** - 只处理和AI/build-in-public相关的内容
- ✅ **限制输出长度** - 摘要保持简洁，控制token消耗
- ✅ **并发控制** - 适配API速率限制，避免浪费重试token
- ✅ **关键词预过滤** - 在AI处理前过滤掉不相关内容

## 技术架构
- Python 3.9+ 异步架构（asyncio/aiohttp）
- 模块化设计，支持多种内容源
- 支持AI处理和基础处理两种模式
- 使用APScheduler进行任务调度

## 配置文件
- `.env` - API密钥配置
- `config/sources.yaml` - 内容源配置
- `logs/aggregator.log` - 运行日志

## 主要模块
- `main.py` - 主入口，支持test/once/schedule模式
- `src/scheduler/daily_job.py` - 核心调度逻辑
- `src/fetchers/` - 各平台内容抓取器
- `src/processors/` - 内容处理和摘要模块
- `src/notion/client.py` - Notion API集成

## Build in Public 焦点
系统特别配置为关注：
- Twitter账户：@levelsio, @dannypostmaa, @marc_lou_ 等
- Reddit社区：r/buildinpublic, r/indiehackers, r/sideproject
- GitHub主题：ai-saas, indie-hacker, buildinpublic
- 内容分类：收入里程碑、产品发布、进展更新、工具资源

## 运行命令
```bash
# 测试模式
python3 main.py --mode test

# 单次运行完整简报
python3 main.py --mode once

# 启动定时任务
python3 main.py --mode schedule
```

## API需求
- Twitter API v2（Bearer Token）
- GitHub Personal Access Token
- Anthropic API Key（Claude）
- Notion Integration Token + Database ID

## 项目状态
✅ 核心架构完成
✅ 所有内容抓取器实现
✅ AI摘要和分类功能  
✅ Notion集成完成
✅ 定时任务调度
✅ Build in Public焦点配置
✅ **token使用优化** - 批量处理减少API调用
⏳ API密钥配置完成后即可完整运行