from __future__ import annotations

import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
PROMPT_EXAMPLES_DIR = REPO_ROOT / "config" / "prompts" / "examples"
CASE_REPORT_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Case_Report_Form.csv"
CASE_SERIES_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Case_Series_Reports.csv"
COHORTS_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Cohorts.csv"
OBS_COHORT_SHEET = EXAMPLES_DIR / "datasheet_examples_MC_Observ_Cohort_Cross_sect.csv"
INDIVIDUAL_OUT = PROMPT_EXAMPLES_DIR / "02_individual_examples.json"
GROUP_OUT = PROMPT_EXAMPLES_DIR / "02_group_examples.json"
PUBLICATION_TYPE_OUT = PROMPT_EXAMPLES_DIR / "03_publication_type_examples.json"


def dedupe_headers(headers: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    deduped: list[str] = []
    for header in headers:
        clean = header.strip()
        counts[clean] = counts.get(clean, 0) + 1
        deduped.append(clean if counts[clean] == 1 else f"{clean}__{counts[clean]}")
    return deduped


def load_case_report_rows(path: Path) -> set[tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        headers = dedupe_headers(next(reader))
        keys: set[tuple[str, str]] = set()
        for row_values in reader:
            if not row_values:
                continue
            row = {
                headers[index]: row_values[index] if index < len(row_values) else ""
                for index in range(len(headers))
            }
            reference_id = (row.get("Reference") or "").strip()
            case_id = (row.get("case_ID") or "").strip()
            if reference_id:
                keys.add((reference_id, case_id))
        return keys


def load_sheet_ids(path: Path, key: str) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {(row.get(key) or "").strip() for row in reader if (row.get(key) or "").strip()}


def validate_individual_sources(payload: list[dict[str, object]], case_rows: set[tuple[str, str]]) -> None:
    missing: list[str] = []
    for item in payload:
        paper_id = str(item.get("paper_id") or "").strip()
        case_id = str(item.get("case_id") or "").strip()
        if (paper_id, case_id) not in case_rows:
            missing.append(f"{paper_id}:{case_id or '<blank>'}")
    if missing:
        raise ValueError(f"Missing individual example rows in curated case-report sheet: {', '.join(missing)}")


def validate_sheet_sources(payload: list[dict[str, object]], valid_ids: set[str], label: str) -> None:
    missing = [
        str(item.get("paper_id") or "").strip()
        for item in payload
        if str(item.get("paper_id") or "").strip() not in valid_ids
    ]
    if missing:
        raise ValueError(f"Missing {label} example IDs in curated sheet: {', '.join(missing)}")


def write_json(path: Path, payload: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def individual_examples() -> list[dict[str, object]]:
    return [
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "12013",
            "case_id": "",
            "text": "A 43-year-old white woman developed insidious generalized stiffness at age 40. Painful generalized spasms, sensory symptoms, pain, and fatigue followed, and she was initially labelled as having Parkinson disease. Anti-GAD antibodies were detected. She was treated with IVIG together with benzodiazepines, gabapentin, and physiotherapy. The report did not state the treatment response.",
            "extractions": [
                {"extraction_class": "individual_presentation", "extraction_text": "insidious generalized stiffness, painful generalized spasms, sensory symptoms, pain, and fatigue"},
                {"extraction_class": "individual_diagnostics", "extraction_text": "she was initially labelled as having Parkinson disease. Anti-GAD antibodies were detected"},
                {"extraction_class": "individual_treatment", "extraction_text": "treated with IVIG together with benzodiazepines, gabapentin, and physiotherapy"},
                {"extraction_class": "individual_limitations", "extraction_text": "The report did not state the treatment response"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "2846",
            "case_id": "1",
            "text": "A 40-year-old woman presented with abdominal spasms and exaggerated startle and was initially thought to have complex partial seizures. Diagnostic criteria included axial muscle stiffness, painful spasms, EMG confirmation of continuous paraspinal muscle activity, and anti-GAD antibodies in blood or CSF. Her anti-GAD titre was greater than 30 IU/mL, and CSF testing was not done. She received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines, baclofen, and propofol for symptomatic control. She was reported as a responder.",
            "extractions": [
                {"extraction_class": "individual_presentation", "extraction_text": "abdominal spasms and exaggerated startle"},
                {"extraction_class": "individual_diagnostics", "extraction_text": "initially thought to have complex partial seizures; EMG confirmation of continuous paraspinal muscle activity; anti-GAD titre was greater than 30 IU/mL; CSF testing was not done"},
                {"extraction_class": "individual_treatment", "extraction_text": "received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines, baclofen, and propofol for symptomatic control"},
                {"extraction_class": "individual_outcome", "extraction_text": "She was reported as a responder"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "2846",
            "case_id": "2",
            "text": "A 57-year-old woman presented with spasms and startle and was initially considered to have cerebellar ataxia or spinocerebellar ataxia. Anti-GAD antibodies were present and CSF antibodies were also detected. She was treated with IVIG, plasma exchange, and autologous hematopoietic stem-cell transplantation, with benzodiazepines and baclofen as symptomatic treatment. She was reported as a partial responder.",
            "extractions": [
                {"extraction_class": "individual_presentation", "extraction_text": "spasms and startle"},
                {"extraction_class": "individual_diagnostics", "extraction_text": "initially considered to have cerebellar ataxia or spinocerebellar ataxia. Anti-GAD antibodies were present and CSF antibodies were also detected"},
                {"extraction_class": "individual_treatment", "extraction_text": "treated with IVIG, plasma exchange, and autologous hematopoietic stem-cell transplantation, with benzodiazepines and baclofen as symptomatic treatment"},
                {"extraction_class": "individual_outcome", "extraction_text": "She was reported as a partial responder"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "2846",
            "case_id": "3",
            "text": "A 27-year-old woman presented with spasms and startle and was initially diagnosed as CIDP/AAG. Anti-GAD antibodies were present, but CSF was normal. She received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines for symptom control. She had no reported response.",
            "extractions": [
                {"extraction_class": "individual_presentation", "extraction_text": "spasms and startle"},
                {"extraction_class": "individual_diagnostics", "extraction_text": "initially diagnosed as CIDP/AAG. Anti-GAD antibodies were present, but CSF was normal"},
                {"extraction_class": "individual_treatment", "extraction_text": "received IVIG and autologous hematopoietic stem-cell transplantation, with benzodiazepines for symptom control"},
                {"extraction_class": "individual_outcome", "extraction_text": "She had no reported response"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "2472",
            "case_id": "",
            "text": "A 25-year-old woman presented with gait difficulty, weakness, and pain, together with numbness, autonomic symptoms, hyperhidrosis, and tachycardia. She had generalized stiffness and spasms. Anti-GAD and amphiphysin antibodies were reported, with a GAD titre of 253 nmol/L. She was treated with IVIG, benzodiazepines, and baclofen, and she improved.",
            "extractions": [
                {"extraction_class": "individual_presentation", "extraction_text": "gait difficulty, weakness, pain, numbness, autonomic symptoms, hyperhidrosis, tachycardia, generalized stiffness, and spasms"},
                {"extraction_class": "individual_diagnostics", "extraction_text": "Anti-GAD and amphiphysin antibodies were reported, with a GAD titre of 253 nmol/L"},
                {"extraction_class": "individual_treatment", "extraction_text": "treated with IVIG, benzodiazepines, and baclofen"},
                {"extraction_class": "individual_outcome", "extraction_text": "she improved"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "552",
            "case_id": "",
            "text": "A 49-year-old man had multiple painful stiffness and spasm symptoms involving the upper and lower extremities. He was anti-GAD positive with a titre of 609 nmol/L. MRI was reported as normal. He received IVIG together with symptomatic therapy, and the paper noted that repeated IVIG infusions were required.",
            "extractions": [
                {"extraction_class": "individual_presentation", "extraction_text": "multiple painful stiffness and spasm symptoms involving the upper and lower extremities"},
                {"extraction_class": "individual_diagnostics", "extraction_text": "anti-GAD positive with a titre of 609 nmol/L. MRI was reported as normal"},
                {"extraction_class": "individual_treatment", "extraction_text": "received IVIG together with symptomatic therapy"},
                {"extraction_class": "individual_outcome", "extraction_text": "repeated IVIG infusions were required"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "11957",
            "case_id": "",
            "text": "A 46-year-old woman developed stiffness and spasms from age 40 onward. Anti-GAD antibodies were present, and breast cancer was diagnosed 6 years after syndrome onset. She was treated with azathioprine and diazepam, and had previously received monthly IVIG for 1.5 years. The case summary did not clearly state the later treatment response.",
            "extractions": [
                {"extraction_class": "individual_presentation", "extraction_text": "stiffness and spasms from age 40 onward"},
                {"extraction_class": "individual_diagnostics", "extraction_text": "Anti-GAD antibodies were present, and breast cancer was diagnosed 6 years after syndrome onset"},
                {"extraction_class": "individual_treatment", "extraction_text": "treated with azathioprine and diazepam, and had previously received monthly IVIG for 1.5 years"},
                {"extraction_class": "individual_limitations", "extraction_text": "The case summary did not clearly state the later treatment response"},
            ],
        },
    ]


def group_examples() -> list[dict[str, object]]:
    return [
        {
            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
            "paper_id": "3139",
            "text": "This retrospective cohort study from a single outpatient tertiary clinic evaluated 107 patients with stiff-person spectrum disorder within a broader GAD65 neurologic autoimmunity cohort. Median age was 46 years, range 5 to 76, and 25% were male. The majority had classical SPSD, while partial SPSD and exaggerated startle phenotypes were less common. Anti-GAD antibodies were present, median serum titre was 537 nmol/L, CSF anti-GAD antibodies were detected in tested cases, and CMUA and exteroceptive reflex abnormalities were reported. Treated patients received steroids, IVIG, plasma exchange, rituximab, or cyclophosphamide; 34 of 44 treated patients responded, including 24 partial and 10 near-complete responses, and 32 of 44 had sustained response at follow-up. The study was retrospective and further antibody testing was not always available.",
            "extractions": [
                {"extraction_class": "group_design", "extraction_text": "retrospective cohort study from a single outpatient tertiary clinic"},
                {"extraction_class": "group_characteristics", "extraction_text": "107 patients with stiff-person spectrum disorder; median age 46 years, range 5 to 76; 25% were male; the majority had classical SPSD, with partial SPSD and exaggerated startle phenotypes also represented"},
                {"extraction_class": "group_findings", "extraction_text": "Anti-GAD antibodies were present, median serum titre was 537 nmol/L, CSF anti-GAD antibodies were detected in tested cases, and CMUA and exteroceptive reflex abnormalities were reported"},
                {"extraction_class": "group_treatment_outcomes", "extraction_text": "34 of 44 treated patients responded, including 24 partial and 10 near-complete responses, and 32 of 44 had sustained response at follow-up"},
                {"extraction_class": "group_limitations", "extraction_text": "The study was retrospective and further antibody testing was not always available"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
            "paper_id": "233",
            "text": "This observational cohort study from Germany investigated the head retraction reflex in 50 patients with stiff-man syndrome, stiff-limb syndrome, or PERM. Mean age was 45.7 years and 45% were male. The cohort included 28 SMS cases, 2 SLS cases, and 20 PERM cases. Anti-GAD positivity was reported in 15 of 28 SMS cases, 2 of 2 SLS cases, and 15 of 20 PERM cases. The main study focus was the prevalence and electrophysiologic characteristics of the head retraction reflex. The study provided limited detail on symptoms, patient history, and treatment.",
            "extractions": [
                {"extraction_class": "group_design", "extraction_text": "observational cohort study"},
                {"extraction_class": "group_characteristics", "extraction_text": "50 patients; mean age 45.7 years; 45% were male; 28 SMS cases, 2 SLS cases, and 20 PERM cases"},
                {"extraction_class": "group_findings", "extraction_text": "Anti-GAD positivity was reported in 15 of 28 SMS cases, 2 of 2 SLS cases, and 15 of 20 PERM cases"},
                {"extraction_class": "group_limitations", "extraction_text": "The study provided limited detail on symptoms, patient history, and treatment"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
            "paper_id": "13224",
            "text": "This observational cohort study analysed 29 stiff-person syndrome cases within a broader screening program for GABAB receptor antibodies in neurologic syndromes associated with GAD antibodies. The study focused on antibody testing rather than detailed clinical phenotyping. All stiff-person syndrome cases were negative for GABAB receptor antibodies. The primary focus was not SPSD and the report provided little detail on SPSD characteristics.",
            "extractions": [
                {"extraction_class": "group_design", "extraction_text": "observational cohort study"},
                {"extraction_class": "group_characteristics", "extraction_text": "29 stiff-person syndrome cases within a broader screening program for GABAB receptor antibodies"},
                {"extraction_class": "group_findings", "extraction_text": "All stiff-person syndrome cases were negative for GABAB receptor antibodies"},
                {"extraction_class": "group_limitations", "extraction_text": "The primary focus was not SPSD and the report provided little detail on SPSD characteristics"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
            "paper_id": "6073",
            "text": "This retrospective cohort study from Japan screened 5 stiff-person syndrome patients for gephyrin antibodies. One patient had anti-gephyrin antibodies and mediastinal cancer, while 4 patients were gephyrin negative. The report provided very limited demographic, clinical, and treatment detail.",
            "extractions": [
                {"extraction_class": "group_design", "extraction_text": "retrospective cohort study"},
                {"extraction_class": "group_characteristics", "extraction_text": "5 stiff-person syndrome patients"},
                {"extraction_class": "group_findings", "extraction_text": "One patient had anti-gephyrin antibodies and mediastinal cancer, while 4 patients were gephyrin negative"},
                {"extraction_class": "group_limitations", "extraction_text": "The report provided very limited demographic, clinical, and treatment detail"},
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
            "paper_id": "899",
            "text": "This retrospective cohort study described 9 stiff-person syndrome cases from Tanzania. Mean age at onset was 36.7 years and 77.8% were male. The cohort included juvenile onset disease, stiff-limb syndrome, an anti-GAD positive case with later breast carcinoma, and patients with femoral fractures caused by spasms. Lumbar hyperlordosis, opisthotonus, abdominal rigidity, spasms, and hyperreflexia were common. Treatment included benzodiazepines and baclofen, and one anti-GAD positive patient improved markedly after IVIG. Laboratory confirmation was limited in this setting.",
            "extractions": [
                {"extraction_class": "group_design", "extraction_text": "retrospective cohort study"},
                {"extraction_class": "group_characteristics", "extraction_text": "9 stiff-person syndrome cases from Tanzania; mean age at onset was 36.7 years; 77.8% were male"},
                {"extraction_class": "group_findings", "extraction_text": "The cohort included juvenile onset disease, stiff-limb syndrome, an anti-GAD positive case with later breast carcinoma, and patients with femoral fractures caused by spasms. Lumbar hyperlordosis, opisthotonus, abdominal rigidity, spasms, and hyperreflexia were common"},
                {"extraction_class": "group_treatment_outcomes", "extraction_text": "Treatment included benzodiazepines and baclofen, and one anti-GAD positive patient improved markedly after IVIG"},
                {"extraction_class": "group_limitations", "extraction_text": "Laboratory confirmation was limited in this setting"},
            ],
        },
    ]


def publication_type_examples() -> list[dict[str, object]]:
    return [
        {
            "source_sheet": "datasheet_examples_MC_Case_Report_Form.csv",
            "paper_id": "12013",
            "text": "A single-patient clinical vignette described one woman with progressive stiffness, spasms, anti-GAD positivity, and treatment with IVIG and symptomatic therapy.",
            "extractions": [
                {"extraction_class": "publication_type", "extraction_text": "Case Series & Reports"}
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Series_Reports.csv",
            "paper_id": "1242",
            "text": "This conference abstract presented a small descriptive report of stiff-person syndrome cases with very limited clinical detail and no formal cohort design.",
            "extractions": [
                {"extraction_class": "publication_type", "extraction_text": "Case Series & Reports"}
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
            "paper_id": "3139",
            "text": "This retrospective cohort study reviewed 107 patients with stiff-person spectrum disorder and compared clinical manifestations, antibody findings, and immunotherapy responses.",
            "extractions": [
                {"extraction_class": "publication_type", "extraction_text": "Observ Cohort & Cross sect"}
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Cohorts.csv",
            "paper_id": "899",
            "text": "This retrospective cohort study described 9 stiff-person syndrome cases from Tanzania and reported prevalence and aggregate clinical features.",
            "extractions": [
                {"extraction_class": "publication_type", "extraction_text": "Observ Cohort & Cross sect"}
            ],
        },
        {
            "source_sheet": "datasheet_examples_MC_Case_Series_Reports.csv",
            "paper_id": "493",
            "text": "This small placebo-controlled levetiracetam trial compared intervention and placebo exposure in a stiff-person syndrome series.",
            "extractions": [
                {"extraction_class": "publication_type", "extraction_text": "Controlled Intervention Studies"}
            ],
        },
    ]


def main() -> None:
    case_rows = load_case_report_rows(CASE_REPORT_SHEET)
    case_series_ids = load_sheet_ids(CASE_SERIES_SHEET, "ID")
    cohort_ids = load_sheet_ids(COHORTS_SHEET, "ID")
    obs_ids = load_sheet_ids(OBS_COHORT_SHEET, "Study ID")

    individual_payload = individual_examples()
    group_payload = group_examples()
    publication_type_payload = publication_type_examples()

    validate_individual_sources(individual_payload, case_rows)
    validate_sheet_sources(group_payload, cohort_ids, "group")
    validate_sheet_sources(
        [item for item in publication_type_payload if item["source_sheet"] == "datasheet_examples_MC_Case_Series_Reports.csv"],
        case_series_ids,
        "publication-type case-series",
    )
    validate_sheet_sources(
        [item for item in publication_type_payload if item["source_sheet"] == "datasheet_examples_MC_Cohorts.csv"],
        cohort_ids,
        "publication-type cohort",
    )
    validate_sheet_sources(
        [item for item in publication_type_payload if item["source_sheet"] == "datasheet_examples_MC_Case_Report_Form.csv"],
        {paper_id for paper_id, _ in case_rows},
        "publication-type case-report",
    )
    if not obs_ids:
        raise ValueError("Observation cohort examples sheet could not be read.")

    write_json(INDIVIDUAL_OUT, individual_payload)
    write_json(GROUP_OUT, group_payload)
    write_json(PUBLICATION_TYPE_OUT, publication_type_payload)
    print(f"Wrote {len(individual_payload)} individual examples to {INDIVIDUAL_OUT}")
    print(f"Wrote {len(group_payload)} group examples to {GROUP_OUT}")
    print(f"Wrote {len(publication_type_payload)} publication-type examples to {PUBLICATION_TYPE_OUT}")


if __name__ == "__main__":
    main()
