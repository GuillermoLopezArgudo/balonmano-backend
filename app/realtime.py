"""Pub/sub in-memory por club (un proceso / un worker)."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger("siete.realtime")

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    global _main_loop
    _main_loop = loop


class ClubHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, id_equipo: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[id_equipo].add(ws)
        logger.debug("ws connect club=%s n=%s", id_equipo, len(self._rooms[id_equipo]))

    async def disconnect(self, id_equipo: str, ws: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(id_equipo)
            if not room:
                return
            room.discard(ws)
            if not room:
                self._rooms.pop(id_equipo, None)

    async def broadcast(self, id_equipo: str, event: dict[str, Any]) -> None:
        async with self._lock:
            peers = list(self._rooms.get(id_equipo, ()))
        dead: list[WebSocket] = []
        for ws in peers:
            if ws.client_state != WebSocketState.CONNECTED:
                dead.append(ws)
                continue
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(id_equipo, ws)


club_hub = ClubHub()


def publish_club(id_equipo: UUID | str, event: dict[str, Any]) -> None:
    """Llamar desde rutas sync: encola el broadcast en el loop principal."""
    eid = str(id_equipo)
    loop = _main_loop
    if loop is None or not loop.is_running():
        logger.debug("publish_club sin loop activo: %s", event.get("type"))
        return
    try:
        asyncio.run_coroutine_threadsafe(club_hub.broadcast(eid, event), loop)
    except Exception:
        logger.exception("publish_club falló")
