import base64
import json
import os
from uuid import UUID

import httpx


class TelnyxCallService:
    _BASE = "https://api.telnyx.com/v2"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {os.environ['TELNYX_API_KEY']}",
            "Content-Type": "application/json",
        }

    async def create_outbound_call(
        self,
        to_number: str,
        from_number: str,
        session_id: UUID,
        leg: str,
    ) -> None:
        client_state = base64.b64encode(
            json.dumps({"session_id": str(session_id), "leg": leg}).encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._BASE}/calls",
                headers=self._headers(),
                json={
                    "to": to_number,
                    "from": from_number,
                    "connection_id": os.environ["TELNYX_CONNECTION_ID"],
                    "client_state": client_state,
                },
            )
            response.raise_for_status()

    async def bridge_calls(
        self, call_control_id: str, target_call_control_id: str
    ) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._BASE}/calls/{call_control_id}/actions/bridge",
                headers=self._headers(),
                json={"call_control_id": target_call_control_id},
            )
            response.raise_for_status()

    async def hangup_call(self, call_control_id: str) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._BASE}/calls/{call_control_id}/actions/hangup",
                headers=self._headers(),
            )
            response.raise_for_status()

    async def start_playback(self, call_control_id: str) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._BASE}/calls/{call_control_id}/actions/playback_start",
                headers=self._headers(),
                json={
                    "audio_url": "https://uncabled-zina-fusilly.ngrok-free.dev/static/test.mp3"
                },
            )
            response.raise_for_status()
