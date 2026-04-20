from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from src.pipelines._sps_case_counting import estimate_sps_case_count


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_COUNT_SCRIPT = REPO_ROOT / "src" / "pipelines" / "06_extract_sps_case_counts.py"


def load_case_count_stage():
    spec = importlib.util.spec_from_file_location("case_count_stage_module", CASE_COUNT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestSpsCaseCounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stage_module = load_case_count_stage()

    def test_ignores_age_in_case_report_abstract(self) -> None:
        estimate = estimate_sps_case_count(
            title="Postoperative hypotonia in a patient with stiff person syndrome: a case report and literature review.",
            abstract=(
                "PURPOSE: Stiff person syndrome (SPS), an autoimmune disease that manifests with episodic muscle "
                "rigidity and spasms, has anesthetic considerations because postoperative hypotonia may occur. "
                "We present a patient with SPS who experienced hypotonia following total intravenous anesthesia. "
                "CLINICAL FEATURES: A 46-yr-old female patient with SPS underwent breast lumpectomy."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 1)

    def test_ignores_literature_case_totals_when_single_case_is_described(self) -> None:
        estimate = estimate_sps_case_count(
            title=(
                "The horses are the first thought but one must not forget the zebras even if they are rare: "
                "Stiff person syndrome associated with malignant mesothelioma."
            ),
            abstract=(
                "Stiff person syndrome (SPS) is a rare condition. SPS cases associated with breast cancer, "
                "small cell lung carcinoma, thymoma, Hodgkin's lymphoma and colorectal cancer have been reported "
                "in the literature. We present a case of a 58-year-old female patient who had malignant "
                "mesothelioma-associated SPS."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 1)

    def test_captures_participant_count_in_group_study_abstract(self) -> None:
        estimate = estimate_sps_case_count(
            title="Autologous Hematopoietic Stem Cell Transplantation for Stiff-Person Spectrum Disorder: A Clinical Trial.",
            abstract=(
                "OBJECTIVE: To test the hypothesis that autologous nonmyeloablative hematopoietic stem cell "
                "transplantation is safe and shows efficacy in the treatment of stiff-person spectrum disorder. "
                "METHODS: Twenty-three participants were treated in a prospective open-label cohort study of "
                "safety and efficacy."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 23)

    def test_ignores_scale_range_as_patient_count(self) -> None:
        estimate = estimate_sps_case_count(
            title="Levetiracetam in stiff-person syndrome.",
            abstract=(
                "We studied the effects of oral levetiracetam in three women with stiff-person syndrome in a "
                "single-blind, placebo-controlled study. The severity of symptoms was assessed by a rating scale "
                "of 0-4 and by the Patients Global Impressions Scale."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 3)

    def test_extracts_diagnosis_specific_single_case_from_mixed_disorder_trial(self) -> None:
        estimate = estimate_sps_case_count(
            title="Therapeutic trial of milacemide in patients with myoclonus and other intractable movement disorders.",
            abstract=(
                "We performed a therapeutic trial with the glycine precursor, milacemide, on 10 patients with "
                "intractable movement disorders. Six had myoclonus of various etiologies and one each had "
                "progressive supranuclear palsy, Filipino X-linked dystonia with parkinsonism, painful legs and "
                "moving toes, and stiff-person syndrome. No clear-cut observable improvement occurred."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 1)
        self.assertEqual(estimate.count_basis, "diagnosis_specific_list_count")

    def test_extracts_results_section_count_for_conference_abstract_children(self) -> None:
        estimate = estimate_sps_case_count(
            title="Paediatric neurological syndromes associated with glycine receptor antibodies",
            abstract="",
            early_body_text=(
                "Results: six girls with a mean age of 8 years were identified. "
                "The children presented with refractory focal seizures or cognitive behavioural changes."
            ),
        )
        self.assertEqual(estimate.likely_case_count, 6)
        self.assertEqual(estimate.count_basis, "early_body_count_signal")

    def test_ignores_title_only_count_when_title_is_not_sps_specific(self) -> None:
        estimate = estimate_sps_case_count(
            title="Neurological syndromes associated with glutamic acid decarboxylase antibodies in 121 patients",
            abstract=(
                "We characterised mixed neurological phenotypes including cerebellar ataxia, epilepsy, "
                "encephalitis, and occasional stiff-person syndrome."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 0)
        self.assertEqual(estimate.count_basis, "no_reliable_count_signal")

    def test_extracts_table_row_sps_subgroup_count(self) -> None:
        estimate = estimate_sps_case_count(
            title="Intravenous methylprednisolone or immunoglobulin for anti-GAD65 autoimmune encephalitis.",
            abstract="",
            early_body_text=(
                "Patient 1 Patient 2 Patient 3 Patient 4 Patient 5 Patient 6 "
                "Other symptoms CI CI, SPS*, CA, NBC CI CI, SPS* CI CI "
                "AEDS LEV, 1000 mg/day."
            ),
        )
        self.assertEqual(estimate.likely_case_count, 2)
        self.assertEqual(estimate.count_basis, "diagnosis_specific_table_row_count")

    def test_extracts_table_no_of_cases_sps_row(self) -> None:
        estimate = estimate_sps_case_count(
            title="The spectrum of antineuronal autoantibodies in a series of neurological patients.",
            abstract="",
            early_body_text=(
                "Table 1 Groups of patients No. of cases "
                "Patients with neurological disorder and systemic autoimmune disease "
                "Stiff-Person syndrome 18 Connective tissue diseases 38"
            ),
        )
        self.assertEqual(estimate.likely_case_count, 18)
        self.assertEqual(estimate.count_basis, "diagnosis_specific_table_row_count")

    def test_extracts_stiff_man_phenomena_table_row_count(self) -> None:
        estimate = estimate_sps_case_count(
            title="Glutamic acid decarboxylase autoimmunity with brainstem, extrapyramidal, and spinal cord dysfunction.",
            abstract="",
            early_body_text=(
                "TABLE 1. Neurological Manifestations in 62 Patients Seropositive for GAD65 Antibody "
                "No. (%) Level involved of patients Signs and symptoms Miscellaneous "
                "Extrapyramidal 10 (16) Axial or neck rigidity (8) "
                "Stiff-man phenomena 16 (26) Leg or arm spasms (14); stiff-man syndrome (2)"
            ),
        )
        self.assertEqual(estimate.likely_case_count, 16)
        self.assertEqual(estimate.count_basis, "diagnosis_specific_table_row_count")

    def test_ignores_literature_case_totals_in_single_patient_interventional_report(self) -> None:
        estimate = estimate_sps_case_count(
            title="Trialing of intrathecal baclofen therapy for refractory stiff-person syndrome.",
            abstract=(
                "OBJECTIVE: We report a patient with severe SPS refractory to oral standard therapies. "
                "CASE REPORT: A 48-year-old white man with SPS underwent successful continuous intrathecal "
                "catheter trial of baclofen. The literature reports only 5 cases of GAD(-) SPS patients treated "
                "with intrathecal baclofen therapy, and these resulted in poor long-term success."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 1)

    def test_ignores_protein_number_as_patient_count(self) -> None:
        estimate = estimate_sps_case_count(
            title=(
                "Glutamic acid decarboxylase autoantibodies in stiff-man syndrome and insulin-dependent diabetes "
                "mellitus exhibit similarities and differences in epitope recognition."
            ),
            abstract=(
                "Our results indicate that individuals with SMS have GAD Abs in 100- to 500-fold higher titer "
                "than individuals with IDDM. These two regions of the GAD 65 protein are similar to regions "
                "targeted by GAD 65-specific Abs found in individuals with IDDM."
            ),
            early_body_text="",
        )
        self.assertEqual(estimate.likely_case_count, 0)

    def test_stage_defaults_single_case_when_no_count_signal_exists(self) -> None:
        result = self.stage_module.build_case_count_record(
            reference_row={
                "Covidence": "9496",
                "Title": "Stiff-man syndrome in a child",
                "Authors": "Example, A",
                "Abstract": "",
            },
            text_record={"paper_id": "9496", "_path": "data/extraction_json/text/9496.json"},
            preferred_record={"pages": []},
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "9496.json",
            source_row={
                "source_category": "single_case_report",
                "source_subtype": "case_report",
            },
        )
        self.assertEqual(result["likely_sps_case_count"], "1")
        self.assertIn(result["count_basis"], {"source_single_case_default", "single_case_text_signal"})

    def test_stage_does_not_force_single_case_when_multi_case_is_explicit(self) -> None:
        result = self.stage_module.build_case_count_record(
            reference_row={
                "Covidence": "214",
                "Title": "Plasma exchange in stiff-man syndrome.",
                "Authors": "Example, C",
                "Abstract": (
                    "We report on the use of plasma exchange in 2 patients with stiff-man syndrome. "
                    "One patient showed minimal clinical improvement while the second reported subjective improvement."
                ),
            },
            text_record={"paper_id": "214", "_path": "data/extraction_json/text/214.json"},
            preferred_record={"pages": [{"text": "Case 1 ... Case 2 ..."}]},
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "214.json",
            source_row={
                "source_category": "case_series_or_multi_case",
                "source_subtype": "case_series",
            },
        )
        self.assertEqual(result["likely_sps_case_count"], "2")

    def test_stage_uses_early_body_single_case_signal_when_abstract_is_missing(self) -> None:
        result = self.stage_module.build_case_count_record(
            reference_row={
                "Covidence": "9086",
                "Title": "Stiff person syndrome - Therapeutic response to corticosteroids",
                "Authors": "Example, D",
                "Abstract": "",
            },
            text_record={"paper_id": "9086", "_path": "data/extraction_json/text/9086.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "This communication documents the clinical state of an individual with stiff person "
                            "syndrome. A 56 yrs housewife was referred for evaluation."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "9086.json",
            source_row={
                "source_category": "unclear_manual_review",
                "source_subtype": "unclear",
            },
        )
        self.assertEqual(result["likely_sps_case_count"], "1")

    def test_stage_ignores_untrimmed_proceedings_body_patient_labels_for_single_case(self) -> None:
        result = self.stage_module.build_case_count_record(
            reference_row={
                "Covidence": "6073",
                "Title": "Detection of gephyrin antibody in stiff-person syndrome",
                "Authors": "Example, B",
                "Abstract": "",
            },
            text_record={"paper_id": "6073", "_path": "data/extraction_json/text/6073.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Poster session. Patient 1 had unrelated symptoms. Patient 2 had unrelated symptoms. "
                            "Patient 3 had unrelated symptoms."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "6073.json",
            source_row={
                "source_category": "conference_abstract",
                "source_subtype": "single_case_conference_abstract",
            },
        )
        self.assertEqual(result["likely_sps_case_count"], "1")


if __name__ == "__main__":
    unittest.main()
