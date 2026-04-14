from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "02_build_pdf_source_registry.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pdf_source_registry", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_references_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "Covidence",
        "Ref",
        "Study",
        "Title",
        "Authors",
        "Published Year",
        "Journal",
        "DOI",
        "Tags",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def make_args(references_csv: Path, pdf_dir: Path, manifest_path: Path, output_path: Path):
    return argparse.Namespace(
        references_csv=references_csv,
        pdf_dir=pdf_dir,
        manifest_path=manifest_path,
        output_path=output_path,
        queue_output_path=output_path.with_name("pdf_acquisition_queue.csv"),
    )


class TestBuildPdfSourceRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.references_csv = self.tmp_path / "refs.csv"
        self.pdf_dir = self.tmp_path / "pdfs"
        self.manifest_path = self.tmp_path / "manifest.jsonl"
        self.output_path = self.tmp_path / "out.csv"
        self.pdf_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def default_reference(self, covidence_id: str = "123") -> dict[str, str]:
        return {
            "Covidence": covidence_id,
            "Ref": f"R{covidence_id}",
            "Study": f"S{covidence_id}",
            "Title": "Alpha Study" if covidence_id == "123" else f"Study {covidence_id}",
            "Authors": "Smith J" if covidence_id == "123" else "Jones P",
            "Published Year": "2020" if covidence_id == "123" else "2021",
            "Journal": "Neurology",
            "DOI": "10.1000/example",
            "Tags": "screened",
        }

    def build_rows(
        self,
        *,
        reference_rows: list[dict[str, str]],
        manifest_rows: list[dict],
    ) -> list[dict[str, str]]:
        write_references_csv(self.references_csv, reference_rows)
        write_manifest_jsonl(self.manifest_path, manifest_rows)
        args = make_args(self.references_csv, self.pdf_dir, self.manifest_path, self.output_path)
        return self.module.build_registry(args)

    def test_basic_match_missing_and_orphan_pdf(self) -> None:
        write_references_csv(
            self.references_csv,
            [
                self.default_reference("123"),
                {
                    **self.default_reference("456"),
                    "Title": "Beta Study",
                    "Authors": "Jones P",
                    "Published Year": "2021",
                },
            ],
        )
        write_manifest_jsonl(
            self.manifest_path,
            [
                {
                    "covidence_id": "123",
                    "status": "downloaded",
                    "card_publication_title": "Alpha Study",
                    "card_authors_full": "Smith J",
                    "card_year": "2020",
                }
            ],
        )
        (self.pdf_dir / "123_alpha.pdf").touch()
        (self.pdf_dir / "999_orphan.pdf").touch()
        rows = self.module.build_registry(
            make_args(self.references_csv, self.pdf_dir, self.manifest_path, self.output_path)
        )

        self.assertEqual(len(rows), 3)

        matched = next(row for row in rows if row["covidence_id"] == "123")
        self.assertEqual(matched["download_status"], "downloaded")
        self.assertEqual(matched["local_file_count"], "1")
        self.assertEqual(matched["card_title_matches_export"], "true")
        self.assertEqual(matched["card_authors_match_export"], "true")
        self.assertEqual(matched["card_year_matches_export"], "true")
        self.assertEqual(matched["pdf_filename"], "123_alpha.pdf")

        missing = next(row for row in rows if row["covidence_id"] == "456")
        self.assertEqual(missing["download_status"], "missing")
        self.assertEqual(missing["local_file_count"], "0")

        orphan = next(
            row
            for row in rows
            if row["covidence_id"] == "999" and row["download_status"] == "unmatched_local_file"
        )
        self.assertEqual(orphan["pdf_filename"], "999_orphan.pdf")

    def test_multiple_local_files_flagged_and_joined(self) -> None:
        write_references_csv(self.references_csv, [self.default_reference("123")])
        write_manifest_jsonl(self.manifest_path, [])
        (self.pdf_dir / "123_alpha.pdf").touch()
        (self.pdf_dir / "123_alpha_duplicate.pdf").touch()

        rows = self.module.build_registry(
            make_args(self.references_csv, self.pdf_dir, self.manifest_path, self.output_path)
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["covidence_id"], "123")
        self.assertEqual(row["local_file_count"], "2")
        self.assertEqual(row["download_status"], "multiple_local_files")
        self.assertEqual(row["pdf_filename"], "123_alpha.pdf | 123_alpha_duplicate.pdf")

    def test_missing_local_pdf_uses_manifest_status_and_metadata(self) -> None:
        rows = self.build_rows(
            reference_rows=[self.default_reference("123")],
            manifest_rows=[
                {
                    "covidence_id": "123",
                    "status": "paywalled",
                    "method": "manual",
                    "download_url": "https://example.org/paper.pdf",
                    "error": "403 Forbidden",
                }
            ],
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["download_status"], "paywalled")
        self.assertEqual(row["local_file_count"], "0")
        self.assertEqual(row["manifest_status"], "paywalled")
        self.assertEqual(row["download_method"], "manual")
        self.assertEqual(row["download_url"], "https://example.org/paper.pdf")
        self.assertEqual(row["manifest_error"], "403 Forbidden")

    def test_latest_manifest_row_wins_for_same_covidence_id(self) -> None:
        rows = self.build_rows(
            reference_rows=[self.default_reference("123")],
            manifest_rows=[
                {
                    "covidence_id": "123",
                    "status": "missing",
                    "card_publication_title": "Old Title",
                },
                {
                    "covidence_id": "123",
                    "status": "downloaded",
                    "card_publication_title": "Alpha Study",
                },
            ],
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["manifest_status"], "downloaded")
        self.assertEqual(row["card_publication_title"], "Alpha Study")

    def test_unmatched_filename_without_numeric_prefix_produces_orphan_row(self) -> None:
        write_references_csv(self.references_csv, [self.default_reference("123")])
        write_manifest_jsonl(self.manifest_path, [])
        (self.pdf_dir / "manual_upload.pdf").touch()

        rows = self.module.build_registry(
            make_args(self.references_csv, self.pdf_dir, self.manifest_path, self.output_path)
        )

        self.assertEqual(len(rows), 2)
        orphan = next(row for row in rows if row["download_status"] == "unmatched_local_file")
        self.assertEqual(orphan["covidence_id"], "")
        self.assertEqual(orphan["pdf_filename"], "manual_upload.pdf")
        self.assertEqual(orphan["local_file_count"], "1")

    def test_compare_flags_normalise_text_and_year(self) -> None:
        self.assertEqual(self.module.compare_text_flag("Alpha Study", "alpha study"), "true")
        self.assertEqual(self.module.compare_text_flag("Alpha-Study", "Alpha Study"), "true")
        self.assertEqual(self.module.compare_text_flag("Smith, J.", "smith j"), "true")
        self.assertEqual(self.module.compare_year_flag("2020", "2020"), "true")
        self.assertEqual(self.module.compare_year_flag("2020", "2021"), "false")

    def test_relative_to_repo_uses_forward_slashes(self) -> None:
        pdf_path = self.tmp_path / "data" / "pdf_original" / "123_alpha.pdf"
        pdf_path.parent.mkdir(parents=True)
        pdf_path.touch()

        with patch.object(self.module, "REPO_ROOT", self.tmp_path):
            relative = self.module.relative_to_repo(pdf_path)
            absolute = self.module.join_paths([pdf_path], absolute=True)

        self.assertEqual(relative, "data/pdf_original/123_alpha.pdf")
        self.assertEqual(absolute, f"{self.tmp_path.as_posix()}/data/pdf_original/123_alpha.pdf")

    def test_write_registry_writes_expected_header_and_rows(self) -> None:
        (self.pdf_dir / "123_alpha.pdf").touch()
        rows = self.build_rows(
            reference_rows=[self.default_reference("123")],
            manifest_rows=[],
        )

        self.module.write_registry(rows, self.output_path)

        with self.output_path.open(encoding="utf-8", newline="") as handle:
            header = handle.readline().strip()
        expected_header = ",".join(
            [
                "covidence_id",
                "ref",
                "study",
                "title",
                "authors",
                "published_year",
                "journal",
                "doi",
                "tags",
                "card_identifier_text",
                "card_first_author",
                "card_year",
                "card_authors_full",
                "card_publication_title",
                "card_title_matches_export",
                "card_authors_match_export",
                "card_year_matches_export",
                "pdf_filename",
                "pdf_path_relative",
                "pdf_path_absolute",
                "local_file_count",
                "download_status",
                "manifest_status",
                "download_method",
                "download_url",
                "manifest_error",
            ]
        )
        self.assertEqual(header, expected_header)

        written_rows = read_csv_rows(self.output_path)
        self.assertEqual(len(written_rows), 1)
        self.assertEqual(written_rows[0]["covidence_id"], "123")
        self.assertEqual(written_rows[0]["pdf_filename"], "123_alpha.pdf")

    def test_build_acquisition_queue_keeps_only_non_downloaded_reference_rows(self) -> None:
        rows = self.build_rows(
            reference_rows=[
                self.default_reference("123"),
                self.default_reference("456"),
                self.default_reference("789"),
            ],
            manifest_rows=[
                {"covidence_id": "123", "status": "failed", "error": "Timed out"},
                {"covidence_id": "456", "status": "downloaded"},
                {"covidence_id": "789", "status": "paywalled"},
            ],
        )
        queue_rows = self.module.build_acquisition_queue(rows)

        self.assertEqual([row["covidence_id"] for row in queue_rows], ["123", "789"])
        failed_row = next(row for row in queue_rows if row["covidence_id"] == "123")
        paywalled_row = next(row for row in queue_rows if row["covidence_id"] == "789")
        self.assertEqual(failed_row["queue_reason"], "No local PDF is present and the last download attempt failed.")
        self.assertEqual(paywalled_row["queue_reason"], "No local PDF is present and the source appears paywalled.")

    def test_write_acquisition_queue_writes_expected_rows(self) -> None:
        queue_path = self.tmp_path / "pdf_acquisition_queue.csv"
        queue_rows = [
            {
                "covidence_id": "123",
                "ref": "R123",
                "study": "S123",
                "title": "Alpha Study",
                "authors": "Smith J",
                "published_year": "2020",
                "journal": "Neurology",
                "doi": "10.1000/example",
                "tags": "screened",
                "download_status": "failed",
                "manifest_status": "failed",
                "download_method": "direct_fetch",
                "download_url": "https://example.org/alpha.pdf",
                "manifest_error": "Timed out",
                "queue_reason": "No local PDF is present and the last download attempt failed.",
            }
        ]

        self.module.write_acquisition_queue(queue_rows, queue_path)
        written_rows = read_csv_rows(queue_path)

        self.assertEqual(len(written_rows), 1)
        self.assertEqual(written_rows[0]["covidence_id"], "123")
        self.assertEqual(written_rows[0]["download_status"], "failed")

    def test_main_builds_and_writes_registry(self) -> None:
        write_references_csv(self.references_csv, [self.default_reference("123")])
        write_manifest_jsonl(self.manifest_path, [])
        (self.pdf_dir / "123_alpha.pdf").touch()
        args = make_args(self.references_csv, self.pdf_dir, self.manifest_path, self.output_path)
        stdout = StringIO()

        with patch.object(self.module, "parse_args", return_value=args):
            with redirect_stdout(stdout):
                self.module.main()

        self.assertTrue(self.output_path.exists())
        self.assertTrue(args.queue_output_path.exists())
        self.assertIn("Wrote 1 rows", stdout.getvalue())
        written_rows = read_csv_rows(self.output_path)
        queue_rows = read_csv_rows(args.queue_output_path)
        self.assertEqual(len(written_rows), 1)
        self.assertEqual(len(queue_rows), 0)
        self.assertEqual(written_rows[0]["download_status"], "downloaded")


if __name__ == "__main__":
    unittest.main()
