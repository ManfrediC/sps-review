# Stage 06 b002 Review Notes

- Combined QA CSV: `qa\validation\stage06_llm\stage06_backfill_b002_n50_20260418_combined.csv`
- Inspection pack: `qa\validation\stage06_llm\stage06_backfill_b002_n50_20260418_inspection.md`
- Per-paper comments: `qa\validation\stage06_llm\stage06_backfill_b002_n50_20260418_review_comments.csv`

## Outcome

- Reviewed papers: 50
- `llm_bounded_alternative`: 1
- `llm_candidate_exact`: 38
- `llm_semantic_conflict_manual_review_required`: 1
- `manual_review_override`: 10

## Model-Based Triage

- Likely clean on first pass: 10, 17, 19, 80, 113, 121, 127, 133, 134, 139, 150, 154, 162, 166, 167, 182, 189, 190, 206, 213, 214, 220, 229, 231
- Likely user review candidates: 25, 34, 49, 58, 65, 95, 126, 155, 175, 185, 193, 197, 208, 211, 223, 228

## Resolved Manual Overrides

- `39 -> 13`: The competing counts are 13 from the interview and psychologic-testing cohort and 39 from the larger diagnosed/referral pool. The extractable SPS-spectrum count is 13 because only 13 patients were actually studied in this paper.
- `43 -> 33`: The extracted counts are 35 from the abstract total, 33 from Methods (`Sera were obtained with informed consent from 33 SMS patients identified ...`), and 9 from the HLA-haplotyped subgroup. The extractable SPS-spectrum count is 33 because the methods cohort is the main diagnosed sample counted under standard criteria.
- `92 -> 1`: The paper reports 3 paraneoplastic encephalomyelitis patients, but only patient 3 is clearly tied to rigidity and the SPS-spectrum signal. The safest extractable SPS-spectrum count is therefore 1.
- `102 -> 11`: The competing numbers are 11 patients and 105. The extractable SPS-spectrum count is 11 because 105 is the ICA 105 autoantigen name rather than a patient denominator.
- `140 -> 2`: The competing counts are 2 and 4. The extractable SPS-spectrum count is 2 because this paper reports two original stiff-leg syndrome patients, while 4 refers to previously published literature cases in the introduction.
- `146 -> 13`: The competing counts are 13 and 39. The extractable SPS-spectrum count is 13 because the paper reports interviews and psychologic testing on 13 studied patients, whereas 39 is the broader diagnosed pool from which they were drawn.
- `180 -> 1`: This is a single-patient paraneoplastic stiff-limb case report. The correct extractable SPS-spectrum count is 1; the earlier 8 came from unrelated stitched-issue text rather than the article itself.
- `191 -> 1`: The competing numbers are 1 and 135. The extractable SPS-spectrum count is 1 because this is a longitudinal single-case report; 135 is a page or table artefact from the PDF text layer.
- `219 -> 24`: The extractable SPS-spectrum count is 24 because the quality-of-life analysis is reported on 24 SPS patients who completed the study assessments. Smaller numbers in the paper refer to narrower subgroups or previously published overlap.
- `224 -> 43`: The competing counts are 43 and 7. The extractable SPS-spectrum count is 43 because the paper investigates 43 consecutive stiff-man-spectrum patients overall, while 7 is only the PERM subgroup row in the table.

## Priority Review Candidates

- `25`: Pipeline output: 30. Extracted counts seen: 30 (abstract_count_signal). GPT decision: candidate_exact; medium.
- `34`: Pipeline output: 2. Extracted counts seen: 2 (diagnosis_specific_direct_cohort_count; abstract_count_signal). GPT decision: candidate_exact; medium.
- `49`: pipeline output `18` still needs manual source comparison.
- `58`: Pipeline output: 3. Extracted counts seen: 3 (abstract_count_signal; diagnosis_specific_suffix_count; early_body_count_signal). GPT decision: candidate_exact; high.
- `65`: Pipeline output: 8. Extracted counts seen: 8 (title_count_signal; diagnosis_specific_named_cohort_count). GPT decision: candidate_exact; medium.
- `95`: Pipeline output: 9. Extracted counts seen: 9 (abstract_count_signal; diagnosis_specific_series_cohort_count; early_body_count_signal). GPT decision: candidate_exact; medium.
- `126`: Pipeline output: 1. Extracted counts seen: 1 (single_case_text_signal; source_single_case_default; source_single_case_override). GPT decision: candidate_exact; high.
- `155`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_override; case_report_marker_single_case; source_single_case_default), 2 (abstract_count_signal). GPT decision: candidate_exact; medium. The likelier count is still unclear because the candidate package surfaced competing counts: 1, 2.
- `175`: Pipeline output: 1. Extracted counts seen: 1 (diagnosis_specific_table_row_count), 2 (abstract_count_signal). GPT decision: candidate_exact; medium. The likelier count is still unclear because the candidate package surfaced competing counts: 1, 2.
- `185`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default). GPT decision: candidate_exact; medium.
- `193`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default). GPT decision: candidate_exact; medium.
- `197`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `208`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `211`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `223`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.
- `228`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium.

## Assistant QA Notes

- Reviewed overrides have already been folded into the combined QA CSV and these notes.
- Populate the paired review-comments CSV during manual batch QA for the remaining review candidates.