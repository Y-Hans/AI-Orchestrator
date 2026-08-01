"""Unit tests for Capability 8 — Result Synthesis Engine."""

from __future__ import annotations

import pytest
from uuid import uuid4

from synthesis_models import (
    SynthesisReport,
    SynthesisResult,
    SynthesisSource,
    SynthesisSourceType,
    SynthesisStatus,
)
from synthesis_engine import DeterministicSynthesizer, SynthesisEngine, Synthesizer
from workspace import ExecutionRecord, workspace_store, workspace_to_dict
from brain import AntigravityBrain
from ai_orchestrator_mcp import (
    handle_request,
    synthesize_tool,
    synthesize_task_tool,
    synthesize_plan_tool,
    get_synthesis_tool,
    list_syntheses_tool,
    delete_synthesis_tool,
)


def test_synthesis_models_serialization():
    source = SynthesisSource(
        source_type=SynthesisSourceType.EXECUTION,
        source_id="exec-123",
        title="Execution Output 1",
        metadata={"provider": "gemini"},
    )
    s_dict = source.to_dict()
    assert s_dict["source_type"] == "EXECUTION"
    assert s_dict["source_id"] == "exec-123"
    assert s_dict["title"] == "Execution Output 1"

    res = SynthesisResult(
        synthesis_id="synth-1",
        title="Summary Report",
        summary="All tasks complete",
        content={"data": "test"},
        metadata={"algo": "deterministic"},
    )
    r_dict = res.to_dict()
    assert r_dict["synthesis_id"] == "synth-1"

    # Verify immutability of SynthesisResult
    with pytest.raises(AttributeError):
        res.title = "Modified"  # type: ignore

    report = SynthesisReport(
        report_id="rep-1",
        workspace_id="ws-1",
        status=SynthesisStatus.COMPLETED,
        result=res,
        sources=[source],
    )
    rep_dict = report.to_dict()
    assert rep_dict["report_id"] == "rep-1"
    assert rep_dict["status"] == "COMPLETED"
    assert len(rep_dict["sources"]) == 1


def test_deterministic_synthesizer():
    synthesizer = DeterministicSynthesizer()
    s1 = SynthesisSource(source_type=SynthesisSourceType.EXECUTION, source_id="e1", title="Exec 1")
    s2 = SynthesisSource(source_type=SynthesisSourceType.REVIEW, source_id="r1", title="Rev 1")
    inputs = {
        "e1": {"response": "Hello world"},
        "r1": {"status": "PASSED", "score": 1.0},
    }

    result = synthesizer.synthesize("Test Title", [s1, s2], inputs)
    assert isinstance(result, SynthesisResult)
    assert result.title == "Test Title"
    assert "2 source(s)" in result.summary
    assert len(result.content["items"]) == 2
    assert result.content["items"][0]["source_id"] == "e1"
    assert result.content["items"][1]["source_id"] == "r1"
    assert result.metadata["source_counts"]["EXECUTION"] == 1
    assert result.metadata["source_counts"]["REVIEW"] == 1


def test_workspace_synthesis_integration():
    ws = workspace_store.create_workspace("Test Synthesis Workspace")
    assert hasattr(ws, "synthesis_engine")
    assert hasattr(ws, "syntheses")
    assert ws.syntheses == {}

    # Add execution record
    exec_rec = ExecutionRecord(
        execution_id="e1",
        provider="gemini",
        model="gemini-1.5-flash",
        prompt="Test prompt",
        started_at="2026-08-01T00:00:00Z",
        completed_at="2026-08-01T00:00:01Z",
        latency_ms=100,
        success=True,
        response="Model response text",
    )
    ws.executions.append(exec_rec)

    # Perform synthesis
    report = ws.synthesis_engine.synthesize(
        title="Workspace Synthesis",
        execution_ids=["e1"],
    )

    assert report.status == SynthesisStatus.COMPLETED
    assert report.report_id in ws.syntheses
    assert ws.syntheses[report.report_id] == report

    # Test workspace_to_dict
    ws_dict = workspace_to_dict(ws)
    assert "syntheses" in ws_dict
    assert len(ws_dict["syntheses"]) == 1
    assert ws_dict["syntheses"][0]["report_id"] == report.report_id


