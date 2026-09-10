"""Data models and schemas for MNPI Agent System.

Defines Pydantic models for:
- SA1: Entities extraction
- SA2: Trigger words detection
- SA3: Public verification & linguistic secrecy markers
- Coordinator: Fact Checking Dossier
- Decision Authority: Arbiter 4-Test Assessment and Final Verdict
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
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
# Standardized Machine-Enforceable Verification & Justification Codes
# ==============================================================================

class MaterialityCode(str, Enum):
    MAT_01_MARKET_MOVING_MA = "MAT_01_MARKET_MOVING_MA"
    MAT_02_EARNINGS_VARIANCE = "MAT_02_EARNINGS_VARIANCE"
    MAT_03_ROADMAP_DISRUPTION = "MAT_03_ROADMAP_DISRUPTION"
    MAT_04_REGULATORY_RESTRICTION = "MAT_04_REGULATORY_RESTRICTION"
    MAT_CLEARED_DE_MINIMIS = "MAT_CLEARED_DE_MINIMIS"


class MosaicCode(str, Enum):
    MOSAIC_01_VERIFIED_PUBLIC_WIRE = "MOSAIC_01_VERIFIED_PUBLIC_WIRE"
    MOSAIC_02_CONFIRMED_NON_PUBLIC = "MOSAIC_02_CONFIRMED_NON_PUBLIC"
    MOSAIC_03_AMBIGUOUS_RUMOR = "MOSAIC_03_AMBIGUOUS_RUMOR"


class DutyCode(str, Enum):
    DUTY_01_EXPLICIT_SECRECY_MARKER = "DUTY_01_EXPLICIT_SECRECY_MARKER"
    DUTY_02_INTERNAL_CODENAME = "DUTY_02_INTERNAL_CODENAME"
    DUTY_03_INSIDER_FIDUCIARY_BREACH = "DUTY_03_INSIDER_FIDUCIARY_BREACH"
    DUTY_CLEARED_EXTERNAL_SOURCE = "DUTY_CLEARED_EXTERNAL_SOURCE"


class HarmCode(str, Enum):
    HARM_01_FRONT_RUNNING_EXPOSURE = "HARM_01_FRONT_RUNNING_EXPOSURE"
    HARM_02_STRATEGIC_SPOILAGE = "HARM_02_STRATEGIC_SPOILAGE"
    HARM_CLEARED_BENIGN = "HARM_CLEARED_BENIGN"


# ==============================================================================
# Causal Attribution & Reinforcement Learning Metrics
# ==============================================================================

class CausalAttributionScore(BaseModel):
    """Causal Attribution metrics computed via Leave-One-Out (LOO) ablation."""
    ablation_mode: Literal[
        "skipped_high_confidence",
        "skipped_low_confidence",
        "single_token_loo",
        "joint_cluster",
        "not_applicable"
    ] = Field(description="Execution mode of the hierarchical ablation trigger")
    candidate_tokens: List[str] = Field(default_factory=list, description="Tokens evaluated for causal attribution")
    full_violation_score: float = Field(description="Violation score P(Violation | Prompt + Sensitive Data)")
    counterfactual_score: float = Field(description="Counterfactual score P(Violation | Prompt + ∅)")
    data_influence_score: float = Field(description="Data influence S = P(Full) - P(Counterfactual)")
    prompt_influence_score: float = Field(description="Prompt influence U = P(Counterfactual)")
    individual_deltas: Dict[str, float] = Field(default_factory=dict, description="Marginal delta per candidate token")
    joint_influence_score: float = Field(default=0.0, description="Joint ablation score S_joint for token cluster C")
    is_overdetermined: bool = Field(default=False, description="True if multiple concurrent leaks mask individual deltas")
    is_causally_dominant: bool = Field(default=False, description="True if S > U - tau indicating sensitive data is causal driver")
    causal_rationale: str = Field(description="Explanation of counterfactual causal attribution findings")


class RewardWeightsConfig(BaseModel):
    """Dynamically adjustable hyperparameters and penalty weights for RL compliance reward model."""
    r_task: float = Field(default=1.0, description="Base task completion reward R_task")
    lambda_veto: float = Field(default=-10.0, description="Catastrophic unredacted leak veto penalty lambda_veto")
    false_positive_penalty: float = Field(default=-4.0, description="Conservative bias over-blocking penalty R_fp")
    gamma_causal: float = Field(default=2.0, ge=0.0, description="Causal data influence sensitivity factor gamma")
    dpo_min_margin: float = Field(default=2.5, ge=0.0, description="DPO pair acceptance minimum margin threshold")

    # Standardized Code Weight fine-tuning
    weight_mat_ma: float = Field(default=-3.0, description="Penalty for unredacted MAT_01 (Market Moving M&A)")
    weight_mat_earnings: float = Field(default=-2.5, description="Penalty for unredacted MAT_02 (Earnings Variance)")
    weight_mat_roadmap: float = Field(default=-2.0, description="Penalty for unredacted MAT_03 (Roadmap Disruption)")
    weight_mat_regulatory: float = Field(default=-2.0, description="Penalty for unredacted MAT_04 (Regulatory Restriction)")
    weight_mat_cleared: float = Field(default=1.0, description="Bonus for MAT_CLEARED")

    weight_mosaic_public: float = Field(default=1.5, description="Bonus for MOSAIC_01 (Verified Public Wire)")
    weight_mosaic_non_public: float = Field(default=-2.0, description="Penalty for MOSAIC_02 (Confirmed Non-Public)")
    weight_mosaic_rumor: float = Field(default=-1.0, description="Penalty for MOSAIC_03 (Ambiguous Rumor)")

    weight_duty_marker: float = Field(default=-2.5, description="Penalty for DUTY_01 (Explicit Secrecy Marker)")
    weight_duty_codename: float = Field(default=-2.0, description="Penalty for DUTY_02 (Internal Codename)")
    weight_duty_fiduciary: float = Field(default=-3.0, description="Penalty for DUTY_03 (Insider Fiduciary Breach)")
    weight_duty_cleared: float = Field(default=1.0, description="Bonus for DUTY_CLEARED")

    weight_harm_frontrunning: float = Field(default=-3.0, description="Penalty for HARM_01 (Front-Running Exposure)")
    weight_harm_spoilage: float = Field(default=-2.0, description="Penalty for HARM_02 (Strategic Spoilage)")
    weight_harm_cleared: float = Field(default=1.0, description="Bonus for HARM_CLEARED")

    def get_code_weight(self, code: str, default: float = 0.0) -> float:
        """Resolves the weight for a given standardized assessment code."""
        mapping = {
            MaterialityCode.MAT_01_MARKET_MOVING_MA.value: self.weight_mat_ma,
            MaterialityCode.MAT_02_EARNINGS_VARIANCE.value: self.weight_mat_earnings,
            MaterialityCode.MAT_03_ROADMAP_DISRUPTION.value: self.weight_mat_roadmap,
            MaterialityCode.MAT_04_REGULATORY_RESTRICTION.value: self.weight_mat_regulatory,
            MaterialityCode.MAT_CLEARED_DE_MINIMIS.value: self.weight_mat_cleared,

            MosaicCode.MOSAIC_01_VERIFIED_PUBLIC_WIRE.value: self.weight_mosaic_public,
            MosaicCode.MOSAIC_02_CONFIRMED_NON_PUBLIC.value: self.weight_mosaic_non_public,
            MosaicCode.MOSAIC_03_AMBIGUOUS_RUMOR.value: self.weight_mosaic_rumor,

            DutyCode.DUTY_01_EXPLICIT_SECRECY_MARKER.value: self.weight_duty_marker,
            DutyCode.DUTY_02_INTERNAL_CODENAME.value: self.weight_duty_codename,
            DutyCode.DUTY_03_INSIDER_FIDUCIARY_BREACH.value: self.weight_duty_fiduciary,
            DutyCode.DUTY_CLEARED_EXTERNAL_SOURCE.value: self.weight_duty_cleared,

            HarmCode.HARM_01_FRONT_RUNNING_EXPOSURE.value: self.weight_harm_frontrunning,
            HarmCode.HARM_02_STRATEGIC_SPOILAGE.value: self.weight_harm_spoilage,
            HarmCode.HARM_CLEARED_BENIGN.value: self.weight_harm_cleared,
        }
        return mapping.get(code, default)


class RLRewardMetrics(BaseModel):
    """Reinforcement Learning multi-objective reward shaping metrics."""
    task_reward: float = Field(description="Task utility and execution score R_task")
    veto_penalty: float = Field(description="Penalty lambda_veto * I(Veto Triggered) for unredacted MNPI leaks")
    fp_penalty: float = Field(description="False positive penalty R_fp for over-blocking verified public/benign text")
    causal_penalty: float = Field(description="Penalty proportional to causal data influence -gamma * S_influence")
    code_penalties: Dict[str, float] = Field(default_factory=dict, description="Penalties derived from standardized verification codes")
    total_reward: float = Field(description="Final shaped scalar reward R_total = R_task + Veto + Penalties - R_fp")
    reward_rationale: str = Field(description="Breakdown explaining positive and negative reward components")


# ==============================================================================
# Arbiter: 4 Assessment Criteria & Final Verdict
# ==============================================================================

class CriteriaAssessment(BaseModel):
    """Evaluation result for one of the 4 Arbiter Assessment Criteria."""
    test_name: str = Field(description="Name of the assessment test")
    code: Optional[str] = Field(default=None, description="Standardized machine-enforceable verification code")
    passed_or_failed: str = Field(
        description="Result description (e.g. 'VIOLATION / MATERIAL', 'NON-PUBLIC', 'CLEARED / PUBLIC')"
    )
    score: float = Field(ge=0.0, le=1.0, description="Risk / probability score between 0.0 (benign) and 1.0 (severe)")
    rationale: str = Field(description="Reasoning grounded in jurisprudence, facts, and legal standards")


# ==============================================================================
# Enterprise Security & Entitlements Tag Schema
# ==============================================================================

class SecurityEntitlementsTag(BaseModel):
    """Indexable document security tag and hierarchical access entitlements manifest.

    Designed for O(1) query filtering across downstream data stores (BigQuery RLS,
    GCS object metadata, Vertex AI Search, and enterprise vector databases).
    """
    tag_version: str = Field(default="1.0", description="Schema version of the entitlements tag")
    document_id: str = Field(description="Document filename or unique identifier")
    classification_tier: Literal[
        "MNPI_CRITICAL",
        "MNPI_HIGH",
        "INTERNAL_CONFIDENTIAL",
        "PUBLIC_UNRESTRICTED"
    ] = Field(description="Normalized enterprise classification tier")
    clearance_rank: Optional[int] = Field(
        default=None,
        description="Hierarchical clearance rank (Nullified/Unassigned pending organizational entitlement carveout)"
    )
    min_role_required: Optional[str] = Field(
        default=None,
        description="Minimum job role required (Nullified/Unassigned pending organizational entitlement carveout)"
    )
    permitted_departments: List[str] = Field(
        default_factory=list,
        description="List of enterprise departments permitted access (e.g. INVESTMENT_BANKING, LEGAL, COMPLIANCE)"
    )
    permitted_groups: List[str] = Field(
        default_factory=list,
        description="Directory/IAM groups entitled to access (e.g. grp-mnpi-cleared-vp, grp-compliance-officers)"
    )
    ticker_restrictions: List[str] = Field(
        default_factory=list,
        description="Associated stock tickers subject to trading blackout or watch list"
    )
    routing_action: Literal[
        "BLOCK_COMMUNICATION",
        "REDACT_AND_PROCEED",
        "ESCALATE_TO_COMPLIANCE",
        "APPROVE_RELEASE"
    ] = Field(description="Automated routing and gateway enforcement directive")
    is_redacted: bool = Field(
        default=False,
        description="True if unredacted content was stripped/sanitized for lower clearance tiers"
    )
    audit_hash: Optional[str] = Field(
        default=None,
        description="Cryptographic SHA-256 audit digest binding document content to this tag"
    )
    created_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 UTC timestamp of tag generation"
    )

    def to_gcs_metadata(self) -> Dict[str, str]:
        """Converts entitlement attributes to GCS object custom metadata string key-values."""
        return {
            "mnpi-tag-version": self.tag_version,
            "mnpi-classification": self.classification_tier,
            "mnpi-clearance-rank": str(self.clearance_rank) if self.clearance_rank is not None else "null",
            "mnpi-min-role": self.min_role_required or "unassigned",
            "mnpi-routing-action": self.routing_action,
            "mnpi-is-redacted": str(self.is_redacted).lower(),
            "mnpi-audit-hash": self.audit_hash or "",
            "mnpi-tickers": ",".join(self.ticker_restrictions),
            "mnpi-departments": ",".join(self.permitted_departments),
        }

    def to_manifest_dict(self) -> Dict[str, Any]:
        """Exports complete structured JSON envelope for sidecar storage and BigQuery ingestion."""
        return self.model_dump()


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

    verification_codes: List[str] = Field(
        default_factory=list,
        description="Machine-enforceable verification codes from the 4 criteria"
    )
    causal_attribution: Optional[CausalAttributionScore] = Field(
        default=None,
        description="Causal attribution and LOO counterfactual metrics"
    )
    rl_metrics: Optional[RLRewardMetrics] = Field(
        default=None,
        description="Reinforcement learning reward metrics"
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
    entitlements: Optional[SecurityEntitlementsTag] = Field(
        default=None,
        description="Indexable document security tag and hierarchical access entitlements manifest"
    )


