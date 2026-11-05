"""
Database Persistence Module: SQLite-based storage engine for SwitchOps.
Preserves incidents, agent tasks, evidence, patches, test runs, approvals,
and audit logs across server restarts.
"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Dict, Any, List, Optional


class Database:
    """Manages SQLite persistence for SwitchOps entities."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        elif os.getenv("SQLITE_DB_PATH"):
            self.db_path = os.getenv("SQLITE_DB_PATH")
        elif os.getenv("VERCEL") == "1" or os.getenv("NOW_REGION"):
            self.db_path = "/tmp/switchops.db"
        else:
            self.db_path = os.path.join(os.getcwd(), "switchops.db")

        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception:
                pass

        self._init_tables()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_tables(self):
        """Initializes tables for all Section 8 database entities."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Incidents Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    service_name TEXT,
                    environment TEXT,
                    severity TEXT,
                    severity_reason TEXT,
                    summary TEXT,
                    logs TEXT,
                    stack_trace TEXT,
                    repository TEXT,
                    created_at REAL,
                    switch_room_id TEXT,
                    status TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    correlation_id TEXT,
                    affected_file TEXT,
                    line_number INTEGER,
                    likely_root_cause TEXT,
                    recommended_fix TEXT,
                    confidence_level TEXT,
                    confidence_explanation TEXT,
                    raw_payload_redacted TEXT,
                    event_fingerprint TEXT,
                    llm_assisted INTEGER DEFAULT 0
                )
            """)

            # Agent Tasks Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT,
                    agent_type TEXT,
                    status TEXT,
                    input_summary TEXT,
                    output_summary TEXT,
                    started_at REAL,
                    completed_at REAL,
                    error_code TEXT,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                )
            """)

            # Evidence Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT,
                    source_type TEXT,
                    file_path TEXT,
                    line_reference INTEGER,
                    excerpt TEXT,
                    created_at REAL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                )
            """)

            # Patches Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patches (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT,
                    branch_name TEXT,
                    diff TEXT,
                    files_changed TEXT,
                    explanation TEXT,
                    risk_notes TEXT,
                    approval_status TEXT,
                    created_at REAL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                )
            """)

            # Test Runs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT,
                    command_profile TEXT,
                    exit_code INTEGER,
                    status TEXT,
                    stdout_reference TEXT,
                    stderr_reference TEXT,
                    duration_ms INTEGER,
                    created_at REAL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                )
            """)

            # Approvals Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT,
                    action_type TEXT,
                    decision TEXT,
                    reviewer TEXT,
                    comment TEXT,
                    created_at REAL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                )
            """)

            # Audit Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT,
                    actor TEXT,
                    action TEXT,
                    result TEXT,
                    timestamp REAL,
                    metadata TEXT
                )
            """)

            conn.commit()

    def save_incident(self, incident: Any):
        """Upserts an incident record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO incidents (
                    id, source, service_name, environment, severity, severity_reason,
                    summary, logs, stack_trace, repository, created_at, switch_room_id,
                    status, error_type, error_message, correlation_id, affected_file,
                    line_number, likely_root_cause, recommended_fix, confidence_level,
                    confidence_explanation, raw_payload_redacted, event_fingerprint, llm_assisted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident.id, incident.source, incident.service_name, incident.environment,
                incident.severity.value, incident.severity_reason, incident.summary,
                incident.logs, incident.stack_trace, incident.repository, incident.created_at,
                incident.switch_room_id, incident.status.value, incident.error_type,
                incident.error_message, incident.correlation_id, incident.affected_file,
                incident.line_number, incident.likely_root_cause, incident.recommended_fix,
                incident.confidence_level, incident.confidence_explanation,
                json.dumps(incident.raw_payload_redacted), incident.event_fingerprint,
                1 if incident.llm_assisted else 0
            ))
            conn.commit()

    def save_agent_task(self, task: Any):
        """Saves an agent task execution record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO agent_tasks (
                    id, incident_id, agent_type, status, input_summary,
                    output_summary, started_at, completed_at, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.incident_id, task.agent_type, task.status,
                task.input_summary, task.output_summary, task.started_at,
                task.completed_at, task.error_code
            ))
            conn.commit()

    def save_evidence(self, evidence: Any):
        """Saves an evidence item."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO evidence (
                    id, incident_id, source_type, file_path, line_reference, excerpt, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence.id, evidence.incident_id, evidence.source_type,
                evidence.file_path, evidence.line_reference, evidence.excerpt, evidence.created_at
            ))
            conn.commit()

    def save_patch(self, patch: Any):
        """Saves a remediation patch."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO patches (
                    id, incident_id, branch_name, diff, files_changed,
                    explanation, risk_notes, approval_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patch.id, patch.incident_id, patch.branch_name, patch.diff,
                json.dumps(patch.files_changed), patch.explanation,
                patch.risk_notes, patch.approval_status, patch.created_at
            ))
            conn.commit()

    def save_test_run(self, test_run: Any):
        """Saves a test runner output record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO test_runs (
                    id, incident_id, command_profile, exit_code, status,
                    stdout_reference, stderr_reference, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_run.id, test_run.incident_id, test_run.command_profile,
                test_run.exit_code, test_run.status, test_run.stdout_reference,
                test_run.stderr_reference, test_run.duration_ms, test_run.created_at
            ))
            conn.commit()

    def save_approval(self, approval: Any):
        """Saves an approval decision record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO approvals (
                    id, incident_id, action_type, decision, reviewer, comment, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                approval.id, approval.incident_id, approval.action_type,
                approval.decision, approval.reviewer, approval.comment, approval.created_at
            ))
            conn.commit()

    def save_audit_event(self, event: Any):
        """Saves an audit event log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO audit_events (
                    id, incident_id, actor, action, result, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id, event.incident_id, event.actor, event.action,
                event.result, event.timestamp, json.dumps(event.metadata)
            ))
            conn.commit()

    def load_all_incidents(self) -> List[Dict[str, Any]]:
        """Retrieves all past incidents ordered by creation time descending."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def load_agent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent agent tasks."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_tasks ORDER BY started_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def load_audit_events(self, incident_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves audit events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if incident_id:
                cursor.execute("SELECT * FROM audit_events WHERE incident_id = ? ORDER BY timestamp DESC LIMIT ?", (incident_id, limit))
            else:
                cursor.execute("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
