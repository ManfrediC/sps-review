# data / references

## Purpose
Source metadata exports and generated canonical cross-stage registries keyed by reference or paper ID.

This directory should contain live reference exports, live registries, and current manual-review ledgers only.

Historical trial runs, spot checks, and ad hoc QA snapshots belong under `qa/validation/`, not here.

## Directory Contents Snapshot
- Last updated: `2026-04-27`
- Immediate subdirectories (0): _None_
- Immediate files include canonical pipeline registries and ledgers such as `source_categorisation_registry.csv`, `source_categorisation_manual_review.csv`, `source_sps_case_count_registry.csv`, `source_sps_case_count_manual_review.csv`, `paper_artifact_registry.csv`, `pdf_source_registry.csv`, and proceedings/text-trim registries.

## Stage-06 count registries

- `source_sps_case_count_registry.csv`
  - Canonical stage-`06` SPS-spectrum case-count registry.
  - Current publication is produced by `src/pipelines/06c_publish_sps_case_count_registry.py` from reviewed gold, tracked manual count overrides, hybrid backfill QA rows, and flagged reference-only fallbacks where no run artefact is available.
  - Rows with unresolved provenance or reference-only fallback evidence remain marked with `count_manual_review_required=true`.
- `source_sps_case_count_manual_review.csv`
  - Reviewed count override ledger used by stage `06b` and the stage `06c` publish step.

## Cross-stage revisit registry

- `paper_revisit_registry.csv`
  - Canonical cross-stage list of paper/stage issues that need source, QC, or processing follow-up.
  - Built by `src/pipelines/13_build_paper_revisit_registry.py` from acquisition queues, proceedings trim/QC ledgers, source-categorisation review state, stage-06 count review state, and case-series split status.
  - Contains one row per paper/stage issue, so a paper may appear more than once when multiple stages need attention.
- `paper_revisit_registry.summary.json`
  - Machine-readable count summary by stage and severity for the current revisit registry.

## Proceedings registries

- `text_trim_registry.csv`
  - Canonical stage-`05` proceedings trimming ledger.
  - Records proceedings detection, chosen trim mode, matched title/code, and start/end page and line anchors for the selected span.
- `proceedings_text_qc_registry.csv`
  - Canonical stage-`05b` proceedings QC ledger.
  - Records whether the preferred proceedings text is safe to use downstream, including boundary-aware statuses such as `confirmed_full`, `partial_truncated`, `header_only_source`, `spillover_detected`, `mismatch`, and `untrimmed_localised`.