def test_synthesis_engine_task_and_plan():
    ws = workspace_store.create_workspace("Task & Plan Synthesis WS")
    node = ws.task_graph.create_task(title="Build Feature", description="Implement feature X")
    task_id = node.task_id

    # Bind execution
    exec_rec = ExecutionRecord(
        execution_id="e-task-1",
        provider="groq",
        model="llama-3.1-8b-instant",
        prompt="Write code",
        started_at="2026-08-01T00:00:00Z",
        completed_at="2026-08-01T00:00:01Z",
        latency_ms=200,
        success=True,
        response="code written",
    )
    ws.executions.append(exec_rec)
    ws.task_execution_index.bind_execution(task_id=task_id, execution_id="e-task-1", execution_type="PRIMARY")

    # Review task
    rev_report = ws.review_engine.review_task(task_id=task_id)

    # Create artifact
    from artifact_store import Artifact, ArtifactType
    ws.artifact_store.create_artifact(Artifact(
        artifact_id="art-1",
        task_id=task_id,
        execution_id=None,
        workspace_id=ws.workspace_id,
        name="output.txt",
        artifact_type=ArtifactType.TEXT,
        mime_type="text/plain",
        content="File contents",
        metadata={},
        created_at="2026-08-01T00:00:00Z",
    ))

    # Store memory
    ws.memory_engine.store_memory(
        title="Feature note",
        content="Note content",
        workspace_id=ws.workspace_id,
        tags=[task_id],
    )

    # Synthesize task
    task_synth = ws.synthesis_engine.synthesize_task(
        task_id=task_id,
        include_memories=True,
    )

    assert task_synth.status == SynthesisStatus.COMPLETED
    assert len(task_synth.sources) >= 3  # execution, review, artifact, memory
    source_types = {s.source_type for s in task_synth.sources}
    assert SynthesisSourceType.EXECUTION in source_types
    assert SynthesisSourceType.REVIEW in source_types
    assert SynthesisSourceType.ARTIFACT in source_types
    assert SynthesisSourceType.MEMORY in source_types

    # Synthesize plan
    plan_synth = ws.synthesis_engine.synthesize_plan()
    assert plan_synth.status == SynthesisStatus.COMPLETED

    # Query & Delete syntheses
    s_list = ws.synthesis_engine.list_syntheses()
    assert len(s_list) == 2

    fetched = ws.synthesis_engine.get_synthesis(task_synth.report_id)
    assert fetched.report_id == task_synth.report_id

    del_report = ws.synthesis_engine.delete_synthesis(task_synth.report_id)
    assert del_report.report_id == task_synth.report_id
    assert len(ws.synthesis_engine.list_syntheses()) == 1

    with pytest.raises(KeyError):
        ws.synthesis_engine.get_synthesis(task_synth.report_id)


def test_brain_synthesis_facade():
    brain = AntigravityBrain(execute_model=lambda args: {"ok": True, "text": "mock"})
    ws = workspace_store.create_workspace("Brain Synthesis WS")

    # Call brain.synthesize
    res = brain.synthesize({
        "workspace_id": ws.workspace_id,
        "title": "Brain Test Synthesis",
    })
    assert res["status"] == "COMPLETED"
    report_id = res["report_id"]

    # Call brain.get_synthesis
    get_res = brain.get_synthesis(workspace_id=ws.workspace_id, report_id=report_id)
    assert get_res["report_id"] == report_id

    # Call brain.list_syntheses
    list_res = brain.list_syntheses(ws.workspace_id)
    assert len(list_res["syntheses"]) == 1

    # Call brain.delete_synthesis
    del_res = brain.delete_synthesis(workspace_id=ws.workspace_id, report_id=report_id)
    assert del_res["report_id"] == report_id

    # Ensure list is now empty
    assert len(brain.list_syntheses(ws.workspace_id)["syntheses"]) == 0


def test_mcp_synthesis_tools():
    ws = workspace_store.create_workspace("MCP Synthesis WS")

    # MCP synthesize
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "synthesize",
            "arguments": {
                "workspace_id": ws.workspace_id,
                "title": "MCP Synthesis Title",
            },
        },
    }
    resp = handle_request(req)
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "COMPLETED" in content
    assert "MCP Synthesis Title" in content

    # List syntheses tool
    list_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "list_syntheses",
            "arguments": {"workspace_id": ws.workspace_id},
        },
    }
    list_resp = handle_request(list_req)
    assert "result" in list_resp
    assert "syntheses" in list_resp["result"]["content"][0]["text"]
