"""Entity lookup and ticker resolution tools for SA1 (Entities).

Provides capabilities to:
1. Identify known internal project codenames (e.g. Project Titan, Project Apollo).
2. Look up stock ticker symbols and exchange status.
3. Check restricted compliance watchlists.
"""

from __future__ import annotations

from typing import Any, Dict
from config import settings


# Sample compliance watchlist and ticker database
TICKER_DIRECTORY = {
    "apple": {"ticker": "AAPL", "exchange": "NASDAQ", "is_public": True},
    "microsoft": {"ticker": "MSFT", "exchange": "NASDAQ", "is_public": True},
    "target": {"ticker": "TGT", "exchange": "NYSE", "is_public": True},
    "google": {"ticker": "GOOGL", "exchange": "NASDAQ", "is_public": True},
    "alphabet": {"ticker": "GOOGL", "exchange": "NASDAQ", "is_public": True},
    "amazon": {"ticker": "AMZN", "exchange": "NASDAQ", "is_public": True},
    "meta": {"ticker": "META", "exchange": "NASDAQ", "is_public": True},
    "nvidia": {"ticker": "NVDA", "exchange": "NASDAQ", "is_public": True},
    "tesla": {"ticker": "TSLA", "exchange": "NASDAQ", "is_public": True},
}


def check_restricted_or_internal_codename(name: str) -> Dict[str, Any]:
    """Checks if a name corresponds to an internal confidential project codename or restricted list.

    Args:
        name: Name of the project, entity, or codename to check (e.g. 'Project Titan', 'Project Apollo').

    Returns:
        Dictionary indicating whether the name is an internal restricted project.
    """
    clean_name = name.strip().lower()
    is_internal = clean_name in settings.known_project_codenames

    return {
        "entity_query": name,
        "is_internal_codename": is_internal,
        "classification": "CONFIDENTIAL_INTERNAL_PROJECT" if is_internal else "STANDARD_ENTITY",
        "guidance": (
            "CRITICAL: This matches an internal confidential project codename. High probability of MNPI."
            if is_internal
            else "Entity not found on internal secret codename registry."
        ),
    }


def resolve_ticker_and_status(entity_name: str) -> Dict[str, Any]:
    """Resolves a corporate name to its stock ticker and public trading exchange.

    Args:
        entity_name: Name of the company or potential ticker symbol.

    Returns:
        Dictionary with ticker symbol, exchange, and public listing confirmation.
    """
    clean_name = entity_name.strip().lower().replace("$", "")

    # Direct ticker check
    for comp, info in TICKER_DIRECTORY.items():
        if clean_name == comp or clean_name == info["ticker"].lower():
            return {
                "matched_name": comp.title(),
                "ticker": info["ticker"],
                "exchange": info["exchange"],
                "is_public_equity": True,
                "notes": f"Public equity traded on {info['exchange']}.",
            }

    return {
        "matched_name": entity_name,
        "ticker": None,
        "exchange": None,
        "is_public_equity": False,
        "notes": "Entity may be a private enterprise, subsidiary, unlisted target, or project codename.",
    }
