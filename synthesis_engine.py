"""Result Synthesis Engine for Capability 8.

Coordinates collection of execution records, review reports, artifacts,
and memory records from a TaskWorkspace and synthesizes them into structured deliverables.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from synthesis_models import (
    SynthesisReport,
    SynthesisResult,
    SynthesisSource,
    SynthesisSourceType,
    SynthesisStatus,
    utc_now,
)


class Synthesizer(ABC):
    """Abstract base class for result synthesizers."""

    @abstractmethod
    def synthesize(
        self,
        title: str,
        sources: list[SynthesisSource],
        inputs_data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> SynthesisResult:
        """Synthesize collected source inputs into a single immutable result deliverable."""
        pass


class DeterministicSynthesizer(Synthesizer):
    """Default non-AI synthesizer that deterministically combines inputs in order."""

    def synthesize(
        self,
        title: str,
        sources: list[SynthesisSource],
        inputs_data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> SynthesisResult:
        synthesis_id = str(uuid4())
        combined_items: list[dict[str, Any]] = []

        for source in sources:
            data = inputs_data.get(source.source_id)
            combined_items.append({
                "source_type": source.source_type.value if hasattr(source.source_type, "value") else str(source.source_type),
                "source_id": source.source_id,
                "title": source.title,
                "data": data,
            })

        summary = f"Deterministic synthesis of {len(sources)} source(s) for '{title}'."
        
        counts: dict[str, int] = {}
        for s in sources:
            stype = s.source_type.value if hasattr(s.source_type, "value") else str(s.source_type)
            counts[stype] = counts.get(stype, 0) + 1

        result_metadata = {
            "synthesizer": "DeterministicSynthesizer",
            "source_counts": counts,
            "total_sources": len(sources),
        }
        if metadata:
            result_metadata.update(metadata)

        content = {
            "title": title,
            "summary": summary,
            "items": combined_items,
        }

        return SynthesisResult(
            synthesis_id=synthesis_id,
            title=title,
            summary=summary,
            content=content,
            metadata=result_metadata,
        )


class SynthesisEngine:
    """Engine responsible for collecting inputs and orchestrating result synthesis."""

    def __init__(
        self,
        workspace: Any,  # TaskWorkspace
        synthesizer: Synthesizer | None = None,
    ) -> None:
        self._workspace = workspace
        self._synthesizer = synthesizer or DeterministicSynthesizer()

    def set_synthesizer(self, synthesizer: Synthesizer) -> None:
        """Inject a custom Synthesizer strategy."""
        self._synthesizer = synthesizer

    def synthesize(
        self,
        title: str,
        source_ids: list[str] | None = None,
        sources: list[SynthesisSource] | None = None,
        task_id: str | None = None,
        plan_id: str | None = None,
        execution_ids: list[str] | None = None,
        review_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        memory_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SynthesisReport:
        """Synthesize outputs from explicit parameters or explicit source lists."""
        collected_sources: list[SynthesisSource] = list(sources) if sources else []
        inputs_data: dict[str, Any] = {}

        # 1. Gather specified execution IDs
        if execution_ids:
            for eid in execution_ids:
                record = next((e for e in self._workspace.executions if e.execution_id == eid), None)
                if record:
                    src = SynthesisSource(
                        source_type=SynthesisSourceType.EXECUTION,
                        source_id=record.execution_id,
                        title=f"Execution {record.execution_id}",
                        metadata={"provider": record.provider, "model": record.model, "success": record.success},
                    )
                    if not any(s.source_id == src.source_id for s in collected_sources):
                        collected_sources.append(src)
                    inputs_data[record.execution_id] = {
                        "execution_id": record.execution_id,
                        "provider": record.provider,
                        "model": record.model,
                        "prompt": record.prompt,
                        "response": record.response,
                        "error": record.error,
                        "success": record.success,
                    }

        # 2. Gather specified review IDs
        if review_ids:
            for rid in review_ids:
                rep = self._workspace.review_reports.get(rid)
                if rep:
                    src = SynthesisSource(
                        source_type=SynthesisSourceType.REVIEW,
                        source_id=rep.report_id,
                        title=f"Review Report {rep.report_id}",
                        metadata={"status": str(rep.review_result.status), "overall_score": rep.review_result.overall_score},
                    )
                    if not any(s.source_id == src.source_id for s in collected_sources):
                        collected_sources.append(src)
                    inputs_data[rep.report_id] = rep.to_dict()

        # 3. Gather specified artifact IDs
        if artifact_ids:
            for aid in artifact_ids:
                art = self._workspace.artifact_store.get_artifact(aid)
                if art:
                    src = SynthesisSource(
                        source_type=SynthesisSourceType.ARTIFACT,
                        source_id=art.artifact_id,
                        title=art.name,
                        metadata={"artifact_type": str(art.artifact_type), "mime_type": art.mime_type},
                    )
                    if not any(s.source_id == src.source_id for s in collected_sources):
                        collected_sources.append(src)
                    inputs_data[art.artifact_id] = {
                        "artifact_id": art.artifact_id,
                        "name": art.name,
                        "artifact_type": str(art.artifact_type),
                        "mime_type": art.mime_type,
                        "content": getattr(art, "content", None),
                        "metadata": art.metadata,
                    }

        # 4. Gather specified memory IDs
        if memory_ids:
            for mid in memory_ids:
                mem = self._workspace.memory_engine.retrieve_memory(mid)
                if mem:
                    src = SynthesisSource(
                        source_type=SynthesisSourceType.MEMORY,
                        source_id=mem.memory_id,
                        title=mem.title,
                        metadata={"memory_type": str(mem.memory_type), "tags": mem.tags},
                    )
                    if not any(s.source_id == src.source_id for s in collected_sources):
                        collected_sources.append(src)
                    inputs_data[mem.memory_id] = mem.to_dict()

        # 5. If task_id or plan_id passed, supplement sources
        if task_id and not (execution_ids or review_ids or artifact_ids):
            task_report = self._collect_task_sources(task_id=task_id, include_reviews=True, include_artifacts=True, include_memories=False)
            for s in task_report["sources"]:
                if not any(cs.source_id == s.source_id for cs in collected_sources):
                    collected_sources.append(s)
            inputs_data.update(task_report["inputs_data"])

        if plan_id and not (execution_ids or review_ids or artifact_ids):
            plan_report = self._collect_plan_sources(plan_id=plan_id, include_reviews=True, include_artifacts=True, include_memories=False)
            for s in plan_report["sources"]:
                if not any(cs.source_id == s.source_id for cs in collected_sources):
                    collected_sources.append(s)
            inputs_data.update(plan_report["inputs_data"])

        report_id = str(uuid4())
        try:
            result = self._synthesizer.synthesize(
                title=title,
                sources=collected_sources,
                inputs_data=inputs_data,
                metadata=metadata,
            )
            report = SynthesisReport(
                report_id=report_id,
                workspace_id=self._workspace.workspace_id,
                status=SynthesisStatus.COMPLETED,
                result=result,
                sources=collected_sources,
                created_at=utc_now(),
                metadata=metadata or {},
            )
        except Exception as exc:
            report = SynthesisReport(
                report_id=report_id,
                workspace_id=self._workspace.workspace_id,
                status=SynthesisStatus.FAILED,
                result=None,
                sources=collected_sources,
                created_at=utc_now(),
                metadata={"error": str(exc)},
            )

        self._workspace.syntheses[report.report_id] = report
        return report

    def synthesize_task(
        self,
        task_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        include_reviews: bool = True,
        include_artifacts: bool = True,
        include_memories: bool = False,
    ) -> SynthesisReport:
        """Synthesize all execution outputs, reviews, and artifacts for a single task."""
        # Ensure task exists
        self._workspace.task_graph.get_task(task_id)

        collected = self._collect_task_sources(
            task_id=task_id,
            include_reviews=include_reviews,
            include_artifacts=include_artifacts,
            include_memories=include_memories,
        )

        effective_title = title or f"Synthesis for Task {task_id}"
        return self.synthesize(
            title=effective_title,
            sources=collected["sources"],
            metadata=metadata,
            task_id=task_id,
        )

    def synthesize_plan(
        self,
        plan_id: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        include_reviews: bool = True,
        include_artifacts: bool = True,
        include_memories: bool = False,
    ) -> SynthesisReport:
        """Synthesize outputs across all tasks in a target plan."""
        collected = self._collect_plan_sources(
            plan_id=plan_id,
            include_reviews=include_reviews,
            include_artifacts=include_artifacts,
            include_memories=include_memories,
        )

        effective_title = title or f"Synthesis for Plan {plan_id or 'default'}"
        return self.synthesize(
            title=effective_title,
            sources=collected["sources"],
            metadata=metadata,
            plan_id=plan_id,
        )

    def get_synthesis(self, report_id: str) -> SynthesisReport:
        """Retrieve a stored synthesis report by report_id."""
        report = self._workspace.syntheses.get(report_id)
        if report is None:
            raise KeyError(f"Synthesis report not found: {report_id}")
        return report

    def list_syntheses(self) -> list[SynthesisReport]:
        """List all synthesis reports in the workspace."""
        return list(self._workspace.syntheses.values())

    def delete_synthesis(self, report_id: str) -> SynthesisReport:
        """Delete a stored synthesis report from the workspace."""
        if report_id not in self._workspace.syntheses:
            raise KeyError(f"Synthesis report not found: {report_id}")
        return self._workspace.syntheses.pop(report_id)

    # ------------------------------------------------------------------
    # Helper Data Collection Methods (Read-Only)
    # ------------------------------------------------------------------

    def _collect_task_sources(
        self,
        task_id: str,
        include_reviews: bool,
        include_artifacts: bool,
        include_memories: bool,
    ) -> dict[str, Any]:
        sources: list[SynthesisSource] = []
        inputs_data: dict[str, Any] = {}

        # Bound executions
        bindings = self._workspace.task_execution_index.get_task_executions(task_id)
        execution_ids = [b.execution_id for b in bindings]
        for eid in execution_ids:
            record = next((e for e in self._workspace.executions if e.execution_id == eid), None)
            if record:
                src = SynthesisSource(
                    source_type=SynthesisSourceType.EXECUTION,
                    source_id=record.execution_id,
                    title=f"Execution {record.execution_id} (Task {task_id})",
                    metadata={"provider": record.provider, "model": record.model, "success": record.success},
                )
                sources.append(src)
                inputs_data[record.execution_id] = {
                    "execution_id": record.execution_id,
                    "provider": record.provider,
                    "model": record.model,
                    "prompt": record.prompt,
                    "response": record.response,
                    "error": record.error,
                    "success": record.success,
                }

        # Task review reports
        if include_reviews:
            for rep in self._workspace.review_reports.values():
                if rep.task_id == task_id or (rep.execution_id and rep.execution_id in execution_ids):
                    src = SynthesisSource(
                        source_type=SynthesisSourceType.REVIEW,
                        source_id=rep.report_id,
                        title=f"Review Report {rep.report_id}",
                        metadata={"status": str(rep.review_result.status), "overall_score": rep.review_result.overall_score},
                    )
                    sources.append(src)
                    inputs_data[rep.report_id] = rep.to_dict()

        # Task artifacts
        if include_artifacts:
            for art in self._workspace.artifact_store.list_task_artifacts(task_id):
                src = SynthesisSource(
                    source_type=SynthesisSourceType.ARTIFACT,
                    source_id=art.artifact_id,
                    title=art.name,
                    metadata={"artifact_type": str(art.artifact_type), "mime_type": art.mime_type},
                )
                sources.append(src)
                inputs_data[art.artifact_id] = {
                    "artifact_id": art.artifact_id,
                    "name": art.name,
                    "artifact_type": str(art.artifact_type),
                    "mime_type": art.mime_type,
                    "content": getattr(art, "content", None),
                    "metadata": art.metadata,
                }

        # Memories
        if include_memories:
            for mem in self._workspace.memory_engine.list_memories():
                if task_id in mem.tags or (mem.metadata and mem.metadata.get("task_id") == task_id):
                    src = SynthesisSource(
                        source_type=SynthesisSourceType.MEMORY,
                        source_id=mem.memory_id,
                        title=mem.title,
                        metadata={"memory_type": str(mem.memory_type), "tags": mem.tags},
                    )
                    sources.append(src)
                    inputs_data[mem.memory_id] = mem.to_dict()

        return {"sources": sources, "inputs_data": inputs_data}

    def _collect_plan_sources(
        self,
        plan_id: str | None,
        include_reviews: bool,
        include_artifacts: bool,
        include_memories: bool,
    ) -> dict[str, Any]:
        sources: list[SynthesisSource] = []
        inputs_data: dict[str, Any] = {}

        tasks = list(self._workspace.task_graph.nodes.values())
        for task_node in tasks:
            tid = task_node.task_id
            collected = self._collect_task_sources(
                task_id=tid,
                include_reviews=include_reviews,
                include_artifacts=include_artifacts,
                include_memories=include_memories,
            )
            for s in collected["sources"]:
                if not any(existing.source_id == s.source_id for existing in sources):
                    sources.append(s)
            inputs_data.update(collected["inputs_data"])

        return {"sources": sources, "inputs_data": inputs_data}
