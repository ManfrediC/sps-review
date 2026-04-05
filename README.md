# sps-review

This repository aims to provide a reproducible workflow that shifts effort from manual searching/typing to **rapid verification** of structured extractions against **colour-coded highlights** in the original PDFs.

---

## Core idea

- **Excel remains the reviewer interface** for all final values and decisions.
- **Quotes do not live in the main Excel sheet.** Instead, they are stored in structured extraction outputs and used to:
  - generate **annotated PDFs** with **colour-coded highlights** by variable domain, and
  - provide **one-click evidence access** from each case row in Excel.

---

## Repository layout

- `data/pdf_original/`  
  Source PDFs *(not committed)*

- `data/extraction_json/`  
  Structured extraction + evidence (value, quote, location, confidence) *(not committed)*

- `data/pdf_annotated/`  
  Highlighted PDFs for reviewer verification *(not committed)*

- `data/excel/`  
  Reviewer workbook(s) *(not committed)*

- `src/pipelines/`  
  Pipeline scripts *(download -> extract -> clean -> route -> downstream extraction)*

- `config/`  
  Schema + data dictionary + colour map

- `doc/`  
  Methods and protocol documentation

- `results/`  
  Canonical pipeline-produced exports and runtime outputs *(not committed by default)*

- `qa/`  
  Non-canonical validation packs, spot checks, and manual review sheets

---

## Purpose

Develop and operate a reproducible workflow for **case-level** data extraction from a large corpus of `1039` screened SPS-spectrum references, while preserving **dual-reviewer verification** and improving speed, auditability, and consistency.

---

## Core objectives

1. Extract **structured, case-level** data for predefined variables with source-text traceability.
2. Preserve **dual-reviewer verification** in a time-efficient, auditable format.
3. Maintain a clean, fast Excel workspace for reviewers.
4. Automatically generate annotated PDFs with **colour-coded highlights** for each extracted data point.
5. Produce a reproducible pipeline from **PDF -> structured data -> final analysis dataset**.
6. Ensure methodological transparency suitable for publication.

---

## Conceptual architecture

### 1) Source layer
- Input: original PDFs (one stable `paper_id` per file)
- Stored unchanged in a dedicated directory

### 2) Extraction layer
- AI performs schema-driven extraction at **case level** (not paper level).
- Output is structured JSON including:
  - `paper_id`
  - `case_id`
  - `field_name`
  - `value`
  - `quote`
  - `location` (page/section)
  - `confidence`

This JSON serves as the machine-readable audit trail.

### 3) Evidence layer
- Quotes are not stored in the main Excel sheet.
- Quotes are used to:
  - locate corresponding text in the PDF
  - generate an annotated PDF
  - apply colour-coded highlights by variable domain

Each case row in Excel contains a one-click link to its annotated PDF.

### 4) Excel reviewer layer
Excel is the primary working environment and contains:
- one row per case
- final extraction fields (values)
- reviewer decision columns
- hyperlink to annotated PDF

No long text fields are stored in the main sheet.

Column background colours reflect variable domains (e.g., phenotype, antibodies, EMG, malignancy, treatment, outcome). A separate legend sheet defines variables and colour coding.

---

## Reviewer workflow

For each case:
1. Open the annotated PDF via the Excel hyperlink.
2. Navigate visually using colour-coded highlights.
3. Validate or correct extracted values.
4. Mark reviewer decision *(accept / edit / unclear)*.

Manual searching within PDFs is minimised.

Dual review is preserved via either:
- sequential validation with adjudication of changes, or
- parallel independent validation against the same annotated evidence.

---

## Outputs

### Primary
- Clean, adjudicated, case-level dataset for analysis.

### Secondary
- Annotated PDF corpus with all supporting evidence highlighted.
- Structured JSON extraction archive.
- Audit log of AI vs final human-validated values.

These outputs support reproducibility, transparency, and rapid re-checking.

---

## Data structure and organisation

Project directories (conceptually):
- `pdf_original/` - source files
- `pdf_annotated/` - automatically highlighted evidence PDFs
- `extraction_json/` - structured AI outputs
- `excel/` - reviewer workbook and final dataset
- `qa/` - non-canonical validation and review material
- `src/pipelines/` - automation and transformation steps

