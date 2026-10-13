"""
Feature engineering shared by training (ml/train.py) and inference
(services/recommender.py). Keeping it in one place guarantees the model sees
the same features in both situations.
"""
from __future__ import annotations

from collections.abc import Iterable

from app.services.catalog import Role

# Order matters: the match-score model is trained on columns in this order.
MATCH_FEATURES: list[str] = [
    "weighted_overlap",     # sum(weights of matched required) / sum(all required weights)
    "pct_required",         # matched required count / required count
    "nice_ratio",           # matched nice-to-have / nice-to-have count
    "semantic_similarity",  # cosine(resume profile embedding, role description embedding)
    "classifier_prob",      # P(role | resume) from the role classifier
    "experience_fit",       # 0..1 how well years of experience fit the role level
]


def weighted_overlap(skills: set[str], role: Role) -> float:
    total = role.total_weight
    if total == 0:
        return 0.0
    return sum(rs.weight for rs in role.required_skills if rs.skill in skills) / total


def pct_required(skills: set[str], role: Role) -> float:
    req = role.required_names
    return sum(1 for s in req if s in skills) / len(req) if req else 0.0


def nice_ratio(skills: set[str], role: Role) -> float:
    nice = role.nice_to_have
    return sum(1 for s in nice if s in skills) / len(nice) if nice else 0.0


def experience_fit(years: float, role: Role) -> float:
    """
    1.0 when the candidate meets the role's typical minimum experience.
    Each missing year costs 0.35 (floor 0.2). Very experienced people get a
    small penalty for intern roles (they are usually over-qualified).
    """
    years = max(0.0, float(years or 0.0))
    if role.experience_level == "intern" and years > 3:
        return 0.8
    if years >= role.min_years:
        return 1.0
    return max(0.2, 1.0 - (role.min_years - years) * 0.35)


def rule_features(skills: Iterable[str], years: float, role: Role) -> dict[str, float]:
    """The four features that only depend on skills + experience."""
    sk = set(skills)
    return {
        "weighted_overlap": weighted_overlap(sk, role),
        "pct_required": pct_required(sk, role),
        "nice_ratio": nice_ratio(sk, role),
        "experience_fit": experience_fit(years, role),
    }


def heuristic_match(feats: dict[str, float]) -> float:
    """
    Transparent fallback formula (used if trained models are missing, and as
    the explanation shown in the UI tooltip). Returns 0..100.
    """
    score = (
        0.55 * feats["weighted_overlap"]
        + 0.15 * feats["pct_required"]
        + 0.08 * feats["nice_ratio"]
        + 0.10 * feats.get("semantic_similarity", 0.0)
        + 0.04 * feats.get("classifier_prob", 0.0)
        + 0.08 * feats["experience_fit"]
    )
    return max(0.0, min(100.0, score * 100))


def synthetic_target(skills: set[str], years: float, role: Role, is_true_role: bool) -> float:
    """
    Ground-truth match score used to create the synthetic training pairs
    (before noise). Depends only on the TRUE skill set, so the regressor must
    learn to recover it from noisy parsed features.
    """
    f = rule_features(skills, years, role)
    base = 100 * (0.62 * f["weighted_overlap"] + 0.18 * f["pct_required"]
                  + 0.10 * f["nice_ratio"] + 0.10 * f["experience_fit"])
    return base + (4.0 if is_true_role else 0.0)


def profile_text(skills: Iterable[str], titles: Iterable[str] = (), projects: Iterable[str] = (),
                 summary: str = "") -> str:
    """
    Short text summarising a resume, used for sentence embeddings. Embedding
    models work best on short focused text, not on a whole noisy resume.
    """
    parts: list[str] = []
    if summary:
        parts.append(summary.strip()[:300])
    titles = [t for t in titles if t]
    if titles:
        parts.append("Experience as " + ", ".join(titles[:4]) + ".")
    projects = [p for p in projects if p]
    if projects:
        parts.append("Projects: " + "; ".join(projects[:4]) + ".")
    sk = list(skills)
    if sk:
        parts.append("Skills: " + ", ".join(sk[:40]) + ".")
    return " ".join(parts) or "No information"
