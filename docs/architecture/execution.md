# ExecutionEngine Architecture & Injected Executors

**Module**: [execution_engine.py](file:///c:/Users/user/AI-Orchestrator/execution_engine.py)

---

## 1. Overview

`ExecutionEngine` is the sole coordinator for task execution workflows. It receives an injected executor callable, decoupling task execution from provider SDKs and model routing decisions.

---

## 2. Injected Executor Pattern

```python
class ExecutionEngine:
    def __init__(
        self,
        executor: Callable[[dict[str, Any]], ExecutionResult],
        task_graph: TaskGraph,
        execution_index: TaskExecutionIndex,
        execution_store_add: Callable[[Any], None],
    ) -> None:
        self._executor = executor
        self._task_graph = task_graph
        self._execution_index = execution_index
        self._execution_store_add = execution_store_add
```

- The engine invokes `self._executor(arguments)` during `execute_task(...)`.
- `AntigravityBrain` injects a thin adapter `_build_executor()` that normalizes raw provider responses into an `ExecutionResult` dataclass.

---

## 3. Single vs. Batch Execution

### Single Task Execution (`execute_task`)
1. Fetches `TaskNode` from `TaskGraph`.
2. Calls `node.start_execution(execution_id)`.
3. Invokes injected executor callable.
4. Appends `ExecutionRecord` to workspace execution log.
5. Binds execution in `TaskExecutionIndex`.
6. Calls `node.complete_execution(...)` or `node.fail_execution(...)`.

### Batch Task Execution (`execute_tasks`)
- Accepts parallel lists of `task_ids` and `arguments_list`.
- When `parallel=True`, uses `concurrent.futures.ThreadPoolExecutor` to execute tasks concurrently.
- When `parallel=False`, executes tasks sequentially.
