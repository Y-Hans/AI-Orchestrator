from brain import AntigravityBrain
from execution_binding import ExecutionType, ExecutionBinding, TaskExecutionIndex
from workspace import workspace_store
import pytest


def mocked_execute_model(arguments):
    provider = arguments["provider"]
    return {
        "ok": True,
        "provider": provider,
        "model": arguments.get("model", "mock-model"),
        "text": f"{provider} response",
        "raw": {"mock": True},
    }


def test_binding_one_execution():
    workspace = workspace_store.create_workspace()
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    task = workspace.task_graph.create_task(title="Task A")

    payload = brain.execute(
        {
            "workspace_id": workspace.workspace_id,
            "task_id": task.task_id,
            "provider": "gemini",
            "model": "gemini-1.5-flash",
            "prompt": "hello",
            "execution_type": "REVIEW",
        }
    )

    assert payload["ok"] is True
    # The workspace should have exactly 1 execution record
    assert len(workspace.executions) == 1
    execution_record = workspace.executions[0]

    # Check that it bound the execution to the task
    bindings = workspace.task_execution_index.get_task_executions(task.task_id)
    assert len(bindings) == 1
    binding = bindings[0]

    assert binding.task_id == task.task_id
    assert binding.execution_id == execution_record.execution_id
    assert binding.execution_type == ExecutionType.REVIEW
    assert binding.created_at

    # Verify no provider or model field on binding
    assert not hasattr(binding, "provider")
    assert not hasattr(binding, "model")

    # Verify lookups
    assert workspace.task_execution_index.get_execution(execution_record.execution_id) == binding


def test_binding_multiple_executions():
    workspace = workspace_store.create_workspace()
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    task = workspace.task_graph.create_task(title="Task A")

    payload = brain.execute_many(
        {
            "workspace_id": workspace.workspace_id,
            "task_id": task.task_id,
            "requests": [
                {"provider": "gemini", "prompt": "first"},
                {"provider": "groq", "prompt": "second"},
            ],
            "execution_type": "PARALLEL",
        }
    )

    assert len(payload["results"]) == 2
    assert len(workspace.executions) == 2

    # Check bindings
    bindings = workspace.task_execution_index.get_task_executions(task.task_id)
    assert len(bindings) == 2

    assert bindings[0].task_id == task.task_id
    assert bindings[0].execution_type == ExecutionType.PARALLEL

    assert bindings[1].task_id == task.task_id
    assert bindings[1].execution_type == ExecutionType.PARALLEL

    # Verify we can list all bindings
    all_bindings = workspace.task_execution_index.list_bindings()
    assert len(all_bindings) == 2


def test_multiple_providers_attached_to_one_task():
    workspace = workspace_store.create_workspace()
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    task = workspace.task_graph.create_task(title="Task A")

    # First call with Gemini
    brain.execute(
        {
            "workspace_id": workspace.workspace_id,
            "task_id": task.task_id,
            "provider": "gemini",
            "prompt": "one",
            "execution_type": "PRIMARY",
        }
    )

    # Second call with Groq
    brain.execute(
        {
            "workspace_id": workspace.workspace_id,
            "task_id": task.task_id,
            "provider": "groq",
            "prompt": "two",
            "execution_type": "VALIDATION",
        }
    )

    bindings = workspace.task_execution_index.get_task_executions(task.task_id)
    assert len(bindings) == 2

    execution_ids = {b.execution_id for b in bindings}
    assert len(execution_ids) == 2

    types = {b.execution_type for b in bindings}
    assert types == {ExecutionType.PRIMARY, ExecutionType.VALIDATION}


def test_removing_bindings():
    workspace = workspace_store.create_workspace()
    index = workspace.task_execution_index

    binding = index.bind_execution(
        task_id="task-1",
        execution_id="exec-1",
        execution_type=ExecutionType.PRIMARY,
    )

    assert len(index.list_bindings()) == 1
    assert index.get_execution("exec-1") == binding

    # Remove the binding
    index.remove_binding(binding.binding_id)

    assert len(index.list_bindings()) == 0
    assert index.get_execution("exec-1") is None

    # Removing non-existent binding should raise KeyError
    with pytest.raises(KeyError):
        index.remove_binding("invalid-binding-id")


def test_retrieving_task_executions():
    workspace = workspace_store.create_workspace()
    index = workspace.task_execution_index

    # Bind some executions to different tasks
    index.bind_execution(task_id="task-1", execution_id="exec-1", execution_type="PRIMARY")
    index.bind_execution(task_id="task-1", execution_id="exec-2", execution_type="REVIEW")
    index.bind_execution(task_id="task-2", execution_id="exec-3", execution_type="PRIMARY")

    # Retrieve for task-1
    task_1_executions = index.get_task_executions("task-1")
    assert len(task_1_executions) == 2
    assert {e.execution_id for e in task_1_executions} == {"exec-1", "exec-2"}

    # Retrieve for task-2
    task_2_executions = index.get_task_executions("task-2")
    assert len(task_2_executions) == 1
    assert task_2_executions[0].execution_id == "exec-3"

    # Retrieve for non-existent task should be empty
    assert index.get_task_executions("task-none") == []
