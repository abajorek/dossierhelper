"""Rule-based artifact classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from dateutil import parser as date_parser


class Category(Enum):
    TEACHING = "Teaching"
    SERVICE = "Service"
    SCHOLARLY = "Scholarly / Creative"
    ADVISING = "Advising"
    FORM = "Form"


@dataclass
class ClassificationResult:
    category: Category
    subcategory: str
    portfolio_destination: str
    rationale: str


_RULES: list[tuple[tuple[str, ...], ClassificationResult]] = [
    (("concert program", "ensemble"), ClassificationResult(Category.TEACHING, "Ensemble Leadership", "Primary PDF → Teaching Evidence", "Ensemble programs demonstrate instructional leadership.")),
    (("student assessment", "quiz", "evaluation"), ClassificationResult(Category.TEACHING, "Course Assessment", "Primary PDF → Teaching Evidence", "Student feedback shows teaching effectiveness.")),
    (("repertoire feedback", "pedagogy"), ClassificationResult(Category.TEACHING, "Course Material", "Primary PDF → Teaching Evidence", "Pedagogical material documents learning outcomes.")),
    (("member info", "roster"), ClassificationResult(Category.SERVICE, "Recruiting (admin evidence)", "Primary PDF → Service Evidence", "Recruitment management is classified as service.")),
    (("recruiting email", "prospect"), ClassificationResult(Category.SERVICE, "Recruiting (outreach)", "Primary PDF → Service Evidence", "Outreach recruiting is a service activity.")),
    (("vendor order", "invoice", "receipt"), ClassificationResult(Category.SERVICE, "Logistics / Ops", "Appendices", "Operational logistics go to appendices.")),
    (("leadership application", "mentorship"), ClassificationResult(Category.TEACHING, "Mentorship / Leadership Dev.", "Primary PDF → Teaching Evidence", "Leadership development counts as teaching.")),
    (("drill design", "musx", "sib"), ClassificationResult(Category.SCHOLARLY, "Creative Output", "Primary PDF → Scholarship Evidence", "Design files are creative scholarship.")),
    (("composition", "arrangement"), ClassificationResult(Category.SCHOLARLY, "Creative Output", "Primary PDF → Scholarship Evidence", "Compositions qualify as scholarship.")),
    (("literature review", "bib"), ClassificationResult(Category.SCHOLARLY, "Research Prep", "Primary PDF → Scholarship Evidence", "Lit reviews prepare scholarship.")),
    (("recording", "publicity"), ClassificationResult(Category.SCHOLARLY, "Creative Output", "Primary PDF → Scholarship Evidence", "Recordings promote creative work.")),
    (("community performance", "pep band", "game"), ClassificationResult(Category.SERVICE, "University Visibility", "Primary PDF → Service Evidence", "Campus performances expand visibility.")),
    (("clinic", "adjudicat"), ClassificationResult(Category.SERVICE, "Professional Engagement", "Primary PDF → Service Evidence", "Clinics and adjudication are service.")),
    (("advising load", "advisee"), ClassificationResult(Category.ADVISING, "Formal Advising", "Primary PDF → Advising Summary", "Advising reports document workload.")),
    (("orientation", "grad plan"), ClassificationResult(Category.ADVISING, "Advising Artifacts", "Primary PDF → Advising Evidence", "Advising materials support advising.")),
    (("annual evaluation",), ClassificationResult(Category.FORM, "Annual Eval", "SummaryTable (in Primary PDF)", "Annual evaluations are required forms.")),
    (("notice of intent", "cover sheet"), ClassificationResult(Category.FORM, "Cover Sheet", "Form (separate PDF)", "Cover sheets belong in the form section.")),
]


def normalize(text: str) -> str:
    return text.lower().strip()


def _tokenize(text: str) -> set[str]:
    text = normalize(text)
    tokens: set[str] = set()
    for part in text.replace("_", " ").replace("-", " ").split():
        tokens.add(part)
    return tokens


def classify(path: Path, *, metadata: Optional[dict[str, str]] = None, text: Optional[str] = None) -> Optional[ClassificationResult]:
    """Return a classification result if a rule matches."""

    haystacks: list[str] = [path.stem, path.suffix]
    if metadata:
        haystacks.extend(str(value) for value in metadata.values() if isinstance(value, str))
    if text:
        haystacks.append(text[:500])

    tokens: set[str] = set()
    for haystack in haystacks:
        tokens.update(_tokenize(haystack))

    for keywords, result in _RULES:
        if all(any(token.startswith(keyword) for token in tokens) for keyword in keywords):
            return result
    return None


def filter_by_year(paths: Iterable[Path], *, year: Optional[int], metadata_lookup: callable[[Path], dict[str, str]]) -> list[Path]:
    """Filter artifacts using creation year metadata or filesystem timestamps."""

    if year is None:
        return list(paths)

    filtered: list[Path] = []
    for path in paths:
        info = metadata_lookup(path)
        date_str = info.get("kMDItemContentCreationDate") or info.get("creation_date")
        if not date_str:
            stat = path.stat()
            created = datetime.fromtimestamp(stat.st_ctime)
            if created.year == year:
                filtered.append(path)
            continue
        try:
            parsed_date = date_parser.parse(str(date_str))
        except (ValueError, TypeError):
            continue
        if parsed_date.year == year:
            filtered.append(path)
    return filtered
