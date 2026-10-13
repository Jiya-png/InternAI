"""Step 1 tests: static catalog integrity + alias normalisation."""
from __future__ import annotations

import pytest

from app.ml.validate_catalog import validate
from app.services.catalog import (
    get_role,
    load_courses,
    load_roles,
    load_skills,
    normalize_skill,
)


def test_catalog_has_no_errors() -> None:
    errors = validate()
    assert errors == [], "\n".join(errors)


def test_minimum_sizes() -> None:
    assert len(load_skills()) >= 300
    assert len(load_roles()) >= 25


@pytest.mark.parametrize(
    "surface, canonical",
    [
        ("js", "JavaScript"),
        ("ReactJS", "React"),
        ("golang", "Go"),
        ("Go", "Go"),
        ("sklearn", "scikit-learn"),
        ("k8s", "Kubernetes"),
        ("ML", "Machine Learning"),
        ("power bi", "Power BI"),
        ("Excel", "Microsoft Excel"),
        ("aws", "Amazon Web Services"),
        ("pyspark", "Apache Spark"),
        ("seo", "Search Engine Optimization"),
    ],
)
def test_alias_normalisation(surface: str, canonical: str) -> None:
    assert normalize_skill(surface) == canonical


@pytest.mark.parametrize("word", ["go", "excel", "agile", "express", "r", "c", "unity", "notion"])
def test_strict_terms_do_not_match_lowercase_words(word: str) -> None:
    # Common English words must not be mistaken for skills.
    assert normalize_skill(word) is None


def test_role_lookup_by_id_and_title() -> None:
    assert get_role("data_analyst") is not None
    role = get_role("Data Analyst")
    assert role is not None and role.id == "data_analyst"
    assert role.weight_of("SQL") == 5


def test_required_roles_exist() -> None:
    titles = {r.title for r in load_roles().values()}
    for must in [
        "Data Analyst", "Business Analyst", "Backend Developer", "Frontend Developer",
        "Full Stack Developer", "Machine Learning Engineer", "Data Scientist", "DevOps Engineer",
        "SEO / Digital Marketing Analyst", "Product Analyst", "QA / Test Engineer",
        "Cybersecurity Analyst", "IoT Engineer",
    ]:
        assert must in titles, must


def test_every_role_skill_has_courses() -> None:
    courses = load_courses()
    for role in load_roles().values():
        for name in role.required_names + list(role.nice_to_have):
            assert 2 <= len(courses[name]) <= 3
            assert all(c["url"].startswith("https://") for c in courses[name])
