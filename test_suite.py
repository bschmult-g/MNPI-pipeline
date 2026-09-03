"""Comprehensive Unit & Integration Test Suite for MNPI Compliance System.

Tests the full pipeline against 4 real-world compliance scenarios:
1. Critical MNPI Leak (Acquisition + Secret Codename + "Don't share")
2. Confirmed Public News (Target Q2 public financial release)
3. Unannounced Roadmap Slip (Potential MNPI forward-looking milestone)
4. Benign Routine Memo (Immaterial operational chat)
"""

from __future__ import annotations

import unittest
from workflow import build_mnpi_workflow, create_mnpi_runner, run_pipeline
from schemas import ArbiterVerdict, FactCheckingDossier


class TestMNPIComplianceSystem(unittest.TestCase):
    """Test suite validating Fact Checker tools, Arbiter 4-Test criteria, and verdicts."""

    def test_adk_workflow_graph_structure(self):
        """Validates that the native Google ADK Workflow and Runner are constructed properly."""
        wf = build_mnpi_workflow()
        node_names = [n.name for n in wf.graph.nodes]
        self.assertIn("__START__", node_names)
        self.assertIn("fact_checker_agent", node_names)
        self.assertIn("arbiter_agent", node_names)

        runner = create_mnpi_runner(wf)
        self.assertIsNotNone(runner)

    def test_critical_mnpi_leak(self):
        """Test Case 1: High-stakes M&A leak with confidential codename and explicit secrecy marker."""
        leak_text = (
            "Don't share this yet, but we are finalizing Project Titan to acquire "
            "TechCo for $2.4B next Tuesday ahead of the upcoming Q3 earnings call."
        )

        dossier, verdict = run_pipeline(leak_text)

        # 1. Fact Checker Verifications
        self.assertIn("Project Titan", dossier.entities.internal_codenames_found)
        self.assertTrue(dossier.triggers.has_ma_triggers)
        self.assertEqual(dossier.triggers.highest_sensitivity, "CRITICAL")
        self.assertTrue(dossier.public_check.has_secrecy_markers)
        self.assertIn("don't share", dossier.public_check.linguistic_markers)
        self.assertFalse(dossier.public_check.is_publicly_verified)
        self.assertTrue(dossier.high_risk_signals_present)

        # 2. Arbiter 4-Test Assessment Verifications
        self.assertEqual(verdict.verdict, "MNPI_CONFIRMED")
        self.assertEqual(verdict.risk_level, "CRITICAL")
        self.assertEqual(verdict.recommended_action, "BLOCK_COMMUNICATION")

        # Check Test 1 (Materiality)
        self.assertGreaterEqual(verdict.materiality_test.score, 0.7)
        # Check Test 2 (Public Availability)
        self.assertGreaterEqual(verdict.public_availability_test.score, 0.7)
        # Check Test 3 (Source & Duty)
        self.assertGreaterEqual(verdict.source_and_duty_test.score, 0.7)
        # Check Test 4 (Actionability / Harm)
        self.assertGreaterEqual(verdict.actionability_harm_test.score, 0.7)

    def test_confirmed_public_news(self):
        """Test Case 2: Discussion of verified public financial filing."""
        public_text = (
            "Target publicly reported Q2 financial results on August 21, "
            "confirming 2.7% comparable sales growth and reaffirming full-year guidance."
        )

        dossier, verdict = run_pipeline(public_text)

        self.assertTrue(dossier.public_check.is_publicly_verified)
        self.assertFalse(dossier.public_check.has_secrecy_markers)
        self.assertEqual(verdict.verdict, "CLEARED")
        self.assertEqual(verdict.risk_level, "LOW")
        self.assertEqual(verdict.recommended_action, "APPROVE_RELEASE")
        self.assertLessEqual(verdict.public_availability_test.score, 0.3)

    def test_unannounced_roadmap_slip(self):
        """Test Case 3: Forward-looking roadmap delay without public disclosure."""
        roadmap_text = (
            "The executive committee decided that the roadmap feature release is slipping "
            "by two quarters to allow for architectural redesign."
        )

        dossier, verdict = run_pipeline(roadmap_text)

        self.assertTrue(dossier.triggers.has_roadmap_or_release_triggers)
        self.assertFalse(dossier.public_check.is_publicly_verified)
        self.assertEqual(verdict.verdict, "POTENTIAL_MNPI")
        self.assertEqual(verdict.risk_level, "HIGH")
        self.assertEqual(verdict.recommended_action, "ESCALATE_TO_COMPLIANCE")

    def test_benign_routine_memo(self):
        """Test Case 4: Routine operational communication lacking materiality."""
        benign_text = (
            "Reminder to all team members: the quarterly facilities maintenance "
            "will take place this Saturday from 9 AM to 1 PM."
        )

        dossier, verdict = run_pipeline(benign_text)

        self.assertEqual(len(dossier.triggers.triggers), 0)
        self.assertFalse(dossier.high_risk_signals_present)
        self.assertEqual(verdict.verdict, "PUBLIC_NON_MATERIAL")
        self.assertEqual(verdict.risk_level, "LOW")
        self.assertEqual(verdict.recommended_action, "APPROVE_RELEASE")

    def test_agent_entrypoint_and_app_structure(self):
        """Validates that agent.py exports root_agent and app compatible with ADK deployment."""
        import agent
        self.assertTrue(hasattr(agent, "root_agent"))
        self.assertTrue(hasattr(agent, "app"))
        self.assertEqual(agent.root_agent.name, "mnpi_compliance_workflow")
        self.assertEqual(agent.app.name, "mnpi_compliance_agent")


if __name__ == "__main__":
    unittest.main(verbosity=2)

