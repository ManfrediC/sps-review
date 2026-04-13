# Stage-05 Officialisation And Retirement Plan

## Goal

Promote the LLM proceedings workflow to the official stage-05 path, keep one canonical downstream text layer, and retire superseded deterministic and experimental stage-05 variants to legacy.

## Current State

- Canonical downstream proceedings text now lives in `data/extraction_json/text_proceedings_ready/`.
- Canonical publication registry now lives in `data/references/text_proceedings_ready_registry.csv`.
- The current live LLM flow is:
  - `src/pipelines/05_trim_proceedings_text_LLM.py`
  - `src/pipelines/05b_validate_proceedings_text_LLM.py`
  - `src/pipelines/05c_publish_proceedings_ready.py`
- Downstream consumers already prefer the proceedings-ready layer.

## Recommended End State

- `src/pipelines/05_trim_proceedings_text.py`
  becomes the current LLM candidate builder.
- `src/pipelines/05b_validate_proceedings_text.py`
  becomes the current LLM validator.
- `src/pipelines/05c_publish_proceedings_ready.py`
  remains a required publication step.
- `data/extraction_json/text_proceedings_ready/`
  becomes the only stage-05 output consumed downstream.
- `data/extraction_json/text_trimmed/`
  remains provenance-only during transition, then becomes legacy.

## Proposed Phases

### Phase 1: Freeze The Canonical Contract

- Treat `text_proceedings_ready/` as the only downstream-facing proceedings text layer.
- Document that `text_trimmed/` and `text_trimmed_llm/` are intermediate or legacy layers, not downstream interfaces.
- Add an explicit note that gold-standard reviewed JSONs and LLM-validated outputs are both acceptable stage-05 sources.

### Phase 2: Officialise The LLM Scripts

- Rename or swap in the LLM scripts as the official stage-05 entry points.
- Preserve the current deterministic scripts under `legacy/stage_05_deterministic/`.
- Preserve CLI compatibility where practical, or document the changed interface in one place.

### Phase 3: Close The Remaining Gaps

- Decide how `candidate_not_needed` papers should be represented in the final stage-05 registry.
- Recommended change:
  - teach `05b_validate_proceedings_text.py` to emit a final row for accepted passthrough papers, for example `full_text_passthrough_llm_accepted`
  - publish those papers as explicitly LLM-accepted rather than generic `source_text_passthrough`
- Decide how to handle persistent validator failures like `11109`.
- Recommended change:
  - support one explicit manual-resolution path that writes a reviewed final stage-05 row rather than silently falling back to `legacy_trimmed`

### Phase 4: Retire Legacy Outputs

- Stop treating `data/extraction_json/text_trimmed/` as a live fallback once all remaining legacy rows have been replaced.
- Keep the directory for provenance until a later archive pass.
- Remove legacy fallback branches from `05c_publish_proceedings_ready.py` only after the final legacy count reaches zero.

### Phase 5: Final Clean-Up

- Update README and pipeline docs to describe only the official stage-05 route.
- Move superseded tests for deterministic-only stage-05 behaviour into `legacy/` or delete them if they no longer protect live behaviour.
- Remove references to parallel stage-05 variants from active docs.

## Acceptance Criteria

- Every proceedings-like paper resolves to one of:
  - `gold_manual`
  - `llm_validated`
  - `llm_decision_rebuilt`
  - an explicitly LLM-accepted passthrough status
- No live downstream script reads `data/extraction_json/text_trimmed/`.
- No live pipeline doc points users to the retired deterministic stage-05 scripts.
- Legacy stage-05 scripts and tests are archived under `legacy/`.

## Immediate Next Actions

1. Add a final accepted status for `candidate_not_needed` papers in the LLM validation/publication path.
2. Resolve `11109`, which still falls back to `legacy_trimmed` after invalid LLM output.
3. Once those are done, swap the LLM scripts into the official `05` and `05b` filenames.
