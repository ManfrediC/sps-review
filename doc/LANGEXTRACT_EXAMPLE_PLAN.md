# LangExtract Example Compendium Plan

## Goal

Use your manually extracted datasheet examples as the primary source of truth, pair each extracted value with supporting PDF quotes, and build a large reviewed compendium of examples for LangExtract.

This compendium will support:
- individual-level extraction (case report and case series content)
- group-level extraction (cohort/aggregate content)
- quality assessment extraction (publication-type specific)
- publication-type classification

## Current State (After Your Cleanup)

I rechecked the CSV exports in `examples/`:
- trailing empty rows: none found
- headers: now single-row/regular in the exported files

Current file sizes and usable row counts:
- `examples/datasheet_examples_MC_Case_Report_Form.csv`: 288 data rows
- `examples/datasheet_examples_MC_Case_Series_Reports.csv`: 181 data rows
- `examples/datasheet_examples_MC_Cohorts.csv`: 23 data rows
- `examples/datasheet_examples_MC_Observ_Cohort_Cross_sect.csv`: 16 data rows

Prompt-example status remains minimal:
- `config/prompts/examples/02_individual_examples.json`: 1 example
- `config/prompts/examples/02_group_examples.json`: 1 example
- `config/prompts/examples/03_publication_type_examples.json`: 2 examples

## Core Principle

Do not train from synthetic examples first. Start from your manually curated rows, attach real evidence quotes from source PDFs, manually review, then convert accepted rows into LangExtract few-shot examples.

## Target Artefacts

### 1) Master compendium table
Create a single review table (CSV) at:
- `data/training_compendium/langextract_example_compendium.csv`

Proposed columns:
- `paper_id`
- `source_pdf`
- `publication_type`
- `task` (`individual`, `group`, `quality`, `pubtype`)
- `field`
- `target_value`
- `quote`
- `page_index`
- `quote_char_start`
- `quote_char_end`
- `evidence_strength` (`high`, `medium`, `low`)
- `status` (`draft`, `reviewed`, `accepted`, `rejected`)
- `review_notes`

### 2) Source registry
Track PDF provenance and retrieval status in:
- `data/training_compendium/pdf_source_registry.csv`

Columns:
- `paper_id`
- `reference`
- `doi_or_url`
- `pdf_filename`
- `download_status`
- `copyright_notes`

### 3) Accepted LangExtract example files
Generate from accepted compendium rows:
- `config/prompts/examples/02_individual_examples.json`
- `config/prompts/examples/02_group_examples.json`
- `config/prompts/examples/03_publication_type_examples.json`
- `config/prompts/examples/03_quality_examples_<publication_type>.json` (recommended split)

## Phased Plan

### Phase 1: Normalise and map the manual datasets
- Standardise keys across the four datasheet exports (`paper_id`, `reference`, publication type).
- Harmonise field names to dictionary/schema names where needed.
- Produce one merged intermediate table with source sheet tags.

### Phase 2: Acquire and register source PDFs
- Download or collect PDFs corresponding to the manual rows.
- Populate `pdf_source_registry.csv` with DOI/URL and file mapping.
- Store PDFs in your raw PDF input directory for pipeline compatibility.

### Phase 3: Process PDFs to text JSON
- Run `src/pipelines/01_extract_text.py` on the acquired PDFs.
- Keep OCR fallback enabled for image-based files.
- Verify each paper has:
  - text JSON output
  - stable `paper_id`
  - usable page text coverage

### Phase 4: Build draft quote links from manual values
- For each manual row and target field, find candidate quote spans in extracted text.
- Record best candidate quote plus page index and character offsets.
- Mark confidence as `high`/`medium`/`low`.
- Save everything as `draft` in the compendium.

### Phase 5: Manual review loop (critical)
- Review draft quote-value matches in batches (for example, 100 rows at a time).
- Keep only high-quality, directly evidential mappings.
- Set status to `accepted` or `rejected`, with notes for failures.

### Phase 6: Compile accepted rows into LangExtract examples
- Convert accepted rows into task-specific few-shot JSON.
- Ensure extraction class names match pipeline expectations exactly.
- Preserve realistic, noisy, and ambiguous examples (not only clean sentences).

### Phase 7: Validate with held-out papers
- Reserve a held-out subset not used for example creation.
- Run:
  - `src/pipelines/02_LangExtract.py`
  - `src/pipelines/03_quality_assessment.py`
- Compare outputs to manual gold rows and record error patterns.

### Phase 8: Iterate examples first, prompts second
- First fix performance by improving example coverage/diversity.
- Only then adjust prompt wording when a pattern cannot be solved by examples alone.

## Coverage Targets

### Publication-type classification (`03`)
Minimum 3 accepted examples per quality publication type:
- `Observ Cohort & Cross sect`
- `Case Control`
- `Case Series & Reports`
- `Before-After (Pre-Post) N contr`
- `Controlled Intervention Studies`

### Individual extraction (`02`)
At least 10 accepted examples spanning:
- symptom onset language variation
- treatment sequences and timing
- outcome trajectories
- explicit missingness (`NA`)
- OCR noise and imperfect wording

### Group extraction (`02`)
At least 10 accepted examples spanning:
- cohort descriptors and sample composition
- percentages and denominators
- treatment response summaries
- limitations and bias language

### Quality extraction (`03`)
At least 8 accepted examples per publication type, including:
- binary items (`0`, `1`, `NA`)
- quality category (`poor`, `fair`, `good` where applicable)
- free-text notes when required by the dictionary

## Acceptance Criteria

- Every example in prompt JSON is traceable to at least one reviewed quote in the compendium.
- No unresolved header/key mismatches between manual data and dictionaries.
- `NA` handling is consistent with project rules.
- Quality outputs pass schema validation.
- Publication-type classification is robust across held-out papers.

## Practical Notes

- Start with a 10-PDF pilot, then scale once review workflow is stable.
- Keep compendium rows small and auditable rather than building oversized unreviewed examples.
- Add concise progress entries to `doc/JOURNAL.md` after each completed phase.

## References

- LangExtract GitHub: https://github.com/google/langextract
- LangExtract README (raw): https://raw.githubusercontent.com/google/langextract/main/README.md
- LangExtract medication example (raw): https://raw.githubusercontent.com/google/langextract/main/docs/examples/medication_examples.md
- LangExtract long-text example (raw): https://raw.githubusercontent.com/google/langextract/main/docs/examples/longer_text_example.md
- LangExtract prompt validation source (raw): https://raw.githubusercontent.com/google/langextract/main/langextract/prompting/prompt_validation.py
- Google Health AI Foundations: https://developers.google.com/health-ai-developer-foundations/libraries/langextract
- JBI Case Report Checklist: https://jbi-global-wiki.refined.site/space/MANUAL/4687452/Checklist+for+Case+Reports
- JBI Case Series Checklist: https://jbi-global-wiki.refined.site/space/MANUAL/4687453/Checklist+for+Case+Series
