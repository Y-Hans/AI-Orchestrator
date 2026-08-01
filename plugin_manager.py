"""PluginManager for coordinating plugin lifecycle and capability registration."""

from __future__ import annotations

from threading import Lock
from typing import Any

from capability_models import Plugin, PluginStatus
from capability_registry import CapabilityRegistry


class PluginManager:
    """Coordinator responsible for plugin lifecycle.

    Forwards capability registrations into CapabilityRegistry, which remains
    the single source of truth for all capability metadata.
    """

    def __init__(self, capability_registry: CapabilityRegistry) -> None:
        self._capability_registry = capability_registry
        self._plugins: dict[str, Plugin] = {}
        self._lock = Lock()

    def register_plugin(self, plugin: Plugin) -> Plugin:
        """Register a plugin and forward its contained capabilities to CapabilityRegistry.

        Raises:
            ValueError: If the plugin ID is already registered.
        """
        with self._lock:
            if plugin.plugin_id in self._plugins:
                raise ValueError(f"Plugin already registered: {plugin.plugin_id}")

            # Register all capabilities into CapabilityRegistry
            for cap in plugin.capabilities:
                self._capability_registry.register_capability(cap)

            plugin.status = PluginStatus.LOADED
            self._plugins[plugin.plugin_id] = plugin
            return plugin

    def unregister_plugin(self, plugin_id: str) -> Plugin:
        """Unregister a plugin and remove its capabilities from CapabilityRegistry.

        Raises:
            KeyError: If the plugin is not found.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise KeyError(f"Plugin not found: {plugin_id}")

            plugin = self._plugins[plugin_id]

            # Unregister capabilities from CapabilityRegistry
            for cap in plugin.capabilities:
                try:
                    self._capability_registry.unregister_capability(cap.capability_id)
                except (KeyError, ValueError):
                    pass

            plugin.status = PluginStatus.UNLOADED
            return self._plugins.pop(plugin_id)

    def get_plugin(self, plugin_id: str) -> Plugin:
        """Retrieve a registered plugin by ID.

        Raises:
            KeyError: If the plugin is not found.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise KeyError(f"Plugin not found: {plugin_id}")
            return self._plugins[plugin_id]

    def list_plugins(self) -> list[Plugin]:
        """Return a deterministically ordered list of all registered plugins."""
        with self._lock:
            return sorted(self._plugins.values(), key=lambda p: p.plugin_id)

    def load_plugin(self, plugin_id: str) -> Plugin:
        """Load an unloaded plugin and enable its capabilities.

        Raises:
            KeyError: If the plugin is not found.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise KeyError(f"Plugin not found: {plugin_id}")
            plugin = self._plugins[plugin_id]
            plugin.status = PluginStatus.LOADED
            for cap in plugin.capabilities:
                try:
                    self._capability_registry.enable_capability(cap.capability_id)
                except (KeyError, ValueError):
                    pass
            return plugin

    def unload_plugin(self, plugin_id: str) -> Plugin:
        """Unload an active plugin and disable its capabilities.

        Raises:
            KeyError: If the plugin is not found.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise KeyError(f"Plugin not found: {plugin_id}")
            plugin = self._plugins[plugin_id]
            plugin.status = PluginStatus.UNLOADED
            for cap in plugin.capabilities:
                try:
                    self._capability_registry.disable_capability(cap.capability_id)
                except (KeyError, ValueError):
                    pass
            return plugin

    def validate_plugin(self, plugin_id: str) -> bool:
        """Validate if a plugin and all its capabilities/dependencies are healthy."""
        with self._lock:
            if plugin_id not in self._plugins:
                return False
            plugin = self._plugins[plugin_id]
            status_str = plugin.status.value if hasattr(plugin.status, "value") else str(plugin.status)
            if status_str != PluginStatus.LOADED.value:
                return False

            for cap in plugin.capabilities:
                try:
                    registered_cap = self._capability_registry.get_capability(cap.capability_id)
                    if not self._capability_registry.validate_dependencies(registered_cap.capability_id):
                        return False
                except KeyError:
                    return False
            return True

    def summary(self) -> dict[str, Any]:
        """Generate a summary of plugin metrics."""
        with self._lock:
            total = len(self._plugins)
            loaded = 0
            unloaded = 0
            error_count = 0

            for p in self._plugins.values():
                status_str = p.status.value if hasattr(p.status, "value") else str(p.status)
                if status_str == PluginStatus.LOADED.value:
                    loaded += 1
                elif status_str == PluginStatus.UNLOADED.value:
                    unloaded += 1
                elif status_str == PluginStatus.ERROR.value:
                    error_count += 1

            return {
                "plugin_count": total,
                "loaded_count": loaded,
                "unloaded_count": unloaded,
                "error_count": error_count,
            }
