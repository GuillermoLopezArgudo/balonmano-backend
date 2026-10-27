"""Auditoría."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_audit: uuid.UUID
    accion: str
    resumen: str
    actor_nombre: str | None = None
    actor_correo: str | None = None
    entidad: str | None = None
    id_entidad: str | None = None
    detalle: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    creado_en: datetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int
    retention_days: int = 180
