# qa / validation / text_exports

Human-readable `.txt` exports built from `data/extraction_json/text/{paper_id}.json` for manual QA.

These folders are generated views over the canonical JSONs. When the canonical text changes, the corresponding selection CSVs in `qa/validation/` and the subset folders here should be refreshed together.

## Subdirectories

- `all/`
  - Full corpus export.
  - Contains one TXT per extracted paper JSON.

- `weaker_cases/`
  - Review subset for weaker or borderline extractions.
  - Used when the extraction is probably usable but not strong enough to trust without inspection.

- `weaker_text_quality_defects/`
  - Weaker-case subset where the JSON text itself shows spacing, tokenization, mojibake, or similar text-quality defects.

- `weaker_proceedings_context/`
  - Weaker-case subset where the JSON text appears to come from a supplement, abstract book, proceedings file, or issue-level context.

- `weaker_metadata_matching_only/`
  - Weaker-case subset where the JSON text looks broadly readable, but matching is weak mainly because of metadata variation, author formatting, or likely source-reference mismatch.

- `likely_failures/`
  - Review subset for the extraction outputs that still appear genuinely unresolved after QC.
  - This is the main folder to inspect when looking for papers that may need a better source PDF, different extraction route, or manual handling.

Historical snapshot folders may also exist here when an older generated set is preserved for before/after comparison.
