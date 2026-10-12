"""RAG_MODE controls whether the full policy text is in the system prompt."""
import os

from src.agent.prompts import system_prompt
from src.security.scope import Role

FULL_TEXT_MARKER = "48 hours or more"   # only present when full policy text is inlined


def test_rag_mode_omits_full_policy_text(monkeypatch):
    monkeypatch.setenv("RAG_MODE", "rag")
    p = system_prompt(Role.AGENT)
    assert FULL_TEXT_MARKER not in p
    assert "POLICY INDEX" in p
    assert "search_policy" in p


def test_full_mode_includes_full_policy_text(monkeypatch):
    monkeypatch.setenv("RAG_MODE", "full")
    p = system_prompt(Role.CUSTOMER)
    assert FULL_TEXT_MARKER in p
