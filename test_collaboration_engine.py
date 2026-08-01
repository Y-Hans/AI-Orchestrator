"""Unit tests for Capability 9 — Multi-Agent Collaboration Framework."""

from __future__ import annotations

import pytest
from uuid import uuid4

from agent_models import (
    Agent,
    AgentAssignment,
    AgentMessage,
    AgentRole,
    AgentStatus,
    AssignmentStatus,
    CollaborationSession,
    CollaborationStatus,
    CollaborationSummary,
    MessageType,
    utc_now,
)
from agent_registry import AgentRegistry
from collaboration_store import CollaborationStore
from collaboration_engine import CollaborationEngine, InMemoryMessagingBackend, MessagingBackend
from workspace import TaskWorkspace, workspace_store, workspace_to_dict
from brain import AntigravityBrain
from ai_orchestrator_mcp import handle_request, TOOL_SCHEMAS


# ---------------------------------------------------------------------------
# 1. Model Serialization & Immutability Tests
# ---------------------------------------------------------------------------

def test_agent_model_serialization() -> None:
    agent = Agent(
        agent_id="agent-101",
        name="PlannerAgent",
        role=AgentRole.PLANNER,
        description="Decomposes objectives into tasks",
        capabilities=["planning", "decomposition"],
        status=AgentStatus.IDLE,
    )
    d = agent.to_dict()
    assert d["agent_id"] == "agent-101"
    assert d["name"] == "PlannerAgent"
    assert d["role"] == "PLANNER"
    assert d["status"] == "IDLE"
    assert "planning" in d["capabilities"]


def test_agent_assignment_serialization() -> None:
    assignment = AgentAssignment(
        assignment_id="assign-1",
        session_id="session-1",
        agent_id="agent-101",
        workspace_id="ws-1",
        task_id="task-A",
        status=AssignmentStatus.PENDING,
    )
    d = assignment.to_dict()
    assert d["assignment_id"] == "assign-1"
    assert d["session_id"] == "session-1"
    assert d["agent_id"] == "agent-101"
    assert d["workspace_id"] == "ws-1"
    assert d["task_id"] == "task-A"
    assert d["status"] == "PENDING"


def test_agent_message_immutability() -> None:
    msg = AgentMessage(
        message_id="msg-1",
        session_id="session-1",
        sender_agent_id="agent-101",
        receiver_agent_id="agent-102",
        message_type=MessageType.REQUEST,
        content={"action": "review_code"},
    )
    d = msg.to_dict()
    assert d["message_id"] == "msg-1"
    assert d["sender_agent_id"] == "agent-101"
    assert d["receiver_agent_id"] == "agent-102"
    assert d["message_type"] == "REQUEST"
    assert d["content"] == {"action": "review_code"}

    # Immutability check (frozen dataclass)
    with pytest.raises(AttributeError):
        msg.content = "modified"  # type: ignore[misc]


def test_collaboration_session_lightweight() -> None:
    session = CollaborationSession(
        session_id="sess-1",
        workspace_id="ws-1",
        objective="Refactor Auth Module",
        participant_ids=["agent-1", "agent-2"],
        status=CollaborationStatus.ACTIVE,
    )
    d = session.to_dict()
    assert d["session_id"] == "sess-1"
    assert d["workspace_id"] == "ws-1"
    assert d["participant_ids"] == ["agent-1", "agent-2"]
    assert d["status"] == "ACTIVE"
    # Ensure assignments and messages are NOT embedded inside the session object
    assert "messages" not in d
    assert "assignments" not in d


