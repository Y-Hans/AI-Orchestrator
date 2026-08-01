# Synthesis Data Models

All models are defined in `synthesis_models.py`.

## Enums

### `SynthesisStatus`
- `PENDING`: Synthesis initiated but not finished.
- `COMPLETED`: Synthesis successfully completed.
- `FAILED`: Synthesis encountered an error.

### `SynthesisSourceType`
- `EXECUTION`: Output from an execution record.
- `REVIEW`: Finding or evaluation from a review report.
- `ARTIFACT`: File or object from the artifact store.
- `MEMORY`: Record from the long-term memory engine.

## Dataclasses

### `SynthesisSource`
- `source_type`: `SynthesisSourceType`
- `source_id`: `str`
- `title`: `str`
- `metadata`: `dict[str, Any]`

### `SynthesisResult` (Frozen)
- `synthesis_id`: `str`
- `title`: `str`
- `summary`: `str`
- `content`: `Any`
- `metadata`: `dict[str, Any]`

### `SynthesisReport`
- `report_id`: `str`
- `workspace_id`: `str`
- `status`: `SynthesisStatus`
- `result`: `SynthesisResult | None`
- `sources`: `list[SynthesisSource]`
- `created_at`: `str`
- `metadata`: `dict[str, Any]`
