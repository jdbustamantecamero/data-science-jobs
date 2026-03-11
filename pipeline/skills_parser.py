"""
Keyword-based skills extraction from job descriptions (Silver Layer).

This module provides high-performance keyword matching for identifying technical
skills within job descriptions. It uses a pre-compiled, case-insensitive regular
expression for efficient scanning.

SCALABILITY NOTE:
For up to ~1,000 skills, a single alternated regex (e.g., r'\b(python|sql|...)\b') 
is highly optimized by the underlying C engine of Python's 're' module. 
If the skill list grows into the thousands, we should migrate this to the 
Aho-Corasick algorithm (using the 'pyahocorasick' library).
"""
from __future__ import annotations

import re

# ── Skill Taxonomy ──────────────────────────────────────────────────────────
# This list defines the universe of skills the pipeline can detect.
# To add a new skill, simply append its lowercase name to this list.
SKILLS: list[str] = [
    # Languages
    "python", "sql", "r", "scala", "java", "julia", "sas", "matlab", "bash",
    # ML / Stats concepts
    "machine learning", "deep learning", "statistics", "nlp",
    "computer vision", "llm", "generative ai", "reinforcement learning",
    "time series", "a/b testing", "feature engineering",
    "transformers", "anomaly detection", "forecasting",
    # ML frameworks & libraries
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost", "lightgbm",
    "hugging face", "langchain",
    # Data / analytics libraries
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly", "dask",
    # Cloud platforms
    "aws", "gcp", "azure", "sagemaker", "databricks",
    # Data warehouses & databases
    "snowflake", "bigquery", "redshift", "postgresql", "mysql",
    "mongodb", "elasticsearch",
    # Orchestration / pipelines
    "spark", "hadoop", "kafka", "airflow", "dbt", "luigi", "prefect", "dagster",
    # MLOps / model serving
    "docker", "kubernetes", "mlflow", "kubeflow", "wandb", "fastapi", "flask",
    # BI / Visualisation
    "tableau", "power bi", "looker", "excel", "qlik",
    # DevOps / systems
    "git", "linux", "terraform",
]

# ── Pre-compiled Scanner ──────────────────────────────────────────────────────
# We compile the regex at the module level to avoid the overhead of re-compiling 
# it for every job description. We use word boundaries (\b) to ensure we match
# 'R' but not the letter 'r' inside 'bread'.
_SKILLS_PATTERN = r"\b(" + "|".join(re.escape(s) for s in SKILLS) + r")\b"
_SKILLS_REGEX = re.compile(_SKILLS_PATTERN, re.IGNORECASE)


def extract_skills(text: str | None) -> list[str]:
    """
    Scan a job description and return a list of detected technical skills.

    Args:
        text: The cleaned job description text (Silver layer).

    Returns:
        A sorted list of unique, lowercase skill names found in the text.
        Returns an empty list if no skills are found or text is None.
    """
    if not text:
        return []
    
    # findall() returns all matches in the text.
    # We use a set comprehension to normalize to lowercase and remove duplicates.
    matches = _SKILLS_REGEX.findall(text)
    unique_matches = {m.lower() for m in matches}
    
    return sorted(list(unique_matches))
