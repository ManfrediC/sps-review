from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_XML import core  # noqa: E402


REVIEWED_DIR = (
    REPO_ROOT
    / "qa"
    / "validation"
    / "stage07_xml"
    / "gold_standard"
    / "stage07_xml_live_test10_20260425"
    / "reviewed_annotations"
)


class TestStage07XmlGoldRegression(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.output_paths = core.output_paths(self.tmp_path / "stage07_xml")
        core.ensure_output_dirs(self.output_paths)
        self.source_rows = core.load_csv_rows_by_id(core.SOURCE_CATEGORISATION_PATH, "paper_id")
        self.manual_rows = core.load_csv_rows_by_id(core.SOURCE_MANUAL_REVIEW_PATH, "paper_id")
        self.stage06_rows = core.load_csv_rows_by_id(core.SOURCE_CASE_COUNT_PATH, "paper_id")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_reviewed(self, paper_id: str) -> core.ProcessResult:
        prior = core.parse_stage06_prior(self.stage06_rows.get(paper_id, {}))
        source_path = core.resolve_source_json_path(
            paper_id=paper_id,
            source_row=self.source_rows.get(paper_id, {}),
            stage06_prior=prior,
        )
        prepared = core.prepare_source(paper_id=paper_id, source_path=source_path)
        reviewed_payload = json.loads((REVIEWED_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
        annotation = core.compile_reviewed_annotation_payload(
            reviewed_payload=reviewed_payload,
            prepared_source=prepared,
        )
        return core.process_paper(
            paper_id=paper_id,
            source_row=self.source_rows.get(paper_id, {}),
            manual_row=self.manual_rows.get(paper_id, {}),
            stage06_row=self.stage06_rows.get(paper_id, {}),
            paths=self.output_paths,
            manifest_run_id="stage07_xml_gold_regression",
            annotation_model="gpt-5.5",
            annotation_payload=annotation,
        )

    def assert_ready(self, result: core.ProcessResult, target_ids: set[str], route: str) -> None:
        self.assertEqual(result.registry_row["route_mode"], route)
        self.assertEqual(set(result.target_view_payloads), target_ids)
        self.assertEqual(result.registry_row["ready_for_langextract"], "true")
        self.assertEqual(result.validation_payload["roundtrip_status"], "passed")
        self.assertEqual(result.validation_payload["status"], "passed")

    def test_reviewed_gold_batch_matches_feedback(self) -> None:
        paper10 = self.run_reviewed("10")
        self.assert_ready(paper10, {"p1", "p2"}, "individual_case_split")
        self.assertIn("A 63-year-old Hispanic woman", paper10.target_view_payloads["p1"]["input_text"])
        self.assertIn("A 53-year-old black man", paper10.target_view_payloads["p2"]["input_text"])
        self.assertIn("Both fulfill the diagnostic criteria", paper10.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("TABLE 1", paper10.target_view_payloads["p1"]["input_text"])

        paper11 = self.run_reviewed("11")
        self.assert_ready(paper11, {"g1"}, "group")
        self.assertIn("cases 8, 9, and 10", paper11.target_view_payloads["g1"]["input_text"])
        self.assertIn("Stiff-person", paper11.target_view_payloads["g1"]["input_text"])
        self.assertNotIn("Postanoxic", paper11.target_view_payloads["g1"]["input_text"])

        paper17 = self.run_reviewed("17")
        self.assert_ready(paper17, {"p1"}, "individual")
        self.assertIn("CasePresentation", paper17.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("Rapid #", paper17.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("TheCaseinContext", paper17.target_view_payloads["p1"]["input_text"])

        paper19 = self.run_reviewed("19")
        self.assert_ready(paper19, {"p1", "p2"}, "individual_case_split")
        self.assertIn("Case 1. A 46-", paper19.target_view_payloads["p1"]["input_text"])
        self.assertIn("Case 2. A 25-year-old", paper19.target_view_payloads["p2"]["input_text"])
        self.assertIn("Both cases fulfill", paper19.target_view_payloads["p1"]["input_text"])
        self.assertIn("patient 2 did not", paper19.target_view_payloads["p2"]["input_text"])

        paper22 = self.run_reviewed("22")
        self.assert_ready(paper22, {"p1"}, "individual")
        self.assertIn("Case 10", paper22.target_view_payloads["p1"]["input_text"])
        self.assertIn("Stiff-person syndrome 4,800", paper22.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("clinical rating score did not change", paper22.target_view_payloads["p1"]["input_text"])

        paper23 = self.run_reviewed("23")
        self.assert_ready(paper23, {"p1", "p2"}, "individual_case_split")
        self.assertIn("Patient 1. A 42-year", paper23.target_view_payloads["p1"]["input_text"])
        self.assertIn("Patient 2. A 68-year-old", paper23.target_view_payloads["p2"]["input_text"])
        self.assertIn("Both patients meet the criterion", paper23.target_view_payloads["p1"]["input_text"])

        paper25 = self.run_reviewed("25")
        self.assert_ready(paper25, {"g1"}, "group")
        self.assertIn("autoantibodies of 30", paper25.target_view_payloads["g1"]["input_text"])
        self.assertIn("30 of the 72 GAD-Abs positive SMS sera", paper25.target_view_payloads["g1"]["input_text"])
        self.assertNotIn("Purification of Rat Brain GAD", paper25.target_view_payloads["g1"]["input_text"])

        paper29 = self.run_reviewed("29")
        self.assert_ready(paper29, {"p1"}, "individual")
        self.assertIn("Following several months of low back pain", paper29.target_view_payloads["p1"]["input_text"])
        self.assertIn("The patient was a 36-year-old right-handed black man", paper29.target_view_payloads["p1"]["input_text"])
        self.assertIn("The decreased tone of uninjected thigh muscles", paper29.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("Address correspondence", paper29.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("REFERENCES", paper29.target_view_payloads["p1"]["input_text"])

        paper30 = self.run_reviewed("30")
        self.assert_ready(paper30, {"p1", "p2", "p3"}, "individual_case_split")
        self.assertIn("Patient | has been described previously", paper30.target_view_payloads["p1"]["input_text"])
        self.assertIn("A 76-year-old woman began", paper30.target_view_payloads["p2"]["input_text"])
        self.assertIn("A 66-year-old woman began", paper30.target_view_payloads["p3"]["input_text"])
        self.assertIn("In none of the patients", paper30.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("A 76-year-old woman began", paper30.target_view_payloads["p1"]["input_text"])
        self.assertNotIn("Downloaded from nejm.org", paper30.target_view_payloads["p3"]["input_text"])

        paper34 = self.run_reviewed("34")
        self.assert_ready(paper34, {"p1", "p2"}, "individual_case_split")
        self.assertEqual(paper34.registry_row["stage06_diverged"], "true")
        self.assertIn("Patient Be. A 37-year-old man", paper34.target_view_payloads["p1"]["input_text"])
        self.assertIn("Abnormal visual evoked potentials", paper34.target_view_payloads["p1"]["input_text"])
        self.assertIn("tinued, the patient was admitted", paper34.target_view_payloads["p1"]["input_text"])
        self.assertIn("Patient Rm. A published abstractlo", paper34.target_view_payloads["p2"]["input_text"])
        self.assertNotIn("Patient Rm. A published abstractlo", paper34.target_view_payloads["p1"]["input_text"])


if __name__ == "__main__":
    unittest.main()
