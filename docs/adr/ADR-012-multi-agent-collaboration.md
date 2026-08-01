# ADR-012: Multi-Agent Collaboration Framework Architecture

## Status
Accepted

## Context
AI-Orchestrator requires first-class support for multi-agent workflows where specialized agents can register their capabilities, receive explicit assignments, collaborate inside sessions, and exchange immutable messages. At the same time, all frozen invariants of Capabilities 1–8 (Planner, Scheduler, Execution Engine, Review Engine, Memory Engine, Synthesis Engine) must be strictly preserved.

## Decision
1. **Separation of Orchestration Types**: The Multi-Agent Collaboration Framework orchestrates *between* agents—it does NOT orchestrate tasks, execute models, plan graphs, perform reviews, or summarize results.
2. **State Ownership**: `CollaborationStore` is introduced as the single thread-safe owner of `CollaborationSession`, `AgentAssignment`, and `AgentMessage` records. `CollaborationEngine` acts solely as a coordinator without owning state.
3. **Agent Registry**: `AgentRegistry` is the single source of truth for `Agent` domain models. Sessions, assignments, and messages reference agents by `agent_id` only.
4. **Lightweight Sessions**: `CollaborationSession` objects store only metadata and `participant_ids`. Messages and assignments are queried dynamically from `CollaborationStore`.
5. **Immutable Messages**: `AgentMessage` records are frozen and append-only, ensuring deterministic timestamp ordering.
6. **Messaging Abstraction**: Inter-agent transport uses an abstract `MessagingBackend` interface, defaulting to `InMemoryMessagingBackend`.
7. **Workspace Scope**: Sessions belong strictly to a single `workspace_id`.
8. **Explicit Deferral**: No auto-delegation, routing heuristics, leader election, consensus algorithms, or swarm intelligence.

## Consequences
- Clean separation between task orchestration and agent coordination.
- 100% backward compatibility with Capabilities 1–8.
- Thread-safe, deterministic multi-agent session management.
