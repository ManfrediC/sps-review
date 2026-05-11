# src / validation

Review apps, benchmark tools, smoke runners, and audit utilities for checking
pipeline artefacts against source evidence.

These scripts are separate from `src/pipelines/`: pipelines build canonical
outputs under `data/`, while validation scripts produce non-canonical review
material under `qa/validation/` or focused QA workspaces such as `qa/trimming/`.

Several review interfaces use Streamlit.

## General Audit Utilities

- `validate_pdf_source_registry.py`: samples rows from
  `data/references/pdf_source_registry.csv` and checks title/author/year
  signals against the local PDF or extracted text.
- `validate_text_extraction_quality.py`: builds stratified manual-review samples
  for extracted text quality.
- `export_text_json_to_txt.py`: renders `data/extraction_json/text/{paper_id}.json`
  as reviewer-friendly TXT packets under `qa/validation/text_exports/`.
- `find_missed_proceedings_candidates.py`: builds review queues for proceedings
  fragments that stage 04 did not label as `conference_abstract`.

Example:

```bash
python src/validation/validate_pdf_source_registry.py --sample-size 20 --output-path qa/validation/pdf_source_registry_validation.json
```

## Stage 04 Review And Benchmarking

- `build_source_categorisation_review_sample.py`: builds stratified manual
  source-routing review samples.
- `build_stage04_gold_batch.py`: creates reproducible stage-04 gold-standard
  review rounds.
- `review_stage04_gold_app.py`: Streamlit reviewer for stage-04 gold rounds.
- `build_stage04_llm_gold_batch.py`: creates LLM stage-04 category/count review
  rounds.
- `review_stage04_llm_gold_app.py`: Streamlit reviewer for the LLM category and
  count rounds.
- `benchmark_stage04_gold.py`: scores source/category logic against reviewed
  gold rows.
- `stage04_model_benchmark/`: isolated cross-model stage-04 benchmark workflow.

Run a browser review interface:

```bash
streamlit run src/validation/review_stage04_gold_app.py
```

## Stage 05 Proceedings Review

- `manage_trimming_batches.py`: prepares or resumes live proceedings-trimming
  QA batches under `qa/trimming/`.
- `review_stage05_llm_app.py`: Streamlit inspector for candidate, final, and
  proceedings-ready stage-05 outputs.
- `update_trimming_review_outputs.py`: refreshes batch-local review queue,
  feedback, override, and acceptance outputs.
- `apply_trimming_manual_overrides.py`: applies reviewed fallback span overrides
  for residual stage-05 failures.
- `evaluate_trimming_feedback.py`: evaluates trimming feedback and regression
  packs.

Run:

```bash
python src/validation/manage_trimming_batches.py
streamlit run src/validation/review_stage05_llm_app.py
```

## Stage 06 Count Review

- `review_stage06_count_app.py`: Streamlit review workflow for stage-06 count
  decisions; it can write reviewed responses into
  `data/references/source_sps_case_count_manual_review.csv`.
- `build_stage06_backfill_campaign.py`: builds the stage-06 hybrid backfill
  inventory and batch manifests.
- `run_stage06_backfill_batch.py`: runs or resumes one stage-06 backfill batch
  and rebuilds its QA pack.
- `bootstrap_stage06_gold_json.py`: builds per-paper stage-06 gold JSONs from
  reviewed cumulative gold rows.
- `benchmark_stage06_hybrid.py`: scores stage-06 workflow CSVs or the canonical
  registry against reviewed gold.

Run:

```bash
streamlit run src/validation/review_stage06_count_app.py
python src/validation/benchmark_stage06_hybrid.py --workflow canonical=data/references/source_sps_case_count_registry.csv
```

## Stage 07 Smoke And Review Packs

- `run_stage07_smoke.py`: selects finalised multi-case papers, runs
  `src/pipelines/07_split_case_series.py` into an isolated smoke folder, and
  builds a review pack.
- `_stage07_review.py`: shared helpers for combined stage-07 QA CSVs, inspection
  Markdown, and review-comment scaffolds.

Smoke outputs belong under `qa/validation/stage07_smoke/{run_id}/`. Local smoke
folders are ignored by git by default; force-add only curated packs that are
intended as provenance.

Run a heuristics-only smoke test:

```bash
python src/validation/run_stage07_smoke.py --adjudication-model disabled
```

## Output Policy

- Canonical registries and data products belong under `data/`.
- Pipeline traces and manifests belong under `results/`.
- Validation reports, review sheets, smoke runs, and audit packs belong under
  `qa/validation/` or `qa/trimming/`.
- Do not start paid LLM/API runs without explicit approval and the required
  script flag.
