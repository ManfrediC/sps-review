from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_XML import core  # noqa: E402
from src.validation import _stage07_xml_docx_review as docx_review  # noqa: E402
from src.validation import _stage07_xml_review as review  # noqa: E402


def segment(
    *,
    segment_id: str,
    logical_segment_id: str,
    targets: list[str],
    role: str,
    source_text: str,
    selected_text: str,
) -> dict[str, object]:
    start = source_text.index(selected_text)
    end = start + len(selected_text)
    return {
        "segment_id": segment_id,
        "logical_segment_id": logical_segment_id,
        "targets": targets,
        "role": role,
        "text": selected_text,
        "source_offsets": {"start": start, "end": end},
        "source_block_id": "b0001",
        "confidence": "high",
        "evidence": f"Evidence for {segment_id}",
    }


class TestStage07XmlDocxReview(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.stage07_root = self.tmp_path / "stage07_xml"
        self.registry_path = self.tmp_path / "stage07_xml_registry.csv"
        self.review_root = self.tmp_path / "docx_review"
        self.registry_rows: list[dict[str, str]] = []

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_stage07_output(
        self,
        *,
        paper_id: str,
        source_text: str,
        entities: list[dict[str, str]],
        segments: list[dict[str, object]],
        route_mode: str = "individual_case_split",
    ) -> None:
        paper_json_path = self.stage07_root / "papers" / f"{paper_id}.json"
        segments_json_path = self.stage07_root / "segments" / f"{paper_id}.segments.json"
        annotated_text_path = self.stage07_root / "annotated_text" / f"{paper_id}.annotated.txt"
        validation_json_path = self.stage07_root / "validation" / f"{paper_id}.validation.json"
        for path in (paper_json_path, segments_json_path, annotated_text_path, validation_json_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        source_sha = review.sha256_text(source_text)
        paper_json_path.write_text(
            json.dumps(
                {
                    "paper_id": paper_id,
                    "title": f"Paper {paper_id}",
                    "source": {"prepared_source_sha256": source_sha},
                    "source_route": {"resolved_langextract_mode": route_mode},
                    "annotation": {"annotation_mode": "mock", "validation_status": "passed"},
                    "entities": entities,
                    "manual_review": {"manual_review_required": False, "reasons": []},
                }
            ),
            encoding="utf-8",
        )
        segments_json_path.write_text(
            json.dumps(
                {
                    "paper_id": paper_id,
                    "source": {
                        "prepared_source_sha256": source_sha,
                        "prepared_source_character_count": len(source_text),
                    },
                    "entities": entities,
                    "source_blocks": [
                        {
                            "block_id": "b0001",
                            "source_offsets": {"start": 0, "end": len(source_text)},
                            "page_index": 0,
                            "text": source_text,
                        }
                    ],
                    "segments": segments,
                    "validation": {"status": "passed"},
                }
            ),
            encoding="utf-8",
        )
        annotated_text_path.write_text(source_text, encoding="utf-8")
        validation_json_path.write_text(json.dumps({"status": "passed"}), encoding="utf-8")
        self.registry_rows.append(
            {
                "paper_id": paper_id,
                "paper_json_path": str(paper_json_path),
                "segments_json_path": str(segments_json_path),
                "annotated_text_path": str(annotated_text_path),
                "validation_json_path": str(validation_json_path),
                "route_mode": route_mode,
                "validation_status": "passed",
                "roundtrip_status": "passed",
                "manual_review_required": "false",
                "manual_review_reasons": "",
            }
        )

    def write_registry(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "paper_id",
            "paper_json_path",
            "segments_json_path",
            "annotated_text_path",
            "validation_json_path",
            "route_mode",
            "validation_status",
            "roundtrip_status",
            "manual_review_required",
            "manual_review_reasons",
        ]
        with self.registry_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.registry_rows)

    def build_two_patient_fixture(self) -> str:
        source_text = (
            "Patient 1 had stiffness.\n\n"
            "Patient 2 had spasms.\n\n"
            "Both patients improved."
        )
        self.write_stage07_output(
            paper_id="1001",
            source_text=source_text,
            entities=[
                {"id": "p1", "kind": "patient", "label": "Patient 1"},
                {"id": "p2", "kind": "patient", "label": "Patient 2"},
            ],
            segments=[
                segment(
                    segment_id="s0001",
                    logical_segment_id="l0001",
                    targets=["p1"],
                    role="patient_specific",
                    source_text=source_text,
                    selected_text="Patient 1 had stiffness.",
                ),
                segment(
                    segment_id="s0002",
                    logical_segment_id="l0002",
                    targets=["p2"],
                    role="patient_specific",
                    source_text=source_text,
                    selected_text="Patient 2 had spasms.",
                ),
                segment(
                    segment_id="s0003",
                    logical_segment_id="l0003",
                    targets=["p1", "p2"],
                    role="shared",
                    source_text=source_text,
                    selected_text="Both patients improved.",
                ),
            ],
        )
        self.write_registry()
        return source_text

    def build_docx_pack(self) -> None:
        docx_review.build_docx_review_pack(
            round_id="round_01",
            stage07_root=self.stage07_root,
            registry_path=self.registry_path,
            review_root=self.review_root,
            force=True,
        )

    def test_build_docx_review_pack_writes_docx_markdown_and_metadata(self) -> None:
        self.build_two_patient_fixture()
        self.build_docx_pack()

        docx_path = self.review_root / "round_01" / "papers" / "1001.docx"
        legend_path = self.review_root / "round_01" / "papers" / "1001.colour_legend_and_notes.md"
        metadata_path = self.review_root / "round_01" / "papers" / "1001.docx_metadata.json"
        index_path = self.review_root / "round_01" / "docx_review_index.csv"

        self.assertTrue(docx_path.exists())
        self.assertTrue(legend_path.exists())
        self.assertTrue(metadata_path.exists())
        self.assertTrue(index_path.exists())
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("REVIEW TARGET | target_id=p1", document_xml)
        self.assertIn("REVIEW TARGET | target_id=p2", document_xml)
        legend = legend_path.read_text(encoding="utf-8")
        self.assertIn("| p1 | Patient 1 | patient | yellow | FFF2CC |", legend)
        self.assertIn("| p2 | Patient 2 | patient | orange | F4B183 |", legend)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["targets"][1]["colour_hex"], "F4B183")

    def test_import_unchanged_docx_review_produces_reviewed_annotation(self) -> None:
        self.build_two_patient_fixture()
        self.build_docx_pack()

        result = docx_review.import_docx_review_round(
            round_dir=self.review_root / "round_01",
            force=True,
            regenerate_gold=False,
        )

        self.assertEqual(result["passed_count"], "1")
        annotation_path = self.review_root / "round_01" / "reviewed_annotations" / "1001.json"
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        roles_by_targets = {
            (tuple(segment["targets"]), segment["role"])
            for segment in payload["segments"]
        }
        self.assertIn((("p1",), "patient_specific"), roles_by_targets)
        self.assertIn((("p2",), "patient_specific"), roles_by_targets)
        self.assertIn((("p1", "p2"), "shared"), roles_by_targets)
        shared = next(segment for segment in payload["segments"] if segment["role"] == "shared")
        self.assertEqual(shared["selections"][0]["text"], "Both patients improved.")
        self.assertIn("source_start", shared["selections"][0])

    def test_import_docx_review_can_rescore_candidate_outputs(self) -> None:
        self.build_two_patient_fixture()
        self.build_docx_pack()
        evaluation_root = self.tmp_path / "evaluation"

        result = docx_review.import_docx_review_round(
            round_dir=self.review_root / "round_01",
            force=True,
            regenerate_gold=False,
            rescore_candidate_stage07_root=self.stage07_root,
            rescore_candidate_registry_path=self.registry_path,
            rescore_evaluation_root=evaluation_root,
            rescore_run_id="round_01_rescore",
            rescore_matrix_config_name="H0",
        )

        self.assertEqual(result["passed_count"], "1")
        self.assertTrue((evaluation_root / "round_01_rescore" / "summary.json").exists())
        self.assertTrue((evaluation_root / "round_01_rescore" / "paper_scores.csv").exists())
        self.assertIn("round_01_rescore", result["benchmark_run_dir"])

    def test_import_rejects_docx_source_text_edits(self) -> None:
        self.build_two_patient_fixture()
        self.build_docx_pack()
        docx_path = self.review_root / "round_01" / "papers" / "1001.docx"
        replace_docx_text(docx_path, "Patient 1 had stiffness.", "Patient 1 had rigidity.", count=2)

        result = docx_review.import_docx_review_round(
            round_dir=self.review_root / "round_01",
            force=True,
            regenerate_gold=False,
        )

        self.assertEqual(result["failed_count"], "1")
        report_path = self.review_root / "round_01" / "import_reports" / "1001.import_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("source_text_hash_mismatch:p1", report["errors"])
        self.assertFalse((self.review_root / "round_01" / "reviewed_annotations" / "1001.json").exists())

    def test_import_accepts_new_target_from_legend_and_matching_docx_section(self) -> None:
        source_text = "Patient 1 had stiffness.\n\nNew patient had spasms."
        self.write_stage07_output(
            paper_id="1002",
            source_text=source_text,
            entities=[{"id": "p1", "kind": "patient", "label": "Patient 1"}],
            segments=[
                segment(
                    segment_id="s0001",
                    logical_segment_id="l0001",
                    targets=["p1"],
                    role="patient_specific",
                    source_text=source_text,
                    selected_text="Patient 1 had stiffness.",
                )
            ],
        )
        self.write_registry()
        self.build_docx_pack()
        round_dir = self.review_root / "round_01"
        legend_path = round_dir / "papers" / "1002.colour_legend_and_notes.md"
        legend = legend_path.read_text(encoding="utf-8").replace(
            "| new_target_1 | New target 1 | template | lightGray | D9D9D9 |",
            "| p2 | Patient 2 | patient | orange | F4B183 |",
        )
        legend_path.write_text(legend, encoding="utf-8")
        docx_path = round_dir / "papers" / "1002.docx"
        replace_docx_text(
            docx_path,
            "REVIEW TARGET | target_id=new_target_1 | label=New target 1 | kind=template | colour=lightGray | fill=D9D9D9",
            "REVIEW TARGET | target_id=p2 | label=Patient 2 | kind=patient | colour=orange | fill=F4B183",
            count=1,
        )
        shade_docx_paragraph_after_heading(
            docx_path,
            heading_prefix="REVIEW TARGET | target_id=p2",
            paragraph_text="New patient had spasms.",
            fill="F4B183",
        )

        result = docx_review.import_docx_review_round(
            round_dir=round_dir,
            force=True,
            regenerate_gold=False,
        )

        self.assertEqual(result["passed_count"], "1")
        payload = json.loads((round_dir / "reviewed_annotations" / "1002.json").read_text(encoding="utf-8"))
        self.assertEqual([target["id"] for target in payload["targets"]], ["p1", "p2"])
        self.assertEqual(payload["route_mode"], "individual_case_split")
        p2_segment = next(segment for segment in payload["segments"] if segment["targets"] == ["p2"])
        self.assertEqual(p2_segment["selections"][0]["text"], "New patient had spasms.")

    def test_reviewed_annotation_offset_selection_compiles(self) -> None:
        source_path = self.tmp_path / "source.json"
        source_path.write_text(
            json.dumps({"paper_id": "1003", "pages": [{"page_index": 0, "text": "Intro. Patient had SPSD."}]}),
            encoding="utf-8",
        )
        prepared = core.prepare_source(paper_id="1003", source_path=source_path)
        payload = core.compile_reviewed_annotation_payload(
            reviewed_payload={
                "paper_id": "1003",
                "route_mode": "individual",
                "targets": [{"id": "p1", "kind": "patient", "label": "Patient 1"}],
                "segments": [
                    {
                        "targets": ["p1"],
                        "role": "patient_specific",
                        "selections": [
                            {
                                "source_start": 7,
                                "source_end": 24,
                                "text": "Patient had SPSD.",
                            }
                        ],
                    }
                ],
            },
            prepared_source=prepared,
        )

        self.assertEqual(payload["segments"][0]["spans"][0]["selected_text"], "Patient had SPSD.")

    def test_docx_safe_text_preserves_original_control_character_in_imported_selection(self) -> None:
        source_text = "Patient had SPSD.\x0bFollow-up improved."
        self.write_stage07_output(
            paper_id="1004",
            source_text=source_text,
            entities=[{"id": "p1", "kind": "patient", "label": "Patient 1"}],
            segments=[
                segment(
                    segment_id="s0001",
                    logical_segment_id="l0001",
                    targets=["p1"],
                    role="patient_specific",
                    source_text=source_text,
                    selected_text=source_text,
                )
            ],
            route_mode="individual",
        )
        self.write_registry()
        self.build_docx_pack()

        metadata = json.loads(
            (self.review_root / "round_01" / "papers" / "1004.docx_metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["docx_text_replacements"][0]["source_codepoint"], 11)

        docx_review.import_docx_review_round(
            round_dir=self.review_root / "round_01",
            force=True,
            regenerate_gold=False,
        )

        payload = json.loads(
            (self.review_root / "round_01" / "reviewed_annotations" / "1004.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["segments"][0]["selections"][0]["text"], source_text)


def replace_docx_text(path: Path, old: str, new: str, *, count: int) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    text = entries["word/document.xml"].decode("utf-8")
    entries["word/document.xml"] = text.replace(old, new, count).encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def shade_docx_paragraph_after_heading(
    path: Path,
    *,
    heading_prefix: str,
    paragraph_text: str,
    fill: str,
) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    document = etree.fromstring(entries["word/document.xml"])
    in_section = False
    for paragraph in document.findall(".//w:body/w:p", namespaces=docx_review.NSMAP):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespaces=docx_review.NSMAP))
        if text.startswith(heading_prefix):
            in_section = True
            continue
        if in_section and text == paragraph_text:
            for run in paragraph.findall("w:r", namespaces=docx_review.NSMAP):
                run_properties = run.find("w:rPr", namespaces=docx_review.NSMAP)
                if run_properties is None:
                    run_properties = etree.Element(docx_review.w_tag("rPr"))
                    run.insert(0, run_properties)
                etree.SubElement(
                    run_properties,
                    docx_review.w_tag("shd"),
                    {
                        docx_review.w_tag("val"): "clear",
                        docx_review.w_tag("color"): "auto",
                        docx_review.w_tag("fill"): fill,
                    },
                )
            break
    entries["word/document.xml"] = etree.tostring(
        document,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


if __name__ == "__main__":
    unittest.main()