def test_collaboration_summary_model() -> None:
    summary = CollaborationSummary(
        session_id="sess-1",
        workspace_id="ws-1",
        objective="Test Objective",
        participant_count=2,
        assignment_count=3,
        active_assignment_count=1,
        message_count=5,
        status=CollaborationStatus.ACTIVE,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    d = summary.to_dict()
    assert d["session_id"] == "sess-1"
    assert d["participant_count"] == 2
    assert d["active_assignment_count"] == 1
    assert d["message_count"] == 5
    assert d["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# 2. AgentRegistry CRUD & Filtering Tests
# ---------------------------------------------------------------------------

def test_agent_registry_crud() -> None:
    registry = AgentRegistry()

    # Register
    agent1 = registry.register_agent(
        name="CoderAgent",
        role="CODER",
        capabilities=["python", "pytest"],
    )
    assert agent1.name == "CoderAgent"
    assert agent1.role == AgentRole.CODER
    assert agent1.status == AgentStatus.IDLE

    # Get
    retrieved = registry.get_agent(agent1.agent_id)
    assert retrieved.agent_id == agent1.agent_id

    # Update status
    updated = registry.update_status(agent1.agent_id, "BUSY")
    assert updated.status == AgentStatus.BUSY

    # List
    agents = registry.list_agents()
    assert len(agents) == 1

    # Unregister
    removed = registry.unregister_agent(agent1.agent_id)
    assert removed.agent_id == agent1.agent_id
    assert len(registry.list_agents()) == 0

    with pytest.raises(KeyError):
        registry.get_agent(agent1.agent_id)


def test_agent_registry_filters() -> None:
    registry = AgentRegistry()
    a1 = registry.register_agent(name="Planner", role=AgentRole.PLANNER, capabilities=["planning"])
    a2 = registry.register_agent(name="Reviewer", role=AgentRole.REVIEWER, capabilities=["quality", "planning"])
    a3 = registry.register_agent(name="Coder", role=AgentRole.CODER, capabilities=["python"])

    planners = registry.filter_by_role("PLANNER")
    assert len(planners) == 1
    assert planners[0].agent_id == a1.agent_id

    planners_cap = registry.filter_by_capability("planning")
    assert len(planners_cap) == 2
    assert {a.agent_id for a in planners_cap} == {a1.agent_id, a2.agent_id}


# ---------------------------------------------------------------------------
# 3. CollaborationStore Tests
# ---------------------------------------------------------------------------

def test_collaboration_store_sessions_assignments_messages() -> None:
    store = CollaborationStore()
    sess = CollaborationSession(
        session_id="s1",
        workspace_id="ws1",
        objective="Build UI",
    )
    store.add_session(sess)
    assert store.get_session("s1").session_id == "s1"

    assign = AgentAssignment(
        assignment_id="a1",
        session_id="s1",
        agent_id="ag1",
        workspace_id="ws1",
    )
    store.add_assignment(assign)
    assert store.get_assignment("a1").agent_id == "ag1"

    # Status update
    updated_a = store.update_assignment_status("a1", AssignmentStatus.IN_PROGRESS)
    assert updated_a.status == AssignmentStatus.IN_PROGRESS

    msg = AgentMessage(
        message_id="m1",
        session_id="s1",
        sender_agent_id="ag1",
        message_type=MessageType.INFO,
        content="Working on UI component",
    )
    store.add_message(msg)

    messages = store.list_messages(session_id="s1")
    assert len(messages) == 1
    assert messages[0].content == "Working on UI component"


# ---------------------------------------------------------------------------
# 4. CollaborationEngine Operations & Backend Injection
# ---------------------------------------------------------------------------

def test_collaboration_engine_workflow() -> None:
    ws = workspace_store.create_workspace(title="Multi-Agent Workspace")
    reg = ws.agent_registry
    engine = ws.collaboration_engine

    # Register agents
    coder = reg.register_agent(name="Coder", role=AgentRole.CODER)
    reviewer = reg.register_agent(name="Reviewer", role=AgentRole.REVIEWER)

    # Create session
    session = engine.create_session(
        objective="Develop feature X",
        participant_ids=[coder.agent_id, reviewer.agent_id],
    )
    assert session.status == CollaborationStatus.ACTIVE
    assert set(session.participant_ids) == {coder.agent_id, reviewer.agent_id}

    # Assign agent to session/task
    assignment = engine.assign_agent(
        session_id=session.session_id,
        agent_id=coder.agent_id,
        task_id="task-1",
    )
    assert assignment.status == AssignmentStatus.PENDING
    assert reg.get_agent(coder.agent_id).status == AgentStatus.BUSY

    # Inter-agent message
    msg = engine.send_message(
        session_id=session.session_id,
        sender_agent_id=coder.agent_id,
        receiver_agent_id=reviewer.agent_id,
        content="PR submitted for task-1",
        message_type=MessageType.REQUEST,
    )
    assert msg.sender_agent_id == coder.agent_id
    assert msg.receiver_agent_id == reviewer.agent_id

    # Receive messages
    msgs = engine.receive_messages(session_id=session.session_id, receiver_agent_id=reviewer.agent_id)
    assert len(msgs) == 1
    assert msgs[0].content == "PR submitted for task-1"

    # Get summary
    summary = engine.get_session_summary(session.session_id)
    assert summary.participant_count == 2
    assert summary.assignment_count == 1
    assert summary.message_count == 1
    assert summary.active_assignment_count == 1

    # Close session
    closed = engine.close_session(session.session_id)
    assert closed.status == CollaborationStatus.COMPLETED
    assert reg.get_agent(coder.agent_id).status == AgentStatus.IDLE


class MockCustomMessagingBackend(MessagingBackend):
    def __init__(self) -> None:
        self.dispatched: list[AgentMessage] = []

    def dispatch_message(self, message: AgentMessage, store: CollaborationStore) -> None:
        self.dispatched.append(message)
        store.add_message(message)


def test_messaging_backend_injection() -> None:
    ws = workspace_store.create_workspace(title="Custom Messaging Workspace")
    mock_backend = MockCustomMessagingBackend()
    store = CollaborationStore()
    reg = AgentRegistry()
    engine = CollaborationEngine(workspace=ws, registry=reg, store=store, messaging_backend=mock_backend)

    ag = reg.register_agent(name="AgentA", role=AgentRole.GENERAL)
    sess = engine.create_session(objective="Custom Messaging", participant_ids=[ag.agent_id])

    msg = engine.send_message(session_id=sess.session_id, sender_agent_id=ag.agent_id, content="Ping")
    assert len(mock_backend.dispatched) == 1
    assert mock_backend.dispatched[0].message_id == msg.message_id


# ---------------------------------------------------------------------------
# 5. Workspace Serialization Integration
# ---------------------------------------------------------------------------

def test_workspace_to_dict_includes_agents_and_sessions() -> None:
    ws = workspace_store.create_workspace(title="Serialization Test WS")
    ag = ws.agent_registry.register_agent(name="Worker", role=AgentRole.EXECUTOR)
    sess = ws.collaboration_engine.create_session(objective="Serialize Me", participant_ids=[ag.agent_id])

    data = workspace_to_dict(ws)
    assert "agents" in data
    assert "sessions" in data
    assert len(data["agents"]) == 1
    assert len(data["sessions"]) == 1
    assert data["agents"][0]["agent_id"] == ag.agent_id
    assert data["sessions"][0]["session_id"] == sess.session_id


# ---------------------------------------------------------------------------
# 6. AntigravityBrain Façade Methods
# ---------------------------------------------------------------------------

def test_brain_collaboration_facade() -> None:
    ws = workspace_store.create_workspace(title="Brain Façade WS")
    brain = AntigravityBrain(execute_model=lambda args: {"ok": True})

    # Register Agent
    reg_res = brain.register_agent({
        "workspace_id": ws.workspace_id,
        "name": "SynthesizerBot",
        "role": "SYNTHESIZER",
    })
    ag_id = reg_res["agent_id"]
    assert reg_res["name"] == "SynthesizerBot"

    # Get Agent
    get_res = brain.get_agent(workspace_id=ws.workspace_id, agent_id=ag_id)
    assert get_res["agent_id"] == ag_id

    # List Agents
    list_res = brain.list_agents(workspace_id=ws.workspace_id)
    assert len(list_res["agents"]) == 1

    # Create Collaboration Session
    collab_res = brain.create_collaboration({
        "workspace_id": ws.workspace_id,
        "objective": "Synthesize Reports",
        "participant_ids": [ag_id],
    })
    sess_id = collab_res["session_id"]
    assert collab_res["objective"] == "Synthesize Reports"

    # Assign Agent
    assign_res = brain.assign_agent({
        "workspace_id": ws.workspace_id,
        "session_id": sess_id,
        "agent_id": ag_id,
    })
    assert assign_res["session_id"] == sess_id

    # Send Message
    msg_res = brain.send_agent_message({
        "workspace_id": ws.workspace_id,
        "session_id": sess_id,
        "sender_agent_id": ag_id,
        "content": "Report synthesized",
    })
    assert msg_res["content"] == "Report synthesized"

    # List Messages
    msgs_res = brain.list_messages(workspace_id=ws.workspace_id, session_id=sess_id)
    assert len(msgs_res["messages"]) == 1

    # List Sessions
    sessions_res = brain.list_sessions(workspace_id=ws.workspace_id)
    assert len(sessions_res["sessions"]) == 1

    # Close Collaboration
    close_res = brain.close_collaboration({
        "workspace_id": ws.workspace_id,
        "session_id": sess_id,
    })
    assert close_res["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# 7. MCP Tools Registration & JSON-RPC Calls
# ---------------------------------------------------------------------------

def test_mcp_capability_9_tools_registered() -> None:
    tool_names = [t["name"] for t in TOOL_SCHEMAS]
    expected_tools = [
        "register_agent",
        "unregister_agent",
        "get_agent",
        "list_agents",
        "create_collaboration",
        "close_collaboration",
        "assign_agent",
        "send_agent_message",
        "list_messages",
        "list_assignments",
        "list_sessions",
    ]
    for tool in expected_tools:
        assert tool in tool_names, f"Tool {tool} not found in TOOL_SCHEMAS"


def test_mcp_json_rpc_collaboration_flow() -> None:
    # Create workspace via MCP call
    res = handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_workspace",
            "arguments": {"title": "MCP Collaboration Test Workspace"},
        },
    })
    assert "result" in res
    import json
    content = json.loads(res["result"]["content"][0]["text"])
    ws_id = content["workspace_id"]

    # 1. register_agent
    res = handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "register_agent",
            "arguments": {"workspace_id": ws_id, "name": "AgentAlpha", "role": "CODER"},
        },
    })
    agent_data = json.loads(res["result"]["content"][0]["text"])
    agent_id = agent_data["agent_id"]
    assert agent_data["name"] == "AgentAlpha"

    # 2. create_collaboration
    res = handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "create_collaboration",
            "arguments": {"workspace_id": ws_id, "objective": "MCP Mission", "participant_ids": [agent_id]},
        },
    })
    session_data = json.loads(res["result"]["content"][0]["text"])
    session_id = session_data["session_id"]
    assert session_data["objective"] == "MCP Mission"

    # 3. assign_agent
    res = handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "assign_agent",
            "arguments": {"workspace_id": ws_id, "session_id": session_id, "agent_id": agent_id},
        },
    })
    assign_data = json.loads(res["result"]["content"][0]["text"])
    assert assign_data["agent_id"] == agent_id

    # 4. send_agent_message
    res = handle_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "send_agent_message",
            "arguments": {
                "workspace_id": ws_id,
                "session_id": session_id,
                "sender_agent_id": agent_id,
                "content": "Status Update OK",
            },
        },
    })
    msg_data = json.loads(res["result"]["content"][0]["text"])
    assert msg_data["content"] == "Status Update OK"

    # 5. list_messages
    res = handle_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "list_messages",
            "arguments": {"workspace_id": ws_id, "session_id": session_id},
        },
    })
    msgs_data = json.loads(res["result"]["content"][0]["text"])
    assert len(msgs_data["messages"]) == 1

    # 6. close_collaboration
    res = handle_request({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "close_collaboration",
            "arguments": {"workspace_id": ws_id, "session_id": session_id},
        },
    })
    closed_data = json.loads(res["result"]["content"][0]["text"])
    assert closed_data["status"] == "COMPLETED"
