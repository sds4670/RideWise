"""Configuration loaded from environment variables only.

Secrets (the LLM API key) come from the local .env file, which is gitignored.
Nothing here is ever logged. See .env.example for the expected variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root is two levels up from this file (src/config.py -> project root).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "ridewise.db"
POLICY_RULES_PATH = PROJECT_ROOT / "src" / "rules" / "policy_rules.yaml"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str


def load_llm_config() -> LLMConfig:
    """Read LLM settings from the environment. Raises if any are missing.

    The API key is never printed or logged; only its presence is checked.
    """
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()

    missing = [
        name
        for name, value in (
            ("LLM_BASE_URL", base_url),
            ("LLM_API_KEY", api_key),
            ("LLM_MODEL", model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in the values from NeoStats."
        )
    return LLMConfig(base_url=base_url, api_key=api_key, model=model)
