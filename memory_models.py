"""Data models for Capability 7 — Long-Term Memory.

Provides strongly typed dataclasses and enums for memory types, memory status,
memory records, memory queries, search results, and memory summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


class MemoryType(str, Enum):
    """Supported types of stored memory records."""
    OBJECTIVE = "OBJECTIVE"
    PLAN = "PLAN"
    EXECUTION = "EXECUTION"
    REVIEW = "REVIEW"
    ARTIFACT = "ARTIFACT"
    TEMPLATE = "TEMPLATE"
    NOTE = "NOTE"


class MemoryStatus(str, Enum):
    """Lifecycle status of a stored memory record."""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


@dataclass
class MemoryRecord:
    """A single persistent memory item stored within a workspace."""
    memory_id: str
    workspace_id: str
    memory_type: MemoryType
    title: str
    description: str | None = None
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    status: MemoryStatus = MemoryStatus.ACTIVE
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "workspace_id": self.workspace_id,
            "memory_type": self.memory_type.value if hasattr(self.memory_type, "value") else str(self.memory_type),
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "metadata": dict(self.metadata),
            "tags": list(self.tags),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class MemoryQuery:
    """Search query parameters for retrieving memory records."""
    text: str | None = None
    memory_types: list[MemoryType] | list[str] | None = None
    tags: list[str] | None = None
    limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        types_list = None
        if self.memory_types is not None:
            types_list = [
                t.value if hasattr(t, "value") else str(t)
                for t in self.memory_types
            ]
        return {
            "text": self.text,
            "memory_types": types_list,
            "tags": list(self.tags) if self.tags is not None else None,
            "limit": self.limit,
        }


@dataclass(frozen=True)
class MemoryResult:
    """Immutable result set returned from a memory search or query."""
    query: MemoryQuery
    matches: tuple[MemoryRecord, ...]
    total_matches: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query.to_dict(),
            "matches": [m.to_dict() for m in self.matches],
            "total_matches": self.total_matches,
        }


@dataclass
class MemorySummary:
    """Aggregated summary of stored memories."""
    total_memories: int
    memories_by_type: dict[str, int]
    total_tags: int
    latest_memory: MemoryRecord | None = None
    oldest_memory: MemoryRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_memories": self.total_memories,
            "memories_by_type": dict(self.memories_by_type),
            "total_tags": self.total_tags,
            "latest_memory": self.latest_memory.to_dict() if self.latest_memory else None,
            "oldest_memory": self.oldest_memory.to_dict() if self.oldest_memory else None,
        }
