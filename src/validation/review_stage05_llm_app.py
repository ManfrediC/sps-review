from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

PIPELINE_DIR = Path(__file__).resolve().parents[1] / "pipelines"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from src.pipelines import _proceedings_trim_llm as trim_llm
from src.pipelines._proceedings_text import flatten_lines
from src.validation import _stage05_review as review


PDF_VIEW_HEIGHT = 1000
PDF_SEARCH_RESULT_LIMIT = 12
PDF_ZOOM_MIN = 0.5
PDF_ZOOM_MAX = 3.0
PDF_ZOOM_STEP = 0.25
PDF_DEFAULT_ZOOM = 1.0

DEFAULT_CANDIDATE_REGISTRY_PATH = review.REPO_ROOT / "data" / "references" / "text_trim_llm_candidate_registry.csv"
DEFAULT_FINAL_REGISTRY_PATH = review.REPO_ROOT / "data" / "references" / "text_trim_llm_registry.csv"


@st.cache_data(show_spinner=False)
def load_pdf_bytes(pdf_path_text: str) -> bytes:
    return review.resolve_repo_path(pdf_path_text).read_bytes()


@st.cache_data(show_spinner=False)
def load_text_pages(text_json_path_text: str) -> list[dict[str, object]]:
    return review.load_text_page_entries(text_json_path_text)


@st.cache_data(show_spinner=False)
def load_registry_rows(path: str) -> list[dict[str, str]]:
    return review.load_csv_rows(Path(path))


@st.cache_data(show_spinner=False)
def load_trimmed_preview(trimmed_text_json_path_text: str) -> str:
    trimmed_path = review.resolve_repo_path(trimmed_text_json_path_text)
    if not trimmed_path.exists():
        return ""
    payload = json.loads(trimmed_path.read_text(encoding="utf-8"))
    lines: list[str] = []
    for page in payload.get("pages") or []:
        lines.extend(line.strip() for line in str(page.get("text") or "").splitlines() if line.strip())
    if not lines:
        return ""
    if len(lines) <= 18:
        return "\n".join(lines)
    preview = lines[:10] + ["...", "..."] + lines[-8:]
    return "\n".join(preview)


def bool_label(value: str) -> str:
    return "yes" if str(value or "").strip().lower() == "true" else "no"


def parse_int(value: str, default: int = 0) -> int:
    return review.parse_int(value, default=default)


def editor_prefix(paper_id: str) -> str:
    return f"stage05_llm_review::{paper_id}"


def editor_key(prefix: str, suffix: str) -> str:
    return f"{prefix}::{suffix}"


def clamp_zoom_level(value: float) -> float:
    return max(PDF_ZOOM_MIN, min(PDF_ZOOM_MAX, round(value, 2)))


def adjust_zoom_level(key: str, delta: float) -> None:
    current = float(st.session_state.get(key, PDF_DEFAULT_ZOOM))
    st.session_state[key] = clamp_zoom_level(current + delta)


def set_session_value(key: str, value: int | str | float) -> None:
    st.session_state[key] = value


