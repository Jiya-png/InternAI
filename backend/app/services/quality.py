"""
Resume quality score (0-100) with concrete tips and bullet rewrites.

Components (max points):
    Section completeness   25   contact, education, experience, projects, skills, certifications
    Quantified bullets     20   bullets with numbers / % / money / counts
    Action verbs           15   bullets that start with a strong action verb
    Length                 15   ~350-800 words is ideal for students / early career
    Skill relevance        25   number of recognised skills + best role match

Weak bullets are rewritten with the template:
    Action verb + task + tool + measurable result
"""
from __future__ import annotations

import re
from typing import Any

ACTION_VERBS = {
    "achieved", "analysed", "analyzed", "architected", "automated", "boosted", "built", "championed",
    "collaborated", "conducted", "configured", "coordinated", "created", "cut", "debugged", "decreased",
    "delivered", "deployed", "designed", "developed", "devised", "drove", "engineered", "enhanced",
    "established", "evaluated", "executed", "expanded", "facilitated", "fine-tuned", "generated", "grew",
    "guided", "headed", "identified", "implemented", "improved", "increased", "initiated", "integrated",
    "introduced", "launched", "led", "maintained", "managed", "mentored", "migrated", "modelled", "modeled",
    "monitored", "negotiated", "optimised", "optimized", "orchestrated", "organised", "organized",
    "oversaw", "pioneered", "planned", "presented", "produced", "programmed", "prototyped", "published",
    "raised", "redesigned", "reduced", "refactored", "resolved", "restructured", "revamped", "saved",
    "scaled", "screened", "secured", "simplified", "spearheaded", "streamlined", "strengthened",
    "supervised", "tested", "trained", "transformed", "visualised", "visualized", "wrote", "researched",
    "containerised", "containerized", "authored", "curated", "audited", "forecasted", "modernised",
    "modernized", "onboarded", "recruited", "sourced", "shipped", "won", "ranked", "conceptualised",
    "conceptualized", "benchmarked", "created", "deployed", "grew", "handled", "set",
}
WEAK_OPENERS = re.compile(
    r"^(worked on|working on|responsible for|helped( the team)?( with| in| to)?|was involved in|involved in|"
    r"did|assisted( in| with)?|participated in|handled|tasked with|part of|was part of|duties included|"
    r"took part in|learned|learnt|got)\b[\s:,-]*",
    re.I,
)
QUANT_RE = re.compile(r"(\d+(\.\d+)?\s*(%|x|k|m|\+|lakh|crore|hours?|hrs?|users?|ms|s\b)|[₹$€£]\s?\d|\b\d{2,}\b|\b\d+\b)", re.I)

VERB_HINTS = [
    (r"dashboard|report|visuali", "Built"),
    (r"analy|insight|eda|study|research", "Analyzed"),
    (r"model|classifier|predict|train|neural|bert|lstm", "Trained"),
    (r"api|backend|app|website|web|frontend|feature|service|system|portal", "Developed"),
    (r"test|qa|bug", "Automated"),
    (r"campaign|seo|content|blog|social|ads", "Launched"),
    (r"hiring|recruit|onboard|interview|engagement|event", "Coordinated"),
    (r"pipeline|deploy|docker|kubernetes|ci/cd|infra|cloud", "Automated"),
    (r"design|ui|ux|prototype|wireframe", "Designed"),
    (r"data|clean|annotat", "Performed"),
]
RESULT_HINTS = [
    (r"dashboard|report", "cutting reporting time by [X]%"),
    (r"model|classifier|predict|train", "achieving [X]% accuracy / F1"),
    (r"api|backend|service|query|performance", "reducing response time by [X]%"),
    (r"app|website|web|feature|portal", "used by [N]+ users"),
    (r"test|bug|qa", "raising test coverage to [X]% / catching [N] bugs"),
    (r"campaign|seo|content|ads|social", "growing traffic / conversions by [X]%"),
    (r"hiring|recruit|interview|onboard", "for [N] candidates / new joiners"),
    (r"event|engagement", "with [N]+ participants"),
    (r"data|clean|annotat", "across [N]K records, improving data quality by [X]%"),
]


def _starts_with_action_verb(bullet: str) -> bool:
    first = re.sub(r"[^a-zA-Z-]", "", bullet.split()[0]).lower() if bullet.split() else ""
    return first in ACTION_VERBS or (first.endswith("ed") and len(first) > 4 and not WEAK_OPENERS.match(bullet))


def _is_quantified(bullet: str) -> bool:
    return bool(QUANT_RE.search(bullet))


def _pick(hints: list[tuple[str, str]], text: str, default: str) -> str:
    for pattern, value in hints:
        if re.search(pattern, text, re.I):
            return value
    return default


def rewrite_bullet(bullet: str, user_skills: list[str], bullet_skills: list[str]) -> dict[str, Any]:
    """Return {original, issues, suggestion} using Action verb + task + tool + result."""
    issues: list[str] = []
    weak = WEAK_OPENERS.match(bullet)
    if weak or not _starts_with_action_verb(bullet):
        issues.append("Starts with a weak or passive phrase - lead with a strong action verb")
    if not _is_quantified(bullet):
        issues.append("No measurable result - add a number (%, time saved, users, accuracy)")
    if not bullet_skills:
        issues.append("No tool/technology mentioned")

    task = WEAK_OPENERS.sub("", bullet).strip().rstrip(".")
    if task and not weak and _starts_with_action_verb(task):
        verb, task = task.split()[0], " ".join(task.split()[1:])
    else:
        verb = _pick(VERB_HINTS, bullet, "Delivered")
    if task:
        task = task[0].lower() + task[1:]
    else:
        task = "[what you built or improved]"
    tool = ""
    if not bullet_skills:
        tool = f" using {user_skills[0]}" if user_skills else " using [tool/technology]"
    result = "" if _is_quantified(bullet) else ", " + _pick(RESULT_HINTS, bullet, "improving [metric] by [X]%")
    suggestion = f"{verb} {task}{tool}{result}."
    suggestion = re.sub(r"\s+", " ", suggestion).replace(" ,", ",")
    return {"original": bullet, "issues": issues, "suggestion": suggestion}


