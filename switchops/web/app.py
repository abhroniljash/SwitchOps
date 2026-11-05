"""
SwitchOps Web Application & REST API Surface.
Implements the exact REST API endpoints and stateful endpoints specified in Section 14
of the SwitchOps Roadmap, along with the demo 500 endpoint and integration health checks.
"""

import os
import time
from flask import Flask, render_template, request, jsonify

from switchops.switch_bridge.room_manager import SwitchOpsOrchestrator
from switchops.core.incident_engine import IncidentSeverity
from switchops.core.workflow import WorkflowState
from switchops.config import get_config

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")
STATIC_DIR = os.path.join(WEB_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)

config = get_config()
orchestrator = SwitchOpsOrchestrator(workspace_root=os.getcwd())


# =====================================================================
# Controlled Demo Endpoint (Section 6)
# =====================================================================
@app.route("/demo/error-500", methods=["GET", "POST"])
def demo_error_endpoint():
    """Controlled demo endpoint that intentionally simulates a production 500 KeyError."""
    return jsonify({
        "error": "InternalServerError",
        "message": "KeyError: 'eur' in currency conversion during checkout",
        "service": "payments-service",
        "status_code": 500,
        "stack_trace": (
            "Traceback (most recent call last):\n"
            "  File \"switchops/sample_apps/payments_service/app.py\", line 78, in process_checkout\n"
            "    final_amount = self.convert_currency(subtotal_usd, \"USD\", raw_currency)\n"
            "  File \"switchops/sample_apps/payments_service/app.py\", line 37, in convert_currency\n"
            "    to_rate = EXCHANGE_RATES[to_currency]\n"
            "KeyError: 'eur'"
        )
    }), 500


# =====================================================================
# Dashboard HTML
# =====================================================================
@app.route("/")
def index():
    return render_template("index.html")


# =====================================================================
# Section 14: Core API Surface
# =====================================================================

# 1. POST /incidents - Create a manual or demo incident
@app.route("/incidents", methods=["POST"])
@app.route("/api/incidents", methods=["POST"])
@app.route("/api/incident/trigger", methods=["POST"])
def create_incident():
    data = request.get_json(silent=True) or {}
    alert_payload = data.get("alert") or data

    if alert_payload.get("demo") is True or not alert_payload.get("service_name"):
        # Demo incident trigger
        incident = orchestrator.create_or_ingest_incident()
    else:
        # Manual incident submission with input validation
        if not alert_payload.get("summary") and not alert_payload.get("error_message"):
            return jsonify({"error": "Validation Error: 'summary' or 'error_message' is required"}), 400
        incident = orchestrator.create_or_ingest_incident(alert_payload)

    # Automatically trigger triage
    task = None
    try:
        incident, task = orchestrator.run_triage(incident.id)
    except Exception as e:
        print(f"[API] Error running triage: {e}")

    session = orchestrator.sessions[incident.id]
    return jsonify({
        "status": "success",
        "incident_id": incident.id,
        "room_id": incident.switch_room_id,
        "incident": incident.to_dict(),
        "patch": session["patch"].to_dict() if session.get("patch") else None,
        "messages": orchestrator.switch_client.get_room_messages(incident.switch_room_id),
    }), 201


# 2. GET /incidents - List incidents with optional filters
@app.route("/incidents", methods=["GET"])
@app.route("/api/incidents", methods=["GET"])
def list_incidents():
    status_filter = request.args.get("status")
    severity_filter = request.args.get("severity")

    results = []
    for inc in orchestrator.incident_engine.incidents.values():
        if status_filter and inc.status.value.lower() != status_filter.lower():
            continue
        if severity_filter and inc.severity.value.lower() != severity_filter.lower():
            continue
        results.append(inc.to_dict())

    return jsonify({"incidents": results, "total": len(results)})


