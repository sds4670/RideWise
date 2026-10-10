"""Smoke test for the NeoStats LLM endpoint.

Run:  python -m scripts.smoke_llm

Checks, in order:
  1. Config present (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in .env).
  2. A basic chat completion returns text.
  3. Whether the endpoint supports tool/function calling (returns a tool_call).

Prints a short report. Never prints the API key. Exits 0 if config is present
and the basic call works, 1 otherwise, so it can gate later work.
"""
from __future__ import annotations

import json
import sys

from src.config import load_llm_config
from src.llm import chat, get_client

PING_MESSAGES = [
    {"role": "user", "content": "Reply with exactly the word: pong"},
]

TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two integers and return the sum.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        },
    }
]
TOOL_MESSAGES = [
    {"role": "user", "content": "Use the add tool to add 2 and 3. Call the tool."},
]


def main() -> int:
    print("== RideWise LLM smoke test ==")

    # 1. Config
    try:
        cfg = load_llm_config()
    except RuntimeError as exc:
        print("[1] config: MISSING")
        print("    ", exc)
        print("Result: cannot run LLM checks without credentials.")
        return 1
    print(f"[1] config: OK (base_url set, model={cfg.model}, key hidden)")

    client = get_client(cfg)

    # 2. Basic completion
    try:
        resp = chat(PING_MESSAGES, client=client, cfg=cfg)
        text = (resp.choices[0].message.content or "").strip()
        print(f"[2] basic completion: OK -> {text!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"[2] basic completion: FAILED -> {type(exc).__name__}: {exc}")
        return 1

    # 3. Tool / function calling
    try:
        resp = chat(TOOL_MESSAGES, tools=TOOL_SCHEMA, client=client, cfg=cfg)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            call = tool_calls[0]
            args = call.function.arguments
            print(f"[3] tool calling: SUPPORTED -> {call.function.name}({args})")
            try:
                print(f"    parsed args: {json.loads(args)}")
            except Exception:  # noqa: BLE001
                pass
        else:
            print("[3] tool calling: NOT USED (model answered in text instead)")
            print(f"    content: {(msg.content or '').strip()!r}")
            print("    -> may need prompt-driven tool use rather than native tools.")
    except Exception as exc:  # noqa: BLE001
        print(f"[3] tool calling: ERROR -> {type(exc).__name__}: {exc}")
        print("    -> endpoint may not accept the tools parameter.")

    print("Result: endpoint reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
