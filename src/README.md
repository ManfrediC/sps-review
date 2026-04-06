# `src` Overview

This folder contains the project pipeline scripts, validation utilities, and shared code. They are designed to be run from the repository root and operate on the data stored under `data/`.

Validation scripts should write their non-canonical review and audit outputs under `qa/validation/`, not `data/` or `results/`.

## Pipeline Order

1. `pipelines/01_download_covidence_pdfs.py`
   - Downloads source PDFs from the Covidence extraction view into `data/pdf_original/`.
   - Uses local/browser session state plus Covidence credentials.

2. `pipelines/02_build_pdf_source_registry.py`
   - Builds `data/references/pdf_source_registry.csv`.
   - Links each Covidence reference to its downloaded PDF path and download metadata.
   - Also refreshes `data/references/pdf_acquisition_queue.csv` for the remaining references with no local PDF.

3. `pipelines/03_extract_text.py`
   - Extracts page-level text from the downloaded PDFs.
   - Uses native PDF text first, then falls back to OCR when the extracted text is sparse or corrupted.
   - Honors reviewed per-paper overrides from `config/extraction/text_extraction_overrides.csv` for a small number of known corpus-specific PDFs.
   - Writes `data/extraction_json/text/{paper_id}.json`.

4. `pipelines/03b_clean_text.py`
   - Applies deterministic text cleanup only to the reviewed subset of paper IDs listed in `config/extraction/text_cleanup_overrides.csv`.
   - Supports reviewed per-paper source strategies such as `json_cleanup` and `pdftotext_cleanup`.
   - Preserves the original extracted JSON for each cleaned paper under `data/extraction_json/text_preclean/{paper_id}.json`.
   - Overwrites the final canonical cleaned JSON in `data/extraction_json/text/{paper_id}.json`.
   - Also owns the reviewed residual rescue path via `--stage2`, using `config/extraction/text_cleanup_stage2_overrides.csv`, `config/extraction/text_cleanup_stage2_substitutions.csv`, and backups in `data/extraction_json/text_preclean_stage2/{paper_id}.json`.

5. `pipelines/04_source_categorisation_LLM.py`
   - Runs the canonical LLM-based stage-04 routing flow.
   - Jointly predicts source category and extractable SPS case count from the same LLM pass.
   - Checkpoints per-paper results under `results/stage04_llm_runs/{run_id}/`, supports resume, and requires explicit approval before paid LLM calls.
   - Publishes `data/references/source_categorisation_registry.csv` and `data/references/source_sps_case_count_registry.csv` only after a complete run.
   - Refreshes `data/references/paper_artifact_registry.csv` after publish unless skipped.

6. `pipelines/05_trim_proceedings_text.py`
   - Detects large proceedings or multi-abstract PDFs.
   - Finds the target abstract/publication by fuzzy title and author matching.
   - Writes focused text records to `data/extraction_json/text_trimmed/{paper_id}.json`.

7. `pipelines/05b_validate_proceedings_text.py`
   - Validates proceedings-derived text by searching the extracted text for the target title and author surnames.
   - Confirms whether trimmed proceedings text appears to contain the correct abstract or whether manual follow-up is still needed.
   - Writes `data/references/proceedings_text_qc_registry.csv`.

8. `pipelines/07_split_case_series.py`
   - Splits reviewed multi-case papers into explicit case segments when stable `Case 1` / `Patient 1` style headings are present.
   - Writes per-paper split artifacts to `data/extraction_json/text_case_series_split/{paper_id}.json`.
   - Writes `data/references/case_series_split_registry.csv`.

9. `pipelines/09_build_langextract_examples.py`
   - Rebuilds the LangExtract few-shot JSONs in `config/prompts/examples/`.
   - Uses curated examples from `examples/` and validates that each prompt example maps back to a real curated row.

10. `pipelines/10_langextract.py`
   - Reads extracted text and runs LangExtract with OpenAI models.
   - Uses reviewed source routing by default.
   - Explicitly skips records reviewed as `incorrect_reference`.
   - Prefers trimmed proceedings text when available and uses case-series split artifacts for reviewed multi-case papers.
   - Writes raw extractions to `data/extraction_json/langextract/` and summaries to `data/extraction_json/summary/`.

11. `pipelines/11_quality_assessment.py`
   - Reads extracted text and runs publication-type detection plus dictionary-driven quality extraction.
   - Uses reviewed source routing to exclude records reviewed as `incorrect_reference`.
   - Prefers trimmed proceedings text when available.
   - Writes raw outputs to `data/extraction_json/quality/raw/` and structured records to `data/extraction_json/quality/records/`.

## Registry / Support Scripts

- `pipelines/12_build_paper_artifact_registry.py`
  - Builds `data/references/paper_artifact_registry.csv`.
  - This is the project-wide source-of-truth table linking references, PDFs, extracted text, trimmed text, reviewed routing, proceedings QC, case-series splits, LangExtract outputs, summaries, and quality records.

- `pipelines/90_screen_text_extraction.py`
  - Screens extracted text for likely issues such as proceedings-like documents, noisy website chrome, or suspicious text-quality patterns.
  - Writes `data/references/text_screening_registry.csv`.

