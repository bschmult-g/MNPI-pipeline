"""Lightweight Demonstration Server for MNPI Ingestion, Routing, and Redaction.

Simulates the end-to-end flow from Ingestion Producers (Zoom, Slack, Email, Salesforce)
through the Quarantine Holding Zone (Cloud Storage) to the Two-Agent Platform
(Fact Checker & Arbiter), and final routing into Approved Assets (General vs. Scoped Use).

Compliant with secure web coding standards:
- Binds strictly to localhost (127.0.0.1)
- Validates file upload types and size limits
- Sanitizes file paths to prevent directory traversal
"""

from __future__ import annotations

import os
import re
import time
import logging
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr

from workflow import run_pipeline
from schemas import ArbiterVerdict, FactCheckingDossier
from audit_logger import (
    log_document_alignment_to_bq,
    fetch_document_alignment_logs,
    get_bigquery_client,
    get_table_full_id,
)
from config import settings

logger = logging.getLogger("mnpi_demo")
logging.basicConfig(level=logging.INFO)

# Root directory of this app
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
QUARANTINE_DIR = BASE_DIR / "quarantine_bucket" / "incoming"

app = FastAPI(
    title="MNPI Compliance Pipeline Ingestion Simulator",
    description="Interactive front end to demonstrate document ingestion, quarantine, arbitration, and redaction.",
    version="1.0.0",
)

# Ensure quarantine directory exists
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# Pydantic Request/Response Models
# ==============================================================================

class ProcessRequest(BaseModel):
    """Payload for processing a document through the arbitration pipeline."""
    text: constr(min_length=1, max_length=100000)
    channel: Literal["zoom", "slack", "email", "salesforce", "cloud_storage", "upload"] = "upload"
    document_title: str = Field(default="Untitled Document", max_length=200)
    source_uri: Optional[str] = Field(default=None, max_length=500)


class FetchBucketRequest(BaseModel):
    """Payload to fetch a file from a Google Cloud Storage bucket path."""
    gcs_uri: str = Field(..., description="URI in the format gs://bucket-name/path/to/file.txt")


class IngestionPreset(BaseModel):
    id: str
    channel: str
    title: str
    description: str
    expected_verdict: str
    sample_text: str


# ==============================================================================
# Pre-canned Scenarios (From Architecture Diagram)
# ==============================================================================

PRESET_SCENARIOS: List[IngestionPreset] = [
    IngestionPreset(
        id="scenario_slack_leak",
        channel="slack",
        title="Slack #deal-room: Project Titan M&A Leak",
        description="Internal corporate development channel leaking an unannounced $2.4B acquisition under a secret codename with explicit secrecy cues.",
        expected_verdict="MNPI_CONFIRMED (Critical Risk)",
        sample_text=(
            "[Slack Export - #deal-room-restricted]\n"
            "Timestamp: 2026-09-03 14:15:22 UTC\n"
            "Author: Senior Director, Corporate Development\n\n"
            "Don't share this yet, but we are finalizing Project Titan to acquire TechCo "
            "for $2.4B next Tuesday ahead of the upcoming Q3 earnings call. Need legal "
            "sign-off on the tender offer terms by tomorrow 5 PM."
        ),
    ),
    IngestionPreset(
        id="scenario_email_public",
        channel="email",
        title="Email Memo: Reuters Public Wire Confirmation",
        description="Public news wire regarding Apple ($AAPL) transaction already confirmed on SEC Form 8-K. Tests false-positive immunity.",
        expected_verdict="PUBLIC_NON_MATERIAL / CLEARED (Low Risk)",
        sample_text=(
            "From: press-clips@financialwire.com\n"
            "Subject: Reuters: Apple confirms acquisition of EdgeTech for $500M\n"
            "Date: September 1, 2026\n\n"
            "Reuters reports Apple Inc ($AAPL) has officially completed its acquisition "
            "of EdgeTech for $500M in cash and stock. The transaction was filed with the "
            "SEC on Form 8-K earlier this morning and is publicly confirmed by investor relations."
        ),
    ),
    IngestionPreset(
        id="scenario_zoom_delay",
        channel="zoom",
        title="Zoom Call: Unannounced Product Milestone Slip",
        description="Confidential engineering team call discussing thermal validation failure and a 2-month launch delay for internal Project Falcon.",
        expected_verdict="POTENTIAL_MNPI (Escalate to Compliance)",
        sample_text=(
            "[Zoom Call Transcript - Confidential Engineering Sync]\n"
            "Date: September 2, 2026\n"
            "Participants: Lead Architect, VP Engineering, Product Director\n\n"
            "VP Engineering: Team, our Project Falcon launch is slipping into late November. "
            "The latest thermal test chamber validation failed by 12 degrees. We can't let this "
            "hit the public wire before we resolve the heatsink supplier issue.\n"
            "Lead Architect: Agreed. We will keep this internal until the revised thermal model passes QA."
        ),
    ),
    IngestionPreset(
        id="scenario_salesforce_benign",
        channel="salesforce",
        title="Salesforce CRM: Routine Account Review",
        description="Routine enterprise account review notes devoid of market-moving catalysts, financial figures, or secrecy breaches.",
        expected_verdict="PUBLIC_NON_MATERIAL (Approved Release)",
        sample_text=(
            "[Salesforce CRM Note - Account: Acme Corp]\n"
            "Date: September 3, 2026\n"
            "Representative: Account Executive East\n\n"
            "Held quarterly account review with Acme Corp procurement team. Reviewed existing "
            "subscription tiers and agreed to schedule an annual renewal discussion in late Q4. "
            "No pricing changes or material contract adjustments requested."
        ),
    ),
]


