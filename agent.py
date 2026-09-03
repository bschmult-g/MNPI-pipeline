"""MNPI Compliance Agent Entrypoint for ADK & Vertex AI Agent Runtime."""

from __future__ import annotations

from google.adk.apps import App
from workflow import build_mnpi_workflow

# The primary workflow agent orchestrating Fact Checker and Arbiter
root_agent = build_mnpi_workflow()

# ADK App declaration for serving via API Server and Agent Runtime
app = App(
    name="mnpi_compliance_agent",
    root_agent=root_agent,
)

__all__ = ["root_agent", "app"]