def load_review_rows(candidate_registry_path_text: str, final_registry_path_text: str) -> list[dict[str, str]]:
    candidate_registry_path = Path(candidate_registry_path_text)
    final_registry_path = Path(final_registry_path_text)
    if not candidate_registry_path.exists():
        return []
    candidate_rows = {row["paper_id"]: row for row in load_registry_rows(str(candidate_registry_path)) if row.get("paper_id")}
    final_rows = {}
    if final_registry_path.exists():
        final_rows = {row["paper_id"]: row for row in load_registry_rows(str(final_registry_path)) if row.get("paper_id")}
    artifact_rows = review.rows_by_id(review.ARTIFACT_REGISTRY_PATH)

    def sort_key(paper_id: str) -> tuple[int, str]:
        return (parse_int(paper_id, default=10**9), paper_id)

    rows: list[dict[str, str]] = []
    for paper_id in sorted(candidate_rows, key=sort_key):
        candidate_row = candidate_rows[paper_id]
        final_row = final_rows.get(paper_id, {})
        artifact_row = artifact_rows.get(paper_id, {})
        rows.append(
            {
                "paper_id": paper_id,
                "title": str(final_row.get("title") or candidate_row.get("title") or "").strip(),
                "authors": str(final_row.get("authors") or candidate_row.get("authors") or "").strip(),
                "source_filename": str(final_row.get("source_filename") or candidate_row.get("source_filename") or "").strip(),
                "source_text_json_path": str(
                    final_row.get("source_text_json_path") or candidate_row.get("source_text_json_path") or ""
                ).strip(),
                "candidate_json_path": str(
                    candidate_row.get("candidate_json_path") or final_row.get("candidate_source_json_path") or ""
                ).strip(),
                "trimmed_text_json_path": str(final_row.get("trimmed_text_json_path") or "").strip(),
                "pdf_path_relative": review.first_pipe_separated_value(artifact_row.get("pdf_paths_relative") or ""),
                "candidate_count": str(candidate_row.get("candidate_count") or "0").strip(),
                "candidate_heuristics": str(candidate_row.get("candidate_heuristics") or "").strip(),
                "baseline_candidate_id": str(candidate_row.get("baseline_candidate_id") or "").strip(),
                "overshoot_candidate_id": str(candidate_row.get("overshoot_candidate_id") or "").strip(),
                "trim_status": str(final_row.get("trim_status") or candidate_row.get("trim_status") or "").strip(),
                "trim_reason": str(final_row.get("trim_reason") or candidate_row.get("trim_reason") or "").strip(),
                "end_selection_mode": str(final_row.get("end_selection_mode") or "").strip(),
                "llm_decision_type": str(final_row.get("llm_decision_type") or "").strip(),
                "llm_selected_candidate_id": str(final_row.get("llm_selected_candidate_id") or "").strip(),
                "llm_last_abstract_line_global_index": str(
                    final_row.get("llm_last_abstract_line_global_index") or ""
                ).strip(),
                "llm_confidence": str(final_row.get("llm_confidence") or "").strip(),
                "llm_end_reason": str(final_row.get("llm_end_reason") or "").strip(),
                "llm_explanation_short": str(final_row.get("llm_explanation_short") or "").strip(),
                "llm_validation_passed": str(final_row.get("llm_validation_passed") or "").strip(),
                "heuristic_fallback_used": str(final_row.get("heuristic_fallback_used") or "").strip(),
            }
        )
    return rows


def filtered_rows(rows: list[dict[str, str]], trim_filter: str, candidate_filter: str) -> list[dict[str, str]]:
    filtered = rows
    if trim_filter != "All":
        filtered = [row for row in filtered if row["trim_status"] == trim_filter]
    if candidate_filter == "2+":
        filtered = [row for row in filtered if parse_int(row["candidate_count"], default=0) >= 2]
    elif candidate_filter == "1":
        filtered = [row for row in filtered if parse_int(row["candidate_count"], default=0) == 1]
    return filtered


def load_candidate_context(candidate_json_path_text: str) -> tuple[trim_llm.CandidatePackage, list]:
    package = trim_llm.load_candidate_package(review.resolve_repo_path(candidate_json_path_text))
    source_record = json.loads(trim_llm.source_path_from_package(package).read_text(encoding="utf-8"))
    source_lines = flatten_lines(source_record)
    return package, source_lines


def candidate_rows_for_display(package: trim_llm.CandidatePackage) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in package.candidates:
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "heuristic": candidate.heuristic_name,
                "rank": str(candidate.rank),
                "end_line_exclusive": str(candidate.end_index_exclusive),
                "end_page": str(candidate.end_page_index + 1),
                "n_lines": str(candidate.n_lines),
                "tail_metadata": bool_label(trim_llm.bool_text(candidate.contains_tail_metadata)),
                "soft_boundary": bool_label(trim_llm.bool_text(candidate.contains_soft_boundary)),
                "confidence": candidate.confidence_class,
                "rationale": candidate.rationale,
            }
        )
    return rows


def candidate_boundary_preview(package: trim_llm.CandidatePackage, candidate_id: str, source_lines: list) -> str:
    candidate = trim_llm.candidate_by_id(package, candidate_id)
    if candidate is None:
        return "Candidate not found."
    positions = {line.global_index: index for index, line in enumerate(source_lines)}
    end_inclusive = candidate.end_index_exclusive - 1
    end_position = positions.get(end_inclusive)
    if end_position is None:
        return "Candidate end is outside the current source line map."
    start_position = max(0, end_position - 5)
    end_position_exclusive = min(len(source_lines), end_position + 7)
    preview_lines: list[str] = []
    for line_ref in source_lines[start_position:end_position_exclusive]:
        markers: list[str] = []
        if line_ref.global_index == end_inclusive:
            markers.append("included end")
        if line_ref.global_index == candidate.end_index_exclusive:
            markers.append("first excluded")
        marker_text = f" <<< {'; '.join(markers)}" if markers else ""
        preview_lines.append(f"[{line_ref.global_index}] p{line_ref.page_index + 1} {line_ref.text}{marker_text}")
    return "\n".join(preview_lines)


