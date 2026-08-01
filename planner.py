"""Core implementation for Capability 5 — Intelligent Task Planner.

Includes PlanGraphBuilder, PlanValidator, PlanningEngine interface,
DeterministicPlanningEngine, PlanVisualizer, and TaskPlanner coordinator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from planner_models import (
    LevelType,
    Objective,
    Plan,
    PlanningLevelSpec,
    PlanningResult,
    PlanStatus,
    TaskSpecification,
    utc_now,
)
from task_graph import DependencyType, TaskGraph, TaskNode, TaskStatus
from scheduler import DependencyScheduler

if TYPE_CHECKING:
    from workspace import TaskWorkspace


# ----------------------------------------------------------------------
# Graph Construction Layer
# ----------------------------------------------------------------------

class PlanGraphBuilder:
    """Internal graph-building layer insulating planning strategy logic from TaskGraph mutations."""

    def __init__(self, task_graph: TaskGraph) -> None:
        self._graph = task_graph

    def build_root_task(self, objective: Objective) -> TaskNode:
        """Create and register the root task for an objective."""
        metadata = dict(objective.metadata)
        metadata.update({
            "plan_role": "ROOT_OBJECTIVE",
            "is_executable": False,
            "objective_id": objective.objective_id,
        })
        node = self._graph.create_task(
            title=objective.title,
            description=objective.description,
            metadata=metadata,
            status=TaskStatus.PENDING,
        )
        node.priority = objective.priority
        return node

    def build_level_node(
        self,
        parent_task_id: str,
        title: str,
        description: str | None = None,
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
        level_name: str = "Phase",
    ) -> TaskNode:
        """Create a structural level node under a parent task."""
        meta = dict(metadata or {})
        meta.update({
            "plan_role": "LEVEL_GROUP",
            "level_name": level_name,
            "is_executable": False,
        })
        node = self._graph.create_subtask(
            parent_task_id=parent_task_id,
            title=title,
            description=description,
            metadata=meta,
            status=TaskStatus.PENDING,
        )
        node.priority = priority
        return node

    def build_leaf_task(
        self,
        parent_task_id: str,
        title: str,
        description: str | None = None,
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
    ) -> TaskNode:
        """Create an executable leaf task node."""
        meta = dict(metadata or {})
        meta.update({
            "plan_role": "LEAF_TASK",
            "is_executable": True,
        })
        node = self._graph.create_subtask(
            parent_task_id=parent_task_id,
            title=title,
            description=description,
            metadata=meta,
            status=TaskStatus.PENDING,
        )
        node.priority = priority
        return node

    def connect_dependency(
        self,
        source_task_id: str,
        target_task_id: str,
        dependency_type: DependencyType = DependencyType.DEPENDS_ON,
    ) -> Any:
        """Add a dependency edge between source and target task nodes."""
        return self._graph.add_dependency(
            source_task_id=source_task_id,
            target_task_id=target_task_id,
            dependency_type=dependency_type,
        )


# ----------------------------------------------------------------------
# Single-Authority Validation Engine
# ----------------------------------------------------------------------

class PlanValidator:
    """Single authority for structural plan correctness and graph consistency."""

    @staticmethod
    def validate(
        plan: Plan,
        objective: Objective,
        task_graph: TaskGraph,
        workspace_objectives: dict[str, Objective] | None = None,
        workspace_plans: dict[str, Plan] | None = None,
        max_depth: int = 4,
    ) -> dict[str, Any]:
        """Validate structural integrity of the generated plan graph."""
        errors: list[str] = []
        warnings: list[str] = []
        checks: dict[str, str] = {}

        # 1. Cycle Detection
        scheduler = DependencyScheduler(task_graph)
        cycles = scheduler.detect_cycles()
        if cycles:
            errors.append(f"Dependency cycle detected in graph: {cycles}")
            checks["cycles_check"] = "FAILED"
        else:
            checks["cycles_check"] = "PASSED"

        # 2. Registry Uniqueness
        if workspace_objectives:
            matches = [o for o in workspace_objectives.values() if o.objective_id == objective.objective_id]
            if len(matches) > 1:
                errors.append(f"Duplicate Objective ID found in registry: {objective.objective_id}")
        if workspace_plans:
            matches = [p for p in workspace_plans.values() if p.plan_id == plan.plan_id]
            if len(matches) > 1:
                errors.append(f"Duplicate Plan ID found in registry: {plan.plan_id}")
        checks["uniqueness_check"] = "FAILED" if any("Duplicate" in e for e in errors) else "PASSED"

        # 3. Root Task Presence
        if plan.root_task_id not in task_graph.nodes:
            errors.append(f"Root task {plan.root_task_id} not found in task graph.")
            checks["root_check"] = "FAILED"
        else:
            checks["root_check"] = "PASSED"

        # 4. Orphan & Disconnected Task Check
        root_id = plan.root_task_id
        for tid, node in task_graph.nodes.items():
            if tid == root_id:
                continue
            if not node.parent_task_id:
                errors.append(f"Orphan task found (no parent): task_id={tid}, title='{node.title}'")
            elif node.parent_task_id not in task_graph.nodes:
                errors.append(f"Disconnected task (invalid parent_task_id={node.parent_task_id}): task_id={tid}")
        checks["orphans_check"] = "FAILED" if any("Orphan" in e or "Disconnected" in e for e in errors) else "PASSED"

        # 5. Invalid Edge Target Verification
        for edge in task_graph.edges:
            if edge.source_task_id not in task_graph.nodes:
                errors.append(f"Dependency edge source node not found: {edge.source_task_id}")
            if edge.target_task_id not in task_graph.nodes:
                errors.append(f"Dependency edge target node not found: {edge.target_task_id}")
        checks["edges_check"] = "FAILED" if any("edge" in e for e in errors) else "PASSED"

        # 6. Hierarchy Depth & Circular Parentage Check
        max_found_depth = 0
        for tid in task_graph.nodes:
            depth = 0
            curr = tid
            visited_parents: set[str] = set()
            while curr and curr in task_graph.nodes:
                if curr in visited_parents:
                    errors.append(f"Circular parent-child hierarchy detected at task_id={curr}")
                    break
                visited_parents.add(curr)
                parent_id = task_graph.nodes[curr].parent_task_id
                if parent_id:
                    depth += 1
                curr = parent_id or ""
            if depth > max_found_depth:
                max_found_depth = depth
            if depth > max_depth:
                errors.append(f"Task hierarchy depth {depth} exceeds max allowed depth {max_depth} at task_id={tid}")
        checks["depth_check"] = "FAILED" if any("depth" in e or "Circular parent" in e for e in errors) else "PASSED"

        # 7. Leaf Node Executability Check
        parent_ids = {n.parent_task_id for n in task_graph.nodes.values() if n.parent_task_id}
        for tid, node in task_graph.nodes.items():
            if tid not in parent_ids and tid != root_id:
                # Node is a leaf
                if node.metadata.get("is_executable") is not True:
                    warnings.append(f"Leaf task '{node.title}' (ID: {tid}) is not marked as executable.")
        checks["leaf_executability_check"] = "PASSED"

        is_valid = len(errors) == 0
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "max_depth_found": max_found_depth,
        }


# ----------------------------------------------------------------------
# Planning Engine Strategy Abstraction
# ----------------------------------------------------------------------

class PlanningEngine(ABC):
    """Abstract interface for planning engines."""

    @abstractmethod
    def plan(
        self,
        objective: Objective,
        levels: list[PlanningLevelSpec],
        builder: PlanGraphBuilder,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Decompose objective and level specs into TaskGraph via builder.

        Returns root_task_id string.
        """
        pass


