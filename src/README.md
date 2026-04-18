# `src` Overview

This folder contains the project pipeline scripts, validation utilities, legacy helpers, and shared code. They are designed to be run from the repository root and operate on the data stored under `data/`.

Validation scripts should write their non-canonical review and audit outputs under `qa/validation/`, not `data/` or `results/`.

The retired stage-05 autoresearch bundle now lives under `legacy/stage_05_autoresearch/`. Any future autoresearch harnesses should write benchmark-local artefacts under non-canonical QA folders such as `qa/trimming/`.

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
   - Shows an interactive progress bar during paid terminal runs so long batches expose current progress and ETA.
   - Publishes `data/references/source_categorisation_registry.csv` after a complete run.
   - Still emits a provisional count snapshot during stage 04, but the final canonical SPS case-count registry is now expected to be refreshed by the stage-06 hybrid run.
   - Refreshes `data/references/paper_artifact_registry.csv` after publish unless skipped.

6. `pipelines/05_trim_proceedings_text_LLM.py`
   - Official stage-05 candidate-generation step for proceedings trimming.
   - Builds ordered proceedings end-candidate packages under `data/extraction_json/text_trimmed_llm_candidates/`.
   - Writes `data/references/text_trim_llm_candidate_registry.csv`.

7. `pipelines/05b_validate_proceedings_text_LLM.py`
   - Official stage-05 validation step for proceedings trimming.
   - Uses an OpenAI model to confirm the best proceedings end candidate or fall back to guarded heuristics.
   - Writes final LLM-reviewed trims to `data/extraction_json/text_trimmed_llm/{paper_id}.json`.
   - Writes `data/references/text_trim_llm_registry.csv`.

8. `pipelines/05c_publish_proceedings_ready.py`
   - Publishes the canonical proceedings-ready layer under `data/extraction_json/text_proceedings_ready/{paper_id}.json`.
   - Writes `data/references/text_proceedings_ready_registry.csv`.
   - Refreshes `data/references/paper_artifact_registry.csv`.

9. `pipelines/07_split_case_series.py`
   - Splits reviewed multi-case papers into explicit case segments when stable `Case 1` / `Patient 1` style headings are present.
   - Prefers `data/extraction_json/text_proceedings_ready/` before falling back to legacy trimmed or full source text.
   - Writes per-paper split artifacts to `data/extraction_json/text_case_series_split/{paper_id}.json`.
   - Writes `data/references/case_series_split_registry.csv`.

12. `pipelines/09_build_langextract_examples.py`
   - Rebuilds the LangExtract few-shot JSONs in `config/prompts/examples/`.
   - Uses curated examples from `examples/` and validates that each prompt example maps back to a real curated row.

13. `pipelines/10_langextract.py`
   - Reads extracted text and runs LangExtract with OpenAI models.
   - Uses reviewed source routing by default.
   - Explicitly skips records reviewed as `incorrect_reference`.
   - Prefers proceedings-ready text when available and uses case-series split artifacts for reviewed multi-case papers.
   - Writes raw extractions to `data/extraction_json/langextract/` and summaries to `data/extraction_json/summary/`.

14. `pipelines/11_quality_assessment.py`
   - Reads extracted text and runs publication-type detection plus dictionary-driven quality extraction.
   - Uses reviewed source routing to exclude records reviewed as `incorrect_reference`.
   - Prefers trimmed proceedings text when available.
   - Writes raw outputs to `data/extraction_json/quality/raw/` and structured records to `data/extraction_json/quality/records/`.

## Registry / Support Scripts

- `pipelines/12_build_paper_artifact_registry.py`
  - Builds `data/references/paper_artifact_registry.csv`.
  - This is the project-wide source-of-truth table linking references, PDFs, extracted text, proceedings-ready text, reviewed routing, proceedings QC, case-series splits, LangExtract outputs, summaries, and quality records.

- `pipelines/90_screen_text_extraction.py`
  - Screens extracted text for likely issues such as proceedings-like documents, noisy website chrome, or suspicious text-quality patterns.
  - Writes `data/references/text_screening_registry.csv`.

