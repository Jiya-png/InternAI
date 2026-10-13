"""
Step 2 - Synthetic resume generator.

Creates 5,000+ realistic-looking resumes (plain text), each with a known true
role, plus (resume, role, match_score) pairs used to train the match regressor.

Design
------
* For each role: required skills are sampled with high probability
  (0.80-0.95, higher for heavier weights), nice-to-have skills with 30%,
  plus 1-3 random "noise" skills and 1-3 soft skills.
* Random name, college, degree, CGPA, 0-3 internships, 1-4 projects with
  templated bullets (varied action verbs, numbers, tools), certifications.
* 6 formatting styles (heading names, bullet glyphs, date formats, skills
  layout, with/without a skills section). Styles 4 and 5 are held out for
  validation in train.py to test generalisation to unseen layouts.
* ~10% hard cases: 5% hybrid profiles (two roles mixed) and 5% weak resumes.
* Skills are written with aliases 30% of the time ("JS", "sklearn", "k8s").

Outputs (in app/data/):
    synthetic_resumes.csv  - one row per resume
    match_pairs.csv        - (resume_id, role_id, match_score) triples

Run from ``backend``:
    python -m app.ml.generate_data --n 5400
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.config import DATA_DIR, RANDOM_SEED
from app.services.catalog import Role, load_roles, load_skills
from app.services.features import synthetic_target

# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Ishaan", "Rohan", "Karan", "Rahul", "Aman",
    "Priya", "Ananya", "Diya", "Sneha", "Kavya", "Pooja", "Neha", "Riya", "Meera", "Isha",
    "Mohammed", "Ayesha", "Fatima", "Imran", "Zoya", "Harpreet", "Gurpreet", "Simran", "Manpreet",
    "Lakshmi", "Venkat", "Karthik", "Divya", "Swathi", "Nikhil", "Tanvi", "Yash", "Shreya",
    "Emily", "James", "Olivia", "Daniel", "Sophia", "Michael", "Chloe", "Lucas", "Maria", "David",
    "Wei", "Mei", "Kenji", "Yuki", "Carlos", "Lucia", "Ahmed", "Sara", "Tomás", "Grace",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Patel", "Reddy", "Nair", "Iyer", "Menon", "Singh", "Kaur",
    "Khan", "Ali", "Das", "Bose", "Chatterjee", "Mukherjee", "Joshi", "Kulkarni", "Deshmukh",
    "Rao", "Pillai", "Agarwal", "Mehta", "Shah", "Jain", "Mishra", "Pandey", "Yadav", "Choudhary",
    "Fernandes", "D'Souza", "Smith", "Johnson", "Brown", "Garcia", "Martinez", "Lee", "Wang",
    "Chen", "Kim", "Tanaka", "Silva", "Lopez", "Wilson", "Taylor", "Anderson", "Thomas",
]
CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "New Delhi", "Noida", "Gurugram",
          "Kolkata", "Ahmedabad", "Jaipur", "Kochi", "Indore", "Chandigarh", "Bhubaneswar", "Remote"]
COLLEGES = [
    "Indian Institute of Technology, Bombay", "National Institute of Technology, Trichy",
    "Vellore Institute of Technology", "Delhi Technological University", "BITS Pilani",
    "Manipal Institute of Technology", "SRM Institute of Science and Technology",
    "Anna University", "Jadavpur University", "University of Delhi", "Christ University",
    "Symbiosis International University", "Amity University", "Lovely Professional University",
    "PES University", "RV College of Engineering", "College of Engineering Pune",
    "Thapar Institute of Engineering and Technology", "Kalinga Institute of Industrial Technology",
    "Chandigarh University", "Nirma University", "Osmania University", "Mumbai University",
    "St. Xavier's College, Mumbai", "Loyola College, Chennai", "Narsee Monjee Institute of Management Studies",
    "Shri Ram College of Commerce", "National Institute of Design", "IIIT Hyderabad", "Jamia Millia Islamia",
]
COMPANIES = [
    "Nimbus Analytics", "BrightPath Technologies", "Orbitron Labs", "Quantix Solutions", "BluePeak Software",
    "Cobalt Systems", "Vertex Digital", "Saffron Tech", "Zenith Data Co.", "Helix Innovations",
    "Northwind Retail", "Lumen Fintech", "Arcadia Health", "TerraGrid Energy", "Pixelcraft Studios",
    "Kestrel Security", "Monsoon Media", "Evergreen Logistics", "Nova Edtech", "Crimson Consulting",
    "Silverline Networks", "UrbanNest Realty", "Aurora Motors", "Greenleaf Agritech", "Sparrow Mobility",
]

DEGREES_BY_DOMAIN: dict[str, list[str]] = {
    "tech": ["B.Tech in Computer Science and Engineering", "B.E. in Information Technology",
             "B.Tech in Electronics and Communication", "Bachelor of Computer Applications (BCA)",
             "Master of Computer Applications (MCA)", "B.Sc. in Computer Science", "M.Tech in Computer Science",
             "B.Tech in Artificial Intelligence and Data Science"],
    "electronics": ["B.Tech in Electronics and Communication", "B.E. in Electrical and Electronics Engineering",
                    "B.Tech in Instrumentation Engineering", "M.Tech in VLSI and Embedded Systems"],
    "business": ["Bachelor of Business Administration (BBA)", "MBA in Business Analytics", "B.Com (Honours)",
                 "MBA in Marketing", "B.Sc. in Economics", "PGDM"],
    "finance": ["B.Com (Honours)", "MBA in Finance", "BBA in Finance", "M.Com", "B.Sc. in Economics"],
    "design": ["Bachelor of Design (B.Des)", "B.Sc. in Multimedia and Animation", "B.Des in Interaction Design",
               "B.F.A. in Applied Arts"],
    "marketing": ["BBA in Marketing", "Bachelor of Mass Media (BMM)", "BA in English Literature",
                  "MBA in Marketing", "BA in Journalism and Mass Communication"],
    "hr": ["MBA in Human Resource Management", "BBA in Human Resources", "MA in Psychology",
           "BA in Psychology", "PGDM in HR"],
}
DOMAIN_TO_DEGREE = {
    "Data": "tech", "Software Engineering": "tech", "AI/ML": "tech", "Cloud & DevOps": "tech",
    "Security": "tech", "Emerging Tech": "tech", "IoT & Embedded": "electronics", "Business": "business",
    "Product": "business", "Finance": "finance", "Design": "design", "Marketing": "marketing",
    "Human Resources": "hr",
}

ARTIFACTS: dict[str, list[str]] = {
    "Data": ["an interactive sales dashboard", "a customer churn analysis", "automated weekly KPI reports",
             "a data quality monitoring pipeline", "a market basket analysis", "an HR attrition analysis",
             "a COVID-19 trends report", "a retail demand forecasting study"],
    "Business": ["a requirements document for a loan origination module", "process maps for the order-to-cash flow",
                 "a vendor evaluation report", "a customer feedback analysis", "a gap analysis for a CRM rollout",
                 "user stories for a hospital appointment system"],
    "Software Engineering": ["a REST backend for a food delivery app", "an e-commerce web application",
                             "a real-time chat application", "an expense tracker app", "a URL shortener service",
                             "a library management system", "a job portal", "a blog platform with authentication"],
    "AI/ML": ["a fake news classifier", "a movie recommendation engine", "a house price prediction model",
              "a resume screening model", "a defect detection model", "a customer support chatbot",
              "a credit risk scoring model", "a traffic sign recognition model"],
    "Cloud & DevOps": ["a CI/CD pipeline for a microservice", "auto-scaling infrastructure for a web app",
                       "a centralized logging and monitoring stack", "infrastructure templates for staging and production",
                       "a containerized deployment of a three-tier app", "a cost dashboard for cloud resources"],
    "Security": ["a home-lab SOC with custom alert rules", "a vulnerability assessment of a web application",
                 "a phishing awareness simulation", "network hardening for a college lab",
                 "a password-strength auditing tool", "an incident response playbook"],
    "Marketing": ["an SEO audit for a D2C website", "a social media campaign for a product launch",
                  "a content calendar for a SaaS blog", "Google Ads campaigns for a local business",
                  "an email nurture campaign", "a competitor keyword gap analysis"],
    "Product": ["a funnel analysis for an onboarding flow", "a feature prioritisation framework",
                "a product teardown of a fintech app", "an A/B test on a pricing page",
                "a retention cohort analysis", "a PRD for a referral feature"],
    "IoT & Embedded": ["a smart irrigation system", "a home automation controller", "an air-quality monitoring device",
                       "a smart energy meter", "a vehicle tracking device", "a wearable health monitor"],
    "Design": ["a redesign of a college event app", "a design system for a fintech dashboard",
               "a mobile banking app prototype", "an e-commerce checkout flow", "a travel booking app UI",
               "an accessibility audit of a news website"],
    "Emerging Tech": ["a decentralized voting dApp", "an NFT marketplace prototype", "a 2D platformer game",
                      "a VR campus tour", "a crowdfunding smart contract", "a multiplayer racing game"],
    "Finance": ["a three-statement financial model for a listed company", "a DCF valuation of an FMCG company",
                "a monthly budget variance report", "an equity research report on the auto sector",
                "a working capital analysis", "a GST reconciliation workbook"],
    "Human Resources": ["a campus hiring drive", "an employee onboarding programme", "an engagement survey analysis",
                        "an HR policy handbook", "a payroll audit", "a referral hiring campaign"],
}
ACTION_VERBS = ["Developed", "Built", "Designed", "Implemented", "Created", "Engineered", "Led", "Optimized",
                "Automated", "Analyzed", "Deployed", "Integrated", "Streamlined", "Launched", "Architected",
                "Conducted", "Delivered", "Improved", "Migrated", "Spearheaded", "Configured", "Researched",
                "Produced", "Managed", "Coordinated", "Executed", "Prototyped", "Modelled"]
METRICS_DOWN = ["processing time", "page load time", "reporting time", "error rate", "monthly costs",
                "bug count", "API response time", "customer churn", "manual effort", "turnaround time"]
METRICS_UP = ["user engagement", "conversion rate", "organic traffic", "test coverage", "customer satisfaction",
              "team productivity", "model accuracy", "lead quality", "retention", "click-through rate"]
CERTS: dict[str, list[str]] = {
    "Data": ["Google Data Analytics Professional Certificate", "Microsoft Certified: Power BI Data Analyst Associate",
             "IBM Data Analyst Professional Certificate"],
    "AI/ML": ["Machine Learning Specialization - DeepLearning.AI", "TensorFlow Developer Certificate",
              "NPTEL: Introduction to Machine Learning", "Deep Learning Specialization - Coursera"],
    "Cloud & DevOps": ["AWS Certified Cloud Practitioner", "AWS Certified Solutions Architect - Associate",
                       "Certified Kubernetes Administrator (CKA)", "Microsoft Certified: Azure Fundamentals"],
    "Security": ["CompTIA Security+", "Certified Ethical Hacker (CEH)", "Cisco CyberOps Associate",
                 "Google Cybersecurity Certificate"],
    "Marketing": ["Google Ads Search Certification", "HubSpot Content Marketing Certification",
                  "Google Analytics Certification", "Meta Certified Digital Marketing Associate"],
    "Software Engineering": ["Meta Front-End Developer Certificate", "Oracle Certified Java Programmer",
                             "freeCodeCamp Responsive Web Design", "NPTEL: Programming in Java"],
    "Business": ["IIBA ECBA", "Google Project Management Certificate", "Six Sigma Yellow Belt"],
    "Product": ["Product Management - Duke University (Coursera)", "Google UX Design Certificate"],
    "IoT & Embedded": ["NPTEL: Introduction to Internet of Things", "Embedded Systems - Shape the World (edX)"],
    "Design": ["Google UX Design Professional Certificate", "Interaction Design Foundation - UI Design Patterns"],
    "Emerging Tech": ["Blockchain Basics - Coursera", "Unity Certified User: Programmer"],
    "Finance": ["NISM Equity Derivatives", "Financial Modeling & Valuation Analyst (FMVA)", "CA Intermediate"],
    "Human Resources": ["SHRM Essentials of HR Management", "LinkedIn Recruiter Certification"],
}
SOFT_SKILLS = ["Communication", "Teamwork", "Leadership", "Problem Solving", "Critical Thinking",
               "Time Management", "Adaptability", "Attention to Detail", "Presentation Skills"]

N_STYLES = 6
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class Experience:
    title: str
    company: str
    start: date
    end: date | None  # None = present
    bullets: list[str]


@dataclass
class Project:
    title: str
    bullets: list[str]
    tech: list[str]


@dataclass
class Profile:
    name: str
    email: str
    phone: str
    city: str
    summary: str
    degree: str
    college: str
    grad_year: int
    score: str
    experiences: list[Experience]
    projects: list[Project]
    skills: list[str]                       # canonical, ground truth
    soft: list[str]
    certifications: list[str]
    surface: dict[str, str] = field(default_factory=dict)  # canonical -> written form


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #
class ResumeGenerator:
    def __init__(self, seed: int = RANDOM_SEED) -> None:
        self.rng = random.Random(seed)
        self.skills = load_skills()
        self.roles = list(load_roles().values())
        self.tech_skill_names = [n for n, s in self.skills.items() if s.category != "soft_skills"]
        self.today = date(2026, 6, 30)

    # ---- skill sampling -------------------------------------------------- #
    def sample_skills(self, role: Role, case: str, partner: Role | None) -> list[str]:
        rng = self.rng
        chosen: list[str] = []
        if case == "weak":
            req = role.required_names[:]
            rng.shuffle(req)
            chosen += req[: rng.randint(2, 4)]
        else:
            for rs in role.required_skills:
                if rng.random() < 0.65 + 0.06 * rs.weight:   # 0.71 .. 0.95
                    chosen.append(rs.skill)
            for nh in role.nice_to_have:
                if rng.random() < 0.30:
                    chosen.append(nh)
        if partner is not None:                               # hybrid profile
            for rs in partner.required_skills:
                if rng.random() < 0.55:
                    chosen.append(rs.skill)
        # noise skills
        chosen += rng.sample(self.tech_skill_names, rng.randint(1, 3))
        # dedupe keep order
        seen: set[str] = set()
        out = [s for s in chosen if not (s in seen or seen.add(s))]
        return out

    def surface_form(self, skill: str) -> str:
        """Write a skill the way a human might: canonical (70%) or an alias (30%)."""
        s = self.skills[skill]
        if s.aliases and self.rng.random() < 0.30:
            alias = self.rng.choice(s.aliases)
            # keep strict aliases exactly; others sometimes capitalised
            if alias in s.strict or self.rng.random() < 0.5:
                return alias
            return alias.title() if len(alias) > 3 else alias.upper()
        return s.name

    # ---- text helpers ---------------------------------------------------- #
    def join_skills(self, items: list[str]) -> str:
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + " and " + items[-1]

    def result_phrase(self) -> str:
        rng = self.rng
        options = [
            lambda: f"reducing {rng.choice(METRICS_DOWN)} by {rng.randint(10, 65)}%",
            lambda: f"improving {rng.choice(METRICS_UP)} by {rng.randint(8, 45)}%",
            lambda: f"serving {rng.choice([200, 500, 1200, 3000, 10000, 25000])}+ users",
            lambda: f"saving {rng.randint(3, 20)} hours of manual work per week",
            lambda: f"achieving {rng.randint(82, 98)}% accuracy on the test set",
            lambda: f"processing {rng.choice([5, 20, 50, 100, 500])}K+ records daily",
            lambda: f"cutting costs by ₹{rng.randint(1, 15)} lakh annually",
            lambda: f"used by {rng.randint(3, 12)} teams across the organisation",
        ]
        return rng.choice(options)()

    def strong_bullet(self, artifact: str, skills: list[str]) -> str:
        rng = self.rng
        verb = rng.choice(ACTION_VERBS)
        sk = self.join_skills([self.surface[s] for s in skills]) if skills else "modern tools"
        templates = [
            f"{verb} {artifact} using {sk}, {self.result_phrase()}.",
            f"{verb} {artifact} with {sk}; {self.result_phrase()}.",
            f"Using {sk}, {verb.lower()} {artifact}, {self.result_phrase()}.",
            f"{verb} and maintained {artifact} ({sk}), {self.result_phrase()}.",
            f"{verb} {artifact} in {sk} for {rng.randint(2, 40)} stakeholders, {self.result_phrase()}.",
        ]
        return rng.choice(templates)

    def weak_bullet(self, artifact: str, skills: list[str]) -> str:
        rng = self.rng
        sk = self.join_skills([self.surface[s] for s in skills]) if skills else "various tools"
        templates = [
            f"Worked on {artifact} using {sk}.",
            f"Responsible for {artifact}.",
            f"Helped the team with {sk}.",
            f"Was involved in {artifact} and used {sk}.",
            f"Did tasks related to {artifact}.",
        ]
        return rng.choice(templates)

    # ---- profile ---------------------------------------------------------- #
    def make_profile(self, role: Role, case: str, partner: Role | None) -> Profile:
        rng = self.rng
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower().replace(chr(39), '')}{rng.randint(1, 99)}@{rng.choice(['gmail.com', 'outlook.com', 'yahoo.in', 'proton.me'])}"
        phone = rng.choice([f"+91 {rng.randint(70000, 99999)} {rng.randint(10000, 99999)}",
                            f"+91-{rng.randint(7000000000, 9999999999)}",
                            f"{rng.randint(7000000000, 9999999999)}"])
        skills = self.sample_skills(role, case, partner)
        self.surface = {s: self.surface_form(s) for s in skills}
        soft = rng.sample(SOFT_SKILLS, rng.randint(1, 3))
        for s in soft:
            self.surface.setdefault(s, s)

        degree_key = DOMAIN_TO_DEGREE.get(role.domain, "tech")
        degree = rng.choice(DEGREES_BY_DOMAIN[degree_key])

        # experience ------------------------------------------------------- #
        years_target = 0.0
        if role.experience_level == "mid" and case != "weak" and rng.random() < 0.75:
            years_target = rng.uniform(1.5, 5)
        elif role.experience_level == "entry" and rng.random() < 0.25:
            years_target = rng.uniform(0.5, 2.5)
        grad_year = self.today.year - int(years_target) - rng.choice([0, 0, 1])
        if years_target < 0.5:
            grad_year = rng.choice([2025, 2026, 2026, 2027])
        score = rng.choice([f"CGPA: {rng.uniform(6.2, 9.8):.2f}/10", f"CGPA {rng.uniform(6.2, 9.8):.1f}",
                            f"Percentage: {rng.randint(62, 95)}%", f"GPA: {rng.uniform(2.8, 4.0):.2f}/4.0"])

        artifacts = ARTIFACTS.get(role.domain, ARTIFACTS["Software Engineering"])[:]
        if partner is not None:
            artifacts += ARTIFACTS.get(partner.domain, [])
        rng.shuffle(artifacts)
        weak = case == "weak"

        tech_skills = [s for s in skills if self.skills[s].category != "soft_skills"] or skills
        pool = tech_skills[:]
        rng.shuffle(pool)

        def take(k: int) -> list[str]:
            nonlocal pool
            if not pool:
                pool = tech_skills[:]
                rng.shuffle(pool)
            got, pool = pool[:k], pool[k:]
            return got

        experiences: list[Experience] = []
        end = self.today if years_target else date(rng.choice([2025, 2026]), rng.randint(1, 12), 1)
        n_intern = 0 if weak else rng.choice([0, 1, 1, 2, 2, 3])
        # full-time jobs for experienced profiles
        remaining_months = int(years_target * 12)
        while remaining_months >= 6:
            months = min(remaining_months, rng.randint(10, 36))
            start = _add_months(end, -months)
            title = rng.choice([t for t in role.typical_titles if "Intern" not in t] or [role.title])
            n_b = rng.randint(2, 4)
            bullets = [self.strong_bullet(artifacts[i % len(artifacts)], take(rng.randint(1, 3)))
                       for i in range(n_b)]
            experiences.append(Experience(title, rng.choice(COMPANIES), start,
                                          None if end == self.today and not experiences else end, bullets))
            end = _add_months(start, -rng.randint(0, 3))
            remaining_months -= months
        for _ in range(n_intern):
            months = rng.randint(2, 6)
            start = _add_months(end, -months)
            titles = [t for t in role.typical_titles if "Intern" in t] or [f"{role.title} Intern"]
            bullets = []
            for i in range(rng.randint(1, 3)):
                art = rng.choice(artifacts)
                ks = take(rng.randint(1, 3))
                bullets.append(self.weak_bullet(art, ks) if rng.random() < 0.2 else self.strong_bullet(art, ks))
            experiences.append(Experience(rng.choice(titles), rng.choice(COMPANIES), start, end, bullets))
            end = _add_months(start, -rng.randint(1, 6))

        # projects ----------------------------------------------------------- #
        projects: list[Project] = []
        n_proj = 1 if weak else rng.randint(1, 4)
        for i in range(n_proj):
            art = artifacts[(i + 3) % len(artifacts)]
            title = _title_from_artifact(art)
            tech = take(rng.randint(2, 4))
            n_b = rng.randint(1, 3)
            bullets = []
            for _ in range(n_b):
                if weak or rng.random() < 0.15:
                    bullets.append(self.weak_bullet(art, tech[:2]))
                else:
                    bullets.append(self.strong_bullet(art, rng.sample(tech, min(len(tech), rng.randint(1, 3)))))
            projects.append(Project(title, bullets, tech))
        # make sure every leftover skill appears in some project's tech line
        mentioned = {s for p in projects for s in p.tech}
        leftovers = [s for s in tech_skills if s not in mentioned]
        for j, s in enumerate(leftovers):          # spread round-robin
            if projects:
                projects[j % len(projects)].tech.append(s)

        certs: list[str] = []
        if not weak:
            pool_c = CERTS.get(role.domain, []) + [f"{self.skills[s].name} - Coursera" for s in tech_skills[:3]]
            certs = rng.sample(pool_c, min(len(pool_c), rng.choice([0, 1, 1, 2, 3])))

        top3 = [self.surface[s] for s in tech_skills[:3]]
        summary = rng.choice([
            f"{rng.choice(['Motivated', 'Detail-oriented', 'Curious', 'Results-driven', 'Enthusiastic'])} "
            f"{degree.split(' in ')[0]} {'graduate' if grad_year <= 2026 else 'student'} interested in "
            f"{role.domain.lower()} with hands-on experience in {self.join_skills(top3)}.",
            f"Aspiring {role.title} who enjoys solving real problems using {self.join_skills(top3)}.",
            f"{role.title} with {max(1, round(years_target))}+ years of experience in {self.join_skills(top3)}."
            if years_target >= 1 else
            f"Final-year student seeking a {role.title} internship; skilled in {self.join_skills(top3)}.",
        ])
        if weak:
            summary = "Looking for a job where I can learn and grow."

        return Profile(name, email, phone, rng.choice(CITIES), summary, degree, rng.choice(COLLEGES),
                       grad_year, score, experiences, projects, skills, soft, certs, dict(self.surface))

    # ---- rendering -------------------------------------------------------- #
    def fmt_date(self, d: date | None, style: int) -> str:
        if d is None:
            return "Present" if style != 3 else "Current"
        return [
            f"{MONTHS[d.month - 1]} {d.year}",
            f"{d.month:02d}/{d.year}",
            f"{MONTHS_LONG[d.month - 1]} {d.year}",
            f"{MONTHS[d.month - 1]} {d.year}",
            f"{d.year}-{d.month:02d}",
            f"{MONTHS[d.month - 1]}' {str(d.year)[2:]}",
        ][style]

    def render(self, p: Profile, style: int) -> str:
        rng = self.rng
        H = {  # heading text per style
            0: dict(sum="SUMMARY", edu="EDUCATION", exp="EXPERIENCE", proj="PROJECTS", sk="SKILLS", cert="CERTIFICATIONS"),
            1: dict(sum="Profile:", edu="Education:", exp="Work Experience:", proj="Projects:", sk="Technical Skills:", cert="Certifications:"),
            2: dict(sum="## About Me", edu="## Education", exp="## Work Experience", proj="## Projects", sk="## Skills", cert="## Certifications"),
            3: dict(sum="CAREER OBJECTIVE", edu="ACADEMIC BACKGROUND", exp="INTERNSHIPS", proj="PERSONAL PROJECTS", sk="TECHNICAL SKILLS", cert="COURSES & CERTIFICATIONS"),
            4: dict(sum="Professional Summary", edu="Academic Qualifications", exp="Professional Experience", proj="Key Projects", sk="", cert="Licenses & Certifications"),
            5: dict(sum="Objective", edu="Education Details", exp="Experience", proj="Academic Projects", sk="Skills & Tools", cert="Achievements & Certifications"),
        }[style]
        bullet = ["•", "-", "*", "–", "", "➢"][style]
        sep = [" | ", " · ", " | ", ", ", " | ", " / "][style]
        L: list[str] = []

        # header
        L.append(p.name.upper() if style in (0, 3) else p.name)
        contact = [p.email, p.phone, p.city]
        if rng.random() < 0.6:
            contact.append(f"linkedin.com/in/{p.name.lower().replace(' ', '-')}")
        if rng.random() < 0.5:
            contact.append(f"github.com/{p.name.split()[0].lower()}{rng.randint(1, 999)}")
        if style == 4:
            L += contact
        else:
            L.append(sep.join(contact))
        L.append("")

        if p.summary and (style in (2, 3, 4) or rng.random() < 0.5):
            L += [H["sum"], p.summary, ""]

        def bl(text: str) -> str:
            return f"{bullet} {text}" if bullet else text

        edu_block = [H["edu"]]
        if style in (1, 5):
            edu_block += [f"{p.degree} — {p.college} ({p.grad_year - 4} - {p.grad_year})", p.score]
        else:
            edu_block += [p.degree, f"{p.college}, {p.grad_year - 4} – {p.grad_year}", p.score]
        if rng.random() < 0.3:
            edu_block.append(f"Class XII (CBSE) — {rng.randint(70, 97)}%")
        edu_block.append("")

        exp_block: list[str] = []
        if p.experiences:
            exp_block.append(H["exp"])
            for e in p.experiences:
                dr = f"{self.fmt_date(e.start, style)} - {self.fmt_date(e.end, style)}"
                if style in (0, 3):
                    exp_block.append(f"{e.title}, {e.company}    {dr}")
                elif style == 1:
                    exp_block += [f"{e.title} | {e.company}", dr]
                elif style == 2:
                    exp_block.append(f"### {e.title} @ {e.company} ({dr})")
                elif style == 4:
                    exp_block.append(f"{e.company} — {e.title} ({dr})")
                    exp_block.append(" ".join(e.bullets))
                    exp_block.append("")
                    continue
                else:
                    exp_block += [f"{e.company}", f"{e.title} ({dr})"]
                exp_block += [bl(b) for b in e.bullets]
                exp_block.append("")

        proj_block = [H["proj"]]
        for pr in p.projects:
            tech_line = ", ".join(p.surface.get(s, s) for s in pr.tech)
            if style == 4:
                proj_block += [pr.title, " ".join(pr.bullets) + f" Technologies: {tech_line}.", ""]
            elif style == 2:
                proj_block += [f"### {pr.title}", f"*Tech:* {tech_line}"] + [bl(b) for b in pr.bullets] + [""]
            else:
                head = f"{pr.title} ({tech_line})" if style in (0, 5) else pr.title
                proj_block.append(head)
                if style not in (0, 5):
                    proj_block.append(f"Tech stack: {tech_line}")
                proj_block += [bl(b) for b in pr.bullets] + [""]

        sk_block: list[str] = []
        if H["sk"]:
            tech = [s for s in p.skills if self.skills[s].category != "soft_skills"]
            soft = [p.surface.get(s, s) for s in p.soft] + \
                   [p.surface[s] for s in p.skills if self.skills[s].category == "soft_skills"]
            sk_block.append(H["sk"])
            if style == 1:  # grouped by category
                groups: dict[str, list[str]] = {}
                for s in tech:
                    groups.setdefault(self.skills[s].category_label, []).append(p.surface[s])
                sk_block += [f"{k}: {', '.join(v)}" for k, v in groups.items()]
            elif style == 5:
                levels = ["Beginner", "Intermediate", "Advanced"]
                sk_block += [bl(f"{p.surface[s]} ({rng.choice(levels)})") for s in tech]
            elif style == 2:
                sk_block.append(" | ".join(p.surface[s] for s in tech))
            else:
                sk_block.append(", ".join(p.surface[s] for s in tech))
            if soft:
                sk_block.append(f"Soft skills: {', '.join(soft)}")
            sk_block.append("")
        else:  # no skills section -> soft skills go into summary-ish line
            sk_block = [f"Strengths: {', '.join(p.soft)}", ""]

        cert_block = ([H["cert"]] + [bl(c) for c in p.certifications] + [""]) if p.certifications else []

        # section ordering varies a little
        order = [edu_block, exp_block, proj_block, sk_block, cert_block]
        if style in (0, 2) or rng.random() < 0.3:
            order = [sk_block, exp_block, proj_block, edu_block, cert_block]
        for block in order:
            L += block
        return "\n".join(L).strip() + "\n"

    def years_of_experience(self, p: Profile) -> float:
        months = 0
        for e in p.experiences:
            end = e.end or self.today
            months += max(1, (end.year - e.start.year) * 12 + end.month - e.start.month)
        return round(months / 12, 1)


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def _title_from_artifact(art: str) -> str:
    words = art.split()
    if words[0] in ("a", "an", "the"):
        words = words[1:]
    small = {"a", "an", "the", "for", "of", "on", "in", "to", "and", "with"}
    out = []
    for k, w in enumerate(words):
        if w.isupper() or any(c.isdigit() for c in w) or (k and w in small):
            out.append(w)
        else:
            out.append(w[0].upper() + w[1:])
    return " ".join(out)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def generate(n: int, seed: int = RANDOM_SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    gen = ResumeGenerator(seed)
    rng = gen.rng
    nprng = np.random.default_rng(seed)
    roles = gen.roles
    rows: list[dict[str, object]] = []
    pairs: list[dict[str, object]] = []
    for i in range(n):
        role = roles[i % len(roles)]                          # balanced classes
        r = rng.random()
        case = "hybrid" if r < 0.05 else "weak" if r < 0.10 else "normal"
        partner = rng.choice([x for x in roles if x.id != role.id]) if case == "hybrid" else None
        style = rng.randrange(N_STYLES)
        prof = gen.make_profile(role, case, partner)
        years = gen.years_of_experience(prof)
        text = gen.render(prof, style)
        rid = f"R{i:05d}"
        rows.append({
            "resume_id": rid, "role_id": role.id, "role_title": role.title, "style_id": style,
            "case_type": case, "partner_role": partner.id if partner else "",
            "skills": "|".join(prof.skills + prof.soft), "years_experience": years, "text": text,
        })
        # match pairs: true role + same-domain role + 2 random roles
        true_skills = set(prof.skills) | set(prof.soft)
        others = [x for x in roles if x.id != role.id]
        same = [x for x in others if x.domain == role.domain]
        cand = ([rng.choice(same)] if same else []) + rng.sample(others, 2)
        if partner is not None:
            cand.append(partner)
        for target_role in [role] + cand:
            score = synthetic_target(true_skills, years, target_role, target_role.id == role.id)
            score = float(np.clip(score + nprng.normal(0, 3.0), 0, 100))
            pairs.append({"resume_id": rid, "role_id": target_role.id, "match_score": round(score, 2)})
    df = pd.DataFrame(rows)
    pairs_df = pd.DataFrame(pairs).drop_duplicates(["resume_id", "role_id"])
    return df, pairs_df


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic resumes for InternAI")
    ap.add_argument("--n", type=int, default=5400, help="number of resumes (default 5400 = 180 per role)")
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = ap.parse_args()

    df, pairs = generate(args.n, args.seed)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "synthetic_resumes.csv"
    out_pairs = DATA_DIR / "match_pairs.csv"
    df.to_csv(out, index=False)
    pairs.to_csv(out_pairs, index=False)

    print(f"Saved {len(df)} resumes -> {out}")
    print(f"Saved {len(pairs)} (resume, role, match_score) pairs -> {out_pairs}")
    print("\nClass distribution:")
    print(df["role_title"].value_counts().sort_index().to_string())
    print("\nCase types:", df["case_type"].value_counts().to_dict())
    print("Styles   :", df["style_id"].value_counts().sort_index().to_dict())
    print(f"Match score: mean={pairs.match_score.mean():.1f}  min={pairs.match_score.min():.1f}  max={pairs.match_score.max():.1f}")


if __name__ == "__main__":
    main()
