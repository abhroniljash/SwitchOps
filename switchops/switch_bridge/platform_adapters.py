"""
Platform Adapters: Translates Switch Room events and incident proposals into
native Slack Block Kit payloads and Discord Embeds with interactive buttons.
"""

from typing import Dict, Any, Optional
from ..core.incident_engine import Incident
from ..core.workflow import Patch
from ..core.git_commander import PullRequest


class PlatformAdapters:
    """Provides Slack Block Kit and Discord message formatting."""

    @staticmethod
    def format_slack_incident_card(incident: Incident, patch: Patch) -> Dict[str, Any]:
        """Formats an interactive Slack Block Kit card."""
        target_file = patch.files_changed[0] if patch.files_changed else "service code"
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
                        {"type": "mrkdwn", "text": f"*Service:* `{incident.service_name}`"},
                        {"type": "mrkdwn", "text": f"*Severity:* *{incident.severity.value}*"},
                        {"type": "mrkdwn", "text": f"*Target:* `{target_file}`"},
                        {"type": "mrkdwn", "text": f"*Risk Score:* `{patch.risk_notes}`"},
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Root Cause Analysis:*\n>{incident.likely_root_cause or incident.summary}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Proposed Fix (Unified Diff):*\n```{patch.diff}```"
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"incident_actions_{incident.id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Authorize Tests", "emoji": True},
                            "style": "primary",
                            "value": f"approve_{incident.id}",
                            "action_id": "btn_approve_patch"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject Fix", "emoji": True},
                            "style": "danger",
                            "value": f"reject_{incident.id}",
                            "action_id": "btn_reject"
                        }
                    ]
                }
            ]
        }

    @staticmethod
    def format_discord_incident_embed(incident: Incident, patch: Patch) -> Dict[str, Any]:
        """Formats a rich Discord Embed object."""
        color = 0xFF0000 if incident.severity.value == "Critical" else 0xFFA500
        target_file = patch.files_changed[0] if patch.files_changed else "service code"
        return {
            "embeds": [
                {
                    "title": f"🚨 [SwitchOps] Production Incident: {incident.id}",
                    "description": (
                        f"**Service:** `{incident.service_name}` | **Severity:** `{incident.severity.value}`\n\n"
                        f"**Root Cause:**\n{incident.likely_root_cause or incident.summary}\n\n"
                        f"**Target File:** `{target_file}`\n"
                        f"**Risk Notes:** `{patch.risk_notes}`"
                    ),
                    "color": color,
                    "fields": [
                        {
                            "name": "Proposed Diff",
                            "value": f"```diff\n{patch.diff[:800]}\n```",
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
                        "text": (
                            f"🎉 *Incident `{incident.id}` Remediated Successfully!*\n"
                            f"Pull Request opened: *<{pr.url}|PR #{pr.pr_number}: {pr.title}>*\n"
                            f"Branch: `{pr.branch}` | Status: *{pr.status}*"
                        )
                    }
                }
            ]
        }
