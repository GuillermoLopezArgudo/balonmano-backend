"""Partidos y rivales."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PartidoCreate(BaseModel):
    """Crea un partido del club autenticado contra un rival propio."""

    id_rival: uuid.UUID
    es_local: bool = True
    id_temporada: uuid.UUID
    fecha: datetime
    jornada: int | None = Field(default=None, ge=1)
    pabellon: str | None = Field(default=None, max_length=200)
    competicion: str | None = Field(default=None, max_length=100)
    goles_local: int = Field(default=0, ge=0)
    goles_visitante: int = Field(default=0, ge=0)
    estado: str = Field(
        default="programado", pattern="^(programado|aplazado|jugado|sin_resultado)$"
    )


class PartidoUpdate(BaseModel):
    id_rival: uuid.UUID | None = None
    es_local: bool | None = None
    goles_local: int | None = Field(default=None, ge=0)
    goles_visitante: int | None = Field(default=None, ge=0)
    jornada: int | None = Field(default=None, ge=1)
    fecha: datetime | None = None
    pabellon: str | None = Field(default=None, max_length=200)
    competicion: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(
        default=None, pattern="^(programado|aplazado|jugado|sin_resultado)$"
    )


class PartidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_partido: uuid.UUID
    id_equipo_local: uuid.UUID | None = None
    id_equipo_visitante: uuid.UUID | None = None
    id_equipo: uuid.UUID | None = None
    id_rival: uuid.UUID | None = None
    es_local: bool | None = None
    id_temporada: uuid.UUID
    fecha: datetime
    jornada: int | None = None
    pabellon: str | None = None
    competicion: str | None = None
    goles_local: int
    goles_visitante: int
    estado: str = "programado"
    equipo_local_nombre: str | None = None
    equipo_visitante_nombre: str | None = None
    temporada_nombre: str | None = None
    temporada_estado: str | None = None


class RivalCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)


class RivalUpdate(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)


class RivalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_rival: uuid.UUID
    id_equipo: uuid.UUID
    nombre: str


class RivalJugadorCreate(BaseModel):
    dorsal: int = Field(ge=0, le=99)
    nombre: str | None = Field(default=None, max_length=120)


class RivalJugadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_rival_jugador: uuid.UUID
    id_rival: uuid.UUID
    dorsal: int
    nombre: str | None = None
    activo: bool = True


class RivalGoleadoraOut(BaseModel):
    id_rival_jugador: uuid.UUID | None = None
    dorsal: int | None = None
    nombre: str | None = None
    goles: int
    zona_top: str | None = None
    zona_top_label: str | None = None
    zonas: dict[str, int] = {}
