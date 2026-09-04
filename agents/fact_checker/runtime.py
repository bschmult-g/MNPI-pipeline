"""Agent 1: MNPI Fact Checker Agent Runtime for Vertex AI Agent Engine."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("mnpi_fact_checker_runtime")


class MNPIFactCheckerRuntime:
    """Vertex AI Reasoning Engine Runtime for Agent 1 (MNPI Fact Checker).
    
    This agent serves as the investigative factual foundation of the pipeline:
    - Coordinates 3 specialized sub-agents:
      1. SA1 (entities_agent): extracts entities, tickers, and confidential internal codenames.
      2. SA2 (trigger_words_agent): identifies catalysts (M&A, roadmap slips, earnings, executive departures).
      3. SA3 (public_check_agent): verifies public availability and detects secrecy markers (\"don't share\").
    - Invokes callable tools:
      - extract_named_entities_and_codenames
      - match_insider_trading_keywords
      - query_public_news_archive
      - query_regulatory_filings
    - Outputs a synthesized FactCheckingDossier ready for handoff to Agent 2.
    """

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
        logger.info(
            f"Initialized MNPIFactCheckerRuntime for project={self.project_id}, "
            f"location={self.location}, model={self.model}"
        )

    def query(
        self,
        text: Optional[str] = None,
        prompt: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Executes Agent 1 flow on the provided document text.
        
        Args:
            text: The raw document text or communication to investigate.
            prompt: Alternative argument name supported by Vertex AI Console Playground.
            input: Alternative argument name supported by Vertex AI Reasoning Engine.
            
        Returns:
            Dict containing the synthesized FactCheckingDossier.
        """
        document_text = text or prompt or input or kwargs.get("message") or kwargs.get("content") or ""
        from workflow import get_genai_client, run_live_fact_checker, run_offline_fact_checker

        client = get_genai_client()
        if client:
            dossier = run_live_fact_checker(client, document_text)
        else:
            dossier = run_offline_fact_checker(document_text)

        return dossier.model_dump()
