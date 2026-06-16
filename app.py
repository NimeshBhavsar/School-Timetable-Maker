from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from core import (
    BREAK_AFTER_SLOT,
    SchoolData,
    build_class_grid,
    build_teacher_grid,
    class_assignment_options,
    default_school_data,
    load_school_data,
    normalize_list,
    parse_teacher_subjects,
    save_school_data,
    school_data_from_json,
    school_data_to_json,
    teacher_assignment_options,
    teacher_subject_text,
    timetable_view_for_class,
    timetable_view_for_teacher,
    weekly_subject_class_summary_for_teacher,
    weekly_subject_summary_for_class,
    update_from_class_grid,
    update_from_teacher_grid,
    validate_schedule,
)


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "timetable_data.json"


st.set_page_config(page_title="School Timetable Maker", layout="wide")


def init_state() -> None:
    if "data" not in st.session_state:
        st.session_state.data = load_school_data(DATA_FILE)
    if "last_message" not in st.session_state:
        st.session_state.last_message = ""


def set_data(data: SchoolData) -> None:
    st.session_state.data = data


def text_block(label: str, value: str, height: int = 120) -> str:
    return st.text_area(label, value=value, height=height)


def parse_school_inputs() -> SchoolData:
    current: SchoolData = st.session_state.data
    school_name = st.text_input("School name", value=current.school_name)
    classes_text = st.text_area(
        "Class / section list",
        value="\n".join(current.classes),
        height=120,
        help="One class-section per line, for example 7-A",
    )
    subjects_text = st.text_area(
        "Subjects",
        value="\n".join(current.subjects),
        height=120,
        help="One subject per line",
    )
    teachers_text = st.text_area(
        "Teachers and subjects",
        value=teacher_subject_text(current.teacher_subjects) or "Mr. Sharma: Math, Science",
        height=160,
        help="One teacher per line. Use Teacher: Subject1, Subject2",
    )

    teachers, teacher_subjects = parse_teacher_subjects(teachers_text)
    classes = normalize_list(classes_text)
    subjects = normalize_list(subjects_text)
    if not teachers:
        teachers = current.teachers.copy()
        teacher_subjects = current.teacher_subjects.copy()

    return SchoolData(
        school_name=school_name.strip() or "School Timetable",
        days=current.days,
        slots=current.slots,
        classes=classes or current.classes,
        teachers=teachers,
        subjects=subjects or current.subjects,
        teacher_subjects=teacher_subjects,
        entries=current.entries,
    )


def save_current_data(data: SchoolData) -> None:
    save_school_data(data, DATA_FILE)
    set_data(data)
    st.session_state.last_message = "Saved timetable data."


def render_status() -> None:
    data: SchoolData = st.session_state.data
    issues = validate_schedule(data)
    if issues:
        st.error("Schedule issues detected")
        st.write("\n".join(f"- {issue}" for issue in issues[:20]))
        if len(issues) > 20:
            st.caption(f"And {len(issues) - 20} more issues.")
    else:
        st.success("No timetable conflicts found.")

    if st.session_state.last_message:
        st.info(st.session_state.last_message)


init_state()

data: SchoolData = st.session_state.data

st.title("School Timetable Maker")
st.caption("Minimal timetable editor for classes, sections, and teachers. Fixed day structure: 5 periods, break, then 5 periods.")

with st.sidebar:
    st.header("School setup")
    edited_data = parse_school_inputs()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Save settings", use_container_width=True):
            save_current_data(edited_data)
            st.rerun()
    with col_b:
        if st.button("Reset sample", use_container_width=True):
            sample = default_school_data()
            save_current_data(sample)
            st.rerun()

    st.divider()
    st.subheader("Load / export")
    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded is not None:
        try:
            imported = school_data_from_json(uploaded.read().decode("utf-8"))
            save_current_data(imported)
            st.success("Imported file.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    st.download_button(
        "Download JSON",
        school_data_to_json(st.session_state.data),
        file_name="timetable_data.json",
        mime="application/json",
        use_container_width=True,
    )

render_status()

st.markdown(
    f"**Daily structure:** Period 1-5, Break, Period 6-10. Break is fixed after period {BREAK_AFTER_SLOT}."
)

editor_tab, view_tab, data_tab = st.tabs(["Timetable editor", "Timetable views", "Data summary"])

with editor_tab:
    mode = st.radio("Edit mode", ["By class", "By teacher"], horizontal=True)

    if mode == "By class":
        left, right = st.columns([3, 1])
        with left:
            target = st.selectbox("Choose class / section", st.session_state.data.classes)
            options = class_assignment_options(st.session_state.data)
            grid = build_class_grid(st.session_state.data, target)
            edited_grid = st.data_editor(
                grid,
                use_container_width=True,
                num_rows="fixed",
                hide_index=False,
                column_config={slot: st.column_config.SelectboxColumn(slot, options=options) for slot in grid.columns},
                key=f"class_grid_{target}",
            )
            if st.button("Apply class timetable", type="primary"):
                updated = st.session_state.data
                update_from_class_grid(updated, target, edited_grid)
                save_current_data(updated)
                st.rerun()

            st.caption("Cell format: Subject | Teacher")

        with right:
            st.subheader("Weekly summary")
            class_summary = weekly_subject_summary_for_class(st.session_state.data, target)
            if class_summary.empty:
                st.info("No lessons scheduled yet.")
            else:
                st.dataframe(class_summary, use_container_width=True, hide_index=True)

    else:
        left, right = st.columns([3, 1])
        with left:
            target = st.selectbox("Choose teacher", st.session_state.data.teachers)
            options = teacher_assignment_options(st.session_state.data, target)
            grid = build_teacher_grid(st.session_state.data, target)
            edited_grid = st.data_editor(
                grid,
                use_container_width=True,
                num_rows="fixed",
                hide_index=False,
                column_config={slot: st.column_config.SelectboxColumn(slot, options=options) for slot in grid.columns},
                key=f"teacher_grid_{target}",
            )
            if st.button("Apply teacher timetable", type="primary"):
                updated = st.session_state.data
                update_from_teacher_grid(updated, target, edited_grid)
                save_current_data(updated)
                st.rerun()

            st.caption("Cell format: Class-Section | Subject")

        with right:
            st.subheader("Weekly summary")
            teacher_summary = weekly_subject_class_summary_for_teacher(st.session_state.data, target)
            if teacher_summary.empty:
                st.info("No lessons scheduled yet.")
            else:
                st.dataframe(teacher_summary, use_container_width=True, hide_index=True)

with view_tab:
    left, right = st.columns(2)
    with left:
        class_choice = st.selectbox("View class timetable", st.session_state.data.classes, key="class_view")
        st.dataframe(timetable_view_for_class(st.session_state.data, class_choice), use_container_width=True)
    with right:
        teacher_choice = st.selectbox("View teacher timetable", st.session_state.data.teachers, key="teacher_view")
        st.dataframe(timetable_view_for_teacher(st.session_state.data, teacher_choice), use_container_width=True)

with data_tab:
    st.subheader("Current records")
    entries_df = pd.DataFrame(st.session_state.data.entries)
    if entries_df.empty:
        st.info("No timetable entries yet.")
    else:
        st.dataframe(entries_df.sort_values(["class_section", "day", "slot"]), use_container_width=True)

    st.subheader("Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Classes", len(st.session_state.data.classes))
    with c2:
        st.metric("Teachers", len(st.session_state.data.teachers))
    with c3:
        st.metric("Subjects", len(st.session_state.data.subjects))

    st.caption("Tip: create one class timetable, then use the teacher view to verify or fill teacher loads.")
