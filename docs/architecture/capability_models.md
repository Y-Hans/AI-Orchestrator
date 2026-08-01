# Architecture: Capability Domain Models

## Overview

Capability 10 introduces strongly-typed Python dataclasses and Enums to model capabilities, plugins, and system metrics.

## Enums

- **`CapabilityStatus`**: `REGISTERED`, `ENABLED`, `DISABLED`, `ERROR`
- **`PluginStatus`**: `LOADED`, `UNLOADED`, `ERROR`
- **`CapabilityType`**: `CORE`, `EXTENSION`, `PLUGIN`, `EXPERIMENTAL`

## Dataclasses

### `Capability`

```python
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
```

### `Plugin`

```python
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
```

### `CapabilitySummary`

```python
@dataclass
class CapabilitySummary:
    capability_count: int
    enabled_count: int
    disabled_count: int
    plugin_count: int
    version_summary: dict[str, str]
```
