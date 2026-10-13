"""
Catalog loader for InternAI.

Loads the three static data files in ``app/data`` once (cached) and exposes
typed, convenient accessors used by every other module:

* ``skills.json``  -> skill taxonomy (category, aliases, strict terms)
* ``jobs.json``    -> role catalog (weighted required skills, nice-to-haves)
* ``courses.json`` -> learning resources per skill

Nothing here touches ML libraries, so it is safe to import anywhere.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Skill:
    """One canonical skill from the taxonomy."""

    name: str
    category: str                 # category key, e.g. "web"
    category_label: str           # human label, e.g. "Web Development"
    aliases: tuple[str, ...] = ()
    strict: tuple[str, ...] = ()  # terms that must match with exact case

    @property
    def terms(self) -> tuple[str, ...]:
        """Name + aliases (all surface forms that map to this skill)."""
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class RoleSkill:
    skill: str
    weight: int  # 1..5


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    domain: str
    description: str
    experience_level: str  # intern | entry | mid
    min_years: int
    required_skills: tuple[RoleSkill, ...]
    nice_to_have: tuple[str, ...]
    typical_titles: tuple[str, ...] = field(default_factory=tuple)

    @property
    def required_names(self) -> list[str]:
        return [rs.skill for rs in self.required_skills]

    @property
    def total_weight(self) -> int:
        return sum(rs.weight for rs in self.required_skills)

    def weight_of(self, skill: str) -> int:
        for rs in self.required_skills:
            if rs.skill == skill:
                return rs.weight
        return 0


# --------------------------------------------------------------------------- #
# Raw loaders (cached)
# --------------------------------------------------------------------------- #
def _read_json(filename: str) -> Any:
    path = DATA_DIR / filename
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_skills() -> dict[str, Skill]:
    """Return ``{canonical_name: Skill}`` preserving file order."""
    raw = _read_json("skills.json")
    skills: dict[str, Skill] = {}
    for cat_key, cat in raw["categories"].items():
        for s in cat["skills"]:
            skills[s["name"]] = Skill(
                name=s["name"],
                category=cat_key,
                category_label=cat["label"],
                aliases=tuple(s.get("aliases", [])),
                strict=tuple(s.get("strict", [])),
            )
    return skills


@lru_cache(maxsize=1)
def load_implications() -> dict[str, list[str]]:
    """``{skill: [skills it implies]}`` e.g. PostgreSQL -> [SQL]."""
    return dict(_read_json("skills.json").get("implies", {}))


def expand_implied(skills: list[str]) -> list[str]:
    """Return the skills that are implied by ``skills`` but not already in it (transitive)."""
    imp = load_implications()
    have = set(skills)
    added: list[str] = []
    frontier = list(skills)
    while frontier:
        s = frontier.pop()
        for t in imp.get(s, []):
            if t not in have:
                have.add(t)
                added.append(t)
                frontier.append(t)
    return added


@lru_cache(maxsize=1)
def load_categories() -> dict[str, str]:
    """Return ``{category_key: label}``."""
    raw = _read_json("skills.json")
    return {k: v["label"] for k, v in raw["categories"].items()}


@lru_cache(maxsize=1)
def load_roles() -> dict[str, Role]:
    """Return ``{role_id: Role}`` preserving file order."""
    raw = _read_json("jobs.json")
    roles: dict[str, Role] = {}
    for r in raw["roles"]:
        roles[r["id"]] = Role(
            id=r["id"],
            title=r["title"],
            domain=r["domain"],
            description=r["description"],
            experience_level=r["experience_level"],
            min_years=int(r.get("min_years", 0)),
            required_skills=tuple(RoleSkill(x["skill"], int(x["weight"])) for x in r["required_skills"]),
            nice_to_have=tuple(r.get("nice_to_have", [])),
            typical_titles=tuple(r.get("typical_titles", [])),
        )
    return roles


@lru_cache(maxsize=1)
def load_courses() -> dict[str, list[dict[str, Any]]]:
    """Return ``{skill_name: [resource, ...]}``. Empty dict if not generated yet."""
    path = DATA_DIR / "courses.json"
    if not path.exists():
        return {}
    return _read_json("courses.json")["courses"]


# --------------------------------------------------------------------------- #
# Alias index / normalisation
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def alias_index() -> tuple[dict[str, str], dict[str, str]]:
    """
    Build two lookup tables:

    * ``loose``  : lower-cased term -> canonical name (case-insensitive terms)
    * ``strict`` : exact-case term  -> canonical name (case-sensitive terms)
    """
    loose: dict[str, str] = {}
    strict: dict[str, str] = {}
    for skill in load_skills().values():
        for term in skill.terms:
            if term in skill.strict:
                strict[term] = skill.name
            else:
                loose.setdefault(term.lower(), skill.name)
    return loose, strict


def normalize_skill(text: str) -> str | None:
    """
    Map any surface form (``"js"``, ``"ReactJS"``, ``"Golang"``) to its canonical
    skill name, or ``None`` if unknown. Strict terms need exact case.
    """
    text = text.strip()
    if not text:
        return None
    loose, strict = alias_index()
    if text in strict:
        return strict[text]
    if text in load_skills():          # canonical name typed exactly
        return text
    return loose.get(text.lower())


def skill_category(name: str) -> str | None:
    skill = load_skills().get(name)
    return skill.category if skill else None


def get_role(role_id_or_title: str) -> Role | None:
    """Look a role up by id (``data_analyst``) or title (``Data Analyst``)."""
    roles = load_roles()
    if role_id_or_title in roles:
        return roles[role_id_or_title]
    key = role_id_or_title.strip().lower()
    for role in roles.values():
        if role.title.lower() == key:
            return role
    return None
