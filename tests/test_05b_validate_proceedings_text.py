from __future__ import annotations

import tempfile
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "05b_validate_proceedings_text.py"


def load_module():
    pipeline_dir = SCRIPT_PATH.parent
    if str(pipeline_dir) not in sys.path:
        sys.path.insert(0, str(pipeline_dir))
    spec = importlib.util.spec_from_file_location("validate_proceedings_text", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestValidateProceedingsText(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_write_registry_preserve_existing_keeps_unprocessed_rows(self) -> None:
        registry_path = self.tmp_path / "proceedings_text_qc_registry.csv"
        existing_rows = [
            {"paper_id": "1001", "qc_status": "confirmed_full", "manual_follow_up_required": "false"},
            {"paper_id": "1002", "qc_status": "mismatch", "manual_follow_up_required": "true"},
        ]
        updated_rows = [
            {"paper_id": "1002", "qc_status": "confirmed_full", "manual_follow_up_required": "false"},
            {"paper_id": "1003", "qc_status": "partial_truncated", "manual_follow_up_required": "true"},
        ]

        self.module.write_registry(existing_rows, registry_path)
        self.module.write_registry(updated_rows, registry_path, preserve_existing=True)

        with registry_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(self.module.csv.DictReader(handle))
        self.assertEqual([row["paper_id"] for row in rows], ["1001", "1002", "1003"])
        self.assertEqual(rows[1]["qc_status"], "confirmed_full")

    def make_source_record(self) -> tuple[dict[str, object], list[str]]:
        lines = [
            "Previous abstract tail text that should not be part of the target source.",
            "A STIFF WOMAN",
            "Fnu Srinithya; Saikrishna Gadde. Example Hospital, Birmingham, AL",
            "BACKGROUND: A 37 year old woman developed progressive stiffness and painful spasms over several months with repeated falls and escalating disability.",
            "METHODS: The patient underwent extensive neurological, rheumatological, and paraneoplastic testing before the final antibody results clarified the diagnosis.",
            "RESULTS: Imaging and cerebrospinal fluid studies were unrevealing, but serum amphiphysin antibody testing and the oncological workup supported stiff person syndrome.",
            "DISCUSSION: This presentation highlights how broad the initial differential can be and why early recognition matters for both supportive care and malignancy screening.",
            "CONCLUSION: Immunotherapy, benzodiazepines, and rehabilitation improved mobility and pain control while the team pursued treatment of the associated malignancy.",
            "DISCLOSURE: Nothing to disclose.",
            "A STROKE OF LUCK",
            "Shruti Rao; Thomas Wong. Another Hospital, San Francisco, CA",
            "CASE: Another unrelated case begins here.",
        ]
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        return record, lines

    def make_trimmed_record(self, lines: list[str], start: int, end: int) -> dict[str, object]:
        return {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines[start:end]),
                }
            ],
            "start_line_global_index": start,
            "end_line_global_index_exclusive": end,
            "matched_block_code": "",
        }

    def test_validate_trimmed_segmentation_confirms_clean_uncoded_span(self) -> None:
        source_record, lines = self.make_source_record()
        trimmed_record = self.make_trimmed_record(lines, 1, 9)

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.95,
            author_score=0.50,
            combined_score=0.84,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertTrue(segmentation["span_located"])
        self.assertTrue(segmentation["start_boundary_ok"])
        self.assertFalse(segmentation["spillover"])
        self.assertFalse(segmentation["truncated_by_gap"])
        self.assertEqual(status, "confirmed_full")
        self.assertFalse(manual_follow_up)

    def test_validate_trimmed_segmentation_flags_spillover_into_next_header(self) -> None:
        source_record, lines = self.make_source_record()
        trimmed_record = self.make_trimmed_record(lines, 1, 11)

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.95,
            author_score=0.50,
            combined_score=0.84,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertTrue(segmentation["spillover"])
        self.assertEqual(status, "spillover_detected")
        self.assertTrue(manual_follow_up)

    def test_validate_trimmed_segmentation_flags_truncation_before_next_header(self) -> None:
        source_record, lines = self.make_source_record()
        trimmed_record = self.make_trimmed_record(lines, 1, 6)

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.95,
            author_score=0.50,
            combined_score=0.84,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertTrue(segmentation["truncated_by_gap"])
        self.assertGreaterEqual(segmentation["meaningful_tail_gap_count"], 2)
        self.assertEqual(status, "partial_truncated")
        self.assertTrue(manual_follow_up)

    def test_validate_trimmed_segmentation_ignores_disclosure_block_after_conclusion(self) -> None:
        lines = [
            "P601",
            "Spectrum of stiff person syndrome expands with presence of retinal pathology",
            "T. Shoemaker, A. Rothman, J. Prince, S. Saidha, P.A. Calabresi, S.D. Newsome",
            "Objective: To assess structural and functional changes in the afferent visual system of patients with SPS.",
            "Background: SPS is a rare neuroimmunological disorder that can be misdiagnosed because of overlapping symptoms and under-recognised visual complaints.",
            "Methods: Forty SPS patients and matched healthy controls underwent retinal testing with structural and functional visual assessments.",
            "Results: SPS patients exhibited lower visual acuity, thinner GCIP layer thickness, and consistent retinal changes after adjustment for age and diabetes history.",
            "Conclusions: Clinicians should be aware of the expanding spectrum of SPS to help prevent misdiagnosis as more common conditions like MS.",
            "Disclosure",
            "Thomas Shoemaker: nothing to disclose.",
            "Scott Newsome has served on scientific advisory boards for Biogen and Genzyme.",
            "P602",
            "Retinal ganglion cell layer thickness predicts disease activity in clinically isolated syndrome",
            "Another author line",
        ]
        source_record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        trimmed_record = self.make_trimmed_record(lines, 0, 8)
        trimmed_record["matched_block_code"] = "P601"

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.95,
            author_score=0.60,
            combined_score=0.86,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertFalse(segmentation["truncated_by_gap"])
        self.assertEqual(segmentation["meaningful_tail_gap_count"], 0)
        self.assertEqual(segmentation["next_header_rule"], "next_abstract_boundary")
        self.assertEqual(status, "confirmed_full")
        self.assertFalse(manual_follow_up)

    def test_validate_trimmed_segmentation_flags_preamble_before_real_title(self) -> None:
        lines = [
            "Earlier abstract closing line that should not be part of the target source.",
            "doi:10.1016/j.jns.2013.07.1574",
            "Abstract - WCN 2013",
            "No: 1465",
            "Topic: 7 - Neuromuscular disorders",
            "Stiff man syndrome associated with breast cancer about 2 cases",
            "L. Noutsa, P.C. Mbonda Chimi, M. Camara",
            "Dakar, Senegal",
            "Background: The stiff-man syndrome is one of the syndromes of neuromuscular hyperactivity.",
            "Observation: Two patients had axial stiffness and rigidity.",
            "Conclusion: The diagnosis requires a search for associated pathologies.",
            "doi:10.1016/j.jns.2013.07.1575",
            "Abstract - WCN 2013",
            "No: 1362",
            "Topic: 7 - Neuromuscular disorders",
            "Effect of carpal tunnel syndrome on ulnar nerve at wrist",
            "S. Kang, S.N. Yang",
        ]
        source_record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        trimmed_record = self.make_trimmed_record(lines, 1, 11)

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.90,
            author_score=0.60,
            combined_score=0.82,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertFalse(segmentation["start_boundary_ok"])
        self.assertTrue(segmentation["leading_spillover"])
        self.assertEqual(status, "spillover_detected")
        self.assertTrue(manual_follow_up)

    def test_validate_trimmed_segmentation_accepts_title_start_after_coded_boundary(self) -> None:
        lines = [
            "Level of Evidence: Level V",
            "Poster 237",
            "Bilateral Hip Fracture During Hospitalization for",
            "Spasm Exacerbation in an Adult with Stiff Person",
            "Syndrome: A Case Report",
            "Tomasz K. Podobinski, DO, Paolo C. Mimbella, MD",
            "Case/Program Description: The patient developed progressive painful spasms and bilateral hip fractures during a hospital admission.",
            "Setting: Tertiary care hospital.",
            "Results: Symptoms continued to interfere with rehabilitation participation.",
            "Discussion: This is the first reported case, to our knowledge, of bilateral hip fractures in a female with stiff person syndrome related spasms.",
            "Conclusions: Refractory spasms may contribute to significant forces exerted on bony elements leading to fractures.",
            "Level of Evidence: Level V",
            "Poster 238",
            "Tumefactive Demyelinating Lesions",
            "Another Author, MD",
            "Case/Program Description: Another unrelated case begins here.",
        ]
        source_record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        trimmed_record = self.make_trimmed_record(lines, 2, 11)

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.92,
            author_score=0.60,
            combined_score=0.84,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertTrue(segmentation["start_boundary_ok"])
        self.assertEqual(segmentation["start_boundary_rule"], "after_coded_boundary")
        self.assertFalse(segmentation["spillover"])
        self.assertEqual(status, "confirmed_full")
        self.assertFalse(manual_follow_up)

    def test_validate_trimmed_segmentation_accepts_title_start_after_coded_boundary_with_date_preamble(self) -> None:
        lines = [
            "042",
            "3rd January 2018",
            "Hypokinesia, Brainstem Involvement, Rigidity and",
            "Exaggerated Startle in a Child with Glycine",
            "Receptors Antibodies",
            "SA M I N1, B HAMEED 1, MO . EB A B I K E R1",
            "1University Hospitals Bristol",
            "Background: We report a video presentation of a previously well 7-year-old boy with worsening rigidity and exaggerated startle.",
            "Results: Steroids were subsequently introduced with a marked clinical improvement.",
            "Conclusions: PERM should be considered in the differential diagnosis in any child presenting with similar symptoms.",
            "043",
            "3rd January 2018",
            "Another abstract title",
            "Another author line",
        ]
        source_record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        trimmed_record = self.make_trimmed_record(lines, 2, 10)

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.92,
            author_score=0.35,
            combined_score=0.78,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertTrue(segmentation["start_boundary_ok"])
        self.assertEqual(segmentation["start_boundary_rule"], "after_coded_boundary_preamble")
        self.assertFalse(segmentation["spillover"])
        self.assertEqual(status, "confirmed_full")
        self.assertFalse(manual_follow_up)

    def test_page_matches_uses_header_slice_for_identity_scoring(self) -> None:
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "126",
                            "Double trouble: opisthotonos associated with",
                            "Guillain-Barr/C19e Syndrome and GAD autoantibody",
                            "A. Alwis, D. Ram, G. Vassallo",
                            "Introduction: Guillain-Barr/C19e Syndrome is typified by weakness, areflexia, and elevated CSF protein.",
                            "Case: We present a unique case with severe pain, opisthotonos, and positive anti-glutamic acid decarboxylase antibodies.",
                            "Discussion: An additional diagnosis should be considered when opisthotonos is present.",
                            "Conclusion: Anti-GAD antibody levels should be measured in this instance.",
                        ]
                    ),
                }
            ]
        }

        page_index, title_score, author_score, combined_score, _ = self.module.page_matches(
            record=record,
            reference_title="Double trouble: Opisthotonos associated with guillain-barre Syndrome and GAD autoantibody",
            reference_authors="Alwis A.; Ram D.; Vassallo G.",
        )

        self.assertEqual(page_index, 0)
        self.assertGreaterEqual(title_score, 0.60)
        self.assertGreaterEqual(author_score, 0.66)
        self.assertGreaterEqual(combined_score, 0.62)

    def test_page_matches_handles_mojibake_title_windows(self) -> None:
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "0028 Sti ï¬€-Limb Syndrome: Thinking about that!",
                            "A. Delorme, D.E. Pencu, G. De Saint-Hubert",
                            "Introduction: Stiff-limb syndrome can masquerade as orthopaedic or functional disease.",
                            "Case report: We describe a patient whose diagnosis was delayed by the unusual focal presentation.",
                            "Conclusion: Immune-mediated stiffness syndromes should remain in the differential diagnosis.",
                        ]
                    ),
                }
            ]
        }

        page_index, title_score, author_score, combined_score, _ = self.module.page_matches(
            record=record,
            reference_title="Stiff-limb syndrome: Thinking about that!",
            reference_authors="Delorme A.; Pencu D.E.; De Saint-Hubert G.",
        )

        self.assertEqual(page_index, 0)
        self.assertGreaterEqual(title_score, 0.85)
        self.assertGreaterEqual(author_score, 0.60)
        self.assertGreaterEqual(combined_score, 0.78)

    def test_validate_trimmed_segmentation_accepts_dotted_code_boundary(self) -> None:
        lines = [
            "P.026 Acute lower limb spasticity: Stiff person syndrome responsive to immunomodulatory therapy in an adolescent female",
            "R. Ogilvie, H. Kolski",
            "Background: Progressive lower-limb spasticity can obscure the diagnosis of SPS in younger patients.",
            "Methods: The patient underwent MRI, electrophysiology, cerebrospinal fluid analysis, and autoimmune testing over several admissions before the diagnosis was settled.",
            "Results: Immunomodulatory therapy improved mobility and painful spasms while allowing rehabilitation participation to resume over the following weeks.",
            "Conclusion: Early recognition can prevent unnecessary delay in treatment and reduce the risk of avoidable disability in adolescent presentations of SPS.",
            "P.027 Another abstract title",
            "Another author line",
        ]
        source_record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        trimmed_record = self.make_trimmed_record(lines, 0, 6)
        trimmed_record["matched_block_code"] = "P.026"

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.95,
            author_score=0.70,
            combined_score=0.89,
            section_hits=3,
            body_chars=320,
            header_only=False,
            segmentation=segmentation,
        )

        self.assertTrue(segmentation["start_boundary_ok"])
        self.assertEqual(segmentation["start_boundary_rule"], "coded_boundary")
        self.assertEqual(status, "confirmed_full")
        self.assertFalse(manual_follow_up)

    def test_validate_trimmed_segmentation_ignores_conference_footer_gap(self) -> None:
        lines = [
            "E-P10.05A A rare person with Stiff Person syndrome",
            "R. Suciu, D. Stoicanescu, M. Cevei, F. Bodog",
            "Background: Stiff Person syndrome is a very rare and severe neuromuscular condition.",
            "Case report: The patient had longstanding gait difficulty, painful spasms, impaired balance, and repeated functional decline requiring multidisciplinary rehabilitation.",
            "Conclusion: Medical rehabilitation targets to reduce spasticity, pain, improve gait and stability while supportive pharmacological treatment controls symptoms.",
            "Abstracts from the 50 th European Society of Human Genetics Conference:. . . 949",
            "E-P10.06 Another abstract title",
            "Another author line",
        ]
        source_record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        trimmed_record = self.make_trimmed_record(lines, 0, 5)
        trimmed_record["matched_block_code"] = "E-P10.05A"

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.94,
            author_score=0.70,
            combined_score=0.88,
            section_hits=3,
            body_chars=320,
            header_only=False,
            segmentation=segmentation,
        )

        self.assertFalse(segmentation["spillover"])
        self.assertFalse(segmentation["truncated_by_gap"])
        self.assertEqual(segmentation["meaningful_tail_gap_count"], 0)
        self.assertEqual(status, "confirmed_full")
        self.assertFalse(manual_follow_up)

    def test_validate_trimmed_segmentation_flags_spillover_into_id_prefixed_header(self) -> None:
        lines = [
            "doi:10.1016/j.clinph.2015.11.204",
            "ID 140 – Left-side asymmetry in cortical and spinal inhibitory",
            "circuits in stiff-person syndrome: A case report—V. Bocek,",
            "B. Cvickova, T. Peisker, I. Stetkarova",
            "Objective: Stiff-person syndrome is an autoimmune disease.",
            "Conclusion: Loss of GABA-ergic inhibition corresponded to clinical status.",
            "Supported by PRVOUK P34, IGA-NT 13693, 12282.",
            "doi:10.1016/j.clinph.2015.11.205",
            "ID 159 – Madelung’s disease. A case report—N. Ausín Morales",
            "Objective: Madelung’s disease is characterised by fat accumulation.",
        ]
        source_record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(lines),
                }
            ]
        }
        trimmed_record = self.make_trimmed_record(lines, 1, 9)

        segmentation = self.module.validate_trimmed_segmentation(source_record, trimmed_record)
        section_hits, body_chars, header_only = self.module.body_metrics(trimmed_record)
        status, manual_follow_up, _ = self.module.derive_qc_status(
            trimmed_present=True,
            title_score=0.90,
            author_score=0.60,
            combined_score=0.82,
            section_hits=section_hits,
            body_chars=body_chars,
            header_only=header_only,
            segmentation=segmentation,
        )

        self.assertTrue(segmentation["spillover"])
        self.assertEqual(segmentation["next_header_rule"], "next_abstract_boundary")
        self.assertEqual(status, "spillover_detected")
        self.assertTrue(manual_follow_up)

    def test_collect_candidate_ids_ignores_stale_trim_row_when_manual_override_is_not_proceedings(self) -> None:
        (self.tmp_path / "1391.json").write_text("{}", encoding="utf-8")

        candidate_ids = self.module.collect_candidate_ids(
            text_dir=self.tmp_path,
            trim_registry_rows={
                "1391": {
                    "paper_id": "1391",
                    "proceedings_detected": "true",
                }
            },
            heuristic_rows={
                "1391": {
                    "paper_id": "1391",
                    "source_category": "conference_abstract",
                    "source_subtype": "case_series_conference_abstract",
                }
            },
            manual_rows={
                "1391": {
                    "paper_id": "1391",
                    "final_source_category": "case_series_or_multi_case",
                    "final_source_subtype": "small_case_series",
                }
            },
            paper_ids=["1391"],
            limit=0,
        )

        self.assertEqual(candidate_ids, [])


if __name__ == "__main__":
    unittest.main()
