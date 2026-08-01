"""Data models for Capability 8 — Result Synthesis Engine.

Provides strongly typed dataclasses and enums for synthesis status,
source types, synthesis sources, immutable synthesis results, and synthesis reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


class SynthesisStatus(str, Enum):
    """Status of a result synthesis operation."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SynthesisSourceType(str, Enum):
    """Supported source categories for result synthesis."""
    EXECUTION = "EXECUTION"
    REVIEW = "REVIEW"
    ARTIFACT = "ARTIFACT"
    MEMORY = "MEMORY"


@dataclass
class SynthesisSource:
    """Reference to an input item consumed during result synthesis."""
    source_type: SynthesisSourceType
    source_id: str
    title: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type.value if hasattr(self.source_type, "value") else str(self.source_type),
            "source_id": self.source_id,
            "title": self.title,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SynthesisResult:
    """Immutable deliverable produced by a Synthesizer."""
    synthesis_id: str
    title: str
    summary: str
    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "metadata": dict(self.metadata),
        }


@dataclass
class SynthesisReport:
    """Structured synthesis report stored within a TaskWorkspace."""
    report_id: str
    workspace_id: str
    status: SynthesisStatus
    result: SynthesisResult | None
    sources: list[SynthesisSource] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "result": self.result.to_dict() if self.result is not None else None,
            "sources": [s.to_dict() for s in self.sources],
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }
