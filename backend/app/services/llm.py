"""Server-side NVIDIA LLM provider (Step 2).

Small module used by the AI helper. Never logs or formats the API key.
"""

import asyncio
import time

import httpx

from app.core.config import settings


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM provider cannot serve a request."""


def _require_key() -> str:
    key = settings.NVIDIA_API_KEY
    if not key:
        raise LLMUnavailableError(
            "NVIDIA_API_KEY is not set; the AI helper is unavailable. "
            "Set NVIDIA_API_KEY in backend/.env."
        )
    return key


def candidate_models() -> list[str]:
    """Step 3 benchmark candidate model ids, in order."""
    return [
        "nvidia/nemotron-3-nano-30b-a3b",
        "openai/gpt-oss-20b",
        "nvidia/nemotron-3-super-120b-a12b",
        "meta/llama-3.3-70b-instruct",
    ]


def _is_retryable_status(status: int) -> bool:
    return status == 429 or status >= 500


async def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    timeout_seconds: float = 60.0,
) -> dict:
    """Call the NVIDIA chat-completions endpoint with retries/fallback.

    Returns {"text": str, "model": str, "latency_seconds": float}.
    Raises LLMUnavailableError on missing key or exhausted retries.
    """
    api_key = _require_key()
    base_url = settings.NVIDIA_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"
    if model:
        models = [model]
    else:
        models = [settings.NVIDIA_MODEL_FAST, settings.NVIDIA_MODEL_STRONG]

    backoffs = (1.0, 2.0, 4.0)
    last_status: int | None = None
    last_exc: str | None = None

    headers = {"Authorization": "Bearer " + api_key}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for model_id in models:
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            for attempt in range(3):
                start = time.monotonic()
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exc = type(exc).__name__
                    last_status = None
                    if attempt < 2:
                        await asyncio.sleep(backoffs[attempt])
                    continue
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"].get("content") or ""
                    latency = time.monotonic() - start
                    return {
                        "text": content,
                        "model": model_id,
                        "latency_seconds": round(latency, 3),
                    }
                if not _is_retryable_status(response.status_code):
                    raise LLMUnavailableError(
                        f"LLM provider returned HTTP {response.status_code}"
                    )
                last_status = response.status_code
                last_exc = None
                if attempt < 2:
                    await asyncio.sleep(backoffs[attempt])

    if last_status is not None:
        raise LLMUnavailableError(
            f"LLM provider unavailable after retries (last HTTP {last_status})"
        )
    raise LLMUnavailableError(
        f"LLM provider unavailable after retries (last error {last_exc or 'unknown'})"
    )
