"""Five specialized Microsoft Agent Framework agents for order fulfilment."""

import re


def clean_agent_text(text: str | None) -> str:
    """Strip Qwen3 reasoning blocks (both <think>...</think> and orphan leading ...</think>)."""
    if not text:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    if "</think>" in cleaned.lower():
        parts = re.split(r"</think>", cleaned, flags=re.IGNORECASE)
        cleaned = parts[-1]
    return cleaned.strip()
