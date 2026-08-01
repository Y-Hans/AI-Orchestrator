# Review Engine Architecture

## Overview
`ReviewEngine` coordinates evaluation workflows for execution records, task nodes, task batches, and plans.

## Key Components

### `ReviewEngine`
Located in `review_engine.py`. Primary methods:
- `review_execution(execution_id, criteria, reviewer, metadata)`
- `review_task(task_id, criteria, reviewer, metadata)`
- `review_tasks(task_ids, criteria, reviewer, metadata)`
- `review_plan(plan_id, criteria, reviewer, metadata)`
- `get_review(report_id)`
- `list_reviews()`

### Injected Reviewer Callable
Receives execution/task details and returns `ReviewResult`. Allows injecting custom evaluation logic or external verifiers without modifying `ReviewEngine`.
