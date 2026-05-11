# qa / validation

Non-canonical validation and review outputs generated while auditing pipeline
artefacts.

These files support QA and adjudication, but they are not canonical pipeline
outputs.

## Typical Contents

- sampled validation reports and manual review CSVs
- text-cleanup audit passes
- focused proceedings and routing audits
- stage-06 calibration, backfill, benchmark, and review material
- stage-07 smoke runs and review packs
- spot-check folders
- human-readable text exports under `text_exports/`
- archived historical QA material under `archive/`

## Important Folders

- `text_exports/`: TXT renders of `data/extraction_json/text/{paper_id}.json`
  for manual inspection.
- `stage06_llm/`: non-canonical stage-06 calibration, backfill, benchmark, and
  publish-evidence artefacts.
- `stage07_smoke/`: isolated stage-07 smoke-run outputs. Local smoke folders are
  ignored by git by default; force-add only curated packs.
- `source_categorisation/gold_standard/`: reviewed stage-04 source-category and
  stage-06 count gold corpus.
- `archive/`: historical QA artefacts that should not be treated as live
  registries or current review queues.

## Text Exports

`text_exports/` is generated from canonical text JSONs and should be refreshed
when the canonical text layer changes.

Common subsets:

- `all/`: one TXT per extracted paper.
- `weaker_cases/`: papers flagged for weaker or borderline extraction matches.
- `weaker_text_quality_defects/`: weaker cases with degraded JSON text.
- `weaker_proceedings_context/`: weaker cases from proceedings or supplement
  contexts.
- `weaker_metadata_matching_only/`: readable text with mostly metadata or
  matching uncertainty.
- `likely_failures/`: currently unresolved extraction failures.

Superseded snapshot folders should be archived or removed rather than allowed
to accumulate as live-looking material.

## Historical Packs

- `proceedings_stage05_2026-04-06/`: provenance for the 6 April 2026 stage-05
  / stage-05b refactor.
- `missed_proceedings_audit_2026-04-06/`: focused audit pack for
  proceedings-like sources missed by stage 04.

Use `data/references/paper_revisit_registry.csv` for the current cross-stage
follow-up queue.
