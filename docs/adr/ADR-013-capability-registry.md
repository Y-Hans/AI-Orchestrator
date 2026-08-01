# ADR-013: Capability Registry & Plugin Framework

## Status

Accepted

## Context

AI-Orchestrator required a centralized registry for discovery, dependency validation, and lifecycle management of installed system capabilities and external plugins. Without a single authority, capability metadata could become fragmented across workspace subsystems.

## Decision

1. **Introduce `CapabilityRegistry` as Single Source of Truth**:
   - Thread-safe registry owned per `TaskWorkspace`.
   - Sole authority for capability metadata, dependency validation, and capability status tracking.
2. **Introduce `PluginManager` as Coordinator**:
   - Receives `CapabilityRegistry` via dependency injection.
   - Manages plugin lifecycle (LOADED, UNLOADED, ERROR).
   - Forwards capability registrations to `CapabilityRegistry` (stores no duplicate capability state).
3. **Workspace Ownership**:
   - `TaskWorkspace` owns its `capability_registry` and `plugin_manager`.
   - No global singleton registry is introduced.
4. **Thin Façade in `AntigravityBrain`**:
   - `AntigravityBrain` delegates capability and plugin operations directly to workspace instances without embedding business logic.

## Consequences

- Clear, single-authority model for capability metadata.
- Thread-safe capability operations across multi-agent sessions.
- Strict architectural boundaries: Capability 10 is strictly discovery & lifecycle management (no execution, planning, scheduling, review, synthesis, memory, or collaboration).
- Complete backward compatibility with Capabilities 1–9.
