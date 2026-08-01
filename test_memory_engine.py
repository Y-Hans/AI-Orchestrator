"""Comprehensive unit tests for Capability 7 — Long-Term Memory Engine."""

from __future__ import annotations

import pytest
from memory_models import (
    MemoryQuery,
    MemoryRecord,
    MemoryResult,
    MemoryStatus,
    MemorySummary,
    MemoryType,
    utc_now,
)
from memory_store import MemoryStore
from memory_engine import MemoryEngine
from workspace import workspace_store, workspace_to_dict
from brain import AntigravityBrain
from ai_orchestrator_mcp import (
    store_memory_tool,
    retrieve_memory_tool,
    search_memories_tool,
    list_memories_tool,
    delete_memory_tool,
    archive_memory_tool,
    summarize_memories_tool,
    McpError,
)


def test_memory_models_serialization():
    now = utc_now()
    record = MemoryRecord(
        memory_id="mem-1",
        workspace_id="ws-1",
        memory_type=MemoryType.PLAN,
        title="Architecture Plan",
        description="Detailed system design",
        content={"steps": [1, 2, 3]},
        metadata={"author": "Antigravity"},
        tags=["design", "architecture"],
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )

    d = record.to_dict()
    assert d["memory_id"] == "mem-1"
    assert d["workspace_id"] == "ws-1"
    assert d["memory_type"] == "PLAN"
    assert d["title"] == "Architecture Plan"
    assert d["description"] == "Detailed system design"
    assert d["content"] == {"steps": [1, 2, 3]}
    assert d["metadata"] == {"author": "Antigravity"}
    assert d["tags"] == ["design", "architecture"]
    assert d["status"] == "ACTIVE"
    assert d["created_at"] == now

    query = MemoryQuery(
        text="architecture",
        memory_types=[MemoryType.PLAN],
        tags=["design"],
        limit=5,
    )
    qd = query.to_dict()
    assert qd["text"] == "architecture"
    assert qd["memory_types"] == ["PLAN"]
    assert qd["tags"] == ["design"]
    assert qd["limit"] == 5

    res = MemoryResult(query=query, matches=(record,), total_matches=1)
    res_d = res.to_dict()
    assert res_d["total_matches"] == 1
    assert len(res_d["matches"]) == 1
    assert res_d["matches"][0]["memory_id"] == "mem-1"

    # Test immutability of MemoryResult
    with pytest.raises(AttributeError):
        res.total_matches = 2  # type: ignore

    summary = MemorySummary(
        total_memories=1,
        memories_by_type={"PLAN": 1, "NOTE": 0},
        total_tags=2,
        latest_memory=record,
        oldest_memory=record,
    )
    sd = summary.to_dict()
    assert sd["total_memories"] == 1
    assert sd["latest_memory"]["memory_id"] == "mem-1"


def test_memory_store_crud_and_lifecycle():
    store = MemoryStore()
    record = MemoryRecord(
        memory_id="mem-100",
        workspace_id="ws-1",
        memory_type=MemoryType.NOTE,
        title="Meeting Notes",
        content="Discussed Capability 7 implementation.",
        tags=["meeting"],
    )

    store.store_memory(record)
    retrieved = store.get_memory("mem-100")
    assert retrieved.title == "Meeting Notes"

    with pytest.raises(KeyError):
        store.get_memory("non-existent")

    listed = store.list_memories(workspace_id="ws-1")
    assert len(listed) == 1
    assert listed[0].memory_id == "mem-100"

    # Archive record
    archived = store.archive_memory("mem-100")
    assert archived.status == MemoryStatus.ARCHIVED
    assert store.get_memory("mem-100").status == MemoryStatus.ARCHIVED

    # Soft delete record
    deleted = store.delete_memory("mem-100")
    assert deleted.status == MemoryStatus.DELETED
    assert len(store.list_memories(workspace_id="ws-1")) == 0  # Default excludes deleted
    assert len(store.list_memories(workspace_id="ws-1", status=MemoryStatus.DELETED)) == 1


