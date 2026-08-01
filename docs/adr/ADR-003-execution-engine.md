# ADR-003: Provider-Decoupled ExecutionEngine via Injected Callable

## Context
Task execution requires calling external AI provider SDKs or HTTP APIs (Gemini, Groq, OpenRouter, Ollama). Hardcoding provider API calls into the task execution coordinator couples core orchestration logic to specific vendor SDKs, breaking testability and flexibility.

## Decision
We decided that `ExecutionEngine` ([execution_engine.py](file:///c:/Users/user/AI-Orchestrator/execution_engine.py)) accepts an injected executor callable `(arguments: dict) -> ExecutionResult` at construction time.

Key aspects:
- `ExecutionEngine` does not import provider SDKs or route model requests.
- `AntigravityBrain` provides a thin adapter function `_build_executor()` converting raw execution payloads into normalized `ExecutionResult` dataclasses.
- `ExecutionEngine` manages state transitions (`RUNNING` → `COMPLETED`/`FAILED`), attempts counter, latency timing, execution log recording, and index binding.

## Consequences
### Positive
- **Zero Provider Coupling**: `ExecutionEngine` remains purely generic and vendor-agnostic.
- **Trivial Mocking**: Unit tests pass mock callables without hitting real network endpoints.
- **Flexible Adapter Pattern**: Custom adapters can wrap any executor API (local models, remote services, mock functions).

### Negative
- Requires passing executor configuration via workspace wiring (`workspace.configure_executor(fn)`).

## Alternatives Considered
- **Direct SDK Dependencies**: Hardcoding `google.generativeai` or `openai` inside `ExecutionEngine`. Rejected due to tight vendor coupling.
- **Provider Inheritance Tree**: Abstract `BaseProviderEngine` subclasses for each provider. Rejected as over-engineered compared to callable dependency injection.
