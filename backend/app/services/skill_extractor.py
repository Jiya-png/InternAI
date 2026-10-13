"""
Skill extraction with spaCy PhraseMatcher.

Two matchers are built from skills.json:
* ``loose``  - attr="LOWER": case-insensitive (``python``, ``ReactJS``)
* ``strict`` - attr="ORTH" : exact case for ambiguous words (``R``, ``Go``, ``Excel``)

Overlapping matches keep the longest span (so ``C++`` beats ``C`` and
``React Native`` beats ``React``). One-letter skills (R, C) are only accepted
in the skills section or on a line that lists at least two other skills, to
avoid false positives from initials like "Priya R".

Only the spaCy tokenizer is needed (``spacy.blank("en")``), so this is fast
and does not need the en_core_web_sm model.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

import spacy
from spacy.matcher import PhraseMatcher
from spacy.util import filter_spans

from app.services.catalog import load_skills

# Characters used as separators/bullets in resumes -> replaced by " , "
_SEPARATORS = re.compile(r"[|•➢▪●·◦►✓✔■□★◆❖➤→]")
_URLISH = re.compile(r"(@|https?://|www\.|linkedin\.com|github\.com)", re.I)


@dataclass
class SkillHit:
    name: str
    category: str
    category_label: str
    count: int = 0
    sections: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "category_label": self.category_label,
            "count": self.count,
            "sections": sorted(self.sections),
        }


class SkillExtractor:
    def __init__(self) -> None:
        self.nlp = spacy.blank("en")
        self.skills = load_skills()
        self.loose = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        self.strict = PhraseMatcher(self.nlp.vocab, attr="ORTH")
        loose_patterns: dict[str, list] = defaultdict(list)
        strict_patterns: dict[str, list] = defaultdict(list)
        for skill in self.skills.values():
            for term in skill.terms:
                doc = self.nlp.make_doc(term)
                if term in skill.strict:
                    strict_patterns[skill.name].append(doc)
                else:
                    loose_patterns[skill.name].append(doc)
        for name, pats in loose_patterns.items():
            self.loose.add(name, pats)
        for name, pats in strict_patterns.items():
            self.strict.add(name, pats)

    @staticmethod
    def prepare(line: str) -> str:
        return _SEPARATORS.sub(" , ", line)

    def match_line(self, line: str) -> list[tuple[str, str]]:
        """Return [(canonical_skill, matched_text)] for one line."""
        doc = self.nlp.make_doc(self.prepare(line))
        spans = []
        for matcher in (self.loose, self.strict):
            for match_id, start, end in matcher(doc):
                span = doc[start:end]
                span.label_ = self.nlp.vocab.strings[match_id]
                spans.append(span)
        spans = filter_spans(spans)  # longest, non-overlapping
        return [(s.label_, s.text) for s in spans]

    def extract(self, sections: dict[str, list[str]], skip_lines: set[str] | None = None) -> list[SkillHit]:
        """
        Scan every section (skills, projects, experience, summary, ...).
        ``skip_lines`` = exact lines to ignore (e.g. the candidate's name).
        """
        skip_lines = skip_lines or set()
        hits: dict[str, SkillHit] = {}
        for section, lines in sections.items():
            for line in lines:
                if not line.strip() or line in skip_lines or _URLISH.search(line):
                    continue
                found = self.match_line(line)
                names_on_line = {n for n, _ in found}
                for name, text in found:
                    if len(text) == 1:  # "R" / "C": need list context
                        if section != "skills" and len(names_on_line - {name}) < 2:
                            continue
                    sk = self.skills[name]
                    hit = hits.setdefault(name, SkillHit(name, sk.category, sk.category_label))
                    hit.count += 1
                    hit.sections.add(section)
        return sorted(hits.values(), key=lambda h: (-h.count, h.name))

    def extract_from_text(self, text: str) -> list[str]:
        """Convenience: skills from free text (no section info)."""
        hits = self.extract({"text": text.splitlines()})
        return [h.name for h in hits]


@lru_cache(maxsize=1)
def get_extractor() -> SkillExtractor:
    return SkillExtractor()
