# Capability 10 — Capability Registry & Plugin Framework

## Executive Summary

Capability 10 completes the core platform architecture of AI-Orchestrator by introducing a centralized, thread-safe `CapabilityRegistry` and a lightweight `PluginManager`. It establishes an extensible discovery and lifecycle management layer across workspaces while preserving the frozen architecture of Capabilities 1–9.

## Key Architectural Principles

1. **CapabilityRegistry as Single Authority**: The registry is the sole source of truth for installed capability metadata, dependency validation, and lifecycle state.
2. **PluginManager as Coordinator**: Manages plugin loading/unloading and forwards capability registrations into `CapabilityRegistry` (does not store duplicate capability state).
3. **TaskWorkspace Ownership**: Each `TaskWorkspace` owns its `capability_registry` and `plugin_manager` instances. No global singleton registry exists.
4. **Strongly Typed Domain Models**: Dedicated dataclasses (`Capability`, `Plugin`, `CapabilitySummary`) and enums (`CapabilityStatus`, `PluginStatus`, `CapabilityType`).
5. **Brain Façade Routing**: `AntigravityBrain` exposes façade routing methods delegating directly to the target workspace without embedding business logic.
6. **Strict Responsibility Scoping**: Capability 10 is strictly responsible for capability/plugin discovery, registration, dependency checking, and metadata. It never executes tasks, plans, schedules, reviews, synthesizes, stores memories, or coordinates agents.

## Core Domain Models

- **`Capability`**: Represents an individual system capability or extension.
  - Fields: `capability_id`, `name`, `version`, `description`, `capability_type`, `status`, `dependencies`, `mcp_tools`, `metadata`, `created_at`.
- **`Plugin`**: Represents a bundle of capabilities and metadata.
  - Fields: `plugin_id`, `name`, `version`, `description`, `status`, `capabilities`, `metadata`, `created_at`.
- **`CapabilitySummary`**: Aggregated statistics for workspace capabilities and plugins.
  - Fields: `capability_count`, `enabled_count`, `disabled_count`, `plugin_count`, `version_summary`.

## MCP Tools (13 New Tools)

- `register_capability`: Register a capability.
- `unregister_capability`: Remove a capability.
- `get_capability`: Retrieve capability metadata.
- `list_capabilities`: List all registered capabilities in deterministic order.
- `enable_capability`: Enable a capability after dependency validation.
- `disable_capability`: Disable an active capability.
- `register_plugin`: Register a plugin and forward capabilities into registry.
- `unregister_plugin`: Remove a plugin and its capabilities.
- `load_plugin`: Load an unloaded plugin.
- `unload_plugin`: Unload an active plugin.
- `list_plugins`: List registered plugins in deterministic order.
- `get_plugin`: Retrieve plugin details.
- `capability_summary`: Retrieve capability and plugin metric summary.

## Verification & Status

Capability 10 is fully verified with unit tests covering serialization, thread safety, dependency validation, workspace ownership, Brain façade routing, and MCP JSON-RPC tool dispatch.
