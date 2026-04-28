# Pipelines

This folder contains the text extraction pipeline for source PDFs.

## `01_download_covidence_pdfs.py`

This script automates the Covidence full-text download step from the extraction view.

It:

- opens the Covidence extraction page in Chromium,
- logs in with runtime credentials or a saved browser session,
- finds each reference block with a `View full text` control,
- reveals the PDF link,
- downloads the PDF into `data/pdf_original`, and
- writes a JSONL manifest to `data/extraction_json/covidence/download_manifest.jsonl`.

After each run, it also refreshes `data/references/pdf_source_registry.csv` unless `--skip-registry-refresh` is passed.

### Requirements

- `playwright` installed in the project virtual environment
- Chromium installed via Playwright
- Covidence credentials supplied at runtime or through `COVIDENCE_EMAIL` and `COVIDENCE_PASSWORD`

### Run

First run:

```bash
python src/pipelines/01_download_covidence_pdfs.py
```

Headless rerun:

```bash
python src/pipelines/01_download_covidence_pdfs.py --headless
```

## `02_build_pdf_source_registry.py`

This script builds a reference-to-file registry in `data/references/pdf_source_registry.csv`.

It joins:

- the Covidence export in `data/references/sps_references_export.csv`,
- the downloaded PDFs in `data/pdf_original/`, and
- the Covidence download manifest in `data/extraction_json/covidence/download_manifest.jsonl`.

The output gives each reference its local PDF filename/path plus a `download_status`.

It also refreshes `data/references/pdf_acquisition_queue.csv`, which is the canonical backlog of references that still do not have a local PDF. The queue currently includes only matched references with no local PDF and a non-terminal `download_status` such as `missing`, `failed`, or `paywalled`.

### Run

```bash
python src/pipelines/02_build_pdf_source_registry.py
```

## `12_build_paper_artifact_registry.py`

This is the cross-pipeline source-of-truth registry for the project.

It writes `data/references/paper_artifact_registry.csv` with one row per `paper_id` across the union of:

- the Covidence reference export,
- downloaded PDFs,
- text extraction outputs,
- proceedings-ready text outputs,
- source categorisation outputs,
- SPS case-count outputs,
- LangExtract raw outputs,
- summary outputs, and
- quality-assessment outputs.

This makes the reference, local PDF, extracted text, and downstream AI artifacts traceable from one table.

### Run

```bash
python src/pipelines/12_build_paper_artifact_registry.py
```

## `05_trim_proceedings_text_LLM.py`

This script is the official stage-05 candidate-generation step for the LLM-assisted proceedings workflow.

It:

- reads the same full text JSON files from `data/extraction_json/text`,
- reuses the deterministic stage-05 matching logic to find the target proceedings block,
- builds a small ordered set of possible abstract-end candidates from the matched start,
- records whether LLM review is recommended for that package,
- writes one candidate package per paper to `data/extraction_json/text_trimmed_llm_candidates/{paper_id}.json`, and
- writes the paired registry `data/references/text_trim_llm_candidate_registry.csv`.

The candidate packages are intentionally separate from the retired deterministic `text_trimmed/` outputs so the live LLM path can be inspected independently.

### Run

```bash
python src/pipelines/05_trim_proceedings_text_LLM.py
```

Run a focused subset:

```bash
python src/pipelines/05_trim_proceedings_text_LLM.py --all-papers --paper-id 1001 --paper-id 1011 --paper-id 1028
```

## `05b_validate_proceedings_text_LLM.py`

This script is the official stage-05 validation step for the LLM-assisted proceedings workflow.

It:

- reads candidate packages from `data/extraction_json/text_trimmed_llm_candidates/`,
- sends the overshoot span plus candidate markers to an OpenAI model,
- validates the structured LLM answer against guardrails,
- falls back to the heuristic candidate order if the LLM answer is missing or invalid,
- writes final LLM-validated trims to `data/extraction_json/text_trimmed_llm/{paper_id}.json`, and
- writes the paired registry `data/references/text_trim_llm_registry.csv`.

