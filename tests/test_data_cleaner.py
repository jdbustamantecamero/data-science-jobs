"""Tests for data_cleaner module."""
from pipeline.data_cleaner import (
    clean_description,
    classify_seniority,
    extract_years_experience,
)


# --- clean_description ---

def test_strips_html_tags():
    assert clean_description("<p>We need <b>Python</b> skills.</p>") == "We need Python skills."


def test_collapses_whitespace():
    assert clean_description("hello   \n\n  world") == "hello world"


def test_none_returns_none():
    assert clean_description(None) is None


def test_empty_returns_none():
    assert clean_description("") is None


# --- extract_years_experience ---

def test_basic_years():
    assert extract_years_experience("Requires 3+ years of experience.") == 3


def test_range_returns_minimum():
    assert extract_years_experience("3-5 years of experience required.") == 3


def test_minimum_of():
    assert extract_years_experience("Minimum of 4 years in data science.") == 4


def test_at_least():
    assert extract_years_experience("At least 2 years of work experience.") == 2


def test_no_match_returns_none():
    assert extract_years_experience("No experience required.") is None


def test_none_returns_none():
    assert extract_years_experience(None) is None


# --- classify_seniority ---

def test_senior_from_title():
    assert classify_seniority("Senior Data Scientist", None) == "Senior"


def test_junior_from_title():
    assert classify_seniority("Junior Data Analyst", None) == "Junior"


def test_intern_from_title():
    assert classify_seniority("Data Science Internship", None) == "Intern"


def test_lead_from_title():
    assert classify_seniority("Lead Data Scientist", None) == "Lead"


def test_principal_from_title():
    assert classify_seniority("Principal Data Scientist", None) == "Lead"


def test_director_from_title():
    assert classify_seniority("Director of Data Science", None) == "Director+"


def test_title_wins_over_years():
    # Title says Senior, years say Junior — title wins
    assert classify_seniority("Senior Data Scientist", 1) == "Senior"


def test_years_used_when_no_title_keyword():
    assert classify_seniority("Data Scientist", 1) == "Junior"
    assert classify_seniority("Data Scientist", 4) == "Mid"
    assert classify_seniority("Data Scientist", 7) == "Senior"
    assert classify_seniority("Data Scientist", 12) == "Lead"


def test_default_mid_when_no_signals():
    assert classify_seniority("Data Scientist", None) == "Mid"
    assert classify_seniority(None, None) == "Mid"