def quality_score(parsed: dict[str, Any], best_match: float, skill_finder=None) -> dict[str, Any]:
    """
    parsed     : output of services.parser.parse_text
    best_match : highest role match % (0-100) from the recommender
    skill_finder: callable(text) -> list[str] of skills in a bullet (optional)
    """
    tips: list[str] = []
    found = set(parsed.get("sections_found", []))
    bullets: list[str] = [b for b in parsed.get("bullets", []) if len(b.split()) >= 3]

    # ---- completeness (25) ------------------------------------------------- #
    checks = [
        ("email", 3, bool(parsed.get("email")), "Add a professional email address at the top."),
        ("phone", 2, bool(parsed.get("phone")), "Add a phone number so recruiters can reach you."),
        ("education", 5, bool(parsed.get("education")) or "education" in found,
         "Add an Education section with degree, college, graduation year and CGPA."),
        ("experience", 5, bool(parsed.get("experience")),
         "Add internships, freelance work or part-time roles under an Experience section."),
        ("projects", 4, bool(parsed.get("projects")),
         "Add 2-3 projects with what you built, tools used and the result."),
        ("skills", 4, "skills" in found, "Add a dedicated Skills section grouped by category."),
        ("certifications", 2, "certifications" in found,
         "Add relevant certifications or online courses (Coursera, NPTEL, Google, AWS...)."),
    ]
    completeness = 0
    section_status = []
    for key, pts, ok, tip in checks:
        section_status.append({"section": key, "present": ok, "points": pts})
        if ok:
            completeness += pts
        else:
            tips.append(tip)
    if not parsed.get("links", {}).get("linkedin"):
        tips.append("Add your LinkedIn profile URL (and GitHub/portfolio for technical roles).")

    # ---- bullets ------------------------------------------------------------ #
    n = len(bullets)
    quant_ratio = sum(_is_quantified(b) for b in bullets) / n if n else 0.0
    verb_ratio = sum(_starts_with_action_verb(b) for b in bullets) / n if n else 0.0
    quantified = round(20 * min(1.0, quant_ratio / 0.6))
    action = round(15 * min(1.0, verb_ratio / 0.8))
    if n == 0:
        tips.append("Describe your experience and projects with bullet points (3-5 per entry).")
    else:
        if quant_ratio < 0.6:
            tips.append(f"Only {round(quant_ratio * 100)}% of your bullets contain numbers. Aim for 60%+: "
                        "add impact like '% faster', 'users served', 'hours saved', 'accuracy'.")
        if verb_ratio < 0.8:
            tips.append("Start every bullet with a strong action verb (Built, Led, Automated, Analyzed...) "
                        "instead of 'Worked on' / 'Responsible for'.")

    # ---- length (15) --------------------------------------------------------- #
    wc = int(parsed.get("word_count", 0))
    if 350 <= wc <= 800:
        length = 15
    elif 250 <= wc < 350 or 800 < wc <= 1000:
        length = 10
    elif 150 <= wc < 250 or 1000 < wc <= 1300:
        length = 6
    else:
        length = 2
    if wc < 350:
        tips.append(f"Your resume is short ({wc} words). Add detail to projects and experience (target 350-800 words).")
    elif wc > 1000:
        tips.append(f"Your resume is long ({wc} words). Trim to 1 page (2 max) - keep the most relevant work.")

    # ---- skill relevance (25) ---------------------------------------------- #
    n_skills = len(parsed.get("skills", []))
    relevance = round(10 * min(1.0, n_skills / 12) + 15 * (best_match / 100))
    if n_skills < 8:
        tips.append("List more of your technical skills explicitly - we detected only "
                    f"{n_skills}. Mention tools inside project bullets too.")
    if best_match < 60:
        tips.append("Your best role match is below 60%. Check the skill gaps below and build one project "
                    "that uses the top missing skills.")

    total = int(min(100, completeness + quantified + action + length + relevance))
    label = "Excellent" if total >= 80 else "Good" if total >= 65 else "Fair" if total >= 50 else "Needs work"

    # ---- weak bullets ------------------------------------------------------- #
    weak: list[dict[str, Any]] = []
    user_skills = [s for s in parsed.get("skills", [])][:5]
    for b in bullets:
        if len(weak) >= 6:
            break
        if WEAK_OPENERS.match(b) or not _is_quantified(b) or not _starts_with_action_verb(b):
            b_sk = skill_finder(b) if skill_finder else []
            weak.append(rewrite_bullet(b, user_skills, b_sk))

    return {
        "score": total,
        "label": label,
        "breakdown": [
            {"name": "Section completeness", "score": completeness, "max": 25},
            {"name": "Quantified bullets", "score": quantified, "max": 20},
            {"name": "Action verbs", "score": action, "max": 15},
            {"name": "Length", "score": length, "max": 15},
            {"name": "Skill relevance", "score": relevance, "max": 25},
        ],
        "sections": section_status,
        "stats": {
            "bullets": n,
            "quantified_pct": round(quant_ratio * 100),
            "action_verb_pct": round(verb_ratio * 100),
            "word_count": wc,
            "skills_detected": n_skills,
        },
        "tips": tips,
        "weak_bullets": weak,
    }
