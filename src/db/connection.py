"""Read-only SQLite connection and per-role TEMP views.

The database is opened with mode=ro via a file: URI, so the process physically
cannot modify data/ridewise.db. On top of that read-only base we create TEMP
views (which live in SQLite's separate, always-writable temp database) that
shadow the real tables:

  - CUSTOMER role: customers / bookings / payments / damage_reports are filtered
    to the session's own customer_id; vehicles is unfiltered.
  - AGENT role: all rows, but the customers view masks PII (phone, email,
    driving_license_no, date_of_birth).

Queries then run against these unqualified view names (enforced by the
validator), so scope and masking are applied in the database layer, not by the
LLM. The session customer_id is validated to a strict format before being
embedded in view DDL (parameters are not allowed in CREATE VIEW).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from src.config import DB_PATH
from src.security.scope import Role, Session

# The only names a query may reference (the TEMP views we create).
ALLOWED_VIEWS = ("customers", "bookings", "payments", "damage_reports", "vehicles")

_CUSTOMER_ID_RE = re.compile(r"^CUST\d{4}$")


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a read-only connection to the RideWise database."""
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}. Copy the provided ridewise.db into "
            f"the data/ folder (see README)."
        )
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_customer_id(customer_id: str | None) -> str:
    if not customer_id or not _CUSTOMER_ID_RE.match(customer_id):
        raise ValueError(f"Invalid customer_id for scoping: {customer_id!r}")
    return customer_id


def _customer_view_ddl(cid: str) -> list[str]:
    """Views filtered to a single customer (CUSTOMER role)."""
    return [
        f"CREATE TEMP VIEW customers AS "
        f"SELECT * FROM main.customers WHERE customer_id = '{cid}'",
        f"CREATE TEMP VIEW bookings AS "
        f"SELECT * FROM main.bookings WHERE customer_id = '{cid}'",
        f"CREATE TEMP VIEW payments AS "
        f"SELECT p.* FROM main.payments p "
        f"JOIN main.bookings b ON p.booking_id = b.booking_id "
        f"WHERE b.customer_id = '{cid}'",
        f"CREATE TEMP VIEW damage_reports AS "
        f"SELECT d.* FROM main.damage_reports d "
        f"JOIN main.bookings b ON d.booking_id = b.booking_id "
        f"WHERE b.customer_id = '{cid}'",
        "CREATE TEMP VIEW vehicles AS SELECT * FROM main.vehicles",
    ]


def _agent_view_ddl() -> list[str]:
    """Views over all rows, with PII masked in customers (AGENT role)."""
    masked_customers = (
        "CREATE TEMP VIEW customers AS SELECT "
        "customer_id, full_name, "
        "'******' || substr(phone, -4) AS phone, "
        "'[masked]' AS email, "
        "city, "
        "'[masked]' AS date_of_birth, "
        "'[masked]' AS driving_license_no, "
        "kyc_status, customer_tier, created_at "
        "FROM main.customers"
    )
    return [
        masked_customers,
        "CREATE TEMP VIEW bookings AS SELECT * FROM main.bookings",
        "CREATE TEMP VIEW payments AS SELECT * FROM main.payments",
        "CREATE TEMP VIEW damage_reports AS SELECT * FROM main.damage_reports",
        "CREATE TEMP VIEW vehicles AS SELECT * FROM main.vehicles",
    ]


def build_role_views(conn: sqlite3.Connection, session: Session) -> None:
    """Create the TEMP views appropriate to the session's role."""
    if session.role is Role.CUSTOMER:
        cid = _safe_customer_id(session.customer_id)
        ddl = _customer_view_ddl(cid)
    elif session.role is Role.AGENT:
        ddl = _agent_view_ddl()
    else:  # pragma: no cover - Role is a closed enum
        raise ValueError(f"Unknown role: {session.role}")
    for stmt in ddl:
        conn.execute(stmt)


def connect_for_session(session: Session, db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a read-only connection with this session's role views installed."""
    conn = connect(db_path)
    build_role_views(conn, session)
    return conn
