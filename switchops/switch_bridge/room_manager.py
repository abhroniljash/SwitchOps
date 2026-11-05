"""
Orchestrator: Owns the multi-agent incident workflow state machine,
routes tasks between specialized agents, records audit events and approvals,
and dispatches updates to the Switch room.
"""

import time
from typing import Dict, Any, Optional, List, Tuple

from .adapter import SwitchAdapter, NormalizedSwitchEvent
from .client import SwitchClient
from .platform_adapters import PlatformAdapters
from ..core.incident_engine import IncidentEngine, Incident, IncidentSeverity
from ..core.remediation_engine import RemediationEngine
from ..core.test_runner import TestRunner
from ..core.git_commander import GitCommander, PullRequest
from ..core.roi_telemetry import ROITelemetryTracker
from ..core.database import Database
from ..core.workflow import (
    WorkflowState,
    validate_transition,
    Evidence,
    AgentTask,
    Patch,
    TestRun,
    Approval,
    AuditEvent,
)


class SwitchOpsOrchestrator:
    """Coordinates the full lifecycle of human-AI incident collaboration via Switch."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root
        self.db = Database()
        self.switch_adapter = SwitchAdapter()
        self.switch_client = SwitchClient(is_simulation=False)
        self.incident_engine = IncidentEngine(workspace_root=workspace_root)
        self.remediation_engine = RemediationEngine(workspace_root=workspace_root)
        self.test_runner = TestRunner(workspace_root=workspace_root)
        self.git_commander = GitCommander(workspace_root=workspace_root)
        self.telemetry = ROITelemetryTracker()

        # In-memory storage of incident workflows and history
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.agent_tasks: List[AgentTask] = []
        self.audit_log: List[AuditEvent] = []
        self.active_room_id: Optional[str] = None

        # Restore past incident records from SQLite database
        self._load_persisted_incidents()

    def _load_persisted_incidents(self):
        """Restores past incidents from SQLite into engine registry."""
        try:
            persisted = self.db.load_all_incidents()
            for row in persisted:
                sev_val = (row.get("severity") or "High").capitalize()
                sev = IncidentSeverity(sev_val) if sev_val in IncidentSeverity._value2member_map_ else IncidentSeverity.HIGH
                status_str = row.get("status") or "RECEIVED"
                try:
                    wf_status = WorkflowState(status_str)
                except Exception:
                    wf_status = WorkflowState.RECEIVED

                inc = Incident(
                    id=row["id"],
                    source=row.get("source", "db"),
                    service_name=row.get("service_name", "payments-service"),
                    environment=row.get("environment", "demo"),
                    severity=sev,
                    severity_reason=row.get("severity_reason", ""),
                    summary=row.get("summary", ""),
                    logs=row.get("logs", ""),
                    stack_trace=row.get("stack_trace"),
                    repository=row.get("repository", "org/payments-service"),
                    created_at=row.get("created_at", time.time()),
                    switch_room_id=row.get("switch_room_id"),
                    status=wf_status,
                    error_type=row.get("error_type", "Error"),
                    error_message=row.get("error_message", ""),
                    correlation_id=row.get("correlation_id"),
                    affected_file=row.get("affected_file"),
                    line_number=row.get("line_number"),
                    likely_root_cause=row.get("likely_root_cause"),
                    recommended_fix=row.get("recommended_fix"),
                    confidence_level=row.get("confidence_level", "Medium"),
                    confidence_explanation=row.get("confidence_explanation", ""),
                    event_fingerprint=row.get("event_fingerprint"),
                    llm_assisted=bool(row.get("llm_assisted", 0)),
                )
                self.incident_engine.incidents[inc.id] = inc
                if inc.event_fingerprint:
                    self.incident_engine.fingerprint_cache[inc.event_fingerprint] = inc.id
                
                # Reconstruct session
                self.sessions[inc.id] = {
                    "incident": inc,
                    "room_id": inc.switch_room_id or f"room_{inc.id.lower()}",
                    "room_name": f"incident-{inc.id.lower()}",
                    "patch": None,
                    "test_run": None,
                    "pull_request": None,
                    "approvals": [],
                    "start_time": inc.created_at,
                }
                self.active_room_id = inc.switch_room_id or self.active_room_id
        except Exception as e:
            print(f"[Orchestrator] Warning restoring past incidents from DB: {e}")

    def _record_audit(self, incident_id: str, actor: str, action: str, result: str = "SUCCESS", meta: dict = None):
        event = AuditEvent(
            incident_id=incident_id,
            actor=actor,
            action=action,
            result=result,
            metadata=meta or {}
        )
        self.audit_log.append(event)
        self.db.save_audit_event(event)
        return event

    def create_or_ingest_incident(self, payload: Optional[Dict[str, Any]] = None) -> Incident:
        """Step 1: Ingests an incoming alert or creates a demo incident in RECEIVED state."""
        if payload:
            incident, is_dup = self.incident_engine.ingest(payload)
        else:
            incident = self.incident_engine.create_demo_incident()

        incident.status = WorkflowState.RECEIVED
        self.telemetry.start_incident(incident.id)

        # Create or bind collaborative Switch Room
        room_name = f"incident-{incident.id.lower()}"
        topic = f"🚨 {incident.severity.value} Incident: {incident.summary}"
        room = self.switch_client.create_room(
            name=room_name,
            topic=topic,
            agents=["TriageAgent", "RemediationAgent", "TestRunner", "GitOpsAgent"]
        )
        incident.switch_room_id = room["id"]
        self.active_room_id = room["id"]

        # Initialize session state
        self.sessions[incident.id] = {
            "incident": incident,
            "room_id": incident.switch_room_id,
            "room_name": room_name,
            "patch": None,
            "test_run": None,
            "pull_request": None,
            "approvals": [],
            "start_time": time.time(),
        }

        self.db.save_incident(incident)
        self._record_audit(incident.id, "MonitoringSystem", "INCIDENT_RECEIVED", meta={"service": incident.service_name})

        # Post notice to Switch Room
        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender="SwitchOps-System",
            role="system",
            text=f"🚨 **Incident Ingested:** `{incident.id}` ({incident.severity.value}) in `{incident.service_name}`. Initialized in state `RECEIVED`."
        )

        return incident

    def run_triage(self, incident_id: str) -> Tuple[Incident, AgentTask]:
        """Step 2: Executes evidence-based triage and transitions to TRIAGED -> AWAITING_FIX_APPROVAL."""
        session = self.sessions.get(incident_id)
        if not session:
            raise KeyError(f"Incident {incident_id} not found")

        incident: Incident = session["incident"]
        validate_transition(incident.status, WorkflowState.TRIAGING)

        # Notify room
        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender="SwitchOps-TriageAgent",
            role="agent",
            text="🔍 **Triage Agent:** Investigating stack trace and extracting repository evidence..."
        )

        triage_start = time.time()
        task = self.incident_engine.triage(incident)
        triage_duration = time.time() - triage_start
        self.agent_tasks.append(task)
        self.telemetry.record_triage(incident.id, triage_duration)

        self.db.save_incident(incident)
        self.db.save_agent_task(task)
        for evi in incident.evidence_list:
            self.db.save_evidence(evi)

        self._record_audit(incident.id, "TriageAgent", "TRIAGE_COMPLETED", meta={"confidence": incident.confidence_level})

        # Report evidence in room
        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender="SwitchOps-TriageAgent",
            role="agent",
            text=(
                f"💡 **Triage Findings ({incident.confidence_level} Confidence):**\n"
                f"{incident.likely_root_cause}\n"
                f"- **Affected File:** `{incident.affected_file}` (line {incident.line_number})\n"
                f"- **Recommended Fix:** {incident.recommended_fix}"
            )
        )

        # Automatically synthesize proposed patch
        self.run_remediation(incident_id)

        return incident, task

    def run_remediation(self, incident_id: str) -> Tuple[Patch, AgentTask]:
        """Step 3: Remediation Agent synthesizes minimal patch and requests human fix approval."""
        session = self.sessions.get(incident_id)
        incident: Incident = session["incident"]

        validate_transition(incident.status, WorkflowState.AWAITING_FIX_APPROVAL)

        patch, task = self.remediation_engine.generate_patch(incident)
        session["patch"] = patch
        self.agent_tasks.append(task)
        incident.status = WorkflowState.AWAITING_FIX_APPROVAL
        self.db.save_incident(incident)
        self.db.save_patch(patch)
        self.db.save_agent_task(task)
        self._record_audit(incident.id, "RemediationAgent", "PATCH_GENERATED", meta={"files": patch.files_changed})

        # Post Human-in-the-Loop Fix Approval Card into the Switch room
        approval_prompt = (
            f"📋 **Human-in-the-Loop Approval Required (Step 1 of 2):**\n\n"
            f"**Proposed Patch for `{patch.files_changed[0]}`:**\n"
            f"```diff\n{patch.diff}\n```\n"
            f"**Risk Notes:** `{patch.risk_notes}`\n\n"
            f"👉 *Type `approve` to authorize running isolated validation tests, or `reject` to dismiss.*"
        )

        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender="SwitchOps-RemediationAgent",
            role="agent",
            text=approval_prompt,
            metadata={"requires_fix_approval": True, "patch_id": patch.id}
        )

        return patch, task

    def approve_patch(self, incident_id: str, reviewer: str = "OnCallEngineer", comment: str = "") -> TestRun:
        """Step 4: User approves proposed patch -> transitions to PATCH_APPROVED -> runs isolated tests."""
        session = self.sessions.get(incident_id)
        incident: Incident = session["incident"]
        patch: Patch = session["patch"]

        validate_transition(incident.status, WorkflowState.PATCH_APPROVED)
        incident.status = WorkflowState.PATCH_APPROVED
        patch.approval_status = "APPROVED"

        approval = Approval(
            incident_id=incident.id,
            action_type="PATCH_APPROVAL",
            decision="APPROVED",
            reviewer=reviewer,
            comment=comment or "Patch approved for testing."
        )
        session["approvals"].append(approval)
        self.telemetry.record_approval(incident.id)
        self.db.save_approval(approval)
        self._record_audit(incident.id, reviewer, "PATCH_APPROVED")

        # Post approval acknowledgment
        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender=reviewer,
            role="user",
            text=f"✅ Patch approved by {reviewer}. Commencing isolated validation tests."
        )

        # Move to TESTING and apply the approved code patch to disk
        validate_transition(incident.status, WorkflowState.TESTING)
        incident.status = WorkflowState.TESTING
        self.remediation_engine.apply_patch(patch)

        # Execute isolated test runner against the patched code
        test_task = AgentTask(
            incident_id=incident.id,
            agent_type="TestRunner",
            status="STARTED",
            input_summary="Executing allowlisted test suite against patched code"
        )

        test_run = self.test_runner.run_tests(incident.id)
        session["test_run"] = test_run
        test_task.status = "COMPLETED"
        test_task.completed_at = time.time()
        test_task.output_summary = f"Test status: {test_run.status} (exit code: {test_run.exit_code}, {test_run.duration_ms}ms)"
        self.agent_tasks.append(test_task)
        self.db.save_test_run(test_run)
        self.db.save_agent_task(test_task)

        passed = (test_run.status == "PASSED")
        self.telemetry.record_test_run(incident.id, passed, test_run.duration_ms)

        if passed:
            validate_transition(incident.status, WorkflowState.TEST_PASSED)
            incident.status = WorkflowState.TEST_PASSED
            self._record_audit(incident.id, "TestRunner", "TESTS_PASSED", meta={"exit_code": test_run.exit_code})

            # Transition to AWAITING_PR_APPROVAL (Step 2 of approval)
            validate_transition(incident.status, WorkflowState.AWAITING_PR_APPROVAL)
            incident.status = WorkflowState.AWAITING_PR_APPROVAL

            pr_approval_prompt = (
                f"🧪 **Automated Validation Tests: PASSED ✅**\n"
                f"- **Command:** `{test_run.command_profile}`\n"
                f"- **Exit Code:** `0` | **Duration:** `{test_run.duration_ms}ms`\n\n"
                f"📋 **Human-in-the-Loop Approval Required (Step 2 of 2):**\n"
                f"Validation succeeded. Authorize creating branch and opening GitHub Pull Request?\n"
                f"👉 *Type `approve pr` to create PR, or `reject` to cancel.*"
            )
            self.switch_client.send_message(
                room_id=incident.switch_room_id,
                sender="SwitchOps-TestRunner",
                role="agent",
                text=pr_approval_prompt,
                metadata={"requires_pr_approval": True}
            )
        else:
            validate_transition(incident.status, WorkflowState.TEST_FAILED)
            incident.status = WorkflowState.TEST_FAILED
            self._record_audit(incident.id, "TestRunner", "TESTS_FAILED", meta={"exit_code": test_run.exit_code})

            self.switch_client.send_message(
                room_id=incident.switch_room_id,
                sender="SwitchOps-TestRunner",
                role="agent",
                text=f"❌ **Validation Tests Failed (Exit Code: {test_run.exit_code}):**\n```{test_run.stderr_reference or test_run.stdout_reference}```\nWorkflow halted for human review."
            )

        return test_run

    def approve_pr_creation(self, incident_id: str, reviewer: str = "OnCallEngineer", comment: str = "") -> PullRequest:
        """Step 5: User approves opening PR -> transitions to CREATING_PR -> PR_CREATED."""
        session = self.sessions.get(incident_id)
        incident: Incident = session["incident"]
        patch: Patch = session["patch"]
        test_run: TestRun = session["test_run"]

        validate_transition(incident.status, WorkflowState.CREATING_PR)
        incident.status = WorkflowState.CREATING_PR

        approval = Approval(
            incident_id=incident.id,
            action_type="PR_APPROVAL",
            decision="APPROVED",
            reviewer=reviewer,
            comment=comment or "PR creation authorized."
        )
        session["approvals"].append(approval)
        self.telemetry.record_approval(incident.id)
        self.db.save_approval(approval)
        self._record_audit(incident.id, reviewer, "PR_CREATION_APPROVED")

        # GitOps Agent creates branch and PR
        pr_start = time.time()
        pr, task = self.git_commander.create_pull_request(incident, patch, test_run)
        pr_duration = time.time() - pr_start

        session["pull_request"] = pr
        self.agent_tasks.append(task)
        self.telemetry.record_pr_created(incident.id, pr_duration)
        self.db.save_agent_task(task)

        validate_transition(incident.status, WorkflowState.PR_CREATED)
        incident.status = WorkflowState.PR_CREATED
        self.db.save_incident(incident)
        self._record_audit(incident.id, "GitOpsAgent", "PR_CREATED", meta={"url": pr.url, "pr_number": pr.pr_number})

        # Post PR link to originating Switch room
        resolution_msg = (
            f"🚀 **Pull Request Created Successfully!**\n\n"
            f"- **PR Link:** [{pr.title}]({pr.url})\n"
            f"- **Branch:** `{pr.branch}` (Base: `{pr.base_branch}`)\n"
            f"- **Status:** `{pr.status}` (Verified with real test suite)\n\n"
            f"ℹ️ *Human review required on GitHub before merge. No automatic production deployment performed.*"
        )
        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender="SwitchOps-GitOpsAgent",
            role="agent",
            text=resolution_msg,
            metadata={"pull_request": pr.to_dict()}
        )

        return pr

    def reject_workflow(self, incident_id: str, reviewer: str = "OnCallEngineer", reason: str = "") -> Incident:
        """Rejects the current proposed fix or PR and halts the workflow."""
        session = self.sessions.get(incident_id)
        incident: Incident = session["incident"]
        patch: Patch = session.get("patch")

        # Revert any applied disk patches upon rejection
        if patch:
            self.remediation_engine.revert_patch(patch)

        validate_transition(incident.status, WorkflowState.REJECTED)
        incident.status = WorkflowState.REJECTED

        approval = Approval(
            incident_id=incident.id,
            action_type="WORKFLOW_REJECTION",
            decision="REJECTED",
            reviewer=reviewer,
            comment=reason or "Rejected by human operator."
        )
        session["approvals"].append(approval)
        self._record_audit(incident.id, reviewer, "WORKFLOW_REJECTED", meta={"reason": reason})

        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender=reviewer,
            role="user",
            text=f"❌ Workflow rejected by {reviewer}. Reason: {reason or 'Manual review required.'}"
        )
        return incident

    def retry_remediation(self, incident_id: str, reviewer: str = "OnCallEngineer") -> Tuple[Patch, AgentTask]:
        """
        Bounded Retry: When tests fail or an operator requests a revised fix,
        analyzes failure output and synthesizes an alternative patch.
        Transitions state from TEST_FAILED -> AWAITING_FIX_APPROVAL.
        """
        session = self.sessions.get(incident_id)
        if not session:
            raise KeyError(f"Incident {incident_id} not found")

        incident: Incident = session["incident"]
        test_run: Optional[TestRun] = session.get("test_run")

        validate_transition(incident.status, WorkflowState.AWAITING_FIX_APPROVAL)

        patch, task = self.remediation_engine.suggest_alternative_fix(incident, test_run)
        session["patch"] = patch
        self.agent_tasks.append(task)
        incident.status = WorkflowState.AWAITING_FIX_APPROVAL
        self.db.save_incident(incident)
        self.db.save_patch(patch)
        self.db.save_agent_task(task)
        self._record_audit(incident.id, "RemediationAgent", "ALTERNATIVE_PATCH_GENERATED", meta={"files": patch.files_changed})

        retry_prompt = (
            f"🔄 **Alternative Remediation Synthesized (Iteration 2):**\n\n"
            f"**Refined Patch for `{patch.files_changed[0]}`:**\n"
            f"```diff\n{patch.diff}\n```\n"
            f"**Risk Notes:** `{patch.risk_notes}`\n\n"
            f"👉 *Type `approve` to authorize running isolated validation tests, or `reject` to dismiss.*"
        )
        self.switch_client.send_message(
            room_id=incident.switch_room_id,
            sender="SwitchOps-RemediationAgent",
            role="agent",
            text=retry_prompt,
            metadata={"requires_fix_approval": True, "patch_id": patch.id}
        )
        return patch, task

    def handle_incoming_switch_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """Processes normalized incoming Switch events with idempotency and room routing."""
        normalized, is_duplicate = self.switch_adapter.validate_and_normalize(raw_event)
        if is_duplicate:
            return {"status": "ignored", "reason": "duplicate_event_id"}
        if not normalized:
            return {"status": "error", "reason": "invalid_payload"}

        # Find incident associated with room
        incident_id = None
        for inc_id, sess in self.sessions.items():
            if sess.get("room_id") == normalized.room_id:
                incident_id = inc_id
                break

        msg_lower = normalized.message.strip().lower()

        # Route chat decisions
        if not incident_id:
            # If no active incident in room, start demo incident
            if any(w in msg_lower for w in ["incident", "triage", "fix", "error", "500"]):
                inc = self.create_or_ingest_incident()
                self.run_triage(inc.id)
                return {"status": "incident_started", "incident_id": inc.id}
            return {"status": "acknowledged", "reply": "No active incident room bound."}

        session = self.sessions[incident_id]
        current_status = session["incident"].status

        if any(w in msg_lower for w in ["approve", "lgtm", "yes", "proceed"]):
            if current_status == WorkflowState.AWAITING_FIX_APPROVAL:
                self.approve_patch(incident_id, reviewer=normalized.sender)
                return {"status": "patch_approved", "next_state": session["incident"].status.value}
            elif current_status == WorkflowState.AWAITING_PR_APPROVAL:
                self.approve_pr_creation(incident_id, reviewer=normalized.sender)
                return {"status": "pr_created", "next_state": session["incident"].status.value}
        elif any(w in msg_lower for w in ["retry", "alternative", "fix again", "re-patch"]):
            if current_status == WorkflowState.TEST_FAILED:
                self.retry_remediation(incident_id, reviewer=normalized.sender)
                return {"status": "alternative_patch_generated", "next_state": session["incident"].status.value}
        elif any(w in msg_lower for w in ["reject", "cancel", "no", "stop"]):
            self.reject_workflow(incident_id, reviewer=normalized.sender, reason=normalized.message)
            return {"status": "rejected", "next_state": "REJECTED"}

        # Echo acknowledgment back into Switch room
        self.switch_client.send_message(
            room_id=normalized.room_id,
            sender=normalized.sender,
            role="user",
            text=normalized.message
        )
        return {"status": "message_routed", "current_state": current_status.value}
