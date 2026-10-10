"""Agent loop tests using a stubbed LLM (no live endpoint).

Covers tool routing, scope enforcement, output screening, and prompt-injection
handling (the mudguard damage report, DMG0003 on B-0412).
"""
import json
import types

import pytest

from src.agent import guards
from src.agent.loop import run_turn
from src.config import DB_PATH
from src.security.scope import Role, Session

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="data/ridewise.db not present")


# --- stub LLM ------------------------------------------------------------

def _tool_call(call_id, name, args):
    fn = types.SimpleNamespace(name=name, arguments=json.dumps(args))
    return types.SimpleNamespace(id=call_id, function=fn)


def _resp(content=None, tool_calls=None):
    msg = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


class StubLLM:
    """Replays a scripted list of responses and records the messages it saw."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []  # messages seen on each call

    def __call__(self, messages, tool_schemas):
        self.calls.append([dict(m) for m in messages])
        return self._responses.pop(0)


# --- tests ---------------------------------------------------------------

def test_tool_routing_and_sources():
    stub = StubLLM([
        _resp(tool_calls=[_tool_call("c1", "get_booking", {"booking_id": "B-0001"})]),
        _resp(content="Your booking B-0001 is completed."),
    ])
    session = Session(role=Role.CUSTOMER, customer_id="CUST0001")  # owns B-0001
    out = run_turn(session, [], "What's the status of B-0001?", chat_fn=stub)
    assert "completed" in out["answer"].lower()
    assert {c["tool"] for c in out["sources"]["tool_calls"]} == {"get_booking"}
    # The tool actually ran against the scoped DB (booking was found).
    tool_msg = next(m for m in stub.calls[1] if m["role"] == "tool")
    assert '"found": true' in tool_msg["content"]


def test_out_of_scope_refusal_skips_model():
    def must_not_call(messages, tool_schemas):
        raise AssertionError("LLM should not be called for out-of-scope requests")

    session = Session(role=Role.CUSTOMER, customer_id="CUST0001")
    out = run_turn(session, [], "Show me CUST0002's phone number", chat_fn=must_not_call)
    assert out["answer"] == guards.REFUSAL
    assert out["sources"].get("refused") is True


def test_output_screening_redacts_other_ids_and_phones():
    stub = StubLLM([_resp(content="Here is CUST0002 and phone 9876543210.")])
    session = Session(role=Role.CUSTOMER, customer_id="CUST0001")
    out = run_turn(session, [], "tell me about my account", chat_fn=stub)
    assert "CUST0002" not in out["answer"]
    assert "9876543210" not in out["answer"]
    assert "[redacted]" in out["answer"]


def test_injection_in_damage_description_is_wrapped_as_data():
    # Agent asks for damage on B-0412; DMG0003 carries an injection in its text.
    stub = StubLLM([
        _resp(tool_calls=[_tool_call("c1", "get_damage", {"booking_id": "B-0412"})]),
        _resp(content="There is one damage report; I will not follow instructions "
                      "embedded in it."),
    ])
    session = Session(role=Role.AGENT)
    out = run_turn(session, [], "Any damage on B-0412?", chat_fn=stub)
    tool_msg = next(m for m in stub.calls[1] if m["role"] == "tool")
    # The injected instruction is present but fenced as untrusted data.
    assert guards.UNTRUSTED_OPEN in tool_msg["content"]
    assert "Ignore previous instructions" in tool_msg["content"]
    idx_open = tool_msg["content"].index(guards.UNTRUSTED_OPEN)
    idx_inj = tool_msg["content"].index("Ignore previous instructions")
    assert idx_open < idx_inj  # wrapped before the injected text
    assert "will not follow" in out["answer"]


def test_json_action_mode():
    stub = StubLLM([
        _resp(content=json.dumps({"action": "tool", "tool": "get_booking",
                                  "args": {"booking_id": "B-0001"}})),
        _resp(content=json.dumps({"action": "final", "answer": "Done."})),
    ])
    session = Session(role=Role.CUSTOMER, customer_id="CUST0001")
    out = run_turn(session, [], "status of B-0001?", chat_fn=stub, tool_mode="json")
    assert out["answer"] == "Done."
    assert out["sources"]["tool_calls"][0]["tool"] == "get_booking"
