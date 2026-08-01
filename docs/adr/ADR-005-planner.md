# ADR-005: Non-Executing Intelligent Task Planner with Strategy Pattern

## Context
High-level user objectives must be decomposed into structured task graphs with generic levels, dependencies, and priorities. Planning strategies may vary (e.g. deterministic level specifications vs. future LLM-based decomposition).

## Decision
We decided to implement `TaskPlanner` ([planner.py](file:///c:/Users/user/AI-Orchestrator/planner.py)) using the Strategy Pattern via an abstract `PlanningEngine` base class and a reference `DeterministicPlanningEngine` implementation.

Key aspects:
- **Planning NEVER executes.** Plans are created with tasks in `PENDING` status.
- `PlanGraphBuilder` insulates strategy implementations from direct `TaskGraph` dictionary mutations.
- `PlanValidator` acts as a mandatory validation boundary before plans are marked `VALIDATED`.
- Re-planning (`regenerate_plan`) is conservative, leaving `COMPLETED`, `FAILED`, and `RUNNING` tasks untouched.

## Consequences
### Positive
- **Pluggable Strategies**: Future LLM-driven planning engines can be added by implementing `PlanningEngine.plan(...)`.
- **Safe Decomposition**: Guarantees that planning errors cannot trigger unintended side effects or model execution calls.
- **State Preservation**: Re-planning preserves historical execution history.

### Negative
- Requires multi-step pipeline (Objective -> Builder -> Engine -> Validator -> Result).

## Alternatives Considered
- **Direct Execution Planning**: Having the planner execute tasks as it decomposes them. Rejected because it violates the rule that Planning NEVER executes.
- **Monolithic Planner Function**: Writing a single monolithic function. Rejected because it prevents strategy switching and clean graph validation.
