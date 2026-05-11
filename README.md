# sps-review

This repository supports a systematic review of stiff person spectrum disorder
(SPSD). It links Covidence references to local PDFs, extracts and cleans text,
classifies source type, prepares proceedings abstracts, counts extractable SPSD
cases, and splits multi-case papers before downstream extraction.

The stable join key is `paper_id`, which is the Covidence ID.

## Start Here

- `doc/repo_rules.md`: authoritative local workflow rules, pipeline order, and
  output-location policy.
- `doc/notes/repo_overview_to_stage07.md`: concise collaborator overview of the
  repo through stage 07, including inputs and outputs for each stage.
- `data/references/paper_artifact_registry.csv`: cross-stage index for every
  paper and known artefact path.
- `data/references/paper_revisit_registry.csv`: current list of paper/stage
  issues that still need source, QC, or processing follow-up.

Everything after stage 07 is preliminary. LangExtract, summary, and quality
assessment scripts and outputs exist, but they still need stronger contracts,
validation, and review before they should be treated as final systematic-review
data.

## Repository Layout

- `data/references/`: canonical registries and manual-review ledgers.
- `data/pdf_original/`: local source PDFs, ignored by git except placeholders.
- `data/extraction_json/`: canonical machine-readable text and processing JSONs.
- `results/`: pipeline-produced run traces, manifests, and runtime logs.
- `qa/validation/`: non-canonical validation packs, review sheets, smoke runs,
  and audit material.
- `src/pipelines/`: numbered pipeline entry points.
- `src/validation/`: review, benchmark, audit, and smoke-test utilities.
- `config/`: prompts, schemas, dictionaries, and reviewed extraction controls.
- `examples/`: curated rows used to build few-shot prompt examples.
- `doc/`: repo rules, collaborator notes, methods, plans, and protocol material.
- `tests/`: focused automated tests for pipeline and validation behaviour.

## Current Workflow

The canonical workflow is developed through stage 07:

1. `01_download_covidence_pdfs.py`: download PDFs from Covidence into
   `data/pdf_original/`.
2. `02_build_pdf_source_registry.py`: link reference metadata to local PDFs in
   `data/references/pdf_source_registry.csv`.
3. `03_extract_text.py`: extract page-level text to
   `data/extraction_json/text/`.
4. `03b_clean_text.py`: apply reviewed deterministic cleanup to selected text
   JSONs.
5. `90_screen_text_extraction.py`: optional text-quality triage.
6. `04_source_categorisation_LLM.py`: classify source type and publish
   `data/references/source_categorisation_registry.csv`.
7. `05_trim_proceedings_text_LLM.py`: build proceedings end-candidate packages.
8. `05b_validate_proceedings_text_LLM.py`: validate proceedings trim decisions.
9. `05c_publish_proceedings_ready.py`: publish canonical proceedings-ready text
   under `data/extraction_json/text_proceedings_ready/`.
10. `06_extract_sps_case_counts_hybrid.py`: build stage-06 count run artefacts.
11. `06c_publish_sps_case_count_registry.py`: publish the canonical SPSD case
    count registry.
12. `07_split_case_series.py`: publish attribution-safe units for selected
    multi-case papers.
13. `12_build_paper_artifact_registry.py`: refresh the cross-stage artefact
    registry.
14. `13_build_paper_revisit_registry.py`: refresh the cross-stage revisit list.

Use `src/pipelines/README.md` for the script-by-script map and
`doc/notes/repo_overview_to_stage07.md` when onboarding a collaborator.

## Key Registries

- `data/references/sps_references_export.csv`: upstream Covidence reference
  export.
- `data/references/pdf_source_registry.csv`: reference-to-PDF linkage.
- `data/references/pdf_acquisition_queue.csv`: unresolved PDF acquisition
  backlog.
- `data/references/source_categorisation_registry.csv`: stage-04 routing.
- `data/references/source_categorisation_manual_review.csv`: reviewed routing
  overrides and source-linkage flags.
- `data/references/text_proceedings_ready_registry.csv`: stage-05 publication
  layer for proceedings text.
- `data/references/source_sps_case_count_registry.csv`: canonical stage-06 SPSD
  case counts.
- `data/references/source_sps_case_count_manual_review.csv`: reviewed count
  overrides.
- `data/references/case_series_split_registry.csv`: stage-07 split status and
  output paths.
- `data/references/paper_artifact_registry.csv`: one-row-per-paper artefact
  index across all stages.
- `data/references/paper_revisit_registry.csv`: one-row-per-paper/stage issue
  queue.

## Review Interfaces

Several review utilities use Streamlit for a local browser interface:

- `src/validation/review_stage04_gold_app.py`
- `src/validation/review_stage04_llm_gold_app.py`
- `src/validation/review_stage05_llm_app.py`
- `src/validation/review_stage06_count_app.py`

Run them from the repo root with the project virtual environment active, for
example:

```bash
streamlit run src/validation/review_stage06_count_app.py
```

## Output Policy

- Canonical research artefacts belong under `data/` and `data/references/`.
- Pipeline run traces and generated exports belong under `results/`.
- Non-canonical validation and review material belongs under `qa/validation/`.
- Source PDFs, extracted bulk JSON, Excel workbooks, run logs, and local secrets
  are ignored by git unless explicitly force-added for a curated reason.

## Safety Notes

Use the project virtual environment unless a README says otherwise:

```bash
.\.venv\Scripts\python.exe -m pytest tests -q
```

Do not start paid LLM/API runs without explicit approval. Scripts that can call
paid services normally require an explicit flag such as `--allow-paid-run`.
