"""
Deepgram streaming STT client — MVP test only.

Connects to Deepgram's WebSocket API and streams mulaw 8000 Hz audio directly
(Deepgram supports mulaw natively, no PCM conversion needed).
Partial and final transcripts are printed to logs.
"""

import asyncio
import json
import logging
import os

import websockets

logger = logging.getLogger(__name__)

_DEEPGRAM_WS_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=linear16"
    "&sample_rate=8000"
    "&channels=1"
    "&model=nova-2"
    "&language=bg"
    "&interim_results=true"
    "&endpointing=300"
)


class DeepgramStreamClient:
    """Manages a single streaming STT session with Deepgram."""

    def __init__(self) -> None:
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._recv_task: asyncio.Task | None = None

    async def connect(self) -> None:
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        logger.info("STT_AUTH deepgram key present: %s", bool(api_key))
        logger.info("STT_AUTH deepgram key length: %s", len(api_key) if api_key else None)
        if not api_key:
            raise RuntimeError("DEEPGRAM_API_KEY is not set")
        self._ws = await websockets.connect(
            _DEEPGRAM_WS_URL,
            extra_headers={"Authorization": f"Token {api_key}"},
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        logger.info("STT connected to Deepgram")

    async def send_audio(self, mulaw_bytes: bytes) -> None:
        """Push a raw mulaw audio chunk to Deepgram."""
        if self._ws is not None:
            try:
                await self._ws.send(mulaw_bytes)
            except Exception as exc:
                logger.warning("[STT_DG] failed to send audio: %s", exc)

    async def _recv_loop(self) -> None:
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning("[STT_DG] non-JSON message from Deepgram: %s", message[:200])
                    continue

                msg_type = data.get("type")

                if msg_type != "Results":
                    logger.info("[STT_DG] non-transcript event: %s", msg_type)
                    continue

                alts = data.get("channel", {}).get("alternatives", [])
                if not alts:
                    continue

                transcript = alts[0].get("transcript", "").strip()
                confidence = alts[0].get("confidence", 0.0)
                is_final = data.get("is_final", False)

                if transcript:
                    logger.info(
                        "[STT_DG] %s transcript: '%s' (conf=%.2f)",
                        "FINAL" if is_final else "PARTIAL",
                        transcript,
                        confidence,
                    )

                else:
                    logger.info("[STT_DG] Results received but transcript is empty (silence/noise)")

        except websockets.exceptions.ConnectionClosed as exc:
            logger.warning("[STT_DG] Deepgram connection closed: %s", exc)
        except Exception as exc:
            logger.warning("[STT_DG] recv loop error: %s", exc)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._recv_task is not None:
            self._recv_task.cancel()
            self._recv_task = None
        logger.info("STT_DISCONNECTED deepgram websocket closed")
