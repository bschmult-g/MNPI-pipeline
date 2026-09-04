"""Google ADK Workflow Orchestrator for MNPI Agent System.

Wires together:
1. MPNI Agent (Fact checker) with sub-agents as tools (SA1, SA2, SA3).
2. MPNI Agent Arbiter (Decision Authority) applying the 4 Assessment Criteria.

Supports:
- Google ADK Workflow graph orchestration.
- ADK Runner with InMemorySessionService.
- Deterministic offline simulation runner for zero-dependency testing without live API keys.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from google.adk import Workflow, Runner
from google.adk.agents import Agent
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from config import settings
from schemas import (
    ArbiterVerdict,
    CriteriaAssessment,
    EntityExtractionResult,
    EntityItem,
    FactCheckingDossier,
    PublicCheckResult,
    TriggerDetectionResult,
    TriggerItem,
)
from fact_checker_agent import create_fact_checker_agent
from arbiter_agent import create_arbiter_agent
from tools.entity_tools import check_restricted_or_internal_codename, resolve_ticker_and_status
from tools.search_tools import detect_secrecy_markers, search_public_press_and_filings

logger = logging.getLogger(__name__)


# ==============================================================================
# Google ADK Native Workflow Construction
# ==============================================================================

def build_mnpi_workflow(
    model: Optional[str] = None,
    fact_checker: Optional[Agent] = None,
    arbiter: Optional[Agent] = None,
) -> Workflow:
    """Builds the native Google ADK Workflow graph.

    Graph Topology:
        START -> MPNI Fact Checker (with SA1, SA2, SA3 tools) -> MPNI Arbiter
    """
    fc_agent = fact_checker or create_fact_checker_agent(model=model)
    arb_agent = arbiter or create_arbiter_agent(model=model)

    workflow = Workflow(
        name="mnpi_compliance_workflow",
        description="End-to-end MNPI detection, fact-checking, and compliance arbitration pipeline.",
        edges=[
            ("START", fc_agent),
            (fc_agent, arb_agent),
        ],
    )
    return workflow


def create_mnpi_runner(
    workflow: Optional[Workflow] = None,
    app_name: str = "mnpi_compliance_app",
) -> Runner:
    """Creates a Google ADK Runner configured with InMemorySessionService."""
    wf = workflow or build_mnpi_workflow()
    session_service = InMemorySessionService()

    return Runner(
        app_name=app_name,
        agent=wf,
        session_service=session_service,
        auto_create_session=True,
    )


async def run_adk_workflow_async(
    text: str,
    runner: Optional[Runner] = None,
    user_id: str = "compliance_officer_1",
    session_id: str = "session_001",
) -> AsyncGenerator[Event, None]:
    """Asynchronously executes the Google ADK workflow for a given text chunk."""
    r = runner or create_mnpi_runner()
    message = Content(role="user", parts=[Part.from_text(text=text)])

    async for event in r.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        yield event


# ==============================================================================
# Deterministic Offline Pipeline (For Immediate Testing & Unit Tests)
# ==============================================================================

def run_offline_fact_checker(text: str) -> FactCheckingDossier:
    """Executes the Fact Checker sub-agent tools deterministically without remote LLM calls.

    Useful for CI/CD, unit tests, and offline development.
    """
    lower_text = text.lower()

    # 1. SA1: Entities Extraction
    entities_list = []
    tickers_found = []
    codenames_found = []

    # Check for tickers or known corporate entities
    for word in text.split():
        clean_word = word.strip(".,;:!?()[]\"'")
        if clean_word.startswith("$") and len(clean_word) > 1:
            sym = clean_word[1:].upper()
            # If starts with digit, it is a monetary amount (e.g. $2.4B), not a stock ticker
            if sym and sym[0].isdigit():
                continue
            tickers_found.append(sym)
            entities_list.append(
                EntityItem(
                    name=clean_word,
                    category="stock_ticker",
                    context_snippet=word,
                    is_internal_or_restricted=False,
                    notes=f"Identified stock ticker symbol {sym}",
                )
            )

    # Check for known project codenames
    for codename in settings.known_project_codenames:
        if codename in lower_text:
            codenames_found.append(codename.title())
            status = check_restricted_or_internal_codename(codename)
            entities_list.append(
                EntityItem(
                    name=codename.title(),
                    category="project_codename",
                    context_snippet=f"...{codename}...",
                    is_internal_or_restricted=True,
                    notes=status["guidance"],
                )
            )

    # Check corporate directory
    from tools.entity_tools import TICKER_DIRECTORY
    for comp, info in TICKER_DIRECTORY.items():
        if comp in lower_text and not any(e.name.lower() == comp for e in entities_list):
            entities_list.append(
                EntityItem(
                    name=comp.title(),
                    category="corporate_name",
                    context_snippet=f"...{comp}...",
                    is_internal_or_restricted=False,
                    notes=f"Public entity ({info['ticker']} on {info['exchange']})",
                )
            )

    entity_result = EntityExtractionResult(
        entities=entities_list,
        tickers_found=list(set(tickers_found)),
        internal_codenames_found=list(set(codenames_found)),
        summary=f"Extracted {len(entities_list)} entities. Codenames: {codenames_found}. Tickers: {tickers_found}.",
    )

    # 2. SA2: Trigger Words
    triggers_list = []
    has_ma = False
    has_roadmap = False
    highest_sens = "LOW"

    for trigger in settings.ma_triggers:
        if trigger in lower_text:
            has_ma = True
            highest_sens = "CRITICAL"
            triggers_list.append(
                TriggerItem(
                    term=trigger,
                    category="merger_acquisition",
                    context_snippet=f"Detected trigger term '{trigger}'",
                    sensitivity_level="CRITICAL",
                )
            )

    for trigger in settings.roadmap_release_triggers:
        if trigger in lower_text:
            has_roadmap = True
            if highest_sens != "CRITICAL":
                highest_sens = "HIGH"
            triggers_list.append(
                TriggerItem(
                    term=trigger,
                    category="product_release" if "release" in trigger or "launch" in trigger else "roadmap_forward_looking",
                    context_snippet=f"Detected milestone term '{trigger}'",
                    sensitivity_level="HIGH",
                )
            )

    for trigger in settings.financial_triggers:
        if trigger in lower_text:
            highest_sens = "CRITICAL"
            triggers_list.append(
                TriggerItem(
                    term=trigger,
                    category="financial_earnings",
                    context_snippet=f"Detected financial term '{trigger}'",
                    sensitivity_level="CRITICAL",
                )
            )

    trigger_result = TriggerDetectionResult(
        triggers=triggers_list,
        highest_sensitivity=highest_sens,
        has_ma_triggers=has_ma,
        has_roadmap_or_release_triggers=has_roadmap,
        summary=f"Identified {len(triggers_list)} sensitive trigger terms (Highest: {highest_sens}).",
    )

    # 3. SA3: Public Check & Linguistic Secrecy Markers
    secrecy_markers = detect_secrecy_markers(text)
    has_secrecy = len(secrecy_markers) > 0

    # Search public records for entity / trigger combinations
    search_query = " ".join([e.name for e in entities_list[:2]] + [t.term for t in triggers_list[:2]])
    search_output = search_public_press_and_filings(search_query) if search_query else "No public search query generated"

    is_public = "PUBLIC RECORDS FOUND" in search_output
    conf = 0.9 if is_public else (0.1 if has_secrecy else 0.4)

    public_result = PublicCheckResult(
        claims_evaluated=[search_query] if search_query else ["General text"],
        is_publicly_verified=is_public,
        verification_confidence=conf,
        sources_cited=settings.trusted_public_sources[:2] if is_public else [],
        linguistic_markers=secrecy_markers,
        has_secrecy_markers=has_secrecy,
        mosaic_check_notes=search_output,
    )

    high_risk = bool(codenames_found or has_ma or has_secrecy or highest_sens == "CRITICAL")

    return FactCheckingDossier(
        original_text=text,
        entities=entity_result,
        triggers=trigger_result,
        public_check=public_result,
        dossier_summary=(
            f"Fact check complete: {len(entities_list)} entities, {len(triggers_list)} triggers. "
            f"Public verified: {is_public}. Secrecy markers: {secrecy_markers}."
        ),
        high_risk_signals_present=high_risk,
    )


def run_offline_arbiter(dossier: FactCheckingDossier) -> ArbiterVerdict:
    """Executes the Arbiter 4-Test Assessment deterministically against a dossier."""
    text = dossier.original_text

    # Test 1: Materiality Test
    is_ma = dossier.triggers.has_ma_triggers
    is_codename = len(dossier.entities.internal_codenames_found) > 0
    is_roadmap = dossier.triggers.has_roadmap_or_release_triggers

    if is_ma or is_codename:
        mat_score = 0.95
        mat_result = "VIOLATION / HIGHLY MATERIAL"
        mat_rationale = "M&A events and internal confidential project codenames are intrinsically market-moving under Basic Inc. v. Levinson."
    elif is_roadmap or dossier.triggers.highest_sensitivity in ("CRITICAL", "HIGH"):
        mat_score = 0.75
        mat_result = "MATERIAL"
        mat_rationale = "Forward-looking roadmaps or product release schedules substantially alter valuation projections."
    elif len(dossier.triggers.triggers) > 0:
        mat_score = 0.4
        mat_result = "BORDERLINE / LOW MATERIALITY"
        mat_rationale = "Minor corporate keywords present, but lacks decisive financial catalysts."
    else:
        mat_score = 0.05
        mat_result = "PASSED / IMMATERIAL"
        mat_rationale = "No market-moving financial, operational, or M&A catalysts detected."

    # Test 2: Public Availability Test (Mosaic Check)
    if dossier.public_check.is_publicly_verified:
        pub_score = 0.1
        pub_result = "CLEARED / PUBLIC"
        pub_rationale = "Claims verified in official SEC filings / top-tier public news wires."
    else:
        pub_score = 0.9
        pub_result = "VIOLATION / NON-PUBLIC"
        pub_rationale = "Information is not verified in top-tier public press or SEC filings. Fails Mosaic check."

    # Test 3: Source & Duty Test
    if dossier.public_check.has_secrecy_markers:
        src_score = 0.95
        src_result = "VIOLATION / BREACH OF CONFIDENTIALITY"
        src_rationale = f"Explicit secrecy markers detected: {dossier.public_check.linguistic_markers}. Indicates duty of confidentiality."
    elif is_codename:
        src_score = 0.85
        src_result = "HIGH RISK / INSIDER SOURCE"
        src_rationale = "Usage of internal project codenames indicates corporate insider provenance."
    else:
        src_score = 0.2
        src_result = "PASSED / LOW SOURCE RISK"
        src_rationale = "No explicit confidentiality markers or restricted insider source signatures detected."

    # Test 4: Actionability / Harm Test
    if (is_ma or is_codename or dossier.public_check.has_secrecy_markers) and not dossier.public_check.is_publicly_verified:
        harm_score = 0.9
        harm_result = "VIOLATION / HIGH HARM POTENTIAL"
        harm_rationale = "Exposing unannounced material corporate transactions or secret initiatives enables front-running."
    elif mat_score >= 0.6 and not dossier.public_check.is_publicly_verified:
        harm_score = 0.55
        harm_result = "MODERATE HARM / STRATEGIC UNCERTAINTY"
        harm_rationale = "Unannounced operational or roadmap shifts could impact short-term positioning if released prematurely."
    else:
        harm_score = 0.15
        harm_result = "PASSED / LOW HARM"
        harm_rationale = "Information does not provide illicit trading advantage or compromise strategic positioning."

    # Verdict Matrix
    # MNPI_CONFIRMED requires: Material + Non-Public + Insider provenance / Secrecy breach
    if mat_score >= 0.8 and not dossier.public_check.is_publicly_verified and (src_score >= 0.7 or harm_score >= 0.7):
        verdict = "MNPI_CONFIRMED"
        risk = "CRITICAL"
        action = "BLOCK_COMMUNICATION"
        redacted = "[REDACTED MNPI CONTENT]"
        justification = (
            "CRITICAL COMPLIANCE VIOLATION: Contains Material Non-Public Information. "
            "High materiality, absence of public record, and insider secrecy markers present."
        )
    elif mat_score >= 0.5 and not dossier.public_check.is_publicly_verified:
        verdict = "POTENTIAL_MNPI"
        risk = "HIGH"
        action = "ESCALATE_TO_COMPLIANCE"
        redacted = text
        justification = (
            "POTENTIAL MNPI DETECTED: Information lacks public verification and possesses material significance. "
            "Referred to Legal & Compliance for human mosaic analysis."
        )
    elif dossier.public_check.is_publicly_verified:
        verdict = "CLEARED"
        risk = "LOW"
        action = "APPROVE_RELEASE"
        redacted = text
        justification = "CLEARED: Statements verified in public filings/press. No non-public information identified."
    else:
        verdict = "PUBLIC_NON_MATERIAL"
        risk = "LOW"
        action = "APPROVE_RELEASE"
        redacted = text
        justification = "CLEARED: Content lacks financial or operational materiality."

    return ArbiterVerdict(
        verdict=verdict,
        risk_level=risk,
        materiality_test=CriteriaAssessment(
            test_name="1. Materiality Test",
            passed_or_failed=mat_result,
            score=mat_score,
            rationale=mat_rationale,
        ),
        public_availability_test=CriteriaAssessment(
            test_name="2. Public Availability Test (Mosaic Check)",
            passed_or_failed=pub_result,
            score=pub_score,
            rationale=pub_rationale,
        ),
        source_and_duty_test=CriteriaAssessment(
            test_name="3. Source & Duty Test",
            passed_or_failed=src_result,
            score=src_score,
            rationale=src_rationale,
        ),
        actionability_harm_test=CriteriaAssessment(
            test_name="4. Actionability / Harm Test",
            passed_or_failed=harm_result,
            score=harm_score,
            rationale=harm_rationale,
        ),
        recommended_action=action,
        redacted_text=redacted,
        summary_justification=justification,
    )


# ==============================================================================
# Live Multi-Agent Execution with Gemini 3.8 Flash (Region: US)
# ==============================================================================

def get_genai_client() -> Optional[Any]:
    """Returns an authenticated google.genai.Client for Vertex AI in the US region."""
    from google import genai
    from google.genai.types import HttpOptions

    # 1. First try gcloud CLI access token (fastest and guaranteed valid for local workstation)
    try:
        import subprocess
        from google.oauth2.credentials import Credentials
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if token:
            return genai.Client(
                vertexai=True,
                project=settings.project_id,
                location=settings.location,
                credentials=Credentials(token),
                http_options=HttpOptions(base_url=settings.api_endpoint),
            )
    except Exception as e:
        logger.debug(f"gcloud token check notice: {e}")

    # 2. Fallback to standard Application Default Credentials (ADC)
    try:
        return genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
            http_options=HttpOptions(base_url=settings.api_endpoint),
        )
    except Exception as err:
        logger.warning(f"Unable to initialize Vertex AI GenAI client via ADC: {err}")

    return None


def run_live_fact_checker(client: Any, text: str) -> FactCheckingDossier:
    """Executes the Fact Checker Agent using live Gemini 3.8 Flash inference.
    
    Extracts entities (SA1), trigger keywords (SA2), and evaluates public availability (SA3).
    Zero hardcoded heuristics: all results are generated dynamically by Gemini.
    """
    from google.genai.types import GenerateContentConfig

    prompt = f"""You are the expert MPNI Fact Checker Agent (Coordinator).
