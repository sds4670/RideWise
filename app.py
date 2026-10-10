"""RideWise Assist - Streamlit UI.

Role selection (Customer / Support Agent), customer identity for the customer
role, a chat window and a "New conversation" reset. The conversation is driven
by src.agent.loop.run_turn. The agent loop is not implemented yet, so a turn
currently reports that clearly rather than pretending to answer.
"""
from __future__ import annotations

import streamlit as st

from src.agent.loop import run_turn
from src.security.scope import Role, Session

st.set_page_config(page_title="RideWise Assist", page_icon=None)


def get_session() -> Session:
    role = Role(st.session_state["role"])
    customer_id = st.session_state.get("customer_id") or None
    return Session(role=role, customer_id=customer_id if role is Role.CUSTOMER else None)


def reset_conversation() -> None:
    st.session_state["history"] = []


with st.sidebar:
    st.header("RideWise Assist")
    st.radio(
        "Role",
        options=[Role.CUSTOMER.value, Role.AGENT.value],
        format_func=lambda r: "Customer" if r == Role.CUSTOMER.value else "Support Agent",
        key="role",
    )
    if st.session_state.get("role") == Role.CUSTOMER.value:
        st.text_input("Customer ID", placeholder="CUST0001", key="customer_id")
    st.button("New conversation", on_click=reset_conversation)

st.session_state.setdefault("history", [])

st.title("RideWise Assist")

for msg in st.session_state["history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask about a booking, refund, late fee, policy...")
if prompt:
    st.session_state["history"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    session = get_session()
    if session.role is Role.CUSTOMER and not session.customer_id:
        reply = "Please enter your Customer ID (for example CUST0001) in the sidebar."
    else:
        try:
            reply = run_turn(session, st.session_state["history"], prompt)
        except NotImplementedError:
            reply = "The assistant is not wired up yet (agent loop pending). UI is working."

    st.session_state["history"].append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)
