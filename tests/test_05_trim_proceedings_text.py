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
            self.module.LineRef(global_index=4, page_index=0, line_index=4, text="doi:10.1016/j.jns.2013.07.1575"),
            self.module.LineRef(global_index=5, page_index=0, line_index=5, text="Abstract - WCN 2013"),
            self.module.LineRef(global_index=6, page_index=0, line_index=6, text="No: 1362"),
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
            end_index=7,
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


if __name__ == "__main__":
    unittest.main()
