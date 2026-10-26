"""Registro de auditoría: accesos y mutaciones por club."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app import models

RETENTION_DAYS = 180

# Rutas que no deben generar ruido (health, lecturas de sesión, etc.)
_SKIP_PREFIXES = (
    "/api/health",
    "/api/ws",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/sesion",
    "/api/auth/me",  # incluye /me/password (se registra en el endpoint)
    "/api/auditoria",
)

_LABELS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^/api/auth/registro$"), "auth.registro", "Registro de club"),
    (re.compile(r"^/api/auth/aceptar-invitacion$"), "auth.invitar_aceptar", "Aceptó invitación"),
    (re.compile(r"^/api/auth/me/password$"), "auth.password", "Cambió contraseña"),
    (re.compile(r"^/api/auth/logout$"), "auth.logout", "Cierre de sesión"),
    (re.compile(r"^/api/auth/me(/datos|/perfil)?$"), "auth.perfil", "Actualizó perfil / club"),
    (re.compile(r"^/api/miembros/?$"), "miembro.invitar", "Invitó / creó miembro"),
    (re.compile(r"^/api/miembros/[^/]+/reinvitar$"), "miembro.reinvitar", "Reenvió invitación"),
    (re.compile(r"^/api/miembros/[^/]+/hacer-administrador$"), "miembro.admin", "Nombró administrador"),
    (re.compile(r"^/api/miembros/[^/]+$"), "miembro.editar", "Editó / eliminó miembro"),
    (re.compile(r"^/api/jugadores/?$"), "jugador.crear", "Creó jugadora"),
    (re.compile(r"^/api/jugadores/[^/]+$"), "jugador.editar", "Editó / eliminó jugadora"),
    (re.compile(r"^/api/partidos/?$"), "partido.crear", "Creó partido"),
    (re.compile(r"^/api/partidos/[^/]+$"), "partido.editar", "Editó / eliminó partido"),
    (re.compile(r"^/api/convocatorias/"), "convocatoria.guardar", "Guardó convocatoria"),
    (re.compile(r"^/api/cuotas/"), "cuotas.editar", "Actualizó cuotas / federación"),
    (re.compile(r"^/api/temporadas/"), "temporada.gestionar", "Gestionó temporada"),
    (re.compile(r"^/api/rivales/"), "rival.gestionar", "Gestionó rival"),
    (re.compile(r"^/api/jugadas/"), "jugada.gestionar", "Gestionó jugada"),
    (re.compile(r"^/api/preparaciones/"), "preparacion.gestionar", "Gestionó preparación física"),
    (re.compile(r"^/api/asistencias/"), "asistencia.gestionar", "Gestionó asistencia"),
    (re.compile(r"^/api/alineaciones/"), "alineacion.gestionar", "Gestionó alineación"),
    (re.compile(r"^/api/uploads/"), "upload", "Subió archivo"),
    (re.compile(r"^/api/estadisticas/acciones"), "directo.accion", "Acción en directo"),
    (re.compile(r"^/api/estadisticas/"), "estadistica.gestionar", "Actualizó estadísticas"),
]


def client_meta(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else None)
    ua = (request.headers.get("user-agent") or "")[:400] or None
    return ip, ua


def describe_path(method: str, path: str) -> tuple[str, str]:
    path = path.split("?")[0]
    for pattern, codigo, label in _LABELS:
        if pattern.search(path):
            verb = {
                "POST": "Creó",
                "PUT": "Guardó",
                "PATCH": "Actualizó",
                "DELETE": "Eliminó",
            }.get(method.upper(), method)
            # Prefer specific label; tweak delete
            if method.upper() == "DELETE" and "Editó / eliminó" in label:
                label = label.replace("Editó / eliminó", "Eliminó")
            elif method.upper() == "PATCH" and "Editó / eliminó" in label:
                label = label.replace("Editó / eliminó", "Editó")
            elif method.upper() == "POST" and codigo.endswith(".editar"):
                pass
            return codigo, label
    return f"http.{method.lower()}", f"{method} {path}"


def should_skip_path(path: str) -> bool:
    path = path.split("?")[0]
    return any(path.startswith(p) for p in _SKIP_PREFIXES)


def _detalle_json(detalle: Any) -> str | None:
    if detalle is None:
        return None
    if isinstance(detalle, str):
        return detalle[:2000]
    try:
        return json.dumps(detalle, ensure_ascii=False, default=str)[:2000]
    except TypeError:
        return str(detalle)[:2000]


def log_audit(
    db: Session,
    *,
    id_equipo: uuid.UUID | None,
    accion: str,
    resumen: str,
    id_miembro: uuid.UUID | None = None,
    actor_nombre: str | None = None,
    actor_correo: str | None = None,
    entidad: str | None = None,
    id_entidad: str | None = None,
    detalle: Any = None,
    ip: str | None = None,
    user_agent: str | None = None,
    commit: bool = False,
) -> models.AuditLog | None:
    """Escribe una fila de auditoría. Nunca lanza: no debe romper la petición."""
    if id_equipo is None:
        return None
    try:
        row = models.AuditLog(
            id_equipo=id_equipo,
            id_miembro=id_miembro,
            actor_nombre=(actor_nombre or "")[:150] or None,
            actor_correo=(actor_correo or "").strip().lower()[:255] or None,
            accion=(accion or "evento")[:80],
            resumen=(resumen or accion)[:300],
            entidad=(entidad or None) and str(entidad)[:80],
            id_entidad=(id_entidad or None) and str(id_entidad)[:80],
            detalle=_detalle_json(detalle),
            ip=(ip or None) and str(ip)[:64],
            user_agent=(user_agent or None) and str(user_agent)[:400],
            creado_en=datetime.utcnow(),
        )
        db.add(row)
        if commit:
            db.commit()
        else:
            db.flush()
        return row
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None


def actor_from_session(session) -> dict:
    m = getattr(session, "miembro", None)
    equipo = getattr(session, "equipo", None)
    if m:
        return {
            "id_miembro": m.id_miembro,
            "actor_nombre": m.nombre,
            "actor_correo": m.correo,
        }
    return {
        "id_miembro": None,
        "actor_nombre": "Cuenta del club",
        "actor_correo": getattr(equipo, "correo", None) if equipo else None,
    }


def purge_old(db: Session, *, id_equipo: uuid.UUID | None = None) -> int:
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    q = db.query(models.AuditLog).filter(models.AuditLog.creado_en < cutoff)
    if id_equipo:
        q = q.filter(models.AuditLog.id_equipo == id_equipo)
    n = q.delete(synchronize_session=False)
    return int(n or 0)
