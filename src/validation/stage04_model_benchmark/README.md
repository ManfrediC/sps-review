## Stage-04 Model Benchmark

This module builds and scores a fixed 20-paper benchmark for stage-04 model comparison.

Goals:
- reuse cached `gpt-4.1` outputs without regenerating them
- freeze exactly the same payloads for all newly run models
- compare model behaviour on both clear and ambiguous papers
- record `tiktoken` prompt estimates before any paid API run

Layout:
- `build_benchmark_set.py`
  - selects a fixed mixed 20-paper benchmark from reviewed stage-04 gold rows
  - seeds auxiliary gold fields for:
    - original SPS data yes/no
    - individual-level data presence
    - group-level data presence
    - ambiguity tier
- `freeze_payloads.py`
  - assembles and saves the exact `PaperPayload` and formatted user message for every benchmark paper
  - records per-model `tiktoken` prompt estimates for:
    - `gpt-4.1`
    - `gpt-5.4`
    - `gpt-5.4-mini`
    - `gpt-5.4-nano`
- `run_models.py`
  - runs the benchmark payloads through the benchmark models
  - uses the same schema, validator logic, and adjudication policy as the canonical stage-04 pipeline
  - keeps `gpt-4.1` cached-only by default, but allows an explicit `--allow-baseline-regeneration` rerun on the frozen set when full structured outputs are needed
- `score_models.py`
  - compares cached `gpt-4.1` outputs with the newly run models
  - reports partial scoring for `gpt-4.1` where raw structured outputs are unavailable
- `review_app.py`
  - lightweight Streamlit reviewer for benchmark papers
  - shows the source PDF, gold labels, side-by-side model outputs, and optional per-paper review notes

Benchmark artefacts are written under:

- `qa/validation/source_categorisation/model_benchmark/<benchmark_id>/`

Expected workflow:

```bash
python src/validation/stage04_model_benchmark/build_benchmark_set.py
python src/validation/stage04_model_benchmark/freeze_payloads.py
python src/validation/stage04_model_benchmark/run_models.py --estimate-only
python src/validation/stage04_model_benchmark/run_models.py --allow-paid-run
python src/validation/stage04_model_benchmark/score_models.py
streamlit run src/validation/stage04_model_benchmark/review_app.py
```

Notes:
- Cached `gpt-4.1` rows are loaded from flattened registries only.
- If `model_outputs/gpt-4.1/predictions.jsonl` exists, scoring prefers those fresh raw outputs over the cached flattened baseline.
- Metrics that require raw structured outputs, such as evidence-quality scoring and `original_sps_spectrum_data`, may be unavailable for `gpt-4.1`.
- The benchmark set seeds auxiliary gold fields automatically, but keeps them explicit in `benchmark_set.csv` so they can be checked and edited before scoring.
- Review notes from the Streamlit app are written to `review_notes.csv` inside the benchmark directory.