def test_memory_store_search():
    store = MemoryStore()
    r1 = MemoryRecord(
        memory_id="mem-1",
        workspace_id="ws-1",
        memory_type=MemoryType.OBJECTIVE,
        title="Build Orchestrator",
        description="High level goal",
        content="Primary objective statement",
        tags=["core", "v1"],
        created_at="2026-08-01T10:00:00Z",
    )
    r2 = MemoryRecord(
        memory_id="mem-2",
        workspace_id="ws-1",
        memory_type=MemoryType.REVIEW,
        title="Review Code",
        description="Validation report",
        content="All tests passed cleanly",
        tags=["quality", "v1"],
        created_at="2026-08-01T11:00:00Z",
    )
    r3 = MemoryRecord(
        memory_id="mem-3",
        workspace_id="ws-2",
        memory_type=MemoryType.NOTE,
        title="Other Workspace Note",
        content="Unrelated data",
        tags=["other"],
    )

    store.store_memory(r1)
    store.store_memory(r2)
    store.store_memory(r3)

    # Search by text
    res = store.search_memories(MemoryQuery(text="tests"), workspace_id="ws-1")
    assert res.total_matches == 1
    assert res.matches[0].memory_id == "mem-2"

    # Search by type
    res_type = store.search_memories(MemoryQuery(memory_types=[MemoryType.OBJECTIVE]), workspace_id="ws-1")
    assert res_type.total_matches == 1
    assert res_type.matches[0].memory_id == "mem-1"

    # Search by tags
    res_tags = store.search_memories(MemoryQuery(tags=["v1"]), workspace_id="ws-1")
    assert res_tags.total_matches == 2

    # Limit search
    res_limit = store.search_memories(MemoryQuery(tags=["v1"], limit=1), workspace_id="ws-1")
    assert res_limit.total_matches == 2
    assert len(res_limit.matches) == 1


def test_memory_store_summarize():
    store = MemoryStore()
    assert store.summarize(workspace_id="ws-1").total_memories == 0

    r1 = MemoryRecord(
        memory_id="m1",
        workspace_id="ws-1",
        memory_type=MemoryType.PLAN,
        title="Plan 1",
        tags=["t1"],
        created_at="2026-08-01T10:00:00Z",
    )
    r2 = MemoryRecord(
        memory_id="m2",
        workspace_id="ws-1",
        memory_type=MemoryType.EXECUTION,
        title="Execution 1",
        tags=["t1", "t2"],
        created_at="2026-08-01T12:00:00Z",
    )
    store.store_memory(r1)
    store.store_memory(r2)

    summary = store.summarize(workspace_id="ws-1")
    assert summary.total_memories == 2
    assert summary.memories_by_type["PLAN"] == 1
    assert summary.memories_by_type["EXECUTION"] == 1
    assert summary.total_tags == 2
    assert summary.oldest_memory.memory_id == "m1"
    assert summary.latest_memory.memory_id == "m2"


def test_memory_engine_coordination():
    store = MemoryStore()
    engine = MemoryEngine(memory_store=store)

    rec = engine.store_memory(
        title="Stored via Engine",
        content="Engine content",
        memory_type="TEMPLATE",
        workspace_id="ws-engine",
        tags=["engine"],
    )

    assert rec.memory_type == MemoryType.TEMPLATE
    assert rec.workspace_id == "ws-engine"

    retrieved = engine.retrieve_memory(rec.memory_id)
    assert retrieved.title == "Stored via Engine"

    search_res = engine.search_memories(text="Engine", workspace_id="ws-engine")
    assert search_res.total_matches == 1

    summary = engine.summarize(workspace_id="ws-engine")
    assert summary.total_memories == 1

    archived = engine.archive_memory(rec.memory_id)
    assert archived.status == MemoryStatus.ARCHIVED

    deleted = engine.delete_memory(rec.memory_id)
    assert deleted.status == MemoryStatus.DELETED


