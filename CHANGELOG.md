# Changelog

All notable changes to the AI-Orchestrator project are documented in this file. The project follows Semantic Versioning (`0.x.0` for capability releases).

---

## [1.0.0] - Capability 10: Capability Registry & Plugin Framework (Core Architecture Complete)

### Added
- **Data Models** (`capability_models.py`):
  - `Capability` dataclass with `CapabilityStatus` (`REGISTERED`, `ENABLED`, `DISABLED`, `ERROR`) and `CapabilityType` (`CORE`, `EXTENSION`, `PLUGIN`, `EXPERIMENTAL`).
  - `Plugin` dataclass with `PluginStatus` (`LOADED`, `UNLOADED`, `ERROR`).
  - `CapabilitySummary` metric model.
- **Capability Registry** (`capability_registry.py`):
  - Thread-safe `CapabilityRegistry` as single authority for capability metadata, state transitions, dependency validation, and active dependent tracking.
- **Plugin Manager** (`plugin_manager.py`):
  - `PluginManager` coordinator managing plugin lifecycle and forwarding capability registrations into `CapabilityRegistry`.
- **Workspace & Brain Integration** (`workspace.py`, `brain.py`):
  - `TaskWorkspace` owns `capability_registry` and `plugin_manager`.
  - Updated `workspace_to_dict()` with `capabilities`, `plugins`, and `capability_summary`.
  - 13 `AntigravityBrain` façade methods for capability and plugin management.
- **MCP Server Integration** (`ai_orchestrator_mcp.py`):
  - Registered and dispatched 13 new MCP tools: `register_capability`, `unregister_capability`, `get_capability`, `list_capabilities`, `enable_capability`, `disable_capability`, `register_plugin`, `unregister_plugin`, `load_plugin`, `unload_plugin`, `list_plugins`, `get_plugin`, `capability_summary`.
- **Documentation & Architecture**:
  - `docs/capabilities/capability_10.md`, `docs/architecture/capability_registry.md`, `docs/architecture/plugin_manager.md`, `docs/architecture/capability_models.md`, `docs/diagrams/capability_registry.md`, `docs/diagrams/plugin_lifecycle.md`, `docs/diagrams/plugin_sequence.md`, `docs/adr/ADR-013-capability-registry.md`.
- **Test Suite** (`test_capability_registry.py`):
  - 15 new comprehensive unit tests covering models, registry, plugin manager, thread safety, workspace, brain facade, and MCP tools.
  - Total test suite: **121 / 121 tests passing**.

---

## [0.9.0] - Capability 9: Multi-Agent Collaboration Framework

### Added
- **Data Models** (`agent_models.py`):
  - `Agent` dataclass with `AgentStatus` (`IDLE`, `BUSY`, `WAITING`, `OFFLINE`, `ERROR`) and `AgentRole` (`GENERAL`, `PLANNER`, `EXECUTOR`, `REVIEWER`, `RESEARCHER`, `CODER`, `TESTER`, `SYNTHESIZER`, `MEMORY`, `CUSTOM`).
  - `AgentAssignment` model with `AssignmentStatus` (`PENDING`, `ACCEPTED`, `IN_PROGRESS`, `COMPLETED`, `DECLINED`, `FAILED`).
  - `AgentMessage` immutable frozen dataclass with `MessageType` (`REQUEST`, `RESPONSE`, `STATUS`, `INFO`, `WARNING`, `ERROR`).
  - `CollaborationSession` lightweight session entity storing objective, participant agent IDs, and `CollaborationStatus` (`ACTIVE`, `PAUSED`, `COMPLETED`, `FAILED`).
  - `CollaborationSummary` lightweight summary model.
- **Agent Registry** (`agent_registry.py`):
  - Thread-safe store serving as single source of truth for Agent entities.
  - Agent registration, unregistration, status transitions, role filtering, and capability filtering.
- **Collaboration Store** (`collaboration_store.py`):
  - Thread-safe single owner for `CollaborationSession`, `AgentAssignment`, and `AgentMessage` entities.
  - Immutability and deterministic creation timestamp ordering for messages.
- **Collaboration Engine & Transport** (`collaboration_engine.py`):
  - Coordinator for multi-agent collaboration sessions and explicit task assignments.
  - Abstract `MessagingBackend` interface with default `InMemoryMessagingBackend`.
  - Session summary calculations and workspace boundary enforcement.
- **Workspace & Brain Integration** (`workspace.py`, `brain.py`):
  - Attached `AgentRegistry`, `CollaborationStore`, and `CollaborationEngine` to `TaskWorkspace`.
  - Serialization of agents and sessions in `workspace_to_dict()`.
  - 11 Brain façade methods for multi-agent operations.
- **MCP Server Integration** (`ai_orchestrator_mcp.py`):
  - Registered and dispatched 11 MCP tools: `register_agent`, `unregister_agent`, `get_agent`, `list_agents`, `create_collaboration`, `close_collaboration`, `assign_agent`, `send_agent_message`, `list_messages`, `list_assignments`, `list_sessions`.
- **Test Suite** (`test_collaboration_engine.py`):
  - 14 comprehensive unit tests verifying models, registry, store, engine workflow, messaging backends, workspace serialization, brain facade, and MCP tools.
  - 106/106 total tests passing.

---

## [0.5.0] - Capability 5: Intelligent Task Planner

### Added
- **Data Models** (`planner_models.py`):
  - `Objective` dataclass for user objective representation.
  - `Plan` dataclass with `PlanStatus` enum (`DRAFT`, `VALIDATED`, `ACTIVE`, `REVISED`, `ARCHIVED`, `FAILED`).
  - `PlanningLevelSpec` and `TaskSpecification` models.
  - `PlanningResult` immutable snapshot return type.
