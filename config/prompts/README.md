# config / prompts

Prompt templates and few-shot examples for preliminary downstream extraction
and quality-assessment stages.

## Templates

- `02_individual_prompt.md`: individual-level LangExtract prompt.
- `02_group_prompt.md`: group-level LangExtract prompt.
- `03_publication_type_prompt.md`: publication-type prompt template.
- `03_quality_prompt.md`: quality-extraction prompt template.

## Examples

- `examples/02_individual_examples.json`
- `examples/02_group_examples.json`
- `examples/03_publication_type_examples.json`

Rebuild example JSONs from curated rows with:

```bash
python src/pipelines/09_build_langextract_examples.py
```

Stages 10 and 11 are preliminary, so prompt changes should be paired with
focused tests and review before relying on the outputs.
