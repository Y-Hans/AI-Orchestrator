# ADR-008: Mandatory Single-Authority Pre-Scheduling Validation Boundary

## Context
Generated task plans can contain structural flaws such as circular dependencies, orphan tasks, invalid parent references, duplicate identifiers, or excessive hierarchy depth. Scheduling or executing invalid graphs causes runtime deadlocks, infinite loops, or orphaned task states.

## Decision
We decided to implement `PlanValidator` ([planner.py](file:///c:/Users/user/AI-Orchestrator/planner.py)) as the single authority for plan graph validation. Validation is executed mandatorily before any plan transitions to `PlanStatus.VALIDATED`.

The 7-step validation process includes:
1. **Cycle Detection**: Calls `DependencyScheduler.detect_cycles()`.
2. **Registry Uniqueness**: Verifies Objective and Plan IDs.
3. **Root Task Verification**: Confirms presence of root task.
4. **Orphan & Disconnected Node Detection**: Verifies valid parent task IDs.
5. **Edge Target Verification**: Ensures edge source and target existence.
6. **Hierarchy Depth & Circular Parentage Check**: Validates max depth limit.
7. **Leaf Node Executability Verification**: Asserts leaf node readiness.

## Consequences
### Positive
- **Guaranteed Graph Integrity**: Schedulers and engines only operate on validated, acyclic task graphs.
- **Single Authority**: Centralized validation rules prevent fragmented check logic across components.
- **Detailed Diagnostic Reporting**: Returns comprehensive error and warning lists in `PlanningResult`.

### Negative
- Adds a small computational validation step upon plan creation (typically <1ms).

## Alternatives Considered
- **Ad-Hoc Runtime Checks**: Checking dependencies on-the-fly during execution. Rejected because invalid graphs could be partially executed before discovering errors.
- **Post-Scheduling Validation**: Validating during execution queue polling. Rejected because validation must occur before scheduling or execution begins.
