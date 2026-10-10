"""Thin wrapper around the OpenAI SDK pointed at the NeoStats endpoint.

Responsibilities:
  - build a client from env-only config (key never logged);
  - set a request timeout and retry transient failures a few times;
  - on unrecoverable failure, return a graceful fallback message instead of
    raising into the UI.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from openai import OpenAI

from src.config import LLMConfig, load_llm_config

logger = logging.getLogger("ridewise.llm")

REQUEST_TIMEOUT_S = 30.0
MAX_RETRIES = 2            # retries on top of the first attempt
RETRY_BACKOFF_S = 1.5
FALLBACK_MESSAGE = (
    "Sorry, I could not reach the assistant service just now. Please try again "
    "in a moment."
)


@dataclass
class LLMResult:
    ok: bool
    message: str          # assistant text, or the fallback message on failure
    raw: object = None    # the raw SDK response when ok, else None
    error: str | None = None


def get_client(cfg: LLMConfig | None = None) -> OpenAI:
    """Construct an OpenAI client for the NeoStats endpoint."""
    cfg = cfg or load_llm_config()
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=REQUEST_TIMEOUT_S)


def chat(messages: list[dict], *, tools: list[dict] | None = None,
         cfg: LLMConfig | None = None, client: OpenAI | None = None):
    """Call chat.completions with retry. Returns the raw SDK response.

    Raises the last exception if all attempts fail; callers that must not raise
    should use chat_safe().
    """
    cfg = cfg or load_llm_config()
    client = client or get_client(cfg)
    kwargs: dict = {"model": cfg.model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surface after retries
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def chat_safe(messages: list[dict], *, tools: list[dict] | None = None,
              cfg: LLMConfig | None = None, client: OpenAI | None = None) -> LLMResult:
    """Like chat() but never raises: returns LLMResult with a fallback on error."""
    try:
        resp = chat(messages, tools=tools, cfg=cfg, client=client)
        text = resp.choices[0].message.content or ""
        return LLMResult(ok=True, message=text, raw=resp)
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM call failed; using fallback message")
        return LLMResult(ok=False, message=FALLBACK_MESSAGE, error=str(exc))
