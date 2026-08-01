"""Dependency-Aware Task Scheduler.

Determines task execution eligibility based strictly on TaskGraph state
and dependency relationships. Does not make provider, model, prompt, or
orchestration decisions.
"""

from __future__ import annotations

from typing import Any

from task_graph import DependencyType, TaskGraph, TaskNode, TaskStatus


class DependencyScheduler:
    """Deterministic, dependency-driven scheduler for TaskGraph."""

    def __init__(self, task_graph: TaskGraph) -> None:
        self.task_graph = task_graph

    # ------------------------------------------------------------------
    # Core Readiness & Eligibility Checks
    # ------------------------------------------------------------------

    def is_task_ready(self, task_id: str) -> bool:
        """Return True if the task exists, is pending/ready, and all direct prerequisites are COMPLETED."""
        if task_id not in self.task_graph.nodes:
            return False
        node = self.task_graph.get_task(task_id)
        if node.status not in (TaskStatus.PENDING, TaskStatus.READY):
            return False

        prereqs = self.task_graph.get_dependencies(task_id)
        for prereq_id in prereqs:
            prereq_node = self.task_graph.nodes.get(prereq_id)
            if not prereq_node or prereq_node.status != TaskStatus.COMPLETED:
                return False
        return True

    def is_task_blocked(self, task_id: str) -> bool:
        """Return True if the task is pending/ready but cannot run because of uncompleted dependencies or cycles."""
        if task_id not in self.task_graph.nodes:
            return False
        node = self.task_graph.get_task(task_id)
        if node.status not in (TaskStatus.PENDING, TaskStatus.READY):
            return False

        # If it's part of a cycle, it's blocked
        cycles = self.detect_cycles()
        for cycle in cycles:
            if task_id in cycle:
                return True

        # Check if any prerequisite is uncompleted
        prereqs = self.task_graph.get_dependencies(task_id)
        for prereq_id in prereqs:
            prereq_node = self.task_graph.nodes.get(prereq_id)
            if not prereq_node or prereq_node.status != TaskStatus.COMPLETED:
                return True
        return False

    def can_execute(self, task_id: str) -> bool:
        """Return True if task can be executed right now (ready and unblocked)."""
        return self.is_task_ready(task_id)

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------

    def get_ready_tasks(self) -> list[TaskNode]:
        """Return all tasks that are ready for immediate execution, sorted deterministically."""
        ready = [
            node for tid, node in self.task_graph.nodes.items()
            if self.is_task_ready(tid)
        ]
        ready.sort(key=lambda n: (-n.priority, n.created_at, n.task_id))
        return ready

    def get_blocked_tasks(self) -> list[TaskNode]:
        """Return all tasks that are currently blocked by dependencies or cycles."""
        blocked = [
            node for tid, node in self.task_graph.nodes.items()
            if self.is_task_blocked(tid)
        ]
        blocked.sort(key=lambda n: (-n.priority, n.created_at, n.task_id))
        return blocked

    def get_completed_tasks(self) -> list[TaskNode]:
        """Return all tasks in COMPLETED status."""
        completed = [
            node for node in self.task_graph.nodes.values()
            if node.status == TaskStatus.COMPLETED
        ]
        completed.sort(key=lambda n: (n.completed_at or "", n.task_id))
        return completed

    def get_failed_tasks(self) -> list[TaskNode]:
        """Return all tasks in FAILED status."""
        failed = [
            node for node in self.task_graph.nodes.values()
            if node.status == TaskStatus.FAILED
        ]
        failed.sort(key=lambda n: (n.completed_at or "", n.task_id))
        return failed

    def next_execution_batch(self) -> list[TaskNode]:
        """Return all tasks that can be executed concurrently right now."""
        return self.get_ready_tasks()

    def get_execution_queue(self) -> list[TaskNode]:
        """Return ordered execution queue of executable/pending tasks in topological order."""
        pending_ids = {
            tid for tid, node in self.task_graph.nodes.items()
            if node.status in (TaskStatus.PENDING, TaskStatus.READY)
        }

        completed_ids = {
            tid for tid, node in self.task_graph.nodes.items()
            if node.status == TaskStatus.COMPLETED
        }

        queued_ids: set[str] = set()
        queue: list[TaskNode] = []

        while True:
            candidates: list[TaskNode] = []
            for tid in pending_ids - queued_ids:
                prereqs = self.task_graph.get_dependencies(tid)
                if all(p in completed_ids or p in queued_ids for p in prereqs):
                    candidates.append(self.task_graph.nodes[tid])

            if not candidates:
                break

            candidates.sort(key=lambda n: (-n.priority, n.created_at, n.task_id))
            for cand in candidates:
                queued_ids.add(cand.task_id)
                queue.append(cand)

        return queue

    def detect_cycles(self) -> list[list[str]]:
        """Detect and return any directed dependency cycles in the graph."""
        adj: dict[str, list[str]] = {tid: [] for tid in self.task_graph.nodes}
        for tid in self.task_graph.nodes:
            adj[tid] = self.task_graph.get_dependencies(tid)

        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)

            for neighbor in adj.get(node, []):
                if neighbor not in self.task_graph.nodes:
                    continue
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

    def get_scheduler_state(self) -> dict[str, Any]:
        """Return full scheduler state summary for the workspace."""
        cycles = self.detect_cycles()
        return {
            "workspace_id": self.task_graph.workspace_id,
            "ready_tasks": [n.to_dict() for n in self.get_ready_tasks()],
            "blocked_tasks": [n.to_dict() for n in self.get_blocked_tasks()],
            "completed_tasks": [n.to_dict() for n in self.get_completed_tasks()],
            "failed_tasks": [n.to_dict() for n in self.get_failed_tasks()],
            "execution_queue": [n.to_dict() for n in self.get_execution_queue()],
            "has_cycles": len(cycles) > 0,
            "cycles": cycles,
        }