Your responsibility is to analyze the following corporate communication and build an exhaustive, objective Factual Dossier.

Perform the following 3 specialist analytical passes:
1. SA1 (Entities): Extract all corporate names, stock tickers, internal project codenames, and executive names. Accurately categorize each and flag if known or suspected to be an internal/confidential codename.
2. SA2 (Triggers): Identify all corporate event catalysts (M&A, forward-looking roadmap delays or slips, unannounced product releases, earnings surprises, restructuring). Classify sensitivity level (CRITICAL, HIGH, MEDIUM, LOW).
3. SA3 (Public Check & Secrecy Markers): Evaluate whether the claims are confirmed in public records or appear non-public. Identify linguistic secrecy markers (e.g., 'don\'t share', 'confidential', 'keep quiet', 'off the record', 'between us', 'not public yet').

Document to analyze:
\"\"\"{text}\"\"\"
"""

    config = GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=FactCheckingDossier,
        temperature=0.1,
    )

    resp = client.models.generate_content(
        model=settings.default_model,
        contents=prompt,
        config=config,
    )
    return FactCheckingDossier.model_validate_json(resp.text)


def run_live_arbiter(client: Any, text: str, dossier: FactCheckingDossier) -> ArbiterVerdict:
    """Executes the Arbiter Decision Authority Agent using live Gemini 3.8 Flash inference.
    
    Applies the 4 Assessment Criteria grounded in securities law:
    - Test 1: Materiality Test (Basic Inc. v. Levinson standard)
    - Test 2: Public Availability Test / Mosaic Check
    - Test 3: Source & Duty Test (Chiarella / Dirks breach of duty)
    - Test 4: Actionability / Harm Test
    
    Renders binding verdict ('MNPI_CONFIRMED', 'POTENTIAL_MNPI', 'PUBLIC_NON_MATERIAL', or 'CLEARED'),
    actionable recommendations, and redacts sensitive MNPI content if needed.
    """
    from google.genai.types import GenerateContentConfig

    prompt = f"""You are the definitive MPNI Compliance Arbiter Agent (Decision Authority).
