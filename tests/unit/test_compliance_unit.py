"""Unit tests for MNPI Compliance System (Fact Checker, Arbiter, and Schemas)."""

from __future__ import annotations

import unittest
try:
    from app.workflow import build_mnpi_workflow, create_mnpi_runner, run_pipeline
    from app.schemas import ArbiterVerdict, FactCheckingDossier
except ImportError:
    from workflow import build_mnpi_workflow, create_mnpi_runner, run_pipeline
    from schemas import ArbiterVerdict, FactCheckingDossier


class TestMNPIComplianceSystem(unittest.TestCase):
    """Unit test suite validating Fact Checker tools, Arbiter 4-Test criteria, and verdicts."""

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

        self.assertIn("Project Titan", dossier.entities.internal_codenames_found)
        self.assertTrue(dossier.triggers.has_ma_triggers)
        self.assertEqual(dossier.triggers.highest_sensitivity, "CRITICAL")
        self.assertTrue(dossier.public_check.has_secrecy_markers)
        self.assertTrue(any("don't share" in m.lower() for m in dossier.public_check.linguistic_markers))
        self.assertFalse(dossier.public_check.is_publicly_verified)
        self.assertTrue(dossier.high_risk_signals_present)

        self.assertEqual(verdict.verdict, "MNPI_CONFIRMED")
        self.assertEqual(verdict.risk_level, "CRITICAL")
        self.assertEqual(verdict.recommended_action, "BLOCK_COMMUNICATION")
        self.assertGreaterEqual(verdict.materiality_test.score, 0.7)
        self.assertGreaterEqual(verdict.public_availability_test.score, 0.7)
        self.assertGreaterEqual(verdict.source_and_duty_test.score, 0.7)
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
        self.assertIn(verdict.verdict, ["POTENTIAL_MNPI", "MNPI_CONFIRMED"])
        self.assertIn(verdict.risk_level, ["HIGH", "CRITICAL"])
        self.assertIn(verdict.recommended_action, ["ESCALATE_TO_COMPLIANCE", "BLOCK_COMMUNICATION", "REDACT_AND_PROCEED"])

    def test_benign_routine_memo(self):
        """Test Case 4: Routine operational communication lacking materiality."""
        benign_text = (
            "Reminder to all team members: the quarterly facilities maintenance "
            "will take place this Saturday from 9 AM to 1 PM."
        )
        dossier, verdict = run_pipeline(benign_text)

        self.assertEqual(len(dossier.triggers.triggers), 0)
        self.assertFalse(dossier.high_risk_signals_present)
        self.assertIn(verdict.verdict, ["PUBLIC_NON_MATERIAL", "CLEARED"])
        self.assertEqual(verdict.risk_level, "LOW")
        self.assertEqual(verdict.recommended_action, "APPROVE_RELEASE")

    def test_agent_entrypoint_and_app_structure(self):
        """Validates that agent.py exports root_agent and app compatible with ADK deployment."""
        try:
            from app import agent
        except ImportError:
            import agent
        self.assertTrue(hasattr(agent, "root_agent"))
        self.assertTrue(hasattr(agent, "app"))
        self.assertEqual(agent.root_agent.name, "mnpi_compliance_workflow")
        self.assertEqual(agent.app.name, "mnpi_compliance_agent")

    def test_runtime_query_protocol(self):
        """Validates agent.runtime.query protocol returns compliant dictionary output."""
        try:
            from app.agent import runtime
        except ImportError:
            from agent import runtime
        res = runtime.query(text="Target announced earnings on CNBC.", log_to_bq=False)
        self.assertIsInstance(res, dict)
        self.assertIn("dossier", res)
        self.assertIn("verdict", res)


