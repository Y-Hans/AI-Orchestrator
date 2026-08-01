# Execution Records Schema & Persistence

**Module**: [workspace.py](file:///c:/Users/user/AI-Orchestrator/workspace.py)

---

## 1. Schema & Data Model

`ExecutionRecord` is an immutable record representing an individual model invocation:

```python
@dataclass
class ExecutionRecord:
    execution_id: str
    provider: str
    model: str | None
    prompt: str
    started_at: str
    completed_at: str
    latency_ms: int
    success: bool
    response: Any = None
    error: Any = None
```

---

## 2. Field Definitions

| Field | Type | Description |
| :--- | :--- | :--- |
| `execution_id` | `str` | Unique UUID v4 identifying the execution. |
| `provider` | `str` | Provider string (`gemini`, `groq`, `openrouter`, `ollama`). |
| `model` | `str \| None` | Model name executed. |
| `prompt` | `str` | User prompt string or serialized messages payload. |
| `started_at` | `str` | ISO 8601 UTC timestamp of execution start. |
| `completed_at` | `str` | ISO 8601 UTC timestamp of execution completion. |
| `latency_ms` | `int` | Execution round-trip latency in milliseconds. |
| `success` | `bool` | Boolean flag indicating whether execution succeeded. |
| `response` | `Any` | Normalized model response payload string or dictionary. |
| `error` | `Any` | Error dictionary `{"code": ..., "message": ...}` if failed. |

---

## 3. Workspace Store Integration

`ExecutionRecord` objects are stored sequentially in `TaskWorkspace.executions`. They provide an immutable execution audit log for all model calls executed in the workspace context.
