"""Central configuration for provider credentials and endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


@dataclass(frozen=True)
class ProviderConfig:
    gemini_api_key: str
    groq_api_key: str
    openrouter_api_key: str
    ollama_base_url: str

    def is_gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    def is_groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    def is_openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key)

    def missing_required(self) -> list[str]:
        missing = []
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if not self.openrouter_api_key:
            missing.append("OPENROUTER_API_KEY")
        if not self.ollama_base_url:
            missing.append("OLLAMA_BASE_URL")
        return missing


def load_config() -> ProviderConfig:
    load_dotenv(ENV_FILE)

    import os

    return ProviderConfig(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        groq_api_key=os.environ.get("GROQ_API_KEY", "").strip(),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip() or DEFAULT_OLLAMA_BASE_URL,
    )


config = load_config()
