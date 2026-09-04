"""MNPI Decision Authority Agent Entrypoint for ADK & Vertex AI Agent Runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.decision_authority.runtime import MNPIDecisionAuthorityRuntime

try:
    from google.adk.apps import App
    from arbiter_agent import create_arbiter_agent
    root_agent = create_arbiter_agent()
    app = App(
        name="mnpi_decision_authority_agent",
        root_agent=root_agent,
    )
except ImportError:
    root_agent = None
    app = None

runtime = MNPIDecisionAuthorityRuntime()

__all__ = ["root_agent", "app", "runtime", "MNPIDecisionAuthorityRuntime"]

