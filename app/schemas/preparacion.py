"""Preparación física."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


_PREP_TIPO = (
    "^(fuerza|resistencia|potencia|movilidad|prevencion|prepartido|recuperacion|otro)$"
)


_PREP_INTENSIDAD = "^(baja|media|alta)$"


class PreparacionFisicaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(default="fuerza", pattern=_PREP_TIPO)
    objetivo: str | None = Field(default=None, max_length=300)
    contenido: str | None = Field(default=None, max_length=20000)
    duracion_min: int | None = Field(default=None, ge=1, le=600)
    intensidad: str | None = Field(default=None, pattern=_PREP_INTENSIDAD)


class PreparacionFisicaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: str | None = Field(default=None, pattern=_PREP_TIPO)
    objetivo: str | None = Field(default=None, max_length=300)
    contenido: str | None = Field(default=None, max_length=20000)
    duracion_min: int | None = Field(default=None, ge=1, le=600)
    intensidad: str | None = Field(default=None, pattern=_PREP_INTENSIDAD)


class PreparacionFisicaOut(BaseModel):
    id_preparacion: uuid.UUID
    nombre: str
    tipo: str
    objetivo: str | None = None
    contenido: str | None = None
    duracion_min: int | None = None
    intensidad: str | None = None
    creado_en: datetime
    actualizado_en: datetime
