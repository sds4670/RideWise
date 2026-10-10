"""PII masking for the AGENT role.

Phone, email, driving licence and date of birth are masked by default so an
agent sees enough to identify a record without exposing full personal data.
Not yet implemented.
"""
from __future__ import annotations

PII_FIELDS = ("phone", "email", "driving_license_no", "date_of_birth")


def mask_customer(row: dict) -> dict:
    """Return a copy of a customer row with PII fields masked."""
    raise NotImplementedError
