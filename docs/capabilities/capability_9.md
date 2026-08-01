# Capability 9 — Multi-Agent Collaboration Framework

## Overview
Capability 9 introduces first-class Agent entities and coordinated multi-agent workflows for AI-Orchestrator without modifying the core responsibilities or frozen invariants of Capabilities 1–8 (Planner, Scheduler, Execution Engine, Review Engine, Memory Engine, Synthesis Engine).

The Multi-Agent Collaboration Framework provides structured agent registration, capability discovery, task assignments, collaboration session management, immutable inter-agent messaging, and workspace coordination.

## Core Invariants & Architectural Principles
1. **First-class Agent entities**: Every agent has a unique identity (`agent_id`), role, description, capabilities list, status, metadata, and creation timestamp. Serves as a domain model owned by `AgentRegistry`.
2. **Session-driven collaboration**: Collaboration occurs inside a `CollaborationSession` owned by `CollaborationStore`. Sessions belong strictly to a single workspace (`workspace_id`).
3. **Explicit inter-agent communication**: Interactions are recorded as immutable `AgentMessage` entities stored in deterministic order.
4. **Deterministic assignment**: `AgentAssignment` objects explicitly link agents to collaboration sessions and optional task IDs. No hidden AI routing.
5. **Zero Execution, Planning, Review, or Synthesis Logic**: The collaboration engine is an inter-agent coordinator only. Model executions remain owned by `ExecutionEngine`, task graphs by `TaskPlanner`, reviews by `ReviewEngine`, memories by `MemoryEngine`, and result synthesis by `SynthesisEngine`.
6. **Thread-Safe Architecture**: `AgentRegistry` and `CollaborationStore` employ fine-grained mutex locking to guarantee concurrent safe execution across threads.

## Architecture & Components

```
+------------------------------------------------------------------+
|                          AntigravityBrain                        |
+------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------+
|                           TaskWorkspace                          |
|  +--------------------+  +-------------------+  +-------------+  |
|  |   AgentRegistry    |  | CollaborationEngine|  |CollabStore  |  |
|  +--------------------+  +-------------------+  +-------------+  |
+------------------------------------------------------------------+
```

### Components
- **`agent_models.py`**: Enums (`AgentStatus`, `AgentRole`, `MessageType`, `CollaborationStatus`, `AssignmentStatus`) and dataclasses (`Agent`, `AgentAssignment`, `AgentMessage`, `CollaborationSession`, `CollaborationSummary`).
- **`agent_registry.py`**: Thread-safe registry for agent registration, lookup, status updates, and capability discovery.
- **`collaboration_store.py`**: Thread-safe store owning `CollaborationSession`, `AgentAssignment`, and `AgentMessage` persistent records.
- **`collaboration_engine.py`**: Coordinator exposing workflow methods (`create_session`, `close_session`, `assign_agent`, `send_message`, `receive_messages`, `get_session_summary`) with dependency injection for messaging backends.

## MCP Tools Introduced
1. `register_agent`
2. `unregister_agent`
3. `get_agent`
4. `list_agents`
5. `create_collaboration`
6. `close_collaboration`
7. `assign_agent`
8. `send_agent_message`
9. `list_messages`
10. `list_assignments`
11. `list_sessions`
