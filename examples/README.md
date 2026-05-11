# examples

Curated example rows used to build few-shot prompt assets and validate
extraction behaviour.

Current use:

- stage-09 example generation reads these files to rebuild
  `config/prompts/examples/*.json`.
- stage-04 and stage-06 validation workflows may exclude or compare against
  curated example papers.

Regenerate prompt examples with:

```bash
python src/pipelines/09_build_langextract_examples.py
```