# ==============================================================================
# Helper Functions
# ==============================================================================

def sanitize_filename(filename: str) -> str:
    """Strips directory traversal and unsafe characters from filenames."""
    base = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', base)
    return clean or "uploaded_document.txt"


def perform_redaction_diff(original: str, redacted: str) -> Dict[str, Any]:
    """Generates structured diff metadata comparing original and redacted text."""
    is_redacted = (original.strip() != redacted.strip())
    return {
        "is_redacted": is_redacted,
        "original_char_count": len(original),
        "redacted_char_count": len(redacted),
        "redacted_placeholder": "[REDACTED MNPI CONTENT]" if is_redacted else None,
    }


# ==============================================================================
# API Endpoints
# ==============================================================================

@app.get("/api/scenarios", response_model=List[IngestionPreset])
def get_preset_scenarios():
    """Returns catalog of realistic demonstration presets matching the diagram."""
    return PRESET_SCENARIOS


DEFAULT_GCS_BUCKET = "green-carrier-500109-k2-quarantine"


def get_storage_client(project_id: Optional[str] = None):
    """Returns an authenticated google.cloud.storage.Client.
    
    1. Attempts standard Google Cloud ADC credentials (verifying token validity).
    2. Seamlessly falls back to local gcloud CLI access token if user is logged into gcloud.
    """
    project = project_id or os.getenv("GCP_PROJECT", "green-carrier-500109-k2")
    try:
        from google.cloud import storage
        client = storage.Client(project=project)
        # Test if ADC credentials actually work or require reauth
        client.get_service_account_email()
        return client
    except Exception as e1:
        logger.debug(f"Standard storage.Client() verification notice: {e1}")

    try:
        import subprocess
        from google.oauth2.credentials import Credentials
        from google.cloud import storage
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if token:
            creds = Credentials(token)
            return storage.Client(project=project, credentials=creds)
    except Exception as e2:
        logger.debug(f"gcloud access token fallback notice: {e2}")

    return None


def _read_and_validate_file(safe_name: str, content_bytes: bytes) -> str:
    """Validates file extension and size, then returns decoded UTF-8 string."""
    allowed_extensions = {".txt", ".json", ".md", ".eml", ".csv", ".log", ".transcript"}
    ext = Path(safe_name).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(allowed_extensions)}"
        )
    max_bytes = 5 * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum allowed size of 5MB")
    try:
        return content_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to decode text content: {e}")


