# Capability 6 — Review & Validation Engine

The Review & Validation Engine evaluates completed execution records, individual task nodes, task batches, and overall plans against defined requirements and quality criteria.

## Core Responsibilities

The Review Engine SHALL:
- Review completed task outputs and execution records.
- Evaluate execution quality against explicit or default criteria.
- Produce structured validation reports (`ReviewReport`).
- Generate deterministic review scores (0.0 to 1.0) and statuses (`PASSED`, `PARTIAL`, `FAILED`, `ERROR`, `PENDING`).
- Record review history within `TaskWorkspace.review_reports`.
- Return actionable recommendations for downstream tasks or plans.

The Review Engine SHALL NOT:
- Execute tasks.
- Schedule tasks.
- Modify task graph topology.
- Retry executions or replan objectives.
- Invoke LLM providers directly.

## Data Ownership

| Component | Owner |
| :--- | :--- |
| `ReviewResult` | `ReviewEngine` (immutable) |
| `ReviewReport` | `TaskWorkspace.review_reports` |
| Review History | `TaskWorkspace` |
| Review Criteria | `ReviewEngine` / Caller |
| Review Status | `ReviewReport` |

## Review Engine Flow

```
ExecutionEngine ──> ExecutionResult ──> ReviewEngine ──> ReviewResult ──> ReviewReport ──> Workspace Registry
```
