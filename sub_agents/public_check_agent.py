"""SA3: Public Check Sub-Agent.

Responsible for:
1. Conducting public availability searches (Mosaic Theory fact-check in SEC filings & top-tier wire press).
2. Detecting linguistic secrecy markers (e.g. "don't share", "keep this quiet", "strictly confidential", "for your eyes only").

Configured with mode='single_turn' so the parent Fact Checker Agent exposes it
automatically as a tool.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from config import settings
from schemas import PublicCheckResult
from tools.search_tools import (
    detect_secrecy_markers,
    search_public_press_and_filings,
)

PUBLIC_CHECK_AGENT_INSTRUCTION = """You are SA3: Public Availability & Secrecy Specialist, a specialized sub-agent tool for the MNPI Fact Checker.

YOUR MISSION:
Fact-check whether the claims in the text are already public and whether there are explicit linguistic indicators of confidentiality.

CORE RESPONSIBILITIES:
1. Public Record Fact-Check:
   - Use `search_public_press_and_filings` to query whether the corporate event, product launch, or financial announcement has already appeared in SEC filings, wire services, or verified press.
   - If no public record exists, the information is deemed NON-PUBLIC.

2. Linguistic Secrecy Markers:
   - Use `detect_secrecy_markers` to scan the text for phrases such as "don't share", "dont share", "keep this quiet", "strictly confidential", "internal only", "embargoed", or "between us".
   - The presence of linguistic secrecy markers strongly implies insider provenance and non-public transmission.

3. Mosaic Theory Evaluation:
   - Determine whether the text merely synthesizes widely disseminated public news or introduces novel, unverified internal data points (non-public puzzle pieces).

Return a structured PublicCheckResult.
"""


def create_public_check_agent(model: str | None = None) -> Agent:
    """Creates the SA3 Public Check Agent."""
    return Agent(
        name="public_check_agent",
        description="Verifies public availability in SEC filings/press and scans for secrecy markers like 'don't share'.",
        instruction=PUBLIC_CHECK_AGENT_INSTRUCTION,
        model=model or settings.default_model,
        tools=[
            FunctionTool(search_public_press_and_filings),
            FunctionTool(detect_secrecy_markers),
        ],
        output_schema=PublicCheckResult,
        mode="single_turn",
    )
