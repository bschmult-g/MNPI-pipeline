"""MNPI Fact Checker Agent Package."""
try:
    from .runtime import MNPIFactCheckerRuntime
except ImportError:
    from agents.fact_checker.runtime import MNPIFactCheckerRuntime

try:
    from .agent import app, root_agent
except Exception:
    app, root_agent = None, None

__all__ = ["MNPIFactCheckerRuntime", "app", "root_agent"]


