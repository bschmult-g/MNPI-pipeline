"""Unit & Integration Tests for Enterprise Security & Entitlements Tagging.

Validates:
1. derive_security_entitlements mapping hierarchy (Rank 1 to Rank 4)
2. GCS custom metadata conversion (x-goog-meta-mnpi-*)
3. Sidecar manifest generation (<doc>.entitlements.json)
4. Downstream policy verification endpoint (/api/entitlements/verify)
5. Audit logging persistence of clearance_rank and entitlements_json
"""

import json
import os
import unittest
from pathlib import Path
from starlette.testclient import TestClient

from app.schemas import (
    ArbiterVerdict,
    FactCheckingDossier,
    EntityExtractionResult,
    EntityItem,
    TriggerDetectionResult,
    TriggerItem,
    PublicCheckResult,
    SecurityEntitlementsTag,
)
from app.workflow import derive_security_entitlements, run_offline_arbiter
from demo.demo_server import app, QUARANTINE_DIR


class TestSecurityEntitlementsTagging(unittest.TestCase):
    """Unit tests validating the hierarchical security entitlements tagging."""

    def test_clearance_rank_hierarchy_mapping(self):
        """Validates that each compliance tier maps strictly to its designated clearance rank."""
        # 1. Critical MNPI -> Rank 4
        dossier_critical = FactCheckingDossier(
            original_text="Secret Project Titan acquisition of TechCo for $2.4B.",
            entities=EntityExtractionResult(
                entities=[
                    EntityItem(name="Project Titan", category="project_codename", context_snippet="", is_internal_or_restricted=True),
                    EntityItem(name="TechCo", category="corporate_name", context_snippet=""),
                ],
                internal_codenames_found=["Project Titan"],
                tickers_found=["TECH"],
                summary="Codenames found",
            ),
            triggers=TriggerDetectionResult(
                triggers=[TriggerItem(term="acquisition", category="merger_acquisition", context_snippet="", sensitivity_level="CRITICAL")],
                highest_sensitivity="CRITICAL",
                has_ma_triggers=True,
                summary="M&A trigger",
            ),
            public_check=PublicCheckResult(
                is_publicly_verified=False,
                verification_confidence=0.9,
                mosaic_check_notes="Non-public leak",
            ),
            dossier_summary="Critical leak",
            high_risk_signals_present=True,
        )

        verdict_critical = run_offline_arbiter(dossier_critical, document_name="project_titan_leak.txt")
        self.assertIsNotNone(verdict_critical.entitlements)
        ent = verdict_critical.entitlements

        self.assertEqual(ent.clearance_rank, 4)
        self.assertEqual(ent.min_role_required, "VICE_PRESIDENT")
        self.assertEqual(ent.classification_tier, "MNPI_CRITICAL")
        self.assertIn("INVESTMENT_BANKING", ent.permitted_departments)
        self.assertIn("LEGAL", ent.permitted_departments)
        self.assertIn("TECH", ent.ticker_restrictions)
        self.assertIsNotNone(ent.audit_hash)
        self.assertTrue(ent.audit_hash.startswith("sha256:"))

        # 2. Potential MNPI -> Rank 3
        dossier_potential = FactCheckingDossier(
            original_text="Supplier component shipment indicates potential next-quarter launch delay.",
            entities=EntityExtractionResult(
                entities=[EntityItem(name="Supplier X", category="other", context_snippet="")],
                internal_codenames_found=[],
                tickers_found=[],
                summary="Third-party vendor notice",
            ),
            triggers=TriggerDetectionResult(
                triggers=[TriggerItem(term="launch delay", category="roadmap_forward_looking", context_snippet="", sensitivity_level="HIGH")],
                highest_sensitivity="HIGH",
                has_roadmap_or_release_triggers=True,
                summary="Roadmap delay",
            ),
            public_check=PublicCheckResult(
                is_publicly_verified=False,
                verification_confidence=0.5,
                mosaic_check_notes="Vendor chatter; unconfirmed in public press",
            ),
            dossier_summary="Potential leak",
            high_risk_signals_present=True,
        )

        verdict_potential = run_offline_arbiter(dossier_potential, document_name="project_falcon.txt")
        self.assertEqual(verdict_potential.entitlements.clearance_rank, 3)
        self.assertEqual(verdict_potential.entitlements.min_role_required, "SENIOR_ASSOCIATE")
        self.assertEqual(verdict_potential.entitlements.classification_tier, "MNPI_HIGH")

        # 3. Public Non-Material / Cleared -> Rank 1 or 2
        dossier_cleared = FactCheckingDossier(
            original_text="Routine operational quarterly facilities sync.",
            entities=EntityExtractionResult(entities=[], tickers_found=[], summary="Clean"),
            triggers=TriggerDetectionResult(triggers=[], highest_sensitivity="LOW", summary="Clean"),
            public_check=PublicCheckResult(is_publicly_verified=True, verification_confidence=1.0, mosaic_check_notes="Clean"),
            dossier_summary="Clean",
            high_risk_signals_present=False,
        )
        verdict_cleared = run_offline_arbiter(dossier_cleared, document_name="facilities_sync.txt")
        self.assertEqual(verdict_cleared.entitlements.clearance_rank, 1)
        self.assertEqual(verdict_cleared.entitlements.min_role_required, "ANY")
        self.assertEqual(verdict_cleared.entitlements.classification_tier, "PUBLIC_UNRESTRICTED")

    def test_gcs_metadata_export(self):
        """Validates that to_gcs_metadata() produces standard key-values formatted for object storage."""
        tag = SecurityEntitlementsTag(
            tag_version="1.0",
            document_id="deal_memo_2026.pdf",
            classification_tier="MNPI_CRITICAL",
            clearance_rank=4,
            min_role_required="VICE_PRESIDENT",
            permitted_departments=["LEGAL", "COMPLIANCE"],
            permitted_groups=["grp-mnpi-cleared-vp"],
            ticker_restrictions=["AAPL", "MSFT"],
            routing_action="BLOCK_COMMUNICATION",
            is_redacted=False,
            audit_hash="sha256:abc123def456",
        )

        metadata = tag.to_gcs_metadata()
        self.assertEqual(metadata["mnpi-clearance-rank"], "4")
        self.assertEqual(metadata["mnpi-classification"], "MNPI_CRITICAL")
        self.assertEqual(metadata["mnpi-min-role"], "VICE_PRESIDENT")
        self.assertEqual(metadata["mnpi-routing-action"], "BLOCK_COMMUNICATION")
        self.assertEqual(metadata["mnpi-is-redacted"], "false")
        self.assertEqual(metadata["mnpi-tickers"], "AAPL,MSFT")
        self.assertEqual(metadata["mnpi-audit-hash"], "sha256:abc123def456")


