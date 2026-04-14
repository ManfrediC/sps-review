from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from src.validation import _stage06_review as review


PDF_VIEW_HEIGHT = 1000
PDF_SEARCH_RESULT_LIMIT = 12
PDF_ZOOM_MIN = 0.5
PDF_ZOOM_MAX = 3.0
PDF_ZOOM_STEP = 0.25
PDF_DEFAULT_ZOOM = 1.0
REVIEW_STATUS_OPTIONS = ("pending", "reviewed", "needs_follow_up")


@st.cache_data(show_spinner=False)
def load_pdf_bytes(pdf_path_text: str) -> bytes:
    return review.resolve_repo_path(pdf_path_text).read_bytes()


@st.cache_data(show_spinner=False)
def load_text_pages(text_json_path_text: str) -> list[dict[str, object]]:
    return review.load_text_page_entries(text_json_path_text)


@st.cache_data(show_spinner=False)
def load_review_rows_from_run(run_dir_text: str) -> list[dict[str, str]]:
    return review.load_review_rows_from_run(Path(run_dir_text))


@st.cache_data(show_spinner=False)
def load_review_rows_from_runs(run_dir_texts: tuple[str, ...]) -> list[dict[str, str]]:
    latest_by_paper: dict[str, dict[str, str]] = {}
    for run_dir_text in run_dir_texts:
        for row in review.load_review_rows_from_run(Path(run_dir_text)):
            paper_id = str(row.get("paper_id") or "").strip()
            if paper_id and paper_id not in latest_by_paper:
                latest_by_paper[paper_id] = row
    return sorted(
        latest_by_paper.values(),
        key=lambda row: (
            review.parse_int(row.get("paper_id"), default=10**9),
            str(row.get("paper_id") or ""),
        ),
    )


@st.cache_data(show_spinner=False)
def load_review_rows_from_registry(registry_path_text: str) -> list[dict[str, str]]:
    return review.load_review_rows_from_registry(Path(registry_path_text))


@st.cache_data(show_spinner=False)
def load_candidate_package(path_text: str) -> dict[str, Any]:
    return review.load_candidate_package(path_text)


@st.cache_data(show_spinner=False)
def load_decision_payload(path_text: str) -> dict[str, Any]:
    return review.load_decision_payload(path_text)


@st.cache_data(show_spinner=False)
def load_evidence_payload(path_text: str) -> dict[str, Any]:
    return review.load_evidence_payload(path_text)


@st.cache_data(show_spinner=False)
def load_run_manifest(run_dir_text: str) -> dict[str, Any]:
    return review.load_json(Path(run_dir_text) / "run_manifest.json")


def normalise_count_text(value: str) -> str:
    stripped = str(value or "").strip()
    return stripped if stripped else "0"


def bool_label(value: str) -> str:
    return "yes" if review.truthy(value) else "no"


def parse_candidate_count(value: str) -> int:
    return review.parse_int(value, default=0)


def review_status_for_row(
    row: dict[str, str],
    responses_by_id: dict[str, dict[str, str]],
) -> str:
    response_row = responses_by_id.get((row.get("paper_id") or "").strip(), {})
    status = str(response_row.get("review_status") or "").strip()
    return status or "pending"


def editor_prefix(scope_id: str, paper_id: str) -> str:
    return f"stage06_review::{scope_id}::{paper_id}"


def editor_key(prefix: str, suffix: str) -> str:
    return f"{prefix}::{suffix}"


def response_defaults(
    review_row: dict[str, str],
    response_row: dict[str, str],
) -> tuple[bool, str, str, str]:
    predicted_count = normalise_count_text(review_row.get("likely_sps_case_count") or "")
    saved_count = normalise_count_text(response_row.get("reviewed_count") or "")
    prediction_correct = review.truthy(response_row.get("prediction_correct") or "")
    if response_row and not prediction_correct:
        count_value = saved_count or predicted_count
    else:
        count_value = predicted_count
        if not response_row:
            prediction_correct = True
    review_status = (response_row.get("review_status") or "pending").strip() or "pending"
    notes_value = (response_row.get("reviewer_notes") or "").strip()
    return prediction_correct, count_value, review_status, notes_value


