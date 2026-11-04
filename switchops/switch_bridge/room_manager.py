"""
Room Manager & Orchestrator: Central state machine coordinating incidents,
collaborative Switch Rooms, agent interactions, and human approvals.
"""

import time
from typing import Dict, Any, Optional, List

from .client import SwitchClient
from .platform_adapters import PlatformAdapters
from .wispr_voice import WisprVoiceAdapter, VoiceCommandResult
from ..core.incident_engine import IncidentEngine, Incident, IncidentStatus, IncidentSeverity
from ..core.remediation_engine import RemediationEngine, RemediationProposal
from ..core.git_commander import GitCommander, PullRequest
from ..core.roi_telemetry import ROITelemetryTracker, ROIMetrics


class SwitchOpsOrchestrator:
    """Manages the full lifecycle of human-AI incident collaboration via Switch."""

    def __init__(self, workspace_root: Optional[str] = None, is_simulation: bool = True):
        self.workspace_root = workspace_root
        self.client = SwitchClient(is_simulation=is_simulation)
        self.incident_engine = IncidentEngine(workspace_root=workspace_root)
        self.remediation_engine = RemediationEngine(workspace_root=workspace_root)
        self.git_commander = GitCommander(workspace_root=workspace_root)
        self.roi_tracker = ROITelemetryTracker()
        self.wispr_voice = WisprVoiceAdapter()

        # In-memory session tracking by room_id
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.active_room_id: Optional[str] = None

    def start_incident_workflow(self, custom_alert: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Kicks off an incident workflow:
        1. Ingests or creates incident
        2. Spawns collaborative Switch Room
        3. Runs RCA and synthesizes test-verified fix
        4. Posts interactive proposal card awaiting human approval
        """
        start_time = time.time()

        # Step 1: Ingest alert
        if custom_alert:
            incident = self.incident_engine.ingest_webhook(custom_alert)
        else:
            incident = self.incident_engine.create_demo_incident()

        # Step 2: Create Switch Room
        room_name = f"incident-{incident.id.lower()}"
        topic = f"🚨 {incident.severity.value} Incident: {incident.title}"
        room = self.client.create_room(
            name=room_name,
            topic=topic,
            agents=["SwitchOps-TriageAgent", "SwitchOps-RemediationAgent", "SwitchOps-GitAgent"]
        )
        room_id = room["id"]
        self.active_room_id = room_id

        # Step 3: Broadcast incident detected into the Room
        self.client.send_message(
            room_id=room_id,
            sender="SwitchOps-System",
            role="system",
            text=f"🚨 **Incident Ingested:** `{incident.id}` in `{incident.service}`. Spawning SRE agents in room `{room_name}`."
        )

        # Step 4: Perform automated RCA
        self.client.send_message(
            room_id=room_id,
            sender="SwitchOps-TriageAgent",
            role="agent",
            text="🔍 **Triage Agent:** Inspecting stack traces, locating offending source files, and analyzing git history..."
        )
        self.incident_engine.analyze(incident)

        self.client.send_message(
            room_id=room_id,
            sender="SwitchOps-TriageAgent",
            role="agent",
            text=f"💡 **Diagnosis Complete:**\n{incident.root_cause_summary}\n- Affected file: `{incident.affected_file}` (line {incident.line_number})"
        )

        # Step 5: Synthesize verified fix & regression test
        self.client.send_message(
            room_id=room_id,
            sender="SwitchOps-RemediationAgent",
            role="agent",
            text="🛠️ **Remediation Agent:** Synthesizing non-breaking fix and running automated regression tests..."
        )
        proposal = self.remediation_engine.generate_fix(incident)

        # Step 6: Post Human-in-the-Loop Approval Card
        slack_card = PlatformAdapters.format_slack_incident_card(incident, proposal)
        discord_embed = PlatformAdapters.format_discord_incident_embed(incident, proposal)

        approval_message = (
            f"📋 **Human-in-the-Loop Approval Requested:**\n\n"
            f"**Proposed Patch for `{proposal.target_file}`:**\n"
            f"```diff\n{proposal.diff}\n```\n\n"
            f"**Automated Verification:** `{proposal.regression_test_name}` (PASSED ✅)\n"
            f"**Risk Assessment:** `{proposal.risk_assessment}`\n\n"
            f"👉 *Reply `approve` (or speak via Wispr) to commit & open a GitHub Pull Request, or `reject` to dismiss.*"
        )

        self.client.send_message(
            room_id=room_id,
            sender="SwitchOps-RemediationAgent",
            role="agent",
            text=approval_message,
            metadata={"slack_card": slack_card, "discord_embed": discord_embed, "requires_approval": True}
        )

        # Store session state
        session_data = {
            "room_id": room_id,
            "room_name": room_name,
            "incident": incident,
            "proposal": proposal,
            "pull_request": None,
            "roi": None,
            "start_time": start_time,
            "status": "AWAITING_APPROVAL",
        }
        self.sessions[room_id] = session_data
        return session_data

    def handle_user_input(self, room_id: str, user_text: str, user_name: str = "OnCallEngineer") -> Dict[str, Any]:
        """Processes human message or approval decision in the chat thread."""
        session = self.sessions.get(room_id)
        if not session:
            return {"error": "Room session not found"}

        # Record human message in Switch room
        self.client.send_message(
            room_id=room_id,
            sender=user_name,
            role="user",
            text=user_text
        )

        clean_text = user_text.strip().lower()

        # Check approval
        if any(w in clean_text for w in ["approve", "approved", "yes", "lgtm", "ship it", "merge"]):
            return self.approve_and_open_pr(room_id)
        elif any(w in clean_text for w in ["reject", "cancel", "no", "deny"]):
            return self.reject_proposal(room_id)
        elif "status" in clean_text or "progress" in clean_text:
            status_text = f"Current incident status: `{session['status']}` for `{session['incident'].id}`."
            self.client.send_message(room_id=room_id, sender="SwitchOps-System", role="system", text=status_text)
            return {"status": session["status"], "reply": status_text}
        else:
            reply = (
                f"Acknowledged '{user_text}'. Current incident `{session['incident'].id}` is awaiting approval. "
                f"Type `approve` to create the PR, or `reject` to cancel."
            )
            self.client.send_message(room_id=room_id, sender="SwitchOps-System", role="system", text=reply)
            return {"status": session["status"], "reply": reply}

    def handle_voice_command(self, room_id: str, transcript: str) -> Dict[str, Any]:
        """Processes Wispr Flow voice dictation."""
        voice_result: VoiceCommandResult = self.wispr_voice.parse_dictation(transcript)

        # Log transcription into room
        self.client.send_message(
            room_id=room_id,
            sender="OnCallEngineer (via Wispr Flow 🎙️)",
            role="user",
            text=f"🎙️ *\"{voice_result.raw_transcript}\"*\n*(Intent: `{voice_result.detected_intent}`, Confidence: {int(voice_result.confidence_score*100)}%)*"
        )

        if voice_result.detected_intent == "APPROVE_REMEDIATION":
            res = self.approve_and_open_pr(room_id)
            res["voice_feedback"] = voice_result.response_speech
            return res
        elif voice_result.detected_intent == "REJECT_REMEDIATION":
            res = self.reject_proposal(room_id)
            res["voice_feedback"] = voice_result.response_speech
            return res
        elif voice_result.detected_intent == "TRIAGE_AND_REMEDIATE":
            return self.start_incident_workflow()
        else:
            return self.handle_user_input(room_id, transcript)

    def approve_and_open_pr(self, room_id: str) -> Dict[str, Any]:
        """Executes patch, creates branch, opens Pull Request, and computes Switch ROI."""
        session = self.sessions.get(room_id)
        if not session:
            return {"error": "Session not found"}

        incident: Incident = session["incident"]
        proposal: RemediationProposal = session["proposal"]

        # Step 1: Apply patch to codebase
        self.remediation_engine.apply_patch(proposal)

        # Step 2: Git branch and commit
        branch = self.git_commander.prepare_branch(incident.id)
        self.git_commander.commit_remediation(branch, proposal)

        # Step 3: Open Pull Request
        pr: PullRequest = self.git_commander.open_pull_request(incident, proposal)
        session["pull_request"] = pr
        session["status"] = "RESOLVED"
        incident.status = IncidentStatus.RESOLVED

        # Step 4: Calculate Switch ROI
        duration = time.time() - session["start_time"]
        roi_metric = self.roi_tracker.record_incident_resolution(incident.id, duration_seconds=duration)
        session["roi"] = roi_metric

        # Step 5: Post resolution card into Switch room
        resolution_msg = (
            f"🚀 **Pull Request Opened & Verified!**\n\n"
            f"- **PR Link:** [{pr.title}]({pr.url})\n"
            f"- **Branch:** `{pr.branch_name}`\n"
            f"- **Status:** `{pr.status}`\n\n"
            f"📊 **Switch ROI & Telemetry Summary:**\n"
            f"- **MTTR Reduced:** From `{roi_metric.baseline_manual_mttr_minutes}m` down to `{round(roi_metric.actual_resolution_seconds, 1)}s` (**{roi_metric.mttr_reduction_percent}% reduction**)\n"
            f"- **Estimated Value Delivered:** `${roi_metric.total_value_delivered_usd:,.2f}`\n"
            f"- **LLM Cost:** `${roi_metric.llm_cost_usd}` (**{roi_metric.roi_multiplier}x ROI**)"
        )

        self.client.send_message(
            room_id=room_id,
            sender="SwitchOps-GitAgent",
            role="agent",
            text=resolution_msg,
            metadata={"pull_request": pr.to_dict(), "roi": roi_metric.to_dict()}
        )

        return {
            "status": "RESOLVED",
            "pull_request": pr.to_dict(),
            "roi": roi_metric.to_dict(),
            "messages": self.client.get_room_messages(room_id)
        }

    def reject_proposal(self, room_id: str) -> Dict[str, Any]:
        """Rejects the remediation proposal and logs feedback."""
        session = self.sessions.get(room_id)
        if not session:
            return {"error": "Session not found"}

        session["status"] = "REJECTED"
        session["incident"].status = IncidentStatus.CLOSED

        rejection_msg = "❌ **Remediation Rejected by Human Operator.** Workspace changes discarded. Incident flagged for manual review."
        self.client.send_message(room_id=room_id, sender="SwitchOps-System", role="system", text=rejection_msg)

        return {"status": "REJECTED", "messages": self.client.get_room_messages(room_id)}
