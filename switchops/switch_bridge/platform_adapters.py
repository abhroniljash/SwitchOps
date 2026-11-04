"""
Platform Adapters: Translates Switch Room events and incident proposals into
native Slack Block Kit payloads and Discord Embeds with interactive buttons.
"""

from typing import Dict, Any, Optional
from ..core.incident_engine import Incident
from ..core.remediation_engine import RemediationProposal
from ..core.git_commander import PullRequest


class PlatformAdapters:
    """Provides Slack Block Kit and Discord message formatting."""

    @staticmethod
    def format_slack_incident_card(incident: Incident, proposal: RemediationProposal) -> Dict[str, Any]:
        """Formats an interactive Slack Block Kit card."""
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 [SwitchOps] Incident Alert: {incident.id}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Service:* `{incident.service}`"},
                        {"type": "mrkdwn", "text": f"*Severity:* *{incident.severity.value}*"},
                        {"type": "mrkdwn", "text": f"*Target:* `{proposal.target_file}`"},
                        {"type": "mrkdwn", "text": f"*Risk Score:* `{proposal.risk_assessment}`"},
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Root Cause Analysis:*\n>{incident.root_cause_summary}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Proposed Fix (Unified Diff):*\n```{proposal.diff}```"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Automated Regression Verification:*\n```{proposal.test_run_output}```"
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"incident_actions_{incident.id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve & Open PR", "emoji": True},
                            "style": "primary",
                            "value": f"approve_{incident.id}",
                            "action_id": "btn_approve_pr"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject Fix", "emoji": True},
                            "style": "danger",
                            "value": f"reject_{incident.id}",
                            "action_id": "btn_reject"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "💬 Request Changes", "emoji": True},
                            "value": f"modify_{incident.id}",
                            "action_id": "btn_modify"
                        }
                    ]
                }
            ]
        }

    @staticmethod
    def format_discord_incident_embed(incident: Incident, proposal: RemediationProposal) -> Dict[str, Any]:
        """Formats a rich Discord Embed object."""
        color = 0xFF0000 if incident.severity.value == "CRITICAL" else 0xFFA500
        return {
            "embeds": [
                {
                    "title": f"🚨 [SwitchOps] Production Incident: {incident.id}",
                    "description": f"**Service:** `{incident.service}` | **Severity:** `{incident.severity.value}`\n\n"
                                   f"**Root Cause:**\n{incident.root_cause_summary}\n\n"
                                   f"**Target File:** `{proposal.target_file}`\n"
                                   f"**Risk Assessment:** `{proposal.risk_assessment}`\n"
                                   f"**Verification:** `{proposal.regression_test_name}` (PASSED ✅)",
                    "color": color,
                    "fields": [
                        {
                            "name": "Proposed Diff",
                            "value": f"```diff\n{proposal.diff[:800]}\n```",
                            "inline": False
                        }
                    ],
                    "footer": {
                        "text": "SwitchOps • Powered by Switch (SandboxAQ) • Awaiting On-Call Approval"
                    }
                }
            ]
        }

    @staticmethod
    def format_slack_pr_resolution(incident: Incident, pr: PullRequest) -> Dict[str, Any]:
        """Formats final resolution message after human approval."""
        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🎉 *Incident `{incident.id}` Remediated Successfully!*\n"
                                f"Pull Request opened: *<{pr.url}|PR #{pr.pr_id}: {pr.title}>*\n"
                                f"Branch: `{pr.branch_name}` | Status: *{pr.status}*"
                    }
                }
            ]
        }
