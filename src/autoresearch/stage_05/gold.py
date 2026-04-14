from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
TRIMMING_QA_DIR = REPO_ROOT / "qa" / "trimming"
GOLD_STANDARD_DIR = TRIMMING_QA_DIR / "gold_standard"
GOLD_PAPERS_DIR = GOLD_STANDARD_DIR / "papers"
MANIFEST_PATH = GOLD_STANDARD_DIR / "manifest.json"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def resolve_repo_path(path_text: str) -> Path:
    raw_path = str(path_text or "").strip()
    windows_path = PureWindowsPath(raw_path)
    if windows_path.is_absolute():
        if os.name == "nt":
            return Path(str(windows_path))
        return Path("/mnt", windows_path.drive.rstrip(":").lower(), *windows_path.parts[1:])

    path = Path(raw_path.replace("\\", "/"))
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def parse_int(value: Any, default: int = 10**9) -> int:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else default


def strict_normalise_text(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
    return " ".join(normalized.split()).strip()


def trimmed_text_payload(path: Path) -> tuple[str, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[str] = []
    lines: list[str] = []
    for page in payload.get("pages") or []:
        page_text = str(page.get("text") or "")
        if not page_text:
            continue
        chunks.append(page_text)
        lines.extend(line.strip() for line in page_text.splitlines() if line.strip())
    return "\n".join(chunks), lines


def raw_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalised_text_hash(text: str) -> str:
    return hashlib.sha256(strict_normalise_text(text).encode("utf-8")).hexdigest()


def historical_first_line(path: Path) -> str:
    _, lines = trimmed_text_payload(path)
    return lines[0] if lines else ""


def historical_last_line(path: Path) -> str:
    _, lines = trimmed_text_payload(path)
    return lines[-1] if lines else ""


def empty_manifest() -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "paper_count": 0,
        "entries": [],
    }


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not manifest_path.exists():
        return empty_manifest()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("entries"), list):
        return empty_manifest()
    return payload


def save_manifest(entries: list[dict[str, Any]], manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    ordered_entries = sorted(entries, key=lambda entry: parse_int(entry.get("paper_id")))
    payload = {
        "generated_at_utc": now_utc_iso(),
        "paper_count": sum(1 for entry in ordered_entries if str(entry.get("gold_status") or "") == "active"),
        "entries": ordered_entries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def active_entries_by_id(manifest_path: Path = MANIFEST_PATH) -> dict[str, dict[str, Any]]:
    payload = load_manifest(manifest_path)
    return {
        str(entry.get("paper_id") or "").strip(): entry
        for entry in payload.get("entries") or []
        if str(entry.get("paper_id") or "").strip() and str(entry.get("gold_status") or "").strip() == "active"
    }


def manifest_entry_for_gold_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "paper_id": path.stem,
            "gold_json_path": display_path(path),
            "source_text_path": "",
            "reviewer": "",
            "notes": "",
            "raw_text_hash": "",
            "normalised_text_hash": "",
            "gold_first_line": "",
            "gold_last_line": "",
            "gold_status": "invalid_json",
        }

    paper_id = str(payload.get("paper_id") or path.stem).strip()
    raw_text, lines = trimmed_text_payload(path)
    source_text_path = str(payload.get("source_text_path") or payload.get("source_text_json_path") or "").strip()
    reviewer = str(payload.get("reviewer") or payload.get("reviewer_id") or "").strip()
    notes = str(payload.get("notes") or payload.get("review_notes") or "").strip()
    return {
        "paper_id": paper_id,
        "gold_json_path": display_path(path),
        "source_text_path": source_text_path,
        "reviewer": reviewer,
        "notes": notes,
        "raw_text_hash": raw_text_hash(raw_text),
        "normalised_text_hash": normalised_text_hash(raw_text),
        "gold_first_line": lines[0] if lines else "",
        "gold_last_line": lines[-1] if lines else "",
        "gold_status": "active",
    }


def sync_manifest(
    *,
    gold_papers_dir: Path = GOLD_PAPERS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    entries = [manifest_entry_for_gold_json(path) for path in sorted(gold_papers_dir.glob("*.json"))]
    return save_manifest(entries, manifest_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync the stage-05 gold-standard manifest from direct gold JSONs.")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Scan qa/trimming/gold_standard/papers and rewrite manifest.json.",
    )
    parser.add_argument(
        "--gold-papers-dir",
        type=Path,
        default=GOLD_PAPERS_DIR,
        help="Directory containing gold-standard per-paper trimmed JSONs.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=MANIFEST_PATH,
        help="Manifest output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.sync:
        raise SystemExit("Pass --sync to rewrite the stage-05 gold manifest.")
    payload = sync_manifest(gold_papers_dir=args.gold_papers_dir, manifest_path=args.manifest_path)
    print(f"Active gold papers: {payload['paper_count']}")
    print(f"Manifest: {display_path(args.manifest_path)}")


if __name__ == "__main__":
    main()