This flow produces the final live stage-05 LLM trim layer that feeds `05c_publish_proceedings_ready.py`.

Run the canonical publication pass afterwards:

```bash
python src/pipelines/05c_publish_proceedings_ready.py
```

### Run

```bash
python src/pipelines/05b_validate_proceedings_text_LLM.py
```

Run the same focused subset after loading `OPENAI_API_KEY`:

```bash
python src/pipelines/05b_validate_proceedings_text_LLM.py --paper-id 1001 --paper-id 1011 --paper-id 1028
```

## `05c_publish_proceedings_ready.py`

This script publishes the canonical proceedings-ready text layer used by downstream stages and is the required third step of the live stage-05 workflow.

It:

- reads the resolved conference-abstract universe from stage 04,
- prefers active gold-standard proceedings trims when available,
- publishes validated LLM trims and rebuilt LLM boundary spans where needed,
- keeps safe full-text passthrough abstracts together in the same canonical layer,
- treats legacy `text_trimmed/` as archived provenance rather than a live interface,
- writes canonical outputs to `data/extraction_json/text_proceedings_ready/{paper_id}.json`,
- writes the paired registry `data/references/text_proceedings_ready_registry.csv`, and
- refreshes `data/references/paper_artifact_registry.csv`.

### Run

```bash
python src/pipelines/05c_publish_proceedings_ready.py
```

## Retired Stage-05 `_autoresearch` Copies

The isolated stage-05 `_autoresearch` copies have been retired from the live pipeline tree.

They are preserved under `legacy/stage_05_autoresearch/src/pipelines/` together with the archived benchmark harness, dedicated tests, and non-canonical run artefacts.

## Retired Deterministic Stage 05

The older deterministic stage-05 entrypoints have been retired to `legacy/stage_05_deterministic/src/pipelines/`.

Shared deterministic helpers that are still reused by the live LLM workflow remain in place as internal support modules:

- `_proceedings_trim_deterministic.py`
- `_proceedings_validate_deterministic.py`

## `03_extract_text.py`

Briefly, this script:

- Reads all `*.pdf` files from `data/pdf_original`.
- Derives `paper_id` from each filename (the number before the first underscore).
- Extracts text page-by-page with `pypdf`.
- Computes a SHA-256 checksum for each source PDF.
- Detects low-text or corrupted native text and optionally runs OCR (`ocrmypdf`) before re-extracting text.
- Writes one JSON output per PDF to `data/extraction_json/text/{paper_id}.json`.
- Writes the raw extraction stage only; reviewed text cleanup is a separate downstream stage in `03b_clean_text.py`.

## Output JSON includes

- `paper_id`, `source_filename`, `source_sha256`
- `n_pages`, `page_char_counts`, `pages`
- OCR status fields such as `needs_ocr_before_ocr`, `ocr_trigger_reasons`, `needs_ocr`, `remaining_text_quality_flags`, `ocr_applied`, `ocr_mode`, `ocr_error`

## Run

From repo root:

```bash
python src/pipelines/03_extract_text.py
```

## `03b_clean_text.py`

This script is now the canonical cleanup stage for both the deterministic pass and the reviewed residual rescue pass.

It:

- reads the target list from `config/extraction/text_cleanup_overrides.csv`,
- honors the reviewed `source_strategy` for each target (`json_cleanup` or `pdftotext_cleanup`),
- processes only enabled paper IDs (or an explicit `--paper-id` subset),
- stores the original raw JSON snapshot at `data/extraction_json/text_preclean/{paper_id}.json`,
- overwrites the canonical cleaned JSON at `data/extraction_json/text/{paper_id}.json`, and
- refreshes `data/references/paper_artifact_registry.csv` unless `--skip-registry-refresh` is passed.

Cleanup is intentionally conservative and deterministic:

- common mojibake and ligature repair
- a small reviewed substitution layer for corpus-specific glyph damage such as `gamma-aminobutyric` placeholders
- line-break hyphenation repair
- conservative punctuation/spacing normalization
- light repeated header/footer and publisher boilerplate removal

