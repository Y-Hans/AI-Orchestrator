# Capability 8 — Result Synthesis Engine

## Overview

The **Result Synthesis Engine** combines validated execution outputs, review reports, artifacts, and long-term memory records into coherent, structured deliverables. It represents the final stage of the orchestration pipeline.

## Architectural Principles

1. **Dedicated Models Module (`synthesis_models.py`)**: All domain models are isolated in `synthesis_models.py`.
2. **Explicit Workspace Ownership**: `TaskWorkspace` owns `synthesis_engine: SynthesisEngine` and `syntheses: dict[str, SynthesisReport]`.
3. **Strong Typing**: APIs use dataclasses (`SynthesisSource`, `SynthesisResult`, `SynthesisReport`) and enums (`SynthesisStatus`, `SynthesisSourceType`).
4. **Dependency Injection**: `SynthesisEngine` accepts an injected `Synthesizer` strategy, defaulting to `DeterministicSynthesizer`.
5. **Read-Only Data Consumption**: Synthesis never mutates task graphs, executions, review reports, artifacts, or memories.
6. **Single Responsibility**: Coordinates collecting inputs, merging inputs, formatting outputs, and producing reports.

## Component Overview

```
Execution Engine ---> Execution Records ---+
Review Engine ------> Review Reports ------|
Artifact Store -----> Artifacts -----------+---> Synthesis Engine ---> Synthesis Report
Memory Engine ------> Memory Records ------|
                                           |
TaskWorkspace -----------------------------+
```

## Strategy: DeterministicSynthesizer

The default synthesizer combines source contents in deterministic order without AI reasoning:
- Preserves ordering of input sources.
- Groups sources into structured sections.
- Computes aggregate metrics and metadata.
- Generates reproducible summaries.

## Core API & MCP Tools

- `synthesize`: Combine explicit parameters or source lists.
- `synthesize_task`: Combine execution outputs, reviews, and artifacts for a single task.
- `synthesize_plan`: Combine outputs across an entire plan.
- `get_synthesis`: Retrieve a stored report by ID.
- `list_syntheses`: List all reports in a workspace.
- `delete_synthesis`: Remove a report from a workspace.
