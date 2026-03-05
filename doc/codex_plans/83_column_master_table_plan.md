# 83-Column Master Table Implementation Plan

Date: 2026-03-04
Goal: Build a canonical master table with one row per paper and the 83 case-report fields from `config/dictionaries/SPS_column_dictionary.csv`.

## Objective

Create a reproducible pipeline that outputs:

- `data/references/paper_83col_master.csv`

with:

- one row per `paper_id`
- fixed 83-column field order from the dictionary
- explicit handling of missing/unavailable data
- provenance and validation support

## Plan

1. Define the row contract and output policy.
- One row per paper (`paper_id`).
- Include all 83 dictionary fields.
- Add minimal provenance columns (e.g., `paper_id`, source path, route category, extractor/model version, timestamp).
- Decide and document multi-case representation for one-row-per-paper output:
- recommended: join multi-values with `;` and add `row_granularity=paper`.

2. Compile dictionary into machine schema.
- Implement `src/pipelines/13_build_case_report_schema.py`.
- Parse `SPS_column_dictionary.csv` into a JSON schema artifact containing:
- field order
- data type
- accepted values
- entry guidance
- version metadata

3. Implement explicit missing-data states.
- Per field status values:
- `filled`
- `na_not_reported`
- `na_not_applicable`
- `unclear_conflict`
- Keep status in metadata, not mixed into value text.

4. Add field applicability by source category.
- Create config mapping field applicability to resolved source categories.
- Automatically mark non-applicable fields as `na_not_applicable`.

5. Implement field-level extraction engine.
- Implement `src/pipelines/14_extract_case_report_fields.py`.
- Inputs:
- extracted text artifacts (full/trimmed/split as applicable)
- resolved routing metadata
- compiled schema artifact
- For each applicable field:
- attempt extraction
- produce value + status + confidence
- require evidence quote/page for `filled` values

6. Implement normalization and validation.
- Implement `src/pipelines/15_validate_case_report_fields.py`.
- Enforce:
- accepted values for categorical fields
- numeric parsing/type constraints
- evidence presence for `filled`
- valid status values
- Emit validation flags and conflict diagnostics.

7. Build the final master table writer.
- Implement `src/pipelines/16_build_case_report_master_table.py`.
- Flatten per-paper structured artifacts into:
- `data/references/paper_83col_master.csv`
- Preserve stable column ordering and deterministic rebuild behavior.

8. Add reviewer queue outputs.
- Generate:
- `data/references/case_report_field_review_queue.csv`
- Include low-confidence and `unclear_conflict` fields with evidence pointers.

9. Pilot in staged batches.
- Pilot A: 10 single-case papers.
- Pilot B: 50 mixed papers.
- Track:
- field fill-rate
- invalid-value rate
- conflict rate
- manual correction burden

10. Integrate into canonical pipeline sequence.
- Insert stages after routing/trim/QC/split:
- `13_build_case_report_schema.py`
- `14_extract_case_report_fields.py`
- `15_validate_case_report_fields.py`
- `16_build_case_report_master_table.py`
- Keep `10_langextract.py` as narrative/high-level extraction layer, separate from this field-level pipeline.

## Acceptance Criteria

- Master table is reproducible from artifacts (no manual edits required in final CSV).
- All 83 fields are present in the correct order for every paper row.
- Missing values are explicit via status policy.
- Filled values have supporting evidence metadata.
- Validation catches type/value violations before final CSV generation.
