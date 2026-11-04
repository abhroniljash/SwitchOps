"""
Switch Core Gateway Client: Connects directly with the sandbox-quantum/switch platform.
Supports Room creation, dynamic agent dispatch, and message streaming.
"""

import logging
import time
import uuid
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger("switch_client")


class SwitchClient:
    """Client for the SandboxAQ Switch Core Gateway."""

    def __init__(self, gateway_url: str = "http://localhost:8000", api_key: str = "demo_key", is_simulation: bool = True):
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key = api_key
        self.is_simulation = is_simulation
        self.simulated_rooms: Dict[str, Dict[str, Any]] = {}
        self.simulated_messages: Dict[str, List[Dict[str, Any]]] = {}

    def create_room(self, name: str, topic: str, agents: List[str]) -> Dict[str, Any]:
        """Creates a collaborative Switch Room for an incident."""
        room_id = f"room_{uuid.uuid4().hex[:8]}"

        if self.is_simulation:
            room = {
                "id": room_id,
                "name": name,
                "topic": topic,
                "agents": agents,
                "created_at": time.time(),
                "status": "ACTIVE",
            }
            self.simulated_rooms[room_id] = room
            self.simulated_messages[room_id] = []
            return room

        try:
            resp = requests.post(
                f"{self.gateway_url}/api/v1/rooms",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"name": name, "topic": topic, "agents": agents},
                timeout=5
            )
            if resp.status_code in (200, 201):
                return resp.json()
        except Exception as e:
            logger.warning(f"Failed to reach live Switch Gateway ({e}); falling back to local simulation.")

        # Fallback simulation
        room = {
            "id": room_id,
            "name": name,
            "topic": topic,
            "agents": agents,
            "created_at": time.time(),
            "status": "ACTIVE",
        }
        self.simulated_rooms[room_id] = room
        self.simulated_messages[room_id] = []
        return room

    def send_message(self, room_id: str, sender: str, text: str, role: str = "agent", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

        if self.is_simulation:
            if room_id not in self.simulated_messages:
                self.simulated_messages[room_id] = []
            self.simulated_messages[room_id].append(msg)
            return msg

        try:
            resp = requests.post(
                f"{self.gateway_url}/api/v1/rooms/{room_id}/messages",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=msg,
                timeout=5
            )
            if resp.status_code in (200, 201):
                return resp.json()
        except Exception as e:
            logger.warning(f"Error posting to live Switch Gateway: {e}")

        if room_id not in self.simulated_messages:
            self.simulated_messages[room_id] = []
        self.simulated_messages[room_id].append(msg)
        return msg

    def get_room_messages(self, room_id: str) -> List[Dict[str, Any]]:
        """Retrieves conversation history from a Switch Room."""
        if self.is_simulation or room_id in self.simulated_messages:
            return self.simulated_messages.get(room_id, [])

        try:
            resp = requests.get(
                f"{self.gateway_url}/api/v1/rooms/{room_id}/messages",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json().get("messages", [])
        except Exception:
            pass

        return self.simulated_messages.get(room_id, [])
