"""
Step 5 - Recommendation engine.

* Ranks all roles by predicted match % and returns the top 5.
* Explains each match: matched skills, missing required skills sorted by
  priority (= weight x (1 + market demand)), missing nice-to-haves, the
  feature breakdown, a radar of skill categories and course suggestions.
* What-if simulator: re-scores the resume with hypothetical extra skills and
  returns the gain per skill ("Learning Docker: +6%").
* Resume quality score and the 4-week roadmap (see quality.py / roadmap.py).

All scoring for many variants is batched (one classifier call + one
embedding call), so the full analysis takes well under a second on CPU.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np

from app.config import DISCLAIMER, TOP_K_ROLES
from app.services.catalog import Role, load_categories, load_courses, load_roles, load_skills, normalize_skill
from app.services.features import MATCH_FEATURES, profile_text, rule_features
from app.services.model_store import ModelBundle, get_models
from app.services.quality import quality_score
from app.services.roadmap import build_roadmap
from app.services.skill_extractor import get_extractor

MAX_GAIN_CANDIDATES = 14  # missing skills per role evaluated for what-if gains

HOW_CALCULATED = (
    "Your match % comes from a small machine-learning model that looks at 6 signals: "
    "(1) how many of the role's required skills you have, weighted by importance (1-5); "
    "(2) the share of required skills you have; (3) nice-to-have skills; "
    "(4) how similar your resume summary is to the job description (AI text embeddings); "
    "(5) how confident a role classifier is that your resume belongs to this role; and "
    "(6) whether your experience level fits. Required skills matter most."
)


@lru_cache(maxsize=1)
def skill_demand() -> dict[str, float]:
    """How many roles require each skill, scaled 0..1 (market demand proxy)."""
    c = Counter(rs.skill for r in load_roles().values() for rs in r.required_skills)
    top = max(c.values())
    return {s: n / top for s, n in c.items()}


@dataclass
class ResumeContext:
    """Everything the scorer needs from a parsed resume."""

    skills: list[str]
    years: float
    text: str
    titles: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_parsed(cls, parsed: dict[str, Any]) -> "ResumeContext":
        return cls(
            skills=list(parsed.get("skills", [])),
            years=float(parsed.get("years_of_experience") or 0.0),
            text=parsed.get("text", "") or " ".join(parsed.get("skills", [])),
            titles=[e["title"] for e in parsed.get("experience", []) if e.get("title")],
            projects=[p["title"] for p in parsed.get("projects", []) if p.get("title")],
            summary=parsed.get("summary", ""),
        )

    def variant(self, extra: list[str] | tuple[str, ...] = ()) -> tuple[list[str], str, str]:
        """(skills, classifier text, embedding profile) with hypothetical extra skills."""
        extra = [s for s in extra if s not in self.skills]
        skills = self.skills + extra
        text = self.text + ("\nSkills: " + ", ".join(extra) if extra else "")
        return skills, text, profile_text(skills, self.titles, self.projects, self.summary)


class Recommender:
    def __init__(self, models: ModelBundle | None = None) -> None:
        self.models = models or get_models()
        self.roles: dict[str, Role] = load_roles()
        self.role_ids = self.models.role_ids
        self.skills_meta = load_skills()

    # ------------------------------------------------------------------ #
    # Core batched scorer
    # ------------------------------------------------------------------ #
    def score_variants(self, ctx: ResumeContext, extras: list[list[str]],
                       role_ids: list[str] | None = None) -> tuple[np.ndarray, list[list[dict[str, float]]]]:
        """
        Score several skill variants against roles.
        Returns scores (n_variants, n_roles) and the feature dicts used.
        """
        role_ids = role_ids or self.role_ids
        variants = [ctx.variant(e) for e in extras]
        probs = self.models.role_probabilities_many([v[1] for v in variants], [v[0] for v in variants])
        sims = self.models.similarities([v[2] for v in variants])
        col = {r: i for i, r in enumerate(self.role_ids)}
        feats: list[list[dict[str, float]]] = []
        flat: list[dict[str, float]] = []
        for vi, (skills, _, _) in enumerate(variants):
            row = []
            for rid in role_ids:
                f = rule_features(skills, ctx.years, self.roles[rid])
                f["semantic_similarity"] = float(sims[vi, col[rid]])
                f["classifier_prob"] = float(probs[vi, col[rid]]) if self.models.classifier is not None else 0.0
                row.append(f)
                flat.append(f)
            feats.append(row)
        scores = self.models.predict_match(flat).reshape(len(variants), len(role_ids))
        return scores, feats

    # ------------------------------------------------------------------ #
    # Explanations
    # ------------------------------------------------------------------ #
    def _missing(self, role: Role, skills: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
        demand = skill_demand()
        req = []
        for rs in role.required_skills:
            if rs.skill not in skills:
                d = demand.get(rs.skill, 0.0)
                req.append({
                    "skill": rs.skill,
                    "weight": rs.weight,
                    "demand": round(d, 2),
                    "priority": round(rs.weight * (1 + d), 2),
                    "category": self.skills_meta[rs.skill].category_label,
                })
        req.sort(key=lambda x: (-x["priority"], x["skill"]))
        nice = [s for s in role.nice_to_have if s not in skills]
        return req, nice

    def _radar(self, role: Role, skills: set[str]) -> list[dict[str, Any]]:
        """Per skill category: role requirement (100) vs your coverage (% of weight)."""
        cats = load_categories()
        need: Counter = Counter()
        have: Counter = Counter()
        for rs in role.required_skills:
            c = self.skills_meta[rs.skill].category
            need[c] += rs.weight
            if rs.skill in skills:
                have[c] += rs.weight
        for s in role.nice_to_have:  # nice-to-haves count a little
            c = self.skills_meta[s].category
            need[c] += 1
            if s in skills:
                have[c] += 1
        ordered = sorted(need, key=lambda c: -need[c])[:8]
        return [{"category": cats[c], "role": 100, "you": round(100 * have[c] / need[c])} for c in ordered]

    def _courses(self, skills: list[str], limit: int = 8) -> list[dict[str, Any]]:
        courses = load_courses()
        return [{"skill": s, "category": self.skills_meta[s].category_label, "resources": courses.get(s, [])}
                for s in skills[:limit]]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze(self, parsed: dict[str, Any]) -> dict[str, Any]:
        ctx = ResumeContext.from_parsed(parsed)
        have = set(ctx.skills)
        scores, feats = self.score_variants(ctx, [[]])
        base = scores[0]
        order = np.argsort(-base)
        all_roles = [{
            "role_id": self.role_ids[i], "title": self.roles[self.role_ids[i]].title,
            "domain": self.roles[self.role_ids[i]].domain, "match": int(round(base[i])),
        } for i in order]
        top_ids = [self.role_ids[i] for i in order[:TOP_K_ROLES]]

        # what-if gains for every missing skill of the top roles (one batch)
        cand: list[str] = []
        per_role_missing: dict[str, tuple[list[dict[str, Any]], list[str]]] = {}
        for rid in top_ids:
            req, nice = self._missing(self.roles[rid], have)
            per_role_missing[rid] = (req, nice)
            for s in [m["skill"] for m in req] + nice:
                if s not in cand and len(cand) < MAX_GAIN_CANDIDATES * TOP_K_ROLES:
                    cand.append(s)
        gain_scores, _ = self.score_variants(ctx, [[s] for s in cand], top_ids) if cand else (np.zeros((0, 0)), [])
        gains = {(s, rid): max(0.0, float(gain_scores[ci, ri] - base[self.role_ids.index(rid)]))
                 for ci, s in enumerate(cand) for ri, rid in enumerate(top_ids)}

        top: list[dict[str, Any]] = []
        for rank, rid in enumerate(top_ids, start=1):
            role = self.roles[rid]
            i = self.role_ids.index(rid)
            req, nice = per_role_missing[rid]
            for m in req:
                m["gain"] = round(gains.get((m["skill"], rid), 0.0), 1)
            nice_items = sorted(({"skill": s, "gain": round(gains.get((s, rid), 0.0), 1),
                                  "category": self.skills_meta[s].category_label} for s in nice),
                                key=lambda x: -x["gain"])
            matched = sorted(({"skill": rs.skill, "weight": rs.weight} for rs in role.required_skills
                              if rs.skill in have), key=lambda x: -x["weight"])
            f = feats[0][i]
            top.append({
                "rank": rank,
                "role_id": rid,
                "title": role.title,
                "domain": role.domain,
                "experience_level": role.experience_level,
                "description": role.description,
                "match": int(round(base[i])),
                "matched_skills": matched,
                "matched_nice": [s for s in role.nice_to_have if s in have],
                "missing_required": req,
                "missing_nice": nice_items,
                "required_total": len(role.required_skills),
                "breakdown": {k: round(f[k], 3) for k in MATCH_FEATURES},
                "radar": self._radar(role, have),
                "courses": self._courses([m["skill"] for m in req] + [n["skill"] for n in nice_items[:2]]),
            })

        best = float(base[order[0]]) if len(order) else 0.0
        quality = quality_score(parsed, best, skill_finder=get_extractor().extract_from_text)
        return {
            "top_roles": top,
            "all_roles": all_roles,
            "quality": quality,
            "how_calculated": HOW_CALCULATED,
            "model_info": {
                "trained_models": self.models.trained,
                "embedding_backend": self.models.metadata.get("embedding_backend_in_use"),
                "classifier": self.models.metadata.get("classifier", {}).get("chosen"),
                "regressor": self.models.metadata.get("regressor", {}).get("chosen"),
            },
            "disclaimer": DISCLAIMER,
        }

    def what_if(self, parsed: dict[str, Any], role_id: str, extra_skills: list[str]) -> dict[str, Any]:
        role = self.roles[role_id]
        ctx = ResumeContext.from_parsed(parsed)
        extra: list[str] = []
        unknown: list[str] = []
        for s in extra_skills:
            canon = normalize_skill(s)
            if canon is None:
                unknown.append(s)
            elif canon not in ctx.skills and canon not in extra:
                extra.append(canon)
        variants = [[], extra] + [[s] for s in extra]
        scores, feats = self.score_variants(ctx, variants, [role_id])
        base = float(scores[0, 0])
        new = max(base, float(scores[1, 0]))  # adding skills never lowers your score
        per_skill = sorted(({"skill": s, "delta": round(max(0.0, float(scores[2 + k, 0]) - base), 1)}
                            for k, s in enumerate(extra)), key=lambda x: -x["delta"])
        missing_after = [rs.skill for rs in role.required_skills if rs.skill not in set(ctx.skills) | set(extra)]
        return {
            "role_id": role_id,
            "role_title": role.title,
            "base_match": round(base, 1),
            "new_match": round(new, 1),
            "delta": round(new - base, 1),
            "added_skills": extra,
            "unknown_skills": unknown,
            "per_skill": per_skill,
            "missing_required_after": missing_after,
            "breakdown": {k: round(feats[1][0][k], 3) for k in MATCH_FEATURES},
        }

    def roadmap(self, parsed: dict[str, Any], role_id: str) -> dict[str, Any]:
        role = self.roles[role_id]
        ctx = ResumeContext.from_parsed(parsed)
        req, nice = self._missing(role, set(ctx.skills))
        missing = req + [{"skill": s} for s in nice]
        focus = [m["skill"] for m in missing[:3]]
        scores, _ = self.score_variants(ctx, [[], focus], [role_id])
        return build_roadmap(role, missing, float(scores[0, 0]), max(float(scores[0, 0]), float(scores[1, 0])))


@lru_cache(maxsize=1)
def get_recommender() -> Recommender:
    return Recommender()
