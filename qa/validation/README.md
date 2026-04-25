# qa / validation

## Purpose
Non-canonical validation and review outputs generated while auditing pipeline artefacts.

Typical contents:
- sampled validation reports
- manual review CSVs
- triaged audit sheets
- text-cleanup audit passes such as `text_cleanup_audit_round1.csv` and `text_cleanup_audit_round2.csv`
- archived historical QA material under `archive/`
- focused pipeline validation packs such as `proceedings_stage05_2026-04-06/`
- focused routing audits such as `missed_proceedings_audit_2026-04-06/`
- spot-check folders
- human-readable text exports under `text_exports/`

These files support QA and adjudication, but they are not canonical pipeline outputs.

The weaker-case CSVs in this folder are the selection source for the subset TXT folders under `text_exports/` and should be regenerated together when the canonical text JSONs change.

## `archive/`

Historical non-canonical QA artefacts that were previously stored in workflow directories such as `data/references/`.

- Keep archived trial runs and spot checks here when they are worth preserving for provenance.
- Do not treat archived files as live registries or current review queues.

## `text_exports/`

Human-readable `.txt` renders of `data/extraction_json/text/{paper_id}.json` for manual inspection.

- `all/`
  - Full corpus export: one TXT per extracted paper.
- `weaker_cases/`
  - TXT exports for papers flagged as weaker or borderline extraction matches that may still need manual review.
- `weaker_text_quality_defects/`
  - Weaker-case TXT exports where the JSON text itself appears degraded.
- `weaker_proceedings_context/`
  - Weaker-case TXT exports where the JSON appears to come from a proceedings or supplement context.
- `weaker_metadata_matching_only/`
  - Weaker-case TXT exports where the JSON looks readable and the weakness is mainly matching or metadata-related.
- `likely_failures/`
  - TXT exports for the currently unresolved extraction failures.

The live folders above should stay current. Superseded snapshot folders should be archived or removed rather than accumulating here.

## `proceedings_stage05_2026-04-06/`

Small real-data verification pack for the updated proceedings trimming and proceedings-QC logic.

- Contains subset outputs for paper IDs `1229`, `12807`, `1605`, and `1793`.
- Includes:
  - `text_trim_registry_subset.csv`
  - `proceedings_text_qc_registry_subset.csv`
  - `text_trimmed/`
- Use this folder as provenance for the 6 April 2026 stage-`05` / stage-`05b` refactor, not as a live registry source.

## `missed_proceedings_audit_2026-04-06/`

Focused audit pack for proceedings-like sources that stage 04 did not currently label `conference_abstract`.

- Contains:
  - an exploratory whole-corpus report and review CSV
  - a smaller reviewed mixed batch under `focused_batch_mixed/`
  - per-paper snippet TXT files for the selected candidates
- Use the focused batch as the current heuristic-check pack while the audit logic is still being calibrated.

## `stage07_xml/`

Human-verification material for Stage 07 XML patient/group assignment.

- Static HTML review rounds and editable response CSVs live under `stage07_xml/gold_standard/<round_id>/`.
- The cumulative reviewed ledger is `stage07_xml/gold_standard/07_xml_assignment_gold_standard.csv`.
- These files are QA evidence only; canonical Stage 07 XML outputs remain under `data/extraction_json/stage07_xml/`.