Phase 1 is intentionally limited to deterministic cleanup on a reviewed subset. Proceedings/context localization problems and true source-linkage problems should be handled elsewhere rather than pushed into this script.

With `--stage2`, the same script switches to the reviewed residual-cleanup path. In that mode it:

- reads `config/extraction/text_cleanup_stage2_overrides.csv`,
- applies reviewed per-paper substitutions from `config/extraction/text_cleanup_stage2_substitutions.csv`,
- can rebuild from `pdftotext`, localized OCR, or an alternate in-repo PDF when the attached PDF is known to be wrong, and
- preserves stage-2 backups in `data/extraction_json/text_preclean_stage2/{paper_id}.json`.

### Run

```bash
python src/pipelines/03b_clean_text.py
```

Force a rerun from preserved raw backups:

```bash
python src/pipelines/03b_clean_text.py --force
```

Run the reviewed residual rescue pass explicitly:

```bash
python src/pipelines/03b_clean_text.py --stage2 --paper-id 43 --paper-id 62 --paper-id 155
```

Force a rerun from preserved stage-2 backups:

```bash
python src/pipelines/03b_clean_text.py --stage2 --paper-id 43 --force
```

## `04_source_categorisation_LLM.py`

This script is the canonical stage-04 routing pass and uses the LLM workflow to classify each extracted source and estimate the paired extractable SPS case count in one run.

It:

- reads the full text JSON from `data/extraction_json/text`,
- prefers `data/extraction_json/text_proceedings_ready/{paper_id}.json` when available,
- falls back to legacy `data/extraction_json/text_trimmed/{paper_id}.json`,
- reuses `data/references/text_trim_registry.csv` for proceedings signals,
- assigns categories such as `single_case_report`, `case_series_or_multi_case`, `observational_group_study`, `conference_abstract`, `review_article`, `non_clinical_basic_science`, or `unclear_manual_review`,
- estimates `likely_sps_case_count` from the same LLM pass,
- records whether case-series splitting is a candidate, and
- checkpoints each completed paper under `results/stage04_llm_runs/{run_id}/`,
- supports resume and publish-only recovery from saved run artefacts, and
- publishes `data/references/source_categorisation_registry.csv` after a complete run, while the stage-04 count output should be treated as provisional until `06_extract_sps_case_counts_hybrid.py` refreshes the canonical stage-06 registry.

Manual adjudications for papers that required case-by-case review are stored in:

- `data/references/source_categorisation_manual_review.csv`

That manual override ledger records:

- the original predicted decision
- the final reviewed category and subtype
- short review notes
- a review batch label and timestamp
- `pdf_content_alignment_tag`

Alignment tags currently used:

- `appears_matched`
  - the downloaded PDF/content appears consistent with the reference
- `uncertain`
  - the paper was classifiable, but the local file or extracted text was not fully conclusive
- `likely_wrong_pdf_attached`
  - the PDF/content appears inconsistent with the reference metadata and should be treated cautiously
- `incorrect_reference`
  - the stored reference metadata itself appears to be wrong or points to the wrong paper, so the local PDF/text should not be treated as recoverable by extraction cleanup alone

Category meanings:

- `single_case_report`
  - one patient or one clearly case-level report
  - route to individual-level LangExtract
- `case_series_or_multi_case`
  - more than one individual case with case-level content
  - run case-series splitting before LangExtract
- `observational_group_study`
  - cohort/cross-sectional/group paper without per-patient extraction target
  - route to group-level LangExtract
- `interventional_study`
  - controlled or therapeutic group study
  - route to group-level LangExtract
- `conference_abstract`
  - meeting abstract, supplement, proceedings item, or trimmed proceedings record
  - often needs trimming or manual review before downstream use
- `lab_heavy_clinical_or_translational`
  - clinically relevant group paper dominated by antibody/laboratory/method content
  - usually keep for group-level extraction, not case splitting
