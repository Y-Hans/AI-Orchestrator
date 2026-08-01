# ADR-009: Capability 6 — Review & Validation Engine Architecture

## Status
Accepted

## Context
AI-Orchestrator requires a dedicated evaluation subsystem to assess completed task execution outputs against defined criteria, generate structured validation reports, produce deterministic review scores, and record review history. Capabilities 1–5 established frozen primitives (TaskWorkspace, TaskGraph, TaskNode, TaskEdge, ExecutionEngine, DependencyScheduler, TaskPlanner, AntigravityBrain, and MCP Server APIs).

## Decision
We introduce **Capability 6 — Review & Validation Engine** as a pure, deterministic evaluation layer.

Key architectural decisions:
1. **Pure Evaluation Subsystem**: The Review Engine never executes tasks, schedules tasks, modifies task graph topology, retries executions, replans objectives, or calls LLM providers directly.
2. **Dependency Injection**: Following the `ExecutionEngine` pattern, `ReviewEngine` accepts an injected reviewer callable (`reviewer`). When omitted, a deterministic fallback evaluator assesses execution records and criteria.
3. **Explicit Ownership**:
   - `ReviewResult` is immutable (`@dataclass(frozen=True)`).
   - `ReviewReport` is stored directly in `TaskWorkspace.review_reports`.
   - `ReviewEngine` is owned by `TaskWorkspace.review_engine`.
4. **Brain Facade & MCP Integration**: `AntigravityBrain` acts as a pure facade delegating review operations (`review_task`, `review_tasks`, `review_execution`, `review_plan`, `get_review`, `list_reviews`) to the workspace's `ReviewEngine`. 6 matching MCP tools are registered.

## Consequences
- Evaluation logic is decoupled from execution and scheduling.
- Backward compatibility with Capabilities 1–5 is strictly maintained.
- All review history is persisted deterministically within `TaskWorkspace`.
