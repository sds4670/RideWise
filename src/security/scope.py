"""Role and scope enforcement.

Two roles:
  - CUSTOMER: may read only their own data (the session customer_id) and
    policies. Requests about other customers get a polite refusal that does not
    reveal whether another id exists.
  - AGENT: may read operational data across RideWise, with PII masked by default.

The Session carries the authenticated identity. Tools receive the Session and
derive scope from it; they never trust an LLM-supplied customer_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"


@dataclass(frozen=True)
class Session:
    role: Role
    customer_id: str | None = None  # required for CUSTOMER, None for AGENT


def assert_can_access_customer(session: Session, target_customer_id: str) -> None:
    """Raise PermissionError if the session may not access target_customer_id.

    A CUSTOMER may only access their own id. An AGENT may access any. The DB
    views already enforce this; this is a defence-in-depth check for any code
    path that resolves a customer_id outside a view.
    """
    if session.role is Role.AGENT:
        return
    if session.role is Role.CUSTOMER and session.customer_id == target_customer_id:
        return
    raise PermissionError("Access to this customer's data is not permitted.")
