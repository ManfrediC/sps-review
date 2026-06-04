# Qwen/Ollama single-case extraction QA

This folder is for non-canonical pilot runs from
`src/validation/ollama_single_case_dry_run.py`.

Run payloads are ignored by default because prompts, raw responses, and parsed
JSON can contain source text excerpts or unreviewed model output. Force-add only
small curated summaries when they are useful review evidence.

Current local pilot summaries of interest:

- `pilot_10_dry_run_contract_refresh`: latest prompt/contract dry run for
  paper `12013`.
- `pilot_10_actual_preflight_12013_v3_salvage_revalidated`: stored-response
  revalidation after quote-salvage and allowed-value fixes.
- `pilot_10_actual_preflight_12013_hard_quote_order`: approved one-paper live
  Ollama run with the hard quote-order prompt.
