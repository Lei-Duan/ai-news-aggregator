# Notion page templates for different types of content

from typing import List, Dict
from datetime import datetime

class NotionTemplates:
    """Templates for different Notion page layouts"""

    @staticmethod
    def get_daily_briefing_template() -> Dict:
        """Template for daily AI briefing page"""
        return {
            "icon": {"emoji": "🤖"},
            "cover": {
                "external": {
                    "url": "https://images.unsplash.com/photo-1677442136019-21780ecad995"
                }
            },
            "properties": {
                "Status": {
                    "select": {"name": "Published"}
                }
            }
        }

    @staticmethod
    def get_section_templates() -> Dict[str, Dict]:
        """Templates for different content sections"""
        return {
            "agent_projects": {
                "icon": {"emoji": "🤖"},
                "color": "blue",
                "description": "Latest AI agent projects and frameworks"
            },
            "model_releases": {
                "icon": {"emoji": "🚀"},
                "color": "green",
                "description": "New AI model releases and updates"
            },
            "research_papers": {
                "icon": {"emoji": "📄"},
                "color": "purple",
                "description": "Latest AI research papers and publications"
            },
            "industry_news": {
                "icon": {"emoji": "🏢"},
                "color": "orange",
                "description": "AI industry news and company updates"
            },
            "technical_tutorials": {
                "icon": {"emoji": "🛠️"},
                "color": "yellow",
                "description": "Technical tutorials and implementation guides"
            },
            "product_launches": {
                "icon": {"emoji": "🆕"},
                "color": "red",
                "description": "New AI product launches and features"
            },
            "open_source": {
                "icon": {"emoji": "🔓"},
                "color": "gray",
                "description": "Open source AI projects and tools"
            }
        }

    @staticmethod
    def get_item_block_template(item_type: str) -> Dict:
        """Template for individual items"""
        templates = {
            "tweet": {
                "type": "callout",
                "callout": {
                    "rich_text": [],
                    "icon": {"emoji": "🐦"},
                    "color": "blue_background"
                }
            },
            "github": {
                "type": "callout",
                "callout": {
                    "rich_text": [],
                    "icon": {"emoji": "⭐"},
                    "color": "green_background"
                }
            },
            "article": {
                "type": "callout",
                "callout": {
                    "rich_text": [],
                    "icon": {"emoji": "📰"},
                    "color": "orange_background"
                }
            },
            "paper": {
                "type": "callout",
                "callout": {
                    "rich_text": [],
                    "icon": {"emoji": "📝"},
                    "color": "purple_background"
                }
            }
        }

        return templates.get(item_type, templates["article"])

    @staticmethod
    def get_stats_block(stats: Dict) -> List[Dict]:
        """Create statistics block"""
        return [
            {
                "object": "block",
                "type": "divider",
                "divider": {}
            },
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": "📊 Daily Statistics"}
                    }]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": f"Total Items: {stats.get('total_items', 0)}"},
                            "annotations": {"bold": True}
                        }
                    ]
                }
            }
        ]

    @staticmethod
    def get_trending_tags_block(tags: List[str]) -> Dict:
        """Create trending tags block"""
        tag_elements = []
        for tag in tags:
            tag_elements.append({
                "type": "text",
                "text": {"content": f"#{tag} "},
                "annotations": {
                    "color": "blue",
                    "bold": True
                }
            })

        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "Trending: "},
                        "annotations": {"bold": True}
                    }
                ] + tag_elements
            }
        }

    @staticmethod
    def get_database_schema() -> Dict:
        """Schema for the Notion database"""
        return {
            "title": [{"type": "text", "text": {"content": "AI Daily Briefings"}}],
            "properties": {
                "Name": {
                    "title": {}
                },
                "Date": {
                    "date": {}
                },
                "Tags": {
                    "multi_select": {
                        "options": [
                            {"name": "AI", "color": "blue"},
                            {"name": "Machine Learning", "color": "green"},
                            {"name": "Deep Learning", "color": "purple"},
                            {"name": "LLM", "color": "orange"},
                            {"name": "Agent", "color": "red"},
                            {"name": "Research", "color": "yellow"},
                            {"name": "Industry", "color": "gray"},
                            {"name": "Open Source", "color": "brown"}
                        ]
                    }
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
                    "number": {
                        "format": "number"
                    }
                },
                "Agent Projects": {
                    "number": {
                        "format": "number"
                    }
                },
                "Model Releases": {
                    "number": {
                        "format": "number"
                    }
                },
                "Research Papers": {
                    "number": {
                        "format": "number"
                    }
                },
                "URL": {
                    "url": {}
                }
            }
        }