@app.get("/api/bucket/status")
def get_bucket_status(bucket: Optional[str] = None):
    """Checks connectivity to Google Cloud Storage and returns live status."""
    target_bucket = bucket or os.getenv("GCS_QUARANTINE_BUCKET", DEFAULT_GCS_BUCKET)
    client = get_storage_client()
    if client:
        try:
            b = client.bucket(target_bucket)
            if b.exists():
                return {
                    "connected": True,
                    "mode": "live_gcs",
                    "bucket_name": target_bucket,
                    "bucket_uri": f"gs://{target_bucket}/incoming/",
                    "project": client.project,
                }
        except Exception as e:
            logger.info(f"GCS bucket status check failed: {e}")

    return {
        "connected": False,
        "mode": "simulated",
        "bucket_name": target_bucket,
        "bucket_uri": f"gs://{target_bucket}/incoming/",
        "detail": "Using simulated local quarantine directory (quarantine_bucket/incoming/)",
    }


@app.get("/api/bucket/files")
def list_quarantine_bucket_files(bucket: Optional[str] = None):
    """Lists files available in live GCS or the simulated quarantine bucket."""
    target_bucket = bucket or os.getenv("GCS_QUARANTINE_BUCKET", DEFAULT_GCS_BUCKET)
    
    # 1. Check if real GCS bucket is accessible
    client = get_storage_client()
    if client and target_bucket:
        try:
            b = client.bucket(target_bucket)
            blobs = list(b.list_blobs(prefix="incoming/"))
            live_files = []
            for blob in blobs:
                name = os.path.basename(blob.name)
                if not blob.name.endswith("/") and name and not name.startswith("."):
                    updated_str = blob.updated.strftime("%Y-%m-%d %H:%M:%S UTC") if blob.updated else "Unknown"
                    live_files.append({
                        "filename": name,
                        "gcs_uri": f"gs://{target_bucket}/{blob.name}",
                        "size_bytes": blob.size,
                        "updated": updated_str,
                    })
            if live_files or b.exists():
                return {
                    "bucket": f"gs://{target_bucket}/incoming/",
                    "bucket_name": target_bucket,
                    "files": live_files,
                    "mode": "live_gcs",
                    "count": len(live_files),
                }
        except Exception as e:
            logger.info(f"Live GCS bucket lookup ({target_bucket}) fell back to local: {e}")

    # 2. Fallback to simulated local quarantine storage
    files = []
    if QUARANTINE_DIR.exists():
        for path in sorted(QUARANTINE_DIR.glob("*")):
            if path.is_file() and not path.name.startswith("."):
                mtime = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(path.stat().st_mtime))
                files.append({
                    "filename": path.name,
                    "gcs_uri": f"gs://{target_bucket}/incoming/{path.name}",
                    "size_bytes": path.stat().st_size,
                    "updated": mtime,
                })
    return {
        "bucket": f"gs://{target_bucket}/incoming/",
        "bucket_name": target_bucket,
        "files": files,
        "mode": "simulated",
        "count": len(files),
    }


