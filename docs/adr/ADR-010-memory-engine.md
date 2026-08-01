# ADR-010: Architecture of Long-Term Memory Engine

## Context

AI-Orchestrator requires persistent knowledge retention across execution runs and task workspaces. As the OS framework expands, AI agents need to persist and query domain artifacts, plans, execution outputs, reviews, templates, objectives, and freeform notes without violating core architectural constraints.

## Decision

We implement **Capability 7 — Long-Term Memory** following strict separation of concerns and deterministic retrieval principles:

1. **Dedicated Models Module (`memory_models.py`)**: All domain entities are defined as strongly typed dataclasses and enums (`MemoryType`, `MemoryStatus`, `MemoryRecord`, `MemoryQuery`, `MemoryResult`, `MemorySummary`).
2. **Explicit `MemoryStore` (`memory_store.py`)**: A thread-safe, in-memory store acts as the single authority for record persistence, status mutation, deterministic query filtering, and summary calculation.
3. **`MemoryEngine` Coordinator (`memory_engine.py`)**: Coordinates storage, retrieval, search, and metrics, delegating all persistence to `MemoryStore`.
4. **TaskWorkspace Integration**: Each `TaskWorkspace` owns its `MemoryEngine` instance.
5. **Deterministic Searching Only**: In Capability 7, search is strictly deterministic (text substring matching, type filtering, tag matching). Vector search and embeddings are explicitly postponed to Capabilities 11–13.
6. **Facade & MCP Interfaces**: `AntigravityBrain` and `ai_orchestrator_mcp.py` expose 7 explicit primitives: `store_memory`, `retrieve_memory`, `search_memories`, `list_memories`, `delete_memory`, `archive_memory`, `summarize_memories`.

## Consequences

### Positive
- Strict architectural isolation: Memory logic never executes, schedules, plans, or reviews tasks.
- 100% thread-safe in-memory operations without external database overhead for Cap 7.
- Complete backward compatibility with existing capabilities 1–6.
- Strongly typed data structures guarantee API stability.

### Negative / Limitations
- Advanced semantic capabilities (vector embeddings, distance metrics) are not present in Capability 7.
- In-memory store resets on process termination (persistent DB backends belong to future capability tiers).
