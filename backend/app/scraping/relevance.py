"""Keyword filter that keeps general-news and trending pages on topic.

STRICT is for outlets like TMZ where "model" or "agent" usually means a person.
BROAD is for code repos, where "agent" and "inference" almost always mean AI.
"""

import re
from enum import StrEnum


class AiFilter(StrEnum):
    NONE = "none"
    STRICT = "strict"
    BROAD = "broad"


# ASCII-only lookarounds so "AI" still matches next to CJK text, which counts as \w.
_ACRONYMS = re.compile(r"(?<![A-Za-z])(AI|A\.I\.|AGI|LLMs?|GPTs?|RAG|MCP)(?![A-Za-z])")

_STRICT_TERMS = re.compile(
    r"\b(artificial intelligence|machine learning|deep learning|neural networks?|chatgpt|openai"
    r"|anthropic|hugging ?face|deepfakes?|chatbots?|generative|large language models?"
    r"|ai agents?|agentic|deepmind|nvidia)\b",
    re.IGNORECASE,
)

_BROAD_TERMS = re.compile(
    r"\b(agents?|multi-agent|inference|embeddings?|transformers?|diffusion|fine-?tun\w*"
    r"|prompts?|claude|codex|copilot|gemini|llama|mistral|ollama|langchain"
    r"|vector (db|database|search)"
    r"|voice cloning|speech|transcription|text-to-\w+|computer vision|model context protocol)\b",
    re.IGNORECASE,
)


def is_ai_related(*texts: str | None, mode: AiFilter = AiFilter.STRICT) -> bool:
    if mode is AiFilter.NONE:
        return True
    text = " ".join(t for t in texts if t)
    if _ACRONYMS.search(text) or _STRICT_TERMS.search(text):
        return True
    return mode is AiFilter.BROAD and bool(_BROAD_TERMS.search(text))


# Trending lists on open hubs regularly include adult models and apps. HangingAi
# embeds live demos, so anything flagged or named like this is dropped at ingest.
_NSFW_TAGS = frozenset({"not-for-all-audiences", "nsfw"})
_NSFW_TERMS = re.compile(
    r"(?<![a-z])(nsfw|uncensored|nude|nudity|naked|porn\w*|hentai|lewd|erotic\w*|18\+|xxx|onlyfans"
    r"|undress\w*)(?![a-z])",
    re.IGNORECASE,
)


def is_safe_for_work(*texts: str | None, tags: list[str] | tuple[str, ...] = ()) -> bool:
    if any(tag.lower() in _NSFW_TAGS for tag in tags):
        return False
    return not _NSFW_TERMS.search(" ".join(t for t in texts if t))
