# 20260419T225240Z Stage-07 High-Risk Review Roll-up

- Run folder: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke`
- Selection JSON: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\selection.json`
- Combined QA CSV: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\20260419T225240Z_stage07_smoke_combined.csv`
- Inspection pack: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\20260419T225240Z_stage07_smoke_inspection.md`
- Scope: `10` stage-06-finalised papers reviewed after stage-07 GPT-5.4 adjudication
- Review workflow: read each paper summary first, then use the verbatim evidence section below when prose feedback needs to point to exact extracted text.

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

## Verbatim Evidence Appendix

- Companion to: `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\high_risk_review_rollup.md`
- Source of all text below: the per-paper stage-07 JSON outputs under `qa\validation\stage07_smoke\20260419T225240Z_stage07_smoke\text_case_series_units\`
- Purpose: show the exact unit text and key unresolved excerpts so a human reviewer can see precisely what stage `07` extracted
- Note: OCR and source-text corruption are preserved exactly as they appear in the stage-07 JSONs

## Published or partially published units

### `140`

Status: `partial_publish_with_unresolved_remainder`

`Patient 1` (`p1:46-75`)

```text
Patient 1
A 63-year-old woman noticed rigidity of the right leg with
progressive gait instability in October 1991. Two months
later, she developed episodes of sudden, painful spasms in-
volving dorsiflexion and inversion of her right foot with ex-
tension of the leg. Her symptoms progressed, leading to a
persistent abnormal posture of the leg with considerable dif-
ficulty in walking. Treatment with diazepam provided relief
of the spasms, but the gait disturbance persisted. Past med-
ical history was significant for hyperthyroidism at 50 years of
age that reverted to normal with treatment in 1 year. On
neurological examination, there was abnormal posturing,
with persistent extension and abduction, of the right leg and
medial inversion of the foot and hyperextension of the toes.
The leg was rigid, more so distally, and movements were
severely limited, with no palpable muscle tenderness. Volun-
tary movements of the leg and tactile stimuli often precipi-
tated a spasm. She could only walk with assistance. Her gait
was characterized by shuffling, mild widened base, and short-
ened stride. She admitted a fear of failing and refused to
walk without the help of another person. The rest of the
neurological and general examination was normal. Results of
magnetic resonance imaging of the brain and spinal cord,
CSF examination, and routine laboratory analysis, including
thyroid hormones, were normal. The patient was treated
with intravenous immune globulin (IVIG) (400 mg/kg/day
for 5 days). The rigidity improved with almost normalization
in her abnormal posture within a few days. Improvement has
been maintained for 2 years with bimonthly 1-day courses of
IVIG, but she still needs a cane to walk in the street.
```

`Patient 2` (`p1:76-100`)

```text
Patient 2
A 56-year-old woman was referred for evaluation of a pro-
gressive gait disorder that started 11 years ago when she no-
ticed occasional episodes in which the right leg suddenly be-
came stiff, usually when the patient attempted to cross the
street or was forced to walk in a hurry. The episodes became
more frequent and provoked unexpected falls. She was diag-
nosed as having agoraphobic anxiety neurosis and treated
with benzodiazepines with partial relief of her spasms. Over
the ensuing 6 years, her symptoms progressed slowly, leading
to permanent stiffness of the right leg, with abnormal pos-
ture and increased gait disturbance. Past medical history was
significant for epilepsy diagnosed in childhood and IDDM
discovered at 52 years of age. General examination was nor-
mal. On neurological examination there was abnormal pos-
turing of the right leg, with knee extension, ankle plantar-
flexion, and inversion of the foot. The leg was rigid, with
limitation of the movements of the foot. Voluntary move-
ment of the leg and tactile stimuli occasionally precipitated a
spasm. The gait was slow and very cautious, searching for
points of support. She walked only with assistance on short
steps, with a mildly widened base and stiffness of the right
leg. Results of magnetic resonance imaging of the brain and
spinal cord, CSF analysis, and routine laboratory analysis, in-
cluding thyroid hormones, were normal.
```

Shared-context blocks linked to both units:

```text
[140__shared__001] muscles. Two patients had clinical or serological evi-
[140__shared__002] We report on 2 patients with stiffness and spasms
[140__shared__003] The results were essentially identical in both patients.
[140__shared__004] median nerves in both patients.
[140__shared__005] The serum and CSF of the 2 patients recognized a
[140__shared__006] 2 patients immunoreacted with GABA-ergic nerve ter-
[140__shared__007] We describe 2 patients with a similar clinical picture,
[140__shared__008] bition of the spinal motoneurons. Both patients had
```

Representative unresolved remainder excerpt:

```text
disclosed continuous motor unit activity and abnor-
mally enhanced exteroceptive reflexes suggesting dishi-
high-titer GAD-Ab, a useful marker of SMS in the
setting of appropriate clinical and electrophysiological
features.
GAD-Ab are also reported in a few patients with
other neurological disorders, particularly cerebellar
ata~ia.~.â€™-â€™~ The refore, the finding of GAD-Ab by it-
self does not absolutely mean our patientsâ€™ syndrome
represents a particular clinical expression of SMS.
However, we favor the possibility of a focal form of
SMS based on the following reasons:
```

### `239`

Status: `partial_publish_with_unresolved_remainder`

`Case 1` (`p0:70-79`, `p0:82`, `p0:87`, `p1:0-9`)

```text
Subjects, methods, and results. Case 1. At age 53, the fa-
ther experienced episodic stiffness and discomfort in the right leg.
On two occasions, while driving, he had transient, involuntary
extension of his right leg. This necessitated removing his foot from
the automobile accelerator with his hand. One of these episodes
contributed to a minor motor vehicle accident. At neurologic eval-
uation 15 months after symptom onset, he had episodic right leg
Additional material related to this article can be found on the Neurology
Web site. Go to www.neurology.org and scroll down the Table of Con-
tents for the November 11 issue to find the title link for this article.
Immunology, Neurology, and Laboratory Medicine and Pathology (Dr. Lennon), Mayo Clinic, Mayo Graduate and Medical Schools, Rochester, MN.
22908; e-mail: tmb8r@virginia.edu
stiffness and spasm especially provoked by anxiety. He had a
history of pernicious anemia and thyroiditis. His family history
included type 1 diabetes, thyroiditis, and pernicious anemia (fig-
ure 1). Neurologic examination demonstrated episodic stiffening of
the right leg with knee extension and ankle dorsiflexion. The right
patellar muscle stretch reflex was disproportionately brisk and its
elicitation was followed immediately by prolonged spasm of the
quadriceps femoris. Plantar responses were flexor. There was no
lumbar hyperlordosis.
Head and cervicothoracic spine MRI and CSF studies had normal
```

`Case 2` (`p1:27-76`)

```text
Case 2. His daughterâ€™s initial symptom of SPS began at age
31 years. She experienced recurrent, episodic extension of her
head and neck. These episodes were initially brief, lasting only 2
to 3 seconds, and were provoked by anxiety and startle, but pro-
gressed over 6 years to last as long as 8 seconds. More severe
episodes were uncomfortable and associated with a transient
â€œtightnessâ€ in her throat that interfered with swallowing and
speaking. On examination, tapping of left or right patellar tendon
provoked opisthotonos lasting 4 to 6 seconds (see video E-1 at
www.neurology.org). This was more pronounced when the left pa-
tellar tendon was tapped while the patient was engaged in casual
conversation. The opisthotonic response abated when the patient
simultaneously performed mental arithmetic. Muscle stretch re-
flex testing elsewhere in the body did not elicit an abnormal re-
sponse. There was no lumbar hyperlordosis.
Surface electrodes recorded abnormally protracted motor unit
activity lasting up to 8 seconds following patellar tendon tapping
(figure 2). GAD65Ab values were 88.7 nmol/L and 95.6 nmol/L,
and thyroperoxidase antibody value was 100 IU/mL (normal /H1102120
IU/mL). She did not have clinical evidence of thyroiditis. Baclofen
relieved symptoms initially; it was gradually tapered and discon-
tinued as spontaneous opisthotonos became infrequent. However,
provocative maneuvers and anxiety continue to cause opisthoto-
nos, 48 months after initial presentation.
During this period, the daughter gave birth to a healthy infant
girl. Despite acquiring maternal GAD65 antibodies transplacen-
tally, the infant (now 3 years old) has not exhibited clinical symp-
toms or signs of SPS. Serial serum evaluations revealed GAD65Ab
values of 72.7 nmol/L at birth, 6.65 nmol/L at 3 months, and 0.65
nmol/L at 7 months.
Familial genetic and autoantibody investigation. With pro-
tocol approval by the Lahey Clinic Investigational Review Board
(LCID 2001â€“041), and the patientâ€™s informed consent, we obtained
blood samples from the father, daughter, and nine other family
members (see figure 1). Serologic tests were performed for the
following autoantibodies: GAD65, thyrogastric, thyroid microso-
mal (peroxidase), gastric parietal cell, voltage-gated calcium chan-
nel N-type and P/Q-type, muscle acetylcholine receptor binding,
striated muscle, antinuclear (ANA), smooth muscle, mitochon-
drial, IA-2 islet cell, and neuronal cytoplasmic and nuclear anti-
bodies. Consistent with a hereditary predisposition to thyrogastric
Figure 1. Pedigree of family with stiff-person syndrome,
GAD65 antibodies, and multiple thyrogastric autoimmune
disorders. Circles represent female subjects; squares repre-
sent male subjects. Diagonal slash symbols represent de-
ceased individuals. Black arrow indicates father. Asterisks
indicate individuals who were assessed clinically and had
serologic testing and MHC II haplotyping. The exception is
III-13, who was not haplotyped. Detected autoantibodies
are indicated near each subject. Negative autoantibody
```

Shared-context blocks linked to both units:

```text
[239__shared__001] bers (in low titer except in our two patients) and one or more
[239__shared__002] Discussion. We consider these two patients to rep-
[239__shared__003] sider that the presence of GAD65Ab in both patients
```

Representative unresolved remainder excerpt:

```text
prednisone plus diazepam. Follow-up GAD65Ab were 12.9 nmol/L
and 15.9 nmol/L. Subsequently he developed similar but milder prob-
lems with his other leg, requiring an increase in medications. Low-
dose prednisone was discontinued 5.5 years after initial presentation
and 6 months after initiating azathioprine. Now, 8 years after pre-
sentation, he is maintained on azathioprine 150 mg daily with diaz-
epam, and has mild residual symptoms of SPS.
```

### `559`

Status: `publish_all_units`

`Patient 1` (`p0:81-107`)

```text
Patient 1
A 33-year-old woman, with autoimmune thyroid-
itis, presented in September 1999 with subacute
onset of brainstem symptoms, diplopia, dysphagia
and gait ataxia that improved spontaneously in
5 weeks. In January 2000, she progressively devel-
oped rigidity of lower limbs with painful spasms,
involuntary jerks and contracture of both ankles
and urinary retention. Brain and spinal MRI and
cerebrospinal ï¬‚uid (CSF) examination was normal
with negative oligoclonal bands. EMG demon-
strated involuntary continuous motor unit activity
and abnormal exteroceptive reï¬‚ exes. Onconeural
antibodies (Hu, Y o, Ri, T r, CV2, Ma2, amphiphysin)
and GAD-ab were negative. A progressive complete
recovery was obtained with corticosteroids, diaz-
epam and baclofen. She relapsed with stiffness and
painful spasms predominantly of the right leg in
November 2001. She was treated with a course of
intravenous immunoglobulin (IVIG) (0.4 g/kg/
day35 days) and restarted with symptomatic
therapy. By May 2002, she returned to work, and
she has been asymptomatic for 8 years. GlyR-ab
were found positive, with a score of 3.5 in serum
stored from 2001 (CSF was not available for anal-
ysis). A follow-up serum sample obtained in 2009
was low positive with a score of 1.
```

`Patient 2` (multi-span across `p0:108-141`, `p1:0-21`)

```text
Patient 2
A 60-year-old man complained of progressive
dysphagia. Five days later, he began to experience
brief attacks of rigidity of his legs with painful
spasms and back pain. T wo days later, the spasms
became more frequent; he noticed diplopia and right
facial numbness that prompted his admission. The
ClÄ±Â´nic and Institut dâ€™ InvestigacioÂ´
Biome`dica August Pi i Sunyer
(IDIBAPS), Barcelona, Spain
Neurosciences, Weatheral
Institut of Molecular Medicine,
UK
Universitario FundacioÂ´n
AlcorcoÂ´n, Madrid, Spain
Sant Joan Dâ€™Alacant, Alicante,
Spain
Correspondence to
Dr Francesc Graus, Servei de
Villarroel 170, Barcelona 08036,
Spain; fgraus@clinic.ub.es
Revised 18 October 2010
Accepted 20 October 2010
Published Online First
10 December 2010
J Neurol Neurosurg Psychiatry 2011;82:1399e1401. doi:10.1136/jnnp.2010.229104 1399
Short report
family had also noted emotional irritability, anxiety and behav-
ioural changes in the last month. On examination, he was anxious
with no evidence of cognitive deterioration. There was a mild
paresis of the VI and VII left cranial nerves, right trigeminal
hypoaesthesia and dysarthria. He had dif ï¬culties in swallowing,
and the tongue was weak. The rigidity and spasms of the legs were
spontaneous and easily elicited by sensory stimuli accompanied
by diaphoresis and tachycardia. Routine haematological,
biochemical and CSF analysis, CSF oligoclonal bands, whole body
CT and brain MRI were normal or negative. EMG demonstrated
involuntary continuous motor unit activity. Onconeural anti-
bodies and GAD-ab were negative, but GlyR-ab were present in
serum and CSF (both at score 3.5). In the ensuing days, the
brainstem symptoms worsened, and he developed spastic para-
paresis with bilateral Babinski signs and ankle clonus. There was
also severe stimuli-sensitive multifocal myoclonus. Seven days
after admission, he developed repetitive right and left motor
seizures, with severe autonomic instability (profuse sweating,
mydriasis, tachycardia, high blood pressure and hyperthermia)
followed by a cardiac arrest. He was intubated and ventilated but
did not recover, and he has remained in a persistent vegetative
state and ventilator-dependent.
```

