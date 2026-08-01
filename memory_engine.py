"""Memory engine coordinator for Capability 7 — Long-Term Memory.

Coordinates memory operations (storage, retrieval, deterministic search,
summarization, lifecycle management) by delegating persistence to a MemoryStore.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from memory_models import (
    MemoryQuery,
    MemoryRecord,
    MemoryResult,
    MemoryStatus,
    MemorySummary,
    MemoryType,
    utc_now,
)
from memory_store import MemoryStore, default_memory_store


class MemoryEngine:
    """Coordinator for long-term memory operations.

    Delegates persistence to an explicit MemoryStore. Does not execute, plan,
    schedule, or review tasks.
    """

    def __init__(
        self,
        memory_store: MemoryStore | None = None,
        workspace: Any = None,
    ) -> None:
        self.store = memory_store or default_memory_store
        self._workspace = workspace

    def _effective_workspace_id(self, workspace_id: str | None) -> str:
        if workspace_id:
            return workspace_id
        if self._workspace and hasattr(self._workspace, "workspace_id"):
            return str(self._workspace.workspace_id)
        return ""

    def store_memory(
        self,
        title: str,
        content: Any,
        memory_type: MemoryType | str = MemoryType.NOTE,
        workspace_id: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        """Create and persist a new MemoryRecord in the MemoryStore."""
        effective_ws_id = self._effective_workspace_id(workspace_id)

        if isinstance(memory_type, str):
            try:
                mtype = MemoryType(memory_type.upper())
            except ValueError:
                mtype = MemoryType.NOTE
        else:
            mtype = memory_type

        now = utc_now()
        record = MemoryRecord(
            memory_id=str(uuid4()),
            workspace_id=effective_ws_id,
            memory_type=mtype,
            title=title,
            description=description,
            content=content,
            metadata=dict(metadata) if metadata else {},
            tags=list(tags) if tags else [],
            status=MemoryStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        return self.store.store_memory(record)

    def retrieve_memory(self, memory_id: str) -> MemoryRecord:
        """Retrieve a specific memory record by ID."""
        return self.store.get_memory(memory_id)

    def search_memories(
        self,
        text: str | None = None,
        memory_types: list[MemoryType | str] | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
        workspace_id: str | None = None,
    ) -> MemoryResult:
        """Search memory records deterministically."""
        effective_ws_id = self._effective_workspace_id(workspace_id) or None

        parsed_types: list[MemoryType] | None = None
        if memory_types:
            parsed_types = []
            for t in memory_types:
                if isinstance(t, str):
                    try:
                        parsed_types.append(MemoryType(t.upper()))
                    except ValueError:
                        pass
                else:
                    parsed_types.append(t)

        query = MemoryQuery(
            text=text,
            memory_types=parsed_types,
            tags=tags,
            limit=limit,
        )
        return self.store.search_memories(query, workspace_id=effective_ws_id)

    def list_memories(
        self,
        workspace_id: str | None = None,
        memory_type: MemoryType | str | None = None,
        status: MemoryStatus | str | None = None,
    ) -> list[MemoryRecord]:
        """List stored memory records."""
        effective_ws_id = self._effective_workspace_id(workspace_id) or None
        return self.store.list_memories(
            workspace_id=effective_ws_id,
            memory_type=memory_type,
            status=status,
        )

    def delete_memory(self, memory_id: str) -> MemoryRecord:
        """Mark a memory record as DELETED."""
        return self.store.delete_memory(memory_id)

    def archive_memory(self, memory_id: str) -> MemoryRecord:
        """Mark a memory record as ARCHIVED."""
        return self.store.archive_memory(memory_id)

    def summarize(self, workspace_id: str | None = None) -> MemorySummary:
        """Generate a summary of stored memory metrics."""
        effective_ws_id = self._effective_workspace_id(workspace_id) or None
        return self.store.summarize(workspace_id=effective_ws_id)
