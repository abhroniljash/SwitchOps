"""
SwitchOps Web Application & Interactive SRE Incident Cockpit.
Provides a real-time UI simulating the Switch Room, Slack/Discord cards,
Git diff viewer, and Switch ROI telemetry dashboard.
"""

import os
from flask import Flask, render_template, request, jsonify
from switchops.switch_bridge.room_manager import SwitchOpsOrchestrator
from switchops.config import get_config

# Paths
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")
STATIC_DIR = os.path.join(WEB_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)

config = get_config()
orchestrator = SwitchOpsOrchestrator(workspace_root=os.getcwd(), is_simulation=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/incident/trigger", methods=["POST"])
def trigger_incident():
    data = request.get_json(silent=True) or {}
    custom_alert = data.get("alert")
    session = orchestrator.start_incident_workflow(custom_alert)
    return jsonify({
        "status": "success",
        "room_id": session["room_id"],
        "incident": session["incident"].to_dict(),
        "proposal": session["proposal"].to_dict(),
        "messages": orchestrator.client.get_room_messages(session["room_id"]),
    })


@app.route("/api/chat/send", methods=["POST"])
def send_chat():
    data = request.get_json() or {}
    room_id = data.get("room_id") or orchestrator.active_room_id
    text = data.get("text", "")
    user = data.get("user", "OnCallEngineer")

    if not room_id:
        return jsonify({"error": "No active incident room"}), 400

    result = orchestrator.handle_user_input(room_id, text, user)
    return jsonify({
        "result": result,
        "messages": orchestrator.client.get_room_messages(room_id),
    })


@app.route("/api/voice/send", methods=["POST"])
def send_voice():
    data = request.get_json() or {}
    room_id = data.get("room_id") or orchestrator.active_room_id
    transcript = data.get("transcript", "Hey SwitchOps, investigate the checkout crash and draft a hotfix")

    if not room_id:
        # If no active room, start workflow first
        session = orchestrator.start_incident_workflow()
        room_id = session["room_id"]

    result = orchestrator.handle_voice_command(room_id, transcript)
    return jsonify({
        "result": result,
        "messages": orchestrator.client.get_room_messages(room_id),
        "wispr_scorecard": orchestrator.wispr_voice.generate_wispr_scorecard()
    })


@app.route("/api/incident/approve", methods=["POST"])
def approve_incident():
    data = request.get_json() or {}
    room_id = data.get("room_id") or orchestrator.active_room_id
    if not room_id:
        return jsonify({"error": "No active incident room"}), 400

    result = orchestrator.approve_and_open_pr(room_id)
    return jsonify({
        "status": "success",
        "result": result,
        "messages": orchestrator.client.get_room_messages(room_id)
    })


@app.route("/api/incident/reject", methods=["POST"])
def reject_incident():
    data = request.get_json() or {}
    room_id = data.get("room_id") or orchestrator.active_room_id
    if not room_id:
        return jsonify({"error": "No active incident room"}), 400

    result = orchestrator.reject_proposal(room_id)
    return jsonify({
        "status": "success",
        "result": result,
        "messages": orchestrator.client.get_room_messages(room_id)
    })


@app.route("/api/room/state", methods=["GET"])
def room_state():
    room_id = request.args.get("room_id") or orchestrator.active_room_id
    if not room_id or room_id not in orchestrator.sessions:
        return jsonify({"active": False, "messages": []})

    session = orchestrator.sessions[room_id]
    return jsonify({
        "active": True,
        "room_id": room_id,
        "incident": session["incident"].to_dict(),
        "proposal": session["proposal"].to_dict() if session.get("proposal") else None,
        "pull_request": session["pull_request"].to_dict() if session.get("pull_request") else None,
        "roi": session["roi"].to_dict() if session.get("roi") else None,
        "messages": orchestrator.client.get_room_messages(room_id)
    })


@app.route("/api/wispr/scorecard", methods=["GET"])
def wispr_scorecard():
    return jsonify(orchestrator.wispr_voice.generate_wispr_scorecard())


def run_server():
    print(f"🚀 SwitchOps Cockpit running on http://{config.host}:{config.port}")
    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    run_server()
