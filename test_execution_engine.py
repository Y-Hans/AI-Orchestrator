"""Integration tests for Capability 3: Autonomous Task Execution Framework.

All provider calls are mocked.  No network traffic is produced.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from artifact_store import Artifact, ArtifactStore, ArtifactType
from execution_binding import ExecutionType, TaskExecutionIndex
from execution_engine import ExecutionEngine
from execution_result import ExecutionResult
from task_graph import ExecutionState, TaskGraph, TaskStatus
from workspace import TaskWorkspace, workspace_store, workspace_to_dict


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_result(success: bool = True, response: str = "hello") -> ExecutionResult:
    from uuid import uuid4
    return ExecutionResult(
        execution_id=str(uuid4()),
        provider="gemini",
        model="gemini-1.5-flash",
        prompt="test prompt",
        response=response if success else None,
        error=None if success else {"code": "TestError", "message": "boom"},
        latency_ms=42,
        success=success,
    )


def _make_engine(executor, workspace: TaskWorkspace) -> ExecutionEngine:
    return ExecutionEngine(
        executor=executor,
        task_graph=workspace.task_graph,
        execution_index=workspace.task_execution_index,
        execution_store_add=workspace._add_execution_record,
    )


@pytest.fixture
def workspace() -> TaskWorkspace:
    return workspace_store.create_workspace(title="test-workspace")


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def test_fields_set_correctly(self):
        r = _make_result(success=True, response="ok")
        assert r.success is True
        assert r.response == "ok"
        assert r.error is None
        assert r.latency_ms == 42

    def test_failure_result(self):
        r = _make_result(success=False)
        assert r.success is False
        assert r.response is None
        assert r.error["code"] == "TestError"


# ---------------------------------------------------------------------------
# ArtifactStore
# ---------------------------------------------------------------------------

class TestArtifactStore:
    def _artifact(self, workspace_id="ws1", task_id="t1", execution_id=None) -> Artifact:
        from uuid import uuid4
        from datetime import UTC, datetime
        return Artifact(
            artifact_id=str(uuid4()),
            task_id=task_id,
            execution_id=execution_id,
            workspace_id=workspace_id,
            name="test-artifact",
            artifact_type=ArtifactType.TEXT,
            mime_type="text/plain",
            content="hello",
            metadata={},
            created_at=datetime.now(UTC).isoformat(),
        )

    def test_create_and_get(self):
        store = ArtifactStore()
        a = self._artifact()
        store.create_artifact(a)
        retrieved = store.get_artifact(a.artifact_id)
        assert retrieved is a

    def test_list_all(self):
        store = ArtifactStore()
        a1 = self._artifact()
        a2 = self._artifact()
        store.create_artifact(a1)
        store.create_artifact(a2)
        assert len(store.list_artifacts()) == 2

    def test_list_task_artifacts(self):
        store = ArtifactStore()
        a1 = self._artifact(task_id="t-A")
        a2 = self._artifact(task_id="t-B")
        store.create_artifact(a1)
        store.create_artifact(a2)
        assert store.list_task_artifacts("t-A") == [a1]

    def test_list_execution_artifacts(self):
        store = ArtifactStore()
        a1 = self._artifact(execution_id="exec-1")
        a2 = self._artifact(execution_id=None)
        store.create_artifact(a1)
        store.create_artifact(a2)
        assert store.list_execution_artifacts("exec-1") == [a1]

    def test_delete(self):
        store = ArtifactStore()
        a = self._artifact()
        store.create_artifact(a)
        store.delete_artifact(a.artifact_id)
        assert store.list_artifacts() == []

    def test_get_missing_raises(self):
        store = ArtifactStore()
        with pytest.raises(KeyError):
            store.get_artifact("nonexistent")


# ---------------------------------------------------------------------------
# TaskNode lifecycle methods
# ---------------------------------------------------------------------------

class TestTaskNodeLifecycle:
    def test_start_execution(self, workspace):
        graph = workspace.task_graph
        task = graph.create_task("test task")
        assert task.attempt_count == 0
        assert task.execution_state == ExecutionState.WAITING

        task.start_execution("exec-1")
        assert task.status == TaskStatus.RUNNING
        assert task.execution_state == ExecutionState.RUNNING
        assert task.attempt_count == 1
        assert task.last_execution_id == "exec-1"
        assert task.started_at is not None

    def test_start_execution_increments_attempt_count(self, workspace):
        graph = workspace.task_graph
        task = graph.create_task("test task")
        task.start_execution("exec-1")
        task.fail_execution()
        task.reset_execution()
        task.start_execution("exec-2")
        assert task.attempt_count == 2

    def test_complete_execution(self, workspace):
        graph = workspace.task_graph
        task = graph.create_task("test task")
        task.start_execution("exec-1")
        task.complete_execution(result_summary="done")
        assert task.status == TaskStatus.COMPLETED
        assert task.execution_state == ExecutionState.COMPLETED
        assert task.result_summary == "done"
        assert task.completed_at is not None

    def test_fail_execution(self, workspace):
        graph = workspace.task_graph
        task = graph.create_task("test task")
        task.start_execution("exec-1")
        task.fail_execution(result_summary="error: boom")
        assert task.status == TaskStatus.FAILED
        assert task.execution_state == ExecutionState.FAILED
        assert task.result_summary == "error: boom"
        assert task.completed_at is not None

    def test_reset_execution(self, workspace):
        graph = workspace.task_graph
        task = graph.create_task("test task")
        task.start_execution("exec-1")
        task.fail_execution("error")
        task.reset_execution()
        assert task.status == TaskStatus.PENDING
        assert task.execution_state == ExecutionState.WAITING
        assert task.started_at is None
        assert task.completed_at is None
        assert task.last_execution_id is None
        assert task.result_summary is None

    def test_to_dict_includes_lifecycle_fields(self, workspace):
        graph = workspace.task_graph
        task = graph.create_task("test task")
        d = task.to_dict()
        assert "priority" in d
        assert "attempt_count" in d
        assert "execution_state" in d
        assert "last_execution_id" in d
        assert "result_summary" in d
        assert d["execution_state"] == "WAITING"


# ---------------------------------------------------------------------------
# ExecutionEngine – single task
# ---------------------------------------------------------------------------

class TestExecutionEngineExecuteTask:
    def test_successful_execution_updates_task(self, workspace):
        task = workspace.task_graph.create_task("my task")
        executor = MagicMock(return_value=_make_result(success=True, response="great response"))
        engine = _make_engine(executor, workspace)

        result = engine.execute_task(task.task_id, {"provider": "gemini", "prompt": "hello"})

        assert result["success"] is True
        assert result["task_id"] == task.task_id
        assert "execution_id" in result
        assert result["execution_type"] == "PRIMARY"

        # Task node must reflect COMPLETED state
        assert task.status == TaskStatus.COMPLETED
        assert task.execution_state == ExecutionState.COMPLETED
        assert task.attempt_count == 1
        assert task.result_summary is not None

    def test_failed_execution_updates_task(self, workspace):
        task = workspace.task_graph.create_task("failing task")
        executor = MagicMock(return_value=_make_result(success=False))
        engine = _make_engine(executor, workspace)

        result = engine.execute_task(task.task_id, {"provider": "gemini", "prompt": "hello"})

        assert result["success"] is False
        assert "error" in result
        assert task.status == TaskStatus.FAILED
        assert task.execution_state == ExecutionState.FAILED

    def test_executor_exception_marks_task_failed(self, workspace):
        task = workspace.task_graph.create_task("boom task")

        def boom(_args):
            raise RuntimeError("network timeout")

        engine = _make_engine(boom, workspace)
        result = engine.execute_task(task.task_id, {"provider": "gemini", "prompt": "hi"})

        assert result["success"] is False
        assert task.status == TaskStatus.FAILED

    def test_execution_record_persisted(self, workspace):
        task = workspace.task_graph.create_task("record task")
        executor = MagicMock(return_value=_make_result(success=True))
        engine = _make_engine(executor, workspace)

        engine.execute_task(task.task_id, {"provider": "gemini", "prompt": "p"})

        assert len(workspace.executions) == 1
        record = workspace.executions[0]
        assert record.provider == "gemini"
        assert record.success is True

    def test_execution_binding_created(self, workspace):
        task = workspace.task_graph.create_task("bind task")
        executor = MagicMock(return_value=_make_result(success=True))
        engine = _make_engine(executor, workspace)

        result = engine.execute_task(task.task_id, {"provider": "gemini", "prompt": "p"}, execution_type="REVIEW")

        bindings = workspace.task_execution_index.get_task_executions(task.task_id)
        assert len(bindings) == 1
        assert bindings[0].execution_type == ExecutionType.REVIEW
        assert bindings[0].execution_id == result["execution_id"]

    def test_missing_task_raises(self, workspace):
        executor = MagicMock(return_value=_make_result())
        engine = _make_engine(executor, workspace)
        with pytest.raises(KeyError):
            engine.execute_task("nonexistent-task-id", {"provider": "gemini", "prompt": "hi"})


# ---------------------------------------------------------------------------
# ExecutionEngine – multiple tasks (sequential)
# ---------------------------------------------------------------------------

class TestExecutionEngineExecuteTasks:
    def test_sequential_execution(self, workspace):
        t1 = workspace.task_graph.create_task("task 1")
        t2 = workspace.task_graph.create_task("task 2")
        executor = MagicMock(side_effect=[
            _make_result(success=True, response="r1"),
            _make_result(success=True, response="r2"),
        ])
        engine = _make_engine(executor, workspace)

        result = engine.execute_tasks(
            task_ids=[t1.task_id, t2.task_id],
            arguments_list=[
                {"provider": "gemini", "prompt": "p1"},
                {"provider": "gemini", "prompt": "p2"},
            ],
        )

        assert len(result["results"]) == 2
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is True
        assert t1.status == TaskStatus.COMPLETED
        assert t2.status == TaskStatus.COMPLETED

    def test_parallel_execution(self, workspace):
        t1 = workspace.task_graph.create_task("p-task 1")
        t2 = workspace.task_graph.create_task("p-task 2")
        # parallel calls may interleave, use thread-safe mock
        from unittest.mock import patch
        import threading

        call_count = {"n": 0}
        lock = threading.Lock()

        def _executor(_args):
            with lock:
                call_count["n"] += 1
            return _make_result(success=True)

        engine = _make_engine(_executor, workspace)
        result = engine.execute_tasks(
            task_ids=[t1.task_id, t2.task_id],
            arguments_list=[
                {"provider": "gemini", "prompt": "p1"},
                {"provider": "gemini", "prompt": "p2"},
            ],
            parallel=True,
        )

        assert len(result["results"]) == 2
        assert call_count["n"] == 2

    def test_mismatched_lengths_raise(self, workspace):
        t1 = workspace.task_graph.create_task("t1")
        engine = _make_engine(MagicMock(), workspace)
        with pytest.raises(ValueError, match="same length"):
            engine.execute_tasks(
                task_ids=[t1.task_id],
                arguments_list=[{}, {}],
            )


# ---------------------------------------------------------------------------
# TaskWorkspace integration
# ---------------------------------------------------------------------------

class TestTaskWorkspaceIntegration:
    def test_workspace_has_artifact_store(self, workspace):
        assert workspace.artifact_store is not None
        assert isinstance(workspace.artifact_store, ArtifactStore)

    def test_workspace_has_execution_engine(self, workspace):
        assert workspace.execution_engine is not None

    def test_configure_executor_updates_engine(self, workspace):
        task = workspace.task_graph.create_task("wired task")
        executor = MagicMock(return_value=_make_result(success=True))
        workspace.configure_executor(executor)
        result = workspace.execution_engine.execute_task(
            task.task_id, {"provider": "gemini", "prompt": "hi"}
        )
        assert result["success"] is True
        executor.assert_called_once()

    def test_workspace_to_dict_includes_artifacts(self, workspace):
        from uuid import uuid4
        from datetime import UTC, datetime
        artifact = Artifact(
            artifact_id=str(uuid4()),
            task_id=None,
            execution_id=None,
            workspace_id=workspace.workspace_id,
            name="readme",
            artifact_type=ArtifactType.MARKDOWN,
            mime_type="text/markdown",
            content="# Hello",
            metadata={},
            created_at=datetime.now(UTC).isoformat(),
        )
        workspace.artifact_store.create_artifact(artifact)
        d = workspace_to_dict(workspace)
        assert "artifacts" in d
        assert len(d["artifacts"]) == 1
        assert d["artifacts"][0]["name"] == "readme"

    def test_no_executor_returns_failed_result(self, workspace):
        """Workspace without a configured executor produces a failed ExecutionResult.

        The ExecutionEngine catches all executor exceptions internally and converts
        them to a failed result to ensure the task lifecycle always reaches a
        terminal state.
        """
        task = workspace.task_graph.create_task("unconfigured")
        # The engine catches RuntimeError from _no_executor and marks the task FAILED
        result = workspace.execution_engine.execute_task(
            task.task_id, {"provider": "gemini", "prompt": "hi"}
        )
        assert result["success"] is False
        assert task.status == TaskStatus.FAILED


# ---------------------------------------------------------------------------
# Brain integration (execute_task / execute_tasks delegation)
# ---------------------------------------------------------------------------

class TestBrainExecuteTask:
    def _make_brain(self, raw_response: dict):
        from brain import AntigravityBrain
        return AntigravityBrain(execute_model=MagicMock(return_value=raw_response))

    def test_execute_task_success(self):
        ws = workspace_store.create_workspace(title="brain-ws")
        task = ws.task_graph.create_task("brain task")
        brain = self._make_brain({"ok": True, "provider": "gemini", "model": "gemini-1.5-flash", "text": "answer"})

        result = brain.execute_task({
            "workspace_id": ws.workspace_id,
            "task_id": task.task_id,
            "provider": "gemini",
            "prompt": "q?",
        })

        assert result["success"] is True
        assert task.status == TaskStatus.COMPLETED

    def test_execute_task_missing_workspace_id(self):
        from brain import AntigravityBrain
        brain = AntigravityBrain(execute_model=MagicMock())
        with pytest.raises(ValueError, match="workspace_id"):
            brain.execute_task({"task_id": "t", "provider": "gemini", "prompt": "p"})

    def test_execute_task_missing_task_id(self):
        ws = workspace_store.create_workspace(title="brain-ws-2")
        from brain import AntigravityBrain
        brain = AntigravityBrain(execute_model=MagicMock())
        with pytest.raises(ValueError, match="task_id"):
            brain.execute_task({"workspace_id": ws.workspace_id, "provider": "gemini", "prompt": "p"})

    def test_execute_tasks_success(self):
        ws = workspace_store.create_workspace(title="brain-multi-ws")
        t1 = ws.task_graph.create_task("task A")
        t2 = ws.task_graph.create_task("task B")
        raw = {"ok": True, "provider": "gemini", "model": "gemini-1.5-flash", "text": "res"}
        brain = self._make_brain(raw)

        result = brain.execute_tasks({
            "workspace_id": ws.workspace_id,
            "tasks": [
                {"task_id": t1.task_id, "provider": "gemini", "prompt": "q1"},
                {"task_id": t2.task_id, "provider": "gemini", "prompt": "q2"},
            ],
        })

        assert len(result["results"]) == 2
        assert all(r["success"] for r in result["results"])

    def test_execute_tasks_empty_list_raises(self):
        ws = workspace_store.create_workspace(title="brain-empty-ws")
        from brain import AntigravityBrain
        brain = AntigravityBrain(execute_model=MagicMock())
        with pytest.raises(ValueError, match="non-empty"):
            brain.execute_tasks({"workspace_id": ws.workspace_id, "tasks": []})
