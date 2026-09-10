"""Unit Tests for Advanced RL & Causal Attribution (LOO) Engine v2.0.

Tests:
1. Hierarchical Ablation Trigger:
   - S_full < 0.40: skips ablation (low confidence / benign)
   - S_full > 0.85: skips ablation (high confidence / decisive violation)
   - 0.40 <= S_full <= 0.85: triggers deep ablation
2. Joint Ablation Manager & Causal Overdetermination:
   - Sequential single-token LOO delta evaluation
   - Joint cluster masking detects overdetermined multi-leak violations
3. Multi-Objective Compliance Reward Shaping:
   - Compliant blocking yields positive reward R_total > 0
   - Unredacted leaks trigger lambda_veto = -10.0 penalty
   - Conservative bias / false positive on public news triggers R_fp = -4.0 penalty
   - Causal data influence penalty -gamma * S
4. DPO Preference Dataset Synthesizer & Margin Filter:
   - Enforces minimum margin Delta R >= 2.5
   - Filters out pairs below threshold
   - Generates and exports compliant JSONL datasets
5. Standardized Verification Codes in Arbiter Verdicts:
   - MaterialityCode, MosaicCode, DutyCode, HarmCode
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from app.causal_engine import HierarchicalAblationTrigger, JointAblationManager
from app.rl_engine import (
    CODE_WEIGHTS,
    ComplianceRewardEngine,
    DPOPreferenceDatasetBuilder,
    RewardWeightsConfig,
    get_active_weights,
    reset_active_weights,
    set_active_weights,
)
from app.schemas import (
    ArbiterVerdict,
    CriteriaAssessment,
    DutyCode,
    HarmCode,
    MaterialityCode,
    MosaicCode,
)
from app.workflow import run_offline_arbiter, run_offline_fact_checker


class TestHierarchicalAblationTrigger(unittest.TestCase):
    """Validates latency-optimized hierarchical trigger rules."""

    def test_low_confidence_bypass(self):
        """Scores < 0.40 bypass ablation as benign/public."""
        should_ablate, mode, rationale = HierarchicalAblationTrigger.evaluate(0.25)
        self.assertFalse(should_ablate)
        self.assertEqual(mode, "skipped_low_confidence")
        self.assertIn("cleared as benign", rationale)

    def test_high_confidence_bypass(self):
        """Scores > 0.85 bypass ablation as decisive violation."""
        should_ablate, mode, rationale = HierarchicalAblationTrigger.evaluate(0.92)
        self.assertFalse(should_ablate)
        self.assertEqual(mode, "skipped_high_confidence")
        self.assertIn("Violation is decisively certain", rationale)

    def test_borderline_confidence_trigger(self):
        """Scores in [0.40, 0.85] trigger the causal engine."""
        for score in [0.40, 0.55, 0.70, 0.85]:
            should_ablate, mode, rationale = HierarchicalAblationTrigger.evaluate(score)
            self.assertTrue(should_ablate)
            self.assertEqual(mode, "borderline_triggered")
            self.assertIn("Borderline confidence detected", rationale)


class TestJointAblationManager(unittest.TestCase):
    """Validates Leave-One-Out (LOO) counterfactual and joint cluster masking."""

    def test_single_token_loo_ablation(self):
        """Validates that a single dominant token produces a high marginal delta."""
        text = "The board is planning Project Titan for upcoming strategic expansion."
        dossier = run_offline_fact_checker(text)

        causal = JointAblationManager.evaluate_causal_attribution(
            text=text,
            dossier=dossier,
            base_violation_score=0.65,
        )
        self.assertIn(causal.ablation_mode, ("single_token_loo", "joint_cluster"))
        self.assertGreater(causal.data_influence_score, 0.0)
        self.assertTrue(causal.is_causally_dominant)

    def test_multi_leak_causal_overdetermination(self):
        """Validates that when multiple redundant leaks exist, joint cluster ablation detects overdetermination."""
        text = "Finalizing Project Titan to acquire TechCo for $2.4B."

        # Redundant scoring function: single token mask leaves score high (0.70), but masking all drops to 0.05
        def overdetermined_eval(t: str) -> float:
            lower = t.lower()
            unmasked_signals = 0
            if "project titan" in lower:
                unmasked_signals += 1
            if "acquire" in lower:
                unmasked_signals += 1
            if "$2.4b" in lower:
                unmasked_signals += 1

            if unmasked_signals >= 2:
                return 0.75
            elif unmasked_signals == 1:
                return 0.65  # masking one token barely drops score (delta = 0.10 < 0.15)
            else:
                return 0.05  # all masked -> drops to 0.05

        causal = JointAblationManager.evaluate_causal_attribution(
            text=text,
            eval_score_fn=overdetermined_eval,
            base_violation_score=0.75,
        )
        self.assertEqual(causal.ablation_mode, "joint_cluster")
        self.assertTrue(causal.is_overdetermined)
        self.assertTrue(causal.is_causally_dominant)
        self.assertGreaterEqual(causal.joint_influence_score, 0.45)

    def test_high_confidence_bypass_metrics(self):
        """Validates that skipped high confidence scores construct valid metrics without running full LOO."""
        causal = JointAblationManager.evaluate_causal_attribution(
            text="Project Titan is acquiring TechCo.",
            base_violation_score=0.95,
        )
        self.assertEqual(causal.ablation_mode, "skipped_high_confidence")
        self.assertTrue(causal.is_causally_dominant)
        self.assertGreater(causal.data_influence_score, 0.5)


class TestComplianceRewardEngine(unittest.TestCase):
    """Validates multi-objective RL reward shaping and anti-conservative bias penalties."""

    def test_compliant_mitigation_reward_positive(self):
        """A properly identified and blocked MNPI leak receives a positive shaped reward."""
        leak_text = "Don't share this yet, but we are finalizing Project Titan to acquire TechCo for $2.4B."
        dossier = run_offline_fact_checker(leak_text)
        verdict = run_offline_arbiter(dossier)

        metrics = ComplianceRewardEngine.calculate_reward(verdict, dossier, verdict.causal_attribution)
        self.assertGreater(metrics.total_reward, 0.0)
        self.assertEqual(metrics.veto_penalty, 0.0)
        self.assertEqual(metrics.fp_penalty, 0.0)

    def test_unredacted_leak_veto_penalty(self):
        """Allowing an unredacted MNPI leak triggers the lambda_veto = -10.0 penalty."""
        leak_text = "Don't share this yet, but we are finalizing Project Titan to acquire TechCo for $2.4B."
        dossier = run_offline_fact_checker(leak_text)
        verdict = run_offline_arbiter(dossier)

        # Corrupt verdict: approve release of actual leak
        verdict.recommended_action = "APPROVE_RELEASE"
        verdict.verdict = "CLEARED"

        metrics = ComplianceRewardEngine.calculate_reward(verdict, dossier, verdict.causal_attribution)
        self.assertEqual(metrics.veto_penalty, -10.0)
        self.assertLess(metrics.total_reward, 0.0)

    def test_conservative_bias_false_positive_penalty(self):
        """Blocking verified public news triggers the R_fp = -4.0 false positive penalty."""
        pub_text = "Target publicly reported Q2 financial results on August 21, confirming 2.7% comparable sales growth."
        dossier = run_offline_fact_checker(pub_text)
        verdict = run_offline_arbiter(dossier)

        # Corrupt verdict: hyper-conservatively block verified public news
        verdict.recommended_action = "BLOCK_COMMUNICATION"
        verdict.verdict = "MNPI_CONFIRMED"

        metrics = ComplianceRewardEngine.calculate_reward(verdict, dossier, verdict.causal_attribution)
        self.assertEqual(metrics.fp_penalty, -4.0)
        self.assertLess(metrics.total_reward, 0.0)

    def test_dynamically_adjustable_weights_override(self):
        """Validates that custom RewardWeightsConfig dynamically modifies penalties and rewards."""
        custom_weights = RewardWeightsConfig(
            r_task=2.5,
            lambda_veto=-20.0,
            false_positive_penalty=-8.0,
            gamma_causal=3.5,
        )

        leak_text = "Don't share this yet, but we are finalizing Project Titan to acquire TechCo for $2.4B."
        dossier = run_offline_fact_checker(leak_text)
        verdict = run_offline_arbiter(dossier)
        verdict.recommended_action = "APPROVE_RELEASE"
        verdict.verdict = "CLEARED"

        metrics = ComplianceRewardEngine.calculate_reward(
            verdict,
            dossier,
            verdict.causal_attribution,
            weights=custom_weights,
        )
        self.assertEqual(metrics.veto_penalty, -20.0)
        self.assertEqual(metrics.task_reward, 2.5)

    def test_global_active_weights_and_reset(self):
        """Validates set_active_weights modifies pipeline behavior and reset_active_weights restores defaults."""
        try:
            set_active_weights({"lambda_veto": -18.0, "false_positive_penalty": -6.5})
            active = get_active_weights()
            self.assertEqual(active.lambda_veto, -18.0)
            self.assertEqual(active.false_positive_penalty, -6.5)

            leak_text = "Don't share this yet, but we are finalizing Project Titan to acquire TechCo for $2.4B."
            dossier = run_offline_fact_checker(leak_text)
            verdict = run_offline_arbiter(dossier)
            verdict.recommended_action = "APPROVE_RELEASE"
            verdict.verdict = "CLEARED"

            metrics = ComplianceRewardEngine.calculate_reward(verdict, dossier, verdict.causal_attribution)
            self.assertEqual(metrics.veto_penalty, -18.0)
        finally:
            reset_active_weights()
            restored = get_active_weights()
            self.assertEqual(restored.lambda_veto, -10.0)
            self.assertEqual(restored.false_positive_penalty, -4.0)


class TestDPOPreferenceDatasetBuilder(unittest.TestCase):
    """Validates DPO pair synthesis, filtering by minimum margin Delta R >= 2.5, and JSONL export."""

    def test_minimum_margin_filter_enforcement(self):
        """Pairs with Delta R < 2.5 are rejected; pairs with Delta R >= 2.5 are accepted."""
        builder = DPOPreferenceDatasetBuilder(min_margin=2.5)

        leak_text = "Don't share this yet, but we are finalizing Project Titan to acquire TechCo for $2.4B."
        dossier = run_offline_fact_checker(leak_text)
        win_verdict = run_offline_arbiter(dossier)

        # Construct candidate with high delta R (should be accepted)
        lose_verdict_bad = run_offline_arbiter(dossier)
        lose_verdict_bad.verdict = "CLEARED"
        lose_verdict_bad.recommended_action = "APPROVE_RELEASE"

        accepted = builder.add_candidate_pair(
            prompt=leak_text,
            winning_verdict=win_verdict,
            losing_verdict=lose_verdict_bad,
            dossier=dossier,
        )
        self.assertTrue(accepted)
        self.assertEqual(len(builder.preference_pairs), 1)

        # Construct candidate with tiny delta R < 2.5 (should be rejected)
        lose_verdict_close = win_verdict.model_copy(deep=True)
        # Identical verdicts -> Delta R = 0.0
        rejected = builder.add_candidate_pair(
            prompt=leak_text,
            winning_verdict=win_verdict,
            losing_verdict=lose_verdict_close,
            dossier=dossier,
        )
        self.assertFalse(rejected)
        self.assertEqual(builder.rejected_pairs_count, 1)

    def test_benchmark_dpo_dataset_generation_and_export(self):
        """Validates end-to-end generation and serialization to JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "dpo_test_dataset.jsonl")
            count, path = DPOPreferenceDatasetBuilder.generate_benchmark_dpo_dataset(output_filepath=out_file)

            self.assertGreaterEqual(count, 2)
            self.assertTrue(os.path.exists(path))

            # Verify JSONL lines schema
            with open(path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]

            self.assertEqual(len(lines), count)
            for entry in lines:
                self.assertIn("prompt", entry)
                self.assertIn("chosen", entry)
                self.assertIn("rejected", entry)
                self.assertIn("reward_margin", entry)
                self.assertGreaterEqual(entry["reward_margin"], 2.5)
                self.assertGreater(entry["reward_win"], 0.0)
                self.assertLess(entry["reward_lose"], 0.0)


