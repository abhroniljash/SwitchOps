"""
Security & Privacy Module: Redaction of sensitive credentials,
path traversal prevention, command allowlists, webhook HMAC signature validation,
and dashboard API authentication guards.
"""

import hashlib
import hmac
import os
import re
from typing import List, Optional, Dict, Any

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
    ("docker", "run"),
]

# Dangerous shell characters that should never be executed
DANGEROUS_SHELL_CHARACTERS = [";", "&&", "||", "|", "`", "$", ">", "<"]


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
    Strictly validates that target_path is within the canonical workspace_root and
    does not touch sensitive system or configuration files.
    """
    if not target_path or not workspace_root:
        return False

    # Normalize and canonicalize absolute paths
    abs_workspace = os.path.realpath(os.path.abspath(workspace_root))
    abs_target = os.path.realpath(os.path.abspath(os.path.join(abs_workspace, target_path)))

    # Path traversal check: must start with the canonical workspace root
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

    # Block any shell meta-characters embedded inside arguments
    for arg in command:
        for dangerous in DANGEROUS_SHELL_CHARACTERS:
            if dangerous in arg:
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


def verify_hmac_signature(raw_payload: bytes, signature_header: Optional[str], secret: Optional[str]) -> bool:
    """
    Validates HMAC SHA256 webhook signatures (used by Switch, GitHub, and Sentry).
    If no secret is configured, accepts requests in development mode.
    """
    if not secret:
        # Development / local testing mode without secret verification
        return True

    if not signature_header:
        return False

    # Clean header prefixes like 'sha256=' or 'v0='
    clean_signature = signature_header
    if "=" in signature_header:
        clean_signature = signature_header.split("=", 1)[1]

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        raw_payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig.lower(), clean_signature.lower())


def validate_api_key(provided_key: Optional[str], expected_key: Optional[str]) -> bool:
    """Validates API Key / Bearer tokens for securing dashboard REST endpoints."""
    if not expected_key:
        # Dev mode: open access if no DASHBOARD_API_KEY is configured
        return True

    if not provided_key:
        return False

    # Support 'Bearer <key>'
    clean_key = provided_key.replace("Bearer ", "").replace("bearer ", "").strip()
    return hmac.compare_digest(clean_key, expected_key.strip())