def overshoot_span_preview(review_row: dict[str, str], package: trim_llm.CandidatePackage, source_lines: list) -> str:
    overshoot_candidate = trim_llm.candidate_by_id(package, package.overshoot_candidate_id)
    if overshoot_candidate is None:
        return "Overshoot candidate not found."
    selected_candidate_id = review_row.get("llm_selected_candidate_id") or ""
    selected_last_line = parse_int(review_row.get("llm_last_abstract_line_global_index") or "", default=-1)
    candidate_end_markers: dict[int, list[str]] = {}
    for candidate in package.candidates:
        relative_line_number = candidate.end_index_exclusive - package.matched_start_index
        candidate_end_markers.setdefault(relative_line_number, []).append(f"{candidate.candidate_id} ends")
    selected_candidate = trim_llm.candidate_by_id(package, selected_candidate_id) if selected_candidate_id else None
    selected_candidate_relative = (
        selected_candidate.end_index_exclusive - package.matched_start_index if selected_candidate is not None else None
    )
    selected_last_line_relative = selected_last_line - package.matched_start_index + 1 if selected_last_line >= 0 else None

    overshoot_lines = trim_llm.line_refs_for_span(
        source_lines,
        package.matched_start_index,
        overshoot_candidate.end_index_exclusive,
    )
    preview_lines: list[str] = []
    for line_number, line_ref in enumerate(overshoot_lines, start=1):
        markers = list(candidate_end_markers.get(line_number, []))
        if selected_candidate_relative == line_number:
            markers.append("selected candidate")
        if selected_last_line_relative == line_number:
            markers.append("selected last abstract line")
        marker_text = f" <<< {'; '.join(markers)}" if markers else ""
        preview_lines.append(f"[{line_number:03d}] [g{line_ref.global_index}] p{line_ref.page_index + 1} {line_ref.text}{marker_text}")
    return "\n".join(preview_lines)


def ensure_pdf_state(prefix: str, preferred_page: int) -> tuple[str, str, str]:
    pdf_view_page_key = editor_key(prefix, "pdf_view_page")
    pdf_search_query_key = editor_key(prefix, "pdf_search_query")
    pdf_zoom_level_key = editor_key(prefix, "pdf_zoom_level")
    if pdf_view_page_key not in st.session_state:
        st.session_state[pdf_view_page_key] = preferred_page
    if pdf_search_query_key not in st.session_state:
        st.session_state[pdf_search_query_key] = ""
    if pdf_zoom_level_key not in st.session_state:
        st.session_state[pdf_zoom_level_key] = PDF_DEFAULT_ZOOM
    return pdf_view_page_key, pdf_search_query_key, pdf_zoom_level_key


