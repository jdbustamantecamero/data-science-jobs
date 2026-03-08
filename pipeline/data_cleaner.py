"""Data cleaning utilities: HTML stripping, experience extraction, seniority."""
from __future__ import annotations

import re
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def clean_description(text: str | None) -> str | None:
    """Strip HTML tags and collapse whitespace from a job description."""
    if not text:
        return text
    stripper = _HTMLStripper()
    stripper.feed(text)
    cleaned = stripper.get_text()
    # Collapse multiple spaces/newlines to a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


# ---------------------------------------------------------------------------
# Years of experience extraction
# ---------------------------------------------------------------------------

# Each pattern captures the *minimum* years in group 1.
# Ordered from most specific to least specific.
_YEARS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(\d+)\s*[-–to]+\s*\d+\s+years?\s+(?:of\s+)?(?:relevant\s+|work\s+)?experience", re.I),
    re.compile(r"(\d+)\+?\s+years?\s+(?:of\s+)?(?:relevant\s+|work\s+)?experience", re.I),
    re.compile(r"minimum\s+(?:of\s+)?(\d+)\s+years?", re.I),
    re.compile(r"at\s+least\s+(\d+)\s+years?", re.I),
    re.compile(r"(\d+)\+?\s+years?\s+(?:of\s+)?(?:industry\s+)?experience", re.I),
]


def extract_years_experience(text: str | None) -> int | None:
    """Return the minimum years of experience mentioned in *text*, or None."""
    if not text:
        return None
    for pattern in _YEARS_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except (IndexError, ValueError):
                continue
    return None


# ---------------------------------------------------------------------------
# Seniority classification
# ---------------------------------------------------------------------------

# Rules are checked in order; first match wins.
# Each entry: (seniority_label, [regex_patterns_against_lowercased_title])
_TITLE_RULES: list[tuple[str, list[str]]] = [
    ("Intern",     [r"\bintern\b", r"\binternship\b", r"\bco-op\b", r"\bcoop\b"]),
    ("Junior",     [r"\bjunior\b", r"\bjr\b", r"\bentry[\s-]level\b", r"\bassociate\b",
                    r"\bnew\s+grad\b", r"\bgraduate\b"]),
    ("Senior",     [r"\bsenior\b", r"\bsr\b"]),
    ("Lead",       [r"\blead\b", r"\bstaff\b", r"\bprincipal\b", r"\barchitect\b"]),
    ("Director+",  [r"\bdirector\b", r"\bhead\s+of\b", r"\bvp\b", r"\bvice\s+president\b",
                    r"\bchief\b", r"\bmanager\b"]),
]

_COMPILED_TITLE_RULES: list[tuple[str, list[re.Pattern[str]]]] = [
    (label, [re.compile(p, re.I) for p in patterns])
    for label, patterns in _TITLE_RULES
]

_YEARS_TO_SENIORITY: list[tuple[int, str]] = [
    (2,  "Junior"),
    (5,  "Mid"),
    (9,  "Senior"),
    (99, "Lead"),
]


def classify_seniority(title: str | None, years_exp: int | None) -> str:
    """Return a seniority label for a job.

    Priority:
    1. Explicit keyword in the job title
    2. Years of experience extracted from the description
    3. Default: "Mid"
    """
    if title:
        for label, patterns in _COMPILED_TITLE_RULES:
            if any(p.search(title) for p in patterns):
                return label

    if years_exp is not None:
        for threshold, label in _YEARS_TO_SENIORITY:
            if years_exp <= threshold:
                return label

    return "Mid"
