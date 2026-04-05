from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "11_quality_assessment.py"


def load_module():
    pipeline_dir = str(SCRIPT_PATH.parent)
    if pipeline_dir not in sys.path:
        sys.path.insert(0, pipeline_dir)
    spec = importlib.util.spec_from_file_location("quality_assessment_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestQualityAssessment(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.input_dir = self.tmp_path / "text"
        self.raw_out_dir = self.tmp_path / "quality_raw"
        self.record_out_dir = self.tmp_path / "quality_records"
        self.input_dir.mkdir()
        self.raw_out_dir.mkdir()
        self.record_out_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_process_file_skips_incorrect_reference_without_writing_outputs(self) -> None:
        module = self.module
        input_path = self.input_dir / "263.json"
        input_path.write_text(
            json.dumps(
                {
                    "paper_id": "263",
                    "source_filename": "263_wrong.pdf",
                    "pages": [{"page_index": 0, "text": "Wrong attached PDF text."}],
                }
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(
            raw_out_dir=self.raw_out_dir,
            record_out_dir=self.record_out_dir,
            force=False,
            dry_run=False,
            publication_type="",
            model_id="gpt-4.1-mini",
            skip_schema_validation=False,
        )

        outcome = module.process_file(
            path=input_path,
            args=args,
            quality_dict={},
            publication_types=[],
            schema=None,
            prompt_assets={},
            heuristic_rows={},
            manual_rows={
                "263": {
                    "final_source_category": "unclear_manual_review",
                    "final_source_subtype": "incorrect_reference",
                    "review_decision_notes": "Attached PDF belongs to another paper.",
                    "pdf_content_alignment_tag": "incorrect_reference",
                }
            },
        )

        self.assertEqual(outcome, "skipped_incorrect_reference")
        self.assertFalse((self.raw_out_dir / "263.json").exists())
        self.assertFalse((self.record_out_dir / "263.json").exists())


if __name__ == "__main__":
    unittest.main()
