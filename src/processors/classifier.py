from typing import List, Dict
from enum import Enum
import re

class ContentCategory(Enum):
    AGENT_PROJECT = "agent-project"
    MODEL_RELEASE = "model-release"
    RESEARCH_PAPER = "research-paper"
    INDUSTRY_NEWS = "industry-news"
    TECHNICAL_TUTORIAL = "technical-tutorial"
    PRODUCT_LAUNCH = "product-launch"
    POLICY_UPDATE = "policy-update"
    OPEN_SOURCE = "open-source"
    OTHER = "other"

class ContentClassifier:
    """Classify content into categories based on keywords and patterns"""

    def __init__(self):
        self.category_patterns = {
            ContentCategory.AGENT_PROJECT: [
                r"\bagent\b", r"\bautonomous\b", r"\btool.?(use|using)\b",
                r"\bfunction.?(call|calling)\b", r"\breact.?(agent)?\b",
                r"\bchain.?(of)?.?thought\b", r"\bplanning.?(agent)?\b",
                r"\bmulti.?(agent)?\b", r"\bswarm\b"
            ],
            ContentCategory.MODEL_RELEASE: [
                r"\b(gpt|claude|llama|gemini|palm|bard)\b.*\brelease\b",
                r"\bnew.?(model|llm)\b", r"\blaunch.*\bmodel\b",
                r"\bfoundation.?(model)?\b.*\breleased?\b",
                r"\bopen.?(source)?.*\bmodel\b", r"\bmodel.*\bavailable\b"
            ],
            ContentCategory.RESEARCH_PAPER: [
                r"\bpaper\b", r"\barxiv\b", r"\bresearch\b.*\bpublish\b",
                r"\bconference\b", r"\bjournal\b", r"\bpeer.?(review)?\b",
                r"\bacademic\b", r"\bstudy\b", r"\bexperiment\b"
            ],
            ContentCategory.INDUSTRY_NEWS: [
                r"\b(openai|anthropic|google|microsoft|meta)\b.*\bacquir\b",
                r"\bfunding.*\b(ai|ml)\b", r"\bstartup.*\bai\b",
                r"\bpartnership.*\b(ai|ml)\b", r"\bcollaboration.*\bai\b",
                r"\bmarket.*\bai\b", r"\bregulation.*\bai\b"
            ],
            ContentCategory.TECHNICAL_TUTORIAL: [
                r"\btutorial\b", r"\bguide\b", r"\bhow.?(to)?\b",
                r"\bstep.?(by)?.?step\b", r"\bimplementation\b",
                r"\bcode.*\bexample\b", r"\bdemo\b", r"\bworkshop\b"
            ],
            ContentCategory.PRODUCT_LAUNCH: [
                r"\blaunch.*\b(product|feature)\b", r"\bnew.*\bfeature\b",
                r"\bproduct.*\bannounce\b", r"\bavailable.*\bnow\b",
                r"\bintroduc.*\b(product)?\b", r"\brelease.*\bversion\b"
            ],
            ContentCategory.OPEN_SOURCE: [
                r"\bopen.?(source)?\b", r"\bgit(hub|lab)\b",
                r"\brepository\b", r"\bgithub\.com\b",
                r"\bcontribut.*\b", r"\bmit.?(license)?\b",
                r"\bapache.?(license)?\b"
            ]
        }

    def classify_text(self, text: str, title: str = "") -> ContentCategory:
        """Classify text into a content category"""
        combined_text = f"{title} {text}".lower()

        # Count matches for each category
        category_scores = {}
        for category, patterns in self.category_patterns.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, combined_text, re.IGNORECASE)
                score += len(matches)
            category_scores[category] = score

        # Return category with highest score
        if max(category_scores.values()) > 0:
            return max(category_scores, key=category_scores.get)

        return ContentCategory.OTHER

    def classify_batch(self, items: List[Dict]) -> Dict[ContentCategory, List[Dict]]:
        """Classify multiple items and group by category"""
        categorized = {category: [] for category in ContentCategory}

        for item in items:
            text = item.get("text", "")
            title = item.get("title", "")
            category = self.classify_text(text, title)
            categorized[category].append(item)

        return categorized

    def extract_entities(self, text: str) -> List[str]:
        """Extract key entities from text"""
        entities = []

        # Company names
        companies = [
            "OpenAI", "Anthropic", "Google", "Microsoft", "Meta", "Facebook",
            "DeepMind", "NVIDIA", "Hugging Face", "Stability AI", "Midjourney",
            "Runway", "Cohere", "AI21 Labs", "Character.AI", "Inflection"
        ]

        # Model names
        models = [
            "GPT", "Claude", "LLaMA", "Gemini", "PaLM", "Bard", "DALL-E",
            "Stable Diffusion", "Midjourney", "ChatGPT", "GPT-4", "GPT-3.5"
        ]

        # Frameworks/Tools
        frameworks = [
            "PyTorch", "TensorFlow", "JAX", "Hugging Face", "Transformers",
            "LangChain", "LlamaIndex", "AutoGPT", "BabyAGI", "MetaGPT"
        ]

        # Check for each entity type
        for company in companies:
            if company.lower() in text.lower():
                entities.append(company)

        for model in models:
            if model.lower() in text.lower():
                entities.append(model)

        for framework in frameworks:
            if framework.lower() in text.lower():
                entities.append(framework)

        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append(entity)

        return unique_entities

    def is_ai_related(self, text: str, title: str = "") -> bool:
        """Check if content is AI-related"""
        ai_keywords = [
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "transformer", "GPT", "LLM", "large language model",
            "generative AI", "AGI", "natural language processing", "computer vision",
            "reinforcement learning", "supervised learning", "unsupervised learning",
            "fine-tuning", "prompt engineering", "token", "embedding", "latent",
            "diffusion", "GAN", "VAE", "BERT", "T5", "PaLM", "Claude", "ChatGPT"
        ]

        combined_text = f"{title} {text}".lower()

        # Check for AI keywords
        for keyword in ai_keywords:
            if keyword.lower() in combined_text:
                return True

        return False

    def get_content_type(self, url: str = "", source: str = "") -> str:
        """Determine content type based on URL and source"""
        if "arxiv.org" in url:
            return "research_paper"
        elif "github.com" in url:
            return "repository"
        elif "twitter.com" in url or "x.com" in url:
            return "tweet"
        elif "reddit.com" in url:
            return "reddit_post"
        elif "news.ycombinator.com" in url:
            return "hackernews_post"
        elif any(term in source.lower() for term in ["blog", "medium", "substack"]):
            return "blog_post"
        elif "youtube.com" in url or "youtu.be" in url:
            return "video"
        else:
            return "article"