@app.post("/api/bucket/fetch")
def fetch_from_storage_bucket(req: FetchBucketRequest):
    """Fetches text content from a GCS URI (supporting real GCS or simulated bucket)."""
    uri = req.gcs_uri.strip()
    if not uri.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid GCS URI. Must start with 'gs://'")

    # 1. Attempt live GCS fetch
    match = re.match(r"^gs://([^/]+)/(.+)$", uri)
    if match:
        bucket_name, blob_name = match.groups()
        client = get_storage_client()
        if client:
            try:
                b = client.bucket(bucket_name)
                blob = b.blob(blob_name)
                if blob.exists():
                    content = blob.download_as_text()
                    return {
                        "source": "live_gcs",
                        "gcs_uri": uri,
                        "filename": os.path.basename(blob_name),
                        "content": content,
                        "bytes": len(content.encode("utf-8")),
                    }
            except Exception as gcs_err:
                logger.info(f"Live GCS fetch attempt for {uri} failed: {gcs_err}")

    # 2. Check simulated local quarantine storage
    filename = os.path.basename(uri)
    sanitized = sanitize_filename(filename)
    local_target = QUARANTINE_DIR / sanitized
    if local_target.exists():
        try:
            content = local_target.read_text(encoding="utf-8", errors="replace")
            return {
                "source": "simulated_gcs",
                "gcs_uri": uri,
                "filename": sanitized,
                "content": content,
                "bytes": len(content.encode("utf-8")),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read file from storage: {e}")

    raise HTTPException(
        status_code=404,
        detail=f"Object not found at {uri}. Ensure file exists in the Quarantine Holding Zone."
    )


@app.post("/api/bucket/upload")
async def upload_to_bucket(
    file: UploadFile = File(...),
    bucket: Optional[str] = Form(None),
):
    """Uploads a document directly to the GCS quarantine bucket (incoming/) and mirrors locally."""
    safe_name = sanitize_filename(file.filename or "uploaded_doc.txt")
    max_bytes = 5 * 1024 * 1024
    content_bytes = await file.read(max_bytes + 1)
    text = _read_and_validate_file(safe_name, content_bytes)

    target_bucket = bucket or os.getenv("GCS_QUARANTINE_BUCKET", DEFAULT_GCS_BUCKET)
    gcs_uploaded = False
    gcs_uri = f"gs://{target_bucket}/incoming/{safe_name}"

    client = get_storage_client()
    if client:
        try:
            b = client.bucket(target_bucket)
            blob = b.blob(f"incoming/{safe_name}")
            blob.upload_from_string(content_bytes, content_type=file.content_type or "text/plain")
            gcs_uploaded = True
            logger.info(f"Successfully uploaded {safe_name} to live GCS {gcs_uri}")
        except Exception as e:
            logger.warning(f"Live GCS upload failed ({gcs_uri}), saved to local quarantine only: {e}")

    # Mirror to local directory
    dest_path = QUARANTINE_DIR / safe_name
    dest_path.write_text(text, encoding="utf-8")

    return {
        "status": "QUARANTINED",
        "filename": safe_name,
        "gcs_uri": gcs_uri,
        "uploaded_to_gcs": gcs_uploaded,
        "mode": "live_gcs" if gcs_uploaded else "simulated",
        "bucket": target_bucket,
        "bytes": len(content_bytes),
        "text": text,
    }


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    channel: str = Form("upload"),
):
    """Receives a document upload, validates it, and stages it into GCS and Quarantine."""
    safe_name = sanitize_filename(file.filename or "uploaded.txt")
    max_bytes = 5 * 1024 * 1024
    content_bytes = await file.read(max_bytes + 1)
    text = _read_and_validate_file(safe_name, content_bytes)

    target_bucket = os.getenv("GCS_QUARANTINE_BUCKET", DEFAULT_GCS_BUCKET)
    gcs_uploaded = False
    gcs_uri = f"gs://{target_bucket}/incoming/{safe_name}"

    client = get_storage_client()
    if client:
        try:
            b = client.bucket(target_bucket)
            blob = b.blob(f"incoming/{safe_name}")
            blob.upload_from_string(content_bytes, content_type=file.content_type or "text/plain")
            gcs_uploaded = True
        except Exception as e:
            logger.warning(f"Live GCS upload fallback: {e}")

    # Save to local quarantine
    dest_path = QUARANTINE_DIR / safe_name
    dest_path.write_text(text, encoding="utf-8")

    return {
        "status": "QUARANTINED",
        "filename": safe_name,
        "quarantine_uri": gcs_uri,
        "uploaded_to_gcs": gcs_uploaded,
        "mode": "live_gcs" if gcs_uploaded else "simulated",
        "channel": channel,
        "text": text,
        "bytes": len(content_bytes),
    }