- `non_clinical_basic_science`
  - mechanistic/basic-science work without useful clinical extraction target
  - usually skip LangExtract
- `review_article`
  - narrative/systematic review style paper
  - usually skip case-level LangExtract
- `unclear_manual_review`
  - signals conflict or confidence is too low
  - manual routing required

The current corpus-level manual review pass has been completed, so all rows that were initially `manual_review_required` now have reviewed decisions in `data/references/source_categorisation_manual_review.csv`.

Practical downstream rule:

- if a paper appears in `source_categorisation_manual_review.csv`, use the reviewed `final_source_category` and `final_source_subtype`
- otherwise, use the stage-04 LLM values from `source_categorisation_registry.csv`

Paid LLM calls are blocked unless `--allow-paid-run` is passed explicitly.

After publish, it also refreshes `data/references/paper_artifact_registry.csv` unless `--skip-registry-refresh` is passed.

### Run

```bash
python src/pipelines/04_source_categorisation_LLM.py --estimate-only
```

Start an approved checkpointed run:

```bash
python src/pipelines/04_source_categorisation_LLM.py --allow-paid-run --run-id stage04_llm_20260406 --max-runtime-minutes 180
```

Publish a completed run:

```bash
python src/pipelines/04_source_categorisation_LLM.py --publish-only --run-id stage04_llm_20260406
```

## `06_extract_sps_case_counts.py`

This script is the frozen legacy heuristic-plus-GPT comparator for the separate extractable SPS case-count registry.

It:

- reads the full text JSON from `data/extraction_json/text`,
- prefers `data/extraction_json/text_proceedings_ready/{paper_id}.json` when available,
- falls back to `data/extraction_json/text_trimmed/{paper_id}.json`,
- joins the source category from `data/references/source_categorisation_registry.csv`,
- estimates `likely_sps_case_count` with a separate SPS-specific count heuristic,
- records count confidence, basis, and whether manual count review is advisable, and
- can still write `data/references/source_sps_case_count_registry.csv` when run directly.

This stage is retained for benchmarking and fallback comparison. New stage-06 production work should go into `06_extract_sps_case_counts_hybrid.py` instead.

After each run, it also refreshes `data/references/paper_artifact_registry.csv` unless `--skip-registry-refresh` is passed.

### Run

```bash
python src/pipelines/06_extract_sps_case_counts.py
```

## `06_extract_sps_case_counts_LLM.py`

This script is the QA-only calibration runner for an alternative stage-06 workflow that combines:

- a local Ollama first pass using `gemma4:e4b`, and
- a paid OpenAI adjudication pass using `gpt-5.4` on every selected row.

It deliberately does not publish canonical outputs. Instead, it writes calibration artefacts so the local-model signal can be compared against the existing stage-06 GPT adjudication flow before any production switch is considered.

It:

- reads the same preferred proceedings-ready/full-text inputs as the current stage-06 script,
- reuses the existing deterministic stage-06 candidate package and evidence-window builder,
- sends a derived evidence pack to the local model rather than the raw OCR JSON,
- records the local model's count, evidence span, granularity, confidence, review flag, and optional competing possibilities,
- passes every row through GPT-5.4 during calibration,
- appends local-model provenance and comparison fields onto the stage-06 count row, and
- writes non-canonical outputs under:
  - `results/stage06_count_llm_runs/{run_id}/`
  - `qa/validation/stage06_llm/{run_id}.csv`

The existing deterministic hard gates are preserved. Review/basic-science rows, single-case constraints, explicit SPS subgroup caps, and SPS-status uncertainty signals remain active guardrails around the model outputs.

Paid GPT calls are blocked unless `--allow-paid-run` is passed explicitly.

This script is a calibration harness only. It should not replace the canonical stage-06 registry directly.

### Requirements

- Ollama running locally and serving `gemma4:e4b`
- `OPENAI_API_KEY` available in the shell environment

### Run

Estimate the selected run without model calls:

