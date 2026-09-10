"""Comprehensive Unit & Integration Test Suite for MNPI Compliance System.

Maintains backward-compatible entrypoint aggregating tests from:
- tests/unit/test_compliance_unit.py
- tests/integration/test_demo_server.py
"""

from __future__ import annotations

import unittest
from tests.unit.test_compliance_unit import TestMNPIComplianceSystem, TestTwoAgentArchitectureAndAudit
from tests.integration.test_demo_server import TestDemoServer
from tests.unit.test_rl_causal_v2 import (
    TestHierarchicalAblationTrigger,
    TestJointAblationManager,
    TestComplianceRewardEngine,
    TestDPOPreferenceDatasetBuilder,
    TestStandardizedVerificationCodes,
)
from tests.unit.test_security_entitlements import (
    TestSecurityEntitlementsTagging,
    TestEntitlementsApiAndSidecar,
)

__all__ = [
    "TestMNPIComplianceSystem",
    "TestTwoAgentArchitectureAndAudit",
    "TestDemoServer",
    "TestHierarchicalAblationTrigger",
    "TestJointAblationManager",
    "TestComplianceRewardEngine",
    "TestDPOPreferenceDatasetBuilder",
    "TestStandardizedVerificationCodes",
    "TestSecurityEntitlementsTagging",
    "TestEntitlementsApiAndSidecar",
]

if __name__ == "__main__":
    unittest.main(verbosity=2)
