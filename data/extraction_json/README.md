# data / extraction_json

Machine-readable JSON artefacts produced by extraction, proceedings
preparation, case-series splitting, and preliminary downstream extraction
stages.

Most contents are ignored by git because they are generated or bulky. Tracked
registries under `data/references/` record which JSON artefacts exist and how
they should be interpreted.

## Live Paths

- `covidence/download_manifest.jsonl`: Covidence PDF-download manifest from
  stage 01.
- `text/{paper_id}.json`: canonical full extracted text after any reviewed
  cleanup.
- `text_preclean/{paper_id}.json`: backup before stage-03b deterministic
  cleanup.
- `text_preclean_stage2/{paper_id}.json`: backup before reviewed residual
  cleanup.
- `text_trimmed_llm_candidates/{paper_id}.json`: stage-05 proceedings
  end-candidate packages.
- `text_trimmed_llm/{paper_id}.json`: stage-05b validated LLM proceedings trims.
- `text_proceedings_ready/{paper_id}.json`: stage-05c canonical downstream
  proceedings-ready text layer.
- `text_case_series_units/{paper_id}.json`: current stage-07 unit packages for
  selected multi-case papers.

## Preliminary Downstream Paths

- `langextract/{paper_id}.json`: raw LangExtract outputs from stage 10.
- `summary/{paper_id}.json`: summary outputs from stage 10.
- `quality/raw/{paper_id}.json`: raw quality-assessment model output.
- `quality/records/{paper_id}.json`: structured quality-assessment records.

Everything after stage 07 is preliminary and should not yet be treated as final
review data.

## Historical Paths

- `text_trimmed/`: older deterministic proceedings trims retained for
  provenance/fallback compatibility.
- `text_case_series_split/`: historical case-series split path. Current stage-07
  outputs use `text_case_series_units/`.
- `text_trimmed_trial*`: archived trial proceedings outputs if present.

Use `data/references/paper_artifact_registry.csv` and
`data/references/case_series_split_registry.csv` for the authoritative current
path for a paper.
