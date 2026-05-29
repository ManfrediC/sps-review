# Git Status

 M .gitignore
 M examples/datasheet_examples_MC_Case_Report_Form.csv
 M src/pipelines/09_build_langextract_examples.py
 M src/pipelines/10_langextract.py
 M src/pipelines/README.md
 M tests/test_10_langextract.py
?? doc/plans/embeddings_plan.md
?? doc/proposals/
?? doc/reports/
?? examples/langextract_bootstrap/
?? qa/validation/langextract_example_bootstrap/
?? resources/stage07_single_case_gold_json_index.csv
?? tests/test_09_build_langextract_examples.py


# Staged Diff





# Unstaged Diff

 .gitignore                                         |    1 +
 .../datasheet_examples_MC_Case_Report_Form.csv     |   12 +-
 src/pipelines/09_build_langextract_examples.py     | 1559 ++++++++++++++++----
 src/pipelines/10_langextract.py                    |   15 +
 src/pipelines/README.md                            |    9 +-
 tests/test_10_langextract.py                       |   26 +
 6 files changed, 1327 insertions(+), 295 deletions(-)


diff --git a/.gitignore b/.gitignore
index 19cb24f..7825d00 100644
--- a/.gitignore
+++ b/.gitignore
@@ -66,3 +66,4 @@ qa/validation/stage07_smoke/*_stage07_smoke/
 # Local scratch plans and manuscript drafts
 /plans/
 /doc/notes/
+/scratch/
diff --git a/examples/datasheet_examples_MC_Case_Report_Form.csv b/examples/datasheet_examples_MC_Case_Report_Form.csv
index 730dffb..8e96e06 100644
--- a/examples/datasheet_examples_MC_Case_Report_Form.csv
+++ b/examples/datasheet_examples_MC_Case_Report_Form.csv
@@ -425,7 +425,7 @@ steroids was maintained. Rituximab was started 4 months thereafter
 as maintenance therapy (2 1 g doses separated by one
 fortnight, then 1 g 6-monthly), allowing steroid cessation. IV
 immunoglobulin was not administered.",improvement,,,,,,,,,
-MC,197,,58,M,,58,,0.25,multiple,stiffness;spasms;gait_disorder;dysarthria;dysphagia,,Stiff_Person,,,stiffness;spasms,multiple,lumb_prox_LE;distal_LE;axial,,multiple,axial;bulbar,,,,,,,,,,,,,,,,,,stiffness;spasms,generalised,,generalised;tongue;esophagus,gerneralised,,,multiple,touch;noise,,,myoclonus,,,,,,multiple,gephyrin;ANA,,,GAD;amphiphysin,"western blot, cell based assay",,antibody_present,gephyrin,,1,,,0,,1,undifferentiated carcinoma of undetermined origin in the mediastinum,,,,benzo,"Oral diazepam was initiated before surgery (20 mg/day). Both the stiffness spasms lessened markedly, and the patient was  able to walk and speak smoothly.",improvement,tumour removal,,,,,
+MC,197,,58,M,,58,,0.17,multiple,stiffness;spasms;gait_disorder;dysarthria;dysphagia,,Stiff_Person,,,stiffness;spasms,multiple,lumb_prox_LE;distal_LE;axial,,multiple,axial;bulbar,,,,,,,,,,,,,,,,,,stiffness;spasms,generalised,,generalised;tongue;esophagus,gerneralised,,,multiple,touch;noise,,,myoclonus,,,,,,multiple,gephyrin;ANA,,,GAD;amphiphysin,"western blot, cell based assay",,antibody_present,gephyrin,,1,,,0,,1,undifferentiated carcinoma of undetermined origin in the mediastinum,,,,benzo,"Oral diazepam was initiated before surgery (20 mg/day). Both the stiffness spasms lessened markedly, and the patient was  able to walk and speak smoothly.",improvement,tumour removal,,,,,
 MC,11913,,54,F,E_asia,44,10,,multiple,unresponsiveness,,GAD-Epilepsy;Stiff_Person,,,,,,,,,,,,,,,seizure,,,focal impaired awareness,,,,,,60,,stiffness,lumb_prox_LE;distal_LE;UE,,,,,,,,,,cognitive;babinski,,,,,,GAD,,0.111111111,dilution,,,,antibody_present,GAD,0.111111111,1,,,0,,0,,steroids;IVIG,"intravenous infusion of 1000 mg methylprednisolone per day for three consecutive days, which was then reduced gradually to 240 mg for three days, 120 mg for three days, and then orally to 60 mg per day. On
 the fourteenth day of hospitalization, the patient was administered intravenous infusion
 of 
@@ -491,7 +491,7 @@ MC,12545,,22,F,,,,,spasms,,,,,,,,,,,,,,,,,,,,,,,,,,,,,spasms;stiffness,axial;lum
 MC,1398,,58,M,,45,,,multiple,memory_disorder;anxiety;depression;OCD;apathy,,,,,stiffness,,,,,,,,,,,,,,,,,,,,,156,,,axial,,,,,,,,,,gait_disorder;balance_disorder;memory_disorder;autonomic;hyperreflexia,bladder_incontinence;nausea,,,,,GAD,,,,,,,isolated protein elevation,,,,,,1,right temporal lobe and hippocampal atrophy,,,IVIG,,improvement,,,,,,,,,
 MC,12202,,16,F,E_asia,16,3,,multiple,impaired_consciousness;urinary_incontinence;stiffness;fever;tachycardia;hypotension;rhabdomyolysis;renal_injury,,PERM,,,,multiple,distal_LE;lumb_prox_LE,,,,,,,,,,,,,,,,other,"myocarditis, encephalitis and septic shock",monophasic,0.25,,,multiple,axial;lumb_prox_LE;distal_LE,,generalised,,,touch,,,,encephalopathy;autonomic;oculomotor,hyperpyrexia;bladder_incontinence;constipation;flushing;blood_pressure_instability,nystagmus,,5,,GAD;Ro;ANA,,170,IU/mL,GAD;Ro;ANA;NMDAR;CASPR2;LGI1;AMPAR;GABAAR;GABABR,,,isolated pleocytosis,,,,,,1,"Brain: subtle hyperintensity in bilateral medial temporal lobes on T2 and FLAIR. Spine: myelitis with mildly swollen spinal cord, bilat T2 hyperintensity Th10 to conus medullaris",0,,steroids;IVIG;PLEX;RXB,"steroids, IVIG, PLEX: fluctuating partial response. RXB: significant and persistent response. No relapse during 3y post discharge.",improvement,benzo,midazolam: improvement,,,thyroid,,,,Testing for anti-GlyR and CSF anti-GAD was not available. EEG: generalised delta brush
 MC,896,,50,F,E_asia,48,2,,multiple,stiffness;spasms,,Stiff_Person,,,,NA,,,NA,,,,,,,,,,,,,,,,,,24,,,,,,,,,,,,hypersomnia;central_sleep_apnoea,,,,,,seronegative,,,,GAD65,,,,,,1,,,,,1,thymoma (SPS began AFTER excision),IVIG,IVIG: somnolence improved after administration,improvement,benzo;clonazepam;pregabalin,diazepam: improved CMUA. Clonazepam: severe adverse effects (unspecified). Pregabalin: improvement,improvement,,,,,,SPS began AFTER thymoma excision
-MC,155,,51,M,,,,,multiple,stiffness,,Stiff_Person,,Lorish et al.,,,,,,,,,,,,,,,,,,,,,,,,,axial,,,other,,unspecified,movement;noise,,,,,,,,,,GAD;IA-2,,,,,,,normal,NA,NA,1,,,,,,,steroids;IVIG,"500mg iv prednisolone / day for 10d, followed by oral tapering. Then daily 5mg prednisolone and 3 x 5mg diazepam",,benzo,"diazepam 3 x 2.5mg / day for 1 year, then diazepam was no longer effective. Then baclofen 3 x 20-25mg/day, improvement for only 4 weeks. Then immunosuppression.",improvement,,,diabetes,,,"""thin basement membrane disease"" as comorbidity"
+MC,155,,51,M,,,,,multiple,stiffness,,Stiff_Person,,Lorish et al.,,,,,,,,,,,,,,,,,,,,,,,,,axial,,,other,,unspecified,movement;noise,,,,,,,,,,GAD;islet_cell,,,,,,,normal,NA,NA,1,,,,,,,steroids,"500mg iv prednisolone / day for 10d, followed by oral tapering. Then daily 5mg prednisolone and 3 x 5mg diazepam",,benzo,"diazepam 3 x 2.5mg / day for 1 year, then diazepam was no longer effective. Then baclofen 3 x 20-25mg/day, improvement for only 4 weeks. Then immunosuppression.",improvement,,,diabetes,,,"""thin basement membrane disease"" as comorbidity"
 MC,6054,,55,M,,54,2,,multiple,tingling;myocloni,,PERM,,,,,,,multiple,distal_LE;lumb_prox_LE;UE;axial,,multiple,touch;noise,,,,,,,,,,,,,1,,,multiple,axial;lumb_prox_LE;distal_LE,,,,,touch;noise,,,,oculomotor;facial_weakness,,bilateral_ptosis;partial_horizontal_gaze_palsies;,,,,GlyR,,,,Yo;Hu;Ri;GAD;Amphiphysin;MAG;GM1;GQ1B,cell based assay,,inflammatory,,,1,,,0,,0,,IVIG;steroids;PLEX;CP,"Improvement with IVIG, methylprednisolone, PLEX, and 3x iv cyclophosphamide 0.82g, but relapse after 14 months. Restarted with iv methylprednisolone, PLEX and 6x CP. Improvement",improvement,benzo;levetiracetam,"clonazepam and levetiracetam improved the hyperekplexia. After immunotherapy, intraspinal baclofen pump with improvement.",,,,,,,R2 blink reflexes were absent
 MC,3134,,49,,,,,0.66,multiple,stiffness;spasms,,,,,,,,,,,,touch,,,,,,,,,,,,,,,,,axial,,,generalised,,,touch,,,,diabetes_insipidus;babinski;autonomic,hypertension;tachycardia,,,,,amphiphysin,,0.263888889,,GAD;Hu;Yo;GlyR;amphiphysin,,,inflammatory,NA,NA,1,,,1,"Brain: hyperintensity over the hypothalamus (FLAIR). Spine: T2 signal abnormality C1-C6, consistent with transverse myelitis",1,breast: invasive metastatic ductal carcinoma,steroids;IVIG;PLEX;RXB,"steroids: minimal effect. IVIG, PLEX and RXB followed by stabilisation of neurological symptoms, also resolution of DI",stabilisation,benzo;baclofen,diazepam and baclofen: minimal improvement,minimal,,,,,,Paraneoplastic SPS with central diabetes insipidus and transverse myelitis. Normal EEG
 MC,12114,,83,F,white,83,0.5,,multiple,weakness;spasms,,Stiff_Person,,,,,,,,,,,,,,,,,,,,,,,monophasic,3,6,spasms,distal_LE,,,multiple,lumb_prox_LE;distal_LE,,touch,,,,hypaesthesia;dystonia;babinski,,,,,,amphiphysin,,,,amphiphysin;GAD;TPO;TG;ganglioside;polymyositis;NMDAR;CV2.1;AchR;VGCC;AQP4;VGKC;titin;parietal_cell,,,inflammatory,,,1,,,0,,1,breast: invasive metastatic ductal carcinoma,PLEX,,none,methocarbamol;cyclobenzaprine;baclofen;benzo,"methocarbamol, cyclobenzaprine, baclofen: minimal response. Diazepam: improvement",improvement,"tumour therapy declined, death after 6 months",other,coeliac,,,
@@ -500,7 +500,7 @@ MC,12387,,48,F,,,,,multiple,pain;stiffness;spasms;gait_disorder,,Stiff_Person,,,
 MC,2387,,27,F,latin,,,0.16,multiple,arm weakness; arm limited range of motion,,Stiff_Person,,,,,,,,,,,,,,,,,,,,,,,,2,,stiffness,UE;axial,,,,,,noise,,generalised,,dispnoea;autonomic;dysarthria;dysphagia,nausea;palpitations,,,,,GAD;dsDNA;ANA,,3145,nmol/L,,,,NA,,,1,,,0,,0,,steroids,methylprednisolone over 5 days.,improvement,baclofen;clonazepam;oxycodone/paracetamol,baclofen 10mg 3x/d,improvement,,,,,,
 MC,637,,50,F,africa,,2.5,,multiple,stiffness;spasms,,PERM,,,,generalised,,,,,,multiple,touch;noise;movement,,,,babinski,,,,,,,,,,,stiffness;spasms,UE,,,generalised,,,,,,,oculomotor;cynanosis_of_affected_arm,,horizontal_nystagmus;myoclonus,,,,thyreoglobulin (GAD not performed),,,,"RF;ANA,anti-smooth_muscle",,,isolated pleocytosis,,,1,,,1,"""T2 weighted cerebral MRI showed small hypersignals of the subcortical white matter in the hemispheres""",0,,steroids,methylprednisolone 1g/d for 5d,improvement,benzo; baclofen,"Initially: diazepam 45mg/d. After progression: diazepam 75mg/d, baclofen 80mg/d",improvement,,thyroid,,,,
 MC,9496,,6,M,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,chronic_stable,,,stiffness;spasms,multiple,lumb_prox_LE;distal_LE;axial,,multiple,lumb_prox_LE;distal_LE;axial,,,,,,,,,,,,seronegative,,,,GAD;thyroid_microsomal;TG,,,,seronegative,,1,,,0,,,,none,,,benzo;baclofen,"diazepam up to 22mg/d, baclofen up to 15mg/d",improvement,,,,,,
-MC,92,3,68,,,67,1.2,,multiple,confusion;stiffness;myoclonus;numbness,,,,,,distal_LE,,,,,,,,,,,hyperreflexia;polyneuropathy,,,,,insidious,,,chronic_stable,1.3,,,multiple,lumb_prox_LE;distal_LE;axial;diaphragm,,,,,,,,,respiratory_insufficiency,,,,,,amphiphysin,,,,antineuronal,western_blot;tissue_assay,,inflammatory,,,0,,,,,1,SCLC,IVIG;steroids,IVIG and prednisone,partial improvement,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,"Initial: stiffness and myoclonus partially ameliorated by diazepam, valproate, baclofen. Established disease: Pancuronium, ventilatory support and sedation after development of respiratory distress (diaphragm stiffness)",,6 cycles of SCLC chemotherapy with cisplatin and etoposide,,paraneoplastic polyneuropathy,,,SPS and PNP in SCLC
+MC,92,3,67,,,67,1.2,,multiple,confusion;stiffness;myoclonus;numbness,,,,,,distal_LE,,,,,,,,,,,hyperreflexia;polyneuropathy,,,,,insidious,,,chronic_stable,1.3,,,multiple,lumb_prox_LE;distal_LE;axial;diaphragm,,,,,,,,,respiratory_insufficiency,,,,,,amphiphysin,,,,antineuronal,western_blot;tissue_assay,,inflammatory,,,0,,,,,1,SCLC,IVIG;steroids,IVIG and prednisone,partial improvement,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,"Initial: stiffness and myoclonus partially ameliorated by diazepam, valproate, baclofen. Established disease: Pancuronium, ventilatory support and sedation after development of respiratory distress (diaphragm stiffness)",,6 cycles of SCLC chemotherapy with cisplatin and etoposide,,paraneoplastic polyneuropathy,,,SPS and PNP in SCLC
 MC,3279,,36,M,,34,2,,multiple,cramp;stiffness,,,,,stiffness;spasms,distal_LE,,,distal_LE,,,,,,,,,,,,,,,,monophasic,0.25,,stiffness;spasms,multiple,lumb_prox_LE;distal_LE;axial,,multiple,lumb_prox_LE;distal_LE;axial,,,,,,autonomic,urine_retention;stool_retention,,,,,GAD;other,cerebellar structures,,,GAD,,,normal,,,1,,,0,,1,Hodgkin's lymphoma diagnosed 3y prior to SPSD onset. Relapse coincided with SPS manifestation.,,,,benzo;baclofen,"diazepam 30mg/d, baclofen 10mg 2x/d",improvement,Hodgkin: 3x MOPP and 3x ABVD cycles with improvement of HL and SPS,,,,,
 MC,30,1,56,F,,54,2,1,multiple,paraethesia;pain;stiffness,,Stiff_Person,,,,UE,,,,,,,,,,,paraethesia,,,,,,,,monophasic,1,,,multiple,UE;axial,,,,,,,,,,,,,,,amphiphysin,,,,"islet_cell;parietal_cell;TG,TPO;GAD",western_blot;tissue_assay,,antibody_present,amphiphysin,,1,,,,,1,invasive ductal adenocarcinoma of the breast,steroids,prednisone,improvement,benzo,diazepam,none,breast ductal adenocarcinoma: tamoxifen. Improvement of SPSD after prednisone + tamoxifen,,,,,
 MC,30,2,80,F,,76,4,2,multiple,contractures;weakness;stiffness,,Stiff_Person,,,,UE,,,,,,,,,,,,,,,,,,,chronic-progressive,24,,,multiple,UE;axial;lumb_prox_LE;distal_LE,,,,,,,,,,,,,,,amphiphysin,,,,"islet_cell;parietal_cell;TG,TPO;GAD",western_blot;tissue_assay,,normal,NA,,1,,,,,1,poorly differentiated ductal carcinoma of breast,,,,benzo;baclofen,diazepam and baclofen,NA,tamoxifen,,,,,
@@ -524,7 +524,7 @@ MC,11975,,14,F,,,,,focal_seizures,,,SPS/GAD-encephalitits,,,,,,,,,,,,,,,seizures
 MC,6010,,41,M,turkish,38,3,1,multiple,stiffness;spasms;startle,,,,,stiffness,multiple,axial;lumb_prox_LE;distal_LE,,undefined,,,noise,,,,,,,,,,,,,chronic-stable,12,,stiffness;spasms;startle,multiple,lumb_prox_LE;distal_LE;axial,,,,,,,,,seizures,,,,,,GAD,,30,U/mL,,,,,,,1,,,0,,,,IVIG;PLEX,IVIG 0.4g/kg/d for 4d: no improvement. PLEX 7x over 14d: marked improvement,improvement,benzo;clonazepam;baclofen,,none,,,,,,
 MC,6012,,67,M,,67,,,other,paraesthesia;numbness;gait_disorder,,SPS/GAD-encephalomyelitis,,,,,,,,,,,,,,,paraethesia;hypaesthesia;gait_disorder;oculomotor;hyporeflexia;ataxia,,downbeat_nystagmus,,,,,,,,,,,,,distal_LE,,,,,,,,,,,,,GAD,,1/80000,titre,GAD;Hu;Yo;Ri;Ma1/2;CV2;amphiphysin,,,inflammatory,GAD,0.597222222,1,,,0,,1,well-differentiated pancreatic endocrine neoplasm,,,,,,,,,,,,with paraneoplastic sensory PNP
 MC,2872,,65,F,african,65,,,multiple,spasms;startle;pain,,Stiff_Person,,,,,,,,,,multiple,noise;visual,,,,,,,,,,,,monophasic,,,stiffness,,,,,,,,,,,weakness;hyperhidrosis;dysphagia;decreased_esophageal_motility,,,,,,GAD,,250,IU/mL,,,,,,,,,,,,0,,IVIG,,improvement,benzo;tizanidine,IV lorazepam with improvement,improvement,,thyroid,hypothyroidism (unspecified),,,
-MC,162,,33,F,white,,,2.5,pain,,,Stiff_Person,,,stiffness,axial,,,,,,,,,,,abdominal_pain,,,,,,pancreatitis,,,28,,,multiple,lumb_prox_LE;distal_LE;axial;UE,,,,,,,,,hyporeflexia,,,,,,GAD65;microsomal,,3.513888889,titre,ANA;insulin;insulin_receptor,,,,GAD65,0.388888889,0,,,1,,,,none,,,oxycodone;nortriptyline;benzo,"oxycodone, nortriptyline: ineffective. Diazepam 10mg: dramatic improvement. Baclofen: improvement",improvement,,thyroid;diabetes,"Hashimoto, DM1",,,
+MC,162,,33,F,white,,,2.5,pain,,,Stiff_Person,,,stiffness,axial,,,,,,,,,,,abdominal_pain,,,,,,pancreatitis,,,NA,,,multiple,lumb_prox_LE;distal_LE;axial;UE,,,,,,,,,hyporeflexia,,,,,,GAD65;microsomal,,3.513888889,titre,ANA;insulin;insulin_receptor,,,,GAD65,0.388888889,0,,,1,,,,none,,,oxycodone;nortriptyline;benzo,"oxycodone, nortriptyline: ineffective. Diazepam 10mg: dramatic improvement. Baclofen: improvement",improvement,,thyroid;diabetes,"Hashimoto, DM1",,,
 MC,712,,43,F,E_asia,43,0.5,0.5,spasms,,,Stiff_Person,,,,,,,,,,noise,,,,,dysphoria,,,,,,,panic disorder,chronic-stable,18,,stiffness;spasms;startle,,axial,,,,,,,,,anxiety;oculomotor,,saccadic_intrusions,,,,GAD65,,230,U/mL,ANA;dsDNA;cardiolipin;GAD,,,,,,1,1,,0,,,,steroids,methylprednisolone iv 1g/d for 3d,improvement,benzo;baclofen,"alprazolam 0.25mg 3x/d, baclofen 10mg: moderate improvement",improvement,,,,,,
 MC,6021,,43,F,,43,,,,,,paraneoplastic_SPS,,,,,,,,,,,,,,,,,,,,,,,,,,stiffness;spasms;startle,multiple,lumb_prox_LE;distal_LE;axial;UE,,unspecified,,,,,,,hyperreflexia;clonus;hyperhidrosis;autonomic;depression;anxiety,urinary_retention;constipation,,,,,Ri;ANA,,,,GAD;amphiphysin;Ri;ANA,,,,,,1,,,,,1,breast cancer metastases detected upon screening after SPS diagnosis; first diagnosis of breast cancer 13y prior to SPS onset,unspecified,,improvement,unspecified,,improvement,tumour chemotherapy with remission of breast cancer and improvement of neurological symptoms,,,,,
 MC,12412,,39,F,,30,,9,multiple,stiffness;spasms,,Stiff_Limb,,,stiffness;spasms,multiple,lumb_prox_LE;distal_LE,,,,,multiple,somatosensory;emotional,,,,gait_disorder,,,,,,,,,,84,stiffness;spasms;startle,other,left_leg,,,,,,,,,,,,,,,GAD,,1164,U/mL,GAD,,,antibody_present,GAD65,,1,,,0,,,,none,,,benzo,"diazepam 12mg/d: improvement, but sedation as adverse effect. Gabapentin 1200 - 2400 mg/d improvement, reduction of diazepam possible; stability of symptoms achieved for 7 years.",improvement,,thyroid,hypothyroidism (unspecified),,,long term symptomatic treatment of stiff limb
@@ -561,7 +561,7 @@ MC,621,,58,F,E_asia,46,12,10,other,ataxia,,other,SPS_with_ataxia,,,none,,,none,,
 MC,537,,29,M,africa,29,,,other,dyspnoea,,paraneoplastic_SPS,,,,,,,,,,,,,,,dyspnoea,,,,,,,,monophasic,,,stiffness;spasms,multiple,distal_LE;lumb_prox_LE;axial,,multiple,distal_LE;lumb_prox_LE,,,,,,pain;weakness,,,,,,GAD,,,,GAD;AChR,,,,,,,,,,,1,thymoma invasive lymphocytic predominant epithelial type,,,,benzo;morphine,diazepam 5mg iv and morphine with complete resolution of neurological symptoms,improvement,resection and chemotherapy of thymoma with complete resolution of neurological symptoms,,,,,
 MC,5631,,54,F,,52,,2,multiple,stiffness;gait_disorder,,Stiff_Person,,,,axial,,,,,,,,,,,gait_disorder,,,,,,,,RR,24,12,stiffness;spasms,generalised,,,multiple,distal_LE;lumb_prox_LE;axial,,,,,,hyperreflexia;autonomic,urinary_retention;tachycardia;hypertension,,,,,GAD,,,,,,,,,,1,,,,,,,unspecified,,improvement,benzo;baclofen,diazepam and baclofen: improvement,improvement,,thyroid,unspecified,,,superimposed attacks of intense muscle spasms following acute gastroenteritis
 MC,650,,55,F,,54,,,multiple,psychiatric;spasms,,paraneoplastic_SPS,,,psychiatric;spasms,,,,multiple,distal_LE;lumb_prox_LE,,,,,,,panic_attacks;visual_hallucinations;seizures,,,cacosmia;tonic-clonic,,,,,monophasic,2,,stiffness;spasms,multiple,distal_LE;lumb_prox_LE,,multiple,distal_LE;lumb_prox_LE,,multiple,touch;movement,,,hyporeflexia,,,,,,amphiphysin,,,,amphiphysin;GAD;Hu;R;Ma2;Yo;CV2;VGKC;ANNA-3,,,high_cell_count;antibody_present,,,,,,1,T2 hyperintensity in the left temporal lobe with enhancement after gadolinium administration on T1-weighted images. Brain MRI at 1-year follow-up post cancer therapy showed partial resolution of the temporal lobe abnormality and enhancement,1,metastatic ductal breast cancer,,,,benzo;baclofen;levetiracetam,"She was maintained on low doses of baclofen and diazepam to treat minor persistent symptoms of stiffness in the lower extremities. Leviteracetam (for seizures) was successfully tapered several weeks after her treatment, and she had no further episodic affective or sensory symptoms.",improvement,"chemotherapy, radiotherapy of breast cancer with dramatic improvement of stiffness and spasms and recovery of tendon reflexes. ",,,,,
-MC,75,,39,F,africa,38,0,1,spasms,,,,,,,,,,multiple,axial;right_leg,,,,,,,pain;vomiting,,,,,,,,,12,,,,,,axial,,,multiple,noise;tactile;speaking,,,,,,,,,GAD,,,,,,,,GAD,,1,,,,,,,,,,benzo;other,diazepam 5mg and chlorzoxazone 500mg qid with improvement,improvement,,gastric,atrophic gastritis with vitamin B12 deficiency,,,
+MC,75,,39,F,africa,38,0,1,spasms,,,,,,,,,,multiple,axial;right_leg,,,,,,,pain;vomiting,,,,,,,,,12,,,,,,axial,,,multiple,tactile;speaking,,,,,,,,,GAD,,,,,,,,GAD,,1,,,,,,,,,,benzo;other,diazepam 5mg and chlorzoxazone 500mg qid with improvement,improvement,,gastric,atrophic gastritis with vitamin B12 deficiency,,,
 MC,1327,,8,M,,8,,,spasms,,,Stiff_Person,,,,,,,right_leg,,,,,,,,,,,,,,,,,1.5,1,spasms,generalised,,,multiple,distal_LE;lumb_prox_LE;axial;UE,,,,,,myocloni;pain,,,,,,GAD65,,,,GAD;NMDAR,,,antibody_present,GAD65,,,1,,0,,,,steroids;IVIG;RXB,"Methylprednisolone intravenous (IV) for 5 days: no improvement. IVIG for 5 d: no improvement. IV rituximab 375 mgm/m2/week, After the second dose of rituximab, myoclonus decreased significantly. Total 4x Rituximab.",improvement,clonazepam;valproate,"clonazepam, valproate: initially no improvement.",none,,none,,,,
 MC,680,,39,M,SE_asia,39,,,multiple,spasms;trismus,,PERM,,,,trismus,,,other,masseter,,,,,,,,,,,,,other,tetanus;dystonia,RR,0.06,,,trismus,,,multiple,masseter;right_leg,,,,,,facial_weakness;dysarthria;dysphagia;myocloni;fasciculations;ptosis,,,,,,GlyR,,,,GlyR;Yo;Hu;Ri;amphiphysin;Ma2;CRMP5;GAD;NMDAR,,,,,,1,,,1,"high FLAIR in subcortical, deep and periventricular white matter of the cerebral hemispheres bilaterally",1,SCLC,IVIG;methylprednisolone;PLEX;RXB,"IVIG during 1st phase: improvement. After relapse, IVIG, 5d 500mg methylprednisolone, 5d PLEX: no effect. Rituximab: dramatic and sustained improvement.",improvement,trihexyphenidyl;levodopa;dantrolene;clonazepam,"trihexyphenidyl, levodopa: slight improvement of trismus. Dantrolene: transient improvement. Clonazepam: improvement",improvement,"chemotherapy, radiotherapy of SCLC with improvement of SCLC and neurological symptoms",,,,,
 MC,5647,,44,F,white,44,6,,multiple,spasms;diplopia,,Stiff_Person,,,,,,,multiple,distal_LE;lumb_prox_LE,,,,,,,oculomotor,,diplopia,,,,,,,1,6,spasms,multiple,distal_LE;lumb_prox_LE,,multiple,distal_LE;lumb_prox_LE,,,,,,hyperreflexia;oculomotor,,ophthalmoplegia,,,,GAD,,,,,,,,,,,,,,,1,invisive mixed-type thymoma,steroids,iv methylprednisolone: no improvement. PLEX followed by IVIG: notable improvement of stiffness and ophthalmoplegia,,,,improvement,resection and radiotherapy of thymoma,,,,,
@@ -663,7 +663,7 @@ MC,488,5,72,F,,72,,,,,,Stiff_Person,,,,,,,,,,,,,,,,,,,,,,,,,,,,1,,,,,,4,,,,,,,,,
 MC,1273,,65,F,,49,3,,stiffness;spasms,,,Stiff_Person,,,stiffness;spasms,lumb_prox_LE,,,lumb_prox_LE,,,,,,,,hyperhidrosis;tachycardia,,,,,insidious,functional;epileptic,,chronic_progressive,144,,stiffness;spasms,generalised,,,generalised,,,touch,,,,hyperhidrosis;tachycardia;babinski,,,,4,,amphiphysin;other,CV2;Ma2 (low positivity),Jan-50,titre,GAD;Ri;CV2;Ma2;amphiphysin,,,OCB,,,1,1,,0,,0,,,,,pregabalin;other,"Pregabalin 150mg 2x/d: marked improvement. Prior treatment with buxamine/phenobarbital/phenitoine at a dosage of 500/100/100 mg/day, clonazepam at a daily dose of 6 mg, diazepam at a dose of 15 mg/day, levetiracetam up to 3000 mg/day, valproate at a dose of 1000 mg/day and lacosamide up to 200 mg/day, without improvement.",improvement,,thyroid;diabetes,"Graves disease, DM1",,,
 MC,9385,,50,M,S_asia,46,1,8,pain,,,Stiff_Person,Lorish et al,,stiffness;spasms,multiple,distal_LE;lumb_prox_LE;UE,,lumb_prox_LE,,,,,,,,,,,,,insidious,,,chronic_progressive,60,,stiffness;spasms,generalised,,,multiple,axial;lumb_prox_LE;distal_LE;UE,,,,,,,,,,,,,,,,,,,,,,1,,,,,,,,,,baclofen;benzo,diazepam 15mg 3x/d: marked improvement,improvement,,,,,,
 MC,455,,55,F,white,,,,,,,Stiff_Person,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,GAD,,,,,,,,,,,,,,,,,steroids;IVIG,,NA,,,,,other,scleritis,,,
-MC,395,,59,F,E_asia,57,,,stiffness,,,Stiff_Person,,,stiffness,UE,,,,,,,,,,,,,,,,insidious,,,monophasic,2,,stiffness;spasms,multiple,distal_LE;lumb_prox_LE;axial;UE,,unspecified,,,touch,,,,ptosis;dysphagia,,,,,both,GAD,,16800,U/ml,GAD;AChR,,,,,,,1,,,,1,"thymoma, lymphocytic type, WHO B1",IVIG,,,baclofen;benzo,"baclofen, diazepam",,,,,,,
+MC,395,,57,F,E_asia,57,,,stiffness,,,Stiff_Person,,,stiffness,UE,,,,,,,,,,,,,,,,insidious,,,monophasic,2,,stiffness;spasms,multiple,distal_LE;lumb_prox_LE;axial;UE,,unspecified,,,touch,,,,ptosis;dysphagia,,,,,both,GAD,,16800,U/ml,GAD;AChR,,,,,,,1,,,,1,"thymoma, lymphocytic type, WHO B1",IVIG,,,baclofen;benzo,"baclofen, diazepam",,,,,,,
 MC,6278,,46,F,,,46,,other,burning;itching,,paraneoplastic_SPS,,,dysaesthesia,,,,,,,,,,,,,,,,,insidious,SPSD,,,5,,stiffness,axial,,,,,,,,,,,,,,,,amphiphysin,,,,,,,,,,,,,0,,1,metastatic breast cancer,,,,,,,,,,,,
 MC,6690,1,42,F,,,,,,,,paraneoplastic_SPS,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,GAD,,,,,,,,,,,,,,,1,breast adenocarcinoma,,,,,,,,,,,,
 MC,6690,2,47,F,,,,,,,,paraneoplastic_SPS,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,GAD,,,,,,,,,,,,,,,1,lung adenocarcinoma,,,,,,,,,,,,
diff --git a/src/pipelines/09_build_langextract_examples.py b/src/pipelines/09_build_langextract_examples.py
index 815dcea..4793e72 100644
--- a/src/pipelines/09_build_langextract_examples.py
+++ b/src/pipelines/09_build_langextract_examples.py
@@ -1,326 +1,1311 @@
 from __future__ import annotations
 
+import argparse
 import csv
+import hashlib
 import json
+import os
+import sys
+import time
+from dataclasses import asdict, dataclass
+from datetime import datetime, timezone
 from pathlib import Path
+from typing import Any
 
 
 REPO_ROOT = Path(__file__).resolve().parents[2]
-EXAMPLES_DIR = REPO_ROOT / "examples"
-PROMPT_EXAMPLES_DIR = REPO_ROOT / "config" / "prompts" / "examples"
-CASE_REPORT_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Case_Report_Form.csv"
-CASE_SERIES_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Case_Series_Reports.csv"
-COHORTS_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Cohorts.csv"
-OBS_COHORT_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Observ_Cohort_Cross_sect.csv"
-INDIVIDUAL_OUT = PROMPT_EXAMPLES_DIR / "02_individual_examples.json"
-GROUP_OUT = PROMPT_EXAMPLES_DIR / "02_group_examples.json"
-PUBLICATION_TYPE_OUT = PROMPT_EXAMPLES_DIR / "03_publication_type_examples.json"
-
-
-# Build dedupe headers.
-def dedupe_headers(headers: list[str]) -> list[str]:
-    counts: dict[str, int] = {}
-    deduped: list[str] = []
-    for header in headers:
-        clean = header.strip()
-        counts[clean] = counts.get(clean, 0) + 1
-        deduped.append(clean if counts[clean] == 1 else f"{clean}__{counts[clean]}")
-    return deduped
-
-
-# Load case report rows.
-def load_case_report_rows(path: Path) -> set[tuple[str, str]]:
-    with path.open(encoding="utf-8", newline="") as handle:
-        reader = csv.reader(handle)
-        headers = dedupe_headers(next(reader))
-        keys: set[tuple[str, str]] = set()
-        for row_values in reader:
-            if not row_values:
-                continue
-            row = {
-                headers[index]: row_values[index] if index < len(row_values) else ""
-                for index in range(len(headers))
-            }
-            reference_id = (row.get("Reference") or "").strip()
-            case_id = (row.get("case_ID") or "").strip()
-            if reference_id:
-                keys.add((reference_id, case_id))
-        return keys
+INDEX_PATH = REPO_ROOT / "resources" / "stage07_single_case_gold_json_index.csv"
+MC_CASE_REPORT_PATH = REPO_ROOT / "examples" / "datasheet_examples_MC_Case_Report_Form.csv"
+DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "validation" / "langextract_example_bootstrap"
+DEFAULT_EXAMPLES_OUT_DIR = REPO_ROOT / "examples" / "langextract_bootstrap"
+DEFAULT_GEMINI_ENV_FILE = REPO_ROOT / "env" / "gemini.env"
+DEFAULT_OPENAI_ENV_FILE = REPO_ROOT / "env" / "openai_api_key.env"
+DEFAULT_SPAN_PLAN_PATH = DEFAULT_OUTPUT_ROOT / "pilot_10" / "gold_source_span_plan.csv"
+DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
+DEFAULT_OPENAI_MODEL = "gpt-5.5"
+DEFAULT_OPENAI_REASONING_EFFORT = "low"
+DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 8000
+SOURCE_SHEET_NAME = "datasheet_examples_MC_Case_Report_Form.csv"
 
+PROVENANCE_FIELDS = {"extractor", "Reference", "case_ID"}
+EVIDENCE_MODES = {"exact_quote", "inferred_from_text", "not_found"}
 
-# Load sheet IDs.
-def load_sheet_ids(path: Path, key: str) -> set[str]:
-    with path.open(encoding="utf-8", newline="") as handle:
-        reader = csv.DictReader(handle)
-        return {(row.get(key) or "").strip() for row in reader if (row.get(key) or "").strip()}
+REVIEW_FIELDNAMES = [
+    "paper_id",
+    "case_id",
+    "field_name",
+    "spreadsheet_value",
+    "model_spreadsheet_value",
+    "evidence_mode",
+    "extraction_text",
+    "char_start",
+    "char_end",
+    "supporting_snippets_json",
+    "supports_manual_value",
+    "reasoning_short",
+    "validator_status",
+    "review_status",
+    "review_notes",
+    "target_view_json_path",
+]
 
 
-# Validate individual sources.
-def validate_individual_sources(payload: list[dict[str, object]], case_rows: set[tuple[str, str]]) -> None:
-    missing: list[str] = []
-    for item in payload:
-        paper_id = str(item.get("paper_id") or "").strip()
-        case_id = str(item.get("case_id") or "").strip()
-        if (paper_id, case_id) not in case_rows:
-            missing.append(f"{paper_id}:{case_id or '<blank>'}")
-    if missing:
-        raise ValueError(f"Missing individual example rows in curated case-report sheet: {', '.join(missing)}")
-
-
-# Validate sheet sources.
-def validate_sheet_sources(payload: list[dict[str, object]], valid_ids: set[str], label: str) -> None:
-    missing = [
-        str(item.get("paper_id") or "").strip()
-        for item in payload
-        if str(item.get("paper_id") or "").strip() not in valid_ids
-    ]
-    if missing:
-        raise ValueError(f"Missing {label} example IDs in curated sheet: {', '.join(missing)}")
+@dataclass(frozen=True)
+class PilotRecord:
+    paper_id: str
+    case_id: str
+    target_view_json_path: Path
+    source_text: str
+    manual_fields: dict[str, str]
+
+
+@dataclass(frozen=True)
+class FieldGrounding:
+    field_name: str
+    spreadsheet_value: str
+    evidence_mode: str
+    extraction_text: str
+    supporting_snippets: list[str]
+    reasoning_short: str
+    supports_manual_value: bool
+
+
+@dataclass(frozen=True)
+class BootstrappedCaseExample:
+    paper_id: str
+    case_id: str
+    model_id: str
+    field_groundings: list[FieldGrounding]
+
+
+def now_utc_iso() -> str:
+    return datetime.now(timezone.utc).isoformat()
+
+
+def repo_path(path_text: str) -> Path:
+    normalised = path_text.replace("\\", "/")
+    path = Path(normalised)
+    if path.is_absolute():
+        return path
+    return REPO_ROOT / path
+
 
+def repo_rel(path: Path) -> str:
+    try:
+        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
+    except ValueError:
+        return str(path)
 
-# Write JSON.
-def write_json(path: Path, payload: list[dict[str, object]]) -> None:
+
+def sha256_text(text: str) -> str:
+    return hashlib.sha256(text.encode("utf-8")).hexdigest()
+
+
+def read_csv_rows(path: Path) -> list[dict[str, str]]:
+    with path.open(encoding="utf-8-sig", newline="") as handle:
+        return list(csv.DictReader(handle))
+
+
+def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
+    path.parent.mkdir(parents=True, exist_ok=True)
+    with path.open("w", encoding="utf-8", newline="") as handle:
+        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
+        writer.writeheader()
+        writer.writerows(rows)
+
+
+def write_csv_rows_atomic(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
+    tmp_path = path.with_name(f"{path.name}.tmp")
+    write_csv_rows(tmp_path, rows, fieldnames)
+    tmp_path.replace(path)
+
+
+def write_json(path: Path, payload: Any) -> None:
     path.parent.mkdir(parents=True, exist_ok=True)
     path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
 
 
-# Build individual examples.
-def individual_examples() -> list[dict[str, object]]:
-    return [
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "12013",
-            "case_id": "",
-            "text": "A 43-year-old white woman developed insidious generalized stiffness at age 40. Painful generalized spasms, sensory symptoms, pain, and fatigue followed, and she was initially labelled as having Parkinson disease. Anti-GAD antibodies were detected. She was treated with IVIG together with benzodiazepines, gabapentin, and physiotherapy. The report did not state the treatment response.",
-            "extractions": [
-                {"extraction_class": "individual_presentation", "extraction_text": "insidious generalized stiffness, painful generalized spasms, sensory symptoms, pain, and fatigue"},
-                {"extraction_class": "individual_diagnostics", "extraction_text": "she was initially labelled as having Parkinson disease. Anti-GAD antibodies were detected"},
-                {"extraction_class": "individual_treatment", "extraction_text": "treated with IVIG together with benzodiazepines, gabapentin, and physiotherapy"},
-                {"extraction_class": "individual_limitations", "extraction_text": "The report did not state the treatment response"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "2846",
-            "case_id": "1",
-            "text": "A 40-year-old woman presented with abdominal spasms and exaggerated startle and was initially thought to have complex partial seizures. Diagnostic criteria included axial muscle stiffness, painful spasms, EMG confirmation of continuous paraspinal muscle activity, and anti-GAD antibodies in blood or CSF. Her anti-GAD titre was greater than 30 IU/mL, and CSF testing was not done. She received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines, baclofen, and propofol for symptomatic control. She was reported as a responder.",
-            "extractions": [
-                {"extraction_class": "individual_presentation", "extraction_text": "abdominal spasms and exaggerated startle"},
-                {"extraction_class": "individual_diagnostics", "extraction_text": "initially thought to have complex partial seizures; EMG confirmation of continuous paraspinal muscle activity; anti-GAD titre was greater than 30 IU/mL; CSF testing was not done"},
-                {"extraction_class": "individual_treatment", "extraction_text": "received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines, baclofen, and propofol for symptomatic control"},
-                {"extraction_class": "individual_outcome", "extraction_text": "She was reported as a responder"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "2846",
-            "case_id": "2",
-            "text": "A 57-year-old woman presented with spasms and startle and was initially considered to have cerebellar ataxia or spinocerebellar ataxia. Anti-GAD antibodies were present and CSF antibodies were also detected. She was treated with IVIG, plasma exchange, and autologous hematopoietic stem-cell transplantation, with benzodiazepines and baclofen as symptomatic treatment. She was reported as a partial responder.",
-            "extractions": [
-                {"extraction_class": "individual_presentation", "extraction_text": "spasms and startle"},
-                {"extraction_class": "individual_diagnostics", "extraction_text": "initially considered to have cerebellar ataxia or spinocerebellar ataxia. Anti-GAD antibodies were present and CSF antibodies were also detected"},
-                {"extraction_class": "individual_treatment", "extraction_text": "treated with IVIG, plasma exchange, and autologous hematopoietic stem-cell transplantation, with benzodiazepines and baclofen as symptomatic treatment"},
-                {"extraction_class": "individual_outcome", "extraction_text": "She was reported as a partial responder"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "2846",
-            "case_id": "3",
-            "text": "A 27-year-old woman presented with spasms and startle and was initially diagnosed as CIDP/AAG. Anti-GAD antibodies were present, but CSF was normal. She received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines for symptom control. She had no reported response.",
-            "extractions": [
-                {"extraction_class": "individual_presentation", "extraction_text": "spasms and startle"},
-                {"extraction_class": "individual_diagnostics", "extraction_text": "initially diagnosed as CIDP/AAG. Anti-GAD antibodies were present, but CSF was normal"},
-                {"extraction_class": "individual_treatment", "extraction_text": "received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines for symptom control"},
-                {"extraction_class": "individual_outcome", "extraction_text": "She had no reported response"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "2472",
-            "case_id": "",
-            "text": "A 25-year-old woman presented with gait difficulty, weakness, and pain, together with numbness, autonomic symptoms, hyperhidrosis, and tachycardia. She had generalized stiffness and spasms. Anti-GAD and amphiphysin antibodies were reported, with a GAD titre of 253 nmol/L. She was treated with IVIG, benzodiazepines, and baclofen, and she improved.",
-            "extractions": [
-                {"extraction_class": "individual_presentation", "extraction_text": "gait difficulty, weakness, pain, numbness, autonomic symptoms, hyperhidrosis, tachycardia, generalized stiffness, and spasms"},
-                {"extraction_class": "individual_diagnostics", "extraction_text": "Anti-GAD and amphiphysin antibodies were reported, with a GAD titre of 253 nmol/L"},
-                {"extraction_class": "individual_treatment", "extraction_text": "treated with IVIG, benzodiazepines, and baclofen"},
-                {"extraction_class": "individual_outcome", "extraction_text": "she improved"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "552",
-            "case_id": "",
-            "text": "A 49-year-old man had multiple painful stiffness and spasm symptoms involving the upper and lower extremities. He was anti-GAD positive with a titre of 609 nmol/L. MRI was reported as normal. He received IVIG together with symptomatic therapy, and the paper noted that repeated IVIG infusions were required.",
-            "extractions": [
-                {"extraction_class": "individual_presentation", "extraction_text": "multiple painful stiffness and spasm symptoms involving the upper and lower extremities"},
-                {"extraction_class": "individual_diagnostics", "extraction_text": "anti-GAD positive with a titre of 609 nmol/L. MRI was reported as normal"},
-                {"extraction_class": "individual_treatment", "extraction_text": "received IVIG together with symptomatic therapy"},
-                {"extraction_class": "individual_outcome", "extraction_text": "repeated IVIG infusions were required"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "11957",
-            "case_id": "",
-            "text": "A 46-year-old woman developed stiffness and spasms from age 40 onward. Anti-GAD antibodies were present, and breast cancer was diagnosed 6 years after syndrome onset. She was treated with azathioprine and diazepam, and had previously received monthly IVIG for 1.5 years. The case summary did not clearly state the later treatment response.",
-            "extractions": [
-                {"extraction_class": "individual_presentation", "extraction_text": "stiffness and spasms from age 40 onward"},
-                {"extraction_class": "individual_diagnostics", "extraction_text": "Anti-GAD antibodies were present, and breast cancer was diagnosed 6 years after syndrome onset"},
-                {"extraction_class": "individual_treatment", "extraction_text": "treated with azathioprine and diazepam, and had previously received monthly IVIG for 1.5 years"},
-                {"extraction_class": "individual_limitations", "extraction_text": "The case summary did not clearly state the later treatment response"},
-            ],
+def write_json_atomic(path: Path, payload: Any) -> None:
+    tmp_path = path.with_name(f"{path.name}.tmp")
+    write_json(tmp_path, payload)
+    tmp_path.replace(path)
+
+
+def load_stage07_text(path: Path) -> str:
+    payload = json.loads(path.read_text(encoding="utf-8"))
+    text = (payload.get("input_text") or payload.get("text") or "").strip()
+    if not text:
+        raise ValueError(f"No Stage 07 input text found in {path}")
+    return text
+
+
+def manual_fields_from_row(row: dict[str, str]) -> dict[str, str]:
+    fields: dict[str, str] = {}
+    for key, value in row.items():
+        clean_key = (key or "").strip()
+        clean_value = (value or "").strip()
+        if not clean_key or not clean_value:
+            continue
+        if clean_key in PROVENANCE_FIELDS:
+            continue
+        fields[clean_key] = clean_value
+    return fields
+
+
+def manual_rows_by_reference(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
+    by_id: dict[str, list[dict[str, str]]] = {}
+    for row in rows:
+        paper_id = (row.get("Reference") or "").strip()
+        if paper_id:
+            by_id.setdefault(paper_id, []).append(row)
+    return by_id
+
+
+def select_pilot_records(
+    *,
+    limit: int,
+    explicit_ids: list[str],
+    excluded_ids: list[str] | None = None,
+    index_path: Path | None = None,
+    manual_path: Path | None = None,
+) -> list[PilotRecord]:
+    index_rows = read_csv_rows(index_path or INDEX_PATH)
+    manual_by_id = manual_rows_by_reference(read_csv_rows(manual_path or MC_CASE_REPORT_PATH))
+    wanted = {paper_id.strip() for paper_id in explicit_ids if paper_id.strip()}
+    excluded = {paper_id.strip() for paper_id in (excluded_ids or []) if paper_id.strip()}
+    selected: list[PilotRecord] = []
+
+    for index_row in index_rows:
+        paper_id = (index_row.get("paper_id") or "").strip()
+        if not paper_id:
+            continue
+        if paper_id in excluded:
+            continue
+        if (index_row.get("manually_reviewed_MC") or "").strip() != "TRUE":
+            continue
+        if wanted and paper_id not in wanted:
+            continue
+        target_view_path = repo_path(index_row.get("stage07_target_view_json_path", ""))
+        source_text = load_stage07_text(target_view_path)
+
+        for manual_row in manual_by_id.get(paper_id, []):
+            manual_fields = manual_fields_from_row(manual_row)
+            if not manual_fields:
+                continue
+            selected.append(
+                PilotRecord(
+                    paper_id=paper_id,
+                    case_id=(manual_row.get("case_ID") or "").strip(),
+                    target_view_json_path=target_view_path,
+                    source_text=source_text,
+                    manual_fields=manual_fields,
+                )
+            )
+            if not wanted and limit > 0 and len(selected) >= limit:
+                return selected
+    return selected
+
+
+def build_bootstrap_prompt(record: PilotRecord) -> str:
+    manual_payload = json.dumps(record.manual_fields, ensure_ascii=False, indent=2)
+    return f"""
+You are building grounded examples for an information extraction system.
+
+You will receive:
+1. Source text from one reviewed single-case SPSD paper.
+2. A dictionary of manually extracted gold-standard spreadsheet fields.
+
+For every provided field:
+- Return exactly one field_groundings item.
+- Preserve field_name exactly.
+- Preserve spreadsheet_value exactly.
+- If the value is directly quoteable, set evidence_mode to exact_quote and put
+  the shortest verbatim supporting source phrase or sentence in extraction_text.
+- If the value requires clinical inference from the text, set evidence_mode to
+  inferred_from_text and provide one or more verbatim supporting snippets.
+- If the value cannot be supported from the supplied text, set evidence_mode to
+  not_found, set supports_manual_value to false, and leave extraction_text empty.
+- Do not invent evidence.
+- Do not use outside knowledge.
+- Do not change the manual value.
+
+Paper ID: {record.paper_id}
+Case ID: {record.case_id}
+
+Manual gold fields:
+{manual_payload}
+
+Source text:
+\"\"\"
+{record.source_text}
+\"\"\"
+""".strip()
+
+
+def load_env_file(path: Path) -> None:
+    if not path.exists():
+        return
+    for line in path.read_text(encoding="utf-8").splitlines():
+        stripped = line.strip()
+        if not stripped or stripped.startswith("#") or "=" not in stripped:
+            continue
+        key, value = stripped.split("=", 1)
+        os.environ.setdefault(key.strip(), value.strip())
+
+
+def require_paid_run_approval(allow_paid_run: bool) -> None:
+    if not allow_paid_run:
+        raise SystemExit("Refusing to call a paid LLM API without --allow-paid-run.")
+
+
+def response_schema_class() -> type[Any]:
+    try:
+        from pydantic import BaseModel, ConfigDict, Field
+    except ImportError as exc:
+        raise SystemExit("pydantic is required for paid response schema validation.") from exc
+
+    class ModelFieldGrounding(BaseModel):
+        model_config = ConfigDict(extra="forbid")
+
+        field_name: str = Field(description="Manual spreadsheet column name.")
+        spreadsheet_value: str = Field(description="Exact non-empty value from the manual row.")
+        evidence_mode: str = Field(description="exact_quote, inferred_from_text, or not_found.")
+        extraction_text: str = Field(description="Verbatim supporting text, or empty if not found.")
+        supporting_snippets: list[str] = Field(description="Verbatim source snippets supporting inferred values.")
+        reasoning_short: str = Field(description="Brief reviewer-facing explanation.")
+        supports_manual_value: bool
+
+    class ModelBootstrappedCaseExample(BaseModel):
+        model_config = ConfigDict(extra="forbid")
+
+        paper_id: str
+        case_id: str
+        model_id: str
+        field_groundings: list[ModelFieldGrounding]
+
+    return ModelBootstrappedCaseExample
+
+
+def parse_model_payload(payload: dict[str, Any], *, paper_id: str, case_id: str, model_id: str) -> BootstrappedCaseExample:
+    groundings: list[FieldGrounding] = []
+    for item in payload.get("field_groundings") or []:
+        if not isinstance(item, dict):
+            continue
+        snippets = item.get("supporting_snippets") or []
+        if not isinstance(snippets, list):
+            snippets = []
+        groundings.append(
+            FieldGrounding(
+                field_name=str(item.get("field_name") or "").strip(),
+                spreadsheet_value=str(item.get("spreadsheet_value") or "").strip(),
+                evidence_mode=str(item.get("evidence_mode") or "").strip(),
+                extraction_text=str(item.get("extraction_text") or "").strip(),
+                supporting_snippets=[str(snippet).strip() for snippet in snippets if str(snippet).strip()],
+                reasoning_short=str(item.get("reasoning_short") or "").strip(),
+                supports_manual_value=parse_bool(item.get("supports_manual_value")),
+            )
+        )
+    return BootstrappedCaseExample(
+        paper_id=paper_id,
+        case_id=case_id,
+        model_id=model_id,
+        field_groundings=groundings,
+    )
+
+
+def parse_bool(value: Any) -> bool:
+    if isinstance(value, bool):
+        return value
+    if isinstance(value, str):
+        return value.strip().lower() in {"1", "true", "yes"}
+    return bool(value)
+
+
+def run_gemini_bootstrap(
+    record: PilotRecord,
+    *,
+    model_id: str,
+    allow_paid_run: bool,
+    env_file: Path,
+) -> BootstrappedCaseExample:
+    require_paid_run_approval(allow_paid_run)
+    load_env_file(env_file)
+    api_key = os.getenv("GEMINI_API_KEY")
+    if not api_key:
+        raise SystemExit("GEMINI_API_KEY is not set.")
+
+    try:
+        from google import genai
+        from google.genai import types
+    except ImportError as exc:
+        raise SystemExit("google-genai is required for paid Gemini bootstrapping.") from exc
+
+    prompt = build_bootstrap_prompt(record)
+    client = genai.Client(api_key=api_key)
+    response = client.models.generate_content(
+        model=model_id,
+        contents=prompt,
+        config=types.GenerateContentConfig(
+            response_mime_type="application/json",
+            response_schema=response_schema_class(),
+            temperature=0.0,
+        ),
+    )
+    parsed_text = response.text or "{}"
+    return parse_model_payload(
+        json.loads(parsed_text),
+        paper_id=record.paper_id,
+        case_id=record.case_id,
+        model_id=model_id,
+    )
+
+
+def run_openai_bootstrap(
+    record: PilotRecord,
+    *,
+    model_id: str,
+    allow_paid_run: bool,
+    env_file: Path,
+    reasoning_effort: str,
+    max_output_tokens: int,
+) -> BootstrappedCaseExample:
+    require_paid_run_approval(allow_paid_run)
+    load_env_file(env_file)
+    api_key = os.getenv("OPENAI_API_KEY")
+    if not api_key:
+        raise SystemExit(f"OPENAI_API_KEY is not set. Checked environment and {repo_rel(env_file)}.")
+
+    try:
+        from openai import OpenAI
+    except ImportError as exc:
+        raise SystemExit("openai is required for paid OpenAI bootstrapping.") from exc
+
+    schema = response_schema_class()
+    prompt = build_bootstrap_prompt(record)
+    client = OpenAI(api_key=api_key)
+    response = client.responses.create(
+        model=model_id,
+        store=False,
+        input=[
+            {
+                "role": "system",
+                "content": (
+                    "You are a systematic-review extraction auditor. Return only JSON that "
+                    "matches the supplied schema. Ground every non-empty manual value in the "
+                    "provided source text, and mark unsupported values as not_found."
+                ),
+            },
+            {"role": "user", "content": prompt},
+        ],
+        reasoning={"effort": reasoning_effort},
+        text={
+            "format": {
+                "type": "json_schema",
+                "name": "langextract_bootstrap_case_example",
+                "schema": schema.model_json_schema(),
+                "strict": True,
+            },
+            "verbosity": "low",
         },
+        max_output_tokens=max_output_tokens,
+    )
+
+    if getattr(response, "status", "") == "incomplete":
+        details = getattr(response, "incomplete_details", None)
+        reason = getattr(details, "reason", "") if details is not None else ""
+        raise RuntimeError(
+            f"OpenAI response was incomplete for paper {record.paper_id}; "
+            f"reason={reason or 'unknown'} max_output_tokens={max_output_tokens}"
+        )
+    output_text = getattr(response, "output_text", "")
+    if not output_text.strip():
+        raise RuntimeError(f"OpenAI response did not contain output_text for paper {record.paper_id}.")
+    parsed = schema.model_validate_json(output_text)
+    actual_model_id = str(getattr(response, "model", "") or model_id)
+    return parse_model_payload(
+        parsed.model_dump(mode="json"),
+        paper_id=record.paper_id,
+        case_id=record.case_id,
+        model_id=actual_model_id,
+    )
+
+
+def retryable_gemini_error(exc: Exception) -> bool:
+    message = str(exc)
+    retryable_terms = (
+        "503 UNAVAILABLE",
+        "temporarily unavailable",
+        "high demand",
+        "try again later",
+    )
+    return any(term.lower() in message.lower() for term in retryable_terms)
+
+
+def retryable_openai_error(exc: Exception) -> bool:
+    message = str(exc).lower()
+    if any(term in message for term in ("insufficient_quota", "billing", "prepayment", "invalid_api_key")):
+        return False
+    status_code = getattr(exc, "status_code", None)
+    if status_code in {408, 409, 429, 500, 502, 503, 504}:
+        return True
+    retryable_terms = (
+        "temporarily unavailable",
+        "rate limit",
+        "timeout",
+        "timed out",
+        "server error",
+        "connection",
+    )
+    return any(term in message for term in retryable_terms)
+
+
+def retryable_provider_error(exc: Exception, provider: str) -> bool:
+    if provider == "openai":
+        return retryable_openai_error(exc)
+    return retryable_gemini_error(exc)
+
+
+def run_bootstrap(
+    record: PilotRecord,
+    *,
+    args: argparse.Namespace,
+) -> BootstrappedCaseExample:
+    if args.provider == "openai":
+        return run_openai_bootstrap(
+            record,
+            model_id=args.model_id,
+            allow_paid_run=args.allow_paid_run,
+            env_file=args.openai_env_file,
+            reasoning_effort=args.openai_reasoning_effort,
+            max_output_tokens=args.openai_max_output_tokens,
+        )
+    if args.provider == "gemini":
+        return run_gemini_bootstrap(
+            record,
+            model_id=args.model_id,
+            allow_paid_run=args.allow_paid_run,
+            env_file=args.gemini_env_file,
+        )
+    raise ValueError(f"Unsupported provider: {args.provider}")
+
+
+def run_gemini_bootstrap_with_retries(
+    record: PilotRecord,
+    *,
+    args: argparse.Namespace,
+) -> BootstrappedCaseExample:
+    attempts_remaining = args.api_retries
+    while True:
+        try:
+            return run_bootstrap(record, args=args)
+        except Exception as exc:
+            if attempts_remaining <= 0 or not retryable_provider_error(exc, args.provider):
+                raise
+            attempts_used = args.api_retries - attempts_remaining + 1
+            print(
+                f"{args.provider} transient failure for paper {record.paper_id}; "
+                f"retry {attempts_used}/{args.api_retries} after "
+                f"{args.api_retry_wait_seconds} seconds.",
+                flush=True,
+            )
+            attempts_remaining -= 1
+            time.sleep(args.api_retry_wait_seconds)
+
+
+def find_text_span(source_text: str, snippet: str) -> tuple[int, int] | None:
+    if not snippet:
+        return None
+    start = source_text.find(snippet)
+    if start < 0:
+        return None
+    return start, start + len(snippet)
+
+
+def support_snippet_failures(source_text: str, snippets: list[str]) -> list[str]:
+    return [snippet for snippet in snippets if snippet and snippet not in source_text]
+
+
+def validator_status_for_grounding(
+    *,
+    record: PilotRecord,
+    item: FieldGrounding,
+    expected_value: str,
+    duplicate_field: bool,
+) -> tuple[str, tuple[int, int] | None]:
+    span = find_text_span(record.source_text, item.extraction_text)
+    missing_support = support_snippet_failures(record.source_text, item.supporting_snippets)
+
+    if duplicate_field:
+        status = "duplicate_field_from_model_output"
+    elif expected_value != item.spreadsheet_value:
+        status = "manual_value_changed"
+    elif item.evidence_mode not in EVIDENCE_MODES:
+        status = "invalid_evidence_mode"
+    elif item.evidence_mode == "exact_quote":
+        status = "passed" if span else "quote_not_found"
+    elif item.evidence_mode == "inferred_from_text":
+        if span is None and item.extraction_text:
+            status = "inference_anchor_not_found"
+        elif not item.supporting_snippets:
+            status = "inference_missing_supporting_snippets"
+        elif missing_support:
+            status = "inference_snippet_not_found"
+        else:
+            status = "passed"
+    elif item.supports_manual_value:
+        status = "not_found_supports_manual_value_conflict"
+    else:
+        status = "needs_review"
+    return status, span
+
+
+def review_row(
+    *,
+    record: PilotRecord,
+    field_name: str,
+    spreadsheet_value: str,
+    model_spreadsheet_value: str,
+    evidence_mode: str,
+    extraction_text: str,
+    span: tuple[int, int] | None,
+    supporting_snippets: list[str],
+    supports_manual_value: bool,
+    reasoning_short: str,
+    validator_status: str,
+) -> dict[str, str]:
+    return {
+        "paper_id": record.paper_id,
+        "case_id": record.case_id,
+        "field_name": field_name,
+        "spreadsheet_value": spreadsheet_value,
+        "model_spreadsheet_value": model_spreadsheet_value,
+        "evidence_mode": evidence_mode,
+        "extraction_text": extraction_text,
+        "char_start": "" if span is None else str(span[0]),
+        "char_end": "" if span is None else str(span[1]),
+        "supporting_snippets_json": json.dumps(supporting_snippets, ensure_ascii=False),
+        "supports_manual_value": str(supports_manual_value).upper(),
+        "reasoning_short": reasoning_short,
+        "validator_status": validator_status,
+        "review_status": "draft",
+        "review_notes": "",
+        "target_view_json_path": repo_rel(record.target_view_json_path),
+    }
+
+
+def validate_case_output(record: PilotRecord, output: BootstrappedCaseExample) -> list[dict[str, str]]:
+    requested_fields = set(record.manual_fields)
+    returned_fields = [item.field_name for item in output.field_groundings]
+    returned_field_set = {field for field in returned_fields if field}
+    duplicate_fields = {field for field in returned_fields if returned_fields.count(field) > 1}
+    review_rows: list[dict[str, str]] = []
+
+    for item in output.field_groundings:
+        expected_value = record.manual_fields.get(item.field_name, "")
+        if item.field_name not in requested_fields:
+            status = "extra_field_from_model_output"
+            span = find_text_span(record.source_text, item.extraction_text)
+        else:
+            status, span = validator_status_for_grounding(
+                record=record,
+                item=item,
+                expected_value=expected_value,
+                duplicate_field=item.field_name in duplicate_fields,
+            )
+        review_rows.append(
+            review_row(
+                record=record,
+                field_name=item.field_name,
+                spreadsheet_value=expected_value,
+                model_spreadsheet_value=item.spreadsheet_value,
+                evidence_mode=item.evidence_mode,
+                extraction_text=item.extraction_text,
+                span=span,
+                supporting_snippets=item.supporting_snippets,
+                supports_manual_value=item.supports_manual_value,
+                reasoning_short=item.reasoning_short,
+                validator_status=status,
+            )
+        )
+
+    for field_name in sorted(requested_fields - returned_field_set):
+        review_rows.append(
+            review_row(
+                record=record,
+                field_name=field_name,
+                spreadsheet_value=record.manual_fields[field_name],
+                model_spreadsheet_value="",
+                evidence_mode="",
+                extraction_text="",
+                span=None,
+                supporting_snippets=[],
+                supports_manual_value=False,
+                reasoning_short="",
+                validator_status="missing_from_model_output",
+            )
+        )
+
+    extra_fields = sorted(returned_field_set - requested_fields)
+    if extra_fields:
+        review_rows.append(
+            review_row(
+                record=record,
+                field_name="__extra_model_fields__",
+                spreadsheet_value=";".join(extra_fields),
+                model_spreadsheet_value="",
+                evidence_mode="",
+                extraction_text="",
+                span=None,
+                supporting_snippets=[],
+                supports_manual_value=False,
+                reasoning_short="",
+                validator_status="extra_fields_from_model_output",
+            )
+        )
+    return review_rows
+
+
+def accepted_promotion_text(row: dict[str, str]) -> str:
+    extraction_text = (row.get("extraction_text") or "").strip()
+    if extraction_text:
+        return extraction_text
+    try:
+        snippets = json.loads(row.get("supporting_snippets_json") or "[]")
+    except json.JSONDecodeError:
+        return ""
+    if not isinstance(snippets, list):
+        return ""
+    return str(snippets[0]).strip() if snippets else ""
+
+
+def build_langextract_examples_from_review(review_rows: list[dict[str, str]]) -> list[dict[str, object]]:
+    accepted = [
+        row
+        for row in review_rows
+        if row.get("review_status") == "accepted"
+        and row.get("validator_status") == "passed"
+        and accepted_promotion_text(row)
     ]
 
+    by_case: dict[tuple[str, str, str], list[dict[str, str]]] = {}
+    for row in accepted:
+        key = (
+            row.get("paper_id", ""),
+            row.get("case_id", ""),
+            row.get("target_view_json_path", ""),
+        )
+        if key[0] and key[2]:
+            by_case.setdefault(key, []).append(row)
 
-# Group examples.
-def group_examples() -> list[dict[str, object]]:
-    return [
-        {
-            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
-            "paper_id": "3139",
-            "text": "This retrospective cohort study from a single outpatient tertiary clinic evaluated 107 patients with stiff-person spectrum disorder within a broader GAD65 neurologic autoimmunity cohort. Median age was 46 years, range 5 to 76, and 25% were male. The majority had classical SPSD, while partial SPSD and exaggerated startle phenotypes were less common. Anti-GAD antibodies were present, median serum titre was 537 nmol/L, CSF anti-GAD antibodies were detected in tested cases, and CMUA and exteroceptive reflex abnormalities were reported. Treated patients received steroids, IVIG, plasma exchange, rituximab, or cyclophosphamide; 34 of 44 treated patients responded, including 24 partial and 10 near-complete responses, and 32 of 44 had sustained response at follow-up. The study was retrospective and further antibody testing was not always available.",
-            "extractions": [
-                {"extraction_class": "group_design", "extraction_text": "retrospective cohort study from a single outpatient tertiary clinic"},
-                {"extraction_class": "group_characteristics", "extraction_text": "107 patients with stiff-person spectrum disorder; median age 46 years, range 5 to 76; 25% were male; the majority had classical SPSD, with partial SPSD and exaggerated startle phenotypes also represented"},
-                {"extraction_class": "group_findings", "extraction_text": "Anti-GAD antibodies were present, median serum titre was 537 nmol/L, CSF anti-GAD antibodies were detected in tested cases, and CMUA and exteroceptive reflex abnormalities were reported"},
-                {"extraction_class": "group_treatment_outcomes", "extraction_text": "34 of 44 treated patients responded, including 24 partial and 10 near-complete responses, and 32 of 44 had sustained response at follow-up"},
-                {"extraction_class": "group_limitations", "extraction_text": "The study was retrospective and further antibody testing was not always available"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
-            "paper_id": "233",
-            "text": "This observational cohort study from Germany investigated the head retraction reflex in 50 patients with stiff-man syndrome, stiff-limb syndrome, or PERM. Mean age was 45.7 years and 45% were male. The cohort included 28 SMS cases, 2 SLS cases, and 20 PERM cases. Anti-GAD positivity was reported in 15 of 28 SMS cases, 2 of 2 SLS cases, and 15 of 20 PERM cases. The main study focus was the prevalence and electrophysiologic characteristics of the head retraction reflex. The study provided limited detail on symptoms, patient history, and treatment.",
-            "extractions": [
-                {"extraction_class": "group_design", "extraction_text": "observational cohort study"},
-                {"extraction_class": "group_characteristics", "extraction_text": "50 patients; mean age 45.7 years; 45% were male; 28 SMS cases, 2 SLS cases, and 20 PERM cases"},
-                {"extraction_class": "group_findings", "extraction_text": "Anti-GAD positivity was reported in 15 of 28 SMS cases, 2 of 2 SLS cases, and 15 of 20 PERM cases"},
-                {"extraction_class": "group_limitations", "extraction_text": "The study provided limited detail on symptoms, patient history, and treatment"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
-            "paper_id": "13224",
-            "text": "This observational cohort study analysed 29 stiff-person syndrome cases within a broader screening program for GABAB receptor antibodies in neurologic syndromes associated with GAD antibodies. The study focused on antibody testing rather than detailed clinical phenotyping. All stiff-person syndrome cases were negative for GABAB receptor antibodies. The primary focus was not SPSD and the report provided little detail on SPSD characteristics.",
-            "extractions": [
-                {"extraction_class": "group_design", "extraction_text": "observational cohort study"},
-                {"extraction_class": "group_characteristics", "extraction_text": "29 stiff-person syndrome cases within a broader screening program for GABAB receptor antibodies"},
-                {"extraction_class": "group_findings", "extraction_text": "All stiff-person syndrome cases were negative for GABAB receptor antibodies"},
-                {"extraction_class": "group_limitations", "extraction_text": "The primary focus was not SPSD and the report provided little detail on SPSD characteristics"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
-            "paper_id": "6073",
-            "text": "This retrospective cohort study from Japan screened 5 stiff-person syndrome patients for gephyrin antibodies. One patient had anti-gephyrin antibodies and mediastinal cancer, while 4 patients were gephyrin negative. The report provided very limited demographic, clinical, and treatment detail.",
-            "extractions": [
-                {"extraction_class": "group_design", "extraction_text": "retrospective cohort study"},
-                {"extraction_class": "group_characteristics", "extraction_text": "5 stiff-person syndrome patients"},
-                {"extraction_class": "group_findings", "extraction_text": "One patient had anti-gephyrin antibodies and mediastinal cancer, while 4 patients were gephyrin negative"},
-                {"extraction_class": "group_limitations", "extraction_text": "The report provided very limited demographic, clinical, and treatment detail"},
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
-            "paper_id": "899",
-            "text": "This retrospective cohort study described 9 stiff-person syndrome cases from Tanzania. Mean age at onset was 36.7 years and 77.8% were male. The cohort included juvenile onset disease, stiff-limb syndrome, an anti-GAD positive case with later breast carcinoma, and patients with femoral fractures caused by spasms. Lumbar hyperlordosis, opisthotonus, abdominal rigidity, spasms, and hyperreflexia were common. Treatment included benzodiazepines and baclofen, and one anti-GAD positive patient improved markedly after IVIG. Laboratory confirmation was limited in this setting.",
-            "extractions": [
-                {"extraction_class": "group_design", "extraction_text": "retrospective cohort study"},
-                {"extraction_class": "group_characteristics", "extraction_text": "9 stiff-person syndrome cases from Tanzania; mean age at onset was 36.7 years; 77.8% were male"},
-                {"extraction_class": "group_findings", "extraction_text": "The cohort included juvenile onset disease, stiff-limb syndrome, an anti-GAD positive case with later breast carcinoma, and patients with femoral fractures caused by spasms. Lumbar hyperlordosis, opisthotonus, abdominal rigidity, spasms, and hyperreflexia were common"},
-                {"extraction_class": "group_treatment_outcomes", "extraction_text": "Treatment included benzodiazepines and baclofen, and one anti-GAD positive patient improved markedly after IVIG"},
-                {"extraction_class": "group_limitations", "extraction_text": "Laboratory confirmation was limited in this setting"},
-            ],
+    examples: list[dict[str, object]] = []
+    for (paper_id, case_id, target_view_json_path), rows in sorted(by_case.items()):
+        payload = json.loads(repo_path(target_view_json_path).read_text(encoding="utf-8"))
+        text = normalise_example_text(payload.get("input_text") or payload.get("text") or "")
+        extractions = [
+            {
+                "extraction_class": row["field_name"],
+                "extraction_text": normalise_example_text(accepted_promotion_text(row)),
+                "attributes": {
+                    "value": row["spreadsheet_value"],
+                    "case_id": case_id,
+                    "evidence_mode": row["evidence_mode"],
+                },
+            }
+            for row in rows
+        ]
+        examples.append(
+            {
+                "source_sheet": SOURCE_SHEET_NAME,
+                "paper_id": paper_id,
+                "case_id": case_id,
+                "target_view_json_path": target_view_json_path,
+                "text": text,
+                "extractions": extractions,
+            }
+        )
+    return examples
+
+
+def load_support_spans(row: dict[str, str]) -> list[dict[str, object]]:
+    try:
+        payload = json.loads(row.get("support_spans_json") or "[]")
+    except json.JSONDecodeError:
+        return []
+    if not isinstance(payload, list):
+        return []
+    spans: list[dict[str, object]] = []
+    for item in payload:
+        if not isinstance(item, dict):
+            continue
+        span_text = str(item.get("span_text") or "")
+        if not span_text:
+            continue
+        try:
+            char_start = int(item.get("char_start", ""))
+            char_end = int(item.get("char_end", ""))
+        except (TypeError, ValueError):
+            continue
+        spans.append(
+            {
+                "span_text": span_text,
+                "char_start": char_start,
+                "char_end": char_end,
+                "span_role": str(item.get("span_role") or ""),
+                "selection_source": str(item.get("selection_source") or ""),
+                "match_mode": str(item.get("match_mode") or ""),
+            }
+        )
+    return spans
+
+
+def langextract_attributes(attributes: dict[str, object]) -> dict[str, str | list[str]]:
+    coerced: dict[str, str | list[str]] = {}
+    for key, value in attributes.items():
+        if isinstance(value, list):
+            coerced[key] = [normalise_example_text(str(item)) for item in value]
+        else:
+            coerced[key] = normalise_example_text(str(value))
+    return coerced
+
+
+def normalise_example_text(text: str) -> str:
+    return " ".join(text.split())
+
+
+def validate_span_plan_rows(span_plan_rows: list[dict[str, str]]) -> dict[str, object]:
+    coverage_errors: list[dict[str, object]] = []
+    span_count = 0
+    by_quality: dict[str, int] = {}
+    by_recommendation: dict[str, int] = {}
+
+    for row in span_plan_rows:
+        paper_id = row.get("paper_id", "")
+        field_name = row.get("field_name", "")
+        target_path = row.get("target_view_json_path", "")
+        spans = load_support_spans(row)
+        by_quality[row.get("coverage_quality", "")] = by_quality.get(row.get("coverage_quality", ""), 0) + 1
+        recommendation = row.get("langextract_recommendation", "")
+        by_recommendation[recommendation] = by_recommendation.get(recommendation, 0) + 1
+
+        if not spans:
+            coverage_errors.append(
+                {
+                    "paper_id": paper_id,
+                    "field_name": field_name,
+                    "error": "missing_support_spans",
+                }
+            )
+            continue
+
+        payload = json.loads(repo_path(target_path).read_text(encoding="utf-8"))
+        source_text = (payload.get("input_text") or payload.get("text") or "")
+        for span in spans:
+            span_count += 1
+            char_start = int(span["char_start"])
+            char_end = int(span["char_end"])
+            if source_text[char_start:char_end] != span["span_text"]:
+                coverage_errors.append(
+                    {
+                        "paper_id": paper_id,
+                        "field_name": field_name,
+                        "error": "span_offset_mismatch",
+                        "char_start": char_start,
+                        "char_end": char_end,
+                    }
+                )
+
+    return {
+        "field_row_count": len(span_plan_rows),
+        "support_span_count": span_count,
+        "coverage_error_count": len(coverage_errors),
+        "coverage_errors": coverage_errors,
+        "coverage_quality_counts": dict(sorted(by_quality.items())),
+        "recommendation_counts": dict(sorted(by_recommendation.items())),
+    }
+
+
+def build_langextract_examples_from_span_plan(span_plan_rows: list[dict[str, str]]) -> list[dict[str, object]]:
+    by_case: dict[tuple[str, str, str], list[dict[str, str]]] = {}
+    for row in span_plan_rows:
+        key = (
+            row.get("paper_id", ""),
+            row.get("case_id", ""),
+            row.get("target_view_json_path", ""),
+        )
+        if key[0] and key[2]:
+            by_case.setdefault(key, []).append(row)
+
+    examples: list[dict[str, object]] = []
+    for (paper_id, case_id, target_view_json_path), rows in sorted(by_case.items()):
+        payload = json.loads(repo_path(target_view_json_path).read_text(encoding="utf-8"))
+        text = normalise_example_text(payload.get("input_text") or payload.get("text") or "")
+        extraction_pool: list[dict[str, object]] = []
+        for row in rows:
+            spans = load_support_spans(row)
+            for index, span in enumerate(spans, start=1):
+                extraction_pool.append(
+                    {
+                        "extraction_class": row["field_name"],
+                        "extraction_text": normalise_example_text(str(span["span_text"])),
+                        "attributes": langextract_attributes(
+                            {
+                                "value": row["spreadsheet_value"],
+                                "case_id": case_id,
+                                "support_span_index": index,
+                                "support_span_count": len(spans),
+                                "char_start": span["char_start"],
+                                "char_end": span["char_end"],
+                                "span_role": span["span_role"],
+                                "coverage_quality": row.get("coverage_quality", ""),
+                                "langextract_recommendation": row.get("langextract_recommendation", ""),
+                                "original_evidence_mode": row.get("original_evidence_mode", ""),
+                                "original_validator_status": row.get("original_validator_status", ""),
+                            }
+                        ),
+                    }
+                )
+
+        extraction_pool.sort(
+            key=lambda item: (
+                int(item["attributes"]["char_start"]),
+                int(item["attributes"]["char_end"]),
+                str(item["extraction_class"]),
+            )
+        )
+        extraction_groups = partition_langextract_extractions(extraction_pool)
+
+        for group_index, extractions in enumerate(extraction_groups, start=1):
+            for extraction in extractions:
+                extraction["attributes"]["example_part_index"] = str(group_index)
+                extraction["attributes"]["example_part_count"] = str(len(extraction_groups))
+            examples.append(
+                {
+                    "source_sheet": SOURCE_SHEET_NAME,
+                    "paper_id": paper_id,
+                    "case_id": case_id,
+                    "example_part_index": group_index,
+                    "example_part_count": len(extraction_groups),
+                    "target_view_json_path": target_view_json_path,
+                    "text": text,
+                    "extractions": extractions,
+                }
+            )
+    return examples
+
+
+def partition_langextract_extractions(extractions: list[dict[str, object]]) -> list[list[dict[str, object]]]:
+    groups: list[list[dict[str, object]]] = []
+    group_last_end: list[int] = []
+
+    for extraction in extractions:
+        char_start = int(extraction["attributes"]["char_start"])
+        char_end = int(extraction["attributes"]["char_end"])
+        placed = False
+        for group_index, last_end in enumerate(group_last_end):
+            if char_start >= last_end:
+                groups[group_index].append(extraction)
+                group_last_end[group_index] = char_end
+                placed = True
+                break
+        if not placed:
+            groups.append([extraction])
+            group_last_end.append(char_end)
+
+    return groups
+
+
+def validate_langextract_example_payload(examples: list[dict[str, object]]) -> dict[str, object]:
+    try:
+        import langextract as lx
+        from langextract import prompt_validation as pv
+    except ImportError as exc:
+        raise SystemExit("langextract is required to validate span-plan examples.") from exc
+
+    attribute_errors: list[dict[str, object]] = []
+    example_data: list[Any] = []
+    extraction_count = 0
+
+    for example_index, example in enumerate(examples, start=1):
+        text = str(example.get("text") or "").strip()
+        extraction_rows = example.get("extractions") or []
+        if not text or not isinstance(extraction_rows, list):
+            continue
+
+        extractions: list[Any] = []
+        for extraction_index, row in enumerate(extraction_rows, start=1):
+            if not isinstance(row, dict):
+                continue
+
+            extraction_class = str(row.get("extraction_class") or "").strip()
+            extraction_text = str(row.get("extraction_text") or "").strip()
+            attributes: dict[str, str | list[str]] | None = None
+            attribute_payload = row.get("attributes")
+
+            if attribute_payload is not None:
+                if not isinstance(attribute_payload, dict):
+                    attribute_errors.append(
+                        {
+                            "example_index": example_index,
+                            "extraction_index": extraction_index,
+                            "key": "__attributes__",
+                            "type": type(attribute_payload).__name__,
+                        }
+                    )
+                else:
+                    attributes = {}
+                    for key, value in attribute_payload.items():
+                        clean_key = str(key).strip()
+                        if not clean_key:
+                            continue
+                        if isinstance(value, str):
+                            attributes[clean_key] = value
+                        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
+                            attributes[clean_key] = value
+                        else:
+                            attribute_errors.append(
+                                {
+                                    "example_index": example_index,
+                                    "extraction_index": extraction_index,
+                                    "key": clean_key,
+                                    "type": type(value).__name__,
+                                }
+                            )
+                            if isinstance(value, list):
+                                attributes[clean_key] = [str(item) for item in value]
+                            else:
+                                attributes[clean_key] = str(value)
+                    attributes = attributes or None
+
+            if extraction_class and extraction_text:
+                extractions.append(
+                    lx.data.Extraction(
+                        extraction_class=extraction_class,
+                        extraction_text=extraction_text,
+                        attributes=attributes,
+                    )
+                )
+                extraction_count += 1
+
+        if extractions:
+            example_data.append(lx.data.ExampleData(text=text, extractions=extractions))
+
+    policy = pv.AlignmentPolicy(enable_fuzzy_alignment=False, accept_match_lesser=False)
+    report = pv.validate_prompt_alignment(example_data, policy=policy)
+    alignment_issues = [str(issue) for issue in report.issues]
+
+    return {
+        "example_count": len(example_data),
+        "extraction_count": extraction_count,
+        "alignment_issue_count": len(alignment_issues),
+        "attribute_error_count": len(attribute_errors),
+        "alignment_policy": {
+            "enable_fuzzy_alignment": False,
+            "accept_match_lesser": False,
         },
-    ]
+        "alignment_issues": alignment_issues[:25],
+        "attribute_errors": attribute_errors[:25],
+    }
 
 
-# Build publication type examples.
-def publication_type_examples() -> list[dict[str, object]]:
+def selected_rows(records: list[PilotRecord]) -> list[dict[str, str]]:
     return [
         {
-            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
-            "paper_id": "12013",
-            "text": "A single-patient clinical vignette described one woman with progressive stiffness, spasms, anti-GAD positivity, and treatment with IVIG and symptomatic therapy.",
-            "extractions": [
-                {"extraction_class": "publication_type", "extraction_text": "Case Series & Reports"}
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Series_Reports.csv",
-            "paper_id": "1242",
-            "text": "This conference abstract presented a small descriptive report of stiff-person syndrome cases with very limited clinical detail and no formal cohort design.",
-            "extractions": [
-                {"extraction_class": "publication_type", "extraction_text": "Case Series & Reports"}
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
-            "paper_id": "3139",
-            "text": "This retrospective cohort study reviewed 107 patients with stiff-person spectrum disorder and compared clinical manifestations, antibody findings, and immunotherapy responses.",
-            "extractions": [
-                {"extraction_class": "publication_type", "extraction_text": "Observ Cohort & Cross sect"}
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
-            "paper_id": "899",
-            "text": "This retrospective cohort study described 9 stiff-person syndrome cases from Tanzania and reported prevalence and aggregate clinical features.",
-            "extractions": [
-                {"extraction_class": "publication_type", "extraction_text": "Observ Cohort & Cross sect"}
-            ],
-        },
-        {
-            "source_sheet": "datasheet_examples_MC_Case_Series_Reports.csv",
-            "paper_id": "493",
-            "text": "This small placebo-controlled levetiracetam trial compared intervention and placebo exposure in a stiff-person syndrome series.",
-            "extractions": [
-                {"extraction_class": "publication_type", "extraction_text": "Controlled Intervention Studies"}
-            ],
-        },
+            "paper_id": record.paper_id,
+            "case_id": record.case_id,
+            "target_view_json_path": repo_rel(record.target_view_json_path),
+            "field_count": str(len(record.manual_fields)),
+            "text_sha256": sha256_text(record.source_text),
+        }
+        for record in records
     ]
 
 
-# Run the pipeline entrypoint.
-def main() -> None:
-    case_rows = load_case_report_rows(CASE_REPORT_SHEET)
-    case_series_ids = load_sheet_ids(CASE_SERIES_SHEET, "ID")
-    cohort_ids = load_sheet_ids(COHORTS_SHEET, "ID")
-    obs_ids = load_sheet_ids(OBS_COHORT_SHEET, "Study ID")
+def selected_fieldnames() -> list[str]:
+    return ["paper_id", "case_id", "target_view_json_path", "field_count", "text_sha256"]
+
+
+def manifest_payload(
+    *,
+    args: argparse.Namespace,
+    selected_count: int,
+    field_review_count: int,
+    selected_rows_path: Path,
+    field_candidates_path: Path | None = None,
+    field_review_path: Path | None = None,
+    draft_examples_path: Path | None = None,
+    run_status: str = "completed",
+    completed_record_count: int | None = None,
+    failed_paper_id: str = "",
+    failure_type: str = "",
+    failure_message: str = "",
+) -> dict[str, object]:
+    return {
+        "generated_at_utc": now_utc_iso(),
+        "run_status": run_status,
+        "provider": args.provider,
+        "model_id": args.model_id,
+        "gemini_env_file": repo_rel(args.gemini_env_file),
+        "openai_env_file": repo_rel(args.openai_env_file),
+        "openai_reasoning_effort": args.openai_reasoning_effort,
+        "openai_max_output_tokens": args.openai_max_output_tokens,
+        "dry_run": bool(args.dry_run or not args.allow_paid_run),
+        "allow_paid_run": bool(args.allow_paid_run),
+        "api_retries": args.api_retries,
+        "api_retry_wait_seconds": args.api_retry_wait_seconds,
+        "selected_record_count": selected_count,
+        "completed_record_count": selected_count if completed_record_count is None else completed_record_count,
+        "field_review_row_count": field_review_count,
+        "selected_rows_path": repo_rel(selected_rows_path),
+        "field_candidates_path": "" if field_candidates_path is None else repo_rel(field_candidates_path),
+        "field_review_path": "" if field_review_path is None else repo_rel(field_review_path),
+        "draft_examples_path": "" if draft_examples_path is None else repo_rel(draft_examples_path),
+        "failed_paper_id": failed_paper_id,
+        "failure_type": failure_type,
+        "failure_message": failure_message,
+    }
 
-    individual_payload = individual_examples()
-    group_payload = group_examples()
-    publication_type_payload = publication_type_examples()
 
-    validate_individual_sources(individual_payload, case_rows)
-    validate_sheet_sources(group_payload, cohort_ids, "group")
-    validate_sheet_sources(
-        [item for item in publication_type_payload if item["source_sheet"] == "datasheet_examples_MC_Case_Series_Reports.csv"],
-        case_series_ids,
-        "publication-type case-series",
+def write_manifest(path: Path, payload: dict[str, object]) -> None:
+    write_json(path, payload)
+
+
+def checkpoint_paid_run(
+    *,
+    args: argparse.Namespace,
+    records: list[PilotRecord],
+    completed: int,
+    all_review_rows: list[dict[str, str]],
+    selected_path: Path,
+    jsonl_path: Path,
+    review_path: Path,
+    run_status: str,
+    failed_paper_id: str = "",
+    failure_type: str = "",
+    failure_message: str = "",
+) -> None:
+    write_csv_rows_atomic(review_path, all_review_rows, REVIEW_FIELDNAMES)
+    write_json_atomic(
+        args.output_dir / "run_manifest.json",
+        manifest_payload(
+            args=args,
+            selected_count=len(records),
+            completed_record_count=completed,
+            field_review_count=len(all_review_rows),
+            selected_rows_path=selected_path,
+            field_candidates_path=jsonl_path,
+            field_review_path=review_path,
+            run_status=run_status,
+            failed_paper_id=failed_paper_id,
+            failure_type=failure_type,
+            failure_message=failure_message,
+        ),
     )
-    validate_sheet_sources(
-        [item for item in publication_type_payload if item["source_sheet"] == "datasheet_examples_MC_Cohorts.csv"],
-        cohort_ids,
-        "publication-type cohort",
+
+
+def write_dry_run_outputs(args: argparse.Namespace, records: list[PilotRecord]) -> None:
+    selected_path = args.output_dir / "selected_rows.csv"
+    write_csv_rows(selected_path, selected_rows(records), selected_fieldnames())
+    write_manifest(
+        args.output_dir / "run_manifest.json",
+        manifest_payload(
+            args=args,
+            selected_count=len(records),
+            field_review_count=0,
+            selected_rows_path=selected_path,
+        ),
     )
-    validate_sheet_sources(
-        [item for item in publication_type_payload if item["source_sheet"] == "datasheet_examples_MC_Case_Report_Form.csv"],
-        {paper_id for paper_id, _ in case_rows},
-        "publication-type case-report",
+    print(f"Dry run selected {len(records)} records. No {args.provider} calls made.")
+    print(f"Wrote selected rows to {selected_path}")
+
+
+def write_paid_run_outputs(args: argparse.Namespace, records: list[PilotRecord]) -> None:
+    jsonl_path = args.output_dir / "field_candidates.jsonl"
+    review_path = args.output_dir / "field_review.csv"
+    selected_path = args.output_dir / "selected_rows.csv"
+    all_review_rows: list[dict[str, str]] = []
+
+    write_csv_rows(selected_path, selected_rows(records), selected_fieldnames())
+    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
+    completed = 0
+    checkpoint_paid_run(
+        args=args,
+        records=records,
+        completed=completed,
+        all_review_rows=all_review_rows,
+        selected_path=selected_path,
+        jsonl_path=jsonl_path,
+        review_path=review_path,
+        run_status="running",
+    )
+    try:
+        with jsonl_path.open("w", encoding="utf-8") as handle:
+            for record in records:
+                output = run_gemini_bootstrap_with_retries(record, args=args)
+                handle.write(json.dumps(asdict(output), ensure_ascii=False) + "\n")
+                handle.flush()
+                os.fsync(handle.fileno())
+                all_review_rows.extend(validate_case_output(record, output))
+                completed += 1
+                checkpoint_paid_run(
+                    args=args,
+                    records=records,
+                    completed=completed,
+                    all_review_rows=all_review_rows,
+                    selected_path=selected_path,
+                    jsonl_path=jsonl_path,
+                    review_path=review_path,
+                    run_status="running",
+                )
+    except Exception as exc:
+        checkpoint_paid_run(
+            args=args,
+            records=records,
+            completed=completed,
+            all_review_rows=all_review_rows,
+            selected_path=selected_path,
+            jsonl_path=jsonl_path,
+            review_path=review_path,
+            run_status="failed",
+            failed_paper_id=records[completed].paper_id if completed < len(records) else "",
+            failure_type=type(exc).__name__,
+            failure_message=str(exc),
+        )
+        raise
+
+    checkpoint_paid_run(
+        args=args,
+        records=records,
+        completed=completed,
+        all_review_rows=all_review_rows,
+        selected_path=selected_path,
+        jsonl_path=jsonl_path,
+        review_path=review_path,
+        run_status="completed",
     )
-    if not obs_ids:
-        raise ValueError("Observation cohort examples sheet could not be read.")
+    print(f"Wrote {len(records)} {args.provider} candidate records to {jsonl_path}")
+    print(f"Wrote {len(all_review_rows)} review rows to {review_path}")
+
+
+def promote_from_review(args: argparse.Namespace) -> None:
+    review_rows = read_csv_rows(args.promote_from_review)
+    examples = build_langextract_examples_from_review(review_rows)
+    out_path = args.examples_out_dir / "draft_langextract_examples.json"
+    write_json(out_path, examples)
+    write_manifest(
+        args.output_dir / "run_manifest.json",
+        manifest_payload(
+            args=args,
+            selected_count=len(examples),
+            field_review_count=len(review_rows),
+            selected_rows_path=args.promote_from_review,
+            draft_examples_path=out_path,
+        ),
+    )
+    print(f"Wrote {len(examples)} draft examples to {out_path}")
+
+
+def build_from_span_plan(args: argparse.Namespace) -> None:
+    span_plan_rows = read_csv_rows(args.build_from_span_plan)
+    validation = validate_span_plan_rows(span_plan_rows)
+    if validation["coverage_error_count"]:
+        raise SystemExit(
+            f"Span plan has {validation['coverage_error_count']} coverage errors; refusing to build examples."
+        )
+
+    examples = build_langextract_examples_from_span_plan(span_plan_rows)
+    compatibility = validate_langextract_example_payload(examples)
+    if compatibility["alignment_issue_count"] or compatibility["attribute_error_count"]:
+        raise SystemExit(
+            "LangExtract compatibility validation failed: "
+            f"{compatibility['alignment_issue_count']} alignment issues, "
+            f"{compatibility['attribute_error_count']} attribute errors."
+        )
+
+    out_path = args.examples_out_dir / args.span_plan_examples_name
+    manifest_path = args.output_dir / "span_plan_examples_manifest.json"
+    source_document_count = len(
+        {
+            (
+                row.get("paper_id", ""),
+                row.get("case_id", ""),
+                row.get("target_view_json_path", ""),
+            )
+            for row in span_plan_rows
+            if row.get("paper_id") and row.get("target_view_json_path")
+        }
+    )
+    write_json(out_path, examples)
+    write_json(
+        manifest_path,
+        {
+            "generated_at_utc": now_utc_iso(),
+            "span_plan_path": repo_rel(args.build_from_span_plan),
+            "examples_path": repo_rel(out_path),
+            "example_count": len(examples),
+            "source_document_count": source_document_count,
+            "extraction_count": compatibility["extraction_count"],
+            "langextract_compatibility": compatibility,
+            **validation,
+        },
+    )
+    print(f"Wrote {len(examples)} all-gold draft examples to {out_path}")
+    print(f"Wrote span-plan coverage manifest to {manifest_path}")
+
+
+def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
+    parser = argparse.ArgumentParser(
+        description="Bootstrap reviewed MC single-case LangExtract examples with a paid LLM provider."
+    )
+    parser.add_argument("--limit", type=int, default=10)
+    parser.add_argument("--paper-id", action="append", default=[])
+    parser.add_argument("--exclude-paper-id", action="append", default=[])
+    parser.add_argument("--provider", choices=["openai", "gemini"], default="openai")
+    parser.add_argument("--model-id", default=None)
+    parser.add_argument("--gemini-env-file", type=Path, default=DEFAULT_GEMINI_ENV_FILE)
+    parser.add_argument("--openai-env-file", type=Path, default=DEFAULT_OPENAI_ENV_FILE)
+    parser.add_argument("--openai-reasoning-effort", default=DEFAULT_OPENAI_REASONING_EFFORT)
+    parser.add_argument("--openai-max-output-tokens", type=int, default=DEFAULT_OPENAI_MAX_OUTPUT_TOKENS)
+    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / "pilot_10")
+    parser.add_argument("--examples-out-dir", type=Path, default=DEFAULT_EXAMPLES_OUT_DIR)
+    parser.add_argument("--allow-paid-run", action="store_true")
+    parser.add_argument("--dry-run", action="store_true")
+    parser.add_argument("--api-retries", type=int, default=2)
+    parser.add_argument("--api-retry-wait-seconds", type=float, default=20.0)
+    parser.add_argument("--promote-from-review", type=Path, default=None)
+    parser.add_argument("--build-from-span-plan", type=Path, default=None)
+    parser.add_argument("--span-plan-examples-name", default="draft_langextract_examples_all_gold.json")
+    args = parser.parse_args(argv)
+    if args.model_id is None:
+        args.model_id = DEFAULT_OPENAI_MODEL if args.provider == "openai" else DEFAULT_GEMINI_MODEL
+    return args
+
+
+def main(argv: list[str] | None = None) -> None:
+    args = parse_args(argv)
+    args.output_dir.mkdir(parents=True, exist_ok=True)
+
+    if args.promote_from_review:
+        promote_from_review(args)
+        return
+
+    if args.build_from_span_plan:
+        build_from_span_plan(args)
+        return
+
+    records = select_pilot_records(
+        limit=args.limit,
+        explicit_ids=args.paper_id,
+        excluded_ids=args.exclude_paper_id,
+    )
+    if not records:
+        raise SystemExit("No manually reviewed MC records selected.")
+
+    if args.dry_run or not args.allow_paid_run:
+        write_dry_run_outputs(args, records)
+        return
 
-    write_json(INDIVIDUAL_OUT, individual_payload)
-    write_json(GROUP_OUT, group_payload)
-    write_json(PUBLICATION_TYPE_OUT, publication_type_payload)
-    print(f"Wrote {len(individual_payload)} individual examples to {INDIVIDUAL_OUT}")
-    print(f"Wrote {len(group_payload)} group examples to {GROUP_OUT}")
-    print(f"Wrote {len(publication_type_payload)} publication-type examples to {PUBLICATION_TYPE_OUT}")
+    write_paid_run_outputs(args, records)
 
 
 if __name__ == "__main__":
-    main()
+    main(sys.argv[1:])
diff --git a/src/pipelines/10_langextract.py b/src/pipelines/10_langextract.py
index 9273187..eb7b27e 100644
--- a/src/pipelines/10_langextract.py
+++ b/src/pipelines/10_langextract.py
@@ -161,6 +161,20 @@ def default_group_examples_payload() -> list[dict[str, Any]]:
 
 # Convert example payload dictionaries into LangExtract ExampleData objects.
 def to_example_data(payload: list[dict[str, Any]]) -> list[Any]:
+    def coerce_attributes(value: Any) -> dict[str, str | list[str]] | None:
+        if not isinstance(value, dict):
+            return None
+        attributes: dict[str, str | list[str]] = {}
+        for key, item in value.items():
+            clean_key = str(key).strip()
+            if not clean_key:
+                continue
+            if isinstance(item, list):
+                attributes[clean_key] = [str(part) for part in item]
+            else:
+                attributes[clean_key] = str(item)
+        return attributes or None
+
     examples: list[Any] = []
     for item in payload:
         text = (item.get("text") or "").strip()
@@ -176,6 +190,7 @@ def to_example_data(payload: list[dict[str, Any]]) -> list[Any]:
                     lx.data.Extraction(
                         extraction_class=extraction_class,
                         extraction_text=extraction_text,
+                        attributes=coerce_attributes(row.get("attributes")),
                     )
                 )
         if extractions:
diff --git a/src/pipelines/README.md b/src/pipelines/README.md
index 5d0299e..aa01002 100644
--- a/src/pipelines/README.md
+++ b/src/pipelines/README.md
@@ -248,8 +248,13 @@ python src/pipelines/07_split_case_series.py
 
 ### `09_build_langextract_examples.py`
 
-Rebuilds few-shot JSON assets in `config/prompts/examples/` from curated rows
-under `examples/`.
+Bootstraps reviewable LangExtract example candidates from manually reviewed MC
+single-case rows and Stage 07 gold target-view text. Dry runs and Gemini
+candidate outputs stay under `qa/validation/langextract_example_bootstrap/`;
+accepted pilot examples are compiled under `examples/langextract_bootstrap/`
+before any later promotion into `config/prompts/examples/`. The span-plan build
+path validates exact Stage 07 offsets and runs strict LangExtract prompt
+alignment before writing the all-gold draft examples.
 
 ### `10_langextract.py`
 
diff --git a/tests/test_10_langextract.py b/tests/test_10_langextract.py
index 1a10c95..dca8bcb 100644
--- a/tests/test_10_langextract.py
+++ b/tests/test_10_langextract.py
@@ -51,6 +51,32 @@ class TestLangExtractRouting(unittest.TestCase):
     def tearDown(self) -> None:
         self.temp_dir.cleanup()
 
+    def test_to_example_data_preserves_langextract_attributes(self) -> None:
+        examples = self.module.to_example_data(
+            [
+                {
+                    "text": "A 39-year-old woman had spasms.",
+                    "extractions": [
+                        {
+                            "extraction_class": "age_description",
+                            "extraction_text": "39-year-old",
+                            "attributes": {
+                                "value": 39,
+                                "case_id": "",
+                                "field_flags": ["gold", "exact"],
+                            },
+                        }
+                    ],
+                }
+            ]
+        )
+
+        self.assertEqual(len(examples), 1)
+        self.assertEqual(
+            examples[0].extractions[0].attributes,
+            {"value": "39", "case_id": "", "field_flags": ["gold", "exact"]},
+        )
+
     def test_process_file_skips_incorrect_reference_without_writing_outputs(self) -> None:
         module = self.module
         input_path = self.input_dir / "1841.json"


# Untracked Files

## doc/plans/embeddings_plan.md


## doc/proposals/langextract_single_case_bootstrap_proposal.md
# Proposal: Bootstrap LangExtract Examples From Reviewed Single-Case Gold

## Purpose

Build a reviewable pilot workflow that turns 10 manually reviewed MC case-report rows into high-quality LangExtract examples, then scales to the full 85 reviewed rows once the evidence quality and review workflow are acceptable.

The proposal supersedes the exploratory bottom section of `src/pipelines/09_build_langextract_examples.py`. That script can still be mined for ideas, but it should not be treated as canonical. The new implementation should be explicit, CLI-verifiable, and safe around paid Gemini calls.

## Inputs

- `resources/stage07_single_case_gold_json_index.csv`
  - Use only rows where `manually_reviewed_MC == TRUE`.
  - Use `stage07_target_view_json_path` to load the Stage 07 gold target-view JSON.
  - The text field is expected as `input_text`; accept `text` only as a fallback.
- `examples/datasheet_examples_MC_Case_Report_Form.csv`
  - Treat this as the manual gold standard.
  - Join by `Reference == paper_id`.
  - Preserve `case_ID` as case metadata.
  - Use all non-empty manually extracted data fields as candidate extraction targets.
- `qa/validation/stage07_single_case_codex_gold/.../json/target_views/{paper_id}/p1.json`
  - Use its raw clinical text for grounding.
- `env/gemini.env`
  - Local secret file containing `GEMINI_API_KEY=...`.
  - The script may load this file, but must never print, persist, or commit the key.

## Output Shape

Pilot outputs should be non-canonical review artefacts under:

`qa/validation/langextract_example_bootstrap/pilot_10/`

Planned files:

- `selected_rows.csv`: the 10 selected paper/case rows and source paths.
- `field_candidates.jsonl`: one JSON record per paper/case containing Gemini output for all non-empty manual fields.
- `field_review.csv`: one row per manual field, optimised for human review.
- `run_manifest.json`: model, input hashes, selected IDs, command, and validation summary.

Accepted pilot examples should be compiled into:

`examples/langextract_bootstrap/draft_langextract_examples.json`

Accepted examples should not be written to `config/prompts/examples/` until after review.

## Product Survival Brief

- Primary workflow: convert manual MC spreadsheet rows plus Stage 07 gold text into reviewed LangExtract examples.
- Core data object and owner: one bootstrapped field-level evidence candidate, owned by this repo's review workflow.
- Roles and permissions affected: no app roles; CLI only.
- Lifecycle states: `draft`, `needs_review`, `accepted`, `rejected`.
- External service state: Gemini API call, gated by `--allow-paid-run`.
- Admin/support need: run manifest plus per-field review CSV for repair and reruns.
- Observability need: counts for selected papers, fields requested, fields returned, exact quote matches, inferred fields, not found fields, and validation failures.
- Non-goals: full 85-row production promotion, prompt optimisation, and running Gemini without explicit approval.

## Premortem

Premortem frame: it is 6 months from now and the LangExtract example bootstrap failed. We are working backwards to identify why.

1. The model produced plausible but ungrounded clinical evidence.
   - Mitigation: require exact text snippets for quoteable fields, local substring validation, and explicit `evidence_mode` for inferred fields.
2. The workflow silently dropped manual fields.
   - Mitigation: validate one Gemini result per non-empty manual target field.
3. The pilot confused provenance fields with extraction targets.
   - Mitigation: keep `extractor`, `Reference`, and `case_ID` as metadata; include all other non-empty manual fields as extraction targets.
4. The Stage 07 text did not contain enough evidence for some manual values.
   - Mitigation: allow `not_found` and `inferred_from_text` statuses; do not force exact quotes for inferential fields.
5. The generated examples were promoted too early.
   - Mitigation: write only review packs first; require accepted review rows before writing prompt examples.
6. The model version or SDK behaviour changed.
   - Mitigation: record model ID, SDK version if available, response schema, command, and input hashes in `run_manifest.json`.

## Proposed Implementation

The proposal is to rewrite `src/pipelines/09_build_langextract_examples.py` into a focused bootstrap-and-promote CLI, or create a new module and leave a thin compatibility wrapper in `09_build_langextract_examples.py`. I recommend a rewrite because the existing file already owns stage 09 in `doc/repo_rules.md`, but the current bottom sample is exploratory and mixed with unrelated code.

### 1. Constants And Response Schema

```python
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


# Keep all paths repository-relative where possible so review outputs can be
# compared across machines and worktrees.
REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "resources" / "stage07_single_case_gold_json_index.csv"
MC_CASE_REPORT_PATH = REPO_ROOT / "examples" / "datasheet_examples_MC_Case_Report_Form.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "validation" / "langextract_example_bootstrap"
DEFAULT_EXAMPLES_OUT_DIR = REPO_ROOT / "examples" / "langextract_bootstrap"
DEFAULT_GEMINI_ENV_FILE = REPO_ROOT / "env" / "gemini.env"


# The user requested Gemini 2.5 Flash. Keep it configurable so the exact
# provider model ID can be corrected without editing code if the SDK exposes a
# slightly different spelling.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


# These fields identify the manual row and reviewer, but they are not clinical
# facts to ask LangExtract to extract from article text.
PROVENANCE_FIELDS = {"extractor", "Reference", "case_ID"}


class FieldGrounding(BaseModel):
    # The spreadsheet column name. The caller will verify that every requested
    # non-empty field appears exactly once in the response.
    field_name: str = Field(description="Manual spreadsheet column name.")

    # Preserve the exact manual value as the gold standard. The model may not
    # normalise, translate, or silently rewrite it.
    spreadsheet_value: str = Field(description="Exact non-empty value from the manual row.")

    # Exact quotes work for fields such as age, sex wording, treatments, titres,
    # and named diagnoses. Some higher-level fields, such as phenotype, may need
    # inference from several snippets.
    evidence_mode: Literal["exact_quote", "inferred_from_text", "not_found"] = Field(
        description="How the manual value is supported by the source text."
    )

    # For exact_quote, this must be a verbatim substring of source_text. For
    # inferred_from_text, this should be the shortest useful source phrase or
    # sentence that anchors the inference. For not_found, leave it empty.
    extraction_text: str = Field(description="Verbatim supporting text, or empty if not found.")

    # Optional additional verbatim snippets for inferred fields where one text
    # span is not enough. The validator checks each snippet as a substring.
    supporting_snippets: list[str] = Field(default_factory=list)

    # A short explanation for reviewers. This is never promoted into the final
    # LangExtract example unless explicitly chosen later.
    reasoning_short: str = Field(description="Brief reviewer-facing explanation.")

    # The model must mark false if it cannot support the manual value from the
    # supplied text. This gives the validator a simple fail-visible gate.
    supports_manual_value: bool


class BootstrappedCaseExample(BaseModel):
    # Paper and case metadata allow one paper to produce multiple examples when
    # the manual sheet has multiple case rows.
    paper_id: str
    case_id: str
    model_id: str
    field_groundings: list[FieldGrounding]
```

Summary: this block defines the proposed script-level constants and the structured Gemini response schema. The key design choice is to separate quoteable evidence from inferred evidence rather than pretending every spreadsheet value must have a direct quote.

### 2. Load And Join The 10-Paper Pilot

```python
@dataclass(frozen=True)
class PilotRecord:
    # A PilotRecord is the smallest unit sent to Gemini: one paper/case row,
    # the Stage 07 text for that paper, and all non-empty manual fields for that
    # case row.
    paper_id: str
    case_id: str
    target_view_json_path: Path
    source_text: str
    manual_fields: dict[str, str]


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    # Use utf-8-sig so a byte-order mark in CSV exports does not become part of
    # the first header name.
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_stage07_text(path: Path) -> str:
    # Stage 07 target-view JSONs currently expose the clinical input text as
    # input_text. The fallback to text is included because the user described
    # the raw text generically as a text field, and older artefacts may differ.
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = (payload.get("input_text") or payload.get("text") or "").strip()
    if not text:
        raise ValueError(f"No Stage 07 input text found in {path}")
    return text


def manual_fields_from_row(row: dict[str, str]) -> dict[str, str]:
    # Keep every non-empty manually extracted data value. Provenance columns are
    # retained elsewhere as metadata, not sent as extraction targets.
    fields: dict[str, str] = {}
    for key, value in row.items():
        clean_key = (key or "").strip()
        clean_value = (value or "").strip()
        if not clean_key or not clean_value:
            continue
        if clean_key in PROVENANCE_FIELDS:
            continue
        fields[clean_key] = clean_value
    return fields


def select_pilot_records(limit: int, explicit_ids: list[str]) -> list[PilotRecord]:
    # The resource index is the authoritative bridge from Stage 07 gold IDs to
    # target-view JSON paths and the manually_reviewed_MC flag.
    index_rows = load_csv_rows(INDEX_PATH)
    manual_rows = load_csv_rows(MC_CASE_REPORT_PATH)

    manual_by_id: dict[str, list[dict[str, str]]] = {}
    for row in manual_rows:
        paper_id = (row.get("Reference") or "").strip()
        if paper_id:
            manual_by_id.setdefault(paper_id, []).append(row)

    wanted = {paper_id.strip() for paper_id in explicit_ids if paper_id.strip()}
    selected: list[PilotRecord] = []

    for index_row in index_rows:
        paper_id = (index_row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        if index_row.get("manually_reviewed_MC") != "TRUE":
            continue
        if wanted and paper_id not in wanted:
            continue

        target_path = REPO_ROOT / index_row["stage07_target_view_json_path"]
        source_text = load_stage07_text(target_path)

        for manual_row in manual_by_id.get(paper_id, []):
            fields = manual_fields_from_row(manual_row)
            if not fields:
                continue
            selected.append(
                PilotRecord(
                    paper_id=paper_id,
                    case_id=(manual_row.get("case_ID") or "").strip(),
                    target_view_json_path=target_path,
                    source_text=source_text,
                    manual_fields=fields,
                )
            )
            if not wanted and len(selected) >= limit:
                return selected

    return selected
```

Summary: this block proposes the deterministic data join. It selects only `manually_reviewed_MC == TRUE` rows, loads the Stage 07 target-view text, joins to MC manual rows by `Reference`, and keeps all non-empty non-provenance fields for the pilot.

### 3. Build The Gemini Prompt

```python
def build_bootstrap_prompt(record: PilotRecord) -> str:
    # Keep the prompt specific to this single call. Do not mention later stages,
    # future scaling, or unrelated pipeline tasks.
    manual_payload = json.dumps(record.manual_fields, ensure_ascii=False, indent=2)

    return f"""
You are building grounded examples for an information extraction system.

You will receive:
1. Source text from one reviewed single-case SPSD paper.
2. A dictionary of manually extracted gold-standard spreadsheet fields.

For every provided field:
- Return exactly one field_groundings item.
- Preserve field_name exactly.
- Preserve spreadsheet_value exactly.
- If the value is directly quoteable, set evidence_mode to exact_quote and put
  the shortest verbatim supporting source phrase or sentence in extraction_text.
- If the value requires clinical inference from the text, set evidence_mode to
  inferred_from_text and provide one or more verbatim supporting snippets.
- If the value cannot be supported from the supplied text, set evidence_mode to
  not_found, set supports_manual_value to false, and leave extraction_text empty.
- Do not invent evidence.
- Do not use outside knowledge.
- Do not change the manual value.

Paper ID: {record.paper_id}
Case ID: {record.case_id}

Manual gold fields:
{manual_payload}

Source text:
\"\"\"
{record.source_text}
\"\"\"
""".strip()
```

Summary: this block proposes the per-case prompt. It is deliberately narrow: the model only grounds the manual values against the supplied Stage 07 text and must return one structured item per field.

### 4. Call Gemini 2.5 Flash Behind An Explicit Paid-Run Gate

```python
def require_paid_run_approval(allow_paid_run: bool) -> None:
    # The repo rules forbid starting paid LLM/API runs without explicit user
    # approval. A CLI flag is auditable and keeps dry-runs safe by default.
    if not allow_paid_run:
        raise SystemExit("Refusing to call Gemini without --allow-paid-run.")


def load_env_file(path: Path) -> None:
    # Keep this intentionally tiny: read KEY=VALUE lines, ignore comments and
    # blanks, and never print the loaded values. Existing environment variables
    # win so callers can override locally without editing files.
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def gemini_client(env_file: Path) -> genai.Client:
    # Secrets stay in environment variables or local env files. The script should
    # not print the key or write it into run artefacts.
    load_env_file(env_file)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def run_gemini_bootstrap(
    record: PilotRecord,
    *,
    model_id: str,
    allow_paid_run: bool,
    env_file: Path,
) -> BootstrappedCaseExample:
    require_paid_run_approval(allow_paid_run)
    client = gemini_client(env_file)
    prompt = build_bootstrap_prompt(record)

    # response_schema asks Gemini for JSON that Pydantic can validate. Keep
    # temperature at zero to reduce variation and make reruns easier to compare.
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BootstrappedCaseExample,
            temperature=0.0,
        ),
    )

    # Parse through Pydantic even when the SDK says it returned JSON. Treat model
    # output as untrusted until schema validation succeeds.
    payload = json.loads(response.text or "{}")
    parsed = BootstrappedCaseExample.model_validate(payload)

    # The model should echo these, but the caller owns the truth. Overwrite them
    # so downstream review rows cannot drift because of model formatting.
    return parsed.model_copy(
        update={
            "paper_id": record.paper_id,
            "case_id": record.case_id,
            "model_id": model_id,
        }
    )
```

Summary: this block proposes the Gemini call. It uses `gemini-2.5-flash` by default, can load `GEMINI_API_KEY` from `env/gemini.env`, requires `--allow-paid-run`, keeps the API key out of logs and artefacts, and validates the response before any output is trusted.

### 5. Validate Grounding And Write The Review Pack

```python
def find_text_span(source_text: str, snippet: str) -> tuple[int, int] | None:
    # Exact offsets are computed locally, not trusted from the model. If the
    # snippet is absent, the review row is marked invalid.
    if not snippet:
        return None
    start = source_text.find(snippet)
    if start < 0:
        return None
    return start, start + len(snippet)


def validate_case_output(
    record: PilotRecord,
    output: BootstrappedCaseExample,
) -> list[dict[str, str]]:
    requested_fields = set(record.manual_fields)
    returned_fields = [item.field_name for item in output.field_groundings]
    returned_field_set = set(returned_fields)

    review_rows: list[dict[str, str]] = []

    # Missing and extra fields are fatal for promotion, but they are still
    # written to the review CSV so the user can see what went wrong.
    missing_fields = sorted(requested_fields - returned_field_set)
    extra_fields = sorted(returned_field_set - requested_fields)

    for item in output.field_groundings:
        expected_value = record.manual_fields.get(item.field_name, "")
        span = find_text_span(record.source_text, item.extraction_text)

        supporting_missing = [
            snippet
            for snippet in item.supporting_snippets
            if snippet and snippet not in record.source_text
        ]

        if item.evidence_mode == "exact_quote":
            validator_status = "passed" if span else "quote_not_found"
        elif item.evidence_mode == "inferred_from_text":
            validator_status = "passed" if item.supporting_snippets and not supporting_missing else "inference_snippet_not_found"
        elif item.evidence_mode == "not_found":
            validator_status = "needs_review"
        else:
            validator_status = "invalid_evidence_mode"

        if expected_value != item.spreadsheet_value:
            validator_status = "manual_value_changed"

        review_rows.append(
            {
                "paper_id": record.paper_id,
                "case_id": record.case_id,
                "field_name": item.field_name,
                "spreadsheet_value": expected_value,
                "model_spreadsheet_value": item.spreadsheet_value,
                "evidence_mode": item.evidence_mode,
                "extraction_text": item.extraction_text,
                "char_start": "" if span is None else str(span[0]),
                "char_end": "" if span is None else str(span[1]),
                "supporting_snippets_json": json.dumps(item.supporting_snippets, ensure_ascii=False),
                "supports_manual_value": str(item.supports_manual_value).upper(),
                "reasoning_short": item.reasoning_short,
                "validator_status": validator_status,
                "review_status": "draft",
                "review_notes": "",
                "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
            }
        )

    for field_name in missing_fields:
        review_rows.append(
            {
                "paper_id": record.paper_id,
                "case_id": record.case_id,
                "field_name": field_name,
                "spreadsheet_value": record.manual_fields[field_name],
                "model_spreadsheet_value": "",
                "evidence_mode": "",
                "extraction_text": "",
                "char_start": "",
                "char_end": "",
                "supporting_snippets_json": "[]",
                "supports_manual_value": "FALSE",
                "reasoning_short": "",
                "validator_status": "missing_from_model_output",
                "review_status": "draft",
                "review_notes": "",
                "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
            }
        )

    if extra_fields:
        # Record the unexpected fields once per case. This makes schema drift
        # visible without trying to promote unknown targets.
        review_rows.append(
            {
                "paper_id": record.paper_id,
                "case_id": record.case_id,
                "field_name": "__extra_model_fields__",
                "spreadsheet_value": ";".join(extra_fields),
                "model_spreadsheet_value": "",
                "evidence_mode": "",
                "extraction_text": "",
                "char_start": "",
                "char_end": "",
                "supporting_snippets_json": "[]",
                "supports_manual_value": "FALSE",
                "reasoning_short": "",
                "validator_status": "extra_fields_from_model_output",
                "review_status": "draft",
                "review_notes": "",
                "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
            }
        )

    return review_rows
```

Summary: this block proposes the local validator. It checks that Gemini returned every requested field, did not change manual values, and supplied snippets that are actually present in the Stage 07 text.

### 6. Convert Accepted Review Rows To LangExtract Examples

```python
def build_langextract_examples_from_review(review_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    # Only accepted rows become prompt examples. This prevents draft model output
    # from becoming canonical few-shot material.
    accepted = [
        row
        for row in review_rows
        if row.get("review_status") == "accepted"
        and row.get("validator_status") == "passed"
        and row.get("extraction_text")
    ]

    by_case: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in accepted:
        key = (
            row["paper_id"],
            row.get("case_id", ""),
            row["target_view_json_path"],
        )
        by_case.setdefault(key, []).append(row)

    examples: list[dict[str, object]] = []
    for (paper_id, case_id, target_view_json_path), rows in by_case.items():
        source_payload = json.loads((REPO_ROOT / target_view_json_path).read_text(encoding="utf-8"))
        text = (source_payload.get("input_text") or source_payload.get("text") or "").strip()

        extractions = []
        for row in rows:
            # extraction_class is the manual spreadsheet field name. The gold
            # value is stored in attributes so LangExtract examples can teach
            # both the evidence span and the structured target value.
            extractions.append(
                {
                    "extraction_class": row["field_name"],
                    "extraction_text": row["extraction_text"],
                    "attributes": {
                        "value": row["spreadsheet_value"],
                        "case_id": case_id,
                        "evidence_mode": row["evidence_mode"],
                    },
                }
            )

        examples.append(
            {
                "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
                "paper_id": paper_id,
                "case_id": case_id,
                "target_view_json_path": target_view_json_path,
                "text": text,
                "extractions": extractions,
            }
        )

    return examples
```

Summary: this block proposes the promotion compiler. It groups accepted field rows by paper/case and creates LangExtract-compatible examples with spreadsheet field names as extraction classes and manual values in attributes.

### 7. CLI Orchestration

```python
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap reviewed MC single-case LangExtract examples with Gemini."
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--model-id", default=DEFAULT_GEMINI_MODEL)
    parser.add_argument("--gemini-env-file", type=Path, default=DEFAULT_GEMINI_ENV_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / "pilot_10")
    parser.add_argument("--examples-out-dir", type=Path, default=DEFAULT_EXAMPLES_OUT_DIR)
    parser.add_argument("--allow-paid-run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--promote-from-review", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.promote_from_review:
        review_rows = load_csv_rows(args.promote_from_review)
        examples = build_langextract_examples_from_review(review_rows)
        out_path = args.examples_out_dir / "draft_langextract_examples.json"
        out_path.write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {len(examples)} draft examples to {out_path}")
        return

    records = select_pilot_records(limit=args.limit, explicit_ids=args.paper_id)
    if not records:
        raise SystemExit("No manually reviewed MC records selected.")

    selected_path = args.output_dir / "selected_rows.csv"
    with selected_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["paper_id", "case_id", "target_view_json_path", "field_count", "text_sha256"],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "paper_id": record.paper_id,
                    "case_id": record.case_id,
                    "target_view_json_path": str(record.target_view_json_path.relative_to(REPO_ROOT)),
                    "field_count": len(record.manual_fields),
                    "text_sha256": sha256_text(record.source_text),
                }
            )

    if args.dry_run:
        print(f"Dry run selected {len(records)} records. No Gemini calls made.")
        return

    jsonl_path = args.output_dir / "field_candidates.jsonl"
    review_path = args.output_dir / "field_review.csv"
    all_review_rows: list[dict[str, str]] = []

    with jsonl_path.open("w", encoding="utf-8") as jsonl_handle:
        for record in records:
            output = run_gemini_bootstrap(
                record,
                model_id=args.model_id,
                allow_paid_run=args.allow_paid_run,
                env_file=args.gemini_env_file,
            )
            jsonl_handle.write(output.model_dump_json() + "\n")
            all_review_rows.extend(validate_case_output(record, output))

    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_review_rows[0]))
        writer.writeheader()
        writer.writerows(all_review_rows)

    manifest = {
        "generated_at_utc": now_utc_iso(),
        "model_id": args.model_id,
        "gemini_env_file": str(args.gemini_env_file.relative_to(REPO_ROOT)),
        "selected_record_count": len(records),
        "field_review_row_count": len(all_review_rows),
        "selected_rows_path": str(selected_path.relative_to(REPO_ROOT)),
        "field_candidates_path": str(jsonl_path.relative_to(REPO_ROOT)),
        "field_review_path": str(review_path.relative_to(REPO_ROOT)),
    }
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

Summary: this block proposes the end-to-end CLI. The dry-run selects the 10 pilot records without API calls. The paid run writes raw model candidates, a review CSV, and a manifest. Promotion is a separate command that only uses reviewed rows.

### 8. Focused Tests

```python
def test_manual_fields_excludes_only_provenance() -> None:
    row = {
        "extractor": "MC",
        "Reference": "75",
        "case_ID": "",
        "age_description": "39",
        "sex": "F",
        "empty_field": "",
    }
    assert manual_fields_from_row(row) == {"age_description": "39", "sex": "F"}


def test_validate_case_output_rejects_missing_quote() -> None:
    record = PilotRecord(
        paper_id="75",
        case_id="",
        target_view_json_path=Path("qa/validation/example.json"),
        source_text="A 39-year-old woman presented with spasms.",
        manual_fields={"age_description": "39"},
    )
    output = BootstrappedCaseExample(
        paper_id="75",
        case_id="",
        model_id="gemini-2.5-flash",
        field_groundings=[
            FieldGrounding(
                field_name="age_description",
                spreadsheet_value="39",
                evidence_mode="exact_quote",
                extraction_text="A 40-year-old woman",
                supporting_snippets=[],
                reasoning_short="Age phrase.",
                supports_manual_value=True,
            )
        ],
    )
    rows = validate_case_output(record, output)
    assert rows[0]["validator_status"] == "quote_not_found"


def test_validate_case_output_flags_missing_field() -> None:
    record = PilotRecord(
        paper_id="75",
        case_id="",
        target_view_json_path=Path("qa/validation/example.json"),
        source_text="A 39-year-old woman presented with spasms.",
        manual_fields={"age_description": "39", "sex": "F"},
    )
    output = BootstrappedCaseExample(
        paper_id="75",
        case_id="",
        model_id="gemini-2.5-flash",
        field_groundings=[
            FieldGrounding(
                field_name="age_description",
                spreadsheet_value="39",
                evidence_mode="exact_quote",
                extraction_text="39-year-old",
                supporting_snippets=[],
                reasoning_short="Age phrase.",
                supports_manual_value=True,
            )
        ],
    )
    rows = validate_case_output(record, output)
    assert any(row["validator_status"] == "missing_from_model_output" for row in rows)
```

Summary: this block proposes focused regression tests for the highest-risk behaviour: preserving all non-empty manual targets, rejecting non-verbatim quotes, and detecting dropped fields.

## Pilot Selection

Start with the first 10 `manually_reviewed_MC == TRUE` IDs in `resources/stage07_single_case_gold_json_index.csv`, unless explicit IDs are supplied:

`75, 92, 155, 162, 187, 197, 395, 427, 439, 512`

This gives a small but realistic spread of older case reports and variable text lengths.

## Review Rules

For each field in `field_review.csv`:

- `accepted`: evidence is clinically and textually acceptable for a LangExtract example.
- `rejected`: evidence is wrong, over-inferred, not useful, or model changed the manual value.
- `needs_review`: evidence may be inferential, ambiguous, or absent from the Stage 07 text.

Recommended first-pass acceptance rules:

- Accept `exact_quote` only when the quote is a verbatim substring and supports the manual value.
- Accept `inferred_from_text` only when the supporting snippets make the inference clear to a human reviewer.
- Reject `not_found` for promotion, but keep it in the review pack as evidence of missingness.
- Do not promote fields where Gemini changed the spreadsheet value.

## Verification Plan

Before any Gemini call:

```powershell
.\\.venv\\Scripts\\python.exe src\\pipelines\\09_build_langextract_examples.py --dry-run --limit 10
```

Expected evidence:

- 10 selected records.
- No Gemini calls.
- `selected_rows.csv` exists.
- Every selected row has a Stage 07 target-view JSON path and at least one manual field.

For the paid pilot, after explicit approval:

```powershell
.\\.venv\\Scripts\\python.exe src\\pipelines\\09_build_langextract_examples.py --limit 10 --allow-paid-run --model-id gemini-2.5-flash
```

Expected evidence:

- `field_candidates.jsonl` has 10 records.
- `field_review.csv` has one row per non-empty manual target field, plus any explicit validator rows.
- `run_manifest.json` records model ID and counts.
- Validator summary reports missing fields, quote failures, inferred fields, and not-found fields.

After manual review:

```powershell
.\\.venv\\Scripts\\python.exe src\\pipelines\\09_build_langextract_examples.py --promote-from-review qa\\validation\\langextract_example_bootstrap\\pilot_10\\field_review.csv
```

Expected evidence:

- `draft_langextract_examples.json` contains only accepted rows.
- No draft, rejected, not-found, or validator-failed fields are promoted.

## Answered Design Decisions For The Implementation Patch

1. `case_ID` is part of the example grouping key. Blank `case_ID` values are valid and group as `(paper_id, "")`.
2. Semicolon-delimited manual values are preserved as the original manual string for the pilot. Splitting can be reconsidered after review.
3. Inferred fields may be promoted into draft examples only after human acceptance in the review CSV.
4. Accepted pilot examples are compiled into `examples/langextract_bootstrap/draft_langextract_examples.json`; they do not replace `config/prompts/examples/02_individual_examples.json` during the 10-row pilot.

## Done Criteria For The First Patch

- `src/pipelines/09_build_langextract_examples.py` is cleaned or replaced with the proposed CLI.
- `--dry-run --limit 10` works without API credentials.
- Tests cover field preservation, quote validation, missing-field detection, and promotion filtering.
- No Gemini calls occur without `--allow-paid-run`.
- Pilot outputs are written only under `qa/validation/langextract_example_bootstrap/pilot_10/`.
- The final report states all commands run, checks passed or skipped, and the exact number of selected records and manual fields.


## doc/reports/langextract_openai_pilot10_gold_pdf_audit.md
# LangExtract OpenAI Pilot 10 Gold And PDF Audit

Date: 2026-05-29

## Scope

This report audits the second 10-paper LangExtract bootstrap pilot produced with
the OpenAI API from the manually reviewed MC case-report gold rows.

Primary artefacts:

- OpenAI run directory: `qa/validation/langextract_example_bootstrap/openai_pilot_10/`
- Selected papers: `524`, `537`, `551`, `552`, `554`, `566`, `573`, `615`, `621`, `623`
- Manual gold standard: `examples/datasheet_examples_MC_Case_Report_Form.csv`
- Stage 07 source text: `qa/validation/stage07_single_case_codex_gold/.../target_views/{paper_id}/p1.json`
- Original PDFs: `data/pdf_original/...`
- All-gold LangExtract JSON: `examples/langextract_bootstrap/draft_langextract_examples_openai_pilot10_all_gold.json`

The audit question was stricter than "did the model find a plausible answer".
Every non-empty manual gold value had to be represented in a span plan, and every
span used in the LangExtract example JSON had to be exact source text after only
whitespace normalisation.

## Run And Validation Summary

The successful paid run used:

- Provider: `openai`
- Model: `gpt-5.5`
- Reasoning effort: `low`
- Max output tokens per paper: `8000`
- Completed records: `10/10`
- Raw review rows: `263`

The first higher-effort run timed out before a completed paper was flushed, so
`src/pipelines/09_build_langextract_examples.py` now checkpoints partial paid
results after every completed paper. The successful run wrote a complete
manifest, review CSV, and JSONL candidate file.

Raw OpenAI validator status:

| Status | Count |
|---|---:|
| `passed` | 112 |
| `inference_snippet_not_found` | 71 |
| `quote_not_found` | 51 |
| `needs_review` | 29 |

The repaired span plan now covers all 263 manual gold fields:

| Coverage quality | Count | Meaning |
|---|---:|---|
| `direct_exact_span_ready` | 112 | OpenAI supplied exact source text that validated directly. |
| `covered_by_repaired_exact_source_text` | 127 | The value is source-backed, but I repaired the span to exact Stage 07 text. |
| `gold_source_conflict_or_partial_support` | 12 | The gold value conflicts with, or is only partly supported by, the source/PDF. |
| `needs_human_adjudication` | 7 | The source gives related evidence, but the coding interpretation is not safe to promote. |
| `context_or_absence_only_not_direct_extraction` | 5 | The gold value is an absence/context code, not a directly extractable positive span. |

LangExtract compatibility validation:

| Check | Result |
|---|---:|
| Source documents | 10 |
| Generated example payloads | 50 |
| Extraction rows | 387 |
| Alignment issues | 0 |
| Attribute type errors | 0 |
| Literal `\n` in example text/extraction text | 0 |

The generated JSON is technically LangExtract-compatible. It is intentionally an
all-gold audit JSON, not a clean promotion set. Rows with
`langextract_recommendation=do_not_promote_as_standard_langextract_example` or
`review_before_promoting` should be filtered out or adjudicated before use as
standard examples.

## LangExtract Span Practice Applied

For LangExtract, the `extraction_text` should be the shortest exact source text
that supports the field. The normalised spreadsheet value is stored as the
`value` attribute, because many MC fields are coded values, semicolon-delimited
normalisations, inferred classifications, or absence codes.

When a value required more than one non-contiguous source passage, the span plan
uses multiple exact spans instead of a stitched quote. When spans overlapped, the
builder split the paper into multiple example payloads for the same source text,
which is why 10 source documents became 50 compatible example payloads.

## PDF Extraction Tool Note

I compared liteparse against `pypdf` and the Stage 07 text while checking the
source PDFs.

ID `537` is the clearest case where liteparse helps. `pypdf` extracted only 647
characters, while liteparse extracted 43,238 characters and recovered evidence
around the anti-GAD negative result and the literature-review table. The output
was noisy and column/table text was interleaved, but it was useful for locating
terms that `pypdf` missed.

ID `623` is the clearest table case. `pypdf` extracted 20,063 characters and
liteparse extracted 30,372 characters. Both tools flattened the table row around
`Present 40 F SPS ... steroid pulse ... immunoadsorption ... thymectomy ...
radiation`. Liteparse was slightly cleaner around some OCR artefacts, for
example anti-GAD and thymoma wording, but it did not preserve table cells or
headers well enough to rely on it as a structured table extractor.

Practical conclusion: liteparse is a useful fallback for scanned or difficult
PDFs and for term hunting, especially where `pypdf` returns little text. It does
not extract tables well enough to replace exact Stage 07 spans or manual PDF
review for LangExtract examples.

## Paper-By-Paper Audit

### ID 524

Title: "Stiff person syndrome associated with lower motor neuron disease and
infiltration of cytotoxic T cells in the spinal cord."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 4 |
| Repaired exact span | 32 |
| Context/absence only | 1 |

Verdict: mostly correct after span repair. The clinical values are covered by
exact source text, including the normal neuroaxis imaging evidence for
`MRI_normal=0` and the malignancy workup/autopsy evidence for `tu_screening=0`.
The one non-promotable row is `ethnicity=white`: the case text says
`A previously healthy 67-year-old male presented`, but I found no patient
ethnicity evidence in the Stage 07 text or PDF-derived text. The row is covered
only as a discrepancy/context row and should not be promoted.

### ID 537

Title: "The occurrence of stiff person syndrome in a patient with thymoma: case
report and literature review."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 21 |
| Gold/source conflict or partial support | 2 |

Verdict: strong for most fields, but two gold rows conflict with the source. The
PDF/OCR text says the paraneoplastic panel included anti-GAD antibodies and that
the result was negative, so `antibody_status=GAD` is contradicted. The treatment
row is also only partly supported: the patient received chemotherapy with
complete radiographic resolution, while initial surgical treatment was deferred.
The gold value includes `resection`, which should not be promoted unless the
manual gold row is corrected or a later source passage is adjudicated.

Liteparse was materially better than `pypdf` for this PDF, but its table output
remained flattened and interleaved with body text.

### ID 551

Title: "A perplexing consult for pseudoseizures: stiff-man syndrome."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 3 |
| Repaired exact span | 19 |
| Needs human adjudication | 3 |
| Context/absence only | 1 |

Verdict: usable as a reviewed evidence pack, not clean as a promoted example.
Most demographics, diagnosis, antibody, symptom, and treatment values can be
covered by exact text after span repair. The distribution rows
`spasms_distribution_onset_multiple` and
`spasms_distribution_established_multiple` need adjudication because the source
mentions lower-left-extremity seizure activity, leg pain, falls, and kicking,
but does not cleanly encode the distal/proximal lower-extremity categories. The
`diagnosis_onset=functional` row is related to psychogenic seizure concern and
conversion disorder wording, but it is a coding judgement rather than a direct
extract. `immunotherapy=none` is absence-coded and should not be promoted as a
positive LangExtract example.

### ID 552

Title: "Stiff-person syndrome: a case report and review of the literature."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 6 |
| Repaired exact span | 18 |
| Context/absence only | 2 |

Verdict: mostly correct after span repair. The paper supports the core SPS
case, demographic, antibody, EMG, symptomatic treatment, and clinical-course
fields. `ethnicity=NA` is absence-coded because no ethnicity is stated.
`MRI_normal=NA` is also absence/context only: the source says CT findings of the
head, chest, and abdomen were normal, but does not give an MRI result.

### ID 554

Title: "Stiff-person syndrome treated with rituximab."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 2 |
| Repaired exact span | 5 |
| Gold/source conflict or partial support | 6 |

Verdict: not correct as a clean example until the gold values are adjudicated.
The source describes `A 41-year-old female patient`, while the gold row has
`age_description=32`. It says symptoms began 7 years before admission, which
implies onset around 34, not the gold `age_onset=30`. Follow-up/treatment effect
is stated as about 1 year, not 24 months. The patient treatment passage supports
rituximab at `375 mg/m2`; the text discusses plasma exchange and hyperimmune
globulin as literature options, not as treatments received by this patient. The
symptomatic-treatment evidence supports benzodiazepines/diazepam and botulinum
toxin, but not gabapentin or tizanidine.

The remaining rows are covered by exact spans, but this paper should not be used
as a standard example until the conflicting gold values are corrected or
explicitly accepted.

### ID 566

Title: "A case of glycine-receptor antibody-associated encephalomyelitis with
rigidity and myoclonus (PERM): clinical course, treatment and CSF findings."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 20 |
| Repaired exact span | 4 |

Verdict: correct and one of the strongest OpenAI pilot examples after span
repair. The source text supports the PERM/SPSD diagnosis, glycine receptor
antibody status, MRI normal coding, treatment details, CSF findings, and notes.
The four repaired rows now use exact spans rather than inferred or paraphrased
snippets. No gold/PDF conflict stood out in this audit.

### ID 573

Title: "Stiff person syndrome and pregnancy."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 5 |
| Repaired exact span | 7 |

Verdict: correct after span repair. This is a compact example with relatively
few gold fields, and all are covered by exact source text. I did not identify a
gold/PDF contradiction in the audited fields.

### ID 615

Title: "Anti-GAD antibodies and breast cancer in a patient with stiff-person
syndrome: a puzzling association."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 37 |
| Repaired exact span | 2 |
| Needs human adjudication | 4 |

Verdict: very strong for direct fields, but four inferred course/startle fields
need adjudication. The source supports the diagnosis, anti-GAD findings,
malignancy context, treatment, EMG, and MRI coding. `MRI_normal=0` is supported
because MRI of the whole neuraxis was unremarkable and the column dictionary
uses `0 = normal`. The rows `excessive_startle_onset=unspecified`,
`excessive_startle_established=unspecified`, `timecourse_onset=insidious`, and
`timecourse_subsequent=monophasic` depend on coding interpretation from related
phrases rather than direct extractable facts. They should be adjudicated before
promotion.

### ID 621

Title: "Stiff-person syndrome associated with cerebellar ataxia and high
glutamic acid decarboxylase antibody titer."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 9 |
| Repaired exact span | 23 |
| Gold/source conflict or partial support | 2 |

Verdict: source-rich but OCR-noisy. The case text supports SPS with cerebellar
ataxia, high anti-GAD antibodies, diabetes/autoimmunity, CMUA, diazepam
response, and MRI abnormality coding (`MRI_normal=1`, because asymmetric/mild
cerebellar atrophy is abnormal under the column dictionary). I repaired several
spans because the OCR text fuses words such as `womanexperienced` and
`showedcontinuous`; the final LangExtract JSON uses narrower token-aligned
spans.

Two gold rows conflict or over-specify the source. `age_description=58` is
contradicted by `A 46-year-old Japanese woman`. `diagnosis_onset_other` is coded
as `spinocerebellar_ataxia`, but the source says cerebellar ataxia was
diagnosed and gene analysis for familial ataxia/SCA found no abnormality. The
spinocerebellar-specific code should be adjudicated.

### ID 623

Title: "Stiff-person syndrome associated with invasive thymoma: a case report."

Field coverage:

| Type | Count |
|---|---:|
| Direct exact span | 5 |
| Repaired exact span | 17 |
| Gold/source conflict or partial support | 2 |
| Context/absence only | 1 |

Verdict: mostly source-backed, with three do-not-promote rows. The source/PDF
supports the SPS diagnosis, invasive thymoma, high anti-GAD antibody findings,
CSF antibody evidence, steroid pulse/immunoadsorption therapy, thymectomy, and
radiotherapy. It contradicts `age_description=42`, because the paper reports a
40-year-old female. It contradicts `antibody_status=seronegative`, because high
anti-GAD antibodies were detected in serum and CSF. `ethnicity=E_asia` is not
directly stated for the patient; Japanese context may be inferential, but the
case text only says `A 40-year-old female clerical worker`.

The original PDF table was useful for confirming the treatment summary, but both
`pypdf` and liteparse flatten it. Liteparse gives a slightly cleaner table row,
but neither gives reliable table structure.

## Promotion Recommendation

The OpenAI pilot is successful as an all-gold audit and span-repair workflow.
The generated JSON is compatible with LangExtract and covers every non-empty
manual gold field with exact source text. It should not be promoted wholesale as
a clean examples set.

For the next 10 or full 85-paper build, use this policy:

1. Promote rows with `candidate_for_promotion_after_spot_check` after quick
   human spot check.
2. Promote rows with `candidate_after_span_review` only after the repaired span
   is reviewed in `gold_source_span_plan_long.csv`.
3. Exclude rows with `do_not_promote_as_standard_langextract_example` unless the
   gold standard is corrected.
4. Hold rows with `review_before_promoting` until the field-specific coding rule
   is adjudicated.

This keeps the examples scientifically faithful while preserving an auditable
record of every gold value, including values where the source/PDF does not agree
with the current manual extraction.


## doc/reports/langextract_openai_pilot10_gold_pdf_discrepancies.md
# LangExtract OpenAI Pilot 10 Gold/PDF Discrepancy Evidence

Date: 2026-05-29

This note lists the OpenAI pilot fields where the manual gold value is
contradicted by the source/PDF, only partly supported, or not a directly
extractable positive fact. Exact spans are from the Stage 07 target-view JSONs,
which are the source texts used to build LangExtract examples. I also checked
the original PDFs for the high-impact conflicts and PDF-extraction concerns.

Related files:

- Span plan: `qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan.csv`
- Long span plan: `qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan_long.csv`
- OpenAI audit report: `doc/reports/langextract_openai_pilot10_gold_pdf_audit.md`
- LangExtract JSON: `examples/langextract_bootstrap/draft_langextract_examples_openai_pilot10_all_gold.json`

## Source Conflicts Or Partial Support

These rows should not be promoted as standard LangExtract examples unless the
manual gold value is corrected or a human reviewer adjudicates the coding rule.

| ID | Field | Manual gold | Exact source/PDF evidence | Audit decision |
|---|---|---|---|---|
| 537 | `antibody_status` | `GAD` | Stage 07 chars 3124-3204: `paraneoplastic panel which included anti-GAD antibodies; the result was negative`. Liteparse recovered the same PDF evidence; `pypdf` extracted too little text from this PDF to find it. | Contradicted. The patient appears anti-GAD negative, not GAD positive. |
| 537 | `other_treatment` | `resection and chemotherapy of thymoma with complete resolution of neurological symptoms` | Stage 07 chars 2129-2173: `an initial surgical treat- ment was deferred`; chars 2223-2253: `four-drug-regimen chemotherapy`; chars 3590-3638: `complete radiographic resolution of his thymoma`. | Partly supported. Chemotherapy and radiographic resolution are supported; resection is not supported by the audited source span. |
| 554 | `age_description` | `32` | Stage 07 chars 18-56: `A 41-year-old female patient presented`. | Contradicted. Source age is 41. |
| 554 | `age_onset` | `30` | Stage 07 chars 18-56: `A 41-year-old female patient presented`; chars 282-344: `beginning 7 years prior to admission with a progressive course`. | Contradicted or at least unsupported. The source implies onset around 34, not 30. |
| 554 | `FU_duration` | `24` | Stage 07 chars 2601-2656: `The effect of the treatment has lasted for about 1 year`. | Contradicted. Source follow-up/treatment effect is about 12 months, not 24. |
| 554 | `immunotherapy` | `steroids;IVIG;RXB` | Stage 07 chars 1551-1578: `we decided to try rituximab`; chars 2927-2954: `rituximab (dose 375 mg/m 2)`. The text discusses plasma exchange and hyperimmune globulin as literature options, not as treatment received by this patient. | Partly supported. Rituximab is supported; patient steroids/IVIG are not supported in the audited source text. |
| 554 | `immuntherapy_detail` | `steroids, IVIG: partial improvement. Rituximab 1000mg with improvement of stiffness and spasms, persistence of improvement for 3 months.` | Stage 07 chars 2927-2954: `rituximab (dose 375 mg/m 2)`; chars 2601-2656: `The effect of the treatment has lasted for about 1 year`. | Contradicted. Dose and duration conflict with source, and steroids/IVIG are not supported as patient treatments. |
| 554 | `sympt_treatment` | `benzo;gabapentin;tizanidine` | Stage 07 chars 2817-2872: `still needs to use benzodiazepines as symptomatic drugs`; chars 1187-1249: `intravenous diazepam and application of botulinum toxin type A`. | Partly supported. Benzodiazepine/diazepam is supported; gabapentin and tizanidine are not supported by the audited spans. |
| 621 | `age_description` | `58` | Stage 07 chars 13-63: `A 46-year-old Japanese womanexperienced clumsiness`. The missing space is an OCR artefact; the PDF-derived text still states a 46-year-old woman. | Contradicted. Source age is 46. |
| 621 | `diagnosis_onset_other` | `spinocerebellar_ataxia` | Stage 07 chars 198-273: `Cerebellar ataxia was diagnosed because of her right upper extremity ataxia`; chars 2077-2138: `Gene analysis for familial ataxia (SCA1, 2, 3, 6, 8) found no`. | Over-specific or contradicted. Cerebellar ataxia is supported; spinocerebellar/familial ataxia is not. |
| 623 | `age_description` | `42` | Stage 07 chars 9-49: `We report a case of a 40-year-old female`. The same age appears in the original PDF table row as `Present 40 F SPS`. | Contradicted. Source age is 40. |
| 623 | `antibody_status` | `seronegative` | Stage 07 chars 312-426: `High levels of anti-glutamic acid decarboxylase GAD antibodies were detected in both serum and cerebrospinal fluid`; chars 3512-3531: `Anti-GAD antibodies`. The original PDF and liteparse output also show high anti-GAD antibody evidence. | Contradicted. The patient is anti-GAD positive in serum and CSF, not seronegative. |

## Context Or Absence-Only Rows

These rows may be valid spreadsheet codes, but they are not good positive
LangExtract examples because the evidence is absence, context, or lack of a
statement rather than a direct extractable fact.

| ID | Field | Manual gold | Exact source evidence | Audit decision |
|---|---|---|---|---|
| 524 | `ethnicity` | `white` | Stage 07 chars 16-63: `A previously healthy 67-year-old male presented`. | No patient ethnicity found. Do not promote. |
| 551 | `immunotherapy` | `none` | Stage 07 chars 2656-2771: `diaze- pam (now at 15 mg every 6 hours), baclofen (5 mg t.i.d.), and physical therapy consults had proven help- ful`. | Absence-coded. The passage lists symptomatic therapy, not an explicit no-immunotherapy statement. |
| 552 | `ethnicity` | `NA` | Stage 07 chars 0-85: `A 49-year-old male presented with progressively worsening muscle rigidity and spasms`. | Absence-coded. No ethnicity is stated. |
| 552 | `MRI_normal` | `NA` | Stage 07 chars 956-1040: `Findings from computerized tomographies of the head, chest, and abdomen were normal`. | Absence/context only. CT is normal; MRI is not reported in the audited span. |
| 623 | `ethnicity` | `E_asia` | Stage 07 chars 1130-1179: `A 40-year-old female clerical worker was admitted`. | Not directly stated. Japanese context may be inferential, but patient ethnicity is not explicit. |

## Rows Needing Human Adjudication

These rows have related evidence but should be reviewed against the field
codebook before promotion.

| ID | Field | Manual gold | Exact source evidence | Audit decision |
|---|---|---|---|---|
| 551 | `spasms_distribution_onset_multiple` | `distal_LE;lumb_prox_LE` | Stage 07 chars 419-490: `one tonic- clonic seizure episode (mainly in the lower left extremities`; chars 1179-1229: `onset of leg pain and falls over the last 6 months`. | Related lower-extremity evidence, but distal/proximal coding is not cleanly extractable. |
| 551 | `diagnosis_onset` | `functional` | Stage 07 chars 855-931: `concerns that the patient may be experienc- ing psychogenic seizure episodes`; chars 3266-3287: `con- version disorder`. | Related psychiatric/functional framing, but coding timing needs adjudication. |
| 551 | `spasms_distribution_established_multiple` | `distal_LE;lumb_prox_LE` | Stage 07 chars 960-1002: `spells, kicking his legs on the bed boards`; chars 419-490: `one tonic- clonic seizure episode (mainly in the lower left extremities`. | Related lower-extremity evidence, but the exact distribution categories need review. |
| 615 | `excessive_startle_onset` | `unspecified` | Stage 07 chars 158-217: `Symptoms were amplified by emotional upset or when startled`. | Startle sensitivity is supported, but the `unspecified` coding needs rule review. |
| 615 | `timecourse_onset` | `insidious` | Stage 07 chars 0-92: `In January 1998 a 85-year- old woman complained of sustained involuntary muscle contractions`. | Onset is described, but "insidious" is not directly stated. |
| 615 | `timecourse_subsequent` | `monophasic` | Stage 07 chars 2410-2478: `Treatment was continued successfully with low-dose prednisone orally`; chars 2514-2551: `patient remained symp- tom free since`. | Possibly compatible, but monophasic course is an inferred code. |
| 615 | `excessive_startle_established` | `unspecified` | Stage 07 chars 158-217: `Symptoms were amplified by emotional upset or when startled`. | Startle sensitivity is supported, but the `unspecified` coding needs rule review. |

## PDF Extraction Notes

ID `537`: `pypdf` produced only 647 characters and missed the anti-GAD negative
and treatment passages. Liteparse produced 43,238 characters and recovered the
anti-GAD negative passage, chemotherapy wording, and the literature-review table,
but with noisy column interleaving. This makes liteparse useful for locating
evidence in this PDF, not sufficient for structured table extraction.

ID `623`: `pypdf` and liteparse both found the table-like row containing
`Present 40 F SPS ... steroid pulse ... immunoadsorption ... thymectomy ...
radiation`. Liteparse produced more text and slightly cleaner OCR around
anti-GAD and thymoma, but both tools flattened the table; neither preserved
reliable row/column structure.

These observations support using liteparse as a fallback search/extraction aid
for difficult PDFs. They do not change the promotion rule: LangExtract examples
should still use exact reviewed source spans, and table-derived values should be
manually checked.


## doc/reports/langextract_pilot10_gold_pdf_audit.md
# LangExtract Pilot 10 Gold And PDF Audit

Generated: 2026-05-29

## Scope

This report audits the 10 Gemini-generated LangExtract bootstrap examples in:

- `qa/validation/langextract_example_bootstrap/pilot_10/field_candidates.jsonl`
- `qa/validation/langextract_example_bootstrap/pilot_10/field_review.csv`
- `qa/validation/langextract_example_bootstrap/pilot_10/selected_rows.csv`

The comparison sources were:

- Manual gold standard: `examples/datasheet_examples_MC_Case_Report_Form.csv`
- Stage 07 target-view text: `qa/validation/stage07_single_case_codex_gold/.../target_views/{paper_id}/p1.json`
- Original PDFs: `data/pdf_original/*.pdf`, linked through `data/references/pdf_source_registry.csv`
- Page-indexed PDF text: `data/extraction_json/text/{paper_id}.json`

The original PDFs were present and text-extractable for all 10 records. I used direct `pypdf` extraction to verify that the PDF files are readable, and the existing page-indexed PDF text JSONs for page-level source passages. This is a text-level PDF audit, not a visual image/OCR audit.

## Assessment Definitions

- **Ready as-is** means the generated row preserves the gold value and has a source span that the validator accepted.
- **Repairable** means the gold value appears supported by the PDF, but the generated evidence is not yet suitable for a LangExtract example because the span is stitched, paraphrased, missing supporting snippets, affected by line-break or ligature differences, or otherwise not an exact reusable source span.
- **Adjudicate / do not promote** means the row exposes a probable gold/PDF conflict, a model value change, an unsupported absence-coded value, or a clinical inference that is too indirect to use as a training example without human correction.

The important distinction is that a clinically reasonable value is not automatically a good LangExtract example. LangExtract examples need exact, reviewable source text.

## Overall Findings

The 10-case pilot is useful as a review pack, but none of the 10 full examples should be promoted as a complete example without edits. There are usable individual rows, but every paper has either technical span failures, inferred fields that need exact supporting snippets, or at least one gold/PDF adjudication issue.

Across all 269 generated field rows:

| Metric | Count |
|---|---:|
| Total field rows | 269 |
| Model value exactly preserved the spreadsheet value | 268 |
| Model changed the spreadsheet value | 1 |
| `exact_quote` rows | 124 |
| `inferred_from_text` rows | 129 |
| `not_found` rows | 16 |
| Empty `extraction_text` rows | 37 |
| Validator `passed` rows | 45 |

Validator status distribution:

| Validator status | Count |
|---|---:|
| `passed` | 45 |
| `quote_not_found` | 80 |
| `inference_anchor_not_found` | 100 |
| `inference_snippet_not_found` | 23 |
| `inference_missing_supporting_snippets` | 4 |
| `needs_review` | 15 |
| `manual_value_changed` | 1 |
| `not_found_supports_manual_value_conflict` | 1 |

The dominant failure is not that Gemini changed gold values. The dominant failure is that Gemini often supplied evidence that is clinically relevant but not a valid exact source span. It also sometimes stitched non-contiguous passages with ellipses, relied on absence as evidence, or exposed a likely mismatch between the manual gold value and the PDF.

## Exact Source Span Plan

I added a field-level span workpack that covers every gold value:

- `qa/validation/langextract_example_bootstrap/pilot_10/gold_source_span_plan.csv`
- `qa/validation/langextract_example_bootstrap/pilot_10/gold_source_span_plan_long.csv`

The field-level CSV has one row per gold field. The long CSV has one row per proposed source span, which is easier to inspect manually. Every proposed span is an exact substring of the Stage 07 target-view text that LangExtract will receive.

| Span plan metric | Count |
|---|---:|
| Gold field rows covered | 269 |
| Proposed source spans | 432 |
| Rows with at least one source span | 269 |
| Rows whose proposed spans exactly match Stage 07 text offsets | 269 |

Coverage quality:

| Coverage class | Count | Meaning |
|---|---:|---|
| `direct_exact_span_ready` | 45 | The generated row already had an exact accepted span. |
| `covered_by_repaired_exact_source_text` | 209 | The gold value is covered by repaired exact source text and needs human span review before promotion. |
| `needs_human_adjudication` | 8 | The value is covered by source text, but the coding judgement needs review. |
| `derived_value_needs_coding_rule` | 3 | The value is derived from source text, not literally stated. |
| `context_or_absence_only_not_direct_extraction` | 4 | The source gives only contextual or absence evidence, not a direct extraction. |

LangExtract recommendation:

| Recommendation | Count |
|---|---:|
| `candidate_for_promotion_after_spot_check` | 45 |
| `candidate_after_span_review` | 209 |
| `review_before_promoting` | 8 |
| `review_before_promoting_derived_value` | 3 |
| `do_not_promote_as_standard_langextract_example` | 4 |

The all-gold draft example file now splits overlapping or duplicate spans into
77 LangExtract-compatible example payloads from the 10 source documents. Strict
LangExtract prompt alignment was run with fuzzy matching disabled and lesser
matches disallowed: 432 extractions, 0 alignment issues, and 0 attribute type
errors.

For LangExtract best practice, the `extraction_text` should be the shortest exact original text that supports the field. The spreadsheet value should be kept as an attribute when it is a coded, normalised, semicolon-delimited, or derived value. If a value needs multiple non-contiguous pieces of original text, the long CSV proposes multiple exact spans rather than forcing a stitched quote.

## Source PDF Inventory

| ID | Study | PDF path | PDF pages |
|---:|---|---|---:|
| 75 | Kuhn 1995 | `data/pdf_original/75_Kuhn-1995-Stiff-man syndrome_ case report.pdf` | 4 |
| 92 | Dropcho 1996 | `data/pdf_original/92_Dropcho-1996-Antiamphiphysin antibodies with s.pdf` | 9 |
| 155 | Hummel 1998 | `data/pdf_original/155_Hummel-1998-Humoral and cellular immune parame.pdf` | 5 |
| 162 | Hirsch 1998 | `data/pdf_original/162_Hirsch Severe insulin resistance in a patient with type 1 diabetes and stiff-man syndrome treated with insulin lispro.pdf` | 6 |
| 187 | Khanlou 1999 | `data/pdf_original/187_Khanlou Long-term Remission of Refractory Stiff-Man Syndrome After Treatment With Intravenous Immunoglobulin.pdf` | 2 |
| 197 | Butler 2000 | `data/pdf_original/197_Butler Autoimmunity to Gephyrin in Stiff-Man Syndrome.pdf` | 6 |
| 395 | Tanaka 2005 | `data/pdf_original/395_Tanaka Stiff Man Syndrome With Thymoma.pdf` | 3 |
| 427 | LaSpada 2006 | `data/pdf_original/427_157-03-09_La_Spada.pdf` | 3 |
| 439 | Gutmann 2006 | `data/pdf_original/439_4270-Article Text-15286-1-10-20200722.pdf` | 3 |
| 512 | O'Sullivan 2009 | `data/pdf_original/512_O'Sullivan et al. - 2009 - A case of stiff-person syndrome, type 1 diabetes, .pdf` | 3 |

## Paper-Level Summary

| ID | Fields | Strictly passed | Main verdict |
|---:|---:|---:|---|
| 75 | 21 | 1 | Not correct as a full example. Many values are clinically plausible; onset timing remains ambiguous, and the startle trigger value has been corrected to remove noise. |
| 92 | 27 | 0 | Not correct as-is. Good Patient 3 source material, but no field passed technically; `age_description` is now corrected to 67 and CMUA still needs policy review. |
| 155 | 22 | 4 | Not correct as-is. Several core fields are repairable; antibody status is now corrected to `GAD;islet_cell` and immunotherapy to `steroids`. |
| 162 | 28 | 3 | Not correct as-is. Demographics pass; `onset_to_established` is now `NA`, while multiple titre fields remain derived rather than exact PDF text. |
| 187 | 18 | 6 | Best of the first half, but still not complete. Most values are supported; `MRI_normal=0` is supported because the codebook defines `0 = normal`. |
| 197 | 33 | 3 | Not correct as-is. Several source-supported rows need span repair; `time_to_diagnosis` is now corrected to 0.17 years. |
| 395 | 28 | 10 | Useful but not correct as full example. Many exact biomedical rows pass, and `age_description` is now corrected to 57. |
| 427 | 33 | 4 | Clinically rich but technically poor. Most inferred rows have empty extraction text and need exact snippet reconstruction. |
| 439 | 28 | 2 | Not correct as-is. The PDF supports many values, but OCR hyphenation breaks spans and `immunotherapy=none` is not a positive extractable fact. |
| 512 | 31 | 12 | Stronger than most, but still incomplete. Several rows pass; mRS and some inferred treatment/autoimmunity rows need repair or adjudication. |

## Detailed Audit By Example

### ID 75 - Kuhn 1995

Verdict: **not correct as a full example; partially repairable.**

Strictly ready as-is:

- `age_description`

Repairable fields where the gold value appears broadly supported but the example evidence needs exact span repair:

- `sex`, `ethnicity`
- `first_manifestation`, `spasms_distribution_onset`, `spasms_distribution_onset_multiple`
- `other_symptoms_onset`, `spasms_distribution_established`, `excessive_startle_established`
- `antibody_status`, `CSF_antibody`, `CMUA`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`

Adjudicate / do not promote:

- `age_onset`, `time_to_diagnosis`, and `onset_to_established`: the paper contains multiple duration anchors. The abstract says a "two-year history"; the case narrative says similar symptoms over the "preceding year"; the medical record says symptoms "for about three years". The generated reasoning uses only the one-year anchor, so it is too fragile for a training example unless the gold rule is explicitly documented.
- Resolved correction: `excessive_startle_established_multipleother` is now `tactile;speaking`. The PDF says the episodes were triggered by opening the door, speaking, and tactile stimuli, "but not by loud noises."

Key PDF evidence checked:

- Page 1: "A 39-year-old black woman..."
- Page 1: "two-year history of right leg spasms and low back pain..."
- Page 2: "similar but less intense low back pains and severe right leg spasms over the preceding year."
- Page 2: "history of low back pain with spasms and right lower-extremity spasms for about three years."
- Page 2: "triggered by external stimuli ... opening the door, speaking, and tactile stimuli, but not by loud noises."
- Page 2: lumbar puncture for anti-GAD antibodies with a later positive result.

### ID 92 - Dropcho 1996, Patient 3

Verdict: **not correct as-is; source-rich but technically unusable without repair.**

Strictly ready as-is:

- None.

Repairable fields where the PDF appears to support the gold value but the generated span is not valid as an exact example:

- `age_onset`, `first_manifestation`, `first_manifestation_multiple`
- `stiffness_distribution_onset`, `other_symptoms_onset`
- `timecourse_onset`, `timecourse_subsequent`, `onset_to_established`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `other_symptoms_established`, `antibody_status`, `antibody_tests`, `antibody_testsystem`
- `CSF_status`, `tu_screening`, `tu_screening_abnormal`
- `immunotherapy`, `immuntherapy_detail`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_detail`, `other_treatment`
- `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- Resolved correction: `age_description` is now `67`, matching the PDF statement that Patient 3 was a 67-year-old man in September 1993.
- `CMUA=0`: this is an absence-coded value. The source describes polyneuropathy and other neurophysiology, but not a positive extractable statement of absent CMUA. It should not be used as an example unless the absence rule is separately reviewed.

Key PDF evidence checked:

- Page 2: "Patient 3. In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."
- Page 2: over the next 6 weeks, rigidity spread to abdominal and thoracic muscles including diaphragm; respiratory difficulty developed.
- Page 2: "He was maintained on pancuronium, ventilatory support, and heavy sedation..."
- Page 2: subcarinal mass biopsy showed SCLC; intravenous IgG, prednisone, and cisplatin plus etoposide were given.
- Page 4: Patient 3's antibody titre fell by November 1994, when he was in complete remission from SCLC and had made a partial neurological recovery.

### ID 155 - Hummel 1998

Verdict: **not correct as-is; several strong rows, with the key gold conflicts now corrected.**

Strictly ready as-is:

- `age_description`
- `first_manifestation_multiple`
- `diagnostic_criteria`
- `stiffness_distribution_established`

Repairable fields:

- `sex`
- `included_diagnosis`
- `spasms_distribution_established`, `spasms_distribution_established_other`
- `excessive_startle_established`
- `CSF_status`, `CSF_antibody`, `CSF_antibody_titre`
- `CMUA`
- `immuntherapy_detail`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- `first_manifestation=multiple`: the paired field `first_manifestation_multiple=stiffness` only names stiffness. The PDF supports rigidity/stiffness, but the "multiple" summary value needs review.
- Resolved correction: `antibody_status` is now `GAD;islet_cell`. The source supports GAD and islet cell antibodies, while IA-2 antibodies were undetectable.
- Resolved correction: `immunotherapy` is now `steroids`. Prednisolone is supported; direct page-by-page PDF search found no IVIG/immunoglobulin treatment reference for this paper.

Key PDF evidence checked:

- Page 1 abstract: immune reactivity to GAD and IA-2 was studied.
- Page 1 abstract: raised GAD antibodies were detected; antibodies to IA-2 were undetectable; weak T-cell responses to GAD and IA-2 were seen.
- Page 2: 51-year-old man fulfilled Lorish criteria.
- Page 2: CSF cell count and protein were normal; GAD antibodies were not measured in CSF.
- Page 3: prednisolone regimen appears in the treatment figure/text.

### ID 162 - Hirsch 1998

Verdict: **not correct as-is; demographics are good, many derived fields are not example-safe.**

Strictly ready as-is:

- `age_description`
- `sex`
- `ethnicity`

Repairable fields:

- `first_manifestation`, `included_diagnosis`, `early_symptoms`
- `other_symptoms_onset`, `diagnosis_onset`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `other_symptoms_established`
- `antibody_status`, `antibody_units`, `antibody_tests`
- `CSF_antibody`
- `CMUA`
- `MRI_normal`
- `immunotherapy`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`

Adjudicate / do not promote:

- `time_to_diagnosis=2.5`: Gemini correctly marked this as not found. The PDF does not provide a clean direct time-to-diagnosis statement matching 2.5.
- `stiffness_distribution_onset=axial`: the patient history is broader and does not clearly isolate axial onset.
- Resolved correction: `onset_to_established` is now `NA`. The PDF's "28 months" refers to glycaemic control after insulin lispro, not to SPS onset-to-established interval.
- `antibody_titre=3.513888889` and `CSF_antibody_titre=0.388888889`: the PDF gives titres as 1:5000 and 1:500. The decimal values are transformations, not extractable source text.
- `immunotherapy=none`: this may be true as an absence-coded gold value for SPS immunotherapy, but absence is not a positive extractable example.

Key PDF evidence checked:

- Page 1: "The patient is a 33-year-old Caucasian woman..."
- Page 3: summer 1994 abdominal pain, thought to be pancreatitis.
- Page 4: GAD65 serum end-point titre 1:5000 and CSF GAD65 end-point titre 1:500.
- Page 4: dramatic response to oral diazepam; EMG read as normal but confounded by diazepam and baclofen.
- Page 2: antimicrosomal antibodies positive at 1:40, supporting Hashimoto's thyroiditis.

### ID 187 - Khanlou 1999

Verdict: **mostly clinically supported, but not ready as a complete LangExtract example.**

Strictly ready as-is:

- `age_description`
- `sex`
- `time_to_diagnosis`
- `spasms_distribution_established`
- `spasms_distribution_established_multiple`
- `immunotherapy`

Repairable fields:

- `included_diagnosis`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `excessive_startle_established`, `excessive_startle_established_multipleother`
- `antibody_status`
- `CMUA`
- `immuntherapy_detail`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_detail`

Additional coding note:

- `MRI_normal=0`: the source says magnetic resonance imaging of the head and spinal cord was normal. This supports the gold value because the column dictionary defines `0 = normal` and `1 = abnormal`.

Key PDF evidence checked:

- Page 1: "A 43-year-old man" with a 9-year history.
- Page 1: findings include back rigidity/stiffness, lordosis, difficulty ambulating, frequent spasms affecting both legs and neck.
- Page 1: MRI of head and spinal cord was normal.
- Page 1: serum anti-GAD antibody assay was positive.
- Page 1-2: diazepam and baclofen had limited benefit; IVIg led to complete resolution and durable remission.

### ID 197 - Butler 2000

Verdict: **not correct as-is; multiple adjudication flags.**

Strictly ready as-is:

- `age_description`
- `sex`
- `tu_screening_abnormal`

Repairable fields:

- `age_onset`
- `first_manifestation`, `first_manifestation_multiple`
- `included_diagnosis`
- `early_symptoms`, `overview_established`
- `stiffness_distribution_onset`, `stiffness_distribution_onset_multiple`
- `spasms_distribution_onset`
- `stiffness_distribution_established`, `stiffness_distribution_established_other`
- `spasms_distribution_established`
- `excessive_startle_established`, `excessive_startle_established_multipleother`
- `other_symptoms_established`
- `antibody_status`, `antibody_status_other`, `antibody_tests`, `antibody_testsystem`
- `CSF_status`, `CSF_antibody`
- `tu_screening`
- `sympt_treatment`, `sympt_treatment_effect`
- `other_treatment`

Adjudicate / do not promote:

- Resolved correction: `time_to_diagnosis` is now `0.17`, based on the PDF's 2-month history.
- `spasms_distribution_onset_multiple=axial;bulbar`: the source mentions face and both legs for cramps/spasms. Bulbar/face is supported; axial is not clearly supported by the cited source passage.
- `spasms_distribution_established=gerneralised`: the gold value itself contains a spelling error, and the generated evidence does not cleanly establish generalised spasms.
- `CMUA=1`: the PDF describes low-firing frequency of normal units at rest, but the candidate did not find a clear CMUA statement.
- `MRI_normal=0`: the PDF explicitly says brain, cervical, and lumbar MRIs were normal. This supports the gold value under the column dictionary coding of `0 = normal`.
- `sympt_treatment_detail`: this is the only value-change row in the pilot. The gold says "Both the stiffness spasms lessened..." while Gemini changed the value to "Both the stiffness spasms lessened..." with spacing normalisation in `model_spreadsheet_value`, and the source itself says "Both the stiffness and spasms lessened markedly..." The source likely exposes a gold typo, but the candidate cannot be promoted because it did not preserve the gold value exactly.

Key PDF evidence checked:

- Page 2: "A 58-year-old male... admitted in June of 1998 with a 2 month history..."
- Page 2: progressive gait disturbance, dysarthria, dysphagia due to muscle stiffness and spasms.
- Page 2: brain, cervical, and lumbar MRIs were normal.
- Page 2: CSF and serum contained high-titre autoantibodies directed against gephyrin.
- Page 2: oral diazepam 20 mg/day; stiffness and spasms lessened markedly; walking and speech improved.
- Page 2: mediastinal tumour was undifferentiated carcinoma of undetermined origin.

### ID 395 - Tanaka 2005

Verdict: **partly strong, but not correct as full example because of age and ethnicity issues.**

Strictly ready as-is:

- `sex`
- `included_diagnosis`
- `stiffness_distribution_onset`
- `excessive_startle_established`
- `antibody_status`
- `antibody_titre`
- `antibody_units`
- `immunotherapy`
- `sympt_treatment`
- `sympt_treatment_detail`

Repairable fields:

- `age_onset`
- `first_manifestation`
- `early_symptoms`, `overview_established`
- `timecourse_onset`, `timecourse_subsequent`
- `onset_to_established`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `spasms_distribution_established`
- `other_symptoms_established`
- `course_treatment`
- `antibody_tests`
- `exteroceptive_refl`
- `tu_screening`, `tu_screening_abnormal`

Adjudicate / do not promote:

- Resolved correction: `age_description` is now `57`, matching the PDF's repeated 57-year-old case description.
- `ethnicity=E_asia`: the PDF gives Japanese institutional context but does not state patient ethnicity. This is an inferred demographic category, not a text-grounded extraction.
- `onset_to_established=2`: the source describes symptoms beginning in the upper limbs and deteriorating into trunk/lower-limb stiffness 1 month after onset, then recurrence 1 month after surgery. The gold value may be defensible under a separate coding rule, but the candidate evidence does not make the rule clear.

Key PDF evidence checked:

- Page 1: "We treated a 57-year-old woman..."
- Page 1: symptoms began as tightness in upper limbs and deteriorated into trunk/lower-limb stiffness 1 month after onset.
- Page 1: serum anti-GAD antibody 16,800 U/mL.
- Page 2: chest CT showed anterior mediastinal tumour considered thymoma; pathology was lymphocytic type, WHO B1.
- Page 2: severe bulbar symptoms with ptosis/dysphagia; symptoms relieved after intravenous immunoglobulin.

### ID 427 - LaSpada 2006

Verdict: **clinically useful source, but generated example is technically poor.**

Strictly ready as-is:

- `age_description`
- `other_symptoms_onset`
- `antibody_titre`
- `antibody_units`

Repairable fields:

- Most remaining fields are likely repairable because the PDF contains relevant evidence, but Gemini frequently left `extraction_text` empty and put long evidence in `supporting_snippets_json`. The current validator flags 21 rows as `inference_snippet_not_found`, largely because snippets contain PDF ligatures, line-break artefacts, or are not exact contiguous spans.

Repairable fields include:

- `sex`, `age_onset`
- `first_manifestation`, `first_manifestation_multiple`
- `included_diagnosis`, `included_diagnosis_specify`
- `early_symptoms`
- `stiffness_distribution_onset`, `stiffness_distribution_onset_multiple`
- `spasms_distribution_onset`, `spasms_distribution_onset_multiple`
- `timecourse_subsequent`
- `excessive_startle_established`, `excessive_startle_established_multipleother`
- `antibody_status`, `antibody_status_other`, `antibody_tests`
- `CSF_status`, `CMUA`, `MRI_normal`
- `immunotherapy`, `immuntherapy_detail`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- No single gold value stood out as clearly contradicted in the same way as IDs 75, 155, 197, 395, or 439. The reason this example fails is technical: it is not currently a LangExtract-ready example because most rows do not carry exact extractable spans.

Key PDF evidence checked:

- Page 1: 49-year-old housewife observed in September 2002.
- Page 1: two months of dorsiflexion weakness of the left foot and painful contraction involving abdominal/paravertebral muscles and proximal left lower limb.
- Page 1: left foot drop.
- Page 2: 10 mg oral diazepam three times daily led to no significant improvement.
- Page 2: total dose 2 g/kg IVIG over 5 days; dorsiflexion improved and conduction block resolved.
- Page 3: monthly IVIG plus diazepam, cyclosporine, baclofen, and sodium valproate reduced painful contractures.

### ID 439 - Gutmann 2006

Verdict: **not correct as-is; many spans need repair and at least one absence-coded field should not be promoted.**

Strictly ready as-is:

- `age_description`
- `sex`

Repairable fields:

- `age_onset`
- `first_manifestation`, `first_manifestation_multiple`
- `included_diagnosis`
- `early_symptoms`
- `stiffness_distribution_onset`, `stiffness_distribution_onset_multiple`
- `other_symptoms_onset`, `other_symptoms_onset_auto`
- `timecourse_onset`, `timecourse_subsequent`
- `stiffness_distribution_established`
- `other_symptoms_established`
- `antibody_status`, `antibody_tests`
- `CSF_status`
- `tu_screening`, `tu_screening_abnormal`
- `sympt_treatment`, `sympt_treatment_effect`
- `other_treatment`
- `autoimmunity`, `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- `immunotherapy=none`: this is an absence-coded field. The model marked `not_found` but also set `supports_manual_value=TRUE`, creating an internal conflict. It should not become a positive training example.
- `MRI_normal=0`: the source says lumbar puncture, cerebral angio-CT, and MRI were all normal. This supports the gold value under the column dictionary coding of `0 = normal`.
- `autoimmunity` and `autoimmunity_specify`: the candidate links these to gonarthritis and heterotopic ossification. That may be a coding decision, but it is not a clean direct autoimmune diagnosis in the source.

Key PDF evidence checked:

- Page 1: "A 55 year-old woman..."
- Page 1: three-day history of back pain and trunk stiffness.
- Page 1: progression to leg stiffness, dysphagia, respiratory insufficiency, intubation, and ventilation.
- Page 1: lumbar puncture, cerebral angio-CT, and MRI were all normal; anti-GM1 and anti-GAD were negative.
- Page 2: later CT-guided biopsy revealed classical nodular sclerosis Hodgkin lymphoma.
- Page 2: ABVD polychemotherapy for 8 cycles.

### ID 512 - O'Sullivan 2009

Verdict: **stronger than most, but not complete; several inferred rows need repair.**

Strictly ready as-is:

- `age_description`
- `sex`
- `first_manifestation_multiple`
- `included_diagnosis`
- `stiffness_distribution_onset`
- `other_symptoms_onset`
- `antibody_status_other`
- `antibody_titre`
- `antibody_units`
- `CSF_antibody`
- `CSF_antibody_titre`
- `sympt_treatment_detail`

Repairable fields:

- `age_onset`
- `first_manifestation`
- `timecourse_subsequent`, `onset_to_established`
- `stiffness_distribution_established`
- `spasms_distribution_established`
- `course_treatment`
- `antibody_status`, `antibody_tests`
- `CSF_status`
- `MRI_normal`
- `immunotherapy`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`
- `notes`

Adjudicate / do not promote:

- `established_mRS=5`: I found no mRS score in the PDF text. This is an inferred disability score and should not be used as a LangExtract example unless the coding rule and evidence are explicit.
- `MRI_normal=0`: the candidate cites "MRI scans of the brain and spinal cord were normal." This supports the gold value under the column dictionary coding of `0 = normal`.

Key PDF evidence checked:

- Page 1: 41-year-old man with fall and 4-week history of lower back stiffness and bilateral leg weakness.
- Page 1: serum anti-GAD positive at 105 U/ml.
- Page 2: CSF was acellular with normal protein but anti-GAD antibodies strongly positive at 61 U/ml.
- Page 2: diazepam infusion, plasmapheresis, and later IVIg to good clinical effect.
- Page 2: mycophenylate as immunomodulatory agent; symptoms improved greatly and he returned to work.

## Cross-Example Issues

### 1. Evidence spans are often not LangExtract-ready

Many rows use clinically sensible text but fail as examples because the evidence is not a contiguous exact span. Common problems:

- Multi-sentence stitched evidence in a single `extraction_text`.
- Ellipses joining non-contiguous passages.
- PDF line-break and hyphenation artefacts.
- Ligatures such as `fi`/`fl` represented differently across text layers.
- Inferred rows with no `supporting_snippets`.
- Empty `extraction_text` with long snippets instead.

These rows may still be useful for human review, but they should not be promoted without exact span repair.

### 2. Absence-coded values are poor examples

Rows such as `CMUA=0`, `immunotherapy=none`, and `established_mRS=5` are not straightforward text extractions. Some require absence-of-evidence or clinical scoring. These should either be excluded from LangExtract examples or represented only after an explicit, reviewed coding policy is added.

### 3. Discrepancy answers have been implemented

The seven pilot discrepancies documented in `langextract_pilot10_gold_pdf_discrepancies.md` have been applied to the manually reviewed case-report CSV, the span plans, and the regenerated all-gold LangExtract examples:

- ID 75: `excessive_startle_established_multipleother` is now `tactile;speaking`.
- ID 92: `age_description` is now `67`.
- ID 155: `antibody_status` is now `GAD;islet_cell`; `immunotherapy` is now `steroids`.
- ID 162: `onset_to_established` is now `NA`.
- ID 197: `time_to_diagnosis` is now `0.17`.
- ID 395: `age_description` is now `57`.

Remaining high-priority adjudication examples:

- ID 75: onset duration still has 1-year, 2-year, and 3-year anchors.
- ID 162: decimal titre values are derived from ratios.
- ID 197: `sympt_treatment_detail` exposes a likely typo in the manual gold text.

### 4. Prompting and validation should separate two questions

The current review pack mixes:

1. Is the gold value clinically supported by the article?
2. Is the generated evidence a valid exact LangExtract example?

Those are different gates. A future review sheet should have separate columns, for example:

- `gold_supported_by_pdf`
- `gold_needs_adjudication`
- `span_exact_in_stage07_text`
- `span_exact_in_pdf_text`
- `example_ready_for_langextract`

## Recommended Next Step

Do not promote `draft_langextract_examples.json` yet. Instead:

1. Use `gold_source_span_plan.csv` as the review worklist; it covers all 269 gold values.
2. Accept the 45 `direct_exact_span_ready` rows after a spot check.
3. Review the 199 `covered_by_repaired_exact_source_text` rows and replace the original model evidence with the proposed exact spans.
4. Adjudicate the 25 non-standard rows before promotion: conflicts, derived values, context-only values, and values needing a coding decision.
5. Re-run the promotion step only after `review_status=accepted` is set on rows that are both gold-correct and span-correct.

My judgement is that the pilot was successful as a stress test of the bootstrapping workflow, but not as a final example set. It surfaced exactly the problems the human review layer needs to catch before LangExtract training examples become canonical.

## Commands And Checks Used

Representative local checks:

```powershell
Import-Csv qa\validation\langextract_example_bootstrap\pilot_10\field_review.csv |
  Group-Object validator_status |
  Sort-Object Name |
  Select-Object Name,Count
```

```powershell
Import-Csv data\references\pdf_source_registry.csv |
  Where-Object { @('75','92','155','162','187','197','395','427','439','512') -contains $_.covidence_id } |
  Select-Object covidence_id,study,title,pdf_path_relative,download_status
```

```powershell
.\.venv\Scripts\python.exe -c "import pypdf; print(pypdf.__version__)"
```

Direct PDF text extraction was also run over all 10 source PDFs to confirm page counts and text readability.


## doc/reports/langextract_pilot10_gold_pdf_discrepancies.md
# LangExtract Pilot 10 Gold/PDF Discrepancy Note

Generated: 2026-05-29

This note covers the seven pilot-10 gold fields where the original gold value
was contradicted or only partially supported by the Stage 07 text extracted from
the original PDF. The answers below have been implemented in the manually
reviewed case-report CSV, span plans, and regenerated LangExtract examples.

Important coding correction: `MRI_normal=0` is not a discrepancy. The column
dictionary defines `0 = normal` and `1 = abnormal`, so the normal-MRI source
passages for IDs 187, 197, 439, and 512 support the gold value.

## ID 75 - `excessive_startle_established_multipleother`

Original gold value: `noise;tactile;speaking`

Source: `qa/validation/stage07_single_case_codex_gold/batch000/json/target_views/75/p1.json`, chars 4563-4718

```text
These episodes of opisthotonos seemed trig- 
gered by external stimuli (e.g., by opening the door, 
speaking, and tactile stimuli, but not by loud noises).
```

Audit note: speaking and tactile stimulation are supported, but noise is
directly contradicted by "but not by loud noises". Do not promote this field
until the gold value is adjudicated.

Implemented value: `tactile;speaking`

## ID 92, Case 3 - `age_description`

Original gold value: `68`

Source: `qa/validation/stage07_single_case_codex_gold/batch000/json/target_views/92/p1.json`, chars 10838-10976

```text
In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.
```

Audit note: the source describes Patient 3 as 67 years old. The gold row also
has `age_onset=67`, which is supported. I did not find an exact 68-year-old
case-description span in the Stage 07 text, so `age_description=68` needs
adjudication or a documented derivation rule.

Implemented value: `67`

## ID 155 - `antibody_status`

Original gold value: `GAD;IA-2`

Source: `qa/validation/stage07_single_case_codex_gold/batch002/json/target_views/155/p1.json`, chars 1169-1288, 4512-4563, and 4618-4715

```text
The patient had GAD antibodies and islet
cell antibodies, but no other organ specific or
non-organ specific antibodies.
```

```text
IA-2As were undetectable in all
samples (figure A).
```

```text
Before immunosuppressive therapy T cells
responded to GAD65 (SI=4) and IA-2
(SI=6. 2) (figure B).
```

Audit note: GAD antibody positivity is supported. IA-2 antibody positivity is
contradicted by "IA-2As were undetectable"; the source supports only a cellular
T-cell response to IA-2. Do not promote IA-2 as an antibody-status example
without gold/schema adjudication.

Implemented value: `GAD;islet_cell`

## ID 155 - `immunotherapy`

Original gold value: `steroids;IVIG`

Source: `qa/validation/stage07_single_case_codex_gold/batch002/json/target_views/155/p1.json`, chars 1798-1980. I also checked the original PDF directly:
`data/pdf_original/155_Hummel-1998-Humoral and cellular immune parame.pdf`.

```text
Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone
from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg.
```

Implemented value: `steroids`

Additional PDF evidence, page 3:

```text
The first dose of prednisolone (2×250 mg daily) injected intravenously led to a
complete disappearance of previously described symptoms within 3–4 hours.
```

Audit note: steroid therapy is supported. I searched the original PDF
page-by-page for `IVIG`, `IV Ig`, `intravenous immunoglobulin`,
`immunoglobulin`, `immune globulin`, `gamma globulin`, and `gammaglobulin`; no
IVIG/immunoglobulin treatment reference was found. The only `IgG` hits were
methodological or unrelated text: `ICA-IgG` in the antibody assay methods on
page 2, and a separate shingles "Neurological Picture" item on page 5. The IVIG
part of the gold value is therefore unsupported by the available PDF text.

## ID 162 - `onset_to_established`

Original gold value: `28`

Implemented value: `NA`. If the sheet later allows inferred approximate durations, about 44 months would be defensible, with an uncertainty range of roughly 42-45 months depending on whether onset is anchored to summer 1994 abdominal pain or fall 1994 lower-extremity pain/weakness.

Source: `qa/validation/stage07_single_case_codex_gold/batch002/json/target_views/162/p1.json`, chars 5673-5792, 6037-6117, 9186-9275, 9761-9841, 9842-10124, and 10337-10486

```text
Also during the summer of 1994 she developed
several episodes of intermittent abdominal pain
which required evaluation.
```

```text
By the fall of 1994, she
had also developed lower extremity pain and weak-
ness.
```

```text
On November 16 she was admitted to
the University of Washington Clinical Research
Center.
```

```text
She
continued with meticulous glycemic control for
the next 28 months (Table 1).
```

```text
Although her blood glucose control improved,
her abdominal pain and lower extremity weakness
continued. In addition, she developed intense pain
in her upper and lower extremities. She also com-
plained of rigidity and spasms of her proximal
limb muscles making ambulation difﬁcult.
```

```text
a dramatic response with im-
provement of her pain and stiffness with 10 mg of
oral diazepam conﬁrmed the diagnosis of stiff
man syndrome (SMS) [2].
```

Audit note: the 28-month span is not onset-to-established disease. It is the
duration of glycaemic control after insulin lispro, starting from the 16 November
1995 admission. SPSD-relevant symptoms began in summer/fall 1994, while the
fully established SPSD/diagnosis evidence appears after the 28-month insulin
lispro follow-up, approximately March 1998. That gives an inferred onset-to-
established interval of about 42-45 months. Because the PDF does not state an
exact month-count for SPSD establishment, `NA` is the safest strict extraction.

## ID 197 - `time_to_diagnosis`

Original gold value: `0.25`

Source: `qa/validation/stage07_single_case_codex_gold/batch003/json/target_views/197/p1.json`, chars 0-195

```text
A 58-year-old male (patient 861 of our caseload) was
admitted in June of 1998 with a 2 month history of progressive gait disturbance, dysarthria, and dysphagia
due to muscle stiffness and spasms.
```

Audit note: the source states a 2-month history. That is about 0.17 years, not
0.25 years, unless a separate rounding or diagnosis-date rule is being applied.

Implemented value: `0.17`

## ID 395 - `age_description`

Original gold value: `59`

Source: `qa/validation/stage07_single_case_codex_gold/batch005/json/target_views/395/p1.json`, chars 0-136, 1298-1363, and 0-53

```text
We treated a 57-year-old woman with a type
B1 thymoma, based on the World Health Organization
classiﬁcation, who had stiff man syndrome.
```

```text
A 57-year-old woman was admitted to our hospital in
February 2001
```

```text
We treated a 57-year-old woman with a type
B1 thymoma
```

Audit note: the PDF text repeatedly describes the patient as 57 years old. I
found no exact support for `age_description=59` in the Stage 07 text, so this
gold value should be adjudicated before promotion.

Implemented value: `57`


## examples/langextract_bootstrap/draft_langextract_examples_all_gold.json
[
  {
    "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
    "paper_id": "155",
    "case_id": "",
    "example_part_index": 1,
    "example_part_count": 3,
    "target_view_json_path": "qa\\validation\\stage07_single_case_codex_gold\\batch002\\json\\target_views\\155\\p1.json",
    "text": "51 year old man. He fulfilled all criteria established by Lorish et al’ as (1) prodome of rigidity and stiffness in axial muscles, (2) progression of rigidity and stiffness to include proximal limb muscles, (3) deforming of the spine, in this case lordosis, (4) superimposed spasms precipitated by sudden movement and noise, (5) normal muscle strength and sensory examination, (6) normal intellect, (7) the classic EMG findings (continuous normal motor unit firing, despite the patient’s intention to relax), and (8) a favourable response to oral administration of diazepam. One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test and was diagnosed as having insulin dependent diabetes mellitus. Partial strumectomy had been performed in 1984, but today it is not possible to determine whether the hyperthyroidism was caused by Graves‘ disease or by an adenoma of the thyroid gland. A kidney biopsy performed because of recurrent microhaematuria disclosed the rare syndrome of “thin basal membranes (200 nm)”. This is the first description of a patient with stiff-man syndrome with this extremely rare nephropathy. The patient had GAD antibodies and islet cell antibodies, but no other organ specific or non-organ specific antibodies. Cell count and protein content in the CSF were normal without oligoclonal bands. GAD antibodies were not measured in CSF samples. The HLA type of the patient is HLA-A1, 23; B8, 50; DR3, 3; DQA1*0501, 0501; DQB1*0201, 0201. IMMUNOSUPPRESSIVE THERAPY The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year. Diazepam was then no longer effective and the treatment was changed to baclofen (3 20-25 mg/day), also a GABAergic agonist. Clinical improvement was seen, but lasted only four weeks. Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg. Currently, after 400 days of therapy the patient has good mobility and is without rigidity with 5 mg prednisolone and 3 5 mg diazepam daily (figure A and B). An oral glucose tolerance test (OGTT) performed before immunosuppression, was clearly abnormal (0 min 170 mg%, 120 min 215 mg%, HbA1, 7. 2%) compared with the OGTT of one year before, which indicated impaired glucose tolerance, but no overt diabetes (0 min 119 mg%, 120 min 190 mg%, HbA1, 5. 8%), and insulin therapy was started in parallel with the corticosteroid treatment. Serum samples for detection of antibodies and venous blood for isolation of peripheral blood lymphocytes for T cell proliferation assay were isolated at day—180 before immunosuppressive therapy and at day 0, 5, 10, 20, 30, 50, 205 100, and 201 of the therapy. Blood samples were obtained in the morning before administration of steroid medication. Assays were performed blinded without knowledge of the clinical status of the patient. Results PATIENT Immunosuppressive therapy was initiated after diazepam and baclofen mono-therapy had lost effect. The first dose of prednisolone (2 250 mg daily) injected intravenously led to a complete disappearance of previously described symptoms within 3—4 hours. After 10 days the therapy was changed to oral medication and the doses were successively decreased to 5 mg/day. On day 30 of therapy the patient relapsed with rigidity and stiffness. The prednisolone dose was increased to 10 mg with additional 3 5 mg of diazepam/day. On day 201 prednisolone was reduced to 5 mg/day together with 3 5 mg diazepam. His condition improved and on day 400 he had good mobility and much less muscle rigidity and stiffness than before the therapy. ANTIBODIES At diagnosis the patient had raised concentrations of GADA. Raised antibody concentrations were found against the GAD65, ,,/GAD67,,, 593 (amino terminal epitope), GAD65, 469/ GAD673560. 53 and GAD67, ,,,/GAD65,, 4, sss (carboxy terminal epitope) chimeric constructs, but not the deletion constructs. During the course of immunosuppressive therapy no change in GADA titres against full length GAD65 (figure A) or chimeric constructs were found and no relation between circulating GADA titres and clinical patterns was seen (figure A and B). The patient also had ICAs and IAAs. The ICAs fluctuated and were not detectable before immunosuppression and in one sample during the course of immunotherapy. The IAAs increased after insulin dependent diabetes mellitus diagnosis and exogenous insulin therapy. IA-2As were undetectable in all samples (figure A). T CELL STIMULATION TEST AND CYTOKINE CONCENTRATIONS Before immunosuppressive therapy T cells responded to GAD65 (SI=4) and IA-2 (SI=6. 2) (figure B). High dose steroid medication resulted in decreased cellular reactivity to GAD and IA-2 together with clinical improvement of the patient. On day 30 (reduction of prednisolone therapy to 5 mg/day) rigidity and stiffness returned followed by increased T cell responses to GAD65 and IA-2 (SI,,)=3. 4 and SI, ,=6. 2, respectively). A subsequent increase in steroid therapy (10 mg/day) which resulted in improved mobility was accompanied by a persistent decrease in cellular reactivity to GAD65 and JA-2. T cell reactivity to the control antigens, tetanus toxoid, and PHA was also influenced by immunosuppressive therapy (as shown for tetanus in figure B). On day 30 when steroid therapy was reduced and clinical symptoms returned, a sixfold increase of T cell \"yy Bi Adoo Immunity, immunosuppression, stiff-man syndrome, and insulin dependent diabetes mellitus reactivity to tetanus toxoid (figure B) and a threefold increase in proliferation to PHA (data not shown) were seen. The concentrations of IFN-γ as a marker of T,, 1 dominated T cell response, were measured in supernatants of T cell stimulation tests. At initiation of immunosuppressive therapy and on day 30 (remission of stiff-man syndrome symptoms) high concentrations of IFN-γ were detected in response to both antigens; T cells incubated with GAD65 secreted 183 and 175 pg/ml respectively and T cells incubated with IA-2 secreted considerably higher IFN-γ concentrations— namely, >1000 pg/ml. At all time points T cell responses directed against either GAD65 or IA-2 were accompanied with high IFN-γ concentrations. Cytokine concentrations to both antigens were dependent on antigen concentrations.",
    "extractions": [
      {
        "extraction_class": "age_description",
        "extraction_text": "51 year old man.",
        "attributes": {
          "value": "51",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "0",
          "char_end": "16",
          "span_role": "model_candidate",
          "coverage_quality": "direct_exact_span_ready",
          "langextract_recommendation": "candidate_for_promotion_after_spot_check",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "passed",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "diagnostic_criteria",
        "extraction_text": "He fulfilled all criteria established by Lorish et al’",
        "attributes": {
          "value": "Lorish et al.",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "17",
          "char_end": "71",
          "span_role": "model_candidate",
          "coverage_quality": "direct_exact_span_ready",
          "langextract_recommendation": "candidate_for_promotion_after_spot_check",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "passed",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "first_manifestation",
        "extraction_text": "prodome of rigidity and stiffness in axial muscles",
        "attributes": {
          "value": "multiple",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "79",
          "char_end": "129",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_missing_supporting_snippets",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "excessive_startle_established",
        "extraction_text": "superimposed spasms precipitated by sudden movement and noise",
        "attributes": {
          "value": "movement;noise",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "262",
          "char_end": "323",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "CMUA",
        "extraction_text": "the classic EMG findings (continuous normal motor unit firing, despite the patient’s intention to relax)",
        "attributes": {
          "value": "1",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "403",
          "char_end": "507",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "sympt_treatment_effect",
        "extraction_text": "a favourable response to oral administration of diazepam.",
        "attributes": {
          "value": "improvement",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "517",
          "char_end": "574",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "included_diagnosis",
        "extraction_text": "One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test",
        "attributes": {
          "value": "Stiff_Person",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "575",
          "char_end": "684",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "notes",
        "extraction_text": "A kidney biopsy performed because of recurrent microhaematuria disclosed the rare syndrome of “thin basal membranes (200 nm)”.",
        "attributes": {
          "value": "\"thin basement membrane disease\" as comorbidity",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "937",
          "char_end": "1063",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "antibody_status",
        "extraction_text": "The patient had GAD antibodies and islet cell antibodies, but no other organ specific or non-organ specific antibodies.",
        "attributes": {
          "value": "GAD;islet_cell",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1169",
          "char_end": "1288",
          "span_role": "support",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "not_found",
          "original_validator_status": "needs_review",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "CSF_status",
        "extraction_text": "Cell count and protein content in the CSF were normal without oligoclonal bands.",
        "attributes": {
          "value": "normal",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1289",
          "char_end": "1369",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "CSF_antibody",
        "extraction_text": "GAD antibodies were not measured in CSF samples.",
        "attributes": {
          "value": "NA",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1370",
          "char_end": "1418",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "sympt_treatment",
        "extraction_text": "The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year.",
        "attributes": {
          "value": "benzo",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1539",
          "char_end": "1614",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "immunotherapy",
        "extraction_text": "Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg.",
        "attributes": {
          "value": "steroids",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1798",
          "char_end": "1980",
          "span_role": "support",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "not_found",
          "original_validator_status": "needs_review",
          "example_part_index": "1",
          "example_part_count": "3"
        }
      }
    ]
  },
  {
    "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
    "paper_id": "155",
    "case_id": "",
    "example_part_index": 2,
    "example_part_count": 3,
    "target_view_json_path": "qa\\validation\\stage07_single_case_codex_gold\\batch002\\json\\target_views\\155\\p1.json",
    "text": "51 year old man. He fulfilled all criteria established by Lorish et al’ as (1) prodome of rigidity and stiffness in axial muscles, (2) progression of rigidity and stiffness to include proximal limb muscles, (3) deforming of the spine, in this case lordosis, (4) superimposed spasms precipitated by sudden movement and noise, (5) normal muscle strength and sensory examination, (6) normal intellect, (7) the classic EMG findings (continuous normal motor unit firing, despite the patient’s intention to relax), and (8) a favourable response to oral administration of diazepam. One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test and was diagnosed as having insulin dependent diabetes mellitus. Partial strumectomy had been performed in 1984, but today it is not possible to determine whether the hyperthyroidism was caused by Graves‘ disease or by an adenoma of the thyroid gland. A kidney biopsy performed because of recurrent microhaematuria disclosed the rare syndrome of “thin basal membranes (200 nm)”. This is the first description of a patient with stiff-man syndrome with this extremely rare nephropathy. The patient had GAD antibodies and islet cell antibodies, but no other organ specific or non-organ specific antibodies. Cell count and protein content in the CSF were normal without oligoclonal bands. GAD antibodies were not measured in CSF samples. The HLA type of the patient is HLA-A1, 23; B8, 50; DR3, 3; DQA1*0501, 0501; DQB1*0201, 0201. IMMUNOSUPPRESSIVE THERAPY The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year. Diazepam was then no longer effective and the treatment was changed to baclofen (3 20-25 mg/day), also a GABAergic agonist. Clinical improvement was seen, but lasted only four weeks. Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg. Currently, after 400 days of therapy the patient has good mobility and is without rigidity with 5 mg prednisolone and 3 5 mg diazepam daily (figure A and B). An oral glucose tolerance test (OGTT) performed before immunosuppression, was clearly abnormal (0 min 170 mg%, 120 min 215 mg%, HbA1, 7. 2%) compared with the OGTT of one year before, which indicated impaired glucose tolerance, but no overt diabetes (0 min 119 mg%, 120 min 190 mg%, HbA1, 5. 8%), and insulin therapy was started in parallel with the corticosteroid treatment. Serum samples for detection of antibodies and venous blood for isolation of peripheral blood lymphocytes for T cell proliferation assay were isolated at day—180 before immunosuppressive therapy and at day 0, 5, 10, 20, 30, 50, 205 100, and 201 of the therapy. Blood samples were obtained in the morning before administration of steroid medication. Assays were performed blinded without knowledge of the clinical status of the patient. Results PATIENT Immunosuppressive therapy was initiated after diazepam and baclofen mono-therapy had lost effect. The first dose of prednisolone (2 250 mg daily) injected intravenously led to a complete disappearance of previously described symptoms within 3—4 hours. After 10 days the therapy was changed to oral medication and the doses were successively decreased to 5 mg/day. On day 30 of therapy the patient relapsed with rigidity and stiffness. The prednisolone dose was increased to 10 mg with additional 3 5 mg of diazepam/day. On day 201 prednisolone was reduced to 5 mg/day together with 3 5 mg diazepam. His condition improved and on day 400 he had good mobility and much less muscle rigidity and stiffness than before the therapy. ANTIBODIES At diagnosis the patient had raised concentrations of GADA. Raised antibody concentrations were found against the GAD65, ,,/GAD67,,, 593 (amino terminal epitope), GAD65, 469/ GAD673560. 53 and GAD67, ,,,/GAD65,, 4, sss (carboxy terminal epitope) chimeric constructs, but not the deletion constructs. During the course of immunosuppressive therapy no change in GADA titres against full length GAD65 (figure A) or chimeric constructs were found and no relation between circulating GADA titres and clinical patterns was seen (figure A and B). The patient also had ICAs and IAAs. The ICAs fluctuated and were not detectable before immunosuppression and in one sample during the course of immunotherapy. The IAAs increased after insulin dependent diabetes mellitus diagnosis and exogenous insulin therapy. IA-2As were undetectable in all samples (figure A). T CELL STIMULATION TEST AND CYTOKINE CONCENTRATIONS Before immunosuppressive therapy T cells responded to GAD65 (SI=4) and IA-2 (SI=6. 2) (figure B). High dose steroid medication resulted in decreased cellular reactivity to GAD and IA-2 together with clinical improvement of the patient. On day 30 (reduction of prednisolone therapy to 5 mg/day) rigidity and stiffness returned followed by increased T cell responses to GAD65 and IA-2 (SI,,)=3. 4 and SI, ,=6. 2, respectively). A subsequent increase in steroid therapy (10 mg/day) which resulted in improved mobility was accompanied by a persistent decrease in cellular reactivity to GAD65 and JA-2. T cell reactivity to the control antigens, tetanus toxoid, and PHA was also influenced by immunosuppressive therapy (as shown for tetanus in figure B). On day 30 when steroid therapy was reduced and clinical symptoms returned, a sixfold increase of T cell \"yy Bi Adoo Immunity, immunosuppression, stiff-man syndrome, and insulin dependent diabetes mellitus reactivity to tetanus toxoid (figure B) and a threefold increase in proliferation to PHA (data not shown) were seen. The concentrations of IFN-γ as a marker of T,, 1 dominated T cell response, were measured in supernatants of T cell stimulation tests. At initiation of immunosuppressive therapy and on day 30 (remission of stiff-man syndrome symptoms) high concentrations of IFN-γ were detected in response to both antigens; T cells incubated with GAD65 secreted 183 and 175 pg/ml respectively and T cells incubated with IA-2 secreted considerably higher IFN-γ concentrations— namely, >1000 pg/ml. At all time points T cell responses directed against either GAD65 or IA-2 were accompanied with high IFN-γ concentrations. Cytokine concentrations to both antigens were dependent on antigen concentrations.",
    "extractions": [
      {
        "extraction_class": "sex",
        "extraction_text": "51 year old man.",
        "attributes": {
          "value": "M",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "0",
          "char_end": "16",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_missing_supporting_snippets",
          "example_part_index": "2",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "first_manifestation_multiple",
        "extraction_text": "prodome of rigidity and stiffness in axial muscles",
        "attributes": {
          "value": "stiffness",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "79",
          "char_end": "129",
          "span_role": "model_candidate",
          "coverage_quality": "direct_exact_span_ready",
          "langextract_recommendation": "candidate_for_promotion_after_spot_check",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "passed",
          "example_part_index": "2",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "spasms_distribution_established",
        "extraction_text": "superimposed spasms precipitated by sudden movement and noise",
        "attributes": {
          "value": "other",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "262",
          "char_end": "323",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "2",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "autoimmunity_specify",
        "extraction_text": "One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test and was diagnosed as having insulin dependent diabetes mellitus.",
        "attributes": {
          "value": "diabetes",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "575",
          "char_end": "749",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "2",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "CSF_antibody_titre",
        "extraction_text": "GAD antibodies were not measured in CSF samples.",
        "attributes": {
          "value": "NA",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1370",
          "char_end": "1418",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "2",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "sympt_treatment_detail",
        "extraction_text": "The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year. Diazepam was then no longer effective and the treatment was changed to baclofen (3 20-25 mg/day), also a GABAergic agonist. Clinical improvement was seen, but lasted only four weeks. Immunosuppressive therapy was therefore initiated",
        "attributes": {
          "value": "diazepam 3 x 2.5mg / day for 1 year, then diazepam was no longer effective. Then baclofen 3 x 20-25mg/day, improvement for only 4 weeks. Then immunosuppression.",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1539",
          "char_end": "1847",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "2",
          "example_part_count": "3"
        }
      }
    ]
  },
  {
    "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
    "paper_id": "155",
    "case_id": "",
    "example_part_index": 3,
    "example_part_count": 3,
    "target_view_json_path": "qa\\validation\\stage07_single_case_codex_gold\\batch002\\json\\target_views\\155\\p1.json",
    "text": "51 year old man. He fulfilled all criteria established by Lorish et al’ as (1) prodome of rigidity and stiffness in axial muscles, (2) progression of rigidity and stiffness to include proximal limb muscles, (3) deforming of the spine, in this case lordosis, (4) superimposed spasms precipitated by sudden movement and noise, (5) normal muscle strength and sensory examination, (6) normal intellect, (7) the classic EMG findings (continuous normal motor unit firing, despite the patient’s intention to relax), and (8) a favourable response to oral administration of diazepam. One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test and was diagnosed as having insulin dependent diabetes mellitus. Partial strumectomy had been performed in 1984, but today it is not possible to determine whether the hyperthyroidism was caused by Graves‘ disease or by an adenoma of the thyroid gland. A kidney biopsy performed because of recurrent microhaematuria disclosed the rare syndrome of “thin basal membranes (200 nm)”. This is the first description of a patient with stiff-man syndrome with this extremely rare nephropathy. The patient had GAD antibodies and islet cell antibodies, but no other organ specific or non-organ specific antibodies. Cell count and protein content in the CSF were normal without oligoclonal bands. GAD antibodies were not measured in CSF samples. The HLA type of the patient is HLA-A1, 23; B8, 50; DR3, 3; DQA1*0501, 0501; DQB1*0201, 0201. IMMUNOSUPPRESSIVE THERAPY The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year. Diazepam was then no longer effective and the treatment was changed to baclofen (3 20-25 mg/day), also a GABAergic agonist. Clinical improvement was seen, but lasted only four weeks. Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg. Currently, after 400 days of therapy the patient has good mobility and is without rigidity with 5 mg prednisolone and 3 5 mg diazepam daily (figure A and B). An oral glucose tolerance test (OGTT) performed before immunosuppression, was clearly abnormal (0 min 170 mg%, 120 min 215 mg%, HbA1, 7. 2%) compared with the OGTT of one year before, which indicated impaired glucose tolerance, but no overt diabetes (0 min 119 mg%, 120 min 190 mg%, HbA1, 5. 8%), and insulin therapy was started in parallel with the corticosteroid treatment. Serum samples for detection of antibodies and venous blood for isolation of peripheral blood lymphocytes for T cell proliferation assay were isolated at day—180 before immunosuppressive therapy and at day 0, 5, 10, 20, 30, 50, 205 100, and 201 of the therapy. Blood samples were obtained in the morning before administration of steroid medication. Assays were performed blinded without knowledge of the clinical status of the patient. Results PATIENT Immunosuppressive therapy was initiated after diazepam and baclofen mono-therapy had lost effect. The first dose of prednisolone (2 250 mg daily) injected intravenously led to a complete disappearance of previously described symptoms within 3—4 hours. After 10 days the therapy was changed to oral medication and the doses were successively decreased to 5 mg/day. On day 30 of therapy the patient relapsed with rigidity and stiffness. The prednisolone dose was increased to 10 mg with additional 3 5 mg of diazepam/day. On day 201 prednisolone was reduced to 5 mg/day together with 3 5 mg diazepam. His condition improved and on day 400 he had good mobility and much less muscle rigidity and stiffness than before the therapy. ANTIBODIES At diagnosis the patient had raised concentrations of GADA. Raised antibody concentrations were found against the GAD65, ,,/GAD67,,, 593 (amino terminal epitope), GAD65, 469/ GAD673560. 53 and GAD67, ,,,/GAD65,, 4, sss (carboxy terminal epitope) chimeric constructs, but not the deletion constructs. During the course of immunosuppressive therapy no change in GADA titres against full length GAD65 (figure A) or chimeric constructs were found and no relation between circulating GADA titres and clinical patterns was seen (figure A and B). The patient also had ICAs and IAAs. The ICAs fluctuated and were not detectable before immunosuppression and in one sample during the course of immunotherapy. The IAAs increased after insulin dependent diabetes mellitus diagnosis and exogenous insulin therapy. IA-2As were undetectable in all samples (figure A). T CELL STIMULATION TEST AND CYTOKINE CONCENTRATIONS Before immunosuppressive therapy T cells responded to GAD65 (SI=4) and IA-2 (SI=6. 2) (figure B). High dose steroid medication resulted in decreased cellular reactivity to GAD and IA-2 together with clinical improvement of the patient. On day 30 (reduction of prednisolone therapy to 5 mg/day) rigidity and stiffness returned followed by increased T cell responses to GAD65 and IA-2 (SI,,)=3. 4 and SI, ,=6. 2, respectively). A subsequent increase in steroid therapy (10 mg/day) which resulted in improved mobility was accompanied by a persistent decrease in cellular reactivity to GAD65 and JA-2. T cell reactivity to the control antigens, tetanus toxoid, and PHA was also influenced by immunosuppressive therapy (as shown for tetanus in figure B). On day 30 when steroid therapy was reduced and clinical symptoms returned, a sixfold increase of T cell \"yy Bi Adoo Immunity, immunosuppression, stiff-man syndrome, and insulin dependent diabetes mellitus reactivity to tetanus toxoid (figure B) and a threefold increase in proliferation to PHA (data not shown) were seen. The concentrations of IFN-γ as a marker of T,, 1 dominated T cell response, were measured in supernatants of T cell stimulation tests. At initiation of immunosuppressive therapy and on day 30 (remission of stiff-man syndrome symptoms) high concentrations of IFN-γ were detected in response to both antigens; T cells incubated with GAD65 secreted 183 and 175 pg/ml respectively and T cells incubated with IA-2 secreted considerably higher IFN-γ concentrations— namely, >1000 pg/ml. At all time points T cell responses directed against either GAD65 or IA-2 were accompanied with high IFN-γ concentrations. Cytokine concentrations to both antigens were dependent on antigen concentrations.",
    "extractions": [
      {
        "extraction_class": "stiffness_distribution_established",
        "extraction_text": "prodome of rigidity and stiffness in axial muscles",
        "attributes": {
          "value": "axial",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "79",
          "char_end": "129",
          "span_role": "model_candidate",
          "coverage_quality": "direct_exact_span_ready",
          "langextract_recommendation": "candidate_for_promotion_after_spot_check",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "passed",
          "example_part_index": "3",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "spasms_distribution_established_other",
        "extraction_text": "superimposed spasms precipitated by sudden movement and noise",
        "attributes": {
          "value": "unspecified",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "262",
          "char_end": "323",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "3",
          "example_part_count": "3"
        }
      },
      {
        "extraction_class": "immuntherapy_detail",
        "extraction_text": "Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg. Currently, after 400 days of therapy the patient has good mobility and is without rigidity with 5 mg prednisolone and 3 5 mg diazepam daily",
        "attributes": {
          "value": "500mg iv prednisolone / day for 10d, followed by oral tapering. Then daily 5mg prednisolone and 3 x 5mg diazepam",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1798",
          "char_end": "2120",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_anchor_not_found",
          "example_part_index": "3",
          "example_part_count": "3"
        }
      }
    ]
  },
  {
    "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
    "paper_id": "162",
    "case_id": "",
    "example_part_index": 1,
    "example_part_count": 5,
    "target_view_json_path": "qa\\validation\\stage07_single_case_codex_gold\\batch002\\json\\target_views\\162\\p1.json",
    "text": "Abstract We describe a patient with type 1 diabetes with recurrent diabetic ketoacidosis and severe insulin resistance. Extensive evaluation of the etiology of the insulin resistance did not reveal an etiology, and well over 1000 U of daily insulin did not prevent the ketoacidosis. Her blood glucose and insulin requirements were improved with glucocorti- coids and octreotide, but the effects of both of these agents were short-lived. She was given a trial of insulin lispro with immediate and dramatic effects, lowering her HbA 1c from 14.6 to 5.1% in 7 months with a decrease in insulin requirements of 1600–100 U per day. Besides her diabetes, she had a history of pain and stiffness affecting numerous muscle groups, and hospitalization was required for pain control. The diagnosis of stiff-man syndrome (SMS) was conﬁrmed with high titers of glutamic acid decarboxylase 65 antibodies in both serum and cerebral spinal ﬂuid. In summary, we describe the ﬁrst patient with type 1 diabetes, SMS, and severe insulin resistance. Although the etiology of the insulin resistance is unknown, due to the efﬁcacious response to insulin lispro, hydrocortisone, and perhaps octreotide, we propose an immune-mediated etiology. Although rare, this syndrome needs to be considered as an etiology of insulin resistance. © 1998 Elsevier Science Ireland Ltd. All rights reserved. C

[truncated at 40000 characters]


## examples/langextract_bootstrap/draft_langextract_examples_openai_pilot10_all_gold.json
[
  {
    "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
    "paper_id": "524",
    "case_id": "",
    "example_part_index": 1,
    "example_part_count": 4,
    "target_view_json_path": "qa\\validation\\stage07_single_case_codex_gold\\batch008\\json\\target_views\\524\\p1.json",
    "text": "2. Case history A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg. The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus lead- ing to frequent falls and immobilisation. Neurological examination 7 months after symptom debut revealed generalized atrophy in the left leg with paralysis of the left ankle. Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk, corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale [10]. Moreover, auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale[10]. The ten- don reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms. Babinski sign was negative on the right side, and indifferent on the left. Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves. At month 10 after symp- tom onset, routine blood tests including glucose and electrolytes, extensive radiological examinations of the neuraxis, malignancy workout, antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal. Serum creatinine increased gradu- ally to 1717 units/ml (normal <270 U/ml), but normalized 3 months later. Routine examinations of the cerebrospinal ﬂuid (CSF), includ- ing isoelectric focusing, cell count and quantiﬁcation of albumin, protein and IgG, as well as the ratio of IgG:albumin in CSF:serum were normal. Anti-GAD65 antibodies were markedly and persis- tently increased in serum (0.96–1.57 units at month 10 and 14 after symptom onset, respectively; normal <0.08) and were also detected in CSF (0.84 units at month 10 after symptom onset). The CSF:serum relative ratio of anti-GAD65 antibodies was 3.2 (normal <1.3), and isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF with no or clearly weaker counterparts in serum [8]. Intravenuos diazepam and clonazepam induced transient improvement, but there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins. The patient deteriorated rapidly and became bedridden with almost continuous painful spasms in the left leg. Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days. The serum and CSF GAD65 antibody activity was 1.57 and 0.84, respectively, prior to plasma exchange, and 1.28 and 0.57 after the last procedure. The anti- GAD65 activity in the consecutive plasmapherates was 1.25, 1.28, 1.34, 1.15 and 1.19 units, respectively. The patient did not respond to plasma exchange. The procedure was complicated by transient lymph leakage and catheter pain, and was therefore not repeated. Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms. He died from pneumonia 18 months after symptom onset. No signs of malignancy were detected at autopsy. 3. Neuropathological examination After ﬁxation in 10% formalin, brain, spinal cord and a fragment of the sciatic nerve were embedded in parafﬁn wax. Five /H9262m thick sections were cut and stained with haematoxylin and eosin (HE). Sections from selected areas of the brain and ﬁve segments (cervi- cal, thoracal, lumbar, sacral and conus medullaris/cauda equina) of the spinal cord were stained with the Bodian, Gallyas, Campbell- Switzer and Luxol fast blue techniques. Immunohistochemical analyses were performed using primary antibodies against ubiq- uitin (Dako), glial ﬁbrillary acidic protein (Dako), alfa-synuclein (Zymed), tau (Dako), the leukocyte common antigen (LCA) CD45 (Dako), CD3 (NeoMarkers), CD4 (Novocastra), CD8 (Dako), CD20 (Dako), CD79a (Dako), CD68 (Dako), the complement complex 4d (C4d; Biomedica) and terminal complement complex C3C (Dako), and immunoglobulines A, G and M (Southern Biotechnology Asso- ciates). The brain contained senile plaques throughout the cortex but few neuroﬁbrillary tangles (Braak stage 1–2). Except from a few axonal swellings in the granular cell layer of the cerebellum no other structural changes were detected in the brain. Examination of the spinal cord showed chromatolysis and vacuolisation of some anterior horn cells, as well as axonal swellings and slight glio- Fig. 1. Neuron damage in the anterior horn of the lower spinal cord. Axonal swellings (A) and anterior horn cell chromatolysis (B) were most pronounced in the lower spinal cord. Bodian (A) and Luxol fast blue (B) stainings. Original magniﬁcation 400× (A) and 600× (B). sis. These changes were most pronounced in the lower segments (Fig. 1). Ubiquitin-immunoreactive neuronal inclusions consistent with amyotrophic lateral sclerosis were not detected. A discrete, distinctively unilateral accumulation of CD8+ cytotoxic T cells and proliferation of CD68+ microglial cells in the anterior horn was detected by immunohistochemical examination (Fig. 2). There were no signs of inﬂammation elsewhere. Deposition of the comple- ment complexes was not detected. The spinal nerve roots were normal, whereas a slight loss of nerve ﬁbres were detected in the schiatic nerve. A snap frozen biopsy from the vastus later- alis muscle demonstrated signs of denervation and no evidence of inﬂammation.",
    "extractions": [
      {
        "extraction_class": "ethnicity",
        "extraction_text": "A previously healthy 67-year-old male presented",
        "attributes": {
          "value": "white",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "16",
          "char_end": "63",
          "span_role": "absence_context",
          "coverage_quality": "context_or_absence_only_not_direct_extraction",
          "langextract_recommendation": "do_not_promote_as_standard_langextract_example",
          "original_evidence_mode": "not_found",
          "original_validator_status": "needs_review",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "other_symptoms_onset",
        "extraction_text": "fol- lowed by fasciculations and muscle atrophy in the left leg",
        "attributes": {
          "value": "fasciculation;muscle_atrophy",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "141",
          "char_end": "204",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "timecourse_subsequent",
        "extraction_text": "The condition progressed rapidly",
        "attributes": {
          "value": "monophasic",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "3",
          "char_start": "206",
          "char_end": "238",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "early_symptoms",
        "extraction_text": "marked muscular rigidity and painful superimposed spasms",
        "attributes": {
          "value": "stiffness;spasms",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "244",
          "char_end": "300",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "stiffness_distribution_onset_multiple",
        "extraction_text": "This was most prominent in the left leg, but subsequently also involved the right limb and truncus",
        "attributes": {
          "value": "lumb_prox_LE;distal_LE;axial",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "302",
          "char_end": "400",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "onset_to_established",
        "extraction_text": "Neurological examination 7 months after symptom debut",
        "attributes": {
          "value": "7",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "449",
          "char_end": "502",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "overview_established",
        "extraction_text": "Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk",
        "attributes": {
          "value": "stiffness;spasms",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "582",
          "char_end": "680",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "included_diagnosis",
        "extraction_text": "corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale",
        "attributes": {
          "value": "SPS with lower motor neuron disease",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "682",
          "char_end": "784",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "excessive_startle_established",
        "extraction_text": "auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",
        "attributes": {
          "value": "multiple",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "801",
          "char_end": "922",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "other_symptoms_established",
        "extraction_text": "The ten- don reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms",
        "attributes": {
          "value": "hyporeflexia",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1020",
          "char_end": "1116",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "CMUA",
        "extraction_text": "Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity",
        "attributes": {
          "value": "1",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1193",
          "char_end": "1303",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "MRI_normal",
        "extraction_text": "extensive radiological examinations of the neuraxis",
        "attributes": {
          "value": "0",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "1447",
          "char_end": "1498",
          "span_role": "support",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "not_found",
          "original_validator_status": "needs_review",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "tu_screening",
        "extraction_text": "malignancy workout",
        "attributes": {
          "value": "0",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "3",
          "char_start": "1500",
          "char_end": "1518",
          "span_role": "support",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "not_found",
          "original_validator_status": "needs_review",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "antibody_tests",
        "extraction_text": "antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal",
        "attributes": {
          "value": "gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1520",
          "char_end": "1669",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "CSF_antibody",
        "extraction_text": "Anti-GAD65 antibodies were markedly and persis- tently increased in serum",
        "attributes": {
          "value": "GAD65",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "1986",
          "char_end": "2059",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "antibody_units",
        "extraction_text": "0.96–1.57 units",
        "attributes": {
          "value": "\"units\"",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "2061",
          "char_end": "2076",
          "span_role": "model_candidate",
          "coverage_quality": "direct_exact_span_ready",
          "langextract_recommendation": "candidate_for_promotion_after_spot_check",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "passed",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "CSF_antibody",
        "extraction_text": "were also detected in CSF",
        "attributes": {
          "value": "GAD65",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "2",
          "char_start": "2149",
          "char_end": "2174",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "CSF_status",
        "extraction_text": "isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF",
        "attributes": {
          "value": "antibody_present;OCB",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "2",
          "char_start": "2302",
          "char_end": "2394",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "sympt_treatment",
        "extraction_text": "Intravenuos diazepam and clonazepam induced transient improvement",
        "attributes": {
          "value": "benzo;clonazepam;baclofen;phenytoin",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "2448",
          "char_end": "2513",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "sympt_treatment_detail",
        "extraction_text": "there was no persistent response to these drugs or to baclofene, phenytoin",
        "attributes": {
          "value": "iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "2",
          "char_start": "2519",
          "char_end": "2593",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "immunotherapy",
        "extraction_text": "intravenous immunoglobulins",
        "attributes": {
          "value": "IVIG;PLEX",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "2598",
          "char_end": "2625",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "timecourse_subsequent",
        "extraction_text": "The patient deteriorated rapidly and became bedridden",
        "attributes": {
          "value": "monophasic",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "3",
          "char_start": "2627",
          "char_end": "2680",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "immunotherapy",
        "extraction_text": "Plasma exchange was therefore performed 14 months after symptom onset",
        "attributes": {
          "value": "IVIG;PLEX",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "2",
          "char_start": "2736",
          "char_end": "2805",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "immunotherapy_effect",
        "extraction_text": "The patient did not respond to plasma exchange.",
        "attributes": {
          "value": "none",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "3",
          "char_start": "3121",
          "char_end": "3168",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "immuntherapy_detail",
        "extraction_text": "Two g/kg intravenous immunoglobulin was given after another month",
        "attributes": {
          "value": "5x PLEX: no response. IVIG: 2g/kg",
          "case_id": "",
          "support_span_index": "3",
          "support_span_count": "3",
          "char_start": "3277",
          "char_end": "3342",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "FU_duration",
        "extraction_text": "He died from pneumonia 18 months after symptom onset.",
        "attributes": {
          "value": "18",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "3414",
          "char_end": "3467",
          "span_role": "model_candidate",
          "coverage_quality": "direct_exact_span_ready",
          "langextract_recommendation": "candidate_for_promotion_after_spot_check",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "passed",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "tu_screening",
        "extraction_text": "No signs of malignancy were detected at autopsy",
        "attributes": {
          "value": "0",
          "case_id": "",
          "support_span_index": "3",
          "support_span_count": "3",
          "char_start": "3468",
          "char_end": "3515",
          "span_role": "support",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "not_found",
          "original_validator_status": "needs_review",
          "example_part_index": "1",
          "example_part_count": "4"
        }
      }
    ]
  },
  {
    "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
    "paper_id": "524",
    "case_id": "",
    "example_part_index": 2,
    "example_part_count": 4,
    "target_view_json_path": "qa\\validation\\stage07_single_case_codex_gold\\batch008\\json\\target_views\\524\\p1.json",
    "text": "2. Case history A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg. The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus lead- ing to frequent falls and immobilisation. Neurological examination 7 months after symptom debut revealed generalized atrophy in the left leg with paralysis of the left ankle. Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk, corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale [10]. Moreover, auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale[10]. The ten- don reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms. Babinski sign was negative on the right side, and indifferent on the left. Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves. At month 10 after symp- tom onset, routine blood tests including glucose and electrolytes, extensive radiological examinations of the neuraxis, malignancy workout, antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal. Serum creatinine increased gradu- ally to 1717 units/ml (normal <270 U/ml), but normalized 3 months later. Routine examinations of the cerebrospinal ﬂuid (CSF), includ- ing isoelectric focusing, cell count and quantiﬁcation of albumin, protein and IgG, as well as the ratio of IgG:albumin in CSF:serum were normal. Anti-GAD65 antibodies were markedly and persis- tently increased in serum (0.96–1.57 units at month 10 and 14 after symptom onset, respectively; normal <0.08) and were also detected in CSF (0.84 units at month 10 after symptom onset). The CSF:serum relative ratio of anti-GAD65 antibodies was 3.2 (normal <1.3), and isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF with no or clearly weaker counterparts in serum [8]. Intravenuos diazepam and clonazepam induced transient improvement, but there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins. The patient deteriorated rapidly and became bedridden with almost continuous painful spasms in the left leg. Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days. The serum and CSF GAD65 antibody activity was 1.57 and 0.84, respectively, prior to plasma exchange, and 1.28 and 0.57 after the last procedure. The anti- GAD65 activity in the consecutive plasmapherates was 1.25, 1.28, 1.34, 1.15 and 1.19 units, respectively. The patient did not respond to plasma exchange. The procedure was complicated by transient lymph leakage and catheter pain, and was therefore not repeated. Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms. He died from pneumonia 18 months after symptom onset. No signs of malignancy were detected at autopsy. 3. Neuropathological examination After ﬁxation in 10% formalin, brain, spinal cord and a fragment of the sciatic nerve were embedded in parafﬁn wax. Five /H9262m thick sections were cut and stained with haematoxylin and eosin (HE). Sections from selected areas of the brain and ﬁve segments (cervi- cal, thoracal, lumbar, sacral and conus medullaris/cauda equina) of the spinal cord were stained with the Bodian, Gallyas, Campbell- Switzer and Luxol fast blue techniques. Immunohistochemical analyses were performed using primary antibodies against ubiq- uitin (Dako), glial ﬁbrillary acidic protein (Dako), alfa-synuclein (Zymed), tau (Dako), the leukocyte common antigen (LCA) CD45 (Dako), CD3 (NeoMarkers), CD4 (Novocastra), CD8 (Dako), CD20 (Dako), CD79a (Dako), CD68 (Dako), the complement complex 4d (C4d; Biomedica) and terminal complement complex C3C (Dako), and immunoglobulines A, G and M (Southern Biotechnology Asso- ciates). The brain contained senile plaques throughout the cortex but few neuroﬁbrillary tangles (Braak stage 1–2). Except from a few axonal swellings in the granular cell layer of the cerebellum no other structural changes were detected in the brain. Examination of the spinal cord showed chromatolysis and vacuolisation of some anterior horn cells, as well as axonal swellings and slight glio- Fig. 1. Neuron damage in the anterior horn of the lower spinal cord. Axonal swellings (A) and anterior horn cell chromatolysis (B) were most pronounced in the lower spinal cord. Bodian (A) and Luxol fast blue (B) stainings. Original magniﬁcation 400× (A) and 600× (B). sis. These changes were most pronounced in the lower segments (Fig. 1). Ubiquitin-immunoreactive neuronal inclusions consistent with amyotrophic lateral sclerosis were not detected. A discrete, distinctively unilateral accumulation of CD8+ cytotoxic T cells and proliferation of CD68+ microglial cells in the anterior horn was detected by immunohistochemical examination (Fig. 2). There were no signs of inﬂammation elsewhere. Deposition of the comple- ment complexes was not detected. The spinal nerve roots were normal, whereas a slight loss of nerve ﬁbres were detected in the schiatic nerve. A snap frozen biopsy from the vastus later- alis muscle demonstrated signs of denervation and no evidence of inﬂammation.",
    "extractions": [
      {
        "extraction_class": "age_onset",
        "extraction_text": "A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot",
        "attributes": {
          "value": "67",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "16",
          "char_end": "139",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "2",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "first_manifestation",
        "extraction_text": "The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.",
        "attributes": {
          "value": "multiple",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "2",
          "char_start": "206",
          "char_end": "301",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "2",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "stiffness_distribution_established",
        "extraction_text": "Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk",
        "attributes": {
          "value": "multiple",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "582",
          "char_end": "680",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "2",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "stiffness_distribution_established_other",
        "extraction_text": "a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale",
        "attributes": {
          "value": "5/6 points in SPS stiffness extent scale",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "699",
          "char_end": "784",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "exact_quote",
          "original_validator_status": "quote_not_found",
          "example_part_index": "2",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "spasms_distribution_established",
        "extraction_text": "auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",
        "attributes": {
          "value": "unspecified",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "2",
          "char_start": "801",
          "char_end": "922",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "2",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "included_diagnosis",
        "extraction_text": "Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves.",
        "attributes": {
          "value": "SPS with lower motor neuron disease",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "2",
          "char_start": "1193",
          "char_end": "1355",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "inferred_from_text",
          "original_validator_status": "inference_snippet_not_found",
          "example_part_index": "2",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "MRI_normal",
        "extraction_text": "were all normal",
        "attributes": {
          "value": "0",
          "case_id": "",
          "support_span_index": "2",
          "support_span_count": "2",
          "char_start": "1654",
          "char_end": "1669",
          "span_role": "support",
          "coverage_quality": "covered_by_repaired_exact_source_text",
          "langextract_recommendation": "candidate_after_span_review",
          "original_evidence_mode": "not_found",
          "original_validator_status": "needs_review",
          "example_part_index": "2",
          "example_part_count": "4"
        }
      },
      {
        "extraction_class": "antibody_status",
        "extraction_text": "Anti-GAD65 antibodies were markedly and persis- tently increased in serum",
        "attributes": {
          "value": "GAD65",
          "case_id": "",
          "support_span_index": "1",
          "support_span_count": "1",
          "char_start": "1986",
          "char_end": "2059",
          "span_role": "model_candidate",
          "coverage_quality": "covered_by_repaired_exact_source_text",
       

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/openai_pilot_10/GOAL_PLAN.md
# OpenAI Pilot 10 LangExtract Goal Plan

## Goal
Build a second 10-paper LangExtract example pilot from reviewed MC gold rows using the OpenAI API, then audit and repair the generated evidence against the Stage 07 text and original source PDFs before promotion.

## Acceptance Evidence
- Stage 09 defaults to the chosen GPT model for OpenAI bootstrapping, with a dry-run path and paid-run gate.
- The paid OpenAI run writes selected rows, candidate JSONL, review CSV, and manifest under this directory.
- Each selected paper has all non-empty gold fields represented in the reviewed span plan or explicitly documented as a discrepancy.
- Exact LangExtract examples validate with strict alignment and string-only attributes.
- A report in `doc/reports/` records paper-by-paper correctness, repairs, and source-vs-gold discrepancies for human review.

## Constraints And Boundaries
- Do not print or write API secrets.
- Treat model output as untrusted until validated against source text/PDF evidence.
- Keep non-canonical review artefacts under `qa/validation/`.
- Preserve raw source provenance; normalise whitespace only in LangExtract-facing examples.

## Current Plan
1. Run OpenAI on the 10 dry-run selected reviewed papers.
2. Validate model spans mechanically and identify unsupported or weakly supported fields.
3. Repair evidence spans from Stage 07 text/PDF source and document discrepancies.
4. Build strict LangExtract-compatible example JSON and run focused tests.

## Open Risks / Unknowns
- Some gold values may be inferred rather than directly quoteable; these need source-backed support spans and explicit notes.
- Some PDF OCR text may preserve line breaks or hyphenation that require careful normalisation for LangExtract alignment.


## qa/validation/langextract_example_bootstrap/openai_pilot_10/field_candidates.jsonl
{"paper_id": "524", "case_id": "", "model_id": "gpt-5.5-2026-04-23", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "67", "evidence_mode": "exact_quote", "extraction_text": "67-year-old male", "supporting_snippets": [], "reasoning_short": "The case history directly states the patient was 67 years old.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "M", "evidence_mode": "exact_quote", "extraction_text": "67-year-old male", "supporting_snippets": [], "reasoning_short": "The text directly identifies the patient as male, supporting M.", "supports_manual_value": true}, {"field_name": "ethnicity", "spreadsheet_value": "white", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The supplied text does not report ethnicity.", "supports_manual_value": false}, {"field_name": "age_onset", "spreadsheet_value": "67", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot", "He died from pneumonia 18 months after symptom onset."], "reasoning_short": "Symptoms began at presentation in a 67-year-old man; no other onset age is given.", "supports_manual_value": true}, {"field_name": "FU_duration", "spreadsheet_value": "18", "evidence_mode": "exact_quote", "extraction_text": "He died from pneumonia 18 months after symptom onset.", "supporting_snippets": [], "reasoning_short": "Follow-up/case duration is directly stated as 18 months after symptom onset.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, followed by fasciculations and muscle atrophy in the left leg", "The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms."], "reasoning_short": "Several manifestations occurred at onset/early presentation, supporting multiple.", "supports_manual_value": true}, {"field_name": "first_manifestation_multiple", "spreadsheet_value": "cramps;fasciculation;atrophy;stiffness;spasms", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, followed by fasciculations and muscle atrophy in the left leg", "The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms."], "reasoning_short": "The early presentation included cramps, fasciculations, muscle atrophy, rigidity/stiffness, and spasms.", "supports_manual_value": true}, {"field_name": "included_diagnosis", "spreadsheet_value": "SPS with lower motor neuron disease", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale", "Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves.", "Examination of the spinal cord showed chromatolysis and vacuolisation of some anterior horn cells, as well as axonal swellings and slight gliosis."], "reasoning_short": "SPS is supported by SPS scale findings and continuous motor activity; lower motor neuron disease is supported by denervation and anterior horn cell pathology.", "supports_manual_value": true}, {"field_name": "early_symptoms", "spreadsheet_value": "stiffness;spasms", "evidence_mode": "exact_quote", "extraction_text": "marked muscular rigidity and painful superimposed spasms", "supporting_snippets": [], "reasoning_short": "Early symptoms include rigidity (stiffness) and painful spasms.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_onset", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus"], "reasoning_short": "Stiffness/rigidity involved more than one region early in the disease course.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_onset_multiple", "spreadsheet_value": "lumb_prox_LE;distal_LE;axial", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["This was most prominent in the left leg, but subsequently also involved the right limb and truncus", "Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk"], "reasoning_short": "Leg involvement supports lower extremity categories, and truncus/trunk supports axial involvement.", "supports_manual_value": true}, {"field_name": "other_symptoms_onset", "spreadsheet_value": "fasciculation;muscle_atrophy", "evidence_mode": "exact_quote", "extraction_text": "followed by fasciculations and muscle atrophy in the left leg", "supporting_snippets": [], "reasoning_short": "The text directly reports fasciculations and muscle atrophy early in the left leg.", "supports_manual_value": true}, {"field_name": "timecourse_subsequent", "spreadsheet_value": "monophasic", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["The condition progressed rapidly", "The patient deteriorated rapidly and became bedridden", "He died from pneumonia 18 months after symptom onset."], "reasoning_short": "The text describes a single progressive/deteriorating course without relapses or remissions.", "supports_manual_value": true}, {"field_name": "onset_to_established", "spreadsheet_value": "7", "evidence_mode": "exact_quote", "extraction_text": "Neurological examination 7 months after symptom debut", "supporting_snippets": [], "reasoning_short": "Established examination findings were recorded 7 months after symptom debut.", "supports_manual_value": true}, {"field_name": "overview_established", "spreadsheet_value": "stiffness;spasms", "evidence_mode": "exact_quote", "extraction_text": "Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk", "supporting_snippets": ["triggered painful muscle cramps"], "reasoning_short": "Established findings included muscle stiffness and stimulus-triggered painful cramps/spasms.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk"], "reasoning_short": "At established examination, stiffness was present in both legs and trunk, i.e. multiple regions.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established_multiple", "spreadsheet_value": "lumb_prox_LE;distal_LE;axial", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk"], "reasoning_short": "Stiffness in the legs supports lower extremity involvement and trunk supports axial involvement.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established_other", "spreadsheet_value": "5/6 points in SPS stiffness extent scale", "evidence_mode": "exact_quote", "extraction_text": "a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale", "supporting_snippets": [], "reasoning_short": "The text directly reports five out of six points on the SPS stiffness extent scale.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established", "spreadsheet_value": "unspecified", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["auditory, somatosensory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps", "became bedridden with almost continuous painful spasms in the left leg"], "reasoning_short": "Spasms/cramps are described, mainly left leg later, but a formal distribution category is not specified in the supplied text.", "supports_manual_value": true}, {"field_name": "excessive_startle_established", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["auditory, somatosensory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps"], "reasoning_short": "Multiple stimulus modalities triggered painful cramps, supporting multiple heightened sensitivity/startle triggers.", "supports_manual_value": true}, {"field_name": "excessive_startle_established_multipleother", "spreadsheet_value": "auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale", "evidence_mode": "exact_quote", "extraction_text": "auditory, somatosensory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale", "supporting_snippets": [], "reasoning_short": "The text directly lists auditory, somatosensory, emotional, visual, and movement triggers and the six-of-seven score.", "supports_manual_value": true}, {"field_name": "other_symptoms_established", "spreadsheet_value": "hyporeflexia", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["The tendon reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms."], "reasoning_short": "Absent/weak tendon reflexes in the legs support hyporeflexia.", "supports_manual_value": true}, {"field_name": "antibody_status", "spreadsheet_value": "GAD65", "evidence_mode": "exact_quote", "extraction_text": "Anti-GAD65 antibodies were markedly and persistently increased in serum", "supporting_snippets": [], "reasoning_short": "Anti-GAD65 antibodies are directly reported as increased.", "supports_manual_value": true}, {"field_name": "antibody_titre", "spreadsheet_value": "1.57", "evidence_mode": "exact_quote", "extraction_text": "0.96–1.57 units at month 10 and 14 after symptom onset", "supporting_snippets": [], "reasoning_short": "The serum anti-GAD65 antibody value includes 1.57 units.", "supports_manual_value": true}, {"field_name": "antibody_units", "spreadsheet_value": "\"units\"", "evidence_mode": "exact_quote", "extraction_text": "0.96–1.57 units", "supporting_snippets": [], "reasoning_short": "The antibody result is reported in units.", "supports_manual_value": true}, {"field_name": "antibody_tests", "spreadsheet_value": "gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO", "evidence_mode": "exact_quote", "extraction_text": "antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal", "supporting_snippets": [], "reasoning_short": "The text lists these antibody tests, with voltage gated potassium channels, pancreas islets, DNA, and thyroxin peroxidase corresponding to the manual abbreviations.", "supports_manual_value": true}, {"field_name": "CSF_status", "spreadsheet_value": "antibody_present;OCB", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["were also detected in CSF (0.84 units at month 10 after symptom onset).", "isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF"], "reasoning_short": "Anti-GAD65 antibodies were present in CSF and GAD65-specific oligoclonal IgG bands were shown.", "supports_manual_value": true}, {"field_name": "CSF_antibody", "spreadsheet_value": "GAD65", "evidence_mode": "exact_quote", "extraction_text": "Anti-GAD65 antibodies were markedly and persistently increased in serum", "supporting_snippets": ["were also detected in CSF"], "reasoning_short": "The antibody detected in CSF was anti-GAD65.", "supports_manual_value": true}, {"field_name": "CMUA", "spreadsheet_value": "1", "evidence_mode": "exact_quote", "extraction_text": "Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity", "supporting_snippets": [], "reasoning_short": "Continuous motor unit activity is directly supported by EMG continuous motor activity.", "supports_manual_value": true}, {"field_name": "MRI_normal", "spreadsheet_value": "0", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The text says extensive radiological examinations of the neuraxis were normal, which would support normal imaging rather than the manual value 0; the manual value is not supported.", "supports_manual_value": false}, {"field_name": "tu_screening", "spreadsheet_value": "0", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The text reports malignancy workout was normal and no malignancy at autopsy, which does not support a value of 0 if indicating not performed/positive; the manual value is not directly supportable from the supplied text.", "supports_manual_value": false}, {"field_name": "immunotherapy", "spreadsheet_value": "IVIG;PLEX", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["intravenous immunoglobulins", "Plasma exchange was therefore performed 14 months after symptom onset"], "reasoning_short": "The patient received intravenous immunoglobulin and plasma exchange.", "supports_manual_value": true}, {"field_name": "immuntherapy_detail", "spreadsheet_value": "5x PLEX: no response. IVIG: 2g/kg", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days.", "The patient did not respond to plasma exchange.", "Two g/kg intravenous immunoglobulin was given after another month"], "reasoning_short": "The text supports five plasma exchange procedures with no response and IVIG at two g/kg.", "supports_manual_value": true}, {"field_name": "immunotherapy_effect", "spreadsheet_value": "none", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins.", "The patient did not respond to plasma exchange.", "Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms."], "reasoning_short": "Both IVIG and plasma exchange are described as ineffective/no response.", "supports_manual_value": true}, {"field_name": "sympt_treatment", "spreadsheet_value": "benzo;clonazepam;baclofen;phenytoin", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Intravenuos diazepam and clonazepam induced transient improvement", "no persistent response to these drugs or to baclofene, phenytoin"], "reasoning_short": "Diazepam is a benzodiazepine, and clonazepam, baclofen, and phenytoin are directly named.", "supports_manual_value": true}, {"field_name": "sympt_treatment_detail", "spreadsheet_value": "iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Intravenuos diazepam and clonazepam induced transient improvement", "there was no persistent response to these drugs or to baclofene, phenytoin"], "reasoning_short": "The text reports IV diazepam and clonazepam produced transient improvement and no persistent response to baclofen or phenytoin.", "supports_manual_value": true}, {"field_name": "sympt_treatment_effect", "spreadsheet_value": "minimal improvement", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Intravenuos diazepam and clonazepam induced transient improvement", "there was no persistent response to these drugs or to baclofene, phenytoin"], "reasoning_short": "Only transient improvement occurred with benzodiazepines and no persistent response to other symptomatic treatments, supporting minimal improvement.", "supports_manual_value": true}]}
{"paper_id": "537", "case_id": "", "model_id": "gpt-5.5-2026-04-23", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "29", "evidence_mode": "exact_quote", "extraction_text": "A 29-year-old previously healthy African-\nAmerican male patient", "supporting_snippets": [], "reasoning_short": "The case presentation directly states the patient was 29 years old.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "M", "evidence_mode": "exact_quote", "extraction_text": "African-\nAmerican male patient", "supporting_snippets": [], "reasoning_short": "The text directly identifies the patient as male, supporting M.", "supports_manual_value": true}, {"field_name": "ethnicity", "spreadsheet_value": "africa", "evidence_mode": "exact_quote", "extraction_text": "African-\nAmerican male patient", "supporting_snippets": [], "reasoning_short": "The text directly describes the patient as African-American, supporting the manual ethnicity value.", "supports_manual_value": true}, {"field_name": "age_onset", "spreadsheet_value": "29", "evidence_mode": "exact_quote", "extraction_text": "A 29-year-old previously healthy African-\nAmerican male patient complained of\nfour-week history", "supporting_snippets": [], "reasoning_short": "Symptoms are described in a 29-year-old patient with a four-week history, supporting onset at age 29.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "other", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["complained of\nfour-week history of progressive shortness\nof breath, non-productive cough and left-\nsided chest pain"], "reasoning_short": "The first described symptoms were not stiffness or spasms but respiratory/chest symptoms, corresponding to other.", "supports_manual_value": true}, {"field_name": "first_manifestation_multiple", "spreadsheet_value": "dyspnoea", "evidence_mode": "exact_quote", "extraction_text": "progressive shortness\nof breath", "supporting_snippets": [], "reasoning_short": "Dyspnoea is directly supported by the phrase progressive shortness of breath.", "supports_manual_value": true}, {"field_name": "included_diagnosis", "spreadsheet_value": "paraneoplastic_SPS", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["His\nclinical picture was suggestive of SPS sec-\nondary to invasive thymoma.", "the\ndiagnosis of SPS was made", "pathology specimen being\nconsistent with lymphocytic pre-\ndominant epithelial type thymoma"], "reasoning_short": "SPS is diagnosed and described as secondary to invasive thymoma, supporting paraneoplastic SPS.", "supports_manual_value": true}, {"field_name": "other_symptoms_onset", "spreadsheet_value": "dyspnoea", "evidence_mode": "exact_quote", "extraction_text": "progressive shortness\nof breath", "supporting_snippets": [], "reasoning_short": "The onset symptoms included shortness of breath, equivalent to dyspnoea.", "supports_manual_value": true}, {"field_name": "timecourse_subsequent", "spreadsheet_value": "monophasic", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["at five-month follow up he did-\nn’t have any recurrence of his symp-\ntoms"], "reasoning_short": "No recurrence at follow-up supports a single monophasic episode/course.", "supports_manual_value": true}, {"field_name": "overview_established", "spreadsheet_value": "stiffness;spasms", "evidence_mode": "exact_quote", "extraction_text": "muscle spasms, rigidity", "supporting_snippets": [], "reasoning_short": "The abstract describes SPS features including muscle spasms and rigidity/stiffness.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["truncal, lower ex-\ntremities stiffness", "diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain"], "reasoning_short": "Stiffness involved both trunk/lower back and lower extremities, supporting multiple distributions.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established_multiple", "spreadsheet_value": "distal_LE;lumb_prox_LE;axial", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["truncal, lower ex-\ntremities stiffness", "diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain"], "reasoning_short": "Text supports axial/truncal and lower extremity involvement, with lower back and both lower extremities consistent with listed distributions.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["truncal, lower ex-\ntremities stiffness and painful cramps", "severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs"], "reasoning_short": "Painful cramps/muscle cramps are described with truncal/lower extremity context and both legs, supporting multiple involvement.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established_multiple", "spreadsheet_value": "distal_LE;lumb_prox_LE", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs", "truncal, lower ex-\ntremities stiffness and painful cramps"], "reasoning_short": "Muscle cramps in both legs/lower extremities support lower extremity spasm distribution, though exact distal/proximal subdivision is inferred.", "supports_manual_value": true}, {"field_name": "other_symptoms_established", "spreadsheet_value": "pain;weakness", "evidence_mode": "exact_quote", "extraction_text": "severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs", "supporting_snippets": [], "reasoning_short": "The text directly states lower extremity pain and weakness in both legs.", "supports_manual_value": true}, {"field_name": "antibody_status", "spreadsheet_value": "GAD", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The text states anti-GAD antibodies were included in testing but the result was negative, so a GAD-positive status is not supported.", "supports_manual_value": false}, {"field_name": "antibody_tests", "spreadsheet_value": "GAD;AChR", "evidence_mode": "exact_quote", "extraction_text": "anti-GAD antibodies; the result was\nnegative. Myasthenia gravis was\nruled out by a normal pulmonary\nfunction test and a negative anti-\nAChR antibodies test", "supporting_snippets": [], "reasoning_short": "The text directly mentions anti-GAD and anti-AChR antibody tests.", "supports_manual_value": true}, {"field_name": "tu_screening", "spreadsheet_value": "1", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Computed tomog-\nraphy of the chest demonstrated a large\nleft-sided pleural effusion and a large an-\nterior mediastinal mass", "PET scan\nshowed anterior mediastinal mass"], "reasoning_short": "Tumor evaluation/screening was performed with chest CT and PET showing a mediastinal mass.", "supports_manual_value": true}, {"field_name": "tu_screening_abnormal", "spreadsheet_value": "thymoma invasive lymphocytic predominant epithelial type", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["pathology specimen being\nconsistent with lymphocytic pre-\ndominant epithelial type thymoma", "Due to the invasive behavior of this\nneoplasm"], "reasoning_short": "Pathology identified lymphocytic predominant epithelial type thymoma, and the neoplasm was described as invasive.", "supports_manual_value": true}, {"field_name": "sympt_treatment", "spreadsheet_value": "benzo;morphine", "evidence_mode": "exact_quote", "extraction_text": "diazepam 5 mg intravenously\nalong with intravenous morphine", "supporting_snippets": [], "reasoning_short": "Diazepam is a benzodiazepine and morphine is directly named.", "supports_manual_value": true}, {"field_name": "sympt_treatment_detail", "spreadsheet_value": "diazepam 5mg iv and morphine with complete resolution of neurological symptoms", "evidence_mode": "exact_quote", "extraction_text": "Patient was\ngiven diazepam 5 mg intravenously\nalong with intravenous morphine\nwith complete resolution of his\nsymptoms.", "supporting_snippets": [], "reasoning_short": "The sentence directly supports diazepam 5 mg IV plus IV morphine with complete symptom resolution.", "supports_manual_value": true}, {"field_name": "sympt_treatment_effect", "spreadsheet_value": "improvement", "evidence_mode": "exact_quote", "extraction_text": "complete resolution of his\nsymptoms", "supporting_snippets": [], "reasoning_short": "Complete resolution directly supports improvement.", "supports_manual_value": true}, {"field_name": "other_treatment", "spreadsheet_value": "resection and chemotherapy of thymoma with complete resolution of neurological symptoms", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "Chemotherapy is supported, but surgical resection was deferred/not an option; therefore the full manual value including resection is not supported.", "supports_manual_value": false}]}
{"paper_id": "551", "case_id": "", "model_id": "gpt-5.5-2026-04-23", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "51", "evidence_mode": "exact_quote", "extraction_text": "A 51-year-old white man", "supporting_snippets": [], "reasoning_short": "The case report directly states the patient was 51 years old.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "M", "evidence_mode": "exact_quote", "extraction_text": "white man", "supporting_snippets": [], "reasoning_short": "The term 'man' directly supports male sex.", "supports_manual_value": true}, {"field_name": "ethnicity", "spreadsheet_value": "white", "evidence_mode": "exact_quote", "extraction_text": "white man", "supporting_snippets": [], "reasoning_short": "The source directly describes the patient as white.", "supports_manual_value": true}, {"field_name": "age_onset", "spreadsheet_value": "51", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["A 51-year-old white man", "History revealed an onset of leg pain and falls over the last 6 months"], "reasoning_short": "The patient was 51 at presentation and onset occurred over the prior 6 months, supporting onset around age 51.", "supports_manual_value": true}, {"field_name": "time_to_diagnosis", "spreadsheet_value": "0.5", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["History revealed an onset of leg pain and falls over the last 6 months", "His current neurologist had diagnosed stiff-man syndrome"], "reasoning_short": "Symptoms began over the last 6 months and stiff-man syndrome had been diagnosed by the current neurologist, supporting approximately 0.5 years to diagnosis.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["History revealed an onset of leg pain and falls over the last 6 months"], "reasoning_short": "The onset description includes more than one manifestation: leg pain and falls/weakness-related gait impairment.", "supports_manual_value": true}, {"field_name": "first_manifestation_multiple", "spreadsheet_value": "pain;weakness", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["History revealed an onset of leg pain and falls over the last 6 months", "He was complaining of weakness on his right side and numbness in his right foot."], "reasoning_short": "Leg pain is directly described at onset; weakness is clinically supported by complaints of weakness and falls, though the onset phrase itself says falls rather than weakness.", "supports_manual_value": true}, {"field_name": "included_diagnosis", "spreadsheet_value": "Stiff_Person", "evidence_mode": "exact_quote", "extraction_text": "His current neurologist had diagnosed stiff-man syndrome", "supporting_snippets": [], "reasoning_short": "The diagnosis is directly stated as stiff-man syndrome.", "supports_manual_value": true}, {"field_name": "early_symptoms", "spreadsheet_value": "spasms", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["slight tremors in his legs while sleeping with occasional daytime twitching in his face", "kicking his legs on the bed boards"], "reasoning_short": "Early tremors/twitching and leg kicking are compatible with spasms, but the exact word spasms is not used.", "supports_manual_value": true}, {"field_name": "spasms_distribution_onset", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["slight tremors in his legs while sleeping with occasional daytime twitching in his face"], "reasoning_short": "Abnormal movements are described in more than one region: legs and face.", "supports_manual_value": true}, {"field_name": "spasms_distribution_onset_multiple", "spreadsheet_value": "distal_LE;lumb_prox_LE", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The source mentions leg tremors but does not localize onset spasms to distal lower extremity and lumbar/proximal lower extremity distributions.", "supports_manual_value": false}, {"field_name": "other_symptoms_onset", "spreadsheet_value": "gait_disorder", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["History revealed an onset of leg pain and falls over the last 6 months; he used a cane initially, then a wheelchair, while outside his home."], "reasoning_short": "Falls and progression from cane to wheelchair support gait disorder at onset.", "supports_manual_value": true}, {"field_name": "onset_mRS", "spreadsheet_value": "3", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["he used a cane initially, then a wheelchair, while outside his home"], "reasoning_short": "Use of cane/wheelchair suggests moderate disability requiring assistance, consistent with an inferred mRS of 3.", "supports_manual_value": true}, {"field_name": "diagnosis_onset", "spreadsheet_value": "functional", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The text describes later concerns for psychogenic seizures/conversion disorder, but does not state the onset diagnosis was functional.", "supports_manual_value": false}, {"field_name": "onset_to_established", "spreadsheet_value": "6", "evidence_mode": "exact_quote", "extraction_text": "onset of leg pain and falls over the last 6 months", "supporting_snippets": [], "reasoning_short": "The source directly gives a 6-month interval from onset to the current established presentation.", "supports_manual_value": true}, {"field_name": "overview_established", "spreadsheet_value": "spasms", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["seizure-like episodes", "one tonic-clonic seizure episode (mainly in the lower left extremities)", "kicking his legs on the bed boards"], "reasoning_short": "Established episodes involved lower-extremity tonic-clonic/twitching or kicking movements, clinically consistent with spasms, though 'spasms' is not directly stated.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["one tonic-clonic seizure episode (mainly in the lower left extremities)", "complaining of weakness on his right side and numbness in his right foot", "kicking his legs on the bed boards"], "reasoning_short": "Abnormal motor symptoms involved lower extremities and right-sided complaints, supporting multiple distribution broadly, but precise distribution is not directly stated.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established_multiple", "spreadsheet_value": "distal_LE;lumb_prox_LE", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The text does not specify distal lower extremity plus lumbar/proximal lower extremity distribution for established spasms.", "supports_manual_value": false}, {"field_name": "excessive_startle_established", "spreadsheet_value": "noise", "evidence_mode": "exact_quote", "extraction_text": "noises (beeps of the cardiac monitor and loud visitors) tended to set off his spells", "supporting_snippets": [], "reasoning_short": "Noises are directly reported to trigger spells.", "supports_manual_value": true}, {"field_name": "other_symptoms_established", "spreadsheet_value": "gait_disorder;seizures", "evidence_mode": "exact_quote", "extraction_text": "intractable seizure-like episodes", "supporting_snippets": ["suffering a fall from his wheelchair", "intractable seizure-like episodes"], "reasoning_short": "Seizure-like episodes are directly stated, and wheelchair/fall supports gait disorder.", "supports_manual_value": true}, {"field_name": "other_symptoms_established_seizures", "spreadsheet_value": "functional seizure (EEG normal)", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["concerns that the patient may be experiencing psychogenic seizure episodes", "The EEG, CT myelogram, and head CT were all found to be within normal limits.", "one consistent with conversion disorder"], "reasoning_short": "Psychogenic seizure episodes/conversion disorder with normal EEG supports functional seizure with normal EEG.", "supports_manual_value": true}, {"field_name": "established_mRS", "spreadsheet_value": "4", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["suffering a fall from his wheelchair", "he used a cane initially, then a wheelchair, while outside his home"], "reasoning_short": "Wheelchair use supports moderately severe disability, consistent with inferred mRS 4.", "supports_manual_value": true}, {"field_name": "immunotherapy", "spreadsheet_value": "none", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The source does not state that no immunotherapy was given.", "supports_manual_value": false}, {"field_name": "sympt_treatment", "spreadsheet_value": "benzo;baclofen", "evidence_mode": "exact_quote", "extraction_text": "diazepam (now at 15 mg every 6 hours), baclofen (5 mg t.i.d.)", "supporting_snippets": [], "reasoning_short": "Diazepam is a benzodiazepine and baclofen is directly listed; the treatment regimen is stated.", "supports_manual_value": true}, {"field_name": "sympt_treatment_detail", "spreadsheet_value": "diazepam 15mg every 6h, baclofen 5mg tid", "evidence_mode": "exact_quote", "extraction_text": "diazepam (now at 15 mg every 6 hours), baclofen (5 mg t.i.d.)", "supporting_snippets": [], "reasoning_short": "The dosing details match the manual value.", "supports_manual_value": true}, {"field_name": "other_treatment", "spreadsheet_value": "physical therapy with benefit", "evidence_mode": "exact_quote", "extraction_text": "physical therapy consults had proven helpful", "supporting_snippets": [], "reasoning_short": "Physical therapy and benefit are directly stated.", "supports_manual_value": true}]}
{"paper_id": "552", "case_id": "", "model_id": "gpt-5.5-2026-04-23", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "49", "evidence_mode": "exact_quote", "extraction_text": "A 49-year-old male", "supporting_snippets": [], "reasoning_short": "Age is directly stated.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "M", "evidence_mode": "exact_quote", "extraction_text": "A 49-year-old male", "supporting_snippets": [], "reasoning_short": "Male supports sex coded as M.", "supports_manual_value": true}, {"field_name": "ethnicity", "spreadsheet_value": "NA", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "Ethnicity is not reported in the source text.", "supports_manual_value": false}, {"field_name": "time_to_diagnosis", "spreadsheet_value": "0.5", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration", "He was diagnosed with SPS"], "reasoning_short": "Six months' symptom duration before diagnosis corresponds to 0.5 years.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration", "He experienced constant hip pain"], "reasoning_short": "Initial presentation included multiple manifestations: rigidity/stiffness, spasms, and pain.", "supports_manual_value": true}, {"field_name": "first_manifestation_multiple", "spreadsheet_value": "stiffness;spasms;pain", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["progressively worsening muscle rigidity and spasms", "He experienced constant hip pain"], "reasoning_short": "Muscle rigidity supports stiffness, with spasms and hip pain also directly described.", "supports_manual_value": true}, {"field_name": "included_diagnosis", "spreadsheet_value": "Stiff_Person", "evidence_mode": "exact_quote", "extraction_text": "He was diagnosed with SPS", "supporting_snippets": [], "reasoning_short": "SPS is the diagnosis stated in the source.", "supports_manual_value": true}, {"field_name": "early_symptoms", "spreadsheet_value": "stiffness,spasms", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration"], "reasoning_short": "Early symptoms included rigidity, corresponding to stiffness, and spasms.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_onset", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["muscle rigidity and spasms of his upper and lower extremities", "constant hip pain"], "reasoning_short": "Onset rigidity involved upper and lower extremities with hip involvement, supporting multiple regions.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_onset_multiple", "spreadsheet_value": "lumb_prox_LE;distal_LE;UE", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["muscle rigidity and spasms of his upper and lower extremities", "constant hip pain"], "reasoning_short": "Upper extremities support UE; lower extremities support distal/proximal LE, and hip pain supports lumboproximal/lower proximal involvement.", "supports_manual_value": true}, {"field_name": "spasms_distribution_onset", "spreadsheet_value": "multiple", "evidence_mode": "exact_quote", "extraction_text": "spasms of his upper and lower extremities", "supporting_snippets": [

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/openai_pilot_10/field_review.csv
paper_id,case_id,field_name,spreadsheet_value,model_spreadsheet_value,evidence_mode,extraction_text,char_start,char_end,supporting_snippets_json,supports_manual_value,reasoning_short,validator_status,review_status,review_notes,target_view_json_path
524,,age_description,67,67,exact_quote,67-year-old male,37,53,[],TRUE,The case history directly states the patient was 67 years old.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sex,M,M,exact_quote,67-year-old male,37,53,[],TRUE,"The text directly identifies the patient as male, supporting M.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,ethnicity,white,white,not_found,,,,[],FALSE,The supplied text does not report ethnicity.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,age_onset,67,67,inferred_from_text,,,,"[""A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot"", ""He died from pneumonia 18 months after symptom onset.""]",TRUE,Symptoms began at presentation in a 67-year-old man; no other onset age is given.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,FU_duration,18,18,exact_quote,He died from pneumonia 18 months after symptom onset.,3414,3467,[],TRUE,Follow-up/case duration is directly stated as 18 months after symptom onset.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation,multiple,multiple,inferred_from_text,,,,"[""presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, followed by fasciculations and muscle atrophy in the left leg"", ""The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.""]",TRUE,"Several manifestations occurred at onset/early presentation, supporting multiple.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation_multiple,cramps;fasciculation;atrophy;stiffness;spasms,cramps;fasciculation;atrophy;stiffness;spasms,inferred_from_text,,,,"[""presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, followed by fasciculations and muscle atrophy in the left leg"", ""The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.""]",TRUE,"The early presentation included cramps, fasciculations, muscle atrophy, rigidity/stiffness, and spasms.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,included_diagnosis,SPS with lower motor neuron disease,SPS with lower motor neuron disease,inferred_from_text,,,,"[""corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale"", ""Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves."", ""Examination of the spinal cord showed chromatolysis and vacuolisation of some anterior horn cells, as well as axonal swellings and slight gliosis.""]",TRUE,SPS is supported by SPS scale findings and continuous motor activity; lower motor neuron disease is supported by denervation and anterior horn cell pathology.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,early_symptoms,stiffness;spasms,stiffness;spasms,exact_quote,marked muscular rigidity and painful superimposed spasms,,,[],TRUE,Early symptoms include rigidity (stiffness) and painful spasms.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset,multiple,multiple,inferred_from_text,,,,"[""marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus""]",TRUE,Stiffness/rigidity involved more than one region early in the disease course.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;axial,lumb_prox_LE;distal_LE;axial,inferred_from_text,,,,"[""This was most prominent in the left leg, but subsequently also involved the right limb and truncus"", ""Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk""]",TRUE,"Leg involvement supports lower extremity categories, and truncus/trunk supports axial involvement.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_onset,fasciculation;muscle_atrophy,fasciculation;muscle_atrophy,exact_quote,followed by fasciculations and muscle atrophy in the left leg,,,[],TRUE,The text directly reports fasciculations and muscle atrophy early in the left leg.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,monophasic,inferred_from_text,,,,"[""The condition progressed rapidly"", ""The patient deteriorated rapidly and became bedridden"", ""He died from pneumonia 18 months after symptom onset.""]",TRUE,The text describes a single progressive/deteriorating course without relapses or remissions.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,onset_to_established,7,7,exact_quote,Neurological examination 7 months after symptom debut,,,[],TRUE,Established examination findings were recorded 7 months after symptom debut.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,overview_established,stiffness;spasms,stiffness;spasms,exact_quote,Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk,,,"[""triggered painful muscle cramps""]",TRUE,Established findings included muscle stiffness and stimulus-triggered painful cramps/spasms.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established,multiple,multiple,inferred_from_text,,,,"[""Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk""]",TRUE,"At established examination, stiffness was present in both legs and trunk, i.e. multiple regions.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial,lumb_prox_LE;distal_LE;axial,inferred_from_text,,,,"[""Muscle stiffness was prominent in the left leg but was also found in the right leg and the trunk""]",TRUE,Stiffness in the legs supports lower extremity involvement and trunk supports axial involvement.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_other,5/6 points in SPS stiffness extent scale,5/6 points in SPS stiffness extent scale,exact_quote,a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale,,,[],TRUE,The text directly reports five out of six points on the SPS stiffness extent scale.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,spasms_distribution_established,unspecified,unspecified,inferred_from_text,,,,"[""auditory, somatosensory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps"", ""became bedridden with almost continuous painful spasms in the left leg""]",TRUE,"Spasms/cramps are described, mainly left leg later, but a formal distribution category is not specified in the supplied text.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established,multiple,multiple,inferred_from_text,,,,"[""auditory, somatosensory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps""]",TRUE,"Multiple stimulus modalities triggered painful cramps, supporting multiple heightened sensitivity/startle triggers.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established_multipleother,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,exact_quote,"auditory, somatosensory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale",,,[],TRUE,"The text directly lists auditory, somatosensory, emotional, visual, and movement triggers and the six-of-seven score.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_established,hyporeflexia,hyporeflexia,inferred_from_text,,,,"[""The tendon reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms.""]",TRUE,Absent/weak tendon reflexes in the legs support hyporeflexia.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_status,GAD65,GAD65,exact_quote,Anti-GAD65 antibodies were markedly and persistently increased in serum,,,[],TRUE,Anti-GAD65 antibodies are directly reported as increased.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_titre,1.57,1.57,exact_quote,0.96–1.57 units at month 10 and 14 after symptom onset,,,[],TRUE,The serum anti-GAD65 antibody value includes 1.57 units.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_units,"""units""","""units""",exact_quote,0.96–1.57 units,2061,2076,[],TRUE,The antibody result is reported in units.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_tests,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,exact_quote,"antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal",,,[],TRUE,"The text lists these antibody tests, with voltage gated potassium channels, pancreas islets, DNA, and thyroxin peroxidase corresponding to the manual abbreviations.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_status,antibody_present;OCB,antibody_present;OCB,inferred_from_text,,,,"[""were also detected in CSF (0.84 units at month 10 after symptom onset)."", ""isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF""]",TRUE,Anti-GAD65 antibodies were present in CSF and GAD65-specific oligoclonal IgG bands were shown.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_antibody,GAD65,GAD65,exact_quote,Anti-GAD65 antibodies were markedly and persistently increased in serum,,,"[""were also detected in CSF""]",TRUE,The antibody detected in CSF was anti-GAD65.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CMUA,1,1,exact_quote,"Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity",,,[],TRUE,Continuous motor unit activity is directly supported by EMG continuous motor activity.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,MRI_normal,0,0,not_found,,,,[],FALSE,"The text says extensive radiological examinations of the neuraxis were normal, which would support normal imaging rather than the manual value 0; the manual value is not supported.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,tu_screening,0,0,not_found,,,,[],FALSE,"The text reports malignancy workout was normal and no malignancy at autopsy, which does not support a value of 0 if indicating not performed/positive; the manual value is not directly supportable from the supplied text.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy,IVIG;PLEX,IVIG;PLEX,inferred_from_text,,,,"[""intravenous immunoglobulins"", ""Plasma exchange was therefore performed 14 months after symptom onset""]",TRUE,The patient received intravenous immunoglobulin and plasma exchange.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,5x PLEX: no response. IVIG: 2g/kg,inferred_from_text,,,,"[""Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days."", ""The patient did not respond to plasma exchange."", ""Two g/kg intravenous immunoglobulin was given after another month""]",TRUE,The text supports five plasma exchange procedures with no response and IVIG at two g/kg.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,none,inferred_from_text,,,,"[""there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins."", ""The patient did not respond to plasma exchange."", ""Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms.""]",TRUE,Both IVIG and plasma exchange are described as ineffective/no response.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment,benzo;clonazepam;baclofen;phenytoin,benzo;clonazepam;baclofen;phenytoin,inferred_from_text,,,,"[""Intravenuos diazepam and clonazepam induced transient improvement"", ""no persistent response to these drugs or to baclofene, phenytoin""]",TRUE,"Diazepam is a benzodiazepine, and clonazepam, baclofen, and phenytoin are directly named.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_detail,"iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement","iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",inferred_from_text,,,,"[""Intravenuos diazepam and clonazepam induced transient improvement"", ""there was no persistent response to these drugs or to baclofene, phenytoin""]",TRUE,The text reports IV diazepam and clonazepam produced transient improvement and no persistent response to baclofen or phenytoin.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_effect,minimal improvement,minimal improvement,inferred_from_text,,,,"[""Intravenuos diazepam and clonazepam induced transient improvement"", ""there was no persistent response to these drugs or to baclofene, phenytoin""]",TRUE,"Only transient improvement occurred with benzodiazepines and no persistent response to other symptomatic treatments, supporting minimal improvement.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
537,,age_description,29,29,exact_quote,"A 29-year-old previously healthy African-
American male patient",821,884,[],TRUE,The case presentation directly states the patient was 29 years old.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sex,M,M,exact_quote,"African-
American male patient",854,884,[],TRUE,"The text directly identifies the patient as male, supporting M.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,ethnicity,africa,africa,exact_quote,"African-
American male patient",854,884,[],TRUE,"The text directly describes the patient as African-American, supporting the manual ethnicity value.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,age_onset,29,29,exact_quote,"A 29-year-old previously healthy African-
American male patient complained of
four-week history",821,916,[],TRUE,"Symptoms are described in a 29-year-old patient with a four-week history, supporting onset at age 29.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation,other,other,inferred_from_text,,,,"[""complained of\nfour-week history of progressive shortness\nof breath, non-productive cough and left-\nsided chest pain""]",TRUE,"The first described symptoms were not stiffness or spasms but respiratory/chest symptoms, corresponding to other.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation_multiple,dyspnoea,dyspnoea,exact_quote,"progressive shortness
of breath",920,951,[],TRUE,Dyspnoea is directly supported by the phrase progressive shortness of breath.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,paraneoplastic_SPS,inferred_from_text,,,,"[""His\nclinical picture was suggestive of SPS sec-\nondary to invasive thymoma."", ""the\ndiagnosis of SPS was made"", ""pathology specimen being\nconsistent with lymphocytic pre-\ndominant epithelial type thymoma""]",TRUE,"SPS is diagnosed and described as secondary to invasive thymoma, supporting paraneoplastic SPS.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_onset,dyspnoea,dyspnoea,exact_quote,"progressive shortness
of breath",920,951,[],TRUE,"The onset symptoms included shortness of breath, equivalent to dyspnoea.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,timecourse_subsequent,monophasic,monophasic,inferred_from_text,,,,"[""at five-month follow up he did-\nn’t have any recurrence of his symp-\ntoms""]",TRUE,No recurrence at follow-up supports a single monophasic episode/course.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,overview_established,stiffness;spasms,stiffness;spasms,exact_quote,"muscle spasms, rigidity",149,172,[],TRUE,The abstract describes SPS features including muscle spasms and rigidity/stiffness.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established,multiple,multiple,inferred_from_text,,,,"[""truncal, lower ex-\ntremities stiffness"", ""diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain""]",TRUE,"Stiffness involved both trunk/lower back and lower extremities, supporting multiple distributions.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established_multiple,distal_LE;lumb_prox_LE;axial,distal_LE;lumb_prox_LE;axial,inferred_from_text,,,,"[""truncal, lower ex-\ntremities stiffness"", ""diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain""]",TRUE,"Text supports axial/truncal and lower extremity involvement, with lower back and both lower extremities consistent with listed distributions.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established,multiple,multiple,inferred_from_text,,,,"[""truncal, lower ex-\ntremities stiffness and painful cramps"", ""severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs""]",TRUE,"Painful cramps/muscle cramps are described with truncal/lower extremity context and both legs, supporting multiple involvement.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,distal_LE;lumb_prox_LE,inferred_from_text,,,,"[""severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs"", ""truncal, lower ex-\ntremities stiffness and painful cramps""]",TRUE,"Muscle cramps in both legs/lower extremities support lower extremity spasm distribution, though exact distal/proximal subdivision is inferred.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_established,pain;weakness,pain;weakness,exact_quote,"severe bi-
lateral lower extremity pain, muscle
cramps and weakness in both legs",2453,2533,[],TRUE,The text directly states lower extremity pain and weakness in both legs.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,antibody_status,GAD,GAD,not_found,,,,[],FALSE,"The text states anti-GAD antibodies were included in testing but the result was negative, so a GAD-positive status is not supported.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,antibody_tests,GAD;AChR,GAD;AChR,exact_quote,"anti-GAD antibodies; the result was
negative. Myasthenia gravis was
ruled out by a normal pulmonary
function test and a negative anti-
AChR antibodies test",3160,3315,[],TRUE,The text directly mentions anti-GAD and anti-AChR antibody tests.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening,1,1,inferred_from_text,,,,"[""Computed tomog-\nraphy of the chest demonstrated a large\nleft-sided pleural effusion and a large an-\nterior mediastinal mass"", ""PET scan\nshowed anterior mediastinal mass""]",TRUE,Tumor evaluation/screening was performed with chest CT and PET showing a mediastinal mass.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening_abnormal,thymoma invasive lymphocytic predominant epithelial type,thymoma invasive lymphocytic predominant epithelial type,inferred_from_text,,,,"[""pathology specimen being\nconsistent with lymphocytic pre-\ndominant epithelial type thymoma"", ""Due to the invasive behavior of this\nneoplasm""]",TRUE,"Pathology identified lymphocytic predominant epithelial type thymoma, and the neoplasm was described as invasive.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment,benzo;morphine,benzo;morphine,exact_quote,"diazepam 5 mg intravenously
along with intravenous morphine",2926,2985,[],TRUE,Diazepam is a benzodiazepine and morphine is directly named.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment_detail,diazepam 5mg iv and morphine with complete resolution of neurological symptoms,diazepam 5mg iv and morphine with complete resolution of neurological symptoms,exact_quote,"Patient was
given diazepam 5 mg intravenously
along with intravenous morphine
with complete resolution of his
symptoms.",2908,3027,[],TRUE,The sentence directly supports diazepam 5 mg IV plus IV morphine with complete symptom resolution.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment_effect,improvement,improvement,exact_quote,"complete resolution of his
symptoms",2991,3026,[],TRUE,Complete resolution directly supports improvement.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_treatment,resection and chemotherapy of thymoma with complete resolution of neurological symptoms,resection and chemotherapy of thymoma with complete resolution of neurological symptoms,not_found,,,,[],FALSE,"Chemotherapy is supported, but surgical resection was deferred/not an option; therefore the full manual value including resection is not supported.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
551,,age_description,51,51,exact_quote,A 51-year-old white man,12,35,[],TRUE,The case report directly states the patient was 51 years old.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,sex,M,M,exact_quote,white man,26,35,[],TRUE,The term 'man' directly supports male sex.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,ethnicity,white,white,exact_quote,white man,26,35,[],TRUE,The source directly describes the patient as white.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,age_onset,51,51,inferred_from_text,,,,"[""A 51-year-old white man"", ""History revealed an onset of leg pain and falls over the last 6 months""]",TRUE,"The patient was 51 at presentation and onset occurred over the prior 6 months, supporting onset around age 51.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,time_to_diagnosis,0.5,0.5,inferred_from_text,,,,"[""History revealed an onset of leg pain and falls over the last 6 months"", ""His current neurologist had diagnosed stiff-man syndrome""]",TRUE,"Symptoms began over the last 6 months and stiff-man syndrome had been diagnosed by the current neurologist, supporting approximately 0.5 years to diagnosis.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,first_manifestation,multiple,multiple,inferred_from_text,,,,"[""History revealed an onset of leg pain and falls over the last 6 months""]",TRUE,The onset description includes more than one manifestation: leg pain and falls/weakness-related gait impairment.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,first_manifestation_multiple,pain;weakness,pain;weakness,inferred_from_text,,,,"[""History revealed an onset of leg pain and falls over the last 6 months"", ""He was complaining of weakness on his right side and numbness in his right foot.""]",TRUE,"Leg pain is directly described at onset; weakness is clinically supported by complaints of weakness and falls, though the onset phrase itself says falls rather than weakness.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,included_diagnosis,Stiff_Person,Stiff_Person,exact_quote,His current neurologist had diagnosed stiff-man syndrome,,,[],TRUE,The diagnosis is directly stated as stiff-man syndrome.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,early_symptoms,spasms,spasms,inferred_from_text,,,,"[""slight tremors in his legs while sleeping with occasional daytime twitching in his face"", ""kicking his legs on the bed boards""]",TRUE,"Early tremors/twitching and leg kicking are compatible with spasms, but the exact word spasms is not used.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,spasms_distribution_onset,multiple,multiple,inferred_from_text,,,,"[""slight tremors in his legs while sleeping with occasional daytime twitching in his face""]",TRUE,Abnormal movements are described in more than one region: legs and face.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,spasms_distribution_onset_multiple,distal_LE;lumb_prox_LE,distal_LE;lumb_prox_LE,not_found,,,,[],FALSE,The source mentions leg tremors but does not localize onset spasms to distal lower extremity and lumbar/proximal lower extremity distributions.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,other_symptoms_onset,gait_disorder,gait_disorder,inferred_from_text,,,,"[""History revealed an onset of leg pain and falls over the last 6 months; he used a cane initially, then a wheelchair, while outside his home.""]",TRUE,Falls and progression from cane to wheelchair support gait disorder at onset.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,onset_mRS,3,3,inferred_from_text,,,,"[""he used a cane initially, then a wheelchair, while outside his home""]",TRUE,"Use of cane/wheelchair suggests moderate disability requiring assistance, consistent with an inferred mRS of 3.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,diagnosis_onset,functional,functional,not_found,,,,[],FALSE,"The text describes later concerns for psychogenic seizures/conversion disorder, but does not state the onset diagnosis was functional.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,onset_to_established,6,6,exact_quote,onset of leg pain and falls over the last 6 months,,,[],TRUE,The source directly gives a 6-month interval from onset to the current established presentation.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,overview_established,spasms,spasms,inferred_from_text,,,,"[""seizure-like episodes"", ""one tonic-clonic seizure episode (mainly in the lower left extremities)"", ""kicking his legs on the bed boards""]",TRUE,"Established episodes involved lower-extremity tonic-clonic/twitching or kicking movements, clinically consistent with spasms, though 'spasms' is not directly stated.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,spasms_distribution_established,multiple,multiple,inferred_from_text,,,,"[""one tonic-clonic seizure episode (mainly in the lower left extremities)"", ""complaining of weakness on his right side and numbness in his right foot"", ""kicking his legs on the bed boards""]",TRUE,"Abnormal motor symptoms involved lower extremities and right-sided complaints, supporting multiple distribution broadly, but precise distribution is not directly stated.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,distal_LE;lumb_prox_LE,not_found,,,,[],FALSE,The text does not specify distal lower extremity plus lumbar/proximal lower extremity distribution for established spasms.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,excessive_startle_established,noise,noise,exact_quote,noises (beeps of the cardiac monitor and loud visitors) tended to set off his spells,,,[],TRUE,Noises are directly reported to trigger spells.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,other_symptoms_established,gait_disorder;seizures,gait_disorder;seizures,exact_quote,intractable seizure-like episodes,,,"[""suffering a fall from his wheelchair"", ""intractable seizure-like episodes""]",TRUE,"Seizure-like episodes are directly stated, and wheelchair/fall supports gait disorder.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,other_symptoms_established_seizures,functional seizure (EEG normal),functional seizure (EEG normal),inferred_from_text,,,,"[""concerns that the patient may be experiencing psychogenic seizure episodes"", ""The EEG, CT myelogram, and head CT were all found to be within normal limits."", ""one consistent with conversion disorder""]",TRUE,Psychogenic seizure episodes/conversion disorder with normal EEG supports functional seizure with normal EEG.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,established_mRS,4,4,inferred_from_text,,,,"[""suffering a fall from his wheelchair"", ""he used a cane initially, then a wheelchair, while outside his home""]",TRUE,"Wheelchair use supports moderately severe disability, consistent with inferred mRS 4.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,immunotherapy,none,none,not_found,,,,[],FALSE,The source does not state that no immunotherapy was given.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,sympt_treatment,benzo;baclofen,benzo;baclofen,exact_quote,"diazepam (now at 15 mg every 6 hours), baclofen (5 mg t.i.d.)",,,[],TRUE,Diazepam is a benzodiazepine and baclofen is directly listed; the treatment regimen is stated.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,sympt_treatment_detail,"diazepam 15mg every 6h, baclofen 5mg tid","diazepam 15mg every 6h, baclofen 5mg tid",exact_quote,"diazepam (now at 15 mg every 6 hours), baclofen (5 mg t.i.d.)",,,[],TRUE,The dosing details match the manual value.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,other_treatment,physical therapy with benefit,physical therapy with benefit,exact_quote,physical therapy consults had proven helpful,,,[],TRUE,Physical therapy and benefit are directly stated.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
552,,age_description,49,49,exact_quote,A 49-year-old male,0,18,[],TRUE,Age is directly stated.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,sex,M,M,exact_quote,A 49-year-old male,0,18,[],TRUE,Male supports sex coded as M.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,ethnicity,NA,NA,not_found,,,,[],FALSE,Ethnicity is not reported in the source text.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,time_to_diagnosis,0.5,0.5,inferred_from_text,,,,"[""progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration"", ""He was diagnosed with SPS""]",TRUE,Six months' symptom duration before diagnosis corresponds to 0.5 years.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,first_manifestation,multiple,multiple,inferred_from_text,,,,"[""presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration"", ""He experienced constant hip pain""]",TRUE,"Initial presentation included multiple manifestations: rigidity/stiffness, spasms, and pain.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,first_manifestation_multiple,stiffness;spasms;pain,stiffness;spasms;pain,inferred_from_text,,,,"[""progressively worsening muscle rigidity and spasms"", ""He experienced constant hip pain""]",TRUE,"Muscle rigidity supports stiffness, with spasms and hip pain also directly described.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,included_diagnosis,Stiff_Person,Stiff_Person,exact_quote,He was diagnosed with SPS,1211,1236,[],TRUE,SPS is the diagnosis stated in the source.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,early_symptoms,"stiffness,spasms","stiffness,spasms",inferred_from_text,,,,"[""presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration""]",TRUE,"Early symptoms included rigidity, corresponding to stiffness, and spasms.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,stiffness_distribution_onset,multiple,multiple,inferred_from_text,,,,"[""muscle rigidity and spasms of his upper and lower extremities"", ""constant hip pain""]",TRUE,"Onset rigidity involved upper and lower extremities with hip involvement, supporting multiple regions.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;UE,lumb_prox_LE;distal_LE;UE,inferred_from_text,,,,"[""muscle rigidity and spasms of his upper and lower extremities"", ""constant hip pain""]",TRUE,"Upper extremities support UE; lower extremities support distal/proximal LE, and hip pain supports lumboproximal/lower proximal involvement.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,spasms_distribution_onset,multiple,multiple,exact_quote,spasms of his upper and lower extremities,,,[],TRUE,Spasms are reported in more than one body distribution.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,spasms_distribution_onset_multiple,lumb_prox_LE;distal_LE;UE,lumb_prox_LE;distal_LE;UE,inferred_from_text,,,,"[""muscle rigidity and spasms of his upper and lower extremities"", ""constant hip pain""]",TRUE,Spasms in upper and lower extremities support UE and LE distributions; hip symptoms support lumboproximal region only indirectly.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,stiffness_distribution_established,generalised,generalised,exact_quote,Physical examination revealed generalized rigidity,,,[],TRUE,Established examination described generalized rigidity.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_status,GAD,GAD,exact_quote,Anti– glutamic acid decarboxylase 65 antibody was elevated,,,[],TRUE,GAD65 antibody elevation supports GAD antibody status.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_titre,609,609,exact_quote,609 nmol/L,1108,1118,[],TRUE,Antibody titre value is directly stated.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_units,nmol/L,nmol/L,exact_quote,609 nmol/L,1108,1118,[],TRUE,Antibody units are directly stated.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_tests,GAD,GAD,exact_quote,Anti– glutamic acid decarboxylase 65 antibody,,,[],TRUE,The antibody test described was anti-GAD65.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,CMUA,1,1,exact_quote,Electromyography showed continuous motor unit activity,,,[],TRUE,"Continuous

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan.csv
paper_id,case_id,field_name,spreadsheet_value,model_spreadsheet_value,original_evidence_mode,original_validator_status,coverage_quality,langextract_recommendation,support_span_count,all_spans_exact_in_stage07_text,support_spans_json,support_spans_display,target_view_json_path
524,,age_description,67,67,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""67-year-old male"", ""char_start"": 37, ""char_end"": 53, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",67-year-old male,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sex,M,M,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""67-year-old male"", ""char_start"": 37, ""char_end"": 53, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",67-year-old male,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,ethnicity,white,white,not_found,needs_review,context_or_absence_only_not_direct_extraction,do_not_promote_as_standard_langextract_example,1,TRUE,"[{""span_text"": ""A previously healthy 67-year-old male presented"", ""char_start"": 16, ""char_end"": 63, ""selection_source"": ""manual_audit_override_1"", ""match_mode"": ""exact"", ""span_role"": ""absence_context""}]",A previously healthy 67-year-old male presented,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,age_onset,67,67,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""A previously healthy 67-year-old male presented with rapidly\nevolving and painful ﬂexor cramps of the toes on his left foot"", ""char_start"": 16, ""char_end"": 139, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""He died from pneumonia 18 months after symptom onset."", ""char_start"": 3414, ""char_end"": 3467, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot | He died from pneumonia 18 months after symptom onset.,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,FU_duration,18,18,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""He died from pneumonia 18 months after symptom onset."", ""char_start"": 3414, ""char_end"": 3467, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",He died from pneumonia 18 months after symptom onset.,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""presented with rapidly\nevolving and painful ﬂexor cramps of the toes on his left foot, fol-\nlowed by fasciculations and muscle atrophy in the left leg"", ""char_start"": 54, ""char_end"": 204, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The\ncondition progressed rapidly with marked muscular rigidity and\npainful superimposed spasms."", ""char_start"": 206, ""char_end"": 301, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg | The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation_multiple,cramps;fasciculation;atrophy;stiffness;spasms,cramps;fasciculation;atrophy;stiffness;spasms,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""presented with rapidly\nevolving and painful ﬂexor cramps of the toes on his left foot, fol-\nlowed by fasciculations and muscle atrophy in the left leg"", ""char_start"": 54, ""char_end"": 204, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The\ncondition progressed rapidly with marked muscular rigidity and\npainful superimposed spasms."", ""char_start"": 206, ""char_end"": 301, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg | The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,included_diagnosis,SPS with lower motor neuron disease,SPS with lower motor neuron disease,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""corresponding to a stiffness score of ﬁve out of six possible points at\nthe SPS stiffness extent scale"", ""char_start"": 682, ""char_end"": 784, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Electromyography of the left leg 10, 13, 14 and 16 months after\nsymptom onset showed continuous motor activity and signs of\ndenervation with positive sharp waves."", ""char_start"": 1193, ""char_end"": 1355, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale | Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,early_symptoms,stiffness;spasms,stiffness;spasms,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""marked muscular rigidity and\npainful superimposed spasms"", ""char_start"": 244, ""char_end"": 300, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",marked muscular rigidity and painful superimposed spasms,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""marked muscular rigidity and\npainful superimposed spasms. This was most prominent in the left\nleg, but subsequently also involved the right limb and truncus"", ""char_start"": 244, ""char_end"": 400, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;axial,lumb_prox_LE;distal_LE;axial,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""This was most prominent in the left\nleg, but subsequently also involved the right limb and truncus"", ""char_start"": 302, ""char_end"": 400, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","This was most prominent in the left leg, but subsequently also involved the right limb and truncus | Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_onset,fasciculation;muscle_atrophy,fasciculation;muscle_atrophy,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""fol-\nlowed by fasciculations and muscle atrophy in the left leg"", ""char_start"": 141, ""char_end"": 204, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",fol- lowed by fasciculations and muscle atrophy in the left leg,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,monophasic,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""The\ncondition progressed rapidly"", ""char_start"": 206, ""char_end"": 238, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The\npatient deteriorated rapidly and became bedridden"", ""char_start"": 2627, ""char_end"": 2680, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""He died from pneumonia 18 months after symptom onset."", ""char_start"": 3414, ""char_end"": 3467, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",The condition progressed rapidly | The patient deteriorated rapidly and became bedridden | He died from pneumonia 18 months after symptom onset.,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,onset_to_established,7,7,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Neurological examination\n7 months after symptom debut"", ""char_start"": 449, ""char_end"": 502, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Neurological examination 7 months after symptom debut,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,overview_established,stiffness;spasms,stiffness;spasms,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""triggered painful muscle cramps"", ""char_start"": 891, ""char_end"": 922, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk | triggered painful muscle cramps,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial,lumb_prox_LE;distal_LE;axial,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_other,5/6 points in SPS stiffness extent scale,5/6 points in SPS stiffness extent scale,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""a stiffness score of ﬁve out of six possible points at\nthe SPS stiffness extent scale"", ""char_start"": 699, ""char_end"": 784, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,spasms_distribution_established,unspecified,unspecified,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""auditory, somatosen-\nsory, emotional and visual stimuli and attempts to move the left leg\ntriggered painful muscle cramps"", ""char_start"": 801, ""char_end"": 922, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""became bedridden with almost\ncontinuous painful spasms in the left leg"", ""char_start"": 2664, ""char_end"": 2734, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps | became bedridden with almost continuous painful spasms in the left leg",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""auditory, somatosen-\nsory, emotional and visual stimuli and attempts to move the left leg\ntriggered painful muscle cramps"", ""char_start"": 801, ""char_end"": 922, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established_multipleother,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""auditory, somatosen-\nsory, emotional and visual stimuli and attempts to move the left leg\ntriggered painful muscle cramps, corresponding to six out of seven\n\npossible points at the SPS heightened sensitivity scale"", ""char_start"": 801, ""char_end"": 1014, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_established,hyporeflexia,hyporeflexia,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""The ten-\ndon reﬂexes were absent in the left leg, weak in the right leg, and\nnormal in both arms"", ""char_start"": 1020, ""char_end"": 1116, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","The ten- don reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_status,GAD65,GAD65,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Anti-GAD65 antibodies were markedly and persis-\ntently increased in serum"", ""char_start"": 1986, ""char_end"": 2059, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",Anti-GAD65 antibodies were markedly and persis- tently increased in serum,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_titre,1.57,1.57,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""0.96–1.57 units at month 10 and 14 after\nsymptom onset"", ""char_start"": 2061, ""char_end"": 2115, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",0.96–1.57 units at month 10 and 14 after symptom onset,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_units,"""units""","""units""",exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""0.96–1.57 units"", ""char_start"": 2061, ""char_end"": 2076, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",0.96–1.57 units,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_tests,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""antibodies against gangliosides, voltage gated potassium\nchannels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin\nperoxidase were all normal"", ""char_start"": 1520, ""char_end"": 1669, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_status,antibody_present;OCB,antibody_present;OCB,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""were also detected\nin CSF (0.84 units at month 10 after symptom onset)."", ""char_start"": 2149, ""char_end"": 2220, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""isoelectric focusing-immunoblot displayed several GAD65 speciﬁc\noligoclonal IgG bands in CSF"", ""char_start"": 2302, ""char_end"": 2394, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",were also detected in CSF (0.84 units at month 10 after symptom onset). | isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_antibody,GAD65,GAD65,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Anti-GAD65 antibodies were markedly and persis-\ntently increased in serum"", ""char_start"": 1986, ""char_end"": 2059, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""were also detected\nin CSF"", ""char_start"": 2149, ""char_end"": 2174, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Anti-GAD65 antibodies were markedly and persis- tently increased in serum | were also detected in CSF,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CMUA,1,1,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Electromyography of the left leg 10, 13, 14 and 16 months after\nsymptom onset showed continuous motor activity"", ""char_start"": 1193, ""char_end"": 1303, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,MRI_normal,0,0,not_found,needs_review,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""extensive radiological examinations of the neuraxis"", ""char_start"": 1447, ""char_end"": 1498, ""selection_source"": ""manual_audit_override_1"", ""match_mode"": ""exact"", ""span_role"": ""support""}, {""span_text"": ""were all normal"", ""char_start"": 1654, ""char_end"": 1669, ""selection_source"": ""manual_audit_override_2"", ""match_mode"": ""exact"", ""span_role"": ""support""}]",extensive radiological examinations of the neuraxis | were all normal,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,tu_screening,0,0,not_found,needs_review,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""malignancy\nworkout"", ""char_start"": 1500, ""char_end"": 1518, ""selection_source"": ""manual_audit_override_1"", ""match_mode"": ""manual_override_folded_alnum_to_exact_source"", ""span_role"": ""support""}, {""span_text"": ""were all normal"", ""char_start"": 1654, ""char_end"": 1669, ""selection_source"": ""manual_audit_override_2"", ""match_mode"": ""exact"", ""span_role"": ""support""}, {""span_text"": ""No signs of malignancy were detected at autopsy"", ""char_start"": 3468, ""char_end"": 3515, ""selection_source"": ""manual_audit_override_3"", ""match_mode"": ""exact"", ""span_role"": ""support""}]",malignancy workout | were all normal | No signs of malignancy were detected at autopsy,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy,IVIG;PLEX,IVIG;PLEX,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""intravenous immunoglobulins"", ""char_start"": 2598, ""char_end"": 2625, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""Plasma exchange was\ntherefore performed 14 months after symptom onset"", ""char_start"": 2736, ""char_end"": 2805, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",intravenous immunoglobulins | Plasma exchange was therefore performed 14 months after symptom onset,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,5x PLEX: no response. IVIG: 2g/kg,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""Plasma exchange was\ntherefore performed 14 months after symptom onset with removal\nof 3 l of plasma at ﬁve subsequent days."", ""char_start"": 2736, ""char_end"": 2859, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The patient did not respond\nto plasma exchange."", ""char_start"": 3121, ""char_end"": 3168, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Two g/kg intravenous immunoglobulin was given after another\nmonth"", ""char_start"": 3277, ""char_end"": 3342, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days. | The patient did not respond to plasma exchange. | Two g/kg intravenous immunoglobulin was given after another month,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,none,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""there was no persistent response to these drugs\nor to baclofene, phenytoin and intravenous immunoglobulins."", ""char_start"": 2519, ""char_end"": 2626, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The patient did not respond\nto plasma exchange."", ""char_start"": 3121, ""char_end"": 3168, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Two g/kg intravenous immunoglobulin was given after another\nmonth, but did not affect the increasing rigidity and painful muscle\nspasms."", ""char_start"": 3277, ""char_end"": 3413, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins. | The patient did not respond to plasma exchange. | Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment,benzo;clonazepam;baclofen;phenytoin,benzo;clonazepam;baclofen;phenytoin,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Intravenuos diazepam and clonazepam induced transient\nimprovement"", ""char_start"": 2448, ""char_end"": 2513, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""no persistent response to these drugs\nor to baclofene, phenytoin"", ""char_start"": 2529, ""char_end"": 2593, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Intravenuos diazepam and clonazepam induced transient improvement | no persistent response to these drugs or to baclofene, phenytoin",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_detail,"iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement","iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Intravenuos diazepam and clonazepam induced transient\nimprovement"", ""char_start"": 2448, ""char_end"": 2513, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""there was no persistent response to these drugs\nor to baclofene, phenytoin"", ""char_start"": 2519, ""char_end"": 2593, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Intravenuos diazepam and clonazepam induced transient improvement | there was no persistent response to these drugs or to baclofene, phenytoin",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_effect,minimal improvement,minimal improvement,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Intravenuos diazepam and clonazepam induced transient\nimprovement"", ""char_start"": 2448, ""char_end"": 2513, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""there was no persistent response to these drugs\nor to baclofene, phenytoin"", ""char_start"": 2519, ""char_end"": 2593, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Intravenuos diazepam and clonazepam induced transient improvement | there was no persistent response to these drugs or to baclofene, phenytoin",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
537,,age_description,29,29,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""A 29-year-old previously healthy African-\nAmerican male patient"", ""char_start"": 821, ""char_end"": 884, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A 29-year-old previously healthy African- American male patient,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sex,M,M,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""African-\nAmerican male patient"", ""char_start"": 854, ""char_end"": 884, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",African- American male patient,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,ethnicity,africa,africa,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""African-\nAmerican male patient"", ""char_start"": 854, ""char_end"": 884, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",African- American male patient,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,age_onset,29,29,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""A 29-year-old previously healthy African-\nAmerican male patient complained of\nfour-week history"", ""char_start"": 821, ""char_end"": 916, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A 29-year-old previously healthy African- American male patient complained of four-week history,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation,other,other,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""complained of\nfour-week history of progressive shortness\nof breath, non-productive cough and left-\nsided chest pain"", ""char_start"": 885, ""char_end"": 1000, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","complained of four-week history of progressive shortness of breath, non-productive cough and left- sided chest pain",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation_multiple,dyspnoea,dyspnoea,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""progressive shortness\nof breath"", ""char_start"": 920, ""char_end"": 951, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",progressive shortness of breath,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,paraneoplastic_SPS,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,3,TRUE,"[{""span_text"": ""His\nclinical picture was suggestive of SPS sec-\nondary to invasive thymoma."", ""char_start"": 418, ""char_end"": 493, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""the\ndiagnosis of SPS was made"", ""char_start"": 3435, ""char_end"": 3464, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""pathology specimen being\nconsistent with lymphocytic pre-\ndominant epithelial type thymoma"", ""char_start"": 1990, ""char_end"": 2080, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",His clinical picture was suggestive of SPS sec- ondary to invasive thymoma. | the diagnosis of SPS was made | pathology specimen being consistent with lymphocytic pre- dominant epithelial type thymoma,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_onset,dyspnoea,dyspnoea,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""progressive shortness\nof breath"", ""char_start"": 920, ""char_end"": 951, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",progressive shortness of breath,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,timecourse_subsequent,monophasic,monophasic,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""at five-month follow up he did-\nn’t have any recurrence of his symp-\ntoms"", ""char_start"": 3511, ""char_end"": 3584, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",at five-month follow up he did- n’t have any recurrence of his symp- toms,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,overview_established,stiffness;spasms,stiffness;spasms,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""muscle spasms, rigidity"", ""char_start"": 149, ""char_end"": 172, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","muscle spasms, rigidity",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established,multiple,multiple,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""truncal, lower ex-\ntremities stiffness"", ""char_start"": 322, ""char_end"": 360, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain"", ""char_start"": 2762, ""char_end"": 2853, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","truncal, lower ex- tremities stiffness | diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established_multiple,distal_LE;lumb_prox_LE;axial,distal_LE;lumb_prox_LE;axial,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""truncal, lower ex-\ntremities stiffness"", ""char_start"": 322, ""char_end"": 360, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain"", ""char_start"": 2762, ""char_end"": 2853, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","truncal, lower ex- tremities stiffness | diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established,multiple,multiple,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""truncal, lower ex-\ntremities stiffness and painful cramps"", ""char_start"": 322, ""char_end"": 379, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs"", ""char_start"": 2453, ""char_end"": 2533, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","truncal, lower ex- tremities stiffness and painful cramps | severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,distal_LE;lumb_prox_LE,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs"", ""char_start"": 2453, ""char_end"": 2533, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""truncal, lower ex-\ntremities stiffness and painful cramps"", ""char_start"": 322, ""char_end"": 379, ""selection

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan_draft.csv
paper_id,case_id,field_name,spreadsheet_value,model_spreadsheet_value,original_evidence_mode,original_validator_status,coverage_quality,langextract_recommendation,support_span_count,all_spans_exact_in_stage07_text,support_spans_json,support_spans_display,target_view_json_path
524,,age_description,67,67,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""67-year-old male"", ""char_start"": 37, ""char_end"": 53, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",67-year-old male,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sex,M,M,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""67-year-old male"", ""char_start"": 37, ""char_end"": 53, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",67-year-old male,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,ethnicity,white,white,not_found,needs_review,needs_human_adjudication,review_before_promoting,0,FALSE,[],,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,age_onset,67,67,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""A previously healthy 67-year-old male presented with rapidly\nevolving and painful ﬂexor cramps of the toes on his left foot"", ""char_start"": 16, ""char_end"": 139, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""He died from pneumonia 18 months after symptom onset."", ""char_start"": 3414, ""char_end"": 3467, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot | He died from pneumonia 18 months after symptom onset.,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,FU_duration,18,18,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""He died from pneumonia 18 months after symptom onset."", ""char_start"": 3414, ""char_end"": 3467, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",He died from pneumonia 18 months after symptom onset.,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""presented with rapidly\nevolving and painful ﬂexor cramps of the toes on his left foot, fol-\nlowed by fasciculations and muscle atrophy in the left leg"", ""char_start"": 54, ""char_end"": 204, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The\ncondition progressed rapidly with marked muscular rigidity and\npainful superimposed spasms."", ""char_start"": 206, ""char_end"": 301, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg | The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation_multiple,cramps;fasciculation;atrophy;stiffness;spasms,cramps;fasciculation;atrophy;stiffness;spasms,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""presented with rapidly\nevolving and painful ﬂexor cramps of the toes on his left foot, fol-\nlowed by fasciculations and muscle atrophy in the left leg"", ""char_start"": 54, ""char_end"": 204, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The\ncondition progressed rapidly with marked muscular rigidity and\npainful superimposed spasms."", ""char_start"": 206, ""char_end"": 301, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg | The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,included_diagnosis,SPS with lower motor neuron disease,SPS with lower motor neuron disease,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""corresponding to a stiffness score of ﬁve out of six possible points at\nthe SPS stiffness extent scale"", ""char_start"": 682, ""char_end"": 784, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Electromyography of the left leg 10, 13, 14 and 16 months after\nsymptom onset showed continuous motor activity and signs of\ndenervation with positive sharp waves."", ""char_start"": 1193, ""char_end"": 1355, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale | Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,early_symptoms,stiffness;spasms,stiffness;spasms,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""marked muscular rigidity and\npainful superimposed spasms"", ""char_start"": 244, ""char_end"": 300, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",marked muscular rigidity and painful superimposed spasms,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""marked muscular rigidity and\npainful superimposed spasms. This was most prominent in the left\nleg, but subsequently also involved the right limb and truncus"", ""char_start"": 244, ""char_end"": 400, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;axial,lumb_prox_LE;distal_LE;axial,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""This was most prominent in the left\nleg, but subsequently also involved the right limb and truncus"", ""char_start"": 302, ""char_end"": 400, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","This was most prominent in the left leg, but subsequently also involved the right limb and truncus | Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_onset,fasciculation;muscle_atrophy,fasciculation;muscle_atrophy,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""fol-\nlowed by fasciculations and muscle atrophy in the left leg"", ""char_start"": 141, ""char_end"": 204, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",fol- lowed by fasciculations and muscle atrophy in the left leg,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,monophasic,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""The\ncondition progressed rapidly"", ""char_start"": 206, ""char_end"": 238, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The\npatient deteriorated rapidly and became bedridden"", ""char_start"": 2627, ""char_end"": 2680, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""He died from pneumonia 18 months after symptom onset."", ""char_start"": 3414, ""char_end"": 3467, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",The condition progressed rapidly | The patient deteriorated rapidly and became bedridden | He died from pneumonia 18 months after symptom onset.,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,onset_to_established,7,7,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Neurological examination\n7 months after symptom debut"", ""char_start"": 449, ""char_end"": 502, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Neurological examination 7 months after symptom debut,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,overview_established,stiffness;spasms,stiffness;spasms,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""triggered painful muscle cramps"", ""char_start"": 891, ""char_end"": 922, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk | triggered painful muscle cramps,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial,lumb_prox_LE;distal_LE;axial,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Muscle stiffness was promi-\nnent in the left leg but was also found in the right leg and the trunk"", ""char_start"": 582, ""char_end"": 680, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_other,5/6 points in SPS stiffness extent scale,5/6 points in SPS stiffness extent scale,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""a stiffness score of ﬁve out of six possible points at\nthe SPS stiffness extent scale"", ""char_start"": 699, ""char_end"": 784, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,spasms_distribution_established,unspecified,unspecified,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""auditory, somatosen-\nsory, emotional and visual stimuli and attempts to move the left leg\ntriggered painful muscle cramps"", ""char_start"": 801, ""char_end"": 922, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""became bedridden with almost\ncontinuous painful spasms in the left leg"", ""char_start"": 2664, ""char_end"": 2734, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps | became bedridden with almost continuous painful spasms in the left leg",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established,multiple,multiple,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""auditory, somatosen-\nsory, emotional and visual stimuli and attempts to move the left leg\ntriggered painful muscle cramps"", ""char_start"": 801, ""char_end"": 922, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established_multipleother,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""auditory, somatosen-\nsory, emotional and visual stimuli and attempts to move the left leg\ntriggered painful muscle cramps, corresponding to six out of seven\n\npossible points at the SPS heightened sensitivity scale"", ""char_start"": 801, ""char_end"": 1014, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_established,hyporeflexia,hyporeflexia,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""The ten-\ndon reﬂexes were absent in the left leg, weak in the right leg, and\nnormal in both arms"", ""char_start"": 1020, ""char_end"": 1116, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]","The ten- don reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_status,GAD65,GAD65,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Anti-GAD65 antibodies were markedly and persis-\ntently increased in serum"", ""char_start"": 1986, ""char_end"": 2059, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}]",Anti-GAD65 antibodies were markedly and persis- tently increased in serum,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_titre,1.57,1.57,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""0.96–1.57 units at month 10 and 14 after\nsymptom onset"", ""char_start"": 2061, ""char_end"": 2115, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",0.96–1.57 units at month 10 and 14 after symptom onset,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_units,"""units""","""units""",exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""0.96–1.57 units"", ""char_start"": 2061, ""char_end"": 2076, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",0.96–1.57 units,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_tests,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""antibodies against gangliosides, voltage gated potassium\nchannels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin\nperoxidase were all normal"", ""char_start"": 1520, ""char_end"": 1669, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_status,antibody_present;OCB,antibody_present;OCB,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""were also detected\nin CSF (0.84 units at month 10 after symptom onset)."", ""char_start"": 2149, ""char_end"": 2220, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""isoelectric focusing-immunoblot displayed several GAD65 speciﬁc\noligoclonal IgG bands in CSF"", ""char_start"": 2302, ""char_end"": 2394, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",were also detected in CSF (0.84 units at month 10 after symptom onset). | isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_antibody,GAD65,GAD65,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Anti-GAD65 antibodies were markedly and persis-\ntently increased in serum"", ""char_start"": 1986, ""char_end"": 2059, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""folded_alnum_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""were also detected\nin CSF"", ""char_start"": 2149, ""char_end"": 2174, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Anti-GAD65 antibodies were markedly and persis- tently increased in serum | were also detected in CSF,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CMUA,1,1,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Electromyography of the left leg 10, 13, 14 and 16 months after\nsymptom onset showed continuous motor activity"", ""char_start"": 1193, ""char_end"": 1303, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,MRI_normal,0,0,not_found,needs_review,needs_human_adjudication,review_before_promoting,0,FALSE,[],,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,tu_screening,0,0,not_found,needs_review,needs_human_adjudication,review_before_promoting,0,FALSE,[],,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy,IVIG;PLEX,IVIG;PLEX,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""intravenous immunoglobulins"", ""char_start"": 2598, ""char_end"": 2625, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""Plasma exchange was\ntherefore performed 14 months after symptom onset"", ""char_start"": 2736, ""char_end"": 2805, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",intravenous immunoglobulins | Plasma exchange was therefore performed 14 months after symptom onset,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,5x PLEX: no response. IVIG: 2g/kg,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""Plasma exchange was\ntherefore performed 14 months after symptom onset with removal\nof 3 l of plasma at ﬁve subsequent days."", ""char_start"": 2736, ""char_end"": 2859, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The patient did not respond\nto plasma exchange."", ""char_start"": 3121, ""char_end"": 3168, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Two g/kg intravenous immunoglobulin was given after another\nmonth"", ""char_start"": 3277, ""char_end"": 3342, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days. | The patient did not respond to plasma exchange. | Two g/kg intravenous immunoglobulin was given after another month,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,none,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""there was no persistent response to these drugs\nor to baclofene, phenytoin and intravenous immunoglobulins."", ""char_start"": 2519, ""char_end"": 2626, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The patient did not respond\nto plasma exchange."", ""char_start"": 3121, ""char_end"": 3168, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Two g/kg intravenous immunoglobulin was given after another\nmonth, but did not affect the increasing rigidity and painful muscle\nspasms."", ""char_start"": 3277, ""char_end"": 3413, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins. | The patient did not respond to plasma exchange. | Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms.",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment,benzo;clonazepam;baclofen;phenytoin,benzo;clonazepam;baclofen;phenytoin,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Intravenuos diazepam and clonazepam induced transient\nimprovement"", ""char_start"": 2448, ""char_end"": 2513, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""no persistent response to these drugs\nor to baclofene, phenytoin"", ""char_start"": 2529, ""char_end"": 2593, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Intravenuos diazepam and clonazepam induced transient improvement | no persistent response to these drugs or to baclofene, phenytoin",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_detail,"iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement","iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Intravenuos diazepam and clonazepam induced transient\nimprovement"", ""char_start"": 2448, ""char_end"": 2513, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""there was no persistent response to these drugs\nor to baclofene, phenytoin"", ""char_start"": 2519, ""char_end"": 2593, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Intravenuos diazepam and clonazepam induced transient improvement | there was no persistent response to these drugs or to baclofene, phenytoin",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_effect,minimal improvement,minimal improvement,inferred_from_text,inference_snippet_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Intravenuos diazepam and clonazepam induced transient\nimprovement"", ""char_start"": 2448, ""char_end"": 2513, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""there was no persistent response to these drugs\nor to baclofene, phenytoin"", ""char_start"": 2519, ""char_end"": 2593, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Intravenuos diazepam and clonazepam induced transient improvement | there was no persistent response to these drugs or to baclofene, phenytoin",qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
537,,age_description,29,29,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""A 29-year-old previously healthy African-\nAmerican male patient"", ""char_start"": 821, ""char_end"": 884, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A 29-year-old previously healthy African- American male patient,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sex,M,M,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""African-\nAmerican male patient"", ""char_start"": 854, ""char_end"": 884, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",African- American male patient,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,ethnicity,africa,africa,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""African-\nAmerican male patient"", ""char_start"": 854, ""char_end"": 884, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",African- American male patient,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,age_onset,29,29,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""A 29-year-old previously healthy African-\nAmerican male patient complained of\nfour-week history"", ""char_start"": 821, ""char_end"": 916, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A 29-year-old previously healthy African- American male patient complained of four-week history,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation,other,other,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""complained of\nfour-week history of progressive shortness\nof breath, non-productive cough and left-\nsided chest pain"", ""char_start"": 885, ""char_end"": 1000, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","complained of four-week history of progressive shortness of breath, non-productive cough and left- sided chest pain",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation_multiple,dyspnoea,dyspnoea,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""progressive shortness\nof breath"", ""char_start"": 920, ""char_end"": 951, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",progressive shortness of breath,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,paraneoplastic_SPS,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,3,TRUE,"[{""span_text"": ""His\nclinical picture was suggestive of SPS sec-\nondary to invasive thymoma."", ""char_start"": 418, ""char_end"": 493, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""the\ndiagnosis of SPS was made"", ""char_start"": 3435, ""char_end"": 3464, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""pathology specimen being\nconsistent with lymphocytic pre-\ndominant epithelial type thymoma"", ""char_start"": 1990, ""char_end"": 2080, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",His clinical picture was suggestive of SPS sec- ondary to invasive thymoma. | the diagnosis of SPS was made | pathology specimen being consistent with lymphocytic pre- dominant epithelial type thymoma,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_onset,dyspnoea,dyspnoea,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""progressive shortness\nof breath"", ""char_start"": 920, ""char_end"": 951, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",progressive shortness of breath,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,timecourse_subsequent,monophasic,monophasic,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""at five-month follow up he did-\nn’t have any recurrence of his symp-\ntoms"", ""char_start"": 3511, ""char_end"": 3584, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",at five-month follow up he did- n’t have any recurrence of his symp- toms,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,overview_established,stiffness;spasms,stiffness;spasms,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""muscle spasms, rigidity"", ""char_start"": 149, ""char_end"": 172, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","muscle spasms, rigidity",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established,multiple,multiple,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""truncal, lower ex-\ntremities stiffness"", ""char_start"": 322, ""char_end"": 360, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain"", ""char_start"": 2762, ""char_end"": 2853, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","truncal, lower ex- tremities stiffness | diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established_multiple,distal_LE;lumb_prox_LE;axial,distal_LE;lumb_prox_LE;axial,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""truncal, lower ex-\ntremities stiffness"", ""char_start"": 322, ""char_end"": 360, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""diffuse mus-\ncular stiffness in both lower extrem-\nities along with diffuse lower back\npain"", ""char_start"": 2762, ""char_end"": 2853, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","truncal, lower ex- tremities stiffness | diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established,multiple,multiple,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""truncal, lower ex-\ntremities stiffness and painful cramps"", ""char_start"": 322, ""char_end"": 379, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs"", ""char_start"": 2453, ""char_end"": 2533, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","truncal, lower ex- tremities stiffness and painful cramps | severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,distal_LE;lumb_prox_LE,inferred_from_text,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,2,TRUE,"[{""span_text"": ""severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs"", ""char_start"": 2453, ""char_end"": 2533, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}, {""span_text"": ""truncal, lower ex-\ntremities stiffness and painful cramps"", ""char_start"": 322, ""char_end"": 379, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs | truncal, lower ex- tremities stiffness and painful cramps",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_established,pain;weakness,pain;weakness,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""severe bi-\nlateral lower extremity pain, muscle\ncramps and weakness in both legs"", ""char_start"": 2453, ""char_end"": 2533, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,antibody_status,GAD,GAD,not_found,needs_review,needs_human_adjudication,review_before_promoting,0,FALSE,[],,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,antibody_tests,GAD;AChR,GAD;AChR,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""anti-GAD antibodies; the result was\nnegative. Myasthenia gravis was\nruled out by a normal pulmonary\nfunction test and a negative anti-\nAChR antibodies test"", ""char_start"": 3160, ""char_end"": 3315, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exac

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan_long.csv
paper_id,case_id,field_name,spreadsheet_value,span_index,span_role,char_start,char_end,span_text,span_text_display,selection_source,match_mode,coverage_quality,langextract_recommendation,target_view_json_path
524,,age_description,67,1,model_candidate,37,53,67-year-old male,67-year-old male,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sex,M,1,model_candidate,37,53,67-year-old male,67-year-old male,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,ethnicity,white,1,absence_context,16,63,A previously healthy 67-year-old male presented,A previously healthy 67-year-old male presented,manual_audit_override_1,exact,context_or_absence_only_not_direct_extraction,do_not_promote_as_standard_langextract_example,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,age_onset,67,1,model_candidate,16,139,"A previously healthy 67-year-old male presented with rapidly
evolving and painful ﬂexor cramps of the toes on his left foot",A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,age_onset,67,2,model_candidate,3414,3467,He died from pneumonia 18 months after symptom onset.,He died from pneumonia 18 months after symptom onset.,model_supporting_snippet_2,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,FU_duration,18,1,model_candidate,3414,3467,He died from pneumonia 18 months after symptom onset.,He died from pneumonia 18 months after symptom onset.,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation,multiple,1,model_candidate,54,204,"presented with rapidly
evolving and painful ﬂexor cramps of the toes on his left foot, fol-
lowed by fasciculations and muscle atrophy in the left leg","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation,multiple,2,model_candidate,206,301,"The
condition progressed rapidly with marked muscular rigidity and
painful superimposed spasms.",The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation_multiple,cramps;fasciculation;atrophy;stiffness;spasms,1,model_candidate,54,204,"presented with rapidly
evolving and painful ﬂexor cramps of the toes on his left foot, fol-
lowed by fasciculations and muscle atrophy in the left leg","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation_multiple,cramps;fasciculation;atrophy;stiffness;spasms,2,model_candidate,206,301,"The
condition progressed rapidly with marked muscular rigidity and
painful superimposed spasms.",The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,included_diagnosis,SPS with lower motor neuron disease,1,model_candidate,682,784,"corresponding to a stiffness score of ﬁve out of six possible points at
the SPS stiffness extent scale",corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,included_diagnosis,SPS with lower motor neuron disease,2,model_candidate,1193,1355,"Electromyography of the left leg 10, 13, 14 and 16 months after
symptom onset showed continuous motor activity and signs of
denervation with positive sharp waves.","Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,early_symptoms,stiffness;spasms,1,model_candidate,244,300,"marked muscular rigidity and
painful superimposed spasms",marked muscular rigidity and painful superimposed spasms,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset,multiple,1,model_candidate,244,400,"marked muscular rigidity and
painful superimposed spasms. This was most prominent in the left
leg, but subsequently also involved the right limb and truncus","marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;axial,1,model_candidate,302,400,"This was most prominent in the left
leg, but subsequently also involved the right limb and truncus","This was most prominent in the left leg, but subsequently also involved the right limb and truncus",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;axial,2,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_supporting_snippet_2,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_onset,fasciculation;muscle_atrophy,1,model_candidate,141,204,"fol-
lowed by fasciculations and muscle atrophy in the left leg",fol- lowed by fasciculations and muscle atrophy in the left leg,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,1,model_candidate,206,238,"The
condition progressed rapidly",The condition progressed rapidly,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,2,model_candidate,2627,2680,"The
patient deteriorated rapidly and became bedridden",The patient deteriorated rapidly and became bedridden,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,3,model_candidate,3414,3467,He died from pneumonia 18 months after symptom onset.,He died from pneumonia 18 months after symptom onset.,model_supporting_snippet_3,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,onset_to_established,7,1,model_candidate,449,502,"Neurological examination
7 months after symptom debut",Neurological examination 7 months after symptom debut,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,overview_established,stiffness;spasms,1,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,overview_established,stiffness;spasms,2,model_candidate,891,922,triggered painful muscle cramps,triggered painful muscle cramps,model_supporting_snippet_1,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established,multiple,1,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial,1,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_other,5/6 points in SPS stiffness extent scale,1,model_candidate,699,784,"a stiffness score of ﬁve out of six possible points at
the SPS stiffness extent scale",a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,spasms_distribution_established,unspecified,1,model_candidate,801,922,"auditory, somatosen-
sory, emotional and visual stimuli and attempts to move the left leg
triggered painful muscle cramps","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,spasms_distribution_established,unspecified,2,model_candidate,2664,2734,"became bedridden with almost
continuous painful spasms in the left leg",became bedridden with almost continuous painful spasms in the left leg,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established,multiple,1,model_candidate,801,922,"auditory, somatosen-
sory, emotional and visual stimuli and attempts to move the left leg
triggered painful muscle cramps","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established_multipleother,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,1,model_candidate,801,1014,"auditory, somatosen-
sory, emotional and visual stimuli and attempts to move the left leg
triggered painful muscle cramps, corresponding to six out of seven

possible points at the SPS heightened sensitivity scale","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale",model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_established,hyporeflexia,1,model_candidate,1020,1116,"The ten-
don reﬂexes were absent in the left leg, weak in the right leg, and
normal in both arms","The ten- don reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_status,GAD65,1,model_candidate,1986,2059,"Anti-GAD65 antibodies were markedly and persis-
tently increased in serum",Anti-GAD65 antibodies were markedly and persis- tently increased in serum,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_titre,1.57,1,model_candidate,2061,2115,"0.96–1.57 units at month 10 and 14 after
symptom onset",0.96–1.57 units at month 10 and 14 after symptom onset,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_units,"""units""",1,model_candidate,2061,2076,0.96–1.57 units,0.96–1.57 units,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_tests,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,1,model_candidate,1520,1669,"antibodies against gangliosides, voltage gated potassium
channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin
peroxidase were all normal","antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_status,antibody_present;OCB,1,model_candidate,2149,2220,"were also detected
in CSF (0.84 units at month 10 after symptom onset).",were also detected in CSF (0.84 units at month 10 after symptom onset).,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_status,antibody_present;OCB,2,model_candidate,2302,2394,"isoelectric focusing-immunoblot displayed several GAD65 speciﬁc
oligoclonal IgG bands in CSF",isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_antibody,GAD65,1,model_candidate,1986,2059,"Anti-GAD65 antibodies were markedly and persis-
tently increased in serum",Anti-GAD65 antibodies were markedly and persis- tently increased in serum,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_antibody,GAD65,2,model_candidate,2149,2174,"were also detected
in CSF",were also detected in CSF,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CMUA,1,1,model_candidate,1193,1303,"Electromyography of the left leg 10, 13, 14 and 16 months after
symptom onset showed continuous motor activity","Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,MRI_normal,0,1,support,1447,1498,extensive radiological examinations of the neuraxis,extensive radiological examinations of the neuraxis,manual_audit_override_1,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,MRI_normal,0,2,support,1654,1669,were all normal,were all normal,manual_audit_override_2,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,tu_screening,0,1,support,1500,1518,"malignancy
workout",malignancy workout,manual_audit_override_1,manual_override_folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,tu_screening,0,2,support,1654,1669,were all normal,were all normal,manual_audit_override_2,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,tu_screening,0,3,support,3468,3515,No signs of malignancy were detected at autopsy,No signs of malignancy were detected at autopsy,manual_audit_override_3,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy,IVIG;PLEX,1,model_candidate,2598,2625,intravenous immunoglobulins,intravenous immunoglobulins,model_supporting_snippet_1,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy,IVIG;PLEX,2,model_candidate,2736,2805,"Plasma exchange was
therefore performed 14 months after symptom onset",Plasma exchange was therefore performed 14 months after symptom onset,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,1,model_candidate,2736,2859,"Plasma exchange was
therefore performed 14 months after symptom onset with removal
of 3 l of plasma at ﬁve subsequent days.",Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days.,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,2,model_candidate,3121,3168,"The patient did not respond
to plasma exchange.",The patient did not respond to plasma exchange.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,3,model_candidate,3277,3342,"Two g/kg intravenous immunoglobulin was given after another
month",Two g/kg intravenous immunoglobulin was given after another month,model_supporting_snippet_3,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,1,model_candidate,2519,2626,"there was no persistent response to these drugs
or to baclofene, phenytoin and intravenous immunoglobulins.","there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins.",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,2,model_candidate,3121,3168,"The patient did not respond
to plasma exchange.",The patient did not respond to plasma exchange.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,3,model_candidate,3277,3413,"Two g/kg intravenous immunoglobulin was given after another
month, but did not affect the increasing rigidity and painful muscle
spasms.","Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms.",model_supporting_snippet_3,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment,benzo;clonazepam;baclofen;phenytoin,1,model_candidate,2448,2513,"Intravenuos diazepam and clonazepam induced transient
improvement",Intravenuos diazepam and clonazepam induced transient improvement,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment,benzo;clonazepam;baclofen;phenytoin,2,model_candidate,2529,2593,"no persistent response to these drugs
or to baclofene, phenytoin","no persistent response to these drugs or to baclofene, phenytoin",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_detail,"iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",1,model_candidate,2448,2513,"Intravenuos diazepam and clonazepam induced transient
improvement",Intravenuos diazepam and clonazepam induced transient improvement,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_detail,"iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",2,model_candidate,2519,2593,"there was no persistent response to these drugs
or to baclofene, phenytoin","there was no persistent response to these drugs or to baclofene, phenytoin",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_effect,minimal improvement,1,model_candidate,2448,2513,"Intravenuos diazepam and clonazepam induced transient
improvement",Intravenuos diazepam and clonazepam induced transient improvement,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_effect,minimal improvement,2,model_candidate,2519,2593,"there was no persistent response to these drugs
or to baclofene, phenytoin","there was no persistent response to these drugs or to baclofene, phenytoin",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
537,,age_description,29,1,model_candidate,821,884,"A 29-year-old previously healthy African-
American male patient",A 29-year-old previously healthy African- American male patient,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sex,M,1,model_candidate,854,884,"African-
American male patient",African- American male patient,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,ethnicity,africa,1,model_candidate,854,884,"African-
American male patient",African- American male patient,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,age_onset,29,1,model_candidate,821,916,"A 29-year-old previously healthy African-
American male patient complained of
four-week history",A 29-year-old previously healthy African- American male patient complained of four-week history,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation,other,1,model_candidate,885,1000,"complained of
four-week history of progressive shortness
of breath, non-productive cough and left-
sided chest pain","complained of four-week history of progressive shortness of breath, non-productive cough and left- sided chest pain",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation_multiple,dyspnoea,1,model_candidate,920,951,"progressive shortness
of breath",progressive shortness of breath,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,1,model_candidate,418,493,"His
clinical picture was suggestive of SPS sec-
ondary to invasive thymoma.",His clinical picture was suggestive of SPS sec- ondary to invasive thymoma.,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,2,model_candidate,3435,3464,"the
diagnosis of SPS was made",the diagnosis of SPS was made,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,3,model_candidate,1990,2080,"pathology specimen being
consistent with lymphocytic pre-
dominant epithelial type thymoma",pathology specimen being consistent with lymphocytic pre- dominant epithelial type thymoma,model_supporting_snippet_3,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_onset,dyspnoea,1,model_candidate,920,951,"progressive shortness
of breath",progressive shortness of breath,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,timecourse_subsequent,monophasic,1,model_candidate,3511,3584,"at five-month follow up he did-
n’t have any recurrence of his symp-
toms",at five-month follow up he did- n’t have any recurrence of his symp- toms,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,overview_established,stiffness;spasms,1,model_candidate,149,172,"muscle spasms, rigidity","muscle spasms, rigidity",model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established,multiple,1,model_candidate,322,360,"truncal, lower ex-
tremities stiffness","truncal, lower ex- tremities stiffness",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established,multiple,2,model_candidate,2762,2853,"diffuse mus-
cular stiffness in both lower extrem-
ities along with diffuse lower back
pain",diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established_multiple,distal_LE;lumb_prox_LE;axial,1,model_candidate,322,360,"truncal, lower ex-
tremities stiffness","truncal, lower ex- tremities stiffness",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established_multiple,distal_LE;lumb_prox_LE;axial,2,model_candidate,2762,2853,"diffuse mus-
cular stiffness in both lower extrem-
ities along with diffuse lower back
pain",diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established,multiple,1,model_candidate,322,379,"truncal, lower ex-
tremities stiffness and painful cramps","truncal, lower ex- tremities stiffness and painful cramps",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established,multiple,2,model_candidate,2453,2533,"severe bi-
lateral lower extremity pain, muscle
cramps and weakness in both legs","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,1,model_candidate,2453,2533,"severe bi-
lateral lower extremity pain, muscle
cramps and weakness in both legs","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,2,model_candidate,322,379,"truncal, lower ex-
tremities stiffness and painful cramps","truncal, lower ex- tremities stiffness and painful cramps",model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_established,pain;weakness,1,model_candidate,2453,2533,"severe bi-
lateral lower extremity pain, muscle
cramps and weakness in both legs","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,antibody_status,GAD,1,conflict_context,3124,3204,"paraneoplastic panel which included
anti-GAD antibodies; the result was
negative",paraneoplastic panel which included anti-GAD antibodies; the result was negative,manual_audit_override_1,manual_override_folded_alnum_to_exact_source,gold_source_conflict_or_partial_support,do_not_promote_as_standard_langextract_example,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,antibody_tests,GAD;AChR,1,model_candidate,3160,3315,"anti-GAD antibodies; the result was
negative. Myasthenia gravis was
ruled out by a normal pulmonary
function test and a negative anti-
AChR antibodies test",anti-GAD antibodies; the result was negative. Myasthenia gravis was ruled out by a normal pulmonary function test and a negative anti- AChR antibodies test,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening,1,1,model_candidate,1131,1254,"Computed tomog-
raphy of the chest demonstrated a large
left-sided pleural effusion and a large an-
terior mediastinal mass",Computed tomog- raphy of the chest demonstrated a large left-sided pleural effusion and a large an- terior mediastinal mass,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening,1,2,model_candidate,1758,1799,"PET scan
showed anterior mediastinal mass",PET scan showed anterior mediastinal mass,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening_abnormal,thymoma invasive lymphocytic predominant epithelial type,1,model_candidate,1990,2080,"pathology specimen being
consistent with lymphocytic pre-
dominant epithelial type thymoma",pathology specimen being consistent with lymphocytic pre- dominant epithelial type thymoma,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening_abnormal,thymoma invasive lymphocytic predominant epithelial type,2,model_candidate,2082,2127,"Due to the invasive behavior of this
neoplasm",Due to the invasive behavior of this neoplasm,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment,benzo;morphine,1,model_candidate,2926,2985,"diazepam 5 mg intravenously
along with intravenous morphine",diazepam 5 mg intravenously along with intravenous morphine,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment_detail,diazepam 5mg iv and morphine with complete resolution of neurological symptoms,1,model_candidate,2908,3027,"Patient was
given diazepam 5 mg intravenously
along with intravenous morphine
with complete resolution of his
symptoms.",Patient was given diazepam 5 mg intravenously along with intravenous morphine with complete resolution of his symptoms.,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment_effect,improvement,1,model_candidate,2991,3026,"complete resolution of his
symptoms",complete resolution of his symptoms,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_treatment,resection and chemotherapy of thymoma with complete resolution of neurological symptoms,1,conflict_context,2129,2173,"an initial surgical treat-
ment was deferred",an initial surgical treat- ment was deferred,manual_audit_override_1,manual_override_folded_alnum_to_exact_source,gold_source_conflict_or_partial_support,do_not_promote_as_standard_langextract_example,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_treatment,resection and chemotherapy of thymoma with complete resolution of neurological symptoms,2,conflict_context,2223,2253,four-drug-regimen chemotherapy,four-drug-regimen chemotherapy,manual_audit_override_2,exact,gold_source_conflict_or_partial_support,do_not_promote_as_standard_langextract_example,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_treatment,resection and chemotherapy of thymoma with complete resolution of neurological symptoms,3,conflict_context,3590,3638,"complete radiographic

resolution of his thymoma",complete radiographic resolution of his thymoma,manual_audit_override_3,manual_override_folded_alnum_to_exact_source,gold_source_conflict_or_partial_support,do_not_promote_as_standard_langextract_example,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
551,,age_description,51,1,model_candidate,12,35,A 51-year-old white man,A 51-year-old white man,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,sex,M,1,model_candidate,26,35,white man,white man,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,ethnicity,white,1,model_candidate,26,35,white man,white man,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,age_onset,51,1,model_candidate,12,35,A 51-year-old white man,A 51-year-old white man,model_supporting_snippet_1,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,age_onset,51,2,model_candidate,1159,1229,"Histor

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan_long_draft.csv
paper_id,case_id,field_name,spreadsheet_value,span_index,span_role,char_start,char_end,span_text,span_text_display,selection_source,match_mode,coverage_quality,langextract_recommendation,target_view_json_path
524,,age_description,67,1,model_candidate,37,53,67-year-old male,67-year-old male,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sex,M,1,model_candidate,37,53,67-year-old male,67-year-old male,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,age_onset,67,1,model_candidate,16,139,"A previously healthy 67-year-old male presented with rapidly
evolving and painful ﬂexor cramps of the toes on his left foot",A previously healthy 67-year-old male presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,age_onset,67,2,model_candidate,3414,3467,He died from pneumonia 18 months after symptom onset.,He died from pneumonia 18 months after symptom onset.,model_supporting_snippet_2,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,FU_duration,18,1,model_candidate,3414,3467,He died from pneumonia 18 months after symptom onset.,He died from pneumonia 18 months after symptom onset.,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation,multiple,1,model_candidate,54,204,"presented with rapidly
evolving and painful ﬂexor cramps of the toes on his left foot, fol-
lowed by fasciculations and muscle atrophy in the left leg","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation,multiple,2,model_candidate,206,301,"The
condition progressed rapidly with marked muscular rigidity and
painful superimposed spasms.",The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation_multiple,cramps;fasciculation;atrophy;stiffness;spasms,1,model_candidate,54,204,"presented with rapidly
evolving and painful ﬂexor cramps of the toes on his left foot, fol-
lowed by fasciculations and muscle atrophy in the left leg","presented with rapidly evolving and painful ﬂexor cramps of the toes on his left foot, fol- lowed by fasciculations and muscle atrophy in the left leg",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,first_manifestation_multiple,cramps;fasciculation;atrophy;stiffness;spasms,2,model_candidate,206,301,"The
condition progressed rapidly with marked muscular rigidity and
painful superimposed spasms.",The condition progressed rapidly with marked muscular rigidity and painful superimposed spasms.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,included_diagnosis,SPS with lower motor neuron disease,1,model_candidate,682,784,"corresponding to a stiffness score of ﬁve out of six possible points at
the SPS stiffness extent scale",corresponding to a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,included_diagnosis,SPS with lower motor neuron disease,2,model_candidate,1193,1355,"Electromyography of the left leg 10, 13, 14 and 16 months after
symptom onset showed continuous motor activity and signs of
denervation with positive sharp waves.","Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity and signs of denervation with positive sharp waves.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,early_symptoms,stiffness;spasms,1,model_candidate,244,300,"marked muscular rigidity and
painful superimposed spasms",marked muscular rigidity and painful superimposed spasms,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset,multiple,1,model_candidate,244,400,"marked muscular rigidity and
painful superimposed spasms. This was most prominent in the left
leg, but subsequently also involved the right limb and truncus","marked muscular rigidity and painful superimposed spasms. This was most prominent in the left leg, but subsequently also involved the right limb and truncus",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;axial,1,model_candidate,302,400,"This was most prominent in the left
leg, but subsequently also involved the right limb and truncus","This was most prominent in the left leg, but subsequently also involved the right limb and truncus",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;axial,2,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_supporting_snippet_2,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_onset,fasciculation;muscle_atrophy,1,model_candidate,141,204,"fol-
lowed by fasciculations and muscle atrophy in the left leg",fol- lowed by fasciculations and muscle atrophy in the left leg,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,1,model_candidate,206,238,"The
condition progressed rapidly",The condition progressed rapidly,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,2,model_candidate,2627,2680,"The
patient deteriorated rapidly and became bedridden",The patient deteriorated rapidly and became bedridden,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,timecourse_subsequent,monophasic,3,model_candidate,3414,3467,He died from pneumonia 18 months after symptom onset.,He died from pneumonia 18 months after symptom onset.,model_supporting_snippet_3,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,onset_to_established,7,1,model_candidate,449,502,"Neurological examination
7 months after symptom debut",Neurological examination 7 months after symptom debut,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,overview_established,stiffness;spasms,1,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,overview_established,stiffness;spasms,2,model_candidate,891,922,triggered painful muscle cramps,triggered painful muscle cramps,model_supporting_snippet_1,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established,multiple,1,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial,1,model_candidate,582,680,"Muscle stiffness was promi-
nent in the left leg but was also found in the right leg and the trunk",Muscle stiffness was promi- nent in the left leg but was also found in the right leg and the trunk,model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,stiffness_distribution_established_other,5/6 points in SPS stiffness extent scale,1,model_candidate,699,784,"a stiffness score of ﬁve out of six possible points at
the SPS stiffness extent scale",a stiffness score of ﬁve out of six possible points at the SPS stiffness extent scale,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,spasms_distribution_established,unspecified,1,model_candidate,801,922,"auditory, somatosen-
sory, emotional and visual stimuli and attempts to move the left leg
triggered painful muscle cramps","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,spasms_distribution_established,unspecified,2,model_candidate,2664,2734,"became bedridden with almost
continuous painful spasms in the left leg",became bedridden with almost continuous painful spasms in the left leg,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established,multiple,1,model_candidate,801,922,"auditory, somatosen-
sory, emotional and visual stimuli and attempts to move the left leg
triggered painful muscle cramps","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,excessive_startle_established_multipleother,auditory;somatosensory;emotional;visual;movement;6/7 points on SPS heightened sensitivity scale,1,model_candidate,801,1014,"auditory, somatosen-
sory, emotional and visual stimuli and attempts to move the left leg
triggered painful muscle cramps, corresponding to six out of seven

possible points at the SPS heightened sensitivity scale","auditory, somatosen- sory, emotional and visual stimuli and attempts to move the left leg triggered painful muscle cramps, corresponding to six out of seven possible points at the SPS heightened sensitivity scale",model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,other_symptoms_established,hyporeflexia,1,model_candidate,1020,1116,"The ten-
don reﬂexes were absent in the left leg, weak in the right leg, and
normal in both arms","The ten- don reﬂexes were absent in the left leg, weak in the right leg, and normal in both arms",model_supporting_snippet_1,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_status,GAD65,1,model_candidate,1986,2059,"Anti-GAD65 antibodies were markedly and persis-
tently increased in serum",Anti-GAD65 antibodies were markedly and persis- tently increased in serum,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_titre,1.57,1,model_candidate,2061,2115,"0.96–1.57 units at month 10 and 14 after
symptom onset",0.96–1.57 units at month 10 and 14 after symptom onset,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_units,"""units""",1,model_candidate,2061,2076,0.96–1.57 units,0.96–1.57 units,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,antibody_tests,gangliosides;VGKC;islet_cells;gephyrin;amphiphysin;dsDNA;TPO,1,model_candidate,1520,1669,"antibodies against gangliosides, voltage gated potassium
channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin
peroxidase were all normal","antibodies against gangliosides, voltage gated potassium channels, pancreas islets, gephyrin, ampiphysin, DNA and thyroxin peroxidase were all normal",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_status,antibody_present;OCB,1,model_candidate,2149,2220,"were also detected
in CSF (0.84 units at month 10 after symptom onset).",were also detected in CSF (0.84 units at month 10 after symptom onset).,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_status,antibody_present;OCB,2,model_candidate,2302,2394,"isoelectric focusing-immunoblot displayed several GAD65 speciﬁc
oligoclonal IgG bands in CSF",isoelectric focusing-immunoblot displayed several GAD65 speciﬁc oligoclonal IgG bands in CSF,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_antibody,GAD65,1,model_candidate,1986,2059,"Anti-GAD65 antibodies were markedly and persis-
tently increased in serum",Anti-GAD65 antibodies were markedly and persis- tently increased in serum,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CSF_antibody,GAD65,2,model_candidate,2149,2174,"were also detected
in CSF",were also detected in CSF,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,CMUA,1,1,model_candidate,1193,1303,"Electromyography of the left leg 10, 13, 14 and 16 months after
symptom onset showed continuous motor activity","Electromyography of the left leg 10, 13, 14 and 16 months after symptom onset showed continuous motor activity",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy,IVIG;PLEX,1,model_candidate,2598,2625,intravenous immunoglobulins,intravenous immunoglobulins,model_supporting_snippet_1,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy,IVIG;PLEX,2,model_candidate,2736,2805,"Plasma exchange was
therefore performed 14 months after symptom onset",Plasma exchange was therefore performed 14 months after symptom onset,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,1,model_candidate,2736,2859,"Plasma exchange was
therefore performed 14 months after symptom onset with removal
of 3 l of plasma at ﬁve subsequent days.",Plasma exchange was therefore performed 14 months after symptom onset with removal of 3 l of plasma at ﬁve subsequent days.,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,2,model_candidate,3121,3168,"The patient did not respond
to plasma exchange.",The patient did not respond to plasma exchange.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immuntherapy_detail,5x PLEX: no response. IVIG: 2g/kg,3,model_candidate,3277,3342,"Two g/kg intravenous immunoglobulin was given after another
month",Two g/kg intravenous immunoglobulin was given after another month,model_supporting_snippet_3,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,1,model_candidate,2519,2626,"there was no persistent response to these drugs
or to baclofene, phenytoin and intravenous immunoglobulins.","there was no persistent response to these drugs or to baclofene, phenytoin and intravenous immunoglobulins.",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,2,model_candidate,3121,3168,"The patient did not respond
to plasma exchange.",The patient did not respond to plasma exchange.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,immunotherapy_effect,none,3,model_candidate,3277,3413,"Two g/kg intravenous immunoglobulin was given after another
month, but did not affect the increasing rigidity and painful muscle
spasms.","Two g/kg intravenous immunoglobulin was given after another month, but did not affect the increasing rigidity and painful muscle spasms.",model_supporting_snippet_3,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment,benzo;clonazepam;baclofen;phenytoin,1,model_candidate,2448,2513,"Intravenuos diazepam and clonazepam induced transient
improvement",Intravenuos diazepam and clonazepam induced transient improvement,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment,benzo;clonazepam;baclofen;phenytoin,2,model_candidate,2529,2593,"no persistent response to these drugs
or to baclofene, phenytoin","no persistent response to these drugs or to baclofene, phenytoin",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_detail,"iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",1,model_candidate,2448,2513,"Intravenuos diazepam and clonazepam induced transient
improvement",Intravenuos diazepam and clonazepam induced transient improvement,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_detail,"iv diazepam and clonazepam with transient improvement. Baclofen, phenytoin: no improvement",2,model_candidate,2519,2593,"there was no persistent response to these drugs
or to baclofene, phenytoin","there was no persistent response to these drugs or to baclofene, phenytoin",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_effect,minimal improvement,1,model_candidate,2448,2513,"Intravenuos diazepam and clonazepam induced transient
improvement",Intravenuos diazepam and clonazepam induced transient improvement,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
524,,sympt_treatment_effect,minimal improvement,2,model_candidate,2519,2593,"there was no persistent response to these drugs
or to baclofene, phenytoin","there was no persistent response to these drugs or to baclofene, phenytoin",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json
537,,age_description,29,1,model_candidate,821,884,"A 29-year-old previously healthy African-
American male patient",A 29-year-old previously healthy African- American male patient,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sex,M,1,model_candidate,854,884,"African-
American male patient",African- American male patient,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,ethnicity,africa,1,model_candidate,854,884,"African-
American male patient",African- American male patient,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,age_onset,29,1,model_candidate,821,916,"A 29-year-old previously healthy African-
American male patient complained of
four-week history",A 29-year-old previously healthy African- American male patient complained of four-week history,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation,other,1,model_candidate,885,1000,"complained of
four-week history of progressive shortness
of breath, non-productive cough and left-
sided chest pain","complained of four-week history of progressive shortness of breath, non-productive cough and left- sided chest pain",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,first_manifestation_multiple,dyspnoea,1,model_candidate,920,951,"progressive shortness
of breath",progressive shortness of breath,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,1,model_candidate,418,493,"His
clinical picture was suggestive of SPS sec-
ondary to invasive thymoma.",His clinical picture was suggestive of SPS sec- ondary to invasive thymoma.,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,2,model_candidate,3435,3464,"the
diagnosis of SPS was made",the diagnosis of SPS was made,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,included_diagnosis,paraneoplastic_SPS,3,model_candidate,1990,2080,"pathology specimen being
consistent with lymphocytic pre-
dominant epithelial type thymoma",pathology specimen being consistent with lymphocytic pre- dominant epithelial type thymoma,model_supporting_snippet_3,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_onset,dyspnoea,1,model_candidate,920,951,"progressive shortness
of breath",progressive shortness of breath,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,timecourse_subsequent,monophasic,1,model_candidate,3511,3584,"at five-month follow up he did-
n’t have any recurrence of his symp-
toms",at five-month follow up he did- n’t have any recurrence of his symp- toms,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,overview_established,stiffness;spasms,1,model_candidate,149,172,"muscle spasms, rigidity","muscle spasms, rigidity",model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established,multiple,1,model_candidate,322,360,"truncal, lower ex-
tremities stiffness","truncal, lower ex- tremities stiffness",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established,multiple,2,model_candidate,2762,2853,"diffuse mus-
cular stiffness in both lower extrem-
ities along with diffuse lower back
pain",diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established_multiple,distal_LE;lumb_prox_LE;axial,1,model_candidate,322,360,"truncal, lower ex-
tremities stiffness","truncal, lower ex- tremities stiffness",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,stiffness_distribution_established_multiple,distal_LE;lumb_prox_LE;axial,2,model_candidate,2762,2853,"diffuse mus-
cular stiffness in both lower extrem-
ities along with diffuse lower back
pain",diffuse mus- cular stiffness in both lower extrem- ities along with diffuse lower back pain,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established,multiple,1,model_candidate,322,379,"truncal, lower ex-
tremities stiffness and painful cramps","truncal, lower ex- tremities stiffness and painful cramps",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established,multiple,2,model_candidate,2453,2533,"severe bi-
lateral lower extremity pain, muscle
cramps and weakness in both legs","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,1,model_candidate,2453,2533,"severe bi-
lateral lower extremity pain, muscle
cramps and weakness in both legs","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,spasms_distribution_established_multiple,distal_LE;lumb_prox_LE,2,model_candidate,322,379,"truncal, lower ex-
tremities stiffness and painful cramps","truncal, lower ex- tremities stiffness and painful cramps",model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,other_symptoms_established,pain;weakness,1,model_candidate,2453,2533,"severe bi-
lateral lower extremity pain, muscle
cramps and weakness in both legs","severe bi- lateral lower extremity pain, muscle cramps and weakness in both legs",model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,antibody_tests,GAD;AChR,1,model_candidate,3160,3315,"anti-GAD antibodies; the result was
negative. Myasthenia gravis was
ruled out by a normal pulmonary
function test and a negative anti-
AChR antibodies test",anti-GAD antibodies; the result was negative. Myasthenia gravis was ruled out by a normal pulmonary function test and a negative anti- AChR antibodies test,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening,1,1,model_candidate,1131,1254,"Computed tomog-
raphy of the chest demonstrated a large
left-sided pleural effusion and a large an-
terior mediastinal mass",Computed tomog- raphy of the chest demonstrated a large left-sided pleural effusion and a large an- terior mediastinal mass,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening,1,2,model_candidate,1758,1799,"PET scan
showed anterior mediastinal mass",PET scan showed anterior mediastinal mass,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening_abnormal,thymoma invasive lymphocytic predominant epithelial type,1,model_candidate,1990,2080,"pathology specimen being
consistent with lymphocytic pre-
dominant epithelial type thymoma",pathology specimen being consistent with lymphocytic pre- dominant epithelial type thymoma,model_supporting_snippet_1,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,tu_screening_abnormal,thymoma invasive lymphocytic predominant epithelial type,2,model_candidate,2082,2127,"Due to the invasive behavior of this
neoplasm",Due to the invasive behavior of this neoplasm,model_supporting_snippet_2,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment,benzo;morphine,1,model_candidate,2926,2985,"diazepam 5 mg intravenously
along with intravenous morphine",diazepam 5 mg intravenously along with intravenous morphine,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment_detail,diazepam 5mg iv and morphine with complete resolution of neurological symptoms,1,model_candidate,2908,3027,"Patient was
given diazepam 5 mg intravenously
along with intravenous morphine
with complete resolution of his
symptoms.",Patient was given diazepam 5 mg intravenously along with intravenous morphine with complete resolution of his symptoms.,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
537,,sympt_treatment_effect,improvement,1,model_candidate,2991,3026,"complete resolution of his
symptoms",complete resolution of his symptoms,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json
551,,age_description,51,1,model_candidate,12,35,A 51-year-old white man,A 51-year-old white man,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,sex,M,1,model_candidate,26,35,white man,white man,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,ethnicity,white,1,model_candidate,26,35,white man,white man,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,age_onset,51,1,model_candidate,12,35,A 51-year-old white man,A 51-year-old white man,model_supporting_snippet_1,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,age_onset,51,2,model_candidate,1159,1229,"History revealed an
onset of leg pain and falls over the
last 6 months",History revealed an onset of leg pain and falls over the last 6 months,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,time_to_diagnosis,0.5,1,model_candidate,1159,1229,"History revealed an
onset of leg pain and falls over the
last 6 months",History revealed an onset of leg pain and falls over the last 6 months,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,time_to_diagnosis,0.5,2,model_candidate,1886,1944,"His current neu-
rologist had diagnosed stiff-man
syndrome",His current neu- rologist had diagnosed stiff-man syndrome,model_supporting_snippet_2,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,first_manifestation,multiple,1,model_candidate,1159,1229,"History revealed an
onset of leg pain and falls over the
last 6 months",History revealed an onset of leg pain and falls over the last 6 months,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,first_manifestation_multiple,pain;weakness,1,model_candidate,1159,1229,"History revealed an
onset of leg pain and falls over the
last 6 months",History revealed an onset of leg pain and falls over the last 6 months,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,first_manifestation_multiple,pain;weakness,2,model_candidate,137,217,"He was
complaining of weakness on his
right side and numbness in his
right foot.",He was complaining of weakness on his right side and numbness in his right foot.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,included_diagnosis,Stiff_Person,1,model_candidate,1886,1944,"His current neu-
rologist had diagnosed stiff-man
syndrome",His current neu- rologist had diagnosed stiff-man syndrome,model_extraction_text,folded_alnum_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,early_symptoms,spasms,1,model_candidate,1351,1438,"slight
tremors in his legs while sleeping
with occasional daytime twitching
in his face",slight tremors in his legs while sleeping with occasional daytime twitching in his face,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,early_symptoms,spasms,2,model_candidate,968,1002,kicking his legs on the bed boards,kicking his legs on the bed boards,model_supporting_snippet_2,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json
551,,spasms_distribution_onset,multiple,1,model_candidate,1351,

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/openai_pilot_10/run_manifest.json
{
  "generated_at_utc": "2026-05-29T17:35:55.782170+00:00",
  "run_status": "completed",
  "provider": "openai",
  "model_id": "gpt-5.5",
  "gemini_env_file": "env\\gemini.env",
  "openai_env_file": "env\\openai_api_key.env",
  "openai_reasoning_effort": "low",
  "openai_max_output_tokens": 8000,
  "dry_run": false,
  "allow_paid_run": true,
  "api_retries": 2,
  "api_retry_wait_seconds": 20.0,
  "selected_record_count": 10,
  "completed_record_count": 10,
  "field_review_row_count": 263,
  "selected_rows_path": "qa\\validation\\langextract_example_bootstrap\\openai_pilot_10\\selected_rows.csv",
  "field_candidates_path": "qa\\validation\\langextract_example_bootstrap\\openai_pilot_10\\field_candidates.jsonl",
  "field_review_path": "qa\\validation\\langextract_example_bootstrap\\openai_pilot_10\\field_review.csv",
  "draft_examples_path": "",
  "failed_paper_id": "",
  "failure_type": "",
  "failure_message": ""
}

## qa/validation/langextract_example_bootstrap/openai_pilot_10/selected_rows.csv
paper_id,case_id,target_view_json_path,field_count,text_sha256
524,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\524\p1.json,37,1cc40bcf431cacd40f75bc3819edf3bcfb8b94a12d2e9dee7566516b608f79fa
537,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\537\p1.json,23,9e1ca55982a708ce9f471e47bb7567c8a5d81e931282f00bdfda4d50cde76fdf
551,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\551\p1.json,26,7b810e403a35300114dd24c05dbc2446f10fe2e8b2c4a6ef501b28fd5fe5b8af
552,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json,26,919467ab1152f3f2aa4edbd44d4bd4d69917dfd8783bc9f5b2d856fc87208c5d
554,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\554\p1.json,13,5c9d424227144f6864317d87a8ac536ea97f7588c162909ed2ac8456d96c15b2
566,,qa\validation\stage07_single_case_codex_gold\batch010\json\target_views\566\p1.json,24,7a64cb4a1dd62dfa91a2324aac3fda65e954c36e937082c89a0900e6daf649fd
573,,qa\validation\stage07_single_case_codex_gold\batch010\json\target_views\573\p1.json,12,fb162aaaaa30a4c318d95b1f2c9de0cc7e0e1eabfa43806e87b8e60a18e8442b
615,,qa\validation\stage07_single_case_codex_gold\batch011\json\target_views\615\p1.json,43,c33bdcffd771556d4740326baf9afc728f995ea8bb8641d3d63b8cc066e183cc
621,,qa\validation\stage07_single_case_codex_gold\batch011\json\target_views\621\p1.json,34,59bb1832b987002e747161ca2bc372b61d572f03e02c5c860fd692aa2c1e4caf
623,,qa\validation\stage07_single_case_codex_gold\batch011\json\target_views\623\p1.json,25,907b5a0132b32650151e748906888df49d9a1da939213e73a60642b0a8a189c4


## qa/validation/langextract_example_bootstrap/openai_pilot_10/span_plan_examples_manifest.json
{
  "generated_at_utc": "2026-05-29T18:06:35.010534+00:00",
  "span_plan_path": "qa\\validation\\langextract_example_bootstrap\\openai_pilot_10\\gold_source_span_plan.csv",
  "examples_path": "examples\\langextract_bootstrap\\draft_langextract_examples_openai_pilot10_all_gold.json",
  "example_count": 50,
  "source_document_count": 10,
  "extraction_count": 387,
  "langextract_compatibility": {
    "example_count": 50,
    "extraction_count": 387,
    "alignment_issue_count": 0,
    "attribute_error_count": 0,
    "alignment_policy": {
      "enable_fuzzy_alignment": false,
      "accept_match_lesser": false
    },
    "alignment_issues": [],
    "attribute_errors": []
  },
  "field_row_count": 263,
  "support_span_count": 387,
  "coverage_error_count": 0,
  "coverage_errors": [],
  "coverage_quality_counts": {
    "context_or_absence_only_not_direct_extraction": 5,
    "covered_by_repaired_exact_source_text": 127,
    "direct_exact_span_ready": 112,
    "gold_source_conflict_or_partial_support": 12,
    "needs_human_adjudication": 7
  },
  "recommendation_counts": {
    "candidate_after_span_review": 127,
    "candidate_for_promotion_after_spot_check": 112,
    "do_not_promote_as_standard_langextract_example": 17,
    "review_before_promoting": 7
  }
}

## qa/validation/langextract_example_bootstrap/openai_smoke_552/field_candidates.jsonl
{"paper_id": "552", "case_id": "", "model_id": "gpt-5.5-2026-04-23", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "49", "evidence_mode": "exact_quote", "extraction_text": "A 49-year-old male", "supporting_snippets": [], "reasoning_short": "Age is directly stated.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "M", "evidence_mode": "exact_quote", "extraction_text": "A 49-year-old male", "supporting_snippets": [], "reasoning_short": "Male supports M.", "supports_manual_value": true}, {"field_name": "ethnicity", "spreadsheet_value": "NA", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "Ethnicity is not reported in the supplied text.", "supports_manual_value": false}, {"field_name": "time_to_diagnosis", "spreadsheet_value": "0.5", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration", "He was diagnosed with SPS"], "reasoning_short": "Six months duration before SPS diagnosis corresponds to 0.5 years.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration", "He experienced constant hip pain"], "reasoning_short": "Initial presentation included multiple manifestations: rigidity/stiffness, spasms, and pain.", "supports_manual_value": true}, {"field_name": "first_manifestation_multiple", "spreadsheet_value": "stiffness;spasms;pain", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration", "He experienced constant hip pain"], "reasoning_short": "Muscle rigidity supports stiffness; spasms and hip pain are directly described.", "supports_manual_value": true}, {"field_name": "included_diagnosis", "spreadsheet_value": "Stiff_Person", "evidence_mode": "exact_quote", "extraction_text": "He was diagnosed with SPS", "supporting_snippets": [], "reasoning_short": "SPS denotes stiff-person syndrome in the source context.", "supports_manual_value": true}, {"field_name": "early_symptoms", "spreadsheet_value": "stiffness,spasms", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration"], "reasoning_short": "Muscle rigidity supports stiffness, and spasms are stated as early symptoms.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_onset", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["muscle rigidity and spasms of his upper and lower extremities"], "reasoning_short": "Onset rigidity/stiffness involved upper and lower extremities, i.e. multiple regions.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_onset_multiple", "spreadsheet_value": "lumb_prox_LE;distal_LE;UE", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["muscle rigidity and spasms of his upper and lower extremities", "He experienced constant hip pain"], "reasoning_short": "Upper extremities support UE; lower extremities and hip involvement support lower/proximal distribution, but distal LE is not specifically separated in the text.", "supports_manual_value": true}, {"field_name": "spasms_distribution_onset", "spreadsheet_value": "multiple", "evidence_mode": "exact_quote", "extraction_text": "spasms of his upper and lower extremities", "supporting_snippets": [], "reasoning_short": "Spasms were present in upper and lower extremities, indicating multiple regions.", "supports_manual_value": true}, {"field_name": "spasms_distribution_onset_multiple", "spreadsheet_value": "lumb_prox_LE;distal_LE;UE", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["spasms of his upper and lower extremities"], "reasoning_short": "Upper and lower extremity spasms support UE and LE distribution; the text does not distinguish proximal from distal LE.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established", "spreadsheet_value": "generalised", "evidence_mode": "exact_quote", "extraction_text": "Physical examination revealed generalized rigidity in both upper and lower extremities.", "supporting_snippets": [], "reasoning_short": "Generalized rigidity directly supports generalized stiffness distribution.", "supports_manual_value": true}, {"field_name": "antibody_status", "spreadsheet_value": "GAD", "evidence_mode": "exact_quote", "extraction_text": "Anti– glutamic acid decarboxylase 65 antibody was elevated", "supporting_snippets": [], "reasoning_short": "Glutamic acid decarboxylase antibody corresponds to GAD antibody.", "supports_manual_value": true}, {"field_name": "antibody_titre", "spreadsheet_value": "609", "evidence_mode": "exact_quote", "extraction_text": "609 nmol/L", "supporting_snippets": [], "reasoning_short": "Antibody titre value is directly stated.", "supports_manual_value": true}, {"field_name": "antibody_units", "spreadsheet_value": "nmol/L", "evidence_mode": "exact_quote", "extraction_text": "609 nmol/L", "supporting_snippets": [], "reasoning_short": "Antibody units are directly stated.", "supports_manual_value": true}, {"field_name": "antibody_tests", "spreadsheet_value": "GAD", "evidence_mode": "exact_quote", "extraction_text": "Anti– glutamic acid decarboxylase 65 antibody", "supporting_snippets": [], "reasoning_short": "The antibody test reported was anti-GAD65.", "supports_manual_value": true}, {"field_name": "CMUA", "spreadsheet_value": "1", "evidence_mode": "exact_quote", "extraction_text": "Electromyography showed continuous motor unit activity in agonist and antagonist muscles.", "supporting_snippets": [], "reasoning_short": "Continuous motor unit activity is directly reported, supporting presence coded as 1.", "supports_manual_value": true}, {"field_name": "MRI_normal", "spreadsheet_value": "NA", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "MRI findings are not reported; only computerized tomographies are described.", "supports_manual_value": false}, {"field_name": "immunotherapy", "spreadsheet_value": "IVIG", "evidence_mode": "exact_quote", "extraction_text": "intravenous immunoglobulin at 2 g/kg for 2 days", "supporting_snippets": [], "reasoning_short": "Intravenous immunoglobulin supports IVIG.", "supports_manual_value": true}, {"field_name": "immuntherapy_detail", "spreadsheet_value": "IVIG: 2g/kg for 2d. He has required repeated intravenous infusions\nof immunoglobulin over the years, and his clinical\ncourse has remained stable.", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["intravenous immunoglobulin at 2 g/kg for 2 days", "He has required repeated intravenous infusions of immunoglobulin over the years, and his clinical course has remained stable."], "reasoning_short": "Dose/duration and repeated IVIG course are directly described, though spreadsheet wording is normalized/combined.", "supports_manual_value": true}, {"field_name": "immunotherapy_effect", "spreadsheet_value": "improvement", "evidence_mode": "exact_quote", "extraction_text": "gradual improvement in functional status", "supporting_snippets": [], "reasoning_short": "Clinical improvement after treatment is directly stated.", "supports_manual_value": true}, {"field_name": "sympt_treatment", "spreadsheet_value": "benzo;baclofen", "evidence_mode": "exact_quote", "extraction_text": "10 mg twice daily oral diazepam, oral baclofen at 10 mg thrice daily", "supporting_snippets": [], "reasoning_short": "Diazepam is a benzodiazepine and baclofen is directly named.", "supports_manual_value": true}, {"field_name": "sympt_treatment_detail", "spreadsheet_value": "10 mg twice daily oral diazepam, oral baclofen at 10 mg thrice daily", "evidence_mode": "exact_quote", "extraction_text": "10 mg twice daily oral diazepam, oral baclofen at 10 mg thrice daily", "supporting_snippets": [], "reasoning_short": "The symptomatic treatment details are quoted verbatim.", "supports_manual_value": true}, {"field_name": "other_treatment", "spreadsheet_value": "vitamin B12 replacement", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["He also received vitamin B 12 therapy."], "reasoning_short": "Vitamin B12 therapy supports vitamin B12 replacement.", "supports_manual_value": true}, {"field_name": "autoimmunity", "spreadsheet_value": "diabetes;gastric", "evidence_mode": "inferred_from_text", "extraction_text": "", "supporting_snippets": ["Past medical history was significant for previous hospitalization for diabetic ketoacidosis", "Antibody to intrinsic factor was positive, consistent with a diagnosis of pernicious anemia."], "reasoning_short": "Diabetic ketoacidosis supports diabetes history; intrinsic factor antibody/pernicious anemia supports autoimmune gastric disease.", "supports_manual_value": true}]}


## qa/validation/langextract_example_bootstrap/openai_smoke_552/field_review.csv
paper_id,case_id,field_name,spreadsheet_value,model_spreadsheet_value,evidence_mode,extraction_text,char_start,char_end,supporting_snippets_json,supports_manual_value,reasoning_short,validator_status,review_status,review_notes,target_view_json_path
552,,age_description,49,49,exact_quote,A 49-year-old male,0,18,[],TRUE,Age is directly stated.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,sex,M,M,exact_quote,A 49-year-old male,0,18,[],TRUE,Male supports M.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,ethnicity,NA,NA,not_found,,,,[],FALSE,Ethnicity is not reported in the supplied text.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,time_to_diagnosis,0.5,0.5,inferred_from_text,,,,"[""progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration"", ""He was diagnosed with SPS""]",TRUE,Six months duration before SPS diagnosis corresponds to 0.5 years.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,first_manifestation,multiple,multiple,inferred_from_text,,,,"[""presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration"", ""He experienced constant hip pain""]",TRUE,"Initial presentation included multiple manifestations: rigidity/stiffness, spasms, and pain.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,first_manifestation_multiple,stiffness;spasms;pain,stiffness;spasms;pain,inferred_from_text,,,,"[""presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration"", ""He experienced constant hip pain""]",TRUE,Muscle rigidity supports stiffness; spasms and hip pain are directly described.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,included_diagnosis,Stiff_Person,Stiff_Person,exact_quote,He was diagnosed with SPS,1211,1236,[],TRUE,SPS denotes stiff-person syndrome in the source context.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,early_symptoms,"stiffness,spasms","stiffness,spasms",inferred_from_text,,,,"[""presented with progressively worsening muscle rigidity and spasms of his upper and lower extremities of 6 months’ duration""]",TRUE,"Muscle rigidity supports stiffness, and spasms are stated as early symptoms.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,stiffness_distribution_onset,multiple,multiple,inferred_from_text,,,,"[""muscle rigidity and spasms of his upper and lower extremities""]",TRUE,"Onset rigidity/stiffness involved upper and lower extremities, i.e. multiple regions.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,stiffness_distribution_onset_multiple,lumb_prox_LE;distal_LE;UE,lumb_prox_LE;distal_LE;UE,inferred_from_text,,,,"[""muscle rigidity and spasms of his upper and lower extremities"", ""He experienced constant hip pain""]",TRUE,"Upper extremities support UE; lower extremities and hip involvement support lower/proximal distribution, but distal LE is not specifically separated in the text.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,spasms_distribution_onset,multiple,multiple,exact_quote,spasms of his upper and lower extremities,,,[],TRUE,"Spasms were present in upper and lower extremities, indicating multiple regions.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,spasms_distribution_onset_multiple,lumb_prox_LE;distal_LE;UE,lumb_prox_LE;distal_LE;UE,inferred_from_text,,,,"[""spasms of his upper and lower extremities""]",TRUE,Upper and lower extremity spasms support UE and LE distribution; the text does not distinguish proximal from distal LE.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,stiffness_distribution_established,generalised,generalised,exact_quote,Physical examination revealed generalized rigidity in both upper and lower extremities.,,,[],TRUE,Generalized rigidity directly supports generalized stiffness distribution.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_status,GAD,GAD,exact_quote,Anti– glutamic acid decarboxylase 65 antibody was elevated,,,[],TRUE,Glutamic acid decarboxylase antibody corresponds to GAD antibody.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_titre,609,609,exact_quote,609 nmol/L,1108,1118,[],TRUE,Antibody titre value is directly stated.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_units,nmol/L,nmol/L,exact_quote,609 nmol/L,1108,1118,[],TRUE,Antibody units are directly stated.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,antibody_tests,GAD,GAD,exact_quote,Anti– glutamic acid decarboxylase 65 antibody,,,[],TRUE,The antibody test reported was anti-GAD65.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,CMUA,1,1,exact_quote,Electromyography showed continuous motor unit activity in agonist and antagonist muscles.,,,[],TRUE,"Continuous motor unit activity is directly reported, supporting presence coded as 1.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,MRI_normal,NA,NA,not_found,,,,[],FALSE,MRI findings are not reported; only computerized tomographies are described.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,immunotherapy,IVIG,IVIG,exact_quote,intravenous immunoglobulin at 2 g/kg for 2 days,,,[],TRUE,Intravenous immunoglobulin supports IVIG.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,immuntherapy_detail,"IVIG: 2g/kg for 2d. He has required repeated intravenous infusions
of immunoglobulin over the years, and his clinical
course has remained stable.","IVIG: 2g/kg for 2d. He has required repeated intravenous infusions
of immunoglobulin over the years, and his clinical
course has remained stable.",inferred_from_text,,,,"[""intravenous immunoglobulin at 2 g/kg for 2 days"", ""He has required repeated intravenous infusions of immunoglobulin over the years, and his clinical course has remained stable.""]",TRUE,"Dose/duration and repeated IVIG course are directly described, though spreadsheet wording is normalized/combined.",inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,immunotherapy_effect,improvement,improvement,exact_quote,gradual improvement in functional status,,,[],TRUE,Clinical improvement after treatment is directly stated.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,sympt_treatment,benzo;baclofen,benzo;baclofen,exact_quote,"10 mg twice daily oral diazepam, oral baclofen at 10 mg thrice daily",,,[],TRUE,Diazepam is a benzodiazepine and baclofen is directly named.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,sympt_treatment_detail,"10 mg twice daily oral diazepam, oral baclofen at 10 mg thrice daily","10 mg twice daily oral diazepam, oral baclofen at 10 mg thrice daily",exact_quote,"10 mg twice daily oral diazepam, oral baclofen at 10 mg thrice daily",,,[],TRUE,The symptomatic treatment details are quoted verbatim.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,other_treatment,vitamin B12 replacement,vitamin B12 replacement,inferred_from_text,,,,"[""He also received vitamin B 12 therapy.""]",TRUE,Vitamin B12 therapy supports vitamin B12 replacement.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json
552,,autoimmunity,diabetes;gastric,diabetes;gastric,inferred_from_text,,,,"[""Past medical history was significant for previous hospitalization for diabetic ketoacidosis"", ""Antibody to intrinsic factor was positive, consistent with a diagnosis of pernicious anemia.""]",TRUE,Diabetic ketoacidosis supports diabetes history; intrinsic factor antibody/pernicious anemia supports autoimmune gastric disease.,inference_snippet_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json


## qa/validation/langextract_example_bootstrap/openai_smoke_552/run_manifest.json
{
  "generated_at_utc": "2026-05-29T17:30:36.487008+00:00",
  "run_status": "completed",
  "provider": "openai",
  "model_id": "gpt-5.5",
  "gemini_env_file": "env\\gemini.env",
  "openai_env_file": "env\\openai_api_key.env",
  "openai_reasoning_effort": "low",
  "openai_max_output_tokens": 8000,
  "dry_run": false,
  "allow_paid_run": true,
  "api_retries": 2,
  "api_retry_wait_seconds": 20.0,
  "selected_record_count": 1,
  "completed_record_count": 1,
  "field_review_row_count": 26,
  "selected_rows_path": "qa\\validation\\langextract_example_bootstrap\\openai_smoke_552\\selected_rows.csv",
  "field_candidates_path": "qa\\validation\\langextract_example_bootstrap\\openai_smoke_552\\field_candidates.jsonl",
  "field_review_path": "qa\\validation\\langextract_example_bootstrap\\openai_smoke_552\\field_review.csv",
  "draft_examples_path": "",
  "failed_paper_id": "",
  "failure_type": "",
  "failure_message": ""
}

## qa/validation/langextract_example_bootstrap/openai_smoke_552/selected_rows.csv
paper_id,case_id,target_view_json_path,field_count,text_sha256
552,,qa\validation\stage07_single_case_codex_gold\batch009\json\target_views\552\p1.json,26,919467ab1152f3f2aa4edbd44d4bd4d69917dfd8783bc9f5b2d856fc87208c5d


## qa/validation/langextract_example_bootstrap/pilot_10/field_candidates.jsonl
{"paper_id": "75", "case_id": "", "model_id": "gemini-2.5-flash", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "39", "evidence_mode": "exact_quote", "extraction_text": "A 39-year-old black woman", "supporting_snippets": [], "reasoning_short": "The patient's age is directly stated as 39.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "F", "evidence_mode": "inferred_from_text", "extraction_text": "A 39-year-old black woman", "supporting_snippets": [], "reasoning_short": "The text refers to the patient as a 'woman', indicating female sex.", "supports_manual_value": true}, {"field_name": "ethnicity", "spreadsheet_value": "africa", "evidence_mode": "inferred_from_text", "extraction_text": "A 39-year-old black woman", "supporting_snippets": [], "reasoning_short": "The text describes the patient as 'black', which is categorized as 'africa' in the spreadsheet.", "supports_manual_value": true}, {"field_name": "age_onset", "spreadsheet_value": "38", "evidence_mode": "inferred_from_text", "extraction_text": "A 39-year-old black woman who had back pain was carried into the ED by two relatives. She related that she had had severe, intermittent back spasms over the preceding week. The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year.", "supporting_snippets": [], "reasoning_short": "The patient is 39 years old and reported less intense symptoms over the preceding year, indicating an onset at age 38.", "supports_manual_value": true}, {"field_name": "time_to_diagnosis", "spreadsheet_value": "1", "evidence_mode": "inferred_from_text", "extraction_text": "The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year. She was discharged after four days in the hospital with the diagnosis of probable stiff-man syndrome.", "supporting_snippets": [], "reasoning_short": "Symptoms started 'over the preceding year' (age 38) and diagnosis was made during the current admission (age 39), indicating a 1-year time to diagnosis.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "spasms", "evidence_mode": "exact_quote", "extraction_text": "Review of her medical record showed a history of low back pain with spasms and right lower-extremity spasms for about three years.", "supporting_snippets": [], "reasoning_short": "The medical record indicates a history of 'spasms' as part of the initial symptoms.", "supports_manual_value": true}, {"field_name": "spasms_distribution_onset", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year.", "supporting_snippets": [], "reasoning_short": "The patient experienced spasms in both the low back and right leg, indicating multiple distributions.", "supports_manual_value": true}, {"field_name": "spasms_distribution_onset_multiple", "spreadsheet_value": "axial;right_leg", "evidence_mode": "inferred_from_text", "extraction_text": "The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year.", "supporting_snippets": [], "reasoning_short": "The 'low back pains' correspond to axial distribution, and 'right leg spasms' correspond to right_leg distribution.", "supports_manual_value": true}, {"field_name": "other_symptoms_onset", "spreadsheet_value": "pain;vomiting", "evidence_mode": "inferred_from_text", "extraction_text": "The patient’s review of systems was significant for occasional vomiting when she attempted to take medications. However, she remained alert and cried out in pain.", "supporting_snippets": ["The patient’s review of systems was significant for occasional vomiting when she attempted to take medications.", "However, she remained alert and cried out in pain."], "reasoning_short": "The patient reported occasional vomiting and experienced pain during spasms.", "supports_manual_value": true}, {"field_name": "onset_to_established", "spreadsheet_value": "12", "evidence_mode": "inferred_from_text", "extraction_text": "The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year. She related that she had had severe, intermittent back spasms over the preceding week.", "supporting_snippets": [], "reasoning_short": "The patient had less intense symptoms for a year, which then became severe in the preceding week, indicating 12 months from onset to established severe symptoms.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established", "spreadsheet_value": "axial", "evidence_mode": "inferred_from_text", "extraction_text": "She had intermittent spasms of the trunk with arching posture, lasting 2 to 5 minutes. The patient experienced moderate to severe paraspinal spasm, with a mild-moderate hyperlordosis during spasms.", "supporting_snippets": [], "reasoning_short": "Spasms of the 'trunk' and 'paraspinal' muscles are indicative of axial distribution.", "supports_manual_value": true}, {"field_name": "excessive_startle_established", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "These episodes of opisthotonos seemed triggered by external stimuli (e.g., by opening the door, speaking, and tactile stimuli, but not by loud noises).", "supporting_snippets": [], "reasoning_short": "The text lists multiple external stimuli that triggered spasms.", "supports_manual_value": true}, {"field_name": "excessive_startle_established_multipleother", "spreadsheet_value": "noise;tactile;speaking", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The text explicitly states that spasms were 'not by loud noises', which contradicts the 'noise' component of the spreadsheet value.", "supports_manual_value": false}, {"field_name": "antibody_status", "spreadsheet_value": "GAD", "evidence_mode": "exact_quote", "extraction_text": "A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)", "supporting_snippets": [], "reasoning_short": "The text explicitly mentions a positive result for 'anti-GAD' antibodies.", "supports_manual_value": true}, {"field_name": "CSF_antibody", "spreadsheet_value": "GAD", "evidence_mode": "inferred_from_text", "extraction_text": "A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)", "supporting_snippets": [], "reasoning_short": "A 'lumbar puncture' is used to collect cerebrospinal fluid (CSF), and the test for anti-GAD antibodies was performed on this sample.", "supports_manual_value": true}, {"field_name": "CMUA", "spreadsheet_value": "1", "evidence_mode": "inferred_from_text", "extraction_text": "Needle EMG showed increased volitional activity and poor relaxation, particularly in the right tibialis anterior and lumbosacral paraspinal muscles in association with severe spasm.", "supporting_snippets": [], "reasoning_short": "The EMG findings of increased volitional activity and poor relaxation in affected muscles are characteristic of Continuous Motor Unit Activity (CMUA).", "supports_manual_value": true}, {"field_name": "sympt_treatment", "spreadsheet_value": "benzo;other", "evidence_mode": "inferred_from_text", "extraction_text": "Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid.", "supporting_snippets": [], "reasoning_short": "Diazepam is a benzodiazepine (benzo), and chlorzoxazone is another type of muscle relaxant ('other').", "supports_manual_value": true}, {"field_name": "sympt_treatment_detail", "spreadsheet_value": "diazepam 5mg and chlorzoxazone 500mg qid with improvement", "evidence_mode": "inferred_from_text", "extraction_text": "Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid. A marked amelioration of symptoms with the IV administration of diazepam. The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.", "supporting_snippets": ["Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid.", "A marked amelioration of symptoms with the IV administration of diazepam.", "The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose."], "reasoning_short": "The spreadsheet value combines the initial treatment regimen (diazepam 5mg and chlorzoxazone 500mg qid) with the overall positive effect ('improvement') observed with benzodiazepine treatment, although the improvement was achieved with increased doses.", "supports_manual_value": true}, {"field_name": "sympt_treatment_effect", "spreadsheet_value": "improvement", "evidence_mode": "inferred_from_text", "extraction_text": "A marked amelioration of symptoms with the IV administration of diazepam. The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.", "supporting_snippets": ["A marked amelioration of symptoms with the IV administration of diazepam.", "The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose."], "reasoning_short": "The text states that symptoms were 'ameliorated' and 'finally controlled' with diazepam, indicating an improvement.", "supports_manual_value": true}, {"field_name": "autoimmunity", "spreadsheet_value": "gastric", "evidence_mode": "inferred_from_text", "extraction_text": "Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.", "supporting_snippets": [], "reasoning_short": "Atrophic gastritis is an autoimmune condition affecting the stomach (gastric).", "supports_manual_value": true}, {"field_name": "autoimmunity_specify", "spreadsheet_value": "atrophic gastritis with vitamin B12 deficiency", "evidence_mode": "exact_quote", "extraction_text": "Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.", "supporting_snippets": [], "reasoning_short": "The specific autoimmune condition is directly quoted.", "supports_manual_value": true}]}
{"paper_id": "92", "case_id": "3", "model_id": "gemini-2.5-flash", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "68", "evidence_mode": "inferred_from_text", "extraction_text": "In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "supporting_snippets": ["In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."], "reasoning_short": "The text states the patient was 67 years old when symptoms developed, not 68.", "supports_manual_value": false}, {"field_name": "age_onset", "spreadsheet_value": "67", "evidence_mode": "exact_quote", "extraction_text": "In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "supporting_snippets": ["In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."], "reasoning_short": "The patient was 67 years old when symptoms began.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "supporting_snippets": ["In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."], "reasoning_short": "The patient presented with multiple symptoms including confusion, stiffness, myoclonus, and numbness.", "supports_manual_value": true}, {"field_name": "first_manifestation_multiple", "spreadsheet_value": "confusion;stiffness;myoclonus;numbness", "evidence_mode": "exact_quote", "extraction_text": "In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "supporting_snippets": ["In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."], "reasoning_short": "The patient developed confusion, symmetrical stiffness, myoclonus, and numbness of both feet.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_onset", "spreadsheet_value": "distal_LE", "evidence_mode": "inferred_from_text", "extraction_text": "In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "supporting_snippets": ["In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed."], "reasoning_short": "Initial stiffness was described in 'both legs' and numbness in 'both feet', indicating a distal lower extremity distribution before spreading proximally.", "supports_manual_value": true}, {"field_name": "other_symptoms_onset", "spreadsheet_value": "hyperreflexia;polyneuropathy", "evidence_mode": "exact_quote", "extraction_text": "Examination showed increased tone and hyperreflexia in both legs. Plantar responses were flexor. Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities.", "supporting_snippets": ["Examination showed increased tone and hyperreflexia in both legs.", "Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities."], "reasoning_short": "The examination showed hyperreflexia and electrophysiological studies indicated polyneuropathy.", "supports_manual_value": true}, {"field_name": "timecourse_onset", "spreadsheet_value": "insidious", "evidence_mode": "inferred_from_text", "extraction_text": "In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet. Examination showed increased tone and hyperreflexia in both legs. Plantar responses were flexor. Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities. A sural nerve biopsy specimen showed a mild reduction in the number of myelinated fibers with no inflammation or vasculitis. CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index. The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen. Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.", "supporting_snippets": ["In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed."], "reasoning_short": "The description of symptoms developing and then worsening and spreading over 'the next 6 weeks' suggests an insidious onset.", "supports_manual_value": true}, {"field_name": "timecourse_subsequent", "spreadsheet_value": "chronic_stable", "evidence_mode": "exact_quote", "extraction_text": "As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs. Numbness and dysesthesias of the legs persisted and mild weakness and hyperreflexia of the left arm developed.", "supporting_snippets": ["As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs. Numbness and dysesthesias of the legs persisted and mild weakness and hyperreflexia of the left arm developed."], "reasoning_short": "As of November 1994, the patient's condition was described as 'remained unable to walk' with 'persisted' symptoms, indicating a chronic stable state.", "supports_manual_value": true}, {"field_name": "onset_to_established", "spreadsheet_value": "1.3", "evidence_mode": "inferred_from_text", "extraction_text": "In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet. ... As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.", "supporting_snippets": ["In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.", "As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs."], "reasoning_short": "Symptoms began in September 1993 and by November 1994, the disease was established, which is approximately 1.3 years (1 year and 2 months).", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.", "supporting_snippets": ["Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed."], "reasoning_short": "The rigidity spread proximally to involve abdominal, thoracic muscles, and the diaphragm, indicating multiple distributions.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established_multiple", "spreadsheet_value": "lumb_prox_LE;distal_LE;axial;diaphragm", "evidence_mode": "exact_quote", "extraction_text": "Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed. ... As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.", "supporting_snippets": ["Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm", "As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs."], "reasoning_short": "The rigidity spread to abdominal, thoracic muscles, and the diaphragm (axial, diaphragm), and there was fixed flexion rigidity of both legs (lumb_prox_LE, distal_LE).", "supports_manual_value": true}, {"field_name": "other_symptoms_established", "spreadsheet_value": "respiratory_insufficiency", "evidence_mode": "exact_quote", "extraction_text": "Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.", "supporting_snippets": ["Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed."], "reasoning_short": "The patient developed 'respiratory difficulty' due to diaphragm involvement.", "supports_manual_value": true}, {"field_name": "antibody_status", "spreadsheet_value": "amphiphysin", "evidence_mode": "exact_quote", "extraction_text": "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, though only I patient had clinical rigidity.", "supporting_snippets": ["The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, though only I patient had clinical rigidity."], "reasoning_short": "Patient 3 had antibodies against human amphiphysin.", "supports_manual_value": true}, {"field_name": "antibody_tests", "spreadsheet_value": "antineuronal", "evidence_mode": "exact_quote", "extraction_text": "Serum drawn in September showed antineuronal antibodies (see below).", "supporting_snippets": ["Serum drawn in September showed antineuronal antibodies (see below)."], "reasoning_short": "Antineuronal antibodies were detected in the patient's serum.", "supports_manual_value": true}, {"field_name": "antibody_testsystem", "spreadsheet_value": "western_blot;tissue_assay", "evidence_mode": "exact_quote", "extraction_text": "Serum from each patient immunocytochemically stained the neuropil and to a lesser degree the neuronal cytoplasm in human cerebral and cerebellar cortex. On immunoblots of human neuronal extracts, each patient’s serum contained high-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd.", "supporting_snippets": ["Serum from each patient immunocytochemically stained the neuropil and to a lesser degree the neuronal cytoplasm in human cerebral and cerebellar cortex.", "On immunoblots of human neuronal extracts, each patient’s serum contained high-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd."], "reasoning_short": "Antibodies were detected using immunocytochemical staining (tissue assay) and immunoblots (western blot).", "supports_manual_value": true}, {"field_name": "CSF_status", "spreadsheet_value": "inflammatory", "evidence_mode": "inferred_from_text", "extraction_text": "CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index.", "supporting_snippets": ["CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index."], "reasoning_short": "The CSF analysis showed 30 mononuclear WBCs/µl, which is an elevated count indicating inflammation.", "supports_manual_value": true}, {"field_name": "CMUA", "spreadsheet_value": "0", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "The text describes electrophysiological studies indicating axonal sensorimotor polyneuropathy but does not mention findings specific to CMUA (conduction block or abnormal temporal dispersion).", "supports_manual_value": false}, {"field_name": "tu_screening", "spreadsheet_value": "1", "evidence_mode": "inferred_from_text", "extraction_text": "Biopsy of a subcarinal mass showed SCLC.", "supporting_snippets": ["Biopsy of a subcarinal mass showed SCLC."], "reasoning_short": "A biopsy was performed on a subcarinal mass, indicating tumor screening was done.", "supports_manual_value": true}, {"field_name": "tu_screening_abnormal", "spreadsheet_value": "SCLC", "evidence_mode": "exact_quote", "extraction_text": "Biopsy of a subcarinal mass showed SCLC.", "supporting_snippets": ["Biopsy of a subcarinal mass showed SCLC."], "reasoning_short": "Biopsy of a subcarinal mass showed Small-Cell Lung Carcinoma (SCLC).", "supports_manual_value": true}, {"field_name": "immunotherapy", "spreadsheet_value": "IVIG;steroids", "evidence_mode": "exact_quote", "extraction_text": "The patient received a course of intravenous IgG, was begun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide.", "supporting_snippets": ["The patient received a course of intravenous IgG, was begun on prednisone"], "reasoning_short": "The patient received intravenous IgG and prednisone.", "supports_manual_value": true}, {"field_name": "immuntherapy_detail", "spreadsheet_value": "IVIG and prednisone", "evidence_mode": "exact_quote", "extraction_text": "The patient received a course of intravenous IgG, was begun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide.", "supporting_snippets": ["The patient received a course of intravenous IgG, was begun on prednisone"], "reasoning_short": "The patient received intravenous IgG and prednisone.", "supports_manual_value": true}, {"field_name": "immunotherapy_effect", "spreadsheet_value": "partial improvement", "evidence_mode": "exact_quote", "extraction_text": "Over the next month his mental status returned to near baseline and the myoclonus gradually resolved. ... Patient 3 in the present report partially improved with chemotherapy and immunotherapy, but still could not walk.", "supporting_snippets": ["Over the next month his mental status returned to near baseline and the myoclonus gradually resolved.", "Patient 3 in the present report partially improved with chemotherapy and immunotherapy, but still could not walk."], "reasoning_short": "The patient's mental status returned to near baseline and myoclonus resolved, and it is explicitly stated he 'partially improved'.", "supports_manual_value": true}, {"field_name": "sympt_treatment", "spreadsheet_value": "benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation", "evidence_mode": "exact_quote", "extraction_text": "The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen. Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed. He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks.", "supporting_snippets": ["The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen.", "He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks."], "reasoning_short": "The patient was treated with valproate, diazepam (a benzo), baclofen, pancuronium, ventilatory support, and sedation.", "supports_manual_value": true}, {"field_name": "sympt_treatment_detail", "spreadsheet_value": "Initial: stiffness and myoclonus partially ameliorated by diazepam, valproate, baclofen. Established disease: Pancuronium, ventilatory support and sedation after development of respiratory distress (diaphragm stiffness)", "evidence_mode": "exact_quote", "extraction_text": "The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen. ... He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks.", "supporting_snippets": ["The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen.", "He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks."], "reasoning_short": "The text describes initial treatment with valproate, diazepam, and baclofen for stiffness and myoclonus, and later pancuronium, ventilatory support, and sedation.", "supports_manual_value": true}, {"field_name": "other_treatment", "spreadsheet_value": "6 cycles of SCLC chemotherapy with cisplatin and etoposide", "evidence_mode": "exact_quote", "extraction_text": "The patient received a course of intravenous IgG, was begun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide. ... He received a total of six cycles of chemotherapy; after the first two cycles there was a complete remission of the tumor.", "supporting_snippets": ["began monthly chemotherapy with cisplatin plus etoposide.", "He received a total of six cycles of chemotherapy"], "reasoning_short": "The patient received six cycles of chemotherapy with cisplatin and etoposide for SCLC.", "supports_manual_value": true}, {"field_name": "autoimmunity_specify", "spreadsheet_value": "paraneoplastic polyneuropathy", "evidence_mode": "inferred_from_text", "extraction_text": "Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities. ... Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients.", "supporting_snippets": ["Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities.", "Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients."], "reasoning_short": "The patient had axonal sensorimotor polyneuropathy in the context of a paraneoplastic syndrome associated with SCLC.", "supports_manual_value": true}, {"field_name": "notes", "spreadsheet_value": "SPS and PNP in SCLC", "evidence_mode": "inferred_from_text", "extraction_text": "The third patient had seyere axial and limb rigidity and myoclonus, which partially improved after chemotherapy and treatment with intravenous immunoglobulin and prednisone. ... Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities. ... Biopsy of a subcarinal mass showed SCLC.", "supporting_snippets": ["The third patient had seyere axial and limb rigidity and myoclonus", "Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy", "Biopsy of a subcarinal mass showed SCLC."], "reasoning_short": "Patient 3 presented with rigidity and myoclonus (suggesting SPS), had polyneuropathy (PNP), and an underlying Small-Cell Lung Carcinoma (SCLC).", "supports_manual_value": true}]}
{"paper_id": "155", "case_id": "", "model_id": "gemini-2.5-flash", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "51", "evidence_mode": "exact_quote", "extraction_text": "51 year old man.", "supporting_snippets": [], "reasoning_short": "The age is directly quoted from the text.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "M", "evidence_mode": "inferred_from_text", "extraction_text": "51 year old man.", "supporting_snippets": [], "reasoning_short": "The text refers to the patient as a 'man', indicating male sex.", "supports_manual_value": true}, {"field_name": "first_manifestation", "spreadsheet_value": "multiple", "evidence_mode": "inferred_from_text", "extraction_text": "prodome of rigidity and stiffness in axial muscles", "supporting_snippets": [], "reasoning_short": "The text describes 'rigidity and stiffness' as initial symptoms, implying multiple manifestations.", "supports_manual_value": true}, {"field_name": "first_manifestation_multiple", "spreadsheet_value": "stiffness", "evidence_mode": "exact_quote", "extraction_text": "prodome of rigidity and stiffness in axial muscles", "supporting_snippets": [], "reasoning_short": "Stiffness is explicitly mentioned as a prodromal symptom.", "supports_manual_value": true}, {"field_name": "included_diagnosis", "spreadsheet_value": "Stiff_Person", "evidence_mode": "inferred_from_text", "extraction_text": "One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test", "supporting_snippets": [], "reasoning_short": "The text refers to 'stiff-man syndrome', which is an older term for Stiff Person Syndrome.", "supports_manual_value": true}, {"field_name": "diagnostic_criteria", "spreadsheet_value": "Lorish et al.", "evidence_mode": "exact_quote", "extraction_text": "He fulfilled all criteria established by Lorish et al’", "supporting_snippets": [], "reasoning_short": "The diagnostic criteria are directly attributed to Lorish et al.", "supports_manual_value": true}, {"field_name": "stiffness_distribution_established", "spreadsheet_value": "axial", "evidence_mode": "exact_quote", "extraction_text": "prodome of rigidity and stiffness in axial muscles", "supporting_snippets": [], "reasoning_short": "The text explicitly states stiffness in 'axial muscles'.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established", "spreadsheet_value": "other", "evidence_mode": "inferred_from_text", "extraction_text": "superimposed spasms precipitated by sudden movement and noise", "supporting_snippets": [], "reasoning_short": "The text mentions spasms but does not specify a distribution like axial or limb, thus 'other' is inferred.", "supports_manual_value": true}, {"field_name": "spasms_distribution_established_other", "spreadsheet_value": "unspecified", "evidence_mode": "inferred_from_text", "extraction_text": "superimposed spasms precipitated by sudden movement and noise", "supporting_snippets": [], "reasoning_short": "The text mentions spasms but does not specify a distribution, hence 'unspecified'.", "supports_manual_value": true}, {"field_name": "excessive_startle_established", "spreadsheet_value": "movement;noise", "evidence_mode": "exact_quote", "extraction_text": "superimposed spasms precipitated by sudden movement and noise", "supporting_snippets": [], "reasoning_short": "The text directly states that spasms were precipitated by 'sudden movement and noise'.", "supports_manual_value": true}, {"field_name": "antibody_status", "spreadsheet_value": "GAD;IA-2", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "GAD antibodies are mentioned, but IA-2 antibodies are explicitly stated as undetectable in the text, meaning the full manual value is not supported.", "supports_manual_value": false}, {"field_name": "CSF_status", "spreadsheet_value": "normal", "evidence_mode": "exact_quote", "extraction_text": "Cell count and protein content in the CSF were normal without oligoclonal bands.", "supporting_snippets": [], "reasoning_short": "The CSF cell count and protein content are stated as normal.", "supports_manual_value": true}, {"field_name": "CSF_antibody", "spreadsheet_value": "NA", "evidence_mode": "exact_quote", "extraction_text": "GAD antibodies were not measured in CSF samples.", "supporting_snippets": [], "reasoning_short": "The text explicitly states that GAD antibodies were not measured in CSF samples.", "supports_manual_value": true}, {"field_name": "CSF_antibody_titre", "spreadsheet_value": "NA", "evidence_mode": "inferred_from_text", "extraction_text": "GAD antibodies were not measured in CSF samples.", "supporting_snippets": [], "reasoning_short": "Since CSF antibodies were not measured, their titre is not applicable.", "supports_manual_value": true}, {"field_name": "CMUA", "spreadsheet_value": "1", "evidence_mode": "inferred_from_text", "extraction_text": "the classic EMG findings (continuous normal motor unit firing, despite the patient’s intention to relax)", "supporting_snippets": [], "reasoning_short": "The text describes 'continuous normal motor unit firing', which is characteristic of CMUA.", "supports_manual_value": true}, {"field_name": "immunotherapy", "spreadsheet_value": "steroids;IVIG", "evidence_mode": "not_found", "extraction_text": "", "supporting_snippets": [], "reasoning_short": "Steroids (prednisolone) are mentioned as part of immunosuppressive therapy, but IVIG is not mentioned in the text, meaning the full manual value is not supported.", "supports_manual_value": false}, {"field_name": "immuntherapy_detail", "spreadsheet_value": "500mg iv prednisolone / day for 10d, followed by oral tapering. Then daily 5mg prednisolone and 3 x 5mg diazepam", "evidence_mode": "inferred_from_text", "extraction_text": "Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg. Currently, after 400 days of therapy the patient has good mobility and is without rigidity with 5 mg prednisolone and 3 5 mg diazepam daily", "supporting_snippets": [], "reasoning_short": "Details of prednisolone administration and subsequent maintenance therapy with prednisolone and diazepam are described.", "supports_manual_value": true}, {"field_name": "sympt_treatment", "spreadsheet_value": "benzo", "evidence_mode": "inferred_from_text", "extraction_text": "The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year.", "supporting_snippets": [], "reasoning_short": "Diazepam, a benzodiazepine (benzo), was used for symptomatic treatment.", "supports_manual_value": true}, {"field_name": "sympt_treatment_detail", "spreadsheet_value": "diazepam 3 x 2.5mg / day for 1 year, then diazepam was no longer effective. Then baclofen 3 x 20-25mg/day, improvement for only 4 weeks. Then immunosuppression.", "evidence_mode": "inferred_from_text", "extraction_text": "The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year. Diazepam was then no longer effective and the treatment was changed to baclofen (3 20-25 mg/day), also a GABAergic agonist. Clinical improvement was seen, but lasted only four weeks. Immunosuppressive therapy was therefore initiated", "supporting_snippets": [], "reasoning_short": "The text details the use of diazepam, its loss of effectiveness, the subsequent use of baclofen, its limited effect, and the initiation of immunosuppression.", "supports_manual_value": true}, {"field_name": "sympt_treatment_effect", "spreadsheet_value": "improvement", "evidence_mode": "exact_quote", "extraction_text": "a favourable response to oral administration of diazepam.", "supporting_snippets": [], "reasoning_short": "The text mentions a 'favourable response' to diazepam and 'Clinical improvement' with baclofen.", "supports_manual_value": true}, {"field_name": "autoimmunity_specify", "spreadsheet_value": "diabetes", "evidence_mode": "exact_quote", "extraction_text": "One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test and was diagnosed as having insulin dependent diabetes mellitus.", "supporting_snippets": [], "reasoning_short": "The patient was diagnosed with insulin-dependent diabetes mellitus.", "supports_manual_value": true}, {"field_name": "notes", "spreadsheet_value": "\"thin basement membrane disease\" as comorbidity", "evidence_mode": "exact_quote", "extraction_text": "A kidney biopsy performed because of recurrent microhaematuria disclosed the rare syndrome of “thin basal membranes (200 nm)”.", "supporting_snippets": [], "reasoning_short": "The text describes 'thin basal membranes' as a rare nephropathy found in the patient.", "supports_manual_value": true}]}
{"paper_id": "162", "case_id": "", "model_id": "gemini-2.5-flash", "field_groundings": [{"field_name": "age_description", "spreadsheet_value": "33", "evidence_mode": "exact_quote", "extraction_text": "The patient is a 33-year-old Caucasian woman", "supporting_snippets": ["The patient is a 33-year-old Caucasian woman"], "reasoning_short": "The patient's age is directly quoted as 33 years old.", "supports_manual_value": true}, {"field_name": "sex", "spreadsheet_value": "F", "evidence_mode": "inferred_from_text", "extraction_text": "The patient is a 33-year-old Caucasian woman", "supporting_snippets": ["The patient is a 33-year-old Caucasian woman"], "reasoning_short": "The text refers to the patient as a 'woman', indicating female sex.", "supports_manual_value": true}, {"field_name": "ethnicity", "spreadsheet_value": "white", "evidence_mode": "inferred_from_text", "extraction_text": "The patient is a 33-year-old Caucasian woman", "supporting_snippets": ["The patient is a 

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/pilot_10/field_review.csv
paper_id,case_id,field_name,spreadsheet_value,model_spreadsheet_value,evidence_mode,extraction_text,char_start,char_end,supporting_snippets_json,supports_manual_value,reasoning_short,validator_status,review_status,review_notes,target_view_json_path
75,,age_description,39,39,exact_quote,A 39-year-old black woman,2579,2604,[],TRUE,The patient's age is directly stated as 39.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sex,F,F,inferred_from_text,A 39-year-old black woman,2579,2604,[],TRUE,"The text refers to the patient as a 'woman', indicating female sex.",inference_missing_supporting_snippets,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,ethnicity,africa,africa,inferred_from_text,A 39-year-old black woman,2579,2604,[],TRUE,"The text describes the patient as 'black', which is categorized as 'africa' in the spreadsheet.",inference_missing_supporting_snippets,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,age_onset,38,38,inferred_from_text,"A 39-year-old black woman who had back pain was carried into the ED by two relatives. She related that she had had severe, intermittent back spasms over the preceding week. The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year.",,,[],TRUE,"The patient is 39 years old and reported less intense symptoms over the preceding year, indicating an onset at age 38.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,time_to_diagnosis,1,1,inferred_from_text,The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year. She was discharged after four days in the hospital with the diagnosis of probable stiff-man syndrome.,,,[],TRUE,"Symptoms started 'over the preceding year' (age 38) and diagnosis was made during the current admission (age 39), indicating a 1-year time to diagnosis.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,first_manifestation,spasms,spasms,exact_quote,Review of her medical record showed a history of low back pain with spasms and right lower-extremity spasms for about three years.,,,[],TRUE,The medical record indicates a history of 'spasms' as part of the initial symptoms.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_onset,multiple,multiple,inferred_from_text,The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year.,,,[],TRUE,"The patient experienced spasms in both the low back and right leg, indicating multiple distributions.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_onset_multiple,axial;right_leg,axial;right_leg,inferred_from_text,The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year.,,,[],TRUE,"The 'low back pains' correspond to axial distribution, and 'right leg spasms' correspond to right_leg distribution.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,other_symptoms_onset,pain;vomiting,pain;vomiting,inferred_from_text,"The patient’s review of systems was significant for occasional vomiting when she attempted to take medications. However, she remained alert and cried out in pain.",,,"[""The patient’s review of systems was significant for occasional vomiting when she attempted to take medications."", ""However, she remained alert and cried out in pain.""]",TRUE,The patient reported occasional vomiting and experienced pain during spasms.,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,onset_to_established,12,12,inferred_from_text,"The patient reported similar but less intense low back pains and severe right leg spasms over the preceding year. She related that she had had severe, intermittent back spasms over the preceding week.",,,[],TRUE,"The patient had less intense symptoms for a year, which then became severe in the preceding week, indicating 12 months from onset to established severe symptoms.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_established,axial,axial,inferred_from_text,"She had intermittent spasms of the trunk with arching posture, lasting 2 to 5 minutes. The patient experienced moderate to severe paraspinal spasm, with a mild-moderate hyperlordosis during spasms.",,,[],TRUE,Spasms of the 'trunk' and 'paraspinal' muscles are indicative of axial distribution.,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,excessive_startle_established,multiple,multiple,inferred_from_text,"These episodes of opisthotonos seemed triggered by external stimuli (e.g., by opening the door, speaking, and tactile stimuli, but not by loud noises).",,,[],TRUE,The text lists multiple external stimuli that triggered spasms.,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,excessive_startle_established_multipleother,noise;tactile;speaking,noise;tactile;speaking,not_found,,,,[],FALSE,"The text explicitly states that spasms were 'not by loud noises', which contradicts the 'noise' component of the spreadsheet value.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,antibody_status,GAD,GAD,exact_quote,"A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)",,,[],TRUE,The text explicitly mentions a positive result for 'anti-GAD' antibodies.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,CSF_antibody,GAD,GAD,inferred_from_text,"A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)",,,[],TRUE,"A 'lumbar puncture' is used to collect cerebrospinal fluid (CSF), and the test for anti-GAD antibodies was performed on this sample.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,CMUA,1,1,inferred_from_text,"Needle EMG showed increased volitional activity and poor relaxation, particularly in the right tibialis anterior and lumbosacral paraspinal muscles in association with severe spasm.",,,[],TRUE,The EMG findings of increased volitional activity and poor relaxation in affected muscles are characteristic of Continuous Motor Unit Activity (CMUA).,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment,benzo;other,benzo;other,inferred_from_text,"Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid.",,,[],TRUE,"Diazepam is a benzodiazepine (benzo), and chlorzoxazone is another type of muscle relaxant ('other').",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_detail,diazepam 5mg and chlorzoxazone 500mg qid with improvement,diazepam 5mg and chlorzoxazone 500mg qid with improvement,inferred_from_text,"Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid. A marked amelioration of symptoms with the IV administration of diazepam. The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.",,,"[""Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid."", ""A marked amelioration of symptoms with the IV administration of diazepam."", ""The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.""]",TRUE,"The spreadsheet value combines the initial treatment regimen (diazepam 5mg and chlorzoxazone 500mg qid) with the overall positive effect ('improvement') observed with benzodiazepine treatment, although the improvement was achieved with increased doses.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_effect,improvement,improvement,inferred_from_text,A marked amelioration of symptoms with the IV administration of diazepam. The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.,,,"[""A marked amelioration of symptoms with the IV administration of diazepam."", ""The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.""]",TRUE,"The text states that symptoms were 'ameliorated' and 'finally controlled' with diazepam, indicating an improvement.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,autoimmunity,gastric,gastric,inferred_from_text,Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.,,,[],TRUE,Atrophic gastritis is an autoimmune condition affecting the stomach (gastric).,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,autoimmunity_specify,atrophic gastritis with vitamin B12 deficiency,atrophic gastritis with vitamin B12 deficiency,exact_quote,Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.,,,[],TRUE,The specific autoimmune condition is directly quoted.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
92,3,age_description,68,68,inferred_from_text,"In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.",,,"[""In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.""]",FALSE,"The text states the patient was 67 years old when symptoms developed, not 68.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,age_onset,67,67,exact_quote,"In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.",,,"[""In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.""]",TRUE,The patient was 67 years old when symptoms began.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,first_manifestation,multiple,multiple,inferred_from_text,"In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.",,,"[""In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.""]",TRUE,"The patient presented with multiple symptoms including confusion, stiffness, myoclonus, and numbness.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,first_manifestation_multiple,confusion;stiffness;myoclonus;numbness,confusion;stiffness;myoclonus;numbness,exact_quote,"In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.",,,"[""In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.""]",TRUE,"The patient developed confusion, symmetrical stiffness, myoclonus, and numbness of both feet.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_onset,distal_LE,distal_LE,inferred_from_text,"In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet.",,,"[""In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."", ""Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.""]",TRUE,"Initial stiffness was described in 'both legs' and numbness in 'both feet', indicating a distal lower extremity distribution before spreading proximally.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_symptoms_onset,hyperreflexia;polyneuropathy,hyperreflexia;polyneuropathy,exact_quote,"Examination showed increased tone and hyperreflexia in both legs. Plantar responses were flexor. Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities.",,,"[""Examination showed increased tone and hyperreflexia in both legs."", ""Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities.""]",TRUE,The examination showed hyperreflexia and electrophysiological studies indicated polyneuropathy.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,timecourse_onset,insidious,insidious,inferred_from_text,"In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet. Examination showed increased tone and hyperreflexia in both legs. Plantar responses were flexor. Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities. A sural nerve biopsy specimen showed a mild reduction in the number of myelinated fibers with no inflammation or vasculitis. CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index. The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen. Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.",,,"[""In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."", ""Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.""]",TRUE,The description of symptoms developing and then worsening and spreading over 'the next 6 weeks' suggests an insidious onset.,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,timecourse_subsequent,chronic_stable,chronic_stable,exact_quote,"As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs. Numbness and dysesthesias of the legs persisted and mild weakness and hyperreflexia of the left arm developed.",,,"[""As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs. Numbness and dysesthesias of the legs persisted and mild weakness and hyperreflexia of the left arm developed.""]",TRUE,"As of November 1994, the patient's condition was described as 'remained unable to walk' with 'persisted' symptoms, indicating a chronic stable state.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,onset_to_established,1.3,1.3,inferred_from_text,"In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet. ... As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.",,,"[""In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."", ""As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.""]",TRUE,"Symptoms began in September 1993 and by November 1994, the disease was established, which is approximately 1.3 years (1 year and 2 months).",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_established,multiple,multiple,inferred_from_text,"Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.",,,"[""Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.""]",TRUE,"The rigidity spread proximally to involve abdominal, thoracic muscles, and the diaphragm, indicating multiple distributions.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial;diaphragm,lumb_prox_LE;distal_LE;axial;diaphragm,exact_quote,"Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed. ... As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.",,,"[""Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm"", ""As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.""]",TRUE,"The rigidity spread to abdominal, thoracic muscles, and the diaphragm (axial, diaphragm), and there was fixed flexion rigidity of both legs (lumb_prox_LE, distal_LE).",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_symptoms_established,respiratory_insufficiency,respiratory_insufficiency,exact_quote,"Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.",,,"[""Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed.""]",TRUE,The patient developed 'respiratory difficulty' due to diaphragm involvement.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_status,amphiphysin,amphiphysin,exact_quote,"The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, though only I patient had clinical rigidity.",,,"[""The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, though only I patient had clinical rigidity.""]",TRUE,Patient 3 had antibodies against human amphiphysin.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_tests,antineuronal,antineuronal,exact_quote,Serum drawn in September showed antineuronal antibodies (see below).,,,"[""Serum drawn in September showed antineuronal antibodies (see below).""]",TRUE,Antineuronal antibodies were detected in the patient's serum.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_testsystem,western_blot;tissue_assay,western_blot;tissue_assay,exact_quote,"Serum from each patient immunocytochemically stained the neuropil and to a lesser degree the neuronal cytoplasm in human cerebral and cerebellar cortex. On immunoblots of human neuronal extracts, each patient’s serum contained high-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd.",,,"[""Serum from each patient immunocytochemically stained the neuropil and to a lesser degree the neuronal cytoplasm in human cerebral and cerebellar cortex."", ""On immunoblots of human neuronal extracts, each patient’s serum contained high-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd.""]",TRUE,Antibodies were detected using immunocytochemical staining (tissue assay) and immunoblots (western blot).,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,CSF_status,inflammatory,inflammatory,inferred_from_text,"CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index.",,,"[""CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index.""]",TRUE,"The CSF analysis showed 30 mononuclear WBCs/µl, which is an elevated count indicating inflammation.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,CMUA,0,0,not_found,,,,[],FALSE,The text describes electrophysiological studies indicating axonal sensorimotor polyneuropathy but does not mention findings specific to CMUA (conduction block or abnormal temporal dispersion).,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,tu_screening,1,1,inferred_from_text,Biopsy of a subcarinal mass showed SCLC.,,,"[""Biopsy of a subcarinal mass showed SCLC.""]",TRUE,"A biopsy was performed on a subcarinal mass, indicating tumor screening was done.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,tu_screening_abnormal,SCLC,SCLC,exact_quote,Biopsy of a subcarinal mass showed SCLC.,,,"[""Biopsy of a subcarinal mass showed SCLC.""]",TRUE,Biopsy of a subcarinal mass showed Small-Cell Lung Carcinoma (SCLC).,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy,IVIG;steroids,IVIG;steroids,exact_quote,"The patient received a course of intravenous IgG, was begun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide.",,,"[""The patient received a course of intravenous IgG, was begun on prednisone""]",TRUE,The patient received intravenous IgG and prednisone.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immuntherapy_detail,IVIG and prednisone,IVIG and prednisone,exact_quote,"The patient received a course of intravenous IgG, was begun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide.",,,"[""The patient received a course of intravenous IgG, was begun on prednisone""]",TRUE,The patient received intravenous IgG and prednisone.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy_effect,partial improvement,partial improvement,exact_quote,"Over the next month his mental status returned to near baseline and the myoclonus gradually resolved. ... Patient 3 in the present report partially improved with chemotherapy and immunotherapy, but still could not walk.",,,"[""Over the next month his mental status returned to near baseline and the myoclonus gradually resolved."", ""Patient 3 in the present report partially improved with chemotherapy and immunotherapy, but still could not walk.""]",TRUE,"The patient's mental status returned to near baseline and myoclonus resolved, and it is explicitly stated he 'partially improved'.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,exact_quote,"The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen. Over the next 6 weeks the patient’s myoclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty developed. He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks.",,,"[""The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen."", ""He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks.""]",TRUE,"The patient was treated with valproate, diazepam (a benzo), baclofen, pancuronium, ventilatory support, and sedation.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment_detail,"Initial: stiffness and myoclonus partially ameliorated by diazepam, valproate, baclofen. Established disease: Pancuronium, ventilatory support and sedation after development of respiratory distress (diaphragm stiffness)","Initial: stiffness and myoclonus partially ameliorated by diazepam, valproate, baclofen. Established disease: Pancuronium, ventilatory support and sedation after development of respiratory distress (diaphragm stiffness)",exact_quote,"The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen. ... He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks.",,,"[""The stiffness and myoclonus were partially ameliorated by combinations of oral valproate, diazepam, and baclofen."", ""He was maintained on pancuronium, ventilatory support, and heavy sedation for nearly 2 weeks.""]",TRUE,"The text describes initial treatment with valproate, diazepam, and baclofen for stiffness and myoclonus, and later pancuronium, ventilatory support, and sedation.",quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_treatment,6 cycles of SCLC chemotherapy with cisplatin and etoposide,6 cycles of SCLC chemotherapy with cisplatin and etoposide,exact_quote,"The patient received a course of intravenous IgG, was begun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide. ... He received a total of six cycles of chemotherapy; after the first two cycles there was a complete remission of the tumor.",,,"[""began monthly chemotherapy with cisplatin plus etoposide."", ""He received a total of six cycles of chemotherapy""]",TRUE,The patient received six cycles of chemotherapy with cisplatin and etoposide for SCLC.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,autoimmunity_specify,paraneoplastic polyneuropathy,paraneoplastic polyneuropathy,inferred_from_text,"Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities. ... Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients.",,,"[""Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities."", ""Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients.""]",TRUE,The patient had axonal sensorimotor polyneuropathy in the context of a paraneoplastic syndrome associated with SCLC.,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,notes,SPS and PNP in SCLC,SPS and PNP in SCLC,inferred_from_text,"The third patient had seyere axial and limb rigidity and myoclonus, which partially improved after chemotherapy and treatment with intravenous immunoglobulin and prednisone. ... Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy, with denervation in the upper and lower extremities. ... Biopsy of a subcarinal mass showed SCLC.",,,"[""The third patient had seyere axial and limb rigidity and myoclonus"", ""Electrophysiological studies indicated a moderately severe axonal sensorimotor polyneuropathy"", ""Biopsy of a subcarinal mass showed SCLC.""]",TRUE,"Patient 3 presented with rigidity and myoclonus (suggesting SPS), had polyneuropathy (PNP), and an underlying Small-Cell Lung Carcinoma (SCLC).",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
155,,age_description,51,51,exact_quote,51 year old man.,0,16,[],TRUE,The age is directly quoted from the text.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,sex,M,M,inferred_from_text,51 year old man.,0,16,[],TRUE,"The text refers to the patient as a 'man', indicating male sex.",inference_missing_supporting_snippets,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,first_manifestation,multiple,multiple,inferred_from_text,prodome of rigidity and stiffness in axial muscles,79,129,[],TRUE,"The text describes 'rigidity and stiffness' as initial symptoms, implying multiple manifestations.",inference_missing_supporting_snippets,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,first_manifestation_multiple,stiffness,stiffness,exact_quote,prodome of rigidity and stiffness in axial muscles,79,129,[],TRUE,Stiffness is explicitly mentioned as a prodromal symptom.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,included_diagnosis,Stiff_Person,Stiff_Person,inferred_from_text,One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test,,,[],TRUE,"The text refers to 'stiff-man syndrome', which is an older term for Stiff Person Syndrome.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,diagnostic_criteria,Lorish et al.,Lorish et al.,exact_quote,He fulfilled all criteria established by Lorish et al’,17,71,[],TRUE,The diagnostic criteria are directly attributed to Lorish et al.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,stiffness_distribution_established,axial,axial,exact_quote,prodome of rigidity and stiffness in axial muscles,79,129,[],TRUE,The text explicitly states stiffness in 'axial muscles'.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,spasms_distribution_established,other,other,inferred_from_text,superimposed spasms precipitated by sudden movement and noise,,,[],TRUE,"The text mentions spasms but does not specify a distribution like axial or limb, thus 'other' is inferred.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,spasms_distribution_established_other,unspecified,unspecified,inferred_from_text,superimposed spasms precipitated by sudden movement and noise,,,[],TRUE,"The text mentions spasms but does not specify a distribution, hence 'unspecified'.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,excessive_startle_established,movement;noise,movement;noise,exact_quote,superimposed spasms precipitated by sudden movement and noise,,,[],TRUE,The text directly states that spasms were precipitated by 'sudden movement and noise'.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,antibody_status,GAD;IA-2,GAD;IA-2,not_found,,,,[],FALSE,"GAD antibodies are mentioned, but IA-2 antibodies are explicitly stated as undetectable in the text, meaning the full manual value is not supported.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,CSF_status,normal,normal,exact_quote,Cell count and protein content in the CSF were normal without oligoclonal bands.,,,[],TRUE,The CSF cell count and protein content are stated as normal.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,CSF_antibody,NA,NA,exact_quote,GAD antibodies were not measured in CSF samples.,,,[],TRUE,The text explicitly states that GAD antibodies were not measured in CSF samples.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,CSF_antibody_titre,NA,NA,inferred_from_text,GAD antibodies were not measured in CSF samples.,,,[],TRUE,"Since CSF antibodies were not measured, their titre is not applicable.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,CMUA,1,1,inferred_from_text,"the classic EMG findings (continuous normal motor unit firing, despite the patient’s intention to relax)",,,[],TRUE,"The text describes 'continuous normal motor unit firing', which is characteristic of CMUA.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,immunotherapy,steroids;IVIG,steroids;IVIG,not_found,,,,[],FALSE,"Steroids (prednisolone) are mentioned as part of immunosuppressive therapy, but IVIG is not mentioned in the text, meaning the full manual value is not supported.",needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,immuntherapy_detail,"500mg iv prednisolone / day for 10d, followed by oral tapering. Then daily 5mg prednisolone and 3 x 5mg diazepam","500mg iv prednisolone / day for 10d, followed by oral tapering. Then daily 5mg prednisolone and 3 x 5mg diazepam",inferred_from_text,"Immunosuppressive therapy was therefore initiated, starting with 500 mg intravenous prednisolone from day 1 to 10, followed by oral administration and decreasing doses of 80 to 5 mg. Currently, after 400 days of therapy the patient has good mobility and is without rigidity with 5 mg prednisolone and 3 5 mg diazepam daily",,,[],TRUE,Details of prednisolone administration and subsequent maintenance therapy with prednisolone and diazepam are described.,inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,sympt_treatment,benzo,benzo,inferred_from_text,The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year.,,,[],TRUE,"Diazepam, a benzodiazepine (benzo), was used for symptomatic treatment.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,sympt_treatment_detail,"diazepam 3 x 2.5mg / day for 1 year, then diazepam was no longer effective. Then baclofen 3 x 20-25mg/day, improvement for only 4 weeks. Then immunosuppression.","diazepam 3 x 2.5mg / day for 1 year, then diazepam was no longer effective. Then baclofen 3 x 20-25mg/day, improvement for only 4 weeks. Then immunosuppression.",inferred_from_text,"The patient was first treated with diazepam (3 2. 5-5 mg/day) for one year. Diazepam was then no longer effective and the treatment was changed to baclofen (3 20-25 mg/day), also a GABAergic agonist. Clinical improvement was seen, but lasted only four weeks. Immunosuppressive therapy was therefore initiated",,,[],TRUE,"The text details the use of diazepam, its loss of effectiveness, the subsequent use of baclofen, its limited effect, and the initiation of immunosuppression.",inference_anchor_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,sympt_treatment_effect,improvement,improvement,exact_quote,a favourable response to oral administration of diazepam.,,,[],TRUE,The text mentions a 'favourable response' to diazepam and 'Clinical improvement' with baclofen.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,autoimmunity_specify,diabetes,diabetes,exact_quote,One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test and was diagnosed as having insulin dependent diabetes mellitus.,,,[],TRUE,The patient was diagnosed with insulin-dependent diabetes mellitus.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,notes,"""thin basement membrane disease"" as comorbidity","""thin basement membrane disease"" as comorbidity",exact_quote,A kidney biopsy performed because of recurrent microhaematuria disclosed the rare syndrome of “thin basal membranes (200 nm)”.,,,[],TRUE,The text describes 'thin basal membranes' as a rare nephropathy found in the patient.,quote_not_found,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
162,,age_description,33,33,exact_quote,The patient is a 33-year-old Caucasian woman,1387,1431,"[""The patient is a 33-year-old Caucasian woman""]",TRUE,The patient's age is directly quoted as 33 years old.,passed,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\162\p1.json
162,,sex,F,F,inferred_from_text,The patient is a 33-year-old Caucasian woman,1387,1431,"[""The patient is a 33-year-old Caucasian woman""]",TRUE,"The text refers to the patient as a 'woman', indicating female sex.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\162\p1.json
162,,ethnicity,white,white,inferred_from_text,The patient is a 33-year-old Caucasian woman,1387,1431,"[""The patient is a 33-year-old Caucasian woman""]",TRUE,"The text describes the patient as 'Caucasian', which is synonymous with white ethnicity.",passed,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\162\p1.json
162,,time_to_diagnosis,2.5,2.5,not_found,,,,[],FALSE,The manual value '2.5' is not explicitly stated or clearly inferable from the text regarding the time from symptom onset to SMS diagnosis.,needs_review,draft,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\162\p1.json
162,,first_manifestation,pain,pain,inferred_from_text,"Besides her diabetes, she had a history of pain and stiffness affecting numerous muscle groups, and hospitalization was required for pain control. Also during the summer of 1994 she developed several episodes of intermittent abdominal pain which required evaluation. By the fall of 1994, she had also developed lower extremity pain and weakness.",,,"[""Besides her diabetes, she had a history of pain and stiffness affecting numerous muscle groups, and hospitalization was required for pain control."

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/pilot_10/gold_source_span_plan.csv
paper_id,case_id,field_name,spreadsheet_value,model_spreadsheet_value,original_evidence_mode,original_validator_status,coverage_quality,langextract_recommendation,support_span_count,all_spans_exact_in_stage07_text,support_spans_json,support_spans_display,target_view_json_path
75,,age_description,39,39,exact_quote,passed,direct_exact_span_ready,candidate_for_promotion_after_spot_check,1,TRUE,"[{""span_text"": ""A 39-year-old black woman"", ""char_start"": 2579, ""char_end"": 2604, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A 39-year-old black woman,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sex,F,F,inferred_from_text,inference_missing_supporting_snippets,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""A 39-year-old black woman"", ""char_start"": 2579, ""char_end"": 2604, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A 39-year-old black woman,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,ethnicity,africa,africa,inferred_from_text,inference_missing_supporting_snippets,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""A 39-year-old black woman"", ""char_start"": 2579, ""char_end"": 2604, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""exact"", ""span_role"": ""model_candidate""}]",A 39-year-old black woman,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,age_onset,38,38,inferred_from_text,inference_anchor_not_found,needs_human_adjudication,review_before_promoting,3,TRUE,"[{""span_text"": ""I CASEREPORT \nHistory \nA 39-year-old black woman who had back pain was carried into \nthe ED by two relatives."", ""char_start"": 2556, ""char_end"": 2665, ""selection_source"": ""manual_term:A 39-year-old black woman"", ""match_mode"": ""exact"", ""span_role"": ""support""}, {""span_text"": ""This report describes an illustrative case of a 39-year-old woman who \npresented to the ED with a two-year history of right leg spasms and \nlow back pain that had become so severe in the preceding two days \nthat she was unable to ambulate."", ""char_start"": 418, ""char_end"": 657, ""selection_source"": ""manual_term:two-year history"", ""match_mode"": ""exact"", ""span_role"": ""conflict_context""}, {""span_text"": ""Review of her medical record showed a \nhistory of low back pain with spasms and right lower- \nextremity spasms for about three years."", ""char_start"": 3282, ""char_end"": 3415, ""selection_source"": ""manual_term:about three years"", ""match_mode"": ""exact"", ""span_role"": ""conflict_context""}]",I CASEREPORT History A 39-year-old black woman who had back pain was carried into the ED by two relatives. | This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate. | Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,time_to_diagnosis,1,1,inferred_from_text,inference_anchor_not_found,needs_human_adjudication,review_before_promoting,3,TRUE,"[{""span_text"": ""She was discharged after four days in the \nhospital with the diagnosis of probable stiff-man syn- \ndrome."", ""char_start"": 6434, ""char_end"": 6539, ""selection_source"": ""manual_term:diagnosis of probable stiff-man"", ""match_mode"": ""exact"", ""span_role"": ""support""}, {""span_text"": ""This report describes an illustrative case of a 39-year-old woman who \npresented to the ED with a two-year history of right leg spasms and \nlow back pain that had become so severe in the preceding two days \nthat she was unable to ambulate."", ""char_start"": 418, ""char_end"": 657, ""selection_source"": ""manual_term:two-year history"", ""match_mode"": ""exact"", ""span_role"": ""conflict_context""}, {""span_text"": ""Review of her medical record showed a \nhistory of low back pain with spasms and right lower- \nextremity spasms for about three years."", ""char_start"": 3282, ""char_end"": 3415, ""selection_source"": ""manual_term:about three years"", ""match_mode"": ""exact"", ""span_role"": ""conflict_context""}]",She was discharged after four days in the hospital with the diagnosis of probable stiff-man syn- drome. | This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate. | Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,first_manifestation,spasms,spasms,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""This report describes an illustrative case of a 39-year-old woman who \npresented to the ED with a two-year history of right leg spasms and \nlow back pain that had become so severe in the preceding two days \nthat she was unable to ambulate."", ""char_start"": 418, ""char_end"": 657, ""selection_source"": ""manual_term:two-year history"", ""match_mode"": ""exact"", ""span_role"": ""support""}, {""span_text"": ""Review of her medical record showed a \nhistory of low back pain with spasms and right lower- \nextremity spasms for about three years."", ""char_start"": 3282, ""char_end"": 3415, ""selection_source"": ""manual_term:medical record"", ""match_mode"": ""exact"", ""span_role"": ""support""}]",This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate. | Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_onset,multiple,multiple,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""The patient reported similar but less intense low \nback pains and severe right leg spasms over the pre- \nceding year."", ""char_start"": 3164, ""char_end"": 3281, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",The patient reported similar but less intense low back pains and severe right leg spasms over the pre- ceding year.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_onset_multiple,axial;right_leg,axial;right_leg,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""The patient reported similar but less intense low \nback pains and severe right leg spasms over the pre- \nceding year."", ""char_start"": 3164, ""char_end"": 3281, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",The patient reported similar but less intense low back pains and severe right leg spasms over the pre- ceding year.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,other_symptoms_onset,pain;vomiting,pain;vomiting,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""The patient’s review of systems was significant for \noccasional vomiting when she attempted to take med- \nications."", ""char_start"": 3665, ""char_end"": 3780, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""However, she remained alert and cried out \nin pain."", ""char_start"": 5313, ""char_end"": 5364, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","The patient’s review of systems was significant for occasional vomiting when she attempted to take med- ications. | However, she remained alert and cried out in pain.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,onset_to_established,12,12,inferred_from_text,inference_anchor_not_found,needs_human_adjudication,review_before_promoting,2,TRUE,"[{""span_text"": ""This report describes an illustrative case of a 39-year-old woman who \npresented to the ED with a two-year history of right leg spasms and \nlow back pain that had become so severe in the preceding two days \nthat she was unable to ambulate."", ""char_start"": 418, ""char_end"": 657, ""selection_source"": ""manual_term:two-year history"", ""match_mode"": ""exact"", ""span_role"": ""support""}, {""span_text"": ""Review of her medical record showed a \nhistory of low back pain with spasms and right lower- \nextremity spasms for about three years."", ""char_start"": 3282, ""char_end"": 3415, ""selection_source"": ""manual_term:about three years"", ""match_mode"": ""exact"", ""span_role"": ""conflict_context""}]",This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate. | Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_established,axial,axial,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""She had intermittent \nspasms of the trunk with arching posture, lasting 2 to \n5 minutes."", ""char_start"": 4474, ""char_end"": 4562, ""selection_source"": ""manual_term:intermittent"", ""match_mode"": ""exact"", ""span_role"": ""fallback_context""}]","She had intermittent spasms of the trunk with arching posture, lasting 2 to 5 minutes.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,excessive_startle_established,multiple,multiple,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""These episodes of opisthotonos seemed trig- \ngered by external stimuli (e.g., by opening the door, \nspeaking, and tactile stimuli, but not by loud noises)."", ""char_start"": 4563, ""char_end"": 4718, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","These episodes of opisthotonos seemed trig- gered by external stimuli (e.g., by opening the door, speaking, and tactile stimuli, but not by loud noises).",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,excessive_startle_established_multipleother,tactile;speaking,tactile;speaking,not_found,needs_review,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""These episodes of opisthotonos seemed trig- \ngered by external stimuli (e.g., by opening the door, \nspeaking, and tactile stimuli, but not by loud noises)."", ""char_start"": 4563, ""char_end"": 4718, ""selection_source"": ""manual_answer:remove_noise"", ""match_mode"": ""exact"", ""span_role"": ""support""}]","These episodes of opisthotonos seemed trig- gered by external stimuli (e.g., by opening the door, speaking, and tactile stimuli, but not by loud noises).",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,antibody_status,GAD,GAD,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""A \nlumbar puncture for anti-glutamic acid decarboxylase \n(anti-GAD) antibodies was done. (Several months after \ndischarge, a positive result was obtained.)"", ""char_start"": 6095, ""char_end"": 6250, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,CSF_antibody,GAD,GAD,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""A \nlumbar puncture for anti-glutamic acid decarboxylase \n(anti-GAD) antibodies was done. (Several months after \ndischarge, a positive result was obtained.)"", ""char_start"": 6095, ""char_end"": 6250, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,CMUA,1,1,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Needle EMG showed \nincreased volitional activity and poor relaxation, par- \nticularly in the right tibialis anterior and lumbosacral \nparaspinal muscles in association with severe spasm."", ""char_start"": 5908, ""char_end"": 6094, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Needle EMG showed increased volitional activity and poor relaxation, par- ticularly in the right tibialis anterior and lumbosacral paraspinal muscles in association with severe spasm.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment,benzo;other,benzo;other,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Two days earlier, she \nhad seen an orthopedist who had treated her with diazepam, 5 mg \nbid, and chlorzoxazone, 500 mg qid."", ""char_start"": 2756, ""char_end"": 2879, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_detail,diazepam 5mg and chlorzoxazone 500mg qid with improvement,diazepam 5mg and chlorzoxazone 500mg qid with improvement,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""Two days earlier, she \nhad seen an orthopedist who had treated her with diazepam, 5 mg \nbid, and chlorzoxazone, 500 mg qid."", ""char_start"": 2756, ""char_end"": 2879, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""a marked amelioration of symptoms with the \nIV administration of diazepam."", ""char_start"": 1064, ""char_end"": 1138, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The \npatient was treated with increasing doses of diazepam\n\nand her symptoms were finally controlled on a 10-mg \nqid dose."", ""char_start"": 6311, ""char_end"": 6433, ""selection_source"": ""model_supporting_snippet_3"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid. | a marked amelioration of symptoms with the IV administration of diazepam. | The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_effect,improvement,improvement,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""a marked amelioration of symptoms with the \nIV administration of diazepam."", ""char_start"": 1064, ""char_end"": 1138, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The \npatient was treated with increasing doses of diazepam\n\nand her symptoms were finally controlled on a 10-mg \nqid dose."", ""char_start"": 6311, ""char_end"": 6433, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",a marked amelioration of symptoms with the IV administration of diazepam. | The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,autoimmunity,gastric,gastric,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Her past medical history was significant \nfor a vitamin B12 deficiency and atrophic gastritis for \nwhich she received monthly B12 injections."", ""char_start"": 3904, ""char_end"": 4045, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,autoimmunity_specify,atrophic gastritis with vitamin B12 deficiency,atrophic gastritis with vitamin B12 deficiency,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Her past medical history was significant \nfor a vitamin B12 deficiency and atrophic gastritis for \nwhich she received monthly B12 injections."", ""char_start"": 3904, ""char_end"": 4045, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
92,3,age_description,67,67,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""In September 1993, a 67-year-old man developed confusion, \nsymmetrical stiffness and myoclonus of both legs, and numb- \nness of both feet."", ""char_start"": 10838, ""char_end"": 10976, ""selection_source"": ""manual_answer:use_67"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""support""}]","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,age_onset,67,67,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""In September 1993, a 67-year-old man developed confusion, \nsymmetrical stiffness and myoclonus of both legs, and numb- \nness of both feet."", ""char_start"": 10838, ""char_end"": 10976, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,first_manifestation,multiple,multiple,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""In September 1993, a 67-year-old man developed confusion, \nsymmetrical stiffness and myoclonus of both legs, and numb- \nness of both feet."", ""char_start"": 10838, ""char_end"": 10976, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,first_manifestation_multiple,confusion;stiffness;myoclonus;numbness,confusion;stiffness;myoclonus;numbness,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""In September 1993, a 67-year-old man developed confusion, \nsymmetrical stiffness and myoclonus of both legs, and numb- \nness of both feet."", ""char_start"": 10838, ""char_end"": 10976, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_onset,distal_LE,distal_LE,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""In September 1993, a 67-year-old man developed confusion, \nsymmetrical stiffness and myoclonus of both legs, and numb- \nness of both feet."", ""char_start"": 10838, ""char_end"": 10976, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Over the next 6 weeks the patient’s my- \noclonus and rigidity worsened and spread proximally to \ninvolve the abdominal and thoracic muscles including the \ndiaphragm, to the point where respiratory difficulty devel- \noped."", ""char_start"": 7601, ""char_end"": 7822, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet. | Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_symptoms_onset,hyperreflexia;polyneuropathy,hyperreflexia;polyneuropathy,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Examination showed increased tone and \nhyperreflexia in both legs."", ""char_start"": 10977, ""char_end"": 11043, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Examination showed increased tone and hyperreflexia in both legs.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,timecourse_onset,insidious,insidious,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""In September 1993, a 67-year-old man developed confusion, \nsymmetrical stiffness and myoclonus of both legs, and numb- \nness of both feet."", ""char_start"": 10838, ""char_end"": 10976, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Over the next 6 weeks the patient’s my- \noclonus and rigidity worsened and spread proximally to \ninvolve the abdominal and thoracic muscles including the \ndiaphragm, to the point where respiratory difficulty devel- \noped."", ""char_start"": 7601, ""char_end"": 7822, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet. | Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,timecourse_subsequent,chronic_stable,chronic_stable,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""As of November 1994 he remained \nunable to walk because of severe, fixed flexion rigidity of \nboth legs. Numbness and dysesthesias of the legs persisted \nand mild weakness and hyperreflexia of the left arm devel- \noped."", ""char_start"": 8403, ""char_end"": 8622, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs. Numbness and dysesthesias of the legs persisted and mild weakness and hyperreflexia of the left arm devel- oped.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,onset_to_established,1.3,1.3,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""In September 1993, a 67-year-old man developed confusion, \nsymmetrical stiffness and myoclonus of both legs, and numb- \nness of both feet."", ""char_start"": 10838, ""char_end"": 10976, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""As of November 1994 he remained \nunable to walk because of severe, fixed flexion rigidity of \nboth legs."", ""char_start"": 8403, ""char_end"": 8507, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet. | As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_established,multiple,multiple,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Over the next 6 weeks the patient’s my- \noclonus and rigidity worsened and spread proximally to \ninvolve the abdominal and thoracic muscles including the \ndiaphragm, to the point where respiratory difficulty devel- \noped."", ""char_start"": 7601, ""char_end"": 7822, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial;diaphragm,lumb_prox_LE;distal_LE;axial;diaphragm,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Over the next 6 weeks the patient’s my- \noclonus and rigidity worsened and spread proximally to \ninvolve the abdominal and thoracic muscles including the \ndiaphragm"", ""char_start"": 7601, ""char_end"": 7765, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""As of November 1994 he remained \nunable to walk because of severe, fixed flexion rigidity of \nboth legs."", ""char_start"": 8403, ""char_end"": 8507, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm | As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_symptoms_established,respiratory_insufficiency,respiratory_insufficiency,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Over the next 6 weeks the patient’s my- \noclonus and rigidity worsened and spread proximally to \ninvolve the abdominal and thoracic muscles including the \ndiaphragm, to the point where respiratory difficulty devel- \noped."", ""char_start"": 7601, ""char_end"": 7822, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_status,amphiphysin,amphiphysin,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""The 3 \npatients described here all had SCLC, PEM, and anti- \nbodies against human amphiphysin, though only I pa- \ntient had clinical rigidity."", ""char_start"": 2603, ""char_end"": 2745, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","The 3 patients described here all had SCLC, PEM, and anti- bodies against human amphiphysin, though only I pa- tient had clinical rigidity.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_tests,antineuronal,antineuronal,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Serum drawn in September showed antineuronal \nantibodies (see below)."", ""char_start"": 8208, ""char_end"": 8277, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Serum drawn in September showed antineuronal antibodies (see below).,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_testsystem,western_blot;tissue_assay,western_blot;tissue_assay,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""On immunoblots of human neuronal extracts, each patient’s serum contained \nhigh-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd."", ""char_start"": 747, ""char_end"": 911, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","On immunoblots of human neuronal extracts, each patient’s serum contained high-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,CSF_status,inflammatory,inflammatory,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""CSF analysis revealed a protein \nconcentration of 80 mgidl, 30 mononuclear WBCslpl, and \na normal IgG index."", ""char_start"": 7372, ""char_end"": 7480, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,CMUA,0,0,not_found,needs_review,context_or_absence_only_not_direct_extraction,do_not_promote_as_standard_langextract_example,1,TRUE,"[{""span_text"": ""Examination showed increased tone and \nhyperreflexia in both legs."", ""char_start"": 10977, ""char_end"": 11043, ""selection_source"": ""manual_term:Examination showed increased tone"", ""match_mode"": ""exact"", ""span_role"": ""absence_context""}]",Examination showed increased tone and hyperreflexia in both legs.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,tu_screening,1,1,inferred_from_text,inference_anchor_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Biopsy of a \nsubcarinal mass showed SCLC."", ""char_start"": 7920, ""char_end"": 7961, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Biopsy of a subcarinal mass showed SCLC.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,tu_screening_abnormal,SCLC,SCLC,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,1,TRUE,"[{""span_text"": ""Biopsy of a \nsubcarinal mass showed SCLC."", ""char_start"": 7920, ""char_end"": 7961, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]",Biopsy of a subcarinal mass showed SCLC.,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy,IVIG;steroids,IVIG;steroids,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""The patient received a course of intravenous IgG, was be- \ngun on prednisone, and began monthly chemotherapy with \ncisplatin plus etoposide."", ""char_start"": 7963, ""char_end"": 8103, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The patient received a course of intravenous IgG, was be- \ngun on prednisone"", ""char_start"": 7963, ""char_end"": 8039, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","The patient received a course of intravenous IgG, was be- gun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide. | The patient received a course of intravenous IgG, was be- gun on prednisone",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immuntherapy_detail,IVIG and prednisone,IVIG and prednisone,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""The patient received a course of intravenous IgG, was be- \ngun on prednisone, and began monthly chemotherapy with \ncisplatin plus etoposide."", ""char_start"": 7963, ""char_end"": 8103, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The patient received a course of intravenous IgG, was be- \ngun on prednisone"", ""char_start"": 7963, ""char_end"": 8039, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","The patient received a course of intravenous IgG, was be- gun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide. | The patient received a course of intravenous IgG, was be- gun on prednisone",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy_effect,partial improvement,partial improvement,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,2,TRUE,"[{""span_text"": ""Over the next month his mental\n\nstatus returned to near baseline and the myoclonus gradually \nresolved."", ""char_start"": 8104, ""char_end"": 8207, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""Patient 3 in the \npresent report partially improved with chemotherapy \nand immunotherapy, but still could not walk."", ""char_start"": 39962, ""char_end"": 40077, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","Over the next month his mental status returned to near baseline and the myoclonus gradually resolved. | Patient 3 in the present report partially improved with chemotherapy and immunotherapy, but still could not walk.",qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,exact_quote,quote_not_found,covered_by_repaired_exact_source_text,candidate_after_span_review,3,TRUE,"[{""span_text"": ""The stiffness and myoclonus were par- \ntially ameliorated by combinations of oral valproate, diaze- \npam, and baclofen. Over the next 6 weeks the patient’s my- \noclonus and rigidity worsened and spread proximally to \ninvolve the abdominal and thoracic muscles including the \ndiaphragm, to the point where respiratory difficulty devel- \noped. He was maintained on pancuronium, ventilatory sup- \nport, and heavy sedation for nearly 2 weeks."", ""char_start"": 7481, ""char_end"": 7919, ""selection_source"": ""model_extraction_text"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""The stiffness and myoclonus were par- \ntially ameliorated by combinations of oral valproate, diaze- \npam, and baclofen."", ""char_start"": 7481, ""char_end"": 7600, ""selection_source"": ""model_supporting_snippet_1"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}, {""span_text"": ""He was maintained on pancuronium, ventilatory sup- \nport, and heavy sedation for nearly 2 weeks."", ""char_start"": 7823, ""char_end"": 7919, ""selection_source"": ""model_supporting_snippet_2"", ""match_mode"": ""normalised_to_exact_source"", ""span_role"": ""model_candidate""}]","The stiffness and myoclonus were par- tially ameliorated by combinations of oral valproate, diaze- pam, and baclofe

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/pilot_10/gold_source_span_plan_long.csv
paper_id,case_id,field_name,spreadsheet_value,span_index,span_role,char_start,char_end,span_text,span_text_display,selection_source,match_mode,coverage_quality,langextract_recommendation,target_view_json_path
75,,age_description,39,1,model_candidate,2579,2604,A 39-year-old black woman,A 39-year-old black woman,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sex,F,1,model_candidate,2579,2604,A 39-year-old black woman,A 39-year-old black woman,model_extraction_text,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,ethnicity,africa,1,model_candidate,2579,2604,A 39-year-old black woman,A 39-year-old black woman,model_extraction_text,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,age_onset,38,1,support,2556,2665,"I CASEREPORT 
History 
A 39-year-old black woman who had back pain was carried into 
the ED by two relatives.",I CASEREPORT History A 39-year-old black woman who had back pain was carried into the ED by two relatives.,manual_term:A 39-year-old black woman,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,age_onset,38,2,conflict_context,418,657,"This report describes an illustrative case of a 39-year-old woman who 
presented to the ED with a two-year history of right leg spasms and 
low back pain that had become so severe in the preceding two days 
that she was unable to ambulate.",This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate.,manual_term:two-year history,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,age_onset,38,3,conflict_context,3282,3415,"Review of her medical record showed a 
history of low back pain with spasms and right lower- 
extremity spasms for about three years.",Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,manual_term:about three years,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,time_to_diagnosis,1,1,support,6434,6539,"She was discharged after four days in the 
hospital with the diagnosis of probable stiff-man syn- 
drome.",She was discharged after four days in the hospital with the diagnosis of probable stiff-man syn- drome.,manual_term:diagnosis of probable stiff-man,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,time_to_diagnosis,1,2,conflict_context,418,657,"This report describes an illustrative case of a 39-year-old woman who 
presented to the ED with a two-year history of right leg spasms and 
low back pain that had become so severe in the preceding two days 
that she was unable to ambulate.",This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate.,manual_term:two-year history,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,time_to_diagnosis,1,3,conflict_context,3282,3415,"Review of her medical record showed a 
history of low back pain with spasms and right lower- 
extremity spasms for about three years.",Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,manual_term:about three years,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,first_manifestation,spasms,1,support,418,657,"This report describes an illustrative case of a 39-year-old woman who 
presented to the ED with a two-year history of right leg spasms and 
low back pain that had become so severe in the preceding two days 
that she was unable to ambulate.",This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate.,manual_term:two-year history,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,first_manifestation,spasms,2,support,3282,3415,"Review of her medical record showed a 
history of low back pain with spasms and right lower- 
extremity spasms for about three years.",Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,manual_term:medical record,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_onset,multiple,1,model_candidate,3164,3281,"The patient reported similar but less intense low 
back pains and severe right leg spasms over the pre- 
ceding year.",The patient reported similar but less intense low back pains and severe right leg spasms over the pre- ceding year.,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_onset_multiple,axial;right_leg,1,model_candidate,3164,3281,"The patient reported similar but less intense low 
back pains and severe right leg spasms over the pre- 
ceding year.",The patient reported similar but less intense low back pains and severe right leg spasms over the pre- ceding year.,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,other_symptoms_onset,pain;vomiting,1,model_candidate,3665,3780,"The patient’s review of systems was significant for 
occasional vomiting when she attempted to take med- 
ications.",The patient’s review of systems was significant for occasional vomiting when she attempted to take med- ications.,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,other_symptoms_onset,pain;vomiting,2,model_candidate,5313,5364,"However, she remained alert and cried out 
in pain.","However, she remained alert and cried out in pain.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,onset_to_established,12,1,support,418,657,"This report describes an illustrative case of a 39-year-old woman who 
presented to the ED with a two-year history of right leg spasms and 
low back pain that had become so severe in the preceding two days 
that she was unable to ambulate.",This report describes an illustrative case of a 39-year-old woman who presented to the ED with a two-year history of right leg spasms and low back pain that had become so severe in the preceding two days that she was unable to ambulate.,manual_term:two-year history,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,onset_to_established,12,2,conflict_context,3282,3415,"Review of her medical record showed a 
history of low back pain with spasms and right lower- 
extremity spasms for about three years.",Review of her medical record showed a history of low back pain with spasms and right lower- extremity spasms for about three years.,manual_term:about three years,exact,needs_human_adjudication,review_before_promoting,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,spasms_distribution_established,axial,1,fallback_context,4474,4562,"She had intermittent 
spasms of the trunk with arching posture, lasting 2 to 
5 minutes.","She had intermittent spasms of the trunk with arching posture, lasting 2 to 5 minutes.",manual_term:intermittent,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,excessive_startle_established,multiple,1,model_candidate,4563,4718,"These episodes of opisthotonos seemed trig- 
gered by external stimuli (e.g., by opening the door, 
speaking, and tactile stimuli, but not by loud noises).","These episodes of opisthotonos seemed trig- gered by external stimuli (e.g., by opening the door, speaking, and tactile stimuli, but not by loud noises).",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,excessive_startle_established_multipleother,tactile;speaking,1,support,4563,4718,"These episodes of opisthotonos seemed trig- 
gered by external stimuli (e.g., by opening the door, 
speaking, and tactile stimuli, but not by loud noises).","These episodes of opisthotonos seemed trig- gered by external stimuli (e.g., by opening the door, speaking, and tactile stimuli, but not by loud noises).",manual_answer:remove_noise,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,antibody_status,GAD,1,model_candidate,6095,6250,"A 
lumbar puncture for anti-glutamic acid decarboxylase 
(anti-GAD) antibodies was done. (Several months after 
discharge, a positive result was obtained.)","A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,CSF_antibody,GAD,1,model_candidate,6095,6250,"A 
lumbar puncture for anti-glutamic acid decarboxylase 
(anti-GAD) antibodies was done. (Several months after 
discharge, a positive result was obtained.)","A lumbar puncture for anti-glutamic acid decarboxylase (anti-GAD) antibodies was done. (Several months after discharge, a positive result was obtained.)",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,CMUA,1,1,model_candidate,5908,6094,"Needle EMG showed 
increased volitional activity and poor relaxation, par- 
ticularly in the right tibialis anterior and lumbosacral 
paraspinal muscles in association with severe spasm.","Needle EMG showed increased volitional activity and poor relaxation, par- ticularly in the right tibialis anterior and lumbosacral paraspinal muscles in association with severe spasm.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment,benzo;other,1,model_candidate,2756,2879,"Two days earlier, she 
had seen an orthopedist who had treated her with diazepam, 5 mg 
bid, and chlorzoxazone, 500 mg qid.","Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_detail,diazepam 5mg and chlorzoxazone 500mg qid with improvement,1,model_candidate,2756,2879,"Two days earlier, she 
had seen an orthopedist who had treated her with diazepam, 5 mg 
bid, and chlorzoxazone, 500 mg qid.","Two days earlier, she had seen an orthopedist who had treated her with diazepam, 5 mg bid, and chlorzoxazone, 500 mg qid.",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_detail,diazepam 5mg and chlorzoxazone 500mg qid with improvement,2,model_candidate,1064,1138,"a marked amelioration of symptoms with the 
IV administration of diazepam.",a marked amelioration of symptoms with the IV administration of diazepam.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_detail,diazepam 5mg and chlorzoxazone 500mg qid with improvement,3,model_candidate,6311,6433,"The 
patient was treated with increasing doses of diazepam

and her symptoms were finally controlled on a 10-mg 
qid dose.",The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.,model_supporting_snippet_3,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_effect,improvement,1,model_candidate,1064,1138,"a marked amelioration of symptoms with the 
IV administration of diazepam.",a marked amelioration of symptoms with the IV administration of diazepam.,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,sympt_treatment_effect,improvement,2,model_candidate,6311,6433,"The 
patient was treated with increasing doses of diazepam

and her symptoms were finally controlled on a 10-mg 
qid dose.",The patient was treated with increasing doses of diazepam and her symptoms were finally controlled on a 10-mg qid dose.,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,autoimmunity,gastric,1,model_candidate,3904,4045,"Her past medical history was significant 
for a vitamin B12 deficiency and atrophic gastritis for 
which she received monthly B12 injections.",Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
75,,autoimmunity_specify,atrophic gastritis with vitamin B12 deficiency,1,model_candidate,3904,4045,"Her past medical history was significant 
for a vitamin B12 deficiency and atrophic gastritis for 
which she received monthly B12 injections.",Her past medical history was significant for a vitamin B12 deficiency and atrophic gastritis for which she received monthly B12 injections.,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json
92,3,age_description,67,1,support,10838,10976,"In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",manual_answer:use_67,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,age_onset,67,1,model_candidate,10838,10976,"In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,first_manifestation,multiple,1,model_candidate,10838,10976,"In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,first_manifestation_multiple,confusion;stiffness;myoclonus;numbness,1,model_candidate,10838,10976,"In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_onset,distal_LE,1,model_candidate,10838,10976,"In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_onset,distal_LE,2,model_candidate,7601,7822,"Over the next 6 weeks the patient’s my- 
oclonus and rigidity worsened and spread proximally to 
involve the abdominal and thoracic muscles including the 
diaphragm, to the point where respiratory difficulty devel- 
oped.","Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_symptoms_onset,hyperreflexia;polyneuropathy,1,model_candidate,10977,11043,"Examination showed increased tone and 
hyperreflexia in both legs.",Examination showed increased tone and hyperreflexia in both legs.,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,timecourse_onset,insidious,1,model_candidate,10838,10976,"In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,timecourse_onset,insidious,2,model_candidate,7601,7822,"Over the next 6 weeks the patient’s my- 
oclonus and rigidity worsened and spread proximally to 
involve the abdominal and thoracic muscles including the 
diaphragm, to the point where respiratory difficulty devel- 
oped.","Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,timecourse_subsequent,chronic_stable,1,model_candidate,8403,8622,"As of November 1994 he remained 
unable to walk because of severe, fixed flexion rigidity of 
both legs. Numbness and dysesthesias of the legs persisted 
and mild weakness and hyperreflexia of the left arm devel- 
oped.","As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs. Numbness and dysesthesias of the legs persisted and mild weakness and hyperreflexia of the left arm devel- oped.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,onset_to_established,1.3,1,model_candidate,10838,10976,"In September 1993, a 67-year-old man developed confusion, 
symmetrical stiffness and myoclonus of both legs, and numb- 
ness of both feet.","In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numb- ness of both feet.",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,onset_to_established,1.3,2,model_candidate,8403,8507,"As of November 1994 he remained 
unable to walk because of severe, fixed flexion rigidity of 
both legs.","As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_established,multiple,1,model_candidate,7601,7822,"Over the next 6 weeks the patient’s my- 
oclonus and rigidity worsened and spread proximally to 
involve the abdominal and thoracic muscles including the 
diaphragm, to the point where respiratory difficulty devel- 
oped.","Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial;diaphragm,1,model_candidate,7601,7765,"Over the next 6 weeks the patient’s my- 
oclonus and rigidity worsened and spread proximally to 
involve the abdominal and thoracic muscles including the 
diaphragm",Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,stiffness_distribution_established_multiple,lumb_prox_LE;distal_LE;axial;diaphragm,2,model_candidate,8403,8507,"As of November 1994 he remained 
unable to walk because of severe, fixed flexion rigidity of 
both legs.","As of November 1994 he remained unable to walk because of severe, fixed flexion rigidity of both legs.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_symptoms_established,respiratory_insufficiency,1,model_candidate,7601,7822,"Over the next 6 weeks the patient’s my- 
oclonus and rigidity worsened and spread proximally to 
involve the abdominal and thoracic muscles including the 
diaphragm, to the point where respiratory difficulty devel- 
oped.","Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_status,amphiphysin,1,model_candidate,2603,2745,"The 3 
patients described here all had SCLC, PEM, and anti- 
bodies against human amphiphysin, though only I pa- 
tient had clinical rigidity.","The 3 patients described here all had SCLC, PEM, and anti- bodies against human amphiphysin, though only I pa- tient had clinical rigidity.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_tests,antineuronal,1,model_candidate,8208,8277,"Serum drawn in September showed antineuronal 
antibodies (see below).",Serum drawn in September showed antineuronal antibodies (see below).,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,antibody_testsystem,western_blot;tissue_assay,1,model_candidate,747,911,"On immunoblots of human neuronal extracts, each patient’s serum contained 
high-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd.","On immunoblots of human neuronal extracts, each patient’s serum contained high-titer IgG antibodies reacting with a protein band of apparent molecular mass 125 kd.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,CSF_status,inflammatory,1,model_candidate,7372,7480,"CSF analysis revealed a protein 
concentration of 80 mgidl, 30 mononuclear WBCslpl, and 
a normal IgG index.","CSF analysis revealed a protein concentration of 80 mgidl, 30 mononuclear WBCslpl, and a normal IgG index.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,CMUA,0,1,absence_context,10977,11043,"Examination showed increased tone and 
hyperreflexia in both legs.",Examination showed increased tone and hyperreflexia in both legs.,manual_term:Examination showed increased tone,exact,context_or_absence_only_not_direct_extraction,do_not_promote_as_standard_langextract_example,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,tu_screening,1,1,model_candidate,7920,7961,"Biopsy of a 
subcarinal mass showed SCLC.",Biopsy of a subcarinal mass showed SCLC.,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,tu_screening_abnormal,SCLC,1,model_candidate,7920,7961,"Biopsy of a 
subcarinal mass showed SCLC.",Biopsy of a subcarinal mass showed SCLC.,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy,IVIG;steroids,1,model_candidate,7963,8103,"The patient received a course of intravenous IgG, was be- 
gun on prednisone, and began monthly chemotherapy with 
cisplatin plus etoposide.","The patient received a course of intravenous IgG, was be- gun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy,IVIG;steroids,2,model_candidate,7963,8039,"The patient received a course of intravenous IgG, was be- 
gun on prednisone","The patient received a course of intravenous IgG, was be- gun on prednisone",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immuntherapy_detail,IVIG and prednisone,1,model_candidate,7963,8103,"The patient received a course of intravenous IgG, was be- 
gun on prednisone, and began monthly chemotherapy with 
cisplatin plus etoposide.","The patient received a course of intravenous IgG, was be- gun on prednisone, and began monthly chemotherapy with cisplatin plus etoposide.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immuntherapy_detail,IVIG and prednisone,2,model_candidate,7963,8039,"The patient received a course of intravenous IgG, was be- 
gun on prednisone","The patient received a course of intravenous IgG, was be- gun on prednisone",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy_effect,partial improvement,1,model_candidate,8104,8207,"Over the next month his mental

status returned to near baseline and the myoclonus gradually 
resolved.",Over the next month his mental status returned to near baseline and the myoclonus gradually resolved.,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,immunotherapy_effect,partial improvement,2,model_candidate,39962,40077,"Patient 3 in the 
present report partially improved with chemotherapy 
and immunotherapy, but still could not walk.","Patient 3 in the present report partially improved with chemotherapy and immunotherapy, but still could not walk.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,1,model_candidate,7481,7919,"The stiffness and myoclonus were par- 
tially ameliorated by combinations of oral valproate, diaze- 
pam, and baclofen. Over the next 6 weeks the patient’s my- 
oclonus and rigidity worsened and spread proximally to 
involve the abdominal and thoracic muscles including the 
diaphragm, to the point where respiratory difficulty devel- 
oped. He was maintained on pancuronium, ventilatory sup- 
port, and heavy sedation for nearly 2 weeks.","The stiffness and myoclonus were par- tially ameliorated by combinations of oral valproate, diaze- pam, and baclofen. Over the next 6 weeks the patient’s my- oclonus and rigidity worsened and spread proximally to involve the abdominal and thoracic muscles including the diaphragm, to the point where respiratory difficulty devel- oped. He was maintained on pancuronium, ventilatory sup- port, and heavy sedation for nearly 2 weeks.",model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,2,model_candidate,7481,7600,"The stiffness and myoclonus were par- 
tially ameliorated by combinations of oral valproate, diaze- 
pam, and baclofen.","The stiffness and myoclonus were par- tially ameliorated by combinations of oral valproate, diaze- pam, and baclofen.",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment,benzo;valproate;baclofen;pancuronium;ventilatory_support;sedation,3,model_candidate,7823,7919,"He was maintained on pancuronium, ventilatory sup- 
port, and heavy sedation for nearly 2 weeks.","He was maintained on pancuronium, ventilatory sup- port, and heavy sedation for nearly 2 weeks.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment_detail,"Initial: stiffness and myoclonus partially ameliorated by diazepam, valproate, baclofen. Established disease: Pancuronium, ventilatory support and sedation after development of respiratory distress (diaphragm stiffness)",1,model_candidate,7481,7600,"The stiffness and myoclonus were par- 
tially ameliorated by combinations of oral valproate, diaze- 
pam, and baclofen.","The stiffness and myoclonus were par- tially ameliorated by combinations of oral valproate, diaze- pam, and baclofen.",model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,sympt_treatment_detail,"Initial: stiffness and myoclonus partially ameliorated by diazepam, valproate, baclofen. Established disease: Pancuronium, ventilatory support and sedation after development of respiratory distress (diaphragm stiffness)",2,model_candidate,7823,7919,"He was maintained on pancuronium, ventilatory sup- 
port, and heavy sedation for nearly 2 weeks.","He was maintained on pancuronium, ventilatory sup- port, and heavy sedation for nearly 2 weeks.",model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_treatment,6 cycles of SCLC chemotherapy with cisplatin and etoposide,1,model_candidate,8045,8103,"began monthly chemotherapy with 
cisplatin plus etoposide.",began monthly chemotherapy with cisplatin plus etoposide.,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,other_treatment,6 cycles of SCLC chemotherapy with cisplatin and etoposide,2,model_candidate,8278,8328,"He received a total of six cycles of 
chemotherapy",He received a total of six cycles of chemotherapy,model_supporting_snippet_2,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,autoimmunity_specify,paraneoplastic polyneuropathy,1,model_candidate,130,242,Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients.,Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients.,model_supporting_snippet_2,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,notes,SPS and PNP in SCLC,1,model_candidate,415,484,"The third patient had seyere axial and limb rigidity and myoclo- 
nus",The third patient had seyere axial and limb rigidity and myoclo- nus,model_supporting_snippet_1,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
92,3,notes,SPS and PNP in SCLC,2,model_candidate,7920,7961,"Biopsy of a 
subcarinal mass showed SCLC.",Biopsy of a subcarinal mass showed SCLC.,model_supporting_snippet_3,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json
155,,age_description,51,1,model_candidate,0,16,51 year old man.,51 year old man.,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,sex,M,1,model_candidate,0,16,51 year old man.,51 year old man.,model_extraction_text,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,first_manifestation,multiple,1,model_candidate,79,129,prodome of rigidity and stiffness in axial muscles,prodome of rigidity and stiffness in axial muscles,model_extraction_text,exact,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,first_manifestation_multiple,stiffness,1,model_candidate,79,129,prodome of rigidity and stiffness in axial muscles,prodome of rigidity and stiffness in axial muscles,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,included_diagnosis,Stiff_Person,1,model_candidate,575,684,"One year after the
diagnosis of stiff-man syndrome the patient
had an overtly diabetic glucose tolerance test",One year after the diagnosis of stiff-man syndrome the patient had an overtly diabetic glucose tolerance test,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_review,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,diagnostic_criteria,Lorish et al.,1,model_candidate,17,71,He fulfilled all criteria established by Lorish et al’,He fulfilled all criteria established by Lorish et al’,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,stiffness_distribution_established,axial,1,model_candidate,79,129,prodome of rigidity and stiffness in axial muscles,prodome of rigidity and stiffness in axial muscles,model_extraction_text,exact,direct_exact_span_ready,candidate_for_promotion_after_spot_check,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json
155,,spasms_distribution_established,other,1,model_candidate,262,323,"superimposed spasms
precipitated by sudden movement and noise",superimposed spasms precipitated by sudden movement and noise,model_extraction_text,normalised_to_exact_source,covered_by_repaired_exact_source_text,candidate_after_span_revi

[truncated at 40000 characters]


## qa/validation/langextract_example_bootstrap/pilot_10/run_manifest.json
{
  "generated_at_utc": "2026-05-29T16:09:16.520781+00:00",
  "run_status": "completed",
  "model_id": "gemini-2.5-flash",
  "gemini_env_file": "env\\gemini.env",
  "dry_run": false,
  "allow_paid_run": true,
  "api_retries": 2,
  "api_retry_wait_seconds": 20.0,
  "selected_record_count": 10,
  "completed_record_count": 10,
  "field_review_row_count": 269,
  "selected_rows_path": "qa\\validation\\langextract_example_bootstrap\\pilot_10\\selected_rows.csv",
  "field_candidates_path": "qa\\validation\\langextract_example_bootstrap\\pilot_10\\field_candidates.jsonl",
  "field_review_path": "qa\\validation\\langextract_example_bootstrap\\pilot_10\\field_review.csv",
  "draft_examples_path": "",
  "failed_paper_id": "",
  "failure_type": "",
  "failure_message": ""
}

## qa/validation/langextract_example_bootstrap/pilot_10/selected_rows.csv
paper_id,case_id,target_view_json_path,field_count,text_sha256
75,,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json,21,975b32f4baa729380e11da71c858663930e4eab7c199452909fc21a7405a03c3
92,3,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json,27,7a4bb8079bc18b7b192d53104b9ab8b103b7a37db91a2c8f7e4767d8780406eb
155,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json,22,73bde3a90b5b8770c29a98f2ca37126055455567bf7c8d7bd80e0d2786be5c0b
162,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\162\p1.json,28,adeed3e1a715b23f3b8fd6ca418649e309eafa08455194bf578a2241083ce525
187,,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\187\p1.json,18,134dddf52c4d4a2d80caa008dbc147167088f3fee3c0f16210f82284dca2dbbc
197,,qa\validation\stage07_single_case_codex_gold\batch003\json\target_views\197\p1.json,33,b0fef0e3b090f85e811a1d153b584a80d94c54e7a0a0cd0f1d40c09eba1b6eff
395,,qa\validation\stage07_single_case_codex_gold\batch005\json\target_views\395\p1.json,28,b03c1cab86920b7c038c20b3c3ea360550b3d3797dd29b4be9c5d9cb6bfedb82
427,,qa\validation\stage07_single_case_codex_gold\batch006\json\target_views\427\p1.json,33,66c6959adec84231343c973ac615f109ba672c02764913a2e004962adeba93a2
439,,qa\validation\stage07_single_case_codex_gold\batch006\json\target_views\439\p1.json,28,93e45210f690590dcefa70813d31ff78e92c565ef1c96cde55fcaa3ac729c3c8
512,,qa\validation\stage07_single_case_codex_gold\batch008\json\target_views\512\p1.json,31,c911d1c192e8043de3402a72a79d5988fc0bc1885c66a77d5afd733574ad93fb


## qa/validation/langextract_example_bootstrap/pilot_10/span_plan_examples_manifest.json
{
  "generated_at_utc": "2026-05-29T17:12:57.428940+00:00",
  "span_plan_path": "qa\\validation\\langextract_example_bootstrap\\pilot_10\\gold_source_span_plan.csv",
  "examples_path": "examples\\langextract_bootstrap\\draft_langextract_examples_all_gold.json",
  "example_count": 77,
  "source_document_count": 10,
  "extraction_count": 432,
  "langextract_compatibility": {
    "example_count": 77,
    "extraction_count": 432,
    "alignment_issue_count": 0,
    "attribute_error_count": 0,
    "alignment_policy": {
      "enable_fuzzy_alignment": false,
      "accept_match_lesser": false
    },
    "alignment_issues": [],
    "attribute_errors": []
  },
  "field_row_count": 269,
  "support_span_count": 432,
  "coverage_error_count": 0,
  "coverage_errors": [],
  "coverage_quality_counts": {
    "context_or_absence_only_not_direct_extraction": 4,
    "covered_by_repaired_exact_source_text": 209,
    "derived_value_needs_coding_rule": 3,
    "direct_exact_span_ready": 45,
    "needs_human_adjudication": 8
  },
  "recommendation_counts": {
    "candidate_after_span_review": 209,
    "candidate_for_promotion_after_spot_check": 45,
    "do_not_promote_as_standard_langextract_example": 4,
    "review_before_promoting": 8,
    "review_before_promoting_derived_value": 3
  }
}

## resources/stage07_single_case_gold_json_index.csv
paper_id,manually_reviewed_MC,batch_id,manifest_json_path,stage07_paper_json_path,stage07_segments_json_path,stage07_target_view_json_path,stage07_validation_json_path,stage07_annotated_xml_path,stage06_json_source,stage06_candidate_json_path,stage06_count_evidence_json_path,stage06_result_json_path,stage06_gold_result_json_path,covidence_id,title,authors,source_category,source_subtype,preferred_text_json_path,preferred_text_source,count_eligible,likely_sps_case_count,count_confidence,count_basis,count_manual_review_required,count_original_cohort_provenance_uncertain,count_reason,count_version,heuristic_likely_sps_case_count,heuristic_count_confidence,heuristic_count_basis,heuristic_candidate_count,llm_likely_sps_case_count,llm_count_confidence,llm_selected_candidate_id,heuristic_fallback_used,count_audit_status,count_verification_status,count_validator_flags,counted_at_utc
22,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\22.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\22.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\22\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\22.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\22.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\22.json,22,Therapeutic trial of milacemide in patients with myoclonus and other intractable movement disorders.,"Gordon, M F; Diaz-Olivo, R; Hunt, A L; Fahn, S",interventional_study,controlled_or_therapeutic_group_study,data\extraction_json\text\22.json,full_text,true,1,high,manual_gold_review,false,false,"count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_02 | selection_bucket=count_ambiguity | prediction_correct=false | reviewed_count=1 | reviewed_source_category=interventional_study | predicted_count=10 | predicted_source_category=interventional_study | reviewer_notes=only one patient, case 10",gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:02:17.883920+00:00
29,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\29.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\29.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\29\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\29.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\29.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\29.json,29,Significant improvement of stiff-person syndrome after paraspinal injection of botulinum toxin A.,"Davis, D; Jabbari, B",single_case_report,case_report,data\extraction_json\text\29.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_01 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T12:44:02.861061+00:00
62,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\62.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\62.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\62\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\62.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\62.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\62.json,62,"Autoimmunity in stiff-Man syndrome with breast cancer is targeted to the C-terminal region of human amphiphysin, a protein similar to the yeast proteins, Rvs167 and Rvs161.","David, C; Solimena, M; De Camilli, P",single_case_report,case_report,data\extraction_json\text\62.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_02 | selection_bucket=count_ambiguity | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:03:22.411325+00:00
69,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\69.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\69.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\69\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\69.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\69.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\69.json,69,Stiff-man syndrome. Report of a case.,"Tarsy, D; Miyawaki, E K",single_case_report,case_report,data\extraction_json\text\69.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_02 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:05:15.152505+00:00
75,TRUE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\75.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\75.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\75\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\75.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\75.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\75.json,75,Stiff-man syndrome: case report.,"Kuhn, W F; Light, P J; Kuhn, S C",single_case_report,case_report,data/extraction_json/text/75.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=stage04_llm_category_2026-04-05_round_02 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T18:47:57.078704+00:00
85,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\85.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\85.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\85\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\85.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\85.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\85.json,85,Stiff-man syndrome: report of a case.,"Chang, Y J; Wu, C L; Lu, C S",single_case_report,case_report,data\extraction_json\text\85.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_02 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:06:17.685092+00:00
92,TRUE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\92.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\92.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\92\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\92.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\92.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\92.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\92.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\92.json,,92,Antiamphiphysin antibodies with small-cell lung carcinoma and paraneoplastic encephalomyelitis.,"Dropcho, E J",case_series_or_multi_case,case_series,data/extraction_json/text/92.json,full_text,true,1,high,manual_gold_review,false,false,"count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-18_stage06_b002_manual_review | selection_bucket=stage06_backfill_batch_review | prediction_correct=false | reviewed_count=1 | reviewed_source_category=case_series_or_multi_case | predicted_count=2 | predicted_source_category=case_series_or_multi_case | reviewer_notes=The paper reports 3 paraneoplastic encephalomyelitis patients, but only patient 3 is clearly tied to rigidity and the SPS-spectrum signal. The safest extractable SPS-spectrum count is therefore 1.",gold_reviewed_stage06_v1,2,medium,patient_label_count,2,2,low,,false,manual_gold_review,manual_gold_review,,2026-04-18T12:07:02Z
99,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\99.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\99.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\99\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\99.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\99.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\99.json,99,Improvement of stiff-man syndrome with vigabatrin.,"Vermeij, F H; van Doorn, P A; Busch, H F",single_case_report,case_report,data\extraction_json\text\99.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_03 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:53:13.076438+00:00
101,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\101.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\101.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\101\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\101.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\101.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\101.json,101,Progressive encephalomyelitis with rigidity responsive to plasmapheresis and immunosuppression.,"Fogan, L",single_case_report,case_report,data\extraction_json\text\101.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_03 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:53:23.528649+00:00
103,FALSE,batch000,qa\validation\stage07_single_case_codex_gold\batch000\manifest.json,qa\validation\stage07_single_case_codex_gold\batch000\json\papers\103.json,qa\validation\stage07_single_case_codex_gold\batch000\json\segments\103.segments.json,qa\validation\stage07_single_case_codex_gold\batch000\json\target_views\103\p1.json,qa\validation\stage07_single_case_codex_gold\batch000\json\validation\103.validation.json,qa\validation\stage07_single_case_codex_gold\batch000\xml\103.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\103.json,103,Electrophysiological evaluation of the stiff-man syndrome: further data.,"Martinelli, P; Nassetti, S; Minardi, C; Macri, S; Ippoliti, M",single_case_report,case_report,data\extraction_json\text\103.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_03 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:53:33.537635+00:00
106,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\106.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\106.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\106\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\106.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\106.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\106.json,106,"Subacute encephalomyelitis presenting as stiff-person syndrome: clinical, polygraphic, and pathologic correlations.","Armon, C; Swanson, J W; McLean, J M; Westbrook, P R; Okazaki, H; Kurtin, P J; Kalyan-Raman, U P; Rodriguez, M",single_case_report,case_report,data\extraction_json\text\106.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=2026-04-05_round_03 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T15:53:48.556596+00:00
110,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\110.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\110.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\110\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\110.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\110.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\110.json,110,Stiff-man syndrome: abnormal late responses upon transcranial magnetic stimulation.,"Schulte-Mattler, W J; Zierz, S",single_case_report,case_report,data/extraction_json/text/110.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=stage04_llm_category_2026-04-05_round_01 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T18:00:39.895306+00:00
112,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\112.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\112.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\112\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\112.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\112.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\112.json,112,Anti-gabaergic neuron autoantibodies in a patient with stiff-man syndrome and ataxia.,"Giometto, B; Miotto, D; Faresin, F; Argentiero, V; Scaravilli, T; Tavolato, B",single_case_report,case_report,data/extraction_json/text/112.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=stage04_llm_category_2026-04-05_round_01 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T18:01:00.463928+00:00
113,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\113.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\113.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\113\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\113.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\113.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\113.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\113.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\113.json,,113,Gastrointestinal involvement in neurologic disorders: Stiff-man and Charcot-Marie-Tooth syndromes.,"Soykan, I; McCallum, R W",single_case_report,case_report,data\extraction_json\text\113.json,full_text,true,1,high,diagnosis_specific_mixed_diagnosis_subgroup_count,false,false,"challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=high | llm_selected_candidate_id=cand01 | The paper reports two patients total, but they are mixed diagnoses: one with stiff-man syndrome and one with Charcot-Marie-Tooth syndrome. Only the stiff-man syndrome patient is within the SPS-spectrum, so the diagnosis-specific subgroup count of 1 is the best-supported extractable SPS-spectrum case count.",hybrid_v2_gpt-5.4,1,high,diagnosis_specific_mixed_diagnosis_subgroup_count,5,1,high,cand01,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:41:39.336825+00:00
115,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\115.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\115.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\115\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\115.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\115.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\115.json,115,Improvement of stiff-man syndrome with vigabatrin.,"Prevett, M C; Brown, P; Duncan, J S",single_case_report,case_report,data/extraction_json/text/115.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=stage04_llm_category_2026-04-05_round_02 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T18:48:05.640020+00:00
118,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\118.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\118.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\118\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\118.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\118.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\118.json,118,Stiff-persons' syndrome associated with thymoma and subsequent myasthenia gravis.,"Nicholas, A P; Chatterjee, A; Arnold, M M; Claussen, G C; Zorn, G L Jr; Oh, S J",single_case_report,case_report,data/extraction_json/text/118.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=stage04_llm_category_2026-04-05_round_02 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T18:48:15.907955+00:00
121,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\121.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\121.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\121\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\121.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\121.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\121.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\121.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\121.json,,121,Stiff-man syndrome associated with antecedent myasthenia gravis and organ-specific autoimmunopathy.,"Aso, Y; Sato, A; Narimatsu, M; Takiguchi, Y; Yamaguchi, Y; Inukai, T; Takemura, Y",single_case_report,case_report,data\extraction_json\text\121.json,full_text,true,1,high,case_report_marker_single_case,false,false,"challenge_stage=challenge | verification_status=llm_candidate_exact | llm_count_confidence=high | challenge_reasons=explicit_sps_subgroup_conflict=1 vs 5 | llm_selected_candidate_id=cand02 | This is a single-patient case report. The repeated phrase 'we describe a case' and 'the present case' clearly indicate one original SMS/SPS patient in this paper, whereas the '(5)' count refers to cited literature about prior SMS patients with GAD antibodies, not this paper's cohort.",hybrid_v2_gpt-5.4,5,high,diagnosis_specific_suffix_count,3,1,high,cand02,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:42:11.327427+00:00
126,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\126.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\126.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\126\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\126.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\126.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\126.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\126.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\126.json,,126,Stiff-man syndrome: possible autoimmune etiology targeted against GABA-ergic cells.,"Warich-Kirches, M; Von Bossanyi, P; Treuheit, T; Kirches, E; Dietzmann, K; Feistner, H; Wittig, H",single_case_report,case_report,data\extraction_json\text\126.json,full_text,true,1,high,single_case_text_signal,true,false,"challenge_stage=challenge | llm_semantic_conflict=COUNT_SPS_STATUS_UNCERTAIN | manual_review_gate=true | llm_count_confidence=high | challenge_reasons=semantic_validator_reject=COUNT_SPS_STATUS_UNCERTAIN | llm_selected_candidate_id=cand01 | validator_flags=COUNT_SPS_STATUS_UNCERTAIN | This is an original single-case report explicitly describing one female patient with stiff-man syndrome (older term for SPS). The additional controls and IDDM patients are comparator material, not SPS-spectrum cases, so the extractable SPS-spectrum count is 1.",hybrid_v2_gpt-5.4,1,medium,single_case_text_signal,3,1,high,cand01,false,hybrid_local_gpt,llm_semantic_conflict_manual_review_required,COUNT_SPS_STATUS_UNCERTAIN,2026-04-18T10:42:45.506429+00:00
127,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\127.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\127.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\127\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\127.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\127.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\127.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\127.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\127.json,,127,Sporadic Stiffman syndrome in a young girl.,"Udani, V P; Dharnidharka, V R; Gajendragadkar, A R; Udani, S V",single_case_report,case_report,data\extraction_json\text\127.json,full_text,true,1,high,source_single_case_default,false,false,"challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=high | llm_selected_candidate_id=cand01 | This single-case report describes one original pediatric patient with Stiffman syndrome/SPS, supported by clinical features, EMG findings, and treatment response. The literature counts mentioned are background only and do not add additional original cases from this paper.",hybrid_v2_gpt-5.4,1,medium,source_single_case_default,2,1,high,cand01,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:43:08.918107+00:00
150,FALSE,batch001,qa\validation\stage07_single_case_codex_gold\batch001\manifest.json,qa\validation\stage07_single_case_codex_gold\batch001\json\papers\150.json,qa\validation\stage07_single_case_codex_gold\batch001\json\segments\150.segments.json,qa\validation\stage07_single_case_codex_gold\batch001\json\target_views\150\p1.json,qa\validation\stage07_single_case_codex_gold\batch001\json\validation\150.validation.json,qa\validation\stage07_single_case_codex_gold\batch001\xml\150.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\150.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\150.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\150.json,,150,Stiff-man syndrome in a child.,"Garzo, C; Perez-Sotelo, M; Traba, A; Esteban, A; Grandas, F; Munoz-Blanco, J L",single_case_report,case_report,data\extraction_json\text\150.json,full_text,true,1,high,single_case_text_signal,false,false,"challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=high | llm_selected_candidate_id=cand01 | This is a single-case report and the text explicitly states, ""We report a 6-year-old child"" with clinical and electrophysiological findings consistent with stiff-man syndrome. The subsequent case report section describes one patient only, with no indication of additional original SPS-spectrum cases.",hybrid_v2_gpt-5.4,1,medium,single_case_text_signal,2,1,high,cand01,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:45:56.209929+00:00
155,TRUE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\155.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\155.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\155\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\validation\155.validation.json,qa\validation\stage07_single_case_codex_gold\batch002\xml\155.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\155.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\155.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\155.json,,155,Humoral and cellular immune parameters before and during immunosuppressive therapy of a patient with stiff-man syndrome and insulin dependent diabetes mellitus.,"Hummel, M; Durinovic-Bello, I; Bonifacio, E; Lampasona, V; Endl, J; Fessele, S; Then Bergh, F; Trenkwalder, C; Standl, E; Ziegler, A G",single_case_report,case_report,data\extraction_json\text\155.json,full_text,true,1,medium,source_single_case_override,true,true,"challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=medium | llm_selected_candidate_id=cand01 | The paper is a single-case report and repeatedly states that the immune findings were studied in 'a patient' with autoimmune stiff-man syndrome and IDDM, supporting 1 unique SPS-spectrum case. The apparent count of 2 arises from two autoantigens (GAD and IA-2), not two patients; however, provenance signals indicate some methods/samples were previously described, so manual review remains appropriate.",hybrid_v2_gpt-5.4,1,medium,source_single_case_override,4,1,medium,cand01,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:46:55.977203+00:00
162,TRUE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\162.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\162.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\162\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\validation\162.validation.json,qa\validation\stage07_single_case_codex_gold\batch002\xml\162.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\162.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\162.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\162.json,,162,Severe insulin resistance in a patient with type 1 diabetes and stiff-man syndrome treated with insulin lispro.,"Hirsch, I B; D'Alessio, D; Eng, L; Davis, C; Lernmark, A; Chait, A",single_case_report,case_report,data\extraction_json\text\162.json,full_text,true,1,high,diagnosis_specific_patient_case_count,false,false,challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=high | llm_selected_candidate_id=cand03 | This is a single-patient case report with explicit diagnosis-supported stiff-man syndrome/stiff person spectrum disorder in one individual. The paper repeatedly states that it describes one patient and confirms SMS with GAD65 antibodies in serum and CSF.,hybrid_v2_gpt-5.4,1,medium,case_report_marker_single_case,3,1,high,cand03,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:47:25.542339+00:00
167,FALSE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\167.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\167.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\167\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\validation\167.validation.json,qa\validation\stage07_single_case_codex_gold\batch002\xml\167.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\167.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\167.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\167.json,,167,Large motor neuron involvement in Stiff-man syndrome: a qualitative and quantitative study.,"Ishizawa, K; Komori, T; Okayama, K; Qin, X; Kaneko, K; Sasaki, S; Iwata, M",single_case_report,case_report,data\extraction_json\text\167.json,full_text,true,1,high,diagnosis_specific_table_row_count,false,false,"challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=high | llm_selected_candidate_id=cand01 | This single-case report describes one original patient with a diagnosis of stiff-man syndrome/stiff-person spectrum disorder, studied post mortem and compared against four controls. The diagnosis is explicitly supported by clinical features, EMG, anti-GAD elevation, and diazepam response, so the best-supported extractable SPS-spectrum count is 1.",hybrid_v2_gpt-5.4,1,high,diagnosis_specific_table_row_count,3,1,high,cand01,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:48:31.758604+00:00
173,FALSE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\173.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\173.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\173\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\validation\173.validation.json,qa\validation\stage07_single_case_codex_gold\batch002\xml\173.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\173.json,173,Immune-mediated retinopathy in a patient with stiff-man syndrome.,"Steffen, H; Menger, N; Richter, W; Nolle, B; Krastel, H; Stayer, C; Kolling, G H; Wassle, H; Meinck, H M",single_case_report,case_report,data/extraction_json/text/173.json,full_text,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=stage04_llm_category_2026-04-05_round_02 | selection_bucket=high_confidence_control | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T18:48:26.209606+00:00
182,FALSE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\182.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\182.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\182\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\validation\182.validation.json,qa\validation\stage07_single_case_codex_gold\batch002\xml\182.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\182.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\182.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\182.json,,182,Plasmapheresis and immunosuppression in stiff-man syndrome with type 1 diabetes: a 2-year study.,"Hao, W; Davis, C; Hirsch, I B; Eng, L J; Daniels, T; Walsh, D; Lernmark, A",single_case_report,case_report,data\extraction_json\text\182.json,full_text,true,1,high,source_single_case_default,false,false,"challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=high | llm_selected_candidate_id=cand01 | The paper explicitly states, 'we report a patient with both SMS and type 1 diabetes,' and the case description continues with a single 36-year-old woman. This supports counting 1 unique original SPS-spectrum patient, matching the single-case candidate.",hybrid_v2_gpt-5.4,1,medium,source_single_case_default,2,1,high,cand01,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:50:15.748176+00:00
185,FALSE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\185.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\185.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\185\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\validation\185.validation.json,qa\validation\stage07_single_case_codex_gold\batch002\xml\185.annotated.xml,stage06_count_runs,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\candidate_packages\185.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\count_evidence\185.json,results\stage06_count_runs\stage06_backfill_b002_n50_20260418\results\185.json,,185,Stiff-man syndrome with vacuolar degeneration of anterior horn motor neurons.,"Saiz, A; Minguez, A; Graus, F; Marin, C; Tolosa, E; Cruz-Sanchez, F",single_case_report,case_report,data\extraction_json\text\185.json,full_text,true,1,medium,source_single_case_default,true,true,"challenge_stage=primary | verification_status=llm_candidate_exact | llm_count_confidence=medium | llm_selected_candidate_id=cand01 | The paper explicitly describes a single original stiff-man syndrome patient ('we present a SMS patient' followed by an individual case narrative). This supports a count of 1 unique SPS-spectrum case, but manual review remains appropriate because the evidence pack flags original cohort provenance uncertainty.",hybrid_v2_gpt-5.4,1,medium,source_single_case_default,2,1,medium,cand01,false,hybrid_local_gpt,llm_candidate_exact,,2026-04-18T10:50:36.261961+00:00
187,TRUE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\187.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\187.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\187\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\validation\187.validation.json,qa\validation\stage07_single_case_codex_gold\batch002\xml\187.annotated.xml,stage06_count_gold,,,,qa\validation\source_categorisation\gold_standard\stage06_count_gold\papers\187.json,187,Long-term remission of refractory stiff-man syndrome after treatment with intravenous immunoglobulin.,"Khanlou, H; Eiger, G",single_case_report,case_report,data/extraction_json/text_trimmed/187.json,trimmed,true,1,high,manual_gold_review,false,false,count_basis=manual_gold_review | count_confidence=high | round_id=stage04_llm_category_2026-04-05_round_02 | selection_bucket=conference_edge | prediction_correct=true | reviewed_count=1 | reviewed_source_category=single_case_report | predicted_count=1 | predicted_source_category=single_case_report,gold_reviewed_stage06_v1,,,,,,,,,manual_gold_review,manual_gold_review,,2026-04-05T18:44:38.739991+00:00
189,FALSE,batch002,qa\validation\stage07_single_case_codex_gold\batch002\manifest.json,qa\validation\stage07_single_case_codex_gold\batch002\json\papers\189.json,qa\validation\stage07_single_case_codex_gold\batch002\json\segments\189.segments.json,qa\validation\stage07_single_case_codex_gold\batch002\json\target_views\189\p1.json,qa\validation\stage07_single_case_codex_gold\batch002\json\valida

[truncated at 40000 characters]


## tests/test_09_build_langextract_examples.py
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "09_build_langextract_examples.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage09_langextract_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestStage09LangExtractExampleBootstrap(unittest.TestCase):
    def write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_manual_fields_excludes_only_provenance_and_empty_values(self) -> None:
        module = load_module()
        row = {
            "extractor": "MC",
            "Reference": "75",
            "case_ID": "",
            "age_description": "39",
            "sex": "F",
            "empty_field": "",
        }

        self.assertEqual(
            module.manual_fields_from_row(row),
            {"age_description": "39", "sex": "F"},
        )

    def test_repo_path_keeps_absolute_paths_absolute(self) -> None:
        module = load_module()
        absolute_path = Path(module.REPO_ROOT).resolve() / "qa" / "validation" / "example.json"

        self.assertEqual(module.repo_path(str(absolute_path)), absolute_path)

    def test_retryable_gemini_error_recognises_temporary_demand_failure(self) -> None:
        module = load_module()

        self.assertTrue(
            module.retryable_gemini_error(
                RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
            )
        )
        self.assertFalse(module.retryable_gemini_error(RuntimeError("429 prepayment credits are depleted.")))

    def test_parse_args_defaults_to_openai_gpt_model(self) -> None:
        module = load_module()

        args = module.parse_args([])
        gemini_args = module.parse_args(["--provider", "gemini"])

        self.assertEqual(args.provider, "openai")
        self.assertEqual(args.model_id, module.DEFAULT_OPENAI_MODEL)
        self.assertEqual(gemini_args.model_id, module.DEFAULT_GEMINI_MODEL)

    def test_retryable_openai_error_excludes_billing_failures(self) -> None:
        module = load_module()

        self.assertTrue(module.retryable_openai_error(RuntimeError("rate limit exceeded")))
        self.assertFalse(module.retryable_openai_error(RuntimeError("insufficient_quota billing")))

    def test_select_pilot_records_joins_reviewed_index_to_manual_rows(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            target_json.write_text(
                json.dumps({"paper_id": "75", "input_text": "A 39-year-old woman presented with spasms."}),
                encoding="utf-8",
            )
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            index_path = root / "index.csv"
            manual_path = root / "manual.csv"
            self.write_csv(
                index_path,
                ["paper_id", "manually_reviewed_MC", "stage07_target_view_json_path"],
                [
                    {
                        "paper_id": "75",
                        "manually_reviewed_MC": "TRUE",
                        "stage07_target_view_json_path": target_rel,
                    },
                    {
                        "paper_id": "92",
                        "manually_reviewed_MC": "FALSE",
                        "stage07_target_view_json_path": "missing/stage07/92.json",
                    },
                ],
            )
            self.write_csv(
                manual_path,
                ["extractor", "Reference", "case_ID", "age_description", "sex"],
                [{"extractor": "MC", "Reference": "75", "case_ID": "", "age_description": "39", "sex": "F"}],
            )

            records = module.select_pilot_records(
                limit=10,
                explicit_ids=[],
                index_path=index_path,
                manual_path=manual_path,
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].paper_id, "75")
        self.assertEqual(records[0].case_id, "")
        self.assertEqual(records[0].manual_fields, {"age_description": "39", "sex": "F"})

    def test_select_pilot_records_can_exclude_previous_pilot_ids(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            stage07_dir = root / "stage07"
            stage07_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            manual_rows = []
            for paper_id in ("75", "524"):
                target_json = stage07_dir / f"{paper_id}.json"
                target_json.write_text(
                    json.dumps({"paper_id": paper_id, "input_text": f"Source text for {paper_id}."}),
                    encoding="utf-8",
                )
                target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
                rows.append(
                    {
                        "paper_id": paper_id,
                        "manually_reviewed_MC": "TRUE",
                        "stage07_target_view_json_path": target_rel,
                    }
                )
                manual_rows.append(
                    {
                        "extractor": "MC",
                        "Reference": paper_id,
                        "case_ID": "",
                        "age_description": "39",
                    }
                )
            index_path = root / "index.csv"
            manual_path = root / "manual.csv"
            self.write_csv(index_path, ["paper_id", "manually_reviewed_MC", "stage07_target_view_json_path"], rows)
            self.write_csv(manual_path, ["extractor", "Reference", "case_ID", "age_description"], manual_rows)

            records = module.select_pilot_records(
                limit=10,
                explicit_ids=[],
                excluded_ids=["75"],
                index_path=index_path,
                manual_path=manual_path,
            )

        self.assertEqual([record.paper_id for record in records], ["524"])

    def test_validate_case_output_rejects_missing_exact_quote(self) -> None:
        module = load_module()
        record = module.PilotRecord(
            paper_id="75",
            case_id="",
            target_view_json_path=Path("qa/validation/example.json"),
            source_text="A 39-year-old woman presented with spasms.",
            manual_fields={"age_description": "39"},
        )
        output = module.BootstrappedCaseExample(
            paper_id="75",
            case_id="",
            model_id="gemini-2.5-flash",
            field_groundings=[
                module.FieldGrounding(
                    field_name="age_description",
                    spreadsheet_value="39",
                    evidence_mode="exact_quote",
                    extraction_text="A 40-year-old woman",
                    supporting_snippets=[],
                    reasoning_short="Age phrase.",
                    supports_manual_value=True,
                )
            ],
        )

        rows = module.validate_case_output(record, output)

        self.assertEqual(rows[0]["validator_status"], "quote_not_found")

    def test_validate_case_output_flags_missing_field(self) -> None:
        module = load_module()
        record = module.PilotRecord(
            paper_id="75",
            case_id="",
            target_view_json_path=Path("qa/validation/example.json"),
            source_text="A 39-year-old woman presented with spasms.",
            manual_fields={"age_description": "39", "sex": "F"},
        )
        output = module.BootstrappedCaseExample(
            paper_id="75",
            case_id="",
            model_id="gemini-2.5-flash",
            field_groundings=[
                module.FieldGrounding(
                    field_name="age_description",
                    spreadsheet_value="39",
                    evidence_mode="exact_quote",
                    extraction_text="39-year-old",
                    supporting_snippets=[],
                    reasoning_short="Age phrase.",
                    supports_manual_value=True,
                )
            ],
        )

        rows = module.validate_case_output(record, output)

        self.assertIn("missing_from_model_output", {row["validator_status"] for row in rows})

    def test_promote_from_review_groups_accepted_rows_with_blank_case_id(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            target_json.write_text(
                json.dumps({"input_text": "A 39-year-old woman presented with spasms."}),
                encoding="utf-8",
            )
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            review_rows = [
                {
                    "paper_id": "75",
                    "case_id": "",
                    "field_name": "age_description",
                    "spreadsheet_value": "39",
                    "model_spreadsheet_value": "39",
                    "evidence_mode": "exact_quote",
                    "extraction_text": "39-year-old",
                    "char_start": "2",
                    "char_end": "13",
                    "supporting_snippets_json": "[]",
                    "supports_manual_value": "TRUE",
                    "reasoning_short": "Age phrase.",
                    "validator_status": "passed",
                    "review_status": "accepted",
                    "review_notes": "",
                    "target_view_json_path": target_rel,
                },
                {
                    "paper_id": "75",
                    "case_id": "",
                    "field_name": "sex",
                    "spreadsheet_value": "F",
                    "model_spreadsheet_value": "F",
                    "evidence_mode": "exact_quote",
                    "extraction_text": "woman",
                    "char_start": "17",
                    "char_end": "22",
                    "supporting_snippets_json": "[]",
                    "supports_manual_value": "TRUE",
                    "reasoning_short": "Sex phrase.",
                    "validator_status": "passed",
                    "review_status": "rejected",
                    "review_notes": "",
                    "target_view_json_path": target_rel,
                },
            ]

            examples = module.build_langextract_examples_from_review(review_rows)

        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["paper_id"], "75")
        self.assertEqual(examples[0]["case_id"], "")
        self.assertEqual(len(examples[0]["extractions"]), 1)
        self.assertEqual(examples[0]["extractions"][0]["extraction_class"], "age_description")

    def test_build_from_span_plan_preserves_all_gold_values_with_string_attributes(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            source_text = "A 39-year-old\nwoman presented with spasms."
            target_json.write_text(json.dumps({"input_text": source_text}), encoding="utf-8")
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            span_plan_rows = [
                {
                    "paper_id": "75",
                    "case_id": "",
                    "field_name": "age_description",
                    "spreadsheet_value": "39",
                    "model_spreadsheet_value": "39",
                    "original_evidence_mode": "exact_quote",
                    "original_validator_status": "passed",
                    "coverage_quality": "direct_exact_span_ready",
                    "langextract_recommendation": "candidate_for_promotion_after_spot_check",
                    "support_spans_json": json.dumps(
                        [
                            {
                                "span_text": "39-year-old\nwoman",
                                "char_start": 2,
                                "char_end": 19,
                                "span_role": "support",
                                "selection_source": "test",
                                "match_mode": "exact",
                            }
                        ]
                    ),
                    "target_view_json_path": target_rel,
                }
            ]

            validation = module.validate_span_plan_rows(span_plan_rows)
            examples = module.build_langextract_examples_from_span_plan(span_plan_rows)

        self.assertEqual(validation["coverage_error_count"], 0)
        self.assertEqual(len(examples), 1)
        self.assertEqual(len(examples[0]["extractions"]), 1)
        extraction = examples[0]["extractions"][0]
        self.assertEqual(extraction["extraction_class"], "age_description")
        self.assertNotIn("\n", examples[0]["text"])
        self.assertEqual(extraction["extraction_text"], "39-year-old woman")
        self.assertEqual(extraction["attributes"]["value"], "39")
        self.assertEqual(extraction["attributes"]["char_start"], "2")
        self.assertIsInstance(extraction["attributes"]["support_span_count"], str)

    def test_build_from_span_plan_splits_overlapping_spans_for_langextract_alignment(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            source_text = "A 39-year-old woman presented with spasms."
            target_json.write_text(json.dumps({"input_text": source_text}), encoding="utf-8")
            target_rel = str(target_json.resolve().relative_to(Path(module.REPO_ROOT).resolve()))
            shared_span = json.dumps(
                [
                    {
                        "span_text": "39-year-old",
                        "char_start": 2,
                        "char_end": 13,
                        "span_role": "support",
                        "selection_source": "test",
                        "match_mode": "exact",
                    }
                ]
            )
            base_row = {
                "paper_id": "75",
                "case_id": "",
                "model_spreadsheet_value": "",
                "original_evidence_mode": "exact_quote",
                "original_validator_status": "passed",
                "coverage_quality": "direct_exact_span_ready",
                "langextract_recommendation": "candidate_for_promotion_after_spot_check",
                "support_spans_json": shared_span,
                "target_view_json_path": target_rel,
            }
            span_plan_rows = [
                {**base_row, "field_name": "age_description", "spreadsheet_value": "39"},
                {**base_row, "field_name": "age_onset", "spreadsheet_value": "39"},
            ]

            examples = module.build_langextract_examples_from_span_plan(span_plan_rows)
            try:
                compatibility = module.validate_langextract_example_payload(examples)
            except SystemExit as exc:
                self.skipTest(str(exc))

        self.assertEqual(len(examples), 2)
        self.assertEqual(sum(len(example["extractions"]) for example in examples), 2)
        self.assertEqual(compatibility["alignment_issue_count"], 0)
        self.assertEqual(compatibility["attribute_error_count"], 0)

    def test_paid_gate_stops_before_gemini_import(self) -> None:
        module = load_module()
        record = module.PilotRecord(
            paper_id="75",
            case_id="",
            target_view_json_path=Path("qa/validation/example.json"),
            source_text="A 39-year-old woman presented with spasms.",
            manual_fields={"age_description": "39"},
        )

        with self.assertRaises(SystemExit):
            module.run_gemini_bootstrap(
                record,
                model_id="gemini-2.5-flash",
                allow_paid_run=False,
                env_file=Path("env/gemini.env"),
            )

    def test_paid_run_checkpoints_completed_records_before_later_failure(self) -> None:
        module = load_module()
        temp_base = Path(module.REPO_ROOT) / "pytest_workspace_tmp"
        temp_base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_base) as tmp_dir:
            root = Path(tmp_dir)
            target_json = root / "stage07" / "75.json"
            target_json.parent.mkdir(parents=True, exist_ok=True)
            target_json.write_text(
                json.dumps({"input_text": "A 39-year-old woman presented with spasms."}),
                encoding="utf-8",
            )
            records = [
                module.PilotRecord(
                    paper_id="75",
                    case_id="",
                    target_view_json_path=target_json,
                    source_text="A 39-year-old woman presented with spasms.",
                    manual_fields={"age_description": "39"},
                ),
                module.PilotRecord(
                    paper_id="92",
                    case_id="",
                    target_view_json_path=target_json,
                    source_text="A 39-year-old woman presented with spasms.",
                    manual_fields={"age_description": "39"},
                ),
            ]
            args = argparse.Namespace(
                output_dir=root / "out",
                provider="openai",
                model_id="gpt-5.5",
                gemini_env_file=Path("env/gemini.env"),
                openai_env_file=Path("env/openai_api_key.env"),
                openai_reasoning_effort="low",
                openai_max_output_tokens=8000,
                dry_run=False,
                allow_paid_run=True,
                api_retries=0,
                api_retry_wait_seconds=0.0,
            )
            calls = 0
            original = module.run_gemini_bootstrap_with_retries

            def fake_run(record, *, args):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("simulated later failure")
                return module.BootstrappedCaseExample(
                    paper_id=record.paper_id,
                    case_id=record.case_id,
                    model_id="gpt-5.5",
                    field_groundings=[
                        module.FieldGrounding(
                            field_name="age_description",
                            spreadsheet_value="39",
                            evidence_mode="exact_quote",
                            extraction_text="39-year-old",
                            supporting_snippets=[],
                            reasoning_short="Age phrase.",
                            supports_manual_value=True,
                        )
                    ],
                )

            module.run_gemini_bootstrap_with_retries = fake_run
            try:
                with self.assertRaises(RuntimeError):
                    module.write_paid_run_outputs(args, records)
            finally:
                module.run_gemini_bootstrap_with_retries = original

            candidate_lines = (args.output_dir / "field_candidates.jsonl").read_text(encoding="utf-8").splitlines()
            review_rows = module.read_csv_rows(args.output_dir / "field_review.csv")
            manifest = json.loads((args.output_dir / "run_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(len(candidate_lines), 1)
        self.assertEqual(len(review_rows), 1)
        self.assertEqual(manifest["run_status"], "failed")
        self.assertEqual(manifest["completed_record_count"], 1)
        self.assertEqual(manifest["failed_paper_id"], "92")


if __name__ == "__main__":
    unittest.main()
