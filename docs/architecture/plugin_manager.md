# Architecture: PluginManager

## Overview

The `PluginManager` acts as a lifecycle coordinator for external extensions and plugin packages. It manages plugin metadata while delegating capability state and authority to the workspace's `CapabilityRegistry`.

## Key Architectural Principles

- **Dependency Injection**: `PluginManager` receives the workspace's `CapabilityRegistry` at construction (`__init__`).
- **Single Source of Truth**: Capabilities contained in a plugin are registered directly into `CapabilityRegistry`. `PluginManager` owns zero capability state.
- **Plugin Lifecycle**: Manages loading, unloading, and validation of plugin packages.

## Class Specification

```python
class PluginManager:
    def __init__(self, capability_registry: CapabilityRegistry) -> None: ...
    def register_plugin(self, plugin: Plugin) -> Plugin: ...
    def unregister_plugin(self, plugin_id: str) -> Plugin: ...
    def get_plugin(self, plugin_id: str) -> Plugin: ...
    def list_plugins(self) -> list[Plugin]: ...
    def load_plugin(self, plugin_id: str) -> Plugin: ...
    def unload_plugin(self, plugin_id: str) -> Plugin: ...
    def validate_plugin(self, plugin_id: str) -> bool: ...
    def summary(self) -> dict[str, Any]: ...
```

## Plugin Lifecycle States

- `LOADED`: Plugin is active and its capabilities are registered/enabled.
- `UNLOADED`: Plugin is inactive and its capabilities are disabled.
- `ERROR`: Plugin validation or loading failed.
