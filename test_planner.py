"""Unit test suite for Capability 5 — Intelligent Task Planner."""

import pytest
from planner_models import (
    LevelType,
    Objective,
    Plan,
    PlanningLevelSpec,
    PlanningResult,
    PlanStatus,
    TaskSpecification,
)
from task_graph import DependencyType, TaskGraph, TaskStatus
from workspace import TaskWorkspace
from planner import (
    DeterministicPlanningEngine,
    PlanGraphBuilder,
    PlanValidator,
    PlanVisualizer,
    TaskPlanner,
)


def test_objective_and_plan_models():
    obj = Objective(
        objective_id="obj-1",
        workspace_id="ws-1",
        title="Test Objective",
        description="Description",
        constraints=["c1", "c2"],
        success_criteria=["s1"],
    )
    d = obj.to_dict()
    assert d["objective_id"] == "obj-1"
    assert d["constraints"] == ["c1", "c2"]

    plan = Plan(
        plan_id="plan-1",
        workspace_id="ws-1",
        objective_id="obj-1",
        root_task_id="root-1",
        status=PlanStatus.DRAFT,
    )
    pd = plan.to_dict()
    assert pd["plan_id"] == "plan-1"
    assert pd["status"] == "DRAFT"


def test_plan_graph_builder():
    graph = TaskGraph(workspace_id="ws-1")
    builder = PlanGraphBuilder(graph)

    obj = Objective(objective_id="obj-1", workspace_id="ws-1", title="Root Objective")
    root = builder.build_root_task(obj)
    assert root.title == "Root Objective"
    assert root.metadata["plan_role"] == "ROOT_OBJECTIVE"
    assert root.metadata["is_executable"] is False

    level = builder.build_level_node(root.task_id, "Phase 1", level_name="Phase")
    assert level.parent_task_id == root.task_id
    assert level.metadata["level_name"] == "Phase"

    leaf = builder.build_leaf_task(level.task_id, "Task 1")
    assert leaf.parent_task_id == level.task_id
    assert leaf.metadata["is_executable"] is True

    edge = builder.connect_dependency(leaf.task_id, root.task_id)
    assert edge.source_task_id == leaf.task_id


def test_plan_validator_success_and_failures():
    graph = TaskGraph(workspace_id="ws-1")
    builder = PlanGraphBuilder(graph)

    obj = Objective(objective_id="obj-1", workspace_id="ws-1", title="Valid Plan Objective")
    root = builder.build_root_task(obj)
    level = builder.build_level_node(root.task_id, "Phase 1")
    leaf1 = builder.build_leaf_task(level.task_id, "Leaf Task 1")
    leaf2 = builder.build_leaf_task(level.task_id, "Leaf Task 2")

    builder.connect_dependency(leaf2.task_id, leaf1.task_id)

    plan = Plan(
        plan_id="plan-1",
        workspace_id="ws-1",
        objective_id="obj-1",
        root_task_id=root.task_id,
        status=PlanStatus.DRAFT,
    )

    res = PlanValidator.validate(plan, obj, graph)
    assert res["is_valid"] is True
    assert res["checks"]["cycles_check"] == "PASSED"
    assert res["checks"]["orphans_check"] == "PASSED"

    # Introduce cycle
    builder.connect_dependency(leaf1.task_id, leaf2.task_id)
    res_cycle = PlanValidator.validate(plan, obj, graph)
    assert res_cycle["is_valid"] is False
    assert res_cycle["checks"]["cycles_check"] == "FAILED"


def test_task_planner_full_workflow():
    ws = TaskWorkspace(workspace_id="ws-planner-test", created_at="2026-08-01T00:00:00Z")
    planner = TaskPlanner(ws)

    # 1. Create Objective & Plan
    result = planner.create_plan(
        objective_input={
            "title": "Build Capability 5 Intelligent Task Planner",
            "description": "Decompose high-level request",
            "constraints": ["No execution in planner"],
            "success_criteria": ["All tests pass"],
        },
        levels_spec=[
            {
                "title": "Phase 1: Foundation",
                "level_name": "Phase",
                "priority": 90,
                "tasks": [
                    {"title": "Implement models", "priority": 90},
                    {"title": "Implement builder", "priority": 85, "dependencies": ["Implement models"]},
                ],
            },
            {
                "title": "Phase 2: Integration",
                "level_name": "Phase",
                "priority": 70,
                "tasks": [
                    {"title": "Wire workspace", "priority": 70},
                ],
            },
        ],
    )

    assert isinstance(result, PlanningResult)
    assert result.status == PlanStatus.VALIDATED
    assert result.summary["total_tasks"] == 6  # Root + 2 Phases + 3 Tasks
    assert result.statistics["is_valid"] is True

    # 2. Check workspace registries
    assert len(ws.objectives) == 1
    assert len(ws.plans) == 1

    # 3. Expand task
    leaf_node = [n for n in ws.task_graph.nodes.values() if n.title == "Wire workspace"][0]
    expanded_res = planner.expand_task(
        task_id=leaf_node.task_id,
        subtasks_spec=[
            {"title": "Add objectives field to TaskWorkspace"},
            {"title": "Add plans field to TaskWorkspace"},
        ],
    )
    assert expanded_res.statistics["is_valid"] is True
    assert leaf_node.metadata["is_executable"] is False  # Turned into parent container

    # 4. Visualize Plan
    txt = planner.visualize_plan(format="text")
    assert "Build Capability 5" in txt
    assert "Phase 1: Foundation" in txt

    mermaid = planner.visualize_plan(format="mermaid")
    assert "graph TD" in mermaid

    json_view = planner.visualize_plan(format="json")
    assert "tree" in json_view


def test_regenerate_plan_conservatism():
    ws = TaskWorkspace(workspace_id="ws-regen-test", created_at="2026-08-01T00:00:00Z")
    planner = TaskPlanner(ws)

    res = planner.create_plan(objective_input="Regen Objective")
    plan_id = res.plan_id

    # Mark one leaf task COMPLETED
    leaf_nodes = [n for n in ws.task_graph.nodes.values() if n.metadata.get("is_executable")]
    completed_task = leaf_nodes[0]
    completed_task.complete_execution("Done")

    # Regenerate plan
    regen_res = planner.regenerate_plan(
        plan_id=plan_id,
        levels_spec=[
            {
                "title": "Phase New",
                "tasks": [{"title": "New Task"}],
            }
        ],
    )

    # Verify COMPLETED task still exists!
    assert completed_task.task_id in ws.task_graph.nodes
    assert ws.task_graph.nodes[completed_task.task_id].status == TaskStatus.COMPLETED
    assert regen_res.plan["version"] == 2