class TestTwoAgentArchitectureAndAudit(unittest.TestCase):
    """Test suite validating the 2 distinct agents and BigQuery audit function."""

    def test_two_distinct_agent_apps(self):
        """Validates that Fact Checker and Decision Authority exist as separate ADK Apps."""
        try:
            import app.agents.fact_checker as fc
            import app.agents.arbiter as da
            self.assertEqual(fc.create_fact_checker_agent().name, "fact_checker_agent")
            self.assertEqual(da.create_arbiter_agent().name, "arbiter_agent")
        except Exception:
            import agents.fact_checker as fc
            import agents.decision_authority as da
            self.assertEqual(fc.app.name, "mnpi_fact_checker_agent")
            self.assertEqual(da.app.name, "mnpi_decision_authority_agent")

    def test_arbiter_has_audit_tool(self):
        """Validates that Decision Authority Arbiter is equipped with the BigQuery audit tool."""
        try:
            from app.agents.arbiter import create_arbiter_agent
        except ImportError:
            from arbiter_agent import create_arbiter_agent
        arbiter = create_arbiter_agent()
        tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in arbiter.tools]
        self.assertIn("record_document_alignment_in_bigquery", tool_names)

    def test_bigquery_hash_computation(self):
        """Validates SHA-256 tamper-evident hash generation."""
        try:
            from app.audit_logger import compute_audit_hash
        except ImportError:
            from audit_logger import compute_audit_hash
        h1 = compute_audit_hash("memo1.txt", "Confidential text", "MNPI_CONFIRMED")
        h2 = compute_audit_hash("memo1.txt", "Confidential text", "MNPI_CONFIRMED")
        h3 = compute_audit_hash("memo1.txt", "Altered text", "MNPI_CONFIRMED")
        self.assertTrue(h1.startswith("sha256:"))
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_agent1_fact_checker_runtime(self):
        """Validates Agent 1 (Fact Checker) runtime execution and dossier output."""
        try:
            from app.agents.fact_checker import MNPIFactCheckerRuntime
        except ImportError:
            from agents.fact_checker.runtime import MNPIFactCheckerRuntime
        fc = MNPIFactCheckerRuntime()
        leak_text = "Project Titan acquiring Beta Corp next week for $3B."
        dossier_dict = fc.query(text=leak_text)
        self.assertIsInstance(dossier_dict, dict)
        self.assertIn("entities", dossier_dict)
        self.assertIn("triggers", dossier_dict)
        self.assertIn("public_check", dossier_dict)
        self.assertTrue(dossier_dict["high_risk_signals_present"])

    def test_agent2_decision_authority_runtime_with_dossier(self):
        """Validates Agent 2 (Decision Authority) runtime consuming Agent 1 dossier."""
        try:
            from app.agents.fact_checker import MNPIFactCheckerRuntime
            from app.agents.arbiter import MNPIDecisionAuthorityRuntime
        except ImportError:
            from agents.fact_checker.runtime import MNPIFactCheckerRuntime
            from agents.decision_authority.runtime import MNPIDecisionAuthorityRuntime
        fc = MNPIFactCheckerRuntime()
        da = MNPIDecisionAuthorityRuntime()
        text = "Don't tell anyone, but Project Titan is acquiring Beta Corp for $3B."
        dossier_dict = fc.query(text=text)
        verdict_dict = da.query(text=text, dossier=dossier_dict, log_to_bq=False)
        self.assertIsInstance(verdict_dict, dict)
        self.assertEqual(verdict_dict["verdict"], "MNPI_CONFIRMED")
        self.assertEqual(verdict_dict["risk_level"], "CRITICAL")
        self.assertIn("materiality_test", verdict_dict)

    def test_agent2_decision_authority_runtime_standalone(self):
        """Validates Agent 2 standalone execution autonomously invoking Agent 1 when dossier is None."""
        try:
            from app.agents.arbiter import MNPIDecisionAuthorityRuntime
        except ImportError:
            from agents.decision_authority.runtime import MNPIDecisionAuthorityRuntime
        da = MNPIDecisionAuthorityRuntime()
        text = "Target announced quarterly earnings on CNBC yesterday."
        verdict_dict = da.query(text=text, dossier=None, log_to_bq=False)
        self.assertIsInstance(verdict_dict, dict)
        self.assertEqual(verdict_dict["verdict"], "CLEARED")

    def test_run_two_agent_pipeline_handoff(self):
        """Validates sequential two-agent pipeline with explicit results handoff."""
        try:
            from app.workflow import run_two_agent_pipeline
        except ImportError:
            from workflow import run_two_agent_pipeline
        text = "Project Apollo launch scheduled for next month."
        dossier, verdict = run_two_agent_pipeline(text, log_to_bq=False)
        self.assertIsNotNone(dossier)
        self.assertIsNotNone(verdict)
        self.assertIn("entities", dossier.model_dump())
        self.assertIn("materiality_test", verdict.model_dump())


if __name__ == "__main__":
    unittest.main(verbosity=2)
