"""Unit test suite for Capability 6 — Review & Validation Engine."""

import pytest
from uuid import uuid4

from review_models import (
    ReviewCriterion,
    ReviewFinding,
    ReviewReport,
    ReviewResult,
    ReviewSeverity,
    ReviewStatus,
)
from review_engine import ReviewEngine
from workspace import ExecutionRecord, TaskWorkspace, workspace_store
from brain import AntigravityBrain
from ai_orchestrator_mcp import (
    get_review_tool,
    list_reviews_tool,
    review_execution_tool,
    review_plan_tool,
    review_task_tool,
    review_tasks_tool,
)


def test_review_models_creation_and_immutability():
    crit = ReviewCriterion(
        criterion_id="crit-1",
        title="Accuracy",
        description="Verify accuracy of response",
        weight=2.0,
    )
    assert crit.to_dict()["weight"] == 2.0

    finding = ReviewFinding(
        criterion_id="crit-1",
        severity=ReviewSeverity.INFO,
        message="Response passed accuracy check",
        score=1.0,
    )
    assert finding.to_dict()["severity"] == "INFO"

    res = ReviewResult(
        review_id="rev-1",
        execution_id="exec-1",
        status=ReviewStatus.PASSED,
        overall_score=1.0,
        findings=(finding,),
        summary="All tests passed",
    )
    assert res.to_dict()["status"] == "PASSED"

    # Test immutability
    with pytest.raises(AttributeError):
        res.overall_score = 0.5  # type: ignore

    rep = ReviewReport(
        report_id="rep-1",
        review_result=res,
        workspace_id="ws-1",
        task_id="task-1",
        execution_id="exec-1",
        recommendations=["Proceed"],
    )
    assert rep.to_dict()["recommendations"] == ["Proceed"]


def test_successful_review_execution():
    ws = TaskWorkspace(workspace_id="ws-succ-exec", created_at="2026-08-01T00:00:00Z")
    rec = ExecutionRecord(
        execution_id="exec-ok",
        provider="ollama",
        model="llama3.1",
        prompt="Write test code",
        started_at="2026-08-01T00:00:00Z",
        completed_at="2026-08-01T00:00:01Z",
        latency_ms=1000,
        success=True,
        response="print('hello')",
    )
    ws.executions.append(rec)

    report = ws.review_engine.review_execution("exec-ok")

    assert report.review_result.status == ReviewStatus.PASSED
    assert report.review_result.overall_score == 1.0
    assert report.execution_id == "exec-ok"
    assert "Proceed to downstream tasks" in report.recommendations[0]
    assert report.report_id in ws.review_reports


def test_failed_review_execution():
    ws = TaskWorkspace(workspace_id="ws-fail-exec", created_at="2026-08-01T00:00:00Z")
    rec = ExecutionRecord(
        execution_id="exec-err",
        provider="ollama",
        model="llama3.1",
        prompt="Write test code",
        started_at="2026-08-01T00:00:00Z",
        completed_at="2026-08-01T00:00:01Z",
        latency_ms=500,
        success=False,
        error={"code": "RuntimeError", "message": "Out of memory"},
    )
    ws.executions.append(rec)

    report = ws.review_engine.review_execution("exec-err")

    assert report.review_result.status in (ReviewStatus.FAILED, ReviewStatus.ERROR)
    assert report.review_result.overall_score == 0.0
    assert len(report.review_result.findings) >= 1
    assert report.review_result.findings[0].severity == ReviewSeverity.ERROR


def test_multiple_weighted_criteria():
    ws = TaskWorkspace(workspace_id="ws-multi-crit", created_at="2026-08-01T00:00:00Z")
    rec = ExecutionRecord(
        execution_id="exec-weighted",
        provider="groq",
        model="llama-3.1-8b",
        prompt="Generate JSON",
        started_at="2026-08-01T00:00:00Z",
        completed_at="2026-08-01T00:00:01Z",
        latency_ms=200,
        success=True,
        response='{"status": "ok"}',
    )
    ws.executions.append(rec)

    criteria = [
        ReviewCriterion(criterion_id="crit-success", title="Success Flag", weight=1.0),
        ReviewCriterion(criterion_id="crit-nonempty", title="Non empty output", weight=3.0),
    ]

    report = ws.review_engine.review_execution("exec-weighted", criteria=criteria)
    assert report.review_result.overall_score == 1.0
    assert len(report.review_result.findings) == 2


