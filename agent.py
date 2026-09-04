import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

from typing import Any, Dict, Optional
from google.adk.apps import App
from workflow import build_mnpi_workflow

# The primary workflow agent orchestrating Fact Checker and Arbiter
root_agent = build_mnpi_workflow()

# ADK App declaration for serving via API Server and Agent Runtime
app = App(
    name="mnpi_compliance_agent",
    root_agent=root_agent,
)


class MNPIComplianceAgentRuntime:
    """Vertex AI Reasoning Engine Runtime for MNPI Compliance Agent."""

    def __init__(
        self,
        project_id: str = "green-carrier-500109-k2",
        location: str = "us",
        model: str = "gemini-3.8-flash",
    ):
        self.project_id = project_id
        self.location = location
        self.model = model

    def set_up(self):
        """Initializes runtime environment upon Vertex AI container startup."""
        pass

    def query(
        self,
        text: Optional[str] = None,
        prompt: Optional[str] = None,
        input: Optional[str] = None,
        document_name: str = "compliance_document",
        channel: str = "api",
        log_to_bq: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Executes the full two-agent MNPI compliance pipeline:
        1. Agent 1 (Fact Checker): Extracts entities, catalysts, and verifies public mosaic.
        2. Agent 2 (Decision Authority): Evaluates 4 legal tests and logs to BigQuery.
        """
        content = text or prompt or input or ""
        from workflow import run_pipeline
        import asyncio

        return asyncio.run(
            run_pipeline(
                text=content,
                model=self.model,
                project_id=self.project_id,
                document_name=document_name,
                channel=channel,
                log_to_bq=log_to_bq,
            )
        )


runtime = MNPIComplianceAgentRuntime()

__all__ = ["root_agent", "app", "runtime", "MNPIComplianceAgentRuntime"]

