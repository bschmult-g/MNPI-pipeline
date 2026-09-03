"""SA2: Trigger Words Sub-Agent.

Responsible for scanning and classifying high-impact corporate transaction and milestone triggers:
- Merger & Acquisition (buyout, takeover, due diligence, closing date)
- Roadmap (unannounced features, strategic pivots, forward-looking guidance)
- Product Release (launch dates, delays, beta rollouts, cancellations)
- Financial & Executive (earnings surprises, margin compression, restructuring, CEO transition)

Configured with mode='single_turn' so the parent Fact Checker Agent exposes it
automatically as a tool.
"""

from __future__ import annotations

from google.adk.agents import Agent
from config import settings
from schemas import TriggerDetectionResult

TRIGGER_WORDS_AGENT_INSTRUCTION = """You are SA2: Trigger Words Detection Specialist, a specialized sub-agent tool for the MNPI Fact Checker.

YOUR MISSION:
Perform a deep semantic and lexical scan of the text to detect sensitive corporate events and market-moving triggers.

CORE TRIGGER CATEGORIES TO DETECT:
1. Merger & Acquisition (M&A):
   - Keywords: merger, acquisition, acquiring, buyout, takeover, divestiture, LOI, due diligence, closing date, tender offer.
   - Sensitivity: CRITICAL.

2. Roadmap & Forward-Looking Strategy:
   - Keywords: roadmap, unannounced, strategic pivot, feature freeze, next-gen architecture, planned expansion.
   - Sensitivity: HIGH.

3. Product Release & Launch Milestones:
   - Keywords: product release, launch date, GA (general availability), delay, slip, cancellation, embargoed release.
   - Sensitivity: HIGH.

4. Financial / Earnings / Material Events:
   - Keywords: earnings beat, earnings miss, pre-announcement, revenue adjustment, restructuring, layoff, SEC inquiry.
   - Sensitivity: CRITICAL.

5. Executive Transitions:
   - Keywords: CEO resignation, CFO departure, executive shakeup, board vote.
   - Sensitivity: HIGH.

ANALYSIS RULES:
- Extract exact snippets surrounding each detected trigger.
- Determine if M&A (`has_ma_triggers`) or Roadmap/Release (`has_roadmap_or_release_triggers`) are present.
- Calculate the `highest_sensitivity` level across all triggers found.
- Return a structured TriggerDetectionResult.
"""


def create_trigger_words_agent(model: str | None = None) -> Agent:
    """Creates the SA2 Trigger Words Agent."""
    return Agent(
        name="trigger_words_agent",
        description="Scans text for M&A, roadmap, product release, and financial trigger words and assesses sensitivity.",
        instruction=TRIGGER_WORDS_AGENT_INSTRUCTION,
        model=model or settings.default_model,
        output_schema=TriggerDetectionResult,
        mode="single_turn",
    )
