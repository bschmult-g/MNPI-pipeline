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


if __name__ == "__main__":
    unittest.main(verbosity=2)


