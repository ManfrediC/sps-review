# Stage-06 LLM Calibration

This folder stores non-canonical calibration outputs for the alternative stage-06 counting workflow in `src/pipelines/06_extract_sps_case_counts_LLM.py`.

The calibration runner keeps the existing stage-06 deterministic evidence packaging, asks a local Ollama-served `gemma4:e4b` model for a first-pass count, and then sends every selected row to GPT-5.4 during calibration.

## Inputs

- `data/extraction_json/text/{paper_id}.json`
- `data/extraction_json/text_proceedings_ready/{paper_id}.json` when available
- `data/references/source_categorisation_registry.csv`

## Outputs

- One QA CSV per run, usually named `{run_id}.csv`
- Per-run artefacts under `results/stage06_count_llm_runs/{run_id}/`

The QA CSV preserves the usual stage-06 count columns and appends calibration fields such as:

- `local_model_name`
- `local_model_status`
- `local_n_spsd_patients`
- `local_confidence`
- `local_needs_review`
- `local_data_granularity`
- `local_evidence_span`
- `local_reasoning_short`
- `local_possibility_count`
- `local_validation_flags`
- `local_result_json_path`
- `local_vs_gpt_status`

## Run

Estimate-only:

```bash
python src/pipelines/06_extract_sps_case_counts_LLM.py --estimate-only
```

Focused calibration run:

```bash
python src/pipelines/06_extract_sps_case_counts_LLM.py --allow-paid-run --paper-id 214 --paper-id 724
```

## Notes

- These outputs are QA artefacts only and should not replace `data/references/source_sps_case_count_registry.csv` directly.
- The local model is advisory during calibration. GPT-5.4 still runs on every row in this workflow.
- If the local model fails to parse or violates a deterministic guardrail, the QA row records that status and still continues to GPT.
