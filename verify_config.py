#!/usr/bin/env python3
"""Print a secret-safe configuration summary."""

from __future__ import annotations

from config import config


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def main() -> None:
    print(f"Gemini configured: {yes_no(config.is_gemini_configured())}")
    print(f"Groq configured: {yes_no(config.is_groq_configured())}")
    print(f"OpenRouter configured: {yes_no(config.is_openrouter_configured())}")
    print(f"Ollama URL: {config.ollama_base_url}")


if __name__ == "__main__":
    main()
