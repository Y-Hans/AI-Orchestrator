"""In-memory Execution Binding storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ExecutionType(str, Enum):
    PRIMARY = "PRIMARY"
    REVIEW = "REVIEW"
    RETRY = "RETRY"
    PARALLEL = "PARALLEL"
    SYNTHESIS = "SYNTHESIS"
    VALIDATION = "VALIDATION"


@dataclass
class ExecutionBinding:
    binding_id: str
    task_id: str
    execution_id: str
    execution_type: ExecutionType
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "execution_type": self.execution_type.value if hasattr(self.execution_type, "value") else self.execution_type,
            "created_at": self.created_at,
        }


class TaskExecutionIndex:
    """Index mapping Tasks to Execution Records in a workspace."""

    def __init__(self) -> None:
        self._bindings: dict[str, ExecutionBinding] = {}

    def bind_execution(
        self,
        task_id: str,
        execution_id: str,
        execution_type: ExecutionType | str = ExecutionType.PRIMARY,
        binding_id: str | None = None,
        created_at: str | None = None,
    ) -> ExecutionBinding:
        bid = binding_id or str(uuid4())

        if isinstance(execution_type, str):
            try:
                etype = ExecutionType(execution_type.upper())
            except ValueError:
                raise ValueError(f"Invalid execution type: {execution_type}")
        else:
            etype = execution_type

        binding = ExecutionBinding(
            binding_id=bid,
            task_id=task_id,
            execution_id=execution_id,
            execution_type=etype,
            created_at=created_at or utc_now(),
        )
        self._bindings[bid] = binding
        return binding

    def get_task_executions(self, task_id: str) -> list[ExecutionBinding]:
        return [b for b in self._bindings.values() if b.task_id == task_id]

    def get_execution(self, execution_id: str) -> ExecutionBinding | None:
        for b in self._bindings.values():
            if b.execution_id == execution_id:
                return b
        return None

    def remove_binding(self, binding_id: str) -> None:
        if binding_id in self._bindings:
            del self._bindings[binding_id]
        else:
            raise KeyError(f"Binding not found: {binding_id}")

    def list_bindings(self) -> list[ExecutionBinding]:
        return list(self._bindings.values())
