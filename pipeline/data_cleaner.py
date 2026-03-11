"""Data cleaning utilities: HTML stripping, experience extraction, seniority."""
from __future__ import annotations

import re
import unicodedata
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


# ── Accent stripping ──────────────────────────────────────────────────────────

def _strip_accents(text: str) -> str:
    """Remove diacritics: 'Québec' → 'Quebec', 'Montréal' → 'Montreal'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


# ── Province normalisation ────────────────────────────────────────────────────

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
    """Return canonical English province name, stripping accents and expanding abbreviations."""
    if not state:
        return None
    stripped = _strip_accents(state.strip())
    return _PROVINCE_MAP.get(stripped.lower(), stripped)


# ── City normalisation ────────────────────────────────────────────────────────

# None → ambiguous value; caller should try description inference.
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
    """Canonical city name: strip accents, resolve aliases, remove noise suffixes."""
    if not city:
        return None
    stripped = _strip_accents(city.strip())
    key = stripped.lower()
    if key in _CITY_ALIASES:
        return _CITY_ALIASES[key]  # may be None (ambiguous)
    stripped = re.sub(r"\s+region\s*$", "", stripped, flags=re.IGNORECASE).strip()
    return stripped or None


# ── Country normalisation ─────────────────────────────────────────────────────

_COUNTRY_MAP: dict[str, str] = {
    "ca": "Canada",
    "canada": "Canada",
    "anywhere": "Anywhere",
}


def normalize_country(country: str | None) -> str | None:
    """Normalise country: 'CA' → 'Canada', None → 'Anywhere' (remote)."""
    if not country:
        return "Anywhere"
    return _COUNTRY_MAP.get(country.strip().lower(), country.strip())


# ── City → province lookup ────────────────────────────────────────────────────

_CITY_TO_PROVINCE: dict[str, str] = {
    # Ontario
    "toronto": "Ontario", "mississauga": "Ontario", "brampton": "Ontario",
    "markham": "Ontario", "ottawa": "Ontario", "hamilton": "Ontario",
    "london": "Ontario", "kitchener": "Ontario", "waterloo": "Ontario",
    "windsor": "Ontario", "richmond hill": "Ontario", "oakville": "Ontario",
    "burlington": "Ontario", "oshawa": "Ontario", "barrie": "Ontario",
    "kingston": "Ontario", "sudbury": "Ontario", "thunder bay": "Ontario",
    "nepean": "Ontario", "vaughan": "Ontario",
    # British Columbia
    "vancouver": "British Columbia", "surrey": "British Columbia",
    "burnaby": "British Columbia", "richmond": "British Columbia",
    "abbotsford": "British Columbia", "kelowna": "British Columbia",
    "kamloops": "British Columbia", "port moody": "British Columbia",
    "coquitlam": "British Columbia", "fort st. john": "British Columbia",
    "victoria": "British Columbia",
    # Alberta
    "calgary": "Alberta", "edmonton": "Alberta", "red deer": "Alberta",
    "lethbridge": "Alberta", "fort mcmurray": "Alberta",
    "medicine hat": "Alberta", "grande prairie": "Alberta",
    # Quebec
    "montreal": "Quebec", "quebec city": "Quebec", "laval": "Quebec",
    "gatineau": "Quebec", "longueuil": "Quebec", "sherbrooke": "Quebec",
    "saguenay": "Quebec", "levis": "Quebec", "trois-rivieres": "Quebec",
    "saint-hyacinthe": "Quebec", "drummondville": "Quebec",
    # Manitoba
    "winnipeg": "Manitoba", "brandon": "Manitoba",
    # Saskatchewan
    "saskatoon": "Saskatchewan", "regina": "Saskatchewan",
    # Nova Scotia
    "halifax": "Nova Scotia", "dartmouth": "Nova Scotia", "sydney": "Nova Scotia",
    # New Brunswick
    "moncton": "New Brunswick", "saint john": "New Brunswick",
    "fredericton": "New Brunswick",
    # Newfoundland
    "st. john's": "Newfoundland and Labrador",
    "corner brook": "Newfoundland and Labrador",
    # PEI
    "charlottetown": "Prince Edward Island",
    "summerside": "Prince Edward Island",
    # Territories
    "whitehorse": "Yukon",
    "yellowknife": "Northwest Territories",
    "iqaluit": "Nunavut",
}


def infer_province_from_city(city: str | None) -> str | None:
    """Return province for a known Canadian city, or None."""
    if not city:
        return None
    return _CITY_TO_PROVINCE.get(_strip_accents(city).lower())


# ── Location inference from job description ───────────────────────────────────

_PROVINCE_ABBREVS: dict[str, str] = {
    "ON": "Ontario", "BC": "British Columbia", "AB": "Alberta",
    "QC": "Quebec", "MB": "Manitoba", "SK": "Saskatchewan",
    "NS": "Nova Scotia", "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "PE": "Prince Edward Island", "NT": "Northwest Territories",
    "NU": "Nunavut", "YT": "Yukon",
}

# "City, AB" or "City, Alberta" patterns (longest city first to avoid partial matches)
_CITIES_SORTED = sorted(_CITY_TO_PROVINCE.keys(), key=len, reverse=True)

_ABBREV_ALTS: dict[str, list[str]] = {}
for _abbr, _prov in _PROVINCE_ABBREVS.items():
    _ABBREV_ALTS.setdefault(_prov, []).append(_abbr)

_CITY_PROV_RE: list[tuple[str, re.Pattern[str]]] = []
for _ck in _CITIES_SORTED:
    _prov = _CITY_TO_PROVINCE[_ck]
    _abbrs = _ABBREV_ALTS.get(_prov, [])
    _alts = [re.escape(_prov)] + [re.escape(a) for a in _abbrs]
    _CITY_PROV_RE.append((
        _ck,
        re.compile(
            re.escape(_ck.title()) + r",?\s*(?:" + "|".join(_alts) + r")\b",
            re.IGNORECASE,
        ),
    ))

# Province-abbreviation-only: ", ON" or " ON " etc.
_PROV_ONLY_RE = re.compile(
    r"(?:,\s*|\s)(" + "|".join(_PROVINCE_ABBREVS.keys()) + r")(?:\s|,|$|\b)",
)


def infer_location_from_description(
    description: str | None,
) -> tuple[str | None, str | None]:
    """Infer (city, province) from a job description.

    Uses conservative patterns only (City + Province co-occurrence).
    Returns (None, None) when nothing reliable is found.
    """
    if not description:
        return None, None

    # 1. "City, AB" or "City, Alberta" — most reliable
    for city_key, pattern in _CITY_PROV_RE:
        if pattern.search(description):
            province = _CITY_TO_PROVINCE[city_key]
            return city_key.title(), province

    # 2. Province abbreviation alone (",  ON" etc.) — gives province, no city
    m = _PROV_ONLY_RE.search(description)
    if m:
        abbrev = m.group(1).upper()
        province = _PROVINCE_ABBREVS.get(abbrev)
        if province:
            return None, province

    return None, None


# ── Salary normalisation ──────────────────────────────────────────────────────

_HOURS_PER_YEAR = 2080  # 52 weeks × 40 hours


def normalize_salary(
    salary_min: float | None,
    salary_max: float | None,
    salary_period: str | None,
) -> tuple[float | None, float | None, str]:
    """Convert hourly pay to annual equivalent.

    Returns (salary_min, salary_max, period).
    Values are nulled out if the converted annual exceeds 500k (data error).
    """
    if salary_period != "HOUR":
        return salary_min, salary_max, salary_period or "YEAR"

    def _to_annual(v: float | None) -> float | None:
        if v is None:
            return None
        annual = round(v * _HOURS_PER_YEAR, 2)
        return annual if annual <= 500_000 else None

    return _to_annual(salary_min), _to_annual(salary_max), "YEAR"
