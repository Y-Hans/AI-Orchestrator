"""Tests for DependencyScheduler (Capability 4)."""

import pytest
from task_graph import DependencyType, TaskGraph, TaskStatus
from workspace import TaskWorkspace, workspace_store, workspace_to_dict
from brain import AntigravityBrain
from scheduler import DependencyScheduler
from ai_orchestrator_mcp import (
    get_ready_tasks_tool,
    get_blocked_tasks_tool,
    get_execution_queue_tool,
    get_scheduler_state_tool,
    McpError,
)


def mock_executor(arguments: dict) -> dict:
    """Mock executor returning success without making external API calls."""
    return {
        "ok": True,
        "provider": arguments.get("provider", "mock"),
        "model": arguments.get("model", "mock-model"),
        "text": "mocked response",
    }


def test_single_task_scheduler():
    workspace = workspace_store.create_workspace(title="Single Task Workspace")
    graph = workspace.task_graph
    scheduler = workspace.scheduler

    t1 = graph.create_task(title="Task 1", task_id="t1")

    assert scheduler.is_task_ready("t1") is True
    assert scheduler.is_task_blocked("t1") is False
    assert scheduler.can_execute("t1") is True

    ready = scheduler.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "t1"

    blocked = scheduler.get_blocked_tasks()
    assert len(blocked) == 0

    queue = scheduler.get_execution_queue()
    assert len(queue) == 1
    assert queue[0].task_id == "t1"

    batch = scheduler.next_execution_batch()
    assert len(batch) == 1
    assert batch[0].task_id == "t1"

    assert scheduler.detect_cycles() == []


def test_linear_dependencies():
    workspace = workspace_store.create_workspace(title="Linear Dep Workspace")
    graph = workspace.task_graph
    scheduler = workspace.scheduler

    # t1 -> t2 -> t3 (t2 depends on t1, t3 depends on t2)
    t1 = graph.create_task(title="Task 1", task_id="t1")
    t2 = graph.create_task(title="Task 2", task_id="t2")
    t3 = graph.create_task(title="Task 3", task_id="t3")

    graph.add_dependency(source_task_id="t2", target_task_id="t1", dependency_type=DependencyType.DEPENDS_ON)
    graph.add_dependency(source_task_id="t3", target_task_id="t2", dependency_type=DependencyType.DEPENDS_ON)

    # Initial state
    assert scheduler.is_task_ready("t1") is True
    assert scheduler.is_task_ready("t2") is False
    assert scheduler.is_task_ready("t3") is False

    assert scheduler.is_task_blocked("t1") is False
    assert scheduler.is_task_blocked("t2") is True
    assert scheduler.is_task_blocked("t3") is True

    queue = scheduler.get_execution_queue()
    assert [n.task_id for n in queue] == ["t1", "t2", "t3"]

    batch1 = scheduler.next_execution_batch()
    assert [n.task_id for n in batch1] == ["t1"]

    # Mark t1 completed
    graph.mark_completed("t1")

    assert scheduler.is_task_ready("t1") is False  # Already completed
    assert scheduler.is_task_ready("t2") is True
    assert scheduler.is_task_ready("t3") is False

    assert scheduler.is_task_blocked("t2") is False
    assert scheduler.is_task_blocked("t3") is True

    batch2 = scheduler.next_execution_batch()
    assert [n.task_id for n in batch2] == ["t2"]

    # Mark t2 completed
    graph.mark_completed("t2")

    assert scheduler.is_task_ready("t3") is True
    assert scheduler.is_task_blocked("t3") is False

    batch3 = scheduler.next_execution_batch()
    assert [n.task_id for n in batch3] == ["t3"]


def test_branching_dependencies():
    workspace = workspace_store.create_workspace(title="Branching Dep Workspace")
    graph = workspace.task_graph
    scheduler = workspace.scheduler

    # Root -> B1, B2, B3
    root = graph.create_task(title="Root", task_id="root")
    b1 = graph.create_task(title="Branch 1", task_id="b1", metadata={"priority": 10})
    b2 = graph.create_task(title="Branch 2", task_id="b2", metadata={"priority": 20})
    b3 = graph.create_task(title="Branch 3", task_id="b3", metadata={"priority": 5})

    b1.priority = 10
    b2.priority = 20
    b3.priority = 5

    graph.add_dependency(source_task_id="b1", target_task_id="root", dependency_type=DependencyType.DEPENDS_ON)
    graph.add_dependency(source_task_id="b2", target_task_id="root", dependency_type=DependencyType.DEPENDS_ON)
    graph.add_dependency(source_task_id="b3", target_task_id="root", dependency_type=DependencyType.DEPENDS_ON)

    assert scheduler.get_ready_tasks() == [root]
    assert len(scheduler.get_blocked_tasks()) == 3

    graph.mark_completed("root")

    ready = scheduler.get_ready_tasks()
    assert len(ready) == 3
    # Sorted by priority descending: b2 (20), b1 (10), b3 (5)
    assert [n.task_id for n in ready] == ["b2", "b1", "b3"]


