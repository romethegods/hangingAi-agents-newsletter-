"""Stream one model's answer, whatever provider serves it.

Every provider yields text deltas, then one final Usage. Claude goes through
the official Anthropic SDK; open models through Hugging Face's inference router
(an OpenAI-compatible chat-completions API); dev models are canned and local.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache

import anthropic
import httpx

from app.arena.registry import ArenaModel, Provider
from app.config import get_settings

HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"

# Asking models not to self-identify keeps the comparison blind; answers that
# still do are caught by the leak check and not counted.
SYSTEM_PROMPT = (
    "You are one of two anonymous assistants answering the same request in a blind "
    "side-by-side comparison. Answer as helpfully and accurately as you can. Use "
    "Markdown where it helps. Do not mention your name, model, or the company that made you."
)


class ProviderError(Exception):
    """A model couldn't answer (rate limit, outage, refusal...). Message is user-safe."""


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int
    output_tokens: int
    note: str | None = None  # e.g. why an answer stopped early


@lru_cache
def _anthropic() -> anthropic.AsyncAnthropic:
    # max_retries=0: a slow retry would leave one side of a live battle frozen;
    # failing fast lets the reader start a new battle.
    return anthropic.AsyncAnthropic(
        api_key=get_settings().anthropic_api_key, max_retries=0, timeout=60.0
    )


async def _stream_anthropic(
    model: ArenaModel, prompt: str, max_tokens: int
) -> AsyncIterator[str | Usage]:
    try:
        async with _anthropic().messages.stream(
            model=model.model_id,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
    except anthropic.RateLimitError as exc:
        raise ProviderError("this model is busy right now") from exc
    except anthropic.APIStatusError as exc:
        raise ProviderError(f"this model's provider returned an error ({exc.status_code})") from exc
    except anthropic.APIConnectionError as exc:
        raise ProviderError("couldn't reach this model's provider") from exc
    note = {
        "max_tokens": "answer cut off at the Arena's length limit",
        "refusal": "the model declined to answer",
    }.get(final.stop_reason or "")
    yield Usage(final.usage.input_tokens, final.usage.output_tokens, note)


async def _stream_huggingface(
    model: ArenaModel, prompt: str, max_tokens: int
) -> AsyncIterator[str | Usage]:
    body = {
        "model": model.model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    headers = {"Authorization": f"Bearer {get_settings().hf_token}"}
    usage: Usage | None = None
    produced = 0
    finish = None
    try:
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client,
            client.stream("POST", HF_ROUTER_URL, json=body, headers=headers) as response,
        ):
            if response.status_code == 429:
                raise ProviderError("this model is busy right now")
            if response.status_code >= 400:
                raise ProviderError(
                    f"this model's provider returned an error ({response.status_code})"
                )
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if chunk.get("usage"):
                    u = chunk["usage"]
                    usage = Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                for choice in chunk.get("choices", []):
                    finish = choice.get("finish_reason") or finish
                    if text := (choice.get("delta") or {}).get("content"):
                        produced += len(text)
                        yield text
    except httpx.HTTPError as exc:
        raise ProviderError("couldn't reach this model's provider") from exc
    note = "answer cut off at the Arena's length limit" if finish == "length" else None
    # Some providers omit usage; estimate (~4 characters per token) so the budget still counts it.
    yield usage or Usage(len(prompt) // 4, produced // 4, note)


_DEV_REPLIES = {
    "steady": (
        "Here's a careful, structured answer.\n\n"
        "**Short version:** {gist}\n\n"
        "1. Start with the core idea and check your assumptions.\n"
        "2. Try the simplest version that could work.\n"
        "3. Measure, then improve the slowest part.\n\n"
        "_(Local test model: add API keys to battle real models.)_"
    ),
    "brisk": (
        "Quick take: {gist}. Ship a small version today, look at what breaks, and iterate. "
        "Don't over-plan it.\n\n_(Local test model: add API keys to battle real models.)_"
    ),
}


async def _stream_dev(
    model: ArenaModel, prompt: str, max_tokens: int
) -> AsyncIterator[str | Usage]:
    gist = " ".join(prompt.split()[:12]) or "it depends"
    text = _DEV_REPLIES[model.model_id].format(gist=gist)
    for word in text.split(" "):
        await asyncio.sleep(0.02 if model.model_id == "brisk" else 0.04)
        yield word + " "
    yield Usage(len(prompt) // 4, len(text) // 4)


def stream_answer(model: ArenaModel, prompt: str, max_tokens: int) -> AsyncIterator[str | Usage]:
    match model.provider:
        case Provider.ANTHROPIC:
            return _stream_anthropic(model, prompt, max_tokens)
        case Provider.HUGGINGFACE:
            return _stream_huggingface(model, prompt, max_tokens)
        case Provider.DEV:
            return _stream_dev(model, prompt, max_tokens)
    raise ValueError(f"unknown provider {model.provider}")


def cost_usd(model: ArenaModel, usage: Usage) -> float:
    return (
        usage.input_tokens * model.input_per_mtok + usage.output_tokens * model.output_per_mtok
    ) / 1_000_000
