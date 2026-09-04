"""Agent 2: MNPI Decision Authority Reasoning Engine Runtime for Vertex AI Agent Engine."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("mnpi_decision_authority_runtime")


class MNPIDecisionAuthorityRuntime:
    """Vertex AI Reasoning Engine Runtime for Agent 2 (MNPI Decision Authority).
    
    This agent serves as the instructional arbiter and compliance decision authority:
    - Receives the raw document text AND the FactCheckingDossier payload sent from Agent 1.
    - Evaluates the 4 mandatory legal Assessment Criteria:
      1. Materiality Test (Basic Inc. v. Levinson standard)
      2. Public Availability Test / Mosaic Check (Mosaic Theory)
      3. Source & Duty Test (Chiarella / Dirks fiduciary duty standard)
      4. Actionability & Market Harm Evaluation
    - Invokes BigQuery audit tool (record_document_alignment_in_bigquery) to record alignment.
    - Renders the definitive ArbiterVerdict.
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
            f"Initialized MNPIDecisionAuthorityRuntime for project={self.project_id}, "
            f"location={self.location}, model={self.model}"
        )

    def query(
        self,
        text: Optional[str] = None,
        dossier: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
        input: Optional[str] = None,
        document_name: str = "compliance_document",
        channel: str = "api",
        log_to_bq: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Executes Agent 2 flow given text and the dossier received from Agent 1.
        
        If dossier is omitted (e.g., direct invocation in Vertex AI Console Playground),
        Agent 2 invokes Agent 1 first to produce the factual dossier before arbitrating.
        
        Args:
            text: The original document text.
            dossier: The FactCheckingDossier payload sent from Agent 1 (optional).
            prompt: Alternative argument name supported by Vertex AI Console Playground.
            input: Alternative argument name supported by Vertex AI Reasoning Engine.
            document_name: Document title or filename.
            channel: Ingestion channel (e.g. slack, zoom, gcs, email).
            log_to_bq: Whether to log to BigQuery audit table.
            
        Returns:
            Dict containing the binding ArbiterVerdict.
        """
        document_text = text or prompt or input or kwargs.get("message") or kwargs.get("content") or ""
        from schemas import FactCheckingDossier
        from workflow import get_genai_client, run_live_arbiter, run_offline_arbiter
        from audit_logger import log_document_alignment_to_bq

        # Autonomous handoff: if no dossier provided, invoke Agent 1 runtime
        if dossier is None:
            logger.info("No dossier provided to Agent 2; invoking Agent 1 (MNPIFactCheckerRuntime) first...")
            from agents.fact_checker.runtime import MNPIFactCheckerRuntime
            fc_agent = MNPIFactCheckerRuntime(
                project_id=self.project_id,
                location=self.location,
                model=self.model,
            )
            dossier = fc_agent.query(text=document_text)

        start_t = time.perf_counter()
        parsed_dossier = FactCheckingDossier.model_validate(dossier)

        client = get_genai_client()
        if client:
            verdict = run_live_arbiter(client, document_text, parsed_dossier)
        else:
            verdict = run_offline_arbiter(parsed_dossier)

        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

        if log_to_bq:
            try:
                log_document_alignment_to_bq(
                    document_name=document_name,
                    verdict=verdict,
                    channel=channel,
                    latency_ms=latency_ms,
                    raw_text=document_text,
                    dossier=parsed_dossier,
                )
            except Exception as e:
                logger.warning(f"BigQuery audit log notice: {e}")

        return verdict.model_dump()
