"""Configuration and settings for MNPI Agent System.

Provides configurable settings for:
- Model selection (Gemini 2.5 Flash, Gemini 1.5 Pro)
- Authentication / Environment resolution (API Key vs Vertex AI)
- Compliance trigger catalogs, known codenames, and public verification sources
"""

from __future__ import annotations

import os
from typing import List, Set
from pydantic import BaseModel, Field


class AgentSettings(BaseModel):
    """Global configuration settings for MNPI compliance agents."""

    # Default model
    default_model: str = Field(
        default=os.getenv("MNPI_DEFAULT_MODEL", "gemini-2.5-flash"),
        description="Gemini model identifier for ADK agents"
    )

    arbiter_model: str = Field(
        default=os.getenv("MNPI_ARBITER_MODEL", "gemini-2.5-flash"),
        description="Model identifier for Arbiter (can use a higher reasoning model like pro)"
    )

    # Known internal project codenames (users can customize/extend this)
    known_project_codenames: Set[str] = Field(
        default_factory=lambda: {
            "project titan",
            "project apollo",
            "project falcon",
            "project phoenix",
            "project vanguard",
            "project blue",
            "project horizon",
            "project eclipse",
        },
        description="Set of known sensitive internal project codenames"
    )

    # Core corporate trigger words
    ma_triggers: List[str] = Field(
        default_factory=lambda: [
            "merger", "acquisition", "acquire", "takeover", "buyout", "divestiture",
            "spinoff", "tender offer", "due diligence", "loi", "term sheet", "closing date"
        ]
    )

    roadmap_release_triggers: List[str] = Field(
        default_factory=lambda: [
            "roadmap", "product release", "launch date", "delay", "slip", "unannounced",
            "beta rollout", "general availability", "deprecation", "feature freeze"
        ]
    )

    financial_triggers: List[str] = Field(
        default_factory=lambda: [
            "earnings beat", "earnings miss", "guidance update", "revenue revision",
            "margin compression", "q3 numbers", "q4 numbers", "pre-announcement",
            "restructuring", "headcount reduction", "layoff"
        ]
    )

    # Secrecy & duty linguistic markers
    secrecy_markers: List[str] = Field(
        default_factory=lambda: [
            "don't share", "dont share", "do not share", "keep this quiet", "keep quiet",
            "strictly confidential", "for your eyes only", "internal only", "embargoed",
            "privileged", "off the record", "between us", "do not forward", "not public yet"
        ]
    )

    # Authorized top-tier public sources for Mosaic / public check
    trusted_public_sources: List[str] = Field(
        default_factory=lambda: [
            "sec.gov (EDGAR)",
            "PR Newswire",
            "Business Wire",
            "GlobeNewswire",
            "Bloomberg News",
            "Reuters",
            "Wall Street Journal",
            "Financial Times",
            "Associated Press",
            "Official Corporate Press Release / Investor Relations Portal"
        ]
    )


# Singleton instance
settings = AgentSettings()
