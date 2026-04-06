from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from src.validation.stage04_model_benchmark import _review, _shared


PDF_VIEW_HEIGHT = 1000
PDF_SEARCH_RESULT_LIMIT = 12


@st.cache_data(show_spinner=False)
def load_pdf_bytes(pdf_path_text: str) -> bytes:
    return _review.resolve_repo_path(pdf_path_text).read_bytes()


@st.cache_data(show_spinner=False)
def load_text_pages(text_json_path_text: str) -> list[dict[str, object]]:
    return _review.load_text_page_entries(text_json_path_text)


@st.cache_data(show_spinner=False)
def load_predictions_cached(benchmark_id: str) -> dict[str, dict[str, dict[str, Any]]]:
    return _review.load_predictions_by_model(_shared.benchmark_paths(benchmark_id))


@st.cache_data(show_spinner=False)
def load_benchmark_rows_cached(benchmark_id: str) -> list[dict[str, str]]:
    return _shared.load_csv_rows(_shared.benchmark_paths(benchmark_id).benchmark_set_path)


def editor_prefix(benchmark_id: str, paper_id: str) -> str:
    return f"stage04_model_benchmark::{benchmark_id}::{paper_id}"


def editor_key(prefix: str, suffix: str) -> str:
    return f"{prefix}::{suffix}"


def available_benchmarks() -> list[Path]:
    return list(reversed(_review.discover_benchmark_directories()))


def prediction_result(
    predictions_by_model: dict[str, dict[str, dict[str, Any]]],
    *,
    model_name: str,
    paper_id: str,
) -> dict[str, Any] | None:
    prediction = _review.model_prediction_for_paper(
        predictions_by_model,
        model_name=model_name,
        paper_id=paper_id,
    )
    if prediction is None:
        return None
    return dict(prediction.get("result") or {})


def bool_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "1"}:
        return "yes"
    if text in {"false", "no", "0"}:
        return "no"
    return ""


def preferred_start_page(row: dict[str, str]) -> int:
    return max(1, int((row.get("preferred_start_page") or "1").strip() or "1"))


def first_row_index(
    rows: list[dict[str, str]],
    notes_by_id: dict[str, dict[str, str]],
    *,
    status_filter: str,
) -> int:
    for index, row in enumerate(rows):
        paper_id = (row.get("paper_id") or "").strip()
        status = (notes_by_id.get(paper_id, {}).get("review_status") or _review.DEFAULT_REVIEW_STATUS).strip()
        ambiguity = (row.get("gold_ambiguity_tier") or "").strip()
        if status_filter == "pending" and status == "pending":
            return index
        if status_filter == "flagged" and status == "flagged":
            return index
        if status_filter == "ambiguous" and ambiguity == "ambiguous":
            return index
    return 0


def model_summary_table(
    row: dict[str, str],
    predictions_by_model: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, str]]:
    paper_id = (row.get("paper_id") or "").strip()
    gold_category = (row.get("gold_source_category") or "").strip()
    gold_original = (row.get("gold_original_sps_data") or "").strip()
    gold_individual = bool_label(row.get("gold_contains_individual_level_data"))
    gold_group = bool_label(row.get("gold_contains_group_level_data"))
    gold_count = (row.get("gold_extractable_sps_case_count") or "").strip()

    summary_rows: list[dict[str, str]] = []
    for model_name in _review.MODEL_DISPLAY_ORDER:
        result = prediction_result(predictions_by_model, model_name=model_name, paper_id=paper_id)
        if result is None:
            summary_rows.append(
                {
                    "model": model_name,
                    "category": "missing",
                    "category_match": "",
                    "original_data": "",
                    "individual": "",
                    "group": "",
                    "count": "",
                    "manual_review": "",
                    "confidence": "",
                }
            )
            continue

        category = str(result.get("source_type") or "").strip()
        original = str(result.get("original_sps_spectrum_data") or "").strip()
        individual = bool_label(result.get("contains_individual_level_data"))
        group = bool_label(result.get("contains_group_level_data"))
        count_text = str(result.get("likely_sps_case_count") or "").strip()
        summary_rows.append(
            {
                "model": model_name,
                "category": category,
                "category_match": "match" if category == gold_category else "mismatch",
                "original_data": (
                    f"{original} ({'match' if original == gold_original else 'mismatch'})"
                    if gold_original and original
                    else original
                ),
                "individual": (
                    f"{individual} ({'match' if individual == gold_individual else 'mismatch'})"
                    if gold_individual and individual
                    else individual
                ),
                "group": (
                    f"{group} ({'match' if group == gold_group else 'mismatch'})"
                    if gold_group and group
                    else group
                ),
                "count": (
                    f"{count_text} ({'match' if gold_count and count_text == gold_count else 'check'})"
                    if count_text
                    else ""
                ),
                "manual_review": bool_label(result.get("manual_review_required")),
                "confidence": str(result.get("confidence") or "").strip(),
            }
        )
    return summary_rows


