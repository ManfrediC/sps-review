# LangExtract Example Development Plan

## Objective

Build a robust, quote-grounded example bank for LangExtract that supports:
- individual-level (case report/case series) extraction
- group-level (cohort/aggregate) extraction
- publication-type detection for quality assessment
- quality assessment extraction across study designs

The immediate target is a 10-PDF, manually grounded pilot set.

## What I Reviewed

### Local data
- `config/prompts/examples` currently has:
  - `02_individual_examples.json` (1 example)
  - `02_group_examples.json` (1 example)
  - `03_publication_type_examples.json` (2 examples)
- `data/extraction_json/text` currently has 8 extracted papers:
  - `11849`, `118492`, `133`, `184`, `42`, `5676`, `5718`, `975`
- Text characteristics (current batch):
  - character count range: about 3.3k to 52.3k per paper
  - page count range: 1 to 11 pages
  - OCR flagged pre-extraction in 1/8 papers
  - one OCR-derived file shows visible artefacts/noise, so examples must include noisy text patterns.

### Online guidance (official and related)
- Official LangExtract repository/documentation: few-shot examples, source grounding, long-document batching/chunking, multi-pass extraction, OpenAI provider support.
- LangExtract medical examples: medication extraction and radiology-style structuring show quote-level grounding and class-then-attribute extraction patterns.
- LangExtract prompt validation code/docs: warning modes exist to detect prompt/example misalignment.
- Case report/case series quality frameworks:
  - JBI Case Report Checklist
  - JBI Case Series Checklist
  - Murad-style case report/series appraisal structure (selection, ascertainment, causality, reporting)

## Key Gaps To Address

1. Example coverage is currently too thin.
- One example per major extraction mode is not enough for heterogeneous clinical literature.

2. Publication-type coverage is incomplete.
- Current publication-type examples cover only 2 categories, while your quality dictionary expects 5:
  - `Observ Cohort & Cross sect`
  - `Case Control`
  - `Case Series & Reports`
  - `Before-After (Pre-Post) N contr`
  - `Controlled Intervention Studies`

3. Clinical narrative variability is not represented yet.
- Mixed papers (individual anecdotes plus aggregate results), OCR artefacts, and vague reporting need explicit examples.

4. Quality extraction examples are under-specified.
- Current script dynamically builds small examples; stronger publication-type-specific few-shot examples are needed, including explicit `NA` behaviour and evidence snippets.

## Example Strategy (Target State)

### A) Individual-level extraction examples (`02`)
Create 8-12 examples covering:
- classic single-case narrative
- case series sentence with one patient-level detail embedded
- atypical presentation wording
- treatment sequence with timeline
- outcomes with ambiguous improvement wording
- missing data to `NA`
- multi-item outputs requiring semicolon-separated values
- noisy OCR-like sentence fragments

### B) Group-level extraction examples (`02`)
Create 8-12 examples covering:
- retrospective/prospective cohorts
- cross-sectional summaries
- case-control aggregate reporting
- mixed denominator formats (`n/N`, `%`, subgroup counts)
- treatment exposure and response rates
- study limitations and bias caveats
- aggregate-only extraction when patient anecdotes are present
- noisy table-like text converted to prose

### C) Publication-type classification examples (`03`)
Create at least 3 examples per publication type (minimum 15 total):
- include one clear-positive and one borderline wording per type
- include confuser wording (for example, case-series language inside observational cohort papers)
- ensure exact label text matches dictionary categories

### D) Quality-assessment extraction examples (`03`)
Create publication-type-specific examples that show:
- binary items (`0`, `1`, `NA`) with short evidence
- categorical quality judgement (`poor`/`fair`/`good`)
- free-text notes where justified
- explicit handling of "not reported", "unclear", "not applicable"

For `Case Series & Reports`, anchor examples to JBI/Murad-style quality signals:
- clear inclusion criteria/case definition
- standard, valid condition measurement
- consecutive/incomplete inclusion clarity
- demographics/clinical information completeness
- outcome reporting completeness
- takeaway and adverse event reporting

## 10-PDF Quote-Grounded Pilot Workflow

### Phase 1: Select the 10-paper set
- Stratify by target use:
  - 4 case report/case series dominant papers
  - 4 cohort/group dominant papers
  - 2 mixed or difficult papers (OCR/noisy/ambiguous design)
- If fewer than 10 are currently ready, start with available papers and top up after additional extraction.

### Phase 2: Build a quote bank from your existing datasheet entries
- For each extracted variable, capture:
  - `paper_id`
  - `publication_type`
  - `field`
  - `value` (your curated value)
  - `evidence_quote` (verbatim text span)
  - `page_index` (or page label)
  - `notes` (why this quote supports the value)
- Keep quotes short and directly evidential.

### Phase 3: Convert quote bank into LangExtract examples
- Create task-specific example JSON files in `config/prompts/examples`:
  - `02_individual_examples.json`
  - `02_group_examples.json`
  - `03_publication_type_examples.json`
  - `03_quality_examples_<pubtype>.json` (recommended split) or one merged file
- Each example should use realistic text snippets and extraction labels exactly matching pipeline expectations.

### Phase 4: Dry-run and iterative refinement
- Run both pipelines in `--dry-run` first.
- Then run on the 10-paper set and review:
  - false positives from boilerplate text
  - missed fields (especially nuanced clinical features)
  - incorrect `NA` assignment
  - publication-type misclassification
- Update examples first; update prompt text second.

### Phase 5: Acceptance criteria for the pilot
- Publication type correct for at least 9/10 papers.
- For each mode (individual/group/quality), extracted evidence is visibly quote-grounded and auditable.
- Missingness coding follows project rule (`NA` only).
- No schema-validation failures in quality records.

## Practical Notes

- Keep one held-out subset (for example, 2/10 papers) for validation only.
- Prefer examples that include ambiguity and reporting imperfections, not only clean textbook phrasing.
- Maintain a changelog entry in `doc/JOURNAL.md` when examples/prompts are materially updated.

## Suggested Deliverables

1. `doc/example_quote_bank_template.csv` (simple annotation template)
2. expanded example JSON files under `config/prompts/examples`
3. one short evaluation note in `doc/` after the 10-paper pilot run

## References

- LangExtract GitHub: https://github.com/google/langextract
- LangExtract README (raw): https://raw.githubusercontent.com/google/langextract/main/README.md
- LangExtract medication example (raw): https://raw.githubusercontent.com/google/langextract/main/docs/examples/medication_examples.md
- LangExtract long-text example (raw): https://raw.githubusercontent.com/google/langextract/main/docs/examples/longer_text_example.md
- LangExtract prompt validation source (raw): https://raw.githubusercontent.com/google/langextract/main/langextract/prompting/prompt_validation.py
- Google Health AI Foundations: LangExtract page: https://developers.google.com/health-ai-developer-foundations/libraries/langextract
- JBI Case Report Checklist: https://jbi-global-wiki.refined.site/space/MANUAL/4687452/Checklist+for+Case+Reports
- JBI Case Series Checklist: https://jbi-global-wiki.refined.site/space/MANUAL/4687453/Checklist+for+Case+Series
