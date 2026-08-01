# ADR-007: Explicit Dependency Injection

## Context
Components in complex AI orchestration frameworks often depend on each other (e.g. `TaskPlanner` needs `TaskGraph`, `ExecutionEngine` needs `TaskExecutionIndex` and `TaskGraph`). Hardcoding instances or retrieving them from global registries introduces tight coupling and hidden dependencies.

## Decision
We decided that all dependencies must be explicitly injected at construction time or via explicit configuration methods.

Examples:
- `TaskWorkspace.__post_init__` instantiates child components (`TaskGraph`, `DependencyScheduler`, `TaskExecutionIndex`, `ArtifactStore`, `ExecutionEngine`, `TaskPlanner`) and passes explicit object references.
- `DependencyScheduler(task_graph)` accepts the target `TaskGraph` in its constructor.
- `ExecutionEngine` accepts `executor`, `task_graph`, `execution_index`, and `execution_store_add` in its constructor.
- `workspace.configure_executor(fn)` explicitly updates the executor reference on `ExecutionEngine`.

## Consequences
### Positive
- **No Hidden Dependencies**: Every required dependency is visible in constructor signatures.
- **Easy Unit Testing**: Test code can instantiate individual components with mock or stub dependencies.
- **Zero Service Locator**: No global lookup maps or singletons needed.

### Negative
- Constructor signatures contain multiple parameters.

## Alternatives Considered
- **Global Service Locator**: Component registry lookups (e.g. `Registry.get("task_graph")`). Rejected due to hidden state.
- **Singleton Imports**: Module-level singleton imports. Rejected due to lack of isolation.
