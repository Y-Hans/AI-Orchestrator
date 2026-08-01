"""Thread-safe single-authority registry for installed capabilities."""

from __future__ import annotations

from threading import Lock
from typing import Any

from capability_models import Capability, CapabilityStatus, CapabilitySummary


class CapabilityRegistry:
    """Thread-safe authority for installed capability metadata and lifecycle."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._lock = Lock()

    def register_capability(self, capability: Capability) -> Capability:
        """Register a new capability in the registry.

        Raises:
            ValueError: If a capability with the same ID is already registered.
        """
        with self._lock:
            if capability.capability_id in self._capabilities:
                raise ValueError(f"Capability already registered: {capability.capability_id}")
            self._capabilities[capability.capability_id] = capability
            return capability

    def unregister_capability(self, capability_id: str) -> Capability:
        """Remove a capability from the registry.

        Raises:
            KeyError: If the capability is not found.
            ValueError: If other capabilities depend on this capability.
        """
        with self._lock:
            if capability_id not in self._capabilities:
                raise KeyError(f"Capability not found: {capability_id}")

            dependents = [
                cid for cid, cap in self._capabilities.items()
                if capability_id in cap.dependencies
            ]
            if dependents:
                raise ValueError(
                    f"Cannot unregister capability '{capability_id}': depended upon by {dependents}"
                )

            return self._capabilities.pop(capability_id)

    def get_capability(self, capability_id: str) -> Capability:
        """Retrieve a registered capability by ID.

        Raises:
            KeyError: If the capability is not found.
        """
        with self._lock:
            if capability_id not in self._capabilities:
                raise KeyError(f"Capability not found: {capability_id}")
            return self._capabilities[capability_id]

    def list_capabilities(self) -> list[Capability]:
        """Return a deterministically ordered list of all registered capabilities."""
        with self._lock:
            return sorted(self._capabilities.values(), key=lambda c: c.capability_id)

    def validate_dependencies(self, capability_id: str) -> bool:
        """Check if all declared dependencies for a capability exist and are ENABLED."""
        with self._lock:
            if capability_id not in self._capabilities:
                raise KeyError(f"Capability not found: {capability_id}")
            capability = self._capabilities[capability_id]
            for dep_id in capability.dependencies:
                dep = self._capabilities.get(dep_id)
                if dep is None:
                    return False
                status_str = dep.status.value if hasattr(dep.status, "value") else str(dep.status)
                if status_str != CapabilityStatus.ENABLED.value:
                    return False
            return True

    def enable_capability(self, capability_id: str) -> Capability:
        """Enable a registered capability after verifying its dependencies.

        Raises:
            KeyError: If the capability is not found.
            ValueError: If declared dependencies are missing or not ENABLED.
        """
        with self._lock:
            if capability_id not in self._capabilities:
                raise KeyError(f"Capability not found: {capability_id}")
            capability = self._capabilities[capability_id]

            for dep_id in capability.dependencies:
                dep = self._capabilities.get(dep_id)
                if dep is None:
                    raise ValueError(
                        f"Cannot enable capability '{capability_id}': missing dependency '{dep_id}'"
                    )
                status_str = dep.status.value if hasattr(dep.status, "value") else str(dep.status)
                if status_str != CapabilityStatus.ENABLED.value:
                    raise ValueError(
                        f"Cannot enable capability '{capability_id}': dependency '{dep_id}' is not ENABLED (current status: {status_str})"
                    )

            capability.status = CapabilityStatus.ENABLED
            return capability

    def disable_capability(self, capability_id: str) -> Capability:
        """Disable an active capability.

        Raises:
            KeyError: If the capability is not found.
            ValueError: If enabled capabilities depend on this capability.
        """
        with self._lock:
            if capability_id not in self._capabilities:
                raise KeyError(f"Capability not found: {capability_id}")

            enabled_dependents = []
            for cid, cap in self._capabilities.items():
                if capability_id in cap.dependencies:
                    status_str = cap.status.value if hasattr(cap.status, "value") else str(cap.status)
                    if status_str == CapabilityStatus.ENABLED.value:
                        enabled_dependents.append(cid)

            if enabled_dependents:
                raise ValueError(
                    f"Cannot disable capability '{capability_id}': enabled capabilities depend on it: {enabled_dependents}"
                )

            capability = self._capabilities[capability_id]
            capability.status = CapabilityStatus.DISABLED
            return capability

    def list_dependents(self, capability_id: str) -> list[str]:
        """Return a sorted list of capability IDs that depend on the specified capability."""
        with self._lock:
            if capability_id not in self._capabilities:
                raise KeyError(f"Capability not found: {capability_id}")
            dependents = [
                cid for cid, cap in self._capabilities.items()
                if capability_id in cap.dependencies
            ]
            return sorted(dependents)

    def summary(self, plugin_count: int = 0) -> CapabilitySummary:
        """Generate a summary of capability metrics."""
        with self._lock:
            total = len(self._capabilities)
            enabled = 0
            disabled = 0
            version_sum: dict[str, str] = {}

            for cid, cap in sorted(self._capabilities.items()):
                version_sum[cid] = cap.version
                status_str = cap.status.value if hasattr(cap.status, "value") else str(cap.status)
                if status_str == CapabilityStatus.ENABLED.value:
                    enabled += 1
                elif status_str == CapabilityStatus.DISABLED.value:
                    disabled += 1

            return CapabilitySummary(
                capability_count=total,
                enabled_count=enabled,
                disabled_count=disabled,
                plugin_count=plugin_count,
                version_summary=version_sum,
            )
