# Work Log

## 2026-04-11

- Replayed the reviewed stage-05 trimming regression set in eight tranches under `qa/trimming/reports/stage05_regression_guard/`.
- Added a dedicated regression guard for reviewed stage-05 cases so regenerated outputs are checked against explicit reviewer feedback first and historical reviewed JSON spans otherwise.
- Patched stage 05 to remove the generic trailing DOI trim that had regressed historical reviewed cases, then added explicit compatibility overrides for reviewed legacy exceptions.
- Patched stage 05b so a solitary trailing DOI gap no longer triggers a false truncation warning, and so reviewed exact-span compatibility overrides remain QC-accepted.
- Tightened feedback end-anchor handling to cope with reviewer shorthand such as leading `...` and OCR-merged tail text.
- Refreshed `batch_011` on the patched stage-05 baseline so the next 10-paper review batch is ready in `qa/trimming/reports/batch_011/`.
