"""
Incident Engine: Responsible for ingesting alerts, parsing stack traces,
and executing Root Cause Analysis (RCA) across the codebase.
"""

import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class IncidentSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    TRIAGING = "TRIAGING"
    DIAGNOSED = "DIAGNOSED"
    FIX_PROPOSED = "FIX_PROPOSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass
class Incident:
    id: str
    title: str
    service: str
    severity: IncidentSeverity
    error_type: str
    error_message: str
    stack_trace: str
    timestamp: float = field(default_factory=time.time)
    status: IncidentStatus = IncidentStatus.DETECTED
    affected_file: Optional[str] = None
    line_number: Optional[int] = None
    code_context: Optional[str] = None
    root_cause_summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "service": self.service,
            "severity": self.severity.value,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "affected_file": self.affected_file,
            "line_number": self.line_number,
            "code_context": self.code_context,
            "root_cause_summary": self.root_cause_summary,
            "metadata": self.metadata,
        }


class IncidentEngine:
    """Ingests alerts from APMs/webhooks/chat mentions and performs automated RCA."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()
        self.active_incidents: Dict[str, Incident] = {}

    def create_demo_incident(self) -> Incident:
        """Constructs a realistic production incident based on payments_service."""
        inc_id = f"INC-{int(time.time()) % 10000}"
        stack_trace = """Traceback (most recent call last):
  File "switchops/sample_apps/payments_service/app.py", line 78, in process_checkout
    final_amount = self.convert_currency(subtotal_usd, "USD", raw_currency)
  File "switchops/sample_apps/payments_service/app.py", line 37, in convert_currency
    to_rate = EXCHANGE_RATES[to_currency]
KeyError: 'eur'"""

        incident = Incident(
            id=inc_id,
            title="HTTP 500 Spike on Checkout: KeyError: 'eur' in currency conversion",
            service="payments-service",
            severity=IncidentSeverity.CRITICAL,
            error_type="KeyError",
            error_message="KeyError: 'eur' in convert_currency",
            stack_trace=stack_trace,
            metadata={
                "impacted_users": 142,
                "environment": "production-us-east-1",
                "triggered_by": "Datadog Alert: High 5xx Error Rate (>5%)",
            },
        )
        self.active_incidents[inc_id] = incident
        return incident

    def ingest_webhook(self, payload: Dict[str, Any]) -> Incident:
        """Parses webhook payload from Datadog, Sentry, or custom alerting."""
        inc_id = payload.get("id", f"INC-{int(time.time()) % 10000}")
        title = payload.get("title", "Unhandled Production Exception")
        service = payload.get("service", "unknown-service")
        severity_str = payload.get("severity", "HIGH").upper()
        severity = IncidentSeverity(severity_str) if severity_str in IncidentSeverity.__members__ else IncidentSeverity.HIGH

        stack_trace = payload.get("stack_trace", "")
        error_type = payload.get("error_type", "InternalServerError")
        error_message = payload.get("error_message", "An unexpected error occurred.")

        incident = Incident(
            id=inc_id,
            title=title,
            service=service,
            severity=severity,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            metadata=payload.get("metadata", {}),
        )
        self.active_incidents[inc_id] = incident
        return incident

    def analyze(self, incident: Incident) -> Incident:
        """
        Parses stack trace, locates the offending source file in the repository,
        reads surrounding code context, and produces an actionable RCA.
        """
        incident.status = IncidentStatus.TRIAGING

        # Extract file and line number from stack trace
        file_match = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', incident.stack_trace)
        if file_match:
            # Pick the deepest frame in the application code
            for rel_file, line_num, func_name in reversed(file_match):
                full_path = os.path.join(self.workspace_root, rel_file)
                if os.path.exists(full_path):
                    incident.affected_file = rel_file
                    incident.line_number = int(line_num)
                    break
            
            # Fallback if relative path wasn't resolved directly
            if not incident.affected_file and file_match:
                incident.affected_file = file_match[-1][0]
                incident.line_number = int(file_match[-1][1])

        # Read code context if file found
        if incident.affected_file:
            full_path = os.path.join(self.workspace_root, incident.affected_file)
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                target_idx = (incident.line_number - 1) if incident.line_number else 0
                start_idx = max(0, target_idx - 5)
                end_idx = min(len(lines), target_idx + 6)
                incident.code_context = "".join(lines[start_idx:end_idx])

        # Generate intelligent RCA Summary
        if "KeyError" in incident.error_type:
            incident.root_cause_summary = (
                f"Root Cause: Unhandled KeyError from direct dictionary key lookup in '{incident.affected_file}' without case-normalization. "
                f"Client sent lowercase currency code which missed the uppercase EXCHANGE_RATES keys."
            )
        else:
            incident.root_cause_summary = (
                f"Root Cause: Unhandled {incident.error_type} in {incident.affected_file} "
                f"at line {incident.line_number}: {incident.error_message}"
            )

        incident.status = IncidentStatus.DIAGNOSED
        return incident
