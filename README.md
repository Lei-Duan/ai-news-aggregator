# AI News Aggregator

An automated system that collects AI-related content from various sources (Twitter, GitHub, Reddit, Hacker News) and creates a daily briefing in Notion.

## Features

- **Multi-source Content Collection**: Aggregates content from Twitter(X), GitHub, Reddit, Hacker News, and RSS feeds
- **AI-powered Summarization**: Uses Claude API to summarize and categorize content
- **Smart Filtering**: Filters content by quality, relevance, and engagement metrics
- **Automatic Categorization**: Groups content into categories like Agent Projects, Model Releases, Research Papers, etc.
- **Notion Integration**: Automatically creates daily briefing pages in your Notion workspace
- **Scheduled Execution**: Runs daily at a configurable time (default: 9 AM PST)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-news-aggregator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

### Required API Keys

1. **Twitter API v2**: Get credentials from https://developer.twitter.com/
2. **GitHub Personal Access Token**: Create at https://github.com/settings/tokens
3. **Anthropic API Key**: Get from https://console.anthropic.com/
4. **Notion Integration Token**: Create at https://www.notion.so/my-integrations

### Notion Setup

1. Create a new Notion page for your AI briefings
2. Create an integration and get the token
3. Share your page with the integration
4. Create a database with the following properties:
   - Name (Title)
   - Date (Date)
   - Tags (Multi-select)
   - Status (Select)
   - Items Count (Number)

### Source Configuration

Edit `config/sources.yaml` to customize:
- Twitter accounts to monitor
- GitHub organizations and topics
- Reddit subreddits
- RSS feeds
- Keyword filters

## Usage

### Run Once
```bash
python main.py --mode once
```

### Test Mode (Limited content)
```bash
python main.py --mode test
```

### Scheduled Mode
```bash
python main.py --mode schedule
```

This will run the aggregator daily at the configured time.

## Content Categories

The system categorizes content into:
- **Agent Projects**: Autonomous agents and frameworks
- **Model Releases**: New AI models and updates
- **Research Papers**: Academic papers and publications
- **Industry News**: Company news and industry updates
- **Technical Tutorials**: How-to guides and implementations
- **Product Launches**: New AI products and features
- **Open Source**: Open source projects and tools

## Filtering Criteria

Content is filtered based on:
- Publication date (default: last 24 hours)
- Engagement metrics (likes, stars, upvotes)
- Quality score (AI-powered assessment)
- Relevance to AI/ML field
- Source authority
- Keyword matching

## Output Format

Each Notion page includes:
- Categorized sections with emojis
- Item title with direct link
- Summary and key points
- Source and author information
- Tags and entities
- Quality and relevance scores

## Example Output

Below is a sample of what a daily Notion briefing looks like:

---

### 📅 AI News Briefing — April 7, 2026

---

#### 🤖 Agent Projects (3 items)

**[browser-use/web-ui](https://github.com/browser-use/web-ui)** ⭐ 8,241 · 📈 823 stars/day · TypeScript
> Web UI for Browser Use — lets AI agents control a real browser with a visual interface. Gained 8k stars in 10 days, one of the fastest-rising agent repos this month.
> **Key points:** visual browser control · OpenAI/Claude compatible · Docker support

---

**r/LocalLLaMA · 2.1k upvotes**
[I built an agent that autonomously files my tax return — here's what I learned](https://reddit.com/...)
> Solo dev shares a working agentic pipeline that handles PDF parsing, form filling, and e-filing. Includes source code and a breakdown of failure modes.
> **Key points:** real-world agent · tax automation · RAG for document parsing

---

#### 🚀 Product Launches (2 items)

**[HN · 847 points] Show HN: I built a SaaS that transcribes and summarizes Zoom calls using Whisper + Claude](https://news.ycombinator.com/...)**
> Indie hacker hit $800 MRR in 3 weeks. Post includes full stack breakdown (Next.js + Supabase + Vercel).
> **Key points:** $800 MRR · Whisper + Claude · full stack breakdown

---

#### 📈 Fast-Rising GitHub Repos (5 items)

| Repo | Stars | Speed | Language | Description |
|------|-------|-------|----------|-------------|
| [kortix-ai/suna](https://github.com/kortix-ai/suna) | 9,102 | 910/day | Python | Open-source generalist AI agent |
| [landing-ai/vision-agent](https://github.com/landing-ai/vision-agent) | 4,200 | 280/day | Python | Vision-language agent framework |
| [mendableai/firecrawl](https://github.com/mendableai/firecrawl) | 3,800 | 190/day | TypeScript | Web scraping API for LLMs |

---

#### 📰 From the Builder Community

**@levelsio** · 14k likes
> "Just hit $3M ARR with PhotoAI. Still solo. Still building in public. The secret: pick one problem, stay boring, ship fast."

**r/buildinpublic · 1.4k upvotes**
> "Launched my AI resume screener 3 weeks ago. $0 → $2,400 MRR. Here's the exact landing page copy that converted."

---

*Generated by AI News Aggregator · Sources: GitHub, Reddit, Hacker News, Twitter*

## Customization

### Adding New Sources

1. Create a new fetcher in `src/fetchers/`
2. Implement the fetching logic
3. Add configuration to `config/sources.yaml`
4. Update the daily job in `src/scheduler/daily_job.py`

### Modifying Filters

Edit the filter configuration in `src/scheduler/daily_job.py`:
```python
config = {
    "days": 1,
    "min_engagement": 10,
    "required_keywords": [],
    "excluded_keywords": ["crypto", "nft"],
    "min_quality_score": 0.7
}
```

### Changing Schedule

Update the schedule in `.env`:
```
SCHEDULE_TIME=09:00
TIMEZONE=US/Pacific
```

## Troubleshooting

### Common Issues

1. **API Rate Limits**: The system includes rate limiting, but you may need to adjust fetch intervals
2. **Notion Permissions**: Ensure your integration has access to the database
3. **Content Quality**: Adjust quality thresholds in settings if getting too much/too little content

### Logs

Check logs in `logs/aggregator.log` for detailed execution information.

## Development

### Project Structure
```
ai-news-aggregator/
├── config/                 # Configuration files
│   ├── settings.py        # Environment settings
│   └── sources.yaml       # Source configurations
├── src/
│   ├── fetchers/          # Content fetchers
│   ├── processors/        # Content processing
│   ├── notion/           # Notion integration
│   └── scheduler/        # Job scheduling
├── logs/                  # Log files
├── main.py               # Main entry point
└── requirements.txt      # Dependencies
```

### Running Tests
```bash
pytest tests/
```

## License

MIT License - see LICENSE file for details.