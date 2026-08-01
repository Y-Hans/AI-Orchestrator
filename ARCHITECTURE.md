# AI-Orchestrator System Architecture

**Document Version**: 1.0.0  
- **Current Implementation Status**: Capabilities 1–10 FROZEN (Core Architecture Complete) 
- **Target System**: Operating System for AI Agents

---

## 1. Executive Overview

AI-Orchestrator is a capability-driven framework designed as a foundational operating system for AI agents. The framework provides structured decomposition of goals into tasks, deterministic dependency scheduling, execution lifecycle tracking, artifact management, binding of multi-provider model calls to domain entities, deterministic review & quality validation, long-term memory storage, result synthesis, multi-agent collaboration sessions, and a centralized capability registry with plugin framework.

The architecture strictly adheres to eight fundamental constraints:
1. **Planning NEVER executes.**
2. **Scheduling NEVER plans.**
3. **Execution NEVER plans or schedules.**
4. **Review NEVER executes or schedules.**
5. **Memory NEVER executes, schedules, plans, or reviews.**
6. **Synthesis NEVER executes, schedules, plans, reviews, or mutates state.**
7. **Multi-Agent Collaboration NEVER executes, schedules, plans, reviews, or synthesizes.**
8. **Capability Registry & Plugins NEVER execute, schedule, plan, review, synthesize, store memory, or coordinate agents.**

```
               ┌─────────────────────────────────────────┐
               │           Antigravity / Client          │
               └────────────────────┬────────────────────┘
                                    │ MCP Protocol (JSON-RPC 2.0)
               ┌────────────────────▼────────────────────┐
               │       ai_orchestrator_mcp.py            │
               └────────────────────┬────────────────────┘
                                    │ Direct Facade Calls
               ┌────────────────────▼────────────────────┐
               │         AntigravityBrain                │
               └──────┬──────┬──────┬──────┬──────┬───┬──┘
                      │      │      │      │      │   │
        ┌─────────────▼──┐ ┌─▼───┐┌─▼────┐┌▼──────┴──┐│ ┌─▼──────────────┐
        │   TaskPlanner  │ │Dep. ││Exec. ││ReviewEng. ││ │SynthesisEngine │
        │  (Capability 5)│ │Sched││Engine││(Cap. 6)   ││ │(Capability 8)  │
        └─────────────┬──┘ └─┬───┘└─┬────┘└┬─────────┘│ └─┬──────────────┘
                      │      │      │      │          │   │
                      │      │      │  ┌───┴──────────┼───┴──────────────┐
                      │      │      │  │  ┌───────────▼────────────────┐ │
                      │      │      │  │  │  Capability & Plugins      │ │
                      │      │      │  │  │ (CapRegistry / PluginMgr)  │ │
                      │      │      │  │  └───────────┬────────────────┘ │
                      └──────┴──────┼──┴──────────────┼──────────────────┘
                                    │                 │
                       ┌────────────▼─────────────────▼──┐
                       │          TaskWorkspace          │
                       │          (Data Owner)           │
                       └─────────────────────────────────┘
```

---

## 2. Component Responsibilities

