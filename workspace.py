"""In-memory task workspace storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from artifact_store import ArtifactStore
from task_graph import TaskGraph
from execution_binding import TaskExecutionIndex
from scheduler import DependencyScheduler


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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


@dataclass
class TaskWorkspace:
    workspace_id: str
    created_at: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    executions: list[ExecutionRecord] = field(default_factory=list)
    objectives: dict[str, Any] = field(default_factory=dict)  # dict[str, Objective]
    plans: dict[str, Any] = field(default_factory=dict)            # dict[str, Plan]
    review_reports: dict[str, Any] = field(default_factory=dict)   # dict[str, ReviewReport]
    syntheses: dict[str, Any] = field(default_factory=dict)        # dict[str, SynthesisReport]
    task_graph: TaskGraph = field(init=False)
    scheduler: DependencyScheduler = field(init=False)
    task_execution_index: TaskExecutionIndex = field(init=False)
    artifact_store: ArtifactStore = field(init=False)
    execution_engine: Any = field(init=False)  # ExecutionEngine; typed as Any to avoid circular import
    planner: Any = field(init=False)           # TaskPlanner; typed as Any to avoid circular import
    review_engine: Any = field(init=False)     # ReviewEngine; typed as Any to avoid circular import
    memory_engine: Any = field(init=False)     # MemoryEngine; typed as Any to avoid circular import
    synthesis_engine: Any = field(init=False)  # SynthesisEngine; typed as Any to avoid circular import
    agent_registry: Any = field(init=False)    # AgentRegistry; typed as Any to avoid circular import
    collaboration_store: Any = field(init=False)   # CollaborationStore; typed as Any to avoid circular import
    collaboration_engine: Any = field(init=False) # CollaborationEngine; typed as Any to avoid circular import
    capability_registry: Any = field(init=False)   # CapabilityRegistry; typed as Any to avoid circular import
    plugin_manager: Any = field(init=False)        # PluginManager; typed as Any to avoid circular import

    def __post_init__(self) -> None:
        from execution_engine import ExecutionEngine  # deferred to avoid circular import
        from planner import TaskPlanner              # deferred to avoid circular import
        from review_engine import ReviewEngine        # deferred to avoid circular import
        from memory_engine import MemoryEngine        # deferred to avoid circular import
        from synthesis_engine import SynthesisEngine  # deferred to avoid circular import
        from agent_registry import AgentRegistry      # deferred to avoid circular import
        from collaboration_store import CollaborationStore  # deferred to avoid circular import
        from collaboration_engine import CollaborationEngine  # deferred to avoid circular import
        from capability_registry import CapabilityRegistry    # deferred to avoid circular import
        from plugin_manager import PluginManager        # deferred to avoid circular import
        self.task_graph = TaskGraph(workspace_id=self.workspace_id)
        self.scheduler = DependencyScheduler(task_graph=self.task_graph)
        self.task_execution_index = TaskExecutionIndex()
        self.artifact_store = ArtifactStore()
        self.execution_engine = ExecutionEngine(
            executor=_no_executor,
            task_graph=self.task_graph,
            execution_index=self.task_execution_index,
            execution_store_add=self._add_execution_record,
        )
        self.planner = TaskPlanner(workspace=self)
        self.review_engine = ReviewEngine(workspace=self)
        self.memory_engine = MemoryEngine(workspace=self)
        self.synthesis_engine = SynthesisEngine(workspace=self)
        self.agent_registry = AgentRegistry()
        self.collaboration_store = CollaborationStore()
        self.collaboration_engine = CollaborationEngine(
            workspace=self,
            registry=self.agent_registry,
            store=self.collaboration_store,
        )
        self.capability_registry = CapabilityRegistry()
        self.plugin_manager = PluginManager(capability_registry=self.capability_registry)

    def _add_execution_record(self, record: ExecutionRecord) -> None:
        self.executions.append(record)

    def configure_executor(self, executor: Any) -> None:
        """Replace the executor callable on the workspace's ExecutionEngine.

        Call this after workspace creation to wire in the real provider
        executor (e.g. the ``execute_model`` function from the MCP server).
        """
        from execution_engine import ExecutionEngine  # deferred to avoid circular import
        self.execution_engine = ExecutionEngine(
            executor=executor,
            task_graph=self.task_graph,
            execution_index=self.task_execution_index,
            execution_store_add=self._add_execution_record,
        )


def _no_executor(arguments: Any) -> Any:  # noqa: ANN401
    """Placeholder executor raised when none has been configured."""
    raise RuntimeError(
        "No executor configured on this workspace. "
        "Call workspace.configure_executor(fn) before calling execute_task."
    )


class WorkspaceStore:
    """Process-local workspace registry."""

    def __init__(self) -> None:
        self._workspaces: dict[str, TaskWorkspace] = {}
        self._lock = Lock()

    def create_workspace(self, title: str | None = None, metadata: dict[str, Any] | None = None) -> TaskWorkspace:
        workspace = TaskWorkspace(
            workspace_id=str(uuid4()),
            created_at=utc_now(),
            title=title,
            metadata=metadata or {},
        )
        with self._lock:
            self._workspaces[workspace.workspace_id] = workspace
        return workspace

    def get_workspace(self, workspace_id: str) -> TaskWorkspace:
        with self._lock:
            workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise KeyError(f"Workspace not found: {workspace_id}")
        return workspace

    def list_workspaces(self) -> list[TaskWorkspace]:
        with self._lock:
            return list(self._workspaces.values())

    def add_execution(self, workspace_id: str, record: ExecutionRecord) -> None:
        with self._lock:
            workspace = self._workspaces.get(workspace_id)
            if workspace is None:
                raise KeyError(f"Workspace not found: {workspace_id}")
            workspace.executions.append(record)


workspace_store = WorkspaceStore()


def workspace_to_dict(workspace: TaskWorkspace) -> dict[str, Any]:
    from artifact_store import Artifact  # local import for serialisation
    return {
        "workspace_id": workspace.workspace_id,
        "created_at": workspace.created_at,
        "title": workspace.title,
        "metadata": workspace.metadata,
        "objectives": [obj.to_dict() for obj in workspace.objectives.values()],
        "plans": [plan.to_dict() for plan in workspace.plans.values()],
        "review_reports": [rep.to_dict() for rep in workspace.review_reports.values()],
        "executions": [asdict(e) for e in workspace.executions],
        "task_graph": workspace.task_graph.to_dict(),
        "scheduler": workspace.scheduler.get_scheduler_state(),
        "execution_bindings": [b.to_dict() for b in workspace.task_execution_index.list_bindings()],
        "artifacts": [
            {
                "artifact_id": a.artifact_id,
                "task_id": a.task_id,
                "execution_id": a.execution_id,
                "workspace_id": a.workspace_id,
                "name": a.name,
                "artifact_type": a.artifact_type.value if hasattr(a.artifact_type, "value") else a.artifact_type,
                "mime_type": a.mime_type,
                "metadata": a.metadata,
                "created_at": a.created_at,
            }
            for a in workspace.artifact_store.list_artifacts()
        ],
        "memories": [m.to_dict() for m in workspace.memory_engine.list_memories()],
        "memory_summary": workspace.memory_engine.summarize().to_dict(),
        "syntheses": [s.to_dict() for s in workspace.syntheses.values()],
        "agents": [a.to_dict() for a in workspace.agent_registry.list_agents()],
        "sessions": [s.to_dict() for s in workspace.collaboration_engine.list_sessions()],
        "capabilities": [c.to_dict() for c in workspace.capability_registry.list_capabilities()],
        "plugins": [p.to_dict() for p in workspace.plugin_manager.list_plugins()],
        "capability_summary": workspace.capability_registry.summary(plugin_count=len(workspace.plugin_manager.list_plugins())).to_dict(),
    }


def workspace_summary(workspace: TaskWorkspace) -> dict[str, Any]:
    return {
        "workspace_id": workspace.workspace_id,
        "created_at": workspace.created_at,
        "title": workspace.title,
        "metadata": workspace.metadata,
        "execution_count": len(workspace.executions),
    }
