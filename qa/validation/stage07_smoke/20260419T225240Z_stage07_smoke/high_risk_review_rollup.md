# 20260419T225240Z Stage-07 High-Risk Review Roll-up

- Run folder: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke`
- Selection JSON: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\selection.json`
- Combined QA CSV: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\20260419T225240Z_stage07_smoke_combined.csv`
- Inspection pack: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\20260419T225240Z_stage07_smoke_inspection.md`
- Scope: `10` stage-06-finalised papers reviewed after stage-07 GPT-5.4 adjudication

## Headline judgement

- `559` is the only near-clean auto-publish candidate in this batch, but I would still tidy `Patient 2` before treating it as truly canonical.
- `140`, `239`, and `748` have useful patient splits, but all three still attach too much cross-patient or non-clinical material, so I agree with keeping them as partial outputs rather than clean publication.
- `456` looks genuinely recoverable. The paper text contains explicit subject-level material, but the current boundary logic is not stable enough yet.
- `668`, `679`, `766`, and `776` are correctly withheld on attribution-safety grounds.
- `715` is best understood as an upstream text-selection failure, not a splitter failure.

## Best current candidate

### `559` - Antiglycine-receptor encephalomyelitis with rigidity.

Stage-06 prior: `count=3`, `count_confidence=high`, `count_verification_status=manual_review_override`. No canonical granularity is populated.

Stage-07 output: `publish_all_units`; `3` individual units; `2` shared-context blocks; no unresolved remainder.

Extracted:
`Patient 1` (`p0:81-107`) is a coherent case narrative for a 33-year-old woman with autoimmune thyroiditis, brainstem symptoms, later lower-limb rigidity and spasms, abnormal EMG, negative GAD/onconeural antibodies, steroid/diazepam/baclofen response, later relapse, IVIG, and long-term follow-up.
`Patient 2` (multi-span across `p0:108-141` and `p1:0-21`) is a coherent clinical case for a 60-year-old man with dysphagia, spasms, brainstem features, GlyR antibodies, severe progression, seizures, autonomic instability, cardiac arrest, and persistent vegetative state.
`Patient 3` (`p1:22-51`) is a coherent case for a 48-year-old man with pruritus, behavioural change, dysgeusia, hypersomnia, right-leg rigidity, trismus/opisthotonic spells, GlyR antibodies, and partial improvement after IVIG plus corticosteroids.

Pipeline rationale: the deterministic splitter found three explicit patient headings and matched the stage-06 count. GPT-5.4 independently agreed that there were three attribution-safe case units, but its adjudicated resolution was still more cautious than the final selected output: it preferred a partial publish and explicitly noted that `Patient 2` needed exclusion of intervening author and journal metadata.

My assessment: this is structurally the strongest result in the batch and the patient-level separation is almost certainly correct. The main flaw is that the published `Patient 2` text still contains author, affiliation, and journal boilerplate inside the unit body. That does not confuse patient identity, but it is not clean enough for a canonical downstream hand-off. The two shared-context blocks are low-risk, but they are also not very useful and could probably be dropped entirely. I would treat this as the best current candidate, but still subject to one final hygiene pass rather than as a fully finished output.

Verdict: best current auto-publish candidate; likely correct split, but still needs light cleaning before I would call it canonical.

## Useful but still partial

### `140` - Stiff-leg syndrome: a focal form of stiff-man syndrome.

Stage-06 prior: `count=2`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `partial_publish_with_unresolved_remainder`; `2` individual units; `8` shared-context blocks; unresolved remainder retained.

Extracted:
`Patient 1` (`p1:46-75`) is a strong single-patient block for a 63-year-old woman with right-leg rigidity, painful spasms, progressive gait instability, abnormal posturing, normal MRI/CSF/routine laboratories, and sustained improvement after IVIG.
`Patient 2` (`p1:76-100`) is a strong single-patient block for a 56-year-old woman with an 11-year progressive gait disorder, episodic right-leg stiffness and falls, prior anxiety misdiagnosis, epilepsy and diabetes history, abnormal posturing/rigidity, and normal MRI/CSF/routine laboratories.

