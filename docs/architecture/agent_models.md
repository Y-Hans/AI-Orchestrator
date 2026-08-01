# Agent Data Models Architecture

## Overview
`agent_models.py` provides strongly typed dataclasses and string enums for Capability 9.

## Key Models & Enums

### Enums
- **`AgentStatus`**: `IDLE`, `BUSY`, `WAITING`, `OFFLINE`, `ERROR`.
- **`AgentRole`**: `GENERAL`, `PLANNER`, `EXECUTOR`, `REVIEWER`, `RESEARCHER`, `CODER`, `TESTER`, `SYNTHESIZER`, `MEMORY`, `CUSTOM`.
- **`MessageType`**: `REQUEST`, `RESPONSE`, `STATUS`, `INFO`, `WARNING`, `ERROR`.
- **`CollaborationStatus`**: `ACTIVE`, `PAUSED`, `COMPLETED`, `FAILED`.
- **`AssignmentStatus`**: `PENDING`, `ACCEPTED`, `IN_PROGRESS`, `COMPLETED`, `DECLINED`, `FAILED`.

### Dataclasses
- **`Agent`**: First-class domain model with `agent_id`, `name`, `role`, `description`, `capabilities`, `metadata`, `status`, `created_at`.
- **`AgentAssignment`**: Explicit link between agent, session, workspace, and optional task ID with assignment status.
- **`AgentMessage`**: Immutable, frozen dataclass representing inter-agent messages with deterministic creation timestamp ordering.
- **`CollaborationSession`**: Lightweight session object storing `session_id`, `workspace_id`, `objective`, `participant_ids`, `status`, `metadata`, `created_at`, `updated_at`.
- **`CollaborationSummary`**: Lightweight summary statistics for a session.