def ensure_editor_state(
    *,
    benchmark_id: str,
    row: dict[str, str],
    notes_row: dict[str, str],
) -> str:
    paper_id = (row.get("paper_id") or "").strip()
    prefix = editor_prefix(benchmark_id, paper_id)
    active_key = "stage04_model_benchmark_active_editor"
    if st.session_state.get(active_key) != prefix:
        st.session_state[editor_key(prefix, "review_status")] = (
            (notes_row.get("review_status") or _review.DEFAULT_REVIEW_STATUS).strip()
            or _review.DEFAULT_REVIEW_STATUS
        )
        st.session_state[editor_key(prefix, "review_notes")] = (notes_row.get("review_notes") or "").strip()
        st.session_state[editor_key(prefix, "pdf_search_query")] = ""
        st.session_state[editor_key(prefix, "pdf_view_page")] = preferred_start_page(row)
        st.session_state[active_key] = prefix
    return prefix


def render_prediction_block(
    *,
    model_name: str,
    result: dict[str, Any] | None,
    gold_row: dict[str, str],
) -> None:
    st.markdown(f"### {model_name}")
    if result is None:
        st.info("No prediction saved for this model.")
        return

    gold_category = (gold_row.get("gold_source_category") or "").strip()
    gold_original = (gold_row.get("gold_original_sps_data") or "").strip()
    gold_individual = bool_label(gold_row.get("gold_contains_individual_level_data"))
    gold_group = bool_label(gold_row.get("gold_contains_group_level_data"))
    gold_count = (gold_row.get("gold_extractable_sps_case_count") or "").strip()

    predicted_category = str(result.get("source_type") or "").strip()
    predicted_original = str(result.get("original_sps_spectrum_data") or "").strip()
    predicted_individual = bool_label(result.get("contains_individual_level_data"))
    predicted_group = bool_label(result.get("contains_group_level_data"))
    predicted_count = str(result.get("likely_sps_case_count") or "").strip()

    st.write(
        {
            "category": predicted_category,
            "category_match": predicted_category == gold_category,
            "original_data": predicted_original,
            "original_match": predicted_original == gold_original if gold_original and predicted_original else None,
            "individual": predicted_individual,
            "individual_match": predicted_individual == gold_individual if gold_individual and predicted_individual else None,
            "group": predicted_group,
            "group_match": predicted_group == gold_group if gold_group and predicted_group else None,
            "case_count": predicted_count,
            "count_confidence": str(result.get("count_confidence") or "").strip(),
            "manual_review": bool_label(result.get("manual_review_required")),
            "count_manual_review": bool_label(result.get("count_manual_review_required")),
            "confidence": str(result.get("confidence") or "").strip(),
        }
    )

    reasoning = str(result.get("reasoning_summary") or "").strip()
    if reasoning:
        st.caption("Categorisation reasoning")
        st.write(reasoning)

    count_reasoning = str(result.get("count_reasoning_summary") or "").strip()
    if count_reasoning:
        st.caption("Count reasoning")
        st.write(count_reasoning)

    evidence = list(result.get("evidence") or [])
    if evidence:
        st.caption("Evidence")
        for idx, item in enumerate(evidence, start=1):
            section = str(item.get("section") or "").strip()
            page = item.get("page")
            supports = str(item.get("supports") or "").strip()
            quote = str(item.get("quote") or "").strip()
            prefix_bits = [f"{idx}."]
            if page not in {None, ""}:
                prefix_bits.append(f"p.{page}")
            if section:
                prefix_bits.append(section)
            if supports:
                prefix_bits.append(f"supports: {supports}")
            st.markdown(" | ".join(prefix_bits))
            st.code(quote, language="text")


