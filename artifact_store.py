from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

class ArtifactType(str, Enum):
    TEXT = "TEXT"
    MARKDOWN = "MARKDOWN"
    PYTHON = "PYTHON"
    JSON = "JSON"
    CSV = "CSV"
    HTML = "HTML"
    IMAGE = "IMAGE"
    PDF = "PDF"
    DIFF = "DIFF"
    PATCH = "PATCH"
    LOG = "LOG"
    UNKNOWN = "UNKNOWN"

@dataclass
class Artifact:
    artifact_id: str
    task_id: str | None
    execution_id: str | None
    workspace_id: str
    name: str
    artifact_type: ArtifactType
    mime_type: str
    content: Any
    metadata: dict[str, Any]
    created_at: str

class ArtifactStore:
    """In‑memory store for artifacts.

    All operations are deterministic and thread‑unsafe – the surrounding
    workspace is assumed to be accessed by a single thread in the current
    implementation.
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    def create_artifact(self, artifact: Artifact) -> Artifact:
        """Store a new artifact.

        The caller is responsible for providing a unique ``artifact_id``.
        """
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def get_artifact(self, artifact_id: str) -> Artifact:
        return self._artifacts[artifact_id]

    def list_artifacts(self) -> list[Artifact]:
        return list(self._artifacts.values())

    def list_task_artifacts(self, task_id: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.task_id == task_id]

    def list_execution_artifacts(self, execution_id: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.execution_id == execution_id]

    def delete_artifact(self, artifact_id: str) -> None:
        del self._artifacts[artifact_id]
