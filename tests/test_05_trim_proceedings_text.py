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


if __name__ == "__main__":
    unittest.main()
