# Architecture: CapabilityRegistry

## Overview

The `CapabilityRegistry` is a thread-safe, single-authority component responsible for capability lifecycle and metadata management within an AI-Orchestrator workspace.

## Component Responsibilities

- **Capability Registration & Unregistration**: Safely registers new capabilities and prevents duplicate capability IDs.
- **Dependency Validation**: Validates that all declared capability dependencies exist and are in the `ENABLED` status before activating a capability.
- **Dependency Tracking**: Tracks dependent capabilities to prevent unregistering or disabling capabilities that active dependents rely upon.
- **Deterministic Ordering**: Returns capability lists ordered deterministically by `capability_id`.
- **Thread Safety**: Uses internal reentrant/mutex locks (`threading.Lock`) to guarantee safe concurrent access.

## Class Specification

```python
class CapabilityRegistry:
    def register_capability(self, capability: Capability) -> Capability: ...
    def unregister_capability(self, capability_id: str) -> Capability: ...
    def get_capability(self, capability_id: str) -> Capability: ...
    def list_capabilities(self) -> list[Capability]: ...
    def enable_capability(self, capability_id: str) -> Capability: ...
    def disable_capability(self, capability_id: str) -> Capability: ...
    def validate_dependencies(self, capability_id: str) -> bool: ...
    def list_dependents(self, capability_id: str) -> list[str]: ...
    def summary(self, plugin_count: int = 0) -> CapabilitySummary: ...
```

## Lifecycle States

- `REGISTERED`: Capability is registered but not active.
- `ENABLED`: Capability is verified, dependencies satisfied, and active.
- `DISABLED`: Capability is manually or automatically deactivated.
- `ERROR`: Capability encountered an initialization or runtime fault.
