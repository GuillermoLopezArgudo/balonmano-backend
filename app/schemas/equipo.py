"""Equipos, cuenta, temporadas y catálogos."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import PasswordNueva


class DatosEquipoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    nombre_corto: str | None = Field(default=None, max_length=80)
    entrenador_nombre: str | None = Field(default=None, max_length=150)
    codigo_federativo: str | None = Field(default=None, max_length=40)
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)
    pabellon: str | None = Field(default=None, max_length=200)
    img_escudo: str | None = Field(default=None, max_length=255)


class DatosEquipoOut(DatosEquipoIn):
    model_config = ConfigDict(from_attributes=True)

    id_equipo: uuid.UUID


class DatosEquipoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    nombre_corto: str | None = Field(default=None, max_length=80)
    entrenador_nombre: str | None = Field(default=None, max_length=150)
    codigo_federativo: str | None = Field(default=None, max_length=40)
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)
    pabellon: str | None = Field(default=None, max_length=200)
    img_escudo: str | None = Field(default=None, max_length=255)


class EquipoCreate(BaseModel):
    correo: str = Field(min_length=3, max_length=255)
    password: PasswordNueva
    datos: DatosEquipoIn


class EquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_equipo: uuid.UUID
    correo: str
    datos: DatosEquipoOut | None = None


class CuentaUpdate(BaseModel):
    correo: str | None = Field(default=None, min_length=3, max_length=255)
    # actual puede ser corta (cuentas legacy); la nueva exige 8+
    password_actual: str | None = Field(default=None, min_length=1, max_length=128)
    password_nueva: PasswordNueva | None = None
    nombre_display: str | None = Field(default=None, max_length=150)
    entrenador_nombre: str | None = Field(default=None, max_length=150)


class TemporadaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    fecha_inicio: date
    fecha_fin: date
    activar: bool = True


class TemporadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_temporada: uuid.UUID
    nombre: str
    fecha_inicio: date
    fecha_fin: date
    estado: str = "activa"
    cerrada_en: datetime | None = None
    pendientes: int = 0


class TemporadaAbrir(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    fecha_inicio: date
    fecha_fin: date
    cerrar_anterior: bool = True


class EquipoTemporadaCreate(BaseModel):
    id_equipo: uuid.UUID
    id_temporada: uuid.UUID
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)


class EquipoTemporadaOut(EquipoTemporadaCreate):
    model_config = ConfigDict(from_attributes=True)


class PosicionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_posicion: int
    nombre: str


class TipoAccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tipo_accion: int
    nombre: str
