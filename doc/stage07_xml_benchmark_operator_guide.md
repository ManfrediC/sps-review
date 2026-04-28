# Stage 07 XML Benchmark Operator Guide

This guide describes the review and optimisation loop for Stage 07 XML/JSON.
The goal is to compare candidate configurations with reviewer-corrected gold
outputs, while keeping paid API calls explicit and all benchmark artefacts
contained under `qa/validation/stage07_xml/evaluation/{run_id}`.

## Principles

- Treat reviewer-edited DOCX packs as the source of truth after import.
- Keep paid API runs behind explicit approval. Benchmark rescoring can be run
  entirely from saved Stage 07 outputs.
- Keep candidate outputs, metrics, telemetry, and summaries inside the
  evaluation run directory.
- Keep reviewed annotations and regenerated gold outputs inside the existing
  DOCX or gold-standard review round directories.
- Do not write API keys, reasoning content, or other secrets to traces,
  telemetry, or reports.

## 1. Run Matrix Candidates

For saved local Stage 07 outputs, run the benchmark directly against the
candidate root. This does not call any model provider:

```powershell
python src\pipelines\stage07_benchmarking\run_stage07_benchmark.py `
  --paper-id 10 `
  --paper-id 11 `
  --paper-id 17 `
  --candidate-stage07-root data\extraction_json\stage07_xml `
  --candidate-registry-path data\references\stage07_xml_registry.csv `
  --evaluation-root qa\validation\stage07_xml\evaluation `
  --run-id local_saved_stage07_YYYYMMDD `
  --matrix-config-name local_saved_stage07
```

For live candidates, first run Stage 07 with an approved matrix/configuration
label and telemetry destination. This is the paid step when `--allow-paid-run`
is used:

```powershell
python src\pipelines\stage07_XML\run_stage07_xml.py `
  --paper-id 10 `
  --run-id stage07_xml_candidate_YYYYMMDD `
  --allow-paid-run `
  --benchmark-run-id candidate_eval_YYYYMMDD `
  --matrix-config-name O1_gpt55_medium_25k `
  --architecture-variant current_block_offsets `
  --telemetry-jsonl-path qa\validation\stage07_xml\evaluation\candidate_eval_YYYYMMDD\api_telemetry.jsonl `
  --telemetry-csv-path qa\validation\stage07_xml\evaluation\candidate_eval_YYYYMMDD\api_telemetry.csv
```

Then rescore the saved candidate outputs against reviewed gold:

```powershell
python src\pipelines\stage07_benchmarking\run_stage07_benchmark.py `
  --paper-id 10 `
  --candidate-stage07-root data\extraction_json\stage07_xml `
  --candidate-registry-path data\references\stage07_xml_registry.csv `
  --evaluation-root qa\validation\stage07_xml\evaluation `
  --run-id candidate_eval_YYYYMMDD `
  --matrix-config-name O1_gpt55_medium_25k `
  --api-telemetry-path qa\validation\stage07_xml\evaluation\candidate_eval_YYYYMMDD\api_telemetry.jsonl
```

The default matrix lives in `src/pipelines/stage07_benchmarking/matrix.py`.
Use the matrix names as stable labels for candidate runs; this keeps per-paper
scores, telemetry, and Pareto summaries joinable across batches.

## 2. Generate A DOCX Review Pack

Create the review pack from saved Stage 07 XML outputs:

```powershell
python src\validation\build_stage07_xml_docx_review_pack.py `
  --round-id stage07_xml_review_YYYYMMDD `
  --paper-id 10 `
  --paper-id 11 `
  --paper-id 17
