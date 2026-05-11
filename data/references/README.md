# data / references

Live reference metadata, canonical cross-stage registries, and reviewed
manual-review ledgers keyed by `paper_id`.

Historical trial runs, spot checks, and ad hoc QA snapshots belong under
`qa/validation/`, not here.

## Core Metadata

- `sps_references_export.csv`: upstream Covidence reference export.
- `sps_references_export.ris`: upstream RIS export when present.
- `pdf_source_registry.csv`: reference-to-PDF linkage built by stage 02.
- `pdf_acquisition_queue.csv`: unresolved local PDF acquisition backlog.

## Source Text And Proceedings

- `text_screening_registry.csv`: optional stage-90 text-quality screening
  output.
- `text_trim_llm_candidate_registry.csv`: stage-05 candidate-generation
  registry for proceedings end-boundary options.
- `text_trim_llm_registry.csv`: stage-05b validated LLM trim registry.
- `text_proceedings_ready_registry.csv`: stage-05c publication registry for the
  canonical proceedings-ready text layer.
- `text_trim_registry.csv` and `proceedings_text_qc_registry.csv`: legacy
  deterministic proceedings-trim/QC registries retained for provenance and
  compatibility.

## Routing And Counts

- `source_categorisation_registry.csv`: canonical stage-04 routing registry.
- `source_categorisation_manual_review.csv`: reviewed routing overrides and
  source-linkage flags such as `incorrect_reference`.
- `source_sps_case_count_registry.csv`: canonical stage-06 SPSD case-count
  registry.
- `source_sps_case_count_manual_review.csv`: reviewed stage-06 count override
  ledger used by stage 06b/06c.

## Stage 07

- `case_series_split_registry.csv`: stage-07 split status, publication decision,
  and output pointers for reviewed multi-case papers.

## Cross-Stage Indexes

- `paper_artifact_registry.csv`: one row per paper, with paths and status fields
  for reference metadata, PDF, extracted text, proceedings-ready text, stage-04
  routing, stage-06 count, stage-07 split, and preliminary downstream outputs.
  Rebuild with:

```bash
python src/pipelines/12_build_paper_artifact_registry.py
```

- `paper_revisit_registry.csv`: one row per unresolved paper/stage issue, built
  from acquisition queues, proceedings review state, source-linkage problems,
  count review state, and stage-07 split status.
- `paper_revisit_registry.summary.json`: machine-readable summary of the revisit
  queue.

Refresh after registry, QC, or manual-ledger changes:

```bash
python src/pipelines/13_build_paper_revisit_registry.py
```
