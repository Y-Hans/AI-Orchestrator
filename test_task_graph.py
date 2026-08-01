import pytest
from task_graph import TaskStatus, DependencyType, TaskGraph, TaskNode, TaskEdge
from workspace import workspace_store
from ai_orchestrator_mcp import (
    create_task_tool,
    create_subtask_tool,
    add_dependency_tool,
    get_task_tool,
    list_tasks_tool,
    McpError,
)


def test_workspace_owns_graph():
    workspace = workspace_store.create_workspace(title="Graph Owner Test")
    assert hasattr(workspace, "task_graph")
    assert isinstance(workspace.task_graph, TaskGraph)
    assert workspace.task_graph.workspace_id == workspace.workspace_id
    assert len(workspace.task_graph.nodes) == 0
    assert len(workspace.task_graph.edges) == 0


def test_task_creation():
    workspace = workspace_store.create_workspace(title="Task Creation Test")
    graph = workspace.task_graph

    # Test creating a task with generated ID
    node = graph.create_task(
        title="Root Task",
        description="First task",
        metadata={"priority": "high"},
    )
    assert node.task_id
    assert node.workspace_id == workspace.workspace_id
    assert node.parent_task_id is None
    assert node.title == "Root Task"
    assert node.description == "First task"
    assert node.status == TaskStatus.PENDING
    assert node.metadata == {"priority": "high"}
    assert node.created_at
    assert node.started_at is None
    assert node.completed_at is None

    # Test retrieving the task
    retrieved = graph.get_task(node.task_id)
    assert retrieved == node

    # Test creating task with pre-specified ID
    custom_id = "custom-123"
    node_custom = graph.create_task(title="Custom Task", task_id=custom_id)
    assert node_custom.task_id == custom_id
    assert graph.get_task(custom_id) == node_custom

    # Test duplicate ID failure
    with pytest.raises(ValueError, match="already exists"):
        graph.create_task(title="Duplicate", task_id=custom_id)


def test_subtask_creation():
    workspace = workspace_store.create_workspace(title="Subtask Test")
    graph = workspace.task_graph

    parent = graph.create_task(title="Parent Task")
    sub = graph.create_subtask(
        parent_task_id=parent.task_id,
        title="Sub Task",
        description="Subtask details",
    )

    assert sub.task_id
    assert sub.parent_task_id == parent.task_id
    assert sub.title == "Sub Task"
    assert sub.description == "Subtask details"
    assert sub.status == TaskStatus.PENDING

    # Subtask for non-existent parent
    with pytest.raises(KeyError, match="Parent task not found"):
        graph.create_subtask(parent_task_id="invalid-id", title="Orphan Subtask")


def test_dependency_creation():
    workspace = workspace_store.create_workspace(title="Dependency Test")
    graph = workspace.task_graph

    t1 = graph.create_task(title="Task 1")
    t2 = graph.create_task(title="Task 2")

    edge = graph.add_dependency(
        source_task_id=t1.task_id,
        target_task_id=t2.task_id,
        dependency_type=DependencyType.DEPENDS_ON,
    )

    assert edge.source_task_id == t1.task_id
    assert edge.target_task_id == t2.task_id
    assert edge.dependency_type == DependencyType.DEPENDS_ON
    assert edge in graph.edges

    # Check duplicate edge isn't added
    assert len(graph.edges) == 1
    graph.add_dependency(
        source_task_id=t1.task_id,
        target_task_id=t2.task_id,
        dependency_type=DependencyType.DEPENDS_ON,
    )
    assert len(graph.edges) == 1

    # Check key errors for invalid tasks
    with pytest.raises(KeyError, match="Source task not found"):
        graph.add_dependency(source_task_id="invalid", target_task_id=t2.task_id)

    with pytest.raises(KeyError, match="Target task not found"):
        graph.add_dependency(source_task_id=t1.task_id, target_task_id="invalid")


