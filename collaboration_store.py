"""Thread-safe persistent store for multi-agent collaboration entities.

Single owner of CollaborationSession, AgentAssignment, and AgentMessage entities,
mirroring ArtifactStore and MemoryStore patterns.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from agent_models import (
    AgentAssignment,
    AgentMessage,
    AssignmentStatus,
    CollaborationSession,
    CollaborationStatus,
    utc_now,
)


class CollaborationStore:
    """Thread-safe in-memory store for collaboration sessions, assignments, and messages."""

    def __init__(self) -> None:
        self._sessions: dict[str, CollaborationSession] = {}
        self._assignments: dict[str, AgentAssignment] = {}
        self._messages: list[AgentMessage] = []
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Collaboration Sessions
    # ------------------------------------------------------------------

    def add_session(self, session: CollaborationSession) -> CollaborationSession:
        """Store a new collaboration session."""
        with self._lock:
            if session.session_id in self._sessions:
                raise ValueError(f"Collaboration session already exists: {session.session_id}")
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> CollaborationSession:
        """Retrieve a session by session_id."""
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Collaboration session not found: {session_id}")
        return session

    def list_sessions(self, workspace_id: str | None = None) -> list[CollaborationSession]:
        """List collaboration sessions, optionally filtered by workspace_id."""
        with self._lock:
            sessions = list(self._sessions.values())
        if workspace_id is not None:
            sessions = [s for s in sessions if s.workspace_id == workspace_id]
        return sessions

    def update_session(
        self,
        session_id: str,
        status: CollaborationStatus | str | None = None,
        participant_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CollaborationSession:
        """Update session state (status, participants, or metadata)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Collaboration session not found: {session_id}")

            if status is not None:
                session.status = status if isinstance(status, CollaborationStatus) else CollaborationStatus(status.upper())
            if participant_ids is not None:
                session.participant_ids = list(set(participant_ids))
            if metadata is not None:
                session.metadata.update(metadata)
            session.updated_at = utc_now()
            return session

    # ------------------------------------------------------------------
    # Agent Assignments
    # ------------------------------------------------------------------

    def add_assignment(self, assignment: AgentAssignment) -> AgentAssignment:
        """Store a new agent assignment."""
        with self._lock:
            if assignment.assignment_id in self._assignments:
                raise ValueError(f"Assignment already exists: {assignment.assignment_id}")
            self._assignments[assignment.assignment_id] = assignment
        return assignment

    def get_assignment(self, assignment_id: str) -> AgentAssignment:
        """Retrieve an assignment by assignment_id."""
        with self._lock:
            assignment = self._assignments.get(assignment_id)
        if assignment is None:
            raise KeyError(f"Assignment not found: {assignment_id}")
        return assignment

    def update_assignment_status(
        self,
        assignment_id: str,
        status: AssignmentStatus | str,
    ) -> AgentAssignment:
        """Update assignment status."""
        status_enum = status if isinstance(status, AssignmentStatus) else AssignmentStatus(status.upper())
        with self._lock:
            assignment = self._assignments.get(assignment_id)
            if assignment is None:
                raise KeyError(f"Assignment not found: {assignment_id}")
            assignment.status = status_enum
            return assignment

    def list_assignments(
        self,
        session_id: str | None = None,
        agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[AgentAssignment]:
        """List assignments filtered by session_id, agent_id, and/or workspace_id."""
        with self._lock:
            assignments = list(self._assignments.values())

        if session_id is not None:
            assignments = [a for a in assignments if a.session_id == session_id]
        if agent_id is not None:
            assignments = [a for a in assignments if a.agent_id == agent_id]
        if workspace_id is not None:
            assignments = [a for a in assignments if a.workspace_id == workspace_id]
        return assignments

    # ------------------------------------------------------------------
    # Agent Messages (Immutable, Append-Only)
    # ------------------------------------------------------------------

    def add_message(self, message: AgentMessage) -> AgentMessage:
        """Append an immutable agent message."""
        with self._lock:
            self._messages.append(message)
        return message

    def list_messages(
        self,
        session_id: str | None = None,
        receiver_agent_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentMessage]:
        """List messages in deterministic order (creation/index), with optional filters."""
        with self._lock:
            msgs = list(self._messages)

        if session_id is not None:
            msgs = [m for m in msgs if m.session_id == session_id]

        if receiver_agent_id is not None:
            # Matches direct messages to this receiver or session broadcast messages (receiver_agent_id is None)
            msgs = [
                m for m in msgs
                if m.receiver_agent_id is None or m.receiver_agent_id == receiver_agent_id
            ]

        if limit is not None and limit > 0:
            msgs = msgs[-limit:]

        return msgs