class DeterministicPlanningEngine(PlanningEngine):
    """Default deterministic planning engine implementation."""

    def plan(
        self,
        objective: Objective,
        levels: list[PlanningLevelSpec | dict[str, Any]],
        builder: PlanGraphBuilder,
        options: dict[str, Any] | None = None,
    ) -> str:
        options = options or {}

        # Reuse existing root task if present for this objective
        root_node = None
        for node in builder._graph.nodes.values():
            if node.metadata.get("plan_role") == "ROOT_OBJECTIVE" and node.metadata.get("objective_id") == objective.objective_id:
                root_node = node
                break
        if not root_node:
            root_node = builder.build_root_task(objective)

        # Map to store task title/index to task_id for dependency resolution
        task_id_by_title: dict[str, str] = {}

        # Default phases if none provided
        if not levels:
            levels = [
                PlanningLevelSpec(
                    title="Phase 1: Discovery & Analysis",
                    level_name="Phase",
                    priority=90,
                    tasks=[
                        TaskSpecification(title="Analyze objective requirements and constraints", priority=90),
                    ],
                ),
                PlanningLevelSpec(
                    title="Phase 2: Core Implementation",
                    level_name="Phase",
                    priority=70,
                    tasks=[
                        TaskSpecification(
                            title="Execute core objective workflow",
                            priority=70,
                            dependencies=["Analyze objective requirements and constraints"],
                        ),
                    ],
                ),
                PlanningLevelSpec(
                    title="Phase 3: Verification & Output",
                    level_name="Phase",
                    priority=50,
                    tasks=[
                        TaskSpecification(
                            title="Verify outputs and finalize artifacts",
                            priority=50,
                            dependencies=["Execute core objective workflow"],
                        ),
                    ],
                ),
            ]

        prev_level_task_ids: list[str] = []

        for level_idx, lspec in enumerate(levels):
            if isinstance(lspec, dict):
                level_title = lspec.get("title", "Phase")
                level_desc = lspec.get("description")
                level_prio = lspec.get("priority", 50)
                level_name = lspec.get("level_name", "Phase")
                raw_tasks = lspec.get("tasks", [])
            else:
                level_title = lspec.title
                level_desc = lspec.description
                level_prio = lspec.priority
                level_name = lspec.level_name
                raw_tasks = lspec.tasks

            level_node = builder.build_level_node(
                parent_task_id=root_node.task_id,
                title=level_title,
                description=level_desc,
                priority=level_prio,
                level_name=level_name,
                metadata={"level_index": level_idx},
            )

            current_level_task_ids: list[str] = []

            for tspec in raw_tasks:
                if isinstance(tspec, dict):
                    t_title = tspec.get("title", "Task")
                    t_desc = tspec.get("description")
                    t_prio = tspec.get("priority", 50)
                    t_deps = tspec.get("dependencies") or tspec.get("depends_on_indices") or []
                    t_meta = tspec.get("metadata") or {}
                else:
                    t_title = tspec.title
                    t_desc = tspec.description
                    t_prio = tspec.priority
                    t_deps = tspec.dependencies
                    t_meta = tspec.metadata

                leaf_node = builder.build_leaf_task(
                    parent_task_id=level_node.task_id,
                    title=t_title,
                    description=t_desc,
                    priority=t_prio,
                    metadata=t_meta,
                )
                task_id_by_title[t_title] = leaf_node.task_id
                current_level_task_ids.append(leaf_node.task_id)

                for dep in t_deps:
                    if isinstance(dep, str) and dep in task_id_by_title:
                        target_id = task_id_by_title[dep]
                        builder.connect_dependency(
                            source_task_id=leaf_node.task_id,
                            target_task_id=target_id,
                            dependency_type=DependencyType.DEPENDS_ON,
                        )

            # Sequential phase wiring if no explicit dependencies specified for first task in subsequent level
            if prev_level_task_ids and current_level_task_ids:
                first_current_id = current_level_task_ids[0]
                builder_graph_deps = builder._graph.get_dependencies(first_current_id)
                if not builder_graph_deps:
                    builder.connect_dependency(
                        source_task_id=first_current_id,
                        target_task_id=prev_level_task_ids[-1],
                        dependency_type=DependencyType.DEPENDS_ON,
                    )

            prev_level_task_ids = current_level_task_ids

        return root_node.task_id


