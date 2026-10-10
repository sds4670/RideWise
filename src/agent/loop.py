"""The agent loop: drives the OpenAI SDK against the NeoStats endpoint.

Flow: build system prompt + tools for the session, send the conversation, run
any tool calls (scoped by the session), feed results back, and return the final
assistant message. The client is configured from env vars via src.config; the
API key is never logged. Not yet implemented.
"""
from __future__ import annotations

from src.security.scope import Session  # noqa: F401


def run_turn(session: Session, history: list[dict], user_message: str) -> str:
    """Run one assistant turn and return the assistant's reply text."""
    raise NotImplementedError
