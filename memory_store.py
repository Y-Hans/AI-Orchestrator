"""In-memory storage layer for Capability 7 — Long-Term Memory.

Provides a thread-safe MemoryStore class that manages persistent memory records,
deterministic text/tag/type filtering search, status lifecycle operations,
and summary calculations.
"""

from __future__ import annotations

from threading import Lock
from typing import Any, Sequence

from memory_models import (
    MemoryQuery,
    MemoryRecord,
    MemoryResult,
    MemoryStatus,
    MemorySummary,
    MemoryType,
    utc_now,
)


class MemoryStore:
    """Thread-safe in-memory store for MemoryRecord objects."""

    def __init__(self) -> None:
        self._memories: dict[str, MemoryRecord] = {}
        self._lock = Lock()

    def store_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Persist or update a MemoryRecord in the store."""
        with self._lock:
            self._memories[record.memory_id] = record
        return record

    def get_memory(self, memory_id: str) -> MemoryRecord:
        """Retrieve a stored MemoryRecord by its memory_id.

        Raises:
            KeyError: If memory_id does not exist.
        """
        with self._lock:
            record = self._memories.get(memory_id)
        if record is None:
            raise KeyError(f"Memory record not found: {memory_id}")
        return record

    def list_memories(
        self,
        workspace_id: str | None = None,
        memory_type: MemoryType | str | None = None,
        status: MemoryStatus | str | None = None,
    ) -> list[MemoryRecord]:
        """List memory records with optional filtering by workspace, type, and status."""
        target_type = (
            memory_type.value if hasattr(memory_type, "value") else str(memory_type)
        ) if memory_type else None

        target_status = (
            status.value if hasattr(status, "value") else str(status)
        ) if status else None

        with self._lock:
            records = list(self._memories.values())

        filtered: list[MemoryRecord] = []
        for r in records:
            if workspace_id and r.workspace_id != workspace_id:
                continue

            r_type = r.memory_type.value if hasattr(r.memory_type, "value") else str(r.memory_type)
            if target_type and r_type != target_type:
                continue

            r_status = r.status.value if hasattr(r.status, "value") else str(r.status)
            if target_status:
                if r_status != target_status:
                    continue
            else:
                # Default: exclude deleted records unless explicitly requested
                if r_status == MemoryStatus.DELETED.value:
                    continue

            filtered.append(r)

        return filtered

    def search_memories(
        self,
        query: MemoryQuery,
        workspace_id: str | None = None,
    ) -> MemoryResult:
        """Deterministically search memories based on text, types, tags, and workspace."""
        records = self.list_memories(workspace_id=workspace_id)

        target_types = None
        if query.memory_types:
            target_types = {
                t.value if hasattr(t, "value") else str(t)
                for t in query.memory_types
            }

        target_tags = set(query.tags) if query.tags else None
        text_query = query.text.lower().strip() if query.text else None

        matched: list[MemoryRecord] = []
        for r in records:
            r_type = r.memory_type.value if hasattr(r.memory_type, "value") else str(r.memory_type)
            if target_types and r_type not in target_types:
                continue

            if target_tags:
                r_tags = set(r.tags)
                if not target_tags.issubset(r_tags):
                    continue

            if text_query:
                content_str = str(r.content) if r.content is not None else ""
                desc_str = r.description or ""
                searchable_text = f"{r.title} {desc_str} {content_str} {' '.join(r.tags)}".lower()
                if text_query not in searchable_text:
                    continue

            matched.append(r)

        total_matches = len(matched)
        if query.limit is not None and query.limit > 0:
            matched = matched[: query.limit]

        return MemoryResult(
            query=query,
            matches=tuple(matched),
            total_matches=total_matches,
        )

    def archive_memory(self, memory_id: str) -> MemoryRecord:
        """Mark a memory record as ARCHIVED."""
        with self._lock:
            record = self._memories.get(memory_id)
            if record is None:
                raise KeyError(f"Memory record not found: {memory_id}")
            record.status = MemoryStatus.ARCHIVED
            record.updated_at = utc_now()
        return record

    def delete_memory(self, memory_id: str) -> MemoryRecord:
        """Mark a memory record as DELETED (soft delete)."""
        with self._lock:
            record = self._memories.get(memory_id)
            if record is None:
                raise KeyError(f"Memory record not found: {memory_id}")
            record.status = MemoryStatus.DELETED
            record.updated_at = utc_now()
        return record

    def summarize(self, workspace_id: str | None = None) -> MemorySummary:
        """Generate summary metrics for stored memory records."""
        records = self.list_memories(workspace_id=workspace_id)
        if not records:
            return MemorySummary(
                total_memories=0,
                memories_by_type={t.value: 0 for t in MemoryType},
                total_tags=0,
                latest_memory=None,
                oldest_memory=None,
            )

        memories_by_type = {t.value: 0 for t in MemoryType}
        all_tags: set[str] = set()

        for r in records:
            r_type = r.memory_type.value if hasattr(r.memory_type, "value") else str(r.memory_type)
            memories_by_type[r_type] = memories_by_type.get(r_type, 0) + 1
            all_tags.update(r.tags)

        sorted_records = sorted(records, key=lambda x: x.created_at)

        return MemorySummary(
            total_memories=len(records),
            memories_by_type=memories_by_type,
            total_tags=len(all_tags),
            latest_memory=sorted_records[-1],
            oldest_memory=sorted_records[0],
        )


default_memory_store = MemoryStore()
