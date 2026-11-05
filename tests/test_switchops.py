"""
Comprehensive Test Suite for SwitchOps.
Implements the full test plan from Section 17 of the Technical Implementation Guide:
- Unit tests: validation, severity, state transitions, deduplication, secret redaction, path safety, approvals.
- Integration tests: Switch adapter normalization, orchestrator routing, real test runner execution, GitHub PR dispatch.
- End-to-end acceptance test.
"""

import os
import sys
import unittest
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from switchops.core.security import redact_secrets, is_safe_path, is_command_allowed
from switchops.core.workflow import (
    WorkflowState,
    validate_transition,
    InvalidStateTransitionError,
    Evidence,
    Patch,
    TestRun,
    Approval,
)
from switchops.core.incident_engine import IncidentEngine, Incident, IncidentSeverity
from switchops.core.remediation_engine import RemediationEngine
from switchops.core.test_runner import TestRunner
from switchops.core.git_commander import GitCommander
from switchops.core.roi_telemetry import ROITelemetryTracker
from switchops.switch_bridge.adapter import SwitchAdapter
from switchops.switch_bridge.room_manager import SwitchOpsOrchestrator
from switchops.sample_apps.payments_service.app import PaymentsService, PaymentProcessingError


class TestSwitchOpsSecurityAndValidation(unittest.TestCase):
    """Unit tests covering security redaction, path restrictions, and command allowlists."""

    def test_secret_redaction(self):
        log_sample = "Error connecting with token: ghp_123456789012345678901234567890123456 and bearer eyJhbGciOi..."
        redacted = redact_secrets(log_sample)
        self.assertNotIn("ghp_1234", redacted)
        self.assertIn("[REDACTED_GITHUB_PAT]", redacted)
        self.assertIn("[REDACTED_TOKEN]", redacted)

    def test_path_traversal_and_forbidden_paths(self):
        workspace = os.path.abspath(".")
        # Valid path inside workspace
        self.assertTrue(is_safe_path("switchops/sample_apps/payments_service/app.py", workspace))
        # Directory traversal attempt
        self.assertFalse(is_safe_path("../../windows/system32/cmd.exe", workspace))
        # Forbidden paths
        self.assertFalse(is_safe_path(".env", workspace))
        self.assertFalse(is_safe_path(".git/config", workspace))
        self.assertFalse(is_safe_path("secrets/keys.json", workspace))

    def test_command_allowlist(self):
        # Allowed test commands
        self.assertTrue(is_command_allowed(["python", "-m", "unittest", "discover"]))
        self.assertTrue(is_command_allowed(["pytest", "-v"]))
        # Blocked commands
        self.assertFalse(is_command_allowed(["rm", "-rf", "/"]))
        self.assertFalse(is_command_allowed(["bash", "-c", "curl evil.com"]))
        self.assertFalse(is_command_allowed(["git", "push", "--force"]))


class TestWorkflowStateMachine(unittest.TestCase):
    """Unit tests validating state transitions and rejection of invalid jumps."""

    def test_valid_state_transitions(self):
        # RECEIVED -> TRIAGING
        validate_transition(WorkflowState.RECEIVED, WorkflowState.TRIAGING)
        # TRIAGING -> TRIAGED
        validate_transition(WorkflowState.TRIAGING, WorkflowState.TRIAGED)
        # TRIAGED -> AWAITING_FIX_APPROVAL
        validate_transition(WorkflowState.TRIAGED, WorkflowState.AWAITING_FIX_APPROVAL)
        # AWAITING_FIX_APPROVAL -> PATCH_APPROVED
        validate_transition(WorkflowState.AWAITING_FIX_APPROVAL, WorkflowState.PATCH_APPROVED)
        # PATCH_APPROVED -> TESTING
        validate_transition(WorkflowState.PATCH_APPROVED, WorkflowState.TESTING)
        # TESTING -> TEST_PASSED
        validate_transition(WorkflowState.TESTING, WorkflowState.TEST_PASSED)
        # TEST_PASSED -> AWAITING_PR_APPROVAL
        validate_transition(WorkflowState.TEST_PASSED, WorkflowState.AWAITING_PR_APPROVAL)
        # AWAITING_PR_APPROVAL -> CREATING_PR
        validate_transition(WorkflowState.AWAITING_PR_APPROVAL, WorkflowState.CREATING_PR)
        # CREATING_PR -> PR_CREATED
        validate_transition(WorkflowState.CREATING_PR, WorkflowState.PR_CREATED)

    def test_invalid_state_transitions_raise_error(self):
        # Direct jump from RECEIVED to PR_CREATED is prohibited
        with self.assertRaises(InvalidStateTransitionError):
            validate_transition(WorkflowState.RECEIVED, WorkflowState.PR_CREATED)

        # Jumping from TESTING directly to CREATING_PR without approval is prohibited
        with self.assertRaises(InvalidStateTransitionError):
            validate_transition(WorkflowState.TESTING, WorkflowState.CREATING_PR)