| Component | Module | Responsibilities | Invariants |
| :--- | :--- | :--- | :--- |
| **`TaskWorkspace`** | [workspace.py](file:///c:/Users/user/AI-Orchestrator/workspace.py) | Explicit owner of runtime state (TaskGraph, Scheduler, Index, ArtifactStore, Engine, Planner, ReviewEngine, MemoryEngine, SynthesisEngine, AgentRegistry, CollaborationStore, CollaborationEngine, CapabilityRegistry, PluginManager). | Single point of state ownership per workspace ID. |
| **`TaskGraph`** | [task_graph.py](file:///c:/Users/user/AI-Orchestrator/task_graph.py) | Maintains in-memory DAG of `TaskNode` objects and `TaskEdge` dependencies. | Rejects duplicate task IDs; validates parent presence. |
| **`TaskPlanner`** | [planner.py](file:///c:/Users/user/AI-Orchestrator/planner.py) | Top-level coordinator for Objective creation, plan generation, and task expansion. | Delegates graph mutations to `PlanGraphBuilder`. |
| **`PlanGraphBuilder`** | [planner.py](file:///c:/Users/user/AI-Orchestrator/planner.py) | Insulates planning strategy logic from direct `TaskGraph` mutations. | Encapsulates metadata assignment (`is_executable`, `plan_role`). |
| **`PlanValidator`** | [planner.py](file:///c:/Users/user/AI-Orchestrator/planner.py) | Single authority for structural plan correctness and graph consistency. | Runs pre-scheduling checks (cycles, orphans, max depth). |
| **`DependencyScheduler`**| [scheduler.py](file:///c:/Users/user/AI-Orchestrator/scheduler.py) | Evaluates task readiness, blocked states, topological execution queues, and cycles. | Purely deterministic; makes no execution or provider decisions. |
| **`ExecutionEngine`** | [execution_engine.py](file:///c:/Users/user/AI-Orchestrator/execution_engine.py) | Coordinates single/batch task execution using an injected executor callable. | Never routes or parses model output; updates lifecycle states. |
| **`ReviewEngine`** | [review_engine.py](file:///c:/Users/user/AI-Orchestrator/review_engine.py) | Coordinates pure evaluation of executions, tasks, and plans via injected reviewer. | Never executes tasks, schedules tasks, or calls LLM providers directly. |
| **`MemoryEngine`** | [memory_engine.py](file:///c:/Users/user/AI-Orchestrator/memory_engine.py) | Coordinates knowledge storage, retrieval, deterministic search, and summary calculation. | Delegates persistence to `MemoryStore`; does not execute, plan, or schedule. |
| **`MemoryStore`** | [memory_store.py](file:///c:/Users/user/AI-Orchestrator/memory_store.py) | Thread-safe in-memory store for `MemoryRecord` objects. Enforces lifecycle status and search filtering. | Single owner of persistent memory records. |
| **`SynthesisEngine`** | [synthesis_engine.py](file:///c:/Users/user/AI-Orchestrator/synthesis_engine.py) | Coordinates aggregation of execution outputs, review reports, artifacts, and memory into final deliverables. | Read-only input consumption; delegates synthesis to `Synthesizer`. |
| **`AgentRegistry`** | [agent_registry.py](file:///c:/Users/user/AI-Orchestrator/agent_registry.py) | Single source of truth for `Agent` entities. Handles agent registration, capability filtering, and status transitions. | Thread-safe in-memory store for Agent entities. |
| **`CollaborationStore`** | [collaboration_store.py](file:///c:/Users/user/AI-Orchestrator/collaboration_store.py) | Thread-safe store for `CollaborationSession`, `AgentAssignment`, and `AgentMessage` entities. | Single owner of collaboration state. |
| **`CollaborationEngine`** | [collaboration_engine.py](file:///c:/Users/user/AI-Orchestrator/collaboration_engine.py) | Coordinator for multi-agent collaboration sessions, task assignments, and message transport backends. | Inter-agent coordinator only; zero execution or planning logic. |
| **`CapabilityRegistry`** | [capability_registry.py](file:///c:/Users/user/AI-Orchestrator/capability_registry.py) | Single authority for capability metadata, dependency validation, and capability status tracking. | Thread-safe, single source of truth for installed capabilities. |
| **`PluginManager`** | [plugin_manager.py](file:///c:/Users/user/AI-Orchestrator/plugin_manager.py) | Coordinator for plugin loading, unloading, and forwarding capabilities into `CapabilityRegistry`. | Lifecycle coordinator only; stores no capability metadata itself. |
| **`TaskExecutionIndex`** | [execution_binding.py](file:///c:/Users/user/AI-Orchestrator/execution_binding.py) | Index mapping `TaskNode` objects to `ExecutionRecord` instances via `ExecutionBinding`. | Strongly-typed binding types (`PRIMARY`, `REVIEW`, `RETRY`, etc.). |
| **`ArtifactStore`** | [artifact_store.py](file:///c:/Users/user/AI-Orchestrator/artifact_store.py) | In-memory store for task and execution artifacts. | Artifacts are stored explicitly; never extracted automatically. |
| **`AntigravityBrain`** | [brain.py](file:///c:/Users/user/AI-Orchestrator/brain.py) | Public facade connecting MCP tools to workspace operations. | Enforces pre-execution scheduler checks before execution. |user/AI-Orchestrator/synthesis_engine.py) | Coordinates aggregation of execution outputs, review reports, artifacts, and memory into final deliverables. | Read-only input consumption; delegates synthesis to `Synthesizer`. |
| **`Synthesizer`** | [synthesis_engine.py](file:///c:/Users/user/AI-Orchestrator/synthesis_engine.py) | Abstract interface for output synthesis strategies (default: `DeterministicSynthesizer`). | Produces immutable `SynthesisResult` objects. |
| **`TaskExecutionIndex`** | [execution_binding.py](file:///c:/Users/user/AI-Orchestrator/execution_binding.py) | Index mapping `TaskNode` objects to `ExecutionRecord` instances via `ExecutionBinding`. | Strongly-typed binding types (`PRIMARY`, `REVIEW`, `RETRY`, etc.). |
| **`ArtifactStore`** | [artifact_store.py](file:///c:/Users/user/AI-Orchestrator/artifact_store.py) | In-memory store for task and execution artifacts. | Artifacts are stored explicitly; never extracted automatically. |
| **`AntigravityBrain`** | [brain.py](file:///c:/Users/user/AI-Orchestrator/brain.py) | Public facade connecting MCP tools to workspace operations. | Enforces pre-execution scheduler checks before execution. |

---

## 3. Data Ownership & Thread Safety

### Explicit Ownership Hierarchy

```
WorkspaceStore (Global Process Registry)
 └── TaskWorkspace (Keyed by workspace_id)
      ├── TaskGraph (nodes: dict[str, TaskNode], edges: list[TaskEdge])
      ├── DependencyScheduler (references TaskGraph)
      ├── TaskExecutionIndex (bindings: dict[str, ExecutionBinding])
      ├── ArtifactStore (_artifacts: dict[str, Artifact])
      ├── ExecutionEngine (references TaskGraph, TaskExecutionIndex)
      ├── TaskPlanner (references TaskWorkspace)
      ├── ReviewEngine (references TaskWorkspace)
      ├── Objectives Store (objectives: dict[str, Objective])
      ├── Plans Store (plans: dict[str, Plan])
      ├── Review Reports Store (review_reports: dict[str, ReviewReport])
      └── Execution Records List (executions: list[ExecutionRecord])
```AntigravityBrain`** | [brain.py](file:///c:/Users/user/AI-Orchestrator/brain.py) | Public facade connecting MCP tools to workspace operations. | Enforces pre-execution scheduler checks before execution. |

---

## 3. Data Ownership & Thread Safety

### Explicit Ownership Hierarchy

```
WorkspaceStore (Global Process Registry)
 └── TaskWorkspace (Keyed by workspace_id)
      ├── TaskGraph (nodes: dict[str, TaskNode], edges: list[TaskEdge])
      ├── DependencyScheduler (references TaskGraph)
      ├── TaskExecutionIndex (bindings: dict[str, ExecutionBinding])
      ├── ArtifactStore (_artifacts: dict[str, Artifact])
      ├── ExecutionEngine (references TaskGraph, TaskExecutionIndex)
      ├── TaskPlanner (references TaskWorkspace)
      ├── Objectives Store (objectives: dict[str, Objective])
      ├── Plans Store (plans: dict[str, Plan])
      └── Execution Records List (executions: list[ExecutionRecord])
```

### Concurrency Model
- `WorkspaceStore` uses an internal reentrant `Lock` to guard workspace registration and retrieval.
- Individual `TaskWorkspace` operations are deterministic and synchronous. Thread pool concurrency is used in `ExecutionEngine.execute_tasks(parallel=True)` and `AntigravityBrain.execute_many(parallel=True)` for non-blocking I/O against remote model providers.

---

## 4. System Lifecycle & Workflows

### 4.1 Planning Lifecycle Flow
1. Client issues `create_plan` with an `Objective` string or object and optional level specifications.
2. `TaskPlanner` instantiates an `Objective` entity and registers it in `workspace.objectives`.
3. `TaskPlanner` invokes `PlanningEngine.plan(...)` via `PlanGraphBuilder`.
4. `PlanGraphBuilder` creates root node, level group nodes, and leaf task nodes with explicit parent-child relations and dependencies in `TaskGraph`.
5. `PlanValidator.validate(...)` performs 7-step graph validation:
   - Cycle detection via `DependencyScheduler.detect_cycles()`
   - Registry ID uniqueness
   - Root task presence
   - Orphan and disconnected node detection
   - Invalid dependency edge target verification
   - Hierarchy max-depth and circular parentage verification
   - Leaf node executability verification
6. If valid, `PlanStatus` becomes `VALIDATED`; otherwise `FAILED`.
7. `TaskPlanner` returns an immutable `PlanningResult` snapshot.

### 4.2 Scheduling Lifecycle Flow
1. Before executing any task, `AntigravityBrain` queries `DependencyScheduler.is_task_blocked(task_id)` and `DependencyScheduler.can_execute(task_id)`.
2. `DependencyScheduler` evaluates prerequisites in `TaskGraph`:
   - A task is **Ready** if it is `PENDING` or `READY` and **all direct prerequisite tasks** are in `COMPLETED` status.
   - A task is **Blocked** if any direct prerequisite is uncompleted or if the task participates in a dependency cycle.
3. If a task is ready and unblocked, `AntigravityBrain` passes control to `ExecutionEngine`.

### 4.3 Execution Lifecycle Flow
1. `ExecutionEngine.execute_task(task_id, arguments, execution_type)` is invoked.
2. `ExecutionEngine` retrieves `TaskNode` from `TaskGraph` and calls `node.start_execution(execution_id)`.
   - Node transitions to `status = TaskStatus.RUNNING` and `execution_state = ExecutionState.RUNNING`.
   - `attempt_count` increments by 1.
3. `ExecutionEngine` invokes the injected executor callable (e.g. `_adapter` wrapping `execute_model`).
4. Upon executor return (or exception catch):
   - Constructs an `ExecutionRecord` and appends it to `workspace.executions`.
   - Binds the execution to the task in `TaskExecutionIndex` with the designated `ExecutionType`.
   - If successful: calls `node.complete_execution(result_summary)`. Node transitions to `COMPLETED`.
   - If failed: calls `node.fail_execution(result_summary)`. Node transitions to `FAILED`.
5. Downstream dependent tasks automatically become ready for the scheduler on subsequent queries.

---

## 5. Component Interaction Matrix

```
┌───────────────────┬──────────────┬───────────┬───────────┬───────────┬───────────┐
│ Invoker \ Target  │ TaskWorkspace│ TaskGraph │ Scheduler │ Engine    │ Planner   │
├───────────────────┼──────────────┼───────────┼───────────┼───────────┼───────────┤
│ AntigravityBrain  │ Reads/Gets   │ -         │ Queries   │ Executes  │ Creates   │
│ TaskPlanner       │ Reads/Writes │ Mutates*  │ -         │ -         │ Self      │
│ DependencySched.  │ -            │ Reads     │ Self      │ -         │ -         │
│ ExecutionEngine   │ Writes Records│ Mutates   │ -         │ Self      │ -         │
└───────────────────┴──────────────┴───────────┴───────────┴───────────┴───────────┘
* Note: TaskPlanner mutates TaskGraph exclusively through PlanGraphBuilder.
```

---

## 6. Extension Philosophy

AI-Orchestrator uses a capability-driven extension model:
1. **Capabilities are Frozen**: Completed capabilities (1–5) have frozen public interfaces and deterministic behavior.
2. **Backward Compatibility**: New capabilities (6–20) must be layered on top of existing abstractions without breaking existing APIs or data schemas.
3. **Pluggable Strategies**: Components like `PlanningEngine` use abstract base classes (`ABC`), allowing custom deterministic or LLM-driven planning strategies to be plugged in seamlessly.
4. **Decoupled Execution**: `ExecutionEngine` does not import provider SDKs; it accepts any Callable matching `(dict) -> ExecutionResult`.
