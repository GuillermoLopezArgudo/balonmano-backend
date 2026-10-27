"""Jugadores."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class JugadorCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    fecha_nacimiento: date | None = None
    altura_cm: int | None = Field(default=None, ge=100, le=250)
    peso_kg: int | None = Field(default=None, ge=30, le=200)
    img_foto: str | None = Field(default=None, max_length=255)
    id_equipo: uuid.UUID | None = None
    dorsal: int = Field(ge=0, le=99)
    id_posicion: int | None = None
    fecha_alta: date | None = None
    activo: bool = True
    disponibilidad: str = Field(
        default="disponible",
        pattern="^(disponible|dudosa|lesion|sancion)$",
    )


class JugadorUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    apellido: str | None = Field(default=None, min_length=1, max_length=100)
    fecha_nacimiento: date | None = None
    altura_cm: int | None = Field(default=None, ge=100, le=250)
    peso_kg: int | None = Field(default=None, ge=30, le=200)
    img_foto: str | None = Field(default=None, max_length=255)
    dorsal: int | None = Field(default=None, ge=0, le=99)
    id_posicion: int | None = None
    activo: bool | None = None
    disponibilidad: str | None = Field(
        default=None,
        pattern="^(disponible|dudosa|lesion|sancion)$",
    )


class JugadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    fecha_nacimiento: date | None = None
    altura_cm: int | None = None
    peso_kg: int | None = None
    img_foto: str | None = Field(default=None, max_length=255)
    dorsal: int | None = None
    id_equipo: uuid.UUID | None = None
    equipo_nombre: str | None = None
    posiciones: list[str] = []
    id_posicion: int | None = None
    activo: bool = True
    disponibilidad: str = "disponible"
