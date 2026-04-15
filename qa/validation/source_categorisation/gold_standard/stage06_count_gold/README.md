# Stage-06 Count Gold JSON Corpus

This directory stores the per-paper gold-standard JSON corpus for stage 06 SPS case counts.

Files:
- `manifest.json`
  - corpus inventory with active, excluded, and conflict statuses
- `papers/{paper_id}.json`
  - one reviewed stage-06-style result payload per active paper

Each paper JSON freezes:
- the reviewed stage-06 `count_row`
- review provenance from `../04_categorisation_gold_standard.csv`
- the live source/count registry snapshots seen at bootstrap time
- any historical stage-06 run artefacts that could still be resolved

Regenerate with:

```bash
python src/validation/bootstrap_stage06_gold_json.py
```