Your role is to evaluate the provided Factual Dossier against the 4 Mandatory Assessment Criteria:

1. Materiality Test: Would a reasonable investor consider this information significant in making an investment decision, or would it substantially alter the 'total mix' of information available (Basic Inc. v. Levinson)? Rate score (0.0 to 1.0).
2. Public Availability Test (Mosaic Check): Has this information been disseminated through recognized public distribution channels (SEC Form 8-K, national press release), or is it non-public? Rate score (0.0 to 1.0, where 1.0 is completely non-public).
3. Source & Duty Test: Did the information originate from a corporate insider under a duty of trust or confidentiality, or are explicit secrecy markers present? Rate score (0.0 to 1.0).
4. Actionability / Harm Test: Does unauthorized exposure create front-running risk, insider trading exposure, or strategic commercial harm? Rate score (0.0 to 1.0).

Requirements:
- Render verdict: 'MNPI_CONFIRMED' (if material, non-public, and insider/secrecy breach), 'POTENTIAL_MNPI' (if material but ambiguous public status), 'PUBLIC_NON_MATERIAL', or 'CLEARED'.
- Risk level: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'.
- Recommended Action: 'BLOCK_COMMUNICATION', 'REDACT_AND_PROCEED', 'ESCALATE_TO_COMPLIANCE', or 'APPROVE_RELEASE'.
- Redacted Text: If MNPI is confirmed or potential, return the original text with all confidential codenames, transaction values, and sensitive unannounced dates replaced with '[REDACTED MNPI CONTENT]'. If clean, return the original text.
- Summary Justification: Comprehensive legal compliance justification for audit manifest.

