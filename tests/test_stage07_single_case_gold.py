from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.validation import stage07_single_case_gold as gold


class TestStage07SingleCaseGold(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stage07_root = self.root / "stage07_xml"
        self.registry_path = self.root / "stage07_xml_registry.csv"
        self.gold_root = self.root / "gold"
        self.paper_id = "101"
        self.write_stage07_outputs("original")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_registry(self, paper_ids: list[str]) -> None:
        with self.registry_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["paper_id", "stage07_status"])
            writer.writeheader()
            for pid in paper_ids:
                writer.writerow({"paper_id": pid, "stage07_status": "ready_for_langextract"})

    def write_stage07_outputs(self, text: str, pid: str | None = None) -> None:
        pid = pid or self.paper_id
        (self.stage07_root / "annotated_text").mkdir(parents=True, exist_ok=True)
        (self.stage07_root / "annotated_text" / f"{pid}.annotated.txt").write_text(
            f"<seg>{text}</seg>",
            encoding="utf-8",
        )
        self.write_json(
            self.stage07_root / "papers" / f"{pid}.json",
            {
                "paper_id": pid,
                "stage07_method": {
                    "manifest_run_id": "run_a",
                    "generated_at_utc": "2026-01-01T00:00:00+00:00",
                },
            },
        )
        self.write_json(self.stage07_root / "segments" / f"{pid}.segments.json", {"paper_id": pid})
        self.write_json(
            self.stage07_root / "target_views" / pid / "p1.json",
            {"paper_id": pid, "input_text": text},
        )
        self.write_json(
            self.stage07_root / "validation" / f"{pid}.validation.json",
            {"status": "passed"},
        )
        self.write_registry([pid])

    def test_snapshot_and_compare_batch(self) -> None:
        gold.snapshot_batch(
            batch_id="batch000",
            paper_ids=[self.paper_id],
            stage07_root=self.stage07_root,
            registry_path=self.registry_path,
            gold_root=self.gold_root,
        )

        self.write_json(
            self.stage07_root / "papers" / f"{self.paper_id}.json",
            {
                "paper_id": self.paper_id,
                "stage07_method": {
                    "manifest_run_id": "run_b",
                    "generated_at_utc": "2026-01-02T00:00:00+00:00",
                },
            },
        )
        self.assertEqual(
            gold.compare_batch(
                batch_id="batch000",
                stage07_root=self.stage07_root,
                gold_root=self.gold_root,
            ),
            [],
        )

    def test_compare_batch_reports_xml_drift(self) -> None:
        gold.snapshot_batch(
            batch_id="batch000",
            paper_ids=[self.paper_id],
            stage07_root=self.stage07_root,
            registry_path=self.registry_path,
            gold_root=self.gold_root,
        )
        (self.stage07_root / "annotated_text" / f"{self.paper_id}.annotated.txt").write_text(
            "<seg>changed</seg>",
            encoding="utf-8",
        )

        self.assertEqual(
            gold.compare_batch(
                batch_id="batch000",
                stage07_root=self.stage07_root,
                gold_root=self.gold_root,
            ),
            [f"{self.paper_id}:annotated_xml"],
        )

    def test_partial_snapshot_preserves_batch_manifest_and_registry(self) -> None:
        other_id = "202"
        self.write_stage07_outputs("original", pid=self.paper_id)
        self.write_stage07_outputs("other", pid=other_id)
        self.write_registry([self.paper_id, other_id])
        gold.snapshot_batch(
            batch_id="batch000",
            paper_ids=[self.paper_id, other_id],
            stage07_root=self.stage07_root,
            registry_path=self.registry_path,
            gold_root=self.gold_root,
        )

        self.write_stage07_outputs("updated", pid=self.paper_id)
        self.write_registry([self.paper_id])
        gold.snapshot_batch(
            batch_id="batch000",
            paper_ids=[self.paper_id],
            stage07_root=self.stage07_root,
            registry_path=self.registry_path,
            gold_root=self.gold_root,
        )

        manifest = json.loads((self.gold_root / "batch000" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["paper_ids"], [self.paper_id, other_id])
        rows = list(csv.DictReader((self.gold_root / "batch000" / "registry.csv").open(encoding="utf-8")))
        self.assertEqual([row["paper_id"] for row in rows], [self.paper_id, other_id])
        self.assertEqual(
            gold.compare_batch(
                batch_id="batch000",
                stage07_root=self.stage07_root,
                gold_root=self.gold_root,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