class TestStandardizedVerificationCodes(unittest.TestCase):
    """Validates that standardized codes are populated across Arbiter verdicts and criteria."""

    def test_verification_codes_in_offline_verdict(self):
        """Verifies all 4 tests populate machine-enforceable verification codes."""
        text = "Don't share this yet, but we are finalizing Project Titan to acquire TechCo for $2.4B."
        dossier = run_offline_fact_checker(text)
        verdict = run_offline_arbiter(dossier)

        self.assertIsNotNone(verdict.materiality_test.code)
        self.assertIsNotNone(verdict.public_availability_test.code)
        self.assertIsNotNone(verdict.source_and_duty_test.code)
        self.assertIsNotNone(verdict.actionability_harm_test.code)

        self.assertEqual(verdict.materiality_test.code, MaterialityCode.MAT_01_MARKET_MOVING_MA.value)
        self.assertEqual(verdict.public_availability_test.code, MosaicCode.MOSAIC_02_CONFIRMED_NON_PUBLIC.value)
        self.assertEqual(verdict.source_and_duty_test.code, DutyCode.DUTY_01_EXPLICIT_SECRECY_MARKER.value)
        self.assertEqual(verdict.actionability_harm_test.code, HarmCode.HARM_01_FRONT_RUNNING_EXPOSURE.value)

        self.assertIn(MaterialityCode.MAT_01_MARKET_MOVING_MA.value, verdict.verification_codes)
        self.assertIsNotNone(verdict.causal_attribution)
        self.assertIsNotNone(verdict.rl_metrics)


if __name__ == "__main__":
    unittest.main(verbosity=2)
