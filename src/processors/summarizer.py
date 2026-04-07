#!/usr/bin/env python3
"""AI-powered content summarization using Claude

Optimized for cost effectiveness:
- Batch processing reduces API call overhead
- Pre-filtered content only relevant items are sent to AI
- Strict output length control minimizes token usage
"""

import asyncio
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import logging
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

@dataclass
class SummaryResult:
    title: str
    summary: str
    summary_zh: str
    key_points: List[str]
    category: str
    quality_score: float
    relevance_score: float
    entities: List[str]

class ContentSummarizer:
    def __init__(self, anthropic_api_key: str):
        # Clear any proxy settings from environment to ensure direct connection
        import os
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)

        import httpx
        client = httpx.AsyncClient()
        client.proxies = None

        self.client = AsyncAnthropic(
            api_key=anthropic_api_key,
            base_url="https://api.anthropic.com",
            http_client=client
        )

    def _build_batch_prompt(self, items: List[Dict], item_type: str) -> str:
        """Build a single prompt for batch processing of multiple items"""

        if item_type == "tweet":
            instruction = """
            For each tweet below, analyze it and output a JSON array with one object per tweet.

            Each object must have these keys:
            - title: string (max 10 words, English)
            - summary: string (max 50 words, English)
            - summary_zh: string (max 80 Chinese characters, Chinese translation of summary)
            - key_points: array of strings (3-5 items, English)
            - category: string (choose from: agent-project, model-release, research-paper, industry-news, tutorial, other)
            - quality_score: number (0-1)
            - relevance_score: number (0-1)
            - entities: array of strings (key companies/models/tech)
            """

            content_items = "\n".join([
                f"--- TWEET {i+1} ---\nAuthor: {item['author']}\nText: \"{item['text']}\"\nLikes: {item.get('engagement', {}).get('likes', 0)}"
                for i, item in enumerate(items)
            ])

        elif item_type == "github":
            instruction = """
            For each GitHub repository below, analyze it and output a JSON array with one object per repository.

            Each object must have these keys:
            - title: string (max 10 words, English)
            - summary: string (max 100 words, English)
            - summary_zh: string (max 120 Chinese characters, Chinese translation of summary)
            - key_points: array of strings (3-5 items, English)
            - category: string (choose from: agent-framework, llm-tool, model-implementation, dataset, tutorial, other)
            - quality_score: number (0-1)
            - relevance_score: number (0-1)
            - entities: array of strings (key technologies/frameworks)
            """

            content_items = "\n".join([
                f"--- REPO {i+1} ---\nName: {item['name']}\nDescription: {item['description']}\nStars: {item['stars']}\nTopics: {', '.join(item.get('topics', []))}"
                for i, item in enumerate(items)
            ])

        else: # article
            instruction = """
            For each article below, analyze it and output a JSON array with one object per article.

            Each object must have these keys:
            - title: string (max 10 words, English)
            - summary: string (max 150 words, English)
            - summary_zh: string (max 150 Chinese characters, Chinese translation of summary)
            - key_points: array of strings (3-7 items, English)
            - category: string (choose from: research-breakthrough, product-launch, technical-tutorial, industry-analysis, policy-update, other)
            - quality_score: number (0-1)
            - relevance_score: number (0-1)
            - entities: array of strings (key companies/people/tech)
            """

            content_items = "\n".join([
                f"--- ARTICLE {i+1} ---\nTitle: {item['title']}\nSource: {item['source']}\nContent: {item['content'][:500]}..."
                for i, item in enumerate(items)
            ])

        final_prompt = f"""{instruction}

{content_items}

IMPORTANT:
- Output ONLY a valid JSON array of objects
- Do NOT include any explanatory text, markdown, backticks, or code blocks
- Follow the schema exactly for each object
- Keep all text within the length limits
"""
        return final_prompt

    async def batch_summarize(self, items: List[Dict], item_type: str) -> List[SummaryResult]:
        """
        Batch process multiple items in ONE API call
        This drastically reduces token overhead vs individual calls
        """
        if not items:
            return []

        prompt = self._build_batch_prompt(items, item_type)

        # Articles need ~400 tokens each (150-word summary + key_points + other fields)
        # Tweets need ~200 tokens each; github repos ~300 tokens each
        tokens_per_item = {"tweet": 200, "github": 300}.get(item_type, 400)
        max_tokens = min(300 + len(items) * tokens_per_item, 8000)

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                temperature=0.2,  # Low temperature for consistent output
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text

            # Extract JSON from response
            try:
                results = json.loads(text)
            except json.JSONDecodeError:
                import re
                # Try code block first, then greedy outer array match
                code_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
                if code_match:
                    try:
                        results = json.loads(code_match.group(1))
                    except Exception:
                        results = None
                else:
                    results = None

                if results is None:
                    # Greedy match for outermost [...]
                    json_match = re.search(r'(\[.*\])', text, re.DOTALL)
                    if json_match:
                        try:
                            results = json.loads(json_match.group(1))
                        except Exception:
                            logger.error(f"Could not extract JSON from batch response: {text[:200]}...")
                            return []
                    else:
                        logger.error(f"Could not extract JSON from batch response: {text[:200]}...")
                        return []

            # Convert to SummaryResult objects with graceful error handling
            summaries = []
            for i, result in enumerate(results):
                try:
                    summaries.append(SummaryResult(
                        title=result.get("title", f"Item {i+1}"),
                        summary=result.get("summary", ""),
                        summary_zh=result.get("summary_zh", ""),
                        key_points=result.get("key_points", []),
                        category=result.get("category", "other"),
                        quality_score=float(result.get("quality_score", 0.5)),
                        relevance_score=float(result.get("relevance_score", 0.5)),
                        entities=result.get("entities", [])
                    ))
                except Exception as e:
                    logger.error(f"Error parsing result {i}: {e}")
                    continue

            logger.info(f"Batch processed {len(summaries)}/{len(items)} {item_type} items successfully")
            return summaries

        except Exception as e:
            logger.error(f"Error in batch summarization: {e}")
            return []

    def filter_by_quality(self, summaries: List[SummaryResult],
                         min_quality_score: float = 0.7,
                         min_relevance_score: float = 0.6) -> List[SummaryResult]:
        """Filter summaries by quality and relevance scores"""
        filtered = []

        for summary in summaries:
            if (summary.quality_score >= min_quality_score and
                summary.relevance_score >= min_relevance_score):
                filtered.append(summary)

        return filtered
