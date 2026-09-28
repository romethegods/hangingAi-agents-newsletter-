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
