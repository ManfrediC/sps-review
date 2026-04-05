# qa / validation

## Purpose
Non-canonical validation and review outputs generated while auditing pipeline artefacts.

Typical contents:
- sampled validation reports
- manual review CSVs
- triaged audit sheets
- text-cleanup audit passes such as `text_cleanup_audit_round1.csv` and `text_cleanup_audit_round2.csv`
- archived historical QA material under `archive/`
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
