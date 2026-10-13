"""
Step 3 - Resume parser.

Pipeline:  file (PDF/DOCX/TXT) -> raw text -> clean lines -> sections
           -> contact info, education, experience (with durations),
              projects, certifications, skills (PhraseMatcher)
           -> structured dict (JSON serialisable)

Public API:
    extract_text(path)            -> str
    parse_text(text)              -> dict
    parse_resume(path)            -> dict
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.catalog import expand_implied, load_skills
from app.services.skill_extractor import get_extractor


class ResumeParseError(ValueError):
    """Raised when a file cannot be read or contains no usable text."""


# --------------------------------------------------------------------------- #
# 1. Text extraction
# --------------------------------------------------------------------------- #
def extract_text(path: str | Path) -> str:
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import pdfplumber

            pages: list[str] = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text(x_tolerance=1.5, y_tolerance=3) or "")
            text = "\n".join(pages)
        elif ext == ".docx":
            import docx  # python-docx

            d = docx.Document(str(path))
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:  # many templates put content in tables
                for row in table.rows:
                    cells = []
                    for c in row.cells:
                        t = c.text.strip()
                        if t and t not in cells:
                            cells.append(t)
                    parts.append(" | ".join(cells))
            text = "\n".join(parts)
        elif ext == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
        else:
            raise ResumeParseError(f"Unsupported file type '{ext}'. Upload a PDF or DOCX.")
    except ResumeParseError:
        raise
    except Exception as exc:  # corrupted / encrypted files
        raise ResumeParseError(f"Could not read the file: {exc}") from exc
    if len(text.strip()) < 50:
        raise ResumeParseError(
            "No readable text found. If this is a scanned/image PDF, export it as a text PDF or DOCX."
        )
    return text


# --------------------------------------------------------------------------- #
# 2. Cleaning
# --------------------------------------------------------------------------- #
_BULLET_CHARS = "•➢▪●◦►✓✔■□★◆❖➤→*-–—o"
_BULLET_RE = re.compile(r"^\s*(?:[•➢▪●◦►✓✔■□★◆❖➤→*]|[-–—](?=\s)|o(?=\s)|\d{1,2}[.)](?=\s))\s*")


def clean_text(text: str) -> list[str]:
    """Normalise unicode, fix whitespace, return a list of lines (blank lines kept)."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r", "\n").replace("\t", " ").replace(" ", " ")
    text = re.sub(r"[​-‏﻿]", "", text)
    lines = [re.sub(r"\s{2,}", "  ", ln).rstrip() for ln in text.split("\n")]
    # collapse 3+ blank lines into one
    out: list[str] = []
    for ln in lines:
        if not ln.strip() and out and not out[-1].strip():
            continue
        out.append(ln.strip())
    return out


def is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


# --------------------------------------------------------------------------- #
# 3. Section detection
# --------------------------------------------------------------------------- #
SECTION_SYNONYMS: dict[str, list[str]] = {
    "summary": ["summary", "profile", "about me", "about", "objective", "career objective", "professional summary",
                "personal statement", "profile summary", "career summary", "professional profile"],
    "education": ["education", "academics", "academic background", "academic qualifications", "qualifications",
                  "education details", "educational qualifications", "academic details", "educational background",
                  "academic profile", "education and training"],
    "experience": ["experience", "work experience", "professional experience", "employment history", "employment",
                   "internships", "internship", "internship experience", "work history", "career history",
                   "relevant experience", "industry experience", "experience and internships",
                   "internships and experience", "professional background"],
    "projects": ["projects", "academic projects", "personal projects", "key projects", "project work",
                 "selected projects", "major projects", "project experience", "technical projects", "projects undertaken"],
    "skills": ["skills", "technical skills", "skills and tools", "core competencies", "technologies", "key skills",
               "skill set", "skillset", "technical expertise", "competencies", "areas of expertise", "it skills",
               "tools and technologies", "skills and expertise", "technical proficiency", "skills summary",
               "core skills", "professional skills"],
    "certifications": ["certifications", "certificates", "courses and certifications", "licenses and certifications",
                       "achievements and certifications", "certifications and courses", "courses", "training",
                       "trainings", "online courses", "certifications and training", "licenses"],
    "achievements": ["achievements", "awards", "honors", "honours", "accomplishments", "awards and achievements",
                     "extracurricular activities", "extra curricular activities", "extracurriculars",
                     "positions of responsibility", "activities", "leadership", "volunteering",
                     "leadership and activities"],
    "other": ["languages", "hobbies", "interests", "hobbies and interests", "references", "publications",
              "personal details", "declaration", "volunteer experience", "personal information"],
}
_HEADING_LOOKUP: dict[str, str] = {syn: sec for sec, syns in SECTION_SYNONYMS.items() for syn in syns}
_INLINE_HEADINGS = {"skills", "technical skills", "key skills", "core skills", "certifications", "it skills"}


