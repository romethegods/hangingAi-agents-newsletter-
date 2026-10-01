"""Models competing in the Arena. Adding or swapping a model is one entry here.

Prices are USD per million tokens, used to enforce the daily spending cap.
Open models run through Hugging Face's inference router, where the provider
price varies; the figures here are conservative estimates, so the cap errs
on the safe side.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.config import Settings


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"  # OpenAI-compatible router: router.huggingface.co/v1
    DEV = "dev"  # canned, free, local-only stand-ins so the Arena works without keys


@dataclass(frozen=True, slots=True)
class ArenaModel:
    slug: str
    name: str
    maker: str
    provider: Provider
    model_id: str
    open_weights: bool
    input_per_mtok: float
    output_per_mtok: float


MODELS: tuple[ArenaModel, ...] = (
    ArenaModel(
        "claude-haiku-4-5",
        "Claude Haiku 4.5",
        "Anthropic",
        Provider.ANTHROPIC,
        "claude-haiku-4-5",
        False,
        1.00,
        5.00,
    ),
    ArenaModel(
        "gpt-oss-20b",
        "gpt-oss-20b",
        "OpenAI",
        Provider.HUGGINGFACE,
        "openai/gpt-oss-20b",
        True,
        0.20,
        0.80,
    ),
    ArenaModel(
        "llama-3-3-70b",
        "Llama 3.3 70B",
        "Meta",
        Provider.HUGGINGFACE,
        "meta-llama/Llama-3.3-70B-Instruct",
        True,
        0.80,
        0.80,
    ),
    ArenaModel(
        "gemma-4-26b",
        "Gemma 4 26B",
        "Google",
        Provider.HUGGINGFACE,
        "google/gemma-4-26B-A4B-it",
        True,
        0.30,
        0.60,
    ),
    ArenaModel(
        "qwen-3-5-9b",
        "Qwen 3.5 9B",
        "Alibaba",
        Provider.HUGGINGFACE,
        "Qwen/Qwen3.5-9B",
        True,
        0.20,
        0.60,
    ),
    ArenaModel(
        "deepseek-v4-1-flash",
        "DeepSeek V4.1 Flash",
        "DeepSeek",
        Provider.HUGGINGFACE,
        "deepseek-ai/DeepSeek-V4.1-Flash",
        True,
        0.30,
        1.20,
    ),
    ArenaModel(
        "glm-5-3-flash",
        "GLM 5.3 Flash",
        "Zhipu AI",
        Provider.HUGGINGFACE,
        "zai-org/GLM-5.3-Flash",
        True,
        0.30,
        1.20,
    ),
    ArenaModel(
        "dev-steady",
        "Dev Steady (local test model)",
        "HangingAi",
        Provider.DEV,
        "steady",
        True,
        0,
        0,
    ),
    ArenaModel(
        "dev-brisk", "Dev Brisk (local test model)", "HangingAi", Provider.DEV, "brisk", True, 0, 0
    ),
)

MODELS_BY_SLUG = {m.slug: m for m in MODELS}


def enabled_models(settings: Settings) -> list[ArenaModel]:
    """Only models we can actually call: real ones need their key, dev ones are opt-in."""
    available = {
        Provider.ANTHROPIC: bool(settings.anthropic_api_key),
        Provider.HUGGINGFACE: bool(settings.hf_token),
        Provider.DEV: settings.arena_dev_models,
    }
    return [
        m for m in MODELS if available[m.provider] and m.slug not in settings.arena_disabled_models
    ]
