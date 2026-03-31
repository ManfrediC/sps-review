# qa / validation

## Purpose
Non-canonical validation and review outputs generated while auditing pipeline artefacts.

Typical contents:
- sampled validation reports
- manual review CSVs
- triaged audit sheets
- spot-check folders
- human-readable text exports under `text_exports/`

These files support QA and adjudication, but they are not canonical pipeline outputs.

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

Historical folders may also appear here when a generated export set is preserved before cleanup or reclassification.
