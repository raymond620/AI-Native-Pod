"""
keyword_planner.py
------------------
Fetches keyword ideas from Google Keyword Planner (via Google Ads API)
and filters/sorts by competition level so you can find the best
low-competition keywords for your landing page.

SETUP
-----
1. Copy .env.example to .env and fill in your credentials.
2. Install dependencies:
       pip install -r requirements.txt
3. Run:
       python keyword_planner.py
   or pass custom seed keywords:
       python keyword_planner.py "help desk software" "ticket management"
"""

import os
import sys
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

load_dotenv()

# ── Credentials (loaded from .env) ──────────────────────────────────────────
DEVELOPER_TOKEN   = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
CLIENT_ID         = os.getenv("GOOGLE_ADS_CLIENT_ID")
CLIENT_SECRET     = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
REFRESH_TOKEN     = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
CUSTOMER_ID       = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "")  # strip dashes

# ── Configuration ────────────────────────────────────────────────────────────
# Default seed keywords — override via CLI args or edit here
DEFAULT_SEEDS = [
    "customer support software",
    "help desk software",
    "support ticket management",
    "customer service platform",
]

# Only return keywords at or below this competition level.
# Options: "LOW", "MEDIUM", "HIGH", "UNSPECIFIED"  — use "MEDIUM" to widen results.
MAX_COMPETITION = "LOW"

# Target location (geo) — 2840 = United States. See:
# https://developers.google.com/google-ads/api/reference/data/geotargets
GEO_TARGET_IDS = [2840]

# Language — 1000 = English. See:
# https://developers.google.com/google-ads/api/reference/data/codes-formats#languages
LANGUAGE_ID = 1000

# Maximum results to display
MAX_RESULTS = 30

# ── Competition rank (for sorting) ───────────────────────────────────────────
COMPETITION_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNSPECIFIED": 3}


def build_client() -> GoogleAdsClient:
    """Build a GoogleAdsClient from environment credentials."""
    config = {
        "developer_token": DEVELOPER_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)


def fetch_keyword_ideas(client: GoogleAdsClient, seed_keywords: list[str]) -> list[dict]:
    """
    Call the KeywordPlanIdeaService and return a list of keyword dicts:
        { text, avg_monthly_searches, competition, competition_index, low_top_bid, high_top_bid }
    """
    service = client.get_service("KeywordPlanIdeaService")
    request = client.get_type("GenerateKeywordIdeasRequest")

    request.customer_id = CUSTOMER_ID
    request.language = f"languageConstants/{LANGUAGE_ID}"
    request.geo_target_constants.extend(
        [f"geoTargetConstants/{gid}" for gid in GEO_TARGET_IDS]
    )
    request.include_adult_keywords = False
    request.keyword_seed.keywords.extend(seed_keywords)

    results = []
    try:
        response = service.generate_keyword_ideas(request=request)
        for idea in response:
            metrics = idea.keyword_idea_metrics
            competition_label = metrics.competition.name  # "LOW" / "MEDIUM" / "HIGH"
            results.append({
                "text": idea.text,
                "avg_monthly_searches": metrics.avg_monthly_searches,
                "competition": competition_label,
                "competition_index": metrics.competition_index,       # 0–100
                "low_top_bid_micros": metrics.low_top_of_page_bid_micros,
                "high_top_bid_micros": metrics.high_top_of_page_bid_micros,
            })
    except GoogleAdsException as ex:
        print(f"\n[Google Ads API Error] Request ID: {ex.request_id}")
        for error in ex.failure.errors:
            print(f"  {error.message}")
        sys.exit(1)

    return results


def filter_and_sort(keywords: list[dict], max_competition: str) -> list[dict]:
    """Keep only keywords at or below max_competition, sorted by monthly searches desc."""
    allowed_ranks = {k for k, v in COMPETITION_RANK.items() if v <= COMPETITION_RANK[max_competition]}
    filtered = [kw for kw in keywords if kw["competition"] in allowed_ranks]
    return sorted(filtered, key=lambda kw: kw["avg_monthly_searches"], reverse=True)


def micros_to_dollars(micros: int) -> str:
    return f"${micros / 1_000_000:.2f}" if micros else "N/A"


def print_results(keywords: list[dict], seed_keywords: list[str]) -> None:
    print("\n" + "=" * 72)
    print("  FlowDesk — Google Keyword Planner Results")
    print(f"  Seeds : {', '.join(seed_keywords)}")
    print(f"  Filter: competition ≤ {MAX_COMPETITION}  |  Top {MAX_RESULTS} by monthly searches")
    print("=" * 72)

    if not keywords:
        print("\n  No keywords found matching your criteria. Try relaxing MAX_COMPETITION.\n")
        return

    header = f"{'Keyword':<42} {'Searches/mo':>12} {'Competition':>13} {'CPC Low':>9} {'CPC High':>9}"
    print(f"\n{header}")
    print("-" * 72)

    for kw in keywords[:MAX_RESULTS]:
        print(
            f"{kw['text']:<42} "
            f"{kw['avg_monthly_searches']:>12,} "
            f"{kw['competition']:>13} "
            f"{micros_to_dollars(kw['low_top_bid_micros']):>9} "
            f"{micros_to_dollars(kw['high_top_bid_micros']):>9}"
        )

    print("-" * 72)
    print(f"\n  {len(keywords)} low-competition keywords found. Showing top {min(len(keywords), MAX_RESULTS)}.\n")


def validate_env() -> None:
    missing = [k for k in ("GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
                            "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
                            "GOOGLE_ADS_CUSTOMER_ID") if not os.getenv(k)]
    if missing:
        print("\n[Error] Missing environment variables:")
        for k in missing:
            print(f"  {k}")
        print("\nCopy .env.example to .env and fill in your Google Ads credentials.\n")
        sys.exit(1)


def main() -> None:
    validate_env()

    seed_keywords = list(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_SEEDS
    print(f"\nFetching keyword ideas for: {seed_keywords} ...")

    client = build_client()
    keywords = fetch_keyword_ideas(client, seed_keywords)
    keywords = filter_and_sort(keywords, MAX_COMPETITION)
    print_results(keywords, seed_keywords)


if __name__ == "__main__":
    main()
