# Stage 07 XML Live 10-Paper Review

- Review pack: `qa\validation\stage07_xml\gold_standard\stage07_xml_live_test10_20260425\index.html`
- Review queue: `qa\validation\stage07_xml\gold_standard\stage07_xml_live_test10_20260425\review_queue.csv`
- Review responses: `qa\validation\stage07_xml\gold_standard\stage07_xml_live_test10_20260425\review_responses.csv`
- Stage 07 XML registry: `data\references\stage07_xml_registry.csv`
- Stage 07 output root: `data\extraction_json\stage07_xml\`
- Raw request and response traces: `results\stage07_xml_runs\stage07_xml_live_test10_20260425\`

## Outcome

- Papers run: 10 (`10`, `11`, `17`, `19`, `22`, `23`, `25`, `29`, `30`, `34`)
- Paid model calls: 8 GPT-5.5 calls
- Deterministic single-patient pass-throughs: 2 (`17`, `29`)
- Paper outputs ready for LangExtract now: 4 (`11`, `17`, `23`, `29`)
- Target views ready for LangExtract now: 5 (`11::g1`, `17::p1`, `23::p1`, `23::p2`, `29::p1`)
- Review-pack rows: 52
- Main result: the XML-style assignment idea is promising, but the first live batch exposed two must-fix implementation issues before scaling.

## Main Findings

- The strongest failure mode is coordinate fragility, not poor patient assignment. Most failed GPT outputs selected plausible text and target IDs, but provided offsets that did not exactly match the source block.
- Exact, unique relocation within the same source block appears sufficient to recover five failed papers: `10`, `19`, `22`, `25`, and `30`.
- Paper `34` is a separate routing or target-inventory problem. The upstream route treated it as a group paper, but the model found individual-level patient material and tried to assign `p1` and `p2`.
- The deterministic single-patient outputs are attribution-safe but too noisy for efficient downstream LangExtract. They currently include front matter, article boilerplate, references, and OCR artefacts.
- Shared or group-level statements need a tighter policy. For patient-split papers, statements applying to all patients should usually be shared across those patient IDs rather than assigned only to a separate group target.

## Paper Reviews

| Paper | Route | Current status | Review |
| --- | --- | --- | --- |
| `10` | individual case split | failed | The model found the expected two-patient structure and selected plausible patient-specific spans, but all eight spans failed exact offset validation. This looks recoverable with exact unique relocation inside each referenced block. Re-run after the relocation patch, then review the two patient pages visually. |
| `11` | group | passed | The group assignment is usable and ready. The table segment includes SPSD-relevant group evidence, but it may also expose non-SPSD myoclonus rows to LangExtract. Human review should check whether the table is acceptable as group context or whether table rows need diagnosis-aware trimming. |
| `17` | individual | passed | The single-patient pass-through is ready by contract, but the target view is broad and includes non-clinical front matter and noisy text. It is safe for attribution, but inefficient for LangExtract. Consider boilerplate/reference trimming or optional GPT annotation for single-patient articles. |
| `19` | individual case split | failed | The model found the expected two cases and the selected text appears structurally correct. Six spans failed offset validation, and both patient targets then lacked accepted evidence. This should be recoverable with exact unique relocation. |
| `22` | group | failed | One accepted group segment exists, but a second segment failed offset validation. Exact relocation should probably make the output ready. Separately, this paper deserves source-routing review because it may be a single SPSD case embedded in a mixed myoclonus context rather than a clean SPSD group. |
| `23` | individual case split | passed | This is the best positive example in the batch. The two patient targets and shared discussion/context are separated cleanly enough for LangExtract. Human review should still check the OCR-affected passages, but no structural patch is required for this paper. |
| `25` | group | failed | Five group-relevant segments were accepted and five failed offset validation. The selected content appears to focus on relevant group/laboratory evidence. Exact relocation should probably make it ready, after which human review should confirm whether the selected lab-heavy context is sufficient for extraction. |
| `29` | individual | passed | The single-patient pass-through is ready, but like `17` it is noisy. This is acceptable for a conservative first pass, but it will spend unnecessary LangExtract tokens unless we trim boilerplate and references. |
| `30` | individual case split | failed | The split is clinically promising: three patient targets plus a group context were identified, and 20 segments were accepted. A single offset mismatch blocks readiness. After relocation, review whether group-wide statements assigned to `g1` should also be shared to `p1`, `p2`, and `p3` so patient views do not miss all-patient facts. |
| `34` | group | failed | This is not mainly an offset problem. The model tried to assign material to `p1` and `p2`, but the route only declared `g1`, so validation rejected the patient targets. The paper needs a routing or validation-policy change for group-routed papers with individual-level patient evidence. |

## Technical Diagnosis

- Validation correctly rejects any span where `selected_text` differs from `source_block[start_offset:end_offset]`.
- In the failed papers, many rejected spans had a `selected_text` that appeared exactly once in the declared block at a different offset.
- A recovery simulation indicated:
  - `10`: 8 of 8 mismatched spans can be uniquely relocated.
  - `19`: 6 of 6 mismatched spans can be uniquely relocated.
  - `22`: 1 of 1 mismatched span can be uniquely relocated.
  - `25`: 5 of 5 mismatched spans can be uniquely relocated.
  - `30`: 1 of 1 mismatched span can be uniquely relocated.
  - `34`: 15 offset mismatches can be uniquely relocated, but the paper still fails because `p1` and `p2` are undeclared under the current group route.
- This supports a deterministic repair rule: if the supplied coordinates fail but `selected_text` occurs exactly once in the same source block, relocate to that exact occurrence and emit a validation warning. Do not use fuzzy matching.

## Recommended Next Changes

1. Add exact unique span relocation inside Stage 07 XML validation.
   - Scope: only same-block exact matches.
   - Audit: record the original and relocated offsets in validation warnings or segment metadata.
   - Expected effect: recover `10`, `19`, `22`, `25`, and `30`.

2. Add a route override or target expansion path for group-routed papers with clear individual-level evidence.
   - Trigger candidate: Stage 06 count greater than 1 plus individual case labels or model-proposed patient targets.
   - Expected effect: give `34` a valid `p1`/`p2` target inventory instead of forcing all evidence into `g1`.

3. Tighten shared-statement assignment for `individual_case_split`.
   - Prefer `target_ids=["p1", "p2", ...]` with `role="shared"` for statements that apply to all named patients.
   - Reserve `g1` for truly aggregate-only evidence that should not be copied into patient views.
   - Expected effect: improve patient-level completeness for papers like `30`.

4. Show rejected proposed spans in the human review pack.
   - Current failed pages may collapse to paper-level rows when no segment survives validation.
   - Reviewers should be able to see rejected model spans, validation errors, and target proposals without opening raw trace files.

5. Trim deterministic single-patient pass-through outputs before LangExtract.
   - Remove obvious front matter, journal boilerplate, references, correspondence text, and unusable OCR garbage where safe.
   - Keep the exact-source invariant for retained text.
   - Expected effect: reduce tokens and improve extraction focus for `17` and `29`.

## Human Review Priorities

1. Review `23` first as the positive control for the intended visual workflow.
2. Review `11`, `17`, and `29` to check whether ready outputs are acceptable for LangExtract despite broad context.
3. After exact relocation is patched, re-run `10`, `19`, `22`, `25`, and `30`, then review their colourised pages.
4. Hold `34` until routing or target-inventory handling is improved.