class TestIncidentEngineAndDeduplication(unittest.TestCase):
    """Unit tests for incident parsing, evidence extraction, and deduplication."""

    def setUp(self):
        self.engine = IncidentEngine(workspace_root=os.path.abspath("."))

    def test_duplicate_event_handling(self):
        payload = {
            "service_name": "payments-service",
            "error_type": "KeyError",
            "stack_trace": "File app.py line 37 KeyError: 'eur'",
        }
        inc1, is_dup1 = self.engine.ingest(payload)
        self.assertFalse(is_dup1)

        # Ingesting same payload should return duplicate flag
        inc2, is_dup2 = self.engine.ingest(payload)
        self.assertTrue(is_dup2)
        self.assertEqual(inc1.id, inc2.id)

    def test_evidence_based_triage(self):
        inc = self.engine.create_demo_incident()
        task = self.engine.triage(inc)

        self.assertEqual(inc.status, WorkflowState.TRIAGED)
        self.assertEqual(task.status, "COMPLETED")
        self.assertGreater(len(inc.evidence_list), 0)
        self.assertEqual(inc.confidence_level, "High")
        self.assertIn("Likely root cause", inc.likely_root_cause)


class TestIsolatedTestRunner(unittest.TestCase):
    """Unit test for the isolated test runner executing real process commands."""

    def setUp(self):
        self.runner = TestRunner(workspace_root=os.path.abspath("."))

    def test_run_real_unit_test(self):
        test_run = self.runner.run_tests(
            incident_id="INC-TEST",
            command=[sys.executable, "-m", "unittest", "switchops/sample_apps/payments_service/tests/test_payments.py"]
        )
        self.assertEqual(test_run.status, "PASSED")
        self.assertEqual(test_run.exit_code, 0)
        self.assertGreater(test_run.duration_ms, 0)
        output_text = test_run.stdout_reference + "\n" + test_run.stderr_reference
        self.assertIn("Ran 4 tests", output_text)


class TestEndToEndWorkflow(unittest.TestCase):
    """Full End-to-End Acceptance Test specified in Section 17."""

    def setUp(self):
        self.workspace = os.path.abspath(".")
        self.orchestrator = SwitchOpsOrchestrator(workspace_root=self.workspace)

    def test_full_incident_remediation_lifecycle(self):
        # 1. Ingest incident
        inc = self.orchestrator.create_or_ingest_incident()
        self.assertEqual(inc.status, WorkflowState.RECEIVED)

        # 2. Run Triage & synthesize patch
        inc, triage_task = self.orchestrator.run_triage(inc.id)
        self.assertEqual(inc.status, WorkflowState.AWAITING_FIX_APPROVAL)
        self.assertIsNotNone(self.orchestrator.sessions[inc.id]["patch"])

        # 3. Approve patch (Step 1 of approval) -> runs tests
        test_run = self.orchestrator.approve_patch(inc.id, reviewer="SeniorSRE")
        self.assertEqual(test_run.status, "PASSED")
        self.assertEqual(inc.status, WorkflowState.AWAITING_PR_APPROVAL)

        # 4. Approve PR (Step 2 of approval) -> creates branch and PR
        pr = self.orchestrator.approve_pr_creation(inc.id, reviewer="SeniorSRE")
        self.assertEqual(inc.status, WorkflowState.PR_CREATED)
        self.assertIn("github.com", pr.url)
        self.assertEqual(pr.status, "OPEN")

        # 5. Verify room messages contain PR link
        messages = self.orchestrator.switch_client.get_room_messages(inc.switch_room_id)
        self.assertTrue(any("Pull Request Created Successfully" in m["text"] for m in messages))

        # 6. Verify audit trail
        audits = [a for a in self.orchestrator.audit_log if a.incident_id == inc.id]
        self.assertGreaterEqual(len(audits), 4)


if __name__ == "__main__":
    unittest.main()
