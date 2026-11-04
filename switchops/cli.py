"""
SwitchOps CLI Entry Point.
Allows running demo mode, launching the web cockpit, or inspecting telemetry.
"""

import argparse
import sys

# Windows UTF-8 console output support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from switchops.web.app import run_server
from switchops.switch_bridge.room_manager import SwitchOpsOrchestrator


def run_cli_demo():
    print("\n=======================================================")
    print("⚡ SwitchOps: Autonomous SRE Teammate via Switch")
    print("=======================================================\n")
    orchestrator = SwitchOpsOrchestrator(is_simulation=True)

    print("1. [Event] Ingesting Production Alert (500 on payments-service)...")
    session = orchestrator.start_incident_workflow()
    inc = session["incident"]
    prop = session["proposal"]

    print(f"   -> Incident Created: {inc.id} ({inc.severity.value})")
    print(f"   -> Root Cause: {inc.root_cause_summary}")
    print(f"   -> Target File: {prop.target_file}")
    print(f"   -> Regression Test: {prop.regression_test_name} (PASSED)")

    print("\n2. [Switch Room] Human-in-the-Loop Approval Required.")
    print("   -> Simulated Slack/Discord Thread:")
    for msg in orchestrator.client.get_room_messages(session["room_id"]):
        print(f"      [{msg['sender']}]: {msg['text'][:90]}...")

    print("\n3. [Action] Approving hotfix remediation and opening Pull Request...")
    result = orchestrator.approve_and_open_pr(session["room_id"])
    pr = result["pull_request"]
    roi = result["roi"]

    print(f"   -> PR Created: {pr['url']}")
    print(f"   -> Branch: {pr['branch_name']}")
    print(f"   -> Status: {pr['status']}")
    print(f"   -> MTTR Reduction: {roi['mttr_reduction_percent']}% (from 45m to {roi['actual_resolution_seconds']}s)")
    print(f"   -> Total Value Delivered: ${roi['total_value_delivered_usd']:,.2f}")
    print(f"   -> ROI Multiplier: {roi['roi_multiplier']}x\n")
    print("🎉 Demo complete! To run the full web UI cockpit, run:")
    print("   python -m switchops.web.app\n")


def main():
    parser = argparse.ArgumentParser(description="SwitchOps: Autonomous Incident Commander via Switch")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("demo", help="Run terminal simulation demo")
    subparsers.add_parser("serve", help="Start web cockpit UI on localhost:5000")

    args = parser.parse_args()
    if args.command == "serve":
        run_server()
    else:
        run_cli_demo()


if __name__ == "__main__":
    main()
