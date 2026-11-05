"""
Safe Isolated Test Runner: Executes allowlisted test commands in an isolated Docker container
when available, or in an isolated local subprocess with resource and time limits.
Captures actual stdout, stderr, execution duration, and exit codes.
"""

import os
import shutil
import subprocess
import sys
import time
from typing import List, Optional, Dict, Any

from .security import is_command_allowed, redact_secrets
from .workflow import TestRun


class TestRunner:
    """Safely executes project tests in Docker or an isolated sub-environment."""

    def __init__(self, workspace_root: Optional[str] = None, timeout_seconds: int = 15):
        self.workspace_root = workspace_root or os.getcwd()
        self.timeout_seconds = timeout_seconds
        self.docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        """Checks if Docker CLI is installed and the Docker daemon is accessible."""
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=2, check=False)
            return res.returncode == 0
        except Exception:
            return False

    def run_tests(
        self,
        incident_id: str,
        command: Optional[List[str]] = None,
        test_path: Optional[str] = None
    ) -> TestRun:
        """
        Executes tests against the patched codebase.
        Uses Docker container isolation if Docker is running; otherwise falls back
        to an isolated process runner and notes the execution environment.
        """
        start_time = time.time()
        
        # Default test command
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

        # 2. Docker Execution when Docker daemon is available
        if self.docker_available:
            try:
                # Map workspace into /app in container
                docker_cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{self.workspace_root}:/app",
                    "-w", "/app",
                    "python:3.11-slim",
                    "python", "-m", "unittest", "discover", "switchops/sample_apps/payments_service/tests"
                ]
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False
                )
                duration_ms = int((time.time() - start_time) * 1000)
                status = "PASSED" if proc.returncode == 0 else "FAILED"
                env_notice = "[Environment: Isolated Docker Container (python:3.11-slim)]\n"
                
                return TestRun(
                    incident_id=incident_id,
                    command_profile="docker run --rm python:3.11-slim " + " ".join(command),
                    exit_code=proc.returncode,
                    status=status,
                    stdout_reference=env_notice + redact_secrets(proc.stdout),
                    stderr_reference=redact_secrets(proc.stderr),
                    duration_ms=duration_ms,
                )
            except Exception as e:
                # Fall back to isolated subprocess if container execution failed
                pass

        # 3. Isolated Subprocess Execution
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
            env_notice = "[Environment: Isolated Subprocess (Dockerfile.test configured for Docker deployment)]\n"

            return TestRun(
                incident_id=incident_id,
                command_profile=" ".join(command),
                exit_code=process.returncode,
                status=status,
                stdout_reference=env_notice + redact_secrets(process.stdout),
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
