# ADR-002: In-Memory Directed Acyclic TaskGraph Structure

## Context
AI-Orchestrator requires a data structure to represent goal decompositions, subtask hierarchies, and dependency relationships between tasks. The graph must support deterministic traversal, topological sorting, parent-child lookups, and cycle detection.

## Decision
We decided to implement an in-memory directed graph (`TaskGraph` in [task_graph.py](file:///c:/Users/user/AI-Orchestrator/task_graph.py)) consisting of strongly typed `TaskNode` entities and explicit directional `TaskEdge` objects.

Key aspects:
- Structural hierarchy is defined via `parent_task_id` on `TaskNode`.
- Execution prerequisites are defined via `TaskEdge` with string enums (`DEPENDS_ON`, `BLOCKS`, `RELATED`).
- Graph operations are deterministic and synchronous.

## Consequences
### Positive
- **High Performance**: In-memory dictionary lookups (`nodes: dict[str, TaskNode]`) are O(1).
- **Explicit Relationship Semantics**: Clearly separates structural containment (`parent_task_id`) from execution ordering (`DEPENDS_ON`).
- **Cycle Inspection**: Allows `DependencyScheduler` to run graph DFS algorithms to detect cycles cleanly.

### Negative
- Graph size is constrained by process RAM (though sufficient for tens of thousands of tasks per workspace).

## Alternatives Considered
- **Adjacency Matrix**: Matrix representation of dependencies. Rejected due to poor memory efficiency for sparse task graphs.
- **Implicit Ordering / Lists**: Using flat lists with implicit sequential ordering. Rejected because real agent workflows involve branching and join dependencies.
