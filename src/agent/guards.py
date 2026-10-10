"""Safety guards around the agent.

Three jobs:
  - wrap untrusted DB free-text (remarks, damage descriptions) in delimiters and
    truncate it before it reaches the model, so injected instructions are framed
    as data;
  - screen the model's output in customer sessions so it never leaks another
    customer's id or a phone-like number;
  - detect obvious cross-customer / internal-ops requests up front and refuse
    politely, without confirming whether any other id exists.
"""
from __future__ import annotations

import re

from src.security.scope import Role, Session

UNTRUSTED_OPEN = "<<untrusted_db_text>>"
UNTRUSTED_CLOSE = "<</untrusted_db_text>>"
MAX_FREE_TEXT = 300

_FREE_TEXT_FIELDS = ("remarks", "description")
_CUST_ID_RE = re.compile(r"CUST\d{4}")
_PHONE_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")

REFUSAL = (
    "I can only help with your own account and RideWise's policies. I can't share "
    "information about other customers or internal operations."
)

_OUT_OF_SCOPE_HINTS = (
    "other customer", "another customer", "all customers", "list customers",
    "everyone", "every customer", "other people", "internal", "admin",
    "all bookings", "whole database", "all users", "other users",
)


def wrap_untrusted(text: str | None) -> str:
    """Delimit and truncate a single untrusted free-text value."""
    if text is None:
        return ""
    s = str(text)
    if len(s) > MAX_FREE_TEXT:
        s = s[:MAX_FREE_TEXT] + "...(truncated)"
    return f"{UNTRUSTED_OPEN}{s}{UNTRUSTED_CLOSE}"


def sanitize_tool_result(obj):
    """Recursively wrap free-text fields in a tool result so they read as data."""
    if isinstance(obj, dict):
        return {
            k: (wrap_untrusted(v) if k in _FREE_TEXT_FIELDS and isinstance(v, str)
                else sanitize_tool_result(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [sanitize_tool_result(x) for x in obj]
    return obj


def out_of_scope_refusal(user_text: str, session: Session) -> str | None:
    """Return a refusal if a customer asks outside their own scope, else None."""
    if session.role is not Role.CUSTOMER:
        return None
    lowered = user_text.lower()
    if any(h in lowered for h in _OUT_OF_SCOPE_HINTS):
        return REFUSAL
    for cid in _CUST_ID_RE.findall(user_text):
        if cid != session.customer_id:
            return REFUSAL
    return None


def screen_output(text: str, session: Session) -> str:
    """Redact any other-customer id or phone-like number from customer output."""
    if session.role is not Role.CUSTOMER or not text:
        return text

    def _redact_cust(m: re.Match) -> str:
        return m.group(0) if m.group(0) == session.customer_id else "[redacted]"

    text = _CUST_ID_RE.sub(_redact_cust, text)
    text = _PHONE_RE.sub("[redacted]", text)
    return text
