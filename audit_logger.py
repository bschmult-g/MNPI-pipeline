"""BigQuery Audit Logger for MNPI Document Alignment.

Records compliance arbitration results, risk classifications, 4 Assessment Criteria scores,
and SHA-256 tamper-evident integrity hashes into Google Cloud BigQuery:
- Project: green-carrier-500109-k2
- Dataset: mnpi_compliance_audit
- Table: document_alignment_log
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.cloud import bigquery
from google.oauth2.credentials import Credentials

from config import settings
from schemas import ArbiterVerdict, FactCheckingDossier

logger = logging.getLogger(__name__)

DEFAULT_DATASET = "mnpi_compliance_audit"
DEFAULT_TABLE = "document_alignment_log"


def get_bigquery_client() -> Optional[bigquery.Client]:
    """Returns an authenticated BigQuery client prioritizing gcloud token, then ADC."""
    project = settings.project_id

    # 1. Prioritize gcloud CLI access token for workstation and local runs
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if token:
            creds = Credentials(token)
            return bigquery.Client(project=project, credentials=creds)
    except Exception as e:
        logger.debug(f"gcloud access token notice for BigQuery: {e}")

    # 2. Fallback to standard Application Default Credentials (e.g., CI/CD or Cloud Run)
    try:
        return bigquery.Client(project=project)
    except Exception as err:
        logger.warning(f"Unable to initialize BigQuery client via ADC: {err}")

    return None


def get_table_full_id(
    project: Optional[str] = None,
    dataset: Optional[str] = None,
    table: Optional[str] = None,
) -> str:
    """Returns the fully-qualified BigQuery table ID."""
    p = project or settings.project_id
    d = dataset or os.getenv("BIGQUERY_DATASET", DEFAULT_DATASET)
    t = table or os.getenv("BIGQUERY_TABLE", DEFAULT_TABLE)
    return f"{p}.{d}.{t}"


def ensure_audit_table(client: Optional[bigquery.Client] = None) -> bool:
    """Ensures that the BigQuery dataset and audit table exist with the required schema."""
    bq_client = client or get_bigquery_client()
    if not bq_client:
        logger.warning("BigQuery client not available; skipping table verification.")
        return False

    project = bq_client.project
    dataset_id = f"{project}.{os.getenv('BIGQUERY_DATASET', DEFAULT_DATASET)}"
    table_id = get_table_full_id(project=project)

    try:
        # 1. Ensure dataset exists
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "US"
        bq_client.create_dataset(dataset, exists_ok=True)

        # 2. Define schema
        schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("document_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("channel", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("verdict", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("risk_level", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("recommended_action", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("materiality_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("public_availability_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("source_duty_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("harm_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("entities_detected", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("triggers_detected", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("has_secrecy_markers", "BOOLEAN", mode="NULLABLE"),
            bigquery.SchemaField("audit_hash", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("summary_justification", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("redacted_preview", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("latency_ms", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("model_used", "STRING", mode="NULLABLE"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        bq_client.create_table(table, exists_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error ensuring BigQuery audit table {table_id}: {e}", exc_info=True)
        return False


def compute_audit_hash(document_name: str, raw_text: str, verdict_str: str) -> str:
    """Generates a SHA-256 cryptographic audit digest ensuring tamper-evident alignment."""
    hasher = hashlib.sha256()
    hasher.update(document_name.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(raw_text.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(verdict_str.encode("utf-8"))
    return f"sha256:{hasher.hexdigest()}"


def log_document_alignment_to_bq(
    document_name: str,
    verdict: ArbiterVerdict,
    channel: str = "quarantine_gcs",
    latency_ms: float = 0.0,
    raw_text: str = "",
    dossier: Optional[FactCheckingDossier] = None,
    client: Optional[bigquery.Client] = None,
) -> Dict[str, Any]:
    """Logs document compliance alignment and verdict to BigQuery."""
    audit_hash = compute_audit_hash(document_name, raw_text, verdict.verdict)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Extract entities and triggers string representation from dossier if present
    entities_str = ""
    triggers_str = ""
    has_secrecy = False
    if dossier:
        try:
            entities_names = [e.name for e in dossier.entity_extraction.entities]
            entities_str = ", ".join(entities_names)
            trigger_terms = [t.term for t in dossier.trigger_detection.triggers]
            triggers_str = ", ".join(trigger_terms)
            has_secrecy = bool(dossier.public_check.has_secrecy_markers)
        except Exception as ex:
            logger.debug(f"Error extracting entities/triggers for audit row: {ex}")

    redacted_preview = (verdict.redacted_text or "")[:500]

    record = {
        "timestamp": now_iso,
        "document_name": document_name,
        "channel": channel,
        "verdict": verdict.verdict,
        "risk_level": verdict.risk_level,
        "recommended_action": verdict.recommended_action,
        "materiality_score": float(verdict.materiality_test.score),
        "public_availability_score": float(verdict.public_availability_test.score),
        "source_duty_score": float(verdict.source_and_duty_test.score),
        "harm_score": float(verdict.actionability_harm_test.score),
        "entities_detected": entities_str,
        "triggers_detected": triggers_str,
        "has_secrecy_markers": has_secrecy,
        "audit_hash": audit_hash,
        "summary_justification": verdict.summary_justification,
        "redacted_preview": redacted_preview,
        "latency_ms": float(latency_ms),
        "model_used": settings.default_model,
    }

    bq_client = client or get_bigquery_client()
    table_id = get_table_full_id(project=bq_client.project if bq_client else None)
    bq_logged = False
    bq_error = None

    if bq_client:
        try:
            errors = bq_client.insert_rows_json(table_id, [record])
            if errors:
                bq_error = f"Insert rows error: {errors}"
                logger.error(f"BigQuery streaming insert failed: {bq_error}")
            else:
                bq_logged = True
                logger.info(f"Successfully logged document alignment to BigQuery: {document_name} -> {table_id}")
        except Exception as e:
            bq_error = str(e)
            logger.warning(f"BigQuery log attempt failed for {document_name}: {e}")

    # Also mirror locally into audit_log.json for offline resilience
    local_log_path = Path(__file__).resolve().parent / "quarantine_bucket" / "audit_log.json"
    try:
        local_log_path.parent.mkdir(parents=True, exist_ok=True)
        records = []
        if local_log_path.exists():
            try:
                records = json.loads(local_log_path.read_text(encoding="utf-8"))
            except Exception:
                records = []
        records.insert(0, record)
        records = records[:200]
        local_log_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    except Exception as local_err:
        logger.debug(f"Local audit log mirror notice: {local_err}")

    return {
        "logged_to_bigquery": bq_logged,
        "table_id": table_id,
        "audit_hash": audit_hash,
        "timestamp": now_iso,
        "error": bq_error,
        "record": record,
    }


def fetch_document_alignment_logs(
    limit: int = 50,
    client: Optional[bigquery.Client] = None,
) -> List[Dict[str, Any]]:
    """Queries BigQuery for historical document alignment logs."""
    bq_client = client or get_bigquery_client()
    table_id = get_table_full_id(project=bq_client.project if bq_client else None)

    if bq_client:
        try:
            query = f"""
            SELECT
                timestamp,
                document_name,
                channel,
                verdict,
                risk_level,
                recommended_action,
                materiality_score,
                public_availability_score,
                source_duty_score,
                harm_score,
                entities_detected,
                triggers_detected,
                has_secrecy_markers,
                audit_hash,
                summary_justification,
                redacted_preview,
                latency_ms,
                model_used
            FROM `{table_id}`
            ORDER BY timestamp DESC
            LIMIT {limit}
            """
            query_job = bq_client.query(query)
            rows = list(query_job.result())
            results = []
            for r in rows:
                row_dict = dict(r)
                if isinstance(row_dict.get("timestamp"), datetime):
                    row_dict["timestamp"] = row_dict["timestamp"].isoformat()
                results.append(row_dict)
            return results
        except Exception as e:
            logger.warning(f"Failed to query BigQuery audit logs: {e}")

    # Fallback to local mirror
    local_log_path = Path(__file__).resolve().parent / "quarantine_bucket" / "audit_log.json"
    if local_log_path.exists():
        try:
            return json.loads(local_log_path.read_text(encoding="utf-8"))[:limit]
        except Exception:
            return []

    return []
