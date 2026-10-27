"""Miembros del cuerpo técnico."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class MiembroCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    correo: str = Field(min_length=5, max_length=255)
    cargo: str = Field(default="Staff", max_length=100)
    estado: str = Field(default="pendiente", pattern="^(activo|pendiente|baja)$")


class MiembroUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    cargo: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, pattern="^(activo|pendiente|baja)$")


class MiembroOut(BaseModel):
    id_miembro: uuid.UUID
    id_equipo: uuid.UUID
    nombre: str
    correo: str
    cargo: str
    permiso: str
    estado: str
    tiene_acceso: bool = False
    invite_url: str | None = None

    model_config = ConfigDict(from_attributes=True)
