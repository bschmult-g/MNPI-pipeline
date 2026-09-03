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


@app.get("/api/bucket/files")
def list_quarantine_bucket_files():
    """Lists files available in live GCS or the simulated quarantine bucket."""
    gcs_bucket_name = os.getenv("GCS_QUARANTINE_BUCKET", "")
    
    # Check if a real GCS bucket is configured and accessible
    if gcs_bucket_name:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(gcs_bucket_name)
            blobs = list(bucket.list_blobs(prefix="incoming/"))
            live_files = [
                {
                    "filename": os.path.basename(b.name),
                    "gcs_uri": f"gs://{gcs_bucket_name}/{b.name}",
                    "size_bytes": b.size,
                }
                for b in blobs if not b.name.endswith("/") and os.path.basename(b.name)
            ]
            if live_files:
                return {
                    "bucket": f"gs://{gcs_bucket_name}/incoming/",
                    "files": live_files,
                    "mode": "live_gcs",
                }
        except Exception as e:
            logger.info(f"Live GCS bucket lookup ({gcs_bucket_name}) fell back to local: {e}")

    # Fallback to simulated local quarantine storage
    files = []
    if QUARANTINE_DIR.exists():
        for path in sorted(QUARANTINE_DIR.glob("*")):
            if path.is_file() and not path.name.startswith("."):
                files.append({
                    "filename": path.name,
                    "gcs_uri": f"gs://{gcs_bucket_name or 'quarantine-holding-zone'}/incoming/{path.name}",
                    "size_bytes": path.stat().st_size,
                })
    return {
        "bucket": f"gs://{gcs_bucket_name or 'quarantine-holding-zone'}/incoming/",
        "files": files,
        "mode": "simulated",
    }


@app.post("/api/bucket/fetch")
def fetch_from_storage_bucket(req: FetchBucketRequest):
    """Fetches text content from a GCS URI (supporting real GCS or simulated bucket)."""
    uri = req.gcs_uri.strip()
    if not uri.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid GCS URI. Must start with 'gs://'")

    # 1. If it's a real GCS URI (not the default simulated 'quarantine-holding-zone'), try live GCS first
    match = re.match(r"^gs://([^/]+)/(.+)$", uri)
    if match:
        bucket_name, blob_name = match.groups()
        if bucket_name != "quarantine-holding-zone":
            try:
                from google.cloud import storage
                client = storage.Client()
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
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


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    channel: str = Form("upload"),
):
    """Receives a document upload, validates it, and stages it into Quarantine."""
    safe_name = sanitize_filename(file.filename or "uploaded.txt")

    # Extension allowlist
    allowed_extensions = {".txt", ".json", ".md", ".eml", ".csv", ".log", ".transcript"}
    ext = Path(safe_name).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(allowed_extensions)}"
        )

    # Read content with 5MB size limit
    max_bytes = 5 * 1024 * 1024
    content_bytes = await file.read(max_bytes + 1)
    if len(content_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum allowed size of 5MB")

    try:
        text = content_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to decode text content: {e}")

    # Save to Quarantine Holding Zone
    dest_path = QUARANTINE_DIR / safe_name
    dest_path.write_text(text, encoding="utf-8")

    quarantine_uri = f"gs://quarantine-holding-zone/incoming/{safe_name}"

    return {
        "status": "QUARANTINED",
        "filename": safe_name,
        "quarantine_uri": quarantine_uri,
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
