"""Data models for Capability 5 — Intelligent Task Planner.

Provides strongly-typed abstractions for Objectives, Plans, Planning Levels,
Task Specifications, and immutable Planning Results.
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


class PlanStatus(str, Enum):
    """Lifecycle status of a Plan."""
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    REVISED = "REVISED"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


class LevelType(str, Enum):
    """Generic hierarchy levels within a plan."""
    ROOT = "ROOT"
    GROUP = "GROUP"      # e.g., Phase, Milestone, Feature, Sprint, Stage
    TASK = "TASK"        # Standard task
    SUBTASK = "SUBTASK"  # Fine-grained subtask


@dataclass
class Objective:
    """First-class representation of a user objective."""
    objective_id: str
    workspace_id: str
    title: str
    description: str | None = None
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "description": self.description,
            "constraints": list(self.constraints),
            "success_criteria": list(self.success_criteria),
            "priority": self.priority,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


@dataclass
class TaskSpecification:
    """Strongly typed input specification for creating tasks within a plan level."""
    title: str
    description: str | None = None
    priority: int = 50
    dependencies: list[str] = field(default_factory=list)  # Task titles or IDs
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "dependencies": list(self.dependencies),
            "metadata": dict(self.metadata),
        }


@dataclass
class PlanningLevelSpec:
    """Generic planning level specification (Milestone, Phase, Sprint, Stage, etc.)."""
    title: str
    description: str | None = None
    level_type: LevelType = LevelType.GROUP
    level_name: str = "Phase"  # Customizable label: Milestone, Feature, Sprint, Stage
    priority: int = 50
    tasks: list[TaskSpecification] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "level_type": self.level_type.value if hasattr(self.level_type, "value") else self.level_type,
            "level_name": self.level_name,
            "priority": self.priority,
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class Plan:
    """First-class representation of a generated task plan."""
    plan_id: str
    workspace_id: str
    objective_id: str
    root_task_id: str
    version: int = 1
    status: PlanStatus = PlanStatus.DRAFT
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "workspace_id": self.workspace_id,
            "objective_id": self.objective_id,
            "root_task_id": self.root_task_id,
            "version": self.version,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class PlanningResult:
    """Immutable snapshot returned upon completing a planning operation."""
    plan_id: str
    objective_id: str
    workspace_id: str
    status: PlanStatus
    summary: dict[str, Any]
    statistics: dict[str, Any]
    warnings: tuple[str, ...]
    validation_result: dict[str, Any]
    plan: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective_id": self.objective_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "summary": dict(self.summary),
            "statistics": dict(self.statistics),
            "warnings": list(self.warnings),
            "validation_result": dict(self.validation_result),
            "plan": dict(self.plan),
        }
