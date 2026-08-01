# ADR-004: Pure, Deterministic DependencyScheduler

## Context
AI agent workflows require evaluating task execution order to avoid executing tasks before their prerequisites complete or running tasks trapped in cyclic dependencies.

## Decision
We decided to create a dedicated `DependencyScheduler` ([scheduler.py](file:///c:/Users/user/AI-Orchestrator/scheduler.py)) component that is purely deterministic, synchronous, and dependency-driven.

Key aspects:
- **Scheduling NEVER plans or executes.**
- Operates strictly on `TaskGraph` state.
- `is_task_ready(task_id)` requires **all direct prerequisite tasks to be `COMPLETED`**.
- Cycle detection is performed using a Depth-First Search (DFS) algorithm with a recursion stack.
- Multi-task candidate sorting is deterministic, ordering candidates by `(-priority, created_at, task_id)`.

## Consequences
### Positive
- **Predictable Execution**: Identical graph inputs always produce identical ready lists and topological queues.
- **Safety Enforcement**: `AntigravityBrain` validates every execution call against `DependencyScheduler` before running, preventing invalid executions.
- **Complete Decoupling**: Schedulers contain zero provider or prompt logic.

### Negative
- Synchronous evaluation means large graphs are traversed on query, though performance remains fast for typical task counts (<0.1ms for 100 nodes).

## Alternatives Considered
- **Event-Driven Async Callback Queue**: Tasks triggering downstream listeners upon completion. Rejected because implicit async callbacks complicate cycle detection and state auditing.
- **Planner-Driven Execution**: Letting the planner decide runtime execution sequence. Rejected because it violates separation of concerns.
