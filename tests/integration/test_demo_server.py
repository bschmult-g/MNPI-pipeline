"""Integration tests for the ingestion simulator FastAPI server and BigQuery audit pipeline."""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient
from demo_server import app


class TestDemoServer(unittest.TestCase):
    """Integration tests for the ingestion simulator FastAPI server."""

    @classmethod
    def setUpClass(cls):
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

    def test_upload_pdf_document(self):
        """Validates PDF upload, binary staging, and text extraction."""
        sample_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
            b"4 0 obj<</Length 75>>stream\n"
            b"BT\n"
            b"/F1 12 Tf\n"
            b"72 712 Td\n"
            b"(Project Titan secret acquisition memo in PDF format) Tj\n"
            b"ET\n"
            b"endstream\n"
            b"endobj\n"
            b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n0000000230 00000 n \n0000000355 00000 n \n"
            b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n423\n%%EOF\n"
        )
        files = {"file": ("test_memo_upload.pdf", sample_pdf, "application/pdf")}
        resp = self.client.post("/api/upload", files=files, data={"channel": "email"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "QUARANTINED")
        self.assertIn("Project Titan secret acquisition memo", data["text"])
        self.assertEqual(data["bytes"], len(sample_pdf))

    def test_upload_docx_document(self):
        """Validates DOCX upload, binary staging, and text extraction."""
        import io
        import docx
        doc = docx.Document()
        doc.add_paragraph("Confidential Q3 acquisition draft for Project Titan.")
        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        files = {"file": ("test_memo_upload.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        resp = self.client.post("/api/upload", files=files, data={"channel": "slack"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "QUARANTINED")
        self.assertIn("Confidential Q3 acquisition draft for Project Titan", data["text"])
        self.assertEqual(data["bytes"], len(docx_bytes))

    def test_upload_unsupported_extension(self):
        """Validates rejection of unsupported file extensions."""
        files = {"file": ("payload.exe", b"binary content", "application/octet-stream")}
        resp = self.client.post("/api/upload", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file extension", resp.json()["detail"])

    def test_upload_oversized_file(self):
        """Validates rejection of files exceeding 15MB limit."""
        large_bytes = b"0" * (15 * 1024 * 1024 + 10)
        files = {"file": ("huge_doc.txt", large_bytes, "text/plain")}
        resp = self.client.post("/api/upload", files=files)
        self.assertEqual(resp.status_code, 413)
        self.assertIn("exceeds maximum allowed size of 15MB", resp.json()["detail"])

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
        self.assertTrue(data["audit"]["logged_to_bigquery"] or data["audit"].get("status") in ["COMPLETED", "RECORDED", "LOGGED_LOCALLY"])

    def test_audit_api_endpoints(self):
        """Validates BigQuery audit log status, schema, and query endpoints."""
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

        schema_resp = self.client.get("/api/audit/schema")
        self.assertEqual(schema_resp.status_code, 200)
        schema_data = schema_resp.json()
        self.assertIn("fields", schema_data)
        self.assertGreaterEqual(len(schema_data["fields"]), 18)

        logs_resp = self.client.get("/api/audit/logs")
        self.assertEqual(logs_resp.status_code, 200)
        logs_data = logs_resp.json()
        self.assertIn("records", logs_data)
        self.assertGreaterEqual(len(logs_data["records"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
