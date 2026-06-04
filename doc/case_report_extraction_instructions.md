# Case report extraction instructions

Generated reference for the Qwen/Ollama single-case extraction pilot.

## Source

- Workbook: `C:\NOS\Stiff Person Review\data extraction forms\Stiff Person risk of Bias and Data Extraction Forms_shermyn_2024_09_18.xlsx`
- Sheet: `Case Reports`
- Source rows: row 1 section labels, row 2 human instructions, row 3 machine names

## Corrections

- Replace both legacy `FU_duration` columns with `Followup_Duration_Months`.
- Correct `first_manifestation_mother` to `first_manifestation_other`.
- Correct `immuntherapy_detail` to `immunotherapy_detail`.
- Do not include CSV-only fields `included_diagnosis` or `included_diagnosis_specify`.

## General rules

- Extract only what the source text states.
- Use `NA` when a value is not reported; do not use `N/A`.
- Preserve ratios, titres, doses, units, and reported measurements verbatim.
- Every non-missing value must carry a short verbatim source quote or per-value evidence quote.
- If a quote uses ellipsis, post-processing searches the source for its fragments and saves the full recovered source span when available.
- Prefer source-order quotes for human review. Out-of-order fragments are a warning if every fragment is found in the source, not a hard failure.
- Use worksheet value formats: numeric age/duration/mRS fields are numbers only; binary fields are `0`, `1`, or `NA`.
- Allowed-value strings are machine tokens; preserve underscores exactly, such as `back_pain`.
- `age_description` requires an exact numeric age; approximate descriptions such as `in her 20s` use `NA`.
- Deterministic arithmetic derivations are allowed only for: Followup_Duration_Months, age_onset, onset_to_established, time_to_diagnosis.
- `Followup_Duration_Months` should be normalised to months when a duration is reported in years.
- `CSF_antibody` records antibody names found in CSF; use `none` when CSF antibody testing found none, and `NA` when CSF antibody testing is not reported.
- `case_ID` should use the exact identifier the article gives, whether that is `Case 1`, `Patient 2`, patient initials, etc.
- Separate multiple values inside one cell with semicolons when the field instruction asks for it.

## Fields

### 1. `extractor`

- Section: 1.section: Identifier and case vignette
- Source column(s): A
- Source label(s):
  - Initials of extractor

Initials of extractor

### 2. `Reference`

- Section: 1.section: Identifier and case vignette
- Source column(s): B
- Source label(s):
  - ID

ID

### 3. `case_ID`