@app.post("/api/process")
def process_document(req: ProcessRequest):
    """Processes document through the 2-Agent Fact Checker -> Arbiter pipeline."""
    start_time = time.perf_counter()

    # Run the compliance arbitration pipeline
    dossier, verdict = run_pipeline(req.text)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Calculate routing destination based on verdict
    if verdict.verdict == "MNPI_CONFIRMED":
        routing_destination = "Approved: Scoped Use (Redacted Only)"
        storage_bucket = "gs://approved-assets/scoped-use/"
        badge_variant = "critical"
        action_summary = "BLOCK_DIRECT_RELEASE & APPLY_REDACTION"
    elif verdict.verdict == "POTENTIAL_MNPI":
        routing_destination = "Compliance Review Queue (Holding Quarantine)"
        storage_bucket = "gs://quarantine-holding-zone/escalated-review/"
        badge_variant = "warning"
        action_summary = "ESCALATE_TO_COMPLIANCE_OFFICER"
    else:
        routing_destination = "Approved: General Use (Unrestricted)"
        storage_bucket = "gs://approved-assets/general-use/"
        badge_variant = "cleared"
        action_summary = "APPROVE_RELEASE_CLEAN"

    redaction_diff = perform_redaction_diff(req.text, verdict.redacted_text or req.text)

    # Automatically stream compliance alignment record to BigQuery
    doc_name = req.document_title or (os.path.basename(req.source_uri) if req.source_uri else "document.txt")
    audit_res = log_document_alignment_to_bq(
        document_name=doc_name,
        verdict=verdict,
        channel=req.channel,
        latency_ms=latency_ms,
        raw_text=req.text,
        dossier=dossier,
    )

    return {
        "status": "COMPLETED",
        "document_title": req.document_title,
        "channel": req.channel,
        "source_uri": req.source_uri or "direct_input",
        "latency_ms": latency_ms,
        "routing": {
            "destination": routing_destination,
            "storage_bucket": storage_bucket,
            "badge_variant": badge_variant,
            "action": verdict.recommended_action,
            "action_summary": action_summary,
        },
        "verdict": verdict.model_dump(),
        "dossier": dossier.model_dump(),
        "redaction_diff": redaction_diff,
        "audit": audit_res,
    }


# ==============================================================================
# BigQuery Document Alignment Audit Endpoints
# ==============================================================================

@app.get("/api/audit/logs")
def get_audit_logs(limit: int = 50):
    """Retrieves document alignment audit records directly from Google Cloud BigQuery."""
    records = fetch_document_alignment_logs(limit=limit)
    return {
        "project": settings.project_id,
        "dataset": os.getenv("BIGQUERY_DATASET", "mnpi_compliance_audit"),
        "table": os.getenv("BIGQUERY_TABLE", "document_alignment_log"),
        "table_id": get_table_full_id(),
        "count": len(records),
        "records": records,
    }


@app.get("/api/audit/status")
def get_audit_status():
    """Checks BigQuery audit dataset and table connectivity and returns total record count."""
    client = get_bigquery_client()
    connected = client is not None
    table_id = get_table_full_id(project=client.project if client else None)
    total_count = 0

    if client:
        try:
            query = f"SELECT count(1) as total FROM `{table_id}`"
            rows = list(client.query(query).result())
            if rows:
                total_count = rows[0]["total"]
        except Exception as e:
            logger.debug(f"Audit status count check error: {e}")

    return {
        "connected": connected,
        "project": client.project if client else settings.project_id,
        "dataset": os.getenv("BIGQUERY_DATASET", "mnpi_compliance_audit"),
        "table": os.getenv("BIGQUERY_TABLE", "document_alignment_log"),
        "table_id": table_id,
        "total_records": total_count,
        "mode": "live_bigquery" if connected else "local_mirror",
    }


