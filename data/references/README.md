# data / references

## Purpose
Source metadata exports and generated canonical cross-stage registries keyed by reference or paper ID.

This directory should contain live reference exports, live registries, and current manual-review ledgers only.

Historical trial runs, spot checks, and ad hoc QA snapshots belong under `qa/validation/`, not here.

## Directory Contents Snapshot
- Last updated: `2026-04-06`
- Immediate subdirectories (0): _None_
- Immediate files (11, excluding `README.md`): `case_series_split_registry.csv`, `paper_artifact_registry.csv`, `pdf_acquisition_queue.csv`, `pdf_source_registry.csv`, `proceedings_manual_review_queue.csv`, `proceedings_text_qc_registry.csv`, `source_categorisation_manual_review.csv`, `source_categorisation_registry.csv`, `sps_references_export.csv`, `sps_references_export.ris`, `text_trim_registry.csv`

## Proceedings registries

- `text_trim_registry.csv`
  - Canonical stage-`05` proceedings trimming ledger.
  - Records proceedings detection, chosen trim mode, matched title/code, and start/end page and line anchors for the selected span.
- `proceedings_text_qc_registry.csv`
  - Canonical stage-`05b` proceedings QC ledger.
  - Records whether the preferred proceedings text is safe to use downstream, including boundary-aware statuses such as `confirmed_full`, `partial_truncated`, `header_only_source`, `spillover_detected`, `mismatch`, and `untrimmed_localised`.
