from typing import List, Dict
import re

class BasicContentProcessor:
    """Basic content processing without AI/ML APIs"""

    @staticmethod
    def categorize_text(text: str) -> str:
        """Basic categorization based on keywords"""
        text_lower = text.lower()

        # Define keyword patterns for each category
        categories = {
            "agent-project": ["agent", "autonomous", "multi-agent", "swarm", "tool use", "function call"],
            "model-release": ["gpt", "claude", "llama", "gemini", "model release", "new model", "foundation model"],
            "research-paper": ["paper", "arxiv", "research", "study", "experiment", "publication"],
            "industry-news": ["funding", "acquisition", "startup", "partnership", "company", "industry"],
            "technical-tutorial": ["tutorial", "guide", "how to", "implementation", "code example", "demo"],
            "product-launch": ["launch", "product", "feature", "announce", "available", "release"],
            "open-source": ["open source", "github", "repository", "mit license", "apache"]
        }

        # Count matches for each category
        category_scores = {}
        for category, keywords in categories.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            category_scores[category] = score

        # Return category with highest score
        if max(category_scores.values()) > 0:
            return max(category_scores, key=category_scores.get)

        return "other"

    @staticmethod
    def extract_entities(text: str) -> List[str]:
        """Extract key entities from text"""
        entities = []
        text_lower = text.lower()

        # Companies and organizations
        companies = [
            "OpenAI", "Anthropic", "Google", "Microsoft", "Meta", "Facebook",
            "DeepMind", "NVIDIA", "Hugging Face", "Stability AI", "Midjourney",
            "Runway", "Cohere", "AI21 Labs", "Character.AI", "Inflection"
        ]

        # AI Models
        models = [
            "GPT", "Claude", "LLaMA", "Gemini", "PaLM", "Bard", "DALL-E",
            "Stable Diffusion", "Midjourney", "ChatGPT", "GPT-4", "GPT-3.5",
            "T5", "BERT", "RoBERTa", "XLNet", "ELECTRA"
        ]

        # Frameworks and tools
        frameworks = [
            "PyTorch", "TensorFlow", "JAX", "Hugging Face", "Transformers",
            "LangChain", "LlamaIndex", "AutoGPT", "BabyAGI", "MetaGPT",
            "Ray", "Weights & Biases", "MLflow", "Kubeflow"
        ]

        # Check for each entity type
        for company in companies:
            if company.lower() in text_lower:
                entities.append(company)

        for model in models:
            if model.lower() in text_lower:
                entities.append(model)

        for framework in frameworks:
            if framework.lower() in text_lower:
                entities.append(framework)

        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append(entity)

        return unique_entities

    @staticmethod
    def generate_summary(text: str, title: str = "", max_length: int = 150) -> str:
        """Generate a basic summary"""
        # Combine title and text
        full_text = f"{title} {text}".strip()

        # If text is already short enough, return it
        if len(full_text) <= max_length:
            return full_text

        # Otherwise, truncate and add ellipsis
        return full_text[:max_length-3] + "..."

    @staticmethod
    def generate_key_points(text: str, num_points: int = 3) -> List[str]:
        """Generate key points from text"""
        # Simple approach: look for sentences with important keywords
        sentences = re.split(r'[.!?]+', text)
        key_sentences = []

        # Keywords that indicate important information
        important_keywords = [
            "breakthrough", "innovation", "achievement", "result", "finding",
            "improvement", "enhancement", "capability", "feature", "function",
            "performance", "accuracy", "efficiency", "method", "approach",
            "algorithm", "architecture", "framework", "model", "system"
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:  # Skip very short sentences
                score = sum(1 for keyword in important_keywords if keyword in sentence.lower())
                if score > 0:
                    key_sentences.append((sentence, score))

        # Sort by score and take top N
        key_sentences.sort(key=lambda x: x[1], reverse=True)
        key_points = [sentence for sentence, score in key_sentences[:num_points]]

        # If no key points found, use first few sentences
        if not key_points:
            key_points = [s.strip() for s in sentences[:num_points] if len(s.strip()) > 20]

        return key_points[:num_points]

    @staticmethod
    def calculate_quality_score(text: str, source_type: str = "") -> float:
        """Calculate a basic quality score (0-1)"""
        base_score = 0.6

        # Length factor (not too short, not too long)
        text_length = len(text)
        if 100 < text_length < 2000:
            base_score += 0.1

        # Technical content factor
        technical_keywords = [
            "algorithm", "model", "neural", "deep learning", "machine learning",
            "artificial intelligence", "transformer", "attention", "embedding",
            "optimization", "training", "inference", "benchmark", "accuracy"
        ]

        technical_count = sum(1 for keyword in technical_keywords if keyword in text.lower())
        if technical_count > 2:
            base_score += 0.1

        # Source type bonus
        source_bonuses = {
            "github": 0.1,
            "arxiv": 0.15,
            "research": 0.1,
            "official": 0.1
        }

        for keyword, bonus in source_bonuses.items():
            if keyword in source_type.lower():
                base_score += bonus
                break

        return min(1.0, base_score)

    @staticmethod
    def calculate_relevance_score(text: str) -> float:
        """Calculate relevance to AI/ML field (0-1)"""
        ai_keywords = [
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "transformer", "gpt", "llm", "large language model",
            "generative ai", "agi", "natural language processing", "computer vision",
            "reinforcement learning", "supervised learning", "unsupervised learning",
            "fine-tuning", "prompt engineering", "token", "embedding", "latent",
            "diffusion", "gan", "vae", "bert", "t5", "palm", "claude", "chatgpt",
            "agent", "autonomous", "rlhf", "sft", "pre-training", "foundation model",
            "ai", "ml", "openai", "anthropic", "google ai", "meta ai", "deepmind",
            "huggingface", "stability ai", "midjourney", "runway", "cohere"
        ]

        text_lower = text.lower()
        matches = sum(1 for keyword in ai_keywords if keyword in text_lower)

        # Normalize to 0-1 scale
        relevance = min(1.0, 0.4 + (matches * 0.05))

        return relevance