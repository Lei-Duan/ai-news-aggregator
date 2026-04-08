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
        """Batch process items, splitting into safe sub-batches to avoid truncation."""
        if not items:
            return []

        # Tweets can be long (note_tweet); keep sub-batches small to avoid truncation
        max_per_call = {"tweet": 5, "github": 10}.get(item_type, 6)

        if len(items) <= max_per_call:
            return await self._summarize_batch(items, item_type)

        # Split and concatenate results
        results = []
        for i in range(0, len(items), max_per_call):
            chunk = items[i:i + max_per_call]
            chunk_results = await self._summarize_batch(chunk, item_type)
            results.extend(chunk_results)
        return results

    async def _summarize_batch(self, items: List[Dict], item_type: str) -> List[SummaryResult]:
        """Single API call for one sub-batch."""
        prompt = self._build_batch_prompt(items, item_type)

        # Give generous token budget so the response is never truncated mid-JSON
        tokens_per_item = {"tweet": 350, "github": 400}.get(item_type, 500)
        max_tokens = min(500 + len(items) * tokens_per_item, 8000)

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()

            # Robust JSON extraction: track bracket nesting depth rather than regex
            results = self._extract_json_array(text)
            if results is None:
                logger.error(f"Could not extract JSON from batch response: {text[:300]}...")
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

    def _extract_json_array(self, text: str) -> Optional[list]:
        """
        Find and parse the first complete JSON array in text.
        Tracks bracket/brace nesting and string escaping — handles nested arrays
        correctly unlike a greedy regex which can mis-match on nested structures.
        """
        # 1. Direct parse (ideal case: Claude returned pure JSON)
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 2. Strip markdown code fences and retry
        import re
        stripped = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        stripped = re.sub(r'\s*```$', '', stripped, flags=re.MULTILINE).strip()
        try:
            result = json.loads(stripped)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 3. Find the first `[` and walk forward tracking depth
        start = text.find('[')
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i, ch in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

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