def test_workspace_memory_integration():
    ws = workspace_store.create_workspace(title="Memory Workspace")
    assert hasattr(ws, "memory_engine")
    assert ws.memory_engine._workspace == ws

    rec = ws.memory_engine.store_memory(
        title="Workspace Knowledge",
        content="Context info",
        memory_type=MemoryType.OBJECTIVE,
    )
    assert rec.workspace_id == ws.workspace_id

    ws_dict = workspace_to_dict(ws)
    assert "memories" in ws_dict
    assert len(ws_dict["memories"]) == 1
    assert ws_dict["memories"][0]["title"] == "Workspace Knowledge"
    assert "memory_summary" in ws_dict
    assert ws_dict["memory_summary"]["total_memories"] == 1


def test_brain_memory_facade():
    brain = AntigravityBrain(execute_model=lambda args: {"ok": True, "text": "mock"})
    ws = workspace_store.create_workspace(title="Brain Memory WS")

    # Store memory
    stored = brain.store_memory({
        "workspace_id": ws.workspace_id,
        "title": "Brain Memory Title",
        "content": "Brain Memory Content",
        "memory_type": "REVIEW",
        "tags": ["brain"],
    })
    mem_id = stored["memory_id"]
    assert stored["title"] == "Brain Memory Title"

    # Retrieve memory
    retrieved = brain.retrieve_memory(workspace_id=ws.workspace_id, memory_id=mem_id)
    assert retrieved["memory_id"] == mem_id

    # List memories
    listed = brain.list_memories(workspace_id=ws.workspace_id)
    assert len(listed["memories"]) == 1

    # Search memories
    search = brain.search_memories({
        "workspace_id": ws.workspace_id,
        "text": "Brain Memory",
    })
    assert search["total_matches"] == 1

    # Summarize memories
    summary = brain.summarize_memories(ws.workspace_id)
    assert summary["total_memories"] == 1

    # Archive memory
    archived = brain.archive_memory(workspace_id=ws.workspace_id, memory_id=mem_id)
    assert archived["status"] == "ARCHIVED"

    # Delete memory
    deleted = brain.delete_memory(workspace_id=ws.workspace_id, memory_id=mem_id)
    assert deleted["status"] == "DELETED"


def test_mcp_memory_tools():
    ws = workspace_store.create_workspace(title="MCP Memory WS")

    # store_memory_tool
    stored = store_memory_tool({
        "workspace_id": ws.workspace_id,
        "title": "MCP Memory",
        "content": "MCP Content",
        "tags": ["mcp"],
    })
    mem_id = stored["memory_id"]
    assert stored["title"] == "MCP Memory"

    # retrieve_memory_tool
    retrieved = retrieve_memory_tool({
        "workspace_id": ws.workspace_id,
        "memory_id": mem_id,
    })
    assert retrieved["memory_id"] == mem_id

    # search_memories_tool
    search_res = search_memories_tool({
        "workspace_id": ws.workspace_id,
        "text": "MCP",
    })
    assert search_res["total_matches"] == 1

    # list_memories_tool
    list_res = list_memories_tool({
        "workspace_id": ws.workspace_id,
    })
    assert len(list_res["memories"]) == 1

    # summarize_memories_tool
    summary_res = summarize_memories_tool({
        "workspace_id": ws.workspace_id,
    })
    assert summary_res["total_memories"] == 1

    # archive_memory_tool
    archive_res = archive_memory_tool({
        "workspace_id": ws.workspace_id,
        "memory_id": mem_id,
    })
    assert archive_res["status"] == "ARCHIVED"

    # delete_memory_tool
    delete_res = delete_memory_tool({
        "workspace_id": ws.workspace_id,
        "memory_id": mem_id,
    })
    assert delete_res["status"] == "DELETED"

    # Error cases
    with pytest.raises(McpError):
        store_memory_tool({"workspace_id": ws.workspace_id})

    with pytest.raises(McpError):
        retrieve_memory_tool({"workspace_id": ws.workspace_id})
