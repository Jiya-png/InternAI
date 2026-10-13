"""Step 5 tests: recommender, what-if, quality score, roadmap."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.parser import parse_resume, parse_text
from app.services.quality import quality_score, rewrite_bullet
from app.services.recommender import get_recommender

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture(scope="module")
def rec():
    return get_recommender()


@pytest.fixture(scope="module")
def fresher() -> dict:
    return parse_resume(SAMPLES / "fresher_data_analyst.pdf")


@pytest.fixture(scope="module")
def analysis(rec, fresher) -> dict:
    return rec.analyze(fresher)


def test_top5_structure(analysis: dict) -> None:
    top = analysis["top_roles"]
    assert len(top) == 5
    matches = [r["match"] for r in top]
    assert matches == sorted(matches, reverse=True)
    assert all(0 <= m <= 100 for m in matches)
    for r in top:
        assert {"matched_skills", "missing_required", "missing_nice", "radar", "courses", "breakdown"} <= set(r)
    assert len(analysis["all_roles"]) >= 25


def test_fresher_best_role_is_data(analysis: dict) -> None:
    assert analysis["top_roles"][0]["role_id"] in {"data_analyst", "data_scientist", "product_analyst"}


def test_missing_sorted_by_priority_and_courses(analysis: dict) -> None:
    for r in analysis["top_roles"]:
        pr = [m["priority"] for m in r["missing_required"]]
        assert pr == sorted(pr, reverse=True)
        for c in r["courses"]:
            assert 2 <= len(c["resources"]) <= 3


def test_whatif_increases_match(rec, fresher) -> None:
    out = rec.what_if(fresher, "data_scientist", ["Machine Learning", "sklearn", "not-a-skill"])
    assert out["new_match"] > out["base_match"]
    assert out["delta"] == pytest.approx(out["new_match"] - out["base_match"], abs=0.11)
    assert "scikit-learn" in out["added_skills"]          # alias normalised
    assert out["unknown_skills"] == ["not-a-skill"]
    assert all(d["delta"] >= 0 for d in out["per_skill"])


def test_whatif_existing_skill_has_no_effect(rec, fresher) -> None:
    out = rec.what_if(fresher, "data_analyst", ["Python"])
    assert out["delta"] == 0 and out["added_skills"] == []


def test_roadmap_has_four_weeks(rec, fresher) -> None:
    rm = rec.roadmap(fresher, "data_scientist")
    assert len(rm["weeks"]) == 4
    assert len(rm["focus_skills"]) == 3
    assert rm["projected_match"] >= rm["current_match"]
    assert all(w["mini_project"]["title"] for w in rm["weeks"])


def test_roadmap_when_nothing_missing(rec) -> None:
    from app.services.catalog import get_role

    role = get_role("frontend_developer")
    skills = ", ".join(rs.skill for rs in role.required_skills) + ", " + ", ".join(role.nice_to_have)
    p = parse_text(f"Jane Doe\njane@x.com\n\nSKILLS\n{skills}\n")
    rm = rec.roadmap(p, "frontend_developer")
    assert len(rm["weeks"]) == 4 and rm["mode"] == "advance"


def test_quality_score(analysis: dict) -> None:
    q = analysis["quality"]
    assert 0 <= q["score"] <= 100
    assert sum(b["score"] for b in q["breakdown"]) == q["score"]
    assert any(w["original"].startswith("Worked on") for w in q["weak_bullets"])


def test_quality_empty_resume_gets_tips() -> None:
    q = quality_score({"skills": [], "sections_found": [], "bullets": [], "word_count": 40}, 10.0)
    assert q["score"] < 30 and len(q["tips"]) >= 5


def test_bullet_rewrite_template() -> None:
    r = rewrite_bullet("Worked on the company website", ["React"], [])
    assert r["suggestion"].startswith("Developed")
    assert "React" in r["suggestion"] and "[" in r["suggestion"]
    assert len(r["issues"]) == 3
