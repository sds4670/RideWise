"""Security: identity/scope enforcement and PII masking.

Identity and scope are enforced here in code, never by the LLM. The active
customer_id comes from the session, never from LLM-supplied arguments.
"""
