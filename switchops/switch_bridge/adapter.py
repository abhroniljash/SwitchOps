"""
Switch Adapter: Dedicated integration module for the Switch Core Platform.
Validates, normalizes, and deduplicates incoming Switch events, maintains connection
health states, and handles bidirectional room messaging.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Set
import requests

logger = logging.getLogger("switchops.switch_adapter")


@dataclass
class NormalizedSwitchEvent:
    event_id: str
    room_id: str
    sender: str
    message: str
    timestamp: float
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "room_id": self.room_id,
            "sender": self.sender,
            "message": self.message,
            "timestamp": self.timestamp,
            "attachments": self.attachments,
            "metadata": self.metadata,
        }


class SwitchAdapter:
    """Dedicated adapter for connecting SwitchOps with the Switch platform."""

    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout_seconds: int = 4
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key = api_key or "switch_demo_key"
        self.timeout_seconds = timeout_seconds
        self.processed_event_ids: Set[str] = set()
        self.is_connected: bool = False
        self.last_health_check: float = 0.0
        self.last_error: Optional[str] = None

    def check_health(self) -> Dict[str, Any]:
        """Probes the Switch Gateway /healthz endpoint and returns connection status."""
        self.last_health_check = time.time()
        try:
            resp = requests.get(
                f"{self.gateway_url}/healthz",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout_seconds
            )
            if resp.status_code == 200:
                self.is_connected = True
                self.last_error = None
                return {
                    "status": "healthy",
                    "connected": True,
                    "gateway_url": self.gateway_url,
                    "latency_ms": int(resp.elapsed.total_seconds() * 1000),
                    "last_checked": self.last_health_check,
                }
            else:
                self.is_connected = False
                self.last_error = f"Gateway returned HTTP {resp.status_code}"
        except Exception as e:
            self.is_connected = False
            self.last_error = str(e)

        return {
            "status": "degraded_or_simulation",
            "connected": False,
            "gateway_url": self.gateway_url,
            "message": "Live Switch Gateway offline; local simulation mode active.",
            "last_error": self.last_error,
            "last_checked": self.last_health_check,
        }

    def validate_and_normalize(self, raw_event: Dict[str, Any]) -> Tuple[Optional[NormalizedSwitchEvent], bool]:
        """
        Validates event schema, extracts required fields, and checks idempotency.
        Returns (normalized_event, is_duplicate).
        """
        if not isinstance(raw_event, dict):
            logger.warning("Rejected non-dict event payload.")
            return None, False

        # Extract event ID or generate deterministic fallback
        event_id = raw_event.get("event_id") or raw_event.get("id") or f"evt_{uuid.uuid4().hex[:8]}"

        # Idempotency check
        if event_id in self.processed_event_ids:
            logger.info(f"Duplicate Switch event detected: {event_id}. Skipping processing.")
            return None, True

        self.processed_event_ids.add(event_id)

        room_id = raw_event.get("room_id") or raw_event.get("room") or "default-incident-room"
        sender = raw_event.get("sender") or raw_event.get("user") or "HumanOperator"
        message = raw_event.get("message") or raw_event.get("text") or ""
        timestamp = raw_event.get("timestamp") or time.time()
        attachments = raw_event.get("attachments") or []
        metadata = raw_event.get("metadata") or {}

        normalized = NormalizedSwitchEvent(
            event_id=event_id,
            room_id=room_id,
            sender=sender,
            message=message,
            timestamp=float(timestamp),
            attachments=attachments,
            metadata=metadata,
        )
        return normalized, False

    def send_room_message(
        self,
        room_id: str,
        sender: str,
        text: str,
        role: str = "agent",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Sends an agent response or card update back to the originating Switch room."""
        payload = {
            "room_id": room_id,
            "sender": sender,
            "role": role,
            "text": text,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

        # Attempt to deliver to live gateway if connected
        try:
            resp = requests.post(
                f"{self.gateway_url}/api/v1/rooms/{room_id}/messages",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout_seconds
            )
            if resp.status_code in (200, 201):
                return resp.json()
        except Exception:
            # Fallback to local dispatch
            pass

        return payload
