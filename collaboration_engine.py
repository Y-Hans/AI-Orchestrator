"""Collaboration Engine for Capability 9 — Multi-Agent Collaboration Framework.

Coordinated multi-agent workflow engine. Does NOT execute models directly, nor
replace TaskPlanner, DependencyScheduler, ExecutionEngine, ReviewEngine, MemoryEngine,
or SynthesisEngine. Serves purely as an inter-agent coordinator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from agent_models import (
    Agent,
    AgentAssignment,
    AgentMessage,
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


class MessagingBackend(ABC):
    """Abstract interface for inter-agent messaging transport backends."""

    @abstractmethod
    def dispatch_message(self, message: AgentMessage, store: CollaborationStore) -> None:
        """Dispatch a message to storage or downstream receivers."""
        pass


class InMemoryMessagingBackend(MessagingBackend):
    """Default deterministic in-memory messaging backend."""

    def dispatch_message(self, message: AgentMessage, store: CollaborationStore) -> None:
        """Store message directly in CollaborationStore."""
        store.add_message(message)


class CollaborationEngine:
    """Coordinator for multi-agent workflows and collaboration sessions."""

    def __init__(
        self,
        workspace: Any,
        registry: AgentRegistry | None = None,
        store: CollaborationStore | None = None,
        messaging_backend: MessagingBackend | None = None,
    ) -> None:
        self.workspace = workspace
        self.workspace_id = workspace.workspace_id if hasattr(workspace, "workspace_id") else str(workspace)
        self.registry = registry or AgentRegistry()
        self.store = store or CollaborationStore()
        self.messaging_backend = messaging_backend or InMemoryMessagingBackend()

    def create_session(
        self,
        objective: str,
        participant_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        workspace_id: str | None = None,
    ) -> CollaborationSession:
        """Create a lightweight collaboration session tied strictly to a single workspace."""
        if not objective or not isinstance(objective, str):
            raise ValueError("Session objective must be a non-empty string.")

        target_workspace_id = workspace_id or self.workspace_id

        # Verify participant agent IDs exist in registry if provided
        p_ids = list(participant_ids) if participant_ids else []
        for pid in p_ids:
            self.registry.get_agent(pid)  # Raises KeyError if agent doesn't exist

        session = CollaborationSession(
            session_id=session_id or str(uuid4()),
            workspace_id=target_workspace_id,
            objective=objective,
            participant_ids=p_ids,
            status=CollaborationStatus.ACTIVE,
            metadata=dict(metadata) if metadata else {},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        return self.store.add_session(session)

    def close_session(
        self,
        session_id: str,
        status: CollaborationStatus | str = CollaborationStatus.COMPLETED,
    ) -> CollaborationSession:
        """Close an active collaboration session."""
        status_enum = status if isinstance(status, CollaborationStatus) else CollaborationStatus(status.upper())
        session = self.store.update_session(session_id, status=status_enum)

        # Set participating agents' status back to IDLE if appropriate
        for pid in session.participant_ids:
            try:
                agent = self.registry.get_agent(pid)
                if agent.status == AgentStatus.BUSY:
                    self.registry.update_status(pid, AgentStatus.IDLE)
            except KeyError:
                pass

        return session

    def get_session(self, session_id: str) -> CollaborationSession:
        """Retrieve a session by session_id."""
        return self.store.get_session(session_id)

    def list_sessions(self, workspace_id: str | None = None) -> list[CollaborationSession]:
        """List collaboration sessions for the workspace."""
        target_ws_id = workspace_id or self.workspace_id
        return self.store.list_sessions(workspace_id=target_ws_id)

    def assign_agent(
        self,
        session_id: str,
        agent_id: str,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        assignment_id: str | None = None,
    ) -> AgentAssignment:
        """Explicitly assign an agent to a collaboration session and optional task."""
        session = self.store.get_session(session_id)
        agent = self.registry.get_agent(agent_id)

        # Add agent to session participant list if not already present
        if agent_id not in session.participant_ids:
            updated_participants = list(session.participant_ids) + [agent_id]
            self.store.update_session(session_id, participant_ids=updated_participants)

        assignment = AgentAssignment(
            assignment_id=assignment_id or str(uuid4()),
            session_id=session_id,
            agent_id=agent_id,
            workspace_id=session.workspace_id,
            task_id=task_id,
            status=AssignmentStatus.PENDING,
            assigned_at=utc_now(),
            metadata=dict(metadata) if metadata else {},
        )

        self.store.add_assignment(assignment)
        self.registry.update_status(agent_id, AgentStatus.BUSY)
        return assignment

    def update_assignment_status(
        self,
        assignment_id: str,
        status: AssignmentStatus | str,
    ) -> AgentAssignment:
        """Update the status of an agent assignment."""
        return self.store.update_assignment_status(assignment_id, status)

    def list_assignments(
        self,
        session_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[AgentAssignment]:
        """List agent assignments filtered by session_id and/or agent_id."""
        return self.store.list_assignments(
            session_id=session_id,
            agent_id=agent_id,
            workspace_id=self.workspace_id,
        )

    def list_participants(self, session_id: str) -> list[Agent]:
        """Return full Agent objects for all participants in a collaboration session."""
        session = self.store.get_session(session_id)
        participants = []
        for pid in session.participant_ids:
            try:
                participants.append(self.registry.get_agent(pid))
            except KeyError:
                pass
        return participants

    def send_message(
        self,
        session_id: str,
        sender_agent_id: str,
        content: Any,
        message_type: MessageType | str = MessageType.INFO,
        receiver_agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessage:
        """Send an immutable AgentMessage within a collaboration session."""
        session = self.store.get_session(session_id)
        self.registry.get_agent(sender_agent_id)  # Validate sender exists

        if receiver_agent_id is not None:
            self.registry.get_agent(receiver_agent_id)  # Validate receiver exists

        msg_type = message_type if isinstance(message_type, MessageType) else MessageType(str(message_type).upper())

        message = AgentMessage(
            message_id=str(uuid4()),
            session_id=session_id,
            sender_agent_id=sender_agent_id,
            receiver_agent_id=receiver_agent_id,
            message_type=msg_type,
            content=content,
            metadata=dict(metadata) if metadata else {},
            created_at=utc_now(),
        )

        self.messaging_backend.dispatch_message(message, self.store)
        return message

    def receive_messages(
        self,
        session_id: str,
        receiver_agent_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentMessage]:
        """Retrieve messages from a session in deterministic creation order."""
        self.store.get_session(session_id)  # Validate session exists
        return self.store.list_messages(
            session_id=session_id,
            receiver_agent_id=receiver_agent_id,
            limit=limit,
        )

    def get_session_history(self, session_id: str) -> list[AgentMessage]:
        """Retrieve full message history for a collaboration session."""
        return self.receive_messages(session_id=session_id)

    def get_session_summary(self, session_id: str) -> CollaborationSummary:
        """Return lightweight summary statistics for a collaboration session."""
        session = self.store.get_session(session_id)
        assignments = self.store.list_assignments(session_id=session_id)
        messages = self.store.list_messages(session_id=session_id)

        active_assignments = [
            a for a in assignments
            if (a.status.value if hasattr(a.status, "value") else str(a.status)) in ("PENDING", "ACCEPTED", "IN_PROGRESS")
        ]

        return CollaborationSummary(
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            objective=session.objective,
            participant_count=len(session.participant_ids),
            assignment_count=len(assignments),
            active_assignment_count=len(active_assignments),
            message_count=len(messages),
            status=session.status,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