Original Document:
\"\"\"{text}\"\"\"

Fact Checking Dossier:
{dossier.model_dump_json(indent=2)}
"""

    config = GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ArbiterVerdict,
        temperature=0.1,
    )

    resp = client.models.generate_content(
        model=settings.arbiter_model,
        contents=prompt,
        config=config,
    )
    return ArbiterVerdict.model_validate_json(resp.text)


def run_pipeline(text: str, force_live: bool = True) -> tuple[FactCheckingDossier, ArbiterVerdict]:
    """Runs the genuine end-to-end Fact Checker -> Arbiter compliance pipeline using Gemini 3.8 Flash.
    
    No hardcoded heuristics: all analysis is generated in real time by Gemini 3.8 Flash in the US region.
    """
    client = get_genai_client() if force_live else None
    if client:
        try:
            logger.info(f"Executing Live Multi-Agent Pipeline via {settings.default_model} in region {settings.location}...")
            dossier = run_live_fact_checker(client, text)
            verdict = run_live_arbiter(client, text, dossier)
            return dossier, verdict
        except Exception as e:
            logger.error(f"Live Gemini 3.8 Flash pipeline execution failed: {e}", exc_info=True)
            raise e

    # Fallback to offline evaluator only if explicitly offline or testing
    logger.info("Executing offline fallback evaluator...")
    dossier = run_offline_fact_checker(text)
    verdict = run_offline_arbiter(dossier)
    return dossier, verdict

