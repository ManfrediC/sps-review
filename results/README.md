# results

Pipeline-produced exports, run traces, manifests, and runtime logs.

Non-canonical validation packs, review sheets, spot checks, and smoke review
material belong under `qa/validation/`.

## Common Subdirectories

- `exports/`: generated exports intended for downstream consumption.
- `stage04_llm_runs/`: resumable stage-04 LLM routing checkpoints.
- `stage06_count_runs/`: stage-06 hybrid count run artefacts.
- `stage06_count_llm_runs/`: calibration artefacts for the QA-only LLM count
  runner, when present.
- `stage07_unit_manifests/`: run-scoped stage-07 unit manifests.
- `overnight/`: orchestration logs and stage status from `99_overnight_run.py`.

Only promote a result into `data/` through the appropriate pipeline publication
step. Do not treat run traces as canonical registries.
