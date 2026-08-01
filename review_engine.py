"""Capability 6 — Review & Validation Engine.

Coordinates review and quality validation of completed task executions,
individual tasks, task batches, and overall plans.

The ReviewEngine is a pure evaluation subsystem. It accepts an injected
reviewer callable, produces structured validation reports with deterministic
scores, and records review history in the TaskWorkspace. It never executes
tasks, schedules tasks, modifies task graph topology, retries executions,
replans objectives, or calls LLM providers directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from review_models import (
    ReviewCriterion,
    ReviewFinding,
    ReviewReport,
    ReviewResult,
    ReviewSeverity,
    ReviewStatus,
    utc_now,
)

if TYPE_CHECKING:
    from workspace import TaskWorkspace, ExecutionRecord


class ReviewEngine:
    """Pure evaluation engine for reviewing executions, tasks, and plans."""

    def __init__(
        self,
        workspace: TaskWorkspace | None = None,
        reviewer: Callable[[dict[str, Any]], ReviewResult | dict[str, Any]] | None = None,
    ) -> None:
        self.workspace = workspace
        self.reviewer = reviewer

    def review_execution(
        self,
        execution_id: str,
        criteria: list[ReviewCriterion | dict[str, Any]] | None = None,
        reviewer: Callable[[dict[str, Any]], ReviewResult | dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewReport:
        """Evaluate a completed execution record against defined criteria."""
        if self.workspace is None:
            raise RuntimeError("ReviewEngine must be associated with a workspace to review executions.")

        record = self._find_execution_record(execution_id)
        if record is None:
            raise KeyError(f"Execution record not found: {execution_id}")

        norm_criteria = self._normalize_criteria(criteria)
        effective_reviewer = reviewer or self.reviewer

        meta = metadata or {}
        task_id = self._find_task_id_for_execution(execution_id)

        if effective_reviewer is not None:
            raw_res = effective_reviewer({
                "execution_id": execution_id,
                "task_id": task_id,
                "workspace_id": self.workspace.workspace_id,
                "execution_record": record,
                "criteria": norm_criteria,
                "metadata": meta,
            })
            review_result = self._normalize_review_result(raw_res, execution_id)
        else:
            review_result = self._evaluate_execution_record(execution_id, record, norm_criteria, meta)

        recommendations = self._generate_execution_recommendations(review_result, record)

        report = ReviewReport(
            report_id=f"report-{uuid4()}",
            review_result=review_result,
            workspace_id=self.workspace.workspace_id,
            task_id=task_id,
            execution_id=execution_id,
            recommendations=recommendations,
            created_at=utc_now(),
            metadata=meta,
        )

        self.workspace.review_reports[report.report_id] = report
        return report

    def review_task(
        self,
        task_id: str,
        criteria: list[ReviewCriterion | dict[str, Any]] | None = None,
        reviewer: Callable[[dict[str, Any]], ReviewResult | dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewReport:
        """Evaluate a task node and its bound executions in the workspace task graph."""
        if self.workspace is None:
            raise RuntimeError("ReviewEngine must be associated with a workspace to review tasks.")

        task_node = self.workspace.task_graph.nodes.get(task_id)
        norm_criteria = self._normalize_criteria(criteria)
        meta = metadata or {}

        bindings = self.workspace.task_execution_index.get_task_executions(task_id)
        bound_execution_ids = [b.execution_id for b in bindings]

        if bound_execution_ids:
            latest_exec_id = bound_execution_ids[-1]
            record = self._find_execution_record(latest_exec_id)
        else:
            record = None

        effective_reviewer = reviewer or self.reviewer

        if effective_reviewer is not None:
            raw_res = effective_reviewer({
                "task_id": task_id,
                "task_node": task_node.to_dict() if task_node else None,
                "workspace_id": self.workspace.workspace_id,
                "execution_ids": bound_execution_ids,
                "execution_record": record,
                "criteria": norm_criteria,
                "metadata": meta,
            })
            review_result = self._normalize_review_result(raw_res, record.execution_id if record else None)
        else:
            review_result = self._evaluate_task_node(task_node, record, norm_criteria, meta)

        recommendations = self._generate_task_recommendations(review_result, task_node, record)

        report = ReviewReport(
            report_id=f"report-{uuid4()}",
            review_result=review_result,
            workspace_id=self.workspace.workspace_id,
            task_id=task_id,
            execution_id=record.execution_id if record else None,
            recommendations=recommendations,
            created_at=utc_now(),
            metadata=meta,
        )

        self.workspace.review_reports[report.report_id] = report
        return report

    def review_tasks(
        self,
        task_ids: list[str],
        criteria: list[ReviewCriterion | dict[str, Any]] | None = None,
        reviewer: Callable[[dict[str, Any]], ReviewResult | dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[ReviewReport]:
        """Evaluate a collection of task nodes sequentially."""
        return [
            self.review_task(tid, criteria=criteria, reviewer=reviewer, metadata=metadata)
            for tid in task_ids
        ]

    def review_plan(
        self,
        plan_id: str | None = None,
        criteria: list[ReviewCriterion | dict[str, Any]] | None = None,
        reviewer: Callable[[dict[str, Any]], ReviewResult | dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewReport:
        """Evaluate an entire plan and all associated task outputs in the workspace."""
        if self.workspace is None:
            raise RuntimeError("ReviewEngine must be associated with a workspace to review plans.")

        if plan_id:
            plan = self.workspace.plans.get(plan_id)
            if plan is None:
                raise KeyError(f"Plan not found: {plan_id}")
        else:
            if not self.workspace.plans:
                raise KeyError("No plan found in workspace to review.")
            plan = list(self.workspace.plans.values())[-1]

        meta = metadata or {}
        norm_criteria = self._normalize_criteria(criteria)
        effective_reviewer = reviewer or self.reviewer

        all_nodes = list(self.workspace.task_graph.nodes.values())
        parent_ids = {n.parent_task_id for n in all_nodes if n.parent_task_id}
        executable_nodes = [
            n for n in all_nodes
            if n.task_id not in parent_ids
            and n.task_id != plan.root_task_id
            and n.metadata.get("is_executable") is not False
        ]

        task_reports = [
            self.review_task(n.task_id, criteria=norm_criteria, reviewer=effective_reviewer, metadata=meta)
            for n in executable_nodes
        ] if executable_nodes else []

        if effective_reviewer is not None and not task_reports:
            raw_res = effective_reviewer({
                "plan_id": plan.plan_id,
                "workspace_id": self.workspace.workspace_id,
                "criteria": norm_criteria,
                "metadata": meta,
            })
            review_result = self._normalize_review_result(raw_res, None)
        else:
            review_result = self._evaluate_plan_aggregate(plan, task_reports, norm_criteria, meta)

        recommendations = self._generate_plan_recommendations(review_result, plan, task_reports)

        report = ReviewReport(
            report_id=f"report-{uuid4()}",
            review_result=review_result,
            workspace_id=self.workspace.workspace_id,
            plan_id=plan.plan_id,
            recommendations=recommendations,
            created_at=utc_now(),
            metadata=meta,
        )

        self.workspace.review_reports[report.report_id] = report
        return report

    def get_review(self, report_id: str) -> ReviewReport:
        """Retrieve a stored review report by its report ID."""
        if self.workspace is None:
            raise RuntimeError("ReviewEngine must be associated with a workspace.")
        report = self.workspace.review_reports.get(report_id)
        if report is None:
            raise KeyError(f"Review report not found: {report_id}")
        return report

    def list_reviews(self) -> list[ReviewReport]:
        """List all review reports stored in the workspace."""
        if self.workspace is None:
            raise RuntimeError("ReviewEngine must be associated with a workspace.")
        return list(self.workspace.review_reports.values())

    # ------------------------------------------------------------------
    # Internal Evaluation & Normalization Helpers
    # ------------------------------------------------------------------

    def _find_execution_record(self, execution_id: str) -> ExecutionRecord | None:
        if self.workspace is None:
            return None
        for rec in self.workspace.executions:
            if rec.execution_id == execution_id:
                return rec
        return None

    def _find_task_id_for_execution(self, execution_id: str) -> str | None:
        if self.workspace is None:
            return None
        for binding in self.workspace.task_execution_index.list_bindings():
            if binding.execution_id == execution_id:
                return binding.task_id
        return None

    def _normalize_criteria(
        self, criteria: list[ReviewCriterion | dict[str, Any]] | None
    ) -> list[ReviewCriterion]:
        if not criteria:
            return [
                ReviewCriterion(
                    criterion_id="crit-output-validity",
                    title="Output Validity & Success",
                    description="Verifies execution completed successfully with non-empty output.",
                    weight=1.0,
                )
            ]

        result = []
        for i, c in enumerate(criteria):
            if isinstance(c, ReviewCriterion):
                result.append(c)
            elif isinstance(c, dict):
                result.append(
                    ReviewCriterion(
                        criterion_id=str(c.get("criterion_id", f"crit-{i+1}")),
                        title=str(c.get("title", f"Criterion {i+1}")),
                        description=c.get("description"),
                        weight=float(c.get("weight", 1.0)),
                        metadata=c.get("metadata", {}),
                    )
                )
            else:
                raise TypeError(f"Invalid criterion type: {type(c)}")
        return result

    def _normalize_review_result(
        self, raw: ReviewResult | dict[str, Any], execution_id: str | None
    ) -> ReviewResult:
        if isinstance(raw, ReviewResult):
            return raw
        if isinstance(raw, dict):
            status_str = raw.get("status", "PASSED")
            try:
                status = ReviewStatus(status_str)
            except ValueError:
                status = ReviewStatus.PASSED

            raw_findings = raw.get("findings", [])
            findings = []
            for f in raw_findings:
                if isinstance(f, ReviewFinding):
                    findings.append(f)
                elif isinstance(f, dict):
                    sev_str = f.get("severity", "INFO")
                    try:
                        sev = ReviewSeverity(sev_str)
                    except ValueError:
                        sev = ReviewSeverity.INFO
                    findings.append(
                        ReviewFinding(
                            criterion_id=str(f.get("criterion_id", "crit-general")),
                            severity=sev,
                            message=str(f.get("message", "")),
                            score=float(f.get("score", 0.0)),
                            metadata=f.get("metadata", {}),
                        )
                    )

            return ReviewResult(
                review_id=str(raw.get("review_id", f"rev-{uuid4()}")),
                execution_id=raw.get("execution_id", execution_id),
                status=status,
                overall_score=float(raw.get("overall_score", 1.0)),
                findings=tuple(findings),
                summary=str(raw.get("summary", "Review complete")),
                metadata=raw.get("metadata", {}),
            )
        raise TypeError(f"Reviewer returned unsupported type: {type(raw)}")

    def _evaluate_execution_record(
        self,
        execution_id: str,
        record: ExecutionRecord,
        criteria: list[ReviewCriterion],
        metadata: dict[str, Any],
    ) -> ReviewResult:
        findings: list[ReviewFinding] = []
        total_weight = sum(c.weight for c in criteria) or 1.0
        weighted_score_accum = 0.0

        for crit in criteria:
            if record.success and record.response:
                score = 1.0
                severity = ReviewSeverity.INFO
                msg = f"Criterion '{crit.title}' satisfied. Execution output present."
            elif record.success and not record.response:
                score = 0.5
                severity = ReviewSeverity.WARNING
                msg = f"Criterion '{crit.title}' partially satisfied. Execution succeeded but output is empty."
            else:
                score = 0.0
                severity = ReviewSeverity.ERROR
                msg = f"Criterion '{crit.title}' failed. Execution failed: {record.error}"

            weighted_score_accum += score * crit.weight
            findings.append(
                ReviewFinding(
                    criterion_id=crit.criterion_id,
                    severity=severity,
                    message=msg,
                    score=score,
                )
            )

        overall_score = round(weighted_score_accum / total_weight, 4)

        if overall_score >= 1.0:
            status = ReviewStatus.PASSED
            summary = "Execution satisfied all quality criteria successfully."
        elif overall_score >= 0.5:
            status = ReviewStatus.PARTIAL
            summary = "Execution partially satisfied review criteria."
        elif record.error is not None:
            status = ReviewStatus.ERROR
            summary = f"Execution encountered error during evaluation: {record.error}"
        else:
            status = ReviewStatus.FAILED
            summary = "Execution failed review criteria."

        return ReviewResult(
            review_id=f"rev-{uuid4()}",
            execution_id=execution_id,
            status=status,
            overall_score=overall_score,
            findings=tuple(findings),
            summary=summary,
            metadata=metadata,
        )

    def _evaluate_task_node(
        self,
        task_node: Any,
        record: ExecutionRecord | None,
        criteria: list[ReviewCriterion],
        metadata: dict[str, Any],
    ) -> ReviewResult:
        if task_node is None:
            return ReviewResult(
                review_id=f"rev-{uuid4()}",
                execution_id=None,
                status=ReviewStatus.ERROR,
                overall_score=0.0,
                findings=(
                    ReviewFinding(
                        criterion_id="crit-task-exists",
                        severity=ReviewSeverity.CRITICAL,
                        message="Task node does not exist in task graph.",
                        score=0.0,
                    ),
                ),
                summary="Task review failed: task node not found.",
                metadata=metadata,
            )

        if record is None:
            status = ReviewStatus.PENDING if task_node.status.value == "PENDING" else ReviewStatus.FAILED
            return ReviewResult(
                review_id=f"rev-{uuid4()}",
                execution_id=None,
                status=status,
                overall_score=0.0,
                findings=(
                    ReviewFinding(
                        criterion_id="crit-execution-bound",
                        severity=ReviewSeverity.WARNING,
                        message=f"Task '{task_node.title}' has no completed bound executions (status={task_node.status.value}).",
                        score=0.0,
                    ),
                ),
                summary=f"Task '{task_node.title}' has no execution bindings to evaluate.",
                metadata=metadata,
            )

        return self._evaluate_execution_record(record.execution_id, record, criteria, metadata)

    def _evaluate_plan_aggregate(
        self,
        plan: Any,
        task_reports: list[ReviewReport],
        criteria: list[ReviewCriterion],
        metadata: dict[str, Any],
    ) -> ReviewResult:
        if not task_reports:
            return ReviewResult(
                review_id=f"rev-{uuid4()}",
                execution_id=None,
                status=ReviewStatus.PENDING,
                overall_score=0.0,
                findings=(
                    ReviewFinding(
                        criterion_id="crit-plan-tasks",
                        severity=ReviewSeverity.INFO,
                        message=f"Plan '{plan.plan_id}' has no executable task outputs yet.",
                        score=0.0,
                    ),
                ),
                summary=f"Plan '{plan.plan_id}' review pending execution of plan tasks.",
                metadata=metadata,
            )

        scores = [r.review_result.overall_score for r in task_reports]
        avg_score = round(sum(scores) / len(scores), 4)

        statuses = [r.review_result.status for r in task_reports]
        if all(s == ReviewStatus.PASSED for s in statuses):
            overall_status = ReviewStatus.PASSED
            summary = f"Plan '{plan.plan_id}' fully validated. All {len(task_reports)} tasks passed review."
        elif any(s in (ReviewStatus.FAILED, ReviewStatus.ERROR) for s in statuses):
            overall_status = ReviewStatus.FAILED
            summary = f"Plan '{plan.plan_id}' failed review due to failing task executions."
        else:
            overall_status = ReviewStatus.PARTIAL
            summary = f"Plan '{plan.plan_id}' partially validated."

        findings: list[ReviewFinding] = []
        for rep in task_reports:
            for f in rep.review_result.findings:
                findings.append(f)

        return ReviewResult(
            review_id=f"rev-{uuid4()}",
            execution_id=None,
            status=overall_status,
            overall_score=avg_score,
            findings=tuple(findings),
            summary=summary,
            metadata=metadata,
        )

    def _generate_execution_recommendations(
        self, result: ReviewResult, record: ExecutionRecord
    ) -> list[str]:
        recs = []
        if result.status == ReviewStatus.PASSED:
            recs.append("Execution output satisfies requirement criteria. Proceed to downstream tasks.")
        elif result.status == ReviewStatus.PARTIAL:
            recs.append("Execution output is incomplete. Consider inspecting output metadata.")
        elif result.status in (ReviewStatus.FAILED, ReviewStatus.ERROR):
            recs.append(f"Execution failed with error: {record.error}. Review parameters or provider settings.")
        return recs

    def _generate_task_recommendations(
        self, result: ReviewResult, task_node: Any, record: ExecutionRecord | None
    ) -> list[str]:
        recs = []
        if result.status == ReviewStatus.PASSED:
            recs.append(f"Task '{task_node.title}' validation passed. Task output confirmed ready.")
        elif result.status == ReviewStatus.PENDING:
            recs.append(f"Task '{task_node.title}' is pending execution. Execute task before validation.")
        else:
            recs.append(f"Task '{task_node.title}' validation issue detected. Status: {result.status.value}.")
        return recs

    def _generate_plan_recommendations(
        self, result: ReviewResult, plan: Any, task_reports: list[ReviewReport]
    ) -> list[str]:
        recs = []
        if result.status == ReviewStatus.PASSED:
            recs.append(f"Plan '{plan.plan_id}' fully verified and ready for completion.")
        elif result.status == ReviewStatus.FAILED:
            failed_count = sum(1 for r in task_reports if r.review_result.status == ReviewStatus.FAILED)
            recs.append(f"Plan '{plan.plan_id}' has {failed_count} failing task execution(s). Check task findings.")
        else:
            recs.append(f"Plan '{plan.plan_id}' validation in state {result.status.value}.")
        return recs
