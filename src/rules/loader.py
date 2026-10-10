"""Load the policy constants from policy_rules.yaml once, as plain dicts."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from src.config import POLICY_RULES_PATH


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    """Return the parsed policy_rules.yaml. Cached for the process lifetime."""
    with open(POLICY_RULES_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
