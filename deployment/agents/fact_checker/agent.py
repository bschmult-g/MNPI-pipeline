"""MNPI Fact Checker Agent Entrypoint for ADK & Vertex AI Agent Runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from deployment.agents.fact_checker.runtime import MNPIFactCheckerRuntime
except ImportError:
    from agents.fact_checker.runtime import MNPIFactCheckerRuntime

try:
    from google.adk.apps import App
    try:
        from app.agents.fact_checker import create_fact_checker_agent
    except ImportError:
        from fact_checker_agent import create_fact_checker_agent
    root_agent = create_fact_checker_agent()
    app = App(
        name="mnpi_fact_checker_agent",
        root_agent=root_agent,
    )
except ImportError:
    root_agent = None
    app = None

runtime = MNPIFactCheckerRuntime()

__all__ = ["root_agent", "app", "runtime", "MNPIFactCheckerRuntime"]
