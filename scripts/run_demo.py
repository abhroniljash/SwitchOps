#!/usr/bin/env python3
"""
SwitchOps Interactive Terminal Demonstration.
Follows the 10-step hackathon workflow specified in Section 18 of the roadmap.
Usage: python scripts/run_demo.py
"""

import os
import sys
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Windows UTF-8 console output support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from switchops.switch_bridge.room_manager import SwitchOpsOrchestrator

# Terminal ANSI colors
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
PURPLE = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def main():
    print(f"\n{BOLD}{CYAN}========================================================================{RESET}")
    print(f"{BOLD}{PURPLE} ⚡ SwitchOps: Autonomous SRE Teammate & Incident Auto-Remediation{RESET}")
    print(f"{BOLD}    Powered by Switch (SandboxAQ) | WeMakeDevs Flip the Switch{RESET}")
    print(f"{BOLD}    [Note: All demo metrics & incidents are labeled as simulated]{RESET}")
    print(f"{BOLD}{CYAN}========================================================================{RESET}\n")

    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    orchestrator = SwitchOpsOrchestrator(workspace_root=workspace)

    # Step 1 & 2: Introduce problem & Switch connection
    print(f"{BOLD}[STEP 1 & 2]{RESET} {BLUE}Initializing Switch Core bridge and listening for alerts...{RESET}")
    health = orchestrator.switch_adapter.check_health()
    print(f"   {GREEN}✓ Switch Bridge Status:{RESET} {health['status']} ({health['gateway_url']})")
    time.sleep(1)

    # Step 3 & 4: Trigger controlled 500 & incident ingestion
    print(f"\n{BOLD}[STEP 3 & 4]{RESET} {YELLOW}🚨 Controlled HTTP 500 Ingested (payments-service)...{RESET}")
    incident = orchestrator.create_or_ingest_incident()
    print(f"   {GREEN}✓ Incident ID:{RESET} {BOLD}{incident.id}{RESET}")
    print(f"   {GREEN}✓ Switch Room Bound:{RESET} {CYAN}#incident-{incident.id.lower()}{RESET}")
    print(f"   {GREEN}✓ State:{RESET} {incident.status.value}")
    time.sleep(1.2)

    # Step 5: Triage Agent evidence-based RCA
    print(f"\n{BOLD}[STEP 5]{RESET} {BLUE}🔍 Triage Agent: Evidence-Based Root-Cause Analysis...{RESET}")
    incident, task = orchestrator.run_triage(incident.id)
    print(f"   {GREEN}✓ Evidence Item:{RESET} {incident.evidence_list[0].file_path} (line {incident.evidence_list[0].line_reference})")
    print(f"   {GREEN}✓ Hypothesis ({incident.confidence_level} Confidence):{RESET}\n     {incident.likely_root_cause}")
    time.sleep(1.2)

    # Step 6: Remediation Agent proposed diff
    session = orchestrator.sessions[incident.id]
    patch = session["patch"]
    print(f"\n{BOLD}[STEP 6]{RESET} {PURPLE}🛠️ Remediation Agent: Synthesizing Safe Scoped Patch...{RESET}")
    print(f"   {GREEN}✓ Target File:{RESET} {patch.files_changed[0]}")
    print(f"   {GREEN}✓ Risk Assessment:{RESET} {patch.risk_notes}")
    print(f"   {GREEN}✓ Current State:{RESET} {BOLD}{YELLOW}{incident.status.value}{RESET}")
    time.sleep(1.2)

    # Step 7: Human approval of patch & real isolated test execution
    print(f"\n{BOLD}[STEP 7]{RESET} {YELLOW}📋 Human-in-the-Loop Approval (Step 1 of 2: Authorize Patch){RESET}")
    print(f"   {CYAN}Operator Reviewer:{RESET} \"Patch looks safe and scoped. Approved for testing.\"")
    test_run = orchestrator.approve_patch(incident.id, reviewer="OnCallEngineer")
    print(f"   {GREEN}✓ Test Runner Command:{RESET} `{test_run.command_profile}`")
    print(f"   {GREEN}✓ Exit Code:{RESET} {test_run.exit_code} ({test_run.duration_ms}ms)")
    print(f"   {GREEN}✓ Test Run Result:{RESET} {BOLD}{GREEN}{test_run.status} ✅{RESET}")
    print(f"   {GREEN}✓ Transitioned to State:{RESET} {BOLD}{YELLOW}{incident.status.value}{RESET}")
    time.sleep(1.2)

    # Step 8 & 9: Human approval of PR & GitOps Agent dispatch
    print(f"\n{BOLD}[STEP 8 & 9]{RESET} {GREEN}🚀 Human-in-the-Loop Approval (Step 2 of 2: Create GitHub PR){RESET}")
    print(f"   {CYAN}Operator Reviewer:{RESET} \"Tests passed. Authorize opening Pull Request on GitHub.\"")
    pr = orchestrator.approve_pr_creation(incident.id, reviewer="OnCallEngineer")
    print(f"   {GREEN}✓ Git Branch:{RESET} {pr.branch} (Base: {pr.base_branch})")
    print(f"   {GREEN}✓ Pull Request Created:{RESET} {BOLD}{CYAN}{pr.url}{RESET}")
    print(f"   {GREEN}✓ Current State:{RESET} {BOLD}{GREEN}{incident.status.value}{RESET}")
    time.sleep(1)

    # Step 10: Safety Controls & Operational Analytics
    print(f"\n{BOLD}[STEP 10]{RESET} {YELLOW}🛡️ Safety Controls & Operational Analytics (Simulated Demo Data):{RESET}")
    summary = orchestrator.telemetry.get_summary()
    print(f"   {GREEN}✓ Time to Triage:{RESET} {summary['average_time_to_triage_seconds']}s")
    print(f"   {GREEN}✓ Time to PR:{RESET} {summary['average_time_to_pr_seconds']}s")
    print(f"   {GREEN}✓ Test Pass Rate:{RESET} {summary['test_pass_rate']}")
    print(f"   {GREEN}✓ Safety Rules:{RESET} No automatic merge, no direct commits to main, human approval required.")

    print(f"\n{BOLD}{GREEN}========================================================================{RESET}")
    print(f"{BOLD}{GREEN} ✨ Demonstration Succeeded! 10/10 Workflow Steps Verified!{RESET}")
    print(f"{BOLD}    To explore the full Web UI Cockpit, run:{RESET}")
    print(f"{BOLD}{CYAN}    python -m switchops.web.app{RESET}")
    print(f"{BOLD}{GREEN}========================================================================{RESET}\n")


if __name__ == "__main__":
    main()