def ensure_editor_state(
    *,
    scope_id: str,
    review_row: dict[str, str],
    response_row: dict[str, str],
) -> str:
    prefix = editor_prefix(scope_id, str(review_row.get("paper_id") or "").strip())
    active_key = "stage06_review_active_editor"
    if st.session_state.get(active_key) != prefix:
        prediction_correct, default_count, default_status, default_notes = response_defaults(review_row, response_row)
        st.session_state[editor_key(prefix, "prediction_correct")] = prediction_correct
        st.session_state[editor_key(prefix, "reviewed_count")] = default_count
        st.session_state[editor_key(prefix, "review_status")] = default_status
        st.session_state[editor_key(prefix, "reviewer_notes")] = default_notes
        st.session_state[editor_key(prefix, "reviewer_id")] = (
            (response_row.get("reviewer_id") or review.DEFAULT_REVIEWER).strip() or review.DEFAULT_REVIEWER
        )
        st.session_state[editor_key(prefix, "pdf_search_query")] = ""
        st.session_state[editor_key(prefix, "pdf_view_page")] = 1
        st.session_state[editor_key(prefix, "pdf_zoom_level")] = PDF_DEFAULT_ZOOM
        st.session_state[editor_key(prefix, "candidate_focus")] = ""
        st.session_state[active_key] = prefix
    return prefix


