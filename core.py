from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple
import json

import pandas as pd


DEFAULT_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DEFAULT_SLOTS = [f"P{i}" for i in range(1, 11)]
BREAK_AFTER_SLOT = 5


@dataclass
class SchoolData:
    school_name: str = "School Timetable"
    days: List[str] = field(default_factory=lambda: DEFAULT_DAYS.copy())
    slots: List[str] = field(default_factory=lambda: DEFAULT_SLOTS.copy())
    classes: List[str] = field(default_factory=lambda: ["7-A", "7-B", "8-A"])
    teachers: List[str] = field(default_factory=lambda: ["Mr. Sharma", "Ms. Khan", "Mr. Patel"])
    subjects: List[str] = field(default_factory=lambda: ["Math", "Science", "English", "Hindi"])
    teacher_subjects: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "Mr. Sharma": ["Math", "Science"],
            "Ms. Khan": ["English", "Hindi"],
            "Mr. Patel": ["Science", "Math"],
        }
    )
    entries: List[Dict[str, str]] = field(default_factory=list)


def default_school_data() -> SchoolData:
    return SchoolData()


def normalize_list(text: str) -> List[str]:
    values: List[str] = []
    for raw in text.splitlines():
        item = raw.strip()
        if item:
            values.append(item)
    return values


