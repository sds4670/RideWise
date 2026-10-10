"""RideWise Assist - Streamlit UI.

Thin front end over src.agent.loop.run_turn. Keeps output minimal: the answer,
plus a "How I got this" expander listing the tool calls, SQL and policy clauses
from the turn's sources. All scope, rules and safety live in the backend.
"""
from __future__ import annotations

import os

import streamlit as st

from src.agent.loop import run_turn
from src.config import DATA_DIR, DB_PATH, load_llm_config
from src.db.connection import connect
from src.security.scope import Role, Session

REQUIRED_PDFS = [
    "01_Rental_Agreement_and_Terms.pdf",
    "02_Cancellation_and_Refund_Policy_v1.pdf",
    "03_Cancellation_and_Refund_Policy_v2.pdf",
    "04_Late_Return_and_Damage_Penalty_Schedule.pdf",
    "05_EV_User_Guide_and_FAQ.pdf",
]

st.set_page_config(page_title="RideWise Assist", page_icon=None)


# --- startup checks (no stack traces in the UI) --------------------------

def _startup_errors() -> list[str]:
    errors: list[str] = []
    if not DB_PATH.exists():
        errors.append(f"Database missing. Copy `ridewise.db` into `{DATA_DIR}`.")
    missing = [p for p in REQUIRED_PDFS if not (DATA_DIR / p).exists()]
    if missing:
        errors.append("Policy PDFs missing from `data/`: " + ", ".join(missing) + ".")
    try:
        load_llm_config()
    except RuntimeError as exc:
        errors.append(str(exc))
    return errors


_errors = _startup_errors()
if _errors:
    st.title("RideWise Assist")
    st.warning("Setup needed before the assistant can start:")
    for e in _errors:
        st.markdown(f"- {e}")
    st.stop()

TOOL_MODE = (os.environ.get("LLM_TOOL_MODE", "native").strip() or "native")


# --- helpers -------------------------------------------------------------

def _customer_exists(customer_id: str) -> bool:
    try:
        conn = connect()
        row = conn.execute(
            "SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:  # noqa: BLE001 - treat any lookup failure as "not found"
        return False


def _reset_chat() -> None:
    st.session_state["turns"] = []


def _render_sources(sources: dict) -> None:
    tool_calls = sources.get("tool_calls") or []
    sqls = sources.get("sql") or []
    clauses = sources.get("policy_clauses") or []
    error = sources.get("error") if os.environ.get("DEBUG_ERRORS") == "1" else None
    if not (tool_calls or sqls or clauses or error):
        return
    with st.expander("How I got this"):
        if error:
            st.caption("Debug (DEBUG_ERRORS=1)")
            st.markdown(f"- Error: `{error.get('type')}: {error.get('message')}`")
        if tool_calls:
            st.caption("Tools")
            for c in tool_calls:
                args = ", ".join(f"{k}={v}" for k, v in (c.get("args") or {}).items())
                st.markdown(f"- `{c['tool']}({args})`")
        if sqls:
            st.caption("SQL")
            for q in sqls:
                st.code(q, language="sql")
        if clauses:
            st.caption("Policy clauses")
            st.markdown(", ".join(clauses))


# --- sidebar -------------------------------------------------------------

st.session_state.setdefault("turns", [])

with st.sidebar:
    st.header("RideWise Assist")
    role = st.radio(
        "Role",
        options=[Role.CUSTOMER.value, Role.AGENT.value],
        format_func=lambda r: "Customer" if r == Role.CUSTOMER.value else "Support Agent",
        key="role",
        on_change=_reset_chat,
    )
    customer_id = ""
    if role == Role.CUSTOMER.value:
        customer_id = st.text_input(
            "Customer ID", placeholder="CUST0001", key="customer_id",
            on_change=_reset_chat,
        ).strip()
    st.button("Start new conversation", on_click=_reset_chat)
    st.caption(f"Tool mode: {TOOL_MODE}. Times shown in IST.")


# --- resolve session -----------------------------------------------------

session: Session | None = None
if role == Role.CUSTOMER.value:
    if not customer_id:
        st.info("Enter your Customer ID in the sidebar to begin (e.g. CUST0001).")
    elif not _customer_exists(customer_id):
        st.error("No account found for that Customer ID. Please check and try again.")
    else:
        session = Session(role=Role.CUSTOMER, customer_id=customer_id)
else:
    session = Session(role=Role.AGENT)


# --- chat ----------------------------------------------------------------

st.title("RideWise Assist")

for turn in st.session_state["turns"]:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        st.markdown(turn["answer"])
        _render_sources(turn["sources"])

prompt = st.chat_input(
    "Ask about a booking, refund, late fee, or policy...",
    disabled=session is None,
)
if prompt and session is not None:
    history: list[dict] = []
    for turn in st.session_state["turns"]:
        history.append({"role": "user", "content": turn["user"]})
        history.append({"role": "assistant", "content": turn["answer"]})

    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Working..."):
            result = run_turn(session, history, prompt, tool_mode=TOOL_MODE)
        st.markdown(result["answer"])
        _render_sources(result["sources"])

    st.session_state["turns"].append(
        {"user": prompt, "answer": result["answer"], "sources": result["sources"]}
    )
