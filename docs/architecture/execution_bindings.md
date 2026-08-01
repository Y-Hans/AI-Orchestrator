# Execution Bindings & Task Execution Index

**Module**: [execution_binding.py](file:///c:/Users/user/AI-Orchestrator/execution_binding.py)

---

## 1. Overview

`ExecutionBinding` correlates tasks (`TaskNode`) with model executions (`ExecutionRecord`). `TaskExecutionIndex` maintains these bindings in memory for rapid lookup.

---

## 2. Data Models

```python
class ExecutionType(str, Enum):
    PRIMARY = "PRIMARY"
    REVIEW = "REVIEW"
    RETRY = "RETRY"
    PARALLEL = "PARALLEL"
    SYNTHESIS = "SYNTHESIS"
    VALIDATION = "VALIDATION"

@dataclass
class ExecutionBinding:
    binding_id: str
    task_id: str
    execution_id: str
    execution_type: ExecutionType
    created_at: str
```

---

## 3. `TaskExecutionIndex` API

```python
class TaskExecutionIndex:
    def bind_execution(
        self,
        task_id: str,
        execution_id: str,
        execution_type: ExecutionType | str = ExecutionType.PRIMARY,
        binding_id: str | None = None,
        created_at: str | None = None,
    ) -> ExecutionBinding: ...

    def get_task_executions(self, task_id: str) -> list[ExecutionBinding]: ...
    def get_execution(self, execution_id: str) -> ExecutionBinding | None: ...
    def remove_binding(self, binding_id: str) -> None: ...
    def list_bindings(self) -> list[ExecutionBinding]: ...
```

---

## 4. Execution Types

- **`PRIMARY`**: Initial standard execution of a task.
- **`REVIEW`**: Secondary evaluation call reviewing primary output.
- **`RETRY`**: Re-execution attempt following a failure.
- **`PARALLEL`**: One of several concurrent model executions for the same task.
- **`SYNTHESIS`**: Combination/merging call synthesizing parallel execution results.
- **`VALIDATION`**: Verification call asserting output correctness.
