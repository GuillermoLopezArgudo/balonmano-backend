"""Sesiones de entrenamiento y asistencia."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SesionEntrenamientoCreate(BaseModel):
    fecha: datetime
    notas: str | None = Field(default=None, max_length=2000)


class SesionEntrenamientoUpdate(BaseModel):
    fecha: datetime | None = None
    notas: str | None = Field(default=None, max_length=2000)


class SesionEntrenamientoListOut(BaseModel):
    id_sesion: uuid.UUID
    fecha: datetime
    notas: str | None = None
    presentes: int = 0
    faltas: int = 0
    justificadas: int = 0
    marcadas: int = 0


class SesionAsistenciaItemIn(BaseModel):
    id_jugador: uuid.UUID
    estado: str = Field(pattern="^(presente|falta|justificada)$")


class SesionAsistenciaPutIn(BaseModel):
    items: list[SesionAsistenciaItemIn] = []


class SesionAsistenciaItemOut(BaseModel):
    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    dorsal: int | None = None
    estado: str | None = None  # None = sin marcar


class SesionEntrenamientoDetalleOut(BaseModel):
    id_sesion: uuid.UUID
    fecha: datetime
    notas: str | None = None
    items: list[SesionAsistenciaItemOut] = []
    presentes: int = 0
    faltas: int = 0
    justificadas: int = 0
