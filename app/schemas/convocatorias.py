"""Convocatorias y alineaciones."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


ZONA_CAMPO_PATTERN = (
    "^(portero|extremo_izq|lateral_izq|central|lateral_der|extremo_der|pivote)$"
)


class ConvocatoriaItemIn(BaseModel):
    id_jugador: uuid.UUID
    rol: str = Field(default="convocado", pattern="^(convocado|titular|banquillo)$")
    zona_campo: str | None = Field(default=None, pattern=ZONA_CAMPO_PATTERN)
    zona_ataque: str | None = Field(default=None, pattern=ZONA_CAMPO_PATTERN)
    zona_defensa: str | None = Field(default=None, pattern=ZONA_CAMPO_PATTERN)


class ConvocatoriaItemOut(BaseModel):
    id_jugador: uuid.UUID
    rol: str
    zona_campo: str | None = None
    zona_ataque: str | None = None
    zona_defensa: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    dorsal: int | None = None
    posiciones: list[str] = []


class ConvocatoriaOut(BaseModel):
    id_partido: uuid.UUID
    items: list[ConvocatoriaItemOut]
    estado: str = Field(default="borrador", pattern="^(borrador|guardada)$")


class ConvocatoriaPut(BaseModel):
    items: list[ConvocatoriaItemIn]
    estado: str = Field(default="borrador", pattern="^(borrador|guardada)$")


class AlineacionItemIn(BaseModel):
    id_jugador: uuid.UUID
    zona_campo: str = Field(pattern=ZONA_CAMPO_PATTERN)


class AlineacionItemOut(BaseModel):
    id_jugador: uuid.UUID
    zona_campo: str
    nombre: str | None = None
    apellido: str | None = None
    dorsal: int | None = None
    posiciones: list[str] = []


class AlineacionCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(default="ataque", pattern="^(ataque|defensa)$")
    items: list[AlineacionItemIn] = []


class AlineacionUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: str | None = Field(default=None, pattern="^(ataque|defensa)$")
    items: list[AlineacionItemIn] | None = None


class AlineacionOut(BaseModel):
    id_alineacion: uuid.UUID
    nombre: str
    tipo: str = "ataque"
    creado_en: datetime
    actualizado_en: datetime
    items: list[AlineacionItemOut] = []
