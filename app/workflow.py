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
import os
from typing import AsyncGenerator, Dict, Any, Optional

from google.adk import Workflow, Runner
from google.adk.agents import Agent
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from app.config import settings
from app.schemas import (
    ArbiterVerdict,
    CriteriaAssessment,
    EntityExtractionResult,
    EntityItem,
    FactCheckingDossier,
    PublicCheckResult,
    TriggerDetectionResult,
    TriggerItem,
    MaterialityCode,
    MosaicCode,
    DutyCode,
    HarmCode,
)
from app.agents.fact_checker import create_fact_checker_agent
from app.agents.arbiter import create_arbiter_agent
from app.causal_engine import HierarchicalAblationTrigger, JointAblationManager
from app.rl_engine import (
    ComplianceRewardEngine,
    RewardWeightsConfig,
    get_active_weights,
    reset_active_weights,
    set_active_weights,
)
from app.tools.entity_tools import check_restricted_or_internal_codename, resolve_ticker_and_status
from app.tools.search_tools import detect_secrecy_markers, search_public_press_and_filings

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
    from app.tools.entity_tools import TICKER_DIRECTORY
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


def run_offline_arbiter(
    dossier: FactCheckingDossier,
    weights: Optional[RewardWeightsConfig] = None,
) -> ArbiterVerdict:
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

    # Determine Standardized Machine Verification Codes
    if is_ma or is_codename:
        mat_code = MaterialityCode.MAT_01_MARKET_MOVING_MA.value
    elif is_roadmap:
        mat_code = MaterialityCode.MAT_03_ROADMAP_DISRUPTION.value
    elif len(dossier.triggers.triggers) > 0:
        mat_code = MaterialityCode.MAT_02_EARNINGS_VARIANCE.value
    else:
        mat_code = MaterialityCode.MAT_CLEARED_DE_MINIMIS.value

    if dossier.public_check.is_publicly_verified:
        pub_code = MosaicCode.MOSAIC_01_VERIFIED_PUBLIC_WIRE.value
    elif dossier.public_check.verification_confidence > 0.4:
        pub_code = MosaicCode.MOSAIC_03_AMBIGUOUS_RUMOR.value
    else:
        pub_code = MosaicCode.MOSAIC_02_CONFIRMED_NON_PUBLIC.value

    if dossier.public_check.has_secrecy_markers:
        src_code = DutyCode.DUTY_01_EXPLICIT_SECRECY_MARKER.value
    elif is_codename:
        src_code = DutyCode.DUTY_02_INTERNAL_CODENAME.value
    else:
        src_code = DutyCode.DUTY_CLEARED_EXTERNAL_SOURCE.value

    if (is_ma or is_codename or dossier.public_check.has_secrecy_markers) and not dossier.public_check.is_publicly_verified:
        harm_code = HarmCode.HARM_01_FRONT_RUNNING_EXPOSURE.value
    elif mat_score >= 0.6 and not dossier.public_check.is_publicly_verified:
        harm_code = HarmCode.HARM_02_STRATEGIC_SPOILAGE.value
    else:
        harm_code = HarmCode.HARM_CLEARED_BENIGN.value

    verification_codes = [mat_code, pub_code, src_code, harm_code]

    # Evaluate Causal Attribution via LOO / Joint Cluster Ablation
    causal = JointAblationManager.evaluate_causal_attribution(
        text=text,
        dossier=dossier,
        base_violation_score=mat_score,
    )

    draft_verdict = ArbiterVerdict(
        verdict=verdict,
        risk_level=risk,
        materiality_test=CriteriaAssessment(
            test_name="1. Materiality Test",
            code=mat_code,
            passed_or_failed=mat_result,
            score=mat_score,
            rationale=mat_rationale,
        ),
        public_availability_test=CriteriaAssessment(
            test_name="2. Public Availability Test (Mosaic Check)",
            code=pub_code,
            passed_or_failed=pub_result,
            score=pub_score,
            rationale=pub_rationale,
        ),
        source_and_duty_test=CriteriaAssessment(
            test_name="3. Source & Duty Test",
            code=src_code,
            passed_or_failed=src_result,
            score=src_score,
            rationale=src_rationale,
        ),
        actionability_harm_test=CriteriaAssessment(
            test_name="4. Actionability / Harm Test",
            code=harm_code,
            passed_or_failed=harm_result,
            score=harm_score,
            rationale=harm_rationale,
        ),
        verification_codes=verification_codes,
        causal_attribution=causal,
        recommended_action=action,
        redacted_text=redacted,
        summary_justification=justification,
    )

    # Compute RL Multi-Objective Reward Metrics
    rl_metrics = ComplianceRewardEngine.calculate_reward(
        verdict=draft_verdict,
        dossier=dossier,
        causal_attribution=causal,
        weights=weights,
    )
    draft_verdict.rl_metrics = rl_metrics

    return draft_verdict