def parse_teacher_subjects(text: str) -> Tuple[List[str], Dict[str, List[str]]]:
    teachers: List[str] = []
    mapping: Dict[str, List[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ":" in line:
            teacher, subjects = line.split(":", 1)
            teacher = teacher.strip()
            subject_list = [s.strip() for s in subjects.split(",") if s.strip()]
        elif "-" in line:
            teacher, subjects = line.split("-", 1)
            teacher = teacher.strip()
            subject_list = [s.strip() for s in subjects.split(",") if s.strip()]
        else:
            teacher = line
            subject_list = []
        if teacher not in teachers:
            teachers.append(teacher)
        mapping[teacher] = subject_list
    return teachers, mapping


def teacher_subject_text(teacher_subjects: Dict[str, List[str]]) -> str:
    lines = []
    for teacher, subjects in teacher_subjects.items():
        lines.append(f"{teacher}: {', '.join(subjects)}" if subjects else teacher)
    return "\n".join(lines)


def school_data_to_json(data: SchoolData) -> str:
    return json.dumps(asdict(data), indent=2, ensure_ascii=False)


def school_data_from_json(text: str) -> SchoolData:
    raw = json.loads(text)
    return SchoolData(
        school_name=raw.get("school_name", "School Timetable"),
        days=raw.get("days", DEFAULT_DAYS.copy()),
        slots=raw.get("slots", DEFAULT_SLOTS.copy()),
        classes=raw.get("classes", []),
        teachers=raw.get("teachers", []),
        subjects=raw.get("subjects", []),
        teacher_subjects=raw.get("teacher_subjects", {}),
        entries=raw.get("entries", []),
    )


def load_school_data(path: Path) -> SchoolData:
    if not path.exists():
        return default_school_data()
    return school_data_from_json(path.read_text(encoding="utf-8"))


def save_school_data(data: SchoolData, path: Path) -> None:
    path.write_text(school_data_to_json(data), encoding="utf-8")


def clean_subjects_for_teacher(data: SchoolData, teacher: str) -> List[str]:
    subjects = data.teacher_subjects.get(teacher, [])
    return [s for s in subjects if s in data.subjects] or data.subjects.copy()


def class_assignment_options(data: SchoolData) -> List[str]:
    options = [""]
    seen = set()
    for subject in data.subjects:
        for teacher in data.teachers:
            allowed = data.teacher_subjects.get(teacher, [])
            if allowed and subject not in allowed:
                continue
            option = f"{subject} | {teacher}"
            if option not in seen:
                options.append(option)
                seen.add(option)
    return options


def teacher_assignment_options(data: SchoolData, teacher: str) -> List[str]:
    options = [""]
    allowed_subjects = clean_subjects_for_teacher(data, teacher)
    for class_section in data.classes:
        for subject in allowed_subjects:
            options.append(f"{class_section} | {subject}")
    return options


def _index_entries(entries: List[Dict[str, str]]) -> Dict[Tuple[str, str, str], Dict[str, str]]:
    index: Dict[Tuple[str, str, str], Dict[str, str]] = {}
    for entry in entries:
        key = (entry["class_section"], entry["day"], entry["slot"])
        index[key] = entry
    return index


def build_class_grid(data: SchoolData, class_section: str) -> pd.DataFrame:
    index = _index_entries(data.entries)
    rows = []
    for day in data.days:
        row = {}
        for slot in data.slots:
            entry = index.get((class_section, day, slot))
            row[slot] = f"{entry['subject']} | {entry['teacher']}" if entry else ""
        rows.append(row)
    return pd.DataFrame(rows, index=data.days, columns=data.slots)


def build_teacher_grid(data: SchoolData, teacher: str) -> pd.DataFrame:
    index = _index_entries(data.entries)
    rows = []
    for day in data.days:
        row = {}
        for slot in data.slots:
            match = None
            for entry in index.values():
                if entry["teacher"] == teacher and entry["day"] == day and entry["slot"] == slot:
                    match = entry
                    break
            row[slot] = f"{match['class_section']} | {match['subject']}" if match else ""
        rows.append(row)
    return pd.DataFrame(rows, index=data.days, columns=data.slots)


def parse_class_cell(value: str) -> Tuple[str, str] | None:
    text = str(value).strip()
    if not text:
        return None
    if "|" not in text:
        return None
    subject, teacher = [part.strip() for part in text.split("|", 1)]
    if not subject or not teacher:
        return None
    return subject, teacher


def parse_teacher_cell(value: str) -> Tuple[str, str] | None:
    text = str(value).strip()
    if not text:
        return None
    if "|" not in text:
        return None
    class_section, subject = [part.strip() for part in text.split("|", 1)]
    if not class_section or not subject:
        return None
    return class_section, subject


def update_from_class_grid(data: SchoolData, class_section: str, grid: pd.DataFrame) -> None:
    remaining = [e for e in data.entries if e["class_section"] != class_section]
    new_entries: List[Dict[str, str]] = []
    for day in data.days:
        for slot in data.slots:
            cell = grid.at[day, slot]
            parsed = parse_class_cell(cell)
            if not parsed:
                continue
            subject, teacher = parsed
            new_entries.append(
                {
                    "class_section": class_section,
                    "day": day,
                    "slot": slot,
                    "subject": subject,
                    "teacher": teacher,
                }
            )
    data.entries = remaining + new_entries


def update_from_teacher_grid(data: SchoolData, teacher: str, grid: pd.DataFrame) -> None:
    remaining = [e for e in data.entries if e["teacher"] != teacher]
    new_entries: List[Dict[str, str]] = []
    for day in data.days:
        for slot in data.slots:
            cell = grid.at[day, slot]
            parsed = parse_teacher_cell(cell)
            if not parsed:
                continue
            class_section, subject = parsed
            new_entries.append(
                {
                    "class_section": class_section,
                    "day": day,
                    "slot": slot,
                    "subject": subject,
                    "teacher": teacher,
                }
            )
    data.entries = remaining + new_entries


def validate_schedule(data: SchoolData) -> List[str]:
    issues: List[str] = []
    seen_teacher_slots: Dict[Tuple[str, str], str] = {}
    seen_class_slots: Dict[Tuple[str, str, str], str] = {}

    for entry in data.entries:
        class_section = entry["class_section"]
        day = entry["day"]
        slot = entry["slot"]
        subject = entry["subject"]
        teacher = entry["teacher"]

        if class_section not in data.classes:
            issues.append(f"Unknown class section: {class_section}")
        if teacher not in data.teachers:
            issues.append(f"Unknown teacher: {teacher}")
        if subject not in data.subjects:
            issues.append(f"Unknown subject: {subject}")

        key = (teacher, day, slot)
        label = f"{teacher} on {day} {slot}"
        if key in seen_teacher_slots:
            issues.append(f"Teacher clash: {label} is used by {seen_teacher_slots[key]} and {class_section} - {subject}")
        else:
            seen_teacher_slots[key] = f"{class_section} - {subject}"

        class_key = (class_section, day, slot)
        if class_key in seen_class_slots:
            issues.append(f"Duplicate class slot: {class_section} on {day} {slot}")
        else:
            seen_class_slots[class_key] = teacher

        allowed = data.teacher_subjects.get(teacher, [])
        if allowed and subject not in allowed:
            issues.append(f"Teacher-subject mismatch: {teacher} is not listed for {subject}")

    return issues


def timetable_view_for_class(data: SchoolData, class_section: str) -> pd.DataFrame:
    grid = build_class_grid(data, class_section)
    return grid.replace("", "—")


def timetable_view_for_teacher(data: SchoolData, teacher: str) -> pd.DataFrame:
    grid = build_teacher_grid(data, teacher)
    return grid.replace("", "—")


def weekly_subject_summary_for_class(data: SchoolData, class_section: str) -> pd.DataFrame:
    counts = Counter(
        entry["subject"]
        for entry in data.entries
        if entry["class_section"] == class_section
    )
    if not counts:
        return pd.DataFrame(columns=["Subject", "Count"])
    rows = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return pd.DataFrame(rows, columns=["Subject", "Count"])


def weekly_subject_class_summary_for_teacher(data: SchoolData, teacher: str) -> pd.DataFrame:
    counts = Counter(
        f"{entry['class_section']} | {entry['subject']}"
        for entry in data.entries
        if entry["teacher"] == teacher
    )
    if not counts:
        return pd.DataFrame(columns=["Subject-Class", "Count"])
    rows = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return pd.DataFrame(rows, columns=["Subject-Class", "Count"])
