# Planner Data Models & Schema Specifications

**Module**: [planner_models.py](file:///c:/Users/user/AI-Orchestrator/planner_models.py)

---

## 1. Overview

`planner_models.py` provides strongly-typed data models for Capability 5 (Intelligent Task Planner), including Objectives, Plans, Level Specs, Task Specs, and immutable Planning Results.

---

## 2. Model Schemas

### `Objective`
First-class representation of a high-level user objective:
- `objective_id`: Unique identifier.
- `workspace_id`: ID of target workspace.
- `title`: Short objective title.
- `description`: Detailed description.
- `constraints`: List of constraint strings.
- `success_criteria`: List of validation criteria strings.
- `priority`: Objective priority (default 100).
- `metadata`: Arbitrary metadata dictionary.
- `created_at`: ISO 8601 UTC timestamp.

### `Plan`
First-class representation of a generated task graph plan:
- `plan_id`: Unique plan identifier.
- `workspace_id`: Target workspace ID.
- `objective_id`: Parent objective ID.
- `root_task_id`: Root `TaskNode` ID in `TaskGraph`.
- `version`: Plan version integer (increments on `regenerate_plan`).
- `status`: `PlanStatus` (`DRAFT`, `VALIDATED`, `ACTIVE`, `REVISED`, `ARCHIVED`, `FAILED`).
- `metadata`, `created_at`, `updated_at`.

### `PlanningLevelSpec` & `TaskSpecification`
Input specs passed to planning engines:
- `PlanningLevelSpec`: `title`, `description`, `level_type` (`ROOT`, `GROUP`, `TASK`, `SUBTASK`), `level_name` ("Phase", "Sprint", etc.), `priority`, `tasks`.
- `TaskSpecification`: `title`, `description`, `priority`, `dependencies`, `metadata`.

### `PlanningResult` (Immutable Snapshot)
Dataclass decorated with `frozen=True` returned upon completing a planning operation:
- `plan_id`, `objective_id`, `workspace_id`, `status`.
- `summary`: Dictionary of task counts and readiness status.
- `statistics`: Dictionary containing node counts, depth, and validity boolean.
- `warnings`: Tuple of warning strings.
- `validation_result`: Detailed output dictionary from `PlanValidator`.
- `plan`: Serialized plan dictionary.
