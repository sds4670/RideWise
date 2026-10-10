"""The agent loop.

Builds the role system prompt + tools, runs up to 6 tool steps, and returns the
answer with its sources (tool calls, SQL, policy clauses). Works in two modes:
native tool calling (preferred, if the endpoint supports it per the smoke test)
or a JSON-action loop fallback. The LLM call is injectable (``chat_fn``) so the
loop can be tested with a stub and never needs a live endpoint.

Scope is enforced by the session-bound connection and the guards, never by the
model: a cross-scope request is refused before any model call.
"""
from __future__ import annotations

import json
import logging
import re

from src.agent import guards, tools
from src.agent.prompts import system_prompt
from src.db.connection import connect_for_session
from src.security.scope import Session

logger = logging.getLogger("ridewise.agent")

MAX_TOOL_STEPS = 6
HISTORY_MESSAGES = 6  # ~ last 3 exchanges
FALLBACK = ("Sorry, I could not complete that just now. Please try again in a "
            "moment.")

_BOOKING_RE = re.compile(r"B-\d{4}")
_VEHICLE_RE = re.compile(r"VEH\d{3}")

_JSON_INSTRUCTIONS = (
    "\n\nYou do not have native tools. To use a tool, reply with ONLY a JSON "
    'object: {"action":"tool","tool":"<name>","args":{...}}. When you have the '
    'answer, reply with ONLY: {"action":"final","answer":"<text>"}. '
    "Available tools: "
)


def _entity_memory(history: list[dict], user_message: str) -> list[dict]:
    """Add a context note resolving follow-ups to the last booking/vehicle."""
    if _BOOKING_RE.search(user_message):
        return []  # the user named a booking explicitly
    blob = " ".join(m.get("content", "") for m in history)
    bookings = _BOOKING_RE.findall(blob)
    vehicles = _VEHICLE_RE.findall(blob)
    if not bookings:
        return []
    note = f"Context from earlier in this conversation: the booking under " \
           f"discussion is {bookings[-1]}"
    if vehicles:
        note += f" (vehicle {vehicles[-1]})"
    note += ". If the user's message refers to 'it'/'that booking', use this."
    return [{"role": "system", "content": note}]


def _default_chat(messages, tool_schemas):
    from src.llm import chat
    return chat(messages, tools=tool_schemas or None)


def _is_tool_support_error(exc: Exception) -> bool:
    """True if the error looks like the endpoint rejecting tool/function calling."""
    msg = str(exc).lower()
    hits = ("tool", "function call", "function_call", "functions")
    problems = ("not support", "unsupported", "invalid", "not allowed",
                "unrecognized", "bad request", "400")
    return any(h in msg for h in hits) and any(p in msg for p in problems)


def _with_error(sources: dict, exc: Exception) -> dict:
    sources["error"] = {"type": type(exc).__name__, "message": str(exc)[:200]}
    return sources


def _collect_source(sources_acc: dict, name: str, args: dict, result) -> None:
    sources_acc["tool_calls"].append({"tool": name, "args": args})
    if isinstance(result, dict):
        if result.get("sql"):
            sources_acc["sql"].append(result["sql"])
        for clause in result.get("sources", []) or []:
            if clause not in sources_acc["policy_clauses"]:
                sources_acc["policy_clauses"].append(clause)


def run_turn(
    session: Session,
    history: list[dict],
    user_message: str,
    *,
    chat_fn=None,
    tool_mode: str = "native",
    conn=None,
    max_tool_steps: int = MAX_TOOL_STEPS,
) -> dict:
    """Run one assistant turn. Returns {'answer': str, 'sources': {...}}."""
    # Pre-model scope guard: refuse out-of-scope without any model call.
    refusal = guards.out_of_scope_refusal(user_message, session)
    if refusal:
        return {"answer": refusal, "sources": {"tool_calls": [], "sql": [],
                                               "policy_clauses": [], "refused": True}}

    chat_fn = chat_fn or _default_chat
    own_conn = conn is None
    conn = conn or connect_for_session(session)
    try:
        ctx = tools.ToolContext(session=session, conn=conn)
        schemas, dispatch = tools.build_tools(ctx)

        def _build_messages(mode: str) -> list[dict]:
            sys = system_prompt(session.role)
            if mode == "json":
                sys += _JSON_INSTRUCTIONS + ", ".join(
                    s["function"]["name"] for s in schemas)
            msgs = [{"role": "system", "content": sys}]
            msgs += _entity_memory(history, user_message)
            msgs += history[-HISTORY_MESSAGES:]
            msgs.append({"role": "user", "content": user_message})
            return msgs

        def _run(mode: str, sources: dict) -> str:
            messages = _build_messages(mode)
            runner = _run_json if mode == "json" else _run_native
            return runner(chat_fn, messages, schemas, dispatch, sources, max_tool_steps)

        sources = {"tool_calls": [], "sql": [], "policy_clauses": []}
        try:
            answer = _run(tool_mode, sources)
        except Exception as exc:  # noqa: BLE001 - never surface a raw error to the UI
            logger.exception("agent turn failed in %s mode", tool_mode)
            # Auto-fallback: if native tool calling is unsupported, retry in json.
            if tool_mode == "native" and _is_tool_support_error(exc):
                logger.warning("native tool calling unsupported; retrying in json mode")
                sources = {"tool_calls": [], "sql": [], "policy_clauses": [],
                           "auto_json_fallback": True}
                try:
                    answer = _run("json", sources)
                except Exception as exc2:  # noqa: BLE001
                    logger.exception("json fallback also failed")
                    return {"answer": FALLBACK, "sources": _with_error(sources, exc2)}
            else:
                return {"answer": FALLBACK, "sources": _with_error(sources, exc)}

        answer = guards.screen_output(answer or "", session)
        return {"answer": answer, "sources": sources}
    finally:
        if own_conn:
            conn.close()


def _run_native(chat_fn, messages, schemas, dispatch, sources, max_steps) -> str:
    for _ in range(max_steps):
        resp = chat_fn(messages, schemas)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return msg.content or ""
        messages.append({
            "role": "assistant", "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch(name, args)
            _collect_source(sources, name, args, result)
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(guards.sanitize_tool_result(result), default=str),
            })
    # Out of steps: ask for a final answer with no further tools.
    resp = chat_fn(messages, None)
    return resp.choices[0].message.content or ""


def _run_json(chat_fn, messages, schemas, dispatch, sources, max_steps) -> str:
    for _ in range(max_steps):
        resp = chat_fn(messages, None)
        content = (resp.choices[0].message.content or "").strip()
        try:
            action = json.loads(content)
        except json.JSONDecodeError:
            return content  # model answered in plain text
        if action.get("action") == "final":
            return action.get("answer", "")
        name, args = action.get("tool"), action.get("args", {}) or {}
        result = dispatch(name, args)
        _collect_source(sources, name, args, result)
        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": "TOOL_RESULT " + json.dumps(
                guards.sanitize_tool_result(result), default=str),
        })
    resp = chat_fn(messages, None)
    return (resp.choices[0].message.content or "").strip()
