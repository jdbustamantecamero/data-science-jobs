"""Keyword-based skills extraction from job descriptions."""
from __future__ import annotations

import re

SKILLS: list[str] = [
    "python", "sql", "r", "scala", "java", "julia",
    "spark", "hadoop", "kafka", "airflow", "dbt", "luigi",
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost", "lightgbm",
    "pandas", "numpy", "matplotlib", "seaborn", "plotly",
    "aws", "gcp", "azure", "databricks", "snowflake", "bigquery", "redshift",
    "docker", "kubernetes", "mlflow", "kubeflow",
    "tableau", "power bi", "looker",
    "git", "linux",
    "statistics", "machine learning", "deep learning", "nlp",
    "computer vision", "llm", "generative ai",
]

# Pre-compile patterns (word-boundary aware, case-insensitive)
_PATTERNS = [(skill, re.compile(r"\b" + re.escape(skill) + r"\b", re.IGNORECASE)) for skill in SKILLS]


def extract_skills(text: str | None) -> list[str]:
    """Return list of matched skill keywords found in *text*."""
    if not text:
        return []
    return [skill for skill, pattern in _PATTERNS if pattern.search(text)]
