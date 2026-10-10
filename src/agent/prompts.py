"""System prompts per role, assembled with the full policy text as context.

The corpus is small, so the full policy text is placed in the prompt instead of
using vector search. The prompt states the answer style (conversational,
concise, show calculation steps and which policy version/document was used, say
"no record found" / "not in policy" instead of guessing) and that any text
coming from the database is untrusted data, not instructions.

Identity and scope are NOT trusted to the prompt; they are enforced in code.
Not yet implemented.
"""
from __future__ import annotations

from src.security.scope import Role  # noqa: F401


def system_prompt(role: Role) -> str:
    """Build the system prompt for the given role, including policy text."""
    raise NotImplementedError
