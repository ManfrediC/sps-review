# src / pipelines

Numbered pipeline entry points for the SPSD review workflow.

Run from the repository root. Use `.venv` unless a script documents another
runtime. Paid model calls require explicit approval and an explicit script flag
such as `--allow-paid-run`.

## Current Scope

Stages 01 through 07 are the developed workflow. Stages after 07 exist as
preliminary extraction, summary, and quality-assessment scaffolding and still
need stronger validation before they are treated as final review data.

## Stages 01-03b: PDF And Text

### `01_download_covidence_pdfs.py`

Downloads full-text PDFs from the Covidence extraction view into
`data/pdf_original/` and writes the Covidence download manifest to
`data/extraction_json/covidence/download_manifest.jsonl`.

It normally refreshes:

- `data/references/pdf_source_registry.csv`
- `data/references/pdf_acquisition_queue.csv`
- `data/references/paper_artifact_registry.csv`

Run:

```bash
python src/pipelines/01_download_covidence_pdfs.py
```

### `02_build_pdf_source_registry.py`

Builds the reference-to-PDF linkage registry from the Covidence export, local
PDFs, and the download manifest.

Outputs:

- `data/references/pdf_source_registry.csv`
- `data/references/pdf_acquisition_queue.csv`

Run:

```bash
python src/pipelines/02_build_pdf_source_registry.py
```

### `03_extract_text.py`

Extracts page-level text from local PDFs, using OCR when native text is sparse
or corrupted.

Inputs:

- `data/pdf_original/*.pdf`
- `config/extraction/text_extraction_overrides.csv`

Output:

- `data/extraction_json/text/{paper_id}.json`

Run:

```bash
python src/pipelines/03_extract_text.py
```

### `03b_clean_text.py`

Applies reviewed deterministic cleanup only to selected extracted text JSONs.
The same entry point owns the reviewed residual cleanup path via `--stage2`.

Inputs:

- `data/extraction_json/text/{paper_id}.json`
- `config/extraction/text_cleanup_overrides.csv`
- `config/extraction/text_cleanup_stage2_overrides.csv`
- `config/extraction/text_cleanup_stage2_substitutions.csv`

Outputs:

- `data/extraction_json/text_preclean/{paper_id}.json`
- `data/extraction_json/text_preclean_stage2/{paper_id}.json`
- updated `data/extraction_json/text/{paper_id}.json`

Run:

```bash
python src/pipelines/03b_clean_text.py
python src/pipelines/03b_clean_text.py --stage2 --paper-id 43
```

## Optional Text Screening

### `90_screen_text_extraction.py`

Screens extracted text for likely quality issues, proceedings-like context, and
other triage signals.

Output:

- `data/references/text_screening_registry.csv`

This is QA support, not a required canonical gate.

## Stage 04: Source Routing

### `04_source_categorisation_LLM.py`

Classifies source type and records routing decisions. It also produces a
provisional count signal, but the canonical count registry is stage 06.

Inputs:

- `data/extraction_json/text/{paper_id}.json`
- `data/extraction_json/text_proceedings_ready/{paper_id}.json` when available
- `data/references/text_trim_registry.csv` for legacy proceedings signals

Outputs:

- `results/stage04_llm_runs/{run_id}/`
- `data/references/source_categorisation_registry.csv`
- `data/references/source_categorisation_manual_review.csv`
- refreshed `data/references/paper_artifact_registry.csv`

Run estimate-only:

```bash
python src/pipelines/04_source_categorisation_LLM.py --estimate-only
```

## Stage 05: Proceedings Text

### `05_trim_proceedings_text_LLM.py`

Builds ordered end-boundary candidate packages for proceedings and conference
abstracts.

Outputs:

- `data/extraction_json/text_trimmed_llm_candidates/{paper_id}.json`
- `data/references/text_trim_llm_candidate_registry.csv`

### `05b_validate_proceedings_text_LLM.py`

Validates the candidate boundary with an OpenAI model or guarded fallback logic.

Outputs:

- `data/extraction_json/text_trimmed_llm/{paper_id}.json`
- `data/references/text_trim_llm_registry.csv`

### `05c_publish_proceedings_ready.py`

Publishes the canonical downstream stage-05 text layer by combining reviewed
gold trims, validated LLM trims, rebuilt boundary spans, and safe passthrough
abstracts.

