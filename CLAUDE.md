# CLAUDE.md

This file provides guidance to Claude Code (`claude.ai/code`) when working with code in this repository.

Also read `AGENTS.md` (working style, editing rules, debugging protocol, hard prohibitions) and `doc/repo_rules.md` (runtime, output locations, pipeline order, stopping conditions) - both are authoritative and complement this file.

---

## Commands

```bash
# Run all tests
python -m unittest discover -s tests -p "test_*.py" -v

# Run a single test file
python -m unittest discover -s tests -p "test_06_extract_sps_case_counts.py" -v

# Lint / format (if configured)
ruff check .
ruff format --check .

# Run any pipeline script (from repo root, .venv active)
python src/pipelines/03_extract_text.py --help
```

Activate the project venv before running anything: `.venv` in the repo root.

---

## Architecture

This is a staged, file-based ETL pipeline for AI-assisted systematic-review extraction of Stiff-Person Spectrum (SPS) sources. Each stage produces artefacts consumed by the next; all stages are keyed on `paper_id` (Covidence reference ID).

### Stage order

```text
01 download PDFs -> 02 PDF-source registry -> 03 extract text -> 03b clean text ->
(90 screen) -> 04 categorise source -> 04b extract SPS case counts ->
05 trim proceedings -> 06 validate trim -> 07 split case series ->
09 build examples -> 10 LangExtract (LLM) -> 11 quality assessment ->
12 master artifact registry -> [99 overnight orchestrator]
```

### Key directories

| Path | Purpose |
|---|---|
| `src/pipelines/` | Numbered ETL scripts (`01-99`); run in order |
| `src/lib/` | Reusable helpers (`text_cleanup.py`, `text_cleanup_stage2.py`) |
| `src/validation/` | QA/audit scripts (non-canonical outputs) |
| `config/schema/` | JSON Schemas that validate LangExtract and QA outputs |
| `config/dictionaries/` | CSV field definitions, accepted values, guidance |
| `config/extraction/` | Per-paper override tables for cleanup and routing |
| `config/prompts/` | LLM prompt Markdown files and auto-generated few-shot JSON |
| `data/` | Canonical research artefacts (PDFs, extracted text, registries) |
| `data/extraction_json/text/` | Cleaned page-level text JSONs (one per paper) |
| `data/extraction_json/langextract/` | Structured LLM-extracted JSON |
| `data/references/` | Covidence export and derived registry CSVs |
| `results/overnight/` | Pipeline logs (`LOG.md`, `stage_status.tsv`) |
| `qa/validation/` | Non-canonical spot checks and review sheets |
| `tests/` | Unit tests; fixtures in `tests/fixtures/` |

### Data contracts

**Text JSON** (`data/extraction_json/text/{paper_id}.json`): `paper_id`, `n_pages`, `pages[]` (each with `page_num`, `text`, `char_count`), OCR flags.

**LangExtract JSON** (`data/extraction_json/langextract/{paper_id}.json`): structured fields grouped into sections (individual or group level). Every field carries `value`, `quote`, `location`, `confidence` for traceability.

**Registries** (`data/references/*.csv`): CSV files keyed on `paper_id` that link metadata, PDFs, text, routing decisions, case counts, and extraction outputs. `paper_artifact_registry.csv` is the master cross-pipeline provenance file.

### Source routing categories

After step `04`, each paper is assigned a category that determines downstream handling:

- `single_case_report` -> direct to LangExtract (individual)
- `case_series_or_multi_case` -> optionally split (step `07`) then LangExtract
- `conference_abstract` -> trim/QC (`05-06`) then optionally split or extract
- `observational_group_study` / `interventional_study` / `lab_heavy_clinical_or_translational` -> group-level extraction
- `review_article` / `non_clinical_basic_science` -> usually skip
- `incorrect_reference` -> excluded from LangExtract and quality assessment via the reviewed override ledger

Manual routing overrides live in `data/references/source_categorisation_manual_review.csv` and take precedence over heuristic output.

### Separate case-count stage

Step `04b` writes `data/references/source_sps_case_count_registry.csv` and keeps extractable SPS case counts separate from the routing decision. That registry records the likely count, count confidence, count basis, and count manual-review flag.

### Text cleanup (`03b`)

Two-phase deterministic cleanup (no LLM rewriting):

- **Phase 1** (`text_cleanup.py`): mojibake repair, ligature normalisation, whitespace, and light boilerplate removal for reviewed papers listed in `config/extraction/text_cleanup_overrides.csv`
- **Phase 2** (`text_cleanup_stage2.py`): per-paper glyph/text substitution rules from `config/extraction/text_cleanup_stage2_substitutions.csv`, applied to papers in `config/extraction/text_cleanup_stage2_overrides.csv`

Pre-clean backups are preserved in `data/extraction_json/text_preclean/`.

### Secrets

Store as environment variables or in `env/*.env` files (gitignored). Required keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`.
