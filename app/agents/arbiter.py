"""MPNI Agent Arbiter (Decision Authority).

Instructional decision-making agent that evaluates the original text and the
factual dossier assembled by the Fact Checker Agent against the 4 Assessment Criteria:

1. Materiality Test:
   "If this information became public right now, would a reasonable investor trade on it
    or would it shift market valuation?"

2. Public Availability Test (Mosaic Check):
   "Did Agent 1 confirm this is verified in top-tier public press/filings? If no, it is Non-Public."

3. Source & Duty Test:
   "Did this information originate from an internal employee, corporate insider, or confidential call?"

4. Actionability / Harm Test:
   "Does exposing this chunk allow an unauthorized party to infer a confidential corporate
    strategy or financial outcome?"
"""

from __future__ import annotations

from typing import Optional
from google.adk.agents import Agent

try:
    from app.config import settings
    from app.schemas import ArbiterVerdict
    from app.tools.audit_tools import record_document_alignment_in_bigquery
except ImportError:
    from config import settings
    from schemas import ArbiterVerdict
    from tools.audit_tools import record_document_alignment_in_bigquery

ARBITER_SYSTEM_PROMPT = """You are the MPNI Agent Arbiter, the definitive Decision Authority for Material Non-Public Information compliance.

YOUR ROLE:
You receive communications or text chunks along with the factual findings from the MPNI Fact Checker Agent.
Your responsibility is INSTRUCTIONAL and JUDICIAL. You strictly evaluate the evidence against the 4 mandatory Agent Assessment Criteria to render a legally grounded, defensible verdict.
You can call `record_document_alignment_in_bigquery` to record the document name and arbitration results into the BigQuery compliance audit table.

================================================================================
AGENT ASSESSMENT CRITERIA (THE 4 TESTS):
================================================================================

1. MATERIALITY TEST:
   - Question: If this information became public right now, would a reasonable investor trade on it or would it shift market valuation?
   - Legal Standard: TSC Industries v. Northway / Basic Inc. v. Levinson. Is there a substantial likelihood that a reasonable investor would consider it important in deciding whether to buy, sell, or hold securities?
   - Factors: Major M&A transactions, unannounced product launch/slip dates, preliminary earnings beats/misses, significant executive departures, or secret codename milestones.
   - Outcome: Score between 0.0 (immaterial chatter) and 1.0 (decisive market-moving catalyst).

2. PUBLIC AVAILABILITY TEST (MOSAIC CHECK):
   - Question: Did Agent 1 (Fact Checker) confirm this is verified in top-tier public press or SEC filings? If no, it is Non-Public.
   - Legal Standard: Mosaic Theory. Public information must be broadly disseminated through wire services (Bloomberg, Reuters, PR Newswire) or SEC filings (10-K, 8-K). Rumors, private chatter, or unconfirmed leaks are Non-Public.
   - Outcome: If Agent 1 found NO public verification for a material fact, classify as NON-PUBLIC.

3. SOURCE & DUTY TEST:
   - Question: Did this information originate from an internal employee, corporate insider, or confidential call?
   - Legal Standard: Chiarella v. United States / Dirks v. SEC / Salman v. United States. Did the source owe a duty of trust and confidentiality (e.g. employee NDA, consultant, insider call)?
   - Indicators: Explicit linguistic secrecy markers ("don't share", "keep this quiet", "strictly confidential", "internal only"), reference to internal meetings, or insider status.
   - Outcome: Score between 0.0 (public third-party commentator) and 1.0 (direct breach of insider duty).

4. ACTIONABILITY / HARM TEST:
   - Question: Does exposing this chunk allow an unauthorized party to infer a confidential corporate strategy or financial outcome?
   - Legal Standard: Misappropriation theory and competitive harm. Does the chunk enable front-running, premature trading, or damage corporate negotiation positions?
   - Outcome: Score between 0.0 (benign, non-actionable) and 1.0 (immediate actionable alpha or corporate damage).

================================================================================
VERDICT DETERMINATION MATRIX:
================================================================================
- MNPI_CONFIRMED: Materiality Test >= 0.7 AND Public Availability = Non-Public AND (Source/Duty >= 0.6 OR Actionability >= 0.6).
  -> Risk Level: CRITICAL. Recommended Action: BLOCK_COMMUNICATION. Provide redacted_text.

- POTENTIAL_MNPI: Materiality Test >= 0.5 AND Public Availability = Non-Public (or partial mosaic piece with ambiguous source).
  -> Risk Level: HIGH. Recommended Action: ESCALATE_TO_COMPLIANCE.

- PUBLIC_NON_MATERIAL: Information is either confirmed public OR lacks materiality (routine chatter, trivial commentary).
  -> Risk Level: LOW. Recommended Action: APPROVE_RELEASE.

- CLEARED: Clean text with no entities of concern, no sensitive triggers, verified public.
  -> Risk Level: LOW. Recommended Action: APPROVE_RELEASE.

OUTPUT REQUIREMENTS:
Render a complete ArbiterVerdict adhering to the defined schema. Detail your analysis for each of the 4 tests thoroughly.
"""


