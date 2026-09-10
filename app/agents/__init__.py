"""Consolidated Agent Definitions (Fact Checker & Arbiter Decision Authority)."""

from __future__ import annotations

from app.agents.fact_checker import create_fact_checker_agent, FACT_CHECKER_SYSTEM_PROMPT
from app.agents.arbiter import create_arbiter_agent, ARBITER_SYSTEM_PROMPT

__all__ = [
    "create_fact_checker_agent",
    "FACT_CHECKER_SYSTEM_PROMPT",
    "create_arbiter_agent",
    "ARBITER_SYSTEM_PROMPT",
]
