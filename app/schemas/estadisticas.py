"""Estadísticas de partido y acciones."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class EstadisticaJugadorCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    minutos_jugados: int = Field(default=0, ge=0, le=60)
    goles: int = Field(default=0, ge=0)
    lanzamientos: int = Field(default=0, ge=0)
    lanzamientos_fallados: int = Field(default=0, ge=0)
    asistencias: int = Field(default=0, ge=0)
    perdidas: int = Field(default=0, ge=0)
    recuperaciones: int = Field(default=0, ge=0)
    faltas_cometidas: int = Field(default=0, ge=0)
    faltas_recibidas: int = Field(default=0, ge=0)
    amarillas: int = Field(default=0, ge=0)
    exclusiones_2min: int = Field(default=0, ge=0)
    rojas: int = Field(default=0, ge=0)
    azules: int = Field(default=0, ge=0)


class EstadisticaJugadorOut(EstadisticaJugadorCreate):
    model_config = ConfigDict(from_attributes=True)

    id_estadistica: uuid.UUID


class EstadisticaLanzamientoCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    lanzamientos_6m: int = Field(default=0, ge=0)
    goles_6m: int = Field(default=0, ge=0)
    lanzamientos_9m: int = Field(default=0, ge=0)
    goles_9m: int = Field(default=0, ge=0)
    lanzamientos_7m: int = Field(default=0, ge=0)
    goles_7m: int = Field(default=0, ge=0)
    lanzamientos_extremo: int = Field(default=0, ge=0)
    goles_extremo: int = Field(default=0, ge=0)
    lanzamientos_contraataque: int = Field(default=0, ge=0)
    goles_contraataque: int = Field(default=0, ge=0)


class EstadisticaLanzamientoOut(EstadisticaLanzamientoCreate):
    model_config = ConfigDict(from_attributes=True)

    id_estadistica: uuid.UUID


class EstadisticaPorteroCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    minutos_jugados: int = Field(default=0, ge=0, le=60)
    lanzamientos_recibidos: int = Field(default=0, ge=0)
    paradas: int = Field(default=0, ge=0)
    goles_recibidos: int = Field(default=0, ge=0)
    lanzamientos_6m: int = Field(default=0, ge=0)
    paradas_6m: int = Field(default=0, ge=0)
    goles_6m: int = Field(default=0, ge=0)
    lanzamientos_9m: int = Field(default=0, ge=0)
    paradas_9m: int = Field(default=0, ge=0)
    goles_9m: int = Field(default=0, ge=0)
    lanzamientos_7m: int = Field(default=0, ge=0)
    paradas_7m: int = Field(default=0, ge=0)
    goles_7m: int = Field(default=0, ge=0)
    lanzamientos_extremo: int = Field(default=0, ge=0)
    paradas_extremo: int = Field(default=0, ge=0)
    goles_extremo: int = Field(default=0, ge=0)
    lanzamientos_contraataque: int = Field(default=0, ge=0)
    paradas_contraataque: int = Field(default=0, ge=0)
    goles_contraataque: int = Field(default=0, ge=0)


class EstadisticaPorteroOut(EstadisticaPorteroCreate):
    model_config = ConfigDict(from_attributes=True)

    id_estadistica: uuid.UUID


# Cómo se llega al lanzamiento (la zona sola no distingue la trayectoria).
CONTEXTOS_LLEGADA = frozenset({"entrada", "giro_izq", "giro_der", "punto_debil", "directo"})


# Causa de una pérdida.
CONTEXTOS_PERDIDA = frozenset({"falta_ataque", "pasos", "dobles", "mal_pase", "interceptado"})


class AccionCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    id_tipo_accion: int
    minuto: int = Field(ge=0, le=80)
    segundo: int = Field(default=0, ge=0, le=59)
    zona: str | None = Field(default=None, max_length=50)
    zona_porteria: str | None = Field(default=None, max_length=50)
    es_contraataque: bool = False
    contexto: str | None = Field(default=None, max_length=30)
    id_rival_jugador: uuid.UUID | None = None


class AccionUpdate(BaseModel):
    id_jugador: uuid.UUID | None = None
    id_tipo_accion: int | None = None
    minuto: int | None = Field(default=None, ge=0, le=80)
    segundo: int | None = Field(default=None, ge=0, le=59)
    zona: str | None = Field(default=None, max_length=50)
    zona_porteria: str | None = Field(default=None, max_length=50)
    es_contraataque: bool | None = None
    contexto: str | None = Field(default=None, max_length=30)
    id_rival_jugador: uuid.UUID | None = None


class AccionOut(AccionCreate):
    model_config = ConfigDict(from_attributes=True)

    id_accion: uuid.UUID
    rival_dorsal: int | None = None
    rival_nombre: str | None = None


class ResumenJugador(BaseModel):
    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    partidos: int
    goles: int
    asistencias: int
    lanzamientos: int
    perdidas: int = 0
    recuperaciones: int = 0
    faltas_cometidas: int = 0
    faltas_recibidas: int = 0
    amarillas: int = 0
    exclusiones_2min: int = 0
    rojas: int = 0
    azules: int = 0
    minutos_jugados: int
    pct_perdidas: float = 0.0
