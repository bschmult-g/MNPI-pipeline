"""MNPI Fact Checker Agent Entrypoint for ADK & Vertex AI Agent Runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from google.adk.apps import App
from fact_checker_agent import create_fact_checker_agent

root_agent = create_fact_checker_agent()

app = App(
    name="mnpi_fact_checker_agent",
    root_agent=root_agent,
)

__all__ = ["root_agent", "app"]
