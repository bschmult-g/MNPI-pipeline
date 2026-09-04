"""Deploy MNPI Agents to Google Cloud Vertex AI Agent Engine.

Guarantees IN-PLACE updates ONLY:
- Never creates new instances or spawns rogue IDs.
- Directly targets fixed Reasoning Engine instances:
  1. Compliance Agent (Agent Runtime):
     projects/799321431260/locations/us-central1/reasoningEngines/5693910574635679744
  2. Fact Checker Agent (Agent 1):
     projects/799321431260/locations/us-central1/reasoningEngines/7905177991674593280
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
FACT_CHECKER_ID = "7905177991674593280"
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


ADK_EXTRA_PACKAGES = [
    "requirements.txt",
    "config.py",
    "schemas.py",
    "fact_checker_agent.py",
    "arbiter_agent.py",
    "audit_logger.py",
    "workflow.py",
    "sub_agents",
    "tools",
]


def _setup_adk_deployment_env(project_id: str):
    """Sets up authentication and schema relaxation for ADK Agent Engine deployment."""
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


def _deploy_adk_agent(
    agent_folder: str,
    agent_engine_id: str,
    display_name: str,
    description: str,
    extra_packages: Optional[List[str]] = None,
    project_id: str = PROJECT_ID,
    location: str = LOCATION,
) -> str:
    """Updates a Reasoning Engine instance in-place with google-adk, A2A protocol, and Cloud Telemetry."""
    logger.info(f"🔄 Updating {display_name} IN-PLACE: {agent_engine_id} via google-adk (A2A + Cloud Telemetry)...")
    _setup_adk_deployment_env(project_id)

    from google.adk.cli.cli_deploy import to_agent_engine
    to_agent_engine(
        agent_folder=os.path.abspath(agent_folder),
        project=project_id,
        region=location,
        agent_engine_id=agent_engine_id,
        otel_to_cloud=True,
        trace_to_cloud=True,
        display_name=display_name,
        description=description,
        requirements_file="requirements.txt",
        extra_packages=extra_packages,
    )

    resource_name = f"projects/{project_id}/locations/{location}/reasoningEngines/{agent_engine_id}"
    logger.info(f"✅ In-place update complete for {display_name}: {resource_name}")
    return resource_name


def update_fact_checker(project_id: str = PROJECT_ID, location: str = LOCATION) -> str:
    """Updates Agent 1 (Fact Checker: 7905177991674593280) in-place with google-adk, A2A, and Cloud Telemetry."""
    return _deploy_adk_agent(
        agent_folder="agents/fact_checker",
        agent_engine_id=FACT_CHECKER_ID,
        display_name="mnpi-fact-checker-agent",
        description="Material Non-Public Information (MNPI) Fact Checker Agent - Extracts entities, triggers, and verifies public mosaic status",
        extra_packages=ADK_EXTRA_PACKAGES,
        project_id=project_id,
        location=location,
    )


def update_decision_authority(project_id: str = PROJECT_ID, location: str = LOCATION) -> str:
    """Updates Agent 2 (Decision Authority: 6736493888371949568) in-place with google-adk, A2A, and Cloud Telemetry."""
    return _deploy_adk_agent(
        agent_folder="agents/decision_authority",
        agent_engine_id=DECISION_AUTHORITY_ID,
        display_name="mnpi-decision-authority-agent",
        description="Material Non-Public Information (MNPI) Decision Authority Arbiter - Applies 4 Assessment Criteria for binding compliance verdict",
        extra_packages=ADK_EXTRA_PACKAGES,
        project_id=project_id,
        location=location,
    )


def update_compliance_agent(project_id: str = PROJECT_ID, location: str = LOCATION) -> str:
    """Updates Compliance Agent (5693910574635679744) in-place with google-adk, A2A, and Cloud Telemetry."""
    return _deploy_adk_agent(
        agent_folder=".",
        agent_engine_id=COMPLIANCE_AGENT_ID,
        display_name="mnpi-compliance-agent",
        description="Material Non-Public Information (MNPI) Compliance Decision Authority Agent",
        extra_packages=None,
        project_id=project_id,
        location=location,
    )


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


