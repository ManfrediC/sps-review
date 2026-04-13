# data

## Purpose
Canonical research artifacts and generated data products used by the pipeline.

## Key canonical outputs

- `extraction_json/text/`
  Full extracted and reviewed source text JSONs.
- `extraction_json/text_trimmed/`
  Legacy deterministic proceedings trims retained for provenance and fallback use.
- `extraction_json/text_trimmed_llm_candidates/`
  Stage-05 LLM candidate packages for proceedings end-boundary review.
- `extraction_json/text_trimmed_llm/`
  Final LLM-reviewed proceedings trims.
- `extraction_json/text_proceedings_ready/`
  Canonical proceedings-ready text JSONs used by downstream stages.
- `references/text_trim_llm_candidate_registry.csv`
  Registry for the LLM candidate-generation pass.
- `references/text_trim_llm_registry.csv`
  Registry for the final LLM validation pass.
- `references/text_proceedings_ready_registry.csv`
  Registry for the canonical proceedings-ready publication layer.
- `references/paper_artifact_registry.csv`
  Cross-pipeline provenance table linking the reference, source text, proceedings artefacts, and downstream outputs.

## Directory Contents Snapshot
- Last updated: `2026-04-13`
- Immediate subdirectories (5): `excel`, `extraction_json`, `pdf_annotated`, `pdf_original`, `references`
- Immediate files (0, excluding `README.md`): _None_