def _norm_heading(line: str) -> str:
    s = line.strip().strip("#*_=:-–— ").lower()
    s = s.replace("&", " and ").replace("/", " and ")
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def detect_heading(line: str) -> tuple[str, str] | None:
    """
    Return (section, inline_content) if the line is a section heading, else None.
    ``inline_content`` is text after 'Skills: ...' style headings.
    """
    raw = line.strip()
    if not raw or len(raw) > 60:
        return None
    m = re.match(r"^[#*_\s]*([A-Za-z &/]+?)\s*[:\-–—]\s*(.+)$", raw)
    if m:  # e.g. "Technical Skills: Python, SQL"
        key = _norm_heading(m.group(1))
        if key in _INLINE_HEADINGS:
            return _HEADING_LOOKUP[key], m.group(2).strip()
    key = _norm_heading(raw)
    if key in _HEADING_LOOKUP and len(key.split()) <= 6:
        return _HEADING_LOOKUP[key], ""
    return None


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Group lines under the most recent heading. Lines before any heading -> 'header'."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for ln in lines:
        h = detect_heading(ln)
        if h:
            current = h[0]
            sections.setdefault(current, [])
            if h[1]:
                sections[current].append(h[1])
            continue
        sections.setdefault(current, []).append(ln)
    return sections


# --------------------------------------------------------------------------- #
# 4. Contact info
# --------------------------------------------------------------------------- #
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{3,5}(?!\d)")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+/?", re.I)


def find_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None


def find_phone(text: str) -> str | None:
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 10 <= len(digits) <= 13 and not re.fullmatch(r"(19|20)\d{2}(19|20)\d{2}", digits[:8] + digits[8:]):
            return m.group(0).strip()
    return None


@lru_cache(maxsize=1)
def _ner_model():
    """en_core_web_sm for PERSON names (optional; parser works without it)."""
    try:
        import spacy

        return spacy.load("en_core_web_sm", disable=["parser", "lemmatizer", "tagger", "attribute_ruler"])
    except Exception:
        return None


def find_name(header: list[str], all_lines: list[str]) -> str | None:
    candidates = [ln for ln in (header or all_lines)[:6] if ln.strip()]
    for ln in candidates:
        s = ln.strip().strip("#*").strip()
        if EMAIL_RE.search(s) or re.search(r"\d", s) or detect_heading(s):
            continue
        words = s.replace(".", ". ").split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", w) for w in words):
            return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in words)
    nlp = _ner_model()
    if nlp is not None:
        doc = nlp("\n".join(candidates[:4]))
        for ent in doc.ents:
            if ent.label_ == "PERSON" and 1 <= len(ent.text.split()) <= 4:
                return ent.text.strip()
    return None


# --------------------------------------------------------------------------- #
# 5. Dates & durations
# --------------------------------------------------------------------------- #
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:{_MON}\s*'?\s*\d{{2,4}}|\d{{1,2}}\s*/\s*\d{{4}}|\d{{4}}\s*[-/]\s*\d{{1,2}}(?!\d)|\d{{4}})"
_PRESENT = r"(?:present|current|now|ongoing|till date|to date|date)"
DATE_RANGE_RE = re.compile(rf"({_DATE})\s*(?:-|–|—|to|till|until|~)\s*({_DATE}|{_PRESENT})", re.I)
DURATION_RE = re.compile(r"(\d{1,2})\s*(?:\+\s*)?(months?|mos?|years?|yrs?)\b", re.I)
TODAY = date.today()


def _parse_date(s: str, is_end: bool = False) -> date | None:
    s = s.strip().lower().replace("’", "'")
    if re.fullmatch(_PRESENT, s, re.I):
        return TODAY
    m = re.match(rf"({_MON})\s*'?\s*(\d{{2,4}})", s, re.I)
    if m:
        mon = _MONTHS.get(m.group(1)[:3].lower(), 1)
        yr = int(m.group(2))
        yr = yr + 2000 if yr < 100 else yr
        return date(yr, mon, 1)
    m = re.match(r"(\d{1,2})\s*/\s*(\d{4})", s)
    if m:
        return date(int(m.group(2)), max(1, min(12, int(m.group(1)))), 1)
    m = re.match(r"(\d{4})\s*[-/]\s*(\d{1,2})", s)
    if m:
        return date(int(m.group(1)), max(1, min(12, int(m.group(2)))), 1)
    m = re.match(r"(\d{4})", s)
    if m:
        return date(int(m.group(1)), 12 if is_end else 1, 1)
    return None


