from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage06_backfill as backfill


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the stage-06 hybrid backfill campaign manifest, batch manifests, and status table."
    )
    parser.add_argument("--campaign-id", default=backfill.default_campaign_id())
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--campaign-root", type=Path, default=backfill.CAMPAIGN_ROOT)
    parser.add_argument("--qa-output-dir", type=Path, default=backfill.QA_OUTPUT_DIR)
    parser.add_argument("--text-dir", type=Path, default=backfill.TEXT_DIR)
    parser.add_argument("--gold-manifest", type=Path, default=backfill.GOLD_MANIFEST_PATH)
    parser.add_argument("--manual-review-path", type=Path, default=backfill.MANUAL_REVIEW_PATH)
    parser.add_argument("--run-root", type=Path, default=backfill.RUN_ROOT)
    parser.add_argument(
        "--repair-existing-campaign",
        action="store_true",
        help="Repair an existing frozen campaign in place instead of rebuilding from the current uncovered pool.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repair_existing_campaign:
        manifest_path = backfill.repair_campaign_outputs(
            campaign_id=args.campaign_id,
            batch_size=args.batch_size,
            campaign_root=args.campaign_root,
            qa_output_dir=args.qa_output_dir,
            text_dir=args.text_dir,
            gold_manifest_path=args.gold_manifest,
            manual_review_path=args.manual_review_path,
            run_root=args.run_root,
        )
        mode = "repair"
    else:
        manifest_path = backfill.write_campaign_outputs(
            campaign_id=args.campaign_id,
            batch_size=args.batch_size or backfill.DEFAULT_BATCH_SIZE,
            campaign_root=args.campaign_root,
            qa_output_dir=args.qa_output_dir,
            text_dir=args.text_dir,
            gold_manifest_path=args.gold_manifest,
            manual_review_path=args.manual_review_path,
            run_root=args.run_root,
        )
        mode = "build"
    payload = backfill.load_json(manifest_path)
    print(
        json.dumps(
            {
                "mode": mode,
                "manifest_path": backfill.display_path(manifest_path),
                "coverage": payload["coverage"]["summary_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
