"""
One-off data quality exploration script.

Run with:
    python -m pipeline.explore_data_quality

Connects to the live DB and prints a diagnostic report on all fields
that are candidates for normalization in data_cleaner.py.
"""
from __future__ import annotations

from collections import Counter

from pipeline.config import SUPABASE_SERVICE_KEY, SUPABASE_URL
from supabase import create_client


def _header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _counter_report(label: str, counter: Counter, top_n: int = 30) -> None:
    print(f"\n--- {label} (top {top_n}) ---")
    for value, count in counter.most_common(top_n):
        print(f"  {count:>5}  {repr(value)}")


def main() -> None:
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Fetch all jobs — only the fields we care about for quality checks
    resp = (
        client.table("job_postings")
        .select(
            "job_id, location_state, location_city, location_country, "
            "title, seniority, salary_currency, salary_min, salary_max, "
            "skills_tags, years_experience_min"
        )
        .execute()
    )
    rows = resp.data
    total = len(rows)

    _header(f"DATA QUALITY REPORT  ({total} total rows)")

    # ── 1. location_state ───────────────────────────────────────────────────
    states = Counter(r["location_state"] for r in rows)
    _counter_report("location_state — all unique values", states, top_n=50)

    null_state = sum(1 for r in rows if not r["location_state"])
    print(f"\n  NULL / empty location_state: {null_state} ({100*null_state/total:.1f}%)")

    # ── 2. location_city ────────────────────────────────────────────────────
    cities = Counter(r["location_city"] for r in rows)
    _counter_report("location_city — top values", cities, top_n=40)

    null_city = sum(1 for r in rows if not r["location_city"])
    print(f"\n  NULL / empty location_city: {null_city} ({100*null_city/total:.1f}%)")

    # ── 3. location_country ─────────────────────────────────────────────────
    countries = Counter(r["location_country"] for r in rows)
    _counter_report("location_country — all unique values", countries, top_n=20)

    # ── 4. seniority ────────────────────────────────────────────────────────
    seniority = Counter(r["seniority"] for r in rows)
    _counter_report("seniority — all values", seniority, top_n=20)

    # ── 5. salary_currency ──────────────────────────────────────────────────
    currencies = Counter(r["salary_currency"] for r in rows)
    _counter_report("salary_currency — all values", currencies, top_n=20)

    # ── 6. salary completeness ──────────────────────────────────────────────
    _header("Salary completeness")
    has_min = sum(1 for r in rows if r["salary_min"] is not None)
    has_max = sum(1 for r in rows if r["salary_max"] is not None)
    print(f"  has salary_min:  {has_min}/{total} ({100*has_min/total:.1f}%)")
    print(f"  has salary_max:  {has_max}/{total} ({100*has_max/total:.1f}%)")

    # Sanity check: any salary_min > salary_max?
    flipped = [r for r in rows if r["salary_min"] and r["salary_max"] and r["salary_min"] > r["salary_max"]]
    print(f"  salary_min > salary_max (bad): {len(flipped)}")

    # Very low salaries that look like hourly rates (< 200)
    low_salary = [r for r in rows if r["salary_min"] and r["salary_min"] < 200]
    print(f"  salary_min < 200 (possible hourly rates): {len(low_salary)}")
    for r in low_salary[:10]:
        print(f"    job_id={r['job_id']}  min={r['salary_min']}  max={r['salary_max']}  currency={r['salary_currency']}")

    # ── 7. source distribution (inferred from job_id prefix) ────────────────
    def _source(job_id: str) -> str:
        for prefix in ("adzuna_", "theirstack_", "serpapi_"):
            if job_id.startswith(prefix):
                return prefix.rstrip("_")
        return "jsearch"

    sources = Counter(_source(r["job_id"]) for r in rows)
    _counter_report("source — distribution (inferred from job_id prefix)", sources, top_n=10)

    # ── 8. title spot-check — unusual characters / casing ───────────────────
    _header("Title spot-check")
    import unicodedata
    weird_titles = [
        r["title"] for r in rows
        if r["title"] and any(unicodedata.category(c).startswith("S") or ord(c) > 127 for c in r["title"])
    ]
    print(f"\n  Titles with non-ASCII or symbol characters: {len(weird_titles)}")
    for t in weird_titles[:20]:
        print(f"    {repr(t)}")

    # ── 9. years_experience_min distribution ────────────────────────────────
    years = Counter(r["years_experience_min"] for r in rows)
    _counter_report("years_experience_min — all values", years, top_n=20)

    null_years = sum(1 for r in rows if r["years_experience_min"] is None)
    print(f"\n  NULL years_experience_min: {null_years} ({100*null_years/total:.1f}%)")

    # ── 10. skills_tags completeness ────────────────────────────────────────
    _header("skills_tags completeness")
    no_skills = sum(1 for r in rows if not r["skills_tags"])
    print(f"  Jobs with no skills extracted: {no_skills}/{total} ({100*no_skills/total:.1f}%)")

    # Most common individual skills
    from collections import Counter as C
    skill_counter: Counter = C()
    for r in rows:
        for skill in (r["skills_tags"] or []):
            skill_counter[skill] += 1
    _counter_report("Top individual skills", skill_counter, top_n=30)


if __name__ == "__main__":
    main()