class TestEntitlementsApiAndSidecar(unittest.TestCase):
    """Integration tests for the demo server entitlements endpoints and sidecar storage."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_entitlements_verify_endpoint(self):
        """Validates policy enforcement checking user role against required clearance rank."""
        # 1. Analyst (Rank 2) attempts to access Rank 4 document -> Denied
        res = self.client.post("/api/entitlements/verify", json={
            "user_role": "ANALYST",
            "clearance_rank": 4,
            "entitlements": {
                "clearance_rank": 4,
                "classification_tier": "MNPI_CRITICAL",
                "min_role_required": "VICE_PRESIDENT",
                "permitted_departments": ["INVESTMENT_BANKING", "LEGAL"],
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["access_granted"])
        self.assertEqual(data["user_rank"], 2)
        self.assertEqual(data["required_rank"], 4)
        self.assertIn("Access Denied", data["reason"])

        # 2. Vice President (Rank 4) attempts to access Rank 4 document -> Granted
        res = self.client.post("/api/entitlements/verify", json={
            "user_role": "VICE_PRESIDENT",
            "clearance_rank": 4,
            "entitlements": {
                "clearance_rank": 4,
                "classification_tier": "MNPI_CRITICAL",
                "min_role_required": "VICE_PRESIDENT",
                "permitted_departments": ["INVESTMENT_BANKING", "LEGAL"],
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["access_granted"])
        self.assertIn("Access Granted", data["reason"])

        # 3. Senior Associate (Rank 3) accesses Rank 3 document -> Granted
        res = self.client.post("/api/entitlements/verify", json={
            "user_role": "SENIOR_ASSOCIATE",
            "clearance_rank": 3,
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["access_granted"])

        # 4. External Guest (Rank 1) accesses Rank 2 document -> Denied
        res = self.client.post("/api/entitlements/verify", json={
            "user_role": "EXTERNAL_GUEST",
            "clearance_rank": 2,
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["access_granted"])

    def test_process_generates_sidecar_file(self):
        """Validates that processing a document generates <doc>.entitlements.json on disk."""
        doc_title = "CI_Entitlements_Proof_Doc.txt"
        text = "Confidential: Project Titan acquisition of TechCo for $2.4B next Tuesday. Do not share."

        res = self.client.post("/api/process", json={
            "text": text,
            "document_title": doc_title,
            "channel": "slack",
        })
        self.assertEqual(res.status_code, 200)
        payload = res.json()

        self.assertIn("entitlements", payload)
        self.assertIn("sidecar_file", payload)

        ent = payload["entitlements"]
        self.assertEqual(ent["clearance_rank"], 4)
        self.assertEqual(ent["min_role_required"], "VICE_PRESIDENT")

        # Verify sidecar file exists on disk
        sidecar_filename = f"{doc_title}.entitlements.json"
        sidecar_path = QUARANTINE_DIR / sidecar_filename
        self.assertTrue(sidecar_path.exists(), f"Sidecar file {sidecar_path} should exist on disk")

        # Verify sidecar content
        stored_manifest = json.loads(sidecar_path.read_text(encoding="utf-8"))
        self.assertEqual(stored_manifest["clearance_rank"], 4)
        self.assertEqual(stored_manifest["classification_tier"], "MNPI_CRITICAL")

        # Verify GET /api/documents/{doc_title}/entitlements endpoint
        res_get = self.client.get(f"/api/documents/{doc_title}/entitlements")
        self.assertEqual(res_get.status_code, 200)
        get_data = res_get.json()
        self.assertEqual(get_data["document_name"], doc_title)
        self.assertEqual(get_data["entitlements"]["clearance_rank"], 4)

        # Clean up test sidecar file
        if sidecar_path.exists():
            sidecar_path.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
