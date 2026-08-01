# ADR-001: Explicit TaskWorkspace State Ownership

## Context
AI-Orchestrator manages multi-step execution workflows involving task graphs, schedulers, execution indices, artifact stores, execution engines, and task planners. In early designs or traditional frameworks, runtime states (e.g. active graphs, task stores) are often stored in global singletons or ambient module-level variables, creating hidden state dependencies, multi-thread collisions, and difficulty isolating test environments.

## Decision
We decided that `TaskWorkspace` ([workspace.py](file:///c:/Users/user/AI-Orchestrator/workspace.py)) is the sole, explicit owner of all runtime state for a given workspace. 

Specifically:
- Each `TaskWorkspace` instance directly owns its own `TaskGraph`, `DependencyScheduler`, `TaskExecutionIndex`, `ArtifactStore`, `ExecutionEngine`, `TaskPlanner`, `objectives`, `plans`, and `executions` log list.
- A thread-safe process-local registry (`WorkspaceStore`) holds workspaces by `workspace_id`.
- Child components do not instantiate global state; they reference their parent `TaskWorkspace` or `TaskGraph`.

## Consequences
### Positive
- **Clear Data Ownership**: Complete transparency regarding where state lives.
- **Test Isolation**: Tests can create lightweight, independent workspaces without cross-test leakage.
- **Multi-Tenant Preparedness**: Multiple workspaces can coexist concurrently in memory without interfering with each other.

### Negative
- Require passing `workspace_id` explicitly across API calls and MCP schemas.

## Alternatives Considered
- **Global Module State**: Storing single graph and execution lists in global variables. Rejected due to inability to support isolated workspaces and clean unit testing.
- **Service Locator Pattern**: Using a central service locator registry for components. Rejected because it obscures dependencies and introduces global state.