```

The pack is written under:

```text
qa/validation/stage07_xml/docx_review/stage07_xml_review_YYYYMMDD/
```

Each paper has:

- `papers/{paper_id}.docx`
- `papers/{paper_id}.docx_metadata.json`
- `papers/{paper_id}.colour_legend_and_notes.md`

Edit the DOCX highlights/colours and the target legend so the document reflects
the desired gold segmentation. The importer infers reviewed Stage 07
annotations from those colours and regenerates XML/JSON gold outputs.

## 3. Import DOCX Feedback

Import the edited DOCX files and regenerate the gold outputs:

```powershell
python src\validation\import_stage07_xml_docx_review.py `
  --round-dir qa\validation\stage07_xml\docx_review\stage07_xml_review_YYYYMMDD `
  --force
```

To import the feedback and immediately rescore a saved candidate root:

```powershell
python src\validation\import_stage07_xml_docx_review.py `
  --round-dir qa\validation\stage07_xml\docx_review\stage07_xml_review_YYYYMMDD `
  --force `
  --rescore-candidate-stage07-root data\extraction_json\stage07_xml `
  --rescore-candidate-registry-path data\references\stage07_xml_registry.csv `
  --rescore-evaluation-root qa\validation\stage07_xml\evaluation `
  --rescore-run-id stage07_xml_review_YYYYMMDD_rescore `
  --rescore-matrix-config-name local_saved_stage07
```

This import-triggered rescore is offline. It uses the imported review as gold
and compares it with saved candidate Stage 07 outputs.

## 4. Artefact Locations

Benchmark run artefacts land in:

```text
qa/validation/stage07_xml/evaluation/{run_id}/
```

Important files are:

- `run_config.json`: selected papers, matrix entries, paths, and schema version.
- `paper_scores.csv`: one row per paper/configuration.
- `target_scores.csv`: per-target character precision, recall, and F1.
- `pareto_summary.csv`: accuracy, contamination, review burden, cost, and latency by configuration.
- `api_telemetry.csv` and `api_telemetry.jsonl`: one row per live API call, if supplied.
- `pricing_table.json`: local versioned pricing assumptions for cost estimates.
- `summary.json` and `summary.md`: compact run-level summary.

Reviewed annotations and regenerated gold outputs from DOCX import remain in
the DOCX review round directory, not in the benchmark directory.

## 5. Metrics

The benchmark computes:

- per-target source-character precision, recall, and F1
- per-paper micro precision, recall, and F1
- target inventory exactness
- missing and extra targets
- role attribution errors
- cross-target and unsafe-section contamination flags
- XML roundtrip and JSON validation status
- manual-review reasons, when a candidate registry is available
- ready-for-langextract calibration, including false-ready and false-not-ready counts
- estimated cost, token counts, latency, response status, and truncation status when telemetry is available

Readiness and manual-review columns depend on passing the candidate registry
that belongs to the candidate outputs being scored. If the registry omits a
paper, the benchmark still scores spans and contamination, but readiness
calibration for that paper is incomplete.

## 6. Promotion Gates

Interpret promotion gates in this order:

1. Contamination must be zero. Any cross-patient, cross-target, reference,
   methods, or background leakage blocks promotion.
2. Ready papers must have exact target inventory. Missing targets and
   unsupported extra targets block automatic readiness.
3. False-ready count must be zero. A candidate that marks a reviewer-failed
   paper as ready is unsafe even if average F1 is high.
4. Holdout precision and recall must meet the documented threshold for the
   matrix stage being evaluated.
5. Cost and latency are tie-breakers after safety and accuracy pass.

High F1 is not sufficient on its own. A configuration with perfect overlap but
one contamination flag remains a failed candidate until the source of the flag
is understood and fixed.

## 7. Tidy Workflow

- Use short run IDs that encode the batch and date.
- Reuse `qa/validation/stage07_xml/evaluation/{run_id}` for benchmark outputs;
  do not create ad hoc experiment directories.
- Keep API telemetry beside the benchmark run that uses it.
- Keep secrets in `env/` or the shell environment only. Do not copy key values
  into manifests, traces, telemetry, comments, or DOCX notes.
- Commit code and docs. Do not commit generated evaluation runs unless a
  specific run is being promoted as a durable validation fixture.