def test_diamond_dependency_graph():
    workspace = workspace_store.create_workspace(title="Diamond Dep Workspace")
    graph = workspace.task_graph
    scheduler = workspace.scheduler

    # Root R -> B1, B2 -> Join J
    r = graph.create_task(title="Root", task_id="r")
    b1 = graph.create_task(title="Branch 1", task_id="b1")
    b2 = graph.create_task(title="Branch 2", task_id="b2")
    j = graph.create_task(title="Join", task_id="j")

    graph.add_dependency(source_task_id="b1", target_task_id="r", dependency_type=DependencyType.DEPENDS_ON)
    graph.add_dependency(source_task_id="b2", target_task_id="r", dependency_type=DependencyType.DEPENDS_ON)
    graph.add_dependency(source_task_id="j", target_task_id="b1", dependency_type=DependencyType.DEPENDS_ON)
    graph.add_dependency(source_task_id="j", target_task_id="b2", dependency_type=DependencyType.DEPENDS_ON)

    # Initial state
    assert scheduler.get_ready_tasks() == [r]
    assert set(n.task_id for n in scheduler.get_blocked_tasks()) == {"b1", "b2", "j"}

    # Root completes
    graph.mark_completed("r")
    assert set(n.task_id for n in scheduler.get_ready_tasks()) == {"b1", "b2"}
    assert scheduler.is_task_blocked("j") is True

    # B1 completes -> J still blocked because B2 is pending
    graph.mark_completed("b1")
    assert scheduler.is_task_blocked("j") is True
    assert scheduler.is_task_ready("j") is False

    # B2 completes -> J becomes ready
    graph.mark_completed("b2")
    assert scheduler.is_task_blocked("j") is False
    assert scheduler.is_task_ready("j") is True
    assert scheduler.get_ready_tasks() == [j]


def test_multiple_independent_root_tasks():
    workspace = workspace_store.create_workspace(title="Independent Roots Workspace")
    graph = workspace.task_graph
    scheduler = workspace.scheduler

    r1 = graph.create_task(title="Root 1", task_id="r1")
    r2 = graph.create_task(title="Root 2", task_id="r2")
    r3 = graph.create_task(title="Root 3", task_id="r3")

    ready = scheduler.get_ready_tasks()
    assert len(ready) == 3
    assert scheduler.get_blocked_tasks() == []
    assert scheduler.next_execution_batch() == ready


def test_failed_dependency_handling():
    workspace = workspace_store.create_workspace(title="Failed Dep Workspace")
    graph = workspace.task_graph
    scheduler = workspace.scheduler
    brain = AntigravityBrain(execute_model=mock_executor)

    t1 = graph.create_task(title="Task 1", task_id="t1")
    t2 = graph.create_task(title="Task 2", task_id="t2")

    graph.add_dependency(source_task_id="t2", target_task_id="t1", dependency_type=DependencyType.DEPENDS_ON)

    # Mark t1 as FAILED
    graph.mark_failed("t1")

    assert scheduler.get_failed_tasks() == [t1]
    assert scheduler.is_task_ready("t2") is False
    assert scheduler.is_task_blocked("t2") is True

    # Attempting to execute blocked t2 via Brain raises ValueError
    with pytest.raises(ValueError, match="blocked by uncompleted dependencies"):
        brain.execute_task({
            "workspace_id": workspace.workspace_id,
            "task_id": "t2",
            "provider": "gemini",
            "prompt": "run t2",
        })


def test_cycle_detection():
    workspace = workspace_store.create_workspace(title="Cycle Workspace")
    graph = workspace.task_graph
    scheduler = workspace.scheduler

    t1 = graph.create_task(title="Task 1", task_id="t1")
    t2 = graph.create_task(title="Task 2", task_id="t2")

    # t1 depends on t2 and t2 depends on t1 -> Cycle!
    graph.add_dependency(source_task_id="t1", target_task_id="t2", dependency_type=DependencyType.DEPENDS_ON)
    graph.add_dependency(source_task_id="t2", target_task_id="t1", dependency_type=DependencyType.DEPENDS_ON)

    cycles = scheduler.detect_cycles()
    assert len(cycles) > 0
    cycle_nodes = cycles[0]
    assert "t1" in cycle_nodes and "t2" in cycle_nodes

    assert scheduler.is_task_ready("t1") is False
    assert scheduler.is_task_ready("t2") is False
    assert scheduler.is_task_blocked("t1") is True
    assert scheduler.is_task_blocked("t2") is True
    assert scheduler.get_ready_tasks() == []


