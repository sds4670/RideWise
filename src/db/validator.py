"""SQL validation and safe execution for LLM-proposed queries.

A query is allowed only if it is exactly one SELECT statement that references
nothing but the allowlisted role views (unqualified names). Everything else -
writes, PRAGMA, ATTACH, multiple statements, qualified table names that could
bypass the views - is rejected before the query ever reaches SQLite. A row LIMIT
is enforced, and execution is bounded by a wall-clock timeout via a progress
handler.
"""
from __future__ import annotations

import sqlite3
import time

import sqlglot
from sqlglot import exp

from src.db.connection import ALLOWED_VIEWS

DEFAULT_MAX_ROWS = 200
DEFAULT_TIMEOUT_S = 5.0


class SQLValidationError(ValueError):
    """Raised when a proposed query is not allowed."""


def validate_sql(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> str:
    """Validate a single read-only SELECT and return it with a LIMIT enforced.

    Raises SQLValidationError on anything disallowed.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("Empty query.")

    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except Exception as exc:  # noqa: BLE001
        raise SQLValidationError(f"Could not parse SQL: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLValidationError("Exactly one statement is allowed.")

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        raise SQLValidationError("Only a single SELECT statement is allowed.")

    # Defence in depth: reject any command/DDL/DML/PRAGMA/ATTACH nodes anywhere.
    forbidden = (
        exp.Command, exp.Pragma, exp.Insert, exp.Update, exp.Delete,
        exp.Create, exp.Drop, exp.Alter, exp.Attach if hasattr(exp, "Attach") else exp.Command,
    )
    for node in stmt.walk():
        if isinstance(node, forbidden):
            raise SQLValidationError(f"Disallowed statement element: {type(node).__name__}.")

    # Every referenced table must be an allowlisted view, with no db/catalog qualifier.
    for table in stmt.find_all(exp.Table):
        if table.args.get("catalog") or table.args.get("db"):
            raise SQLValidationError(
                f"Qualified table names are not allowed: {table.sql()}."
            )
        if table.name not in ALLOWED_VIEWS:
            raise SQLValidationError(
                f"Table/view not allowed: {table.name!r}. "
                f"Allowed: {', '.join(ALLOWED_VIEWS)}."
            )

    # Enforce a row LIMIT if the query does not already set one.
    if stmt.args.get("limit") is None:
        stmt = stmt.limit(max_rows)

    return stmt.sql(dialect="sqlite")


def run_query(
    conn: sqlite3.Connection,
    sql: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> list[dict]:
    """Validate and execute a query on a role-scoped connection.

    Returns up to max_rows rows as dicts. Raises SQLValidationError if the query
    is not allowed, or TimeoutError if it exceeds the time budget.
    """
    safe_sql = validate_sql(sql, max_rows=max_rows)

    deadline = time.monotonic() + timeout_s

    def _guard() -> int:
        return 1 if time.monotonic() > deadline else 0

    conn.set_progress_handler(_guard, 10_000)
    try:
        cur = conn.execute(safe_sql)
        rows = cur.fetchmany(max_rows)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise TimeoutError(f"Query exceeded {timeout_s}s time budget.") from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)

    return [dict(r) for r in rows]
