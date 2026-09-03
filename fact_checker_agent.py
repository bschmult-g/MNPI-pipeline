"""MPNI Agent (Fact checker).

Central coordinator agent that manages sub-agents as tools:
- SA1: entities_agent
- SA2: trigger_words_agent
- SA3: public_check_agent

The Fact Checker gathers findings across all three dimensions and synthesizes
a unified FactCheckingDossier for the Arbiter Decision Authority.
"""

from __future__ import annotations

from typing import List, Optional
from google.adk.agents import Agent
from config import settings
from schemas import FactCheckingDossier
from sub_agents.entities_agent import create_entities_agent
from sub_agents.trigger_words_agent import create_trigger_words_agent
from sub_agents.public_check_agent import create_public_check_agent

FACT_CHECKER_SYSTEM_PROMPT = """You are the MPNI Fact Checker Agent, the investigative foundation of the Material Non-Public Information compliance system.

YOUR ROLE:
You coordinate three specialized sub-agent tools to extract facts, verify public availability, and assemble a factual dossier:
1. `entities_agent` (SA1): Call this tool to identify corporate entities, stock symbols, and confidential internal project names.
2. `trigger_words_agent` (SA2): Call this tool to screen for high-stakes corporate triggers (M&A, roadmap updates, product releases, earnings surprises).
3. `public_check_agent` (SA3): Call this tool to verify whether the facts exist in public press/SEC filings and detect secrecy markers like "don't share".

EXECUTION PROCEDURE:
Step 1: Invoke `entities_agent` with the input text to extract all corporate and project entities.
Step 2: Invoke `trigger_words_agent` with the input text to locate transaction and roadmap triggers.
Step 3: Invoke `public_check_agent` with the input text and extracted claims to check public availability and secrecy markers.
Step 4: Synthesize the findings into a cohesive, factual `FactCheckingDossier`.

CRITICAL INSTRUCTIONS:
- Do NOT make legal conclusions or determine final culpability; that is the sole purview of the Arbiter.
- Be objective, rigorous, and thorough in documenting what is verified public versus what lacks public confirmation.
- Set `high_risk_signals_present=True` if confidential project codenames, M&A triggers, or secrecy markers ("don't share") are discovered.
"""


def create_fact_checker_agent(
    model: Optional[str] = None,
    entities_agent: Optional[Agent] = None,
    trigger_words_agent: Optional[Agent] = None,
    public_check_agent: Optional[Agent] = None,
) -> Agent:
    """Instantiates the MPNI Fact Checker Agent with sub-agents attached as tools.

    In Google ADK, attaching sub-agents with mode='single_turn' exposes them
    automatically as callable tools in the parent agent's toolkit.
    """
    sa1 = entities_agent or create_entities_agent(model=model)
    sa2 = trigger_words_agent or create_trigger_words_agent(model=model)
    sa3 = public_check_agent or create_public_check_agent(model=model)

    return Agent(
        name="fact_checker_agent",
        description="MPNI Fact Checker that coordinates entities, trigger words, and public check sub-agents.",
        instruction=FACT_CHECKER_SYSTEM_PROMPT,
        model=model or settings.default_model,
        sub_agents=[sa1, sa2, sa3],
        output_schema=FactCheckingDossier,
    )
