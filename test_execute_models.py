import time

from brain import AntigravityBrain


def mocked_execute_model(arguments):
    delay = arguments.get("delay", 0)
    if delay:
        time.sleep(delay)

    provider = arguments["provider"]
    if arguments.get("fail"):
        return {
            "ok": False,
            "provider": provider,
            "model": arguments.get("model", "mock-model"),
            "error": "mock_failure",
            "detail": f"{provider} failed",
        }

    return {
        "ok": True,
        "provider": provider,
        "model": arguments.get("model", "mock-model"),
        "text": f"{provider} response",
        "raw": {"mock": True},
    }


def test_execute_models_parallel_execution():
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    started = time.perf_counter()
    payload = brain.execute_many(
        {
            "parallel": True,
            "requests": [
                {"provider": "gemini", "prompt": "one", "delay": 0.2},
                {"provider": "groq", "prompt": "two", "delay": 0.2},
            ],
        }
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.35
    assert [result["provider"] for result in payload["results"]] == ["gemini", "groq"]
    assert all(result["success"] is True for result in payload["results"])


def test_execute_models_sequential_execution():
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    started = time.perf_counter()
    payload = brain.execute_many(
        {
            "parallel": False,
            "requests": [
                {"provider": "gemini", "prompt": "one", "delay": 0.15},
                {"provider": "groq", "prompt": "two", "delay": 0.15},
            ],
        }
    )
    elapsed = time.perf_counter() - started

    assert elapsed >= 0.3
    assert [result["response"] for result in payload["results"]] == [
        "gemini response",
        "groq response",
    ]


def test_execute_models_provider_failure_does_not_stop_remaining_requests():
    brain = AntigravityBrain(execute_model=mocked_execute_model)

    payload = brain.execute_many(
        {
            "parallel": False,
            "requests": [
                {"provider": "gemini", "prompt": "one"},
                {"provider": "groq", "prompt": "two", "fail": True},
                {"provider": "openrouter", "prompt": "three"},
            ],
        }
    )

    assert payload["results"][0]["success"] is True
    assert payload["results"][1]["success"] is False
    assert payload["results"][1]["error"] == {
        "code": "mock_failure",
        "message": "groq failed",
    }
    assert payload["results"][2]["success"] is True
