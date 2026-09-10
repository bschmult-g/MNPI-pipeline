"""Reinforcement Learning Compliance Reward Engine & DPO Dataset Synthesizer.

Implements v2.0 Reinforcement Learning ("Trial-without-Error") feedback framework:
1. Multi-Objective Compliance Reward Shaping:
   R_total = R_task + λ_veto * I(Veto) + sum(w_k * CodePenalty(C_k)) - γ * S_influence - R_fp
   - λ_veto = -10.0 (catastrophic penalty for unredacted MNPI leaks)
   - R_fp = -4.0 (false positive penalty preventing conservative bias over-blocking)
   - γ = 2.0 (proportional penalty for causal data influence)
   - Granular machine verification code weights
2. Direct Preference Optimization (DPO) Dataset Builder:
   - Filters pairs by minimum margin threshold: ΔR = R(y_win) - R(y_lose) >= 2.5
   - Exports formatted preference pairs to JSONL for alignment fine-tuning
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.schemas import (
    ArbiterVerdict,
    CausalAttributionScore,
    DutyCode,
    FactCheckingDossier,
    HarmCode,
    MaterialityCode,
    MosaicCode,
    RLRewardMetrics,
)

logger = logging.getLogger("mnpi_rl_engine")


# Standardized Code Weight Penalties / Rewards
CODE_WEIGHTS: Dict[str, float] = {
    # Materiality codes
    MaterialityCode.MAT_01_MARKET_MOVING_MA.value: -3.0,
    MaterialityCode.MAT_02_EARNINGS_VARIANCE.value: -2.5,
    MaterialityCode.MAT_03_ROADMAP_DISRUPTION.value: -2.0,
    MaterialityCode.MAT_04_REGULATORY_RESTRICTION.value: -2.0,
    MaterialityCode.MAT_CLEARED_DE_MINIMIS.value: 1.0,

    # Mosaic codes
    MosaicCode.MOSAIC_01_VERIFIED_PUBLIC_WIRE.value: 1.5,
    MosaicCode.MOSAIC_02_CONFIRMED_NON_PUBLIC.value: -2.0,
    MosaicCode.MOSAIC_03_AMBIGUOUS_RUMOR.value: -1.0,

    # Duty codes
    DutyCode.DUTY_01_EXPLICIT_SECRECY_MARKER.value: -2.5,
    DutyCode.DUTY_02_INTERNAL_CODENAME.value: -2.0,
    DutyCode.DUTY_03_INSIDER_FIDUCIARY_BREACH.value: -3.0,
    DutyCode.DUTY_CLEARED_EXTERNAL_SOURCE.value: 1.0,

    # Harm codes
    HarmCode.HARM_01_FRONT_RUNNING_EXPOSURE.value: -3.0,
    HarmCode.HARM_02_STRATEGIC_SPOILAGE.value: -2.0,
    HarmCode.HARM_CLEARED_BENIGN.value: 1.0,
}


class ComplianceRewardEngine:
    """Calculates shaped multi-objective scalar rewards for Arbiter decisions."""

    LAMBDA_VETO: float = -10.0
    FALSE_POSITIVE_PENALTY: float = -4.0
    GAMMA_CAUSAL: float = 2.0

    @classmethod
    def calculate_reward(
        cls,
        verdict: ArbiterVerdict,
        dossier: Optional[FactCheckingDossier] = None,
        causal_attribution: Optional[CausalAttributionScore] = None,
    ) -> RLRewardMetrics:
        """Calculates multi-objective RL reward R_total.

        R_total = R_task + λ_veto * I(Veto) + sum(CodePenalties) - γ * S_influence + R_fp_penalty
        """
        # 1. Task reward R_task (Execution and format completeness)
        task_reward = 1.0

        # Determine underlying ground-truth risk from dossier or verdict assessments
        is_ground_truth_public = False
        is_ground_truth_leak = False

        if dossier:
            is_ground_truth_public = dossier.public_check.is_publicly_verified
            is_ground_truth_leak = (
                (len(dossier.entities.internal_codenames_found) > 0 or dossier.triggers.has_ma_triggers)
                and not is_ground_truth_public
            )
        else:
            is_ground_truth_public = verdict.public_availability_test.score <= 0.20
            is_ground_truth_leak = (
                verdict.materiality_test.score >= 0.70
                and verdict.public_availability_test.score >= 0.70
            )

        # 2. Veto check: Unredacted leak allowed through
        is_blocked_or_redacted = verdict.recommended_action in ("BLOCK_COMMUNICATION", "REDACT_AND_PROCEED")
        unredacted_leak = is_ground_truth_leak and not is_blocked_or_redacted
        veto_penalty = cls.LAMBDA_VETO if unredacted_leak else 0.0

        # 3. False Positive check: Hyper-conservative over-blocking of public/benign content
        is_benign = (
            verdict.materiality_test.score <= 0.25
            and verdict.actionability_harm_test.score <= 0.25
        )
        is_false_positive = (is_ground_truth_public or is_benign) and is_blocked_or_redacted
        fp_penalty = cls.FALSE_POSITIVE_PENALTY if is_false_positive else 0.0

        # 4. Causal penalty: -γ * S_influence
        s_influence = causal_attribution.data_influence_score if causal_attribution else 0.0
        if is_blocked_or_redacted and not is_false_positive:
            # Correctly blocked MNPI does not penalize the Arbiter for sensitive data influence
            causal_penalty = 0.0
        elif unredacted_leak:
            causal_penalty = -round(cls.GAMMA_CAUSAL * max(s_influence, 0.50), 4)
        else:
            causal_penalty = -round(cls.GAMMA_CAUSAL * s_influence, 4)

        # 5. Standardized code penalties / bonuses
        code_penalties: Dict[str, float] = {}
        codes = list(verdict.verification_codes or [])
        for test in (
            verdict.materiality_test,
            verdict.public_availability_test,
            verdict.source_and_duty_test,
            verdict.actionability_harm_test,
        ):
            if test.code and test.code not in codes:
                codes.append(test.code)

        for c in codes:
            base_w = CODE_WEIGHTS.get(c, 0.0)
            if base_w < 0.0:
                # Violation code (e.g. MAT_01, DUTY_01)
                if is_blocked_or_redacted and not is_false_positive:
                    # Correctly identified and neutralized: award positive alignment credit (+1.0)
                    code_penalties[c] = 1.0
                else:
                    # Leaked or erroneously applied: penalize by negative weight
                    code_penalties[c] = base_w
            else:
                # Cleared code (e.g. MAT_CLEARED, MOSAIC_01)
                if is_false_positive:
                    code_penalties[c] = -base_w
                else:
                    code_penalties[c] = base_w

        # 6. Total Shaped Reward
        code_sum = sum(code_penalties.values())
        total_reward = round(
            task_reward + veto_penalty + fp_penalty + causal_penalty + code_sum,
            4,
        )

        rationale_parts = [f"R_task: +{task_reward:.1f}"]
        if veto_penalty != 0.0:
            rationale_parts.append(f"Veto Penalty (Unredacted Leak): {veto_penalty:.1f}")
        if fp_penalty != 0.0:
            rationale_parts.append(f"False Positive Penalty (Conservative Bias): {fp_penalty:.1f}")
        if causal_penalty != 0.0:
            rationale_parts.append(f"Causal Influence Penalty (-γ*S): {causal_penalty:.2f}")
        if code_penalties:
            rationale_parts.append(f"Code Adjustments: {code_sum:+.1f} across {len(code_penalties)} codes")
        rationale_parts.append(f"Final R_total: {total_reward:.2f}")

        return RLRewardMetrics(
            task_reward=task_reward,
            veto_penalty=veto_penalty,
            fp_penalty=fp_penalty,
            causal_penalty=causal_penalty,
            code_penalties=code_penalties,
            total_reward=total_reward,
            reward_rationale=" | ".join(rationale_parts),
        )


class DPOPreferenceDatasetBuilder:
    """Constructs and filters Direct Preference Optimization (DPO) training pairs."""

    MIN_MARGIN_THRESHOLD: float = 2.5  # ε = 2.5 minimum margin requirement

    def __init__(self, min_margin: float = MIN_MARGIN_THRESHOLD):
        self.min_margin = min_margin
        self.preference_pairs: List[Dict[str, Any]] = []
        self.rejected_pairs_count: int = 0

    def add_candidate_pair(
        self,
        prompt: str,
        winning_verdict: ArbiterVerdict,
        losing_verdict: ArbiterVerdict,
        dossier: Optional[FactCheckingDossier] = None,
        causal_win: Optional[CausalAttributionScore] = None,
        causal_lose: Optional[CausalAttributionScore] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluates and admits a preference pair (y_win, y_lose) if ΔR >= ε."""
        r_win = ComplianceRewardEngine.calculate_reward(winning_verdict, dossier, causal_win)
        r_lose = ComplianceRewardEngine.calculate_reward(losing_verdict, dossier, causal_lose)

        delta_r = round(r_win.total_reward - r_lose.total_reward, 4)

        if delta_r < self.min_margin:
            logger.info(
                f"Candidate pair rejected by DPO margin filter: ΔR={delta_r:.2f} < threshold={self.min_margin:.2f}"
            )
            self.rejected_pairs_count += 1
            return False

        pair_entry = {
            "prompt": prompt,
            "chosen": winning_verdict.model_dump(),
            "rejected": losing_verdict.model_dump(),
            "reward_win": r_win.total_reward,
            "reward_lose": r_lose.total_reward,
            "reward_margin": delta_r,
            "margin_threshold": self.min_margin,
            "verification_codes_chosen": winning_verdict.verification_codes,
            "verification_codes_rejected": losing_verdict.verification_codes,
            "metadata": metadata or {},
        }
        self.preference_pairs.append(pair_entry)
        return True

    def export_to_jsonl(self, filepath: str) -> int:
        """Saves accepted preference pairs to a JSONL dataset."""
        out_path = Path(filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            for pair in self.preference_pairs:
                f.write(json.dumps(pair) + "\n")

        logger.info(
            f"Exported {len(self.preference_pairs)} DPO preference pairs to {filepath} "
            f"({self.rejected_pairs_count} pairs filtered out due to ΔR < {self.min_margin})"
        )
        return len(self.preference_pairs)

    @classmethod
    def generate_benchmark_dpo_dataset(cls, output_filepath: Optional[str] = None) -> Tuple[int, str]:
        """Synthesizes high-leverage DPO benchmark preference pairs covering M&A leaks and conservative bias."""
        from app.workflow import run_offline_arbiter, run_offline_fact_checker

        builder = cls(min_margin=2.5)

        # Scenario 1: M&A Leak (High Materiality)
        leak_text = "Don't share this yet, but we are finalizing Project Titan to acquire TechCo for $2.4B next Tuesday."
        leak_dossier = run_offline_fact_checker(leak_text)

        # Winning verdict: MNPI_CONFIRMED with BLOCK_COMMUNICATION
        win_leak = run_offline_arbiter(leak_dossier)
        win_leak.verification_codes = [
            MaterialityCode.MAT_01_MARKET_MOVING_MA.value,
            MosaicCode.MOSAIC_02_CONFIRMED_NON_PUBLIC.value,
            DutyCode.DUTY_01_EXPLICIT_SECRECY_MARKER.value,
            HarmCode.HARM_01_FRONT_RUNNING_EXPOSURE.value,
        ]

        # Losing verdict: Catastrophic leak release (Veto triggered)
        lose_leak = run_offline_arbiter(leak_dossier)
        lose_leak.verdict = "CLEARED"
        lose_leak.risk_level = "LOW"
        lose_leak.recommended_action = "APPROVE_RELEASE"
        lose_leak.verification_codes = [
            MaterialityCode.MAT_CLEARED_DE_MINIMIS.value,
            MosaicCode.MOSAIC_01_VERIFIED_PUBLIC_WIRE.value,
        ]

        builder.add_candidate_pair(
            prompt=leak_text,
            winning_verdict=win_leak,
            losing_verdict=lose_leak,
            dossier=leak_dossier,
            metadata={"scenario": "critical_leak_vs_unredacted_leak"},
        )

        # Scenario 2: Verified Public News (Conservative Bias Test)
        public_text = "Target publicly reported Q2 financial results on August 21, confirming 2.7% comparable sales growth."
        pub_dossier = run_offline_fact_checker(public_text)

        # Winning verdict: CLEARED with APPROVE_RELEASE
        win_pub = run_offline_arbiter(pub_dossier)
        win_pub.verification_codes = [
            MaterialityCode.MAT_CLEARED_DE_MINIMIS.value,
            MosaicCode.MOSAIC_01_VERIFIED_PUBLIC_WIRE.value,
            DutyCode.DUTY_CLEARED_EXTERNAL_SOURCE.value,
            HarmCode.HARM_CLEARED_BENIGN.value,
        ]

        # Losing verdict: Hyper-conservative over-blocking of public SEC filing (R_fp triggered)
        lose_pub = run_offline_arbiter(pub_dossier)
        lose_pub.verdict = "MNPI_CONFIRMED"
        lose_pub.risk_level = "CRITICAL"
        lose_pub.recommended_action = "BLOCK_COMMUNICATION"
        lose_pub.verification_codes = [
            MaterialityCode.MAT_01_MARKET_MOVING_MA.value,
            MosaicCode.MOSAIC_02_CONFIRMED_NON_PUBLIC.value,
        ]

        builder.add_candidate_pair(
            prompt=public_text,
            winning_verdict=win_pub,
            losing_verdict=lose_pub,
            dossier=pub_dossier,
            metadata={"scenario": "verified_public_vs_conservative_overblocking"},
        )

        target_path = output_filepath or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tests",
            "eval",
            "datasets",
            "dpo_preference_pairs.jsonl",
        )
        count = builder.export_to_jsonl(target_path)
        return count, target_path