`Patient 3` (`p1:22-51`)

```text
Patient 3
A 48-year-old man presented in September 2009 with 2 months
of pruritus that involved the left scapula, right arm and right
T11eT12 dermatome. At the same time, he became progres-
sively more aggressive and developed emotional irritability,
dysgeusia (metallic taste) and severe diurnal hypersommia. Over
the ensuing weeks, he presented progressive rigidity in the right
leg, severe trismus elicited by yawning or deglutition that
prevent him to drink or eat, and frequent spells of trismus, axial
rigidity with leg spasms that were followed by an opisthotonic
posture and accompanied by facial ï¬‚ushing and diaphoresis of
brief duration. These spells were easily elicited by sensory
stimuli. Neurological examination revealed an alert patient with
normal cognitive status. There was diffuse rigidity of the right
leg with hyper-re ï¬‚exia and Babinski response. A light touch
caused dysesthesia in the areas with pruritus. Sensory, but not
auditory, stimuli (tactile cutaneous and pharyngeal) elicited the
spells described above.
Routine haematological, biochemical and CSF analysis, CSF
oligoclonal bands, whole-body CT , brain and spinal MRI scans
were normal or negative. An EMG performed while he was on
treatment did not show continuous motor unit activity. Onco-
neural antibodies and GAD-ab were negative. GlyR-ab were
present in the serum and CSF (score 3). T reatment with diaz-
epam and gabapentin provided an immediate complete relief of
the spasms. The patient received 10 monthly courses of IVIG
and oral corticosteroids. He showed a partial improvement with
resolution of his leg rigidity but persistence of the pruritus,
dysgeusia, hypersomnia, masseter spasms with yawn, and
behavioural changes.
```