@app.get("/api/audit/schema")
def get_audit_schema():
    """Returns the schema field definitions of the BigQuery document alignment table."""
    client = get_bigquery_client()
    table_id = get_table_full_id(project=client.project if client else None)
    fields = []
    if client:
        try:
            table = client.get_table(table_id)
            for f in table.schema:
                fields.append({
                    "name": f.name,
                    "field_type": f.field_type,
                    "mode": f.mode,
                    "description": f.description or "",
                })
        except Exception as e:
            logger.debug(f"BigQuery get_table schema error: {e}")

    # Fallback schema metadata if offline
    if not fields:
        fields = [
            {"name": "timestamp", "field_type": "TIMESTAMP", "mode": "REQUIRED", "description": "UTC recording timestamp"},
            {"name": "document_name", "field_type": "STRING", "mode": "REQUIRED", "description": "Ingested document identifier or filename"},
            {"name": "channel", "field_type": "STRING", "mode": "NULLABLE", "description": "Ingestion producer channel (gcs, slack, zoom, email)"},
            {"name": "verdict", "field_type": "STRING", "mode": "REQUIRED", "description": "Arbiter compliance decision (MNPI_CONFIRMED, POTENTIAL_MNPI, CLEARED)"},
            {"name": "risk_level", "field_type": "STRING", "mode": "REQUIRED", "description": "Risk categorization (CRITICAL, HIGH, LOW)"},
            {"name": "recommended_action", "field_type": "STRING", "mode": "REQUIRED", "description": "Enforced compliance routing action"},
            {"name": "materiality_score", "field_type": "FLOAT", "mode": "NULLABLE", "description": "Test 1: Materiality score (0.0 - 1.0)"},
            {"name": "public_availability_score", "field_type": "FLOAT", "mode": "NULLABLE", "description": "Test 2: Public Availability / Mosaic score (0.0 - 1.0)"},
            {"name": "source_duty_score", "field_type": "FLOAT", "mode": "NULLABLE", "description": "Test 3: Source & Duty insider fiduciary breach score (0.0 - 1.0)"},
            {"name": "harm_score", "field_type": "FLOAT", "mode": "NULLABLE", "description": "Test 4: Actionability and commercial harm potential (0.0 - 1.0)"},
            {"name": "entities_detected", "field_type": "STRING", "mode": "NULLABLE", "description": "Detected corporate entities, tickers, and internal codenames"},
            {"name": "triggers_detected", "field_type": "STRING", "mode": "NULLABLE", "description": "Detected M&A, roadmap, or financial trigger terms"},
            {"name": "has_secrecy_markers", "field_type": "BOOLEAN", "mode": "NULLABLE", "description": "Whether explicit confidentiality markers were identified"},
            {"name": "audit_hash", "field_type": "STRING", "mode": "NULLABLE", "description": "Cryptographic SHA-256 integrity hash digest"},
            {"name": "summary_justification", "field_type": "STRING", "mode": "NULLABLE", "description": "Binding legal compliance justification for regulatory defense"},
            {"name": "redacted_preview", "field_type": "STRING", "mode": "NULLABLE", "description": "Preview of sanitized document"},
            {"name": "latency_ms", "field_type": "FLOAT", "mode": "NULLABLE", "description": "End-to-end multi-agent pipeline latency in milliseconds"},
            {"name": "model_used", "field_type": "STRING", "mode": "NULLABLE", "description": "Reasoning model utilized (gemini-3.8-flash)"},
        ]

    return {
        "table_id": table_id,
        "project": client.project if client else settings.project_id,
        "dataset": os.getenv("BIGQUERY_DATASET", "mnpi_compliance_audit"),
        "table": os.getenv("BIGQUERY_TABLE", "document_alignment_log"),
        "fields": fields,
        "count": len(fields),
    }


# ==============================================================================
# Static File Mounts & Root Page
# ==============================================================================

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serves the single-page compliance dashboard."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h3>Dashboard file not found. Please verify static/index.html exists.</h3>")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


def run():
    """CLI launcher for local demonstration."""
    import uvicorn
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", "8080"))
    print(f"\n=======================================================")
    print(f"🚀 Starting MNPI Ingestion & Compliance Demo Server")
    print(f"   URL: http://{host}:{port}")
    print(f"=======================================================\n")
    uvicorn.run("demo_server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    run()
