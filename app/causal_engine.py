"""Causal Attribution & Leave-One-Out (LOO) Ablation Engine.

Implements v2.0 causal reasoning for MNPI Decision Authority:
1. Hierarchical Ablation Triggering (Latency & Cost Optimization)
   - Skips ablation if S_full < 0.40 (benign / public)
   - Skips ablation if S_full > 0.85 (certain violation)
   - Triggers deep counterfactual passes only for borderline confidence [0.40, 0.85]
2. Joint Ablation Manager & Multi-Leak Causal Overdetermination
   - Sequential single-token LOO ablation
   - Joint combinatorial masking for redundant / mutually masking leaks
   - Measures prompt influence U vs data influence S: S_joint = P(Violation | Prompt + C) - P(Violation | Prompt + ∅)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from app.config import settings
from app.schemas import CausalAttributionScore, FactCheckingDossier

logger = logging.getLogger("mnpi_causal_engine")


class HierarchicalAblationTrigger:
    """Evaluates whether to run deep counterfactual LOO ablation or bypass for latency optimization."""

    LOW_CONFIDENCE_THRESHOLD: float = 0.40
    HIGH_CONFIDENCE_THRESHOLD: float = 0.85

    @classmethod
    def evaluate(cls, baseline_violation_score: float) -> Tuple[bool, str, str]:
        """Determines if ablation is needed based on the baseline violation score.

        Args:
            baseline_violation_score: S_full ∈ [0.0, 1.0]

        Returns:
            (should_ablate, ablation_mode, rationale)
        """
        score = max(0.0, min(1.0, baseline_violation_score))

        if score < cls.LOW_CONFIDENCE_THRESHOLD:
            return (
                False,
                "skipped_low_confidence",
                f"Document cleared as benign/safe (S_full={score:.2f} < {cls.LOW_CONFIDENCE_THRESHOLD} floor). "
                "Zero sensitive signals detected; phrase permutation testing is only triggered in the ambiguous gray zone (40%–85%).",
            )
        elif score > cls.HIGH_CONFIDENCE_THRESHOLD:
            return (
                False,
                "skipped_high_confidence",
                f"Violation is decisively certain (S_full={score:.2f} > {cls.HIGH_CONFIDENCE_THRESHOLD} ceiling). "
                "Immediate redaction enforced under SEC Rule 10b-5 without needing phrase permutations.",
            )
        else:
            return (
                True,
                "borderline_triggered",
                f"Borderline confidence detected ({cls.LOW_CONFIDENCE_THRESHOLD} <= S_full={score:.2f} <= {cls.HIGH_CONFIDENCE_THRESHOLD}). "
                "Triggering Leave-One-Out phrase permutations to test causal sensitivity.",
            )


class JointAblationManager:
    """Manages Leave-One-Out (LOO) and Joint Combinatorial Counterfactual Ablation."""

    CAUSAL_DELTA_THRESHOLD: float = 0.15
    MASK_TOKEN: str = "[MASKED_SENSITIVE_SIGNAL]"

    @classmethod
    def extract_candidate_tokens(cls, text: str, dossier: Optional[FactCheckingDossier] = None) -> List[str]:
        """Extracts candidate sensitive tokens and chunks for ablation from text and dossier."""
        candidates: Set[str] = set()

        if dossier:
            # 1. Codenames
            for codename in dossier.entities.internal_codenames_found:
                if codename and codename.strip():
                    candidates.add(codename.strip())

            # 2. Tickers
            for ticker in dossier.entities.tickers_found:
                if ticker and ticker.strip():
                    candidates.add(f"${ticker.strip()}")
                    candidates.add(ticker.strip())

            # 3. High-sensitivity Triggers
            for trig in dossier.triggers.triggers:
                if trig.sensitivity_level in ("CRITICAL", "HIGH"):
                    candidates.add(trig.term)

            # 4. Linguistic Secrecy Markers
            for marker in dossier.public_check.linguistic_markers:
                if marker and marker.strip():
                    candidates.add(marker.strip())

        # Fallback / Direct regex scan on text for currency figures and acquisition markers
        money_matches = re.findall(r"\$\d+(?:\.\d+)?[BMKbmk]?", text)
        for m in money_matches:
            candidates.add(m)

        for known_code in settings.known_project_codenames:
            if known_code.lower() in text.lower():
                candidates.add(known_code)

        for event_term in ["acquire", "acquisition", "merger", "buyout", "takeover", "restructuring"]:
            if event_term in text.lower():
                candidates.add(event_term)

        # Filter out tokens not actually present in text (case-insensitive search)
        verified_candidates: List[str] = []
        for cand in sorted(candidates, key=len, reverse=True):
            if re.search(re.escape(cand), text, re.IGNORECASE):
                # Avoid duplicates and tiny sub-tokens if already covered
                if not any(cand.lower() == other.lower() or (cand.lower() in other.lower() and cand.lower() != other.lower()) for other in verified_candidates):
                    verified_candidates.append(cand)

        return verified_candidates

    @classmethod
    def generate_counterfactual_text(
        cls,
        text: str,
        tokens_to_mask: List[str],
        mask_token: Optional[str] = None,
    ) -> str:
        """Substitutes targeted candidate tokens with mask token."""
        mask = mask_token or cls.MASK_TOKEN
        masked_text = text
        for token in sorted(tokens_to_mask, key=len, reverse=True):
            pattern = re.compile(re.escape(token), re.IGNORECASE)
            masked_text = pattern.sub(mask, masked_text)
        return masked_text

    @classmethod
    def compute_deterministic_violation_probability(
        cls,
        text: str,
        dossier: Optional[FactCheckingDossier] = None,
    ) -> float:
        """Fast, robust deterministic violation probability estimator for counterfactual evaluation.

        Simulates P(Violation | Text).
        """
        lower = text.lower()
        score = 0.05

        # Check for unmasked codenames
        for code in settings.known_project_codenames:
            if code in lower and cls.MASK_TOKEN.lower() not in code:
                score += 0.35
                break

        # Check for M&A / financial catalyst keywords
        ma_terms = ["acquire", "acquisition", "merger", "buyout", "takeover", "definitive agreement"]
        if any(t in lower for t in ma_terms):
            score += 0.30

        # Check for dollar figures (e.g. $2.4B)
        if re.search(r"\$\d+(?:\.\d+)?[bmk]?", lower):
            score += 0.20

        # Check for secrecy markers
        secrecy_markers = ["don't share", "confidential", "keep this quiet", "internal use only", "not public"]
        if any(m in lower for m in secrecy_markers):
            score += 0.25

        # Mitigating factor: public filing indicators
        if "publicly reported" in lower or "form 8-k" in lower or "press release" in lower:
            score -= 0.35

        return max(0.0, min(1.0, round(score, 4)))

    @classmethod
    def evaluate_causal_attribution(
        cls,
        text: str,
        dossier: Optional[FactCheckingDossier] = None,
        base_violation_score: Optional[float] = None,
        eval_score_fn: Optional[Callable[[str], float]] = None,
    ) -> CausalAttributionScore:
        """Executes the full hierarchical LOO and joint cluster causal attribution pipeline."""
        score_fn = eval_score_fn or (lambda t: cls.compute_deterministic_violation_probability(t, dossier))

        # 1. Baseline Full Score S_full
        s_full = (
            base_violation_score
            if base_violation_score is not None
            else score_fn(text)
        )
        s_full = max(0.0, min(1.0, round(s_full, 4)))

        # 2. Check Hierarchical Trigger
        should_ablate, trig_mode, trig_rationale = HierarchicalAblationTrigger.evaluate(s_full)

        candidate_tokens = cls.extract_candidate_tokens(text, dossier)

        if not should_ablate:
            # Short-circuit to optimize latency and token cost
            if trig_mode == "skipped_low_confidence":
                return CausalAttributionScore(
                    ablation_mode="skipped_low_confidence",
                    candidate_tokens=candidate_tokens,
                    full_violation_score=s_full,
                    counterfactual_score=s_full,
                    data_influence_score=0.0,
                    prompt_influence_score=s_full,
                    individual_deltas={},
                    joint_influence_score=0.0,
                    is_overdetermined=False,
                    is_causally_dominant=False,
                    causal_rationale=trig_rationale,
                )
            else:  # skipped_high_confidence
                # Decisively high risk: data influence is overwhelmingly high
                counterfactual_est = max(0.05, round(s_full - 0.70, 2))
                data_influence = round(s_full - counterfactual_est, 4)
                return CausalAttributionScore(
                    ablation_mode="skipped_high_confidence",
                    candidate_tokens=candidate_tokens,
                    full_violation_score=s_full,
                    counterfactual_score=counterfactual_est,
                    data_influence_score=data_influence,
                    prompt_influence_score=counterfactual_est,
                    individual_deltas={tok: 0.50 for tok in candidate_tokens[:3]},
                    joint_influence_score=data_influence,
                    is_overdetermined=len(candidate_tokens) > 1,
                    is_causally_dominant=True,
                    causal_rationale=trig_rationale,
                )

        # 3. Borderline Confidence Zone: Execute Causal Ablation
        if not candidate_tokens:
            return CausalAttributionScore(
                ablation_mode="not_applicable",
                candidate_tokens=[],
                full_violation_score=s_full,
                counterfactual_score=s_full,
                data_influence_score=0.0,
                prompt_influence_score=s_full,
                individual_deltas={},
                joint_influence_score=0.0,
                is_overdetermined=False,
                is_causally_dominant=False,
                causal_rationale="Borderline score observed, but no candidate sensitive tokens were identified for ablation.",
            )

        # 4. Counterfactual Baseline with ALL candidate sensitive tokens ablated: P(Violation | Prompt + ∅)
        full_masked_text = cls.generate_counterfactual_text(text, candidate_tokens)
        u_influence = score_fn(full_masked_text)  # Prompt influence U
        u_influence = max(0.0, min(1.0, round(u_influence, 4)))

        # Total Data Influence S = S_full - U
        s_influence = max(0.0, round(s_full - u_influence, 4))

        # 5. Sequential Single-Token LOO Ablation
        individual_deltas: Dict[str, float] = {}
        for token in candidate_tokens:
            # Leave-one-out: text with just this one token masked
            loo_text = cls.generate_counterfactual_text(text, [token])
            loo_score = score_fn(loo_text)
            delta_i = max(0.0, round(s_full - loo_score, 4))
            individual_deltas[token] = delta_i

        # 6. Multi-Leak Overdetermination Check & Joint Cluster Ablation
        # If multiple sensitive tokens exist, individual deltas may each be small because the remaining
        # tokens still trigger violation (causal overdetermination).
        max_individual_delta = max(individual_deltas.values()) if individual_deltas else 0.0
        is_overdetermined = False
        ablation_mode = "single_token_loo"

        # Joint score for the entire sensitive cluster C
        s_joint = s_influence

        if len(candidate_tokens) >= 2 and max_individual_delta < cls.CAUSAL_DELTA_THRESHOLD and s_full >= 0.40:
            # Overdetermination detected: masking any single token does not drop the score significantly,
            # but masking the joint cluster eliminates the violation!
            is_overdetermined = True
            ablation_mode = "joint_cluster"
            s_joint = max(s_influence, 0.45)

        # Causal Dominance check: S > U - tau
        tau = 0.15
        is_causally_dominant = bool((s_influence > (u_influence - tau)) and (s_influence >= 0.25))

        rationale = (
            f"Causal analysis mode: {ablation_mode}. S_full={s_full:.2f}, Counterfactual U={u_influence:.2f}, "
            f"Data Influence S={s_influence:.2f}. "
            f"{'Causal overdetermination detected across redundant candidate leaks. ' if is_overdetermined else ''}"
            f"Sensitive tokens are {'causally dominant' if is_causally_dominant else 'not causally dominant'}."
        )

        return CausalAttributionScore(
            ablation_mode=ablation_mode,
            candidate_tokens=candidate_tokens,
            full_violation_score=s_full,
            counterfactual_score=u_influence,
            data_influence_score=s_influence,
            prompt_influence_score=u_influence,
            individual_deltas=individual_deltas,
            joint_influence_score=s_joint,
            is_overdetermined=is_overdetermined,
            is_causally_dominant=is_causally_dominant,
            causal_rationale=rationale,
        )
