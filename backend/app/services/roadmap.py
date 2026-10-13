"""
4-week personalised learning roadmap for a chosen target role.

Takes the top 3 missing skills (by priority = weight x demand) and spreads
them over four weeks:

    Week 1  skill #1 fundamentals + mini project
    Week 2  skill #2 fundamentals + mini project (keep practising #1)
    Week 3  skill #3 fundamentals + mini project
    Week 4  capstone project that combines all three + resume/portfolio update
"""
from __future__ import annotations

from typing import Any

from app.services.catalog import Role, load_courses, load_skills

# Mini-project templates per skill category ({s} = skill name)
PROJECT_TEMPLATES: dict[str, tuple[str, str]] = {
    "languages": ("CLI utility in {s}", "Write a command-line tool in {s} (e.g. expense splitter or file organiser) "
                  "with input validation, unit tests and a README."),
    "web": ("Mini web app with {s}", "Build a small to-do / notes app using {s}; deploy it free (Vercel/Render) and "
            "link it on your resume."),
    "mobile": ("Pocket app with {s}", "Build a 3-screen mobile app (list, detail, settings) with {s} that consumes a "
               "public API."),
    "data": ("Data story with {s}", "Pick a Kaggle/data.gov.in dataset, use {s} to clean and analyse it, and publish "
             "a one-page insight report or dashboard."),
    "ml": ("Notebook-to-model with {s}", "Train and evaluate a small model on a public dataset using {s}; report "
           "metrics and publish the notebook on GitHub."),
    "cloud": ("Deploy it with {s}", "Take any small app and deploy it using {s}; document the setup steps and costs "
              "(stay within the free tier)."),
    "security": ("Security lab: {s}", "Set up a home lab (VirtualBox/TryHackMe) and practise {s}; write a short "
                 "findings report with remediation steps."),
    "iot": ("Sensor prototype with {s}", "Build a prototype that reads a sensor and sends data using {s}; record a "
            "1-minute demo video."),
    "testing": ("Test suite with {s}", "Write an automated test suite with {s} for a demo website or API; run it "
                "in GitHub Actions."),
    "tools": ("Workflow practice: {s}", "Use {s} in a real mini project for a week (e.g. manage a team project) and "
              "write about the workflow you followed."),
    "cs_fundamentals": ("Problem set: {s}", "Solve 20 graded problems on {s} (LeetCode/GFG/NPTEL assignments) and "
                        "keep notes of patterns in a GitHub repo."),
    "design": ("Case study with {s}", "Redesign one screen of an app you use with {s}; publish a short case study "
               "(problem, research, wireframes, final UI)."),
    "marketing": ("Campaign plan with {s}", "Create a mini campaign for a local business applying {s}; present goals, "
                  "KPIs and expected results in a 5-slide deck."),
    "business": ("Business case with {s}", "Apply {s} to a real company case (annual report / public data) and present "
                 "a 1-page recommendation."),
    "emerging": ("Prototype with {s}", "Build a small working prototype that demonstrates {s} and publish it on GitHub "
                 "with a demo GIF."),
    "soft_skills": ("Practice: {s}", "Practise {s} deliberately: volunteer to present in a club/meetup and ask for "
                    "structured feedback."),
}

CAPSTONES: dict[str, str] = {
    "Data": "an end-to-end analytics project: raw data -> cleaning -> analysis -> dashboard with 3 key insights",
    "Business": "a mini business-analysis case: requirements document, process map and a KPI dashboard",
    "Software Engineering": "a deployed full feature (frontend or API + database + tests) with a clean README",
    "AI/ML": "an ML app: trained model + evaluation report + simple web demo (FastAPI/Streamlit)",
    "Cloud & DevOps": "a production-style deployment: containerised app, CI/CD pipeline and monitoring",
    "Security": "a security assessment report of a lab environment with findings and fixes",
    "Marketing": "a full growth audit for a real website: SEO, analytics setup and a 30-day campaign plan",
    "Product": "a product teardown + metric tree + A/B test proposal for a popular app",
    "IoT & Embedded": "a connected device prototype with sensor data shown on a live dashboard",
    "Design": "a complete UX case study for a mobile app: research, wireframes, prototype, usability test",
    "Emerging Tech": "a polished demo (dApp / game / XR scene) published with a video walkthrough",
    "Finance": "a financial model and valuation of a listed company with a one-page investment memo",
    "Human Resources": "an HR mini-project: hiring funnel analysis, onboarding checklist and engagement plan",
}