def main() -> None:
    st.set_page_config(page_title="Stage 04 Benchmark Reviewer", layout="wide")
    st.title("Stage 04 Benchmark Reviewer")
    st.caption("Review frozen benchmark papers and compare model predictions side by side.")

    benchmark_dirs = available_benchmarks()
    if not benchmark_dirs:
        st.warning(
            "No benchmark sets were found. Run `build_benchmark_set.py` first."
        )
        return

    benchmark_lookup = {_review.benchmark_label(path): path for path in benchmark_dirs}
    selected_benchmark = st.sidebar.selectbox("Benchmark", options=list(benchmark_lookup.keys()))
    paths = _shared.benchmark_paths(selected_benchmark)
    benchmark_rows = load_benchmark_rows_cached(selected_benchmark)
    predictions_by_model = load_predictions_cached(selected_benchmark)
    notes_by_id = _review.load_review_notes_by_id(paths)

    if not benchmark_rows:
        st.error(f"No benchmark rows found in {_review.display_path(paths.benchmark_set_path)}.")
        return

    status_counts = _review.note_status_counts(benchmark_rows, notes_by_id)
    model_coverage = {
        model_name: len(predictions_by_model.get(model_name, {}))
        for model_name in _review.MODEL_DISPLAY_ORDER
    }
    st.sidebar.subheader("Review progress")
    total = len(benchmark_rows)
    st.sidebar.progress(
        status_counts["reviewed"] / total if total else 0.0,
        text=f"{status_counts['reviewed']} of {total} marked reviewed",
    )
    st.sidebar.caption(
        f"Pending: {status_counts['pending']} | Flagged: {status_counts['flagged']}"
    )
    st.sidebar.subheader("Model coverage")
    for model_name, count in model_coverage.items():
        st.sidebar.caption(f"{model_name}: {count}/{total}")
    st.sidebar.caption(f"Notes file: `{_review.display_path(_review.review_notes_path(paths))}`")

    filter_mode = st.sidebar.selectbox(
        "Focus",
        options=("all", "pending", "flagged", "ambiguous"),
        index=0,
    )

    filtered_rows = []
    for row in benchmark_rows:
        paper_id = (row.get("paper_id") or "").strip()
        note_status = (notes_by_id.get(paper_id, {}).get("review_status") or _review.DEFAULT_REVIEW_STATUS).strip()
        ambiguity = (row.get("gold_ambiguity_tier") or "").strip()
        include = True
        if filter_mode == "pending":
            include = note_status == "pending"
        elif filter_mode == "flagged":
            include = note_status == "flagged"
        elif filter_mode == "ambiguous":
            include = ambiguity == "ambiguous"
        if include:
            filtered_rows.append(row)

    if not filtered_rows:
        st.info(f"No papers match the current `{filter_mode}` filter.")
        return

    benchmark_state_key = "stage04_model_benchmark_selected"
    filter_state_key = "stage04_model_benchmark_filter"
    if (
        st.session_state.get(benchmark_state_key) != selected_benchmark
        or st.session_state.get(filter_state_key) != filter_mode
    ):
        st.session_state[benchmark_state_key] = selected_benchmark
        st.session_state[filter_state_key] = filter_mode
        st.session_state["stage04_model_benchmark_index"] = first_row_index(
            filtered_rows,
            notes_by_id,
            status_filter=filter_mode,
        )

    current_index = st.session_state.get("stage04_model_benchmark_index", 0)
    current_index = max(0, min(current_index, len(filtered_rows) - 1))

    jump_options = [
        f"{index + 1}. {(row.get('paper_id') or '').strip()} | {(row.get('benchmark_role') or '').strip()} | {(row.get('title') or '').strip()[:60]}"
        for index, row in enumerate(filtered_rows)
    ]
    jump_selection = st.sidebar.selectbox(
        "Jump to paper",
        options=range(len(filtered_rows)),
        format_func=jump_options.__getitem__,
        index=current_index,
    )
    if jump_selection != current_index:
        st.session_state["stage04_model_benchmark_index"] = jump_selection
        st.rerun()

    nav_prev, nav_next = st.columns([1, 1])
    with nav_prev:
        if st.button("Previous", use_container_width=True, disabled=current_index == 0):
            st.session_state["stage04_model_benchmark_index"] = current_index - 1
            st.rerun()
    with nav_next:
        if st.button("Next", use_container_width=True, disabled=current_index >= len(filtered_rows) - 1):
            st.session_state["stage04_model_benchmark_index"] = current_index + 1
            st.rerun()

    row = filtered_rows[current_index]
    paper_id = (row.get("paper_id") or "").strip()
    notes_row = notes_by_id.get(paper_id, {})
    prefix = ensure_editor_state(
        benchmark_id=selected_benchmark,
        row=row,
        notes_row=notes_row,
    )

    left_col, right_col = st.columns([3, 2], gap="large")
    with left_col:
        st.subheader(f"PDF: {paper_id}")
        pdf_path_relative = (row.get("pdf_path_relative") or "").strip()
        text_json_path_relative = (row.get("preferred_text_json_path") or "").strip()
        pdf_path = _review.resolve_repo_path(pdf_path_relative)
        preferred_page = preferred_start_page(row)
        pdf_view_page_key = editor_key(prefix, "pdf_view_page")
        pdf_search_query_key = editor_key(prefix, "pdf_search_query")
        if pdf_path.exists():
            st.caption(_review.display_path(pdf_path))
            if text_json_path_relative:
                page_entries = load_text_pages(text_json_path_relative)
                page_count = len(page_entries)
                search_col, page_col, reset_col = st.columns([2, 1, 1])
                with search_col:
                    st.text_input(
                        "Search PDF text",
                        key=pdf_search_query_key,
                        placeholder="Enter a phrase to find matching pages",
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
                    if st.button("Suggested page", use_container_width=True):
                        st.session_state[pdf_view_page_key] = preferred_page
                        st.rerun()

                search_query = str(st.session_state[pdf_search_query_key]).strip()
                if search_query:
                    matches = _review.search_text_page_entries(
                        page_entries,
                        search_query,
                        max_results=PDF_SEARCH_RESULT_LIMIT,
                    )
                    if matches:
                        st.caption(
                            f"Found {sum(int(match['match_count']) for match in matches)} match(es) across {len(matches)} page(s)."
                        )
                        for match in matches:
                            page_num = int(match["page_num"])
                            if st.button(
                                f"Page {page_num} ({match['match_count']} hit(s))",
                                key=editor_key(prefix, f"search::{page_num}"),
                                use_container_width=True,
                            ):
                                st.session_state[pdf_view_page_key] = page_num
                                st.rerun()
                            st.caption(str(match["snippet"]))
                    else:
                        st.info("No matching pages were found in the extracted text for this paper.")
            pdf_viewer(
                load_pdf_bytes(pdf_path_relative),
                key=editor_key(prefix, f"pdf::{st.session_state[pdf_view_page_key]}"),
                width="100%",
                height=PDF_VIEW_HEIGHT,
                render_text=True,
                zoom_level="auto",
                scroll_to_page=int(st.session_state[pdf_view_page_key]),
                scroll_behavior="instant",
            )
        else:
            st.error(f"PDF not found: {_review.display_path(pdf_path)}")

    with right_col:
        st.subheader("Paper summary")
        st.markdown(f"**Title**  \n{(row.get('title') or '').strip()}")
        st.markdown(f"**Authors**  \n{(row.get('authors') or '').strip() or 'Unknown'}")
        st.markdown(
            f"**Role**  \n{(row.get('benchmark_role') or '').strip()} | {(row.get('gold_ambiguity_tier') or '').strip()}"
        )
        st.markdown(
            f"**Text source**  \n{(row.get('preferred_text_source') or '').strip()} | trim status: {(row.get('trim_status') or '').strip() or 'none'}"
        )

        st.subheader("Gold labels")
        st.write(
            {
                "category": (row.get("gold_source_category") or "").strip(),
                "original_data": (row.get("gold_original_sps_data") or "").strip(),
                "individual_level": bool_label(row.get("gold_contains_individual_level_data")),
                "group_level": bool_label(row.get("gold_contains_group_level_data")),
                "extractable_case_count": (row.get("gold_extractable_sps_case_count") or "").strip(),
                "label_status": (row.get("gold_label_status") or "").strip(),
            }
        )

        st.subheader("Model comparison")
        st.dataframe(model_summary_table(row, predictions_by_model), use_container_width=True, hide_index=True)

        st.subheader("Review note")
        st.selectbox(
            "Status",
            options=list(_review.REVIEW_STATUS_OPTIONS),
            key=editor_key(prefix, "review_status"),
        )
        st.text_area(
            "Notes",
            key=editor_key(prefix, "review_notes"),
            height=140,
            placeholder="Add any comments about disagreements, weak evidence, or gold-label concerns.",
        )
        if st.button("Save note", use_container_width=True):
            notes_by_id[paper_id] = _review.build_review_note_row(
                benchmark_id=selected_benchmark,
                paper_id=paper_id,
                review_status=str(st.session_state[editor_key(prefix, "review_status")]),
                review_notes=str(st.session_state[editor_key(prefix, "review_notes")]),
            )
            _review.write_review_notes(paths, notes_by_id)
            st.cache_data.clear()
            st.success("Review note saved.")

        with st.expander("Detailed model outputs", expanded=False):
            for model_name in _review.MODEL_DISPLAY_ORDER:
                render_prediction_block(
                    model_name=model_name,
                    result=prediction_result(predictions_by_model, model_name=model_name, paper_id=paper_id),
                    gold_row=row,
                )


if __name__ == "__main__":
    main()
