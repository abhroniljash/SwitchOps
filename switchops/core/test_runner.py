"""
Safe Isolated Test Runner: Executes allowlisted test commands with timeouts,
capturing actual stdout/stderr, execution duration, and exit codes.
"""

import os
import subprocess
import sys
import time
from typing import List, Optional, Dict, Any

from .security import is_command_allowed, redact_secrets
from .workflow import TestRun


class TestRunner:
    """Safely executes project tests and captures real outcome metrics."""

    def __init__(self, workspace_root: Optional[str] = None, timeout_seconds: int = 15):
        self.workspace_root = workspace_root or os.getcwd()
        self.timeout_seconds = timeout_seconds

    def run_tests(
        self,
        incident_id: str,
        command: Optional[List[str]] = None,
        test_path: Optional[str] = None
    ) -> TestRun:
        """
        Executes a test command with strict security checks, timeout protection,
        and real process output capture.
        """
        start_time = time.time()
        
        # Default command: execute unit tests for the targeted service or regression suite
        if not command:
            if test_path:
                command = [sys.executable, "-m", "unittest", test_path]
            else:
                command = [sys.executable, "-m", "unittest", "discover", "switchops/sample_apps/payments_service/tests"]

        # 1. Security Check: Allowlisted command prefix
        if not is_command_allowed(command):
            return TestRun(
                incident_id=incident_id,
                command_profile=" ".join(command),
                exit_code=1,
                status="FAILED",
                stdout_reference="",
                stderr_reference="Security Error: Command not in allowlist. Execution blocked.",
                duration_ms=0,
            )

        # 2. Execute process in isolated working directory with timeout
        try:
            process = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )
            duration_ms = int((time.time() - start_time) * 1000)
            status = "PASSED" if process.returncode == 0 else "FAILED"

            return TestRun(
                incident_id=incident_id,
                command_profile=" ".join(command),
                exit_code=process.returncode,
                status=status,
                stdout_reference=redact_secrets(process.stdout),
                stderr_reference=redact_secrets(process.stderr),
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return TestRun(
                incident_id=incident_id,
                command_profile=" ".join(command),
                exit_code=124,
                status="FAILED",
                stdout_reference="",
                stderr_reference=f"Execution timed out after {self.timeout_seconds} seconds.",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return TestRun(
                incident_id=incident_id,
                command_profile=" ".join(command),
                exit_code=1,
                status="FAILED",
                stdout_reference="",
                stderr_reference=f"Process execution error: {redact_secrets(str(e))}",
                duration_ms=duration_ms,
            )