Shared-context blocks linked to all three units:

```text
[559__shared__001] We have reported on three patients with GlyR-ab who exhibited
[559__shared__002] uniform. The three patients had normal brain and spinal cord
```

### `748`

Status: `partial_publish_with_unresolved_remainder`

`Patient 1` (multi-span across `p0:66-100`, `p1:0-48`)

```text
Patient 1
In October 2013, a 49-year-old African American
woman was admitted to the inpatient Neurology Service
sive stiffness and muscle spasms of her back and neck.
T wo years prior to admission, she developed lower back
pain and underwent L5 discectomy with fixation for pre-
sumed disk disease. In July of 2013, she had worsening
of her lower back pain and spasms, with impairment of
her ability to walk as well as falls. If touched unexpect-
edly, her spasms increased. While in clinic, her Mini-
Mental Status Examination was normal (29 of 30), but
on Montreal Cognitive Assessment she had a score of 24
of 30, with errors in visuospatial and executive domains,
letter fluency tasks, and delayed recall.
T o test for the presence of IMA, she was verbally
asked to perform, with each upper limb, several transitive
pantomimes to verbal command, which is the most sensi-
tive test for IMA.
7 The errors associated with IMA are
often postural, such as using a body part as the tool or
holding the hand and arm in the incorrect position, as
well as movement errors, with incorrect joint move-
ments.
7 On this praxis testing, she frequently made
Medicine, Gainesville, FL.
of Neurology, MBI 1149 Newell Drive, Room L3-100, Gainesville, FL
32611. E-mail: lauren.bowen@neurology.ufl.edu
publication Aug 2, 2014.
View this article online at wileyonlinelibrary.com. DOI: 10.1002/ana.
24245
VC 2014 American Neurological Association 173
postural and movement errors, revealing that she had an
IMA that was more severe in her right than left upper
limb. For example, she was asked to make believe she was
holding a pair of scissors in her hand and to show how
she would cut a piece of paper in half. She was also told
to not use her fingers as blades. When she attempted to
perform this pantomime she made a postural error, keep-
ing her index finger fully extended. She also made a
movement error. When pantomiming the use of scissors,
rather than moving her thumb toward and away from her
index finger, she moved it sideways, so that the thumbâ€™s
movement was parallel to her index finger.
Patients who have limb-kinetic apraxia have a loss of
fingerâ€“hand deftness, with a loss of the ability to perform
precise, independent but coordinated finger movements.
7
T o test for limb-kinetic apraxia, she was assessed with the
coin rotation test, where patients attempt to rotate a nickel
as rapidly as possible between their thumb, index, and mid-
dle finger for 20 rotations.
8 Rotating a coin requires pre-
cise, independent but coordinated finger movements. She
was unable to make any successful rotations with her right
hand. She was able to perform a few rotations with her left
hand, but had so much difficulty we terminated this test.
When asked to write with her right hand she demonstrated
an impaired ability to move the pen in the spatial direc-
tions needed to correctly form the letters of the words she
wanted to write, a sign of apraxic agraphia.
Cranial nerve examination was normal. On motor
examination her strength was normal, but she had prom-
inent axial rigidity and increased rigidity when startled.
She also had moderate plastic rigidity of her upper limbs,
the right being more rigid than the left. Although no
dystonia, myoclonus, or alien hand was observed, when
asked about these symptoms she stated that her right
arm would occasionally appear to spontaneously elevate.
Her sensory and her cerebellar examinations were nor-
mal, but her gait was abnormal, with a wide base, stiff
legs, and small steps (marche /C18a petits pas).
Magnetic resonance imaging (MRI) of her head
revealed no significant abnormalities. MRI of her cervical,
thoracic, and lumbosacral spine without contrast showed
edema of the paraspinous muscles, most prominently in
the right lumbar spine, but there was no abnormality of
the spinal cord. An analysis of her cerebrospinal fluid
(CSF) was positive for oligoclonal bands. Her CSF GAD-
ab count was 210nmol/l (normal < 0.02 nmol/L), and
serum GAD-ab count was 2449.1U/ml (normal < 1U/ml).
```

