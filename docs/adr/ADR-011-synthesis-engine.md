# ADR-011: Result Synthesis Engine Architecture

## Status

Approved

## Context

The system required a dedicated pipeline stage to aggregate, merge, format, and summarize execution outputs, review reports, artifacts, and long-term memory records into coherent user deliverables.

## Decision

1. **Dedicated Data Models**: Create `synthesis_models.py` with strongly typed dataclasses and enums (`SynthesisStatus`, `SynthesisSourceType`, `SynthesisSource`, `SynthesisResult`, `SynthesisReport`).
2. **Explicit Workspace Ownership**: `TaskWorkspace` owns `synthesis_engine: SynthesisEngine` and `syntheses: dict[str, SynthesisReport]`.
3. **Dependency Injection & Strategy Pattern**: `SynthesisEngine` accepts an injected `Synthesizer` interface, defaulting to `DeterministicSynthesizer`.
4. **Read-Only Data Consumption**: Synthesis never mutates execution history, review reports, task graphs, artifacts, or memories.
5. **Deterministic Default Strategy**: `DeterministicSynthesizer` combines inputs sequentially without AI reasoning, preparing extension points for future AI synthesizers.

## Consequences

- Clean separation between execution/review logic and result formatting.
- Synthesis reports are immutable and persistent within `TaskWorkspace`.
- Full backward compatibility across existing Capabilities 1–7.
