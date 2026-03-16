"""
Data cleaning and normalization utilities for the job pipeline (Silver Layer).

This module contains specialized logic for stripping HTML from descriptions,
extracting numerical years of experience, classifying seniority levels,
and normalizing location strings (cities, provinces, countries) specifically 
for the Canadian job market.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from html.parser import HTMLParser
from zoneinfo import ZoneInfo


# ── HTML Cleaning ────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """
    Internal helper to strip HTML tags while preserving text content.
    """
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def clean_description(text: str | None) -> str | None:
    """
    Strip HTML tags and collapse redundant whitespace from a job description.
    Used to normalize raw API descriptions into a clean, searchable format.
    """
    if not text:
        return text
    stripper = _HTMLStripper()
    stripper.feed(text)
    cleaned = stripper.get_text()
    # Collapse multiple spaces/newlines to a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


# ── Timestamp Conversion ───────────────────────────────────────────────────

def convert_relative_timestamp(relative_str: str | None) -> str | None:
    """
    Convert a relative timestamp string (e.g. "1 day ago", "3 hours ago") 
    to an ISO 8601 string in UTC.
    
    Used specifically for SerpAPI results which return posted_at as relative time.
    Assumes the relative time is from now in the Toronto timezone.
    
    Args:
        relative_str: String like "1 day ago", "3 hours ago", "30 minutes ago", etc.
                     Or None/empty string.
    
    Returns:
        ISO 8601 UTC timestamp string (e.g. "2026-03-15T22:55:00+00:00") or None.
    """
    if not relative_str or not isinstance(relative_str, str):
        return None
    
    relative_str = relative_str.strip().lower()
    
    # Try to parse patterns like "1 day ago", "3 hours ago", "30 minutes ago"
    # Also handle singular forms: "1 day ago" vs "2 days ago"
    match = re.match(r'(\d+)\s+(second|minute|hour|day|week)s?\s+ago', relative_str)
    if not match:
        return None
    
    quantity = int(match.group(1))
    unit = match.group(2)
    
    # Create a datetime in Toronto timezone
    toronto_tz = ZoneInfo("America/Toronto")
    now_toronto = datetime.now(tz=toronto_tz)
    
    # Subtract the relative time
    if unit == "second":
        past_time = now_toronto - timedelta(seconds=quantity)
    elif unit == "minute":
        past_time = now_toronto - timedelta(minutes=quantity)
    elif unit == "hour":
        past_time = now_toronto - timedelta(hours=quantity)
    elif unit == "day":
        past_time = now_toronto - timedelta(days=quantity)
    elif unit == "week":
        past_time = now_toronto - timedelta(weeks=quantity)
    else:
        return None
    
    # Convert to UTC and return as ISO 8601 string
    utc_time = past_time.astimezone(ZoneInfo("UTC"))
    return utc_time.isoformat()



# Pre-compiled for performance during large batch transformations.
_YEARS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(\d+)\s*[-–to]+\s*\d+\s+years?\s+(?:of\s+)?(?:relevant\s+|work\s+)?experience", re.I),
    re.compile(r"(\d+)\+?\s+years?\s+(?:of\s+)?(?:relevant\s+|work\s+)?experience", re.I),
    re.compile(r"minimum\s+(?:of\s+)?(\d+)\s+years?", re.I),
    re.compile(r"at\s+least\s+(\d+)\s+years?", re.I),
    re.compile(r"(\d+)\+?\s+years?\s+(?:of\s+)?(?:industry\s+)?experience", re.I),
]


def extract_years_experience(text: str | None) -> int | None:
    """
    Return the minimum years of experience mentioned in a job description.
    
    Tries multiple patterns in order of specificity. 
    Returns the first match found, or None if no experience requirement is detected.
    """
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


# ── Seniority Classification ────────────────────────────────────────────────

# Taxonomy of seniority levels and their title-based keyword rules.
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
    """
    Classify the seniority of a job posting using a tiered approach.

    Priority:
    1. Direct keyword match in the job title (e.g., "Senior Data Scientist").
    2. Numerical experience requirements (e.g., 5 years -> Mid/Senior).
    3. Default to "Mid".
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


# ── Accent Stripping ────────────────────────────────────────────────────────