`Patient 2` (multi-span across `p1:49-109`, `p2:0-11`)

```text
Patient 2
In January 2013, a 68-year-old Caucasian woman with a
past medical history of type II diabetes was admitted to
Seven years prior to admission, she developed gradual
difficulty walking. She started to use a cane 5
1=2 years
prior to presentation and a walker 2 years prior to admis-
sion when her right leg became stiff. Occasionally, she
felt a sense of her lower extremities being alien limbs,
with an inability to control their movements. During the
same time, she noticed increasing difficulty writing and
using utensils with her right hand. T wo years prior to
presentation she underwent cervical laminectomy for
stiffness in her neck and pain radiating down her right
arm.
Her neurological examination on admission
revealed several abnormalities. Except for defective
crossed response inhibition, her mental status and cranial
nerve examinations were normal. There was no ataxia or
adiadochokinesia. Muscle tone was normal in both upper
extremities, but increased in her lower extremities, the
right lower being more rigid than the left. Her back
muscles showed paraspinous muscle hypertrophy in the
lumbar spine. She was not able to stand without assis-
tance and used a rolling walker to ambulate. Her gait
appeared rigid.
She had limb-kinetic apraxia with her right hand
during the coin rotation test,
8 as well as bilateral IMA
with mild bilateral agraphesthesia and constructional
apraxia as tested by having her attempt to copy a draw-
ing of intersecting pentagons. The patientâ€™s handwriting
was small, with some evidence of apraxic agraphia with
the right hand. Although handwriting with the left hand
was unsteady, it was not clearly agraphic.
Imaging studies revealed no spinal cord abnormal-
ities, and she had mild cerebellar atrophy on brain MRI.
An analysis of her CSF was positive for oligoclonal
bands. Her GAD-ab were elevated (2,560U/ml).
In February 2014, she was seen for a 1-year follow-
up after intravenous immunoglobulin treatment. She had
bilateral lower extremity rigidity, greatest in the right leg.
In addition, she now demonstrated rigidity of her upper
extremities, with more rigidity on the right than the left.
She also had axial rigidity. She had positive Myerson
sign, but no other cranial nerve abnormalities including
vertical eye movements.
She was tested for IMA by being asked to panto-
mime, with each upper limb, several transitive actions to
verbal command.
7 On this testing, she revealed spatial
postural and movement errors that were worse when
using her right than left upper extremity. For example,
when asked to pantomime using a pair of scissors with
her right hand, but not to use her fingers as the blades,
she held her forefinger in a fully extended position and
moved her hand at her wrist making ulnar and radial
174 V olume 77, No. 1
deviations. This was also seen in the left hand, but was
less pronounced. When asked to scramble eggs in a
bowel on her lap with a fork held in her right hand, she
demonstrated some flexionâ€“extension motions at her
wrist, but no rotation of her wrist so that her imaginary
fork would rotate. She performed this pantomime nor-
mally with her left hand. She was also tested with the
coin rotation task for limb-kinetic apraxia, and she
revealed bilateral limb-kinetic apraxia that was more
severe in her right than left hand, but when compared to
her prior testing this appeared as less severe.
8
```

