# config/

This directory contains **version-controlled configuration files** used across the SPS extraction and QC pipeline.  
Everything here is treated as *pipeline definition* (inputs to code), not run output.

## Structure

- `schema/`
  - JSON Schemas used to **constrain LLM outputs** (where supported) and to **validate extracted records** during automated QC.
  - Files:
    - `sps_case_extraction.schema.json`
    - `sps_quality_assessment.schema.json`

- `dictionaries/`
  - Human-readable “source of truth” dictionaries (CSV) describing each column (meaning, accepted values, data type).
  - These dictionaries are used to generate/update the JSON Schemas and to keep extraction guidance consistent.
  - Typical files:
    - `SPS_column_dictionary.csv`
    - `SPS_quality_dictionary.csv`

## Conventions

- Schemas use `additionalProperties: false` to catch unexpected fields early.
- Missingness codes are standardised where possible (commonly `NR`, `NA`, `CD`) to keep downstream analysis consistent.