def test_parent_child_lookup():
    workspace = workspace_store.create_workspace(title="Lookup Test")
    graph = workspace.task_graph

    parent = graph.create_task(title="Parent")
    sub1 = graph.create_subtask(parent_task_id=parent.task_id, title="Sub 1")
    sub2 = graph.create_subtask(parent_task_id=parent.task_id, title="Sub 2")

    children = graph.get_children(parent.task_id)
    assert len(children) == 2
    assert sub1 in children
    assert sub2 in children

    parents = graph.get_parents(sub1.task_id)
    assert len(parents) == 1
    assert parents[0] == parent

    # Root task parent lookup
    assert graph.get_parents(parent.task_id) == []

    # Non-existent task lookups
    with pytest.raises(KeyError):
        graph.get_children("invalid")
    with pytest.raises(KeyError):
        graph.get_parents("invalid")


def test_status_transitions():
    workspace = workspace_store.create_workspace(title="Transitions Test")
    graph = workspace.task_graph

    t = graph.create_task(title="Transition Task")
    assert t.status == TaskStatus.PENDING
    assert t.started_at is None
    assert t.completed_at is None

    # Mark running
    graph.mark_running(t.task_id)
    assert t.status == TaskStatus.RUNNING
    assert t.started_at
    assert t.completed_at is None

    # Mark completed
    graph.mark_completed(t.task_id)
    assert t.status == TaskStatus.COMPLETED
    assert t.completed_at
    assert t.started_at

    # Mark failed
    t2 = graph.create_task(title="Failed Task")
    graph.mark_failed(t2.task_id)
    assert t2.status == TaskStatus.FAILED
    assert t2.started_at
    assert t2.completed_at


def test_mcp_task_graph_tools():
    workspace = workspace_store.create_workspace(title="MCP Tools Test")
    ws_id = workspace.workspace_id

    # 1. Create task tool
    task_res = create_task_tool({
        "workspace_id": ws_id,
        "title": "MCP Task",
        "description": "Created via MCP",
        "metadata": {"source": "mcp"},
        "status": "READY",
    })
    assert task_res["task_id"]
    assert task_res["title"] == "MCP Task"
    assert task_res["description"] == "Created via MCP"
    assert task_res["status"] == "READY"
    assert task_res["metadata"] == {"source": "mcp"}

    task_id = task_res["task_id"]

    # 2. Create subtask tool
    sub_res = create_subtask_tool({
        "workspace_id": ws_id,
        "parent_task_id": task_id,
        "title": "MCP Subtask",
    })
    assert sub_res["task_id"]
    assert sub_res["parent_task_id"] == task_id
    assert sub_res["title"] == "MCP Subtask"

    sub_id = sub_res["task_id"]

    # 3. Add dependency tool
    dep_res = add_dependency_tool({
        "workspace_id": ws_id,
        "source_task_id": sub_id,
        "target_task_id": task_id,
        "dependency_type": "BLOCKS",
    })
    assert dep_res["source_task_id"] == sub_id
    assert dep_res["target_task_id"] == task_id
    assert dep_res["dependency_type"] == "BLOCKS"

    # 4. Get task tool
    get_res = get_task_tool({
        "workspace_id": ws_id,
        "task_id": task_id,
    })
    assert get_res["task_id"] == task_id
    assert get_res["title"] == "MCP Task"

    # 5. List tasks tool
    list_res = list_tasks_tool({
        "workspace_id": ws_id,
    })
    assert "tasks" in list_res
    assert len(list_res["tasks"]) == 2
    titles = [t["title"] for t in list_res["tasks"]]
    assert "MCP Task" in titles
    assert "MCP Subtask" in titles

    # 6. Invalid workspace ID error
    with pytest.raises(McpError, match="Workspace not found"):
        create_task_tool({
            "workspace_id": "invalid-workspace",
            "title": "Failed Task",
        })