Pipeline rationale: the deterministic splitter used the explicit `Patient 1` and `Patient 2` headings and matched the stage-06 count. GPT-5.4 agreed that the two patient units were attribution-safe and suggested carrying genuinely both-patient material as shared context rather than forcing it into one case.

My assessment: the two individual units are useful and I think they are materially correct. The problem is the shared context. All eight shared-context blocks are attached to both patients, and several are truncated line fragments rather than clean sentences, for example `muscles. Two patients had clinical or serological evi-` and `The serum and CSF of the 2 patients recognized a`. Some of these are likely valid both-patient statements, but they are not packaged cleanly enough for direct downstream use. The unresolved remainder also still contains clinically relevant and interpretive material. I agree with partial publication, but I would not let LangExtract consume these units yet without stricter shared-context trimming.

Verdict: the patient split itself looks right; the current shared-context packaging is too broad and too fragmentary for canonical use.

### `239` - Clinically disparate stiff-person syndrome with GAD65 autoantibody in a father and daughter.

Stage-06 prior: `count=2`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `partial_publish_with_unresolved_remainder`; `2` individual units; `3` shared-context blocks; unresolved remainder retained.

Extracted:
`Case 1` (multi-span across `p0:70-79`, `p0:82`, `p0:87`, and `p1:0-9`) captures the father with episodic right-leg stiffness while driving, transient involuntary leg extension, anxiety-provoked spasms, thyrogastric autoimmunity, brisk right patellar reflex and spasm, and normal MRI/CSF.
`Case 2` (`p1:27-76`) captures the daughter with episodic extension of head and neck, anxiety/startle-provoked opisthotonos, patellar-tendon-triggered episodes, prolonged abnormal motor unit activity, strong GAD65 antibody positivity, initial baclofen response, and long-term persistence of provoked episodes.

Pipeline rationale: heuristics found explicit `Case 1` and `Case 2` headings and matched the stage-06 count. GPT-5.4 did not get selected because its proposed `Case 1` failed validation: the validator judged it too methods-heavy rather than cleanly patient-specific. The final chosen output therefore fell back to the heuristic split.

My assessment: `Case 2` looks quite strong. `Case 1` is useful, but it clearly contains contamination from article-level material, including website and author lines inserted inside the unit text. The unresolved remainder is not trivial either: it still contains follow-up material for the father that probably belongs with `Case 1`, not in a generic remainder bucket. The shared-context blocks are again thin fragments rather than clean reusable context. So I do think the paper is split in roughly the right direction, but it is not stable enough yet for canonical publication.

Verdict: promising split, especially for `Case 2`, but still too contaminated and incomplete for clean downstream use.

### `748` - Apraxia in anti-glutamic acid decarboxylase-associated stiff person syndrome: link to corticobasal degeneration?

Stage-06 prior: `count=2`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `partial_publish_with_unresolved_remainder`; `2` individual units; `4` shared-context blocks; unresolved remainder retained.

Extracted:
`Patient 1` (multi-span across `p0:66-100` and `p1:0-48`) captures a 49-year-old woman with progressive back and neck stiffness, stimulus-sensitive spasms, apraxia testing abnormalities, right-greater-than-left upper-limb involvement, axial rigidity, abnormal gait, positive oligoclonal bands, and markedly elevated GAD antibodies.
`Patient 2` (multi-span across `p1:49-109` and `p2:0-11`) captures a 68-year-old woman with years of progressive gait difficulty, right-leg stiffness, alien-limb-like symptoms, right-hand apraxic dysfunction, lower-extremity rigidity, paraspinous hypertrophy, oligoclonal bands, elevated GAD antibodies, and one-year follow-up after IVIG.

