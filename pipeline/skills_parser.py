"""Keyword-based skills extraction from job descriptions."""
from __future__ import annotations

import re

SKILLS: list[str] = [
    # ── Languages ──────────────────────────────────────────────────────────────
    "python", "sql", "r", "scala", "java", "julia", "sas", "matlab", "bash",
    # ── ML / Stats concepts ────────────────────────────────────────────────────
    "machine learning", "deep learning", "statistics", "nlp",
    "computer vision", "llm", "generative ai", "reinforcement learning",
    "time series", "a/b testing", "feature engineering",
    "transformers", "anomaly detection", "forecasting",
    # ── ML frameworks & libraries ─────────────────────────────────────────────
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost", "lightgbm",
    "hugging face", "langchain",
    # ── Data / analytics libraries ────────────────────────────────────────────
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly", "dask",
    # ── Cloud platforms ────────────────────────────────────────────────────────
    "aws", "gcp", "azure", "sagemaker", "databricks",
    # ── Data warehouses & databases ───────────────────────────────────────────
    "snowflake", "bigquery", "redshift", "postgresql", "mysql",
    "mongodb", "elasticsearch",
    # ── Orchestration / pipelines ─────────────────────────────────────────────
    "spark", "hadoop", "kafka", "airflow", "dbt", "luigi", "prefect", "dagster",
    # ── MLOps / model serving ─────────────────────────────────────────────────
    "docker", "kubernetes", "mlflow", "kubeflow", "wandb", "fastapi", "flask",
    # ── BI / Visualisation ────────────────────────────────────────────────────
    "tableau", "power bi", "looker", "excel", "qlik",
    # ── DevOps / systems ──────────────────────────────────────────────────────
    "git", "linux", "terraform",
]

# Pre-compile a single alternated regex for all skills (word-boundary aware, case-insensitive)
_SKILLS_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in SKILLS) + r")\b",
    re.IGNORECASE,
)


def extract_skills(text: str | None) -> list[str]:
    """Return list of unique matched skill keywords found in *text*."""
    if not text:
        return []
    # Use findall with the combined regex, then lower() and unique the results.
    matches = _SKILLS_REGEX.findall(text)
    return sorted(list({m.lower() for m in matches}))