# ==============================================================================
# Live Multi-Agent Execution with Gemini 3.8 Flash (Region: US)
# ==============================================================================

def get_genai_client() -> Optional[Any]:
    """Returns an authenticated google.genai.Client for Vertex AI or Google AI Studio."""
    from google import genai
    from google.genai.types import HttpOptions

    # 0. Direct API Key (AI Studio)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            return genai.Client(api_key=api_key)
        except Exception as err:
            logger.debug(f"API key initialization notice: {err}")

    # 1. Standard Application Default Credentials (ADC) with quota project and auto-refresh
    try:
        return genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
            http_options=HttpOptions(base_url=settings.api_endpoint),
        )
    except Exception as err:
        logger.debug(f"Standard ADC initialization notice for Vertex AI: {err}")

    # 2. Fallback to gcloud CLI access token
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
        logger.warning(f"Unable to initialize Vertex AI GenAI client via fallback token: {e}")

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
def run_live_arbiter(
    dossier: FactCheckingDossier,
    text: str,
    model: Optional[str] = None,
    client: Optional[Any] = None,
    weights: Optional[RewardWeightsConfig] = None,
) -> ArbiterVerdict:
    """Invokes the live Gemini model for the Decision Authority Arbiter agent.
    
    Evaluates the FactCheckingDossier against the 4 mandatory assessment criteria:
    - Test 1: Materiality Test (Basic Inc. v. Levinson standard)
    - Test 2: Public Availability Test / Mosaic Check
    - Test 3: Source & Duty Test (Chiarella / Dirks breach of duty)
    - Test 4: Actionability / Harm Test
    
    Renders binding verdict ('MNPI_CONFIRMED', 'POTENTIAL_MNPI', 'PUBLIC_NON_MATERIAL', or 'CLEARED'),
    actionable recommendations, and redacts sensitive MNPI content if needed.
    """
    from google.genai.types import GenerateContentConfig

    active_w = weights or get_active_weights()
    fp_penalty_display = active_w.false_positive_penalty
    genai_client = client or get_genai_client()

    prompt = f"""You are the definitive MPNI Compliance Arbiter Agent (Decision Authority).
Your role is to evaluate the provided Factual Dossier against the 4 Mandatory Assessment Criteria:

1. Materiality Test (Basic Inc. v. Levinson): Rate score (0.0 to 1.0).
   Assign standardized code: MAT_01_MARKET_MOVING_MA, MAT_02_EARNINGS_VARIANCE, MAT_03_ROADMAP_DISRUPTION, MAT_04_REGULATORY_RESTRICTION, or MAT_CLEARED_DE_MINIMIS.
2. Public Availability Test (Mosaic Check): Rate score (0.0 to 1.0, where 1.0 is non-public).
   Assign standardized code: MOSAIC_01_VERIFIED_PUBLIC_WIRE, MOSAIC_02_CONFIRMED_NON_PUBLIC, or MOSAIC_03_AMBIGUOUS_RUMOR.
3. Source & Duty Test (Chiarella / Dirks): Rate score (0.0 to 1.0).
   Assign standardized code: DUTY_01_EXPLICIT_SECRECY_MARKER, DUTY_02_INTERNAL_CODENAME, DUTY_03_INSIDER_FIDUCIARY_BREACH, or DUTY_CLEARED_EXTERNAL_SOURCE.
4. Actionability / Harm Test: Rate score (0.0 to 1.0).
   Assign standardized code: HARM_01_FRONT_RUNNING_EXPOSURE, HARM_02_STRATEGIC_SPOILAGE, or HARM_CLEARED_BENIGN.

CRITICAL RULE (CONSERVATIVE BIAS PREVENTION):
Under our Reinforcement Learning compliance model, blocking or redacting verified public or benign communications incurs a severe False Positive Penalty (R_fp = {fp_penalty_display:.1f}).
If claims are verified in public press or lack market-moving materiality, classify as CLEARED or PUBLIC_NON_MATERIAL and set Recommended Action to APPROVE_RELEASE.

Requirements:
- Render verdict: 'MNPI_CONFIRMED' (if material, non-public, and insider/secrecy breach), 'POTENTIAL_MNPI' (if material but ambiguous public status), 'PUBLIC_NON_MATERIAL', or 'CLEARED'.
- Risk level: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'.
- Recommended Action: 'BLOCK_COMMUNICATION', 'REDACT_AND_PROCEED', 'ESCALATE_TO_COMPLIANCE', or 'APPROVE_RELEASE'.
- Verification Codes: Populate verification_codes array with the 4 standardized codes chosen above.
- Redacted Text: If MNPI is confirmed or potential, return original text with all confidential codenames, transaction values, and sensitive unannounced dates replaced with '[REDACTED MNPI CONTENT]'. If clean, return original text.
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

    resp = genai_client.models.generate_content(
        model=model or settings.arbiter_model,
        contents=prompt,
        config=config,
    )
    verdict = ArbiterVerdict.model_validate_json(resp.text)

    # Ensure standardized codes are consolidated
    codes = list(verdict.verification_codes or [])
    for test in (
        verdict.materiality_test,
        verdict.public_availability_test,
        verdict.source_and_duty_test,
        verdict.actionability_harm_test,
    ):
        if test.code and test.code not in codes:
            codes.append(test.code)
    verdict.verification_codes = codes

    # Always evaluate Causal Attribution and RL Multi-Objective Reward via authoritative engines
    verdict.causal_attribution = JointAblationManager.evaluate_causal_attribution(
        text=text,
        dossier=dossier,
        base_violation_score=verdict.materiality_test.score,
    )
    verdict.rl_metrics = ComplianceRewardEngine.calculate_reward(
        verdict=verdict,
        dossier=dossier,
        causal_attribution=verdict.causal_attribution,
        weights=weights,
    )

    return verdict


def run_two_agent_pipeline(
    text: str,
    document_name: Optional[str] = None,
    channel: str = "quarantine_gcs",
    log_to_bq: bool = False,
    force_live: bool = True,
    model: Optional[str] = None,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
    weights: Optional[RewardWeightsConfig] = None,
    **kwargs: Any,
) -> tuple[FactCheckingDossier, ArbiterVerdict]:
    """Executes the two distinct agent runtimes sequentially with explicit payload handoff.
    
    1. Agent 1 (mnpi-fact-checker-agent):
       Coordinates sub-agents (entities SA1, triggers SA2, public check SA3)
       and callable tools. Synthesizes a FactCheckingDossier.
       
    2. Results Transmission (Handoff):
       Agent 1 hands off the complete FactCheckingDossier payload to Agent 2.
       
    3. Agent 2 (mnpi-decision-authority-agent):
       Receives original text AND Agent 1's FactCheckingDossier results.
       Applies the 4 mandatory legal Assessment Criteria (Basic Inc., Mosaic, Dirks, Harm).
       Invokes BigQuery audit tool and renders binding ArbiterVerdict.
    """
    try:
        from app.agents.fact_checker import MNPIFactCheckerRuntime
        from app.agents.arbiter import MNPIDecisionAuthorityRuntime
    except ImportError:
        from agents.fact_checker.runtime import MNPIFactCheckerRuntime
        from agents.decision_authority.runtime import MNPIDecisionAuthorityRuntime

    fc_runtime = MNPIFactCheckerRuntime(
        project_id=project_id or settings.project_id,
        location=location or settings.location,
        model=model or settings.default_model,
    )
    da_runtime = MNPIDecisionAuthorityRuntime(
        project_id=project_id or settings.project_id,
        location=location or settings.location,
        model=model or settings.arbiter_model,
    )

    logger.info("Executing Agent 1 (mnpi-fact-checker-agent) flow...")
    print(f"   🤖 [1/2] Fact Checker analyzing text with Gemini ({fc_runtime.model})...", flush=True)
    dossier_dict = fc_runtime.query(text)
    dossier = FactCheckingDossier.model_validate(dossier_dict)
    print(f"   ✅ [1/2] Fact Checker complete: {len(dossier.entities.entities)} entities, {len(dossier.triggers.triggers)} triggers. Public verified: {dossier.public_check.is_publicly_verified}.", flush=True)

    logger.info("Agent 1 flow completed. Transmitting results payload to Agent 2 (mnpi-decision-authority-agent)...")
    print(f"   ⚖️  [2/2] Decision Authority evaluating 4 Tests with Gemini ({da_runtime.model})...", flush=True)
    verdict_dict = da_runtime.query(
        text=text,
        dossier=dossier_dict,
        document_name=document_name or "unspecified",
        channel=channel,
        log_to_bq=log_to_bq,
    )
    verdict = ArbiterVerdict.model_validate(verdict_dict)
    print(f"   ✅ [2/2] Arbiter complete: Verdict={verdict.verdict}, Risk={verdict.risk_level}.", flush=True)

    return dossier, verdict


def run_pipeline(
    text: str,
    force_live: bool = True,
    document_name: Optional[str] = None,
    channel: str = "quarantine_gcs",
    log_to_bq: bool = False,
    model: Optional[str] = None,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
    weights: Optional[RewardWeightsConfig] = None,
    **kwargs: Any,
) -> tuple[FactCheckingDossier, ArbiterVerdict]:
    """Compatibility wrapper delegating directly to the Two-Agent Pipeline."""
    return run_two_agent_pipeline(
        text=text,
        document_name=document_name,
        channel=channel,
        log_to_bq=log_to_bq,
        force_live=force_live,
        model=model,
        project_id=project_id,
        location=location,
        weights=weights,
        **kwargs,
    )

