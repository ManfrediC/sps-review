from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "05_trim_proceedings_text.py"


def load_module():
    pipeline_dir = SCRIPT_PATH.parent
    if str(pipeline_dir) not in sys.path:
        sys.path.insert(0, str(pipeline_dir))
    spec = importlib.util.spec_from_file_location("trim_proceedings_text", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestTrimProceedingsRegistryWrites(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_row(self, paper_id: str, source_filename: str, trim_status: str) -> dict[str, str]:
        return {
            "paper_id": paper_id,
            "covidence_id": paper_id,
            "title": f"Title {paper_id}",
            "authors": f"Author {paper_id}",
            "source_filename": source_filename,
            "source_text_json_path": f"data\\extraction_json\\text\\{paper_id}.json",
            "trimmed_text_json_path": "",
            "n_pages": "1",
            "abstract_block_count": "0",
            "title_like_line_count": "0",
            "author_like_line_count": "0",
            "program_marker_count": "0",
            "proceedings_signal_score": "0",
            "proceedings_detected": "false",
            "index_detected": "false",
            "index_confidence": "",
            "index_listed_page": "",
            "index_prev_code": "",
            "index_next_code": "",
            "page_map_method": "",
            "estimated_offset": "",
            "offset_confidence": "",
            "fallback_triggered": "false",
            "trim_status": trim_status,
            "trim_reason": "",
            "trim_method": "",
            "trim_mode": "",
            "matched_block_code": "",
            "matched_block_title": "",
            "title_score": "",
            "author_score": "",
            "match_score": "",
            "start_rule": "",
            "end_rule": "",
            "body_signal_count": "",
            "spillover_flag": "false",
            "header_only_flag": "false",
            "candidate_rank": "",
            "start_page_index": "",
            "end_page_index": "",
            "start_line_global_index": "",
            "end_line_global_index_exclusive": "",
            "trimmed_at_utc": "",
        }

    def test_merge_registry_rows_replaces_matching_paper_id_only(self) -> None:
        existing_rows = [
            self.make_row("100", "100_old.pdf", "not_needed"),
            self.make_row("200", "200_keep.pdf", "trimmed_auto"),
        ]
        updated_rows = [self.make_row("100", "100_new.pdf", "header_only_source")]

        merged_rows = self.module.merge_registry_rows(existing_rows, updated_rows)

        self.assertEqual([row["paper_id"] for row in merged_rows], ["100", "200"])
        self.assertEqual(merged_rows[0]["source_filename"], "100_new.pdf")
        self.assertEqual(merged_rows[0]["trim_status"], "header_only_source")
        self.assertEqual(merged_rows[1]["source_filename"], "200_keep.pdf")

    def test_write_registry_preserve_existing_keeps_unprocessed_rows(self) -> None:
        registry_path = self.tmp_path / "text_trim_registry.csv"
        existing_rows = [
            self.make_row("100", "100_old.pdf", "not_needed"),
            self.make_row("200", "200_keep.pdf", "trimmed_auto"),
        ]
        updated_rows = [self.make_row("100", "100_new.pdf", "header_only_source")]

        self.module.write_registry(existing_rows, registry_path)
        self.module.write_registry(updated_rows, registry_path, preserve_existing=True)

        with registry_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual([row["paper_id"] for row in rows], ["100", "200"])
        self.assertEqual(rows[0]["source_filename"], "100_new.pdf")
        self.assertEqual(rows[1]["source_filename"], "200_keep.pdf")

    def test_extract_blocks_recognises_uncoded_uppercase_headers(self) -> None:
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Previous abstract closing line that should not start a new block.",
                            "A STIFF WOMAN",
                            "Fnu Srinithya; Saikrishna Gadde. Example Hospital, Birmingham, AL",
                            "CASE: A 37 year old woman developed progressive stiffness and painful spasms over several months.",
                            "She underwent an extensive workup and ultimately had amphiphysin antibody positivity.",
                            "CONCLUSION: Treatment improved mobility and symptom control after immunotherapy.",
                            "A STROKE OF LUCK",
                            "Shruti Rao; Thomas Wong. Another Hospital, San Francisco, CA",
                            "CASE: Another unrelated case begins here.",
                        ]
                    ),
                }
            ]
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        blocks = self.module.extract_blocks(lines, pattern)

        self.assertEqual(pattern.dominant_start_style, "uncoded_uppercase")
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].title_text, "A STIFF WOMAN")
        self.assertNotIn("A STROKE OF LUCK", " ".join(line.text for line in blocks[0].line_refs))

    def test_local_window_candidate_stops_at_next_uncoded_header(self) -> None:
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Earlier abstract tail text remains on the same page.",
                            "A STIFF WOMAN",
                            "Fnu Srinithya; Saikrishna Gadde. Example Hospital, Birmingham, AL",
                            "CASE: A 37 year old woman with progressive stiffness presented after months of worsening spasms.",
                            "Investigations were broad and eventually showed amphiphysin antibody positivity with malignancy concern.",
                            "Treatment with immunotherapy, benzodiazepines, and rehabilitation improved mobility and pain control.",
                            "CONCLUSION: Stiff person syndrome should prompt a broad paraneoplastic evaluation in this setting.",
                            "A STROKE OF LUCK",
                            "Shruti Rao; Thomas Wong. Another Hospital, San Francisco, CA",
                            "CASE: Another unrelated case begins here.",
                        ]
                    ),
                }
            ]
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="A stiff woman",
            reference_authors="Srinithya, F; Gadde, S",
            pattern=pattern,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertIn("A STIFF WOMAN", joined)
        self.assertNotIn("A STROKE OF LUCK", joined)
        self.assertIn(candidate.end_rule, {"next_soft_header", "no_header_found", "window_extent_cap", "page_span_cap"})

    def test_candidate_quality_marks_header_only_listing(self) -> None:
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "M206. Another Poster Title",
                            "Other Author, MD. Somewhere, USA.",
                            "M207. Stiff Person Syndrome in a Patient with Atypical",
                            "Carcinoid Tumor of the Lung Secondary to",
                            "Antiamphiphysin Antibodies: A Case Report and",
                            "Literature Review",
                            "Khawla Abusamra, MD, Mangayarkarasi Thandampallayam, MD.",
                            "University of Kentucky, Lexington, KY, USA.",
                            "M208. Subsequent Poster Title",
                            "Next Author, MD. Elsewhere, USA.",
                        ]
                    ),
                }
            ]
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Stiff Person Syndrome in a Patient with Atypical Carcinoid Tumor of the Lung Secondary to Antiamphiphysin Antibodies: A Case Report and Literature Review",
            reference_authors="Abusamra, K; Thandampallayam, M",
            pattern=pattern,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        status, _ = self.module.candidate_quality_status(candidate, "Abusamra, K; Thandampallayam, M")
        self.assertEqual(status, "header_only_source")

    def test_local_window_candidate_skips_preamble_and_keeps_full_uncoded_fragment(self) -> None:
        record = {
            "paper_id": "8317",
            "source_filename": "wcn_fragment.pdf",
            "n_pages": 2,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Early diagnosis is important not only for genetic counseling but also in",
                            "view of the timely treatment with allogenic HSCT.",
                            "doi:10.1016/j.jns.2013.07.1574",
                            "Abstract - WCN 2013",
                            "No: 1465",
                            "Topic: 7 - Neuromuscular disorders",
                            "Stiff man syndrome associated with breast cancer about 2 cases",
                            "L. Noutsa, P.C. Mbonda Chimi, M. Camara, Y. Fogang, K. Toure",
                            "Dakar, Senegal",
                            "Background: The stiff-man syndrome is one of the syndromes of neuromuscular hyperactivity.",
                            "Observation: Two patients aged 54 and 25 years had axial stiffness and rigidity.",
                            "Conclusion: The diagnosis requires a search for associated pathologies.",
                            "doi:10.1016/j.jns.2013.07.1575",
                            "Abstract - WCN 2013",
                            "No: 1362",
                            "Topic: 7 - Neuromuscular disorders",
                            "Effect of carpal tunnel syndrome on ulnar nerve at wrist",
                            "S. Kang, S.N. Yang",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Stiff man syndrome associated with breast cancer about 2 cases",
            reference_authors="Noutsa, L; Mbonda Chimi, P.C.; Camara, M",
            pattern=pattern,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.line_refs[0].text, "Stiff man syndrome associated with breast cancer about 2 cases")
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertNotIn("Early diagnosis is important", joined)
        self.assertNotIn("Effect of carpal tunnel syndrome", joined)
        self.assertIn("Conclusion: The diagnosis requires a search for associated pathologies.", joined)

    def test_local_window_candidate_keeps_conclusion_before_next_coded_header(self) -> None:
        record = {
            "paper_id": "1597",
            "source_filename": "o35_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "O-35 The Stiff Person Syndrome. Neurophysiological findings",
                            "Maria Concepcion Maeztu Sardina, Francisco A. Martinez Garcia",
                            "Murciano de Salud, Murcia, Spain",
                            "Background: Stiff Person Syndrome is an immune-mediated disorder.",
                            "Material and methods: We present a male patient with painful spasms.",
                            "Results: EMG showed continuous involuntary activity of normal motor units.",
                            "Conclusions: The neurophysiological studies play an important role in the differential diagnosis",
                            "of the diseases associated with excess motor unit activity, leading in this patient to the diagnosis",
                            "of encephalomyelitis with rigidity, variant of SPS.",
                            "doi:10.1016/j.clinph.2019.04.351",
                            "O-36 Listening the sound of neuromuscular junction during voluntary contraction",
                            "Sezin Alpaydin Baslo, Tugrul Artug",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="O-35 The Stiff Person Syndrome. Neurophysiological findings",
            reference_authors="Maeztu Sardina, M.C.; Martinez Garcia, F.A.",
            pattern=pattern,
            target_code="O-35",
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertIn("diagnosis of encephalomyelitis with rigidity, variant of SPS.", joined)
        self.assertNotIn("O-36 Listening the sound", joined)

    def test_is_abstract_start_ignores_b12_sentence_continuation(self) -> None:
        match = self.module.is_abstract_start(
            "B12 deficiency, and a family history of autoimmunity, presented with"
        )

        self.assertIsNone(match)

    def test_local_window_candidate_keeps_multipage_conclusion_after_b12_line(self) -> None:
        record = {
            "paper_id": "1418",
            "source_filename": "b12_false_header_fragment.pdf",
            "n_pages": 2,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "1316",
                            "Stiff-limb syndrome with cerebellar features and atypical EMG",
                            "findings responds to IVIG",
                            "S. Rametta, G. Robinson, N. Hellmers, N. Jacoby, H. Sarva (Brooklyn, NY, USA)",
                            "Objective: To describe a case of stiff-limb syndrome with ataxic features which had delayed EMG findings and improvement to IVIG.",
                            "Background: Stiff-person syndrome (SPS) is part of a spectrum of progressive autoimmune neurological diseases that also include isolated cerebellar ataxias.",
                            "Methods: Case report.",
                            "Results: A 52-year-old woman with history of pernicious anemia and",
                            "B12 deficiency, and a family history of autoimmunity, presented with",
                            "two months of axial ataxia, lower back pain, and unsteady gait.",
                            "She was hospitalised after a fall and found to have a low B12 level.",
                            "Medication trials with benzodiazepines, baclofen, pregabalin, dantrolene, and gabapentin were not effective.",
                            "IVIG was initiated with dramatic improvement in pain but no improvement in spasticity or gait until she completed 10 trials.",
                            "After her 12th consecutive dose of IVIG, she has considerable improvement in spasticity and gait and was able to return to work full time.",
                            "Conclusions: Our patient is unique as she had mild ataxia, no dystonia, and delayed unilateral positive EMG findings.",
                            "The exact duration of treatment is still unknown and further research into the long-term prognosis of SLS is needed.",
                            "1317",
                            "Ocular motor disorders among Filipino XDP patients",
                            "Another author line",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Stiff-limb syndrome with cerebellar features and atypical EMG findings responds to IVIG",
            reference_authors="Rametta, S.; Robinson, G.; Hellmers, N.; Jacoby, N.; Sarva, H.",
            pattern=pattern,
            target_code="1316",
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertIn("long-term prognosis of SLS is needed.", joined)
        self.assertNotIn("1317", joined)

    def test_extract_blocks_keeps_multipage_conclusion_across_proceedings_footer(self) -> None:
        record = {
            "paper_id": "1418",
            "source_filename": "footer_wrapped_fragment.pdf",
            "n_pages": 2,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "1316",
                            "Stiff-limb syndrome with cerebellar features and atypical EMG",
                            "findings responds to IVIG",
                            "S. Rametta, G. Robinson, N. Hellmers, N. Jacoby, H. Sarva (Brooklyn, NY, USA)",
                            "Objective: To describe a case of stiff-limb syndrome with ataxic features which had delayed EMG findings and improvement to IVIG.",
                            "Methods: Case report.",
                            "Results: Medication trials were not effective, but IVIG was initiated with dramatic improvement in pain.",
                            "Conclusions: Our patient is unique as she had mild ataxia, no dystonia, and delayed unilateral positive EMG findings.",
                            "The exact duration",
                            "S516 ABSTRACTS",
                            "Movement Disorders, Vol. 32, Suppl. 2, 2017",
                            "Downloaded from https://movementdisorders.onlinelibrary.wiley.com/doi/10.1002/mds.27087",
                        ]
                    ),
                },
                {
                    "page_index": 1,
                    "text": "\n".join(
                        [
                            "of treatment is still unknown and further research into the long-term",
                            "prognosis of SLS is needed.",
                            "1317",
                            "Ocular motor disorders among Filipino XDP patients",
                            "Another author line",
                        ]
                    ),
                },
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        blocks = self.module.extract_blocks(lines, pattern)
        chosen = self.module.best_matching_block(
            blocks=blocks,
            reference_title="Stiff-limb syndrome with cerebellar features and atypical EMG findings responds to IVIG",
            reference_authors="Rametta, S.; Robinson, G.; Hellmers, N.; Jacoby, N.; Sarva, H.",
        )

        self.assertTrue(self.module.is_footer_like("S516 ABSTRACTS"))
        self.assertTrue(self.module.is_footer_like("Movement Disorders, Vol. 32, Suppl. 2, 2017"))
        self.assertIsNotNone(chosen)
        assert chosen is not None
        joined = " ".join(line.text for line in chosen.line_refs)
        self.assertIn("long-term prognosis of SLS is needed.", joined)
        self.assertNotIn("1317", joined)

    def test_local_window_candidate_stops_before_id_prefixed_next_header(self) -> None:
        record = {
            "paper_id": "1257",
            "source_filename": "id_prefixed_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Earlier abstract tail text remains on the same page.",
                            "doi:10.1016/j.clinph.2015.11.204",
                            "ID 140 – Left-side asymmetry in cortical and spinal inhibitory",
                            "circuits in stiff-person syndrome: A case report—V. Bocek,",
                            "B. Cvickova, T. Peisker, I. Stetkarova (Department of Neurology,",
                            "Charles University, Third Faculty of Medicine, Charles University",
                            "Objective: Stiff-person syndrome (SPS) is an autoimmune disease characterized by progressive rigidity.",
                            "Methods: Fifty-one years old male with a two years history of stiffness and muscle spasms was investigated.",
                            "Conclusion: Our findings confirmed loss of GABA-ergic inhibition corresponding to clinical status.",
                            "Supported by PRVOUK P34, IGA-NT 13693, 12282.",
                            "doi:10.1016/j.clinph.2015.11.205",
                            "ID 159 – Madelung’s disease. A case report—N. Ausín Morales a, I. Lambarri San Martín a",
                            "Objective: Madelung’s disease or multiple symmetric lipomatosis is characterised by accumulation of fat.",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Left-side asymmetry in cortical and spinal inhibitory circuits in stiff-person syndrome: A case report",
            reference_authors="Bocek, V.; Cvickova, B.; Peisker, T.; Stetkarova, I.",
            pattern=pattern,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertIn("doi:10.1016/j.clinph.2015.11.205", joined)
        self.assertNotIn("ID 159", joined)
        self.assertEqual(candidate.end_rule, "next_abstract_boundary")

    def test_local_window_candidate_stops_before_spaced_code_next_header(self) -> None:
        record = {
            "paper_id": "1433",
            "source_filename": "spaced_code_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "CGR 7",
                            "EARLY EMPIRICAL TREATMENT OF ANTIBODY-NEGATIVE",
                            "AUTOIMMUNE/PARANEOPLASTIC ENCEPHALITIS WITH",
                            "IMMUNOSUPPRESSION",
                            "P Dai, M-W Lin, N Mahant, B Gao and D Brown",
                            "We report two cases of antibody-negative paraneoplastic/autoimmune encephalitis who were treated empirically with immunosuppression leading to clinical improvement.",
                            "Up to half of autoimmune/paraneoplastic encephalitis is antibody negative.",
                            "These two cases emphasise the importance of using the patients' clinical phenotype in guiding the early initiation of immunosuppression in autoimmune/paraneoplastic encephalitis.",
                            "CGR 8",
                            "A NOVEL CASE FEATURING AN IGE PARAPROTEIN ASSOCIATED",
                            "WITH FAMILIAL MEDITERRANEAN FEVER",
                            "Another author line",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Early empirical treatment of antibody-negative autoimmune/paraneoplastic encephalitis with immunosuppression",
            reference_authors="Dai, P.; Lin, M.-W.; Mahant, N.; Gao, B.; Brown, D.",
            pattern=pattern,
            target_code="CGR 7",
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertIn("early initiation of immunosuppression in autoimmune/paraneoplastic encephalitis.", joined)
        self.assertNotIn("CGR 8", joined)
        self.assertEqual(candidate.end_rule, "next_abstract_boundary")

    def test_extract_blocks_does_not_split_on_inline_reference_citation(self) -> None:
        record = {
            "paper_id": "1332",
            "source_filename": "citation_split_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Stiff face syndrome associated with glycine",
                            "receptor antibodies",
                            "J GADIAN, K LASCELLES, M LIM",
                            "Children’s Neurosciences Centre, St Thomas’ Hospital, London, UK",
                            "Objective: We present the case and videos of a boy with severe stimulus sensitive spasms.",
                            "Discussion: Stiff person syndrome is a spectrum of disorders characterised by spinal cord hyperexcitability.",
                            "spasms, myoclonus, autonomic dysfunction and hyperekplexia.",
                            "Its more severe variant, progressive encephalitis with rigidity",
                            "and myoclonus (PERM), is characterised by more widespread",
                            "features including brainstem involvement or sensory symptoms.",
                            "(Carvajal-Gonzalez et al., Brain, 2014;137(Pt 8):2178-92). The",
                            "detection of GlyR-Ab presents the possibility that PERM is amenable",
                            "to immunotherapy.",
                            "Conclusion: We present, to our knowledge, the first case of",
                            "stimulus sensitive spasms affecting primarily the face, and propose",
                            "that Stiff face syndrome is an important feature of this under-recognised and treatable syndrome.",
                            "Delineation of the movement disorder spectrum",
                            "A PAPANDREOU, RB SCHNEIDER",
                            "Great Ormond Street Hospital, London, UK",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        blocks = self.module.extract_blocks(lines, pattern)

        self.assertEqual(len(blocks), 2)
        joined = " ".join(line.text for line in blocks[0].line_refs)
        self.assertIn("under-recognised and treatable syndrome.", joined)
        self.assertNotIn("Delineation of the movement disorder spectrum", joined)

    def test_local_window_candidate_keeps_full_abstract_with_numbered_date_preamble(self) -> None:
        record = {
            "paper_id": "1333",
            "source_filename": "numbered_date_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "107 12th January 2017",
                            "Glycine antibody mediated progressive",
                            "encephalomyelitis with rigidity and myoclonus",
                            "(PERM): a paediatric presentation",
                            "DST KARIYAWASAM 1, D HILDEBRAND 2,",
                            "S JAYAWANT 1, JP PALACE 3, M I LEITE 4, S RAMDAS 1",
                            "1Paediatric Neurology, John Radcliffe Hospital, Oxford, UK",
                            "Objectives: We present a unique case of glycine receptor antibody mediated PERM.",
                            "Methods: Retrospective review of patient notes and relevant literature search.",
                            "Results: A 15 year-old boy with genetically confirmed APS1 presented with variable bilateral ptosis and diplopia.",
                            "Further review revealed decreased palatal and tongue movements, neck rigidity, dysarthria, and brisk reflexes.",
                            "Conclusions: (1) PERM associated with GlyR Abs has been well described, especially in adult population.",
                            "(2) As in adult cases, clinical presentations with eye signs may mimic ocular myasthenia.",
                            "(3) PERM may be added to the list of the autoimmune manifestations associated with APS1.",
                            "108 12th January 2017",
                            "Out of the loop? Information sharing with",
                            "healthcare professionals regarding outcomes of",
                            "suspected non-accidental head injury (NAHI)",
                            "NE YEO, W DOYLE, P MARSDEN, R ROBINSON",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Glycine antibody mediated progressive encephalomyelitis with rigidity and myoclonus (PERM): A paediatric presentation",
            reference_authors="Kariyawasam, D.S.T.; Hildebrand, D.; Jayawant, S.; Palace, J.; Leite, M.I.; Ramdas, S.",
            pattern=pattern,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertEqual(candidate.line_refs[0].text, "107 12th January 2017")
        self.assertIn("the autoimmune manifestations associated with APS1.", joined)
        self.assertNotIn("108 12th January 2017", joined)
        self.assertEqual(candidate.end_rule, "next_abstract_boundary")

    def test_local_window_candidate_stops_before_poster_session_preamble(self) -> None:
        record = {
            "paper_id": "8198",
            "source_filename": "poster_session_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "623",
                            "Anti-glycine receptor antibody causing relapsing encephalitis",
                            "with rigidity and myoclonus",
                            "J. Williams, K. O'Connell, S. O'Riordan, C. McGuigan",
                            "Objective: To describe a unique case of anti-glycine receptor antibody causing relapsing encephalitis.",
                            "Background: Progressive encephalomyelitis with rigidity and myoclonus is a rare disorder.",
                            "Methods: Observational case study.",
                            "Results: A 54 year old man developed relapsing encephalitis with rigidity and brainstem signs.",
                            "Conclusions: This patient presented with hyperekplexia, rigidity",
                            "and brainstem signs consistent with a diagnosis of PERM due to a",
                            "pathogenic anti-glycine receptor antibody. Although a monophasic",
                            "illness is usually reported, this patient's disease course has been",
                            "relapsing requiring long term immunosuppressive therapy. High serum",
                            "antibody titres correlate with disease activity.",
                            "POSTER SESSION 3",
                            "Tuesday, June 19, 2012",
                            "12:15-13:45",
                            "Linear Park Marquee",
                            "Posters available for viewing 9:00-18:00",
                            "PARKINSON'S DISEASE:",
                            "ELECTROPHYSIOLOGY",
                            "624",
                            "Subthalamic activity during diphasic dyskinesias in Parkinson's disease",
                            "M. Alegre, J. Lopez-Azcarate",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Anti-glycine receptor antibody causing relapsing encephalitis with rigidity and myoclonus",
            reference_authors="Williams, J.; O'Connell, K.; O'Riordan, S.",
            pattern=pattern,
            target_code="623",
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertIn("High serum antibody titres correlate with disease activity.", joined)
        self.assertNotIn("POSTER SESSION 3", joined)
        self.assertNotIn("Subthalamic activity during diphasic dyskinesias", joined)

    def test_choose_best_candidate_prefers_window_when_block_only_adds_preamble_tail(self) -> None:
        line_refs = [
            self.module.LineRef(global_index=0, page_index=0, line_index=0, text="Target title"),
            self.module.LineRef(global_index=1, page_index=0, line_index=1, text="Jane Doe, John Smith"),
            self.module.LineRef(global_index=2, page_index=0, line_index=2, text="Background: target body"),
            self.module.LineRef(global_index=3, page_index=0, line_index=3, text="Conclusion: target body"),
            self.module.LineRef(global_index=4, page_index=0, line_index=4, text="Abstract - WCN 2013"),
            self.module.LineRef(global_index=5, page_index=0, line_index=5, text="No: 1362"),
        ]
        window = self.module.AbstractBlock(
            code="",
            start_index=0,
            end_index=4,
            start_page_index=0,
            end_page_index=0,
            title_text="Target title",
            header_text="Target title Jane Doe, John Smith",
            preview_text="Target title Jane Doe, John Smith Background: target body Conclusion: target body",
            line_refs=line_refs[:4],
            title_score=0.95,
            author_score=0.50,
            match_score=0.82,
            trim_method="page_local_sliding_window_match",
            trim_mode="page_local_sliding_window_match",
        )
        block = self.module.AbstractBlock(
            code="",
            start_index=0,
            end_index=6,
            start_page_index=0,
            end_page_index=0,
            title_text="Target title",
            header_text="Target title Jane Doe, John Smith",
            preview_text=" ".join(line.text for line in line_refs),
            line_refs=line_refs,
            title_score=0.97,
            author_score=0.50,
            match_score=0.90,
            trim_method="fuzzy_title_author_block_match",
            trim_mode="fuzzy_title_author_block_match",
        )

        chosen = self.module.choose_best_candidate(block, window)

        self.assertIs(chosen, window)

    def test_choose_best_candidate_prefers_window_when_it_has_explicit_next_boundary(self) -> None:
        line_refs = [
            self.module.LineRef(global_index=0, page_index=0, line_index=0, text="Poster 20"),
            self.module.LineRef(global_index=1, page_index=0, line_index=1, text="Autonomic dysfunction in stiff person syndrome"),
            self.module.LineRef(global_index=2, page_index=0, line_index=2, text="A. Barboi"),
            self.module.LineRef(global_index=3, page_index=0, line_index=3, text="Objectives: Describe autonomic involvement."),
            self.module.LineRef(global_index=4, page_index=0, line_index=4, text="Results: There were 3 men and 5 women."),
            self.module.LineRef(global_index=5, page_index=0, line_index=5, text="Conclusions: Autonomic involvement may be a clue to the diagnosis."),
            self.module.LineRef(global_index=6, page_index=0, line_index=6, text="Poster 21"),
            self.module.LineRef(global_index=7, page_index=0, line_index=7, text="A comparison of the progression of autonomic dysfunction"),
            self.module.LineRef(global_index=8, page_index=0, line_index=8, text="J.L. Gilden"),
        ]
        window = self.module.AbstractBlock(
            code="Poster 20",
            start_index=0,
            end_index=6,
            start_page_index=0,
            end_page_index=0,
            title_text="Autonomic dysfunction in stiff person syndrome",
            header_text="Poster 20 Autonomic dysfunction in stiff person syndrome",
            preview_text=" ".join(line.text for line in line_refs[:6]),
            line_refs=line_refs[:6],
            title_score=0.95,
            author_score=0.45,
            match_score=0.84,
            trim_method="page_local_sliding_window_match",
            trim_mode="page_local_sliding_window_match",
            start_rule="backtrack_abstract_boundary",
            end_rule="next_abstract_boundary",
        )
        block = self.module.AbstractBlock(
            code="Poster 20",
            start_index=0,
            end_index=9,
            start_page_index=0,
            end_page_index=0,
            title_text="Autonomic dysfunction in stiff person syndrome",
            header_text="Poster 20 Autonomic dysfunction in stiff person syndrome",
            preview_text=" ".join(line.text for line in line_refs),
            line_refs=line_refs,
            title_score=0.97,
            author_score=0.45,
            match_score=0.88,
            trim_method="fuzzy_title_author_block_match",
            trim_mode="fuzzy_title_author_block_match",
        )

        chosen = self.module.choose_best_candidate(block, window)

        self.assertIs(chosen, window)

    def test_proceedings_signals_detect_small_multi_abstract_fragment(self) -> None:
        record = {
            "paper_id": "1597",
            "source_filename": "small_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "O-35 The Stiff Person Syndrome. Neurophysiological findings",
                            "Maria Concepcion Maeztu Sardina, Francisco A. Martinez Garcia",
                            "Murciano de Salud, Murcia, Spain",
                            "Background: Stiff Person Syndrome is an immune-mediated disorder.",
                            "Conclusions: The neurophysiological studies are important.",
                            "doi:10.1016/j.clinph.2019.04.351",
                            "O-36 Listening the sound of neuromuscular junction during voluntary contraction",
                            "Sezin Alpaydin Baslo, Tugrul Artug",
                            "Bakirkoy Mazhar Osman Training and Research Hospital, Istanbul, Turkey",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        signals = self.module.proceedings_signals(record, lines)

        self.assertTrue(signals["proceedings_detected"])
        self.assertGreaterEqual(signals["proceedings_signal_score"], 3)

    def test_proceedings_signals_rejects_standalone_article_style_source(self) -> None:
        record = {
            "paper_id": "969",
            "source_filename": "journal_article.pdf",
            "n_pages": 7,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Novel clinical features of glycine receptor antibody syndrome: A series of 17 cases",
                            "Amanda L. Piquet, Murtaza Khan, Judith E.A. Warner",
                            "Neurol Neuroimmunol Neuroinflamm 2019;6:e592.",
                            "Abstract",
                            "Objective: To describe novel clinical features of glycine receptor antibody syndrome.",
                            "Methods: Patient subjects and ascertainment were reviewed retrospectively.",
                            "Results: We provide a comprehensive evaluation of an expanded neurologic phenotype.",
                            "Discussion: These findings extend the known syndrome spectrum.",
                            "References",
                            "1. Example reference.",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        signals = self.module.proceedings_signals(record, lines)

        self.assertFalse(signals["proceedings_detected"])

    def test_proceedings_signals_rejects_numbered_article_sections(self) -> None:
        record = {
            "paper_id": "980",
            "source_filename": "clinical_case_article.pdf",
            "n_pages": 2,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "EGM clinical case",
                            "An unusual cause of older adult falls: Stiff Leg Syndrome",
                            "M. Michaud, C. Gaudin, D. Brechemier, P. Cintas",
                            "1. Case report",
                            "Mr. B. was hospitalised for repeated falls and painful spasms.",
                            "2. Discussion",
                            "Stiff leg syndrome is a rare neurological disease.",
                            "European Geriatric Medicine 4 (2013) 108-109",
                            "A R T I C L E I N F O",
                            "Article history:",
                            "Available online 4 February 2013",
                            "Keywords:",
                            "Stiff leg syndrome",
                            "3. Conclusion",
                            "Clinicians should know this rare pathology.",
                            "Disclosure of interest",
                            "References",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        signals = self.module.proceedings_signals(record, lines)

        self.assertFalse(signals["proceedings_detected"])

    def test_local_window_candidate_uses_poster_header_boundary(self) -> None:
        record = {
            "paper_id": "1011",
            "source_filename": "poster_booklet.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "sequelae of radiation-induced myelopathy, radiation-induced",
                            "funicular pain is likely to progress with time.",
                            "Poster 313",
                            "Two Cases of Stiff Person Syndrome Treated with",
                            "Intrathecal Baclofen Pump in an Inpatient",
                            "Rehabilitation Unit: A Case Series.",
                            "Hannah A. Shoval; Orlee Hamer; Kenny Chantasi; Udai Nanda",
                            "Case Description: Two patients were admitted after pump placement.",
                            "Conclusions: Intrathecal pump placement followed by an inpatient rehabilitation program should be considered in patients with SPS.",
                            "Poster 314",
                            "The Usefulness of Transcranial Magnetic Stimulation",
                            "and Diffusion Tensor Tractography for Evaluation of Stroke Recovery.",
                            "Bo-Ram Kim; Jongmin Lee",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Two cases of stiff person syndrome treated with intrathecal baclofen pump in an inpatient rehabilitation unit: A case series",
            reference_authors="Shoval, H.A.; Hamer, O.; Chantasi, K.; Nanda, U.",
            pattern=pattern,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.line_refs[0].text, "Poster 313")
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertNotIn("sequelae of radiation-induced myelopathy", joined)
        self.assertNotIn("Poster 314", joined)

    def test_local_window_candidate_keeps_full_ocr_damaged_poster_abstract(self) -> None:
        record = {
            "paper_id": "1117",
            "source_filename": "ocr_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "PP08.9 - 2594",
                            "Glycine receptor antibody mediated progressive",
                            "encephalomyelitis with rigidity and myoclonus (PERM)",
                            "presenting as an abnormal startle response in an adolescent girl",
                            "A. Patel, S. Boyd, B. Amin, R. Robinson, M. Woodhall, A. Vincent, C. Hemingway, P. Munot",
                            "Objective: To describe a young girl in whom stimulus sensitive spasms were a diagnostic clue.",
                            "Results: The patient had progressive encephalomyelitis with rigidity and myoclonus.",
                            "Conclusion: Glycine receptor antibody mediated progressive encephalomyelitis with",
                            "rigidity and myoclonus can present in children as stimulus-sensitive muscle spasms.",
                            "PP08.10 - 2595",
                            "Another abstract title",
                            "Another author line",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        candidate = self.module.local_window_candidate(
            lines=lines,
            record=record,
            reference_title="Glycine receptor antibody mediated progressive encephalomyelitis with rigidity and myoclonus (PERM) presenting as an abnormal startle response in an adolescent girl",
            reference_authors="Patel, A.; Boyd, S.; Amin, B.; Robinson, R.",
            pattern=pattern,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        joined = " ".join(line.text for line in candidate.line_refs)
        self.assertIn("rigidity and myoclonus can present in children as stimulus-sensitive muscle spasms.", joined)
        self.assertNotIn("Another abstract title", joined)

    def test_extract_blocks_does_not_split_on_body_acronym_list_line(self) -> None:
        record = {
            "paper_id": "1439",
            "source_filename": "acronym_body_fragment.pdf",
            "n_pages": 2,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "M300. Unrecognized Respiratory Manifestations of Stiff",
                            "Person Syndrome (SPS)",
                            "Goran Rakocevic, Matthew Woodford, Katrina Pack, Anthony Allen and William Sexaur. Philadelphia, PA",
                            "Introduction: Respiratory manifestations in Stiff-person Syndrome patients have not been systematically investigated and adequately managed.",
                            "Methods: SPS patients were recruited prospectively from neurology clinic in a single university center.",
                            "Results: Fifteen of 16 consented patients had evaluable data.",
                            "There was no significant association between pulmonary",
                            "function and any of the following: VAS1day, UCSD-",
                            "SOBQ, Distribution of Stiffness, or Heightened Sensitivity.",
                            "No correlation between any dyspnea score and any measure",
                            "of SPS disease severity was found.",
                            "Conclusions:",
                            "Dyspnea in SPS is common, and occurs both at rest and with exertion.",
                            "Potential involvement of diaphragmatic muscles is unknown.",
                            "S198 Annals of Neurology Vol 82 (suppl 21) 2017",
                        ]
                    ),
                },
                {
                    "page_index": 1,
                    "text": "\n".join(
                        [
                            "M301. Regenerating Axons and Blood Vessels in Tissue",
                            "Engineered Scaffolds Have Defined Spatial Relationships",
                            "After Complete Spinal Cord Injury in Rats",
                            "Another author line",
                        ]
                    ),
                },
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        blocks = self.module.extract_blocks(lines, pattern)
        chosen = self.module.best_matching_block(
            blocks=blocks,
            reference_title="Unrecognized respiratory manifestations of stiff person syndrome (SPS)",
            reference_authors="Rakocevic, G.; Woodford, M.; Pack, K.; Allen, A.; Sexaur, W.",
        )

        self.assertIsNotNone(chosen)
        assert chosen is not None
        joined = " ".join(line.text for line in chosen.line_refs)
        self.assertIn("Potential involvement of diaphragmatic muscles is unknown.", joined)
        self.assertNotIn("M301.", joined)

    def test_extract_blocks_keeps_split_author_block_and_trims_disclosure_tail(self) -> None:
        record = {
            "paper_id": "1441",
            "source_filename": "split_author_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "P601",
                            "Spectrum of stiff person syndrome expands with presence of",
                            "retinal pathology",
                            "T. Shoemaker",
                            "1, A. Rothman1, J. Prince2, S. Saidha1, P.A.",
                            "Calabresi1, S.D. Newsome1",
                            "1Neurology, Neuroimmunology, 2Electrical and Computer",
                            "Engineering, Johns Hopkins University, Baltimore, MD, United",
                            "States",
                            "Objective: To assess structural and functional changes in the afferent visual system of patients with Stiff-Person Syndrome (SPS).",
                            "Background: SPS is a rare neuroimmunological disorder characterized by progressive rigidity and painful muscle spasms.",
                            "Methods: Forty SPS patients and matched healthy controls underwent retinal testing.",
                            "Results: SPS patients exhibited lower visual acuity and thinner GCIP layer thickness.",
                            "Conclusions: SPS patients have mild visual dysfunction compared to healthy controls.",
                            "Clinicians should be aware of the expanding spectrum of SPS to help prevent misdiagnosis as more common conditions like MS.",
                            "Disclosure",
                            "Thomas Shoemaker: nothing to disclose",
                            "P602",
                            "Retinal ganglion cell layer thickness predicts disease activity",
                            "Another author line",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        blocks = self.module.extract_blocks(lines, pattern)
        chosen = self.module.best_matching_block(
            blocks=blocks,
            reference_title="Spectrum of stiff person syndrome expands with presence of retinal pathology",
            reference_authors="Shoemaker, T.; Rothman, A.; Prince, J.; Saidha, S.; Calabresi, P.A.; Newsome, S.D.",
        )

        self.assertIsNotNone(chosen)
        assert chosen is not None
        joined = " ".join(line.text for line in chosen.line_refs)
        self.assertIn("prevent misdiagnosis as more common conditions like MS.", joined)
        self.assertNotIn("Disclosure", joined)
        self.assertNotIn("P602", joined)

    def test_extract_blocks_keeps_body_when_disclosure_precedes_case_description(self) -> None:
        record = {
            "paper_id": "1011",
            "source_filename": "disclosure_preamble_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Poster 313",
                            "Two Cases of Stiff Person Syndrome Treated with",
                            "Intrathecal Baclofen Pump in an Inpatient",
                            "Rehabilitation Unit: A Case Series.",
                            "Hannah A. Shoval (New York Presbyterian Hospital, New York, NY, United States); Orlee Hamer, DO;",
                            "Kenny Chantasi, DO; Udai Nanda, MD.",
                            "Disclosures: H. A. Shoval, No Disclosures: I Have No Relevant Financial Relationships to Disclose.",
                            "Case Description: RS is a 55-year-old female and PL is a 48-year-old male admitted for stiff person syndrome (SPS) to an inpatient rehabilitation unit after intrathecal baclofen pump placement.",
                            "Setting: Inpatient Rehabilitation Unit of a University Hospital.",
                            "Results or Clinical Course: Both patients improved with intrathecal baclofen pump placement and therapy participation.",
                            "Discussion: Inpatient rehabilitation allows for close coordination of baclofen titration with intensive therapy and fall prevention.",
                            "Conclusions: Patients with SPS may benefit from intrathecal baclofen pumps or inpatient rehabilitation.",
                            "Poster 314",
                            "Another unrelated title",
                            "Another author line",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        blocks = self.module.extract_blocks(lines, pattern)
        chosen = self.module.best_matching_block(
            blocks=blocks,
            reference_title="Two cases of stiff person syndrome treated with intrathecal baclofen pump in an inpatient rehabilitation unit: A case series",
            reference_authors="Shoval, H.A.; Hamer, O.; Chantasi, K.; Nanda, U.",
        )

        self.assertIsNotNone(chosen)
        assert chosen is not None
        joined = " ".join(line.text for line in chosen.line_refs)
        self.assertIn("Patients with SPS may benefit from intrathecal baclofen pumps or inpatient rehabilitation.", joined)
        self.assertNotIn("Poster 314", joined)

    def test_best_matching_block_prefers_full_body_over_header_only_listing(self) -> None:
        listing = self.module.AbstractBlock(
            code="M103",
            start_index=10,
            end_index=18,
            start_page_index=0,
            end_page_index=0,
            title_text="GAD Autoimmunity: Syndromes, Comorbidities, and Coexisting Antibodies in 121 Patients",
            header_text="M103 listing header",
            preview_text="Helena Arino, Nuria Gresa-Arribas, Romana Hoftberger",
            line_refs=[
                self.module.LineRef(global_index=10, page_index=0, line_index=0, text="M103. GAD Autoimmunity: Syndromes, Comorbidities,"),
                self.module.LineRef(global_index=11, page_index=0, line_index=1, text="and Coexisting Antibodies in 121 Patients"),
                self.module.LineRef(global_index=12, page_index=0, line_index=2, text="Helena Arino, Nuria Gresa-Arribas, Romana Hoftberger"),
            ],
        )
        full_body = self.module.AbstractBlock(
            code="M103",
            start_index=100,
            end_index=135,
            start_page_index=9,
            end_page_index=9,
            title_text="GAD Autoimmunity: Syndromes, Comorbidities, and Coexisting Antibodies in 121 Patients",
            header_text="M103 full abstract",
            preview_text=(
                "Helena Arino, Nuria Gresa-Arribas. GAD65-antibodies associate with several neurological "
                "syndromes. In GAD-syndromes, the association with classical PNS and cell-surface antibodies "
                "should prompt cancer screening."
            ),
            line_refs=[
                self.module.LineRef(global_index=100, page_index=9, line_index=0, text="M103. GAD Autoimmunity: Syndromes, Comorbidities,"),
                self.module.LineRef(global_index=101, page_index=9, line_index=1, text="and Coexisting Antibodies in 121 Patients"),
                self.module.LineRef(global_index=102, page_index=9, line_index=2, text="Helena Arino, Nuria Gresa-Arribas, Romana Hoftberger"),
                self.module.LineRef(global_index=103, page_index=9, line_index=3, text="Objective: To determine whether distinct epitopes or coexisting antibodies relate to specific syndromes."),
                self.module.LineRef(global_index=104, page_index=9, line_index=4, text="Methods: We investigated 121 patients with GAD antibody-associated syndromes with and without cancer using multiple detecting techniques."),
                self.module.LineRef(global_index=105, page_index=9, line_index=5, text="Results: Patients with paraneoplastic syndromes had more coexisting CSF cell-surface antibodies and were older, more often male, and more likely to develop classical paraneoplastic syndromes."),
                self.module.LineRef(global_index=106, page_index=9, line_index=6, text="Results: No significant difference among epitope regions and syndromes was detected, and live-neuron studies showed no GAD-antibody internalisation despite strong serum and cerebrospinal fluid titres across multiple disease phenotypes."),
                self.module.LineRef(global_index=107, page_index=9, line_index=7, text="Conclusion: In GAD-syndromes, the association with classical paraneoplastic syndromes and cell-surface antibodies should prompt cancer screening."),
            ],
        )

        chosen = self.module.best_matching_block(
            blocks=[listing, full_body],
            reference_title="GAD autoimmunity: Syndromes, comorbidities, and coexisting antibodies in 121 patients",
            reference_authors="Arino H.; Gresa-Arribas N.; Hoftberger R.",
        )

        self.assertIs(chosen, full_body)

    def test_proceedings_signals_detects_single_page_supplement_fragment(self) -> None:
        record = {
            "paper_id": "1138",
            "source_filename": "jns_index_supplement_fragment.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "1121",
                            "WFN15-1338",
                            "Neuromuscular Disorders",
                            "Abstracts / Journal of the Neurological Sciences 357 (2015) e328-e349 e331",
                            "Stiff person syndrome: review of 14 patients",
                            "V. Cavalcante, A. Souza Bulle Oliveira. Neurology and Neurosurgery, Federal University of Sao Paulo, Sao Paulo, Brazil",
                            "Stiff person syndrome (SPS) is an autoimmune disorder of the central nervous system.",
                            "Objectives: To describe patients affected by SPS.",
                            "Patients and methods: Retrospective analysis of 14 medical records.",
                            "Results: Gender: 11 women and 3 men.",
                            "Conclusion: The results are compatible with literature.",
                            "doi:10.1016/j.jns.2015.08.1181",
                            "1122",
                            "WFN15-0464",
                            "Neuromuscular Disorders",
                            "Causes of critical illness polyneuropathy in adults after cardiac surgery",
                        ]
                    ),
                }
            ],
        }

        lines = self.module.flatten_lines(record)
        signals = self.module.proceedings_signals(record, lines)

        self.assertTrue(signals["proceedings_detected"])
        self.assertGreaterEqual(signals["proceedings_signal_score"], 3)

    def test_header_boundary_accepts_numeric_code_with_session_preamble(self) -> None:
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "1121",
                            "WFN15-1338",
                            "Neuromuscular Disorders",
                            "Stiff person syndrome: review of 14 patients",
                            "V. Cavalcante, A. Souza Bulle Oliveira. Neurology and Neurosurgery, Federal University of Sao Paulo, Sao Paulo, Brazil",
                            "Objectives: To describe patients affected by SPS.",
                        ]
                    ),
                }
            ]
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        matched, _, rule, _ = self.module.header_boundary(lines, 0, pattern, allow_soft=True)

        self.assertTrue(matched)
        self.assertEqual(rule, "coded_boundary")

    def test_extract_blocks_recognises_wip_codes_and_prefers_full_body(self) -> None:
        record = {
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Autoimmune Neurology",
                            "M311.WIP Stiff-Person Syndrome in Association with",
                            "Cerebellar Ataxia: Overlapping Syndrome: A Case",
                            "Report",
                            "Varun H. Chauhan and Abbas A. Jowkar. Detroit, MI",
                            "M312.WIP Another autoimmune title",
                            "Another author line",
                        ]
                    ),
                },
                {
                    "page_index": 1,
                    "text": "\n".join(
                        [
                            "Autoimmune Neurology",
                            "M311WIP . Stiff-Person Syndrome in Association with",
                            "Cerebellar Ataxia: Overlapping Syndrome: A Case",
                            "Report",
                            "Varun H. Chauhan and Abbas A. Jowkar. Detroit, MI",
                            "SPS (Stiff-person Syndrome) is a rare autoimmune condition.",
                            "Our patient had classical features of SPS with cerebellar ataxia",
                            "and demonstrated significant improvement in his symptoms with appropriate treatment.",
                            "M312WIP . Another autoimmune title",
                            "Another author line",
                        ]
                    ),
                },
            ]
        }

        lines = self.module.flatten_lines(record)
        pattern = self.module.infer_proceedings_pattern(lines)
        blocks = self.module.extract_blocks(lines, pattern)

        m311_blocks = [block for block in blocks if self.module.normalize_code(block.code) == "M311WIP"]

        self.assertEqual(len(m311_blocks), 2)

        chosen = self.module.best_matching_block(
            blocks=blocks,
            reference_title="Stiff-person syndrome in association with cerebellar ataxia: Overlapping syndrome: A case report",
            reference_authors="Chauhan V.H.; Jowkar A.A.",
        )

        self.assertIsNotNone(chosen)
        assert chosen is not None
        self.assertEqual(chosen.start_page_index, 1)
        chosen_text = " ".join(line.text for line in chosen.line_refs)
        self.assertIn("appropriate treatment.", chosen_text)

    def test_choose_best_candidate_prefers_full_body_block_over_header_only_window(self) -> None:
        block_candidate = self.module.AbstractBlock(
            code="M311WIP",
            start_index=100,
            end_index=114,
            start_page_index=3,
            end_page_index=3,
            title_text="Stiff-Person Syndrome in Association with Cerebellar Ataxia: Overlapping Syndrome: A Case Report",
            header_text="M311WIP . Stiff-Person Syndrome in Association with Cerebellar Ataxia: Overlapping Syndrome: A Case Report",
            preview_text="Varun H. Chauhan and Abbas A. Jowkar. Detroit, MI. The patient improved with appropriate treatment.",
            line_refs=[
                self.module.LineRef(global_index=100, page_index=3, line_index=0, text="M311WIP . Stiff-Person Syndrome in Association with"),
                self.module.LineRef(global_index=101, page_index=3, line_index=1, text="Cerebellar Ataxia: Overlapping Syndrome: A Case"),
                self.module.LineRef(global_index=102, page_index=3, line_index=2, text="Report"),
                self.module.LineRef(global_index=103, page_index=3, line_index=3, text="Varun H. Chauhan and Abbas A. Jowkar. Detroit, MI"),
                self.module.LineRef(global_index=104, page_index=3, line_index=4, text="SPS is a rare autoimmune condition."),
                self.module.LineRef(global_index=105, page_index=3, line_index=5, text="The patient had classical features of SPS with cerebellar ataxia."),
                self.module.LineRef(global_index=106, page_index=3, line_index=6, text="He demonstrated significant improvement in his symptoms with appropriate treatment."),
                self.module.LineRef(global_index=107, page_index=3, line_index=7, text="This presentation included persistent stiffness, exaggerated startle, and gait impairment."),
                self.module.LineRef(global_index=108, page_index=3, line_index=8, text="Serial assessment supported an overlapping autoimmune neurological syndrome with cerebellar involvement."),
            ],
            title_score=0.83,
            author_score=0.0,
            match_score=0.623,
            trim_method="fuzzy_title_author_block_match",
            trim_mode="fuzzy_title_author_block_match",
            body_signal_count=1,
            header_only_flag=False,
        )
        window_candidate = self.module.AbstractBlock(
            code="M311.WIP",
            start_index=10,
            end_index=14,
            start_page_index=0,
            end_page_index=0,
            title_text="Stiff-Person Syndrome in Association with Cerebellar Ataxia: Overlapping Syndrome: A Case Report",
            header_text="M311.WIP Stiff-Person Syndrome in Association with Cerebellar Ataxia: Overlapping Syndrome: A Case Report",
            preview_text="Varun H. Chauhan and Abbas A. Jowkar. Detroit, MI",
            line_refs=[
                self.module.LineRef(global_index=10, page_index=0, line_index=0, text="M311.WIP Stiff-Person Syndrome in Association with"),
                self.module.LineRef(global_index=11, page_index=0, line_index=1, text="Cerebellar Ataxia: Overlapping Syndrome: A Case"),
                self.module.LineRef(global_index=12, page_index=0, line_index=2, text="Report"),
                self.module.LineRef(global_index=13, page_index=0, line_index=3, text="Varun H. Chauhan and Abbas A. Jowkar. Detroit, MI"),
            ],
            title_score=0.844,
            author_score=0.5,
            match_score=0.712,
            trim_method="page_local_sliding_window_match",
            trim_mode="page_local_sliding_window_match",
            start_rule="backtrack_abstract_boundary",
            end_rule="next_abstract_boundary",
            body_signal_count=0,
            header_only_flag=True,
        )

        chosen = self.module.choose_best_candidate(block_candidate, window_candidate)

        self.assertIs(chosen, block_candidate)

    def test_filter_to_proceedings_candidates_keeps_explicit_ids_subject_to_manual_override(self) -> None:
        input_dir = self.tmp_path / "text"
        input_dir.mkdir()
        target_path = input_dir / "1391.json"
        target_path.write_text("{}", encoding="utf-8")

        source_registry_path = self.tmp_path / "source_categorisation_registry.csv"
        source_manual_review_path = self.tmp_path / "source_categorisation_manual_review.csv"
        existing_trim_registry_path = self.tmp_path / "text_trim_registry.csv"

        with source_registry_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["paper_id", "source_category", "source_subtype"])
            writer.writeheader()
            writer.writerow(
                {
                    "paper_id": "1391",
                    "source_category": "conference_abstract",
                    "source_subtype": "case_series_conference_abstract",
                }
            )

        with source_manual_review_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["paper_id", "final_source_category", "final_source_subtype"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "paper_id": "1391",
                    "final_source_category": "case_series_or_multi_case",
                    "final_source_subtype": "small_case_series",
                }
            )

        with existing_trim_registry_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["paper_id", "trim_status"])
            writer.writeheader()

        filtered = self.module.filter_to_proceedings_candidates(
            paths=[target_path],
            source_categorisation_path=source_registry_path,
            source_manual_review_path=source_manual_review_path,
            existing_trim_registry_path=existing_trim_registry_path,
            force_all_papers=False,
            explicit_paper_ids=["1391"],
            include_already_trimmed=False,
        )

        self.assertEqual(filtered, [])


if __name__ == "__main__":
    unittest.main()