```bash
python src/pipelines/06_extract_sps_case_counts_LLM.py --estimate-only
```

Run a focused calibration subset:

```bash
python src/pipelines/06_extract_sps_case_counts_LLM.py --allow-paid-run --paper-id 214 --paper-id 724
```

Write the QA CSV to an explicit path:

```bash
python src/pipelines/06_extract_sps_case_counts_LLM.py --allow-paid-run --output-path qa/validation/stage06_llm/manual_slice.csv --limit 10
```

## `06_extract_sps_case_counts_hybrid.py`

This script is the canonical stage-06 hybrid runner. Use it to produce full hybrid run artefacts and candidate count rows; use `06c_publish_sps_case_count_registry.py` to publish the final canonical registry from reviewed sources.

It combines:

- deterministic heuristic candidate generation and hard safety rails,
- a local Ollama-served `gemma4:e4b` first pass on every selected paper,
- GPT-5.4 adjudication on rows that still need model resolution,
- a contradiction-focused GPT challenge pass when the first adjudication conflicts with deterministic or conservative evidence, and
- a tracked manual-review override ledger at `data/references/source_sps_case_count_manual_review.csv`.

It:

- reads the same preferred proceedings-ready/full-text inputs as the other stage-06 scripts,
- writes run artefacts under `results/stage06_count_runs/{run_id}/`,
- loads the OpenAI credential from `env/openai_api_key.env` for real runs instead of relying on ambient shell state,
- auto-starts Ollama when needed and aborts if `gemma4:e4b` still is not reachable,
- performs a tiny live OpenAI preflight call only when selected papers require GPT adjudication,
- applies reviewed overrides during publish,
- refuses subset canonical writes from `--paper-id` or `--limit` runs unless explicitly overridden for supervised recovery,
- refuses canonical export when unresolved manual-review rows remain uncovered by overrides unless `--allow-unresolved-export` is passed explicitly, and
- aborts and cleans up the current failed attempt if Ollama or OpenAI fails mid-run rather than emitting provisional fallback rows, and
- refreshes `data/references/paper_artifact_registry.csv` after a canonical write unless skipped.

Estimate-only:

```bash
python src/pipelines/06_extract_sps_case_counts_hybrid.py --estimate-only
```

Canonical hybrid run:

```bash
python src/pipelines/06_extract_sps_case_counts_hybrid.py --allow-paid-run
```

After manual adjudications have been written to
`data/references/source_sps_case_count_manual_review.csv`, you can sync those
reviewed counts into the canonical stage-06 registry without rerunning the
models:

```bash
python src/pipelines/06b_apply_sps_case_count_overrides.py
```

This rewrites `data/references/source_sps_case_count_registry.csv` in place and
refreshes `data/references/paper_artifact_registry.csv` unless
`--skip-registry-refresh` is passed.

## `06c_publish_sps_case_count_registry.py`

This script publishes the canonical stage-06 count registry from already-reviewed local evidence. It does not call paid APIs.

It applies, in order:

- hybrid/backfill QA rows from `qa/validation/stage06_llm/`,
- reviewed manual overrides from `data/references/source_sps_case_count_manual_review.csv`,
- active gold rows from `qa/validation/source_categorisation/gold_standard/stage06_count_gold/`,
- source-linkage exclusions such as `incorrect_reference`, and
- reference-only heuristic fallbacks for rows that otherwise have no count, with `count_manual_review_required=true`.

Run:

```bash
python src/pipelines/06c_publish_sps_case_count_registry.py
python src/pipelines/12_build_paper_artifact_registry.py
python src/validation/benchmark_stage06_hybrid.py --workflow canonical=data/references/source_sps_case_count_registry.csv
```

## `07_split_case_series.py`

This script prepares reviewed multi-case papers for individual-level LangExtract.

It:

