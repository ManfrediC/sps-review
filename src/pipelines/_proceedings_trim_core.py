from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parent


def _load_script_module(module_name: str, file_name: str):
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    script_path = PIPELINE_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load pipeline module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_TRIM_MODULE = _load_script_module("_stage05_trim_proceedings_text_baseline", "05_trim_proceedings_text.py")
_VALIDATE_MODULE = _load_script_module(
    "_stage05_validate_proceedings_text_baseline",
    "05b_validate_proceedings_text.py",
)

REPO_ROOT = _TRIM_MODULE.REPO_ROOT
REFERENCES_CSV = _TRIM_MODULE.REFERENCES_CSV
TEXT_DIR = _TRIM_MODULE.TEXT_DIR
SOURCE_CATEGORISATION_PATH = _TRIM_MODULE.SOURCE_CATEGORISATION_PATH
SOURCE_MANUAL_REVIEW_PATH = _TRIM_MODULE.SOURCE_MANUAL_REVIEW_PATH
TRIM_OVERRIDE_PATH = _TRIM_MODULE.TRIM_OVERRIDE_PATH
ARTIFACT_REGISTRY_SCRIPT = _TRIM_MODULE.ARTIFACT_REGISTRY_SCRIPT

AbstractBlock = _TRIM_MODULE.AbstractBlock
IndexEntry = _TRIM_MODULE.IndexEntry

now_utc_iso = _TRIM_MODULE.now_utc_iso
relative_to_repo = _TRIM_MODULE.relative_to_repo
bool_text = _TRIM_MODULE.bool_text
load_reference_rows = _TRIM_MODULE.load_reference_rows
load_trim_override_rows = _TRIM_MODULE.load_trim_override_rows
collect_input_paths = _TRIM_MODULE.collect_input_paths
filter_to_proceedings_candidates = _TRIM_MODULE.filter_to_proceedings_candidates
load_text_record = _TRIM_MODULE.load_text_record
page_match_scores = _TRIM_MODULE.page_match_scores
truncate_at_next_header = _TRIM_MODULE.truncate_at_next_header
trim_trailing_header_noise = _TRIM_MODULE.trim_trailing_header_noise
trim_leading_header_noise = _TRIM_MODULE.trim_leading_header_noise
parse_index_entries = _TRIM_MODULE.parse_index_entries
best_index_entry = _TRIM_MODULE.best_index_entry
line_matches_code = _TRIM_MODULE.line_matches_code
estimate_page_offset = _TRIM_MODULE.estimate_page_offset
neighbor_entries = _TRIM_MODULE.neighbor_entries
select_search_lines = _TRIM_MODULE.select_search_lines
proceedings_signals = _TRIM_MODULE.proceedings_signals
extract_blocks = _TRIM_MODULE.extract_blocks
best_matching_block = _TRIM_MODULE.best_matching_block
join_window_text = _TRIM_MODULE.join_window_text
title_cluster_score = _TRIM_MODULE.title_cluster_score
local_window_candidate = _TRIM_MODULE.local_window_candidate
index_assisted_candidate = _TRIM_MODULE.index_assisted_candidate
candidate_quality_status = _TRIM_MODULE.candidate_quality_status
choose_best_candidate = _TRIM_MODULE.choose_best_candidate
trim_pages_from_block = _TRIM_MODULE.trim_pages_from_block
build_trimmed_record = _TRIM_MODULE.build_trimmed_record
apply_trim_override = _TRIM_MODULE.apply_trim_override
decision_row = _TRIM_MODULE.decision_row
sort_registry_rows = _TRIM_MODULE.sort_registry_rows
merge_registry_rows = _TRIM_MODULE.merge_registry_rows
refresh_artifact_registry = _TRIM_MODULE.refresh_artifact_registry

body_metrics = _VALIDATE_MODULE.body_metrics
page_matches = _VALIDATE_MODULE.page_matches
validate_trimmed_segmentation = _VALIDATE_MODULE.validate_trimmed_segmentation
derive_qc_status = _VALIDATE_MODULE.derive_qc_status

