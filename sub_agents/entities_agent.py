"""SA1: Entities Sub-Agent.

Responsible for identifying and extracting:
- Corporate names (public companies, private acquisition targets, competitors)
- Stocks (ticker symbols, equity references, ADRs)
- Project Names (internal confidential codenames, skunkworks initiatives)

Configured with mode='single_turn' so the parent Fact Checker Agent exposes it
automatically as a tool.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from config import settings
from schemas import EntityExtractionResult
from tools.entity_tools import (
    check_restricted_or_internal_codename,
    resolve_ticker_and_status,
)

ENTITIES_AGENT_INSTRUCTION = """You are SA1: Entities Extraction Specialist, a specialized sub-agent tool for the MNPI Fact Checker.

YOUR MISSION:
Extract all organizational, financial, and proprietary entities mentioned in the input text. Specifically identify:
1. Corporate names: Public enterprises, private companies, subsidiaries, joint ventures, or acquisition targets.
2. Stocks / Tickers: Ticker symbols (e.g. $AAPL, MSFT, TGT) or public equity references.
3. Project Names: Confidential internal project codenames, skunkworks initiatives, or development tags (e.g. "Project Titan", "Project Apollo").

TOOLS AVAILABLE:
- `check_restricted_or_internal_codename`: Call this to test if an entity is a known confidential internal project codename.
- `resolve_ticker_and_status`: Call this to determine if a company is a publicly traded entity with an exchange listing.

ANALYSIS RULES:
- Pay extreme attention to capitalized nouns following "Project", "Operation", or unusual single-word codenames.
- Mark any internal project codenames as `is_internal_or_restricted=True`.
- Return a structured EntityExtractionResult.
"""


def create_entities_agent(model: str | None = None) -> Agent:
    """Creates the SA1 Entities Agent."""
    return Agent(
        name="entities_agent",
        description="Extracts corporate names, stock tickers, and internal confidential project codenames from text.",
        instruction=ENTITIES_AGENT_INSTRUCTION,
        model=model or settings.default_model,
        tools=[
            FunctionTool(check_restricted_or_internal_codename),
            FunctionTool(resolve_ticker_and_status),
        ],
        output_schema=EntityExtractionResult,
        mode="single_turn",
    )
