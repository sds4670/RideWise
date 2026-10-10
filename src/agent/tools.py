"""Tool definitions exposed to the LLM, bound to the session identity.

Each tool is a thin wrapper over src.db.queries / src.rules.engine. Tools take
their scope from the Session (never from an LLM-supplied customer_id), so the
model can ask for data but cannot widen its own access. Tool results are plain
data; free text from the DB is passed through as data, not instructions.
Not yet implemented.
"""
from __future__ import annotations

from src.security.scope import Session  # noqa: F401

# Each entry: OpenAI tool schema + a Python callable(session, **args).
TOOL_SCHEMAS: list[dict] = []


def build_tools(session: Session):
    """Return (schemas, dispatch) bound to this session for the agent loop."""
    raise NotImplementedError