def first_pending_index(
    rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> int:
    for index, row in enumerate(rows):
        if review_status_for_row(row, responses_by_id) != "reviewed":
            return index
    return 0


def clamp_zoom_level(value: float) -> float:
    return max(PDF_ZOOM_MIN, min(PDF_ZOOM_MAX, round(value, 2)))


def adjust_zoom_level(key: str, delta: float) -> None:
    current = float(st.session_state.get(key, PDF_DEFAULT_ZOOM))
    st.session_state[key] = clamp_zoom_level(current + delta)


def set_session_value(key: str, value: int | str | float) -> None:
    st.session_state[key] = value


def set_search_target(prefix: str, quote: str, page: int | None = None) -> None:
    quote_text = " ".join(str(quote or "").split())
    if quote_text:
        st.session_state[editor_key(prefix, "pdf_search_query")] = quote_text[:160]
    if page is not None and page > 0:
        st.session_state[editor_key(prefix, "pdf_view_page")] = page


def filtered_rows(
    rows: list[dict[str, str]],
    *,
    verification_filter: str,
    review_filter: str,
    category_filter: str,
    candidate_filter: str,
    manual_review_filter: str,
    responses_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    filtered = rows
    if verification_filter != "All":
        filtered = [row for row in filtered if row.get("count_verification_status") == verification_filter]
    if review_filter != "All":
        if review_filter == "Pending":
            filtered = [row for row in filtered if review_status_for_row(row, responses_by_id) == "pending"]
        elif review_filter == "Reviewed":
            filtered = [row for row in filtered if review_status_for_row(row, responses_by_id) == "reviewed"]
        else:
            filtered = [row for row in filtered if review_status_for_row(row, responses_by_id) == "needs_follow_up"]
    if category_filter != "All":
        filtered = [row for row in filtered if row.get("source_category") == category_filter]
    if candidate_filter == "1":
        filtered = [row for row in filtered if parse_candidate_count(row.get("heuristic_candidate_count") or "") == 1]
    elif candidate_filter == "2+":
        filtered = [row for row in filtered if parse_candidate_count(row.get("heuristic_candidate_count") or "") >= 2]
    if manual_review_filter == "Requires manual review":
        filtered = [row for row in filtered if review.truthy(row.get("count_manual_review_required") or "")]
    elif manual_review_filter == "No manual review":
        filtered = [row for row in filtered if not review.truthy(row.get("count_manual_review_required") or "")]
    return filtered


def evidence_items_for_display(
    decision_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    decision_evidence = list(((decision_payload.get("decision") or {}).get("evidence") or []))
    if decision_evidence:
        return decision_evidence
    return list(evidence_payload.get("evidence") or [])


def candidate_rows_for_display(package: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    preferred_candidate_id = str(package.get("preferred_candidate_id") or "").strip()
    fallback_candidate_id = str(package.get("fallback_candidate_id") or "").strip()
    for candidate in package.get("candidates") or []:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        role_bits: list[str] = []
        if candidate_id == preferred_candidate_id:
            role_bits.append("preferred")
        if candidate_id == fallback_candidate_id:
            role_bits.append("fallback")
        rows.append(
            {
                "candidate_id": candidate_id,
                "role": ", ".join(role_bits) or "candidate",
                "proposed_count": str(candidate.get("proposed_count") or ""),
                "kind": str(candidate.get("candidate_kind") or ""),
                "basis": str(candidate.get("count_basis") or ""),
                "confidence": str(candidate.get("count_confidence") or ""),
                "manual_review": bool_label(str(candidate.get("manual_review_required") or "")),
                "score": str(candidate.get("score") or ""),
                "blockers": "; ".join(candidate.get("blockers") or []),
            }
        )
    return rows


def candidate_options(package: dict[str, Any]) -> list[str]:
    return [str(candidate.get("candidate_id") or "").strip() for candidate in package.get("candidates") or [] if candidate.get("candidate_id")]


def candidate_by_id(package: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    for candidate in package.get("candidates") or []:
        if str(candidate.get("candidate_id") or "").strip() == candidate_id:
            return candidate
    return {}


def quoted_search_text(value: str) -> str:
    return " ".join(str(value or "").split())[:160]


def suggested_start_page(
    page_entries: list[dict[str, object]],
    evidence_items: list[dict[str, Any]],
) -> int:
    for item in evidence_items:
        page = review.parse_int(item.get("page"), default=0)
        if page > 0:
            return page
    for item in evidence_items:
        quote = quoted_search_text(str(item.get("quote") or ""))
        if len(quote) < 12:
            continue
        matches = review.search_text_page_entries(page_entries, quote, max_results=1)
        if matches:
            return review.parse_int(matches[0].get("page_num"), default=1)
    return 1


def render_pdf_panel(
    review_row: dict[str, str],
    prefix: str,
    evidence_items: list[dict[str, Any]],
) -> None:
    pdf_path_relative = str(review_row.get("pdf_path_relative") or "").strip()
    text_json_path_relative = str(
        review_row.get("preferred_text_json_path") or review_row.get("source_text_json_path") or ""
    ).strip()
    page_entries = load_text_pages(text_json_path_relative) if text_json_path_relative else []
    preferred_page = suggested_start_page(page_entries, evidence_items)

    pdf_view_page_key = editor_key(prefix, "pdf_view_page")
    pdf_search_query_key = editor_key(prefix, "pdf_search_query")
    pdf_zoom_level_key = editor_key(prefix, "pdf_zoom_level")
    if st.session_state.get(pdf_view_page_key, 1) <= 1:
        st.session_state[pdf_view_page_key] = preferred_page

    if not pdf_path_relative:
        st.error("PDF path is missing from the paper artifact registry.")
        return
    pdf_path = review.resolve_repo_path(pdf_path_relative)
    if not pdf_path.exists():
        st.error(f"PDF not found: {review.display_path(pdf_path)}")
        return

    st.caption(f"{review.display_path(pdf_path)}")
    st.caption(f"Suggested start page: {preferred_page}. Search uses `{text_json_path_relative or 'no text JSON available'}`.")

    if page_entries:
        page_count = len(page_entries)
        search_col, page_col, reset_col = st.columns([2, 1, 1])
        with search_col:
            st.text_input(
                "Search paper text",
                key=pdf_search_query_key,
                placeholder="Enter a phrase to find matching pages",
                help="Search uses the preferred text JSON selected for stage 06.",
            )
        with page_col:
            st.number_input(
                "Page",
                min_value=1,
                max_value=max(page_count, preferred_page),
                step=1,
                key=pdf_view_page_key,
            )
        with reset_col:
            st.write("")
            st.button(
                "Suggested page",
                key=editor_key(prefix, "pdf_reset_page"),
                use_container_width=True,
                on_click=set_session_value,
                args=(pdf_view_page_key, preferred_page),
            )

        search_query = str(st.session_state[pdf_search_query_key]).strip()
        if search_query:
            matches = review.search_text_page_entries(page_entries, search_query, max_results=PDF_SEARCH_RESULT_LIMIT)
            if matches:
                st.caption(
                    f"Found {sum(int(match['match_count']) for match in matches)} match(es) across {len(matches)} page(s)."
                )
                for match in matches:
                    page_num = int(match["page_num"])
                    st.button(
                        f"Page {page_num} ({match['match_count']} hit(s))",
                        key=editor_key(prefix, f"search_result::{page_num}"),
                        use_container_width=True,
                        on_click=set_session_value,
                        args=(pdf_view_page_key, page_num),
                    )
                    st.caption(str(match["snippet"]))
            else:
                st.info("No matching pages were found in the selected text JSON for this paper.")

    zoom_down_col, zoom_slider_col, zoom_up_col, zoom_reset_col = st.columns([1, 2, 1, 1])
    with zoom_down_col:
        st.write("")
        st.button(
            "Zoom -",
            use_container_width=True,
            key=editor_key(prefix, "zoom_down"),
            on_click=adjust_zoom_level,
            args=(pdf_zoom_level_key, -PDF_ZOOM_STEP),
        )
    with zoom_slider_col:
        st.slider(
            "Zoom",
            min_value=PDF_ZOOM_MIN,
            max_value=PDF_ZOOM_MAX,
            step=PDF_ZOOM_STEP,
            key=pdf_zoom_level_key,
        )
    with zoom_up_col:
        st.write("")
        st.button(
            "Zoom +",
            use_container_width=True,
            key=editor_key(prefix, "zoom_up"),
            on_click=adjust_zoom_level,
            args=(pdf_zoom_level_key, PDF_ZOOM_STEP),
        )
    with zoom_reset_col:
        st.write("")
        st.button(
            "100%",
            use_container_width=True,
            key=editor_key(prefix, "zoom_reset"),
            on_click=set_session_value,
            args=(pdf_zoom_level_key, PDF_DEFAULT_ZOOM),
        )

    pdf_viewer(
        load_pdf_bytes(pdf_path_relative),
        key=editor_key(prefix, f"pdf::{st.session_state[pdf_view_page_key]}::{st.session_state[pdf_zoom_level_key]}"),
        width="100%",
        height=PDF_VIEW_HEIGHT,
        render_text=False,
        resolution_boost=2,
        zoom_level=float(st.session_state[pdf_zoom_level_key]),
        viewer_align="left",
        scroll_to_page=int(st.session_state[pdf_view_page_key]),
        scroll_behavior="instant",
    )


def run_option_label(run_dir: Path) -> str:
    manifest = load_run_manifest(str(run_dir))
    result_count = len(list((run_dir / "results").glob("*.json")))
    verification_mode = str(manifest.get("verification_mode") or "").strip() or "unknown"
    model = str(manifest.get("model") or "").strip() or "unknown"
    return f"{run_dir.name} | {result_count} paper(s) | {verification_mode} | {model}"


def main() -> None:
    st.set_page_config(page_title="Stage 06 Count Review App", layout="wide")
    st.title("Stage 06 Count Review App")
    st.caption(
        "Inspect heuristic candidates, optional LLM adjudication evidence, and the source PDF while recording review judgements."
    )

    source_mode = st.sidebar.selectbox("Source", options=["All runs", "Run directory", "Registry CSV"], index=0)
    review_rows: list[dict[str, str]]
    source_scope_id: str
    source_scope_label: str
    source_kind: str
    source_path_text: str

    if source_mode == "All runs":
        run_options = list(reversed(review.discover_run_directories()))
        if not run_options:
            st.warning("No stage 06 run directories were found under `results/stage06_count_runs/`.")
            return
        review_rows = load_review_rows_from_runs(tuple(str(path) for path in run_options))
        source_scope_id = "all_runs"
        source_scope_label = "all_runs"
        source_kind = "all_runs"
        source_path_text = "results/stage06_count_runs/*"
        st.sidebar.caption(f"Loaded {len(run_options)} run directorie(s).")
    elif source_mode == "Run directory":
        run_options = list(reversed(review.discover_run_directories()))
        if not run_options:
            st.warning("No stage 06 run directories were found under `results/stage06_count_runs/`.")
            return
        selected_run = st.sidebar.selectbox("Run", options=run_options, format_func=run_option_label)
        review_rows = load_review_rows_from_run(str(selected_run))
        source_scope_id = review.review_scope_id_for_run(selected_run)
        source_scope_label = selected_run.name
        source_kind = "run_directory"
        source_path_text = review.display_path(selected_run)
    else:
        registry_path_text = st.sidebar.text_input(
            "Registry CSV",
            value=str(review.COUNT_REGISTRY_PATH),
            help="Use the canonical registry or point the app at a batch-specific count registry CSV.",
        )
        registry_path = Path(registry_path_text)
        if not registry_path.exists():
            st.error(f"Registry not found: {registry_path}")
            return
        review_rows = load_review_rows_from_registry(str(registry_path))
        source_scope_id = review.review_scope_id_for_registry(registry_path)
        source_scope_label = review.display_path(registry_path)
        source_kind = "registry_csv"
        source_path_text = str(registry_path)

    if not review_rows:
        st.warning("No stage 06 review rows were found for the selected source.")
        return

    review_dir = review.review_dir_for_scope(source_scope_id)
    review.ensure_review_workspace(
        review_dir,
        source_scope_id=source_scope_id,
        source_scope_label=source_scope_label,
        source_kind=source_kind,
        source_path_text=source_path_text,
    )
    responses_by_id = review.load_responses_by_id(review_dir)

    completed = review.count_completed_reviews(review_rows, responses_by_id)
    total = len(review_rows)
    st.sidebar.subheader("Review progress")
    st.sidebar.progress(completed / total if total else 0.0, text=f"{completed} of {total} reviewed")
    st.sidebar.caption(f"Responses file: `{review.display_path(review.responses_path(review_dir))}`")

    verification_options = ["All"] + sorted({row.get("count_verification_status", "") for row in review_rows if row.get("count_verification_status")})
    category_options = ["All"] + sorted({row.get("source_category", "") for row in review_rows if row.get("source_category")})
    verification_filter = st.sidebar.selectbox("Verification status", options=verification_options, index=0)
    review_filter = st.sidebar.selectbox("Review status", options=["All", "Pending", "Reviewed", "Needs follow-up"], index=0)
    category_filter = st.sidebar.selectbox("Source category", options=category_options, index=0)
    candidate_filter = st.sidebar.selectbox("Candidate count", options=["All", "1", "2+"], index=0)
    manual_review_filter = st.sidebar.selectbox(
        "Pipeline manual review",
        options=["All", "Requires manual review", "No manual review"],
        index=0,
    )

    visible_rows = filtered_rows(
        review_rows,
        verification_filter=verification_filter,
        review_filter=review_filter,
        category_filter=category_filter,
        candidate_filter=candidate_filter,
        manual_review_filter=manual_review_filter,
        responses_by_id=responses_by_id,
    )
    if not visible_rows:
        st.warning("No rows match the current filters.")
        return

    index_key = f"stage06_review_index::{source_scope_id}"
    filter_key = f"stage06_review_filter::{source_scope_id}"
    filter_signature = "|".join(
        [
            source_mode,
            source_scope_id,
            verification_filter,
            review_filter,
            category_filter,
            candidate_filter,
            manual_review_filter,
        ]
    )
    if st.session_state.get(filter_key) != filter_signature:
        st.session_state[filter_key] = filter_signature
        st.session_state[index_key] = first_pending_index(visible_rows, responses_by_id)

    labels = [
        (
            f"{row['paper_id']} | count {row.get('likely_sps_case_count', '?')} | "
            f"{row.get('count_verification_status', 'unknown')} | "
            f"review {review_status_for_row(row, responses_by_id)} | "
            f"{row.get('title', '')[:70]}"
        )
        for row in visible_rows
    ]
    current_index = max(0, min(int(st.session_state.get(index_key, 0)), len(visible_rows) - 1))
    selected_index = st.sidebar.selectbox(
        "Paper",
        options=list(range(len(visible_rows))),
        index=current_index,
        format_func=labels.__getitem__,
    )
    if selected_index != current_index:
        st.session_state[index_key] = selected_index
        current_index = selected_index

    nav_prev, nav_pending, nav_next = st.columns([1, 1, 1])
    with nav_prev:
        if st.button("Previous", use_container_width=True, disabled=current_index == 0):
            st.session_state[index_key] = current_index - 1
            st.rerun()
    with nav_pending:
        if st.button("First pending", use_container_width=True):
            st.session_state[index_key] = first_pending_index(visible_rows, responses_by_id)
            st.rerun()
    with nav_next:
        if st.button("Next", use_container_width=True, disabled=current_index >= len(visible_rows) - 1):
            st.session_state[index_key] = current_index + 1
            st.rerun()

    review_row = visible_rows[current_index]
    response_row = responses_by_id.get((review_row.get("paper_id") or "").strip(), {})
    prefix = ensure_editor_state(scope_id=source_scope_id, review_row=review_row, response_row=response_row)

    package = load_candidate_package(str(review_row.get("count_candidate_json_path") or ""))
    decision_payload = load_decision_payload(str(review_row.get("count_decision_json_path") or ""))
    evidence_payload = load_evidence_payload(str(review_row.get("count_evidence_json_path") or ""))
    evidence_items = evidence_items_for_display(decision_payload, evidence_payload)

    left_col, right_col = st.columns([3, 2], gap="large")
    with left_col:
        render_pdf_panel(review_row, prefix, evidence_items)

    with right_col:
        st.subheader(f"Paper {review_row['paper_id']}")
        st.markdown(f"**Title**  \n{review_row.get('title') or ''}")
        st.markdown(f"**Authors**  \n{review_row.get('authors') or 'Unknown'}")
        st.markdown(
            f"**Current stage 06 result**  \n"
            f"Final count: `{review_row.get('likely_sps_case_count') or '?'}`  \n"
            f"Confidence: `{review_row.get('count_confidence') or 'unknown'}`  \n"
            f"Basis: `{review_row.get('count_basis') or 'unknown'}`  \n"
            f"Verification: `{review_row.get('count_verification_status') or 'unknown'}`"
        )
        st.markdown(
            f"**Heuristic comparison**  \n"
            f"Heuristic count: `{review_row.get('heuristic_likely_sps_case_count') or '?'}`  \n"
            f"LLM count: `{review_row.get('llm_likely_sps_case_count') or 'not used'}`  \n"
            f"Candidate count: `{review_row.get('heuristic_candidate_count') or '0'}`  \n"
            f"Pipeline manual review: `{review_row.get('count_manual_review_required') or 'false'}`"
        )
        st.caption(
            f"Preferred text: `{review_row.get('preferred_text_json_path') or ''}` "
            f"({review_row.get('preferred_text_source') or 'unknown'})"
        )
        if review_row.get("attached_run_id") and review_row.get("attached_run_id") != review_row.get("run_id"):
            st.caption(
                f"Attached latest run artefacts: `{review_row.get('attached_run_id')}`"
            )
        elif review_row.get("run_id"):
            st.caption(f"Run artefacts: `{review_row.get('run_id')}`")
        if review_row.get("count_candidate_json_path"):
            st.caption(f"Candidate JSON: `{review_row.get('count_candidate_json_path')}`")
        if review_row.get("count_decision_json_path"):
            st.caption(f"Decision JSON: `{review_row.get('count_decision_json_path')}`")
        if review_row.get("count_evidence_json_path"):
            st.caption(f"Evidence JSON: `{review_row.get('count_evidence_json_path')}`")
        if review_row.get("count_reason"):
            st.markdown(f"**Pipeline reasoning**  \n{review_row['count_reason']}")
        if review_row.get("count_validator_flags"):
            st.markdown(f"**Validator flags**  \n{review_row['count_validator_flags']}")

        st.subheader("Review")
        prediction_correct_key = editor_key(prefix, "prediction_correct")
        reviewed_count_key = editor_key(prefix, "reviewed_count")
        review_status_key = editor_key(prefix, "review_status")
        reviewer_notes_key = editor_key(prefix, "reviewer_notes")
        reviewer_id_key = editor_key(prefix, "reviewer_id")

        st.toggle("Prediction correct", key=prediction_correct_key)
        if st.session_state[prediction_correct_key]:
            st.session_state[reviewed_count_key] = normalise_count_text(review_row.get("likely_sps_case_count") or "")
        st.text_input(
            "Reviewed count",
            key=reviewed_count_key,
            disabled=bool(st.session_state[prediction_correct_key]),
        )
        st.selectbox("Review status", options=REVIEW_STATUS_OPTIONS, key=review_status_key)
        st.text_area("Reviewer notes", key=reviewer_notes_key, height=140)
        st.text_input("Reviewer ID", key=reviewer_id_key)

        save_col, save_next_col = st.columns(2)
        save_clicked = save_col.button("Save", use_container_width=True)
        save_next_clicked = save_next_col.button("Save and next", use_container_width=True)
        if save_clicked or save_next_clicked:
            reviewed_count_text = normalise_count_text(str(st.session_state[reviewed_count_key]))
            try:
                int(reviewed_count_text)
            except ValueError:
                st.error("The reviewed count must be an integer.")
                st.stop()

            response_to_save = review.build_response_row(
                source_scope_id=source_scope_id,
                source_scope_label=source_scope_label,
                review_row=review_row,
                prediction_correct=bool(st.session_state[prediction_correct_key]),
                reviewed_count=reviewed_count_text,
                review_status=str(st.session_state[review_status_key]).strip(),
                reviewer_notes=str(st.session_state[reviewer_notes_key]).strip(),
                reviewer_id=str(st.session_state[reviewer_id_key]).strip(),
                existing_row=response_row,
            )
            review.save_response_row(review_dir, review_rows, response_to_save)
            if save_next_clicked and current_index < len(visible_rows) - 1:
                st.session_state[index_key] = current_index + 1
            st.rerun()

        if package:
            st.subheader("Heuristic candidates")
            st.dataframe(candidate_rows_for_display(package), use_container_width=True, hide_index=True)
            candidate_ids = candidate_options(package)
            preferred_candidate_id = str(review_row.get("llm_selected_candidate_id") or package.get("preferred_candidate_id") or "")
            default_candidate_index = candidate_ids.index(preferred_candidate_id) if preferred_candidate_id in candidate_ids else 0
            selected_candidate_id = st.selectbox(
                "Candidate to inspect",
                options=candidate_ids,
                index=default_candidate_index,
                format_func=lambda candidate_id: next(
                    (
                        f"{candidate_id} | count {candidate.get('proposed_count')} | {candidate.get('count_basis')}"
                        for candidate in package.get("candidates") or []
                        if str(candidate.get("candidate_id") or "") == candidate_id
                    ),
                    candidate_id,
                ),
            )
            selected_candidate = candidate_by_id(package, selected_candidate_id)
            st.text_area(
                "Candidate rationale",
                value=str(selected_candidate.get("rationale") or "No rationale available."),
                height=80,
                disabled=True,
            )
            st.text_area(
                "Candidate evidence text",
                value=str(selected_candidate.get("evidence_text") or "No candidate evidence text is stored."),
                height=220,
                disabled=True,
            )

        if decision_payload:
            decision = decision_payload.get("decision") or {}
            st.subheader("LLM adjudication")
            st.markdown(
                f"**Model**  \n{decision_payload.get('model_id') or 'unknown'}  \n"
                f"**Decision type**  \n{decision.get('decision_type') or 'unknown'}  \n"
                f"**Verification status**  \n{decision_payload.get('verification_status') or review_row.get('count_verification_status') or 'unknown'}"
            )
            if decision.get("count_reasoning_summary"):
                st.markdown(f"**LLM reasoning**  \n{decision['count_reasoning_summary']}")
            validator_flags = decision_payload.get("validator_flags") or []
            if validator_flags:
                st.markdown(f"**Validator flags**  \n{'; '.join(str(flag) for flag in validator_flags)}")

        if evidence_items:
            st.subheader("Evidence")
            for index, item in enumerate(evidence_items, start=1):
                quote = str(item.get("quote") or "").strip()
                page = review.parse_int(item.get("page"), default=0)
                button_label = f"Search evidence {index}"
                if page > 0:
                    button_label += f" (p.{page})"
                st.button(
                    button_label,
                    key=editor_key(prefix, f"evidence_jump::{index}"),
                    on_click=set_search_target,
                    args=(prefix, quote, page if page > 0 else None),
                    use_container_width=True,
                )
                support_bits = []
                if item.get("section"):
                    support_bits.append(str(item["section"]))
                if item.get("supports"):
                    support_bits.append(str(item["supports"]))
                if support_bits:
                    st.caption(" | ".join(support_bits))
                st.code(quote or "No quote stored.", language="text")

        with st.expander("Stored text context", expanded=False):
            if package.get("llm_evidence_text"):
                st.text_area(
                    "LLM evidence pack",
                    value=str(package.get("llm_evidence_text") or ""),
                    height=220,
                    disabled=True,
                )
            if package.get("abstract_text"):
                st.text_area("Abstract text", value=str(package.get("abstract_text") or ""), height=180, disabled=True)
            if package.get("early_body_text"):
                st.text_area("Preferred text window", value=str(package.get("early_body_text") or ""), height=260, disabled=True)

        with st.expander("Raw payloads", expanded=False):
            if package:
                st.caption("Candidate package")
                st.json(package)
            if decision_payload:
                st.caption("Decision payload")
                st.json(decision_payload)
            elif evidence_payload:
                st.caption("Evidence payload")
                st.json(evidence_payload)


if __name__ == "__main__":
    main()
