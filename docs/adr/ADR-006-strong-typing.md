# ADR-006: Strong Typing via Dataclasses and String Enums

## Context
Dynamically typed Python code bases handling multi-agent state can suffer from schema ambiguity, missing key errors (`KeyError`), and broken API contracts when passing untyped dictionaries between components.

## Decision
We decided to enforce strong typing across all core domain entities using Python `@dataclass` structures and string enums (`str, Enum`).

Key entities:
- `TaskNode`, `TaskEdge` ([task_graph.py](file:///c:/Users/user/AI-Orchestrator/task_graph.py))
- `ExecutionRecord`, `TaskWorkspace` ([workspace.py](file:///c:/Users/user/AI-Orchestrator/workspace.py))
- `ExecutionBinding` ([execution_binding.py](file:///c:/Users/user/AI-Orchestrator/execution_binding.py))
- `ExecutionResult` ([execution_result.py](file:///c:/Users/user/AI-Orchestrator/execution_result.py))
- `Artifact` ([artifact_store.py](file:///c:/Users/user/AI-Orchestrator/artifact_store.py))
- `Objective`, `Plan`, `PlanningLevelSpec`, `TaskSpecification`, `PlanningResult` ([planner_models.py](file:///c:/Users/user/AI-Orchestrator/planner_models.py))

Enums inherit from `(str, Enum)` (e.g. `TaskStatus(str, Enum)`), ensuring string serialisability while preserving type safety.

## Consequences
### Positive
- **IDE Support & Static Checking**: Complete autocomplete, type hinting, and compatibility with `mypy`.
- **JSON Compatibility**: String enums serialize natively to JSON via `.value` or string coercion without custom encoder boilerplate.
- **Contract Guarantees**: Eliminates runtime attribute name errors.

### Negative
- Requires explicit `to_dict()` conversion methods for MCP JSON responses.

## Alternatives Considered
- **Plain Python Dictionaries**: Using untyped dicts for domain objects. Rejected due to vulnerability to key misspelling and lack of type hints.
- **Pydantic Models**: Using Pydantic for validation. Deferred to avoid adding external runtime framework dependencies to core modules.
