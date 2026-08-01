#!/usr/bin/env python3
"""Secret-safe provider verification utility.

This script intentionally performs live provider calls when you run it. It does
not print API keys, authorization headers, raw responses, or provider details
that may contain secrets.
"""

from __future__ import annotations

import socket
import time
import urllib.error
from dataclasses import dataclass
from typing import Any

from ai_orchestrator_mcp import DEFAULT_MODELS, execute_model
from config import config


EXPECTED_REPLY = "Hello from AI Orchestrator"
PROMPT = f"Reply with exactly:\n\n{EXPECTED_REPLY}"

VERIFY_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": DEFAULT_MODELS["groq"],
    "openrouter": DEFAULT_MODELS["openrouter"],
    "ollama": DEFAULT_MODELS["ollama"],
}


@dataclass(frozen=True)
class ProviderCheck:
    name: str
    provider: str
    configured: bool
    missing_key: str | None = None


PROVIDERS = [
    ProviderCheck("Gemini", "gemini", config.is_gemini_configured(), "GEMINI_API_KEY"),
    ProviderCheck("Groq", "groq", config.is_groq_configured(), "GROQ_API_KEY"),
    ProviderCheck("OpenRouter", "openrouter", config.is_openrouter_configured(), "OPENROUTER_API_KEY"),
    ProviderCheck("Ollama", "ollama", bool(config.ollama_base_url)),
]


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def classify_failure(error: str, detail: str) -> str:
    normalized = f"{error} {detail}".lower()
    if error == "missing_api_key":
        return "Missing API key"
    if "401" in normalized or "403" in normalized or "unauthorized" in normalized or "forbidden" in normalized:
        return "Authentication failure"
    if "timed out" in normalized or "timeout" in normalized:
        return "Timeout"
    if "connection" in normalized or "refused" in normalized or "unreachable" in normalized:
        return "Connection failure"
    return "Invalid response"


def is_expected_response(text: str) -> bool:
    return text.strip() == EXPECTED_REPLY


def run_provider(check: ProviderCheck) -> dict[str, Any]:
    model = VERIFY_MODELS[check.provider]
    started = time.perf_counter()

    if check.missing_key and not check.configured:
        return {
            "model": model,
            "latency": None,
            "status": "FAIL",
            "failure": "Missing API key",
            "running": None,
        }

    try:
        result = execute_model({"provider": check.provider, "model": model, "prompt": PROMPT})
    except TimeoutError:
        return failed_result(model, started, "Timeout", check.provider)
    except socket.timeout:
        return failed_result(model, started, "Timeout", check.provider)
    except urllib.error.HTTPError as exc:
        return failed_result(model, started, classify_failure(f"HTTP {exc.code}", ""), check.provider)
    except urllib.error.URLError as exc:
        return failed_result(model, started, classify_failure("connection_error", str(exc.reason)), check.provider)
    except Exception:
        return failed_result(model, started, "Invalid response", check.provider)

    latency = time.perf_counter() - started
    running = None

    if not result.get("ok"):
        failure = classify_failure(str(result.get("error", "")), str(result.get("detail", "")))
        if check.provider == "ollama":
            running = failure not in {"Connection failure", "Timeout"}
        return {
            "model": result.get("model") or model,
            "latency": latency,
            "status": "FAIL",
            "failure": failure,
            "running": running,
        }

    if check.provider == "ollama":
        running = True

    if not is_expected_response(str(result.get("text", ""))):
        return {
            "model": result.get("model") or model,
            "latency": latency,
            "status": "FAIL",
            "failure": "Invalid response",
            "running": running,
        }

    return {
        "model": result.get("model") or model,
        "latency": latency,
        "status": "PASS",
        "failure": None,
        "running": running,
    }


def failed_result(model: str, started: float, failure: str, provider: str) -> dict[str, Any]:
    return {
        "model": model,
        "latency": time.perf_counter() - started,
        "status": "FAIL",
        "failure": failure,
        "running": False if provider == "ollama" and failure in {"Connection failure", "Timeout"} else None,
    }


def print_report() -> None:
    print("=" * 40)
    print("AI Orchestrator Provider Verification")
    print("=" * 40)
    print()

    for check in PROVIDERS:
        result = run_provider(check)
        print(check.name)
        print("-" * len(check.name))
        print(f"Configured : {yes_no(check.configured)}")
        if check.provider == "ollama":
            running = result.get("running")
            print(f"Running    : {yes_no(running) if running is not None else 'Unknown'}")
        print(f"Model      : {result['model']}")
        latency = result.get("latency")
        print(f"Latency    : {latency:.2f} s" if latency is not None else "Latency    : N/A")
        print(f"Status     : {result['status']}")
        if result.get("failure"):
            print(f"Failure    : {result['failure']}")
        print()


def main() -> None:
    print_report()


if __name__ == "__main__":
    main()
