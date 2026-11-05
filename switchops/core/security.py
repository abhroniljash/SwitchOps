"""
Security & Privacy Module: Redaction of sensitive credentials,
path traversal prevention, and execution command allowlists.
"""

import os
import re
from typing import List, Optional

# Regular expressions for detecting sensitive tokens and secrets
SECRET_PATTERNS = [
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_PAT]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_OAUTH]'),
    (r'xoxb-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24,}', '[REDACTED_SLACK_BOT_TOKEN]'),
    (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]'),
    (r'(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{10,}', r'\1[REDACTED_TOKEN]'),
    (r'(?i)(api[_-]?key\s*[:=]\s*["\']?)[a-zA-Z0-9_\-]{16,}(["\']?)', r'\1[REDACTED_API_KEY]\2'),
    (r'(?i)(token\s*[:=]\s*["\']?)[a-zA-Z0-9_\-]{16,}(["\']?)', r'\1[REDACTED_TOKEN]\2'),
    (r'(?i)(password\s*[:=]\s*["\']?)[^\s"\']{6,}(["\']?)', r'\1[REDACTED_PASSWORD]\2'),
    (r'(?i)(secret\s*[:=]\s*["\']?)[a-zA-Z0-9_\-]{16,}(["\']?)', r'\1[REDACTED_SECRET]\2'),
]

# Sensitive files and directories that patches or file readers must NEVER touch
FORBIDDEN_PATHS = [
    ".git",
    ".env",
    "id_rsa",
    "id_ed25519",
    ".aws",
    ".ssh",
    "secrets",
    "credentials",
    "passwd",
    "shadow",
]

# Allowlisted execution commands for the test runner
ALLOWED_TEST_COMMAND_PREFIXES = [
    ("python", "-m", "unittest"),
    ("python", "-m", "pytest"),
    ("pytest",),
    ("unittest",),
]


def redact_secrets(text: str) -> str:
    """Redacts known token patterns and passwords from logs, error messages, and payloads."""
    if not text:
        return ""
    sanitized = str(text)
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def is_safe_path(target_path: str, workspace_root: str) -> bool:
    """
    Validates that target_path is within the workspace_root and
    does not touch sensitive system or configuration files.
    """
    if not target_path or not workspace_root:
        return False

    # Normalize absolute paths
    abs_workspace = os.path.abspath(workspace_root)
    abs_target = os.path.abspath(os.path.join(abs_workspace, target_path))

    # Path traversal check
    if not abs_target.startswith(abs_workspace):
        return False

    # Check against forbidden directory and file names
    parts = os.path.normpath(target_path).replace("\\", "/").split("/")
    for part in parts:
        for forbidden in FORBIDDEN_PATHS:
            if forbidden.lower() in part.lower():
                return False

    return True


def is_command_allowed(command: List[str]) -> bool:
    """Verifies that a test execution command belongs to the strict allowlist."""
    if not command:
        return False

    norm_cmd = [c.lower() for c in command]
    
    # Normalize python executable path (e.g. C:\Python313\python.exe -> python)
    if norm_cmd[0].endswith("python.exe") or norm_cmd[0].endswith("python"):
        norm_cmd[0] = "python"

    for prefix in ALLOWED_TEST_COMMAND_PREFIXES:
        norm_prefix = [p.lower() for p in prefix]
        if norm_cmd[:len(norm_prefix)] == norm_prefix:
            return True

    return False
