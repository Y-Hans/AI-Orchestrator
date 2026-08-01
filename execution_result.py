from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExecutionResult:
    """Strongly typed result of an execution returned by a provider adapter.

    This object is constructed by the provider-specific adapter (e.g., the
    `execute_model` implementation) before being handed to the ExecutionEngine
    for persistence as an `ExecutionRecord`.
    """

    execution_id: str
    provider: str
    model: str | None
    prompt: str
    response: Any = None
    error: Any = None
    latency_ms: int = 0
    success: bool = False
