"""Cuotas y federación."""

import uuid

from pydantic import BaseModel, Field


CUOTA_MESES_ORDEN = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]


class CuotaConfigIn(BaseModel):
    importe_mensual: float = Field(ge=0, le=99999)
    importe_federacion: float = Field(ge=0, le=99999)


class CuotaConfigOut(BaseModel):
    id_temporada: uuid.UUID
    importe_mensual: float
    importe_federacion: float


class CuotaMesEstado(BaseModel):
    mes: int
    pagado: bool


class CuotaJugadoraOut(BaseModel):
    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    dorsal: int | None = None
    federacion_pagada: bool = False
    meses: list[CuotaMesEstado] = []


class CuotaResumenOut(BaseModel):
    total_jugadoras: int = 0
    federacion_pagadas: int = 0
    federacion_pendientes: int = 0
    cuotas_pagadas: int = 0
    cuotas_pendientes: int = 0
    esperado_mensual: float = 0
    cobrado_mensual: float = 0
    esperado_federacion: float = 0
    cobrado_federacion: float = 0


class CuotasTemporadaOut(BaseModel):
    id_temporada: uuid.UUID
    temporada_nombre: str
    temporada_estado: str
    meses: list[int] = Field(default_factory=lambda: list(CUOTA_MESES_ORDEN))
    config: CuotaConfigOut
    jugadoras: list[CuotaJugadoraOut] = []
    resumen: CuotaResumenOut = Field(default_factory=CuotaResumenOut)
    solo_lectura: bool = False


class CuotaMensualPatch(BaseModel):
    id_jugador: uuid.UUID
    mes: int = Field(ge=1, le=12)
    pagado: bool


class FederacionPatch(BaseModel):
    id_jugador: uuid.UUID
    pagado: bool


class CuotaBulkIn(BaseModel):
    id_jugadores: list[uuid.UUID] = Field(min_length=1)
    accion: str = Field(
        pattern="^(limpiar|federacion_pagada|federacion_pendiente|cuotas_pagadas|cuotas_pendientes)$",
        description="cuotas_pagadas = marcar sep–jun como pagadas en la selección",
    )
