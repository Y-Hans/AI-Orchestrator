# Capability 7 — Long-Term Memory

## Overview

**Capability 7 — Long-Term Memory** introduces persistent knowledge preservation across workspaces and executions in AI-Orchestrator. It acts as the dedicated, persistent knowledge storage layer of the orchestration architecture.

The Memory subsystem **stores and retrieves information only**. It strictly refrains from making planning, scheduling, execution, or review decisions.

---

## Architectural Principles & Guarantees

1. **Dedicated Models Module (`memory_models.py`)**: Defines domain entities (`MemoryType`, `MemoryStatus`, `MemoryRecord`, `MemoryQuery`, `MemoryResult`, `MemorySummary`) as strongly typed dataclasses and enums.
2. **Explicit Memory Store (`memory_store.py`)**: `MemoryStore` is the single owner of stored memories with thread-safe CRUD, status transitions, deterministic searching, and summary generation.
3. **Memory Engine Coordinator (`memory_engine.py`)**: `MemoryEngine` coordinates storage, retrieval, search, and metrics, delegating persistence entirely to `MemoryStore`.
4. **Explicit Workspace Ownership**: `TaskWorkspace` owns its own `MemoryEngine`. Multiple workspaces can share an underlying `MemoryStore`.
5. **Deterministic Retrieval**: Searches match text, memory types, and tags deterministically without non-deterministic side effects or vector models (vector search is postponed to Capability 11–13).
6. **Strict Separation of Concerns**: Memory never executes, reviews, schedules, plans, or retries tasks.

---

## Core Data Models

### `MemoryType`
- `OBJECTIVE`: Goal or high-level milestone definition
- `PLAN`: Decomposed plan structure or strategy snapshot
- `EXECUTION`: Task execution output or context record
- `REVIEW`: Evaluation findings or validation report
- `ARTIFACT`: Domain document or output binary reference
- `TEMPLATE`: Reusable task template or pattern definition
- `NOTE`: Freeform knowledge or contextual observation

### `MemoryStatus`
- `ACTIVE`: Active, queryable memory record
- `ARCHIVED`: Soft-archived historical record
- `DELETED`: Soft-deleted record (excluded from standard listings and searches)

---

## Components

| Component | Responsibility |
|---|---|
| `MemoryRecord` | Strongly typed persistent knowledge item containing `memory_id`, `workspace_id`, `memory_type`, `title`, `description`, `content`, `metadata`, `tags`, `status`, `created_at`, `updated_at`. |
| `MemoryQuery` | Deterministic query object with `text`, `memory_types`, `tags`, `limit`. |
| `MemoryResult` | Immutable query result containing `query`, `matches` tuple, and `total_matches`. |
| `MemorySummary` | Aggregated metrics object detailing memory counts, type distribution, tag counts, latest, and oldest records. |
| `MemoryStore` | Thread-safe in-memory registry enforcing CRUD, deterministic search filtering, status transitions (`archive`, `delete`), and summary calculations. |
| `MemoryEngine` | Coordinator exposing high-level memory primitives (`store_memory`, `retrieve_memory`, `search_memories`, `list_memories`, `delete_memory`, `archive_memory`, `summarize`). |

---

## MCP Tools Integration

Capability 7 registers 7 explicit MCP tools in `ai_orchestrator_mcp.py`:

- `store_memory`: Persist a new knowledge record in a workspace.
- `retrieve_memory`: Fetch a specific record by `memory_id`.
- `search_memories`: Execute deterministic text, type, and tag searches.
- `list_memories`: List stored records with type and status filters.
- `delete_memory`: Soft-delete a memory record by marking its status as `DELETED`.
- `archive_memory`: Archive a memory record by marking its status as `ARCHIVED`.
- `summarize_memories`: Calculate memory summary metrics for a workspace.

---

## Verification

Unit tests in `test_memory_engine.py` verify model serialization, immutability of results, store CRUD operations, text/tag/type searching, status transitions, summary generation, workspace binding, facade routing, and MCP tools.