- `pipelines/04_source_categorisation_LLM.py`
  - Builds the canonical source-routing and SPS case-count registries for downstream workflow stages.
  - Adds stage-level provenance into the master artifact registry.
  - Stores resumable run artefacts under `results/stage04_llm_runs/`.
  - Produces `data/references/source_categorisation_registry.csv` and `data/references/source_sps_case_count_registry.csv` only when a completed run is published.
  - Manual adjudications are stored separately in `data/references/source_categorisation_manual_review.csv`.
  - The manual file records:
    - the original predicted category/subtype/confidence
    - the reviewed final category/subtype
    - short review notes
    - a batch marker and timestamp
    - a `pdf_content_alignment_tag` such as `appears_matched`, `uncertain`, `likely_wrong_pdf_attached`, or `incorrect_reference`
  - The manual-review queue for this corpus has been exhausted, so the override ledger now covers all papers that were originally marked `manual_review_required`.
  - Uses the following top-level categories:
    - `single_case_report`: one patient, case-level extraction target
    - `case_series_or_multi_case`: multiple individual cases, split before LangExtract
    - `observational_group_study`: cohort or cross-sectional group paper without per-case extraction target
    - `interventional_study`: controlled or therapeutic group study
    - `conference_abstract`: abstract/supplement/proceedings source, often needing trimming or manual review
    - `lab_heavy_clinical_or_translational`: clinically relevant group paper dominated by laboratory/antibody/method signals
    - `non_clinical_basic_science`: mechanistic/basic-science paper that should not enter clinical LangExtract
    - `review_article`: review-style paper, usually excluded from case-level extraction
    - `unclear_manual_review`: routing was not reliable enough to automate


- `pipelines/06_extract_sps_case_counts.py`
  - Legacy heuristic extractor for the separate extractable SPS case-count registry `data/references/source_sps_case_count_registry.csv`.
  - Uses the preferred available text after categorisation and proceedings trimming.
  - Records `likely_sps_case_count`, confidence, basis, and manual-review flags separately from the routing decision.

- `pipelines/05b_validate_proceedings_text.py`
  - Runs a separate proceedings QC pass after trimming/categorisation.
  - Searches proceedings-derived text for the reference title and author surnames.
  - Writes `data/references/proceedings_text_qc_registry.csv`.
  - Key statuses include:
    - `trimmed_match_confirmed`
    - `trimmed_partial_match`
    - `trimmed_mismatch_suspected`
    - `full_text_localised_untrimmed`
    - `full_text_partial_match`
    - `not_localised`

- `pipelines/07_split_case_series.py`
  - Uses reviewed routing to find case-series papers that should be split before LangExtract.
  - Only auto-splits when explicit case/patient headings make the split stable.
  - Writes per-paper split artifacts to `data/extraction_json/text_case_series_split/`.
  - Writes `data/references/case_series_split_registry.csv`.

- `pipelines/09_build_langextract_examples.py`
  - Rebuilds the prompt examples from curated project sheets in `examples/`.
  - Writes:
    - `config/prompts/examples/02_individual_examples.json`
    - `config/prompts/examples/02_group_examples.json`
    - `config/prompts/examples/03_publication_type_examples.json`
  - Adds provenance fields such as `source_sheet`, `paper_id`, and `case_id` where applicable.

- `pipelines/README.md`
  - More detailed per-script notes and run examples for the pipeline folder.

## Validation Scripts

- `validation/validate_pdf_source_registry.py`
  - Audits sampled rows from `data/references/pdf_source_registry.csv` against the underlying source content.
  - Prefers OCR-backed text JSON from `data/extraction_json/text/` when present and falls back to direct PDF text extraction otherwise.
  - Uses reproducible random sampling plus title / first-author / year matching to flag likely mismatches for manual review.
  - Validation reports should be written to `qa/validation/` by convention.

- `validation/validate_text_extraction_quality.py`
  - Builds a stratified manual-review sample for step 03 extraction QA.
  - Oversamples OCR-backed records, long/proceedings-like PDFs, and artifact-risk extractions instead of relying on a purely random sample.
  - Can write both a machine-readable JSON report and a CSV review sheet for `n=300` audits.
  - Validation reports should be written to `qa/validation/` by convention.

- `validation/export_text_json_to_txt.py`
  - Converts `data/extraction_json/text/{paper_id}.json` into human-readable `.txt` files.
  - Supports full-corpus export or subset export via `--paper-id` / `--selection-csv`.
  - Review-oriented TXT exports should be written under `qa/validation/text_exports/`.
  - The current QA workflow uses it to keep `all/`, `weaker_cases/`, `likely_failures/`, and the split weaker-case folders in sync with the latest canonical JSONs.

- `validation/README.md`
  - Notes for the validation scripts and example commands.

## Practical Notes

- `paper_id` is the Covidence ID and is the key used across all downstream artifacts.
- The full extracted text is preserved even when a trimmed proceedings version exists.
- Reviewed source routing should be preferred over the heuristic source-categorisation output whenever a paper appears in `data/references/source_categorisation_manual_review.csv`.
- Registry builders are meant to keep all generated artifacts traceable from one table.

## Directory Contents Snapshot
- Last updated: `2026-04-05`
- Immediate subdirectories (4): `lib`, `notebooks`, `pipelines`, `validation`
- Immediate files (0, excluding `README.md`): _None_
