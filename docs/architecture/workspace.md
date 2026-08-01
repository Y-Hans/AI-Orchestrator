# TaskWorkspace Architecture & State Ownership

**Module**: [workspace.py](file:///c:/Users/user/AI-Orchestrator/workspace.py)

---

## 1. Overview

`TaskWorkspace` is the explicit owner of runtime state within AI-Orchestrator. It encapsulates all domain entities, task graphs, execution indices, artifact stores, dependency schedulers, execution engines, and task planners associated with a specific workspace ID.

---

## 2. State Ownership & Fields

```python
@dataclass
class TaskWorkspace:
    workspace_id: str
    created_at: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    executions: list[ExecutionRecord] = field(default_factory=list)
    objectives: dict[str, Any] = field(default_factory=dict)
    plans: dict[str, Any] = field(default_factory=dict)
    task_graph: TaskGraph = field(init=False)
    scheduler: DependencyScheduler = field(init=False)
    task_execution_index: TaskExecutionIndex = field(init=False)
    artifact_store: ArtifactStore = field(init=False)
    execution_engine: Any = field(init=False)
    planner: Any = field(init=False)
```

### Managed Child Entities
1. **`task_graph`**: Instance of `TaskGraph(workspace_id)`.
2. **`scheduler`**: Instance of `DependencyScheduler(task_graph)`.
3. **`task_execution_index`**: Instance of `TaskExecutionIndex()`.
4. **`artifact_store`**: Instance of `ArtifactStore()`.
5. **`execution_engine`**: Instance of `ExecutionEngine` initialized with a default placeholder executor callable.
6. **`planner`**: Instance of `TaskPlanner(self)`.

---

## 3. Workspace Store & Concurrency

`WorkspaceStore` manages process-local workspace instances:

```python
class WorkspaceStore:
    def __init__(self) -> None:
        self._workspaces: dict[str, TaskWorkspace] = {}
        self._lock = Lock()
```

- Thread safety for workspace retrieval, listing, and creation is guaranteed via a reentrant `threading.Lock()`.
- Accessing or creating a workspace is thread-safe.

---

## 4. Helper & Serialisation Functions

- `workspace_to_dict(workspace: TaskWorkspace) -> dict`: Complete serialisation of workspace metadata, objectives, plans, execution records, task graph, scheduler state, execution bindings, and artifacts.
- `workspace_summary(workspace: TaskWorkspace) -> dict`: High-level summary dictionary.
