# config

Version-controlled configuration files used across the SPSD extraction and QA
pipeline. Files here are pipeline definitions, not generated run outputs.

## Subdirectories

- `extraction/`: reviewed per-paper controls for text extraction and cleanup.
  Important files include:
  - `text_extraction_overrides.csv`
  - `text_cleanup_overrides.csv`
  - `text_cleanup_stage2_overrides.csv`
  - `text_cleanup_stage2_substitutions.csv`
- `schema/`: JSON Schemas used to constrain and validate structured extraction
  and quality-assessment outputs.
- `dictionaries/`: CSV data dictionaries that define extraction fields, coding
  rules, and accepted value semantics.
- `prompts/`: prompt templates and generated few-shot example JSONs for
  preliminary LangExtract and quality-assessment stages.

## Conventions

- Schemas use `additionalProperties: false` where practical to catch unexpected
  fields early.
- Missingness codes are standardised where possible, commonly `NR`, `NA`, and
  `CD`.
- Do not store secrets here. Runtime credentials belong in environment variables
  or ignored local `env/*.env` files.
