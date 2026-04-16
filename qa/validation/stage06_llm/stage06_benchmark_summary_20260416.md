# Stage 06 Benchmark Summary

## Gold30

- Current heuristic-plus-GPT: `26/30` exact, `1` silent wrong auto-accept, `8` review rows
- Gemma-plus-GPT: `28/30` exact, `0` silent wrong auto-accepts, `10` review rows

## Gold20 Holdout

- Current heuristic-plus-GPT: `17/20` exact, `1` silent wrong auto-accept, `8` review rows
- Gemma-plus-GPT: `17/20` exact, `1` silent wrong auto-accept, `8` review rows
- Local-only Gemma checkpoint after the count-focused evidence patch: `17/20` exact, `0` silent wrong auto-accepts, `16` review rows

## Combined Gold50

- Current heuristic-plus-GPT: `43/50` exact, `2` silent wrong auto-accepts, `16` review rows
- Gemma-plus-GPT: `45/50` exact, `1` silent wrong auto-accept, `18` review rows

## Readout

- The Gemma-first workflow is ahead overall on the combined benchmark because it improved the first 30-paper slice without introducing new silent errors there.
- The 20-paper holdout did not widen the gap, but it did confirm that the local-only Gemma gate is useful for catching input-pack failures before GPT spend.
- The main remaining problems are now shared judgement or GPT-adjudication problems rather than Gemma JSON/interface problems.

## Next Targets

- `12137`: both workflows silently collapse a larger treated SPS cohort to `1`
- `560`: both workflows still overcount a lab-heavy paper as `1` instead of `0`
- `270`: both workflows undercount a very large cohort, though both already route it to review
- `184`: GPT still overrides a safer local abstention
- `629`: both workflows still miss the reviewed `1`
