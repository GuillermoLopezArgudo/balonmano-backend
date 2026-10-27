"""Jugadas (pizarra multipaso)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class JugadaPosicionIn(BaseModel):
    id_pieza: uuid.UUID
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class JugadaFlechaIn(BaseModel):
    id_pieza: uuid.UUID
    x1: float = Field(ge=0, le=100)
    y1: float = Field(ge=0, le=100)
    x2: float = Field(ge=0, le=100)
    y2: float = Field(ge=0, le=100)
    tipo: str = Field(default="movimiento", pattern="^(movimiento|pase|lanzamiento)$")


class JugadaPiezaIn(BaseModel):
    id_pieza: uuid.UUID | None = None
    etiqueta: str = Field(min_length=1, max_length=40)
    color: str | None = Field(default=None, max_length=20)
    id_jugador: uuid.UUID | None = None
    orden: int = Field(default=0, ge=0, le=30)


class JugadaPasoIn(BaseModel):
    id_paso: uuid.UUID | None = None
    orden: int = Field(ge=0, le=200)
    titulo: str | None = Field(default=None, max_length=80)
    balon_x: float | None = Field(default=None, ge=0, le=100)
    balon_y: float | None = Field(default=None, ge=0, le=100)
    id_pieza_balon: uuid.UUID | None = None
    posiciones: list[JugadaPosicionIn] = []
    flechas: list[JugadaFlechaIn] = []


class JugadaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    fase: str = Field(default="ataque", pattern="^(ataque|defensa|completo)$")
    ambito: str = Field(default="tactica", pattern="^(tactica|fisico)$")
    descripcion: str | None = Field(default=None, max_length=4000)
    fecha_sesion: datetime | None = None
    piezas: list[JugadaPiezaIn] = []
    pasos: list[JugadaPasoIn] = []


class JugadaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    fase: str | None = Field(default=None, pattern="^(ataque|defensa|completo)$")
    ambito: str | None = Field(default=None, pattern="^(tactica|fisico)$")
    descripcion: str | None = Field(default=None, max_length=4000)
    fecha_sesion: datetime | None = None
    piezas: list[JugadaPiezaIn] | None = None
    pasos: list[JugadaPasoIn] | None = None


class JugadaPosicionOut(BaseModel):
    id_pieza: uuid.UUID
    x: float
    y: float


class JugadaFlechaOut(BaseModel):
    id_flecha: uuid.UUID
    id_pieza: uuid.UUID
    x1: float
    y1: float
    x2: float
    y2: float
    tipo: str = "movimiento"


class JugadaPiezaOut(BaseModel):
    id_pieza: uuid.UUID
    etiqueta: str
    color: str | None = None
    id_jugador: uuid.UUID | None = None
    orden: int = 0


class JugadaPasoOut(BaseModel):
    id_paso: uuid.UUID
    orden: int
    titulo: str | None = None
    balon_x: float | None = None
    balon_y: float | None = None
    id_pieza_balon: uuid.UUID | None = None
    posiciones: list[JugadaPosicionOut] = []
    flechas: list[JugadaFlechaOut] = []


class JugadaListOut(BaseModel):
    id_jugada: uuid.UUID
    nombre: str
    fase: str
    ambito: str = "tactica"
    descripcion: str | None = None
    fecha_sesion: datetime | None = None
    num_pasos: int = 0
    num_piezas: int = 0
    creado_en: datetime
    actualizado_en: datetime


class JugadaOut(BaseModel):
    id_jugada: uuid.UUID
    nombre: str
    fase: str
    ambito: str = "tactica"
    descripcion: str | None = None
    fecha_sesion: datetime | None = None
    creado_en: datetime
    actualizado_en: datetime
    piezas: list[JugadaPiezaOut] = []
    pasos: list[JugadaPasoOut] = []


class JugadaCopiarIn(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
