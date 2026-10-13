"""
Sanity checks for the static catalog (skills.json, jobs.json, courses.json).

Run from the ``backend`` folder:
    python -m app.ml.validate_catalog

Exits with code 1 and prints every problem if anything is wrong.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

from app.services.catalog import (
    load_categories,
    load_courses,
    load_implications,
    load_roles,
    load_skills,
)

MIN_SKILLS = 300
MIN_ROLES = 25
VALID_LEVELS = {"intern", "entry", "mid"}


def validate() -> list[str]:
    """Return a list of human-readable error strings (empty = all good)."""
    errors: list[str] = []
    skills = load_skills()
    roles = load_roles()
    courses = load_courses()

    # ---- skills ---------------------------------------------------------- #
    if len(skills) < MIN_SKILLS:
        errors.append(f"Only {len(skills)} skills (need >= {MIN_SKILLS})")

    # A loose (case-insensitive) term must map to exactly one skill.
    owner: dict[str, set[str]] = defaultdict(set)
    strict_owner: dict[str, set[str]] = defaultdict(set)
    for s in skills.values():
        for st in s.strict:
            if st not in s.terms:
                errors.append(f"Skill '{s.name}': strict term '{st}' is not in name/aliases")
            loose_terms = {t.lower() for t in s.terms if t not in s.strict}
            if st.lower() in loose_terms:
                errors.append(f"Skill '{s.name}': strict term '{st}' is defeated by a loose alias '{st.lower()}'")
        for term in s.terms:
            if not term.strip():
                errors.append(f"Skill '{s.name}' has an empty alias")
            if term in s.strict:
                strict_owner[term].add(s.name)
            else:
                owner[term.lower()].add(s.name)
    for term, names in owner.items():
        if len(names) > 1:
            errors.append(f"Alias collision: '{term}' -> {sorted(names)}")
    for term, names in strict_owner.items():
        if len(names) > 1:
            errors.append(f"Strict alias collision: '{term}' -> {sorted(names)}")

    for src, targets in load_implications().items():
        for name in [src, *targets]:
            if name not in skills:
                errors.append(f"Implication uses unknown skill '{name}'")

    # ---- roles ----------------------------------------------------------- #
    if len(roles) < MIN_ROLES:
        errors.append(f"Only {len(roles)} roles (need >= {MIN_ROLES})")
    titles = Counter(r.title for r in roles.values())
    for t, n in titles.items():
        if n > 1:
            errors.append(f"Duplicate role title '{t}'")
    for r in roles.values():
        if r.experience_level not in VALID_LEVELS:
            errors.append(f"Role '{r.id}': bad experience_level '{r.experience_level}'")
        if len(r.required_skills) < 6:
            errors.append(f"Role '{r.id}': fewer than 6 required skills")
        if len(r.description.split()) < 20:
            errors.append(f"Role '{r.id}': description too short for embeddings")
        req = r.required_names
        if len(set(req)) != len(req):
            errors.append(f"Role '{r.id}': duplicate required skill")
        for rs in r.required_skills:
            if rs.skill not in skills:
                errors.append(f"Role '{r.id}': unknown required skill '{rs.skill}'")
            if not 1 <= rs.weight <= 5:
                errors.append(f"Role '{r.id}': weight {rs.weight} for '{rs.skill}' not in 1..5")
        for nh in r.nice_to_have:
            if nh not in skills:
                errors.append(f"Role '{r.id}': unknown nice-to-have skill '{nh}'")
            if nh in req:
                errors.append(f"Role '{r.id}': '{nh}' is both required and nice-to-have")

    # ---- courses --------------------------------------------------------- #
    if not courses:
        errors.append("courses.json missing - run: python -m app.ml.build_courses")
    else:
        for name in skills:
            res = courses.get(name)
            if not res:
                errors.append(f"No courses for skill '{name}'")
                continue
            if not 2 <= len(res) <= 3:
                errors.append(f"Skill '{name}': {len(res)} resources (need 2-3)")
            for c in res:
                url = urlparse(str(c.get("url", "")))
                if url.scheme != "https" or not url.netloc:
                    errors.append(f"Skill '{name}': bad URL {c.get('url')}")
                for key in ("title", "platform", "type", "duration", "difficulty"):
                    if not c.get(key):
                        errors.append(f"Skill '{name}': resource missing '{key}'")
        for name in courses:
            if name not in skills:
                errors.append(f"courses.json has unknown skill '{name}'")
    return errors


def summary() -> None:
    """Print a short overview of the catalog."""
    skills = load_skills()
    roles = load_roles()
    courses = load_courses()
    cats = load_categories()
    per_cat = Counter(s.category for s in skills.values())
    n_alias = sum(len(s.aliases) for s in skills.values())
    print(f"Skills : {len(skills)} canonical, {n_alias} aliases, {len(cats)} categories")
    for key, label in cats.items():
        print(f"   - {label:<26} {per_cat[key]:>3}")
    levels = Counter(r.experience_level for r in roles.values())
    print(f"Roles  : {len(roles)}  (levels: {dict(levels)})")
    used = {rs.skill for r in roles.values() for rs in r.required_skills}
    used |= {n for r in roles.values() for n in r.nice_to_have}
    print(f"         {len(used)} distinct skills referenced by roles")
    print(f"Courses: {sum(len(v) for v in courses.values())} resources for {len(courses)} skills")


def main() -> None:
    summary()
    errors = validate()
    if errors:
        print(f"\n{len(errors)} problem(s) found:")
        for e in errors:
            print("  x", e)
        sys.exit(1)
    print("\nCatalog OK ✔")


if __name__ == "__main__":
    main()
