"""Data models for Capability 9 — Multi-Agent Collaboration Framework.

Provides strongly typed dataclasses and enums for agent status, agent roles,
message types, collaboration status, assignment status, agents, assignments,
immutable messages, lightweight collaboration sessions, and collaboration summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


class AgentStatus(str, Enum):
    """Status of an Agent entity."""
    IDLE = "IDLE"
    BUSY = "BUSY"
    WAITING = "WAITING"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class AgentRole(str, Enum):
    """Specialized roles for participating agents."""
    GENERAL = "GENERAL"
    PLANNER = "PLANNER"
    EXECUTOR = "EXECUTOR"
    REVIEWER = "REVIEWER"
    RESEARCHER = "RESEARCHER"
    CODER = "CODER"
    TESTER = "TESTER"
    SYNTHESIZER = "SYNTHESIZER"
    MEMORY = "MEMORY"
    CUSTOM = "CUSTOM"


class MessageType(str, Enum):
    """Types of inter-agent messages."""
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    STATUS = "STATUS"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class CollaborationStatus(str, Enum):
    """Lifecycle status of a collaboration session."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AssignmentStatus(str, Enum):
    """Lifecycle status of an agent assignment."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DECLINED = "DECLINED"
    FAILED = "FAILED"


@dataclass
class Agent:
    """First-class domain model representing an Agent entity."""
    agent_id: str
    name: str
    role: AgentRole
    description: str | None = None
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: AgentStatus = AgentStatus.IDLE
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "description": self.description,
            "capabilities": list(self.capabilities),
            "metadata": dict(self.metadata),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "created_at": self.created_at,
        }


@dataclass
class AgentAssignment:
    """Assignment of an agent to a collaboration session or task within a workspace."""
    assignment_id: str
    session_id: str
    agent_id: str
    workspace_id: str
    task_id: str | None = None
    status: AssignmentStatus = AssignmentStatus.PENDING
    assigned_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "workspace_id": self.workspace_id,
            "task_id": self.task_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "assigned_at": self.assigned_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AgentMessage:
    """Immutable inter-agent message exchanged within a collaboration session."""
    message_id: str
    session_id: str
    sender_agent_id: str
    message_type: MessageType
    content: Any
    receiver_agent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "sender_agent_id": self.sender_agent_id,
            "receiver_agent_id": self.receiver_agent_id,
            "message_type": self.message_type.value if hasattr(self.message_type, "value") else str(self.message_type),
            "content": self.content,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


@dataclass
class CollaborationSession:
    """Lightweight collaboration session entity tied strictly to a single workspace."""
    session_id: str
    workspace_id: str
    objective: str
    participant_ids: list[str] = field(default_factory=list)
    status: CollaborationStatus = CollaborationStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "objective": self.objective,
            "participant_ids": list(self.participant_ids),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CollaborationSummary:
    """Lightweight aggregation summary of a collaboration session."""
    session_id: str
    workspace_id: str
    objective: str
    participant_count: int
    assignment_count: int
    active_assignment_count: int
    message_count: int
    status: CollaborationStatus
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "objective": self.objective,
            "participant_count": self.participant_count,
            "assignment_count": self.assignment_count,
            "active_assignment_count": self.active_assignment_count,
            "message_count": self.message_count,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
