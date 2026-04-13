from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


PIPELINE_DIR = Path(__file__).resolve().parents[1] / "src" / "pipelines"
TRIM_LLM_PATH = PIPELINE_DIR / "_proceedings_trim_llm.py"
VALIDATE_LLM_PATH = PIPELINE_DIR / "05b_validate_proceedings_text_LLM.py"


def load_module(script_path: Path, module_name: str):
    if str(PIPELINE_DIR) not in sys.path:
        sys.path.insert(0, str(PIPELINE_DIR))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestProceedingsTrimLLM(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.trim_llm = load_module(TRIM_LLM_PATH, "_proceedings_trim_llm")
        cls.validate_llm = load_module(VALIDATE_LLM_PATH, "validate_proceedings_text_llm")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_source_lines(self) -> list[str]:
        return [
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

    def make_source_record(self, paper_id: str = "2001") -> dict[str, object]:
        lines = self.make_source_lines()
        return {
            "paper_id": paper_id,
            "source_filename": f"{paper_id}.pdf",
            "n_pages": 1,
            "pages": [{"page_index": 0, "text": "\n".join(lines)}],
        }

    def make_candidates(self):
        trim_llm = self.trim_llm
        return [
            trim_llm.EndCandidate(
                candidate_id="cand_01_current_selected_end",
                heuristic_name="current_selected_end",
                rank=1,
                start_index=1,
                end_index_exclusive=9,
                start_page_index=0,
                end_page_index=0,
                n_lines=8,
                body_char_count=900,
                contains_next_confirmed_header=False,
                contains_soft_boundary=False,
                contains_tail_metadata=True,
                confidence_class="strict",
                rationale="Baseline deterministic span.",
            ),
            trim_llm.EndCandidate(
                candidate_id="cand_02_next_confirmed_header_end",
                heuristic_name="next_confirmed_header_end",
                rank=2,
                start_index=1,
                end_index_exclusive=11,
                start_page_index=0,
                end_page_index=0,
                n_lines=10,
                body_char_count=1000,
                contains_next_confirmed_header=True,
                contains_soft_boundary=False,
                contains_tail_metadata=True,
                confidence_class="permissive",
                rationale="Overshoot span up to the next header.",
            ),
        ]

    def make_package(self, source_path: Path, paper_id: str = "2001"):
        trim_llm = self.trim_llm
        return trim_llm.CandidatePackage(
            paper_id=paper_id,
            source_text_json_path=str(source_path),
            reference_title="A stiff woman",
            reference_authors="Srinithya, F; Gadde, S",
            matched_start_index=1,
            matched_start_page_index=0,
            matched_block_code="",
            matched_block_title="A STIFF WOMAN",
            start_rule="matched_header_start",
            candidate_generation_mode=trim_llm.CANDIDATE_GENERATION_MODE,
            candidates=self.make_candidates(),
            overshoot_candidate_id="cand_02_next_confirmed_header_end",
            baseline_candidate_id="cand_01_current_selected_end",
            proceedings_signals={
                "n_pages": 1,
                "abstract_block_count": 2,
                "title_like_line_count": 2,
                "author_like_line_count": 2,
                "program_marker_count": 0,
                "proceedings_signal_score": 5,
                "proceedings_detected": True,
            },
            upstream_match_metadata={
                "trim_method": "llm_validated_proceedings_trim",
                "trim_mode": "llm_validated_proceedings_trim",
                "title_score": 0.95,
                "author_score": 0.60,
                "match_score": 0.86,
                "end_rule": "next_soft_header",
                "matched_end_index_exclusive": 9,
                "matched_end_page_index": 0,
                "body_signal_count": 4,
                "header_only_flag": False,
                "spillover_flag": False,
                "index_detected": False,
                "index_confidence": 0.0,
                "index_listed_page": "",
                "index_prev_code": "",
                "index_next_code": "",
                "page_map_method": "",
                "estimated_offset": 0.0,
                "offset_confidence": 0.0,
                "fallback_triggered": False,
                "candidate_quality_status": "trimmed_auto",
                "candidate_quality_reason": "Looks valid.",
            },
        )

    def write_source_record(self, record: dict[str, object]) -> Path:
        source_path = self.tmp_path / f"{record['paper_id']}.json"
        source_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return source_path

    def test_dedupe_end_candidates_prefers_higher_priority_heuristic(self) -> None:
        trim_llm = self.trim_llm
        duplicated = [
            trim_llm.EndCandidate(
                candidate_id="",
                heuristic_name="current_selected_end",
                rank=0,
                start_index=10,
                end_index_exclusive=20,
                start_page_index=0,
                end_page_index=0,
                n_lines=10,
                body_char_count=600,
                contains_next_confirmed_header=False,
                contains_soft_boundary=False,
                contains_tail_metadata=False,
                confidence_class="strict",
                rationale="Baseline",
            ),
            trim_llm.EndCandidate(
                candidate_id="",
                heuristic_name="tail_metadata_trim_end",
                rank=0,
                start_index=10,
                end_index_exclusive=20,
                start_page_index=0,
                end_page_index=0,
                n_lines=10,
                body_char_count=600,
                contains_next_confirmed_header=False,
                contains_soft_boundary=False,
                contains_tail_metadata=True,
                confidence_class="medium",
                rationale="Preferred duplicate",
            ),
        ]

        deduped = trim_llm.dedupe_end_candidates(duplicated)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].heuristic_name, "tail_metadata_trim_end")
        self.assertEqual(deduped[0].candidate_id, "cand_01_tail_metadata_trim_end")

    def test_write_and_load_candidate_package_round_trip(self) -> None:
        record = self.make_source_record()
        source_path = self.write_source_record(record)
        package = self.make_package(source_path)
        candidate_path = self.tmp_path / "candidate_package.json"

        self.trim_llm.write_candidate_package(package, candidate_path)
        loaded = self.trim_llm.load_candidate_package(candidate_path)

        self.assertEqual(loaded.paper_id, package.paper_id)
        self.assertEqual(loaded.source_text_json_path, str(source_path))
        self.assertEqual(loaded.baseline_candidate_id, package.baseline_candidate_id)
        self.assertEqual([candidate.candidate_id for candidate in loaded.candidates], [candidate.candidate_id for candidate in package.candidates])

    def test_validate_llm_decision_accepts_exact_candidate_within_overshoot(self) -> None:
        record = self.make_source_record()
        source_path = self.write_source_record(record)
        package = self.make_package(source_path)
        source_lines = self.validate_llm.flatten_lines(record)
        decision = self.trim_llm.LLMDecision(
            decision_type="candidate_exact",
            selected_candidate_id="cand_01_current_selected_end",
            last_abstract_line_global_index=8,
            confidence="high",
            end_reason="candidate_is_exact",
            explanation_short="The baseline candidate ends at the disclosure line.",
        )

        passed, reason = self.trim_llm.validate_llm_decision(package, decision, source_lines)

        self.assertTrue(passed)
        self.assertEqual(reason, "ok")

    def test_validate_llm_decision_rejects_page_footer_cut_before_resumed_body(self) -> None:
        record = {
            "paper_id": "2002",
            "source_filename": "2002.pdf",
            "n_pages": 2,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "Poster 10",
                            "A STIFF WOMAN",
                            "Fnu Srinithya; Saikrishna Gadde. Example Hospital, Birmingham, AL",
                            "BACKGROUND: A 37 year old woman developed progressive stiffness and painful spasms.",
                            "METHODS: The patient underwent extensive testing before the final diagnosis.",
                            "RESULTS: She improved after immunotherapy and benzodiazepines.",
                            "DISCUSSION: Early recognition supported supportive care and malignancy screening.",
                            "Movement Disorders, Vol. 28, Suppl. 1, 2013",
                            "S355POSTER SESSION",
                            "Downloaded from https://movementdisorders.onlinelibrary.wiley.com/",
                        ]
                    ),
                },
                {
                    "page_index": 1,
                    "text": "\n".join(
                        [
                            "Conclusions: The syndrome remained highly treatment responsive.",
                            "The patient regained ambulation with sustained improvement at follow-up.",
                            "Disclosure: Nothing to disclose.",
                        ]
                    ),
                },
            ],
        }
        source_path = self.write_source_record(record)
        package = self.trim_llm.CandidatePackage(
            paper_id="2002",
            source_text_json_path=str(source_path),
            reference_title="A stiff woman",
            reference_authors="Srinithya, F; Gadde, S",
            matched_start_index=1,
            matched_start_page_index=0,
            matched_block_code="",
            matched_block_title="A STIFF WOMAN",
            start_rule="matched_header_start",
            candidate_generation_mode=self.trim_llm.CANDIDATE_GENERATION_MODE,
            candidates=[
                self.trim_llm.EndCandidate(
                    candidate_id="cand_01_tail_metadata_trim_end",
                    heuristic_name="tail_metadata_trim_end",
                    rank=1,
                    start_index=1,
                    end_index_exclusive=13,
                    start_page_index=0,
                    end_page_index=1,
                    n_lines=12,
                    body_char_count=900,
                    contains_next_confirmed_header=False,
                    contains_soft_boundary=False,
                    contains_tail_metadata=True,
                    confidence_class="medium",
                    rationale="Overshoot span reaches the disclosure line.",
                )
            ],
            overshoot_candidate_id="cand_01_tail_metadata_trim_end",
            baseline_candidate_id="cand_01_tail_metadata_trim_end",
            proceedings_signals={"proceedings_detected": True},
            upstream_match_metadata={
                "trim_method": "llm_validated_proceedings_trim",
                "trim_mode": "llm_validated_proceedings_trim",
                "title_score": 0.95,
                "author_score": 0.60,
                "match_score": 0.86,
                "end_rule": "tail_metadata_trim_end",
                "matched_end_index_exclusive": 13,
                "matched_end_page_index": 1,
                "body_signal_count": 4,
                "header_only_flag": False,
                "spillover_flag": False,
                "index_detected": False,
                "index_confidence": 0.0,
                "index_listed_page": "",
                "index_prev_code": "",
                "index_next_code": "",
                "page_map_method": "",
                "estimated_offset": 0.0,
                "offset_confidence": 0.0,
                "fallback_triggered": False,
                "candidate_quality_status": "trimmed_auto",
                "candidate_quality_reason": "Looks valid.",
            },
        )
        source_lines = self.validate_llm.flatten_lines(record)
        decision = self.trim_llm.LLMDecision(
            decision_type="line_within_overshoot",
            selected_candidate_id="cand_01_tail_metadata_trim_end",
            last_abstract_line_global_index=6,
            confidence="high",
            end_reason="metadata_starts",
            explanation_short="The page footer looked like metadata.",
        )

        passed, reason = self.trim_llm.validate_llm_decision(package, decision, source_lines)

        self.assertFalse(passed)
        self.assertEqual(reason, "overshoot_contains_resumed_body_after_page_noise")

    def test_parse_llm_decision_resolves_short_candidate_alias(self) -> None:
        record = self.make_source_record()
        source_path = self.write_source_record(record)
        package = self.make_package(source_path)
        source_lines = self.validate_llm.flatten_lines(record)

        decision = self.trim_llm.parse_llm_decision(
            package,
            {
                "decision_type": "candidate_exact",
                "selected_candidate_id": "cand_01",
                "last_abstract_line_number": None,
                "confidence": "high",
                "end_reason": "candidate_is_exact",
                "explanation_short": "Candidate 01 is already exact.",
            },
            source_lines,
        )

        self.assertEqual(decision.selected_candidate_id, "cand_01_current_selected_end")
        self.assertEqual(decision.last_abstract_line_global_index, 8)

    def test_validate_llm_decision_allows_next_abstract_header_in_remainder(self) -> None:
        record = {
            "paper_id": "2003",
            "source_filename": "2003.pdf",
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": "\n".join(
                        [
                            "P06.173",
                            "A STIFF WOMAN",
                            "Fnu Srinithya; Saikrishna Gadde. Example Hospital, Birmingham, AL",
                            "BACKGROUND: A 37 year old woman developed progressive stiffness and painful spasms.",
                            "METHODS: The patient underwent extensive testing before the final diagnosis.",
                            "RESULTS: She improved after immunotherapy and benzodiazepines.",
                            "RESULTS: Repeat electrophysiology showed reduced continuous motor unit activity.",
                            "RESULTS: Early inpatient rehabilitation restored transfers and supported gait recovery.",
                            "CONCLUSIONS: Early recognition supported durable recovery.",
                            "Disclosure: Nothing to disclose.",
                            "16 Short Communications",
                            "© 2008 EFNS European Journal of Neurology 15 (Suppl. 3), 9-30",
                            "Downloaded from https://onlinelibrary.wiley.com/",
                            "P06.174",
                            "A STROKE OF LUCK",
                            "Shruti Rao; Thomas Wong. Another Hospital, San Francisco, CA",
                            "CASE: Another unrelated case begins here.",
                        ]
                    ),
                }
            ],
        }
        source_path = self.write_source_record(record)
        package = self.trim_llm.CandidatePackage(
            paper_id="2003",
            source_text_json_path=str(source_path),
            reference_title="A stiff woman",
            reference_authors="Srinithya, F; Gadde, S",
            matched_start_index=0,
            matched_start_page_index=0,
            matched_block_code="P06.173",
            matched_block_title="A STIFF WOMAN",
            start_rule="matched_header_start",
            candidate_generation_mode=self.trim_llm.CANDIDATE_GENERATION_MODE,
            candidates=[
                self.trim_llm.EndCandidate(
                    candidate_id="cand_01_current_selected_end",
                    heuristic_name="current_selected_end",
                    rank=1,
                    start_index=0,
                    end_index_exclusive=10,
                    start_page_index=0,
                    end_page_index=0,
                    n_lines=10,
                    body_char_count=700,
                    contains_next_confirmed_header=False,
                    contains_soft_boundary=False,
                    contains_tail_metadata=True,
                    confidence_class="strict",
                    rationale="Baseline candidate.",
                ),
                self.trim_llm.EndCandidate(
                    candidate_id="cand_02_tail_metadata_trim_end",
                    heuristic_name="tail_metadata_trim_end",
                    rank=2,
                    start_index=0,
                    end_index_exclusive=17,
                    start_page_index=0,
                    end_page_index=0,
                    n_lines=17,
                    body_char_count=950,
                    contains_next_confirmed_header=True,
                    contains_soft_boundary=False,
                    contains_tail_metadata=False,
                    confidence_class="medium",
                    rationale="Overshoot candidate including the next abstract header.",
                ),
            ],
            overshoot_candidate_id="cand_02_tail_metadata_trim_end",
            baseline_candidate_id="cand_01_current_selected_end",
            proceedings_signals={"proceedings_detected": True},
            upstream_match_metadata={
                "trim_method": "llm_validated_proceedings_trim",
                "trim_mode": "llm_validated_proceedings_trim",
                "title_score": 0.95,
                "author_score": 0.60,
                "match_score": 0.86,
                "end_rule": "current_selected_end",
                "matched_end_index_exclusive": 8,
                "matched_end_page_index": 0,
                "body_signal_count": 4,
                "header_only_flag": False,
                "spillover_flag": False,
                "index_detected": False,
                "index_confidence": 0.0,
                "index_listed_page": "",
                "index_prev_code": "",
                "index_next_code": "",
                "page_map_method": "",
                "estimated_offset": 0.0,
                "offset_confidence": 0.0,
                "fallback_triggered": False,
                "candidate_quality_status": "trimmed_auto",
                "candidate_quality_reason": "Looks valid.",
            },
        )
        source_lines = self.validate_llm.flatten_lines(record)
        decision = self.trim_llm.LLMDecision(
            decision_type="line_within_overshoot",
            selected_candidate_id="cand_02_tail_metadata_trim_end",
            last_abstract_line_global_index=9,
            confidence="high",
            end_reason="next_header_starts",
            explanation_short="The next abstract begins at P06.174, so the disclosure line is the true end.",
        )

        passed, reason = self.trim_llm.validate_llm_decision(package, decision, source_lines)

        self.assertTrue(passed)
        self.assertEqual(reason, "ok")

    def test_tail_metadata_trim_end_stops_at_references_heading(self) -> None:
        lines = [
            self.trim_llm.LineRef(global_index=20, page_index=0, line_index=0, text="Poster 96"),
            self.trim_llm.LineRef(global_index=21, page_index=0, line_index=1, text="Autoantibodies against glycine-associated synaptic proteins"),
            self.trim_llm.LineRef(global_index=22, page_index=0, line_index=2, text="Author line"),
            self.trim_llm.LineRef(global_index=23, page_index=0, line_index=3, text="Background: The glycine receptor was presumed an autoantibody target."),
            self.trim_llm.LineRef(global_index=24, page_index=0, line_index=4, text="Methods: HEK293 cells expressing recombinant proteins were analysed."),
            self.trim_llm.LineRef(global_index=25, page_index=0, line_index=5, text="Results: Antibodies were found in several patients."),
            self.trim_llm.LineRef(global_index=26, page_index=0, line_index=6, text="Conclusions: This extends the glycinergic autoantibody spectrum."),
            self.trim_llm.LineRef(global_index=27, page_index=1, line_index=0, text="References"),
            self.trim_llm.LineRef(global_index=28, page_index=1, line_index=1, text="[1] Hutchinson, M., Waters, P., McHugh, J., et al., 2008]."),
            self.trim_llm.LineRef(global_index=29, page_index=1, line_index=2, text="doi:10.1016/j.jneuroim.2014.08.060"),
        ]

        trimmed_end = self.trim_llm._tail_metadata_trim_end(lines, 20, 30)

        self.assertEqual(trimmed_end, 27)

    def test_tail_metadata_trim_end_stops_at_inline_references_heading(self) -> None:
        lines = [
            self.trim_llm.LineRef(global_index=40, page_index=0, line_index=0, text="Poster 339"),
            self.trim_llm.LineRef(global_index=41, page_index=0, line_index=1, text="Rapid Onset Stiff Person Syndrome"),
            self.trim_llm.LineRef(global_index=42, page_index=0, line_index=2, text="Author line"),
            self.trim_llm.LineRef(global_index=43, page_index=0, line_index=3, text="Introduction: SPS may present abruptly in rare cases."),
            self.trim_llm.LineRef(global_index=44, page_index=0, line_index=4, text="Case: The patient improved with benzodiazepines and IVIG."),
            self.trim_llm.LineRef(global_index=45, page_index=0, line_index=5, text="Conclusion: SPS should remain in the differential diagnosis."),
            self.trim_llm.LineRef(global_index=46, page_index=0, line_index=6, text="References: 1. Hadavi, S., Noyce, A.J., Leslie, R.D., & Giovannoni, G."),
            self.trim_llm.LineRef(global_index=47, page_index=0, line_index=7, text="Other: Rare disease"),
            self.trim_llm.LineRef(global_index=48, page_index=0, line_index=8, text="340"),
        ]

        trimmed_end = self.trim_llm._tail_metadata_trim_end(lines, 40, 49)

        self.assertEqual(trimmed_end, 46)

    def test_tail_metadata_trim_end_stops_at_footer_metadata_lines(self) -> None:
        lines = [
            self.trim_llm.LineRef(global_index=70, page_index=0, line_index=0, text="307"),
            self.trim_llm.LineRef(global_index=71, page_index=0, line_index=1, text="Stiff-person syndrome - a 15-year review at a tertiary hospital"),
            self.trim_llm.LineRef(global_index=72, page_index=0, line_index=2, text="Authors"),
            self.trim_llm.LineRef(global_index=73, page_index=0, line_index=3, text="Objective: Clinical characterization of stiff-person syndrome."),
            self.trim_llm.LineRef(global_index=74, page_index=0, line_index=4, text="Results: Four patients were identified over 15 years."),
            self.trim_llm.LineRef(global_index=75, page_index=0, line_index=5, text="Conclusions: Prompt diagnosis allows treatment."),
            self.trim_llm.LineRef(global_index=76, page_index=0, line_index=6, text="Movement Disorders, Vol. 36, Suppl. 1,"),
            self.trim_llm.LineRef(global_index=77, page_index=0, line_index=7, text="S132 ABSTRACTS"),
            self.trim_llm.LineRef(global_index=78, page_index=0, line_index=8, text="Downloaded from https://movementdisorders.onlinelibrary.wiley.com/"),
        ]

        trimmed_end = self.trim_llm._tail_metadata_trim_end(lines, 70, 79)

        self.assertEqual(trimmed_end, 76)

    def test_process_candidate_package_uses_reference_metadata_for_final_registry(self) -> None:
        record = self.make_source_record()
        source_path = self.write_source_record(record)
        package = self.make_package(source_path)
        candidate_path = self.tmp_path / "candidate.json"
        self.trim_llm.write_candidate_package(package, candidate_path)
        decision = self.trim_llm.LLMDecision(
            decision_type="candidate_exact",
            selected_candidate_id="cand_01_current_selected_end",
            last_abstract_line_global_index=8,
            confidence="high",
            end_reason="candidate_is_exact",
            explanation_short="The baseline candidate is exact.",
        )
        args = types.SimpleNamespace(
            output_dir=self.tmp_path / "trimmed",
            dry_run=False,
            llm_mode="all",
            openai_model="gpt-5-mini",
            prompt_version="proceedings_llm_trim_prompt_v1",
        )

        with mock.patch.object(self.validate_llm, "call_llm_for_end_decision", return_value=decision):
            row = self.validate_llm.process_candidate_package(
                candidate_path,
                reference_rows={
                    "2001": {
                        "Covidence": "COV-2001",
                        "Title": "Reference title from registry",
                        "Authors": "Registry Authors",
                    }
                },
                override_rows={},
                client=object(),
                args=args,
            )

        self.assertEqual(row["covidence_id"], "COV-2001")
        self.assertEqual(row["title"], "Reference title from registry")
        self.assertEqual(row["authors"], "Registry Authors")
        self.assertEqual(row["trim_status"], "trimmed_auto_llm_candidate_exact")
        self.assertEqual(row["llm_selected_candidate_id"], "cand_01_current_selected_end")
        self.assertTrue((args.output_dir / "2001.json").exists())

    def test_process_candidate_package_falls_back_after_invalid_llm_decision(self) -> None:
        record = self.make_source_record()
        source_path = self.write_source_record(record)
        package = self.make_package(source_path)
        candidate_path = self.tmp_path / "candidate.json"
        self.trim_llm.write_candidate_package(package, candidate_path)
        invalid_decision = self.trim_llm.LLMDecision(
            decision_type="line_within_overshoot",
            selected_candidate_id="cand_02_next_confirmed_header_end",
            last_abstract_line_global_index=25,
            confidence="low",
            end_reason="other",
            explanation_short="Invalid line chosen for testing fallback.",
        )
        args = types.SimpleNamespace(
            output_dir=self.tmp_path / "trimmed",
            dry_run=False,
            llm_mode="all",
            openai_model="gpt-5-mini",
            prompt_version="proceedings_llm_trim_prompt_v1",
        )

        with mock.patch.object(self.validate_llm, "call_llm_for_end_decision", return_value=invalid_decision):
            row = self.validate_llm.process_candidate_package(
                candidate_path,
                reference_rows={
                    "2001": {
                        "Covidence": "COV-2001",
                        "Title": "Reference title from registry",
                        "Authors": "Registry Authors",
                    }
                },
                override_rows={},
                client=object(),
                args=args,
            )

        self.assertEqual(row["trim_status"], "trimmed_auto_llm_fallback_heuristic")
        self.assertEqual(row["heuristic_fallback_used"], "true")
        self.assertEqual(row["llm_validation_passed"], "false")
        self.assertEqual(row["llm_validation_reason"], "final_end_exceeds_overshoot")
        self.assertTrue((args.output_dir / "2001.json").exists())


if __name__ == "__main__":
    unittest.main()
