from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage06_gold as gold


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the stage-06 gold-standard JSON corpus from reviewed gold rows."
    )
    parser.add_argument(
        "--gold-master-path",
        type=Path,
        default=gold.GOLD_MASTER_PATH,
        help="Path to 04_categorisation_gold_standard.csv.",
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=gold.SOURCE_REGISTRY_PATH,
        help="Path to source_categorisation_registry.csv.",
    )
    parser.add_argument(
        "--count-registry-path",
        type=Path,
        default=gold.COUNT_REGISTRY_PATH,
        help="Path to source_sps_case_count_registry.csv.",
    )
    parser.add_argument(
        "--artifact-registry-path",
        type=Path,
        default=gold.ARTIFACT_REGISTRY_PATH,
        help="Path to paper_artifact_registry.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=gold.STAGE06_GOLD_DIR,
        help="Target directory for the stage-06 gold JSON corpus.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Restrict the bootstrap to one or more paper IDs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the manifest summary without writing JSON files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = gold.bootstrap_stage06_gold_store(
        gold_master_path=args.gold_master_path,
        source_registry_path=args.source_registry_path,
        count_registry_path=args.count_registry_path,
        artifact_registry_path=args.artifact_registry_path,
        gold_papers_dir=args.output_dir / "papers",
        manifest_path=args.output_dir / "manifest.json",
        paper_ids=args.paper_id,
        dry_run=args.dry_run,
    )
    print(f"Stage-06 gold directory: {gold.display_path(args.output_dir)}")
    print(f"Active gold JSONs: {summary['active_paper_count']}")
    print(f"Excluded rows: {summary['excluded_paper_count']}")
    print(f"Conflicts: {summary['conflict_paper_count']}")
    if not args.dry_run:
        print(f"Manifest: {gold.display_path(args.output_dir / 'manifest.json')}")


if __name__ == "__main__":
    main()
