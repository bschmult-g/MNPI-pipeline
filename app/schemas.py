"""Data models and schemas for MNPI Agent System.

Defines Pydantic models for:
- SA1: Entities extraction
- SA2: Trigger words detection
- SA3: Public verification & linguistic secrecy markers
- Coordinator: Fact Checking Dossier
- Decision Authority: Arbiter 4-Test Assessment and Final Verdict
"""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# SA1: Entities Schemas
# ==============================================================================

class EntityItem(BaseModel):
    """An individual entity identified in the text."""
    name: str = Field(description="Name or symbol of the entity (e.g. 'Apple Inc', 'MSFT', 'Project Titan')")
    category: Literal["corporate_name", "stock_ticker", "project_codename", "executive_name", "other"] = Field(
        description="Type of entity"
    )
    context_snippet: str = Field(description="Sentence or phrase containing the entity")
    is_internal_or_restricted: bool = Field(
        default=False,
        description="True if known or suspected to be a confidential internal codename or private entity"
    )
    notes: Optional[str] = Field(default=None, description="Optional compliance or contextual notes")


class EntityExtractionResult(BaseModel):
    """Output from SA1: Entities Agent."""
    entities: List[EntityItem] = Field(default_factory=list, description="List of recognized entities")
    tickers_found: List[str] = Field(default_factory=list, description="Extracted stock ticker symbols")
    internal_codenames_found: List[str] = Field(default_factory=list, description="Extracted confidential project names")
    summary: str = Field(description="Summary of entity extraction findings")


# ==============================================================================
# SA2: Trigger Words Schemas
# ==============================================================================

class TriggerItem(BaseModel):
    """An individual trigger keyword or phrase identified."""
    term: str = Field(description="Trigger word or phrase (e.g. 'merger', 'acquisition', 'roadmap', 'product release')")
    category: Literal[
        "merger_acquisition",
        "roadmap_forward_looking",
        "product_release",
        "financial_earnings",
        "restructuring_layoffs",
        "executive_transition",
        "regulatory_investigation",
        "other"
    ] = Field(description="Category of corporate event trigger")
    context_snippet: str = Field(description="Sentence or phrase where trigger appears")
    sensitivity_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        description="Inherent sensitivity level of the trigger category"
    )


class TriggerDetectionResult(BaseModel):
    """Output from SA2: Trigger Words Agent."""
    triggers: List[TriggerItem] = Field(default_factory=list, description="Detected trigger words")
    highest_sensitivity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        default="LOW",
        description="Highest sensitivity level among detected triggers"
    )
    has_ma_triggers: bool = Field(default=False, description="Whether M&A related triggers were detected")
    has_roadmap_or_release_triggers: bool = Field(default=False, description="Whether roadmap or product release triggers were detected")
    summary: str = Field(description="Summary of trigger word scan findings")


# ==============================================================================
# SA3: Public Check Schemas
# ==============================================================================

class PublicCheckResult(BaseModel):
    """Output from SA3: Public Check Agent."""
    claims_evaluated: List[str] = Field(default_factory=list, description="Key factual claims evaluated for public availability")
    is_publicly_verified: bool = Field(
        description="True if all material claims are confirmed to be widely available in top-tier press/SEC filings"
    )
    verification_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0) regarding public status"
    )
    sources_cited: List[str] = Field(
        default_factory=list,
        description="Public sources, filings, or press releases corroborating the information"
    )
    linguistic_markers: List[str] = Field(
        default_factory=list,
        description="Linguistic secrecy markers found (e.g., 'don't share', 'confidential', 'keep quiet', 'internal use only')"
    )
    has_secrecy_markers: bool = Field(
        default=False,
        description="True if linguistic secrecy markers were detected indicating non-public provenance"
    )
    mosaic_check_notes: str = Field(
        description="Detailed assessment of whether this is public knowledge or non-public mosaic puzzle piece"
    )


# ==============================================================================
# Coordinator: Fact Checking Dossier
# ==============================================================================

class FactCheckingDossier(BaseModel):
    """Comprehensive factual report produced by the MPNI Fact Checker Agent."""
    original_text: str = Field(description="The source text analyzed")
    entities: EntityExtractionResult = Field(description="Entities extracted by SA1")
    triggers: TriggerDetectionResult = Field(description="Trigger words identified by SA2")
    public_check: PublicCheckResult = Field(description="Public availability & secrecy check by SA3")
    dossier_summary: str = Field(description="Holistic factual summary synthesized by the Fact Checker Agent")
    high_risk_signals_present: bool = Field(
        description="Flag set to True if high-risk entities, triggers, or secrecy markers are present"
    )


# ==============================================================================
# Arbiter: 4 Assessment Criteria & Final Verdict
# ==============================================================================

class CriteriaAssessment(BaseModel):
    """Evaluation result for one of the 4 Arbiter Assessment Criteria."""
    test_name: str = Field(description="Name of the assessment test")
    passed_or_failed: str = Field(
        description="Result description (e.g. 'VIOLATION / MATERIAL', 'NON-PUBLIC', 'CLEARED / PUBLIC')"
    )
    score: float = Field(ge=0.0, le=1.0, description="Risk / probability score between 0.0 (benign) and 1.0 (severe)")
    rationale: str = Field(description="Reasoning grounded in jurisprudence, facts, and legal standards")


class ArbiterVerdict(BaseModel):
    """Final decision rendered by the MPNI Agent Arbiter (Decision Authority)."""
    verdict: Literal["MNPI_CONFIRMED", "POTENTIAL_MNPI", "PUBLIC_NON_MATERIAL", "CLEARED"] = Field(
        description="Definitive compliance determination"
    )
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        description="Overall compliance and regulatory risk level"
    )

    # The 4 Agent Assessment Criteria from the design:
    materiality_test: CriteriaAssessment = Field(
        description="Criterion 1: Materiality Test (Would a reasonable investor trade on it or shift valuation?)"
    )
    public_availability_test: CriteriaAssessment = Field(
        description="Criterion 2: Public Availability Test / Mosaic Check (Confirmed in top-tier public press/filings?)"
    )
    source_and_duty_test: CriteriaAssessment = Field(
        description="Criterion 3: Source & Duty Test (Did information originate from internal employee, insider, or confidential call?)"
    )
    actionability_harm_test: CriteriaAssessment = Field(
        description="Criterion 4: Actionability / Harm Test (Does exposing this allow inferring confidential strategy/financial outcome?)"
    )

    recommended_action: Literal[
        "BLOCK_COMMUNICATION",
        "REDACT_AND_PROCEED",
        "ESCALATE_TO_COMPLIANCE",
        "APPROVE_RELEASE"
    ] = Field(description="Action required for messaging/publishing systems")

    redacted_text: Optional[str] = Field(
        default=None,
        description="Sanitized version of text with MNPI chunks redacted (if applicable)"
    )
    summary_justification: str = Field(
        description="Official executive compliance justification for audit logs"
    )