def test_scheduler_workspace_integration():
    workspace = workspace_store.create_workspace(title="Integration Workspace")
    assert hasattr(workspace, "scheduler")
    assert isinstance(workspace.scheduler, DependencyScheduler)
    assert workspace.scheduler.task_graph == workspace.task_graph

    graph = workspace.task_graph
    graph.create_task(title="Task 1", task_id="t1")

    serialized = workspace_to_dict(workspace)
    assert "scheduler" in serialized
    assert serialized["scheduler"]["workspace_id"] == workspace.workspace_id
    assert len(serialized["scheduler"]["ready_tasks"]) == 1
    assert serialized["scheduler"]["ready_tasks"][0]["task_id"] == "t1"


def test_scheduler_brain_integration():
    workspace = workspace_store.create_workspace(title="Brain Integration Workspace")
    brain = AntigravityBrain(execute_model=mock_executor)
    ws_id = workspace.workspace_id

    graph = workspace.task_graph
    t1 = graph.create_task(title="Task 1", task_id="t1")
    t2 = graph.create_task(title="Task 2", task_id="t2")
    graph.add_dependency(source_task_id="t2", target_task_id="t1", dependency_type=DependencyType.DEPENDS_ON)

    # 1. Query scheduler state via Brain
    ready_resp = brain.get_ready_tasks(ws_id)
    assert len(ready_resp["ready_tasks"]) == 1
    assert ready_resp["ready_tasks"][0]["task_id"] == "t1"

    blocked_resp = brain.get_blocked_tasks(ws_id)
    assert len(blocked_resp["blocked_tasks"]) == 1
    assert blocked_resp["blocked_tasks"][0]["task_id"] == "t2"

    state_resp = brain.get_scheduler_state(ws_id)
    assert state_resp["workspace_id"] == ws_id
    assert state_resp["has_cycles"] is False

    # 2. Reject blocked task execution
    with pytest.raises(ValueError, match="blocked"):
        brain.execute_task({
            "workspace_id": ws_id,
            "task_id": "t2",
            "provider": "gemini",
            "prompt": "run t2",
        })

    # 3. Execute ready task t1 -> succeeds
    res1 = brain.execute_task({
        "workspace_id": ws_id,
        "task_id": "t1",
        "provider": "gemini",
        "prompt": "run t1",
    })
    assert res1["success"] is True

    # 4. Now t2 becomes ready and succeeds
    ready_resp2 = brain.get_ready_tasks(ws_id)
    assert len(ready_resp2["ready_tasks"]) == 1
    assert ready_resp2["ready_tasks"][0]["task_id"] == "t2"

    res2 = brain.execute_task({
        "workspace_id": ws_id,
        "task_id": "t2",
        "provider": "gemini",
        "prompt": "run t2",
    })
    assert res2["success"] is True


def test_mcp_scheduler_tools():
    workspace = workspace_store.create_workspace(title="MCP Tools Workspace")
    ws_id = workspace.workspace_id
    graph = workspace.task_graph

    t1 = graph.create_task(title="Task 1", task_id="t1")
    t2 = graph.create_task(title="Task 2", task_id="t2")
    graph.add_dependency(source_task_id="t2", target_task_id="t1", dependency_type=DependencyType.DEPENDS_ON)

    # 1. get_ready_tasks
    ready_res = get_ready_tasks_tool({"workspace_id": ws_id})
    assert "ready_tasks" in ready_res
    assert len(ready_res["ready_tasks"]) == 1
    assert ready_res["ready_tasks"][0]["task_id"] == "t1"

    # 2. get_blocked_tasks
    blocked_res = get_blocked_tasks_tool({"workspace_id": ws_id})
    assert "blocked_tasks" in blocked_res
    assert len(blocked_res["blocked_tasks"]) == 1
    assert blocked_res["blocked_tasks"][0]["task_id"] == "t2"

    # 3. get_execution_queue
    queue_res = get_execution_queue_tool({"workspace_id": ws_id})
    assert "execution_queue" in queue_res
    assert [t["task_id"] for t in queue_res["execution_queue"]] == ["t1", "t2"]

    # 4. get_scheduler_state
    state_res = get_scheduler_state_tool({"workspace_id": ws_id})
    assert state_res["workspace_id"] == ws_id
    assert state_res["has_cycles"] is False

    # 5. Invalid workspace_id error handling
    with pytest.raises(McpError, match="Workspace not found"):
        get_ready_tasks_tool({"workspace_id": "non-existent-workspace"})
