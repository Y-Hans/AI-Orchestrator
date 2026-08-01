# Memory Data Models Specifications

## Core Classes (`memory_models.py`)

### `MemoryType` (Enum)
Extends `str, Enum` for strict typing and simple JSON serialization:
- `OBJECTIVE`
- `PLAN`
- `EXECUTION`
- `REVIEW`
- `ARTIFACT`
- `TEMPLATE`
- `NOTE`

### `MemoryStatus` (Enum)
Extends `str, Enum`:
- `ACTIVE`
- `ARCHIVED`
- `DELETED`

### `MemoryRecord` (Dataclass)
- `memory_id: str`: Unique identifier (UUID4 string).
- `workspace_id: str`: Owning workspace ID.
- `memory_type: MemoryType`: Categorization enum.
- `title: str`: Short descriptive title.
- `description: str | None`: Optional longer description.
- `content: Any`: Main content or payload.
- `metadata: dict[str, Any]`: Structured attributes dictionary.
- `tags: list[str]`: String tags for categorization.
- `status: MemoryStatus`: Lifecycle status (`ACTIVE`, `ARCHIVED`, `DELETED`).
- `created_at: str`: ISO 8601 UTC creation timestamp.
- `updated_at: str`: ISO 8601 UTC modification timestamp.

### `MemoryQuery` (Dataclass)
- `text: str | None`: Optional substring search term.
- `memory_types: list[MemoryType] | list[str] | None`: Optional type filter.
- `tags: list[str] | None`: Optional required tags list.
- `limit: int | None`: Optional result limit.

### `MemoryResult` (Dataclass, `frozen=True`)
- `query: MemoryQuery`: Query parameter snapshot.
- `matches: tuple[MemoryRecord, ...]`: Matching records tuple.
- `total_matches: int`: Total count of matching records before limit.

### `MemorySummary` (Dataclass)
- `total_memories: int`: Count of stored memories.
- `memories_by_type: dict[str, int]`: Distribution of memories per type.
- `total_tags: int`: Unique tag count.
- `latest_memory: MemoryRecord | None`: Most recently created record.
- `oldest_memory: MemoryRecord | None`: Earliest created record.