def _months_between(a: date, b: date) -> int:
    return max(1, (b.year - a.year) * 12 + (b.month - a.month))


def find_date_range(text: str) -> tuple[date, date, str] | None:
    m = DATE_RANGE_RE.search(text)
    if not m:
        return None
    start, end = _parse_date(m.group(1)), _parse_date(m.group(2), is_end=True)
    if not start or not end or end < start or start.year < 1980:
        return None
    return start, end, m.group(0)


# --------------------------------------------------------------------------- #
# 6. Entries: education / experience / projects
# --------------------------------------------------------------------------- #
DEGREE_RE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|b\.e\.?|m\.e\.?|b\.?\s?sc|m\.?\s?sc|bca|mca|bba|mba|b\.?\s?com|m\.?\s?com|"
    r"b\.?\s?des|m\.?\s?des|b\.?\s?arch|ph\.?\s?d|bachelor(?:'s)?|master(?:'s)?|diploma|pgdm|pgdba|"
    r"class\s*x(?:ii)?|xii|12th|10th|hsc|ssc|b\.?\s?f\.?\s?a|bmm|b\.a\.|m\.a\.|ca inter\w*|associate degree)\b",
    re.I,
)
INSTITUTION_RE = re.compile(r"\b(university|college|institute|school|academy|iit|nit|iiit|bits|polytechnic|vidyalaya)\b", re.I)
SCORE_RE = re.compile(r"((?:c?gpa|cpi|sgpa)\s*[:\-]?\s*\d{1,2}(?:\.\d{1,2})?(?:\s*/\s*\d{1,2}(?:\.\d)?)?|"
                      r"\d{1,2}\.\d{1,2}\s*(?:/\s*10\s*)?(?:c?gpa|cpi)|"
                      r"\d{2}(?:\.\d{1,2})?\s*%|percentage\s*[:\-]?\s*\d{2}(?:\.\d+)?\s*%?)", re.I)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
TITLE_WORDS = re.compile(
    r"\b(intern|engineer|developer|analyst|manager|designer|associate|executive|consultant|trainee|lead|writer|"
    r"specialist|scientist|administrator|recruiter|architect|officer|coordinator|assistant|programmer|tester|"
    r"sde|representative|apprentice|fellow|researcher|strategist|editor|head|director)\b", re.I)


DEGREE_UPPER_RE = re.compile(r"\b(BA|MA|BSc|MSc|BE|ME|BS|MS|BCom|MCom|PhD)\b")  # case-sensitive short forms


def _has_degree(text: str) -> bool:
    return bool(DEGREE_RE.search(text) or DEGREE_UPPER_RE.search(text))


def parse_education(lines: list[str]) -> list[dict[str, Any]]:
    """
    Each entry: degree, institution, year (graduation / latest year), score.
    A new entry starts on every line that mentions a degree.
    """
    entries: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for raw in lines:
        ln = strip_bullet(raw)
        if not ln:
            continue
        has_deg = _has_degree(ln)
        if cur is None or (has_deg and cur.get("degree")):
            cur = {"degree": None, "institution": None, "year": None, "score": None}
            entries.append(cur)
        sc = SCORE_RE.search(ln)
        if sc and not cur["score"]:
            cur["score"] = sc.group(0).strip()
        years = YEAR_RE.findall(ln)
        if years:
            cur["year"] = max(int(y) for y in years)
        # remove dates / scores, then split into comma / dash / pipe separated parts
        clean = DATE_RANGE_RE.sub(" ", ln)
        clean = SCORE_RE.sub(" ", clean)
        clean = re.sub(r"\b(c?gpa|cpi)\b|\(\s*\)|\b(19|20)\d{2}\b", " ", clean, flags=re.I)
        parts = [p.strip(" ()|,–—-:") for p in re.split(r"\s*[—–|]\s*|\s+-\s+|,\s*|\(|\)", clean)]
        parts = [p for p in parts if p and len(p) > 1]
        if has_deg and not cur["degree"]:
            idx = next((i for i, p in enumerate(parts) if _has_degree(p)), 0)
            deg_parts = [parts[idx]] if parts else [ln]
            for p in parts[idx + 1:]:  # "B.Tech, Information Technology" -> keep the field
                if INSTITUTION_RE.search(p) or _has_degree(p) or len(p.split()) > 5:
                    break
                deg_parts.append(p)
                break
            cur["degree"] = ", ".join(deg_parts)
        if not cur["institution"]:
            for i, p in enumerate(parts):
                if INSTITUTION_RE.search(p) and not DEGREE_RE.search(p):
                    inst = p
                    nxt = parts[i + 1] if i + 1 < len(parts) else ""
                    if nxt and len(nxt.split()) <= 2 and nxt[:1].isupper() and not _has_degree(nxt):
                        inst = f"{p}, {nxt}"  # add the city
                    cur["institution"] = inst
                    break
    return [e for e in entries if e["degree"] or e["institution"]]