# ----------------------------------------------------------------------
# Read-Only Visualizer
# ----------------------------------------------------------------------

class PlanVisualizer:
    """Read-only rendering engine for plans and graph structures."""

    @staticmethod
    def visualize_text(plan: Plan, objective: Objective, graph: TaskGraph) -> str:
        """Render plan as an ASCII tree string."""
        root_id = plan.root_task_id
        if root_id not in graph.nodes:
            return f"[Plan {plan.plan_id}] Empty or invalid plan."

        root_node = graph.nodes[root_id]
        lines: list[str] = [
            f"[Plan: {plan.plan_id}] {objective.title} (Status: {plan.status.value if hasattr(plan.status, 'value') else plan.status}, v{plan.version})",
        ]

        def _append_children(parent_id: str, prefix: str) -> None:
            children = graph.get_children(parent_id)
            for idx, child in enumerate(children):
                is_last = idx == len(children) - 1
                connector = "└── " if is_last else "├── "
                child_prefix = prefix + ("    " if is_last else "│   ")

                deps = graph.get_dependencies(child.task_id)
                dep_str = f", Depends On: {', '.join(deps)}" if deps else ""
                exec_str = ", Executable: True" if child.metadata.get("is_executable") else ""
                
                role = child.metadata.get("level_name") or child.metadata.get("plan_role") or "Node"
                lines.append(f"{prefix}{connector}[{role}] {child.title} (Priority: {child.priority}, Status: {child.status.value}{exec_str}{dep_str})")
                _append_children(child.task_id, child_prefix)

        _append_children(root_id, "")
        return "\n".join(lines)

    @staticmethod
    def visualize_json(plan: Plan, objective: Objective, graph: TaskGraph) -> dict[str, Any]:
        """Render plan as a structured JSON object."""
        root_id = plan.root_task_id
        if root_id not in graph.nodes:
            return {"plan_id": plan.plan_id, "error": "Root task not found"}

        def _build_tree(node_id: str) -> dict[str, Any]:
            node = graph.nodes[node_id]
            children = graph.get_children(node_id)
            deps = graph.get_dependencies(node_id)
            return {
                "task_id": node.task_id,
                "title": node.title,
                "description": node.description,
                "status": node.status.value if hasattr(node.status, "value") else node.status,
                "priority": node.priority,
                "metadata": node.metadata,
                "dependencies": deps,
                "children": [_build_tree(c.task_id) for c in children],
            }

        return {
            "plan_id": plan.plan_id,
            "version": plan.version,
            "status": plan.status.value if hasattr(plan.status, "value") else plan.status,
            "objective": objective.to_dict(),
            "tree": _build_tree(root_id),
        }

    @staticmethod
    def visualize_mermaid(plan: Plan, objective: Objective, graph: TaskGraph) -> str:
        """Render plan as a Mermaid diagram block string."""
        lines: list[str] = ["graph TD"]
        root_id = plan.root_task_id

        # Render nodes
        for tid, node in graph.nodes.items():
            safe_title = node.title.replace('"', "'")
            lines.append(f'    {tid}["{safe_title}"]')

        # Parent-child hierarchy edges
        for tid, node in graph.nodes.items():
            if node.parent_task_id and node.parent_task_id in graph.nodes:
                lines.append(f"    {node.parent_task_id} --> {tid}")

        # Dependency edges
        for edge in graph.edges:
            lines.append(f"    {edge.source_task_id} -. DEPENDS_ON .-> {edge.target_task_id}")

        return "\n".join(lines)


