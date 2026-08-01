# DependencyScheduler Architecture & Evaluation Algorithms

**Module**: [scheduler.py](file:///c:/Users/user/AI-Orchestrator/scheduler.py)

---

## 1. Overview

`DependencyScheduler` is a deterministic, synchronous, dependency-driven scheduler. It inspects `TaskGraph` state to evaluate task eligibility, detect dependency blocks, identify cycle membership, and build topological queues.

---

## 2. Readiness & Blocked Evaluation Algorithms

### Readiness Condition (`is_task_ready`)
A task `T` is **Ready** if and only if:
1. `T` exists in `TaskGraph`.
2. `T.status` is `TaskStatus.PENDING` or `TaskStatus.READY`.
3. **Every direct prerequisite task** `P` returned by `get_dependencies(T)` has `P.status == TaskStatus.COMPLETED`.

### Blocked Condition (`is_task_blocked`)
A task `T` is **Blocked** if:
1. `T` exists in `TaskGraph`.
2. `T.status` is `TaskStatus.PENDING` or `TaskStatus.READY`.
3. **Either**:
   - `T` is part of a directed dependency cycle detected by `detect_cycles()`, **OR**
   - At least one direct prerequisite task `P` has `P.status != TaskStatus.COMPLETED`.

---

## 3. Cycle Detection Algorithm (`detect_cycles`)

Uses Depth-First Search (DFS) with a recursion stack:
```python
def detect_cycles(self) -> list[list[str]]:
    adj = {tid: self.task_graph.get_dependencies(tid) for tid in self.task_graph.nodes}
    cycles, visited, rec_stack = [], set(), []

    def dfs(node: str):
        visited.add(node)
        rec_stack.append(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                cycle_start = rec_stack.index(neighbor)
                cycle = rec_stack[cycle_start:] + [neighbor]
                if cycle not in cycles:
                    cycles.append(cycle)
        rec_stack.pop()

    for node_id in sorted(self.task_graph.nodes.keys()):
        if node_id not in visited:
            dfs(node_id)
    return cycles
```

---

## 4. Execution Queue Generation (`get_execution_queue`)

Generates a deterministic topological order of all pending tasks:
- Iteratively selects ready candidate tasks whose prerequisites are satisfied or already queued.
- Sorts candidates deterministically by `(-priority, created_at, task_id)`.
- Appends candidates to the queue until all reachable tasks are processed.