def create_arbiter_agent(model: Optional[str] = None) -> Agent:
    """Instantiates the MPNI Agent Arbiter (Decision Authority)."""
    return Agent(
        name="arbiter_agent",
        description="MPNI Decision Authority that applies the 4 Assessment Criteria to determine MNPI status.",
        instruction=ARBITER_SYSTEM_PROMPT,
        model=model or settings.arbiter_model,
        tools=[record_document_alignment_in_bigquery],
        output_schema=ArbiterVerdict,
    )


import logging
import time
from typing import Any, Dict

logger = logging.getLogger("mnpi_decision_authority_runtime")


class MNPIDecisionAuthorityRuntime:
    """Vertex AI Reasoning Engine Runtime for Agent 2 (MNPI Decision Authority)."""

    agent_framework: str = "google-adk"

    def __init__(
        self,
        project_id: str = "green-carrier-500109-k2",
        location: str = "us",
        model: str = "gemini-3.8-flash",
    ):
        self.project_id = project_id
        self.location = location
        self.model = model
        self.agent_framework = "google-adk"

    def set_up(self):
        """Initializes runtime environment upon Vertex AI container startup."""
        logger.info(
            f"Initialized MNPIDecisionAuthorityRuntime for project={self.project_id}, "
            f"location={self.location}, model={self.model}"
        )

    def query(
        self,
        text: Optional[str] = None,
        dossier: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        input: Optional[str] = None,
        document_name: str = "compliance_document",
        channel: str = "api",
        log_to_bq: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        document_text = text or prompt or input or kwargs.get("message") or kwargs.get("content") or ""
        try:
            from app.schemas import FactCheckingDossier
            from app.workflow import get_genai_client, run_live_arbiter, run_offline_arbiter
            from app.audit_logger import log_document_alignment_to_bq
        except ImportError:
            from schemas import FactCheckingDossier
            from workflow import get_genai_client, run_live_arbiter, run_offline_arbiter
            from audit_logger import log_document_alignment_to_bq

        if dossier is None:
            logger.info("No dossier provided to Agent 2; invoking Agent 1 (MNPIFactCheckerRuntime) first...")
            try:
                from app.agents.fact_checker import MNPIFactCheckerRuntime
            except ImportError:
                from agents.fact_checker.runtime import MNPIFactCheckerRuntime
            fc_agent = MNPIFactCheckerRuntime(
                project_id=self.project_id,
                location=self.location,
                model=self.model,
            )
            dossier = fc_agent.query(text=document_text)

        start_t = time.perf_counter()
        parsed_dossier = FactCheckingDossier.model_validate(dossier)

        client = get_genai_client()
        if client:
            try:
                verdict = run_live_arbiter(client, document_text, parsed_dossier)
            except Exception as err:
                logger.warning(f"Live Arbiter execution notice ({err}); using deterministic arbiter fallback.")
                verdict = run_offline_arbiter(parsed_dossier)
        else:
            verdict = run_offline_arbiter(parsed_dossier)

        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

        if log_to_bq:
            try:
                log_document_alignment_to_bq(
                    document_name=document_name,
                    verdict=verdict,
                    channel=channel,
                    latency_ms=latency_ms,
                    raw_text=document_text,
                    dossier=parsed_dossier,
                )
            except Exception as e:
                logger.warning(f"BigQuery audit log notice: {e}")

        return verdict.model_dump()

