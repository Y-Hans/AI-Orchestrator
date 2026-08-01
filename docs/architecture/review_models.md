# Review Models

Located in `review_models.py`.

## Data Models

- **`ReviewStatus`**: Enum (`PENDING`, `PASSED`, `FAILED`, `PARTIAL`, `ERROR`)
- **`ReviewSeverity`**: Enum (`INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- **`ReviewCriterion`**: Dataclass (`criterion_id`, `title`, `description`, `weight`, `metadata`)
- **`ReviewFinding`**: Dataclass (`criterion_id`, `severity`, `message`, `score`, `metadata`)
- **`ReviewResult`**: Immutable dataclass (`@dataclass(frozen=True)`) containing `review_id`, `execution_id`, `status`, `overall_score`, `findings`, `summary`, `metadata`.
- **`ReviewReport`**: Dataclass containing `report_id`, `review_result`, `workspace_id`, `task_id`, `execution_id`, `plan_id`, `recommendations`, `created_at`, `metadata`.
