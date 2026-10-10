"""DB layer: role scoping, PII masking, and SQL validation.

Uses the real data/ridewise.db (read-only). Skips if the DB has not been copied
into data/ yet.
"""
import pytest

from src.config import DB_PATH
from src.db.connection import connect_for_session
from src.db.validator import SQLValidationError, run_query, validate_sql
from src.security.scope import Role, Session

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="data/ridewise.db not present"
)

CUST = "CUST0001"


@pytest.fixture
def customer_conn():
    conn = connect_for_session(Session(role=Role.CUSTOMER, customer_id=CUST))
    yield conn
    conn.close()


@pytest.fixture
def agent_conn():
    conn = connect_for_session(Session(role=Role.AGENT))
    yield conn
    conn.close()


# --- scoping -------------------------------------------------------------

def test_customer_sees_only_own_record(customer_conn):
    rows = run_query(customer_conn, "SELECT customer_id FROM customers")
    assert {r["customer_id"] for r in rows} == {CUST}


def test_customer_bookings_are_scoped(customer_conn):
    rows = run_query(customer_conn, "SELECT DISTINCT customer_id FROM bookings")
    assert {r["customer_id"] for r in rows} <= {CUST}


def test_customer_cannot_see_other_customer_even_if_asked(customer_conn):
    # Explicit cross-customer attempt returns nothing, not an error, and never
    # reveals whether the other id exists.
    rows = run_query(
        customer_conn,
        "SELECT * FROM customers WHERE customer_id = 'CUST0002'",
    )
    assert rows == []


def test_customer_payments_scoped_via_join(customer_conn):
    rows = run_query(customer_conn, "SELECT booking_id FROM payments LIMIT 5")
    # Every payment's booking must belong to this customer.
    bookings = {
        r["booking_id"]
        for r in run_query(customer_conn, "SELECT booking_id FROM bookings")
    }
    assert all(r["booking_id"] in bookings for r in rows)


# --- masking -------------------------------------------------------------

def test_agent_pii_is_masked(agent_conn):
    row = run_query(agent_conn, "SELECT * FROM customers LIMIT 1")[0]
    assert row["email"] == "[masked]"
    assert row["driving_license_no"] == "[masked]"
    assert row["date_of_birth"] == "[masked]"
    assert row["phone"].startswith("******")


def test_agent_sees_all_customers(agent_conn):
    n = run_query(agent_conn, "SELECT COUNT(*) AS n FROM customers")[0]["n"]
    assert n > 1


# --- validator -----------------------------------------------------------

@pytest.mark.parametrize(
    "bad_sql",
    [
        "SELECT 1; DROP TABLE customers",          # multiple statements
        "UPDATE customers SET city='x'",            # write
        "DELETE FROM bookings",                     # write
        "PRAGMA table_info(customers)",             # pragma
        "ATTACH DATABASE 'x.db' AS y",              # attach
        "SELECT * FROM main.customers",             # qualified bypass of view
        "SELECT * FROM sqlite_master",              # non-allowlisted table
        "SELECT * FROM users",                      # unknown table
    ],
)
def test_validator_rejects(bad_sql):
    with pytest.raises(SQLValidationError):
        validate_sql(bad_sql)


def test_validator_adds_limit():
    out = validate_sql("SELECT * FROM customers")
    assert "LIMIT" in out.upper()


def test_validator_allows_plain_select():
    out = validate_sql("SELECT customer_id FROM customers WHERE city = 'Bengaluru'")
    assert out.strip().upper().startswith("SELECT")