def render_pdf_panel(review_row: dict[str, str], prefix: str) -> None:
    pdf_path_relative = review_row["pdf_path_relative"]
    text_json_path_relative = review_row["source_text_json_path"]
    preferred_page = 1
    package, _ = load_candidate_context(review_row["candidate_json_path"])
    preferred_page = package.matched_start_page_index + 1
    pdf_view_page_key, pdf_search_query_key, pdf_zoom_level_key = ensure_pdf_state(prefix, preferred_page)

    if not pdf_path_relative:
        st.error("PDF path is missing from the paper artifact registry.")
        return
    pdf_path = review.resolve_repo_path(pdf_path_relative)
    if not pdf_path.exists():
        st.error(f"PDF not found: {review.display_path(pdf_path)}")
        return

    st.caption(f"{review.display_path(pdf_path)}")
    st.caption(f"Suggested start page: {preferred_page}.")
    page_entries = load_text_pages(text_json_path_relative) if text_json_path_relative else []

    if page_entries:
        page_count = len(page_entries)
        search_col, page_col, reset_col = st.columns([2, 1, 1])
        with search_col:
            st.text_input(
                "Search PDF text",
                key=pdf_search_query_key,
                placeholder="Enter a phrase to find matching pages",
                help="Search uses the extracted text JSON and jumps the PDF viewer to matching pages.",
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
                st.caption(f"Found {sum(int(match['match_count']) for match in matches)} match(es) across {len(matches)} page(s).")
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
                st.info("No matching pages were found in the extracted text for this paper.")

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
            value=float(st.session_state[pdf_zoom_level_key]),
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


def main() -> None:
    st.set_page_config(page_title="Stage 05 LLM Review App", layout="wide")
    st.title("Stage 05 LLM Review App")
    st.caption("Inspect the PDF, the final trimmed output, and the heuristic end candidates from the LLM proceedings workflow.")

    candidate_registry_path_text = st.sidebar.text_input(
        "Candidate registry",
        value=str(DEFAULT_CANDIDATE_REGISTRY_PATH),
        help="Use the canonical registry or point the app at a batch-local `text_trim_llm_candidate_registry.csv`.",
    )
    final_registry_path_text = st.sidebar.text_input(
        "Final registry",
        value=str(DEFAULT_FINAL_REGISTRY_PATH),
        help="Use the canonical registry or point the app at a batch-local `text_trim_llm_registry.csv`.",
    )

    rows = load_review_rows(candidate_registry_path_text, final_registry_path_text)
    if not rows:
        st.warning("No LLM stage-05 candidate rows were found at the selected registry paths.")
        return

    trim_options = ["All"] + sorted({row["trim_status"] for row in rows if row["trim_status"]})
    candidate_filter = st.sidebar.selectbox("Candidate count", options=["All", "1", "2+"], index=0)
    trim_filter = st.sidebar.selectbox("Trim status", options=trim_options, index=0)
    visible_rows = filtered_rows(rows, trim_filter, candidate_filter)
    if not visible_rows:
        st.warning("No rows match the current filters.")
        return

    labels = [
        f"{row['paper_id']} | {row['candidate_count']} candidate(s) | {row['trim_status']} | {row['title'][:70]}"
        for row in visible_rows
    ]
    selected_index = st.sidebar.selectbox("Paper", options=range(len(visible_rows)), format_func=labels.__getitem__)
    review_row = visible_rows[selected_index]
    prefix = editor_prefix(review_row["paper_id"])

    left_col, right_col = st.columns([3, 2], gap="large")
    with left_col:
        render_pdf_panel(review_row, prefix)

    with right_col:
        package, source_lines = load_candidate_context(review_row["candidate_json_path"])
        st.subheader(f"Paper {review_row['paper_id']}")
        st.markdown(f"**Title**  \n{review_row['title']}")
        st.markdown(f"**Authors**  \n{review_row['authors'] or 'Unknown'}")
        st.markdown(
            f"**Current LLM status**  \n"
            f"Trim: `{review_row['trim_status'] or 'unknown'}`  \n"
            f"Selection: `{review_row['end_selection_mode'] or 'not yet validated'}`  \n"
            f"Candidates: `{review_row['candidate_count']}`  \n"
            f"Fallback used: `{review_row['heuristic_fallback_used'] or 'false'}`"
        )
        if review_row["trim_reason"]:
            st.markdown(f"**Trim note**  \n{review_row['trim_reason']}")
        if review_row["llm_explanation_short"]:
            st.markdown(f"**LLM explanation**  \n{review_row['llm_explanation_short']}")
        if review_row["candidate_json_path"]:
            st.caption(f"Candidate package: `{review_row['candidate_json_path']}`")
        if review_row["trimmed_text_json_path"]:
            st.caption(f"Trimmed output: `{review_row['trimmed_text_json_path']}`")

        trimmed_preview = load_trimmed_preview(review_row["trimmed_text_json_path"]) if review_row["trimmed_text_json_path"] else ""
        st.text_area(
            "Current trimmed abstract preview",
            value=trimmed_preview or "No final trimmed output is stored for this paper yet.",
            height=240,
            disabled=True,
        )

        st.subheader("Heuristic candidates")
        st.dataframe(candidate_rows_for_display(package), use_container_width=True, hide_index=True)
        candidate_ids = [candidate.candidate_id for candidate in package.candidates]
        default_candidate_index = 0
        if review_row["llm_selected_candidate_id"] in candidate_ids:
            default_candidate_index = candidate_ids.index(review_row["llm_selected_candidate_id"])
        selected_candidate_id = st.selectbox(
            "Candidate boundary to inspect",
            options=candidate_ids,
            index=default_candidate_index,
            format_func=lambda candidate_id: next(
                (
                    f"{candidate.candidate_id} | {candidate.heuristic_name} | end {candidate.end_index_exclusive}"
                    for candidate in package.candidates
                    if candidate.candidate_id == candidate_id
                ),
                candidate_id,
            ),
        )
        st.text_area(
            "Boundary preview around the selected candidate",
            value=candidate_boundary_preview(package, selected_candidate_id, source_lines),
            height=220,
            disabled=True,
        )
        st.text_area(
            "Overshoot span with candidate end markers",
            value=overshoot_span_preview(review_row, package, source_lines),
            height=420,
            disabled=True,
        )


if __name__ == "__main__":
    main()
