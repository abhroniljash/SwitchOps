"""
Comprehensive Test Suite for SwitchOps.
Tests Incident RCA, Remediation Synthesis, Git Operations, Switch Bridge, and ROI Metrics.
"""

import unittest
import os
import sys

# Ensure root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from switchops.core.incident_engine import IncidentEngine, IncidentSeverity, IncidentStatus
from switchops.core.remediation_engine import RemediationEngine
from switchops.core.git_commander import GitCommander
from switchops.core.roi_telemetry import ROITelemetryTracker
from switchops.switch_bridge.room_manager import SwitchOpsOrchestrator
from switchops.switch_bridge.wispr_voice import WisprVoiceAdapter
from switchops.sample_apps.payments_service.app import PaymentsService, PaymentProcessingError


class TestSwitchOps(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.app_path = os.path.join(self.workspace_root, "switchops", "sample_apps", "payments_service", "app.py")
        if os.path.exists(self.app_path):
            with open(self.app_path, "r", encoding="utf-8") as f:
                self.original_app_code = f.read()
        else:
            self.original_app_code = ""
        self.orchestrator = SwitchOpsOrchestrator(workspace_root=self.workspace_root, is_simulation=True)

    def tearDown(self):
        if self.original_app_code and os.path.exists(self.app_path):
            with open(self.app_path, "w", encoding="utf-8") as f:
                f.write(self.original_app_code)

    def test_payments_service_bug_reproduction(self):
        service = PaymentsService()
        # Uppercase works fine
        res = service.process_checkout({
            "order_id": "ORD-OK",
            "items": [{"name": "Book", "price": 10.0, "quantity": 1}],
            "currency": "USD",
            "payment_method": "credit_card"
        })
        self.assertEqual(res["status"], "SETTLED")

        # Lowercase 'eur' triggers KeyError before remediation
        with self.assertRaises(KeyError):
            service.process_checkout({
                "order_id": "ORD-BUG",
                "items": [{"name": "Book", "price": 10.0, "quantity": 1}],
                "currency": "eur",
                "payment_method": "credit_card"
            })

    def test_incident_engine_rca(self):
        engine = IncidentEngine(workspace_root=self.workspace_root)
        incident = engine.create_demo_incident()
        self.assertEqual(incident.severity, IncidentSeverity.CRITICAL)

        engine.analyze(incident)
        self.assertEqual(incident.status, IncidentStatus.DIAGNOSED)
        self.assertIsNotNone(incident.affected_file)
        self.assertIn("KeyError", incident.root_cause_summary)

    def test_remediation_proposal_generation(self):
        engine = IncidentEngine(workspace_root=self.workspace_root)
        incident = engine.create_demo_incident()
        engine.analyze(incident)

        remediation = RemediationEngine(workspace_root=self.workspace_root)
        proposal = remediation.generate_fix(incident)

        self.assertTrue(proposal.tests_passed)
        self.assertIn("upper", proposal.patched_code)
        self.assertIn("test_regression_lowercase_currency", proposal.regression_test_name)

    def test_git_commander_pr_generation(self):
        git = GitCommander(workspace_root=self.workspace_root, repo_name="wemakedevs/payments-service")
        engine = IncidentEngine(workspace_root=self.workspace_root)
        incident = engine.create_demo_incident()
        remediation = RemediationEngine(workspace_root=self.workspace_root)
        proposal = remediation.generate_fix(incident)

        pr = git.open_pull_request(incident, proposal)
        self.assertIn("HOTFIX", pr.title)
        self.assertIn("wemakedevs/payments-service/pull", pr.url)
        self.assertEqual(pr.status, "OPEN")

    def test_switch_roi_telemetry(self):
        tracker = ROITelemetryTracker()
        metric = tracker.record_incident_resolution("INC-TEST", duration_seconds=75.0, tokens_consumed=2500)
        self.assertGreater(metric.mttr_reduction_percent, 90.0)
        self.assertGreater(metric.total_value_delivered_usd, 1000.0)
        self.assertGreater(metric.roi_multiplier, 100.0)

    def test_wispr_voice_parsing(self):
        adapter = WisprVoiceAdapter()
        res_approve = adapter.parse_dictation("Looks great, please approve and open the PR")
        self.assertEqual(res_approve.detected_intent, "APPROVE_REMEDIATION")

        res_triage = adapter.parse_dictation("SwitchOps investigate the checkout failure")
        self.assertEqual(res_triage.detected_intent, "TRIAGE_AND_REMEDIATE")

        scorecard = adapter.generate_wispr_scorecard()
        self.assertTrue(scorecard["wispr_flow_enabled"])

    def test_full_orchestrator_lifecycle(self):
        session = self.orchestrator.start_incident_workflow()
        room_id = session["room_id"]
        self.assertEqual(session["status"], "AWAITING_APPROVAL")

        # Human approves
        res = self.orchestrator.handle_user_input(room_id, "Approve and ship it")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertIsNotNone(res["pull_request"])
        self.assertIsNotNone(res["roi"])


if __name__ == "__main__":
    unittest.main()