def merge_wrapped(lines: list[str]) -> list[str]:
    """
    PDFs wrap long bullets onto several lines. Join a line to the previous
    bullet when it looks like a continuation (starts lower-case, or the
    previous bullet did not end a sentence and this line has no date).
    """
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if (out and s and not is_bullet(s) and is_bullet(out[-1]) and not detect_heading(s)
                and not find_date_range(s)
                and (s[0].islower() or (not re.search(r"[.;:!?]$", out[-1]) and len(out[-1]) > 70))):
            out[-1] = out[-1].rstrip() + " " + s
        else:
            out.append(ln)
    return out


def _blocks(lines: list[str]) -> list[list[str]]:
    """
    Split a section into entries. A new entry starts after a blank line, or
    when a short non-bullet line (title / company / date) follows bullet text.
    """
    lines = merge_wrapped(lines)
    blocks: list[list[str]] = []
    cur: list[str] = []
    prev_content = False  # previous line was a bullet / description
    for i, ln in enumerate(lines):
        if not ln.strip():
            if cur:
                blocks.append(cur)
                cur = []
            prev_content = False
            continue
        bullet = is_bullet(ln)
        header_like = (not bullet) and (len(ln.split()) <= 14 or bool(find_date_range(ln)))
        if cur and prev_content and header_like and not TECH_LINE_RE.match(ln):
            blocks.append(cur)
            cur = []
        cur.append(ln)
        prev_content = bullet or len(ln.split()) > 14
    if cur:
        blocks.append(cur)
    return blocks


def _split_title_company(header: str) -> tuple[str | None, str | None]:
    header = header.strip("# ").strip()
    header = DATE_RANGE_RE.sub("", header)
    header = re.sub(r"\(\s*\)|\s{2,}", " ", header).strip(" ,|()–—-")
    parts = [p.strip(" ,()–—-") for p in re.split(r"\s+[|@—–-]\s+|,\s+|\s+at\s+|\s{2,}", header) if p.strip(" ,()")]
    if not parts:
        return None, None
    titles = [p for p in parts if TITLE_WORDS.search(p)]
    title = titles[0] if titles else parts[0]
    others = [p for p in parts if p != title]
    return title, (others[0] if others else None)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if len(s.strip().split()) >= 4]


