# Legacy Stage-05 Deterministic Archive

This archive preserves the older deterministic stage-05 proceedings workflow that was superseded by the live LLM workflow on `2026-04-14`.

Archived here:
- `src/pipelines/05_trim_proceedings_text.py`
- `src/pipelines/05b_validate_proceedings_text.py`
- `qa/trimming/`
  - historical deterministic batch manifests, reports, regression packs, and tranche-verification outputs moved out of the live `qa/trimming/` workspace during repo cleanup on `2026-04-19`

Removed during cleanup:
- deterministic-only validation helpers and tests that were hard-wired to deleted live entrypoints and had become misleading archive clutter

The live stage-05 CLI surface is now:
- `src/pipelines/05_trim_proceedings_text_LLM.py`
- `src/pipelines/05b_validate_proceedings_text_LLM.py`
- `src/pipelines/05c_publish_proceedings_ready.py`

Shared deterministic logic that is still reused by the live LLM workflow remains active in:
- `src/pipelines/_proceedings_trim_deterministic.py`
- `src/pipelines/_proceedings_validate_deterministic.py`