- **Graph Builder Layer** (`PlanGraphBuilder`):
  - Abstracted `TaskGraph` construction for root tasks, structural level group nodes, and executable leaf tasks.
  - Metadata assignment (`plan_role`, `is_executable`, `level_name`).
- **Validation Engine** (`PlanValidator`):
  - Single-authority 7-step graph validation boundary checking cycle detection, registry uniqueness, root task presence, orphan nodes, edge targets, depth limits, and leaf executability.
- **Planning Engines** (`PlanningEngine`, `DeterministicPlanningEngine`):
  - Strategy interface for goal decomposition.
  - `DeterministicPlanningEngine` reference implementation for level-based graph generation.
- **Visualizer** (`PlanVisualizer`):
  - Read-only rendering of plans into ASCII text trees, JSON structures, and Mermaid diagrams.
- **Coordinator & MCP Tools** (`TaskPlanner`, `ai_orchestrator_mcp.py`):
  - Workspace integration via `workspace.planner`.
  - Added 5 MCP tools: `create_plan`, `expand_task`, `regenerate_plan`, `get_plan`, `visualize_plan`.

---

## [0.4.0] - Capability 4: Dependency Scheduler

### Added
- **Scheduler Core** (`DependencyScheduler` in `scheduler.py`):
  - Purely deterministic, dependency-driven task scheduler operating on `TaskGraph`.
  - `is_task_ready`: checks whether all direct prerequisites are in `COMPLETED` status.
  - `is_task_blocked`: detects dependency blocks and graph cycles.
  - `can_execute`: convenience check combining readiness and unblocked status.
  - `detect_cycles`: Depth-First Search (DFS) cycle detection algorithm returning exact node paths.
  - `get_execution_queue`: topological sorting of pending tasks ordered by priority and creation timestamp.
  - Query methods: `get_ready_tasks`, `get_blocked_tasks`, `get_completed_tasks`, `get_failed_tasks`, `get_scheduler_state`.
- **Integration & MCP Tools**:
  - Attached `DependencyScheduler` to `TaskWorkspace`.
  - Integrated pre-execution scheduler verification into `AntigravityBrain.execute_task` and `execute_tasks`.
  - Added 4 MCP tools: `get_ready_tasks`, `get_blocked_tasks`, `get_execution_queue`, `get_scheduler_state`.

---

## [0.3.0] - Capability 3: Execution Engine & Lifecycle

### Added
- **Execution Engine** (`ExecutionEngine` in `execution_engine.py`):
  - Task execution coordinator accepting an injected executor callable.
  - Sequential and thread-pool parallel multi-task execution (`execute_tasks`).
  - Automatic error handling and exception wrapping into `ExecutionResult`.
- **Task Node Lifecycle Enhancements** (`task_graph.py`):
  - Added lifecycle methods: `start_execution`, `complete_execution`, `fail_execution`, `reset_execution`.
  - Added node lifecycle fields: `priority`, `attempt_count`, `execution_state` (`WAITING`, `RUNNING`, `COMPLETED`, `FAILED`), `last_execution_id`, `result_summary`.
- **Artifact Management** (`ArtifactStore` in `artifact_store.py`):
  - In-memory `ArtifactStore` and `Artifact` model.
  - Strongly typed `ArtifactType` enum (`TEXT`, `MARKDOWN`, `PYTHON`, `JSON`, `CSV`, `HTML`, `IMAGE`, `PDF`, `DIFF`, `PATCH`, `LOG`, `UNKNOWN`).
  - Filtered queries: `list_task_artifacts`, `list_execution_artifacts`.
- **MCP Integration**:
  - Added 5 MCP tools: `execute_task`, `execute_tasks`, `create_artifact`, `get_artifacts`, `get_task_artifacts`.

---

## [0.2.0] - Capability 2: Execution Records & Bindings

### Added
- **Execution Records** (`ExecutionRecord` in `workspace.py`):
  - Dataclass recording execution ID, provider, model, prompt, timestamps, latency (ms), success status, response payload, and error details.
  - Workspace execution log list storing all execution history.
- **Execution Bindings** (`ExecutionBinding` and `TaskExecutionIndex` in `execution_binding.py`):
  - `TaskExecutionIndex` mapping tasks to execution records.
  - `ExecutionType` enum (`PRIMARY`, `REVIEW`, `RETRY`, `PARALLEL`, `SYNTHESIS`, `VALIDATION`).
- **MCP Tools**:
  - Added 2 MCP tools: `get_task_executions`, `list_execution_bindings`.

---

## [0.1.0] - Capability 1: Task Workspace & Task Graph

### Added
- **Task Workspace** (`TaskWorkspace` & `WorkspaceStore` in `workspace.py`):
  - In-memory workspace container owning workspace metadata and runtime state.
  - Thread-safe `WorkspaceStore` process-local registry.
- **Task Graph Core** (`TaskGraph`, `TaskNode`, `TaskEdge` in `task_graph.py`):
  - Node creation (`create_task`), subtask hierarchy (`create_subtask`).
  - Dependency edge management (`add_dependency`).
  - `DependencyType` enum (`DEPENDS_ON`, `BLOCKS`, `RELATED`).
  - `TaskStatus` enum (`PENDING`, `READY`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`).
  - Parent/child and dependency query methods.
- **MCP Infrastructure & Provider Facade** (`ai_orchestrator_mcp.py`, `brain.py`):
  - `AntigravityBrain` facade wrapping low-level execution requests.
  - MCP JSON-RPC 2.0 server exposing base tools (`execute_model`, `execute_models`, `create_workspace`, `get_workspace`, `list_workspaces`, `create_task`, `create_subtask`, `add_dependency`, `get_task`, `list_tasks`).