Shared-context blocks linked to both units:

```text
[748__shared__001] have not been reported to coexist. We report 2 patients
[748__shared__002] we evaluated 2 patients with SPS who revealed asymmet-
[748__shared__003] tion, both patients also had an asymmetrical ideomotor
[748__shared__004] ical atrophy with SPS. The 2 patients being reported, like
```

Representative unresolved remainder excerpt:

```text
SPS, originally described by Moersch and Woltman, is
characterized by progressive axial and limbic rigidity lack-
ing extrapyramidal features, with associated triggered
muscle spasms. 9 Subsequent work divided SPS into sev-
eral subtypes, including stiff limb and progressive
encephalomyelitis with rigidity.
10 Diagnosis originally
was made by clinical presentation and electromyography
demonstrating involuntary firing of motor units with
absent reciprocal firing.
11 The association between GAD-
ab and SPS was first described in 1990, with 60% of
SPS patients testing positive for GAD-ab.
```

## Manual-review holds: key unresolved source excerpts

### `456`

Status: `manual_review_required`

Key unresolved excerpt showing explicit subject-level structure:

```text
Subject 1 is a 45-year-old man affected by type 1
diabetes mellitus, complaining of leg proximal rigidity
and falls; symptoms ameliorated by using diazepam. On
the basis of clinical history and laboratory data (Table 1),
a diagnosis of SPS and epilepsy was done.
Subject 2 is a 53-year-old woman; her medical history
was notable for onset of vitiligo at age 33, Gravesâ€™
disease at age 38, and type 1 diabetes mellitus at age 51.
At age 52 she began complaining of muscle rigidity,
cramps, and painful spasms. These symptoms involved
mainly the axial musculature, but also the proximal por-
tion of lower and upper limbs, and were partially ame-
liorated by low doses of diazepam. On the basis of
clinical and laboratory examinations (Table 1), a diag-
nosis of probable SPS was made.
```

