"""
Switch Core Gateway Client: Connects directly with the sandbox-quantum/switch platform.
Supports live Room creation, dynamic agent dispatch, and message streaming.
Attempts live connection by default, with automatic fallback when the server is offline.
"""

import logging
import os
import time
import uuid
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger("switch_client")


class SwitchClient:
    """Client for connecting to the SandboxAQ Switch Core Gateway."""

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_simulation: bool = False
    ):
        self.gateway_url = (gateway_url or os.getenv("SWITCH_GATEWAY_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("SWITCH_API_KEY", "switch_demo_key")
        self.is_simulation = is_simulation
        self.is_live_connection = False
        self.simulated_rooms: Dict[str, Dict[str, Any]] = {}
        self.simulated_messages: Dict[str, List[Dict[str, Any]]] = {}

        # Test live connection
        if not self.is_simulation:
            self._probe_live_connection()

    def _probe_live_connection(self):
        try:
            resp = requests.get(
                f"{self.gateway_url}/healthz",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=2
            )
            if resp.status_code == 200:
                self.is_live_connection = True
                logger.info(f"[SwitchClient] Connected to live Switch Gateway at {self.gateway_url}")
        except Exception:
            self.is_live_connection = False

    def create_room(self, name: str, topic: str, agents: List[str]) -> Dict[str, Any]:
        """Creates a collaborative Switch Room for an incident."""
        room_id = f"room_{uuid.uuid4().hex[:8]}"
        payload = {"name": name, "topic": topic, "agents": agents}

        if not self.is_simulation:
            try:
                resp = requests.post(
                    f"{self.gateway_url}/api/v1/rooms",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=4
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    self.is_live_connection = True
                    return data
            except Exception as e:
                logger.info(f"[SwitchClient] Live Switch Gateway at {self.gateway_url} not responsive ({e}); using local room store.")

        # Local fallback store
        room = {
            "id": room_id,
            "name": name,
            "topic": topic,
            "agents": agents,
            "created_at": time.time(),
            "status": "ACTIVE",
            "is_live_switch": self.is_live_connection,
        }
        self.simulated_rooms[room_id] = room
        self.simulated_messages[room_id] = []
        return room

    def send_message(
        self,
        room_id: str,
        sender: str,
        text: str,
        role: str = "agent",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Sends a message or rich card into a Switch Room."""
        msg = {
            "id": f"msg_{uuid.uuid4().hex[:6]}",
            "room_id": room_id,
            "sender": sender,
            "role": role,
            "text": text,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

        if not self.is_simulation:
            try:
                resp = requests.post(
                    f"{self.gateway_url}/api/v1/rooms/{room_id}/messages",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=msg,
                    timeout=4
                )
                if resp.status_code in (200, 201):
                    self.is_live_connection = True
                    return resp.json()
            except Exception as e:
                logger.debug(f"[SwitchClient] Live message dispatch failed ({e}); recorded in local room.")

        if room_id not in self.simulated_messages:
            self.simulated_messages[room_id] = []
        self.simulated_messages[room_id].append(msg)
        return msg

    def get_room_messages(self, room_id: str) -> List[Dict[str, Any]]:
        """Retrieves conversation history from a Switch Room."""
        if not self.is_simulation:
            try:
                resp = requests.get(
                    f"{self.gateway_url}/api/v1/rooms/{room_id}/messages",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=4
                )
                if resp.status_code == 200:
                    self.is_live_connection = True
                    return resp.json().get("messages", [])
            except Exception:
                pass

        return self.simulated_messages.get(room_id, [])
