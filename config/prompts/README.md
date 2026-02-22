# Prompt Files

This directory stores editable prompts and few-shot examples for LangExtract pipelines.

## Files

- `02_individual_prompt.md`: prompt for individual-level extraction in `src/pipelines/02_LangExtract.py`
- `02_group_prompt.md`: prompt for group-level extraction in `src/pipelines/02_LangExtract.py`
- `03_publication_type_prompt.md`: publication-type prompt template for `src/pipelines/03_quality_assessment.py`
- `03_quality_prompt.md`: quality-extraction prompt template for `src/pipelines/03_quality_assessment.py`

## Examples

- `examples/02_individual_examples.json`
- `examples/02_group_examples.json`
- `examples/03_publication_type_examples.json`

## Template Placeholders

- `03_publication_type_prompt.md` uses `{options}`.
- `03_quality_prompt.md` uses `{publication_type}` and `{field_block}`.