GOAL_TEMPLATES = [
    "Learn the core concepts of {s} (follow the first resource below)",
    "Practise {s} daily for 45-60 minutes with small exercises",
    "Finish the mini project and push it to GitHub / your portfolio",
]


def _resources(skill: str, k: int = 2) -> list[dict[str, Any]]:
    return load_courses().get(skill, [])[:k]


def _hours(skill: str) -> float:
    res = load_courses().get(skill, [])
    return round(sum(r.get("duration_hours", 4) for r in res[:2]), 1)


def build_roadmap(role: Role, missing: list[dict[str, Any]], current_match: float,
                  projected_match: float | None = None) -> dict[str, Any]:
    """
    role    : target role
    missing : missing skills sorted by priority, each {"skill": str, ...}
    """
    skills_meta = load_skills()
    focus = [m["skill"] for m in missing][:3]
    mode = "gap"
    if not focus:  # nothing missing -> deepen with nice-to-haves / top required
        mode = "advance"
        focus = list(role.nice_to_have[:3]) or [rs.skill for rs in role.required_skills[:3]]

    weeks: list[dict[str, Any]] = []
    for i, skill in enumerate(focus):
        cat = skills_meta[skill].category if skill in skills_meta else "tools"
        title_t, desc_t = PROJECT_TEMPLATES.get(cat, PROJECT_TEMPLATES["tools"])
        goals = [g.format(s=skill) for g in GOAL_TEMPLATES]
        if i > 0:
            goals.insert(2, f"Revise {focus[i - 1]} for 2-3 hours by extending last week's project")
        weeks.append({
            "week": i + 1,
            "title": f"Week {i + 1}: {'Master' if mode == 'advance' else 'Learn'} {skill}",
            "focus_skills": [skill],
            "goals": goals,
            "mini_project": {"title": title_t.format(s=skill), "description": desc_t.format(s=skill)},
            "resources": _resources(skill),
            "estimated_hours": _hours(skill),
        })
    capstone = CAPSTONES.get(role.domain, "a portfolio project that uses everything you learned")
    weeks.append({
        "week": len(weeks) + 1,
        "title": f"Week {len(weeks) + 1}: Capstone & job-ready polish",
        "focus_skills": focus,
        "goals": [
            f"Build {capstone} using {', '.join(focus)}",
            "Write a README with screenshots, setup steps and results (numbers!)",
            "Add the project and new skills to your resume using 'Action verb + task + tool + result' bullets",
            f"Apply to 5-10 {role.title} openings and ask 2 people for referrals",
        ],
        "mini_project": {"title": f"{role.title} capstone",
                         "description": f"Build {capstone}. Combine {', '.join(focus)} in one project you can demo "
                                        "in an interview."},
        "resources": [],
        "estimated_hours": 12.0,
    })
    # Always exactly 4 weeks: if fewer than 3 focus skills, add practice weeks.
    while len(weeks) < 4:
        weeks.insert(len(weeks) - 1, {
            "week": 0, "title": "Practice & interview prep", "focus_skills": focus,
            "goals": [f"Solve 15 interview questions on {', '.join(focus)}",
                      "Do 2 mock interviews (peers / Pramp)", "Polish GitHub profile and LinkedIn headline"],
            "mini_project": {"title": "Interview prep notebook",
                             "description": "Keep a public notes repo of questions and answers you practised."},
            "resources": [], "estimated_hours": 8.0,
        })
    for i, w in enumerate(weeks):
        w["week"] = i + 1
        w["title"] = f"Week {i + 1}: " + w["title"].split(": ", 1)[-1]

    return {
        "role_id": role.id,
        "role_title": role.title,
        "mode": mode,
        "focus_skills": focus,
        "current_match": round(current_match),
        "projected_match": round(projected_match) if projected_match is not None else None,
        "total_hours": round(sum(w["estimated_hours"] for w in weeks), 1),
        "weeks": weeks[:4],
    }
