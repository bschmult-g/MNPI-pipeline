"""BigQuery Document Alignment Audit Tool for MNPI Agents.

Enables the Decision Authority Arbiter agent or compliance workflows to directly record
document evaluation results into BigQuery table `mnpi_compliance_audit.document_alignment_log`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from audit_logger import (
    get_bigquery_client,
    get_table_full_id,
    compute_audit_hash,
)
from datetime import datetime, timezone
from config import settings

logger = logging.getLogger(__name__)


def record_document_alignment_in_bigquery(
    document_name: str,
    verdict: str,
    risk_level: str,
    recommended_action: str,
    materiality_score: float,
    public_availability_score: float,
    source_duty_score: float,
    harm_score: float,
    summary_justification: str,
    channel: str = "quarantine_gcs",
    entities_detected: str = "",
    triggers_detected: str = "",
    has_secrecy_markers: bool = False,
    redacted_preview: str = "",
    latency_ms: float = 0.0,
) -> Dict[str, Any]:
    """Records a document compliance arbitration verdict and alignment scores into Google Cloud BigQuery.

    Args:
        document_name: Name or URI of the evaluated document (e.g. 'merger_memo.txt').
        verdict: Final arbitration verdict ('MNPI_CONFIRMED', 'POTENTIAL_MNPI', 'PUBLIC_NON_MATERIAL', 'CLEARED').
        risk_level: Assessed risk level ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW').
        recommended_action: Enforced compliance action ('BLOCK_COMMUNICATION', 'ESCALATE_TO_COMPLIANCE', 'APPROVE_RELEASE').
        materiality_score: Score from 0.0 to 1.0 for the Materiality Test.
        public_availability_score: Score from 0.0 to 1.0 for the Public Availability Test.
        source_duty_score: Score from 0.0 to 1.0 for the Source & Duty Test.
        harm_score: Score from 0.0 to 1.0 for the Actionability / Harm Test.
        summary_justification: Legal and compliance rationale supporting the verdict.
        channel: Ingestion channel ('quarantine_gcs', 'slack', 'email', 'zoom', 'upload').
        entities_detected: Comma-separated list of identified corporate entities or project codenames.
        triggers_detected: Comma-separated list of detected corporate catalysts.
        has_secrecy_markers: Whether linguistic confidentiality cues ('don't share') were detected.
        redacted_preview: Snippet of the sanitized/redacted document.
        latency_ms: Execution duration in milliseconds.

    Returns:
        Dictionary containing BigQuery recording status, table ID, and SHA-256 audit hash.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    audit_hash = compute_audit_hash(document_name, summary_justification, verdict)

    record = {
        "timestamp": now_iso,
        "document_name": document_name,
        "channel": channel,
        "verdict": verdict,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "materiality_score": float(materiality_score),
        "public_availability_score": float(public_availability_score),
        "source_duty_score": float(source_duty_score),
        "harm_score": float(harm_score),
        "entities_detected": entities_detected,
        "triggers_detected": triggers_detected,
        "has_secrecy_markers": bool(has_secrecy_markers),
        "audit_hash": audit_hash,
        "summary_justification": summary_justification,
        "redacted_preview": (redacted_preview or "")[:500],
        "latency_ms": float(latency_ms),
        "model_used": settings.default_model,
    }

    client = get_bigquery_client()
    table_id = get_table_full_id(project=client.project if client else None)
    bq_logged = False
    error_msg = None

    if client:
        try:
            errors = client.insert_rows_json(table_id, [record])
            if not errors:
                bq_logged = True
            else:
                error_msg = f"Insert errors: {errors}"
        except Exception as e:
            error_msg = str(e)

    return {
        "status": "RECORDED" if bq_logged else "LOGGED_LOCALLY",
        "bigquery_logged": bq_logged,
        "table_id": table_id,
        "audit_hash": audit_hash,
        "timestamp": now_iso,
        "document_name": document_name,
        "verdict": verdict,
        "error": error_msg,
    }
