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
        self.assertTrue(any("don't share" in m.lower() for m in dossier.public_check.linguistic_markers))
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
        import agent
        self.assertTrue(hasattr(agent, "root_agent"))
        self.assertTrue(hasattr(agent, "app"))
        self.assertEqual(agent.root_agent.name, "mnpi_compliance_workflow")
        self.assertEqual(agent.app.name, "mnpi_compliance_agent")


class TestDemoServer(unittest.TestCase):
    """Integration tests for the ingestion simulator FastAPI server."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from demo_server import app
        cls.client = TestClient(app)

    def test_serve_index_html(self):
        """Validates that GET / serves the dashboard HTML."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("MNPI", resp.text)
        self.assertIn("Ingestion Producers", resp.text)

    def test_get_scenarios(self):
        """Validates that GET /api/scenarios returns the 4 preloaded scenarios."""
        resp = self.client.get("/api/scenarios")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data), 4)
        channels = [s["channel"] for s in data]
        self.assertIn("slack", channels)
        self.assertIn("zoom", channels)
        self.assertIn("email", channels)
        self.assertIn("salesforce", channels)

    def test_bucket_status(self):
        """Validates that GET /api/bucket/status returns bucket connection status."""
        resp = self.client.get("/api/bucket/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("mode", data)
        self.assertIn("bucket_name", data)
        self.assertIn("incoming/", data["bucket_uri"])

    def test_bucket_files_listing_and_fetch(self):
        """Validates simulated/live GCS bucket listing and fetching."""
        resp = self.client.get("/api/bucket/files")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("bucket", data)
        self.assertGreater(len(data["files"]), 0)

        # Test fetching the first file
        target_uri = data["files"][0]["gcs_uri"]
        fetch_resp = self.client.post("/api/bucket/fetch", json={"gcs_uri": target_uri})
        self.assertEqual(fetch_resp.status_code, 200)
        fetch_data = fetch_resp.json()
        self.assertIn("content", fetch_data)
        self.assertGreater(len(fetch_data["content"]), 0)

    def test_upload_document(self):
        """Validates document upload into Quarantine Holding Zone."""
        sample_bytes = b"[Zoom Transcript] Secret codename Project Titan test."
        files = {"file": ("test_transcript.txt", sample_bytes, "text/plain")}
        resp = self.client.post("/api/upload", files=files, data={"channel": "zoom"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "QUARANTINED")
        self.assertIn("/incoming/test_transcript.txt", data["quarantine_uri"])
        self.assertEqual(data["text"], sample_bytes.decode())

    def test_bucket_direct_upload(self):
        """Validates direct upload to GCS quarantine bucket."""
        sample_bytes = b"[Email Alert] Direct GCS upload validation payload."
        files = {"file": ("direct_upload_test.txt", sample_bytes, "text/plain")}
        resp = self.client.post("/api/bucket/upload", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "QUARANTINED")
        self.assertIn("/incoming/direct_upload_test.txt", data["gcs_uri"])
        self.assertEqual(data["text"], sample_bytes.decode())

    def test_process_document_routing(self):
        """Validates processing pipeline execution and routing assignment."""
        leak_text = "Don't share, but Project Titan is acquiring TechCo for $2.4B next Tuesday."
        resp = self.client.post("/api/process", json={
            "text": leak_text,
            "channel": "slack",
            "document_title": "M&A Leak Test",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["verdict"]["verdict"], "MNPI_CONFIRMED")
        self.assertEqual(data["routing"]["badge_variant"], "critical")
        self.assertIn("Scoped Use", data["routing"]["destination"])
        self.assertTrue(data["redaction_diff"]["is_redacted"])
        self.assertIn("audit", data)
        self.assertTrue(data["audit"]["logged_to_bigquery"] or data["audit"]["status"] in ["COMPLETED", "RECORDED", "LOGGED_LOCALLY"])

    def test_audit_api_endpoints(self):
        """Validates BigQuery audit log status, schema, and query endpoints."""
        # Ensure at least one test record exists so audit query is self-contained
        from audit_logger import log_document_alignment_to_bq
        from schemas import ArbiterVerdict, CriteriaAssessment
        sample_verdict = ArbiterVerdict(
            verdict="CLEARED",
            risk_level="LOW",
            materiality_test=CriteriaAssessment(
                test_name="Basic Inc. Materiality Test",
                passed_or_failed="CLEARED / NON-MATERIAL",
                score=0.1,
                rationale="Lacks market-moving significance.",
            ),
            public_availability_test=CriteriaAssessment(
                test_name="Mosaic Public Availability Test",
                passed_or_failed="PUBLIC",
                score=0.1,
                rationale="Publicly confirmed in disclosures.",
            ),
            source_and_duty_test=CriteriaAssessment(
                test_name="Chiarella / Dirks Duty Test",
                passed_or_failed="NO BREACH",
                score=0.0,
                rationale="No insider duty breached.",
            ),
            actionability_harm_test=CriteriaAssessment(
                test_name="Actionability / Harm Test",
                passed_or_failed="BENIGN",
                score=0.0,
                rationale="Negligible impact.",
            ),
            recommended_action="APPROVE_RELEASE",
            summary_justification="CI automated test validation record.",
            redacted_text="Test snippet",
        )
        log_document_alignment_to_bq(
            document_name="CI_Test_Verification.txt",
            raw_text="Routine CI verification snippet",
            verdict=sample_verdict,
            channel="ci_test",
        )

        status_resp = self.client.get("/api/audit/status")
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertIn("dataset", status_data)
        self.assertIn("table", status_data)
        self.assertIn("total_records", status_data)

        # Test schema endpoint
        schema_resp = self.client.get("/api/audit/schema")
        self.assertEqual(schema_resp.status_code, 200)
        schema_data = schema_resp.json()
        self.assertIn("fields", schema_data)
        self.assertEqual(len(schema_data["fields"]), 18)

        logs_resp = self.client.get("/api/audit/logs")
        self.assertEqual(logs_resp.status_code, 200)
        logs_data = logs_resp.json()
        self.assertIn("records", logs_data)
        self.assertGreaterEqual(len(logs_data["records"]), 1)


class TestTwoAgentArchitectureAndAudit(unittest.TestCase):
    """Test suite validating the 2 distinct agents and BigQuery audit function."""

    def test_two_distinct_agent_apps(self):
        """Validates that Fact Checker and Decision Authority exist as separate ADK Apps."""
        import agents.fact_checker as fc
        import agents.decision_authority as da

        self.assertEqual(fc.app.name, "mnpi_fact_checker_agent")
        self.assertEqual(fc.root_agent.name, "fact_checker_agent")
        self.assertEqual(da.app.name, "mnpi_decision_authority_agent")
        self.assertEqual(da.root_agent.name, "arbiter_agent")

    def test_arbiter_has_audit_tool(self):
        """Validates that Decision Authority Arbiter is equipped with the BigQuery audit tool."""
        from arbiter_agent import create_arbiter_agent
        arbiter = create_arbiter_agent()
        tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in arbiter.tools]
        self.assertIn("record_document_alignment_in_bigquery", tool_names)

    def test_bigquery_hash_computation(self):
        """Validates SHA-256 tamper-evident hash generation."""
        from audit_logger import compute_audit_hash
        h1 = compute_audit_hash("memo1.txt", "Confidential text", "MNPI_CONFIRMED")
        h2 = compute_audit_hash("memo1.txt", "Confidential text", "MNPI_CONFIRMED")
        h3 = compute_audit_hash("memo1.txt", "Altered text", "MNPI_CONFIRMED")
        self.assertTrue(h1.startswith("sha256:"))
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_agent1_fact_checker_runtime(self):
        """Validates Agent 1 (Fact Checker) runtime execution and dossier output."""
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
        from agents.decision_authority.runtime import MNPIDecisionAuthorityRuntime
        da = MNPIDecisionAuthorityRuntime()
        text = "Target announced quarterly earnings on CNBC yesterday."
        verdict_dict = da.query(text=text, dossier=None, log_to_bq=False)
        self.assertIsInstance(verdict_dict, dict)
        self.assertEqual(verdict_dict["verdict"], "CLEARED")

    def test_run_two_agent_pipeline_handoff(self):
        """Validates sequential two-agent pipeline with explicit results handoff."""
        from workflow import run_two_agent_pipeline
        text = "Project Apollo launch scheduled for next month."
        dossier, verdict = run_two_agent_pipeline(text, log_to_bq=False)
        self.assertIsNotNone(dossier)
        self.assertIsNotNone(verdict)
        self.assertIn("entities", dossier.model_dump())
        self.assertIn("materiality_test", verdict.model_dump())


if __name__ == "__main__":
    unittest.main(verbosity=2)