def parse_experience(lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for block in _blocks(lines):
        header_lines = [ln for ln in block if not is_bullet(ln) and len(ln.split()) <= 14]
        desc_lines = [ln for ln in block if is_bullet(ln) or len(ln.split()) > 14]
        rng = None
        for ln in block:
            rng = find_date_range(ln)
            if rng:
                break
        title = company = None
        hdr = " | ".join(header_lines[:2])
        if hdr:
            if len(header_lines) >= 2 and not TITLE_WORDS.search(header_lines[0]) and TITLE_WORDS.search(header_lines[1]):
                title, _ = _split_title_company(header_lines[1])
                company = DATE_RANGE_RE.sub("", header_lines[0]).strip(" ,|()–—-") or None
            else:
                title, company = _split_title_company(hdr)
        months = None
        if rng:
            months = _months_between(rng[0], rng[1])
        else:
            dm = DURATION_RE.search(" ".join(block))
            if dm:
                n = int(dm.group(1))
                months = n * 12 if dm.group(2).lower().startswith(("y")) else n
        bullets: list[str] = []
        for ln in desc_lines:
            bullets += [strip_bullet(ln)] if is_bullet(ln) else _sentences(ln)
        if not (title or bullets):
            continue
        entries.append({
            "title": title,
            "company": company,
            "start": rng[0].isoformat() if rng else None,
            "end": rng[1].isoformat() if rng else None,
            "duration_months": months,
            "is_internship": bool(title and re.search(r"intern|trainee|apprentice", title, re.I)),
            "bullets": bullets,
        })
    return entries


def total_experience_years(entries: list[dict[str, Any]]) -> float:
    """Union of date intervals (so overlapping jobs are not double counted)."""
    intervals: list[tuple[date, date]] = []
    extra_months = 0
    for e in entries:
        if e.get("start") and e.get("end"):
            intervals.append((date.fromisoformat(e["start"]), date.fromisoformat(e["end"])))
        elif e.get("duration_months"):
            extra_months += int(e["duration_months"])
    intervals.sort()
    merged: list[list[date]] = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    months = sum(_months_between(s, e) for s, e in merged) + extra_months
    return round(months / 12, 1)


TECH_LINE_RE = re.compile(r"^\s*\*?\s*(tech(?:nologies|nology)?(?: stack)?|tools(?: used)?|built with|stack)\s*\*?\s*[:\-]\s*\*?\s*", re.I)


def parse_projects(lines: list[str]) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for block in _blocks(lines):
        title: str | None = None
        tech: list[str] = []
        bullets: list[str] = []
        for ln in block:
            if TECH_LINE_RE.match(ln):
                tech.append(TECH_LINE_RE.sub("", ln))
            elif is_bullet(ln):
                bullets.append(strip_bullet(ln))
            elif title is None and len(ln.split()) <= 14:
                t = DATE_RANGE_RE.sub("", ln.strip("# ").strip())
                m = re.match(r"^(.*?)\s*[(\[](.+)[)\]]\s*$", t)  # "Title (Python, SQL)"
                if m and "," in m.group(2):
                    t = m.group(1)
                    tech.append(m.group(2))
                else:
                    m = re.match(r"^(.*?)\s+[|—–]\s+(.+)$", t)  # "Title | Python, Pandas"
                    if m and get_extractor().match_line(m.group(2)):
                        t = m.group(1)
                        tech.append(m.group(2))
                title = t.strip(" |–—-:")
            else:
                # paragraph description; may contain "Technologies: ..."
                tm = re.search(r"(technologies|tech stack|tools used)\s*:\s*(.+)$", ln, re.I)
                if tm:
                    tech.append(tm.group(2).rstrip("."))
                    ln = ln[: tm.start()]
                bullets += _sentences(ln)
        if title or bullets:
            projects.append({"title": title or "Untitled project", "tech": ", ".join(tech), "bullets": bullets})
    return projects


# --------------------------------------------------------------------------- #
# 7. Main entry points
# --------------------------------------------------------------------------- #
def parse_text(text: str) -> dict[str, Any]:
    lines = clean_text(text)
    sections = split_sections(lines)
    full = "\n".join(lines)
    header = [ln for ln in sections.get("header", []) if ln.strip()]

    name = find_name(header, [ln for ln in lines if ln.strip()])
    email = find_email(full)
    phone = find_phone("\n".join(header) if header else full) or find_phone(full)
    linkedin = LINKEDIN_RE.search(full)
    github = GITHUB_RE.search(full)

    education = parse_education(sections.get("education", []))
    experience = parse_experience(sections.get("experience", []))
    projects = parse_projects(sections.get("projects", []))
    certifications = [strip_bullet(ln) for ln in sections.get("certifications", []) if strip_bullet(ln)]
    summary = " ".join(ln for ln in sections.get("summary", []) if ln.strip())
    # If no explicit summary, use the descriptive line(s) in the header.
    if not summary:
        summary = " ".join(ln for ln in header if len(ln.split()) > 8 and not EMAIL_RE.search(ln))

    skip = {ln for ln in header[:1]}  # never read skills from the name line
    hits = get_extractor().extract({k: v for k, v in sections.items()}, skip_lines=skip)
    skills = [h.name for h in hits]
    details = [h.to_dict() for h in hits]
    meta = load_skills()
    for s in expand_implied(skills):  # e.g. PostgreSQL -> SQL, Spring Boot -> Java
        skills.append(s)
        details.append({"name": s, "category": meta[s].category, "category_label": meta[s].category_label,
                        "count": 0, "sections": ["implied"]})

    bullets = [b for e in experience for b in e["bullets"]] + [b for p in projects for b in p["bullets"]]
    found = [s for s in sections if s != "header" and any(ln.strip() for ln in sections[s])]

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "links": {
            "linkedin": linkedin.group(0) if linkedin else None,
            "github": github.group(0) if github else None,
        },
        "summary": summary[:600],
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "skills": skills,
        "skill_details": details,
        "years_of_experience": total_experience_years(experience),
        "sections_found": found,
        "bullets": bullets,
        "word_count": len(full.split()),
        "text": full,
    }


def parse_resume(path: str | Path) -> dict[str, Any]:
    return parse_text(extract_text(path))
