"""Antigravity Brain facade for execution services.

The Brain is the stable interface between Antigravity and the execution layer.
It does not route, choose providers, orchestrate tasks, or duplicate provider
logic. Antigravity remains responsible for selecting the provider and model.

Future capabilities may be added behind this interface without changing
external callers. Possible future responsibilities are documented only:
think, delegate, review, merge, reflect.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from uuid import uuid4

from execution_result import ExecutionResult
from workspace import ExecutionRecord, utc_now, workspace_store



class AntigravityBrain:
    """Minimal entry point for Antigravity execution requests."""

    def __init__(self, execute_model: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._execute_model = execute_model

    # ------------------------------------------------------------------
    # Provider-level execution (existing API – unchanged)
    # ------------------------------------------------------------------

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Delegate execution to the existing provider execution implementation."""
        started = time.perf_counter()
        started_at = utc_now()
        payload = None
        try:
            payload = self._execute_model(arguments)
            return payload
        except Exception as exc:
            payload = {
                "ok": False,
                "provider": arguments.get("provider", ""),
                "model": arguments.get("model"),
                "error": exc.__class__.__name__,
                "detail": str(exc),
            }
            raise
        finally:
            workspace_id = arguments.get("workspace_id")
            task_id = arguments.get("task_id")
            execution_type = arguments.get("execution_type")
            if workspace_id:
                completed_at = utc_now()
                latency_ms = int((time.perf_counter() - started) * 1000)
                self._record_execution(
                    str(workspace_id),
                    arguments,
                    payload,
                    started_at,
                    completed_at,
                    latency_ms,
                    task_id=task_id,
                    execution_type=execution_type,
                )

    def execute_many(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute exactly the requested model calls, sequentially or concurrently."""
        requests = arguments.get("requests")
        if not isinstance(requests, list) or not requests:
            raise ValueError("requests must be a non-empty list.")

        run_parallel = bool(arguments.get("parallel", False))
        workspace_id = arguments.get("workspace_id")
        task_id = arguments.get("task_id")
        execution_type = arguments.get("execution_type")
        if run_parallel:
            with ThreadPoolExecutor(max_workers=len(requests)) as executor:
                results = list(
                    executor.map(
                        lambda request: self._execute_one(
                            request, workspace_id, task_id, execution_type
                        ),
                        requests,
                    )
                )
        else:
            results = [
                self._execute_one(request, workspace_id, task_id, execution_type)
                for request in requests
            ]

        return {"results": results}

    def _execute_one(
        self,
        request: Any,
        workspace_id: Any = None,
        task_id: Any = None,
        execution_type: Any = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        started_at = utc_now()
        provider = ""

        try:
            if not isinstance(request, dict):
                raise ValueError("Each request must be an object.")
            provider = str(request.get("provider", "")).lower()

            effective_workspace_id = request.get("workspace_id") or workspace_id
            effective_task_id = request.get("task_id") or task_id
            effective_execution_type = request.get("execution_type") or execution_type

            payload = self._execute_model(request)
            latency_ms = int((time.perf_counter() - started) * 1000)

            if payload.get("ok") is True:
                result = {
                    "provider": payload.get("provider", provider),
                    "model": payload.get("model"),
                    "success": True,
                    "response": payload.get("text", ""),
                    "latency_ms": latency_ms,
                }
                self._record_execution(
                    str(effective_workspace_id),
                    request,
                    result,
                    started_at,
                    utc_now(),
                    latency_ms,
                    task_id=effective_task_id,
                    execution_type=effective_execution_type,
                )
                return result

            result = {
                "provider": payload.get("provider", provider),
                "model": payload.get("model"),
                "success": False,
                "error": {
                    "code": payload.get("error", "execution_failed"),
                    "message": payload.get("detail", ""),
                },
                "latency_ms": latency_ms,
            }
            self._record_execution(
                str(effective_workspace_id),
                request,
                result,
                started_at,
                utc_now(),
                latency_ms,
                task_id=effective_task_id,
                execution_type=effective_execution_type,
            )
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = {
                "provider": provider,
                "success": False,
                "error": {"code": exc.__class__.__name__, "message": str(exc)},
                "latency_ms": latency_ms,
            }
            self._record_execution(
                str(effective_workspace_id),
                request,
                result,
                started_at,
                utc_now(),
                latency_ms,
                task_id=effective_task_id,
                execution_type=effective_execution_type,
            )
            return result

    def _record_execution(
        self,
        workspace_id: str,
        request: Any,
        payload: dict[str, Any] | None,
        started_at: str,
        completed_at: str,
        latency_ms: int,
        task_id: str | None = None,
        execution_type: str | None = None,
    ) -> None:
        if not workspace_id or workspace_id == "None":
            return

        if isinstance(request, dict):
            prompt = request.get("prompt")
            if prompt is None and "messages" in request:
                prompt = str(request["messages"])
            provider = str(request.get("provider", ""))
            requested_model = request.get("model")
        else:
            prompt = ""
            provider = ""
            requested_model = None

        payload = payload or {}
        success = payload.get("success", payload.get("ok", False)) is True
        response = payload.get("response", payload.get("text"))
        error = payload.get("error")
        model = payload.get("model", requested_model)
        record = ExecutionRecord(
            execution_id=str(uuid4()),
            provider=str(payload.get("provider", provider)),
            model=str(model) if model is not None else None,
            prompt=str(prompt or ""),
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            success=success,
            response=response,
            error=error,
        )
        workspace_store.add_execution(workspace_id, record)

        if task_id:
            try:
                workspace = workspace_store.get_workspace(workspace_id)
                etype = execution_type or "PRIMARY"
                workspace.task_execution_index.bind_execution(
                    task_id=str(task_id),
                    execution_id=record.execution_id,
                    execution_type=etype,
                )
            except KeyError:
                pass

    # ------------------------------------------------------------------
    # Task-level execution (Capability 3)
    # ------------------------------------------------------------------

    def execute_task(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single task via the workspace's ExecutionEngine.

        Required keys in *arguments*:
          - ``workspace_id`` – target workspace
          - ``task_id`` – task to execute
          - All provider arguments forwarded to ``execute_model``

        Optional keys:
          - ``execution_type`` – binding type (default PRIMARY)
        """
        workspace_id = str(arguments.get("workspace_id") or "")
        task_id = str(arguments.get("task_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for execute_task.")
        if not task_id:
            raise ValueError("task_id is required for execute_task.")

        workspace = workspace_store.get_workspace(workspace_id)

        # Scheduler verification: task must be ready and unblocked
        if workspace.scheduler.is_task_blocked(task_id):
            raise ValueError(f"Task {task_id} is blocked by uncompleted dependencies.")
        if not workspace.scheduler.can_execute(task_id):
            raise ValueError(f"Task {task_id} is not ready for execution.")

        workspace.configure_executor(self._build_executor())

        execution_type = arguments.get("execution_type", "PRIMARY")
        return workspace.execution_engine.execute_task(
            task_id=task_id,
            arguments=arguments,
            execution_type=execution_type,
        )

    def execute_tasks(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute multiple tasks via the workspace's ExecutionEngine.

        Required keys in *arguments*:
          - ``workspace_id`` – target workspace
          - ``tasks`` – list of objects each with ``task_id`` and provider args

        Optional keys:
          - ``parallel`` – whether to run concurrently (default False)
          - ``execution_type`` – binding type applied to all (default PRIMARY)
        """
        workspace_id = str(arguments.get("workspace_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for execute_tasks.")

        tasks = arguments.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise ValueError("tasks must be a non-empty list.")

        workspace = workspace_store.get_workspace(workspace_id)

        # Scheduler verification for each task in batch
        for t in tasks:
            tid = str(t.get("task_id", ""))
            if workspace.scheduler.is_task_blocked(tid):
                raise ValueError(f"Task {tid} is blocked by uncompleted dependencies.")
            if not workspace.scheduler.can_execute(tid):
                raise ValueError(f"Task {tid} is not ready for execution.")

        workspace.configure_executor(self._build_executor())

        task_ids = [str(t.get("task_id", "")) for t in tasks]
        args_list = [dict(t) for t in tasks]
        parallel = bool(arguments.get("parallel", False))
        execution_type = arguments.get("execution_type", "PRIMARY")

        return workspace.execution_engine.execute_tasks(
            task_ids=task_ids,
            arguments_list=args_list,
            execution_type=execution_type,
            parallel=parallel,
        )

    # ------------------------------------------------------------------
    # Scheduler State Queries (Capability 4)
    # ------------------------------------------------------------------

    def get_ready_tasks(self, workspace_id: str) -> dict[str, Any]:
        """Return tasks that are ready for immediate execution in the workspace."""
        workspace = workspace_store.get_workspace(workspace_id)
        ready = workspace.scheduler.get_ready_tasks()
        return {
            "workspace_id": workspace_id,
            "ready_tasks": [node.to_dict() for node in ready],
        }

    def get_blocked_tasks(self, workspace_id: str) -> dict[str, Any]:
        """Return tasks that are blocked by uncompleted dependencies or cycles."""
        workspace = workspace_store.get_workspace(workspace_id)
        blocked = workspace.scheduler.get_blocked_tasks()
        return {
            "workspace_id": workspace_id,
            "blocked_tasks": [node.to_dict() for node in blocked],
        }

    def get_execution_queue(self, workspace_id: str) -> dict[str, Any]:
        """Return ordered execution queue of tasks in topological order."""
        workspace = workspace_store.get_workspace(workspace_id)
        queue = workspace.scheduler.get_execution_queue()
        return {
            "workspace_id": workspace_id,
            "execution_queue": [node.to_dict() for node in queue],
        }

    def get_scheduler_state(self, workspace_id: str) -> dict[str, Any]:
        """Return the complete dependency scheduler state for the workspace."""
        workspace = workspace_store.get_workspace(workspace_id)
        return workspace.scheduler.get_scheduler_state()

    # ------------------------------------------------------------------
    # Planner Methods (Capability 5)
    # ------------------------------------------------------------------

    def create_plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Decompose an objective into a structured, validated Task Graph."""
        workspace_id = str(arguments.get("workspace_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for create_plan.")
        objective = arguments.get("objective")
        if not objective:
            raise ValueError("objective is required for create_plan.")
        workspace = workspace_store.get_workspace(workspace_id)
        levels = arguments.get("levels") or arguments.get("phases")
        options = arguments.get("options") or {}
        res = workspace.planner.create_plan(
            objective_input=objective,
            levels_spec=levels,
            options=options,
        )
        return res.to_dict()

    def expand_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Expand an existing task into finer subtasks."""
        workspace_id = str(arguments.get("workspace_id") or "")
        task_id = str(arguments.get("task_id") or "")
        subtasks = arguments.get("subtasks")
        if not workspace_id:
            raise ValueError("workspace_id is required for expand_task.")
        if not task_id:
            raise ValueError("task_id is required for expand_task.")
        if not isinstance(subtasks, list) or not subtasks:
            raise ValueError("subtasks must be a non-empty list.")
        workspace = workspace_store.get_workspace(workspace_id)
        plan_id = arguments.get("plan_id")
        res = workspace.planner.expand_task(
            task_id=task_id,
            subtasks_spec=subtasks,
            plan_id=plan_id,
        )
        return res.to_dict()

    def regenerate_plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Regenerate unexecuted/pending tasks in a plan without touching completed nodes."""
        workspace_id = str(arguments.get("workspace_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for regenerate_plan.")
        plan_id = str(arguments.get("plan_id") or "")
        workspace = workspace_store.get_workspace(workspace_id)
        res = workspace.planner.regenerate_plan(
            plan_id=plan_id,
            target_task_id=arguments.get("target_task_id"),
            objective_input=arguments.get("objective"),
            levels_spec=arguments.get("levels") or arguments.get("phases"),
            options=arguments.get("options"),
        )
        return res.to_dict()

    def get_plan(self, workspace_id: str, plan_id: str | None = None) -> dict[str, Any]:
        """Return PlanningResult snapshot for workspace plan."""
        workspace = workspace_store.get_workspace(workspace_id)
        res = workspace.planner.get_plan(plan_id=plan_id)
        return res.to_dict()

    def visualize_plan(self, workspace_id: str, plan_id: str | None = None, format: str = "text") -> dict[str, Any]:
        """Render visual representation of target plan."""
        workspace = workspace_store.get_workspace(workspace_id)
        rendered = workspace.planner.visualize_plan(plan_id=plan_id, format=format)
        return {
            "workspace_id": workspace_id,
            "plan_id": plan_id,
            "format": format,
            "visualization": rendered,
        }

    # ------------------------------------------------------------------
    # Review & Validation Engine Methods (Capability 6)
    # ------------------------------------------------------------------

    def review_execution(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a completed execution record against criteria."""
        workspace_id = str(arguments.get("workspace_id") or "")
        execution_id = str(arguments.get("execution_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for review_execution.")
        if not execution_id:
            raise ValueError("execution_id is required for review_execution.")
        workspace = workspace_store.get_workspace(workspace_id)
        criteria = arguments.get("criteria")
        metadata = arguments.get("metadata")
        report = workspace.review_engine.review_execution(
            execution_id=execution_id,
            criteria=criteria,
            metadata=metadata,
        )
        return report.to_dict()

    def review_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a task node and its bound executions."""
        workspace_id = str(arguments.get("workspace_id") or "")
        task_id = str(arguments.get("task_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for review_task.")
        if not task_id:
            raise ValueError("task_id is required for review_task.")
        workspace = workspace_store.get_workspace(workspace_id)
        criteria = arguments.get("criteria")
        metadata = arguments.get("metadata")
        report = workspace.review_engine.review_task(
            task_id=task_id,
            criteria=criteria,
            metadata=metadata,
        )
        return report.to_dict()

    def review_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Evaluate multiple tasks sequentially."""
        workspace_id = str(arguments.get("workspace_id") or "")
        task_ids = arguments.get("task_ids") or arguments.get("tasks")
        if not workspace_id:
            raise ValueError("workspace_id is required for review_tasks.")
        if not isinstance(task_ids, list) or not task_ids:
            raise ValueError("task_ids must be a non-empty list.")
        workspace = workspace_store.get_workspace(workspace_id)
        criteria = arguments.get("criteria")
        metadata = arguments.get("metadata")
        reports = workspace.review_engine.review_tasks(
            task_ids=[str(tid.get("task_id") if isinstance(tid, dict) else tid) for tid in task_ids],
            criteria=criteria,
            metadata=metadata,
        )
        return {
            "workspace_id": workspace_id,
            "reports": [r.to_dict() for r in reports],
        }

    def review_plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Evaluate an entire plan and all associated task outputs."""
        workspace_id = str(arguments.get("workspace_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for review_plan.")
        workspace = workspace_store.get_workspace(workspace_id)
        plan_id = arguments.get("plan_id")
        criteria = arguments.get("criteria")
        metadata = arguments.get("metadata")
        report = workspace.review_engine.review_plan(
            plan_id=str(plan_id) if plan_id else None,
            criteria=criteria,
            metadata=metadata,
        )
        return report.to_dict()

    def get_review(self, workspace_id: str, report_id: str) -> dict[str, Any]:
        """Retrieve a stored review report by report_id."""
        workspace = workspace_store.get_workspace(workspace_id)
        report = workspace.review_engine.get_review(report_id)
        return report.to_dict()

    def list_reviews(self, workspace_id: str) -> dict[str, Any]:
        """List all review reports for a workspace."""
        workspace = workspace_store.get_workspace(workspace_id)
        reports = workspace.review_engine.list_reviews()
        return {
            "workspace_id": workspace_id,
            "reviews": [r.to_dict() for r in reports],
        }

    # ------------------------------------------------------------------
    # Long-Term Memory Engine Methods (Capability 7)
    # ------------------------------------------------------------------

    def store_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Store a new memory record in the workspace's MemoryEngine."""
        workspace_id = str(arguments.get("workspace_id") or "")
        title = str(arguments.get("title") or "")
        content = arguments.get("content")
        if not workspace_id:
            raise ValueError("workspace_id is required for store_memory.")
        if not title:
            raise ValueError("title is required for store_memory.")
        if content is None:
            raise ValueError("content is required for store_memory.")

        workspace = workspace_store.get_workspace(workspace_id)
        record = workspace.memory_engine.store_memory(
            title=title,
            content=content,
            memory_type=arguments.get("memory_type", "NOTE"),
            workspace_id=workspace_id,
            description=arguments.get("description"),
            metadata=arguments.get("metadata"),
            tags=arguments.get("tags"),
        )
        return record.to_dict()

    def retrieve_memory(self, workspace_id: str | dict[str, Any], memory_id: str | None = None) -> dict[str, Any]:
        """Retrieve a stored memory record by workspace_id and memory_id."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            mem_id = str(args.get("memory_id") or "")
        else:
            ws_id = str(workspace_id or "")
            mem_id = str(memory_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for retrieve_memory.")
        if not mem_id:
            raise ValueError("memory_id is required for retrieve_memory.")

        workspace = workspace_store.get_workspace(ws_id)
        record = workspace.memory_engine.retrieve_memory(mem_id)
        return record.to_dict()

    def search_memories(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Search memory records deterministically within a workspace."""
        workspace_id = str(arguments.get("workspace_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for search_memories.")
        workspace = workspace_store.get_workspace(workspace_id)
        result = workspace.memory_engine.search_memories(
            text=arguments.get("text"),
            memory_types=arguments.get("memory_types"),
            tags=arguments.get("tags"),
            limit=arguments.get("limit"),
            workspace_id=workspace_id,
        )
        return result.to_dict()

    def list_memories(
        self,
        workspace_id: str | dict[str, Any],
        memory_type: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List stored memory records for a workspace."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            mtype = args.get("memory_type")
            mstat = args.get("status")
        else:
            ws_id = str(workspace_id or "")
            mtype = memory_type
            mstat = status

        if not ws_id:
            raise ValueError("workspace_id is required for list_memories.")

        workspace = workspace_store.get_workspace(ws_id)
        records = workspace.memory_engine.list_memories(
            workspace_id=ws_id,
            memory_type=mtype,
            status=mstat,
        )
        return {
            "workspace_id": ws_id,
            "memories": [r.to_dict() for r in records],
        }

    def delete_memory(self, workspace_id: str | dict[str, Any], memory_id: str | None = None) -> dict[str, Any]:
        """Mark a memory record as DELETED in the workspace's MemoryEngine."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            mem_id = str(args.get("memory_id") or "")
        else:
            ws_id = str(workspace_id or "")
            mem_id = str(memory_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for delete_memory.")
        if not mem_id:
            raise ValueError("memory_id is required for delete_memory.")

        workspace = workspace_store.get_workspace(ws_id)
        record = workspace.memory_engine.delete_memory(mem_id)
        return record.to_dict()

    def archive_memory(self, workspace_id: str | dict[str, Any], memory_id: str | None = None) -> dict[str, Any]:
        """Mark a memory record as ARCHIVED in the workspace's MemoryEngine."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            mem_id = str(args.get("memory_id") or "")
        else:
            ws_id = str(workspace_id or "")
            mem_id = str(memory_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for archive_memory.")
        if not mem_id:
            raise ValueError("memory_id is required for archive_memory.")

        workspace = workspace_store.get_workspace(ws_id)
        record = workspace.memory_engine.archive_memory(mem_id)
        return record.to_dict()

    def summarize_memories(self, workspace_id: str | dict[str, Any]) -> dict[str, Any]:
        """Summarize stored memory metrics for a workspace."""
        if isinstance(workspace_id, dict):
            ws_id = str(workspace_id.get("workspace_id") or "")
        else:
            ws_id = str(workspace_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for summarize_memories.")

        workspace = workspace_store.get_workspace(ws_id)
        summary = workspace.memory_engine.summarize(workspace_id=ws_id)
        res = summary.to_dict()
        res["workspace_id"] = ws_id
        return res

    # ------------------------------------------------------------------
    # Result Synthesis Engine Methods (Capability 8)
    # ------------------------------------------------------------------

    def synthesize(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Synthesize outputs from explicit parameters or source lists."""
        workspace_id = str(arguments.get("workspace_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for synthesize.")
        title = str(arguments.get("title") or "")
        if not title:
            raise ValueError("title is required for synthesize.")

        workspace = workspace_store.get_workspace(workspace_id)
        report = workspace.synthesis_engine.synthesize(
            title=title,
            source_ids=arguments.get("source_ids"),
            task_id=arguments.get("task_id"),
            plan_id=arguments.get("plan_id"),
            execution_ids=arguments.get("execution_ids"),
            review_ids=arguments.get("review_ids"),
            artifact_ids=arguments.get("artifact_ids"),
            memory_ids=arguments.get("memory_ids"),
            metadata=arguments.get("metadata"),
        )
        return report.to_dict()

    def synthesize_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Synthesize execution outputs, reviews, and artifacts for a single task."""
        workspace_id = str(arguments.get("workspace_id") or "")
        task_id = str(arguments.get("task_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for synthesize_task.")
        if not task_id:
            raise ValueError("task_id is required for synthesize_task.")

        workspace = workspace_store.get_workspace(workspace_id)
        report = workspace.synthesis_engine.synthesize_task(
            task_id=task_id,
            title=arguments.get("title"),
            metadata=arguments.get("metadata"),
            include_reviews=arguments.get("include_reviews", True),
            include_artifacts=arguments.get("include_artifacts", True),
            include_memories=arguments.get("include_memories", False),
        )
        return report.to_dict()

    def synthesize_plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Synthesize execution outputs, reviews, and artifacts across an entire plan."""
        workspace_id = str(arguments.get("workspace_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for synthesize_plan.")

        workspace = workspace_store.get_workspace(workspace_id)
        report = workspace.synthesis_engine.synthesize_plan(
            plan_id=arguments.get("plan_id"),
            title=arguments.get("title"),
            metadata=arguments.get("metadata"),
            include_reviews=arguments.get("include_reviews", True),
            include_artifacts=arguments.get("include_artifacts", True),
            include_memories=arguments.get("include_memories", False),
        )
        return report.to_dict()

    def get_synthesis(self, workspace_id: str | dict[str, Any], report_id: str | None = None) -> dict[str, Any]:
        """Retrieve a stored synthesis report by report_id."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            rep_id = str(args.get("report_id") or "")
        else:
            ws_id = str(workspace_id or "")
            rep_id = str(report_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for get_synthesis.")
        if not rep_id:
            raise ValueError("report_id is required for get_synthesis.")

        workspace = workspace_store.get_workspace(ws_id)
        report = workspace.synthesis_engine.get_synthesis(rep_id)
        return report.to_dict()

    def list_syntheses(self, workspace_id: str | dict[str, Any]) -> dict[str, Any]:
        """List all synthesis reports for a workspace."""
        if isinstance(workspace_id, dict):
            ws_id = str(workspace_id.get("workspace_id") or "")
        else:
            ws_id = str(workspace_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for list_syntheses.")

        workspace = workspace_store.get_workspace(ws_id)
        reports = workspace.synthesis_engine.list_syntheses()
        return {
            "workspace_id": ws_id,
            "syntheses": [r.to_dict() for r in reports],
        }

    def delete_synthesis(self, workspace_id: str | dict[str, Any], report_id: str | None = None) -> dict[str, Any]:
        """Delete a stored synthesis report from a workspace."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            rep_id = str(args.get("report_id") or "")
        else:
            ws_id = str(workspace_id or "")
            rep_id = str(report_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for delete_synthesis.")
        if not rep_id:
            raise ValueError("report_id is required for delete_synthesis.")

        workspace = workspace_store.get_workspace(ws_id)
        report = workspace.synthesis_engine.delete_synthesis(rep_id)
        return report.to_dict()

    # ------------------------------------------------------------------
    # Multi-Agent Collaboration Framework Methods (Capability 9)
    # ------------------------------------------------------------------

    def register_agent(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Register a new agent in the workspace's AgentRegistry."""
        workspace_id = str(arguments.get("workspace_id") or "")
        name = str(arguments.get("name") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for register_agent.")
        if not name:
            raise ValueError("name is required for register_agent.")

        workspace = workspace_store.get_workspace(workspace_id)
        agent = workspace.agent_registry.register_agent(
            name=name,
            role=arguments.get("role", "GENERAL"),
            description=arguments.get("description"),
            capabilities=arguments.get("capabilities"),
            metadata=arguments.get("metadata"),
            agent_id=arguments.get("agent_id"),
            status=arguments.get("status", "IDLE"),
        )
        return agent.to_dict()

    def unregister_agent(self, workspace_id: str | dict[str, Any], agent_id: str | None = None) -> dict[str, Any]:
        """Unregister an agent from the workspace's AgentRegistry."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            ag_id = str(args.get("agent_id") or "")
        else:
            ws_id = str(workspace_id or "")
            ag_id = str(agent_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for unregister_agent.")
        if not ag_id:
            raise ValueError("agent_id is required for unregister_agent.")

        workspace = workspace_store.get_workspace(ws_id)
        agent = workspace.agent_registry.unregister_agent(ag_id)
        return agent.to_dict()

    def get_agent(self, workspace_id: str | dict[str, Any], agent_id: str | None = None) -> dict[str, Any]:
        """Retrieve an agent from the workspace's AgentRegistry."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            ag_id = str(args.get("agent_id") or "")
        else:
            ws_id = str(workspace_id or "")
            ag_id = str(agent_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for get_agent.")
        if not ag_id:
            raise ValueError("agent_id is required for get_agent.")

        workspace = workspace_store.get_workspace(ws_id)
        agent = workspace.agent_registry.get_agent(ag_id)
        return agent.to_dict()

    def list_agents(
        self,
        workspace_id: str | dict[str, Any],
        role: str | None = None,
        capability: str | None = None,
    ) -> dict[str, Any]:
        """List registered agents in a workspace with optional role or capability filters."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            r_filter = args.get("role")
            c_filter = args.get("capability")
        else:
            ws_id = str(workspace_id or "")
            r_filter = role
            c_filter = capability

        if not ws_id:
            raise ValueError("workspace_id is required for list_agents.")

        workspace = workspace_store.get_workspace(ws_id)
        if r_filter:
            agents = workspace.agent_registry.filter_by_role(r_filter)
        elif c_filter:
            agents = workspace.agent_registry.filter_by_capability(c_filter)
        else:
            agents = workspace.agent_registry.list_agents()

        return {
            "workspace_id": ws_id,
            "agents": [a.to_dict() for a in agents],
        }

    def create_collaboration(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Create a new collaboration session within a workspace."""
        workspace_id = str(arguments.get("workspace_id") or "")
        objective = str(arguments.get("objective") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for create_collaboration.")
        if not objective:
            raise ValueError("objective is required for create_collaboration.")

        workspace = workspace_store.get_workspace(workspace_id)
        session = workspace.collaboration_engine.create_session(
            objective=objective,
            participant_ids=arguments.get("participant_ids") or arguments.get("participants"),
            metadata=arguments.get("metadata"),
            session_id=arguments.get("session_id"),
        )
        return session.to_dict()

    def close_collaboration(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Close an active collaboration session."""
        workspace_id = str(arguments.get("workspace_id") or "")
        session_id = str(arguments.get("session_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for close_collaboration.")
        if not session_id:
            raise ValueError("session_id is required for close_collaboration.")

        workspace = workspace_store.get_workspace(workspace_id)
        status = arguments.get("status", "COMPLETED")
        session = workspace.collaboration_engine.close_session(session_id=session_id, status=status)
        return session.to_dict()

    def assign_agent(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Assign an agent to a collaboration session and optional task."""
        workspace_id = str(arguments.get("workspace_id") or "")
        session_id = str(arguments.get("session_id") or "")
        agent_id = str(arguments.get("agent_id") or "")
        if not workspace_id:
            raise ValueError("workspace_id is required for assign_agent.")
        if not session_id:
            raise ValueError("session_id is required for assign_agent.")
        if not agent_id:
            raise ValueError("agent_id is required for assign_agent.")

        workspace = workspace_store.get_workspace(workspace_id)
        assignment = workspace.collaboration_engine.assign_agent(
            session_id=session_id,
            agent_id=agent_id,
            task_id=arguments.get("task_id"),
            metadata=arguments.get("metadata"),
            assignment_id=arguments.get("assignment_id"),
        )
        return assignment.to_dict()

    def send_agent_message(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Send an inter-agent message within a collaboration session."""
        workspace_id = str(arguments.get("workspace_id") or "")
        session_id = str(arguments.get("session_id") or "")
        sender_agent_id = str(arguments.get("sender_agent_id") or "")
        content = arguments.get("content")
        if not workspace_id:
            raise ValueError("workspace_id is required for send_agent_message.")
        if not session_id:
            raise ValueError("session_id is required for send_agent_message.")
        if not sender_agent_id:
            raise ValueError("sender_agent_id is required for send_agent_message.")
        if content is None:
            raise ValueError("content is required for send_agent_message.")

        workspace = workspace_store.get_workspace(workspace_id)
        message = workspace.collaboration_engine.send_message(
            session_id=session_id,
            sender_agent_id=sender_agent_id,
            content=content,
            message_type=arguments.get("message_type", "INFO"),
            receiver_agent_id=arguments.get("receiver_agent_id"),
            metadata=arguments.get("metadata"),
        )
        return message.to_dict()

    def list_messages(
        self,
        workspace_id: str | dict[str, Any],
        session_id: str | None = None,
        receiver_agent_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List messages in a collaboration session."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            s_id = str(args.get("session_id") or "")
            r_id = args.get("receiver_agent_id")
            lim = args.get("limit")
        else:
            ws_id = str(workspace_id or "")
            s_id = str(session_id or "")
            r_id = receiver_agent_id
            lim = limit

        if not ws_id:
            raise ValueError("workspace_id is required for list_messages.")
        if not s_id:
            raise ValueError("session_id is required for list_messages.")

        workspace = workspace_store.get_workspace(ws_id)
        messages = workspace.collaboration_engine.receive_messages(
            session_id=s_id,
            receiver_agent_id=r_id,
            limit=lim,
        )
        return {
            "workspace_id": ws_id,
            "session_id": s_id,
            "messages": [m.to_dict() for m in messages],
        }

    def list_assignments(
        self,
        workspace_id: str | dict[str, Any],
        session_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """List agent assignments in a workspace."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            s_id = args.get("session_id")
            a_id = args.get("agent_id")
        else:
            ws_id = str(workspace_id or "")
            s_id = session_id
            a_id = agent_id

        if not ws_id:
            raise ValueError("workspace_id is required for list_assignments.")

        workspace = workspace_store.get_workspace(ws_id)
        assignments = workspace.collaboration_engine.list_assignments(
            session_id=s_id,
            agent_id=a_id,
        )
        return {
            "workspace_id": ws_id,
            "assignments": [a.to_dict() for a in assignments],
        }

    def list_sessions(self, workspace_id: str | dict[str, Any]) -> dict[str, Any]:
        """List all collaboration sessions for a workspace."""
        if isinstance(workspace_id, dict):
            ws_id = str(workspace_id.get("workspace_id") or "")
        else:
            ws_id = str(workspace_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for list_sessions.")

        workspace = workspace_store.get_workspace(ws_id)
        sessions = workspace.collaboration_engine.list_sessions()
        return {
            "workspace_id": ws_id,
            "sessions": [s.to_dict() for s in sessions],
        }

    # ------------------------------------------------------------------
    # Capability & Plugin Management Facade Methods (Capability 10)
    # ------------------------------------------------------------------

    def register_capability(
        self,
        workspace_id: str | dict[str, Any],
        capability_id: str | None = None,
        name: str | None = None,
        version: str | None = None,
        description: str | None = None,
        capability_type: str | None = None,
        status: str | None = None,
        dependencies: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a new capability in the workspace capability registry."""
        from capability_models import Capability, CapabilityStatus, CapabilityType

        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            cap_id = str(args.get("capability_id") or "")
            c_name = str(args.get("name") or "")
            c_version = str(args.get("version") or "1.0.0")
            c_desc = str(args.get("description") or "")
            c_type = args.get("capability_type") or CapabilityType.EXTENSION
            c_status = args.get("status") or CapabilityStatus.REGISTERED
            c_deps = args.get("dependencies") or []
            c_tools = args.get("mcp_tools") or []
            c_meta = args.get("metadata") or {}
        else:
            ws_id = str(workspace_id or "")
            cap_id = str(capability_id or "")
            c_name = str(name or "")
            c_version = str(version or "1.0.0")
            c_desc = str(description or "")
            c_type = capability_type or CapabilityType.EXTENSION
            c_status = status or CapabilityStatus.REGISTERED
            c_deps = dependencies or []
            c_tools = mcp_tools or []
            c_meta = metadata or {}

        if not ws_id:
            raise ValueError("workspace_id is required for register_capability.")
        if not cap_id:
            raise ValueError("capability_id is required for register_capability.")

        workspace = workspace_store.get_workspace(ws_id)
        capability = Capability(
            capability_id=cap_id,
            name=c_name,
            version=c_version,
            description=c_desc,
            capability_type=c_type,
            status=c_status,
            dependencies=list(c_deps),
            mcp_tools=list(c_tools),
            metadata=dict(c_meta),
        )
        registered = workspace.capability_registry.register_capability(capability)
        return {
            "workspace_id": ws_id,
            "capability": registered.to_dict(),
        }

    def unregister_capability(
        self,
        workspace_id: str | dict[str, Any],
        capability_id: str | None = None,
    ) -> dict[str, Any]:
        """Unregister a capability from the workspace capability registry."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            cap_id = str(args.get("capability_id") or "")
        else:
            ws_id = str(workspace_id or "")
            cap_id = str(capability_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for unregister_capability.")
        if not cap_id:
            raise ValueError("capability_id is required for unregister_capability.")

        workspace = workspace_store.get_workspace(ws_id)
        unregistered = workspace.capability_registry.unregister_capability(cap_id)
        return {
            "workspace_id": ws_id,
            "capability": unregistered.to_dict(),
        }

    def get_capability(
        self,
        workspace_id: str | dict[str, Any],
        capability_id: str | None = None,
    ) -> dict[str, Any]:
        """Get capability details by ID."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            cap_id = str(args.get("capability_id") or "")
        else:
            ws_id = str(workspace_id or "")
            cap_id = str(capability_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for get_capability.")
        if not cap_id:
            raise ValueError("capability_id is required for get_capability.")

        workspace = workspace_store.get_workspace(ws_id)
        capability = workspace.capability_registry.get_capability(cap_id)
        return {
            "workspace_id": ws_id,
            "capability": capability.to_dict(),
        }

    def list_capabilities(self, workspace_id: str | dict[str, Any]) -> dict[str, Any]:
        """List all registered capabilities in a workspace."""
        if isinstance(workspace_id, dict):
            ws_id = str(workspace_id.get("workspace_id") or "")
        else:
            ws_id = str(workspace_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for list_capabilities.")

        workspace = workspace_store.get_workspace(ws_id)
        capabilities = workspace.capability_registry.list_capabilities()
        return {
            "workspace_id": ws_id,
            "capabilities": [c.to_dict() for c in capabilities],
        }

    def enable_capability(
        self,
        workspace_id: str | dict[str, Any],
        capability_id: str | None = None,
    ) -> dict[str, Any]:
        """Enable a registered capability after dependency validation."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            cap_id = str(args.get("capability_id") or "")
        else:
            ws_id = str(workspace_id or "")
            cap_id = str(capability_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for enable_capability.")
        if not cap_id:
            raise ValueError("capability_id is required for enable_capability.")

        workspace = workspace_store.get_workspace(ws_id)
        capability = workspace.capability_registry.enable_capability(cap_id)
        return {
            "workspace_id": ws_id,
            "capability": capability.to_dict(),
        }

    def disable_capability(
        self,
        workspace_id: str | dict[str, Any],
        capability_id: str | None = None,
    ) -> dict[str, Any]:
        """Disable an enabled capability."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            cap_id = str(args.get("capability_id") or "")
        else:
            ws_id = str(workspace_id or "")
            cap_id = str(capability_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for disable_capability.")
        if not cap_id:
            raise ValueError("capability_id is required for disable_capability.")

        workspace = workspace_store.get_workspace(ws_id)
        capability = workspace.capability_registry.disable_capability(cap_id)
        return {
            "workspace_id": ws_id,
            "capability": capability.to_dict(),
        }

    def register_plugin(
        self,
        workspace_id: str | dict[str, Any],
        plugin_id: str | None = None,
        name: str | None = None,
        version: str | None = None,
        description: str | None = None,
        capabilities: list[dict[str, Any] | Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a plugin and forward its capabilities into the workspace CapabilityRegistry."""
        from capability_models import Capability, CapabilityStatus, CapabilityType, Plugin, PluginStatus

        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            p_id = str(args.get("plugin_id") or "")
            p_name = str(args.get("name") or "")
            p_version = str(args.get("version") or "1.0.0")
            p_desc = str(args.get("description") or "")
            raw_caps = args.get("capabilities") or []
            p_meta = args.get("metadata") or {}
        else:
            ws_id = str(workspace_id or "")
            p_id = str(plugin_id or "")
            p_name = str(name or "")
            p_version = str(version or "1.0.0")
            p_desc = str(description or "")
            raw_caps = capabilities or []
            p_meta = metadata or {}

        if not ws_id:
            raise ValueError("workspace_id is required for register_plugin.")
        if not p_id:
            raise ValueError("plugin_id is required for register_plugin.")

        parsed_capabilities: list[Capability] = []
        for c in raw_caps:
            if isinstance(c, Capability):
                parsed_capabilities.append(c)
            elif isinstance(c, dict):
                parsed_capabilities.append(
                    Capability(
                        capability_id=str(c.get("capability_id") or ""),
                        name=str(c.get("name") or ""),
                        version=str(c.get("version") or "1.0.0"),
                        description=str(c.get("description") or ""),
                        capability_type=c.get("capability_type") or CapabilityType.PLUGIN,
                        status=c.get("status") or CapabilityStatus.REGISTERED,
                        dependencies=list(c.get("dependencies") or []),
                        mcp_tools=list(c.get("mcp_tools") or []),
                        metadata=dict(c.get("metadata") or {}),
                    )
                )

        plugin = Plugin(
            plugin_id=p_id,
            name=p_name,
            version=p_version,
            description=p_desc,
            status=PluginStatus.LOADED,
            capabilities=parsed_capabilities,
            metadata=dict(p_meta),
        )

        workspace = workspace_store.get_workspace(ws_id)
        registered_plugin = workspace.plugin_manager.register_plugin(plugin)
        return {
            "workspace_id": ws_id,
            "plugin": registered_plugin.to_dict(),
        }

    def unregister_plugin(
        self,
        workspace_id: str | dict[str, Any],
        plugin_id: str | None = None,
    ) -> dict[str, Any]:
        """Unregister a plugin and remove its capabilities from the workspace CapabilityRegistry."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            p_id = str(args.get("plugin_id") or "")
        else:
            ws_id = str(workspace_id or "")
            p_id = str(plugin_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for unregister_plugin.")
        if not p_id:
            raise ValueError("plugin_id is required for unregister_plugin.")

        workspace = workspace_store.get_workspace(ws_id)
        plugin = workspace.plugin_manager.unregister_plugin(p_id)
        return {
            "workspace_id": ws_id,
            "plugin": plugin.to_dict(),
        }

    def load_plugin(
        self,
        workspace_id: str | dict[str, Any],
        plugin_id: str | None = None,
    ) -> dict[str, Any]:
        """Load an unloaded plugin."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            p_id = str(args.get("plugin_id") or "")
        else:
            ws_id = str(workspace_id or "")
            p_id = str(plugin_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for load_plugin.")
        if not p_id:
            raise ValueError("plugin_id is required for load_plugin.")

        workspace = workspace_store.get_workspace(ws_id)
        plugin = workspace.plugin_manager.load_plugin(p_id)
        return {
            "workspace_id": ws_id,
            "plugin": plugin.to_dict(),
        }

    def unload_plugin(
        self,
        workspace_id: str | dict[str, Any],
        plugin_id: str | None = None,
    ) -> dict[str, Any]:
        """Unload an active plugin."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            p_id = str(args.get("plugin_id") or "")
        else:
            ws_id = str(workspace_id or "")
            p_id = str(plugin_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for unload_plugin.")
        if not p_id:
            raise ValueError("plugin_id is required for unload_plugin.")

        workspace = workspace_store.get_workspace(ws_id)
        plugin = workspace.plugin_manager.unload_plugin(p_id)
        return {
            "workspace_id": ws_id,
            "plugin": plugin.to_dict(),
        }

    def list_plugins(self, workspace_id: str | dict[str, Any]) -> dict[str, Any]:
        """List all registered plugins for a workspace."""
        if isinstance(workspace_id, dict):
            ws_id = str(workspace_id.get("workspace_id") or "")
        else:
            ws_id = str(workspace_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for list_plugins.")

        workspace = workspace_store.get_workspace(ws_id)
        plugins = workspace.plugin_manager.list_plugins()
        return {
            "workspace_id": ws_id,
            "plugins": [p.to_dict() for p in plugins],
        }

    def get_plugin(
        self,
        workspace_id: str | dict[str, Any],
        plugin_id: str | None = None,
    ) -> dict[str, Any]:
        """Get plugin details by ID."""
        if isinstance(workspace_id, dict):
            args = workspace_id
            ws_id = str(args.get("workspace_id") or "")
            p_id = str(args.get("plugin_id") or "")
        else:
            ws_id = str(workspace_id or "")
            p_id = str(plugin_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for get_plugin.")
        if not p_id:
            raise ValueError("plugin_id is required for get_plugin.")

        workspace = workspace_store.get_workspace(ws_id)
        plugin = workspace.plugin_manager.get_plugin(p_id)
        return {
            "workspace_id": ws_id,
            "plugin": plugin.to_dict(),
        }

    def get_capability_summary(self, workspace_id: str | dict[str, Any]) -> dict[str, Any]:
        """Get summary metrics of capabilities and plugins for a workspace."""
        if isinstance(workspace_id, dict):
            ws_id = str(workspace_id.get("workspace_id") or "")
        else:
            ws_id = str(workspace_id or "")

        if not ws_id:
            raise ValueError("workspace_id is required for get_capability_summary.")

        workspace = workspace_store.get_workspace(ws_id)
        summary = workspace.capability_registry.summary(
            plugin_count=len(workspace.plugin_manager.list_plugins())
        )
        return {
            "workspace_id": ws_id,
            "summary": summary.to_dict(),
        }


    def _build_executor(self) -> Callable[[dict[str, Any]], ExecutionResult]:
        """Return a thin adapter that calls ``_execute_model`` and converts its
        raw dict response into a strongly-typed ``ExecutionResult``.

        This adapter is created fresh each time to capture the current
        ``_execute_model`` reference without mutation.
        """
        execute_model = self._execute_model

        def _adapter(arguments: dict[str, Any]) -> ExecutionResult:
            started = time.perf_counter()
            execution_id = str(uuid4())
            prompt = arguments.get("prompt")
            if prompt is None and "messages" in arguments:
                prompt = str(arguments["messages"])

            try:
                raw = execute_model(arguments)
            except Exception as exc:
                return ExecutionResult(
                    execution_id=execution_id,
                    provider=str(arguments.get("provider", "")),
                    model=arguments.get("model"),
                    prompt=str(prompt or ""),
                    success=False,
                    error={"code": exc.__class__.__name__, "message": str(exc)},
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

            latency_ms = int((time.perf_counter() - started) * 1000)
            ok = raw.get("ok", False) is True
            return ExecutionResult(
                execution_id=execution_id,
                provider=str(raw.get("provider", arguments.get("provider", ""))),
                model=raw.get("model", arguments.get("model")),
                prompt=str(prompt or ""),
                response=raw.get("text") if ok else None,
                error=None if ok else {"code": raw.get("error", "execution_failed"), "message": raw.get("detail", "")},
                latency_ms=latency_ms,
                success=ok,
            )

        return _adapter
