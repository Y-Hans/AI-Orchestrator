# Overall System Architecture Diagram

```mermaid
flowchart TD
    subgraph External System
        Client["Antigravity CLI / User Application"]
    end

    subgraph Interface Boundary
        MCP["MCP Server (ai_orchestrator_mcp.py)<br/>26 MCP Tools"]
        Brain["AntigravityBrain (brain.py)<br/>Execution Facade"]
    end

    subgraph Data Owner Container
        WorkspaceStore["WorkspaceStore<br/>(Process-Local Registry)"]
        TaskWorkspace["TaskWorkspace (workspace.py)<br/>Explicit State Owner"]
    end

    subgraph Core Components
        Planner["TaskPlanner (planner.py)<br/>Capability 5"]
        GraphBuilder["PlanGraphBuilder"]
        Validator["PlanValidator"]
        Scheduler["DependencyScheduler (scheduler.py)<br/>Capability 4"]
        Engine["ExecutionEngine (execution_engine.py)<br/>Capability 3"]
    end

    subgraph Domain Models & Stores
        TaskGraph["TaskGraph (task_graph.py)<br/>Capability 1"]
        ExecIndex["TaskExecutionIndex (execution_binding.py)<br/>Capability 2"]
        ArtifactStore["ArtifactStore (artifact_store.py)<br/>Capability 3"]
        ExecStore["Executions Log List<br/>Capability 2"]
    end

    subgraph Injected Infrastructure
        Executor["Injected Executor Callable"]
        Providers["Model Providers<br/>(Gemini / Groq / OpenRouter / Ollama)"]
    end

    Client -->|JSON-RPC 2.0| MCP
    MCP -->|Facade Calls| Brain
    Brain -->|Get/List| WorkspaceStore
    WorkspaceStore -->|Owns| TaskWorkspace
    
    TaskWorkspace *-- Planner
    TaskWorkspace *-- Scheduler
    TaskWorkspace *-- Engine
    TaskWorkspace *-- TaskGraph
    TaskWorkspace *-- ExecIndex
    TaskWorkspace *-- ArtifactStore
    TaskWorkspace *-- ExecStore

    Brain -->|create_plan / get_plan| Planner
    Planner --> GraphBuilder
    GraphBuilder -->|builds nodes/edges| TaskGraph
    Planner --> Validator
    Validator -->|validates structure| TaskGraph
    Validator -->|checks cycles| Scheduler

    Brain -->|verify readiness| Scheduler
    Scheduler -->|queries nodes & edges| TaskGraph

    Brain -->|execute_task| Engine
    Engine -->|start/complete/fail| TaskGraph
    Engine -->|bind_execution| ExecIndex
    Engine -->|append record| ExecStore
    Engine -->|invokes| Executor
    Executor -->|HTTP / API| Providers
```