def _strip_accents(text: str) -> str:
    """
    Normalize strings by removing diacritics. 
    Converts 'Québec' -> 'Quebec', 'Montréal' -> 'Montreal'.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


# ── Province Normalization ──────────────────────────────────────────────────

_PROVINCE_MAP: dict[str, str] = {
    "ab": "Alberta", "alberta": "Alberta",
    "bc": "British Columbia", "b.c.": "British Columbia",
    "british columbia": "British Columbia",
    "mb": "Manitoba", "manitoba": "Manitoba",
    "nb": "New Brunswick", "new brunswick": "New Brunswick",
    "nl": "Newfoundland and Labrador", "newfoundland": "Newfoundland and Labrador",
    "newfoundland and labrador": "Newfoundland and Labrador",
    "ns": "Nova Scotia", "nova scotia": "Nova Scotia",
    "nt": "Northwest Territories", "northwest territories": "Northwest Territories",
    "nu": "Nunavut", "nunavut": "Nunavut",
    "on": "Ontario", "ontario": "Ontario",
    "pe": "Prince Edward Island", "pei": "Prince Edward Island",
    "prince edward island": "Prince Edward Island",
    "qc": "Quebec", "quebec": "Quebec", "québec": "Quebec",
    "sk": "Saskatchewan", "saskatchewan": "Saskatchewan",
    "yt": "Yukon", "yukon": "Yukon",
}


def normalize_province(state: str | None) -> str | None:
    """
    Convert raw province strings or abbreviations to canonical names.
    Handles accent stripping and common shorthand (e.g., 'ON' -> 'Ontario').
    """
    if not state:
        return None
    stripped = _strip_accents(state.strip())
    return _PROVINCE_MAP.get(stripped.lower(), stripped)


# ── City Normalization ──────────────────────────────────────────────────────

_CITY_ALIASES: dict[str, str | None] = {
    "greater vancouver": "Vancouver",
    "north vancouver": "Vancouver",
    "downtown": None,
    "king and spadina": "Toronto",
    "hamilton region": "Hamilton",
    "waterloo region": "Waterloo",
    "winnipeg region": "Winnipeg",
    "fort mcmurray region": "Fort McMurray",
    "halifax regional municipality": "Halifax",
}


def normalize_city(city: str | None) -> str | None:
    """
    Clean and normalize city names.
    Removes accents, resolves regional aliases, and strips generic noise terms.
    """
    if not city:
        return None
    stripped = _strip_accents(city.strip())
    key = stripped.lower()
    if key in _CITY_ALIASES:
        return _CITY_ALIASES[key]
    # Remove 'region' suffix if it exists
    stripped = re.sub(r"\s+region\s*$", "", stripped, flags=re.IGNORECASE).strip()
    return stripped or None


# ── Country Normalization ────────────────────────────────────────────────────

_COUNTRY_MAP: dict[str, str] = {
    "ca": "Canada",
    "canada": "Canada",
    "anywhere": "Anywhere",
}


def normalize_country(country: str | None) -> str | None:
    """
    Normalize country strings. Defaults to 'Anywhere' for missing values (remote indicator).
    """
    if not country:
        return "Anywhere"
    return _COUNTRY_MAP.get(country.strip().lower(), country.strip())


# ── Employment Type Normalization ───────────────────────────────────────────

_EMPLOYMENT_TYPE_MAP: dict[str, str] = {
    # Full-time variations (uppercase, lowercase, with/without hyphen)
    "full-time": "Full-time",
    "fulltime": "Full-time",
    "full_time": "Full-time",
    "full": "Full-time",
    "ft": "Full-time",
    
    # Part-time variations
    "part-time": "Part-time",
    "parttime": "Part-time",
    "part_time": "Part-time",
    "part": "Part-time",
    "pt": "Part-time",
    
    # Contract variations
    "contract": "Contract",
    "contractor": "Contract",
    "contract_to_hire": "Contract",
    "temporary": "Contract",
    "temp": "Contract",
    
    # Internship variations
    "internship": "Internship",
    "intern": "Internship",
    
    # Other
    "permanent": "Full-time",
}


def normalize_employment_type(emp_type: str | None) -> str | None:
    """
    Normalize employment type strings to canonical forms.
    Handles various API formats (FULL_TIME, full-time, Full-time, etc.)
    and maps them to standardized categories: Full-time, Part-time, Contract, Internship.
    """
    if not emp_type:
        return None
    
    # Normalize the input: strip whitespace, lowercase, replace common separators
    normalized = emp_type.strip().lower()
    
    # Check the mapping
    return _EMPLOYMENT_TYPE_MAP.get(normalized, emp_type.strip())


_CITY_TO_PROVINCE: dict[str, str] = {
    "toronto": "Ontario", "vancouver": "British Columbia", "calgary": "Alberta",
    "edmonton": "Alberta", "montreal": "Quebec", "ottawa": "Ontario",
    "mississauga": "Ontario", "brampton": "Ontario", "markham": "Ontario",
    "hamilton": "Ontario", "london": "Ontario", "kitchener": "Ontario",
    "waterloo": "Ontario", "windsor": "Ontario", "richmond hill": "Ontario",
    "oakville": "Ontario", "burlington": "Ontario", "oshawa": "Ontario",
    "barrie": "Ontario", "kingston": "Ontario", "sudbury": "Ontario",
    "thunder bay": "Ontario", "vaughan": "Ontario", "surrey": "British Columbia",
    "burnaby": "British Columbia", "richmond": "British Columbia",
    "abbotsford": "British Columbia", "kelowna": "British Columbia",
    "kamloops": "British Columbia", "port moody": "British Columbia",
    "coquitlam": "British Columbia", "victoria": "British Columbia",
    "red deer": "Alberta", "lethbridge": "Alberta", "fort mcmurray": "Alberta",
    "medicine hat": "Alberta", "grande prairie": "Alberta", "quebec city": "Quebec",
    "laval": "Quebec", "gatineau": "Quebec", "longueuil": "Quebec",
    "sherbrooke": "Quebec", "saguenay": "Quebec", "levis": "Quebec",
    "trois-rivieres": "Quebec", "saint-hyacinthe": "Quebec", "drummondville": "Quebec",
    "winnipeg": "Manitoba", "brandon": "Manitoba", "saskatoon": "Saskatchewan",
    "regina": "Saskatchewan", "halifax": "Nova Scotia", "dartmouth": "Nova Scotia",
    "sydney": "Nova Scotia", "moncton": "New Brunswick", "saint john": "New Brunswick",
    "fredericton": "New Brunswick", "st. john's": "Newfoundland and Labrador",
    "whitehorse": "Yukon", "yellowknife": "Northwest Territories", "iqaluit": "Nunavut",
}


def infer_province_from_city(city: str | None) -> str | None:
    """
    Heuristic to fill missing province values if the city is a known Canadian city.
    """
    if not city:
        return None
    return _CITY_TO_PROVINCE.get(_strip_accents(city).lower())


# ── Location Inference from Description ─────────────────────────────────────

_PROVINCE_ABBREVS: dict[str, str] = {
    "ON": "Ontario", "BC": "British Columbia", "AB": "Alberta", "QC": "Quebec",
    "MB": "Manitoba", "SK": "Saskatchewan", "NS": "Nova Scotia", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "PE": "Prince Edward Island",
    "NT": "Northwest Territories", "NU": "Nunavut", "YT": "Yukon",
}

# Pre-compiled Regex for description-based location scanning.
_CITIES_SORTED = sorted(_CITY_TO_PROVINCE.keys(), key=len, reverse=True)
_CITY_PROV_RE: list[tuple[str, re.Pattern[str]]] = []

for _ck in _CITIES_SORTED:
    _prov = _CITY_TO_PROVINCE[_ck]
    _CITY_PROV_RE.append((
        _ck,
        re.compile(
            re.escape(_ck.title()) + r",?\s*(?:" + re.escape(_prov) + r"|ON|BC|AB|QC|MB|SK|NS|NB|NL|PE|NT|NU|YT)\b",
            re.IGNORECASE,
        ),
    ))

_PROV_ONLY_RE = re.compile(
    r"(?:,\s*|\s)(" + "|".join(_PROVINCE_ABBREVS.keys()) + r")(?:\s|,|$|\b)",
)


def infer_location_from_description(description: str | None) -> tuple[str | None, str | None]:
    """
    Scan the job description for 'City, Province' patterns to fill missing location data.
    Returns (city, province) or (None, None).
    """
    if not description:
        return None, None

    # Try City + Province co-occurrence
    for city_key, pattern in _CITY_PROV_RE:
        if pattern.search(description):
            return city_key.title(), _CITY_TO_PROVINCE[city_key]

    # Fallback to Province-only indicator
    m = _PROV_ONLY_RE.search(description)
    if m:
        abbrev = m.group(1).upper()
        return None, _PROVINCE_ABBREVS.get(abbrev)

    return None, None


# ── Salary Normalization ────────────────────────────────────────────────────

_HOURS_PER_YEAR = 2080  # Baseline: 40 hrs/week * 52 weeks


def normalize_salary(
    salary_min: float | None,
    salary_max: float | None,
    salary_period: str | None,
) -> tuple[float | None, float | None, str]:
    """
    Normalize salary into a yearly CAD figure.
    Converts hourly rates to annual (x2080).
    Sets values to None if the annual rate exceeds 500k (outlier/data error).
    """
    if salary_period != "HOUR":
        return salary_min, salary_max, salary_period or "YEAR"

    def _to_annual(v: float | None) -> float | None:
        if v is None:
            return None
        annual = round(v * _HOURS_PER_YEAR, 2)
        return annual if annual <= 500_000 else None

    return _to_annual(salary_min), _to_annual(salary_max), "YEAR"
