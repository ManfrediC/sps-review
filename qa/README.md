# qa

Non-canonical quality-assurance and review material.

This folder is for validation packs, spot checks, manual review sheets, smoke
runs, and audit outputs that help assess pipeline artefacts. It is not the home
for canonical research outputs.

## Main Areas

- `validation/`: validation reports, review CSVs, smoke runs, text exports, and
  focused audit packs.
- `trimming/`: live stage-05 proceedings-trimming review batches, feedback,
  regression packs, and reports.

## Current Conventions

- Human-readable TXT exports under `qa/validation/text_exports/` are generated
  from canonical JSONs for review convenience and are ignored in git.
- Stage-07 smoke runs live under `qa/validation/stage07_smoke/{run_id}/` and
  are ignored by default unless a curated pack is explicitly force-added.
- Stage-06 calibration and backfill QA material lives under
  `qa/validation/stage06_llm/`.

## Policy

- Canonical data and registries belong under `data/`.
- Pipeline-produced run traces and manifests belong under `results/`.
- Ad hoc validation, review, smoke, and audit material belongs here.