Outputs:

- `data/extraction_json/text_proceedings_ready/{paper_id}.json`
- `data/references/text_proceedings_ready_registry.csv`
- refreshed `data/references/paper_artifact_registry.csv`

Typical run:

```bash
python src/pipelines/05_trim_proceedings_text_LLM.py
python src/pipelines/05b_validate_proceedings_text_LLM.py
python src/pipelines/05c_publish_proceedings_ready.py
```

## Stage 06: SPSD Case Counts

### `06_extract_sps_case_counts_hybrid.py`

Canonical production runner for stage-06 count evidence and candidate rows. It
combines deterministic candidates, local Gemma advice, GPT adjudication where
approved, contradiction escalation, and tracked manual overrides.

Outputs:

- `results/stage06_count_runs/{run_id}/`
- candidate/review material under `qa/validation/stage06_llm/`

### `06b_apply_sps_case_count_overrides.py`

Applies reviewed count overrides to an existing count registry without rerunning
models.

Output:

- `data/references/source_sps_case_count_registry.csv`

### `06c_publish_sps_case_count_registry.py`

Publishes the canonical count registry from reviewed local evidence, hybrid QA
rows, manual overrides, active gold rows, and source-linkage exclusions. It does
not call paid APIs.

Output:

- `data/references/source_sps_case_count_registry.csv`

Publish and refresh indexes:

```bash
python src/pipelines/06c_publish_sps_case_count_registry.py
python src/pipelines/12_build_paper_artifact_registry.py
python src/pipelines/13_build_paper_revisit_registry.py
```

The older `06_extract_sps_case_counts.py` and `06_extract_sps_case_counts_LLM.py`
scripts are retained for comparison and QA calibration, not direct publication.

## Stage 07: Case-Series Splitting

### `07_split_case_series.py`

Prepares reviewed multi-case papers for individual-level downstream extraction
by publishing attribution-safe patient or group units.

Inputs:

- `data/references/source_categorisation_registry.csv`
- `data/references/source_categorisation_manual_review.csv`
- `data/references/source_sps_case_count_registry.csv`
- preferred text from stage 06 when available
- `data/extraction_json/text_proceedings_ready/{paper_id}.json` or full text

Outputs:

- `data/extraction_json/text_case_series_units/{paper_id}.json`
- `data/references/case_series_split_registry.csv`
- `results/stage07_unit_manifests/{run_id}.jsonl`
- refreshed `data/references/paper_artifact_registry.csv`

Run:

```bash
python src/pipelines/07_split_case_series.py
```

## Preliminary Downstream Stages

### `09_build_langextract_examples.py`

Rebuilds few-shot JSON assets in `config/prompts/examples/` from curated rows
under `examples/`.

### `10_langextract.py`

Runs preliminary LangExtract extraction. It prefers proceedings-ready text and
uses stage-07 units for reviewed multi-case papers.

Outputs:

- `data/extraction_json/langextract/{paper_id}.json`
- `data/extraction_json/summary/{paper_id}.json`

### `11_quality_assessment.py`

Runs preliminary publication-type and quality extraction.

Outputs:

- `data/extraction_json/quality/raw/{paper_id}.json`
- `data/extraction_json/quality/records/{paper_id}.json`

Treat stages 10 and 11 as incomplete until their contracts and validation are
settled.

## Registry Maintenance

### `12_build_paper_artifact_registry.py`

Builds `data/references/paper_artifact_registry.csv`, the project-wide
one-row-per-paper index of known paths and status fields across all stages.

Run:

```bash
python src/pipelines/12_build_paper_artifact_registry.py
```

### `13_build_paper_revisit_registry.py`

Builds `data/references/paper_revisit_registry.csv`, the cross-stage list of
papers needing acquisition, source-linkage, proceedings, count, or stage-07
follow-up.

Run:

```bash
python src/pipelines/13_build_paper_revisit_registry.py
```

### `99_overnight_run.py`

Batch orchestration wrapper. It writes logs and status under
`results/overnight/`; it is not a separate data-processing stage.

## Retired Stage-05 Work

Retired deterministic and autoresearch stage-05 copies live under `legacy/`.
The live proceedings workflow is the `05` -> `05b` -> `05c` sequence above.
