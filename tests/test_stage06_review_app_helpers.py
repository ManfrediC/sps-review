from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.validation.review_stage06_count_app import load_review_rows_from_runs


class TestStage06ReviewAppHelpers(unittest.TestCase):
    def test_load_review_rows_from_runs_keeps_latest_run_per_paper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            older = root / "stage06_old"
            newer = root / "stage06_new"
            for run_dir, title in ((older, "Older title"), (newer, "Newer title")):
                (run_dir / "results").mkdir(parents=True)
                (run_dir / "results" / "711.json").write_text(
                    (
                        '{"paper_id":"711","count_row":{"paper_id":"711","title":"%s","likely_sps_case_count":"9",'
                        '"count_verification_status":"llm_candidate_exact"}}'
                    )
                    % title,
                    encoding="utf-8",
                )

            rows = load_review_rows_from_runs((str(newer), str(older)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["paper_id"], "711")
        self.assertEqual(rows[0]["title"], "Newer title")
        self.assertEqual(rows[0]["run_id"], "stage06_new")


if __name__ == "__main__":
    unittest.main()
