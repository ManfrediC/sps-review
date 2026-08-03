from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "validation" / "build_single_case_clean_collection.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_single_case_clean_collection", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestBuildSingleCaseCleanCollection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_targeted_registry_merge_preserves_unselected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "canonical_registry.csv"
            with registry_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "title"])
                writer.writeheader()
                for paper_id in range(1, 477):
                    writer.writerow({"paper_id": str(paper_id), "title": f"Original {paper_id}"})

            updates = [
                {"paper_id": "1", "title": "Updated 1"},
                {"paper_id": "476", "title": "Updated 476"},
            ]
            merged = self.module.merge_targeted_registry_rows(
                registry_path,
                updates,
                {"1", "476"},
            )

        by_id = {row["paper_id"]: row for row in merged}
        self.assertEqual(len(merged), 476)
        self.assertEqual(by_id["1"]["title"], "Updated 1")
        self.assertEqual(by_id["2"]["title"], "Original 2")
        self.assertEqual(by_id["476"]["title"], "Updated 476")

    def test_canonical_pdf_has_highest_candidate_preference(self) -> None:
        candidate = self.module.PdfCandidate(
            paper_id="193",
            kind="canonical",
            path=Path("193.pdf"),
            sha256="example",
            page_count=2,
            text="",
            text_char_count=0,
        )

        self.assertGreater(
            self.module.candidate_preference(candidate),
            self.module.candidate_preference(
                self.module.PdfCandidate(
                    paper_id="193",
                    kind="acquired",
                    path=Path("193-acquired.pdf"),
                    sha256="other",
                    page_count=2,
                    text="",
                    text_char_count=0,
                )
            ),
        )

    def test_recovered_source_id_is_pinned_to_canonical_candidate(self) -> None:
        canonical = self.module.PdfCandidate(
            paper_id="6012",
            kind="canonical",
            path=Path("canonical.pdf"),
            sha256="canonical",
            page_count=2,
            text="Paraneoplastic encephalomyelitis pancreatic tumor Hernandez 2006",
            text_char_count=68,
        )
        legacy = self.module.PdfCandidate(
            paper_id="6012",
            kind="primary",
            path=Path("legacy.pdf"),
            sha256="legacy",
            page_count=7,
            text=(
                "Paraneoplastic encephalomyelitis pancreatic tumor Hernandez 2006 "
                "10.1212/01.wnl.0000196488.87746.7b"
            ),
            text_char_count=105,
        )
        reference = {
            "Title": "Paraneoplastic encephalomyelitis pancreatic tumor",
            "Authors": "Hernandez, L.",
            "Published Year": "2006",
            "DOI": "10.1212/01.wnl.0000196488.87746.7b",
        }

        selected, _ = self.module.select_candidate([legacy, canonical], reference)

        self.assertEqual(selected, canonical)


if __name__ == "__main__":
    unittest.main()
