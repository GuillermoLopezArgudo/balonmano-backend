"""WebSocket en tiempo real por club."""

import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, joinedload

from app import models
from app.auth import parse_token_full, sesion_vigente
from app.database import SessionLocal
from app.realtime import club_hub

logger = logging.getLogger("siete.ws")


def _equipo_from_token(token: str, db: Session) -> models.Equipo | None:
    try:
        data = parse_token_full(token)
    except Exception:
        return None
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == data["id_equipo"])
        .first()
    )
    if not equipo:
        return None
    mid = data.get("id_miembro")
    if mid:
        miembro = (
            db.query(models.MiembroClub)
            .filter(
                models.MiembroClub.id_miembro == mid,
                models.MiembroClub.id_equipo == equipo.id_equipo,
                models.MiembroClub.estado == "activo",
            )
            .first()
        )
        if not miembro or not sesion_vigente(data, equipo, miembro):
            return None
    elif not sesion_vigente(data, equipo, None):
        return None
    return equipo


async def club_ws(websocket: WebSocket):
    token = websocket.query_params.get("token") or ""
    if not token:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        equipo = _equipo_from_token(token, db)
    finally:
        db.close()

    if not equipo:
        await websocket.close(code=4401)
        return

    eid = str(equipo.id_equipo)
    await club_hub.connect(eid, websocket)
    try:
        await websocket.send_json({"type": "connected", "id_equipo": eid})
        while True:
            msg = await websocket.receive_text()
            if msg in ("ping", '{"type":"ping"}'):
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("ws closed club=%s", eid, exc_info=True)
    finally:
        await club_hub.disconnect(eid, websocket)