Stable file naming is mandatory to preserve links between Excel, JSON, and PDFs.

---

## Extraction schema

All variables are predefined in a data dictionary that includes:
- field name
- definition
- allowed values / coding rules
- domain colour for PDF highlights and Excel layout

Extraction is strictly evidence-based:
- if a value is not explicitly stated, it is recorded as **"not stated"**.

---

## Methodological position

This is an **AI-assisted, human-verified** extraction workflow, not automated data collection.

Humans:
- make all final data decisions
- resolve ambiguity
- adjudicate disagreements

AI:
- performs first-pass structured extraction
- provides source-text localisation
- generates visual evidence for rapid verification

This preserves systematic review standards while removing the mechanical bottleneck.

---

## Success criteria

The system is successful if it:
- substantially reduces reviewer time per case
- maintains high agreement between reviewers
- produces a traceable audit trail for every extracted variable
- enables rapid re-checking of any data point directly in the original source

---

## Role of Codex/ChatGPT in this project

Used to:
- design and refine the extraction schema
- generate and optimise structured extraction prompts
- define data models (JSON <-> Excel transformations)
- plan the automation workflow
- support methodological documentation for publication
- troubleshoot edge cases (e.g., multi-patient case series, ambiguous reporting)

ChatGPT does not make final data decisions.

---

## Scope boundaries

This project does not perform:
- study screening
- risk-of-bias assessment
- statistical analysis

It focuses exclusively on **case-level data extraction and verification infrastructure**.

---

## Covidence PDF acquisition

This review stores full texts in Covidence, but Covidence does not provide the project with a simple bulk PDF export step. The repository therefore includes a browser-based downloader at `src/pipelines/01_download_covidence_pdfs.py`.

Workflow:
1. Open the extraction review in Covidence.
2. Run the downloader script.
3. Let the script reveal each `View full text` link and save the PDF into `data/pdf_original/` as `<Covidence_ID>_<original_filename>.pdf`.
4. Feed those PDFs into the existing text-extraction pipeline.

---

## Current project status

The canonical step `01` to step `03` workflow is now in a strong operational state.

- `1039` references are tracked in the live registries.
- `1027` references have downloaded PDFs and canonical extracted text JSONs.
- All `1027` extracted texts have been reviewed at least once through the combined sample-review, remainder-review, and targeted repair workflow.
- The remaining PDF acquisition backlog is explicit in `data/references/pdf_acquisition_queue.csv`:
  - `7` `missing`
  - `5` `failed`
- Two records are now explicitly labelled `incorrect_reference` and are excluded from downstream AI stages:
  - `263`
  - `1841`

This means the remaining open issues after step `03` are now narrow and explicit:
- unresolved source acquisition for the `12` queued references
- two upstream reference-linkage problems

---

## Current text-cleanup stage

The canonical text flow now includes an explicit cleanup step between raw extraction and downstream routing.

1. `src/pipelines/03_extract_text.py` writes raw extracted text JSONs to `data/extraction_json/text/`.
2. `src/pipelines/03b_clean_text.py` is the sole cleanup entry point and applies deterministic cleanup only to the reviewed subset listed in `config/extraction/text_cleanup_overrides.csv`.
3. `03b --stage2` runs the reviewed residual rescue logic for the smaller set of papers that need page-localised OCR, alternate source replacement, or narrow reviewed substitutions.
4. `03b` preserves pre-clean backups for those targeted papers in `data/extraction_json/text_preclean/` and `data/extraction_json/text_preclean_stage2/`.
5. The cleaned canonical JSONs remain together in `data/extraction_json/text/` for downstream stages.

---

## End goal

A scalable, reviewer-centred system that converts narrative SPS case reports into a high-quality, fully auditable dataset suitable for systematic synthesis, while preserving methodological rigour and dramatically reducing manual workload.

## Directory Contents Snapshot
- Last updated: `2026-04-05`
- Immediate subdirectories (14): `.claude`, `.codex`, `.github`, `.venv`, `config`, `data`, `doc`, `env`, `examples`, `qa`, `resources`, `results`, `src`, `tests`
- Immediate files (3, excluding `README.md`): `.gitignore`, `AGENTS.md`, `CLAUDE.md`
