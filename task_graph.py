"""In-memory Task Graph representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4




def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionState(str, Enum):
    """Lifecycle execution state of a TaskNode."""
    WAITING = "WAITING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"


class DependencyType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    BLOCKS = "BLOCKS"
    RELATED = "RELATED"


@dataclass
class TaskNode:
    task_id: str
    workspace_id: str
    parent_task_id: str | None
    title: str
    description: str | None
    status: TaskStatus
    metadata: dict[str, Any]
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    # Capability 3 – execution lifecycle fields (all optional with safe defaults)
    priority: int = 0
    attempt_count: int = 0
    execution_state: ExecutionState = ExecutionState.WAITING
    last_execution_id: str | None = None
    result_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "workspace_id": self.workspace_id,
            "parent_task_id": self.parent_task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "priority": self.priority,
            "attempt_count": self.attempt_count,
            "execution_state": self.execution_state.value if hasattr(self.execution_state, "value") else self.execution_state,
            "last_execution_id": self.last_execution_id,
            "result_summary": self.result_summary,
        }

    # ------------------------------------------------------------------
    # Lifecycle mutation methods
    # ------------------------------------------------------------------

    def start_execution(self, execution_id: str) -> None:
        """Transition the node into RUNNING state for the given execution."""
        self.status = TaskStatus.RUNNING
        self.execution_state = ExecutionState.RUNNING
        self.last_execution_id = execution_id
        self.attempt_count += 1
        if not self.started_at:
            self.started_at = utc_now()

    def complete_execution(self, result_summary: str | None = None) -> None:
        """Transition the node into COMPLETED state."""
        self.status = TaskStatus.COMPLETED
        self.execution_state = ExecutionState.COMPLETED
        self.result_summary = result_summary
        self.completed_at = utc_now()

    def fail_execution(self, result_summary: str | None = None) -> None:
        """Transition the node into FAILED state."""
        self.status = TaskStatus.FAILED
        self.execution_state = ExecutionState.FAILED
        self.result_summary = result_summary
        self.completed_at = utc_now()

    def reset_execution(self) -> None:
        """Reset the node to WAITING/PENDING so it can be retried."""
        self.status = TaskStatus.PENDING
        self.execution_state = ExecutionState.WAITING
        self.started_at = None
        self.completed_at = None
        self.last_execution_id = None
        self.result_summary = None


@dataclass
class TaskEdge:
    source_task_id: str
    target_task_id: str
    dependency_type: DependencyType

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_task_id": self.source_task_id,
            "target_task_id": self.target_task_id,
            "dependency_type": self.dependency_type.value if hasattr(self.dependency_type, "value") else self.dependency_type,
        }


@dataclass
class TaskGraph:
    workspace_id: str
    nodes: dict[str, TaskNode] = field(default_factory=dict)
    edges: list[TaskEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "nodes": {tid: node.to_dict() for tid, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
        }

    def create_task(
        self,
        title: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: TaskStatus = TaskStatus.PENDING,
        task_id: str | None = None,
    ) -> TaskNode:
        tid = task_id or str(uuid4())
        if tid in self.nodes:
            raise ValueError(f"Task with ID {tid} already exists.")

        now = utc_now()
        started_at = None
        completed_at = None

        if status == TaskStatus.RUNNING:
            started_at = now
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            started_at = now
            completed_at = now

        node = TaskNode(
            task_id=tid,
            workspace_id=self.workspace_id,
            parent_task_id=None,
            title=title,
            description=description,
            status=status,
            metadata=metadata or {},
            created_at=now,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.nodes[tid] = node
        return node

    def create_subtask(
        self,
        parent_task_id: str,
        title: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: TaskStatus = TaskStatus.PENDING,
        task_id: str | None = None,
    ) -> TaskNode:
        if parent_task_id not in self.nodes:
            raise KeyError(f"Parent task not found: {parent_task_id}")

        tid = task_id or str(uuid4())
        if tid in self.nodes:
            raise ValueError(f"Task with ID {tid} already exists.")

        now = utc_now()
        started_at = None
        completed_at = None

        if status == TaskStatus.RUNNING:
            started_at = now
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            started_at = now
            completed_at = now

        node = TaskNode(
            task_id=tid,
            workspace_id=self.workspace_id,
            parent_task_id=parent_task_id,
            title=title,
            description=description,
            status=status,
            metadata=metadata or {},
            created_at=now,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.nodes[tid] = node
        return node

    def add_dependency(
        self,
        source_task_id: str,
        target_task_id: str,
        dependency_type: DependencyType = DependencyType.DEPENDS_ON,
    ) -> TaskEdge:
        if source_task_id not in self.nodes:
            raise KeyError(f"Source task not found: {source_task_id}")
        if target_task_id not in self.nodes:
            raise KeyError(f"Target task not found: {target_task_id}")

        edge = TaskEdge(
            source_task_id=source_task_id,
            target_task_id=target_task_id,
            dependency_type=dependency_type,
        )
        if edge not in self.edges:
            self.edges.append(edge)
        return edge

    def get_task(self, task_id: str) -> TaskNode:
        if task_id not in self.nodes:
            raise KeyError(f"Task not found: {task_id}")
        return self.nodes[task_id]

    def list_tasks(self) -> list[TaskNode]:
        return list(self.nodes.values())

    def get_children(self, task_id: str) -> list[TaskNode]:
        if task_id not in self.nodes:
            raise KeyError(f"Task not found: {task_id}")
        return [node for node in self.nodes.values() if node.parent_task_id == task_id]

    def get_parents(self, task_id: str) -> list[TaskNode]:
        if task_id not in self.nodes:
            raise KeyError(f"Task not found: {task_id}")
        parent_id = self.nodes[task_id].parent_task_id
        if parent_id and parent_id in self.nodes:
            return [self.nodes[parent_id]]
        return []

    def get_dependencies(self, task_id: str) -> list[str]:
        """Return IDs of tasks that `task_id` directly depends on (prerequisites)."""
        if task_id not in self.nodes:
            raise KeyError(f"Task not found: {task_id}")
        prereqs = []
        for edge in self.edges:
            if edge.dependency_type == DependencyType.DEPENDS_ON:
                if edge.source_task_id == task_id:
                    prereqs.append(edge.target_task_id)
            elif edge.dependency_type == DependencyType.BLOCKS:
                if edge.target_task_id == task_id:
                    prereqs.append(edge.source_task_id)
        return prereqs

    def get_dependents(self, task_id: str) -> list[str]:
        """Return IDs of tasks that directly depend on `task_id`."""
        if task_id not in self.nodes:
            raise KeyError(f"Task not found: {task_id}")
        dependents = []
        for edge in self.edges:
            if edge.dependency_type == DependencyType.DEPENDS_ON:
                if edge.target_task_id == task_id:
                    dependents.append(edge.source_task_id)
            elif edge.dependency_type == DependencyType.BLOCKS:
                if edge.source_task_id == task_id:
                    dependents.append(edge.target_task_id)
        return dependents

    def mark_running(self, task_id: str) -> TaskNode:
        node = self.get_task(task_id)
        node.status = TaskStatus.RUNNING
        if not node.started_at:
            node.started_at = utc_now()
        return node

    def mark_completed(self, task_id: str) -> TaskNode:
        node = self.get_task(task_id)
        node.status = TaskStatus.COMPLETED
        if not node.started_at:
            node.started_at = utc_now()
        node.completed_at = utc_now()
        return node

    def mark_failed(self, task_id: str) -> TaskNode:
        node = self.get_task(task_id)
        node.status = TaskStatus.FAILED
        if not node.started_at:
            node.started_at = utc_now()
        node.completed_at = utc_now()
        return node