- `pipelines/04_source_categorisation_LLM.py`
  - Builds the canonical source-routing registry and a provisional SPS case-count snapshot for downstream workflow stages.
  - Adds stage-level provenance into the master artifact registry.
  - Stores resumable run artefacts under `results/stage04_llm_runs/`.
  - Produces `data/references/source_categorisation_registry.csv` when a completed run is published.
  - The final canonical `data/references/source_sps_case_count_registry.csv` is expected to be refreshed by `pipelines/06_extract_sps_case_counts_hybrid.py`.
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
  - Frozen legacy heuristic-plus-GPT comparator for the extractable SPS case-count workflow.
  - Kept for benchmarking and fallback comparisons.

- `pipelines/06_extract_sps_case_counts_LLM.py`
  - QA-only Gemma-plus-GPT calibration harness for stage 06.
  - Writes non-canonical calibration artefacts under `qa/validation/stage06_llm/`.

- `pipelines/06_extract_sps_case_counts_hybrid.py`
  - Canonical stage-06 hybrid runner.
  - Combines deterministic candidate generation, local Gemma advice, GPT adjudication, contradiction escalation, and tracked reviewed overrides.
  - Writes the final canonical `data/references/source_sps_case_count_registry.csv`.

- `pipelines/05_trim_proceedings_text_LLM.py`
  - Official stage-05 candidate-generation step for proceedings trimming.
  - Reuses the deterministic matcher to find the target abstract start and proposes ordered end candidates for review.
  - Writes `data/extraction_json/text_trimmed_llm_candidates/` plus `data/references/text_trim_llm_candidate_registry.csv`.

- `pipelines/05b_validate_proceedings_text_LLM.py`
  - Official stage-05 validation step for proceedings trimming.
  - Validates the end choice with an OpenAI model or guarded heuristic fallback and writes `data/extraction_json/text_trimmed_llm/` plus `data/references/text_trim_llm_registry.csv`.

- `pipelines/05c_publish_proceedings_ready.py`
  - Publishes the only live downstream stage-05 layer under `data/extraction_json/text_proceedings_ready/`.
  - Writes `data/references/text_proceedings_ready_registry.csv`.
  - Merges gold-manual, LLM-validated, rebuilt, and safe passthrough proceedings outputs into one canonical interface.

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

- `validation/find_missed_proceedings_candidates.py`
  - Audits non-conference rows for missed proceedings fragments or conference-style abstracts.
  - Combines stage-04 metadata cues with local proceedings-format cues around the matched title and author block.
  - Supports focused batches via repeated `--paper-id` flags before any wider audit pass.
  - Writes review queues and snippet packs under `qa/validation/missed_proceedings_audit_*/`.

- `validation/build_stage06_backfill_campaign.py`
  - Builds the stage-06 backfill campaign manifest from manual-gold coverage plus discovered `hybrid_v2_*` run artifacts.
  - Emits one batch manifest per 50-paper chunk together with a status table under `qa/validation/stage06_llm/backfill_campaign/`.

- `validation/run_stage06_backfill_batch.py`
  - Runs or resumes one subset stage-06 hybrid batch from a batch manifest.
  - Rebuilds the combined batch CSV, inspection Markdown pack, review-comments CSV, and review-notes Markdown scaffold after each invocation.

- `validation/README.md`
  - Notes for the validation scripts and example commands.

## Autoresearch Status

- No active autoresearch harness currently lives under `src/`.
- The retired stage-05 proceedings-trimming archive is preserved under `legacy/stage_05_autoresearch/`.
- The reviewed gold papers and shared `qa/trimming/gold_standard/manifest.json` remain live outside that archive for the manual stage-05 workflow.

## Practical Notes

- `paper_id` is the Covidence ID and is the key used across all downstream artifacts.
- The full extracted text is preserved even when a trimmed proceedings version exists.
- Reviewed source routing should be preferred over the heuristic source-categorisation output whenever a paper appears in `data/references/source_categorisation_manual_review.csv`.
- Registry builders are meant to keep all generated artifacts traceable from one table.

## Directory Contents Snapshot
- Last updated: `2026-04-13`
- Immediate subdirectories (6): `autoresearch`, `legacy`, `lib`, `notebooks`, `pipelines`, `validation`
- Immediate files (0, excluding `README.md`): _None_