Pipeline rationale: explicit `Patient 1` and `Patient 2` headings were detected, matching the stage-06 count. GPT-5.4 agreed that there were two attribution-safe patient units and proposed a bounded shared statement about both patients having GAD-positive SPS with corticobasal-syndrome-like signs.

My assessment: the two patient narratives are substantively valuable and I think the split is directionally correct. The same recurring problem appears again, though: the shared-context blocks are line fragments and not cleanly reusable, and the unresolved remainder is dominated by discussion/background text that has not been sharply separated from patient-specific material. There is also some residual page or publication interruption inside the patient units. This is a good partial result, but not a publishable one yet.

Verdict: useful patient-level recovery, but still not clean enough to be considered final.

## Correct manual-review holds

### `456` - PET evidence of central GABAergic changes in stiff-person syndrome.

Stage-06 prior: `count=2`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `manual_review_required`; `0` published units; unresolved remainder only.

What the text contains: the unresolved excerpt clearly includes an abstract stating that PET was performed in `two subjects with stiff person syndrome`, followed by explicit `Subject 1` and `Subject 2` method-level descriptions with age, clinical features, and laboratory data. This is not a paper with no split signal; it is a paper where the split signal is present but the extraction boundaries are unstable.

Pipeline rationale: heuristics did not find stable publishable units, and GPT-5.4 then failed validation because its proposed `subject_2` unit overlapped an existing unit span. The final output therefore withheld everything.

My assessment: I agree with the current hold, because overlapping subject spans are not attribution-safe. At the same time, this looks fixable rather than fundamentally ambiguous. The subject headings are explicit, and the main issue appears to be boundary handling around methods/results material rather than lack of extractable structure. I would put this near the top of the troubleshooting queue.

Verdict: correct hold today; likely recoverable with better subject-boundary logic.

### `668` - Progressive encephalomyelitis with rigidity and myoclonus: a syndrome with diverse clinical features and antibody responses.

Stage-06 prior: `count=3`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `manual_review_required`; `0` published units; unresolved remainder only.

What the text contains: the excerpt states that the authors `conducted an extensive screening of clinical features and antibody responses of 3 PERM patients` and the abstract briefly mentions `two patients with supratentorial involvement`, `one patient` with renal cell carcinoma, and `another patient` with LGI1 and GAD antibodies. However, these are abstract-level mentions rather than stable per-patient case narratives.

Pipeline rationale: GPT-5.4 tried to recover patient units, but the validator rejected the first proposed unit with `missing a stable patient anchor`. The final output correctly fell back to a full hold.

My assessment: this is exactly the kind of paper where GPT can look numerically plausible while still being attribution-unsafe. The current validator is doing the right job here. On the present evidence pack, I do not think there is enough anchored patient-level text to publish three clean units, even though the abstract makes the existence of three patients obvious.

Verdict: correct hold; good example of why strong deterministic validation is necessary.

### `679` - Successful treatment of stiff person syndrome with sequential use of tacrolimus.

Stage-06 prior: `count=2`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `manual_review_required`; `0` published units; unresolved remainder only.

What the text contains: the excerpt clearly confirms a two-patient SPS series and includes methods language assigning `two patients with SPS`, but the available lines are dominated by background, methods, and treatment protocol text. The GPT adjudication also noted that the excerpt only mentions `case 1` in a header-level way without supplying a full attribution-safe patient block.

Pipeline rationale: GPT-5.4 abstained rather than hallucinating units. It explicitly said that no non-overlapping individual case narratives could be recovered from the supplied lines alone.

My assessment: I agree with the hold. This feels less like a splitter logic failure and more like a text-windowing problem: the paper almost certainly contains patient narratives elsewhere, but the lines available to stage-07 are not enough for safe publication. I would not force a split from this excerpt.

Verdict: correct hold; likely blocked by incomplete or poorly chosen source lines rather than by the splitter itself.

### `766` - Presynaptic neuromuscular transmission defect in the stiff person syndrome.

Stage-06 prior: `count=2`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `manual_review_required`; `0` published units; unresolved remainder only.