# ----------------------------------------------------------------------
# TaskPlanner Coordinator
# ----------------------------------------------------------------------

class TaskPlanner:
    """Top-level coordinator for planning operations attached to TaskWorkspace."""

    def __init__(self, workspace: TaskWorkspace) -> None:
        self.workspace = workspace
        self.engine: PlanningEngine = DeterministicPlanningEngine()

    def create_objective(
        self,
        title: str,
        description: str | None = None,
        constraints: list[str] | None = None,
        success_criteria: list[str] | None = None,
        priority: int = 100,
        metadata: dict[str, Any] | None = None,
        objective_id: str | None = None,
    ) -> Objective:
        """Create and register an Objective in the workspace."""
        oid = objective_id or str(uuid4())
        obj = Objective(
            objective_id=oid,
            workspace_id=self.workspace.workspace_id,
            title=title,
            description=description,
            constraints=constraints or [],
            success_criteria=success_criteria or [],
            priority=priority,
            metadata=metadata or {},
        )
        self.workspace.objectives[oid] = obj
        return obj

    def create_plan(
        self,
        objective_input: str | dict[str, Any] | Objective,
        levels_spec: list[dict[str, Any] | PlanningLevelSpec] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PlanningResult:
        """Create, decompose, validate, and register a new plan."""
        options = options or {}
        
        # 1. Resolve or create Objective
        if isinstance(objective_input, Objective):
            objective = objective_input
            self.workspace.objectives[objective.objective_id] = objective
        elif isinstance(objective_input, dict):
            objective = self.create_objective(
                title=objective_input.get("title", "Untitled Objective"),
                description=objective_input.get("description"),
                constraints=objective_input.get("constraints"),
                success_criteria=objective_input.get("success_criteria"),
                priority=objective_input.get("priority", 100),
                metadata=objective_input.get("metadata"),
            )
        else:
            objective = self.create_objective(title=str(objective_input))

        # 2. Parse Level Specs
        parsed_levels: list[PlanningLevelSpec] = []
        if levels_spec:
            for lspec in levels_spec:
                if isinstance(lspec, PlanningLevelSpec):
                    parsed_levels.append(lspec)
                elif isinstance(lspec, dict):
                    raw_tasks = lspec.get("tasks", [])
                    tasks: list[TaskSpecification] = []
                    for t in raw_tasks:
                        if isinstance(t, TaskSpecification):
                            tasks.append(t)
                        elif isinstance(t, dict):
                            tasks.append(TaskSpecification(
                                title=t.get("title", "Untitled Task"),
                                description=t.get("description"),
                                priority=t.get("priority", 50),
                                dependencies=t.get("dependencies") or t.get("depends_on_indices") or [],
                                metadata=t.get("metadata") or {},
                            ))
                    parsed_levels.append(PlanningLevelSpec(
                        title=lspec.get("title", "Phase"),
                        description=lspec.get("description"),
                        level_type=LevelType(lspec.get("level_type", "GROUP")),
                        level_name=lspec.get("level_name", "Phase"),
                        priority=lspec.get("priority", 50),
                        tasks=tasks,
                    ))

        # 3. Instantiate Plan draft
        plan_id = str(uuid4())
        plan = Plan(
            plan_id=plan_id,
            workspace_id=self.workspace.workspace_id,
            objective_id=objective.objective_id,
            root_task_id="",  # Populated after engine run
            status=PlanStatus.DRAFT,
            metadata=dict(options),
        )
        self.workspace.plans[plan_id] = plan

        # 4. Run PlanningEngine via PlanGraphBuilder
        builder = PlanGraphBuilder(self.workspace.task_graph)
        root_task_id = self.engine.plan(
            objective=objective,
            levels=parsed_levels,
            builder=builder,
            options=options,
        )
        plan.root_task_id = root_task_id

        # 5. Run PlanValidator
        max_depth = options.get("max_depth", 4)
        validation_res = PlanValidator.validate(
            plan=plan,
            objective=objective,
            task_graph=self.workspace.task_graph,
            workspace_objectives=self.workspace.objectives,
            workspace_plans=self.workspace.plans,
            max_depth=max_depth,
        )

        if validation_res["is_valid"]:
            plan.status = PlanStatus.VALIDATED
        else:
            plan.status = PlanStatus.FAILED

        # 6. Build immutable PlanningResult
        scheduler = DependencyScheduler(self.workspace.task_graph)
        ready_tasks = scheduler.get_ready_tasks()
        total_nodes = len(self.workspace.task_graph.nodes)
        parent_ids = {n.parent_task_id for n in self.workspace.task_graph.nodes.values() if n.parent_task_id}
        leaf_nodes = [n for tid, n in self.workspace.task_graph.nodes.items() if tid not in parent_ids and tid != root_task_id]

        result = PlanningResult(
            plan_id=plan.plan_id,
            objective_id=objective.objective_id,
            workspace_id=self.workspace.workspace_id,
            status=plan.status,
            summary={
                "title": objective.title,
                "total_tasks": total_nodes,
                "root_task_id": root_task_id,
                "ready_tasks_count": len(ready_tasks),
                "execution_readiness": "READY_FOR_SCHEDULER" if plan.status == PlanStatus.VALIDATED else "NOT_READY",
            },
            statistics={
                "total_nodes": total_nodes,
                "leaf_nodes_count": len(leaf_nodes),
                "max_depth": validation_res.get("max_depth_found", 0),
                "ready_tasks": len(ready_tasks),
                "is_valid": validation_res["is_valid"],
            },
            warnings=tuple(validation_res.get("warnings", [])),
            validation_result=validation_res,
            plan=plan.to_dict(),
        )
        return result

    def expand_task(
        self,
        task_id: str,
        subtasks_spec: list[dict[str, Any] | TaskSpecification],
        plan_id: str | None = None,
    ) -> PlanningResult:
        """Dynamically expand an existing task into finer subtasks."""
        if task_id not in self.workspace.task_graph.nodes:
            raise KeyError(f"Task not found: {task_id}")

        parent_node = self.workspace.task_graph.nodes[task_id]
        if parent_node.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.RUNNING):
            raise ValueError(f"Cannot expand task in {parent_node.status} state.")

        builder = PlanGraphBuilder(self.workspace.task_graph)
        task_id_map: dict[str, str] = {}

        for st in subtasks_spec:
            if isinstance(st, TaskSpecification):
                tspec = st
            else:
                tspec = TaskSpecification(
                    title=st.get("title", "Subtask"),
                    description=st.get("description"),
                    priority=st.get("priority", parent_node.priority),
                    dependencies=st.get("dependencies") or st.get("depends_on_task_ids") or [],
                    metadata=st.get("metadata") or {},
                )

            leaf_node = builder.build_leaf_task(
                parent_task_id=task_id,
                title=tspec.title,
                description=tspec.description,
                priority=tspec.priority,
                metadata=tspec.metadata,
            )
            task_id_map[tspec.title] = leaf_node.task_id

            for dep in tspec.dependencies:
                target_id = task_id_map.get(dep) or (dep if dep in self.workspace.task_graph.nodes else None)
                if target_id:
                    builder.connect_dependency(
                        source_task_id=leaf_node.task_id,
                        target_task_id=target_id,
                        dependency_type=DependencyType.DEPENDS_ON,
                    )

        # Container parent node is no longer an executable leaf itself
        parent_node.metadata["is_executable"] = False

        target_plan = self._get_active_plan(plan_id)
        return self.get_plan(target_plan.plan_id)

    def regenerate_plan(
        self,
        plan_id: str,
        target_task_id: str | None = None,
        objective_input: str | dict[str, Any] | Objective | None = None,
        levels_spec: list[dict[str, Any] | PlanningLevelSpec] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PlanningResult:
        """Regenerate unexecuted/pending tasks in a plan without touching completed/failed nodes."""
        plan = self.workspace.plans.get(plan_id)
        if not plan:
            raise KeyError(f"Plan not found: {plan_id}")

        # Conservative check: collect tasks that cannot be removed
        non_removable = {
            tid for tid, node in self.workspace.task_graph.nodes.items()
            if node.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.RUNNING)
        }

        # Remove only PENDING tasks that are not completed/failed
        pending_ids = [
            tid for tid, node in self.workspace.task_graph.nodes.items()
            if node.status == TaskStatus.PENDING and tid not in non_removable and tid != plan.root_task_id
        ]

        for tid in pending_ids:
            # Remove node from graph safely
            if tid in self.workspace.task_graph.nodes:
                del self.workspace.task_graph.nodes[tid]

        # Clean edges involving removed nodes
        self.workspace.task_graph.edges = [
            edge for edge in self.workspace.task_graph.edges
            if edge.source_task_id in self.workspace.task_graph.nodes
            and edge.target_task_id in self.workspace.task_graph.nodes
        ]

        # Increment plan version
        plan.version += 1
        plan.updated_at = utc_now()
        plan.status = PlanStatus.REVISED

        # If new levels provided, build them under root
        if levels_spec:
            obj = self.workspace.objectives.get(plan.objective_id)
            if obj:
                builder = PlanGraphBuilder(self.workspace.task_graph)
                self.engine.plan(
                    objective=obj,
                    levels=[ls if isinstance(ls, PlanningLevelSpec) else PlanningLevelSpec(**ls) for ls in levels_spec],
                    builder=builder,
                    options=options,
                )

        return self.get_plan(plan.plan_id)

    def get_plan(self, plan_id: str | None = None) -> PlanningResult:
        """Return PlanningResult snapshot for target or latest plan."""
        plan = self._get_active_plan(plan_id)
        objective = self.workspace.objectives.get(plan.objective_id)
        if not objective:
            objective = Objective(
                objective_id=plan.objective_id,
                workspace_id=self.workspace.workspace_id,
                title="Workspace Objective",
            )

        validation_res = PlanValidator.validate(
            plan=plan,
            objective=objective,
            task_graph=self.workspace.task_graph,
            workspace_objectives=self.workspace.objectives,
            workspace_plans=self.workspace.plans,
        )

        scheduler = DependencyScheduler(self.workspace.task_graph)
        ready_tasks = scheduler.get_ready_tasks()
        total_nodes = len(self.workspace.task_graph.nodes)
        parent_ids = {n.parent_task_id for n in self.workspace.task_graph.nodes.values() if n.parent_task_id}
        leaf_nodes = [n for tid, n in self.workspace.task_graph.nodes.items() if tid not in parent_ids and tid != plan.root_task_id]

        return PlanningResult(
            plan_id=plan.plan_id,
            objective_id=objective.objective_id,
            workspace_id=self.workspace.workspace_id,
            status=plan.status,
            summary={
                "title": objective.title,
                "total_tasks": total_nodes,
                "root_task_id": plan.root_task_id,
                "ready_tasks_count": len(ready_tasks),
                "execution_readiness": "READY_FOR_SCHEDULER" if plan.status == PlanStatus.VALIDATED else "NOT_READY",
            },
            statistics={
                "total_nodes": total_nodes,
                "leaf_nodes_count": len(leaf_nodes),
                "max_depth": validation_res.get("max_depth_found", 0),
                "ready_tasks": len(ready_tasks),
                "is_valid": validation_res["is_valid"],
            },
            warnings=tuple(validation_res.get("warnings", [])),
            validation_result=validation_res,
            plan=plan.to_dict(),
        )

    def list_plans(self) -> list[dict[str, Any]]:
        """List all plans registered in workspace."""
        return [p.to_dict() for p in self.workspace.plans.values()]

    def visualize_plan(self, plan_id: str | None = None, format: str = "text") -> str:
        """Render visual representation of target plan."""
        plan = self._get_active_plan(plan_id)
        objective = self.workspace.objectives.get(plan.objective_id) or Objective(
            objective_id=plan.objective_id,
            workspace_id=self.workspace.workspace_id,
            title="Workspace Objective",
        )

        fmt = format.lower()
        if fmt == "json":
            import json
            return json.dumps(PlanVisualizer.visualize_json(plan, objective, self.workspace.task_graph), indent=2)
        elif fmt == "mermaid":
            return PlanVisualizer.visualize_mermaid(plan, objective, self.workspace.task_graph)
        else:
            return PlanVisualizer.visualize_text(plan, objective, self.workspace.task_graph)

    def _get_active_plan(self, plan_id: str | None = None) -> Plan:
        if plan_id:
            plan = self.workspace.plans.get(plan_id)
            if not plan:
                raise KeyError(f"Plan not found: {plan_id}")
            return plan
        if not self.workspace.plans:
            # Return dummy fallback if no plans registered
            return Plan(
                plan_id="plan-none",
                workspace_id=self.workspace.workspace_id,
                objective_id="obj-none",
                root_task_id="",
                status=PlanStatus.DRAFT,
            )
        # Return most recently updated plan
        return max(self.workspace.plans.values(), key=lambda p: p.updated_at)
