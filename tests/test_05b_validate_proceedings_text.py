from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
