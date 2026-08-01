# Result Synthesis Architecture

## Overview

The Result Synthesis Engine manages the aggregation and formatting of execution outcomes, review evaluations, artifacts, and long-term memories into final deliverables.

## Component Responsibilities

### `SynthesisEngine`
- Orchestrates input data collection across `TaskWorkspace` storage sub-systems.
- Invokes the configured `Synthesizer` implementation.
- Creates and stores `SynthesisReport` objects in `workspace.syntheses`.

### `Synthesizer` (Interface)
- Abstract base class for output synthesis strategies.
- Accepts title, source references, input data dictionary, and metadata.
- Returns an immutable `SynthesisResult`.

### `DeterministicSynthesizer`
- Default strategy that formats and combines input sources sequentially.
- Generates deterministic metadata (counts by source type, totals).

## Workspace Integration

`TaskWorkspace` initializes `synthesis_engine` upon creation:

```python
self.syntheses: dict[str, SynthesisReport] = {}
self.synthesis_engine = SynthesisEngine(workspace=self)
```

`workspace_to_dict` includes all stored synthesis reports under `"syntheses"`.
