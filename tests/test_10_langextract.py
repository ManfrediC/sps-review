from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "10_langextract.py"


def load_module():
    pipeline_dir = str(SCRIPT_PATH.parent)
    if pipeline_dir not in sys.path:
        sys.path.insert(0, pipeline_dir)
    spec = importlib.util.spec_from_file_location("langextract_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLangExtractRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.input_dir = self.tmp_path / "text"
        self.raw_out_dir = self.tmp_path / "langextract_raw"
        self.summary_out_dir = self.tmp_path / "summary"
        self.input_dir.mkdir()
        self.raw_out_dir.mkdir()
        self.summary_out_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_process_file_skips_incorrect_reference_without_writing_outputs(self) -> None:
        module = self.module
        input_path = self.input_dir / "1841.json"
        input_path.write_text(
            json.dumps(
                {
                    "paper_id": "1841",
                    "source_filename": "1841_wrong.pdf",
                    "pages": [{"page_index": 0, "text": "Wrong attached PDF text."}],
                }
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(
            raw_out_dir=self.raw_out_dir,
            summary_out_dir=self.summary_out_dir,
            force=False,
            ignore_routing=False,
            include_individual=False,
            include_group=False,
            dry_run=False,
            model_id="gpt-4.1-mini",
            api_key=None,
            temperature=0.0,
            max_char_buffer=1200,
            batch_length=8,
            max_workers=4,
            extraction_passes=2,
        )

        outcome = module.process_file(
            path=input_path,
            args=args,
            prompt_assets={},
            heuristic_rows={},
            manual_rows={
                "1841": {
                    "final_source_category": "unclear_manual_review",
                    "final_source_subtype": "incorrect_reference",
                    "review_decision_notes": "Attached PDF resolves to another paper.",
                    "pdf_content_alignment_tag": "incorrect_reference",
                }
            },
        )

        self.assertEqual(outcome, "skipped_incorrect_reference")
        self.assertFalse((self.raw_out_dir / "1841.json").exists())
        self.assertFalse((self.summary_out_dir / "1841.json").exists())


if __name__ == "__main__":
    unittest.main()
