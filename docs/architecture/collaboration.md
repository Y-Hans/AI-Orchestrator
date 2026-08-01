# Multi-Agent Collaboration Engine Architecture

## Overview
The `CollaborationEngine` acts as an inter-agent workflow coordinator within a `TaskWorkspace`. It coordinates multi-agent collaboration sessions, agent assignments, and inter-agent message passing without executing models or planning tasks directly.

## Key Responsibilities
- **Session Lifecycle Management**: Create, track, and close lightweight `CollaborationSession` instances bound to a workspace.
- **Agent Assignments**: Bind agents to sessions and specific task IDs via `AgentAssignment` entities with lifecycle status (`PENDING`, `ACCEPTED`, `IN_PROGRESS`, `COMPLETED`, `DECLINED`, `FAILED`).
- **Inter-Agent Messaging**: Transport and deliver immutable `AgentMessage` records between agents (direct or broadcast).
- **Session Summaries**: Provide aggregate statistics (`CollaborationSummary`) detailing participant counts, active assignments, and total message counts.
- **Backend Abstraction**: Expose an abstract `MessagingBackend` interface, defaulting to deterministic `InMemoryMessagingBackend`.

## Non-Responsibilities
- Does NOT execute LLM calls or model prompts (owned by `ExecutionEngine`).
- Does NOT decompose objectives into task graphs (owned by `TaskPlanner`).
- Does NOT enforce task dependency order (owned by `DependencyScheduler`).
- Does NOT evaluate outputs against quality criteria (owned by `ReviewEngine`).
- Does NOT summarize workspace artifacts or executions (owned by `SynthesisEngine`).
- Does NOT store persistent knowledge notes (owned by `MemoryEngine`).

## Data Flow & Storage Separations
`CollaborationEngine` is purely a coordinator and owns no persistent state. All persistent records are stored in `CollaborationStore`, while `AgentRegistry` remains the single source of truth for `Agent` entities.
