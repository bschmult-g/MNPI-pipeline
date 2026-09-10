"""MNPI Compliance Agent Application Package (Google ADK & Vertex AI Agent Engine)."""

from __future__ import annotations

import os
import sys

# Ensure app package is on path for relative and absolute imports
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from app.agent import root_agent, app, runtime, MNPIComplianceAgentRuntime
from app.workflow import run_pipeline, run_two_agent_pipeline, build_mnpi_workflow
from app.schemas import FactCheckingDossier, ArbiterVerdict

__all__ = [
    "root_agent",
    "app",
    "runtime",
    "MNPIComplianceAgentRuntime",
    "run_pipeline",
    "run_two_agent_pipeline",
    "build_mnpi_workflow",
    "FactCheckingDossier",
    "ArbiterVerdict",
]
