"""Thread-safe registry for storing and managing Agent entities.

Responsible ONLY for agent identity, capability discovery, status transitions,
and registry CRUD operations. Serves as the single source of truth for Agent domain models.
"""

from __future__ import annotations

from threading import Lock
from typing import Any
from uuid import uuid4

from agent_models import Agent, AgentRole, AgentStatus, utc_now


class AgentRegistry:
    """Thread-safe in-memory store for Agent entities."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._lock = Lock()

    def register_agent(
        self,
        name: str,
        role: AgentRole | str = AgentRole.GENERAL,
        description: str | None = None,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        agent_id: str | None = None,
        status: AgentStatus | str = AgentStatus.IDLE,
    ) -> Agent:
        """Register a new agent in the registry."""
        if not name or not isinstance(name, str):
            raise ValueError("Agent name must be a non-empty string.")

        if isinstance(role, str):
            try:
                role_enum = AgentRole(role.upper())
            except ValueError:
                role_enum = AgentRole.CUSTOM
        else:
            role_enum = role

        if isinstance(status, str):
            try:
                status_enum = AgentStatus(status.upper())
            except ValueError:
                status_enum = AgentStatus.IDLE
        else:
            status_enum = status

        effective_id = agent_id or str(uuid4())

        agent = Agent(
            agent_id=effective_id,
            name=name,
            role=role_enum,
            description=description,
            capabilities=list(capabilities) if capabilities else [],
            metadata=dict(metadata) if metadata else {},
            status=status_enum,
            created_at=utc_now(),
        )

        with self._lock:
            self._agents[agent.agent_id] = agent
        return agent

    def unregister_agent(self, agent_id: str) -> Agent:
        """Remove an agent from the registry."""
        with self._lock:
            agent = self._agents.pop(agent_id, None)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_id}")
        return agent

    def get_agent(self, agent_id: str) -> Agent:
        """Retrieve an agent by agent_id."""
        with self._lock:
            agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_id}")
        return agent

    def list_agents(self) -> list[Agent]:
        """List all registered agents."""
        with self._lock:
            return list(self._agents.values())

    def update_status(self, agent_id: str, status: AgentStatus | str) -> Agent:
        """Update the operational status of an agent."""
        if isinstance(status, str):
            status_enum = AgentStatus(status.upper())
        else:
            status_enum = status

        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                raise KeyError(f"Agent not found: {agent_id}")
            agent.status = status_enum
            return agent

    def filter_by_role(self, role: AgentRole | str) -> list[Agent]:
        """Filter agents by role."""
        target_role = role.value if isinstance(role, AgentRole) else str(role).upper()
        with self._lock:
            return [
                a for a in self._agents.values()
                if (a.role.value if hasattr(a.role, "value") else str(a.role)) == target_role
            ]

    def filter_by_capability(self, capability: str) -> list[Agent]:
        """Filter agents having a specific capability."""
        with self._lock:
            return [
                a for a in self._agents.values()
                if capability in a.capabilities
            ]