What the text contains: the abstract says the paper describes one SPS patient with longstanding fatigue and presynaptic neuromuscular transmission defect, and contrasts that patient with `2 other SPS patients without fatigue symptoms`. The excerpt then contains a proper `Patient 1` section with substantial clinical detail for the fatigue case.

Pipeline rationale: GPT-5.4 abstained. Its rationale was that the text clearly supports one individual unit but does not safely expose the additional expected units. It also noted the tension between the abstract wording and the stage-06 final count.

My assessment: the hold is right. This is not safe to publish as a single extracted patient while the rest of the cohort remains unresolved. More importantly, this file exposes a contract problem that should be reviewed manually: the visible text sounds like three SPS patients in total, whereas the stage-06 prior is `2`. That may reflect a real stage-06 count issue, or it may mean the abstract is describing a differently scoped comparison than the final count registry captured. Either way, stage-07 is correct not to guess.

Verdict: correct hold; also worth escalating as a possible stage-06 versus source-text mismatch.

### `776` - Stiff person syndrome masquerading as multiple sclerosis.

Stage-06 prior: `count=5`, `count_confidence=high`, `count_verification_status=manual_review_override`.

Stage-07 output: `manual_review_required`; `0` published units; reason code `group_structure_unclear`.

What the text contains: the abstract-level results summarise a five-patient retrospective series and the excerpt then proceeds into individualised prose for `Patient 1`, `Patient 2`, `Patient 3`, and `Patient 4`. The visible excerpt therefore mixes paper-level group summary with partially exposed patient-level sections, and the fifth patient is not yet visible in the retained text.

Pipeline rationale: heuristics found patient headings, but the numbering was not sequential from the extracted material. GPT-5.4 then proposed an individual unit that failed validation because `patient_2` lacked a stable anchor.

My assessment: I agree with the hold. This does not look like a simple explicit-case splitter problem. It looks like a mixed-structure paper where stage-07 needs to decide whether to publish individual units, group-level context, or both, and the current excerpt is not complete enough to do that safely. Publishing from this state would be too brittle.

Verdict: correct hold; likely needs mixed individual-plus-group handling rather than a stronger version of the current individual splitter.

## Upstream input failure

### `715` - Progressive encephalomyelitis with rigidity and myoclonus: a new variant with DPPX antibodies.

Stage-06 prior: `count=3`, `count_confidence=high`, `count_verification_status=manual_review_override`. Source-route hints say both individual and group data may be present.

Stage-07 output: `manual_review_required`; `0` published units; unresolved remainder only.

What the text contains: only Neurology website boilerplate, update links, supplementary-material links, permissions text, and other wrapper content. There is no patient-level or subgroup-level clinical content in the supplied excerpt at all.

Pipeline rationale: GPT-5.4 correctly abstained and explicitly said that the lines contain only article metadata and boilerplate.

My assessment: this is not a meaningful stage-07 failure. The splitter never received usable case-series text, so there was nothing sensible for it to do. I would not spend time tuning case-boundary logic here until the upstream preferred-text or article-window selection is fixed.

Verdict: correct hold; upstream text-selection problem, not a splitter-quality problem.

## Cross-paper conclusions

- The strongest repeated issue is shared-context quality. Several papers attach truncated line fragments as `shared_context`, which is not a safe or useful hand-off format for later extraction.
- Explicit patient headings do help a great deal. Where the text contains clear `Patient 1`, `Patient 2`, or `Case 1`, `Case 2` narratives, stage-07 often recovers the right structure even if the packaging is still rough.
- GPT-5.4 is useful as an audit and recovery layer, but the validator is doing essential safety work. The blocked false-positive on `668` is a real win.
- Some failures are not really stage-07 logic failures. `679` and especially `715` look constrained by the source lines made available to the splitter.
- The best next improvements are still the same ones surfaced in the smoke notes: tighten shared-context selection, improve continuation capture, and separately investigate upstream text-windowing for wrapper-heavy papers.
