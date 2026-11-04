"""
SwitchOps Configuration Module.
Handles environment variables, default settings, and runtime profiles.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SwitchOpsConfig:
    # Mode: 'simulation' or 'live'
    mode: str = field(
        default_factory=lambda: os.getenv("SWITCHOPS_MODE", "simulation").lower()
    )

    # Switch Gateway Configuration (sandbox-quantum/switch core)
    switch_gateway_url: str = field(
        default_factory=lambda: os.getenv("SWITCH_GATEWAY_URL", "http://localhost:8000")
    )
    switch_api_key: str = field(
        default_factory=lambda: os.getenv("SWITCH_API_KEY", "switch_demo_key_secret")
    )

    # Chat Platform Webhooks & Tokens
    slack_webhook_url: Optional[str] = field(
        default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", "")
    )
    slack_bot_token: Optional[str] = field(
        default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", "")
    )
    discord_webhook_url: Optional[str] = field(
        default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", "")
    )

    # LLM Settings
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "mock").lower()
    )
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )

    # GitHub Settings
    github_token: Optional[str] = field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN", "")
    )
    github_repository: str = field(
        default_factory=lambda: os.getenv("GITHUB_REPOSITORY", "org/payments-service")
    )

    # Wispr Flow Settings
    wispr_flow_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("WISPR_FLOW_API_KEY", "")
    )
    wispr_auto_confirm: bool = field(
        default_factory=lambda: os.getenv("WISPR_AUTO_CONFIRM_VOICE", "true").lower() == "true"
    )

    # Server Settings
    host: str = field(
        default_factory=lambda: os.getenv("HOST", "127.0.0.1")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("PORT", "5000"))
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "true").lower() == "true"
    )

    @property
    def is_simulation(self) -> bool:
        return self.mode == "simulation"


def get_config() -> SwitchOpsConfig:
    """Returns singleton-style config instance."""
    return SwitchOpsConfig()
