import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return val


SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_SERVICE_KEY: str = _require("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")

JSEARCH_API_KEY: str = _require("JSEARCH_API_KEY")
ADZUNA_APP_ID: str = _require("ADZUNA_APP_ID")
ADZUNA_APP_KEY: str = _require("ADZUNA_APP_KEY")
THEIRSTACK_API_KEY: str = _require("THEIRSTACK_API_KEY")
SERPAPI_API_KEY: str = _require("SERPAPI_API_KEY")

JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_BASE_URL = "https://jsearch.p.rapidapi.com"

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"

THEIRSTACK_BASE_URL = "https://api.theirstack.com/v1"

SERPAPI_BASE_URL = "https://serpapi.com/search"
SERPAPI_ACCOUNT_URL = "https://serpapi.com/account"
