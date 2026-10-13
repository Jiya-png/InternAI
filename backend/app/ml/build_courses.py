"""
Generate ``app/data/courses.json`` from ``app/data/skills.json``.

For every skill we emit 3 learning resources chosen by the skill's category
(e.g. web -> YouTube + freeCodeCamp + Coursera; cloud -> YouTube + Microsoft
Learn + Coursera). All links are *platform search URLs* for that skill, so
they never become dead links the way hard-coded course URLs do.

Difficulty and approximate duration are derived from a per-skill level
(beginner / intermediate / advanced) defined below.

Run from the ``backend`` folder:
    python -m app.ml.build_courses
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from app.services.catalog import DATA_DIR, load_skills

# --------------------------------------------------------------------------- #
# Platforms: name -> (search URL template, resource type, cost)
# --------------------------------------------------------------------------- #
PLATFORMS: dict[str, tuple[str, str, str]] = {
    "YouTube": ("https://www.youtube.com/results?search_query={q}", "video", "Free"),
    "Coursera": ("https://www.coursera.org/search?query={q}", "course", "Free to audit / paid certificate"),
    "edX": ("https://www.edx.org/search?q={q}", "course", "Free to audit / paid certificate"),
    "Udemy": ("https://www.udemy.com/courses/search/?q={q}", "course", "Paid (frequent discounts)"),
    "freeCodeCamp": ("https://www.freecodecamp.org/news/search/?query={q}", "tutorial", "Free"),
    "NPTEL": ("https://www.google.com/search?q=site%3Anptel.ac.in+{q}", "course", "Free (exam certificate paid)"),
    "Kaggle": ("https://www.kaggle.com/search?q={q}", "practice", "Free"),
    "Microsoft Learn": ("https://learn.microsoft.com/en-us/search/?terms={q}", "tutorial", "Free"),
    "LinkedIn Learning": ("https://www.linkedin.com/learning/search?keywords={q}", "course", "Paid (free trial)"),
}

# Category -> the three platforms to use, in display order.
CATEGORY_PLATFORMS: dict[str, tuple[str, str, str]] = {
    "languages": ("YouTube", "Coursera", "freeCodeCamp"),
    "web": ("YouTube", "freeCodeCamp", "Coursera"),
    "mobile": ("YouTube", "Coursera", "freeCodeCamp"),
    "data": ("YouTube", "Coursera", "Kaggle"),
    "ml": ("YouTube", "Coursera", "Kaggle"),
    "cloud": ("YouTube", "Microsoft Learn", "Coursera"),
    "security": ("YouTube", "Coursera", "edX"),
    "iot": ("YouTube", "NPTEL", "Coursera"),
    "testing": ("YouTube", "Udemy", "freeCodeCamp"),
    "tools": ("YouTube", "freeCodeCamp", "Coursera"),
    "cs_fundamentals": ("YouTube", "NPTEL", "Coursera"),
    "design": ("YouTube", "Coursera", "Udemy"),
    "marketing": ("YouTube", "Coursera", "Udemy"),
    "business": ("Coursera", "YouTube", "LinkedIn Learning"),
    "emerging": ("YouTube", "Coursera", "Udemy"),
    "soft_skills": ("Coursera", "LinkedIn Learning", "YouTube"),
}

# Per-skill level. Anything not listed is "beginner".
ADVANCED: set[str] = {
    "Kubernetes", "MLOps", "Deep Learning", "Reinforcement Learning", "System Design",
    "Distributed Systems", "Compiler Design", "CUDA", "Malware Analysis", "Digital Forensics",
    "Shader Programming", "Retrieval-Augmented Generation", "Large Language Models",
    "Site Reliability Engineering", "Rust", "Haskell", "Microservices", "Financial Modeling",
    "Valuation", "Penetration Testing", "RTOS", "ARM Cortex", "Signal Processing",
    "Kotlin Multiplatform", "Apache Kafka", "Threat Intelligence", "Query Optimization",
    "Transfer Learning", "Object Detection", "Hugging Face Transformers",
}
INTERMEDIATE: set[str] = {
    "TypeScript", "C++", "C#", "Go", "Scala", "React", "Angular", "Next.js", "Redux", "Node.js",
    "Django", "Spring Boot", "Spring Framework", "Hibernate", "GraphQL", "gRPC", "Docker",
    "Terraform", "Ansible", "CI/CD", "Amazon Web Services", "Microsoft Azure",
    "Google Cloud Platform", "Machine Learning", "Natural Language Processing", "Computer Vision",
    "PyTorch", "TensorFlow", "Apache Spark", "Apache Airflow", "Data Warehousing", "Data Modeling",
    "ETL", "Statistics", "Hypothesis Testing", "A/B Testing", "Time Series Analysis",
    "Feature Engineering", "Model Deployment", "Convolutional Neural Networks",
    "Recurrent Neural Networks", "Neural Networks", "Data Structures and Algorithms",
    "Operating Systems", "Computer Networks", "Design Patterns", "Network Security",
    "SIEM", "Incident Response", "Cryptography", "Automation Testing", "Selenium",
    "Performance Testing", "Embedded C", "Embedded Systems", "Microcontrollers",
    "Communication Protocols", "PCB Design", "Flutter", "Android Development",
    "iOS Development", "React Native", "Smart Contracts", "Solidity", "Unreal Engine",
    "Game Physics", "Design Systems", "User Research", "Search Engine Optimization",
    "Marketing Analytics", "Financial Analysis", "Product Management", "Routing and Switching",
    "DAX", "Linear Algebra", "Probability", "Elasticsearch", "LangChain", "Vector Databases",
    "Identity and Access Management", "Infrastructure as Code",
}

# Base hours per resource type, multiplied by a level factor.
BASE_HOURS: dict[str, float] = {"video": 4, "tutorial": 3, "course": 15, "practice": 6}
LEVEL_FACTOR: dict[str, float] = {"beginner": 1.0, "intermediate": 1.6, "advanced": 2.4}

# Better search phrases for ambiguous skill names.
SEARCH_OVERRIDES: dict[str, str] = {
    "C": "C programming language",
    "R": "R programming",
    "Go": "Go programming golang",
    "Swift": "Swift programming iOS",
    "Assembly": "assembly language programming",
    "Unity": "Unity game engine",
    "Notion": "Notion productivity app",
    "Sketch": "Sketch app UI design",
    "Tally": "Tally Prime accounting",
    "Agile": "agile methodology",
    "Research": "research skills",
    "Communication": "communication skills",
    "Spring Framework": "Spring framework Java",
    "Express.js": "Express.js Node",
    "Sales": "sales skills",
    "Regression": "regression machine learning",
    "Classification": "classification machine learning",
    "Clustering": "clustering machine learning",
    "Blender": "Blender 3D",
    "SAP": "SAP ERP",
}


def _level(skill: str) -> str:
    if skill in ADVANCED:
        return "advanced"
    if skill in INTERMEDIATE:
        return "intermediate"
    return "beginner"


def _fmt_duration(hours: float) -> str:
    """Human friendly duration; long courses expressed in weeks at ~5 h/week."""
    hours = round(hours)
    if hours < 10:
        return f"~{hours} hours"
    weeks = max(2, round(hours / 5))
    return f"~{weeks} weeks (≈5 h/week)"


def _title(skill: str, platform: str, rtype: str) -> str:
    if rtype == "video":
        return f"{skill} – full course / crash course videos"
    if rtype == "practice":
        return f"{skill} – hands-on notebooks & exercises"
    if rtype == "tutorial":
        return f"{skill} – tutorials & guides"
    return f"{skill} – structured courses on {platform}"


def build_resources(skill: str, category: str) -> list[dict[str, object]]:
    """Return 3 resource dicts for one skill."""
    level = _level(skill)
    query = quote_plus(SEARCH_OVERRIDES.get(skill, skill))
    resources: list[dict[str, object]] = []
    for idx, platform in enumerate(CATEGORY_PLATFORMS[category]):
        template, rtype, cost = PLATFORMS[platform]
        q = query + ("+tutorial" if platform == "YouTube" else "")
        hours = BASE_HOURS[rtype] * LEVEL_FACTOR[level]
        # Hands-on practice is at least "intermediate"; first resource eases in.
        if rtype == "practice" and level == "beginner":
            difficulty = "intermediate"
        else:
            difficulty = level
        resources.append(
            {
                "title": _title(skill, platform, rtype),
                "platform": platform,
                "type": rtype,
                "url": template.format(q=q),
                "duration": _fmt_duration(hours),
                "duration_hours": round(hours, 1),
                "difficulty": difficulty.capitalize(),
                "cost": cost,
                "priority": idx + 1,  # 1 = start here
            }
        )
    return resources


def build_all() -> dict[str, object]:
    skills = load_skills()
    courses = {name: build_resources(name, s.category) for name, s in skills.items()}
    return {
        "version": "1.0",
        "generated_on": date.today().isoformat(),
        "notes": "Auto-generated by app/ml/build_courses.py. URLs are platform search links for the skill, not specific course pages.",
        "courses": courses,
    }


def main() -> None:
    out_path: Path = DATA_DIR / "courses.json"
    data = build_all()
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    n_skills = len(data["courses"])  # type: ignore[arg-type]
    n_res = sum(len(v) for v in data["courses"].values())  # type: ignore[union-attr]
    print(f"Wrote {out_path} -> {n_skills} skills, {n_res} resources")


if __name__ == "__main__":
    main()
