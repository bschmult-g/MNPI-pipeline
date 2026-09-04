"""Deploy MNPI Agents to Google Cloud Vertex AI Agent Engine.

Guarantees IN-PLACE updates ONLY:
- Never creates new instances or spawns rogue IDs.
- Directly targets fixed Reasoning Engine instances:
  1. Compliance Agent (Agent Runtime):
     projects/799321431260/locations/us-central1/reasoningEngines/5693910574635679744
  2. Fact Checker Agent (Agent 1):
     projects/799321431260/locations/us-central1/reasoningEngines/9003774825776283648
  3. Decision Authority Agent (Agent 2):
     projects/799321431260/locations/us-central1/reasoningEngines/6736493888371949568
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from typing import List, Optional

from google.cloud import storage
from google.oauth2.credentials import Credentials
import vertexai
from vertexai.preview import reasoning_engines

from agents.fact_checker.runtime import MNPIFactCheckerRuntime
from agents.decision_authority.runtime import MNPIDecisionAuthorityRuntime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy_agents")

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "green-carrier-500109-k2")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.getenv("STAGING_BUCKET", "gs://green-carrier-500109-k2-agent-runtime-staging")

COMPLIANCE_AGENT_ID = "5693910574635679744"
FACT_CHECKER_ID = "9003774825776283648"
DECISION_AUTHORITY_ID = "6736493888371949568"

REQUIREMENTS = [
    "google-cloud-aiplatform>=1.70.0",
    "google-adk[a2a]==2.7.1",
    "google-genai>=2.18.0",
    "pydantic>=2.10.0",
    "google-cloud-bigquery>=3.25.0",
    "google-cloud-storage>=2.14.0",
    "python-dotenv>=1.0.0",
]

EXTRA_PACKAGES = [
    "schemas.py",
    "config.py",
    "workflow.py",
    "audit_logger.py",
    "fact_checker_agent.py",
    "arbiter_agent.py",
    "tools",
    "sub_agents",
    "agents",
]


def init_vertex_env():
    """Initializes Vertex AI SDK with credentials for both local and CI environments."""
    token = None
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()
        except Exception:
            token = None

    if token:
        creds = Credentials(token)
        orig_init = storage.Client.__init__

        def patched_init(self, *args, **kwargs):
            if kwargs.get("credentials") is None and len(args) < 2:
                kwargs["credentials"] = creds
            return orig_init(self, *args, **kwargs)

        storage.Client.__init__ = patched_init

        vertexai.init(
            project=PROJECT_ID,
            location=LOCATION,
            credentials=creds,
            staging_bucket=STAGING_BUCKET,
        )
    else:
        vertexai.init(
            project=PROJECT_ID,
            location=LOCATION,
            staging_bucket=STAGING_BUCKET,
        )


def update_fact_checker(project_id: str = PROJECT_ID, location: str = LOCATION) -> str:
    """Updates Agent 1 (Fact Checker Runtime: 9003774825776283648) in-place."""
    logger.info(f"🔄 Updating Agent 1 (Fact Checker) IN-PLACE: {FACT_CHECKER_ID}...")
    fc_runtime = MNPIFactCheckerRuntime(project_id=project_id, location=location, model="gemini-3.8-flash")
    resource_name = f"projects/{project_id}/locations/{location}/reasoningEngines/{FACT_CHECKER_ID}"

    try:
        fc = reasoning_engines.ReasoningEngine(resource_name)
    except Exception as e:
        raise RuntimeError(
            f"❌ Agent 1 ({FACT_CHECKER_ID}) not found in {project_id}/{location}: {e}. "
            "Deployment halted to prevent creating duplicate instances."
        )

    fc.update(
        reasoning_engine=fc_runtime,
        requirements=REQUIREMENTS,
        extra_packages=EXTRA_PACKAGES,
        display_name="mnpi-fact-checker-agent",
        description="Material Non-Public Information (MNPI) Fact Checker Agent - Extracts entities, triggers, and verifies public mosaic status",
    )
    logger.info(f"✅ In-place update complete for Agent 1: {fc.resource_name}")
    return fc.resource_name


def update_decision_authority(project_id: str = PROJECT_ID, location: str = LOCATION) -> str:
    """Updates Agent 2 (Decision Authority Runtime: 6736493888371949568) in-place."""
    logger.info(f"🔄 Updating Agent 2 (Decision Authority) IN-PLACE: {DECISION_AUTHORITY_ID}...")
    da_runtime = MNPIDecisionAuthorityRuntime(project_id=project_id, location=location, model="gemini-3.8-flash")
    resource_name = f"projects/{project_id}/locations/{location}/reasoningEngines/{DECISION_AUTHORITY_ID}"

    try:
        da = reasoning_engines.ReasoningEngine(resource_name)
    except Exception as e:
        raise RuntimeError(
            f"❌ Agent 2 ({DECISION_AUTHORITY_ID}) not found in {project_id}/{location}: {e}. "
            "Deployment halted to prevent creating duplicate instances."
        )

    da.update(
        reasoning_engine=da_runtime,
        requirements=REQUIREMENTS,
        extra_packages=EXTRA_PACKAGES,
        display_name="mnpi-decision-authority-agent",
        description="Material Non-Public Information (MNPI) Decision Authority Arbiter - Applies 4 Assessment Criteria for binding compliance verdict",
    )
    logger.info(f"✅ In-place update complete for Agent 2: {da.resource_name}")
    return da.resource_name


def update_compliance_agent(project_id: str = PROJECT_ID, location: str = LOCATION) -> str:
    """Updates the primary ADK Compliance Agent (5693910574635679744) IN-PLACE."""
    logger.info(f"🔄 Updating Compliance Agent IN-PLACE: {COMPLIANCE_AGENT_ID}...")

    # Monkeypatch Pydantic validation to allow extra fields for Agent Engine config
    from vertexai._genai.types import common
    common.AgentEngineConfig.model_config["extra"] = "allow"

    token = None
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()
        except Exception:
            token = None

    if token:
        import google.auth
        creds = Credentials(token)
        google.auth.default = lambda *args, **kwargs: (creds, project_id)

    from google.adk.cli.cli_deploy import to_agent_engine
    to_agent_engine(
        agent_folder=os.path.abspath("."),
        project=project_id,
        region=location,
        agent_engine_id=COMPLIANCE_AGENT_ID,
    )

    resource_name = f"projects/{project_id}/locations/{location}/reasoningEngines/{COMPLIANCE_AGENT_ID}"
    logger.info(f"✅ In-place update complete for Compliance Agent: {resource_name}")
    return resource_name


def deploy(target: str = "all", project_id: str = PROJECT_ID, location: str = LOCATION):
    """Deploys in-place updates to the specified agent engine instances."""
    init_vertex_env()
    logger.info(f"Connected to Vertex AI Agent Engine in project '{project_id}', location '{location}'")
    logger.info(f"Deploy target: '{target}' (STRICT IN-PLACE MODE: No new instances will be created)")

    results = {}

    if target in ("all", "pipeline", "fact-checker"):
        results["Agent 1 (Fact Checker)"] = update_fact_checker(project_id, location)

    if target in ("all", "pipeline", "decision-authority"):
        results["Agent 2 (Decision Authority)"] = update_decision_authority(project_id, location)

    if target in ("all", "compliance"):
        results["Compliance Agent"] = update_compliance_agent(project_id, location)

    print("\n" + "=" * 65)
    print("🎯 Vertex AI Agent Engine IN-PLACE Update Complete:")
    for name, rname in results.items():
        print(f"   ✓ {name:<30}: {rname}")
    print(f"   Model: Gemini 3.8 Flash (Multi-Region US)")
    print(f"   BigQuery Audit Streaming: {project_id}.mnpi_compliance_audit.document_alignment_log")
    print("=" * 65 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="In-place deployment of MNPI agents to Vertex AI Agent Engine.")
    parser.add_argument(
        "--target",
        choices=["all", "pipeline", "compliance", "fact-checker", "decision-authority"],
        default="all",
        help="Target agent(s) to update in-place (default: all)",
    )
    parser.add_argument("--pipeline", action="store_const", const="pipeline", dest="target", help="Shortcut for --target=pipeline")
    parser.add_argument("--compliance", action="store_const", const="compliance", dest="target", help="Shortcut for --target=compliance")
    parser.add_argument("--project", default=PROJECT_ID, help="GCP Project ID")
    parser.add_argument("--location", default=LOCATION, help="Vertex AI Region")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    deploy(target=args.target, project_id=args.project, location=args.location)


