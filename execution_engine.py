"""Execution Engine – the sole coordinator for task execution workflows.

The ExecutionEngine accepts an injected executor callable so it is
decoupled from any specific provider implementation. It does not infer,
parse, route, synthesise, or automatically extract artefacts from model
output. Every decision is made by Antigravity; the engine only drives the
lifecycle and persists what it is explicitly given.

Public interface
----------------
execute_task(...)   – run a single task
execute_tasks(...)  – run multiple tasks sequentially or in parallel
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from uuid import uuid4

from execution_binding import ExecutionType, TaskExecutionIndex
from execution_result import ExecutionResult
from task_graph import TaskGraph, TaskNode


def _utc_now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


class ExecutionEngine:
    """Coordinates task execution using an injected executor callable.

    Parameters
    ----------
    executor:
        A callable ``(arguments: dict) -> ExecutionResult`` provided by the
        caller at construction time.  The engine never references any
        provider directly.
    task_graph:
        The ``TaskGraph`` of the workspace this engine operates on.
    execution_index:
        The ``TaskExecutionIndex`` of the workspace used to bind executions
        to tasks.
    execution_store_add:
        A callable ``(record) -> None`` that persists an ``ExecutionRecord``
        to the workspace's execution store.
    """

    def __init__(
        self,
        executor: Callable[[dict[str, Any]], ExecutionResult],
        task_graph: TaskGraph,
        execution_index: TaskExecutionIndex,
        execution_store_add: Callable[[Any], None],
    ) -> None:
        self._executor = executor
        self._task_graph = task_graph
        self._execution_index = execution_index
        self._execution_store_add = execution_store_add

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_task(
        self,
        task_id: str,
        arguments: dict[str, Any],
        execution_type: str | ExecutionType = ExecutionType.PRIMARY,
    ) -> dict[str, Any]:
        """Execute a single task and update its lifecycle state.

        Parameters
        ----------
        task_id:
            ID of the task in the workspace's task graph.
        arguments:
            Raw arguments forwarded verbatim to the executor callable.
        execution_type:
            The ``ExecutionType`` binding to associate with the resulting
            execution record. Defaults to PRIMARY.

        Returns
        -------
        dict
            A summary dict containing ``task_id``, ``execution_id``,
            ``success``, ``execution_type``, and optionally ``error``.
        """
        node: TaskNode = self._task_graph.get_task(task_id)

        execution_id = str(uuid4())
        etype = (
            ExecutionType(execution_type.upper())
            if isinstance(execution_type, str)
            else execution_type
        )

        # 1. Transition task to RUNNING
        node.start_execution(execution_id)

        started_at = _utc_now()
        started_perf = time.perf_counter()
        result: ExecutionResult | None = None

        try:
            # 2. Invoke the injected executor
            result = self._executor(arguments)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started_perf) * 1000)
            result = ExecutionResult(
                execution_id=execution_id,
                provider=str(arguments.get("provider", "")),
                model=arguments.get("model"),
                prompt=str(arguments.get("prompt") or arguments.get("messages") or ""),
                success=False,
                error={"code": exc.__class__.__name__, "message": str(exc)},
                latency_ms=latency_ms,
            )

        completed_at = _utc_now()
        if result.latency_ms == 0:
            result = ExecutionResult(
                execution_id=result.execution_id,
                provider=result.provider,
                model=result.model,
                prompt=result.prompt,
                response=result.response,
                error=result.error,
                latency_ms=int((time.perf_counter() - started_perf) * 1000),
                success=result.success,
            )

        # 3. Persist execution record
        from workspace import ExecutionRecord  # local import avoids circular deps
        record = ExecutionRecord(
            execution_id=execution_id,
            provider=result.provider,
            model=result.model,
            prompt=result.prompt,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=result.latency_ms,
            success=result.success,
            response=result.response,
            error=result.error,
        )
        self._execution_store_add(record)

        # 4. Bind execution to task
        self._execution_index.bind_execution(
            task_id=task_id,
            execution_id=execution_id,
            execution_type=etype,
        )

        # 5. Transition task lifecycle
        if result.success:
            node.complete_execution(
                result_summary=str(result.response)[:200] if result.response else None
            )
        else:
            node.fail_execution(
                result_summary=str(result.error)[:200] if result.error else None
            )

        return {
            "task_id": task_id,
            "execution_id": execution_id,
            "success": result.success,
            "execution_type": etype.value,
            **({"error": result.error} if not result.success else {}),
        }

    def execute_tasks(
        self,
        task_ids: list[str],
        arguments_list: list[dict[str, Any]],
        execution_type: str | ExecutionType = ExecutionType.PRIMARY,
        parallel: bool = False,
    ) -> dict[str, Any]:
        """Execute multiple tasks sequentially or in parallel.

        Parameters
        ----------
        task_ids:
            Ordered list of task IDs to execute.
        arguments_list:
            Parallel list of argument dicts – one per task.
        execution_type:
            Binding type applied to all executions.
        parallel:
            When ``True`` executes tasks concurrently using a thread pool.

        Returns
        -------
        dict
            ``{"results": [...]}`` where each item is the return value of
            ``execute_task`` for the corresponding task.
        """
        if len(task_ids) != len(arguments_list):
            raise ValueError(
                "task_ids and arguments_list must have the same length."
            )

        def _run_one(pair: tuple[str, dict[str, Any]]) -> dict[str, Any]:
            tid, args = pair
            return self.execute_task(tid, args, execution_type=execution_type)

        pairs = list(zip(task_ids, arguments_list))

        if parallel:
            with ThreadPoolExecutor(max_workers=len(pairs)) as pool:
                results = list(pool.map(_run_one, pairs))
        else:
            results = [_run_one(p) for p in pairs]

        return {"results": results}