GPT rejection captured in the JSON:

```text
Adjudicated unit subject_2 overlaps existing unit spans at indices [167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179].
```

### `668`

Status: `manual_review_required`

Key unresolved excerpt showing why GPT could be tempted to over-split:

```text
Results: Two patients with supra-
tentorial involvement showed abnormal PET or EEG find-
ings. One patient was discovered to have renal cell carcino-
ma, and protein macroarray revealed Ma3-antibodies.
Another patient with leucine-rich, glioma-inactivated 1
(LGI1) and glutamic acid decarboxylase (GAD) antibodies
showed a good response to immunotherapy.
```

GPT rejection captured in the JSON:

```text
Adjudicated individual unit patient_1 is not attribution-safe: missing a stable patient anchor.
```

### `679`

Status: `manual_review_required`

Representative unresolved excerpt showing that the current source window is mostly background and methods:

```text
Stiff person syndrome (SPS) is a rare neuro-
logical disease with features of an auto-
immune disease. SPS is characterised by
severe progressive muscle stiffness of the
spine and lower extremities with superim-
posed muscle spasms triggered by external
stimuli such as noise, touch and emotional
distress.
...
We n o w
report the successful treatment of patients
with SPS using tacrolimus as the immuno-
suppressive agent.
METHODS
Patients
W e assigned two patients with SPS who
had incomplete responses to conventional
therapies and ful ﬁlled the de ﬁned clinical
criteria (online supplementary table 1).
```

