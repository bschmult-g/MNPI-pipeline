"""MNPI Fact Checker Agent Package."""
from agents.fact_checker.runtime import MNPIFactCheckerRuntime

try:
    from .agent import app, root_agent
except Exception:
    app, root_agent = None, None

__all__ = ["MNPIFactCheckerRuntime", "app", "root_agent"]


