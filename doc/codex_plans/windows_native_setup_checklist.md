# Windows-Native Overnight Setup Checklist

## Environment Decision
- Keep the current Windows-native setup.
- `venv` is equivalent enough to Conda for this repo's current use case: both isolate the Python runtime and installed packages.
- Conda would only be necessary if the project needed a second environment manager for binary dependency resolution. That is not justified here because the repo already works with `.venv`, and OCR/browser dependencies are already installed at the system level.

## Canonical Output Contract
- Keep `data/` and `data/references/` as the canonical artifact locations.
- Use `results/overnight/` only for orchestration logs, calibration reports, and per-stage stdout/stderr traces.

## Source Categorisation Placement
- Run source categorisation on extracted text, not on raw PDFs.
- Preferred input order:
  1. `data/extraction_json/text_trimmed/*.json` when a trimmed proceedings record exists
  2. `data/extraction_json/text/*.json` otherwise
- Reason:
  - OCR, proceedings trimming, and text normalisation already happen before this point.
  - Classification features are easier to express from text than from PDF structure.
  - The classifier can still enrich its decision with metadata from the reference registries if needed.

## Case-Series Splitting Placement
- Run case-series splitting after source categorisation and before LangExtract.
- Restrict splitting to sources classified as multi-case or likely multi-case.
- Write split-case artefacts as a new derived layer instead of overwriting the original text JSON.

## Gemini Key Placement
- Place the Gemini key in `env/gemini.env` as:

```env
GEMINI_API_KEY=your-key-here
```

- That path is already covered by the repo's `env/*.env` ignore rule.
- Future scripts should resolve keys in this order:
  1. explicit CLI flag
  2. process environment
  3. `env/gemini.env`

## Recommended Calibration Gates

### Text Extraction QC
- Validate a stratified sample before any full downstream run.
- Proceed only if:
  - `0` source/reference linkage errors are found in the sample
  - at least `90%` of sampled papers have usable text for the intended downstream stage
  - no systematic OCR failure mode is detected

### Source Categorisation
- Build an initial manually labelled calibration set of `50` sources.
- Proceed to full-corpus classification only if:
  - macro-F1 is at least `0.90`
  - no critical class has precision below `0.85`
  - proceedings/program sources are not being systematically misclassified as single-paper clinical reports

### Case-Series Splitting
- Validate on a manually reviewed set of at least `20` multi-case papers.
- Proceed only if:
  - split-needed detection agreement is at least `0.95`
  - extracted case count matches the manual answer in at least `0.90` of papers
  - key per-case fields remain aligned after splitting in at least `0.90` of reviewed cases

### LangExtract
- Run a pilot on a curated subset first.
- Proceed to broad execution only if manual review shows:
  - at least `90%` of reviewed extracted values are explicitly supported by the source text
  - unsupported hallucinated values are at or below `5%`

### Model Comparison
- No automatic threshold is required.
- Produce comparable outputs from both providers and decide the winner by manual review.

## Immediate Build Tasks
1. Add repo-scoped Codex control files:
   - `.codex/config.toml`
   - `.codex/rules/sps_overnight.rules`
   - root `AGENTS.md`
2. Add a Windows-native overnight runner that logs stage execution without changing canonical output locations.
3. Implement `04_source_categorisation_LLM.py` as the canonical LLM stage and retain the heuristic under `src/legacy/`.
4. Implement `07_split_case_series.py`.
5. Implement `04_model_comparison.py`.
6. Expand LangExtract few-shot examples using the curated material in `examples/`.
7. Run a small end-to-end pilot before any unattended full-corpus run.