GPT abstention summary captured in the JSON:

```text
The excerpt confirms a 2-patient SPS case series and mentions 'case 1' in a subsection header, but the provided lines do not contain attribution-safe patient-specific findings for either patient.
```

### `715`

Status: `manual_review_required`

Representative unresolved excerpt showing the upstream wrapper problem:

```text
Progressive encephalomyelitis with rigidity and myoclonus: A new variant with DPPX
This information is current as of April 2, 2014
Services
Updated Information &
http://n.neurology.org/content/82/17/1521.full
including high resolution figures, can be found at:
Supplementary Material
372.DC2
http://n.neurology.org/content/suppl/2015/04/01/WNL.0000000000000
372.DC1
http://n.neurology.org/content/suppl/2014/04/02/WNL.0000000000000
```

GPT abstention summary captured in the JSON:

```text
The provided lines contain only article metadata, links, and publication boilerplate, with no patient- or subgroup-attributable clinical content.
```

### `766`

Status: `manual_review_required`

Key unresolved excerpt showing the one clear case plus the extra cohort hint:

```text
Case presentations: We describe an SPS patient presenting with longstanding fatigue and electrophysiological
evidence of presynaptic neuromuscular transmission defect, who responded to administration of pyridostigmine.
In contrast, no electrophysiolgical evidence of neuromuscular transmission defect was demonstrated in 2 other
SPS patients without fatigue symptoms.
```

Exact visible `Patient 1` block in the unresolved remainder:

```text
Patient 1
A 62-year old previously healthy Caucasian female expe-
rienced a 20 year history of pain in the neck, truncal and
limb muscles. The symptoms were exacerbated by exer-
cise and had a fluctuating course. In addition, she has
muscle cramps, stiffness and spasms which she needed
periods of rest to allow symptoms to alleviate.
Notably, she reported severe fatigue symptoms for the
same period of time, made worse with physical exertion
and mental stress. She had consulted multiple doctors
and given diagnoses, including chronic fatigue syndrome
(CFS) or myalic encephalomyelitis, and fibromyalgia.
```

GPT abstention summary captured in the JSON:

```text
The provided lines clearly identify Patient 1 and contain individual-level data for that patient, but stage06 indicates a final count of 2 cases and the abstract references 2 other SPS patients. The supplied excerpt does not include explicit case-level sections or attribution-safe spans for those additional patients.
```

### `776`

Status: `manual_review_required`

Key unresolved excerpt showing the paper-level group summary:

```text
Methods: We performed a retrospective chart review of over 100 patients with SPS who were treated at Johns
Hopkins Hospital and identiﬁed ﬁve patients previously diagnosed with MS.
Results: Patients were female with a mean age of 53 years old (range 43 – 64). Mean time to SPS diagnosis was
5.5 years. They presented with typical SPS features (axial/leg spasms, torso rigidity, hyperlordosis, and gait insta-
bility) as well as atypical features (hemiparesis, hemisensory dysfunction,ﬁne motor impairment) and were all
initially given a diagnosis of MS.
```

Exact unresolved excerpt showing the start of the patient-level sections:

```text
Patient 1 presented with progressive gait instability and axial and leg
muscle spasms and rigidity. Exam was additionally notable for
hypomimia, dysarthria, mild proximal left-sided weakness and
dysmetria with a slow unsteady gait.
...
Patient
2 had a history of anxiety, poor memory recall, generalized fatigue, sub-
jective mild hemiparesis/hemisensory dysfunction, gait imbalance, axial
rigidity and spasms.
...
Patient 3 presented with
gait and balance instability and leg stiffness.
...
Patient 4 had a history of
leg spasms and weakness, ﬁne motor impairment, atypical sensory
symptoms in the thighs, and urinary urgency.
```

GPT rejection captured in the JSON:

```text
Adjudicated individual unit patient_2 is not attribution-safe: missing a stable patient anchor.
```
