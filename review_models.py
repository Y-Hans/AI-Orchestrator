"""Data models for Capability 6 — Review & Validation Engine.

Provides strongly typed dataclasses and enums for review evaluation status,
severities, criteria, findings, immutable review results, and review reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


class ReviewStatus(str, Enum):
    """Status of a review evaluation."""
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"


class ReviewSeverity(str, Enum):
    """Severity of a review finding."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ReviewCriterion:
    """Requirement or benchmark against which an output is evaluated."""
    criterion_id: str
    title: str
    description: str | None = None
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "title": self.title,
            "description": self.description,
            "weight": self.weight,
            "metadata": dict(self.metadata),
        }


@dataclass
class ReviewFinding:
    """Individual observation or issue identified during evaluation."""
    criterion_id: str
    severity: ReviewSeverity
    message: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "severity": self.severity.value if hasattr(self.severity, "value") else self.severity,
            "message": self.message,
            "score": self.score,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ReviewResult:
    """Immutable result of a review evaluation."""
    review_id: str
    execution_id: str | None
    status: ReviewStatus
    overall_score: float
    findings: tuple[ReviewFinding, ...]
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "execution_id": self.execution_id,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "overall_score": self.overall_score,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }


@dataclass
class ReviewReport:
    """Structured report produced by the ReviewEngine and stored in TaskWorkspace."""
    report_id: str
    review_result: ReviewResult
    workspace_id: str | None = None
    task_id: str | None = None
    execution_id: str | None = None
    plan_id: str | None = None
    recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "review_result": self.review_result.to_dict(),
            "workspace_id": self.workspace_id,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "recommendations": list(self.recommendations),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }
