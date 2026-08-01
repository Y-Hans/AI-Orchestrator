"""Domain models for Capability Registry & Plugin Framework."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class CapabilityStatus(str, Enum):
    REGISTERED = "REGISTERED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class PluginStatus(str, Enum):
    LOADED = "LOADED"
    UNLOADED = "UNLOADED"
    ERROR = "ERROR"


class CapabilityType(str, Enum):
    CORE = "CORE"
    EXTENSION = "EXTENSION"
    PLUGIN = "PLUGIN"
    EXPERIMENTAL = "EXPERIMENTAL"


@dataclass
class Capability:
    capability_id: str
    name: str
    version: str
    description: str
    capability_type: CapabilityType | str = CapabilityType.EXTENSION
    status: CapabilityStatus | str = CapabilityStatus.REGISTERED
    dependencies: list[str] = field(default_factory=list)
    mcp_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capability_type": (
                self.capability_type.value
                if isinstance(self.capability_type, Enum)
                else str(self.capability_type)
            ),
            "status": (
                self.status.value
                if isinstance(self.status, Enum)
                else str(self.status)
            ),
            "dependencies": list(self.dependencies),
            "mcp_tools": list(self.mcp_tools),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


@dataclass
class Plugin:
    plugin_id: str
    name: str
    version: str
    description: str
    status: PluginStatus | str = PluginStatus.LOADED
    capabilities: list[Capability] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "status": (
                self.status.value
                if isinstance(self.status, Enum)
                else str(self.status)
            ),
            "capabilities": [c.to_dict() for c in self.capabilities],
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


@dataclass
class CapabilitySummary:
    capability_count: int
    enabled_count: int
    disabled_count: int
    plugin_count: int
    version_summary: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
