"""
Workflow States & Entities: Defines the strict multi-step state machine
and core entities requested by the SwitchOps improvement roadmap.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set

from .security import redact_secrets


class WorkflowState(str, Enum):
    RECEIVED = "RECEIVED"
    TRIAGING = "TRIAGING"
    TRIAGED = "TRIAGED"
    AWAITING_FIX_APPROVAL = "AWAITING_FIX_APPROVAL"
    PATCH_APPROVED = "PATCH_APPROVED"
    TESTING = "TESTING"
    TEST_PASSED = "TEST_PASSED"
    TEST_FAILED = "TEST_FAILED"
    AWAITING_PR_APPROVAL = "AWAITING_PR_APPROVAL"
    CREATING_PR = "CREATING_PR"
    PR_CREATED = "PR_CREATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


# Allowed state transitions based on Section 11 of the Roadmap
ALLOWED_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.RECEIVED: {WorkflowState.TRIAGING, WorkflowState.FAILED},
    WorkflowState.TRIAGING: {WorkflowState.TRIAGED, WorkflowState.FAILED},
    WorkflowState.TRIAGED: {WorkflowState.AWAITING_FIX_APPROVAL, WorkflowState.FAILED},
    WorkflowState.AWAITING_FIX_APPROVAL: {WorkflowState.PATCH_APPROVED, WorkflowState.REJECTED},
    WorkflowState.PATCH_APPROVED: {WorkflowState.TESTING, WorkflowState.FAILED},
    WorkflowState.TESTING: {WorkflowState.TEST_PASSED, WorkflowState.TEST_FAILED, WorkflowState.FAILED},
    WorkflowState.TEST_PASSED: {WorkflowState.AWAITING_PR_APPROVAL, WorkflowState.REJECTED},
    WorkflowState.TEST_FAILED: {WorkflowState.AWAITING_FIX_APPROVAL, WorkflowState.FAILED},  # Bounded retry / human review
    WorkflowState.AWAITING_PR_APPROVAL: {WorkflowState.CREATING_PR, WorkflowState.REJECTED},
    WorkflowState.CREATING_PR: {WorkflowState.PR_CREATED, WorkflowState.FAILED},
    WorkflowState.PR_CREATED: {WorkflowState.PR_CREATED},
    WorkflowState.REJECTED: set(),
    WorkflowState.FAILED: set(),
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal workflow state transition is attempted."""
    pass


@dataclass
class Evidence:
    id: str = field(default_factory=lambda: f"evi_{uuid.uuid4().hex[:6]}")
    incident_id: str = ""
    source_type: str = "repository_file"  # repository_file, log_trace, test_output
    file_path: Optional[str] = None
    line_reference: Optional[int] = None
    excerpt: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "source_type": self.source_type,
            "file_path": self.file_path,
            "line_reference": self.line_reference,
            "excerpt": redact_secrets(self.excerpt),
            "created_at": self.created_at,
        }


@dataclass
class AgentTask:
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:6]}")
    incident_id: str = ""
    agent_type: str = "TriageAgent"  # TriageAgent, RemediationAgent, TestRunner, GitOpsAgent
    status: str = "STARTED"  # STARTED, COMPLETED, FAILED
    input_summary: str = ""
    output_summary: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "agent_type": self.agent_type,
            "status": self.status,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round((self.completed_at - self.started_at), 2) if self.completed_at else None,
            "error_code": self.error_code,
        }


@dataclass
class Patch:
    id: str = field(default_factory=lambda: f"patch_{uuid.uuid4().hex[:6]}")
    incident_id: str = ""
    branch_name: str = ""
    diff: str = ""
    files_changed: List[str] = field(default_factory=list)
    explanation: str = ""
    risk_notes: str = "LOW"
    approval_status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "branch_name": self.branch_name,
            "diff": self.diff,
            "files_changed": self.files_changed,
            "explanation": self.explanation,
            "risk_notes": self.risk_notes,
            "approval_status": self.approval_status,
            "created_at": self.created_at,
        }


@dataclass
class TestRun:
    id: str = field(default_factory=lambda: f"tr_{uuid.uuid4().hex[:6]}")
    incident_id: str = ""
    command_profile: str = "python -m unittest"
    exit_code: int = 0
    status: str = "PASSED"  # PASSED, FAILED, SKIPPED, NOT_CONFIGURED
    stdout_reference: str = ""
    stderr_reference: str = ""
    duration_ms: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "command_profile": self.command_profile,
            "exit_code": self.exit_code,
            "status": self.status,
            "stdout_reference": self.stdout_reference,
            "stderr_reference": self.stderr_reference,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at,
        }


@dataclass
class Approval:
    id: str = field(default_factory=lambda: f"appr_{uuid.uuid4().hex[:6]}")
    incident_id: str = ""
    action_type: str = "PATCH_APPROVAL"  # PATCH_APPROVAL or PR_APPROVAL
    decision: str = "APPROVED"  # APPROVED or REJECTED
    reviewer: str = "OnCallEngineer"
    comment: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "action_type": self.action_type,
            "decision": self.decision,
            "reviewer": self.reviewer,
            "comment": self.comment,
            "created_at": self.created_at,
        }


@dataclass
class AuditEvent:
    id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:6]}")
    incident_id: str = ""
    actor: str = "System"
    action: str = ""
    result: str = "SUCCESS"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "actor": self.actor,
            "action": self.action,
            "result": self.result,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


def validate_transition(current: WorkflowState, next_state: WorkflowState):
    """Validates that a transition from current to next_state is legally allowed."""
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if next_state not in allowed:
        raise InvalidStateTransitionError(
            f"Invalid workflow state transition: cannot move from {current.value} to {next_state.value}. "
            f"Allowed next states are: {[s.value for s in allowed]}"
        )
