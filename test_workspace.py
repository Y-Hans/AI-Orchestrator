from brain import AntigravityBrain
from workspace import workspace_store, workspace_to_dict


def mocked_execute_model(arguments):
    provider = arguments["provider"]
    return {
        "ok": True,
        "provider": provider,
        "model": arguments.get("model", "mock-model"),
        "text": f"{provider} response",
        "raw": {"mock": True},
    }


def test_workspace_creation():
    workspace = workspace_store.create_workspace(title="Demo", metadata={"source": "test"})

    assert workspace.workspace_id
    assert workspace.created_at
    assert workspace.title == "Demo"
    assert workspace.metadata == {"source": "test"}
    assert workspace.executions == []


def test_execute_model_stores_execution_record():
    workspace = workspace_store.create_workspace()
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    payload = brain.execute(
        {
            "workspace_id": workspace.workspace_id,
            "provider": "gemini",
            "model": "mock-gemini",
            "prompt": "hello",
        }
    )

    stored = workspace_store.get_workspace(workspace.workspace_id)
    assert payload["ok"] is True
    assert len(stored.executions) == 1
    assert stored.executions[0].provider == "gemini"
    assert stored.executions[0].model == "mock-gemini"
    assert stored.executions[0].prompt == "hello"
    assert stored.executions[0].success is True
    assert stored.executions[0].response == "gemini response"


def test_execute_models_stores_multiple_execution_records():
    workspace = workspace_store.create_workspace()
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    payload = brain.execute_many(
        {
            "workspace_id": workspace.workspace_id,
            "requests": [
                {"provider": "gemini", "prompt": "one"},
                {"provider": "groq", "prompt": "two"},
            ],
        }
    )

    stored = workspace_store.get_workspace(workspace.workspace_id)
    assert [result["provider"] for result in payload["results"]] == ["gemini", "groq"]
    assert len(stored.executions) == 2
    assert [record.provider for record in stored.executions] == ["gemini", "groq"]
    assert [record.prompt for record in stored.executions] == ["one", "two"]


def test_retrieving_workspace_includes_execution_records():
    workspace = workspace_store.create_workspace(title="Retrieve me")
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    brain.execute({"workspace_id": workspace.workspace_id, "provider": "openrouter", "prompt": "hello"})

    payload = workspace_to_dict(workspace_store.get_workspace(workspace.workspace_id))
    assert payload["workspace_id"] == workspace.workspace_id
    assert payload["title"] == "Retrieve me"
    assert payload["executions"][0]["provider"] == "openrouter"
    assert payload["executions"][0]["success"] is True