- Section: 1.section: Identifier and case vignette
- Source column(s): C
- Source label(s):
  - Case reference within the article (case#)

Case reference within the article (case#)

### 4. `age_description`

- Section: 1.section: Identifier and case vignette
- Source column(s): D
- Source label(s):
  - Age at description

Age at description. Use a numeric value only when an exact age is stated. Approximate descriptions such as 'in her 20s' are too imprecise; use NA.

### 5. `sex`

- Section: 1.section: Identifier and case vignette
- Source column(s): E
- Source label(s):
  - Sex: M or F

Sex: M or F

### 6. `ethnicity`

- Section: section: basic demographic data
- Source column(s): F
- Source label(s):
  - Ethnicity (select one) / - white = White/Caucasian / - africa = African/ Afro-Caribbean / - E_asia = East Asia (Japan, Korea, China) / - S_asia = South Asia (India, Pakistan, Bangladesh, Sri Lanka) / - SE_asia = South East Asian (everything East of India and South of China which will cover Thailand, Malaysia, Singapore) / - latin = Latin American (non-African origin; central and S America, without Caribbean) / - other = other (specify in next column)
- Allowed values parsed from instruction: white, africa, E_asia, S_asia, SE_asia, latin, other, turkish, african

Ethnicity (select one)
- white = White/Caucasian
- africa = African/ Afro-Caribbean
- E_asia = East Asia (Japan, Korea, China)
- S_asia = South Asia (India, Pakistan, Bangladesh, Sri Lanka)
- SE_asia = South East Asian (everything East of India and South of China which will cover Thailand, Malaysia, Singapore)
- latin = Latin American (non-African origin; central and S America, without Caribbean)
- other = other (specify in next column)

### 7. `age_onset`

- Section: section: basic demographic data
- Source column(s): G
- Source label(s):
  - Age at onset

Age at onset

### 8. `Followup_Duration_Months`

- Section: section: basic demographic data
- Source column(s): H, AJ
- Source label(s):
  - Follow Up (years)
  - Duration of follow up (months)

Total reported follow-up duration in months. If the paper reports follow-up in years, convert to months. If no follow-up duration is reported, use NA. This is the only permitted numeric conversion; ratios, titres, doses, units, and all other reported measurements stay verbatim.

### 9. `time_to_diagnosis`

- Section: section: basic demographic data
- Source column(s): I
- Source label(s):
  - Time to diagnosis (years)

Time to diagnosis (years)

### 10. `first_manifestation`

- Section: section: basic demographic data
- Source column(s): J
- Source label(s):
  - First manifestation (select) / - stiffness / - spasms / - startle = excessive startle / - multiple = multiple, specify in next cols / - other = other, specify in next cols
- Allowed values parsed from instruction: stiffness, spasms, startle, multiple, other, pain, focal_seizures, seizures, shaking

First manifestation (select)
- stiffness
- spasms
- startle = excessive startle
- multiple = multiple, specify in next cols
- other = other, specify in next cols

### 11. `first_manifestation_multiple`

- Section: section: basic demographic data
- Source column(s): K
- Source label(s):
  - First manifestation (multiple)
- Allowed values parsed from instruction: fatigue, tingling, falls, back_pain, nystagmus, nausea, stiffness, spasms, pain, startle, agoraphobia, weakness, X, dysphagia, myokymia, cramps, itching, foot_oedema, gait_disorder, vertigo, imbalance, ataxia, other, lordosis, thyroiditis, diabetes_mellitus, paraesthesia, numbness, dysarthria, unresponsiveness, oculomotor, decreased_sleep_requirement, disorganised_behaviour, myoclonus, weight_loss, mood_disorder, diarrhoea, headache, anxiety, memory_disorder, confusion, insomnia, depression, OCD, apathy, impaired_consciousness, urinary_incontinence, fever, tachycardia, hypotension, rhabdomyolysis, renal_injury, myocloni, cramp, paraethesia, contractures, swollen_tongue, dizziness, fasciculation, atrophy, ptosis, diplopia, facial_weakness, sensory, tremor, vomiting, dyspnoea, psychiatric, trismus, dystonia-like, autonomic, brainstem, brainstem_dysfunction, cognitive_deficit, tongue_paraesthesia, burning, seizure, behavioural, memory_loss

First manifestation (multiple)

### 12. `first_manifestation_other`

- Section: section: basic demographic data
- Source column(s): L
- Source label(s):
  - First manifestation (other)
- Allowed values parsed from instruction: sensory, pain, fatigue, fasciculations, clonus, numbness, spasticity, startle, agoraphobia, ataxia, nystagmus, dysarthria, dysphagia, vertigo

First manifestation (other)

### 13. `diagnostic_criteria`

- Section: section: basic demographic data
- Source column(s): M
- Source label(s):
  - Diagnostic Criteria Used : Provide below the details of the criteria used to make the diagnosis - copy and paste from text if needed

Diagnostic Criteria Used : Provide below the details of the criteria used to make the diagnosis - copy and paste from text if needed

### 14. `early_symptoms`

- Section: section: basic demographic data
- Source column(s): N
- Source label(s):
  - Overview_SPSD symptoms / early disease (select) / - stiffness / - spasms / - startle = excessive startle
- Allowed values parsed from instruction: stiffness, spasms, startle, fatigue, tingling, falls, back_pain, nystagmus, nausea, pain, ataxia, dysarthria, dyspnoea, dysphagia, psychiatric, dysaesthesia

Overview_SPSD symptoms / early disease (select)
- stiffness
- spasms
- startle = excessive startle

### 15. `stiffness_distribution_onset`

- Section: section: basic demographic data
- Source column(s): O
- Source label(s):
  - Stiffness distribution (select) / - lumb_prox_LE = lumbar/proximal legs / - distal_LE = distal leg(s) / - UE = arm(s) / upper extremity / - axial = axial(thoracic,neck) / - trismus / - multiple = multiple, but not generalised (specify in next col) / - generalised = generalised / - other = other, specify in next col
- Allowed values parsed from instruction: lumb_prox_LE, distal_LE, UE, axial, trismus, multiple, generalised, other, none, left_leg, unspecified, right_leg, spasms

Stiffness distribution (select)
- lumb_prox_LE = lumbar/proximal legs
- distal_LE = distal leg(s)
- UE = arm(s) / upper extremity
- axial = axial(thoracic,neck)
- trismus
- multiple = multiple, but not generalised (specify in next col)
- generalised = generalised
- other = other, specify in next col

### 16. `stiffness_distribution_onset_multiple`

- Section: section: basic demographic data
- Source column(s): P
- Source label(s):
  - Stiffness distribution: multiple (text)
- Allowed values parsed from instruction: lumb_prox_LE, distal_LE, UE, axial, lumb_proximal_LE, trismus, unspecified

Stiffness distribution: multiple (text)

### 17. `stiffness_distribution_onset_other`

- Section: section: basic demographic data
- Source column(s): Q
- Source label(s):
  - Stiffness distribution: other (text)
- Allowed values parsed from instruction: neck

Stiffness distribution: other (text)

### 18. `spasms_distribution_onset`

- Section: section: basic demographic data
- Source column(s): R
- Source label(s):
  - Spasms distribution (select) / - lumb_prox_LE = lumbar/proximal legs / - distal_LE = distal leg(s) / - UE = arm(s) / upper extremity / - axial = axial(thoracic,neck) / - generalised / - multiple = multiple, but not generalised (specify in next col) / - other = other, specify in next col
- Allowed values parsed from instruction: lumb_prox_LE, distal_LE, UE, axial, generalised, multiple, other, abdominal, jaw, diaphragm, esophageal, none, undefined, left_leg, unspecified, right_leg, stiffness, spasms

Spasms distribution (select)
- lumb_prox_LE = lumbar/proximal legs
- distal_LE = distal leg(s)
- UE = arm(s) / upper extremity
- axial = axial(thoracic,neck)
- generalised
- multiple = multiple, but not generalised (specify in next col)
- other = other, specify in next col

### 19. `spasms_distribution_onset_multiple`

- Section: section: basic demographic data
- Source column(s): S
- Source label(s):
  - Spasms distribution: multiple (text)
- Allowed values parsed from instruction: lumb_prox_LE, distal_LE, face, back, leg, UE, axial, bulbar, neck, right_leg, masseter

Spasms distribution: multiple (text)

### 20. `spasms_distribution_onset_other`

- Section: section: basic demographic data
- Source column(s): T
- Source label(s):
  - Spasms distribution: other (text)
- Allowed values parsed from instruction: neck

Spasms distribution: other (text)

### 21. `excessive_startle_onset`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): U
- Source label(s):
  - Excessive startle (select) / - touch = to touch / - noise = to noise / - visual = to visual stimuli / - multiple (specify in next col) / - other (specify in next col)
- Allowed values parsed from instruction: touch, noise, visual, multiple, other, unspecified, startle

Excessive startle (select)
- touch = to touch
- noise = to noise
- visual = to visual stimuli
- multiple (specify in next col)
- other (specify in next col)

### 22. `excessive_startle_onset_multiple`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): V
- Source label(s):
  - Excessive startle: multiple (text)
- Allowed values parsed from instruction: touch, noise, movement, visual, somatosensory, emotional, emotion

Excessive startle: multiple (text)

### 23. `excessive_startle_onset_other`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): W
- Source label(s):
  - Excessive startle: other (text)

Excessive startle: other (text)

### 24. `anxiety_onset`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): X
- Source label(s):
  - Anxiety (select) / - walking = anxiety related to walking unaided / - generalised = specify in next col
- Allowed values parsed from instruction: walking, generalised

Anxiety (select)
- walking = anxiety related to walking unaided
- generalised = specify in next col

### 25. `anxiety_onset_generalised`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): Y
- Source label(s):
  - Anxiety: generalised (text)

Anxiety: generalised (text)

### 26. `other_symptoms_onset`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): Z
- Source label(s):
  - Other symptoms: list all that apply within 1 cell, separated by semicolons  / (example: hyperhidrosis; babinski; sensory) / - hyperhidrosis / - autonomic = other autonomic symptoms (see legend and specify in next col) / - hyperreflexia / - babinski / - weakness / - lower_motor_neuron / - encephalopathy / - seizures = specify type / - oculomotor = specify type / - ptosis / - dysphagia / - dysgeusia / - sensory = hyp/paraesthesia / - allodynia / - freezing = freezing episodes / - other = specify in next col
- Allowed values parsed from instruction: hyperhidrosis, autonomic, hyperreflexia, babinski, weakness, lower_motor_neuron, encephalopathy, seizures, oculomotor, ptosis, dysphagia, dysgeusia, sensory, allodynia, freezing, other, fatigue, tingling, falls, back_pain, nystagmus, nausea, foot_oedema, clonus, hemidystonia, ataxia, LPR, numbness, cognitive, myoclonus, paraesthesia, seizure, polyneuropathy, paraethesia, lumbar_pain, hypoglossal_palsy, diplopia, facial_nerve_palsy, vomiting, cerebellar_ataxia, zoster_lesion_buttock, hypaesthesia, gait_disorder, hyporeflexia, abdominal_pain, dysphoria, fasciculation, muscle_atrophy, dysarthria, facial_weakness, facial_dysaethesia, limited_joint_motion, hearing_loss, asthenia, severe_pain, pain, dyspnoea, panic_attacks, visual_hallucinations, foot_drop, headache, confusion, agitation, hallucinations, anorexia, hiccups, irritability, stridor, respiratory_distress, cognitive_deficit, myocloni, cramp, tongue_paraesthesia, generalised_pruritus, posturing, jerky_movements_in_sleep, tachycardia, memory_loss, behavioural_changes

Other symptoms: list all that apply within 1 cell, separated by semicolons
(example: hyperhidrosis; babinski; sensory)
- hyperhidrosis
- autonomic = other autonomic symptoms (see legend and specify in next col)
- hyperreflexia
- babinski
- weakness
- lower_motor_neuron
- encephalopathy
- seizures = specify type
- oculomotor = specify type
- ptosis
- dysphagia
- dysgeusia
- sensory = hyp/paraesthesia
- allodynia
- freezing = freezing episodes
- other = specify in next col

### 27. `other_symptoms_onset_auto`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AA
- Source label(s):
  - Other symptoms: autonomic (text)
- Allowed values parsed from instruction: vomiting, tachycardia, urinary_urgency, fever, diarrhoea, urinary_retention

Other symptoms: autonomic (text)

### 28. `other_symptoms_onset_oculo`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AB
- Source label(s):
  - Other symptoms: oculomotor (text)
- Allowed values parsed from instruction: nystagmus, diplopia, esotropia, ptosis, anisocoria, spontaneous_downbeat_nystagmus, gaze_evoked_nystagmus, rebound_nystagmus, VOR_suppression_impairment, downbeat_nystagmus, bilateral_ptosis, left_lateral_gaze_palsy, ophthalmoplegia, unspecified

Other symptoms: oculomotor (text)

### 29. `other_symptoms_onset_seizures`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AC
- Source label(s):
  - Other symptoms: seizures (text)
- Allowed values parsed from instruction: focal, bilateral_focal_secondary_generalisation, cacosmia, tonic-clonic

Other symptoms: seizures (text)

### 30. `onset_mRS`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AD
- Source label(s):
  - Disability at onset - SPSD symptoms established; mRS / 0 - No symptoms. / 1 - No significant disability. Able to carry out all usual activities, despite some symptoms. / 2 - Slight disability. Able to look after own affairs without assistance, but unable to carry out all previous activities. / 3 - Moderate disability. Requires some help, but able to walk unassisted (i.e., without another person). / 4 - Moderately severe disability. Unable to attend to own bodily needs without assistance, and unable to walk unassisted. / 5 - Severe disability. Requires constant nursing care and attention, bedridden, incontinent. / 6 - Dead
- Allowed values parsed from instruction: 0, 1, 2, 3, 4, 5, 6

Disability at onset - SPSD symptoms established; mRS
0 - No symptoms.
1 - No significant disability. Able to carry out all usual activities, despite some symptoms.
2 - Slight disability. Able to look after own affairs without assistance, but unable to carry out all previous activities.
3 - Moderate disability. Requires some help, but able to walk unassisted (i.e., without another person).
4 - Moderately severe disability. Unable to attend to own bodily needs without assistance, and unable to walk unassisted.
5 - Severe disability. Requires constant nursing care and attention, bedridden, incontinent.
6 - Dead

### 31. `timecourse_onset`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AE
- Source label(s):
  - Time course of onset (select) / - insidious = insidious/subacute / - RR = relapsing-remitting / - fulminant = fulimant/peracute
- Allowed values parsed from instruction: insidious, RR, fulminant, subacute, insidous

Time course of onset (select)
- insidious = insidious/subacute
- RR = relapsing-remitting
- fulminant = fulimant/peracute

### 32. `diagnosis_onset`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AF
- Source label(s):
  - Diagnosis at onset (select) / - SPSD / - functional / - orthopaedic / - stroke / - other = specify in next col
- Allowed values parsed from instruction: SPSD, functional, orthopaedic, stroke, other, seizure, SPS, pancreatitis, epileptic

Diagnosis at onset (select)
- SPSD
- functional
- orthopaedic
- stroke
- other = specify in next col

### 33. `diagnosis_onset_other`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AG
- Source label(s):
  - Diagnosis at onset - other (text)

Diagnosis at onset - other (text)

### 34. `timecourse_subsequent`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AH
- Source label(s):
  - Subsequent disease course (select) / - monophasic / - RR = relapsing-remitting / - chronic_stable / - chronic-progressive / - rapidly-progressive
- Allowed values parsed from instruction: monophasic, RR, chronic_stable, chronic, rapidly, chronic-progressive, chronic-stable, chronic_progressive

Subsequent disease course (select)
- monophasic
- RR = relapsing-remitting
- chronic_stable
- chronic-progressive
- rapidly-progressive

### 35. `onset_to_established`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AI
- Source label(s):
  - Time from onset to fully established disease (months)

Time from onset to fully established disease (months)

### 36. `overview_established`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AK
- Source label(s):
  - Overview_SPSD symptoms / established disease / - stiffness / - spasms / - startle = excessive startle
- Allowed values parsed from instruction: stiffness, spasms, startle, fatigue, tingling, falls, back_pain, nystagmus, nausea, gait_disorder, pain, dyspnoea, weakness, dysphagia, myoclonus, ataxia, respiratory_failure

Overview_SPSD symptoms / established disease
- stiffness
- spasms
- startle = excessive startle

### 37. `stiffness_distribution_established`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AL
- Source label(s):
  - Stiffness distribution in established disease (select) / - lumb_prox_LE = lumbar/proximal legs / - distal_LE = distal leg(s) / - UE = arm(s) / upper extremity / - axial = axial(thoracic,neck) / - trismus / - multiple = multiple, but not generalised / - generalised = generalised / - other = other, specify in next col
- Allowed values parsed from instruction: lumb_prox_LE, distal_LE, UE, axial, trismus, multiple, generalised, other, unspecified, left_leg, neck, stiffness, spasms, right_leg

Stiffness distribution in established disease (select)
- lumb_prox_LE = lumbar/proximal legs
- distal_LE = distal leg(s)
- UE = arm(s) / upper extremity
- axial = axial(thoracic,neck)
- trismus
- multiple = multiple, but not generalised
- generalised = generalised
- other = other, specify in next col

### 38. `stiffness_distribution_established_multiple`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AM
- Source label(s):
  - Stiffness distribution in established disease: multiple (text)
- Allowed values parsed from instruction: lumb_prox_LE, distal_LE, UE, axial, trismus, diaphragm, left_leg, neck, generalised, facial, 1, 2, 5, 6, axia

Stiffness distribution in established disease: multiple (text)

### 39. `stiffness_distribution_established_other`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AN
- Source label(s):
  - Stiffness distribution in established disease: other (text)
- Allowed values parsed from instruction: 3, 4, 1, 2, generalised, tongue, esophagus, risus_sardonicus, distal_LE, lumb_prox_LE

Stiffness distribution in established disease: other (text)

### 40. `spasms_distribution_established`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AO
- Source label(s):
  - Spasms distribution (select) / - lumb_prox_LE = lumbar/proximal legs / - distal_LE = distal leg(s) / - UE = arm(s) / upper extremity / - axial = axial(thoracic,neck) / - generalised / - multiple = multiple, but not generalised (specify in next col) / - other = other, specify in next col
- Allowed values parsed from instruction: lumb_prox_LE, distal_LE, UE, axial, generalised, multiple, other, abdominal, jaw, diaphragm, esophageal, gerneralised, abdomen, unspecified, right_leg, left_leg, face, chronic_stable

Spasms distribution (select)
- lumb_prox_LE = lumbar/proximal legs
- distal_LE = distal leg(s)
- UE = arm(s) / upper extremity
- axial = axial(thoracic,neck)
- generalised
- multiple = multiple, but not generalised (specify in next col)
- other = other, specify in next col

### 41. `spasms_distribution_established_multiple`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AP
- Source label(s):
  - Spasms distribution: multiple (text)
- Allowed values parsed from instruction: axial, lumb_prox_LE, distal_LE, face, back, leg, UE, laryngospasm, neck, shoulder, masseter, right_leg, facial, axia

Spasms distribution: multiple (text)

### 42. `spasms_distribution_established_other`

- Section: 3. section: disease onset, signs and symptoms
- Source column(s): AQ
- Source label(s):
  - Spasms distribution: other (text)
- Allowed values parsed from instruction: unspecified

Spasms distribution: other (text)

### 43. `excessive_startle_established`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AR
- Source label(s):
  - Excessive startle (select) / - touch = to touch / - noise = to noise / - visual = to visual stimuli / - multiple (specify in next col)
- Allowed values parsed from instruction: touch, noise, visual, multiple, unspecified, movement, none, somatosensory, emotional

Excessive startle (select)
- touch = to touch
- noise = to noise
- visual = to visual stimuli
- multiple (specify in next col)

### 44. `excessive_startle_established_multipleother`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AS
- Source label(s):
  - Excessive startle: multiple or other (text)
- Allowed values parsed from instruction: 1, 3, 0, 2, 4, touch, noise, emotional, auditory, somatosensory, visual, movement, tactile, speaking, environmental, cold, temperature, 6

Excessive startle: multiple or other (text)

### 45. `anxiety_established`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AT
- Source label(s):
  - Anxiety (select) / - walking = anxiety related to walking unaided / - generalised = specify in next col
- Allowed values parsed from instruction: walking, generalised, agoraphobia

Anxiety (select)
- walking = anxiety related to walking unaided
- generalised = specify in next col

### 46. `anxiety_established_generalised`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AU
- Source label(s):
  - Anxiety: generalised (text)

Anxiety: generalised (text)

### 47. `other_symptoms_established`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AV
- Source label(s):
  - Other symptoms: list all that apply within 1 cell, separated by semicolons  / (example: hyperhidrosis; babinski; sensory) / - hyperhidrosis / - autonomic = other autonomic symptoms (see legend and specify in next cols) / - hyperreflexia / - babinski / - weakness / - lower_motor_neuron / - encephalopathy / - seizures = specify type in next cols / - oculomotor = specify type in next cols / - ptosis / - dysphagia / - dysgeusia / - sensory = hyp/paraesthesia / - allodynia / - freezing = freezing episodes / - other = specify in next cols
- Allowed values parsed from instruction: hyperhidrosis, autonomic, hyperreflexia, babinski, weakness, lower_motor_neuron, encephalopathy, seizures, oculomotor, ptosis, dysphagia, dysgeusia, sensory, allodynia, freezing, other, fatigue, tingling, falls, back_pain, nystagmus, nausea, foot_oedema, clonus, hemidystonia, ataxia, LPR, depression, lordosis, tetraparesis, paraethesia, numbness, apnoea, neuropathic_pain, myoclonus, cognitive, paranoia, frontal_syndrome, delirium, delusions, agitation, tremor, hyperekplexia, dysarthria, RBD, delusion, hypersomnia, hyperesthesia, confabulation, Confusion, hallucination, pruritus, anxiety, irritability, gait_disorder, balance_disorder, memory_disorder, central_sleep_apnoea, facial_weakness, diabetes_insipidus, hypaesthesia, dystonia, dispnoea, cynanosis_of_affected_arm, respiratory_insufficiency, opisthotonus, vocal_cord_paralysis, parkinsonism, cerebellar_ataxia, tremors, dysphonia, hyperCKaemia, amnesia, psychomotor_slowing, decreased_esophageal_motility, hyporeflexia, dyspnoea, auditory_hallucinations, areflexia, facial_dysaethesia, hyponatraemia, dysmetria, pain, hearing_loss, paralysis_upper_limbs, myocloni, fasciculations, long_tract_findings, headache, confusion, hallucinations, agoraphobia, pyrexia, jerks, cognitive_disorder, spasticity, atrophy_leg_muscles, UMN_facial_weakness, cramping, visual_disortion, dystonia-like_posturing, scanning_speech, tongue_paraesthesia, facial, dysaesthesia, hyponatriaemia, akinetic_rigid_parkinsonism, immobility, generalised_weakness, weight_loss, respiratory_failure, posturing, respiratory_arrest, posturing_foot, distal_amyotrophy, tachypnoea, dementia, tongue_paresis, hyperaesthesia, tachycardia, intention_tremor, titubation, progressive_scoliosis

Other symptoms: list all that apply within 1 cell, separated by semicolons
(example: hyperhidrosis; babinski; sensory)
- hyperhidrosis
- autonomic = other autonomic symptoms (see legend and specify in next cols)
- hyperreflexia
- babinski
- weakness
- lower_motor_neuron
- encephalopathy
- seizures = specify type in next cols
- oculomotor = specify type in next cols
- ptosis
- dysphagia
- dysgeusia
- sensory = hyp/paraesthesia
- allodynia
- freezing = freezing episodes
- other = specify in next cols

### 48. `other_symptoms_established_auto`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AW
- Source label(s):
  - Other symptoms: autonomic (text)
- Allowed values parsed from instruction: tachycardia, urinary_retention, sympathetic_storming, pallor, fever, hypertension, bladder_incontinence, nausea, hyperpyrexia, constipation, flushing, blood_pressure_instability, palpitations, urine_retention, stool_retention, pupillary_dilation, urinary_urgency, tachypnoea, cardiac_arrhythmia, cardiac_arrest, oculomotor, severe_autonomic_failure, vomiting, diarrhoea, urinary_disorder, orthostatic_hypotension, respiratory_arrest, pulseless_electrical_activity

Other symptoms: autonomic (text)

### 49. `other_symptoms_established_oculo`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AX
- Source label(s):
  - Other symptoms: oculomotor (text)
- Allowed values parsed from instruction: diplopia, disturbed_smooth_pursuit, ophthalmoplegia, blepharospasm, nystagmus, saccadic_pursuit, end-gaze_nystagmus, palsy, gaze-evoked_nystagmus, ptosis, bilateral_ptosis, partial_horizontal_gaze_palsies, horizontal_nystagmus, myoclonus, cerebellar_oculomotor_disorder, saccadic_intrusions, abducens_nerve_palsy, abduction_weakness_left_eye, ocular_flutter, slowed_saccades, complete_horizontal_gaze_palsy, 6th_CN_paresis, multidirectional_nystagmus, slow_saccades, downbeat_nystagmus

Other symptoms: oculomotor (text)

### 50. `other_symptoms_established_seizures`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AY
- Source label(s):
  - Other symptoms: seizures (text)
- Allowed values parsed from instruction: seizures, generalised_tonic_clonic, generalised, unspecified

Other symptoms: seizures (text)

### 51. `established_mRS`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): AZ
- Source label(s):
  - Disability when disease fully established                                  (SPSD symptoms established; mRS / 0 - No symptoms. / 1 - No significant disability. Able to carry out all usual activities, despite some symptoms. / 2 - Slight disability. Able to look after own affairs without assistance, but unable to carry out all previous activities. / 3 - Moderate disability. Requires some help, but able to walk unassisted (i.e., without another person). / 4 - Moderately severe disability. Unable to attend to own bodily needs without assistance, and unable to walk unassisted. / 5 - Severe disability. Requires constant nursing care and attention, bedridden, incontinent. / 6 - Dead
- Allowed values parsed from instruction: 0, 1, 2, 3, 4, 5, 6, 3.5

Disability when disease fully established                                  (SPSD symptoms established; mRS
0 - No symptoms.
1 - No significant disability. Able to carry out all usual activities, despite some symptoms.
2 - Slight disability. Able to look after own affairs without assistance, but unable to carry out all previous activities.
3 - Moderate disability. Requires some help, but able to walk unassisted (i.e., without another person).
4 - Moderately severe disability. Unable to attend to own bodily needs without assistance, and unable to walk unassisted.
5 - Severe disability. Requires constant nursing care and attention, bedridden, incontinent.
6 - Dead

### 52. `course_treatment`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BA
- Source label(s):
  - Course / symptoms potentially influenced by treatment (select) / - none = no treatment / - sympt = benzodiazepine or similar / - immunotherapy / - both = both symptomatic and immunotherapy
- Allowed values parsed from instruction: none, sympt, immunotherapy, both

Course / symptoms potentially influenced by treatment (select)
- none = no treatment
- sympt = benzodiazepine or similar
- immunotherapy
- both = both symptomatic and immunotherapy

### 53. `antibody_status`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BB
- Source label(s):
  - Antibody status (select) / - GAD / - GlyR / - amphiphysin / - DPPX / - seronegative / - multiple = multiple, specify in next col / - other = other, specify in next col / - not_tested = no test performed / - NA = not available, not reported, unclear if tested
- Allowed values parsed from instruction: GAD, GlyR, amphiphysin, DPPX, seronegative, multiple, other, not_tested, NA, ANA, anti-Smith, GAD65, pm-scl, titin, AQP4, Ro, islet_cell, dsDNA, thyroglobulin, TPO, microsomal, Ri, gAChRa3, parietal_cell

Antibody status (select)
- GAD
- GlyR
- amphiphysin
- DPPX
- seronegative
- multiple = multiple, specify in next col
- other = other, specify in next col
- not_tested = no test performed
- NA = not available, not reported, unclear if tested

### 54. `antibody_status_other`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BC
- Source label(s):
  - Antibody status (other) / If "other" was selected, list as text. Otherwise, leave blank.
- Allowed values parsed from instruction: GlyR, GAD, AChR, ANA, gephyrin, Ri, GAD65, IA2, GM1, sulfatide, intrinsic_factor, dsDNA, RP, Scl-70, cardiolipin, thyroglobulin, TPO, NMDAR, VGKC, gastric_parietal_cell, pancreatic_islet, TG, microsomal, mitochondrial, 21betahydroxylase, islet, CV2

Antibody status (other)
If "other" was selected, list as text. Otherwise, leave blank.

### 55. `antibody_titre`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BD
- Source label(s):
  - Antibody titre

Antibody titre

### 56. `antibody_units`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BE
- Source label(s):
  - Antibody units

Antibody units

### 57. `antibody_tests`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BF
- Source label(s):
  - Antibodies tested  / list all antibodies that were tested, separated by semicolons
- Allowed values parsed from instruction: GAD, amphiphysin, GlyR, VGKC, NMDAR, AQP4, Thyroid, ANA, SS-A/B, Amphiphysin, Hu, Ri, Yo, CV2, Ma1, Ma2, SOX, Zic, Gad65, Tr, ANNA3, PCA, AMPAR, CASPR2, DPPX, GABAbR, mGluR1, mGluR5, LGI1, AChR, CYFRA21-1, CEA, MA1, MA2, CRMP5, ssDNA, dsDNA, pancreatic_islet, TG, mitochondrial, CRMP5/Cv2, recoverine, ANCA, paraneoplastic_panel, GABAAR, GABABR, IgLON5, neurexin3a, pm-scl, GAD65, DRD2, Neu3a, AMPA1, AMPA2, Ro, MAG, GM1, GQ1B, TPO, ganglioside, polymyositis, CV2.1, AchR, VGCC, titin, parietal_cell, RF, anti-smooth_muscle, thyroid_microsomal, antineuronal, islet_cell, recoverin, SOX1, Zic4, paraneoplastic, cytoplasm, transglutaminase, gliadin, paretal_cell, insulin, IA-2, Ma1/2, insulin_receptor, cardiolipin, gangliosides, islet_cells, gephyrin, neuronal_surface_antibodies, thyroglobulin, FANA, lupus_anticoagulant, platelet, SSA/B, GQ1b, GABARB, NAE, gAChRa3, gAChRb4, R, ANNA-3, neuronal, thyroid, AGNA, intrinsic_factor, RP, Scl-70, Cv2/CRMP5, Sox1, GABARAP, MUSK, Purkinje, Ma, PCA2, PCA-Tr, coeliac, gastric_parietal_cell

Antibodies tested
list all antibodies that were tested, separated by semicolons

### 58. `antibody_testsystem`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BG
- Source label(s):
  - Antibody test system
- Allowed values parsed from instruction: IHC, radioimmunoprecipitation, immunoblot, western_blot, tissue_assay, immunofluorescence, LIPS, radioimmunoassay, ELISA, RIA, immunocytochemistry, immunoprecipitation

Antibody test system

### 59. `antibody_notes`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BH
- Source label(s):
  - Antibody notes / If not covered by columns to the left, give as text note. Otherwise, leave blank.

Antibody notes
If not covered by columns to the left, give as text note. Otherwise, leave blank.

### 60. `CSF_status`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BI
- Source label(s):
  - CSF (select) /  - normal / - inflammatory / - isolated protein elevation / - not_done = no CSF analysis performed / - antibody_present = antibody present in CSF (specify Ab and titre in next cols) / - NA = not available / NR
- Allowed values parsed from instruction: normal, inflammatory, isolated, not_done, antibody_present, NA, OCB, pleocytosis, isolated_protein_elevation, high_cell_count, high_protein

CSF (select)
 - normal
- inflammatory
- isolated protein elevation
- not_done = no CSF analysis performed
- antibody_present = antibody present in CSF (specify Ab and titre in next cols)
- NA = not available / NR

### 61. `CSF_antibody`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BJ
- Source label(s):
  - CSF antibody (specify)
- Allowed values parsed from instruction: none, GAD, GlyR, Amphiphysin, gephyrin, Ri, DPPX, seronegative, amphiphysin, GAD65, NMDAR

CSF antibody identity. Return antibody names detected in CSF. Use none if CSF antibody testing was reported and no antibodies were found. Use NA if CSF antibody testing is not reported. Do not use not_tested.

### 62. `CSF_antibody_titre`

- Section: 4. section: established disease, signs and symptoms
- Source column(s): BK
- Source label(s):
  - CSF antibody titre (numeric)

CSF antibody titre (numeric)

### 63. `CMUA`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BL
- Source label(s):
  - continuous motor unit activity (CMUA) / 0 = not detected / 1 = present / NA = no EMG, NR, unknown
- Allowed values parsed from instruction: 0, 1

continuous motor unit activity (CMUA)
0 = not detected
1 = present
NA = no EMG, NR, unknown

### 64. `exteroceptive_refl`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BM
- Source label(s):
  - enhanced exteroceptive reflexes / 0 = not detected / 1 = present / NA = not done, NR, unknown
- Allowed values parsed from instruction: 0, 1

enhanced exteroceptive reflexes
0 = not detected
1 = present
NA = not done, NR, unknown

### 65. `brainstem_refl`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BN
- Source label(s):
  - brainstem reflexes / 0 = not detected / 1 = present / NA = not done, NR, unknown
- Allowed values parsed from instruction: 0, 1

brainstem reflexes
0 = not detected
1 = present
NA = not done, NR, unknown

### 66. `MRI_normal`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BO
- Source label(s):
  - MRI / 0 = normal / 1 = abnormal (specify in next col) / NA = no MRI performed, not reported, unclear
- Allowed values parsed from instruction: 0, 1

MRI
0 = normal
1 = abnormal (specify in next col)
NA = no MRI performed, not reported, unclear

### 67. `MRI_abnormalities`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BP
- Source label(s):
  - MRI abnormalities (text)

MRI abnormalities (text)

### 68. `tu_screening`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BQ
- Source label(s):
  - Tumour screening / 0 = normal / no tumour detected / 1 = abnormal (specify in next col) / NA = not performed, NR
- Allowed values parsed from instruction: 0, 1

Tumour screening
0 = normal / no tumour detected
1 = abnormal (specify in next col)
NA = not performed, NR

### 69. `tu_screening_abnormal`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BR
- Source label(s):
  - Tumour screening abnormal / specify tumour entity with text

Tumour screening abnormal
specify tumour entity with text

### 70. `immunotherapy`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BS
- Source label(s):
  - Immunotherapy (specify) / - none = not done / - steroids / - IVIG / - PLEX / - RXB = Rituximab / - CP = Cyclophopsphamide / - Aza = Azathioprine / - multiple = specify in next col / - other = specify in next col / - NA = unknown, NR
- Allowed values parsed from instruction: none, steroids, IVIG, PLEX, RXB, CP, Aza, multiple, other, NA, HSCT, tacrolimus, MMF, CySp, unspecified, AZA, efgartigimod, VIG, SCIG, steorids, vincristine, prednisolone, mycophenolate, methylprednisolone, steroid, cyclosporin

Immunotherapy (specify)
- none = not done
- steroids
- IVIG
- PLEX
- RXB = Rituximab
- CP = Cyclophopsphamide
- Aza = Azathioprine
- multiple = specify in next col
- other = specify in next col
- NA = unknown, NR

### 71. `immunotherapy_detail`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BT
- Source label(s):
  - Immunotherapy in detail (please describe dose, how many cycles, intervals)

Immunotherapy in detail (please describe dose, how many cycles, intervals)

### 72. `immunotherapy_effect`

- Section: 5. section: investigations (antibodies, electrophysiology, other)
- Source column(s): BU
- Source label(s):
  - Effect of immunotherapy (select) / - none / - worsening / - improvement / - stabilisation / - NA = not known
- Allowed values parsed from instruction: none, worsening, improvement, stabilisation, NA, responder, poor, moderate, partial, insufficient

Effect of immunotherapy (select)
- none
- worsening
- improvement
- stabilisation
- NA = not known

### 73. `sympt_treatment`

- Section: 6. section: treatment
- Source column(s): BV
- Source label(s):
  - Symptomatic treatment (select) / - none / - clonazepam / - benzo = other benzodiazepines / - baclofen / - gabapentin / - pregabalin / - tizanidine / - valproate / - other (specify)
- Allowed values parsed from instruction: none, clonazepam, benzo, baclofen, gabapentin, pregabalin, tizanidine, valproate, other, propofol, carbamazepine, botulinum_toxin, morphine, escitalopram, amitriptylin, diazepam, levetiracetam, oxcarbazepine, botulinumtoxin, olanzapine, dexmetomidine, methocarbamol, cyclobenzaprine, oxycodone/paracetamol, pancuronium, ventilatory_support, sedation, botox, rehab, fentanyl, physical_therapy, ethanol, oxycodone, nortriptyline, unspecified, phenytoin, dantrolene, clonidine, amitriptyline, trihexyphenidyl, levodopa, vigabatrin, lacosamide

Symptomatic treatment (select)
- none
- clonazepam
- benzo = other benzodiazepines
- baclofen
- gabapentin
- pregabalin
- tizanidine
- valproate
- other (specify)

### 74. `sympt_treatment_detail`

- Section: 6. section: treatment
- Source column(s): BW
- Source label(s):
  - symptomatic treatment in detail (please describe route of administration and dose)

symptomatic treatment in detail (please describe route of administration and dose)

### 75. `sympt_treatment_effect`

- Section: 6. section: treatment
- Source column(s): BX
- Source label(s):
  - Effect of symptomatic treatment (select) / - none / - worsening / - improvement / - stabilisation / - NA = not known
- Allowed values parsed from instruction: none, worsening, improvement, stabilisation, NA, minimal

Effect of symptomatic treatment (select)
- none
- worsening
- improvement
- stabilisation
- NA = not known

### 76. `other_treatment`

- Section: 6. section: treatment
- Source column(s): BY
- Source label(s):
  - Other treatment (text) / (e.g. tumour therapy)
- Allowed values parsed from instruction: physiotherapy, Died, Thymectomy, RXB, CP, steroids, Aza, steroids/Aza, MMF, CySp, chemotherapy, radiotherapy, tizanidine, R-CHOP, GPi-DBS, tamoxifen, mastectomy, cyclophosphamide, vinblastine, doxorubicin, anti-estrogenics, botulinumtoxin, auto-HSCT

Other treatment (text)
(e.g. tumour therapy)

### 77. `autoimmunity`

- Section: 6. section: treatment
- Source column(s): BZ
- Source label(s):
  - Concomitant autoimmunity (select) / - none / - thyroid = thyroid disease/thyroid antibodies / - diabetes / - vitiligo / - gastric = pernicious anaemia/parietal cell antibodies / - other= other, specify in next col
- Allowed values parsed from instruction: none, thyroid, diabetes, vitiligo, gastric, other, coeliac, PA, asthma, arthritis, myasthenia_gravis, pemphigus, thyoid, SLE, alopecia_totalis, APS2, rheumatoid_arthritis, coeliac_disease, dermatitis_herpetiformis, uveitis

Concomitant autoimmunity (select)
- none
- thyroid = thyroid disease/thyroid antibodies
- diabetes
- vitiligo
- gastric = pernicious anaemia/parietal cell antibodies
- other= other, specify in next col

### 78. `autoimmunity_specify`

- Section: 7. section: concomittant disease and family history
- Source column(s): CA
- Source label(s):
  - Concomitant autoimmunity (specify with text)

Concomitant autoimmunity (specify with text)

### 79. `family_history`

- Section: 7. section: concomittant disease and family history
- Source column(s): CB
- Source label(s):
  - Family history (select) / - none = no fhx for SPSD or autoimmunity / - autoimmune = fhx for autoimmunity (specify in next col) / - SPSD = fhx for SPSD (specify in next col) / - NA = unknown, not reported
- Allowed values parsed from instruction: none, autoimmune, SPSD, NA, autoimmunity

Family history (select)
- none = no fhx for SPSD or autoimmunity
- autoimmune = fhx for autoimmunity (specify in next col)
- SPSD = fhx for SPSD (specify in next col)
- NA = unknown, not reported

### 80. `family_history_abnormal`

- Section: 7. section: concomittant disease and family history
- Source column(s): CC
- Source label(s):
  - Family history (text) / if autoimmune diseases and/or SPSD are present, specify with text

Family history (text)
if autoimmune diseases and/or SPSD are present, specify with text

### 81. `notes`

- Section: 8.section: comments
- Source column(s): CD
- Source label(s):
  - Any observations or aspects not covered but worth mentioning

Any observations or aspects not covered but worth mentioning
