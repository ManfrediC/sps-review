# data

Canonical research artefacts and generated data products used by the pipeline.

Bulk source files and generated JSONs are intentionally ignored by git by
default, while selected registries under `data/references/` are tracked.

## Main Subdirectories

- `pdf_original/`: original local PDFs, named with the Covidence `paper_id`
  prefix where available.
- `pdf_annotated/`: future reviewer-facing annotated PDFs with evidence
  highlights.
- `excel/`: reviewer workbooks and tabular extraction outputs.
- `extraction_json/`: machine-readable JSON artefacts from extraction,
  proceedings preparation, case-series splitting, and preliminary downstream
  extraction stages.
- `references/`: canonical CSV/JSON registries and reviewed manual ledgers.

## Key Canonical Artefacts

- `extraction_json/text/{paper_id}.json`: full extracted and cleaned source
  text.
- `extraction_json/text_preclean/`: preserved backups before reviewed cleanup.
- `extraction_json/text_preclean_stage2/`: preserved backups before residual
  stage-2 cleanup.
- `extraction_json/text_trimmed_llm_candidates/`: stage-05 proceedings
  candidate packages.
- `extraction_json/text_trimmed_llm/`: validated stage-05 LLM trim outputs.
- `extraction_json/text_proceedings_ready/`: canonical stage-05 downstream text
  layer for proceedings and safe passthrough abstracts.
- `extraction_json/text_case_series_units/`: current stage-07 per-paper unit
  packages for selected multi-case sources.
- `references/paper_artifact_registry.csv`: cross-stage index of reference,
  PDF, text, proceedings, routing, count, split, and preliminary downstream
  artefacts.
- `references/paper_revisit_registry.csv`: cross-stage list of unresolved
  paper/stage issues.

The older deterministic `extraction_json/text_trimmed/` and historical
`text_case_series_split/` paths may still exist for provenance or fallback
compatibility. The live stage-05 and stage-07 contracts are
`text_proceedings_ready/` and `text_case_series_units/`.
