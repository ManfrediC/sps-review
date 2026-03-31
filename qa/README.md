# qa

## Purpose
Non-canonical quality-assurance and review material.

This folder is for validation packs, spot checks, manual review sheets, and other audit outputs that help assess pipeline artefacts but are not themselves canonical research outputs.

## Structure
- `validation/`
  - machine-readable validation reports
  - CSV review sheets
  - spot-check folders, text-cleanup audits, and ad hoc audit summaries

Human-readable `.txt` exports under `qa/validation/text_exports/` are generated from canonical JSONs for review convenience and are ignored in git.

## Policy
- Do not store canonical pipeline artefacts here.
- Canonical intermediate and final artefacts belong under `data/`.
- Canonical pipeline-produced exports and runtime logs belong under `results/`.
