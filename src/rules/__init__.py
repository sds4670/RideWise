"""Deterministic rules engine: rental charges, refunds, late fees, penalties.

All money math lives here (not in the LLM) and reads its constants from
policy_rules.yaml. Every function is pure and unit-testable.
"""