def test_injected_reviewer_callable():
    ws = TaskWorkspace(workspace_id="ws-injected", created_at="2026-08-01T00:00:00Z")
    rec = ExecutionRecord(
        execution_id="exec-custom",
        provider="gemini",
        model="gemini-1.5-flash",
        prompt="Analyze text",
        started_at="2026-08-01T00:00:00Z",
        completed_at="2026-08-01T00:00:01Z",
        latency_ms=300,
        success=True,
        response="Analysis completed",
    )
    ws.executions.append(rec)

    def custom_reviewer(data: dict) -> ReviewResult:
        assert data["execution_id"] == "exec-custom"
        return ReviewResult(
            review_id="rev-custom-123",
            execution_id="exec-custom",
            status=ReviewStatus.PASSED,
            overall_score=0.95,
            findings=(
                ReviewFinding(
                    criterion_id="custom-crit",
                    severity=ReviewSeverity.INFO,
                    message="Custom reviewer score high",
                    score=0.95,
                ),
            ),
            summary="Custom reviewer verified output",
        )

    report = ws.review_engine.review_execution("exec-custom", reviewer=custom_reviewer)

    assert report.review_result.review_id == "rev-custom-123"
    assert report.review_result.overall_score == 0.95
    assert report.review_result.summary == "Custom reviewer verified output"


def test_review_history_and_workspace_integration():
    ws = workspace_store.create_workspace(title="Workspace Review History Test")
    ws_id = ws.workspace_id

    # Create task & execution
    task = ws.task_graph.create_task("Task 1")
    rec = ExecutionRecord(
        execution_id="exec-hist-1",
        provider="gemini",
        model="gemini-1.5-flash",
        prompt="Execute task 1",
        started_at="2026-08-01T00:00:00Z",
        completed_at="2026-08-01T00:00:01Z",
        latency_ms=100,
        success=True,
        response="Task 1 output",
    )
    ws.executions.append(rec)
    ws.task_execution_index.bind_execution(task.task_id, rec.execution_id, "PRIMARY")

    report1 = ws.review_engine.review_task(task.task_id)
    report2 = ws.review_engine.review_execution(rec.execution_id)

    reviews = ws.review_engine.list_reviews()
    assert len(reviews) == 2

    fetched = ws.review_engine.get_review(report1.report_id)
    assert fetched.report_id == report1.report_id

    from workspace import workspace_to_dict
    ws_dict = workspace_to_dict(ws)
    assert "review_reports" in ws_dict
    assert len(ws_dict["review_reports"]) == 2


def test_brain_review_integration():
    ws = workspace_store.create_workspace(title="Brain Review Test")
    ws_id = ws.workspace_id

    # Setup plan & task graph via planner
    brain = AntigravityBrain(execute_model=lambda args: {"ok": True, "text": "Model output"})
    plan_res = brain.create_plan({
        "workspace_id": ws_id,
        "objective": "Build Review Engine",
        "levels": [
            {
                "title": "Phase 1",
                "tasks": [{"title": "Implement Review Models"}],
            }
        ],
    })

    plan_id = plan_res["plan_id"]

    # Execute all ready tasks in plan
    while True:
        ready = brain.get_ready_tasks(ws_id)["ready_tasks"]
        if not ready:
            break
        for t in ready:
            brain.execute_task({
                "workspace_id": ws_id,
                "task_id": t["task_id"],
                "provider": "ollama",
            })

    exec_task_id = list(ws.task_execution_index.list_bindings())[0].task_id

    # Review task via brain
    task_rev = brain.review_task({
        "workspace_id": ws_id,
        "task_id": exec_task_id,
    })
    assert task_rev["review_result"]["status"] == "PASSED"

    # Review plan via brain
    plan_rev = brain.review_plan({
        "workspace_id": ws_id,
        "plan_id": plan_id,
    })
    assert plan_rev["plan_id"] == plan_id
    assert plan_rev["review_result"]["status"] == "PASSED"

    # List & Get review via brain
    reviews_list = brain.list_reviews(ws_id)
    assert len(reviews_list["reviews"]) >= 2

    report_id = task_rev["report_id"]
    single_rev = brain.get_review(ws_id, report_id)
    assert single_rev["report_id"] == report_id


def test_mcp_review_tools():
    ws = workspace_store.create_workspace(title="MCP Review Test")
    ws_id = ws.workspace_id

    brain = AntigravityBrain(execute_model=lambda args: {"ok": True, "text": "Result"})
    plan_res = brain.create_plan({
        "workspace_id": ws_id,
        "objective": "Validate MCP",
    })

    while True:
        ready = brain.get_ready_tasks(ws_id)["ready_tasks"]
        if not ready:
            break
        for t in ready:
            brain.execute_task({
                "workspace_id": ws_id,
                "task_id": t["task_id"],
                "provider": "ollama",
            })

    task_id = list(ws.task_execution_index.list_bindings())[0].task_id

    # Call MCP tools
    rev_task_res = review_task_tool({"workspace_id": ws_id, "task_id": task_id})
    assert rev_task_res["review_result"]["status"] == "PASSED"

    rev_plan_res = review_plan_tool({"workspace_id": ws_id})
    assert rev_plan_res["review_result"]["status"] == "PASSED"

    list_res = list_reviews_tool({"workspace_id": ws_id})
    assert len(list_res["reviews"]) >= 2

    rep_id = rev_task_res["report_id"]
    get_res = get_review_tool({"workspace_id": ws_id, "report_id": rep_id})
    assert get_res["report_id"] == rep_id