- reads the reviewed routing decision from `data/references/source_categorisation_manual_review.csv` when available,
- limits automatic splitting to papers that are true case-series candidates,
- builds a composite stage-06 prior from the canonical count registry plus any available run artefacts,
- prefers the stage-06 `preferred_text_json_path`,
- searches for explicit `Case 1` / `Patient 1` style headings and bounded subgroup statements,
- writes per-paper unit artifacts to `data/extraction_json/text_case_series_units/{paper_id}.json`,
- derives a run-scoped JSONL manifest under `results/stage07_unit_manifests/`, and
- writes `data/references/case_series_split_registry.csv`.

It is intentionally conservative. If attribution-safe units are not stable, the paper stays in manual review.

### Run

```bash
python src/pipelines/07_split_case_series.py
```

## `09_build_langextract_examples.py`

This script rebuilds the few-shot JSON files used by LangExtract and the quality-assessment classifier.

It:

- uses curated rows from `examples/`,
- validates that each example points back to a real curated example row, and
- rewrites the prompt assets in `config/prompts/examples/`.

Outputs:

- `config/prompts/examples/02_individual_examples.json`
- `config/prompts/examples/02_group_examples.json`
- `config/prompts/examples/03_publication_type_examples.json`

### Run

```bash
python src/pipelines/09_build_langextract_examples.py
```

## `10_langextract.py`

This script reads text JSON files from `data/extraction_json/text`, applies reviewed routing by default, prefers `data/extraction_json/text_proceedings_ready/{paper_id}.json` when it exists, falls back to `data/extraction_json/text_trimmed/{paper_id}.json`, uses stage-07 unit artifacts when appropriate, runs LangExtract with an OpenAI model, and writes:

- Raw LangExtract entities to `data/extraction_json/langextract/{paper_id}.json`
- Section summaries + overall summary to `data/extraction_json/summary/{paper_id}.json`

The stage-07 unit source defaults to `data/extraction_json/text_case_series_units/` and can be overridden with `--case-units-dir` for smoke runs or isolated validation.

Records reviewed as `incorrect_reference` are explicitly excluded and reported as `skipped_incorrect_reference` in the run summary.

### Requirements

- `langextract[openai]` installed in your virtual environment
- `OPENAI_API_KEY` set in your shell environment

### Run

Dry run (no API calls):

```bash
python src/pipelines/10_langextract.py --dry-run --limit 2
```

Real run:

```bash
python src/pipelines/10_langextract.py
```

Ignore reviewed routing and force explicit CLI mode selection:

```bash
python src/pipelines/10_langextract.py --ignore-routing --include-individual --limit 5
```

## `11_quality_assessment.py`

This script reads text JSON files from `data/extraction_json/text`, prefers `data/extraction_json/text_trimmed/{paper_id}.json` when it exists, and writes:

- Raw quality-assessment LangExtract output to `data/extraction_json/quality/raw/{paper_id}.json`
- Structured quality records to `data/extraction_json/quality/records/{paper_id}.json`

Records reviewed as `incorrect_reference` are explicitly excluded before any downstream model calls.

## `13_build_paper_revisit_registry.py`

This script builds the canonical cross-stage revisit registry at `data/references/paper_revisit_registry.csv`.

It records one row per paper/stage issue from:

- PDF acquisition failures or still-missing acquisition queue entries,
- proceedings trim and proceedings QC manual-follow-up rows,
- failed or fallback LLM trim validation,
- source-linkage failures such as `incorrect_reference`,
- unresolved source-categorisation review rows,
- stage-06 count rows still marked for manual review, and
- case-series split rows requiring manual boundary review.

Run after refreshing the artefact registry or any QC/manual-review ledger:

```bash
python src/pipelines/13_build_paper_revisit_registry.py
```

## Directory Contents Snapshot
- Last updated: `2026-04-27`
- Immediate subdirectories (0): _None_
- Immediate files include the stage entry points `01_download_covidence_pdfs.py` through `13_build_paper_revisit_registry.py`, including `06_extract_sps_case_counts_hybrid.py`, `06b_apply_sps_case_count_overrides.py`, and `06c_publish_sps_case_count_registry.py`.
