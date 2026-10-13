"""Step 3 tests: resume parser on 3 sample resumes (PDF + DOCX) and edge cases."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.parser import (
    ResumeParseError,
    detect_heading,
    extract_text,
    find_date_range,
    parse_resume,
    parse_text,
)

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture(scope="module")
def fresher() -> dict:
    return parse_resume(SAMPLES / "fresher_data_analyst.pdf")


@pytest.fixture(scope="module")
def experienced() -> dict:
    return parse_resume(SAMPLES / "experienced_backend.docx")


@pytest.fixture(scope="module")
def nontech() -> dict:
    return parse_resume(SAMPLES / "nontech_hr.pdf")


# ---- sample 1: fresher, PDF ------------------------------------------------ #
def test_fresher_contact(fresher: dict) -> None:
    assert fresher["name"] == "Ananya Krishnan"
    assert fresher["email"] == "ananya.krishnan@gmail.com"
    assert "98450" in fresher["phone"]
    assert fresher["links"]["linkedin"]


def test_fresher_skills(fresher: dict) -> None:
    for s in ["Python", "SQL", "Power BI", "Pandas", "Microsoft Excel", "DAX", "R", "PostgreSQL"]:
        assert s in fresher["skills"], s


def test_fresher_sections_and_entries(fresher: dict) -> None:
    for sec in ["education", "experience", "projects", "skills", "certifications"]:
        assert sec in fresher["sections_found"]
    assert fresher["education"][0]["institution"].startswith("PES University")
    assert fresher["education"][0]["year"] == 2026
    assert len(fresher["projects"]) == 2
    intern = fresher["experience"][0]
    assert intern["is_internship"] and intern["duration_months"] == 2
    assert fresher["years_of_experience"] < 1


def test_skills_found_outside_skills_section(fresher: dict) -> None:
    # PostgreSQL only appears inside an internship bullet
    detail = {d["name"]: d for d in fresher["skill_details"]}
    assert "experience" in detail["PostgreSQL"]["sections"]


# ---- sample 2: experienced, DOCX --------------------------------------------- #
def test_experienced(experienced: dict) -> None:
    assert experienced["name"] == "Rahul Menon"
    assert len(experienced["experience"]) == 3
    assert experienced["experience"][0]["company"] == "Cobalt Systems"
    assert experienced["years_of_experience"] >= 5
    for s in ["Java", "Spring Boot", "Apache Kafka", "Kubernetes", "Amazon Web Services", "REST API", "Docker"]:
        assert s in experienced["skills"], s


# ---- sample 3: non-tech, PDF -------------------------------------------------- #
def test_nontech(nontech: dict) -> None:
    assert nontech["name"] == "Sneha Kapoor"
    for s in ["Recruitment", "Employee Onboarding", "HRIS", "Payroll", "Microsoft Excel", "Communication"]:
        assert s in nontech["skills"], s
    assert "Python" not in nontech["skills"]
    assert len(nontech["education"]) == 2


# ---- unit helpers ------------------------------------------------------------- #
@pytest.mark.parametrize("line, section", [
    ("EDUCATION", "education"), ("Work Experience:", "experience"), ("## Projects", "projects"),
    ("Skills & Tools", "skills"), ("Licenses & Certifications", "certifications"),
    ("CAREER OBJECTIVE", "summary"),
])
def test_heading_detection(line: str, section: str) -> None:
    h = detect_heading(line)
    assert h is not None and h[0] == section


def test_inline_heading() -> None:
    assert detect_heading("Technical Skills: Python, SQL") == ("skills", "Python, SQL")
    assert detect_heading("Built a dashboard using Python and SQL") is None


@pytest.mark.parametrize("text, months", [
    ("Jan 2024 - Jun 2024", 5), ("06/2021 – 08/2021", 2), ("2022-01 – 2023-01", 12), ("Jun' 23 - Dec' 23", 6),
])
def test_date_ranges(text: str, months: int) -> None:
    rng = find_date_range(text)
    assert rng is not None
    s, e, _ = rng
    assert (e.year - s.year) * 12 + e.month - s.month == months


def test_strict_terms_not_false_positive() -> None:
    p = parse_text("Priya R\npriya@x.com\n\nSUMMARY\nI excel at teamwork and go the extra mile.\n\n"
                   "SKILLS\nPython, SQL\n")
    assert "R" not in p["skills"] and "Go" not in p["skills"] and "Microsoft Excel" not in p["skills"]
    assert {"Python", "SQL", "Teamwork"} <= set(p["skills"])


def test_unsupported_and_empty(tmp_path: Path) -> None:
    bad = tmp_path / "resume.png"
    bad.write_bytes(b"123")
    with pytest.raises(ResumeParseError):
        extract_text(bad)
    empty = tmp_path / "empty.txt"
    empty.write_text("hi")
    with pytest.raises(ResumeParseError):
        extract_text(empty)
