# Stage 06 b002 Review Notes

- Combined QA CSV: `qa\validation\stage06_llm\stage06_backfill_b002_n50_20260418_combined.csv`
- Inspection pack: `qa\validation\stage06_llm\stage06_backfill_b002_n50_20260418_inspection.md`
- Per-paper comments: `qa\validation\stage06_llm\stage06_backfill_b002_n50_20260418_review_comments.csv`

## Outcome

- Reviewed papers: 50
- `llm_bounded_alternative`: 2
- `llm_candidate_exact`: 42
- `llm_manual_review_required`: 2
- `llm_semantic_conflict_manual_review_required`: 4

## Model-Based Triage

- Likely clean on first pass: 10, 17, 19, 80, 113, 121, 127, 133, 134, 139, 150, 154, 162, 166, 167, 182, 189, 190, 206, 213, 214, 220, 229, 231
- Likely user review candidates: 25, 34, 39, 43, 49, 58, 65, 92, 95, 102, 126, 140, 146, 155, 175, 180, 185, 191, 193, 197, 208, 211, 219, 223, 224, 228

## Resolved Manual Overrides

- None applied for this batch.

## Recommended QA Order

- `180`: output `8`, but the extracted text pack appears unrelated to the paper and does not support any SPS-spectrum cohort at all. Treat this as the main routing/text-quality failure in `b002`.
- `92`: output `2`, but the evidence points to a broader three-patient paraneoplastic encephalomyelitis paper with only one patient clearly tied to rigidity/myoclonus. This needs a direct source read before trusting any SPS-spectrum count.
- `43`: current output is bounded to `35`, while the candidate package only surfaced `9`. The likely story is full SMS cohort `35` versus HLA-haplotyped subgroup `9`, but this should be confirmed in the source because GPT had to recover beyond the explicit candidate package.
- `39`: output `13`, with competing `4`. `13` looks like the full SMS cohort and `4` the tumour-associated subset, but seven of the 13 were reportedly described previously, so this is both a subgroup and provenance question.
- `224`: output `43`, with competing `7`. `43` likely represents the umbrella stiff-man-spectrum cohort, while `7` is the PERM subgroup row from the table.
- `102`: output `11`, with competing `105`. `11` looks right; `105` appears to be the ICA 105 autoantigen name rather than a patient count.
- `140`: output `2`, with competing `4`. `2` likely reflects the original case series, while `4` appears to be previously published literature cases mentioned in the introduction.
- `146`: output `13`, with competing `39`. `13` looks like the actually studied psychologic-testing cohort, while `39` is the identified/referral pool.
- `219`: output `24`, with competing `9`. `24` looks like the cohort who completed the quality-of-life study; the main caution is that six patients were published previously.
- `191`: output `1`, with competing `135`. `1` is probably the true single-case count and `135` looks like a page or table artefact.

## Probably Correct But Provenance-Sensitive

- `25 -> 30`: explicit SMS cohort, but the paper also references a larger previously studied SMS sample, so this is mostly a reuse/provenance check.
- `34 -> 2`: two SMS antisera/patients are reported consistently, but the paper itself flags relation to previously reported antisera.
- `49 -> 18`: GPT recovered `18` from HLA-typed SMS patients even though the heuristic candidate package did not surface a clean count; likely a brief-letter provenance issue rather than a real numeric conflict.
- `58 -> 3`: the open-label IVIG cohort of three looks consistent across abstract, body, and table; the main reason it is still flagged is cohort provenance uncertainty.
- `65 -> 8`: the title, abstract, and Table 1 all support eight SMS patients; the flag is mainly because some preliminary findings and at least two patients were published previously.
- `95 -> 9`: nine patients were studied, but several appear to overlap with earlier reports.

## Likely Correct Single-Case Or Low-Noise Rows

- `126 -> 1`: semantic flag only; the paper reads as one SMS case plus comparator IDDM/control material.
- `155 -> 1`: likely one case, with `2` coming from surrounding comparison language rather than a true SPS cohort.
- `175 -> 1`: likely one non-diabetic SMS index patient, with the extra `2` coming from comparison patients.
- `185 -> 1`, `193 -> 1`, `197 -> 1`, `208 -> 1`, `211 -> 1`, `223 -> 1`, `228 -> 1`: all look like single-case or single-index-patient papers, but the extracted text is noisy enough that a quick source confirmation is still worthwhile.

## Assistant QA Notes

- No reviewed override rows were available for this batch when these notes were generated.
- Most `b002` risk comes from three patterns: subgroup-versus-full-cohort conflicts, previously reported/potentially reused patients, and a smaller set of OCR or routing artefacts.
- If time is limited, review `180`, `92`, `43`, `39`, and `224` first.
- Use the paired review-comments CSV to record the final adjudication and note which competing number won.
