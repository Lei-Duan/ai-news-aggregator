import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from notion_client import AsyncClient
from notion_client.errors import APIResponseError
import logging

logger = logging.getLogger(__name__)

class NotionClient:
    def __init__(self, token: str, database_id: str):
        self.client = AsyncClient(auth=token)
        self.database_id = database_id

    async def create_daily_briefing(self, date: datetime, sections: Dict[str, List[Dict]]) -> str:
        """Create a daily briefing page in Notion"""
        try:
            all_blocks = self._build_page_content(sections)

            # Notion does NOT allow table blocks with children in pages.create —
            # we must append them separately after page creation.
            # Split: non-table blocks for creation, table blocks for append.
            non_table = [b for b in all_blocks if b.get("type") != "table"]
            table_blocks = [b for b in all_blocks if b.get("type") == "table"]

            # Create page with first 100 non-table blocks
            page_data = {
                "parent": {"database_id": self.database_id},
                "properties": {
                    "Name": {"title": [{"text": {"content": f"AI Daily Briefing - {date.strftime('%Y-%m-%d')}"}}]},
                    "Date": {"date": {"start": date.strftime("%Y-%m-%d")}},
                    "Tags": {"multi_select": [{"name": "AI"}, {"name": "Daily Briefing"}]},
                },
                "children": non_table[:100],
            }

            response = await self.client.pages.create(**page_data)
            page_id = response["id"]

            # Append remaining non-table blocks in chunks of 100
            for i in range(100, len(non_table), 100):
                await self.append_to_page(page_id, non_table[i:i + 100])

            # Append table blocks individually (each table with its children)
            for table_block in table_blocks:
                await self.append_to_page(page_id, [table_block])

            logger.info(f"Created daily briefing page: {page_id}")
            return page_id

        except APIResponseError as e:
            logger.error(f"Error creating Notion page: {e}")
            raise

    # ── Category → Chinese label ────────────────────────────────────────────
    CATEGORY_ZH = {
        # Tweet categories
        "agent-project":      "🤖 Agent应用",
        "model-release":      "🚀 基础模型迭代",
        "research-paper":     "📄 学术研究",
        "industry-news":      "🏢 行业动态",
        "tutorial":           "🛠 技术教程",
        # GitHub categories
        "agent-framework":    "🤖 Agent框架",
        "llm-tool":           "⚙️ LLM工具",
        "model-implementation":"🔬 模型实现",
        "dataset":            "📦 数据集",
        # Article categories
        "research-breakthrough": "🔬 研究突破",
        "product-launch":     "🆕 产品发布",
        "technical-tutorial": "🛠 技术教程",
        "industry-analysis":  "📊 行业分析",
        "policy-update":      "📋 政策动态",
        # Special
        "podcast":            "🎙 播客",
        "blog":               "📝 官方博客",
        "other":              "📰 其他",
    }

    # ── Section metadata ────────────────────────────────────────────────────
    SECTION_META = {
        "Agent Projects":      {"emoji": "🤖", "zh": "Agent 项目"},
        "Model Releases":      {"emoji": "🚀", "zh": "模型发布"},
        "Research Papers":     {"emoji": "📄", "zh": "研究论文"},
        "Industry News":       {"emoji": "🏢", "zh": "行业动态"},
        "Technical Tutorials": {"emoji": "🛠️", "zh": "技术教程"},
        "Product Launches":    {"emoji": "🆕", "zh": "产品发布"},
        "Open Source":         {"emoji": "🔓", "zh": "开源项目"},
        "Other":               {"emoji": "📰", "zh": "其他"},
    }

    def _section_label(self, title: str) -> str:
        meta = self.SECTION_META.get(title, {"emoji": "📌", "zh": title})
        return f"{meta['emoji']} {meta['zh']} / {title}"

    # ── Helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _h1(text: str) -> Dict:
        return {"object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    @staticmethod
    def _h2(text: str) -> Dict:
        return {"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    @staticmethod
    def _h3(text: str, url: str = "") -> Dict:
        rich = {"type": "text", "text": {"content": text}, "annotations": {"bold": True}}
        if url:
            rich["href"] = url
        return {"object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [rich]}}

    @staticmethod
    def _para(text: str, bold: bool = False, italic: bool = False, color: str = "default") -> Dict:
        ann = {}
        if bold:   ann["bold"] = True
        if italic: ann["italic"] = True
        if color != "default": ann["color"] = color
        rich = {"type": "text", "text": {"content": text}}
        if ann:
            rich["annotations"] = ann
        return {"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [rich]}}

    @staticmethod
    def _bullet(text: str, bold: bool = False) -> Dict:
        ann = {"bold": True} if bold else {}
        rich = {"type": "text", "text": {"content": text}}
        if ann:
            rich["annotations"] = ann
        return {"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [rich]}}

    @staticmethod
    def _divider() -> Dict:
        return {"object": "block", "type": "divider", "divider": {}}

    @staticmethod
    def _blank() -> Dict:
        return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}

    def _build_summary_table(self, sections: Dict[str, List[Dict]]) -> Dict:
        """Build a Notion table block: 类别 | 标题 | 来源 | 中文摘要"""
        header_row = {
            "object": "block", "type": "table_row",
            "table_row": {"cells": [
                [{"type": "text", "text": {"content": "类别 / Category"},
                  "annotations": {"bold": True}}],
                [{"type": "text", "text": {"content": "标题 / Title"},
                  "annotations": {"bold": True}}],
                [{"type": "text", "text": {"content": "来源 / Source"},
                  "annotations": {"bold": True}}],
                [{"type": "text", "text": {"content": "中文摘要 / Summary"},
                  "annotations": {"bold": True}}],
            ]}
        }
        rows = [header_row]

        for section_title, items in sections.items():
            meta = self.SECTION_META.get(section_title, {"emoji": "📌", "zh": section_title})
            cat_label = f"{meta['emoji']} {meta['zh']}"
            for item in items:
                title = item.get("title", "")
                url   = item.get("url", "")
                source = item.get("source", "")
                summary_zh = item.get("summary_zh", item.get("summary", ""))[:100]

                title_cell = [{"type": "text", "text": {"content": title}}]
                if url:
                    title_cell[0]["href"] = url

                rows.append({
                    "object": "block", "type": "table_row",
                    "table_row": {"cells": [
                        [{"type": "text", "text": {"content": cat_label}}],
                        title_cell,
                        [{"type": "text", "text": {"content": source}}],
                        [{"type": "text", "text": {"content": summary_zh}}],
                    ]}
                })

        return {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": 4,
                "has_column_header": True,
                "has_row_header": False,
                "children": rows,
            },
        }

    def _build_page_content(self, sections: Dict[str, List[Dict]]) -> List[Dict]:
        """Build Notion blocks: header → summary table → per-section bilingual detail."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        total = sum(len(v) for v in sections.values())
        blocks: List[Dict] = []

        # ── 1. Header ──────────────────────────────────────────────────────
        blocks.append(self._h1("🤖 AI 日报 | AI Daily Briefing"))
        blocks.append(self._para(
            f"生成时间 / Generated: {now_str}  ·  共 {total} 条 / {total} items",
            italic=True, color="gray"
        ))

        # ── 2. Summary table (top) ─────────────────────────────────────────
        blocks.append(self._h2("📊 今日速览 / Today at a Glance"))
        blocks.append(self._build_summary_table(sections))
        blocks.append(self._divider())

        # ── 3. Detailed sections: each topic = Chinese items then English items
        blocks.append(self._h2("📋 详细内容 / Detailed Content"))
        for section_title, items in sections.items():
            if not items:
                continue
            meta = self.SECTION_META.get(section_title, {"emoji": "📌", "zh": section_title})
            # Section heading: Chinese / English
            blocks.append(self._h2(
                f"{meta['emoji']} {meta['zh']} / {section_title} ({len(items)})"
            ))
            for item in items:
                # Chinese first, then English immediately after
                blocks.extend(self._create_item_blocks_zh(item))
                blocks.extend(self._create_item_blocks_en(item))
            blocks.append(self._blank())

        return blocks

    def _item_meta_line(self, item: Dict) -> str:
        parts = []
        if item.get("source"): parts.append(item["source"])
        if item.get("author"): parts.append(item["author"])
        pub = item.get("published_at", "")
        if pub and isinstance(pub, str): parts.append(pub[:10])
        return "  ·  ".join(parts)

    def _item_tag_block(self, item: Dict) -> Dict:
        """Single paragraph with three inline segments: type · date · 🔗 link."""
        cat = item.get("category", "other")
        cat_label = self.CATEGORY_ZH.get(cat, f"📌 {cat}")

        pub = item.get("published_at", "")
        if hasattr(pub, "strftime"):
            date_str = pub.strftime("%Y-%m-%d")
        elif isinstance(pub, str) and pub:
            date_str = pub[:10]
        else:
            date_str = ""

        url = item.get("url", "")

        rich_text = [
            {
                "type": "text",
                "text": {"content": cat_label},
                "annotations": {"bold": True, "color": "blue"},
            },
        ]
        if date_str:
            rich_text.append({
                "type": "text",
                "text": {"content": f"   🕐 {date_str}"},
                "annotations": {"color": "gray"},
            })
        if url:
            rich_text.append({
                "type": "text",
                "text": {"content": "   🔗 原文", "link": {"url": url}},
                "annotations": {"color": "blue"},
            })

        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text},
        }

    def _create_item_blocks_zh(self, item: Dict) -> List[Dict]:
        blocks = []
        title = item.get("title", "Untitled")
        url   = item.get("url", "")
        blocks.append(self._h3(title, url))

        # Tag line: type · date · 🔗 link
        blocks.append(self._item_tag_block(item))

        summary_zh = item.get("summary_zh", "")
        if summary_zh:
            blocks.append(self._para(summary_zh))

        entities = item.get("entities", [])
        if entities:
            blocks.append(self._para(f"🏷 {', '.join(entities)}", color="gray"))

        blocks.append(self._blank())
        return blocks

    def _create_item_blocks_en(self, item: Dict) -> List[Dict]:
        blocks = []
        title = item.get("title", "Untitled")
        url   = item.get("url", "")
        blocks.append(self._h3(title, url))

        # Tag line: type · date · 🔗 link
        blocks.append(self._item_tag_block(item))

        summary = item.get("summary", "")
        if summary:
            blocks.append(self._para(summary))

        for point in item.get("key_points", []):
            blocks.append(self._bullet(f"{point}"))

        entities = item.get("entities", [])
        if entities:
            blocks.append(self._para(f"🏷 {', '.join(entities)}", color="gray"))

        blocks.append(self._blank())
        return blocks

    async def update_page_properties(self, page_id: str, properties: Dict) -> bool:
        """Update page properties"""
        try:
            await self.client.pages.update(page_id=page_id, properties=properties)
            logger.info(f"Updated page properties: {page_id}")
            return True

        except APIResponseError as e:
            logger.error(f"Error updating page properties: {e}")
            return False

    async def get_existing_pages(self, date: datetime) -> List[Dict]:
        """Check if a briefing already exists for the given date"""
        try:
            # notion-client 3.x removed databases.query; use raw request instead
            response = await self.client.request(
                path=f"databases/{self.database_id}/query",
                method="POST",
                body={
                    "filter": {
                        "property": "Date",
                        "date": {
                            "equals": date.strftime("%Y-%m-%d")
                        }
                    }
                }
            )

            return response.get("results", [])

        except APIResponseError as e:
            logger.error(f"Error querying database: {e}")
            return []

    async def append_to_page(self, page_id: str, content_blocks: List[Dict]) -> bool:
        """Append content blocks to an existing page"""
        try:
            await self.client.blocks.children.append(
                block_id=page_id,
                children=content_blocks
            )
            logger.info(f"Appended content to page: {page_id}")
            return True

        except APIResponseError as e:
            logger.error(f"Error appending to page: {e}")
            return False

    async def create_database_if_not_exists(self, parent_page_id: str) -> str:
        """Create a database for storing daily briefings"""
        try:
            database_data = {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "title": [{
                    "type": "text",
                    "text": {"content": "AI Daily Briefings"}
                }],
                "properties": {
                    "Name": {
                        "title": {}
                    },
                    "Date": {
                        "date": {}
                    },
                    "Tags": {
                        "multi_select": {}
                    },
                    "Status": {
                        "select": {
                            "options": [
                                {"name": "Draft", "color": "yellow"},
                                {"name": "Published", "color": "green"},
                                {"name": "Archived", "color": "gray"}
                            ]
                        }
                    },
                    "Items Count": {
                        "number": {}
                    }
                }
            }

            response = await self.client.request(
                path="databases",
                method="POST",
                body=database_data,
            )
            database_id = response["id"]

            logger.info(f"Created database: {database_id}")
            return database_id

        except APIResponseError as e:
            logger.error(f"Error creating database: {e}")
            raise