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


if __name__ == "__main__":
    unittest.main()
