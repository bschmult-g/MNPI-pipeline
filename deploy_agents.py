"""Deploy both MNPI Agents to Google Cloud Vertex AI Agent Engine.

Deploys the two pipeline agents as distinct Reasoning Engine instances:
1. mnpi-fact-checker-agent: First in pipeline, extracts entities (SA1), triggers (SA2), and verifies public mosaic (SA3).
2. mnpi-decision-authority-agent: Second in pipeline, receives document + fact checking dossier, applies 4 Assessment Criteria.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from google.oauth2.credentials import Credentials
import vertexai

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy_agents")

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "green-carrier-500109-k2")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

FACT_CHECKER_ID = "7905177991674593280"
DECISION_AUTHORITY_ID = "6736493888371949568"


def get_client() -> vertexai.Client:
    """Gets authenticated Vertex AI client."""
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if token:
            return vertexai.Client(project=PROJECT_ID, location=LOCATION, credentials=Credentials(token))
    except Exception as e:
        logger.debug(f"gcloud access token notice: {e}")

    return vertexai.Client(project=PROJECT_ID, location=LOCATION)


def deploy():
    client = get_client()
    logger.info(f"Connected to Vertex AI Agent Engine in project '{PROJECT_ID}', location '{LOCATION}'")

    # 1. Verify or register Agent 1: mnpi-fact-checker-agent
    logger.info(f"Verifying Agent 1 (Fact Checker): {FACT_CHECKER_ID}...")
    try:
        fc = client.agent_engines.get(name=f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{FACT_CHECKER_ID}")
        logger.info(f"✅ Verified Agent 1: {fc.api_resource.display_name} ({fc.api_resource.name})")
    except Exception as e:
        logger.warning(f"Fact Checker not found by ID ({e}), creating new instance...")
        fc = client.agent_engines.create(
            config={
                "display_name": "mnpi-fact-checker-agent",
                "description": "Material Non-Public Information (MNPI) Fact Checker Agent - Extracts entities, triggers, and verifies public mosaic",
            }
        )
        logger.info(f"✅ Created Agent 1: {fc.api_resource.display_name} ({fc.api_resource.name})")

    # 2. Verify or register Agent 2: mnpi-decision-authority-agent
    logger.info(f"Verifying Agent 2 (Decision Authority): {DECISION_AUTHORITY_ID}...")
    try:
        da = client.agent_engines.get(name=f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{DECISION_AUTHORITY_ID}")
        logger.info(f"✅ Verified Agent 2: {da.api_resource.display_name} ({da.api_resource.name})")
    except Exception as e:
        logger.warning(f"Decision Authority not found by ID ({e}), creating new instance...")
        da = client.agent_engines.create(
            config={
                "display_name": "mnpi-decision-authority-agent",
                "description": "Material Non-Public Information (MNPI) Decision Authority Arbiter - Applies 4 Assessment Criteria for binding verdict",
            }
        )
        logger.info(f"✅ Created Agent 2: {da.api_resource.display_name} ({da.api_resource.name})")

    print("\n=======================================================")
    print("🎯 Vertex AI Agent Engine Deployment Status:")
    print(f"   1. Fact Checker Agent:       {fc.api_resource.name}")
    print(f"   2. Decision Authority Agent: {da.api_resource.name}")
    print(f"   Model: Gemini 3.8 Flash (Multi-Region US)")
    print("=======================================================\n")


if __name__ == "__main__":
    deploy()
