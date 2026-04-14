from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "validation" / "validate_pdf_source_registry.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_pdf_source_registry", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestValidatePdfSourceRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.text_dir = self.tmp_path / "text"
        self.text_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_text_json(self, paper_id: str, *, title_line: str, body: str, ocr_applied: bool = False) -> Path:
        path = self.text_dir / f"{paper_id}.json"
        payload = {
            "paper_id": paper_id,
            "source_filename": f"{paper_id}.pdf",
            "ocr_applied": ocr_applied,
            "pages": [
                {
                    "page_index": 0,
                    "text": f"{title_line}\n{body}",
                }
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_validate_row_confirms_exact_match_from_text_json(self) -> None:
        self.write_text_json(
            "123",
            title_line="Stiff-person syndrome: a case report.",
            body="Steve Egwuonwu and Fernando Chedebeau described the 2010 case.",
            ocr_applied=True,
        )
        row = {
            "covidence_id": "123",
            "ref": "R1",
            "study": "Egwuonwu 2010",
            "title": "Stiff-person syndrome: a case report.",
            "authors": "Egwuonwu, Steve; Chedebeau, Fernando",
            "published_year": "2010",
            "pdf_filename": "123_example.pdf",
            "pdf_path_relative": "data\\pdf_original\\123_example.pdf",
            "download_status": "downloaded",
            "manifest_status": "downloaded",
        }

        result = self.module.validate_row(
            row,
            text_dir=self.text_dir,
            title_overlap_threshold=0.75,
        )

        self.assertEqual(result["validation_status"], "confirmed_exact")
        self.assertEqual(result["content_source"], "text_json")
        self.assertTrue(result["ocr_applied"])
        self.assertEqual(result["title_exact_pages"], [0])
        self.assertEqual(result["author_match_pages"], [0])
        self.assertEqual(result["year_match_pages"], [0])

    def test_validation_status_confirms_fuzzy_title_with_author_match(self) -> None:
        status = self.module.validation_status_for(
            title_exact_pages=[],
            fuzzy_title_author_pages=[0],
            best_title_overlap=0.91,
            author_pages=[0],
            year_pages=[0],
            threshold=0.75,
        )
        self.assertEqual(status, "confirmed_fuzzy_title")

    def test_first_author_surname_tokens_handles_compound_and_initial_styles(self) -> None:
        self.assertEqual(
            self.module.first_author_surname_tokens("Gresa-Arribas N.; Arino H."),
            ["arribas", "gresa"],
        )
        self.assertEqual(
            self.module.first_author_surname_tokens("Nguyen PM; Vu DD; Vu KD"),
            ["nguyen"],
        )

    def test_load_text_pages_resolves_legacy_relative_pdf_paths(self) -> None:
        pdf_path = self.tmp_path / "data" / "pdf_original" / "123_example.pdf"
        pdf_path.parent.mkdir(parents=True)
        pdf_path.write_bytes(b"%PDF-1.4\n")
        row = {
            "covidence_id": "123",
            "pdf_path_relative": "data\\pdf_original\\123_example.pdf",
            "pdf_path_absolute": "C:\\Projects\\sps-review\\data\\pdf_original\\123_example.pdf",
        }

        expected_pages = [{"page_index": 0, "text": "PDF text"}]
        expected_metadata = {
            "content_source": "pdf_direct",
            "text_json_path": "",
            "ocr_applied": False,
            "source_filename": "123_example.pdf",
        }
        with patch.object(self.module, "REPO_ROOT", self.tmp_path):
            with patch.object(
                self.module,
                "load_pdf_pages",
                return_value=(expected_pages, expected_metadata),
            ) as load_pdf_pages:
                pages, metadata = self.module.load_text_pages(row, text_dir=self.text_dir)

        self.assertEqual(pages, expected_pages)
        self.assertEqual(metadata, expected_metadata)
        load_pdf_pages.assert_called_once_with(pdf_path)

    def test_eligible_rows_accepts_existing_relative_pdf_when_absolute_path_is_stale(self) -> None:
        pdf_path = self.tmp_path / "data" / "pdf_original" / "123_example.pdf"
        pdf_path.parent.mkdir(parents=True)
        pdf_path.write_bytes(b"%PDF-1.4\n")
        row = {
            "covidence_id": "123",
            "download_status": "downloaded",
            "local_file_count": "1",
            "pdf_path_relative": "data\\pdf_original\\123_example.pdf",
            "pdf_path_absolute": "C:\\Projects\\sps-review\\data\\pdf_original\\123_example.pdf",
        }
        args = Namespace(
            paper_id=[],
            download_status="downloaded",
            text_dir=self.text_dir,
        )

        with patch.object(self.module, "REPO_ROOT", self.tmp_path):
            filtered_rows = self.module.eligible_rows([row], args)

        self.assertEqual(filtered_rows, [row])


if __name__ == "__main__":
    unittest.main()