# 3. GET /incidents/{id} - Read incident details, evidence, and timeline
@app.route("/incidents/<incident_id>", methods=["GET"])
@app.route("/api/incidents/<incident_id>", methods=["GET"])
def get_incident_detail(incident_id):
    session = orchestrator.sessions.get(incident_id)
    if not session:
        return jsonify({"error": f"Incident {incident_id} not found"}), 404

    incident = session["incident"]
    patch = session.get("patch")
    test_run = session.get("test_run")
    pr = session.get("pull_request")
    approvals = session.get("approvals", [])

    return jsonify({
        "incident": incident.to_dict(),
        "patch": patch.to_dict() if patch else None,
        "test_run": test_run.to_dict() if test_run else None,
        "pull_request": pr.to_dict() if pr else None,
        "approvals": [a.to_dict() for a in approvals],
        "audit_events": [e.to_dict() for e in orchestrator.audit_log if e.incident_id == incident_id],
        "messages": orchestrator.switch_client.get_room_messages(incident.switch_room_id),
    })


# 4. POST /incidents/{id}/triage - Start or retry triage
@app.route("/incidents/<incident_id>/triage", methods=["POST"])
@app.route("/api/incidents/<incident_id>/triage", methods=["POST"])
def trigger_triage(incident_id):
    if incident_id not in orchestrator.sessions:
        return jsonify({"error": "Incident not found"}), 404

    try:
        inc, task = orchestrator.run_triage(incident_id)
        return jsonify({"status": "triaged", "incident": inc.to_dict(), "task": task.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# 5. POST /incidents/{id}/patch - Generate proposed remediation patch
@app.route("/incidents/<incident_id>/patch", methods=["POST"])
@app.route("/api/incidents/<incident_id>/patch", methods=["POST"])
def generate_patch_endpoint(incident_id):
    if incident_id not in orchestrator.sessions:
        return jsonify({"error": "Incident not found"}), 404

    try:
        patch, task = orchestrator.run_remediation(incident_id)
        return jsonify({"status": "patch_generated", "patch": patch.to_dict(), "task": task.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# 6. POST /incidents/{id}/tests - Run configured validation
@app.route("/incidents/<incident_id>/tests", methods=["POST"])
@app.route("/api/incidents/<incident_id>/tests", methods=["POST"])
def run_tests_endpoint(incident_id):
    if incident_id not in orchestrator.sessions:
        return jsonify({"error": "Incident not found"}), 404

    session = orchestrator.sessions[incident_id]
    test_run = orchestrator.test_runner.run_tests(incident_id)
    session["test_run"] = test_run
    return jsonify({"test_run": test_run.to_dict()})


# 7. POST /incidents/{id}/approve - Approve or reject specified action
@app.route("/incidents/<incident_id>/approve", methods=["POST"])
@app.route("/api/incidents/<incident_id>/approve", methods=["POST"])
@app.route("/api/incident/approve", methods=["POST"])
def approve_action(incident_id=None):
    data = request.get_json(silent=True) or {}
    inc_id = incident_id or data.get("incident_id")
    if not inc_id:
        # Default to latest active incident
        if orchestrator.sessions:
            inc_id = list(orchestrator.sessions.keys())[-1]
        else:
            return jsonify({"error": "No active incident to approve"}), 400

    session = orchestrator.sessions.get(inc_id)
    if not session:
        return jsonify({"error": "Incident not found"}), 404

    incident = session["incident"]
    action = data.get("action") or "auto"
    reviewer = data.get("reviewer") or "OnCallEngineer"

    try:
        if action == "pr" or incident.status == WorkflowState.AWAITING_PR_APPROVAL:
            # User is approving the Pull Request
            pr = orchestrator.approve_pr_creation(inc_id, reviewer=reviewer)
            return jsonify({
                "status": "pr_approved",
                "next_state": incident.status.value,
                "pull_request": pr.to_dict(),
                "incident": incident.to_dict(),
            })
        else:
            # User is approving the Patch (Step 1)
            test_run = orchestrator.approve_patch(inc_id, reviewer=reviewer)
            return jsonify({
                "status": "patch_approved",
                "next_state": incident.status.value,
                "test_run": test_run.to_dict(),
                "incident": incident.to_dict(),
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# Reject Action
@app.route("/incidents/<incident_id>/reject", methods=["POST"])
@app.route("/api/incidents/<incident_id>/reject", methods=["POST"])
@app.route("/api/incident/reject", methods=["POST"])
def reject_action(incident_id=None):
    data = request.get_json(silent=True) or {}
    inc_id = incident_id or data.get("incident_id")
    if not inc_id:
        if orchestrator.sessions:
            inc_id = list(orchestrator.sessions.keys())[-1]
        else:
            return jsonify({"error": "No active incident"}), 400

    reviewer = data.get("reviewer") or "OnCallEngineer"
    reason = data.get("reason") or "Manual review requested."

    inc = orchestrator.reject_workflow(inc_id, reviewer=reviewer, reason=reason)
    return jsonify({"status": "rejected", "incident": inc.to_dict()})


# 8. POST /integrations/switch/events - Official Switch protocol receiver
@app.route("/integrations/switch/events", methods=["POST"])
@app.route("/api/chat/send", methods=["POST"])
def receive_switch_event():
    data = request.get_json(silent=True) or {}
    raw_event = {
        "event_id": data.get("event_id"),
        "room_id": data.get("room_id") or orchestrator.active_room_id,
        "sender": data.get("user") or data.get("sender") or "OnCallEngineer",
        "message": data.get("text") or data.get("message") or "",
        "timestamp": time.time(),
    }
    result = orchestrator.handle_incoming_switch_event(raw_event)
    active_inc_id = list(orchestrator.sessions.keys())[-1] if orchestrator.sessions else None
    room_id = orchestrator.active_room_id
    messages = orchestrator.switch_client.get_room_messages(room_id) if room_id else []

    return jsonify({"result": result, "messages": messages})


# 9. GET /integrations/health - Return connection status for all integrations
@app.route("/integrations/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def integration_health():
    switch_health = orchestrator.switch_adapter.check_health()
    github_status = "configured" if os.getenv("GITHUB_TOKEN") else "test_mode_active"

    return jsonify({
        "status": "ok",
        "integrations": {
            "switch": switch_health,
            "chat_platform": {"platform": "Slack / Discord", "status": "connected_via_switch"},
            "github": {"status": github_status, "repository": orchestrator.git_commander.repository},
            "monitoring": {"status": "ready", "sources": ["demo_endpoint", "manual_form", "webhooks"]},
        },
        "mode": "simulation",
        "timestamp": time.time()
    })


# 10. GET /agents/tasks - List recent agent tasks
@app.route("/agents/tasks", methods=["GET"])
@app.route("/api/agents/tasks", methods=["GET"])
def list_agent_tasks():
    limit = int(request.args.get("limit", 20))
    tasks = [t.to_dict() for t in reversed(orchestrator.agent_tasks[-limit:])]
    return jsonify({"tasks": tasks, "total": len(orchestrator.agent_tasks)})


# 11. State and Analytics Summary
@app.route("/api/room/state", methods=["GET"])
def room_state():
    if not orchestrator.sessions:
        return jsonify({"active": False, "messages": []})

    latest_id = list(orchestrator.sessions.keys())[-1]
    session = orchestrator.sessions[latest_id]
    incident = session["incident"]
    patch = session.get("patch")
    test_run = session.get("test_run")
    pr = session.get("pull_request")

    return jsonify({
        "active": True,
        "incident_id": latest_id,
        "room_id": incident.switch_room_id,
        "incident": incident.to_dict(),
        "patch": patch.to_dict() if patch else None,
        "test_run": test_run.to_dict() if test_run else None,
        "pull_request": pr.to_dict() if pr else None,
        "analytics": orchestrator.telemetry.get_summary(),
        "messages": orchestrator.switch_client.get_room_messages(incident.switch_room_id),
    })


def run_server():
    print(f"🚀 SwitchOps Cockpit running on http://{config.host}:{config.port}")
    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    run_server()
